"""ImageListWidget: QListWidget with internal drag-reorder + external file drops."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from ..core.image_prep import (
    ALL_ACCEPTED_EXTS,
    COMPRESSED_EXTS,
    probe_uncompressed_size,
    walk_floppy_images,
)
from ..core.project import PROJECT_EXT, FloppyImage


class ImageListWidget(QListWidget):
    """List of floppy images. Supports:
       - drag-reorder within the list (InternalMove)
       - drag external floppy images in from the OS file manager
         (.img / .ima / .vfd / .flp / .imz)
       - drag whole folders in — recurses up to five levels and
         picks up every floppy image inside
       - drag a .fbcd project file in — emits ``project_dropped`` so
         the host window can load the project instead of treating it
         as a floppy image
       - keyboard delete to remove items
    """

    files_dropped = Signal(list)         # list[str] of paths dropped from outside
    project_dropped = Signal(str)        # absolute path to a dropped .fbcd file
    items_reordered = Signal()
    selection_changed = Signal()         # convenience signal
    edit_requested = Signal()            # Enter pressed on a selection

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAlternatingRowColors(True)
        self.setUniformItemSizes(True)
        self.setMinimumHeight(180)
        self.itemSelectionChanged.connect(self.selection_changed.emit)

    # ── Drag-and-drop ─────────────────────────────────────────────────────────

    def _existing_paths(self) -> set[str]:
        return {self.item(i).data(Qt.ItemDataRole.UserRole).path
                for i in range(self.count())}

    @staticmethod
    def _url_is_useful(url) -> bool:
        """True for a local URL that's a folder, a .fbcd project, or
        a floppy-image file extension we accept. Used to decide
        whether to accept the drag at hover time."""
        if not url.isLocalFile():
            return False
        p = Path(url.toLocalFile())
        if p.is_dir():
            return True
        if not p.is_file():
            return False
        ext = p.suffix.lower()
        return ext == PROJECT_EXT or ext in ALL_ACCEPTED_EXTS

    def _mime_is_acceptable(self, mime) -> bool:
        return mime.hasUrls() and any(self._url_is_useful(u) for u in mime.urls())

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if self._mime_is_acceptable(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e: QDragMoveEvent) -> None:
        if self._mime_is_acceptable(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e: QDropEvent) -> None:
        mime = e.mimeData()
        if mime.hasUrls() and self._mime_is_acceptable(mime):
            # Two outcomes are possible from a single drop:
            # (a) a .fbcd project file → emit project_dropped and let
            #     the host window load it (replaces the current
            #     project after the usual unsaved-changes prompt).
            # (b) any combination of floppy-image files and folders
            #     → recurse folders, flatten to a deduped path list,
            #     emit files_dropped. The .fbcd case wins if both
            #     are present in the same drop because loading a
            #     project replaces the image list anyway.
            project_path = None
            floppy_paths: list[str] = []
            existing = self._existing_paths()
            for url in mime.urls():
                if not url.isLocalFile():
                    continue
                p = Path(url.toLocalFile())
                if p.is_file() and p.suffix.lower() == PROJECT_EXT:
                    project_path = str(p)
                    continue
                for found in walk_floppy_images(p):
                    if found not in existing and found not in floppy_paths:
                        floppy_paths.append(found)

            if project_path:
                self.project_dropped.emit(project_path)
                e.acceptProposedAction()
                return
            if floppy_paths:
                self.files_dropped.emit(floppy_paths)
                e.acceptProposedAction()
                return
            e.ignore()
            return
        super().dropEvent(e)
        self.items_reordered.emit()

    # ── Convenience ───────────────────────────────────────────────────────────

    def add_image(self, img: FloppyImage) -> None:
        item = QListWidgetItem(self._format_label(img))
        item.setData(Qt.ItemDataRole.UserRole, img)
        item.setToolTip(img.path)
        self._apply_exists_color(item, img)
        self.addItem(item)

    def update_item(self, row: int) -> None:
        item = self.item(row)
        if item is None:
            return
        img: FloppyImage = item.data(Qt.ItemDataRole.UserRole)
        item.setText(self._format_label(img))
        item.setToolTip(img.path)
        self._apply_exists_color(item, img)

    @staticmethod
    def _apply_exists_color(item: QListWidgetItem, img: FloppyImage) -> None:
        """Tint missing-file rows red; restore the default brush when
        the file is present again. Without the clear branch, an item
        edited from missing→present would stay red."""
        if not img.exists:
            item.setForeground(Qt.GlobalColor.red)
        else:
            # Reset to the view's default text color.
            item.setData(Qt.ItemDataRole.ForegroundRole, None)

    def get_images(self) -> list[FloppyImage]:
        return [self.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.count())]

    def remove_selected(self) -> int:
        rows = sorted({self.row(i) for i in self.selectedItems()}, reverse=True)
        for r in rows:
            self.takeItem(r)
        return len(rows)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.remove_selected():
                event.accept()
                self.items_reordered.emit()
                return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.selectedItems():
                event.accept()
                self.edit_requested.emit()
                return
        super().keyPressEvent(event)

    @staticmethod
    def _format_label(img: FloppyImage) -> str:
        # Show the floppy's real (uncompressed) size for .imz containers
        # so the column reflects what the OS will see, not the archive.
        # Distinguish a missing file from a corrupt/encrypted .imz so the
        # user knows whether to fix the path or re-export the archive.
        ext = Path(img.path).suffix.lower()
        if not img.exists:
            size_str = "missing"
        elif ext in COMPRESSED_EXTS:
            inner = probe_uncompressed_size(img.path)
            if inner == 0:
                size_str = "? (invalid .imz)"
            else:
                kb = inner // 1024
                size_str = (
                    f"{kb} KB" if kb < 4096 else f"{kb / 1024:.1f} MB"
                )
        else:
            kb = img.size_bytes // 1024
            size_str = f"{kb} KB" if kb < 4096 else f"{kb / 1024:.1f} MB"
        prefix = "★ " if img.default else "   "
        label = img.display_label
        return f"{prefix}{label}    [{img.filename}, {size_str}]"
