"""Assisted geographic tagging of a Zotero library.

Pick a library; its records that are not yet tagged ``geodone`` are listed on
the left. Choose one and the tool reads its attached PDF(s), extracts toponyms
with ``core.analyze`` (spaCy NER + your existing ``@`` tags used as a
gazetteer) and shows two check-lists:

* ``@`` tags that already exist in your library and occur in the text
  (pre-checked), and
* new place candidates found by NER (labels ``GPE`` / ``LOC``); each has an
  editable target field (default ``@Name``) and, when it looks close to an
  existing tag, a one-click button to adopt that tag instead.

You approve, the tool writes the tags back through the Zotero **local API**
(Zotero 10.0+, offline), sorts the item's tag list alphabetically and adds a
``geodone`` marker so the record leaves the list. Every action is appended to a
``zotero-assistant-log-*.csv`` file. Skipped-but-pending records simply stay in
the list for a later session.

Run:  ``python zotero_assistant.py``
"""

import csv
import datetime as _dt
import difflib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSplitter, QTableWidget,
    QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

import core
import zotero
from zotero import DONE_TAG, Library, ZoteroLocal

NEW_CANDIDATE_LABELS = ("GPE", "LOC")          # FAC excluded from new candidates
FUZZY_THRESHOLD = 0.85
BATCH = 100
NO_NER = "__no_ner__"

OCRMYPDF = shutil.which("ocrmypdf")            # optional; enables the "Run OCR" button

# spaCy/langdetect code -> Tesseract language code (for ocrmypdf -l)
_TESSERACT_LANG = {
    "it": "ita", "en": "eng", "es": "spa", "fr": "fra", "de": "deu",
    "pt": "por", "nl": "nld", "el": "ell", "pl": "pol", "ro": "ron",
    "sq": "sqi", "la": "lat", "grc": "grc", "tr": "tur", "sr": "srp",
}


def _tesseract_lang(code) -> str:
    return _TESSERACT_LANG.get(code or "", "eng")


@dataclass
class LoadedRecord:
    item: zotero.ZoteroItem
    pdfs: list = field(default_factory=list)   # list[(PdfAttachment, bytes)]
    error: str = ""
    file_unavailable: bool = False


def _strip_at(tag: str) -> str:
    return tag[1:] if tag.startswith("@") else tag


def _pages_str(pages) -> str:
    return ", ".join(str(p) for p in sorted(pages)) if pages else "-"


def _merge_results(results: list[core.AnalysisResult]) -> core.AnalysisResult:
    results = [r for r in results if r is not None]
    if len(results) == 1:
        return results[0]
    acc: dict[str, core.Toponym] = {}
    warnings: list[str] = []
    langs: list[str] = []
    for r in results:
        warnings += r.warnings
        if r.language:
            langs.append(r.language)
        for t in r.toponyms:
            k = t.name.casefold()
            cur = acc.get(k)
            if cur is None:
                acc[k] = core.Toponym(
                    name=t.name, label=t.label, count=t.count,
                    pages=set(t.pages), sources=set(t.sources),
                    gazetteer_id=t.gazetteer_id, lat=t.lat, lon=t.lon,
                )
            else:
                cur.count += t.count
                cur.pages |= set(t.pages)
                cur.sources |= set(t.sources)
                cur.gazetteer_id = cur.gazetteer_id or t.gazetteer_id
                if cur.lat is None:
                    cur.lat, cur.lon = t.lat, t.lon
                if not cur.label:
                    cur.label = t.label
    merged = core.AnalysisResult(
        pdf_path=results[0].pdf_path, engine=results[0].engine,
        language="/".join(dict.fromkeys(langs)), warnings=warnings,
    )
    merged.toponyms = sorted(acc.values(), key=lambda t: t.name.casefold())
    return merged


# --------------------------------------------------------------------------- #
# Workers
# --------------------------------------------------------------------------- #

class ItemListWorker(QThread):
    """Stream the pending records of a library into the table, in batches."""

    batch = pyqtSignal(list)       # list[ZoteroItem]
    done = pyqtSignal(int)
    failed = pyqtSignal(str)

    def __init__(self, zot: ZoteroLocal, lib: Library):
        super().__init__()
        self.zot, self.lib = zot, lib
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            buf, n = [], 0
            for it in self.zot.pending_items(self.lib):
                if self._stop:
                    return
                buf.append(it)
                n += 1
                if len(buf) >= BATCH:
                    self.batch.emit(buf)
                    buf = []
            if buf:
                self.batch.emit(buf)
            self.done.emit(n)
        except Exception as exc:
            self.failed.emit(str(exc))


class RecordLoaderWorker(QThread):
    loaded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, zot: ZoteroLocal, lib: Library, item: zotero.ZoteroItem):
        super().__init__()
        self.zot, self.lib, self.item = zot, lib, item

    def run(self):
        try:
            atts = self.zot.pdf_attachments(self.lib, self.item.key)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        pdfs, errors, unavailable = [], [], False
        for att in atts:
            try:
                pdfs.append((att, self.zot.attachment_bytes(self.lib, att.key)))
            except zotero.ZoteroFileUnavailable as exc:
                errors.append(str(exc))
                unavailable = True
            except zotero.ZoteroError as exc:
                errors.append(str(exc))
        self.loaded.emit(LoadedRecord(
            item=self.item, pdfs=pdfs,
            error="\n".join(errors), file_unavailable=unavailable,
        ))


class AnalysisWorker(QThread):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, pdfs: list, gazetteer: list, *,
                 language: str | None = None, use_ner: bool = True):
        super().__init__()
        self.pdfs, self.gazetteer = pdfs, gazetteer
        self.language, self.use_ner = language, use_ner

    def run(self):
        try:
            results = [
                core.analyze(data, gazetteer=self.gazetteer or None,
                             language=self.language, use_ner=self.use_ner,
                             labels=NEW_CANDIDATE_LABELS, source_name=att.filename)
                for att, data in self.pdfs
            ]
            self.done.emit(_merge_results(results))
        except Exception as exc:
            self.failed.emit(str(exc))


class OcrWorker(QThread):
    """Run ocrmypdf on the record's PDF bytes, off the UI thread."""

    done = pyqtSignal(list)        # list[(PdfAttachment, bytes)]
    failed = pyqtSignal(str)

    def __init__(self, pdfs: list, ocr_lang: str, workdir: Path):
        super().__init__()
        self.pdfs, self.ocr_lang, self.workdir = pdfs, ocr_lang, workdir

    def run(self):
        try:
            out = []
            for i, (att, data) in enumerate(self.pdfs):
                src = self.workdir / f"ocr_in_{i}.pdf"
                dst = self.workdir / f"ocr_out_{i}.pdf"
                src.write_bytes(data)
                proc = subprocess.run(
                    [OCRMYPDF, "--skip-text", "--language", self.ocr_lang,
                     str(src), str(dst)],
                    capture_output=True, text=True, timeout=1800,
                )
                if proc.returncode != 0 or not dst.exists():
                    self.failed.emit(
                        (proc.stderr or proc.stdout or "ocrmypdf failed").strip()[-1500:])
                    return
                out.append((att, dst.read_bytes()))
            self.done.emit(out)
        except Exception as exc:
            self.failed.emit(str(exc))


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("geoNamesFromPdf — Zotero assistant")
        self.resize(1180, 760)

        self.zot: ZoteroLocal = ZoteroLocal()
        self.lib: Library | None = None
        self._libs: list[Library] = []
        self.geo_tags: list[str] = []
        self.gazetteer: list[core.GazEntry] = []
        self._name_to_tag: dict[str, str] = {}

        self.items: list[zotero.ZoteroItem] = []
        self._by_key: dict[str, zotero.ZoteroItem] = {}
        self._filter = ""

        self.current_item: zotero.ZoteroItem | None = None
        self.current: LoadedRecord | None = None
        self.current_result: core.AnalysisResult | None = None
        self.history: list[str] = []
        self.session_done = 0
        self._warned_no_local_files = False

        self._list_worker: ItemListWorker | None = None
        self._loader: RecordLoaderWorker | None = None
        self._analysis: AnalysisWorker | None = None
        self._ocr_worker: OcrWorker | None = None
        self._prefetch_worker: RecordLoaderWorker | None = None
        self._prefetched: dict[str, LoadedRecord] = {}

        self._lang_pref = None            # persists across records: None / code / NO_NER
        self._last_language = ""
        self._gen = 0                     # bumped on every open/re-analyze; stale results ignored
        self._ocr_applied = False         # current record's pdfs are OCR'd (offer to save)

        self._existing_checks: list[QCheckBox] = []
        self._row_tag: dict[QCheckBox, str] = {}
        self._new_rows: list[tuple] = []      # (checkbox, QLineEdit)

        self._tmpdir = Path(tempfile.mkdtemp(prefix="zotassist-"))
        self.log_path = Path.cwd() / (
            "zotero-assistant-log-"
            + _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".csv"
        )
        self._log_header_written = False

        self._build_ui()
        QTimer.singleShot(0, self._startup)

    # -- UI --------------------------------------------------------- #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        top.addWidget(QLabel("Library:"))
        self.library_combo = QComboBox()
        self.library_combo.currentIndexChanged.connect(self._on_library_changed)
        top.addWidget(self.library_combo, 1)
        self.conn_label = QLabel("…")
        top.addWidget(self.conn_label)
        self.auth_button = QPushButton("Authorize writing")
        self.auth_button.clicked.connect(self._authorize)
        top.addWidget(self.auth_button)
        self.progress_label = QLabel("")
        top.addWidget(self.progress_label)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # left: queue
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("filter by title…")
        self.search_edit.textChanged.connect(self._apply_filter)
        lv.addWidget(self.search_edit)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Title", "Year", "Att", "@"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        lv.addWidget(self.table, 1)
        splitter.addWidget(left)

        # middle: current record
        mid = QWidget()
        mv = QVBoxLayout(mid)
        self.meta_label = QLabel("—")
        self.meta_label.setWordWrap(True)
        self.meta_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        mv.addWidget(self.meta_label)
        self.tags_label = QLabel("")
        self.tags_label.setWordWrap(True)
        self.tags_label.setStyleSheet("color: gray")
        mv.addWidget(self.tags_label)

        self.busy_label = QLabel("")
        self.busy_label.setWordWrap(True)
        self.busy_label.setStyleSheet("color: #06c; font-style: italic")
        self.busy_label.clear(); self.busy_label.hide()
        mv.addWidget(self.busy_label)

        self.open_pdf_button = QPushButton("Open PDF")
        self.open_pdf_button.clicked.connect(self._open_pdf)
        mv.addWidget(self.open_pdf_button)

        langrow = QHBoxLayout()
        langrow.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Auto-detect", None)
        for code in sorted(core.LANGUAGE_MODELS):
            self.lang_combo.addItem(code, code)
        self.lang_combo.addItem("— no NER (gazetteer only) —", NO_NER)
        langrow.addWidget(self.lang_combo, 1)
        self.reanalyze_button = QPushButton("Re-analyze")
        self.reanalyze_button.clicked.connect(self._reanalyze)
        langrow.addWidget(self.reanalyze_button)
        mv.addLayout(langrow)

        self.lang_note = QLabel("")
        self.lang_note.setWordWrap(True)
        self.lang_note.setStyleSheet("color: #a60")
        mv.addWidget(self.lang_note)

        self.ocr_button = QPushButton("Run OCR (ocrmypdf)")
        self.ocr_button.clicked.connect(self._run_ocr)
        self.ocr_button.hide()
        mv.addWidget(self.ocr_button)

        self.save_ocr_button = QPushButton("Save searchable PDF…")
        self.save_ocr_button.setToolTip(
            "Save the OCR'd PDF to disk. The attachment in Zotero is not "
            "changed — re-import the saved file yourself if you want it there.")
        self.save_ocr_button.clicked.connect(self._save_ocr)
        self.save_ocr_button.hide()
        mv.addWidget(self.save_ocr_button)

        self.banner = QLabel("")
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("color: #b00; font-weight: bold")
        self.banner.hide()
        mv.addWidget(self.banner)
        mv.addStretch(1)
        splitter.addWidget(mid)

        # right: suggestions
        right = QScrollArea()
        right.setWidgetResizable(True)
        holder = QWidget()
        rv = QVBoxLayout(holder)
        self.existing_group = QGroupBox("Existing @ tags found in the text")
        self.existing_layout = QVBoxLayout(self.existing_group)
        self.new_group = QGroupBox("New places")
        self.new_layout = QVBoxLayout(self.new_group)
        rv.addWidget(self.existing_group)
        rv.addWidget(self.new_group)
        rv.addStretch(1)
        right.setWidget(holder)
        splitter.addWidget(right)

        splitter.setSizes([380, 340, 440])

        actions = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self._on_back)
        self.skip_button = QPushButton("Skip (pending)")
        self.skip_button.clicked.connect(self._on_skip_pending)
        self.skip_forever_button = QPushButton("Skip and don't ask again")
        self.skip_forever_button.clicked.connect(self._on_skip_forever)
        self.save_button = QPushButton("Save selected + Next")
        self.save_button.clicked.connect(self._on_save)
        for b in (self.back_button, self.skip_button,
                  self.skip_forever_button, self.save_button):
            actions.addWidget(b)
        root.addLayout(actions)

        self.status = self.statusBar()
        self._set_actions_enabled(False)

    def _set_actions_enabled(self, on: bool):
        self.save_button.setEnabled(on)
        self.skip_button.setEnabled(on)
        self.skip_forever_button.setEnabled(on)
        has_pdf = bool(self.current and self.current.pdfs)
        self.open_pdf_button.setEnabled(on and has_pdf)
        self.reanalyze_button.setEnabled(on and has_pdf)
        self.lang_combo.setEnabled(on and has_pdf)
        self.back_button.setEnabled(len(self.history) >= 2)

    def _skip_only_state(self, reason: str):
        self.busy_label.clear(); self.busy_label.hide()
        self.banner.setText(reason)
        self.banner.show()
        self.save_button.setEnabled(False)
        has_pdf = bool(self.current and self.current.pdfs)
        self.open_pdf_button.setEnabled(has_pdf)
        self.reanalyze_button.setEnabled(has_pdf)
        self.lang_combo.setEnabled(has_pdf)
        self.skip_button.setEnabled(True)
        self.skip_forever_button.setEnabled(True)
        self.back_button.setEnabled(len(self.history) >= 2)

    def _progress(self):
        self.progress_label.setText(
            f"{self.session_done} done · {len(self.items)} pending")

    # -- startup / library ------------------------------------- #

    def _startup(self):
        try:
            self.zot.ping()
        except zotero.ZoteroUnavailable as exc:
            self.conn_label.setText("offline")
            QMessageBox.critical(self, "Zotero not reachable", str(exc))
            return
        self.conn_label.setText("connected")
        try:
            self._libs = self.zot.libraries()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.library_combo.blockSignals(True)
        self.library_combo.clear()
        self.library_combo.addItems([lib.label for lib in self._libs])
        self.library_combo.blockSignals(False)
        self._on_library_changed(0)

    def _on_library_changed(self, index: int):
        if index < 0 or not self._libs:
            return
        if self._list_worker and self._list_worker.isRunning():
            self._list_worker.stop()

        self.lib = self._libs[index]
        self.items.clear()
        self._by_key.clear()
        self._prefetched.clear()
        self.history.clear()
        self.current_item = self.current = self.current_result = None
        self.session_done = 0
        self.table.setRowCount(0)
        self._clear_suggestions()
        self.banner.hide()
        self.busy_label.clear(); self.busy_label.hide()
        self.lang_note.clear()
        self.ocr_button.hide()
        self.save_ocr_button.hide()
        self._set_actions_enabled(False)
        self.meta_label.setText("Select a record from the list on the left.")
        self.tags_label.setText("")

        try:
            self.geo_tags = self.zot.geo_tags(self.lib)
        except Exception as exc:
            QMessageBox.critical(self, "Error reading the library", str(exc))
            return
        self._name_to_tag = {_strip_at(t).casefold(): t for t in self.geo_tags}
        self.gazetteer = [core.GazEntry(name=_strip_at(t)) for t in self.geo_tags]
        self._progress()
        self.status.showMessage(
            f"{len(self.geo_tags)} geographic tags · loading records…")

        self._list_worker = ItemListWorker(self.zot, self.lib)
        self._list_worker.batch.connect(self._on_items_batch)
        self._list_worker.done.connect(self._on_items_done)
        self._list_worker.failed.connect(
            lambda m: QMessageBox.critical(self, "Error listing records", m))
        self._list_worker.start()

    def _on_items_batch(self, batch: list):
        self.table.setUpdatesEnabled(False)
        for it in batch:
            self.items.append(it)
            self._by_key[it.key] = it
            if self._match(it):
                self._append_row(it)
        self.table.setUpdatesEnabled(True)
        self._progress()

    def _on_items_done(self, total: int):
        self.status.showMessage(f"{total} record(s) to review — pick one")

    # -- table -------------------------------------------------- #

    def _match(self, it: zotero.ZoteroItem) -> bool:
        return not self._filter or self._filter in it.title.casefold()

    def _append_row(self, it: zotero.ZoteroItem):
        row = self.table.rowCount()
        self.table.insertRow(row)
        title = QTableWidgetItem(it.title)
        title.setData(Qt.UserRole, it.key)
        title.setToolTip(it.citation)
        self.table.setItem(row, 0, title)
        self.table.setItem(row, 1, QTableWidgetItem(it.year))
        self.table.setItem(row, 2, QTableWidgetItem(str(it.num_children or "")))
        self.table.setItem(row, 3, QTableWidgetItem(str(it.geo_tag_count or "")))

    def _apply_filter(self, text: str):
        self._filter = text.strip().casefold()
        keep = self.current_item.key if self.current_item else None
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(0)
        for it in self.items:
            if self._match(it):
                self._append_row(it)
        self.table.setUpdatesEnabled(True)
        if keep:
            self._select_key(keep, open_it=False)

    def _row_of(self, key: str) -> int:
        for r in range(self.table.rowCount()):
            cell = self.table.item(r, 0)
            if cell and cell.data(Qt.UserRole) == key:
                return r
        return -1

    def _select_key(self, key: str, *, open_it: bool = True):
        row = self._row_of(key)
        if row < 0:
            return
        if not open_it:
            self.table.blockSignals(True)
        self.table.selectRow(row)
        if not open_it:
            self.table.blockSignals(False)

    def _on_row_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        cell = self.table.item(row, 0)
        if not cell:
            return
        key = cell.data(Qt.UserRole)
        if self.current_item and key == self.current_item.key:
            return
        it = self._by_key.get(key)
        if it is not None:
            self._open_item(it)

    # -- open / analyse a record ------------------------------ #

    def _open_item(self, it: zotero.ZoteroItem):
        self._gen += 1
        gen = self._gen
        self.current_item = it
        self.current = self.current_result = None
        self._ocr_applied = False
        self.history.append(it.key)
        self._clear_suggestions()
        self.banner.hide()
        self.lang_note.clear()
        self.ocr_button.hide()
        self.save_ocr_button.hide()
        self._set_actions_enabled(False)
        self.meta_label.setText(
            it.citation + f"\n[{it.item_type}]  key {it.key}")
        self.tags_label.setText(
            "current tags: "
            + (", ".join(sorted(it.tags, key=str.casefold)) or "—"))
        idx = self.lang_combo.findData(self._lang_pref)
        self.lang_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._set_busy("Opening the record and reading its PDF…")

        rec = self._prefetched.pop(it.key, None)
        if rec is not None:
            self._handle_loaded(rec, gen)
            return
        self.status.showMessage("loading…")
        self._loader = RecordLoaderWorker(self.zot, self.lib, it)
        self._loader.loaded.connect(lambda r, g=gen: self._handle_loaded(r, g))
        self._loader.failed.connect(lambda m, g=gen: self._on_worker_error(m, g))
        self._loader.start()

    def _set_busy(self, text: str):
        self.busy_label.setText(text)
        self.busy_label.show()

    def _handle_loaded(self, rec: LoadedRecord, gen: int):
        if gen != self._gen:
            return
        self.current = rec

        if not rec.pdfs and not rec.error:
            self._skip_only_state("This record has no PDF attachment.")
            return
        if not rec.pdfs:
            self._skip_only_state(rec.error)
            if rec.file_unavailable and not self._warned_no_local_files:
                self._warned_no_local_files = True
                QMessageBox.information(
                    self, "Files not stored locally",
                    "This library's PDF files don't seem to be on this "
                    "computer.\n\nIn Zotero: Settings -> Sync -> tick 'Download "
                    "files', or select the items you want and right-click -> "
                    "Download File, then restart this assistant.\n\nMeanwhile "
                    "you can Skip through the affected records.")
            return

        self._start_analysis(rec.pdfs)

    def _lang_settings(self):
        """(language, use_ner) from the current combo selection."""
        data = self.lang_combo.currentData()
        if data == NO_NER:
            return None, False
        return data, True

    def _start_analysis(self, pdfs: list):
        language, use_ner = self._lang_settings()
        if not use_ner and not self.geo_tags:
            self._skip_only_state(
                "Gazetteer-only mode has nothing to match: this library has no "
                "'@' tags. Pick a language instead.")
            return
        self._gen += 1
        gen = self._gen
        self.status.showMessage("analysing…")
        self._set_actions_enabled(False)
        self._set_busy(
            "Extracting place names from the PDF… for a long document "
            "(a whole book) this can take a minute or more — the list on the "
            "left stays usable meanwhile.")
        self._analysis = AnalysisWorker(pdfs, self.gazetteer,
                                        language=language, use_ner=use_ner)
        self._analysis.done.connect(lambda r, g=gen: self._on_analysis_done(r, g))
        self._analysis.failed.connect(lambda m, g=gen: self._on_worker_error(m, g))
        self._analysis.start()

    def _reanalyze(self):
        if self.current and self.current.pdfs:
            self._lang_pref = self.lang_combo.currentData()
            self.lang_note.clear()
            self.ocr_button.hide()
            self._start_analysis(self.current.pdfs)

    def _on_analysis_done(self, result: core.AnalysisResult, gen: int):
        if gen != self._gen:
            return
        self.busy_label.clear(); self.busy_label.hide()
        self.current_result = result
        self._last_language = result.language
        if self._render_suggestions(result):
            self._set_actions_enabled(True)
        # NER ran (result.model set) on a language we have no model for -> warn
        if result.model and result.language not in core.LANGUAGE_MODELS:
            self.lang_note.setText(
                f"⚠ no spaCy model for '{result.language}': English NER was used, "
                f"so expect false positives. Try '— no NER (gazetteer only) —' "
                f"and Re-analyze.")
        else:
            self.lang_note.clear()
        note = f"  ⚠ {self.current.error}" if self.current and self.current.error else ""
        self.status.showMessage(
            f"language: {result.language or '?'}"
            f"{' (no NER)' if not result.model else ''} · "
            f"{len(result.toponyms)} toponym(s){note}")
        self._start_prefetch()

    def _on_worker_error(self, message: str, gen: int | None = None):
        if gen is not None and gen != self._gen:
            return
        self.status.showMessage("error")
        self._skip_only_state(message)

    # -- suggestions ----------------------------------------- #

    def _clear_suggestions(self):
        for lay in (self.existing_layout, self.new_layout):
            while lay.count():
                w = lay.takeAt(0).widget()
                if w:
                    w.deleteLater()
        self._existing_checks.clear()
        self._row_tag.clear()
        self._new_rows.clear()

    def _closest_existing(self, name: str):
        best, best_tag = 0.0, None
        low = name.casefold()
        for key, tag in self._name_to_tag.items():
            r = difflib.SequenceMatcher(None, low, key).ratio()
            if r > best:
                best, best_tag = r, tag
        return best_tag if FUZZY_THRESHOLD <= best < 1.0 else None

    def _render_suggestions(self, result: core.AnalysisResult) -> bool:
        """Populate the two lists. Returns False if the record can't be tagged
        (scanned PDF) and the window was put in skip-only state instead."""
        self._clear_suggestions()

        if not result.toponyms and any("scanned" in w for w in result.warnings):
            msg = ("This PDF has no extractable text — it is probably a scanned "
                   "document. Make it searchable with an OCR tool, then "
                   "Re-analyze; or Skip.")
            if OCRMYPDF:
                msg += ("\nYou can run ocrmypdf on it now (the file in Zotero is "
                        "not changed).")
            self._skip_only_state(msg)
            if OCRMYPDF:
                self.ocr_button.show()
            return False
        self.ocr_button.hide()

        matched, new = [], []
        for t in result.toponyms:                 # already alphabetical from core
            if t.name.casefold() in self._name_to_tag:
                matched.append(t)
            elif any(s.startswith("ner:") for s in t.sources):
                new.append(t)

        if not matched:
            self.existing_layout.addWidget(QLabel("— none —"))
        for t in matched:
            tag = self._name_to_tag[t.name.casefold()]
            cb = QCheckBox(f"{tag}    ×{t.count}    pp. {_pages_str(t.pages)}")
            cb.setChecked(True)
            self.existing_layout.addWidget(cb)
            self._existing_checks.append(cb)
            self._row_tag[cb] = tag

        if not new:
            self.new_layout.addWidget(QLabel("— none —"))
        for t in new:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            cb = QCheckBox(f"{t.name}    ×{t.count}    pp. {_pages_str(t.pages)}")
            h.addWidget(cb)
            edit = QLineEdit("@" + t.name)
            edit.setMaximumWidth(240)
            h.addWidget(edit)
            close = self._closest_existing(t.name)
            if close:
                btn = QToolButton()
                btn.setText(f"↳ {close}")
                btn.clicked.connect(lambda _=False, e=edit, c=close: e.setText(c))
                h.addWidget(btn)
            h.addStretch(1)
            self.new_layout.addWidget(row)
            self._new_rows.append((cb, edit))
        return True

    def _selected_tags(self) -> list[str]:
        tags = [self._row_tag[cb] for cb in self._existing_checks if cb.isChecked()]
        for cb, edit in self._new_rows:
            if cb.isChecked():
                t = edit.text().strip()
                if t:
                    tags.append(t)
        return tags

    # -- actions ------------------------------------------- #

    def _ensure_write(self) -> bool:
        if self.zot.can_write:
            return True
        try:
            self.zot.authorize_write()
        except zotero.ZoteroWriteUnsupported as exc:
            QMessageBox.warning(self, "Zotero 10 required", str(exc))
            return False
        except zotero.ZoteroAuthDenied as exc:
            QMessageBox.warning(self, "Not authorized", str(exc))
            return False
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return False
        return True

    def _write_and_drop(self, tags: list, action: str):
        try:
            self.zot.add_tags(self.lib, self.current_item.key, tags)
        except Exception as exc:
            QMessageBox.critical(self, "Write failed", str(exc))
            return False
        self._log(self.current_item, action,
                  sorted(tags, key=str.casefold))
        self.session_done += 1
        self._drop_current_row()
        return True

    def _on_save(self):
        if not self.current_item or not self._ensure_write():
            return
        if self._write_and_drop(self._selected_tags() + [DONE_TAG], "saved"):
            self.status.showMessage("saved")

    def _on_skip_forever(self):
        if not self.current_item or not self._ensure_write():
            return
        self._write_and_drop([DONE_TAG], "skip-forever")

    def _on_skip_pending(self):
        if self.current_item:
            self._log(self.current_item, "pending", [])
        row = self._row_of(self.current_item.key) if self.current_item else -1
        self._select_row(row + 1 if row >= 0 else 0)

    def _on_back(self):
        if len(self.history) < 2:
            return
        self.history.pop()                       # current
        while self.history:
            key = self.history[-1]
            if key in self._by_key:
                self.history.pop()               # will be re-added by _open_item
                self._select_key(key)
                return
            self.history.pop()

    def _drop_current_row(self):
        key = self.current_item.key
        row = self._row_of(key)
        self.items = [i for i in self.items if i.key != key]
        self._by_key.pop(key, None)
        self._prefetched.pop(key, None)
        if row >= 0:
            self.table.removeRow(row)
        self._progress()
        self._select_row(row if row >= 0 else 0)

    def _select_row(self, row: int):
        n = self.table.rowCount()
        if n == 0:
            self.current_item = self.current = self.current_result = None
            self._clear_suggestions()
            self.banner.hide()
            self.busy_label.clear(); self.busy_label.hide()
            self.lang_note.clear()
            self.ocr_button.hide()
            self.save_ocr_button.hide()
            self._set_actions_enabled(False)
            self.meta_label.setText("Nothing left to review.")
            self.tags_label.setText("")
            self.status.showMessage(f"finished: {self.session_done} processed")
            return
        self.table.selectRow(min(row, n - 1))

    # -- prefetch ---------------------------------------- #

    def _start_prefetch(self):
        if not self.current_item:
            return
        row = self._row_of(self.current_item.key)
        if row < 0 or row + 1 >= self.table.rowCount():
            return
        cell = self.table.item(row + 1, 0)
        key = cell.data(Qt.UserRole) if cell else None
        it = self._by_key.get(key)
        if it is None or key in self._prefetched:
            return
        self._prefetch_worker = RecordLoaderWorker(self.zot, self.lib, it)
        self._prefetch_worker.loaded.connect(
            lambda rec, k=key: self._prefetched.__setitem__(k, rec))
        self._prefetch_worker.failed.connect(lambda _m: None)
        self._prefetch_worker.start()

    # -- misc ------------------------------------------- #

    def _authorize(self):
        if self._ensure_write():
            self.status.showMessage("write access granted")

    def _open_pdf(self):
        if not self.current or not self.current.pdfs:
            return
        att, data = self.current.pdfs[0]
        path = self._tmpdir / (att.key + "_" + att.filename)
        path.write_bytes(data)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # -- OCR (optional, needs ocrmypdf on PATH) ---------- #

    def _run_ocr(self):
        if not OCRMYPDF or not self.current or not self.current.pdfs:
            return
        lang = _tesseract_lang(self.lang_combo.currentData())
        self._gen += 1
        gen = self._gen
        self.ocr_button.setEnabled(False)
        self.status.showMessage(f"running ocrmypdf (-l {lang})…")
        self._set_busy(
            f"Running OCR with ocrmypdf (-l {lang})… for a scanned book this "
            f"can take several minutes. The file in Zotero is not modified.")
        self._ocr_worker = OcrWorker(self.current.pdfs, lang, self._tmpdir)
        self._ocr_worker.done.connect(lambda p, g=gen: self._on_ocr_done(p, g))
        self._ocr_worker.failed.connect(lambda m, g=gen: self._on_ocr_failed(m, g))
        self._ocr_worker.start()

    def _on_ocr_done(self, pdfs: list, gen: int):
        if gen != self._gen:
            return
        self.ocr_button.setEnabled(True)
        self.ocr_button.hide()
        if self.current:
            self.current.pdfs = pdfs
        self._ocr_applied = True
        self.save_ocr_button.show()
        self.status.showMessage("OCR done — re-analysing")
        self._start_analysis(pdfs)

    def _save_ocr(self):
        if not self._ocr_applied or not self.current or not self.current.pdfs:
            return
        pdfs = self.current.pdfs
        if len(pdfs) == 1:
            att, data = pdfs[0]
            default = str(Path.home() / (Path(att.filename).stem + "_ocr.pdf"))
            path, _ = QFileDialog.getSaveFileName(
                self, "Save searchable PDF", default, "PDF files (*.pdf)")
            if not path:
                return
            Path(path).write_bytes(data)
            saved = [path]
        else:
            folder = QFileDialog.getExistingDirectory(
                self, "Save searchable PDFs into folder", str(Path.home()))
            if not folder:
                return
            saved = []
            for att, data in pdfs:
                p = Path(folder) / (Path(att.filename).stem + "_ocr.pdf")
                p.write_bytes(data)
                saved.append(str(p))
        self._log(self.current_item, "ocr-saved", saved)
        self.status.showMessage(f"saved: {'; '.join(saved)}")

    def _on_ocr_failed(self, message: str, gen: int):
        if gen != self._gen:
            return
        self.ocr_button.setEnabled(True)
        self.busy_label.clear(); self.busy_label.hide()
        QMessageBox.critical(self, "ocrmypdf failed", message)

    def _log(self, item: zotero.ZoteroItem, action: str, tags: list):
        with open(self.log_path, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if not self._log_header_written:
                w.writerow(["timestamp", "library", "item_key", "item_title",
                            "action", "language", "tags_added"])
                self._log_header_written = True
            w.writerow([_dt.datetime.now().isoformat(timespec="seconds"),
                        self.lib.label if self.lib else "",
                        item.key, item.title, action,
                        self._last_language, "; ".join(tags)])

    def closeEvent(self, event):
        if self._list_worker and self._list_worker.isRunning():
            self._list_worker.stop()
        for wk in (self._ocr_worker, self._analysis, self._loader):
            if wk and wk.isRunning():
                wk.wait(2000)
        try:
            self.zot.close()
        except Exception:
            pass
        for p in self._tmpdir.glob("*"):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            self._tmpdir.rmdir()
        except OSError:
            pass
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
