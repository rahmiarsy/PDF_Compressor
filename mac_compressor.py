import sys
import os
import fitz
import io
from PIL import Image
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QWidget, QFileDialog, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# --- Background Worker Thread ---
# This runs the heavy compression logic without freezing the UI
class CompressorThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(str)

    def __init__(self, input_path, output_path, quality=50):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.quality = quality

    def run(self):
        try:
            original_size = os.path.getsize(self.input_path)
            doc = fitz.open(self.input_path)
            total_pages = len(doc)
            processed_xrefs = set()

            for page_num in range(total_pages):
                self.progress.emit(int(((page_num + 1) / total_pages) * 100))
                self.log.emit(f"Processing page {page_num + 1} of {total_pages}...")
                
                page = doc[page_num]
                for img_info in page.get_images():
                    xref = img_info[0]
                    if xref in processed_xrefs: continue
                        
                    try:
                        base_image = doc.extract_image(xref)
                        img = Image.open(io.BytesIO(base_image["image"]))
                        out_bytes = io.BytesIO()
                        img.convert("RGB").save(out_bytes, format="JPEG", quality=self.quality)
                        page.replace_image(xref, stream=out_bytes.getvalue())
                        processed_xrefs.add(xref)
                    except Exception:
                        pass # Silently skip broken images

            self.log.emit("Saving optimized file...")
            doc.save(self.output_path, garbage=4, deflate=True, clean=True)
            doc.close()

            new_size = os.path.getsize(self.output_path)
            saved_mb = (original_size - new_size) / (1024 * 1024)
            self.finished.emit(f"Done! Saved {saved_mb:.2f} MB")
            
        except Exception as e:
            self.finished.emit(f"Error: {str(e)}")


# --- Main Application Window ---
class PDFCompressorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Offline PDF Compressor")
        self.setFixedSize(400, 250)
        self.setAcceptDrops(True) # Enable Drag & Drop

        # UI Layout setup
        layout = QVBoxLayout()
        
        self.drop_label = QLabel("\n📄\n\nDrag and Drop your PDF here\n")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("border: 2px dashed #aaa; border-radius: 10px; font-size: 16px; color: #555;")
        layout.addWidget(self.drop_label)

        self.status_label = QLabel("Waiting for file...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    # Triggered when a file enters the window
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    # Triggered when the file is dropped
    def dropEvent(self, event):
        file_path = event.mimeData().urls()[0].toLocalFile()
        
        if not file_path.lower().endswith(".pdf"):
            self.status_label.setText("Error: Please drop a PDF file.")
            return

        # Open the Save Dialog so you can choose where to put the new file
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Compressed PDF", "", "PDF Files (*.pdf)")
        
        if save_path:
            self.start_compression(file_path, save_path)
        else:
            self.status_label.setText("Compression cancelled.")

    def start_compression(self, input_path, output_path):
        self.drop_label.setStyleSheet("border: 2px solid #4CAF50; border-radius: 10px; font-size: 16px; color: #4CAF50;")
        self.progress_bar.setValue(0)
        
        # Start the background thread
        self.thread = CompressorThread(input_path, output_path, quality=50)
        self.thread.progress.connect(self.progress_bar.setValue)
        self.thread.log.connect(self.status_label.setText)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def on_finished(self, message):
        self.status_label.setText(message)
        self.drop_label.setStyleSheet("border: 2px dashed #aaa; border-radius: 10px; font-size: 16px; color: #555;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PDFCompressorApp()
    window.show()
    sys.exit(app.exec())