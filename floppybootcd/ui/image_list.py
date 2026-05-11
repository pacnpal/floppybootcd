"""ImageListWidget: QListWidget with internal drag-reorder + external file drops."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from ..core.image_prep import (
    ALL_ACCEPTED_EXTS,
    COMPRESSED_EXTS,
    normalize_for_dedup,
    probe_uncompressed_size,
    walk_floppy_images,
)
from ..core.project import PROJECT_EXT, FloppyImage


def parse_dropped_urls(
    urls: Iterable, existing_paths: Iterable[str]
) -> tuple[str | None, list[str]]:
    """Resolve a sequence of QUrls into a (project_path, image_paths) tuple.

    Shared between :class:`ImageListWidget.dropEvent` and
    :meth:`MainWindow.dropEvent` so the drop semantics stay
    consistent between the two drop targets:

    * **Project wins:** if any URL is a ``.fbcd`` file, return it as
      ``project_path`` and an empty image list (project replacement
      makes any image drops moot). Pre-scan in one cheap pass so we
      don't waste UI-thread time recursing a 100k-entry folder whose
      result we'd then throw away.
    * **Otherwise:** walk every URL via :func:`walk_floppy_images`
      (recurses folders, filters by extension), dedup against
      *existing_paths* using :func:`normalize_for_dedup` so paths
      from ``QUrl.toLocalFile()`` (forward slashes on Windows) and
      from ``os.scandir`` (native separators) compare equal.
    * Non-local URLs (``http://``, ``smb://``, …) are silently skipped.

    Returns
    -------
    (project_path, image_paths)
        Exactly one of these will be non-empty; the other is
        ``None`` / ``[]``. A drag of e.g. only a ``.txt`` returns
        ``(None, [])``.
    """
    urls = list(urls)
    for u in urls:
        if not u.isLocalFile():
            continue
        p = Path(u.toLocalFile())
        if p.is_file() and p.suffix.lower() == PROJECT_EXT:
            return str(p), []

    existing_norm = {normalize_for_dedup(p) for p in existing_paths}
    image_paths: list[str] = []
    seen_norm: set[str] = set()
    for u in urls:
        if not u.isLocalFile():
            continue
        for found in walk_floppy_images(Path(u.toLocalFile())):
            key = normalize_for_dedup(found)
            if key in existing_norm or key in seen_norm:
                continue
            seen_norm.add(key)
            image_paths.append(found)
    return None, image_paths


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
        """Set of currently-listed image paths, normalized for dedup
        comparison (separators + case). See
        :func:`normalize_for_dedup` for the rationale."""
        return {normalize_for_dedup(
            self.item(i).data(Qt.ItemDataRole.UserRole).path)
                for i in range(self.count())}

    def mime_is_acceptable(self, mime) -> bool:
        """Decide whether to accept a drag at hover time.

        Three classes of URL are interesting:

        * **Folders** — always accepted. We can't cheaply tell whether
          a folder contains anything new without walking it, and
          walking on every dragMoveEvent would stutter big drags.
          Accept the hover; let the drop-time dedup handle a folder
          that turns out to be all duplicates (rare and silent).
        * **.fbcd project files** — always accepted (drops trigger an
          open-project flow that replaces the current image list,
          which is meaningful even if some images carry over).
        * **Floppy-image files** — accepted only when at least one
          path isn't already in the list. Without this check the
          cursor showed "accept" for a drag whose drop was a pure
          no-op, which read as a bug to the user.

        URLs that aren't local files (http://, etc.) are ignored.
        """
        if not mime.hasUrls():
            return False
        existing = self._existing_paths()  # already normalized
        for u in mime.urls():
            if not u.isLocalFile():
                continue
            p = Path(u.toLocalFile())
            if p.is_dir():
                return True
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            if ext == PROJECT_EXT:
                return True
            if (ext in ALL_ACCEPTED_EXTS
                    and normalize_for_dedup(p) not in existing):
                return True
        return False

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        mime = e.mimeData()
        if self.mime_is_acceptable(mime):
            e.acceptProposedAction()
        elif mime.hasUrls():
            # URL-based drag we explicitly don't want (unknown
            # extension, all duplicates, .txt). Without an explicit
            # ignore() the QListWidget base class — with
            # setAcceptDrops(True) and DragDropMode.DragDrop on —
            # may still accept it as a candidate model item, which
            # would re-show the misleading "accept" cursor for a
            # drop we'd silently no-op.
            e.ignore()
        else:
            # Internal drag (item reorder); the base class knows
            # what to do.
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e: QDragMoveEvent) -> None:
        mime = e.mimeData()
        if self.mime_is_acceptable(mime):
            e.acceptProposedAction()
        elif mime.hasUrls():
            e.ignore()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e: QDropEvent) -> None:
        mime = e.mimeData()
        if mime.hasUrls() and self.mime_is_acceptable(mime):
            # Both this widget and the main window route external
            # drops through parse_dropped_urls() so the two drop
            # targets always agree on what counts. See that helper
            # for the full project-wins / dedup contract.
            existing_paths = [
                self.item(i).data(Qt.ItemDataRole.UserRole).path
                for i in range(self.count())
            ]
            project_path, floppy_paths = parse_dropped_urls(
                mime.urls(), existing_paths,
            )
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
        # Only emit items_reordered for genuine in-widget moves —
        # falling through to super() for an external non-accepted
        # drop (a .txt file, say) used to fire items_reordered too,
        # which marked the project dirty even though nothing changed.
        was_internal = e.source() is self
        super().dropEvent(e)
        if was_internal:
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
