"""
Error handling utilities for the PDF OCR tool
"""
import os
import sys
from pathlib import Path


class PdfOcrError(Exception):
    """Base exception class for PDF OCR tool"""
    pass


class InputFileError(PdfOcrError):
    """Exception raised for errors with input files"""
    pass


class TesseractError(PdfOcrError):
    """Exception raised for Tesseract-related errors"""
    pass


class OutputError(PdfOcrError):
    """Exception raised for errors with output files or directories"""
    pass


def verify_tesseract_installed():
    """
    Check if Tesseract is installed and accessible

    Raises:
        TesseractError: If Tesseract is not installed or not accessible
    """
    import shutil

    if not shutil.which("tesseract"):
        msg = (
            "Tesseract OCR not found. Please install Tesseract:\n"
            "  - Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  - macOS: brew install tesseract\n"
            "  - Linux: sudo apt-get install tesseract-ocr"
        )
        raise TesseractError(msg)


def verify_pymupdf_installed():
    """
    Check if PyMuPDF is installed and accessible

    Raises:
        PdfOcrError: If PyMuPDF is not installed
    """
    try:
        import fitz
    except ImportError:
        msg = (
            "PyMuPDF not found. Please install it:\n"
            "  pip install PyMuPDF\n"
            "This replaces the need for Poppler installation."
        )
        raise PdfOcrError(msg)


def verify_input_file(file_path):
    """
    Verify that the input file exists and is a valid PDF
    
    Args:
        file_path: Path to the input file
        
    Raises:
        InputFileError: If the file doesn't exist or is not a PDF
    """
    path = Path(file_path)
    
    if not path.exists():
        raise InputFileError(f"Input file not found: {file_path}")
        
    if not path.is_file():
        raise InputFileError(f"Input path is not a file: {file_path}")
        
    if path.suffix.lower() != ".pdf":
        raise InputFileError(f"Input file is not a PDF: {file_path}")


def verify_output_location(output_path, is_directory=False):
    """
    Verify that the output location is valid
    
    Args:
        output_path: Path to the output file or directory
        is_directory: Whether the output path should be a directory
        
    Raises:
        OutputError: If the output location is invalid
    """
    path = Path(output_path)
    
    # Check if parent directory exists
    if not path.parent.exists():
        try:
            os.makedirs(path.parent, exist_ok=True)
        except OSError as e:
            raise OutputError(f"Cannot create output directory: {e}")
            
    # If output should be a directory
    if is_directory:
        if path.exists() and not path.is_dir():
            raise OutputError(f"Output path exists but is not a directory: {output_path}")
        
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise OutputError(f"Cannot create output directory: {e}")
    
    # If output is a file
    else:
        if path.exists() and not path.is_file():
            raise OutputError(f"Output path exists but is not a file: {output_path}") 