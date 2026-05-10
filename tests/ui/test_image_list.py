"""Tests for the drag-drop floppy image list widget."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from floppybootcd.core.image_prep import ALL_ACCEPTED_EXTS, FLOPPY_EXTS
from floppybootcd.core.project import FloppyImage
from floppybootcd.ui.image_list import ImageListWidget


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

    def test_imz_in_accepted_exts(self):
        assert ".imz" in ALL_ACCEPTED_EXTS

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

    def test_format_label_includes_size_kb(self, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * 1024)  # 1 KB
        img = FloppyImage(path=str(f))
        text = ImageListWidget._format_label(img)
        assert "1 KB" in text
        assert "a.img" in text

    def test_format_label_missing_file_shows_missing(self):
        img = FloppyImage(path="/x/a.img")
        text = ImageListWidget._format_label(img)
        assert "missing" in text
        assert "a.img" in text

    def test_format_label_missing_imz_shows_missing_not_invalid(self):
        # A missing .imz must NOT be reported as "invalid .imz" — that
        # message is reserved for files that exist but fail to probe.
        img = FloppyImage(path="/x/missing.imz")
        text = ImageListWidget._format_label(img)
        assert "missing" in text
        assert "invalid" not in text

    def test_format_label_invalid_imz_shows_invalid(self, tmp_path):
        f = tmp_path / "broken.imz"
        f.write_bytes(b"this is not a zip")  # exists but won't probe
        img = FloppyImage(path=str(f))
        text = ImageListWidget._format_label(img)
        assert "invalid .imz" in text

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

    def test_format_label_imz_shows_inner_size(self, tmp_path):
        # An .imz that's tiny on disk but contains a 1440 KB inner image
        # should display the 1440 KB inner size, not the archive size.
        f = tmp_path / "boot.imz"
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("boot.ima", b"\0" * 1440 * 1024)
        assert f.stat().st_size < 100 * 1024  # archive is well under 100 KB
        img = FloppyImage(path=str(f))
        text = ImageListWidget._format_label(img)
        assert "1440 KB" in text


class TestDropEventAccepts:
    """Cover what dropEvent() accepts based on extension."""

    def _drop(self, widget, qtbot, paths):
        from PySide6.QtCore import QMimeData, QPoint, QUrl, Qt
        from PySide6.QtGui import QDropEvent

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
        event = QDropEvent(
            QPoint(0, 0),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        widget.dropEvent(event)

    def test_imz_drop_emits_files_dropped(self, widget, tmp_path, qtbot):
        f = tmp_path / "boot.imz"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("boot.ima", b"x")
        with qtbot.waitSignal(widget.files_dropped, timeout=1000) as blocker:
            self._drop(widget, qtbot, [f])
        # QUrl.toLocalFile() yields forward slashes on Windows; compare
        # path-normalized to avoid backslash-vs-forward-slash mismatches.
        assert [Path(p) for p in blocker.args[0]] == [f]

    def test_raw_img_drop_emits_files_dropped(self, widget, tmp_path, qtbot):
        f = tmp_path / "boot.img"
        f.write_bytes(b"x")
        with qtbot.waitSignal(widget.files_dropped, timeout=1000) as blocker:
            self._drop(widget, qtbot, [f])
        assert [Path(p) for p in blocker.args[0]] == [f]

    def test_unknown_extension_drop_does_not_emit(
        self, widget, tmp_path, qtbot
    ):
        f = tmp_path / "readme.txt"
        f.write_bytes(b"x")
        emitted: list[list[str]] = []
        widget.files_dropped.connect(lambda paths: emitted.append(paths))
        self._drop(widget, qtbot, [f])
        assert emitted == []


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
