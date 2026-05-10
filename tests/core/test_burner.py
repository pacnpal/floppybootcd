"""Tests for the burner backends.

These backends call platform-specific tools we can't run in CI; we focus on
the pure logic: parsing output, drive detection regex, verify-by-hash, and
platform gating."""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from floppybootcd.core import burner as burner_mod
from floppybootcd.core.burner import (
    ALL_BURNERS,
    LinuxBurner,
    MacOSBurner,
    OpticalDrive,
    WindowsBurner,
    _run_streaming,
    get_native_burner,
)
from floppybootcd.core.platform import Platform


class TestOpticalDrive:
    def test_display_with_name(self):
        d = OpticalDrive(device="/dev/sr0", name="HL-DT-ST DVDRW")
        assert d.display() == "/dev/sr0 — HL-DT-ST DVDRW"

    def test_display_without_name(self):
        d = OpticalDrive(device="/dev/sr0")
        assert d.display() == "/dev/sr0"


class TestRunStreaming:
    def test_streams_lines_to_log(self):
        """Run a tiny subprocess and verify logs flow through."""
        logs: list[str] = []
        rc = _run_streaming(
            [sys.executable, "-c", "print('hello'); print('world')"],
            log=logs.append,
        )
        assert rc == 0
        assert "hello" in logs
        assert "world" in logs

    def test_progress_regex_extracts_percentage(self):
        # Single capture = a 0-100 percent literal, so _run_streaming
        # divides by 100 to yield a 0..1 fraction.
        progress_calls: list[tuple[str, float]] = []
        rc = _run_streaming(
            [sys.executable, "-c", "print('progress 42%')"],
            log=lambda _: None,
            progress=lambda m, f: progress_calls.append((m, f)),
            progress_re=re.compile(r"progress (\d+)%"),
        )
        assert rc == 0
        assert progress_calls
        _, frac = progress_calls[0]
        assert frac == pytest.approx(0.42)

    def test_progress_regex_uses_two_captures_as_ratio(self):
        # Two captures = current/total, the form cdrecord actually emits
        # ("Track 01: 50 of 700 MB"). Reporting group(1)/100 here would
        # be wildly wrong (50% complete on a 7%-burned disc).
        progress_calls: list[tuple[str, float]] = []
        rc = _run_streaming(
            [sys.executable, "-c", "print('Track 01: 50 of 700 MB')"],
            log=lambda _: None,
            progress=lambda m, f: progress_calls.append((m, f)),
            progress_re=re.compile(r"Track \d+:\s+(\d+) of (\d+) MB"),
        )
        assert rc == 0
        assert progress_calls
        _, frac = progress_calls[0]
        assert frac == pytest.approx(50 / 700)

    def test_progress_clamped_to_unit_interval(self):
        # Defensive: malformed output that would yield > 1.0 must clamp.
        progress_calls: list[tuple[str, float]] = []
        _run_streaming(
            [sys.executable, "-c", "print('p 250%')"],
            log=lambda _: None,
            progress=lambda m, f: progress_calls.append((m, f)),
            progress_re=re.compile(r"p (\d+)%"),
        )
        assert progress_calls[0][1] == 1.0

    def test_progress_zero_total_does_not_crash(self):
        # ZeroDivisionError must be swallowed.
        progress_calls: list[tuple[str, float]] = []
        rc = _run_streaming(
            [sys.executable, "-c", "print('Track 01: 0 of 0 MB')"],
            log=lambda _: None,
            progress=lambda m, f: progress_calls.append((m, f)),
            progress_re=re.compile(r"Track \d+:\s+(\d+) of (\d+) MB"),
        )
        assert rc == 0
        # 0/0 → frac 0.0
        assert progress_calls and progress_calls[0][1] == 0.0

    def test_nonzero_exit_returned(self):
        rc = _run_streaming(
            [sys.executable, "-c", "import sys; sys.exit(7)"],
            log=lambda _: None,
        )
        assert rc == 7


class TestLinuxBurnerListDrives:
    def test_parses_xorriso_cdrecord_devices(self, monkeypatch):
        sample = (
            "0  dev='/dev/sr0' rwrw-- : 'HL-DT-ST' 'DVDRAM GUD0N'\n"
            "1  dev='/dev/sr1' rwrw-- : 'PIONEER' 'BD-RW BDR-209M'\n"
        )
        fake_proc = MagicMock(stdout=sample)
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake_proc)
        # Make the fallback /dev probe never trigger
        monkeypatch.setattr(Path, "exists", lambda self: False)

        drives = LinuxBurner().list_drives()
        assert len(drives) == 2
        assert drives[0].device == "/dev/sr0"
        assert "HL-DT-ST" in drives[0].name
        assert drives[1].device == "/dev/sr1"

    def test_falls_back_to_dev_paths(self, monkeypatch):
        # xorriso missing entirely
        def boom(*a, **k):
            raise FileNotFoundError

        monkeypatch.setattr(subprocess, "run", boom)
        # /dev/sr0 exists, others don't. Compare via Path equality so the
        # mock works on Windows where str(Path("/dev/sr0")) uses backslashes.
        target = Path("/dev/sr0")
        monkeypatch.setattr(Path, "exists", lambda self: self == target)
        drives = LinuxBurner().list_drives()
        assert any(d.device == "/dev/sr0" for d in drives)

    def test_burn_without_drive_raises(self):
        with pytest.raises(RuntimeError, match="Select a drive"):
            LinuxBurner().burn(
                Path("/tmp/x.iso"), None, False, False,
                lambda *_: None, lambda _: None,
            )


class TestLinuxBurnerVerify:
    def test_verify_matching_files(self, tmp_path):
        # Use a regular file as both the "ISO" and the "device".
        iso = tmp_path / "in.iso"
        iso.write_bytes(b"\x00" * 4096 + b"hello world")
        # Verify reads device by raw open(device, "rb"). Use the same file.
        ok = LinuxBurner()._verify(iso, str(iso), log=lambda _: None)
        assert ok is True

    def test_verify_mismatched_files(self, tmp_path):
        iso = tmp_path / "in.iso"
        iso.write_bytes(b"A" * 8192)
        disc = tmp_path / "disc.bin"
        disc.write_bytes(b"B" * 8192)
        ok = LinuxBurner()._verify(iso, str(disc), log=lambda _: None)
        assert ok is False

    def test_verify_permission_error_returns_false(self, tmp_path, monkeypatch):
        iso = tmp_path / "iso"
        iso.write_bytes(b"x" * 1024)

        real_open = open

        def fake_open(path, mode="r", *args, **kwargs):
            if str(path) == "/dev/restricted":
                raise PermissionError("nope")
            return real_open(path, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", fake_open)
        logs: list[str] = []
        ok = LinuxBurner()._verify(iso, "/dev/restricted", log=logs.append)
        assert ok is False
        assert any("permission denied" in m.lower() for m in logs)


class TestLinuxBurnerFindTool:
    def test_find_tool_returns_first_available(self, monkeypatch):
        monkeypatch.setattr(
            burner_mod.shutil, "which",
            lambda name: "/usr/bin/xorriso" if name == "xorriso" else None,
        )
        tool, path = LinuxBurner()._find_tool()
        assert tool == "xorriso"
        assert path == "/usr/bin/xorriso"

    def test_find_tool_falls_back(self, monkeypatch):
        monkeypatch.setattr(
            burner_mod.shutil, "which",
            lambda name: "/usr/bin/wodim" if name == "wodim" else None,
        )
        tool, _path = LinuxBurner()._find_tool()
        assert tool == "wodim"

    def test_find_tool_raises_when_none(self, monkeypatch):
        monkeypatch.setattr(burner_mod.shutil, "which", lambda name: None)
        with pytest.raises(RuntimeError, match="No burning tool"):
            LinuxBurner()._find_tool()


class TestWindowsBurnerListDrives:
    def test_parses_powershell_output(self, monkeypatch):
        sample = "D:|HL-DT-ST DVDRAM GUD0N\nE:|PIONEER BD-RW\n"
        fake_proc = MagicMock(stdout=sample)
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake_proc)

        drives = WindowsBurner().list_drives()
        assert any(d.device == "D:" for d in drives)
        assert any("HL-DT-ST" in d.name for d in drives)

    def test_returns_pseudo_drive_when_powershell_missing(self, monkeypatch):
        def boom(*a, **k):
            raise FileNotFoundError

        monkeypatch.setattr(subprocess, "run", boom)
        drives = WindowsBurner().list_drives()
        assert len(drives) == 1
        assert drives[0].device == ""
        assert "burn time" in drives[0].name.lower()


class TestMacOSBurnerListDrives:
    def test_returns_default_when_hdiutil_lists_anything(self, monkeypatch):
        fake_proc = MagicMock(stdout="some hdiutil output\n")
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake_proc)
        drives = MacOSBurner().list_drives()
        assert len(drives) == 1
        assert drives[0].name.lower().startswith("default")

    def test_returns_empty_when_no_output(self, monkeypatch):
        fake_proc = MagicMock(stdout="")
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake_proc)
        drives = MacOSBurner().list_drives()
        assert drives == []

    def test_returns_empty_when_hdiutil_missing(self, monkeypatch):
        def boom(*a, **k):
            raise FileNotFoundError

        monkeypatch.setattr(subprocess, "run", boom)
        assert MacOSBurner().list_drives() == []


class TestPlatformGating:
    def test_macos_burner_only_available_on_macos(self, monkeypatch):
        monkeypatch.setattr(
            burner_mod.Platform, "current", classmethod(lambda cls: Platform.LINUX)
        )
        assert MacOSBurner.is_available() is False

    def test_windows_burner_only_available_on_windows(self, monkeypatch):
        monkeypatch.setattr(
            burner_mod.Platform, "current", classmethod(lambda cls: Platform.LINUX)
        )
        assert WindowsBurner.is_available() is False

    def test_linux_burner_only_available_on_linux(self, monkeypatch):
        monkeypatch.setattr(
            burner_mod.Platform, "current", classmethod(lambda cls: Platform.MACOS)
        )
        assert LinuxBurner.is_available() is False

    def test_linux_burner_needs_a_tool(self, monkeypatch):
        monkeypatch.setattr(
            burner_mod.Platform, "current", classmethod(lambda cls: Platform.LINUX)
        )
        monkeypatch.setattr(burner_mod.shutil, "which", lambda name: None)
        assert LinuxBurner.is_available() is False

    def test_linux_burner_available_with_xorriso(self, monkeypatch):
        monkeypatch.setattr(
            burner_mod.Platform, "current", classmethod(lambda cls: Platform.LINUX)
        )
        monkeypatch.setattr(
            burner_mod.shutil, "which",
            lambda name: "/usr/bin/xorriso" if name == "xorriso" else None,
        )
        assert LinuxBurner.is_available() is True


class TestGetNativeBurner:
    def test_returns_first_available(self, monkeypatch):
        monkeypatch.setattr(MacOSBurner, "is_available", classmethod(lambda cls: False))
        monkeypatch.setattr(WindowsBurner, "is_available", classmethod(lambda cls: False))
        monkeypatch.setattr(LinuxBurner, "is_available", classmethod(lambda cls: True))
        b = get_native_burner()
        assert isinstance(b, LinuxBurner)

    def test_returns_none_when_none_available(self, monkeypatch):
        for cls in ALL_BURNERS:
            monkeypatch.setattr(cls, "is_available", classmethod(lambda cls: False))
        assert get_native_burner() is None
