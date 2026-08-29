import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QVBoxLayout, QPushButton, QLabel,
    QTextEdit, QWidget, QHBoxLayout, QScrollArea, QInputDialog, QMessageBox,
    QLineEdit
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent

# All extraction logic lives in core.py and is shared with the CLI.
import core


class AnalysisWorker(QThread):
    """Run core.analyze() off the UI thread so the window stays responsive."""

    finished = pyqtSignal(object)   # core.AnalysisResult
    failed = pyqtSignal(str)

    def __init__(self, pdf_path, *, pages, gazetteer, exclude):
        super().__init__()
        self.pdf_path = pdf_path
        self.pages = pages
        self.gazetteer = gazetteer
        self.exclude = exclude

    def run(self):
        try:
            result = core.analyze(
                self.pdf_path,
                pages=self.pages or None,
                gazetteer=self.gazetteer or None,
                exclude=self.exclude or None,
            )
            self.finished.emit(result)
        except Exception as exc:  # surfaced in a dialog by the main window
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GeoNamesFromPdf - GUI")
        self.setGeometry(100, 100, 900, 700)

        # central widget
        self.central = QWidget()
        self.setCentralWidget(self.central)

        # main vertical layout
        self.main_layout = QVBoxLayout()
        self.central.setLayout(self.main_layout)

        # --- Top: Upload PDF (always on top) ---
        self.top_pdf_layout = QVBoxLayout()
        self.top_pdf_label = QLabel("Upload a PDF:")
        self.top_pdf_label.setStyleSheet("font-weight: bold")
        self.top_pdf_layout.addWidget(self.top_pdf_label)

        self.pdf_button = QPushButton("Select PDF")
        self.pdf_button.clicked.connect(self.select_pdf)
        self.top_pdf_layout.addWidget(self.pdf_button)

        self.pdf_path_label = QLabel("No PDF selected.")
        self.top_pdf_layout.addWidget(self.pdf_path_label)

        # Page range input
        self.page_range_layout = QHBoxLayout()
        self.page_range_label = QLabel("Page range (optional):")
        self.page_range_layout.addWidget(self.page_range_label)

        self.page_range_input = QLineEdit()
        self.page_range_input.setPlaceholderText("e.g., 5, 5-10, or 5-10, 12-14")
        self.page_range_layout.addWidget(self.page_range_input)
        self.top_pdf_layout.addLayout(self.page_range_layout)

        self.main_layout.addLayout(self.top_pdf_layout)

        # --- Middle: Gazetteer (left) and Exclude list (right) ---
        self.top_layout = QHBoxLayout()

        # Gazetteer column (left)
        self.gazetteer_col = QVBoxLayout()
        self.gazetteer_title = QLabel("Gazetteer (Included)")
        self.gazetteer_title.setStyleSheet("font-weight: bold")
        self.gazetteer_col.addWidget(self.gazetteer_title)

        self.gazetteer_load_button = QPushButton("Select Gazetteer")
        self.gazetteer_load_button.clicked.connect(self.select_gazetteer)
        self.gazetteer_col.addWidget(self.gazetteer_load_button)

        self.gazetteer_path_label = QLabel("No Gazetteer loaded.")
        self.gazetteer_col.addWidget(self.gazetteer_path_label)

        self.gazetteer_preview = QTextEdit()
        self.gazetteer_preview.setReadOnly(True)
        self.gazetteer_col.addWidget(self.gazetteer_preview)

        # buttons for include list
        self.gazetteer_buttons = QHBoxLayout()
        self.gazetteer_add_button = QPushButton("Add to Included")
        self.gazetteer_add_button.clicked.connect(self.add_to_included)
        self.gazetteer_buttons.addWidget(self.gazetteer_add_button)

        self.gazetteer_remove_button = QPushButton("Remove Selected")
        self.gazetteer_remove_button.clicked.connect(self.remove_from_included)
        self.gazetteer_buttons.addWidget(self.gazetteer_remove_button)

        self.gazetteer_save_button = QPushButton("Save Included to File")
        self.gazetteer_save_button.clicked.connect(self.save_included_to_file)
        self.gazetteer_buttons.addWidget(self.gazetteer_save_button)

        self.gazetteer_col.addLayout(self.gazetteer_buttons)

        self.top_layout.addLayout(self.gazetteer_col, 1)

        # Exclude column (right)
        self.exclude_col = QVBoxLayout()
        self.exclude_title = QLabel("Exclude List")
        self.exclude_title.setStyleSheet("font-weight: bold")
        self.exclude_col.addWidget(self.exclude_title)

        self.exclude_load_button = QPushButton("Select Exclude List")
        self.exclude_load_button.clicked.connect(self.select_exclude_list)
        self.exclude_col.addWidget(self.exclude_load_button)

        self.exclude_path_label = QLabel("No Exclude list loaded.")
        self.exclude_col.addWidget(self.exclude_path_label)

        self.exclude_preview = QTextEdit()
        self.exclude_preview.setReadOnly(True)
        self.exclude_col.addWidget(self.exclude_preview)

        # buttons for exclude list
        self.exclude_buttons = QHBoxLayout()
        self.exclude_add_button = QPushButton("Add to Excluded")
        self.exclude_add_button.clicked.connect(self.add_to_excluded)
        self.exclude_buttons.addWidget(self.exclude_add_button)

        self.exclude_remove_button = QPushButton("Remove Selected")
        self.exclude_remove_button.clicked.connect(self.remove_from_excluded)
        self.exclude_buttons.addWidget(self.exclude_remove_button)

        self.exclude_save_button = QPushButton("Save Excluded to File")
        self.exclude_save_button.clicked.connect(self.save_excluded_to_file)
        self.exclude_buttons.addWidget(self.exclude_save_button)

        self.exclude_col.addLayout(self.exclude_buttons)

        self.top_layout.addLayout(self.exclude_col, 1)

        self.main_layout.addLayout(self.top_layout)

        # --- Process button ---
        self.process_button = QPushButton("Process PDF")
        self.process_button.clicked.connect(self.process_pdf)
        self.main_layout.addWidget(self.process_button)

        self.status_label = QLabel("")
        self.main_layout.addWidget(self.status_label)

        # --- Scrollable results area (takes remaining space) ---
        self.results_area = QScrollArea()
        self.results_area.setWidgetResizable(True)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout()
        self.results_container.setLayout(self.results_layout)
        self.results_area.setWidget(self.results_container)
        self.main_layout.addWidget(self.results_area, 1)

        # Enable drag and drop
        self.setAcceptDrops(True)

        # Data
        self.pdf_path = None
        self.last_pdf_path = None
        self.gazetteer_path = None
        self.gazetteer_data = []
        self.exclude_list = []
        self.worker = None

    # ----------------- File selection and list management -----------------
    def select_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self.last_pdf_path = file_path
            self.pdf_path_label.setText(f"Selected PDF: {file_path}")

    def select_gazetteer(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Gazetteer", "", "Gazetteer files (*.txt *.csv *.tsv)")
        if file_path:
            self.gazetteer_path = file_path
            self.gazetteer_path_label.setText(f"Loaded Gazetteer: {file_path}")
            self.load_gazetteer(file_path)

    def load_gazetteer(self, file_path):
        try:
            self.gazetteer_data = [e.name for e in core.load_gazetteer(file_path)]
            self.gazetteer_preview.setPlainText("\n".join(self.gazetteer_data))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load gazetteer: {e}")

    def select_exclude_list(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Exclude List", "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.exclude_list = [line.strip() for line in f if line.strip()]
                self.exclude_path_label.setText(f"Loaded Exclude list: {file_path}")
                self.exclude_preview.setPlainText("\n".join(self.exclude_list))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load exclude list: {e}")

    def save_included_to_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Included Items", "included.txt", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(self.gazetteer_data))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save included items: {e}")

    def save_excluded_to_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excluded Items", "excluded.txt", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(self.exclude_list))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save excluded items: {e}")

    def add_to_included(self):
        text, ok = QInputDialog.getText(self, "Add to Included Items", "Enter the item to include:")
        if ok and text.strip():
            new_item = text.strip()
            if new_item not in self.gazetteer_data:
                self.gazetteer_data.append(new_item)
                self.gazetteer_preview.setPlainText("\n".join(self.gazetteer_data))

    def remove_from_included(self):
        cursor = self.gazetteer_preview.textCursor()
        cursor.select(cursor.LineUnderCursor)
        selected_text = cursor.selectedText().strip()
        if selected_text in self.gazetteer_data:
            self.gazetteer_data.remove(selected_text)
            self.gazetteer_preview.setPlainText("\n".join(self.gazetteer_data))

    def add_to_excluded(self):
        text, ok = QInputDialog.getText(self, "Add to Excluded Items", "Enter the item to exclude:")
        if ok and text.strip():
            new_item = text.strip()
            if new_item not in self.exclude_list:
                self.exclude_list.append(new_item)
                self.exclude_preview.setPlainText("\n".join(self.exclude_list))

    def remove_from_excluded(self):
        cursor = self.exclude_preview.textCursor()
        cursor.select(cursor.LineUnderCursor)
        selected_text = cursor.selectedText().strip()
        if selected_text in self.exclude_list:
            self.exclude_list.remove(selected_text)
            self.exclude_preview.setPlainText("\n".join(self.exclude_list))

    # ----------------- Processing and results -----------------
    def process_pdf(self):
        # allow re-run using last uploaded path
        if not self.pdf_path:
            if self.last_pdf_path:
                self.pdf_path = self.last_pdf_path
                self.pdf_path_label.setText(f"Using last PDF: {self.pdf_path}")
            else:
                QMessageBox.information(self, "Info", "Please select a PDF first.")
                return

        if self.worker and self.worker.isRunning():
            return

        # Validate the page range up front for immediate feedback.
        page_spec = self.page_range_input.text().strip()
        if page_spec:
            try:
                core.parse_page_ranges(page_spec)
            except ValueError as e:
                QMessageBox.critical(self, "Error", f"Invalid page range: {e}")
                return

        self.results_layout_parent_clear()
        self.process_button.setEnabled(False)
        self.status_label.setText("Processing… (this can take a while for large PDFs)")

        gazetteer = [core.GazEntry(name=n) for n in self.gazetteer_data] or None
        self.worker = AnalysisWorker(
            self.pdf_path,
            pages=page_spec,
            gazetteer=gazetteer,
            exclude=list(self.exclude_list),
        )
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.failed.connect(self._on_analysis_failed)
        self.worker.start()

    def _on_analysis_failed(self, message):
        self.process_button.setEnabled(True)
        self.status_label.setText("")
        QMessageBox.critical(self, "Error", f"Error processing PDF: {message}")

    def _on_analysis_done(self, result):
        self.process_button.setEnabled(True)

        bits = []
        if result.language:
            bits.append(f"language: {result.language}")
        if result.model:
            bits.append(f"model: {result.model}")
        bits.append(f"{len(result.toponyms)} toponym(s)")
        self.status_label.setText(" · ".join(bits))
        for warning in result.warnings:
            self.status_label.setText(self.status_label.text() + f"  ⚠️ {warning}")

        if not result.toponyms:
            self.results_layout.addWidget(QLabel("No toponyms found."))
            return

        # display each place with Add/Remove buttons
        for topo in result.toponyms:
            row = QHBoxLayout()

            pages = ",".join(map(str, sorted(topo.pages)))
            caption = topo.name
            detail = f"  ({topo.label or '?'}, x{topo.count}" + (f", p.{pages}" if pages else "") + ")"
            lbl = QLabel(caption + detail)
            row.addWidget(lbl, 1)

            btn_add = QPushButton("Add")
            btn_add.clicked.connect(lambda _, p=topo.name: self._on_add_from_results(p))
            row.addWidget(btn_add)

            btn_remove = QPushButton("Remove")
            btn_remove.clicked.connect(lambda _, p=topo.name: self._on_remove_from_results(p))
            row.addWidget(btn_remove)

            container = QWidget()
            container.setLayout(row)
            self.results_layout.addWidget(container)

    def _on_add_from_results(self, place):
        if place not in self.gazetteer_data:
            self.gazetteer_data.append(place)
            self.gazetteer_preview.setPlainText("\n".join(self.gazetteer_data))

    def _on_remove_from_results(self, place):
        if place not in self.exclude_list:
            self.exclude_list.append(place)
            self.exclude_preview.setPlainText("\n".join(self.exclude_list))

    def results_layout_parent_clear(self):
        # clear results layout
        for i in reversed(range(self.results_layout.count())):
            widget = self.results_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

    # ----------------- drag & drop -----------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            lower = file_path.lower()
            if lower.endswith('.pdf'):
                self.pdf_path = file_path
                self.last_pdf_path = file_path
                self.pdf_path_label.setText(f"Selected PDF: {file_path}")
            elif lower.endswith(('.txt', '.csv', '.tsv')):
                # treat dropped text file as gazetteer by default
                self.gazetteer_path = file_path
                self.gazetteer_path_label.setText(f"Loaded Gazetteer: {file_path}")
                self.load_gazetteer(file_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
