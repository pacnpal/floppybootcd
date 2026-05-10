"""Build the actual ISO file by assembling a staging tree and running xorriso."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .project import Project
from . import bootloader, image_prep


def find_xorriso(override: str = "") -> str | None:
    """Locate xorriso. Override wins; then PATH; then known install dirs."""
    if override:
        p = Path(override)
        if p.is_file():
            return str(p)

    found = shutil.which("xorriso") or shutil.which("xorrisofs")
    if found:
        return found

    candidates = [
        # macOS Homebrew
        "/opt/homebrew/bin/xorriso",
        "/usr/local/bin/xorriso",
        # Windows common locations
        r"C:\Program Files\xorriso\xorriso.exe",
        r"C:\xorriso\xorriso.exe",
        r"C:\msys64\usr\bin\xorriso.exe",
        # Linux usual
        "/usr/bin/xorriso",
        "/usr/local/bin/xorriso",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    return None


def install_hint() -> str:
    return (
        "xorriso is required to build ISOs. Install it:\n"
        "  • macOS:    brew install xorriso\n"
        "  • Linux:    sudo apt install xorriso   (or your distro's equivalent)\n"
        "  • Windows:  https://www.gnu.org/software/xorriso/  "
        "(or scoop install xorriso)"
    )


@dataclass
class BuildOptions:
    output_path: Path
    xorriso_override: str = ""
    keep_staging: bool = False     # for debugging


@dataclass
class BuildResult:
    iso_path: Path
    staging_path: Path | None      # None if cleaned up


def validate_project(project: Project) -> list[str]:
    """Return a list of human-readable problems. Empty list = ok."""
    problems = []
    if not project.images:
        problems.append("No floppy images added.")
    for i, img in enumerate(project.images, 1):
        p = Path(img.path)
        if not p.is_file():
            problems.append(f"Image {i} not found: {img.path}")
            continue
        size = p.stat().st_size
        if size == 0:
            problems.append(f"Image {i} ({p.name}) is empty.")
            continue
        if image_prep.is_compressed(p):
            err, inner_size = image_prep.verify_imz_readable(p)
            if err is not None:
                problems.append(f"Image {i} ({p.name}): {err}")
                continue
            # verify_imz_readable already rejects empty inner images,
            # so inner_size is guaranteed > 0 here.
            effective_size = inner_size
        else:
            effective_size = size
        # Floppy images aren't strictly required to be 1.44/2.88, but warn on
        # totally absurd sizes.
        if effective_size > 50 * 1024 * 1024:
            problems.append(
                f"Image {i} ({p.name}) is "
                f"{effective_size // (1024*1024)} MiB which is "
                "unusually large for a floppy image. memdisk supports it but "
                "boot times may be very long."
            )
    if project.menu_style == "vesa":
        if project.background_image and not Path(project.background_image).is_file():
            problems.append(f"Background image not found: {project.background_image}")

    # Capacity check: the on-disc size of the floppy payload (using the
    # *uncompressed* inner size for any .imz containers) plus the VESA
    # background image (when used) must fit on a CD-R after the
    # bootloader / ISO 9660 overhead.
    total = image_prep.total_payload_size(
        img.path for img in project.images if Path(img.path).is_file()
    )
    if project.menu_style == "vesa" and project.background_image:
        bg = Path(project.background_image)
        if bg.is_file():
            total += bg.stat().st_size
    if total > image_prep.CD_USABLE_BYTES:
        problems.append(
            f"Total floppy payload is "
            f"{total / (1024 * 1024):.1f} MiB which exceeds the "
            f"{image_prep.CD_USABLE_BYTES / (1024 * 1024):.0f} MiB "
            "usable on an 80-minute 700 MiB CD-R (after bootloader and "
            "ISO 9660 overhead). Remove some images or burn to DVD media."
        )
    return problems


def build(
    project: Project,
    options: BuildOptions,
    progress: Callable[[str, float], None] | None = None,
    log: Callable[[str], None] | None = None,
) -> BuildResult:
    """Build an ISO from the project. Raises RuntimeError on failure."""
    if log is None:
        log = lambda _: None
    if progress is None:
        progress = lambda *_: None

    problems = validate_project(project)
    if problems:
        raise RuntimeError("Project has problems:\n  • " + "\n  • ".join(problems))

    xorriso = find_xorriso(options.xorriso_override)
    if not xorriso:
        raise RuntimeError(install_hint())
    log(f"Using xorriso: {xorriso}")

    # Stage
    staging_root = Path(tempfile.mkdtemp(prefix="floppybootcd_"))
    iso_root = staging_root / "iso"
    iso_root.mkdir()
    log(f"Staging in: {staging_root}")

    try:
        backend = bootloader.get_backend(project.bootloader)
        log(f"Bootloader: {backend.label}")
        result = backend.stage(project, iso_root, progress=progress)

        # Run xorriso
        progress("Building ISO...", -1.0)
        volid = (project.title or "FLOPPYBOOTCD")[:32]
        cmd = [
            xorriso,
            "-as", "mkisofs",
            "-o", str(options.output_path),
            "-V", volid,
            "-J", "-R",
            "-b", result.boot_image_relpath,
            "-c", result.boot_catalog_relpath,
            *result.extra_xorriso_args,
            str(iso_root),
        ]
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
            log(line.rstrip())
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"xorriso exited with status {rc}")

        size = options.output_path.stat().st_size
        log(f"Built {options.output_path} ({size / (1024*1024):.1f} MiB)")
        progress("Build complete.", 1.0)

        return BuildResult(
            iso_path=options.output_path,
            staging_path=staging_root if options.keep_staging else None,
        )
    finally:
        if not options.keep_staging:
            shutil.rmtree(staging_root, ignore_errors=True)
