"""Native CD burning per platform.

Each backend uses the OS's first-party tooling so we get genuine OS dialogs,
permission handling, and disc detection. No third-party deps.

  macOS    → hdiutil burn (built-in, has -verifyburn)
  Windows  → isoburn.exe  (built-in since Vista, native dialog)
  Linux    → xorriso -as cdrecord  (already a build dep, so always present)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .platform import Platform


@dataclass
class OpticalDrive:
    """A burner drive on the system."""
    device: str           # /dev/sr0, /dev/disk2, "D:\\", etc.
    name: str = ""        # "HL-DT-ST DVDRAM GUD0N"
    blank: bool | None = None  # True/False/None=unknown

    def display(self) -> str:
        bits = [self.device]
        if self.name:
            bits.append(self.name)
        return " — ".join(bits)


class BurnerBackend(ABC):
    id: str = ""
    label: str = ""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool: ...

    @abstractmethod
    def list_drives(self) -> list[OpticalDrive]: ...

    @abstractmethod
    def burn(
        self,
        iso_path: Path,
        drive: OpticalDrive | None,
        verify: bool,
        eject: bool,
        progress: Callable[[str, float], None],
        log: Callable[[str], None],
    ) -> None:
        """Raises RuntimeError on failure."""


def _run_streaming(
    cmd: list[str],
    log: Callable[[str], None],
    progress: Callable[[str, float], None] | None = None,
    progress_re: re.Pattern[str] | None = None,
) -> int:
    """Run a subprocess streaming stdout to log, parsing optional progress."""
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        log(line)
        if progress and progress_re:
            m = progress_re.search(line)
            if m:
                try:
                    progress(line, float(m.group(1)) / 100.0)
                except (ValueError, IndexError):
                    pass
    return proc.wait()


# ── macOS ─────────────────────────────────────────────────────────────

class MacOSBurner(BurnerBackend):
    id = "macos"
    label = "macOS hdiutil"

    @classmethod
    def is_available(cls) -> bool:
        return Platform.current() is Platform.MACOS and shutil.which("hdiutil") is not None

    def list_drives(self) -> list[OpticalDrive]:
        # `hdiutil burn -list` prints drives. Output is plist-ish; we parse loosely.
        try:
            out = subprocess.run(
                ["hdiutil", "burn", "-list"],
                capture_output=True, text=True, check=False,
            ).stdout
        except FileNotFoundError:
            return []
        drives: list[OpticalDrive] = []
        # Lines like:  "name : 'HL-DT-ST DVDRW  GS41N'"  or paths to devices.
        # In practice on modern Macs, optical drives are USB and rare; if we
        # find ANY output, we expose a single "Default" pseudo-drive since
        # `hdiutil burn` without -device picks the first burner.
        if out.strip():
            drives.append(OpticalDrive(device="", name="Default optical drive"))
        return drives

    def burn(self, iso_path, drive, verify, eject, progress, log):
        cmd = ["hdiutil", "burn", str(iso_path)]
        if not verify:
            cmd.append("-noverifyburn")
        if eject:
            cmd.append("-eject")
        else:
            cmd.append("-noeject")
        # hdiutil prints "............" dots; no clean percentage. We use
        # indeterminate progress and rely on stage messages.
        progress("Burning...", -1.0)
        rc = _run_streaming(cmd, log)
        if rc != 0:
            raise RuntimeError(f"hdiutil burn failed (exit {rc})")
        progress("Burn complete.", 1.0)


# ── Windows ───────────────────────────────────────────────────────────

class WindowsBurner(BurnerBackend):
    id = "windows"
    label = "Windows isoburn"

    @classmethod
    def is_available(cls) -> bool:
        if Platform.current() is not Platform.WINDOWS:
            return False
        # isoburn.exe lives in System32 since Windows 7
        for d in (os.environ.get("SystemRoot", r"C:\Windows"),):
            if (Path(d) / "System32" / "isoburn.exe").exists():
                return True
        return shutil.which("isoburn.exe") is not None

    def list_drives(self) -> list[OpticalDrive]:
        # isoburn.exe pops a native dialog and lets the user pick; we don't
        # need to enumerate. But for the UI selector, expose drive letters
        # that look like CD/DVD via WMIC or PowerShell.
        drives: list[OpticalDrive] = []
        try:
            out = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_CDROMDrive | "
                    "ForEach-Object { \"$($_.Drive)|$($_.Name)\" }"
                ],
                capture_output=True, text=True, timeout=10, check=False,
            ).stdout
            for line in out.splitlines():
                line = line.strip()
                if not line or "|" not in line:
                    continue
                letter, name = line.split("|", 1)
                if letter:
                    drives.append(OpticalDrive(device=letter.strip(), name=name.strip()))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        if not drives:
            # Always allow "let isoburn ask"
            drives.append(OpticalDrive(device="", name="Choose at burn time"))
        return drives

    def burn(self, iso_path, drive, verify, eject, progress, log):
        # isoburn syntax: isoburn.exe [/Q] [drive:] image.iso
        # /Q is quiet mode; without it, a native dialog appears with verify
        # checkbox the user can toggle. We honor `verify` only in /Q mode by
        # passing it through the dialog default... isoburn doesn't expose a
        # verify flag directly, so for now we always pop the native dialog
        # which has the verify checkbox front and center.
        cmd = ["isoburn.exe"]
        if drive and drive.device:
            cmd.append(drive.device)
        cmd.append(str(iso_path))
        progress("Launching Windows burner...", -1.0)
        rc = _run_streaming(cmd, log)
        if rc != 0:
            raise RuntimeError(
                f"isoburn.exe exited with status {rc}. "
                "If the dialog was cancelled, try again."
            )
        progress("Burn complete.", 1.0)


# ── Linux ───────────────────────────────────────────────────────────────

class LinuxBurner(BurnerBackend):
    id = "linux"
    label = "Linux xorriso/cdrecord"

    @classmethod
    def is_available(cls) -> bool:
        if Platform.current() is not Platform.LINUX:
            return False
        return any(shutil.which(c) for c in ("xorriso", "wodim", "cdrecord"))

    def _find_tool(self) -> tuple[str, str]:
        for tool in ("xorriso", "wodim", "cdrecord"):
            p = shutil.which(tool)
            if p:
                return tool, p
        raise RuntimeError("No burning tool found (need xorriso, wodim, or cdrecord).")

    def list_drives(self) -> list[OpticalDrive]:
        drives: list[OpticalDrive] = []
        # Try xorriso -as cdrecord --devices first
        try:
            out = subprocess.run(
                ["xorriso", "-as", "cdrecord", "--devices"],
                capture_output=True, text=True, timeout=10, check=False,
            ).stdout
            # Lines like:  0 dev='/dev/sr0' rwrw-- : 'HL-DT-ST' 'DVDRAM GUD0N'
            for line in out.splitlines():
                m = re.search(r"dev='([^']+)'.*:\s*'([^']*)'\s*'([^']*)'", line)
                if m:
                    dev = m.group(1)
                    name = (m.group(2) + " " + m.group(3)).strip()
                    drives.append(OpticalDrive(device=dev, name=name))
        except FileNotFoundError:
            pass

        # Fallback: probe /dev/sr* and /dev/cdrom
        if not drives:
            for cand in ("/dev/sr0", "/dev/sr1", "/dev/cdrom", "/dev/dvd"):
                if Path(cand).exists():
                    drives.append(OpticalDrive(device=cand))
        return drives

    def burn(self, iso_path, drive, verify, eject, progress, log):
        if not drive or not drive.device:
            raise RuntimeError("Select a drive before burning.")
        tool, tool_path = self._find_tool()

        if tool == "xorriso":
            cmd = [
                tool_path, "-as", "cdrecord",
                "-v", f"dev={drive.device}", "-dao",
            ]
            if eject:
                cmd.append("-eject")
            cmd.append(str(iso_path))
        else:
            cmd = [tool_path, "-v", f"dev={drive.device}", "-dao"]
            if eject:
                cmd.append("-eject")
            cmd.append(str(iso_path))

        progress("Burning...", -1.0)
        # cdrecord prints "Track 01: x of y MB" - parse for progress
        rc = _run_streaming(
            cmd, log, progress,
            re.compile(r"Track \d+:\s+(\d+) of (\d+) MB"),
        )
        if rc != 0:
            raise RuntimeError(f"{tool} exited with status {rc}")

        if verify:
            progress("Verifying burn...", -1.0)
            log("Verifying burn (reading disc and comparing)...")
            try:
                ok = self._verify(iso_path, drive.device, log)
                if not ok:
                    raise RuntimeError("Verify failed: written disc does not match ISO.")
                log("Verify OK.")
            except Exception as e:
                raise RuntimeError(f"Verify error: {e}") from e

        progress("Burn complete.", 1.0)

    def _verify(self, iso_path: Path, device: str, log: Callable[[str], None]) -> bool:
        """Compare ISO bytes to read-back from disc, sector by sector."""
        import hashlib
        bs = 2048
        iso_size = iso_path.stat().st_size
        sectors = (iso_size + bs - 1) // bs
        h_iso = hashlib.sha1()
        h_disc = hashlib.sha1()
        with open(iso_path, "rb") as f:
            while chunk := f.read(bs * 256):
                h_iso.update(chunk)
        # Read exactly the same number of sectors back from the device.
        try:
            with open(device, "rb") as f:
                remaining = sectors * bs
                while remaining > 0:
                    chunk = f.read(min(bs * 256, remaining))
                    if not chunk:
                        break
                    h_disc.update(chunk)
                    remaining -= len(chunk)
        except PermissionError:
            log(f"WARNING: cannot read {device} for verify (permission denied). "
                "Try running with sudo or adding your user to the cdrom group.")
            return False
        return h_iso.hexdigest() == h_disc.hexdigest()


# ── Registry ──────────────────────────────────────────────────────────

ALL_BURNERS: list[type[BurnerBackend]] = [MacOSBurner, WindowsBurner, LinuxBurner]


def get_native_burner() -> BurnerBackend | None:
    for cls in ALL_BURNERS:
        if cls.is_available():
            return cls()
    return None
