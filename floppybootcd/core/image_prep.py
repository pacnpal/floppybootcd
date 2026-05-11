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
import heapq
import os
import re
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


def normalize_for_dedup(path: str | Path) -> str:
    """Canonical string form of *path* for duplicate-detection only.

    Different ingestion paths can produce textually-different strings
    for the same file:

    * ``QUrl.toLocalFile()`` returns forward slashes on Windows
      (``C:/dos/boot.img``).
    * ``os.scandir`` and ``pathlib`` return native separators
      (``C:\\dos\\boot.img``).
    * Mixed-case drive letters (``c:\\…`` vs ``C:\\…``) are the same
      file on Windows but unequal as strings.

    Plain string equality misses these and lets duplicates slip past
    dedup. Use ``os.path.normcase(os.path.normpath(...))``: textual
    only (no filesystem queries), works on non-existent paths, and
    handles separator + case quirks on every supported platform.

    The returned string is for ``in``-set lookups and not stored in
    the project — :class:`FloppyImage.path` keeps the original form
    so the UI displays paths as the user supplied them.
    """
    return os.path.normcase(os.path.normpath(str(path)))


# Recursion cap for folder drops. A drag-and-drop is a user gesture
# meant to express "all the disks in this pile" — not "scan my whole
# home directory". Five levels deep is generous for any realistic
# floppy-collection layout (e.g. <year>/<vendor>/<product>/<disk>)
# without turning a wrong-folder drop into a multi-minute disk scan.
_DROP_RECURSION_LIMIT = 5

# Per-drop file cap. Anything more than this is almost certainly a
# misdrop (user grabbed the wrong folder); silently truncate and let
# the UI show what made it in.
_DROP_FILE_LIMIT = 1024

# Per-directory cap on the kept (post-sort) entry count. heapq.nsmallest
# below iterates the whole directory but only retains the N
# lexicographically-smallest names, so memory + downstream work stay
# bounded regardless of how many entries a misdropped folder has, and
# the kept subset is the same on every filesystem (deterministic).
# Set to 8x the per-drop file cap so a typical "folder of floppies"
# (a few hundred files) easily fits while a pathological misdrop
# (~/Downloads, /, the desktop) still terminates with a stable
# lex-smallest prefix.
_DROP_DIR_SCAN_CAP = _DROP_FILE_LIMIT * 8


def walk_floppy_images(path: str | Path) -> list[str]:
    """Return floppy-image paths discovered at *path*.

    - If *path* is a file with a recognized extension, returns it as a
      single-element list.
    - If *path* is a directory, walks it (up to ``_DROP_RECURSION_LIMIT``
      levels) and returns every floppy image inside in a deterministic
      depth-first order: each directory's entries are sorted by name
      and folders descended into before moving to the next sibling.
      Order is stable across runs for a given filesystem layout but is
      *not* a global lexicographic sort across nested folders — files
      group by their containing directory, which is what users expect
      when re-opening a previously-built collection.
    - Otherwise returns an empty list.

    Skips hidden files (``.foo``), dot-directories, and macOS
    ``.AppleDouble`` / Windows ``$RECYCLE.BIN`` cruft so drops on
    cloud-synced collections behave predictably.
    """
    p = Path(path)
    if p.is_file():
        return [str(p)] if p.suffix.lower() in ALL_ACCEPTED_EXTS else []
    if not p.is_dir():
        return []

    skip_dir_names = {".AppleDouble", "$RECYCLE.BIN", "System Volume Information"}
    results: list[str] = []

    def _walk(d: Path, depth: int) -> None:
        if depth > _DROP_RECURSION_LIMIT or len(results) >= _DROP_FILE_LIMIT:
            return
        # os.scandir + heapq.nsmallest gives us deterministic,
        # bounded-memory directory enumeration. `sorted(iterdir())`
        # was O(N log N) and ate memory proportional to the source
        # dir size. A previous attempt at `sorted(islice(scandir, N))`
        # bounded memory but was non-deterministic for dirs > N
        # entries because os.scandir's iteration order isn't
        # specified — the *subset* selected by islice depended on
        # the filesystem and could vary between runs.
        # heapq.nsmallest iterates the full scandir but only retains
        # the N lex-smallest entries, so memory stays bounded AND
        # the subset is stable across filesystems and runs.
        # DirEntry objects hold cached name + stat info populated
        # during scandir, so they remain valid (and avoid extra
        # syscalls) after the scandir context closes.
        try:
            with os.scandir(d) as it:
                entries = heapq.nsmallest(
                    _DROP_DIR_SCAN_CAP, it, key=lambda e: e.name,
                )
        except OSError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            # DirEntry.is_dir() / is_file() use cached stat data
            # populated by the OS during scandir, so they don't
            # cost an extra syscall per entry the way Path versions
            # would.
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in skip_dir_names:
                        continue
                    _walk(Path(entry.path), depth + 1)
                    if len(results) >= _DROP_FILE_LIMIT:
                        return
                elif entry.is_file(follow_symlinks=False):
                    if Path(entry.name).suffix.lower() in ALL_ACCEPTED_EXTS:
                        results.append(entry.path)
                        if len(results) >= _DROP_FILE_LIMIT:
                            return
            except OSError:
                # Permission denied / unreadable entry — skip and
                # keep scanning; one bad entry shouldn't abort the
                # whole drop.
                continue

    _walk(p, 0)
    return results


# Characters SYSLINUX/ISOLINUX can't tolerate in an APPEND path
# (whitespace splits the kernel command line, '#' starts a comment, ';'
# and ',' are field separators in some loaders). Replaced with '_' to
# keep the on-disc filename unambiguous. ISO 9660 itself permits more,
# but the bootloader is the strict link in the chain.
_ISO_UNSAFE_CHARS_RE = re.compile(r"[\s#;,]+")


def _sanitize_iso_filename(name: str) -> str:
    """Make *name* safe to embed in an ISOLINUX APPEND directive.

    Replaces whitespace and a few other ISOLINUX-unsafe characters
    with single underscores, collapses underscore runs, and trims
    leading/trailing underscores. Empty results fall back to "image".
    """
    s = _ISO_UNSAFE_CHARS_RE.sub("_", name)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "image"


def staged_filename(src_name: str) -> str:
    """Filename to use when staging *src_name* into the ISO's images dir.

    Raw images keep their name (with whitespace and other
    SYSLINUX-unsafe characters replaced with underscores so the
    isolinux.cfg ``APPEND initrd=/images/<file>`` line parses
    correctly). ``.imz`` containers are always staged as
    ``<stem>.ima`` regardless of the inner member's actual extension
    (``.ima`` is the canonical raw-floppy-image extension and what
    the burned disc should advertise).
    """
    p = Path(src_name)
    if p.suffix.lower() in COMPRESSED_EXTS:
        return _sanitize_iso_filename(p.stem) + ".ima"
    return _sanitize_iso_filename(p.stem) + p.suffix


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


def verify_imz_readable(path: str | Path) -> tuple[str | None, int]:
    """Validate a ``.imz`` and return ``(error, inner_size)``.

    On success, ``error`` is ``None`` and ``inner_size`` is the
    uncompressed size of the inner floppy image in bytes — callers
    (e.g. ``validate_project``) can reuse it without re-opening the
    archive.

    On failure, ``error`` is a user-facing string explaining why and
    ``inner_size`` is 0. The returned string never repeats the source
    filename — callers prefix their own context.

    Checks performed:
    - file is a real ZIP archive
    - archive contains a floppy-image member
    - inner member is not flagged as encrypted (general-purpose bit 0)
    - inner member is non-empty
    - inner member is openable and decompresses cleanly all the way
      to EOF — surfaces ``NotImplementedError`` for unsupported
      compression methods, ``zipfile.BadZipFile`` for CRC mismatches,
      and ``OSError`` for truncated streams. The decompressed bytes
      are discarded chunk-by-chunk so memory use stays flat even on
      multi-MiB floppy images.
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
                    "extract the .ima first.",
                    0,
                )
            # A 0-byte inner image is structurally readable but
            # non-bootable; reject up-front rather than producing an
            # empty staged .ima.
            if member.file_size == 0:
                return ("inner image is empty (0 bytes).", 0)
            # Stream the inner member end-to-end. zipfile only
            # validates the CRC on a full read, so this catches CRC
            # mismatches and truncated archives now rather than
            # half-way through the build. Bytes are discarded chunk
            # by chunk so memory use stays flat even on multi-MiB
            # floppy images.
            with zf.open(member) as fh:
                while fh.read(64 * 1024):
                    pass
            return (None, member.file_size)
    except ValueError as e:
        # _open_imz / _pick_inner_member raise with a "{name}: ..."
        # prefix for callers like stage_image that want a standalone
        # message. Strip it so this helper's contract — "no filename"
        # — holds and callers can add their own prefix.
        msg = str(e)
        prefix = f"{p.name}: "
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
        return (msg, 0)
    except (
        zipfile.BadZipFile,
        OSError,
        RuntimeError,
        NotImplementedError,
    ) as e:
        return (
            f"failed to read .imz ({e}). Re-save it from WinImage as "
            "'Compressed image file' or extract the .ima first.",
            0,
        )


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


def total_disc_payload(image_paths, *, vesa_background: str | Path | None = None) -> int:
    """Sum every byte that will land on the burned disc.

    Wraps :func:`total_payload_size` for the floppy images and adds
    the staged VESA background image when *vesa_background* is set
    (callers pass ``None`` in text-menu mode so the background is
    correctly excluded). Centralizes the capacity math so the
    pre-build validator and the UI status-bar indicator can't drift
    apart.
    """
    total = total_payload_size(image_paths)
    if vesa_background:
        bg = Path(vesa_background)
        if bg.is_file():
            total += bg.stat().st_size
    return total


@functools.lru_cache(maxsize=512)
def _imz_inner_size_cached(path_str: str, mtime_ns: int, size: int) -> int:
    """Read the uncompressed inner-image size out of an ``.imz`` ZIP
    central directory. Cached on (path, mtime, on-disk size) so the UI
    can call this on every refresh without re-opening the archive.

    Returns 0 for any condition that the UI should render as "invalid":
    not a ZIP, no recognizable floppy member, or the chosen member is
    flagged as encrypted (which would block extraction at build time).
    Callers needing a structured reason should use
    :func:`verify_imz_readable` instead.
    """
    try:
        with _open_imz(Path(path_str)) as zf:
            member = _pick_inner_member(zf, Path(path_str).name)
            if member.flag_bits & 0x1:
                # Encrypted member — central directory still has a
                # plausible file_size, but the UI must not present it
                # as a valid floppy size.
                return 0
            return member.file_size
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
