"""MainWindow: the top-level UI."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QThread, Qt, Signal, Slot
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSpinBox, QSplitter, QStatusBar, QToolBar,
    QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__
from ..core import burner as burner_mod
from ..core import iso_builder, syslinux_fetcher
from ..core.bootloader import BUILTIN_BACKENDS, available_backends
from ..core.project import PROJECT_EXT, FloppyImage, Project
from .burn_dialog import BurnDialog
from ..core import image_prep
from ..core.image_prep import ALL_ACCEPTED_EXTS
from .image_list import ImageListWidget


class _BuildWorker(QObject):
    """Background ISO build worker."""
    progress = Signal(str, float)
    log = Signal(str)
    finished = Signal(bool, str, str)   # success, error, iso_path

    def __init__(self, project: Project, options: iso_builder.BuildOptions):
        super().__init__()
        self.project = project
        self.options = options

    @Slot()
    def run(self) -> None:
        try:
            result = iso_builder.build(
                self.project, self.options,
                progress=lambda m, f: self.progress.emit(m, f),
                log=lambda m: self.log.emit(m),
            )
            self.finished.emit(True, "", str(result.iso_path))
        except Exception as e:
            self.finished.emit(False, str(e), "")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = Project()
        self.project_path: Path | None = None
        self._build_thread: QThread | None = None
        self._build_worker: _BuildWorker | None = None
        self._last_iso: Path | None = None
        self._dirty = False

        self.settings = QSettings("pacnpal", APP_NAME)

        self.setWindowTitle(APP_NAME)
        self.resize(820, 640)
        self.setAcceptDrops(True)

        self._build_ui()
        self._build_menus()
        self._build_toolbar()
        self._restore_geometry()
        self._update_title()

    # ── UI construction ─────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # Top: project title + bootloader settings
        top = QGroupBox("Project")
        top_form = QFormLayout(top)
        self.title_edit = QLineEdit(self.project.title)
        self.title_edit.textChanged.connect(self._on_title_changed)
        top_form.addRow("Disc title:", self.title_edit)

        self.bootloader_combo = QComboBox()
        for cls in available_backends():
            self.bootloader_combo.addItem(cls.label, cls.id)
        self.bootloader_combo.currentIndexChanged.connect(self._on_bootloader_changed)
        top_form.addRow("Bootloader:", self.bootloader_combo)

        self.menu_style_combo = QComboBox()
        self.menu_style_combo.addItem("Text menu (menu.c32)", "text")
        self.menu_style_combo.addItem("Graphical menu (vesamenu.c32)", "vesa")
        self.menu_style_combo.currentIndexChanged.connect(self._on_menu_style_changed)
        top_form.addRow("Menu style:", self.menu_style_combo)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(0, 600)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setValue(self.project.timeout_secs)
        self.timeout_spin.setSpecialValueText("No auto-boot")
        self.timeout_spin.valueChanged.connect(self._on_timeout_changed)
        top_form.addRow("Boot timeout:", self.timeout_spin)

        outer.addWidget(top)

        # Middle: image list + side buttons
        middle = QHBoxLayout()
        self.list_widget = ImageListWidget()
        self.list_widget.files_dropped.connect(self._add_paths)
        self.list_widget.project_dropped.connect(self.open_project_path)
        self.list_widget.items_reordered.connect(self._on_list_reordered)
        self.list_widget.selection_changed.connect(self._update_selection_buttons)
        self.list_widget.itemDoubleClicked.connect(lambda _: self._edit_selected())
        self.list_widget.edit_requested.connect(self._edit_selected)
        middle.addWidget(self.list_widget, 1)

        side = QVBoxLayout()
        side.setSpacing(6)
        self.add_btn = QPushButton("Add Images...")
        self.add_btn.clicked.connect(self._add_images)
        side.addWidget(self.add_btn)
        self.edit_btn = QPushButton("Edit...")
        self.edit_btn.clicked.connect(self._edit_selected)
        side.addWidget(self.edit_btn)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_selected)
        side.addWidget(self.remove_btn)
        side.addSpacing(12)
        self.set_default_btn = QPushButton("Set as Default")
        self.set_default_btn.clicked.connect(self._set_default)
        side.addWidget(self.set_default_btn)
        side.addStretch()
        side_widget = QWidget()
        side_widget.setLayout(side)
        side_widget.setFixedWidth(140)
        middle.addWidget(side_widget)
        outer.addLayout(middle, 1)

        # Bottom: log + progress + actions
        bottom = QFrame()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("Log:"))
        log_row.addStretch()
        self.clear_log_btn = QPushButton("Clear")
        self.clear_log_btn.setFlat(True)
        self.clear_log_btn.clicked.connect(lambda: self.log_view.clear())
        log_row.addWidget(self.clear_log_btn)
        bottom_layout.addLayout(log_row)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        font = self.log_view.font()
        # setFamilies() takes a fallback list; setFamily() only takes one
        # family name and treats a comma-separated string as a single
        # bogus family — Qt then spends ~60ms at startup populating
        # font-family aliases and prints a warning.
        font.setFamilies(["Menlo", "Consolas", "monospace"])
        self.log_view.setFont(font)
        bottom_layout.addWidget(self.log_view)

        actions_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        actions_row.addWidget(self.progress_bar, 1)

        self.save_iso_btn = QPushButton("Save ISO...")
        self.save_iso_btn.clicked.connect(self._save_iso)
        actions_row.addWidget(self.save_iso_btn)

        self.burn_btn = QPushButton("Burn to Disc...")
        self.burn_btn.clicked.connect(self._burn)
        actions_row.addWidget(self.burn_btn)

        bottom_layout.addLayout(actions_row)
        outer.addWidget(bottom)

        self.setStatusBar(QStatusBar())
        self.capacity_label = QLabel()
        self.capacity_label.setToolTip(
            "Total floppy payload that will be written to the disc, vs. "
            "the usable capacity of an 80-minute 700 MiB CD-R after "
            "bootloader and ISO 9660 overhead. Compressed (.imz) images "
            "count by their uncompressed size."
        )
        self.statusBar().addPermanentWidget(self.capacity_label)
        self._update_selection_buttons()
        self._refresh_burn_button()
        self._refresh_capacity_label()

    def _build_menus(self) -> None:
        m_file = self.menuBar().addMenu("&File")

        a_new = QAction("&New Project", self)
        a_new.setShortcut(QKeySequence.StandardKey.New)
        a_new.triggered.connect(self._new_project)
        m_file.addAction(a_new)

        a_open = QAction("&Open Project...", self)
        a_open.setShortcut(QKeySequence.StandardKey.Open)
        a_open.triggered.connect(self._open_project)
        m_file.addAction(a_open)

        a_save = QAction("&Save Project", self)
        a_save.setShortcut(QKeySequence.StandardKey.Save)
        a_save.triggered.connect(self._save_project)
        m_file.addAction(a_save)

        a_save_as = QAction("Save Project &As...", self)
        a_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        a_save_as.triggered.connect(self._save_project_as)
        m_file.addAction(a_save_as)

        m_file.addSeparator()

        a_save_iso = QAction("Save &ISO...", self)
        a_save_iso.setShortcut("Ctrl+B")
        a_save_iso.triggered.connect(self._save_iso)
        m_file.addAction(a_save_iso)

        a_burn = QAction("&Burn to Disc...", self)
        a_burn.setShortcut("Ctrl+Shift+B")
        a_burn.triggered.connect(self._burn)
        m_file.addAction(a_burn)

        m_file.addSeparator()
        a_quit = QAction("&Quit", self)
        a_quit.setShortcut(QKeySequence.StandardKey.Quit)
        a_quit.triggered.connect(self.close)
        m_file.addAction(a_quit)

        m_edit = self.menuBar().addMenu("&Edit")
        a_add = QAction("&Add Images...", self)
        a_add.setShortcut("Ctrl+I")
        a_add.triggered.connect(self._add_images)
        m_edit.addAction(a_add)

        m_tools = self.menuBar().addMenu("&Tools")
        a_xorriso = QAction("Set &xorriso Path...", self)
        a_xorriso.triggered.connect(self._set_xorriso_path)
        m_tools.addAction(a_xorriso)
        m_tools.addSeparator()
        a_clear_cache = QAction("Clear Syslinux Cache", self)
        a_clear_cache.triggered.connect(self._clear_syslinux_cache)
        m_tools.addAction(a_clear_cache)

        m_help = self.menuBar().addMenu("&Help")
        a_about = QAction("&About " + APP_NAME, self)
        a_about.triggered.connect(self._show_about)
        m_help.addAction(a_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(tb.iconSize())
        self.addToolBar(tb)

        a_add = QAction("Add Images", self)
        a_add.triggered.connect(self._add_images)
        tb.addAction(a_add)

        tb.addSeparator()

        a_save_iso = QAction("Save ISO", self)
        a_save_iso.triggered.connect(self._save_iso)
        tb.addAction(a_save_iso)

        a_burn = QAction("Burn", self)
        a_burn.triggered.connect(self._burn)
        tb.addAction(a_burn)

    # ── Project management ───────────────────────────────────────────────────────

    def _on_title_changed(self, txt: str) -> None:
        self.project.title = txt
        self._mark_dirty()

    def _on_menu_style_changed(self) -> None:
        # Switching to/from VESA changes whether the background image
        # counts against capacity, so refresh that indicator.
        self.project.menu_style = self.menu_style_combo.currentData()
        self._refresh_capacity_label()
        self._mark_dirty()

    def _on_bootloader_changed(self) -> None:
        data = self.bootloader_combo.currentData()
        if data is None:
            return
        self.project.bootloader = data
        self._mark_dirty()

    def _on_timeout_changed(self, value: int) -> None:
        self.project.timeout_secs = value
        self._mark_dirty()

    def _on_list_reordered(self) -> None:
        self.project.images = self.list_widget.get_images()
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._update_title()
        self._refresh_burn_button()

    def _update_title(self) -> None:
        bits = [APP_NAME]
        if self.project_path:
            bits.append("—")
            bits.append(self.project_path.name)
        else:
            bits.append("—")
            bits.append("Untitled")
        if self._dirty:
            bits.append("•")
        self.setWindowTitle(" ".join(bits))

    def _maybe_save(self) -> bool:
        """Prompt to save if dirty. Returns False if user cancels."""
        if not self._dirty:
            return True
        ans = QMessageBox.question(
            self, "Unsaved changes",
            "Save changes to the current project?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if ans == QMessageBox.StandardButton.Cancel:
            return False
        if ans == QMessageBox.StandardButton.Save:
            return self._save_project()
        return True

    def _new_project(self) -> None:
        if not self._maybe_save():
            return
        self.project = Project()
        self.project_path = None
        self._dirty = False
        self._reload_from_project()

    def _open_project(self) -> None:
        # The unsaved-changes prompt lives inside open_project_path()
        # so the Open menu, drag-and-drop, OS file-association, and CLI
        # paths share one prompt. Calling _maybe_save() here too would
        # double-prompt on dirty projects.
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", str(Path.home()),
            f"FloppyBootCD Project (*{PROJECT_EXT});;All files (*)",
        )
        if path:
            self.open_project_path(path)

    def open_project_path(self, path: str) -> bool:
        """Load *path* as the current project.

        Public so drag-and-drop on the window, the OS file-association
        handler (macOS QFileOpenEvent / Windows file-double-click /
        Linux ``xdg-open``), and any future scripted entry points can
        share one code path with the File → Open menu action.

        Honors the unsaved-changes prompt the menu action would: a
        dirty current project is offered Save / Discard / Cancel
        before the new project replaces it.

        Failure semantics: a malformed .fbcd that loads but blows up
        during ``_reload_from_project()`` (e.g. a non-int
        ``timeout_secs`` that ``QSpinBox.setValue`` rejects) leaves
        the window's previous project AND widgets intact — the swap
        is all-or-nothing. A naive "assign first, reload after"
        sequence would have left ``self.project`` pointing at the
        new project but widgets showing the old one, an internally
        inconsistent state where File → Save would write the new
        project to the new path while the user stared at old data.

        Returns:
            ``True`` if the project was successfully loaded;
            ``False`` if the user cancelled the unsaved-changes prompt
            or if loading / reloading failed (in which case an error
            dialog has already been shown).
        """
        if not self._maybe_save():
            return False

        # Snapshot before any swap so a failure can fully roll back.
        prev_project = self.project
        prev_path = self.project_path
        prev_dirty = self._dirty
        try:
            self.project = Project.load(path)
            self.project_path = Path(path)
            self._dirty = False
            self._reload_from_project()
            return True
        except Exception as e:
            # Atomic rollback. _reload_from_project may have partially
            # populated some widgets before raising; re-running it
            # against the restored project resyncs them.
            #
            # Order matters: _reload_from_project() unconditionally
            # sets self._dirty = False at the end (it's the "we just
            # loaded a fresh project, nothing's changed yet" signal
            # for the normal success path). If we restore _dirty
            # *before* the reload, the reload wipes it. Restore the
            # state-bearing fields first, run the reload to resync
            # widgets, then re-apply prev_dirty so a dirty project
            # the user was just looking at stays marked dirty after
            # a failed open.
            self.project = prev_project
            self.project_path = prev_path
            try:
                self._reload_from_project()
            except Exception:
                # If even the rollback reload fails (it shouldn't —
                # the previous project is what was already on screen),
                # don't mask the original error with a secondary one.
                pass
            self._dirty = prev_dirty
            self._update_title()
            QMessageBox.critical(
                self, "Open failed",
                f"{path}\n\n{e}",
            )
            return False

    def _save_project(self) -> bool:
        if not self.project_path:
            return self._save_project_as()
        try:
            self.project.save(self.project_path)
            self._dirty = False
            self._update_title()
            self.statusBar().showMessage(f"Saved {self.project_path.name}", 3000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return False

    def _save_project_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", str(Path.home() / f"untitled{PROJECT_EXT}"),
            f"FloppyBootCD Project (*{PROJECT_EXT})",
        )
        if not path:
            return False
        if not path.lower().endswith(PROJECT_EXT):
            path += PROJECT_EXT
        self.project_path = Path(path)
        return self._save_project()

    def _reload_from_project(self) -> None:
        # Block signals while we push project state into the widgets — the
        # textChanged / currentIndexChanged / valueChanged handlers all
        # call _mark_dirty(), which would otherwise flag a freshly-loaded
        # project as having unsaved changes.
        widgets = [
            self.title_edit, self.bootloader_combo,
            self.menu_style_combo, self.timeout_spin,
        ]
        prev = [w.blockSignals(True) for w in widgets]
        try:
            self.title_edit.setText(self.project.title)
            for combo, value in (
                (self.bootloader_combo, self.project.bootloader),
                (self.menu_style_combo, self.project.menu_style),
            ):
                for i in range(combo.count()):
                    if combo.itemData(i) == value:
                        combo.setCurrentIndex(i)
                        break
            self.timeout_spin.setValue(self.project.timeout_secs)
        finally:
            for w, p in zip(widgets, prev):
                w.blockSignals(p)
        self.list_widget.clear()
        for img in self.project.images:
            self.list_widget.add_image(img)
        self._dirty = False
        self._update_title()
        self._refresh_burn_button()
        self._refresh_capacity_label()

    # ── Image operations ─────────────────────────────────────────────────────────

    def _add_images(self) -> None:
        last_dir = self.settings.value("last_image_dir", str(Path.home()))
        exts = " ".join(f"*{e}" for e in sorted(ALL_ACCEPTED_EXTS))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Floppy Images", last_dir,
            f"Floppy images ({exts});;All files (*)",
        )
        if paths:
            self.settings.setValue("last_image_dir", str(Path(paths[0]).parent))
            self._add_paths(paths)

    def _add_paths(self, paths: list[str]) -> None:
        # Dedup against the current project using the same normalized
        # form the drop handlers and hover gate use, so a path
        # arriving via CLI / QFileOpenEvent in one casing or
        # separator scheme can't slip past dedup against an
        # equivalent path stored from another source. The stored
        # FloppyImage.path keeps the user's original form for
        # display; normalization is for comparison only. See
        # image_prep.normalize_for_dedup for the rationale.
        from ..core.image_prep import normalize_for_dedup
        existing = {normalize_for_dedup(i.path) for i in self.project.images}
        added_any = False
        for p in paths:
            key = normalize_for_dedup(p)
            if key in existing:
                continue
            existing.add(key)  # within-call dedup too
            img = FloppyImage(path=p, label=Path(p).stem)
            self.project.images.append(img)
            self.list_widget.add_image(img)
            added_any = True
        # Guard side effects so a duplicate-only add (every dropped path
        # matched an existing image) doesn't flip the project to dirty
        # or recompute the capacity label for no reason. Without this
        # the title bar grows a bullet after a no-op drag-drop, which
        # then prompts an "unsaved changes?" dialog on close even
        # though nothing changed.
        if not added_any:
            return
        self.project.ensure_one_default()
        self._refresh_default_marker()
        self._refresh_capacity_label()
        self._mark_dirty()

    def add_paths(self, paths: list[str]) -> None:
        """Public counterpart to :meth:`_add_paths`. Lets out-of-module
        callers (the QFileOpenEvent dispatcher in ``app.py``, future
        plugin entry points) feed floppy-image paths in without
        reaching across the underscore boundary. Behavior identical
        to ``_add_paths``: dedups, sets a default, refreshes the
        capacity label, marks the project dirty."""
        self._add_paths(paths)

    def _remove_selected(self) -> None:
        n = self.list_widget.remove_selected()
        if n:
            self.project.images = self.list_widget.get_images()
            self.project.ensure_one_default()
            self._refresh_default_marker()
            self._refresh_capacity_label()
            self._mark_dirty()

    def _edit_selected(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        item = items[0]
        img: FloppyImage = item.data(Qt.ItemDataRole.UserRole)

        # Lightweight inline edit dialog. Only the bits that users
        # actually want to flip per-entry: the menu label (free text)
        # and whether the boot prompt's Tab editor is offered at boot
        # time for this entry. Description / hotkey / default come
        # from the .fbcd file and are handled elsewhere.
        from PySide6.QtWidgets import (
            QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
        )
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit entry — {img.filename}")
        form = QFormLayout(dlg)
        label_edit = QLineEdit(img.label)
        label_edit.setPlaceholderText(img.filename)
        form.addRow("Boot menu label:", label_edit)
        editable_check = QCheckBox(
            "Allow editing at boot prompt (Tab key on the entry)"
        )
        editable_check.setChecked(img.editable)
        editable_check.setToolTip(
            "Syslinux's Tab-to-edit lock is global, not per-entry — "
            "marking ANY image as not editable causes the generated "
            "isolinux.cfg to emit ALLOWOPTIONS 0, which disables Tab "
            "and Esc for every entry on the disc (including "
            "Boot from hard disk / Reboot / Shutdown).\n\n"
            "When every image is editable (the default), the syslinux "
            "default kicks in and Tab works normally."
        )
        form.addRow("", editable_check)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        img.label = label_edit.text().strip()
        img.editable = editable_check.isChecked()
        row = self.list_widget.row(item)
        self.list_widget.update_item(row)
        self._mark_dirty()

    def _set_default(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        target_img: FloppyImage = items[0].data(Qt.ItemDataRole.UserRole)
        for img in self.project.images:
            img.default = (img is target_img)
        self._refresh_default_marker()
        self._mark_dirty()

    def _refresh_default_marker(self) -> None:
        for i in range(self.list_widget.count()):
            self.list_widget.update_item(i)

    def _update_selection_buttons(self) -> None:
        has_selection = bool(self.list_widget.selectedItems())
        self.edit_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)
        self.set_default_btn.setEnabled(has_selection)

    def _refresh_burn_button(self) -> None:
        ready = bool(self.project.images)
        self.save_iso_btn.setEnabled(ready)
        self.burn_btn.setEnabled(ready)

    def _refresh_capacity_label(self) -> None:
        """Update the status bar's running total / CD capacity indicator."""
        used = image_prep.total_disc_payload(
            (img.path for img in self.project.images),
            vesa_background=(
                self.project.background_image
                if self.project.menu_style == "vesa"
                else None
            ),
        )
        usable = image_prep.CD_USABLE_BYTES
        used_mib = used / (1024 * 1024)
        usable_mib = usable / (1024 * 1024)
        text = f"Disc usage: {used_mib:.1f} MiB / {usable_mib:.0f} MiB"
        if used > usable:
            text += "  ⚠ over CD-R capacity"
            color = "color: #b00020;"
        elif used > usable * 0.9:
            text += "  (near limit)"
            color = "color: #b35900;"
        else:
            color = ""
        self.capacity_label.setText(text)
        self.capacity_label.setStyleSheet(color)

    # ── ISO build / burn ────────────────────────────────────────────────────────

    def _save_iso(self) -> None:
        last_dir = self.settings.value("last_iso_dir", str(Path.home()))
        default_name = (self.project.title or "FloppyBootCD") + ".iso"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save ISO", str(Path(last_dir) / default_name),
            "ISO image (*.iso);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".iso"):
            path += ".iso"
        self.settings.setValue("last_iso_dir", str(Path(path).parent))
        self._build_iso(Path(path), then_burn=False)

    def _burn(self) -> None:
        backend = burner_mod.get_native_burner()
        if backend is None:
            QMessageBox.warning(
                self, "No burner",
                "No native CD burner is available on this platform. "
                "On Linux, install xorriso or wodim.",
            )
            return
        # Build to a temp ISO, then open burn dialog
        import tempfile
        tmp_iso = Path(tempfile.gettempdir()) / "floppybootcd_temp.iso"
        self._build_iso(tmp_iso, then_burn=True, burn_backend=backend)

    def _build_iso(self, output_path: Path, then_burn: bool,
                    burn_backend: burner_mod.BurnerBackend | None = None) -> None:
        if self._build_thread is not None:
            QMessageBox.warning(self, "Busy", "A build is already in progress.")
            return
        # Snapshot project state from UI (covers any in-flight edits)
        self.project.images = self.list_widget.get_images()
        self.project.title = self.title_edit.text() or "FloppyBootCD"
        self.project.timeout_secs = self.timeout_spin.value()
        self.project.menu_style = self.menu_style_combo.currentData()
        self.project.bootloader = self.bootloader_combo.currentData()

        problems = iso_builder.validate_project(self.project)
        if problems:
            QMessageBox.warning(
                self, "Cannot build",
                "Fix these issues first:\n\n• " + "\n• ".join(problems),
            )
            return

        options = iso_builder.BuildOptions(
            output_path=output_path,
            xorriso_override=str(self.settings.value("xorriso_path", "")),
        )
        self._build_thread = QThread(self)
        self._build_worker = _BuildWorker(self.project, options)
        self._build_worker.moveToThread(self._build_thread)

        # Stash dispatch params for the @Slot-decorated finish handler. A bare
        # lambda or undecorated Python callable would get treated as a generic
        # CallbackDynamicSlot and queued onto the *worker* thread, not the GUI
        # thread — so the slots below are real @Slot methods on `self`.
        self._build_then_burn = then_burn
        self._build_burn_backend = burn_backend

        self._build_thread.started.connect(self._build_worker.run)
        self._build_worker.progress.connect(
            self._on_progress, Qt.ConnectionType.QueuedConnection,
        )
        self._build_worker.log.connect(
            self._append_log, Qt.ConnectionType.QueuedConnection,
        )
        self._build_worker.finished.connect(
            self._on_build_done_dispatch, Qt.ConnectionType.QueuedConnection,
        )

        self.save_iso_btn.setEnabled(False)
        self.burn_btn.setEnabled(False)
        self.statusBar().showMessage("Building ISO...")
        self._append_log(f"=== Building {output_path} ===")
        self._build_thread.start()

    @Slot(str, float)
    def _on_progress(self, message: str, fraction: float) -> None:
        if fraction < 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(fraction * 100))
        self.statusBar().showMessage(message)

    @Slot(str)
    def _append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    @Slot(bool, str, str)
    def _on_build_done_dispatch(self, success: bool, error: str, iso_path: str) -> None:
        self._on_build_done(
            success, error, iso_path,
            self._build_then_burn, self._build_burn_backend,
        )

    def _on_build_done(self, success: bool, error: str, iso_path: str,
                       then_burn: bool,
                       burn_backend: burner_mod.BurnerBackend | None) -> None:
        if self._build_thread:
            self._build_thread.quit()
            self._build_thread.wait()
        self._build_thread = None
        self._build_worker = None

        self.progress_bar.setRange(0, 100)
        self._refresh_burn_button()

        if not success:
            self.progress_bar.setValue(0)
            self.statusBar().showMessage("Build failed.", 5000)
            QMessageBox.critical(self, "Build failed", error)
            return

        self.progress_bar.setValue(100)
        self._last_iso = Path(iso_path)
        self.statusBar().showMessage(f"Built {self._last_iso.name}", 5000)

        if then_burn and burn_backend is not None:
            dlg = BurnDialog(burn_backend, self._last_iso, self)
            dlg.exec()
        else:
            QMessageBox.information(
                self, "ISO built",
                f"Saved to:\n{iso_path}",
            )

    # ── Tools ───────────────────────────────────────────────────────────────────────

    def _set_xorriso_path(self) -> None:
        current = str(self.settings.value("xorriso_path", ""))
        path, _ = QFileDialog.getOpenFileName(
            self, "Locate xorriso",
            current or str(Path.home()),
            "All files (*)",
        )
        if not path:
            return
        if not Path(path).is_file():
            QMessageBox.warning(self, "Not found",
                                f"No file at:\n{path}")
            return
        self.settings.setValue("xorriso_path", path)
        self.statusBar().showMessage(f"xorriso path set: {path}", 5000)
        self._append_log(f"xorriso override set to: {path}")

    def _clear_syslinux_cache(self) -> None:
        ans = QMessageBox.question(
            self, "Clear cache",
            "Delete cached syslinux binaries? They will be re-downloaded "
            "on the next build.",
        )
        if ans == QMessageBox.StandardButton.Yes:
            syslinux_fetcher.clear_cache()
            self.statusBar().showMessage("Syslinux cache cleared.", 3000)

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "About " + APP_NAME,
            f"<h3>{APP_NAME}</h3>"
            f"<p>Version {__version__}</p>"
            "<p>Build bootable CDs from collections of floppy disk images "
            "for vintage computers.</p>"
            "<p>Uses ISOLINUX + MEMDISK from the Syslinux project. "
            "Cross-platform native burning via hdiutil (macOS), "
            "isoburn.exe (Windows), and xorriso (Linux).</p>"
        )

    # ── Drag-drop on window itself ───────────────────────────────────────────────────
    # The main window is its own drop target as a backstop for when
    # the cursor lands outside the image list widget (margins, header,
    # log panel). It accepts the same shapes the list widget does:
    # individual floppy images, folders to recurse, and .fbcd project
    # files (which trigger an open-project flow instead of being added
    # as images).

    def dragEnterEvent(self, e) -> None:
        # Delegate the actionability decision to the list widget's
        # hover gate so the two drop targets agree on what counts.
        # The list widget owns the existing-paths dedup check; both
        # drop targets get the same "all duplicates → don't show
        # accept cursor" behavior by routing through the same
        # public method.
        if self.list_widget.mime_is_acceptable(e.mimeData()):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e) -> None:
        if not e.mimeData().hasUrls():
            return
        # parse_dropped_urls applies the project-wins-over-images rule
        # and normalizes paths for dedup against the current project.
        # Single helper lets the list-widget and window-level drops
        # share semantics — see image_list.parse_dropped_urls.
        from .image_list import parse_dropped_urls

        existing_paths = [img.path for img in self.project.images]
        project_path, floppy_paths = parse_dropped_urls(
            e.mimeData().urls(), existing_paths,
        )
        if project_path:
            if self.open_project_path(project_path):
                e.acceptProposedAction()
            else:
                # User cancelled the unsaved-changes prompt, or the
                # load failed (error dialog already shown). The drag
                # was entered with acceptProposedAction(), so we must
                # explicitly ignore here to signal "nothing changed".
                e.ignore()
            return
        if floppy_paths:
            self._add_paths(floppy_paths)
            e.acceptProposedAction()
            return
        # URLs were present but none were recognized (e.g. a .txt
        # dragged onto the window). dragEnterEvent already accepted
        # the drag, so an implicit fall-through would leave the cursor
        # showing the "accept" icon for an op that does nothing. Call
        # e.ignore() so the OS reverts to the normal "drop rejected"
        # cursor and any chained drop handlers get a fair shot.
        e.ignore()

    # ── Geometry persistence ─────────────────────────────────────────────────────────

    def _restore_geometry(self) -> None:
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        state = self.settings.value("window_state")
        if state is not None:
            self.restoreState(state)

    def closeEvent(self, e) -> None:
        if not self._maybe_save():
            e.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        super().closeEvent(e)
