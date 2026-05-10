"""Tests for the drag-drop floppy image list widget."""
from __future__ import annotations

from pathlib import Path

import pytest

from floppybootcd.core.project import FloppyImage
from floppybootcd.ui.image_list import FLOPPY_EXTS, ImageListWidget


@pytest.fixture
def widget(qtbot):
    w = ImageListWidget()
    qtbot.addWidget(w)
    return w


class TestImageListWidget:
    def test_extensions_set(self):
        assert ".img" in FLOPPY_EXTS
        assert ".ima" in FLOPPY_EXTS
        assert ".vfd" in FLOPPY_EXTS
        assert ".flp" in FLOPPY_EXTS

    def test_add_image(self, widget, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * 1474560)
        widget.add_image(FloppyImage(path=str(f)))
        assert widget.count() == 1
        assert widget.get_images()[0].path == str(f)

    def test_get_images_round_trip(self, widget, tmp_path):
        f1 = tmp_path / "a.img"
        f2 = tmp_path / "b.img"
        f1.write_bytes(b"x")
        f2.write_bytes(b"y")
        widget.add_image(FloppyImage(path=str(f1), label="A"))
        widget.add_image(FloppyImage(path=str(f2), label="B"))
        labels = [i.label for i in widget.get_images()]
        assert labels == ["A", "B"]

    def test_remove_selected_returns_count(self, widget, tmp_path):
        for n in ("a.img", "b.img", "c.img"):
            f = tmp_path / n
            f.write_bytes(b"x")
            widget.add_image(FloppyImage(path=str(f)))
        widget.item(0).setSelected(True)
        widget.item(2).setSelected(True)
        assert widget.remove_selected() == 2
        assert widget.count() == 1

    def test_format_label_includes_size_kb(self):
        # Non-existent file → size_bytes returns 0, formatter shows "0 KB".
        img = FloppyImage(path="/x/a.img")
        text = ImageListWidget._format_label(img)
        assert "0 KB" in text
        assert "a.img" in text

    def test_format_label_shows_default_star(self):
        img = FloppyImage(path="/x/a.img", default=True, label="Boot")
        text = ImageListWidget._format_label(img)
        assert text.startswith("★")
        assert "Boot" in text

    def test_format_label_no_star_when_not_default(self):
        img = FloppyImage(path="/x/a.img")
        text = ImageListWidget._format_label(img)
        assert not text.lstrip().startswith("★")

    def test_format_label_uses_mb_for_large_files(self, tmp_path):
        f = tmp_path / "big.img"
        # 5 MB sparse file (>= 4096 KB cutoff)
        with open(f, "wb") as fh:
            fh.seek(5 * 1024 * 1024)
            fh.write(b"\0")
        img = FloppyImage(path=str(f))
        text = ImageListWidget._format_label(img)
        assert "MB" in text


class TestEnterKeyEditsSelection:
    def test_enter_emits_edit_requested(self, widget, tmp_path, qtbot):
        from PySide6.QtCore import Qt as QtConst
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent

        f = tmp_path / "a.img"
        f.write_bytes(b"x")
        widget.add_image(FloppyImage(path=str(f)))
        widget.item(0).setSelected(True)

        with qtbot.waitSignal(widget.edit_requested, timeout=1000):
            qtbot.keyClick(widget, QtConst.Key.Key_Return)

    def test_enter_with_no_selection_does_not_emit(self, widget, qtbot):
        from PySide6.QtCore import Qt as QtConst
        emitted: list[None] = []
        widget.edit_requested.connect(lambda: emitted.append(None))
        qtbot.keyClick(widget, QtConst.Key.Key_Return)
        assert emitted == []


class TestExistingPaths:
    def test_existing_paths_set(self, widget, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"x")
        widget.add_image(FloppyImage(path=str(f)))
        assert str(f) in widget._existing_paths()

    def test_existing_paths_empty_for_empty_widget(self, widget):
        assert widget._existing_paths() == set()
