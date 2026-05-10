"""Tests for platform detection and per-OS path resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

from floppybootcd.core import platform as platform_mod
from floppybootcd.core.platform import (
    Platform,
    app_config_dir,
    app_data_dir,
    cache_dir,
)


class TestPlatformDetection:
    @pytest.mark.parametrize("sys_plat,expected", [
        ("darwin", Platform.MACOS),
        ("win32", Platform.WINDOWS),
        ("linux", Platform.LINUX),
        ("freebsd", Platform.LINUX),  # falls through to "non-mac/non-win" → LINUX
    ])
    def test_current(self, monkeypatch, sys_plat, expected):
        monkeypatch.setattr(platform_mod.sys, "platform", sys_plat)
        assert Platform.current() is expected


class TestAppDataDir:
    def test_macos(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "darwin")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        d = app_data_dir("Test")
        assert d == tmp_path / "Library" / "Application Support" / "Test"
        assert d.is_dir()

    def test_windows_uses_appdata(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
        d = app_data_dir("Test")
        assert d == tmp_path / "Roaming" / "Test"
        assert d.is_dir()

    def test_windows_fallback_when_appdata_unset(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "win32")
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        d = app_data_dir("Test")
        assert d == tmp_path / "AppData" / "Roaming" / "Test"

    def test_linux_uses_xdg_data_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        d = app_data_dir("Test")
        assert d == tmp_path / "data" / "Test"

    def test_linux_fallback_when_xdg_unset(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        d = app_data_dir("Test")
        assert d == tmp_path / ".local" / "share" / "Test"


class TestAppConfigDir:
    def test_linux_uses_xdg_config_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "linux")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        d = app_config_dir("Test")
        assert d == tmp_path / "cfg" / "Test"

    def test_macos_matches_app_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "darwin")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        assert app_config_dir("Test") == app_data_dir("Test")

    def test_windows_matches_app_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
        assert app_config_dir("Test") == app_data_dir("Test")


class TestCacheDir:
    def test_macos(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "darwin")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        d = cache_dir("Test")
        assert d == tmp_path / "Library" / "Caches" / "Test"

    def test_windows_uses_localappdata(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
        d = cache_dir("Test")
        assert d == tmp_path / "Local" / "Test"

    def test_linux_uses_xdg_cache_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "linux")
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        d = cache_dir("Test")
        assert d == tmp_path / "cache" / "Test"

    def test_linux_fallback(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_mod.sys, "platform", "linux")
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        d = cache_dir("Test")
        assert d == tmp_path / ".cache" / "Test"
