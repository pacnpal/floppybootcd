"""Tests for MainWindow state management. Avoids dialog-spawning code paths."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from floppybootcd.core import image_prep
from floppybootcd.core.project import FloppyImage, Project
from floppybootcd.ui.main_window import MainWindow


@pytest.fixture
def win(qtbot, tmp_path, monkeypatch):
    # Replace the QSettings symbol that MainWindow constructs so we don't
    # mutate process-wide QSettings defaults / paths (which have no public
    # restore for setPath, so they would leak across tests in the same
    # interpreter). The replacement always points at a tmp INI file.
    import floppybootcd.ui.main_window as mw_mod

    ini_path = str(tmp_path / "settings.ini")

    class IsolatedQSettings(QSettings):
        def __init__(self, *_args, **_kwargs):
            super().__init__(ini_path, QSettings.Format.IniFormat)

    monkeypatch.setattr(mw_mod, "QSettings", IsolatedQSettings)

    w = MainWindow()
    # closeEvent() pops a modal "Unsaved changes?" dialog when dirty, which
    # hangs at qtbot teardown. Bypass the prompt for tests.
    monkeypatch.setattr(w, "_maybe_save", lambda: True)
    qtbot.addWidget(w)
    yield w


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

    def test_add_paths_dedup_normalizes_separators(self, win, tmp_path):
        """A path arriving with forward slashes (QUrl.toLocalFile()
        on Windows) and the same path with native separators must
        dedup against each other — _add_paths goes through
        normalize_for_dedup like the drop handlers."""
        f = tmp_path / "boot.img"
        f.write_bytes(b"x")
        # Native form (whatever the OS uses)
        win._add_paths([str(f)])
        assert len(win.project.images) == 1
        # Same file, alternate separator scheme. POSIX: identical
        # (forward slashes are native); Windows: forward-slash form
        # of the same absolute path. Either way normalize_for_dedup
        # must match against the existing entry.
        forward_form = str(f).replace("\\", "/")
        win._add_paths([forward_form])
        assert len(win.project.images) == 1, (
            "duplicate slipped past normalize_for_dedup"
        )

    def test_add_paths_within_call_dedup(self, win, tmp_path):
        """A single _add_paths call with the same path twice (in
        different forms) only adds it once."""
        f = tmp_path / "boot.img"
        f.write_bytes(b"x")
        win._add_paths([str(f), str(f), str(f).replace("\\", "/")])
        assert len(win.project.images) == 1

    def test_duplicate_only_add_does_not_mark_dirty(self, win, tmp_path):
        """A second drop of an already-listed file is a no-op. Without
        the added_any guard it used to flip _dirty=True even though
        nothing changed, which then prompted "Save changes?" on close
        even though the user hadn't touched anything."""
        f = tmp_path / "a.img"
        f.write_bytes(b"x")
        win._add_paths([str(f)])
        # Clear dirty manually to isolate the second call.
        win._dirty = False
        win._add_paths([str(f)])
        assert win._dirty is False, (
            "duplicate-only add should leave the dirty flag alone"
        )
        # And the image list is unchanged.
        assert len(win.project.images) == 1

    def test_empty_add_paths_does_not_mark_dirty(self, win):
        """An empty list is also a no-op — _add_paths used to mark dirty
        unconditionally."""
        assert win._dirty is False
        win._add_paths([])
        assert win._dirty is False


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


class TestOpenProjectPath:
    """open_project_path() is the public shared entry point used by
    drag-and-drop, the OS file-association handler (QFileOpenEvent /
    Explorer double-click / xdg-open) and the File → Open menu. The
    tests below lock its load / prompt / error contract in."""

    def test_open_project_path_loads_state(self, win, tmp_path):
        f = tmp_path / "boot.img"
        f.write_bytes(b"\0" * 1024)
        p = Project(
            title="Dropped Project",
            images=[FloppyImage(path=str(f), label="Boot", default=True)],
            timeout_secs=20,
        )
        out = tmp_path / "dropped.fbcd"
        p.save(out)

        win.open_project_path(str(out))

        assert win.project.title == "Dropped Project"
        assert win.project_path == out
        assert win.title_edit.text() == "Dropped Project"
        assert win.timeout_spin.value() == 20
        assert win.list_widget.count() == 1
        # Freshly loaded — not dirty.
        assert win._dirty is False

    def test_open_project_path_prompts_save_when_dirty(self, win, tmp_path, monkeypatch):
        """If the current project is dirty, the unsaved-changes prompt
        must run before load. Returning False from _maybe_save() must
        abort the load entirely (no project replacement)."""
        # Make the window dirty.
        original = win.project
        win._dirty = True

        # _maybe_save → False = "user clicked Cancel"
        called = {"n": 0}
        def fake_maybe_save():
            called["n"] += 1
            return False
        monkeypatch.setattr(win, "_maybe_save", fake_maybe_save)

        # Create a valid .fbcd to "try" to open. Won't get loaded.
        p = Project(title="Should Not Load", images=[])
        out = tmp_path / "x.fbcd"
        p.save(out)

        win.open_project_path(str(out))

        assert called["n"] == 1
        # Original project untouched.
        assert win.project is original
        assert win.project.title != "Should Not Load"

    def test_open_project_path_shows_error_on_failure(self, win, tmp_path, monkeypatch):
        """A corrupt / missing .fbcd surfaces a QMessageBox.critical
        and leaves the current project alone."""
        # Capture the critical() call without spawning a real dialog.
        seen = {}
        def fake_critical(parent, title, message):
            seen["title"] = title
            seen["message"] = message

        import floppybootcd.ui.main_window as mw_mod
        monkeypatch.setattr(mw_mod.QMessageBox, "critical", fake_critical)

        # A nonexistent path → Project.load() raises FileNotFoundError.
        original = win.project
        win.open_project_path(str(tmp_path / "does-not-exist.fbcd"))

        assert "Open failed" in seen.get("title", "")
        # The project the user was working on is preserved.
        assert win.project is original

    def test_open_project_path_rollback_on_partial_load_failure(
        self, win, tmp_path, monkeypatch
    ):
        """A .fbcd that parses cleanly but trips _reload_from_project()
        (e.g. a non-int timeout_secs that QSpinBox.setValue rejects)
        must NOT leave self.project / self.project_path / the widgets
        in a half-swapped state. The old project stays in place; the
        old widget contents stay in place; an error dialog surfaces."""
        seen = {}
        def fake_critical(parent, title, message):
            seen["title"] = title
            seen["message"] = message

        import floppybootcd.ui.main_window as mw_mod
        monkeypatch.setattr(mw_mod.QMessageBox, "critical", fake_critical)

        # Build a .fbcd whose schema parses but whose timeout_secs is
        # a string — Project.load is forgiving (dataclass accepts any
        # field value) but timeout_spin.setValue("nope") raises.
        import json
        bad = tmp_path / "bad.fbcd"
        bad.write_text(json.dumps({
            "title": "Loaded Title",
            "images": [],
            "timeout_secs": "not an int",
            "menu_style": "text",
            "bootloader": "isolinux",
            "syslinux_version": "6.03",
            "background_image": "",
            "notes": "",
        }))

        # Establish a known previous state.
        win.project = Project(title="Original", timeout_secs=42)
        win.project_path = None
        win._dirty = False
        win._reload_from_project()
        assert win.title_edit.text() == "Original"
        assert win.timeout_spin.value() == 42

        win.open_project_path(str(bad))

        # Error surfaced.
        assert "Open failed" in seen.get("title", "")
        # Project NOT swapped — the rollback ran.
        assert win.project.title == "Original"
        assert win.project_path is None
        # Widgets resynced to the original project.
        assert win.title_edit.text() == "Original"
        assert win.timeout_spin.value() == 42

    def test_open_project_path_rollback_preserves_dirty(
        self, win, tmp_path, monkeypatch
    ):
        """Regression: the rollback path used to restore _dirty BEFORE
        calling _reload_from_project(), which unconditionally sets
        _dirty=False at the end. The net effect was that opening a
        broken .fbcd silently clean-flagged a previously-dirty project
        — so the next close skipped the unsaved-changes prompt and
        lost the user's in-flight edits."""
        seen = {}
        def fake_critical(parent, title, message):
            seen["title"] = title
            seen["message"] = message

        import floppybootcd.ui.main_window as mw_mod
        monkeypatch.setattr(mw_mod.QMessageBox, "critical", fake_critical)

        # Establish a dirty current project.
        win.project = Project(title="In Progress", timeout_secs=15)
        win.project_path = None
        win._reload_from_project()  # clean
        win.title_edit.setText("In Progress edited")  # user edit → dirty
        assert win._dirty is True

        # Try to open a malformed .fbcd that survives Project.load but
        # blows up reload (same trick as the rollback test above).
        import json
        bad = tmp_path / "bad.fbcd"
        bad.write_text(json.dumps({
            "title": "X", "images": [],
            "timeout_secs": "not an int", "menu_style": "text",
            "bootloader": "isolinux", "syslinux_version": "6.03",
            "background_image": "", "notes": "",
        }))

        win.open_project_path(str(bad))

        # Error surfaced, AND the user's dirty edit survives.
        assert "Open failed" in seen.get("title", "")
        assert win._dirty is True, (
            "rollback lost the previously-dirty flag — closing the "
            "window now would skip the unsaved-changes prompt"
        )


class TestReloadDoesNotMarkDirty:
    """Regression: programmatic widget setters in _reload_from_project()
    used to fire textChanged / currentIndexChanged / valueChanged, which
    flipped _dirty=True so a freshly loaded or new project pretended to
    have unsaved changes. Block signals during reload."""

    def test_loading_project_leaves_clean_state(self, win, tmp_path):
        proj = Project(
            title="Loaded", bootloader="isolinux",
            menu_style="vesa", timeout_secs=42,
        )
        out = tmp_path / "p.fbcd"
        proj.save(out)

        # Sanity: dirty something so we can see the flip.
        win.title_edit.setText("dirtyfirst")
        assert win._dirty is True

        # Replicate the load-and-reload sequence from _open_project without
        # the file dialog.
        win.project = Project.load(out)
        win.project_path = out
        win._dirty = False
        win._reload_from_project()

        assert win._dirty is False
        assert win.title_edit.text() == "Loaded"
        assert win.timeout_spin.value() == 42
        assert win.menu_style_combo.currentData() == "vesa"

    def test_new_project_leaves_clean_state(self, win):
        win.title_edit.setText("not new")
        assert win._dirty is True
        win.project = Project()
        win._reload_from_project()
        assert win._dirty is False


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
    def test_value_is_threaded_into_build_options(self, win, tmp_path, monkeypatch):
        win.settings.setValue("xorriso_path", "/opt/custom/xorriso")
        f = tmp_path / "a.img"
        f.write_bytes(b"x")
        win._add_paths([str(f)])

        # Capture the BuildOptions handed to the worker without actually
        # building. Use monkeypatch (auto-restored) to neutralize QThread
        # so the worker never runs and BuildOptions so we can inspect it.
        captured: dict = {}
        from floppybootcd.core import iso_builder
        from PySide6.QtCore import QThread

        real_options = iso_builder.BuildOptions

        def spy_options(*args, **kwargs):
            opts = real_options(*args, **kwargs)
            captured["opts"] = opts
            return opts

        import floppybootcd.ui.main_window as mw_mod
        monkeypatch.setattr(mw_mod.iso_builder, "BuildOptions", spy_options)
        monkeypatch.setattr(QThread, "start", lambda self, *a, **k: None)
        win._build_iso(tmp_path / "out.iso", then_burn=False)

        assert captured["opts"].xorriso_override == "/opt/custom/xorriso"


class TestCapacityLabel:
    """The status-bar capacity indicator must reflect uncompressed
    inner-image size for .imz, and switch styling when over capacity."""

    def test_empty_project_shows_zero(self, win):
        text = win.capacity_label.text()
        assert text.startswith("Disc usage: 0.0 MiB")
        assert "MiB" in text  # binary unit, not "MB"

    def test_raw_image_counts_filesystem_size(self, win, tmp_path):
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * (2 * 1024 * 1024))  # 2 MiB
        win._add_paths([str(f)])
        text = win.capacity_label.text()
        assert "2.0 MiB" in text

    def test_imz_counts_uncompressed_inner_size(self, win, tmp_path):
        # Tiny on disk, 1440 KiB inner — capacity should reflect inner.
        f = tmp_path / "boot.imz"
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("boot.ima", b"\0" * 1440 * 1024)
        assert f.stat().st_size < 100 * 1024  # archive is well under 100 KiB
        win._add_paths([str(f)])
        text = win.capacity_label.text()
        # 1440 KiB ≈ 1.4 MiB
        assert "1.4 MiB" in text

    def test_over_capacity_shows_warning_and_red(
        self, win, tmp_path, monkeypatch
    ):
        # Shrink the usable capacity so a small file pushes us over.
        monkeypatch.setattr(image_prep, "CD_USABLE_BYTES", 1024)
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * 4096)  # 4 KiB > 1 KiB usable
        win._add_paths([str(f)])
        text = win.capacity_label.text()
        assert "over CD-R capacity" in text
        assert "#b00020" in win.capacity_label.styleSheet()

    def test_within_capacity_no_warning(self, win, tmp_path, monkeypatch):
        monkeypatch.setattr(
            image_prep, "CD_USABLE_BYTES", 100 * 1024 * 1024
        )
        f = tmp_path / "a.img"
        f.write_bytes(b"\0" * 1024)  # tiny
        win._add_paths([str(f)])
        text = win.capacity_label.text()
        assert "over CD-R capacity" not in text
        assert "near limit" not in text


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
