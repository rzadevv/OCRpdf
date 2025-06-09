#!/usr/bin/env python3
# Takes scanned PDFs and makes them searchable using OCR
# Basically converts images in PDFs to text that you can search/copy

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import pytesseract  # does the actual OCR magic
import fitz  # PyMuPDF - handles PDF stuff without needing poppler
from PIL import Image
from PyPDF2 import PdfWriter, PdfReader  # for combining pages back into PDF
from tqdm import tqdm  # progress bars

from error_handlers import (
    PdfOcrError, InputFileError, TesseractError, OutputError,
    verify_tesseract_installed, verify_pymupdf_installed,
    verify_input_file, verify_output_location
)


class PdfOcr:
    def __init__(self, dpi: int = 300, language: str = "eng", optimize_size: bool = True):
        self.dpi = dpi
        self.language = language
        self.optimize_size = optimize_size

        # if optimizing, use lower DPI for OCR (200 is plenty for text recognition)
        # but keep original DPI for display quality
        self.ocr_dpi = min(dpi, 200) if optimize_size else dpi

        # make sure we have the tools we need
        verify_tesseract_installed()
        verify_pymupdf_installed()
    
    def process_file(self, input_path: str, output_path: Optional[str] = None) -> str:
        # check that the input file exists and is actually a PDF
        verify_input_file(input_path)

        input_path = Path(input_path)

        # if no output name given, just add "_searchable" to the original name
        if not output_path:
            output_path = str(input_path.parent / f"{input_path.stem}_searchable.pdf")

        # make sure we can write to the output location
        verify_output_location(output_path)

        print(f"Processing: {input_path}")
        print(f"Output will be saved to: {output_path}")

        try:
            # use a temp folder for all the intermediate files
            with tempfile.TemporaryDirectory() as temp_dir:
                # step 1: turn PDF pages into image files
                print("Converting PDF to images...")
                images = self._convert_pdf_to_images(str(input_path), temp_dir)

                # step 2: run OCR on each image and make mini PDFs
                print(f"Performing OCR on {len(images)} pages...")
                pdf_writer = PdfWriter()

                for i, image_path in enumerate(tqdm(images, desc="OCR Processing")):
                    # OCR this page and save as a small PDF
                    searchable_page_path = os.path.join(temp_dir, f"searchable_page_{i}.pdf")
                    self._ocr_page(image_path, searchable_page_path)

                    # add this page to our final PDF
                    pdf_reader = PdfReader(searchable_page_path)
                    if len(pdf_reader.pages) > 0:
                        pdf_writer.append(pdf_reader)
                    else:
                        print(f"Warning: OCR produced empty page for page {i+1}")

                # step 3: save the combined PDF
                with open(output_path, 'wb') as output_file:
                    pdf_writer.write(output_file)

                # step 4: compress it to make the file smaller
                if self.optimize_size:
                    self._compress_pdf(output_path)
            
            print(f"Successfully created searchable PDF: {output_path}")
            return output_path
            
        except Exception as e:
            if not isinstance(e, PdfOcrError):
                # Convert generic exceptions to PdfOcrError
                e = PdfOcrError(f"Error processing file {input_path}: {str(e)}")
            raise e
    
    def process_batch(self, input_paths: List[str], output_dir: Optional[str] = None) -> List[str]:
        """
        Process multiple PDF files in batch
        
        Args:
            input_paths: List of paths to input PDF files
            output_dir: Directory to save the output PDF files (if None, will use same directory as input)
            
        Returns:
            List of paths to the output files
        """
        if output_dir:
            # Validate output directory
            verify_output_location(output_dir, is_directory=True)
        
        output_paths = []
        errors = []
        
        for input_path in input_paths:
            try:
                input_path = Path(input_path)
                
                if output_dir:
                    output_path = os.path.join(output_dir, f"{input_path.stem}_searchable.pdf")
                else:
                    output_path = None  # Will use default naming in process_file
                    
                result_path = self.process_file(str(input_path), output_path)
                output_paths.append(result_path)
                
            except PdfOcrError as e:
                print(f"Error: {str(e)}")
                errors.append(str(e))
                continue
        
        # Summarize batch processing
        if output_paths:
            print(f"\nSuccessfully processed {len(output_paths)} out of {len(input_paths)} files")
        
        if errors:
            print(f"\nFailed to process {len(errors)} files:")
            for error in errors:
                print(f"  - {error}")
        
        return output_paths

    def _convert_pdf_to_images(self, pdf_path: str, temp_dir: str) -> List[str]:
        # turn each PDF page into a JPEG image file
        image_paths = []

        try:
            pdf_document = fitz.open(pdf_path)

            # figure out the zoom level to get the DPI we want
            # PyMuPDF uses 72 DPI by default, so we scale from there
            zoom = self.ocr_dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]

                # render this page as an image
                # alpha=False means no transparency, which makes files smaller
                pix = page.get_pixmap(matrix=mat, alpha=False)

                # convert to JPEG with decent quality (85% is good balance of size vs quality)
                img_data = pix.tobytes("jpeg", jpg_quality=85)

                # save the image file
                image_path = os.path.join(temp_dir, f"page_{page_num}.jpg")
                with open(image_path, 'wb') as f:
                    f.write(img_data)

                image_paths.append(image_path)

                # free up memory
                pix = None

            pdf_document.close()

        except Exception as e:
            raise PdfOcrError(f"Failed to convert PDF to images: {str(e)}")

        return image_paths

    def _ocr_page(self, image_path: str, output_path: str) -> None:
        # take an image and turn it into a searchable PDF page
        try:
            # tesseract config - if we're optimizing, use settings that make smaller files
            if self.optimize_size:
                config = '-c tessedit_create_pdf=1 -c textonly_pdf=0'
            else:
                config = ''

            # this is where the magic happens - tesseract reads the image and makes a PDF
            pdf_data = pytesseract.image_to_pdf_or_hocr(
                image_path,
                extension='pdf',
                lang=self.language,
                config=config
            )

            # save the PDF data to a file
            with open(output_path, 'wb') as f:
                f.write(pdf_data)

        except Exception as e:
            raise TesseractError(f"OCR processing failed: {str(e)}")

    def _compress_pdf(self, pdf_path: str) -> None:
        # squeeze the final PDF to make it smaller
        try:
            print("Compressing final PDF...")

            doc = fitz.open(pdf_path)

            # these settings compress the PDF and remove junk
            # deflate=1: zip compression
            # garbage=4: remove unused stuff
            # clean=1: tidy up the file structure
            doc.save(pdf_path, deflate=1, garbage=4, clean=1)
            doc.close()

        except Exception as e:
            # if compression fails, don't crash the whole thing
            print(f"Warning: PDF compression failed: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="Convert scanned PDFs to searchable PDFs using OCR")
    parser.add_argument("input", nargs='+', help="Input PDF file(s)")
    parser.add_argument("-o", "--output", help="Output directory (for batch) or file name (for single file)")
    parser.add_argument("-d", "--dpi", type=int, default=300, help="DPI resolution for conversion (default: 300)")
    parser.add_argument("-l", "--lang", default="eng", help="OCR language (default: eng)")
    parser.add_argument("--no-optimize", action="store_true", help="Disable file size optimization")

    args = parser.parse_args()

    try:
        processor = PdfOcr(dpi=args.dpi, language=args.lang, optimize_size=not args.no_optimize)
        
        if len(args.input) == 1:
            # Process a single file
            processor.process_file(args.input[0], args.output)
        else:
            # Process multiple files
            is_directory = True if not args.output or os.path.isdir(args.output) else False
            if args.output and not is_directory:
                raise OutputError("When processing multiple files, output must be a directory")
            
            processor.process_batch(args.input, args.output)
            
    except PdfOcrError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(2)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main() 