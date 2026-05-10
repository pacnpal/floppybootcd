"""ImageListWidget: QListWidget with internal drag-reorder + external file drops."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from ..core.image_prep import ALL_ACCEPTED_EXTS, probe_uncompressed_size
from ..core.project import FloppyImage


class ImageListWidget(QListWidget):
    """List of floppy images. Supports:
       - drag-reorder within the list (InternalMove)
       - drag external files in from the OS file manager
       - keyboard delete to remove items
    """

    files_dropped = Signal(list)         # list[str] of paths dropped from outside
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

    def _mime_has_external_files(self, mime) -> bool:
        return mime.hasUrls() and any(
            u.isLocalFile() and u.toLocalFile() not in self._existing_paths()
            for u in mime.urls()
        )

    def _existing_paths(self) -> set[str]:
        return {self.item(i).data(Qt.ItemDataRole.UserRole).path
                for i in range(self.count())}

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e: QDragMoveEvent) -> None:
        if e.mimeData().hasUrls() and self._mime_has_external_files(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e: QDropEvent) -> None:
        if e.mimeData().hasUrls() and self._mime_has_external_files(e.mimeData()):
            paths = []
            for url in e.mimeData().urls():
                if url.isLocalFile():
                    p = url.toLocalFile()
                    ext = Path(p).suffix.lower()
                    if Path(p).is_file() and ext in ALL_ACCEPTED_EXTS:
                        paths.append(p)
            if paths:
                self.files_dropped.emit(paths)
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
        if not img.exists:
            item.setForeground(Qt.GlobalColor.red)
        self.addItem(item)

    def update_item(self, row: int) -> None:
        item = self.item(row)
        if item is None:
            return
        img: FloppyImage = item.data(Qt.ItemDataRole.UserRole)
        item.setText(self._format_label(img))
        item.setToolTip(img.path)

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
        size_bytes = probe_uncompressed_size(img.path) or img.size_bytes
        kb = size_bytes // 1024
        size_str = f"{kb} KB" if kb < 4096 else f"{kb / 1024:.1f} MB"
        prefix = "★ " if img.default else "   "
        label = img.display_label
        return f"{prefix}{label}    [{img.filename}, {size_str}]"
