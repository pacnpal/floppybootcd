"""Download syslinux tarball and extract bootloader binaries.

Cross-platform: works on Linux/macOS/Windows since syslinux ships pre-built
x86 boot blobs (they're target binaries, not host binaries).
"""
from __future__ import annotations

import shutil
import ssl
import tarfile
import urllib.request
from pathlib import Path
from typing import Callable

import certifi

from .platform import cache_dir


# certifi's CA bundle; portable across host Pythons that may lack a
# usable system trust store (notably the python.org macOS builds and
# PyInstaller-bundled Pythons), where the default SSL context yields
# "CERTIFICATE_VERIFY_FAILED" against any HTTPS URL.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


# Files we extract from the BIOS variant of syslinux. menu.c32 and
# vesamenu.c32 depend on the lib*.c32 modules since syslinux 5.x.
REQUIRED_BIOS_FILES = [
    "isolinux.bin",
    "memdisk",
    "ldlinux.c32",
    "libcom32.c32",
    "libutil.c32",
    "libmenu.c32",
    "menu.c32",
    "vesamenu.c32",
    "libgpl.c32",
    "chain.c32",
    "reboot.c32",
    # ACPI power-off shim; backs the "Shutdown" menu entry. Issues an
    # ACPI S5 transition via int 15h AX=5307h. Works on any real or
    # virtual BIOS-flavored machine with ACPI (i.e. everything since
    # ~1999); falls through silently on the rare bare hardware where
    # ACPI isn't wired up.
    "poweroff.c32",
]


def syslinux_cache_dir(version: str) -> Path:
    d = cache_dir() / "syslinux" / version
    d.mkdir(parents=True, exist_ok=True)
    return d


def syslinux_tarball_url(version: str) -> str:
    return (
        f"https://mirrors.edge.kernel.org/pub/linux/utils/boot/syslinux/"
        f"syslinux-{version}.tar.gz"
    )


def have_syslinux_files(version: str) -> bool:
    d = syslinux_cache_dir(version)
    return all((d / f).is_file() for f in REQUIRED_BIOS_FILES)


def _download_to(
    url: str,
    dest: Path,
    label: str,
    progress: Callable[[str, float], None] | None,
) -> None:
    """HTTPS GET `url` into `dest`, streaming with progress callbacks.

    Uses certifi's CA bundle via _SSL_CONTEXT so the download succeeds
    even on hosts without a usable system trust store (notably the
    python.org macOS builds and PyInstaller-bundled Pythons).
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": "floppybootcd/syslinux-fetcher",
    })
    with urllib.request.urlopen(req, context=_SSL_CONTEXT) as resp:
        total = int(resp.headers.get("Content-Length", "0") or 0)
        read = 0
        with open(dest, "wb") as out:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                read += len(chunk)
                if progress and total > 0:
                    progress(label, min(1.0, read / total))


def fetch_syslinux(
    version: str,
    progress: Callable[[str, float], None] | None = None,
    force: bool = False,
) -> Path:
    """Ensure syslinux binaries are cached locally. Returns the cache dir.

    progress(message, fraction) where fraction is 0..1 or -1 for indeterminate.
    """
    d = syslinux_cache_dir(version)
    if not force and have_syslinux_files(version):
        if progress:
            progress("Using cached syslinux binaries.", 1.0)
        return d

    tarball = d / f"syslinux-{version}.tar.gz"
    url = syslinux_tarball_url(version)

    if force or not tarball.is_file():
        if progress:
            progress(f"Downloading syslinux {version}...", -1.0)
        try:
            _download_to(url, tarball,
                         label=f"Downloading syslinux {version}...",
                         progress=progress)
        except Exception as e:
            if tarball.exists():
                tarball.unlink()
            raise RuntimeError(
                f"Failed to download syslinux {version} from {url}: {e}"
            ) from e

    if progress:
        progress("Extracting syslinux modules...", -1.0)

    needed = set(REQUIRED_BIOS_FILES)
    found: set[str] = set()
    with tarfile.open(tarball, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = Path(member.name).name
            if name in needed and name not in found:
                # We want the BIOS variant; member paths look like
                # syslinux-6.03/bios/com32/menu/menu.c32 etc. The non-bios
                # versions live under efi32/efi64. Skip those.
                lower = member.name.lower()
                if "/efi32/" in lower or "/efi64/" in lower:
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                (d / name).write_bytes(f.read())
                found.add(name)
                if progress:
                    progress(f"Extracted {name}", len(found) / len(needed))
                if len(found) == len(needed):
                    break

    missing = needed - found
    if missing:
        raise RuntimeError(
            f"Could not find these files in syslinux tarball: "
            f"{', '.join(sorted(missing))}"
        )

    if progress:
        progress("Syslinux ready.", 1.0)
    return d


def clear_cache(version: str | None = None) -> None:
    base = cache_dir() / "syslinux"
    if not base.exists():
        return
    if version is None:
        shutil.rmtree(base, ignore_errors=True)
    else:
        shutil.rmtree(base / version, ignore_errors=True)
