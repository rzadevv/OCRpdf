#!/usr/bin/env python3
# GUI for the PDF OCR tool
# Just a simple interface so you don't have to use command line

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from typing import List, Optional

from ocr_pdf import PdfOcr
from error_handlers import PdfOcrError, verify_tesseract_installed, verify_pymupdf_installed


class TextRedirector:
    # This class captures print statements and shows them in the GUI log window

    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""

    def write(self, string):
        self.buffer += string
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)  # auto-scroll to bottom
        self.text_widget.config(state=tk.DISABLED)

    def flush(self):
        pass  # tkinter doesn't need this but Python expects it


class PdfOcrGui:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF OCR Tool")
        self.root.geometry("750x600")
        self.root.minsize(650, 500)

        # make it look a bit nicer
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, relief="flat", font=("Arial", 10))
        self.style.configure("TLabel", font=("Arial", 10))
        self.style.configure("TFrame", background="#f5f5f5")

        # main container for everything
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # section for selecting PDF files
        self.input_frame = ttk.LabelFrame(self.main_frame, text="Input PDFs", padding="10")
        self.input_frame.pack(fill=tk.X, pady=5)

        # list box to show selected files
        self.input_files_frame = ttk.Frame(self.input_frame)
        self.input_files_frame.pack(fill=tk.BOTH, expand=True)

        self.input_files_list = tk.Listbox(self.input_files_frame, height=5)
        self.input_files_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # scrollbar for the file list
        self.files_scrollbar = ttk.Scrollbar(self.input_files_frame)
        self.files_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # connect scrollbar to listbox
        self.input_files_list.config(yscrollcommand=self.files_scrollbar.set)
        self.files_scrollbar.config(command=self.input_files_list.yview)
        
        # buttons for adding/removing files
        self.input_btns_frame = ttk.Frame(self.input_frame)
        self.input_btns_frame.pack(fill=tk.X, pady=(5, 0))

        self.add_files_btn = ttk.Button(self.input_btns_frame, text="Add PDF Files", command=self.add_files)
        self.add_files_btn.pack(side=tk.LEFT, padx=2)

        self.clear_files_btn = ttk.Button(self.input_btns_frame, text="Clear All", command=self.clear_files)
        self.clear_files_btn.pack(side=tk.LEFT, padx=2)

        # settings section
        self.options_frame = ttk.LabelFrame(self.main_frame, text="OCR Options", padding="10")
        self.options_frame.pack(fill=tk.X, pady=5)

        # image quality setting
        self.dpi_frame = ttk.Frame(self.options_frame)
        self.dpi_frame.pack(fill=tk.X, pady=2)

        ttk.Label(self.dpi_frame, text="DPI Resolution:").pack(side=tk.LEFT)
        self.dpi_var = tk.StringVar(value="300")
        self.dpi_combo = ttk.Combobox(self.dpi_frame, textvariable=self.dpi_var, width=10)
        self.dpi_combo['values'] = ("150", "200", "300", "400", "600")  # 300 is usually good enough
        self.dpi_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # what language to recognize
        self.lang_frame = ttk.Frame(self.options_frame)
        self.lang_frame.pack(fill=tk.X, pady=2)

        ttk.Label(self.lang_frame, text="OCR Language:").pack(side=tk.LEFT)
        self.lang_var = tk.StringVar(value="eng")
        self.lang_combo = ttk.Combobox(self.lang_frame, textvariable=self.lang_var, width=10)
        # most common languages, you can add more if needed
        self.lang_combo['values'] = (
            "eng", "eng+fra", "eng+deu", "eng+spa", "eng+ita", "fra", "deu",
            "spa", "ita", "por", "chi_sim", "jpn", "kor"
        )
        self.lang_combo.pack(side=tk.LEFT, padx=(5, 0))

        # where to save the output files
        self.output_frame = ttk.Frame(self.options_frame)
        self.output_frame.pack(fill=tk.X, pady=2)

        ttk.Label(self.output_frame, text="Output Directory:").pack(side=tk.LEFT)
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(self.output_frame, textvariable=self.output_var)
        self.output_entry.pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)

        self.browse_output_btn = ttk.Button(self.output_frame, text="Browse...", command=self.browse_output)
        self.browse_output_btn.pack(side=tk.LEFT, padx=(5, 0))

        # checkbox to make files smaller (recommended)
        self.optimize_frame = ttk.Frame(self.options_frame)
        self.optimize_frame.pack(fill=tk.X, pady=2)

        self.optimize_var = tk.BooleanVar(value=True)
        self.optimize_check = ttk.Checkbutton(
            self.optimize_frame,
            text="Optimize file size (reduces output size by ~80%)",
            variable=self.optimize_var
        )
        self.optimize_check.pack(side=tk.LEFT)

        # the big button to start processing
        self.process_btn_frame = ttk.Frame(self.main_frame)
        self.process_btn_frame.pack(fill=tk.X, pady=10)

        self.process_btn = ttk.Button(
            self.process_btn_frame,
            text="Process PDFs",
            command=self.process_files,
            style="Accent.TButton"
        )
        self.process_btn.pack(fill=tk.X)

        # spinning progress bar
        self.progress_frame = ttk.Frame(self.main_frame)
        self.progress_frame.pack(fill=tk.X, pady=5)

        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="indeterminate")
        self.progress_bar.pack(fill=tk.X)
        
        # text area to show what's happening
        self.log_frame = ttk.LabelFrame(self.main_frame, text="Process Log", padding="10")
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = ScrolledText(self.log_frame, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # capture print statements and show them in the log
        self.stdout_redirector = TextRedirector(self.log_text)

        # keep track of stuff
        self.input_files = []
        self.processing_thread = None

    def add_files(self):
        # open file dialog to pick PDFs
        files = filedialog.askopenfilenames(
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
            title="Select PDF Files for OCR"
        )

        if not files:
            return

        # add each file to our list (but don't add duplicates)
        for file in files:
            if file not in self.input_files:
                self.input_files.append(file)
                self.input_files_list.insert(tk.END, os.path.basename(file))  # just show filename, not full path
    
    def clear_files(self):
        """Clear the list of input files"""
        self.input_files = []
        self.input_files_list.delete(0, tk.END)
    
    def browse_output(self):
        """Select output directory"""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_var.set(directory)
    
    def process_files(self):
        """Process PDF files with OCR"""
        if not self.input_files:
            messagebox.showwarning("Warning", "No input PDF files selected!")
            return
        
        # Get options
        dpi = int(self.dpi_var.get())
        language = self.lang_var.get()
        output_dir = self.output_var.get() if self.output_var.get() else None
        optimize_size = self.optimize_var.get()
        
        # Disable UI during processing
        self.toggle_ui_state(False)
        
        # Start progress bar
        self.progress_bar.start()
        
        # Clear log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # Redirect stdout/stderr
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        sys.stdout = self.stdout_redirector
        sys.stderr = self.stdout_redirector
        
        # Run processing in a separate thread
        self.processing_thread = threading.Thread(
            target=self._process_thread,
            args=(self.input_files, output_dir, dpi, language, optimize_size)
        )
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        # Check thread status periodically
        self.root.after(100, self.check_processing_thread)
    
    def _process_thread(self, files, output_dir, dpi, language, optimize_size):
        """Thread function to process files"""
        try:
            # Verify required dependencies are installed
            verify_tesseract_installed()
            verify_pymupdf_installed()

            # Create processor
            processor = PdfOcr(dpi=dpi, language=language, optimize_size=optimize_size)
            
            # Process files
            processor.process_batch(files, output_dir)
            
            # Show success message
            self.root.after(0, lambda: messagebox.showinfo("Success", "PDF OCR processing completed!"))
            
        except PdfOcrError as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", msg))
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Unexpected Error", msg))
    
    def check_processing_thread(self):
        """Check if the processing thread is still running"""
        if self.processing_thread and self.processing_thread.is_alive():
            # Still running, check again later
            self.root.after(100, self.check_processing_thread)
        else:
            # Thread finished, restore UI
            self.processing_thread = None
            self.progress_bar.stop()
            
            # Restore stdout/stderr
            sys.stdout = self.old_stdout
            sys.stderr = self.old_stderr
            
            # Enable UI
            self.toggle_ui_state(True)
    
    def toggle_ui_state(self, enabled: bool):
        """Enable or disable UI elements during processing"""
        state = tk.NORMAL if enabled else tk.DISABLED

        self.add_files_btn.config(state=state)
        self.clear_files_btn.config(state=state)
        self.dpi_combo.config(state=state)
        self.lang_combo.config(state=state)
        self.output_entry.config(state=state)
        self.browse_output_btn.config(state=state)
        self.optimize_check.config(state=state)
        self.process_btn.config(state=state)


def main():
    try:
        root = tk.Tk()
        app = PdfOcrGui(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Fatal Error", f"An unexpected error occurred: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 