"""Tests for the burn dialog. Avoids triggering modal QMessageBoxes."""
from __future__ import annotations

from pathlib import Path

import pytest

from floppybootcd.core.burner import BurnerBackend, OpticalDrive
from floppybootcd.ui.burn_dialog import BurnDialog


class _FakeBackend(BurnerBackend):
    id = "fake"
    label = "Fake Burner"

    def __init__(self, drives=None, raise_on_list=False):
        self._drives = drives or []
        self._raise = raise_on_list
        self.burn_calls = []

    @classmethod
    def is_available(cls) -> bool:
        return True

    def list_drives(self):
        if self._raise:
            raise RuntimeError("listing failed")
        return list(self._drives)

    def burn(self, iso_path, drive, verify, eject, progress, log):
        self.burn_calls.append((iso_path, drive, verify, eject))
        progress("Done.", 1.0)


@pytest.fixture
def iso(tmp_path):
    p = tmp_path / "test.iso"
    p.write_bytes(b"\0" * 1024)
    return p


class TestBurnDialog:
    def test_populates_drives_in_combo(self, qtbot, iso):
        backend = _FakeBackend([
            OpticalDrive(device="/dev/sr0", name="Drive A"),
            OpticalDrive(device="/dev/sr1", name="Drive B"),
        ])
        dlg = BurnDialog(backend, iso)
        qtbot.addWidget(dlg)
        assert dlg.drive_combo.count() == 2
        assert dlg.burn_btn.isEnabled() is True

    def test_no_drives_disables_burn(self, qtbot, iso):
        backend = _FakeBackend([])
        dlg = BurnDialog(backend, iso)
        qtbot.addWidget(dlg)
        # The placeholder "no drives detected" item is added with data=None
        assert dlg.drive_combo.count() == 1
        assert dlg.burn_btn.isEnabled() is False

    def test_list_failure_logged(self, qtbot, iso):
        backend = _FakeBackend(raise_on_list=True)
        dlg = BurnDialog(backend, iso)
        qtbot.addWidget(dlg)
        log_text = dlg.log_view.toPlainText()
        assert "Could not list drives" in log_text

    def test_progress_updates_progress_bar_and_status(self, qtbot, iso):
        backend = _FakeBackend([OpticalDrive(device="/dev/sr0")])
        dlg = BurnDialog(backend, iso)
        qtbot.addWidget(dlg)
        dlg._on_progress("Burning chunk", 0.42)
        assert dlg.progress_bar.value() == 42
        assert dlg.status_label.text() == "Burning chunk"

    def test_progress_indeterminate_sets_busy_range(self, qtbot, iso):
        backend = _FakeBackend([OpticalDrive(device="/dev/sr0")])
        dlg = BurnDialog(backend, iso)
        qtbot.addWidget(dlg)
        dlg._on_progress("Working...", -1.0)
        # Indeterminate progress has range 0..0
        assert dlg.progress_bar.minimum() == 0
        assert dlg.progress_bar.maximum() == 0

    def test_log_appends(self, qtbot, iso):
        backend = _FakeBackend([OpticalDrive(device="/dev/sr0")])
        dlg = BurnDialog(backend, iso)
        qtbot.addWidget(dlg)
        dlg._log("hello")
        dlg._log("world")
        text = dlg.log_view.toPlainText()
        assert "hello" in text
        assert "world" in text
