# PDF OCR Tool

Turn scanned PDFs into searchable PDFs. Works with any PDF that contains images or scanned pages.

## What you need

- Python 3.6+
- Tesseract OCR:
  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
  - macOS: `brew install tesseract`
  - Linux: `sudo apt-get install tesseract-ocr`

No need to install Poppler - everything else is handled by Python packages.

## Setup

```bash
pip install -r requirements.txt
```

## How to use

**Basic:**
```bash
python ocr_pdf.py your_file.pdf
```
Creates `your_file_searchable.pdf`

**With GUI:**
```bash
python ocr_gui.py
```

**Multiple files:**
```bash
python ocr_pdf.py file1.pdf file2.pdf file3.pdf
```

**Different language (German example):**
```bash
python ocr_pdf.py document.pdf -l deu
```

**Custom output location:**
```bash
python ocr_pdf.py scan.pdf -o /path/to/output.pdf
```

## Languages

Common language codes:
- `eng` - English
- `deu` - German
- `fra` - French
- `spa` - Spanish
- `ita` - Italian
- `por` - Portuguese
- `chi_sim` - Chinese
- `jpn` - Japanese
- `kor` - Korean

For multiple languages use `+` like: `eng+deu+fra`

## File sizes

The tool automatically optimizes output size.

To disable optimization: `python ocr_pdf.py file.pdf --no-optimize`
