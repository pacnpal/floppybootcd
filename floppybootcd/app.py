"""Application entry point."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME
from .core.platform import Platform
from .core.plugins import load_plugins


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

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("pacnpal")
    app.setOrganizationDomain("pacnp.al")
    app.setDesktopFileName("floppybootcd")     # Linux: links to .desktop entry
    _macos_setup(app)

    load_plugins()

    # Defer import so QApplication exists first
    from .ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
