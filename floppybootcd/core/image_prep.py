"""Floppy-image extension constants and helpers for staging images.

Owns the single source of truth for which file extensions FloppyBootCD
recognizes as floppy images, and the logic for extracting WinImage
``.imz`` archives at build time. The ``.imz`` format is, in modern
WinImage releases, a plain ZIP wrapping a single raw floppy image
(``.ima`` / ``.img`` / etc.). We support that variant. Pre-WinImage-5
proprietary IMZ compression is not supported and produces a clear
user-facing error.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


# Raw floppy-image extensions. These files are sector-by-sector dumps
# that MEMDISK can boot directly.
FLOPPY_EXTS: frozenset[str] = frozenset({".img", ".ima", ".vfd", ".flp"})

# Compressed container extensions that wrap a single raw floppy image.
COMPRESSED_EXTS: frozenset[str] = frozenset({".imz"})

# Everything the UI is willing to accept (file dialog + drag-drop).
ALL_ACCEPTED_EXTS: frozenset[str] = FLOPPY_EXTS | COMPRESSED_EXTS


def is_compressed(path: str | Path) -> bool:
    """True if *path* names a compressed floppy container we extract."""
    return Path(path).suffix.lower() in COMPRESSED_EXTS


def staged_filename(src_name: str) -> str:
    """Filename to use when staging *src_name* into the ISO's images dir.

    Raw images keep their name; ``.imz`` containers are renamed to the
    extracted image's natural extension (``.ima``) so the filename on
    the burned disc reflects what's actually there.
    """
    p = Path(src_name)
    if p.suffix.lower() in COMPRESSED_EXTS:
        return p.stem + ".ima"
    return p.name


def _open_imz(src: Path) -> zipfile.ZipFile:
    """Open *src* as a WinImage ZIP-format ``.imz``. Raise ValueError
    with a user-facing message if it isn't one."""
    if not zipfile.is_zipfile(src):
        raise ValueError(
            f"{src.name}: not a ZIP-format .imz. Re-save it from "
            "WinImage as 'Compressed image file' or extract the .ima "
            "first; legacy proprietary IMZ compression is not supported."
        )
    return zipfile.ZipFile(src, "r")


def _pick_inner_member(zf: zipfile.ZipFile, src_name: str) -> zipfile.ZipInfo:
    """Pick the floppy-image member from inside an .imz archive."""
    candidates = [
        info for info in zf.infolist()
        if not info.is_dir()
        and Path(info.filename).suffix.lower() in FLOPPY_EXTS
    ]
    if not candidates:
        raise ValueError(
            f"{src_name}: .imz archive contains no floppy image "
            f"({', '.join(sorted(FLOPPY_EXTS))})."
        )
    # WinImage writes exactly one image per .imz. If a hand-crafted
    # archive has multiple, prefer the largest (most likely the real
    # floppy rather than a readme or sidecar).
    candidates.sort(key=lambda i: i.file_size, reverse=True)
    return candidates[0]


def stage_image(src: str | Path, dest_dir: str | Path, dest_name: str) -> Path:
    """Place the raw floppy image for *src* at ``dest_dir/dest_name``.

    For raw floppy images this is a metadata-preserving copy. For
    ``.imz`` archives, the inner image is extracted and written to the
    destination. Returns the destination path.
    """
    src_path = Path(src)
    dest = Path(dest_dir) / dest_name
    if is_compressed(src_path):
        with _open_imz(src_path) as zf:
            member = _pick_inner_member(zf, src_path.name)
            with zf.open(member) as inp, open(dest, "wb") as out:
                shutil.copyfileobj(inp, out)
        return dest
    shutil.copy2(src_path, dest)
    return dest


def probe_uncompressed_size(path: str | Path) -> int:
    """Return the size of the inner floppy image.

    For raw images this is the file size on disk. For ``.imz`` it is
    the uncompressed size of the inner member as recorded in the ZIP
    central directory (no decompression performed). Returns 0 if the
    file is missing or unreadable so callers can render gracefully.
    """
    p = Path(path)
    try:
        if is_compressed(p):
            with _open_imz(p) as zf:
                return _pick_inner_member(zf, p.name).file_size
        return p.stat().st_size
    except (OSError, ValueError, zipfile.BadZipFile):
        return 0
