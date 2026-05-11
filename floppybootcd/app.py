"""Application entry point."""
from __future__ import annotations

import sys
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFileOpenEvent, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME
from .core.platform import Platform
from .core.plugins import load_plugins
from .core.project import PROJECT_EXT


class FloppyBootCDApplication(QApplication):
    """QApplication subclass that handles macOS file-open events.

    On macOS, when the user double-clicks a `.fbcd` file in Finder,
    drags one onto the app icon in the Dock, or chooses File → Open
    Recent in the global menu, AppKit dispatches the path to the
    running app as a `QFileOpenEvent` — there's no argv to inspect
    (Finder doesn't relaunch the app to pass args; it sends an Apple
    Event to the already-running instance).

    The event can arrive *before* MainWindow is constructed, so any
    paths that show up early are buffered and replayed when
    ``set_main_window`` wires up the receiver. Per Qt docs, the
    event is sent to ``QApplication::instance()``, so subclassing and
    overriding ``event()`` is the canonical handling (cleaner than
    installEventFilter — see https://doc.qt.io/qtforpython-6/PySide6/QtGui/QFileOpenEvent.html).
    """

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self._pending_open_paths: list[str] = []
        self._main_window = None

    def set_main_window(self, win) -> None:
        """Wire MainWindow as the receiver and flush any buffered drops.

        Buffered paths are batched through :meth:`_dispatch_batch` so a
        QFileOpenEvent flood (e.g. macOS sending several file-open events
        in quick succession when the app is launched as a multi-file
        handler) doesn't accidentally add an image first, mark the
        project dirty, and then prompt the user about unsaved changes
        when a later .fbcd in the same batch tries to open. The batch
        applies "project wins" semantics — see _dispatch_batch.
        """
        self._main_window = win
        pending, self._pending_open_paths = self._pending_open_paths, []
        if pending:
            self._dispatch_batch(pending)

    @staticmethod
    def _canonicalize(path: str) -> str:
        """Return *path* as a canonical absolute string.

        FloppyImage.path is documented as absolute, and projects save
        the image list verbatim — so a relative path landing here from
        an `argv` shell invocation (e.g. ``floppybootcd ./boot.img``)
        would persist into the .fbcd file and break the moment the
        user's working directory changed. Normalize once at the
        boundary via expanduser + resolve(strict=False) so every
        downstream caller sees a stable absolute path. resolve() with
        strict=False is safe on Python 3.6+ even when the target
        doesn't yet exist; it returns the lexically-resolved absolute
        form.
        """
        return str(Path(path).expanduser().resolve(strict=False))

    def _dispatch(self, path: str) -> None:
        """Send *path* to the right MainWindow handler based on its
        extension. .fbcd → load project; floppy image / folder → add."""
        canonical = self._canonicalize(path)
        win = self._main_window
        if win is None:
            self._pending_open_paths.append(canonical)
            return
        # Late import — avoids dragging UI module into module-import
        # time and into worker subprocesses that might import app.
        from .core.image_prep import walk_floppy_images

        p = Path(canonical)
        if p.is_file() and p.suffix.lower() == PROJECT_EXT:
            win.open_project_path(canonical)
            return
        found = walk_floppy_images(p)
        if found:
            win.add_paths(found)

    def _dispatch_batch(self, paths: list[str]) -> None:
        """Dispatch a batch of paths with "project wins" semantics.

        Used by both the argv loop in :func:`main` and the
        :meth:`set_main_window` flush of ``QFileOpenEvent`` paths.
        Both call sites can hand us a mix of types:

            $ floppybootcd boot.img project.fbcd

        The naive sequential dispatch would add ``boot.img`` first
        (marking the project dirty), then call ``open_project_path``
        for ``project.fbcd``, which would prompt the user to save
        changes to a project they never explicitly created. Pre-scan
        the batch for any ``.fbcd`` and, if found, dispatch ONLY the
        first one — the project replaces the entire image list
        anyway, so the rest of the batch would have been clobbered.
        """
        canonical = [self._canonicalize(p) for p in paths]
        for cp in canonical:
            cp_path = Path(cp)
            if cp_path.is_file() and cp_path.suffix.lower() == PROJECT_EXT:
                self._dispatch(cp)
                return
        for cp in canonical:
            self._dispatch(cp)

    def event(self, ev: QEvent) -> bool:  # type: ignore[override]
        if ev.type() == QEvent.Type.FileOpen and isinstance(ev, QFileOpenEvent):
            self._dispatch(ev.file())
            return True
        return super().event(ev)


def _load_app_icon() -> QIcon:
    """Load the bundled floppy-disk icon as a QIcon."""
    try:
        path = files("floppybootcd.resources") / "icon.png"
        return QIcon(str(path))
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return QIcon()


def _windows_setup() -> None:
    """Make Windows treat us as a distinct app for taskbar grouping/icons."""
    if Platform.current() is not Platform.WINDOWS:
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _macos_setup(app: QApplication) -> None:
    """macOS-specific niceties."""
    if Platform.current() is not Platform.MACOS:
        return
    # Use the native menu bar at the top of the screen, not in the window
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, False)


def main() -> int:
    # HiDPI: Qt 6 enables this automatically, but be explicit for older 6.x
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    _windows_setup()

    app = FloppyBootCDApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("pacnpal")
    app.setOrganizationDomain("pacnp.al")
    app.setDesktopFileName("floppybootcd")     # Linux: links to .desktop entry
    app.setWindowIcon(_load_app_icon())        # taskbar / Alt-Tab / window decoration
    _macos_setup(app)

    load_plugins()

    # Defer import so QApplication exists first
    from .ui.main_window import MainWindow
    win = MainWindow()
    app.set_main_window(win)                   # flush any QFileOpenEvent buffered at launch

    # CLI invocation paths: forward everything after argv[0] to
    # _dispatch_batch. Covers Windows file double-click (which
    # spawns floppybootcd.exe <path>), Linux xdg-open (likewise),
    # and shell invocations like `floppybootcd ~/project.fbcd`.
    # _dispatch (called from the batch) canonicalizes its input
    # (expanduser + resolve) and silently no-ops for paths that
    # don't exist or aren't a recognized floppy image / folder /
    # .fbcd, so we DON'T pre-check existence here — pre-checking
    # with a literal "~/foo" would skip dispatch for shell-quoted
    # paths whose tilde the OS hasn't expanded yet (PowerShell,
    # cmd.exe with delayed expansion, etc.). The empty-string and
    # Qt-flag guards stay; without them `floppybootcd ""` would
    # Path("").exists() == True (resolves to CWD) and recurse the
    # working directory.
    cli_paths = [a for a in sys.argv[1:] if a and not a.startswith("-")]
    if cli_paths:
        app._dispatch_batch(cli_paths)

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
