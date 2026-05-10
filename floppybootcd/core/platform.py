"""Platform-specific paths and helpers. One place to handle native quirks."""
from __future__ import annotations

import sys
import os
from pathlib import Path
from enum import Enum


class Platform(Enum):
    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"

    @classmethod
    def current(cls) -> "Platform":
        if sys.platform == "darwin":
            return cls.MACOS
        if sys.platform == "win32":
            return cls.WINDOWS
        return cls.LINUX


def app_data_dir(app_name: str = "FloppyBootCD") -> Path:
    """OS-appropriate place to store cached binaries, settings, projects."""
    p = Platform.current()
    if p is Platform.MACOS:
        base = Path.home() / "Library" / "Application Support"
    elif p is Platform.WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / app_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def app_config_dir(app_name: str = "FloppyBootCD") -> Path:
    """OS-appropriate config dir (separate from data on Linux)."""
    p = Platform.current()
    if p is Platform.MACOS:
        return app_data_dir(app_name)
    if p is Platform.WINDOWS:
        return app_data_dir(app_name)
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / app_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir(app_name: str = "FloppyBootCD") -> Path:
    p = Platform.current()
    if p is Platform.MACOS:
        base = Path.home() / "Library" / "Caches"
    elif p is Platform.WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = base / app_name
    d.mkdir(parents=True, exist_ok=True)
    return d
