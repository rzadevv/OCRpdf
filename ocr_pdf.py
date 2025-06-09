#!/usr/bin/env python3
"""
PDF OCR Tool - Convert scanned PDFs to searchable PDFs
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import pytesseract
import fitz  # PyMuPDF
from PIL import Image
from PyPDF2 import PdfWriter, PdfReader
from tqdm import tqdm

from error_handlers import (
    PdfOcrError, InputFileError, TesseractError, OutputError,
    verify_tesseract_installed, verify_pymupdf_installed,
    verify_input_file, verify_output_location
)


class PdfOcr:
    def __init__(self, dpi: int = 300, language: str = "eng", optimize_size: bool = True):
        """
        Initialize the PDF OCR processor

        Args:
            dpi: DPI resolution for PDF to image conversion
            language: Tesseract language code (e.g., 'eng', 'fra', 'deu', etc.)
            optimize_size: Whether to optimize output file size (default: True)
        """
        self.dpi = dpi
        self.language = language
        self.optimize_size = optimize_size

        # For size optimization, use lower DPI for OCR while maintaining visual quality
        self.ocr_dpi = min(dpi, 200) if optimize_size else dpi

        # Verify required dependencies
        verify_tesseract_installed()
        verify_pymupdf_installed()
    
    def process_file(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Process a single PDF file and create a searchable version
        
        Args:
            input_path: Path to input PDF file
            output_path: Path to save the output PDF file (if None, will use input_path + "_searchable.pdf")
            
        Returns:
            Path to the output file
        """
        # Validate input file
        verify_input_file(input_path)
        
        input_path = Path(input_path)
        
        if not output_path:
            output_path = str(input_path.parent / f"{input_path.stem}_searchable.pdf")
        
        # Validate output location
        verify_output_location(output_path)
        
        print(f"Processing: {input_path}")
        print(f"Output will be saved to: {output_path}")
        
        try:
            # Create a temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Convert PDF to images using PyMuPDF
                print("Converting PDF to images...")
                images = self._convert_pdf_to_images(str(input_path), temp_dir)

                # Process each page
                print(f"Performing OCR on {len(images)} pages...")
                pdf_writer = PdfWriter()

                for i, image_path in enumerate(tqdm(images, desc="OCR Processing")):
                    # Perform OCR and generate a searchable PDF for this page
                    searchable_page_path = os.path.join(temp_dir, f"searchable_page_{i}.pdf")
                    self._ocr_page(image_path, searchable_page_path)

                    # Add the searchable page to our output PDF
                    pdf_reader = PdfReader(searchable_page_path)
                    if len(pdf_reader.pages) > 0:
                        pdf_writer.append(pdf_reader)
                    else:
                        print(f"Warning: OCR produced empty page for page {i+1}")

                # Save the final PDF
                with open(output_path, 'wb') as output_file:
                    pdf_writer.write(output_file)

                # Post-process with PyMuPDF for additional compression if optimization is enabled
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
        """
        Convert PDF pages to images using PyMuPDF (no external dependencies)

        Args:
            pdf_path: Path to the PDF file
            temp_dir: Temporary directory to save images

        Returns:
            List of paths to the generated image files
        """
        image_paths = []

        try:
            # Open the PDF document
            pdf_document = fitz.open(pdf_path)

            # Calculate zoom factor based on OCR DPI (optimized for size)
            # PyMuPDF default is 72 DPI, so we calculate zoom to get desired DPI
            zoom = self.ocr_dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            for page_num in range(len(pdf_document)):
                # Get the page
                page = pdf_document[page_num]

                # Render page to image with optimized settings
                pix = page.get_pixmap(matrix=mat, alpha=False)  # No alpha channel to reduce size

                # Convert to PIL Image for compression
                img_data = pix.tobytes("jpeg", jpg_quality=85)  # Use JPEG with 85% quality

                # Save as JPEG for better compression
                image_path = os.path.join(temp_dir, f"page_{page_num}.jpg")
                with open(image_path, 'wb') as f:
                    f.write(img_data)

                image_paths.append(image_path)

                # Clean up pixmap
                pix = None

            # Close the document
            pdf_document.close()

        except Exception as e:
            raise PdfOcrError(f"Failed to convert PDF to images: {str(e)}")

        return image_paths

    def _ocr_page(self, image_path: str, output_path: str) -> None:
        """
        Perform OCR on a single page image and create a searchable PDF

        Args:
            image_path: Path to the image file
            output_path: Path to save the output searchable PDF
        """
        try:
            # Configure tesseract for optimized output
            if self.optimize_size:
                # Use configuration that optimizes for smaller file size
                config = '-c tessedit_create_pdf=1 -c textonly_pdf=0'
            else:
                config = ''

            # Use pytesseract to create a searchable PDF with the text layer
            pdf_data = pytesseract.image_to_pdf_or_hocr(
                image_path,
                extension='pdf',
                lang=self.language,
                config=config
            )

            # Write the PDF data to the output file
            with open(output_path, 'wb') as f:
                f.write(pdf_data)

        except Exception as e:
            raise TesseractError(f"OCR processing failed: {str(e)}")

    def _compress_pdf(self, pdf_path: str) -> None:
        """
        Compress the final PDF using PyMuPDF for additional size reduction

        Args:
            pdf_path: Path to the PDF file to compress
        """
        try:
            print("Compressing final PDF...")

            # Open the PDF with PyMuPDF
            doc = fitz.open(pdf_path)

            # Save with compression options
            # deflate=1: Enable compression
            # garbage=4: Remove unused objects
            # clean=1: Clean up the PDF structure
            doc.save(pdf_path, deflate=1, garbage=4, clean=1)
            doc.close()

        except Exception as e:
            # If compression fails, just log a warning but don't fail the whole process
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