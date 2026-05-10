"""Tests for MainWindow state management. Avoids dialog-spawning code paths."""
from __future__ import annotations

from pathlib import Path

import pytest

from floppybootcd.core.project import FloppyImage, Project
from floppybootcd.ui.main_window import MainWindow


@pytest.fixture
def win(qtbot, tmp_path, monkeypatch):
    # Isolate QSettings into a temp location (Linux uses XDG_CONFIG_HOME).
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    w = MainWindow()
    # closeEvent() pops a modal "Unsaved changes?" dialog when dirty, which
    # hangs at qtbot teardown. Bypass the prompt for tests.
    monkeypatch.setattr(w, "_maybe_save", lambda: True)
    qtbot.addWidget(w)
    return w


class TestMainWindowAddPaths:
    def test_add_paths_appends_image(self, win, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * 1024)
        win._add_paths([str(f)])
        assert len(win.project.images) == 1
        assert win.project.images[0].path == str(f)

    def test_add_paths_dedups_existing(self, win, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * 1024)
        win._add_paths([str(f)])
        win._add_paths([str(f)])
        assert len(win.project.images) == 1

    def test_add_paths_marks_dirty(self, win, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * 1024)
        assert win._dirty is False
        win._add_paths([str(f)])
        assert win._dirty is True

    def test_add_paths_sets_default(self, win, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * 1024)
        win._add_paths([str(f)])
        assert win.project.images[0].default is True


class TestSetDefault:
    def test_set_default_makes_others_non_default(self, win, qtbot, tmp_path):
        for n in ("a.img", "b.img"):
            f = tmp_path / n
            f.write_bytes(b"x")
            win._add_paths([str(f)])
        # Select second item and make it default
        win.list_widget.item(1).setSelected(True)
        win._set_default()
        defaults = [img.default for img in win.project.images]
        assert defaults == [False, True]


class TestRefreshBurnButton:
    def test_disabled_with_no_images(self, win):
        assert win.save_iso_btn.isEnabled() is False
        assert win.burn_btn.isEnabled() is False

    def test_enabled_with_images(self, win, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"x")
        win._add_paths([str(f)])
        # _add_paths calls _mark_dirty → _refresh_burn_button
        assert win.save_iso_btn.isEnabled() is True
        assert win.burn_btn.isEnabled() is True


class TestProjectIO:
    def test_load_project_updates_state(self, win, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * 1024)
        p = Project(
            title="Loaded",
            images=[FloppyImage(path=str(f), label="A", default=True)],
            timeout_secs=42,
            menu_style="vesa",
        )
        out = tmp_path / "p.fbcd"
        p.save(out)

        loaded = Project.load(out)
        win.project = loaded
        win.project_path = out
        win._dirty = False
        win._reload_from_project()

        assert win.title_edit.text() == "Loaded"
        assert win.timeout_spin.value() == 42
        assert win.list_widget.count() == 1
        assert win.menu_style_combo.currentData() == "vesa"

    def test_dirty_flag_on_title_change(self, win):
        assert win._dirty is False
        win.title_edit.setText("New Title")
        assert win._dirty is True
        assert win.project.title == "New Title"

    def test_dirty_flag_on_timeout_change(self, win):
        win._dirty = False
        win.timeout_spin.setValue(99)
        assert win._dirty is True


class TestUpdateTitle:
    def test_untitled_when_no_path(self, win):
        win.project_path = None
        win._dirty = False
        win._update_title()
        assert "Untitled" in win.windowTitle()

    def test_dirty_marker_appears(self, win, tmp_path):
        win.project_path = tmp_path / "x.fbcd"
        win._dirty = True
        win._update_title()
        assert "•" in win.windowTitle()
        assert "x.fbcd" in win.windowTitle()
