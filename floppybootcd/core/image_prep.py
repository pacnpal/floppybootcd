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

import functools
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

# Capacity of a standard 80-minute CD-R, in bytes (700 MiB). The real
# usable size after the ISO 9660 / Joliet / Rock Ridge directory
# overhead and the bootloader payload is slightly less; we reserve a
# small headroom margin for that.
CD_R_CAPACITY_BYTES: int = 700 * 1024 * 1024
CD_OVERHEAD_BYTES: int = 8 * 1024 * 1024  # ISO metadata + isolinux + memdisk
CD_USABLE_BYTES: int = CD_R_CAPACITY_BYTES - CD_OVERHEAD_BYTES


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


def verify_imz_readable(path: str | Path) -> str | None:
    """Return None if *path* is a fully readable ``.imz`` we can stage.

    Otherwise return a user-facing error string explaining why. The
    returned string never repeats the source filename — callers are
    expected to prefix their own context. This goes beyond
    ``probe_uncompressed_size`` (which only reads the ZIP central
    directory) by checking the inner member's encryption flag and
    attempting a small read so the build doesn't fail mid-stage on
    encrypted / password-protected archives or unsupported
    compression methods.
    """
    p = Path(path)
    try:
        with _open_imz(p) as zf:
            member = _pick_inner_member(zf, p.name)
            # Bit 0 of the general-purpose flag is the encryption flag.
            if member.flag_bits & 0x1:
                return (
                    "inner image is encrypted (password-protected). "
                    "Re-save it from WinImage without a password, or "
                    "extract the .ima first."
                )
            # A 0-byte inner image is structurally readable but
            # non-bootable; reject up-front rather than producing an
            # empty staged .ima.
            if member.file_size == 0:
                return "inner image is empty (0 bytes)."
            # Attempt a small read to surface unsupported compression
            # methods (NotImplementedError) and CRC issues now rather
            # than during the build.
            with zf.open(member) as fh:
                fh.read(1)
    except ValueError as e:
        # _open_imz / _pick_inner_member raise with a "{name}: ..."
        # prefix for callers like stage_image that want a standalone
        # message. Strip it so this helper's contract — "no filename"
        # — holds and callers can add their own prefix.
        msg = str(e)
        prefix = f"{p.name}: "
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
        return msg
    except (
        zipfile.BadZipFile,
        OSError,
        RuntimeError,
        NotImplementedError,
    ) as e:
        return (
            f"failed to read .imz ({e}). Re-save it from WinImage as "
            "'Compressed image file' or extract the .ima first."
        )
    return None


def stage_image(src: str | Path, dest_dir: str | Path, dest_name: str) -> Path:
    """Place the raw floppy image for *src* at ``dest_dir/dest_name``.

    For raw floppy images this is a metadata-preserving copy. For
    ``.imz`` archives, the inner image is extracted and written to the
    destination. Returns the destination path.
    """
    src_path = Path(src)
    dest = Path(dest_dir) / dest_name
    if is_compressed(src_path):
        try:
            with _open_imz(src_path) as zf:
                member = _pick_inner_member(zf, src_path.name)
                with zf.open(member) as inp, open(dest, "wb") as out:
                    shutil.copyfileobj(inp, out)
        except (
            zipfile.BadZipFile,
            OSError,
            RuntimeError,            # encrypted/password-protected member
            NotImplementedError,     # unsupported compression method
        ) as e:
            # is_zipfile() can pass and a later read still fail (truncated
            # archive, bad CRC, encrypted member, unsupported compression).
            # Convert to the same user-facing message _open_imz uses.
            raise ValueError(
                f"{src_path.name}: failed to extract .imz "
                f"({e}). Re-save it from WinImage as 'Compressed image "
                "file' or extract the .ima first."
            ) from e
        return dest
    shutil.copy2(src_path, dest)
    return dest


def total_payload_size(paths) -> int:
    """Sum the effective floppy-image bytes across *paths*.

    For ``.imz`` containers this counts the *uncompressed* inner image
    size (what actually lands on the burned disc), not the archive
    size on disk. Missing or unreadable files contribute 0.
    """
    return sum(probe_uncompressed_size(p) for p in paths)


@functools.lru_cache(maxsize=512)
def _imz_inner_size_cached(path_str: str, mtime_ns: int, size: int) -> int:
    """Read the uncompressed inner-image size out of an ``.imz`` ZIP
    central directory. Cached on (path, mtime, on-disk size) so the UI
    can call this on every refresh without re-opening the archive.
    """
    try:
        with _open_imz(Path(path_str)) as zf:
            return _pick_inner_member(zf, Path(path_str).name).file_size
    except (OSError, ValueError, zipfile.BadZipFile):
        return 0


def probe_uncompressed_size(path: str | Path) -> int:
    """Return the size of the inner floppy image.

    For raw images this is the file size on disk. For ``.imz`` it is
    the uncompressed size of the inner member as recorded in the ZIP
    central directory (no decompression performed). Returns 0 if the
    file is missing or unreadable so callers can render gracefully.

    For ``.imz`` the answer is memoized on (path, mtime, size) so
    repeated UI refreshes don't repeatedly open the archive.
    """
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return 0
    if is_compressed(p):
        return _imz_inner_size_cached(str(p), st.st_mtime_ns, st.st_size)
    return st.st_size
