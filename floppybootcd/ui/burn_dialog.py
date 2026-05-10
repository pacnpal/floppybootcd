"""BurnDialog: drive picker, options, progress, log."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QPlainTextEdit, QVBoxLayout, QWidget,
)

from ..core.burner import BurnerBackend, OpticalDrive


class _BurnWorker(QObject):
    progress = Signal(str, float)
    log = Signal(str)
    finished = Signal(bool, str)   # success, error message

    def __init__(self, backend: BurnerBackend, iso_path: Path,
                 drive: OpticalDrive | None, verify: bool, eject: bool):
        super().__init__()
        self.backend = backend
        self.iso_path = iso_path
        self.drive = drive
        self.verify = verify
        self.eject = eject

    def run(self) -> None:
        try:
            self.backend.burn(
                self.iso_path, self.drive,
                self.verify, self.eject,
                lambda m, f: self.progress.emit(m, f),
                lambda m: self.log.emit(m),
            )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class BurnDialog(QDialog):
    def __init__(self, backend: BurnerBackend, iso_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.backend = backend
        self.iso_path = iso_path
        self._thread: QThread | None = None
        self._worker: _BurnWorker | None = None

        self.setWindowTitle("Burn ISO to Disc")
        self.resize(560, 420)

        layout = QVBoxLayout(self)

        info = QLabel(
            f"<b>ISO:</b> {iso_path.name}<br>"
            f"<b>Backend:</b> {backend.label}"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        form = QFormLayout()
        self.drive_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_drives)
        drive_row = QHBoxLayout()
        drive_row.addWidget(self.drive_combo, 1)
        drive_row.addWidget(self.refresh_btn)
        drive_widget = QWidget()
        drive_widget.setLayout(drive_row)
        form.addRow("Drive:", drive_widget)

        self.verify_check = QCheckBox("Verify after burning")
        self.verify_check.setChecked(True)
        form.addRow("", self.verify_check)

        self.eject_check = QCheckBox("Eject when done")
        self.eject_check.setChecked(True)
        form.addRow("", self.eject_check)

        layout.addLayout(form)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready.")
        layout.addWidget(self.status_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        font = self.log_view.font()
        font.setFamily("Menlo, Consolas, monospace")
        self.log_view.setFont(font)
        layout.addWidget(self.log_view, 1)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        self.burn_btn = QPushButton("Burn")
        self.burn_btn.setDefault(True)
        self.button_box.addButton(self.burn_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        self.burn_btn.clicked.connect(self._start_burn)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._refresh_drives()

    def _refresh_drives(self) -> None:
        self.drive_combo.clear()
        try:
            drives = self.backend.list_drives()
        except Exception as e:
            self._log(f"Could not list drives: {e}")
            drives = []
        if not drives:
            self.drive_combo.addItem("(no drives detected)", None)
            self.burn_btn.setEnabled(False)
            return
        for d in drives:
            self.drive_combo.addItem(d.display(), d)
        self.burn_btn.setEnabled(True)

    def _start_burn(self) -> None:
        drive = self.drive_combo.currentData()
        if drive is None:
            QMessageBox.warning(self, "No drive", "Select a drive first.")
            return
        ans = QMessageBox.question(
            self, "Confirm burn",
            f"Burn {self.iso_path.name} to {drive.display()}?\n\n"
            "Make sure a blank or rewritable disc is inserted.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        self.burn_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        self._thread = QThread(self)
        self._worker = _BurnWorker(
            self.backend, self.iso_path, drive,
            self.verify_check.isChecked(), self.eject_check.isChecked(),
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        # GUI slots must run on the main thread — explicit QueuedConnection
        # because PySide6 routes Python callables as direct callbacks otherwise,
        # which causes QProgressBar.setValue() to repaint off the GUI thread.
        self._worker.progress.connect(
            self._on_progress, Qt.ConnectionType.QueuedConnection,
        )
        self._worker.log.connect(
            self._log, Qt.ConnectionType.QueuedConnection,
        )
        self._worker.finished.connect(
            self._on_done, Qt.ConnectionType.QueuedConnection,
        )
        self._thread.start()

    def _on_progress(self, message: str, fraction: float) -> None:
        if fraction < 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(fraction * 100))
        self.status_label.setText(message)

    def _log(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    def _on_done(self, success: bool, error: str) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._worker = None
        self.refresh_btn.setEnabled(True)
        self.burn_btn.setEnabled(True)
        if success:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.status_label.setText("✓ Burn complete.")
            QMessageBox.information(self, "Done", "Burn completed successfully.")
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.status_label.setText("✗ Burn failed.")
            QMessageBox.critical(self, "Burn failed", error)
