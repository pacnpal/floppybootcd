"""Tests for MainWindow state management. Avoids dialog-spawning code paths."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from floppybootcd.core.project import FloppyImage, Project
from floppybootcd.ui.main_window import MainWindow


@pytest.fixture
def win(qtbot, tmp_path, monkeypatch):
    # Isolate QSettings to a temp INI file. XDG_CONFIG_HOME alone only works
    # on Linux — Windows uses the registry, macOS uses plists. Forcing
    # IniFormat + a custom path covers all three.
    prev_default = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path / "qsettings"),
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    w = MainWindow()
    # closeEvent() pops a modal "Unsaved changes?" dialog when dirty, which
    # hangs at qtbot teardown. Bypass the prompt for tests.
    monkeypatch.setattr(w, "_maybe_save", lambda: True)
    qtbot.addWidget(w)
    yield w
    # Restore global QSettings defaults so this fixture doesn't leak into
    # other tests sharing the process.
    QSettings.setDefaultFormat(prev_default)


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


class TestProjectSyncOnUIChange:
    """Regression: UI controls must write through to self.project AND mark
    dirty, otherwise edits are silently lost on Save Project."""

    def test_bootloader_change_syncs_and_marks_dirty(self, win):
        win._dirty = False
        # The combo only has ISOLINUX by default; force a manual data change
        # via the slot directly so the test isn't dependent on having two
        # registered backends.
        win.bootloader_combo.addItem("Fake Bootloader", "fake-id")
        win.bootloader_combo.setCurrentIndex(win.bootloader_combo.count() - 1)
        assert win.project.bootloader == "fake-id"
        assert win._dirty is True

    def test_timeout_change_syncs_and_marks_dirty(self, win):
        win._dirty = False
        win.timeout_spin.setValue(77)
        assert win.project.timeout_secs == 77
        assert win._dirty is True

    def test_save_after_timeout_change_persists_value(self, win, tmp_path):
        """The whole point of #4: edit timeout, save, reopen — value sticks."""
        win.timeout_spin.setValue(123)
        out = tmp_path / "p.fbcd"
        win.project_path = out
        ok = win._save_project()
        assert ok is True
        # Re-open from disk and check the persisted value.
        loaded = Project.load(out)
        assert loaded.timeout_secs == 123


class TestXorrisoPathSetting:
    def test_value_is_threaded_into_build_options(self, win, tmp_path):
        win.settings.setValue("xorriso_path", "/opt/custom/xorriso")
        f = tmp_path / "a.img"
        f.write_bytes(b"x")
        win._add_paths([str(f)])

        # Capture the BuildOptions handed to the worker without actually
        # building. Patch QThread.start so the worker never runs.
        captured: dict = {}
        from floppybootcd.core import iso_builder

        real_options = iso_builder.BuildOptions

        def spy_options(*args, **kwargs):
            opts = real_options(*args, **kwargs)
            captured["opts"] = opts
            return opts

        import floppybootcd.ui.main_window as mw_mod
        original = mw_mod.iso_builder.BuildOptions
        mw_mod.iso_builder.BuildOptions = spy_options
        try:
            from PySide6.QtCore import QThread
            QThread.start = lambda self, *a, **k: None  # type: ignore[assignment]
            win._build_iso(tmp_path / "out.iso", then_burn=False)
        finally:
            mw_mod.iso_builder.BuildOptions = original

        assert captured["opts"].xorriso_override == "/opt/custom/xorriso"


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
