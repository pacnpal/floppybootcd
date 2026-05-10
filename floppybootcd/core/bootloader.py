"""Bootloader plugin interface.

Implementations write the bootloader's binaries and config into a staging
directory. Adding GRUB4DOS or another loader later is just a new subclass.
"""
from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .project import Project
from . import image_prep, syslinux_fetcher


@dataclass
class StagingResult:
    """Returned by a bootloader after staging. Tells the ISO builder what
    El Torito boot record to use."""
    boot_image_relpath: str          # path to boot record, relative to ISO root
    boot_catalog_relpath: str        # path for boot.cat
    extra_xorriso_args: list[str]    # any per-bootloader xorriso flags


class BootloaderBackend(ABC):
    id: str = ""
    label: str = ""

    @abstractmethod
    def stage(
        self,
        project: Project,
        iso_root: Path,
        progress: Callable[[str, float], None] | None = None,
    ) -> StagingResult:
        """Lay out everything the bootloader needs in iso_root."""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Whether this bootloader can be used (e.g. binaries downloadable)."""


def _safe_label(name: str) -> str:
    """ISOLINUX LABEL must be alphanumeric-ish."""
    out = []
    for c in name:
        out.append(c if c.isalnum() else "_")
    s = "".join(out)
    return s or "entry"


def _shorten_filename_iso9660(name: str) -> str:
    """ISO 9660 Joliet/RR allows long names but mkisofs default level 1 is 8.3.
    We use -J -R below so this is mostly informational. xorriso handles long
    names fine."""
    return name


class IsolinuxBackend(BootloaderBackend):
    """Default backend: ISOLINUX + MEMDISK from syslinux 6.x."""
    id = "isolinux"
    label = "ISOLINUX (BIOS)"

    @classmethod
    def is_available(cls) -> bool:
        return True  # We download what we need

    def stage(
        self,
        project: Project,
        iso_root: Path,
        progress: Callable[[str, float], None] | None = None,
    ) -> StagingResult:
        if progress:
            progress("Preparing bootloader...", -1.0)

        sl_dir = syslinux_fetcher.fetch_syslinux(
            project.syslinux_version, progress=progress
        )

        isolinux_dir = iso_root / "isolinux"
        images_dir = iso_root / "images"
        isolinux_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

        # Copy bootloader binaries + ALL needed COM32 modules. Missing libs
        # is the #1 cause of "Failed to load libcom32.c32" boot errors.
        for fname in syslinux_fetcher.REQUIRED_BIOS_FILES:
            src = sl_dir / fname
            if src.is_file():
                shutil.copy2(src, isolinux_dir / fname)

        # If using vesa menu, copy the background image
        if project.menu_style == "vesa" and project.background_image:
            bg_src = Path(project.background_image)
            if bg_src.is_file():
                shutil.copy2(bg_src, isolinux_dir / "background.png")

        # Stage floppy images, dedup names if needed. Compressed (.imz)
        # sources are extracted; the on-disc filename uses the inner
        # image's natural extension via image_prep.staged_filename.
        seen: set[str] = set()
        renamed: dict[int, str] = {}
        for idx, img in enumerate(project.images):
            src = Path(img.path)
            target_name = image_prep.staged_filename(src.name)
            n = 1
            stem, ext = Path(target_name).stem, Path(target_name).suffix
            while target_name.lower() in seen:
                target_name = f"{stem}_{n}{ext}"
                n += 1
            seen.add(target_name.lower())
            renamed[idx] = target_name
            image_prep.stage_image(src, images_dir, target_name)
            if progress:
                progress(f"Staged {target_name}",
                         (idx + 1) / max(1, len(project.images)))

        # Write isolinux.cfg
        cfg = self._write_config(project, renamed)
        (isolinux_dir / "isolinux.cfg").write_text(cfg, encoding="utf-8")

        return StagingResult(
            boot_image_relpath="isolinux/isolinux.bin",
            boot_catalog_relpath="isolinux/boot.cat",
            extra_xorriso_args=[
                "-no-emul-boot",
                "-boot-load-size", "4",
                "-boot-info-table",
            ],
        )

    def _write_config(self, project: Project, renamed: dict[int, str]) -> str:
        ui_module = "vesamenu.c32" if project.menu_style == "vesa" else "menu.c32"
        lines = [
            f"UI {ui_module}",
            "PROMPT 0",
            f"TIMEOUT {max(0, project.timeout_secs) * 10}",  # 1/10s units
            "",
            f"MENU TITLE {project.title}",
        ]
        if project.menu_style == "vesa" and project.background_image:
            lines.append("MENU BACKGROUND background.png")
        lines += [
            "MENU COLOR border       30;44   #40ffffff #a0000000 std",
            "MENU COLOR title        1;36;44 #9033ccff #a0000000 std",
            "MENU COLOR sel          7;37;40 #e0ffffff #20ffffff all",
            "MENU COLOR unsel        37;44   #50ffffff #a0000000 std",
            "MENU COLOR help         37;40   #c0ffffff #a0000000 std",
            "MENU COLOR timeout_msg  37;40   #80ffffff #00000000 std",
            "MENU COLOR timeout      1;37;40 #c0ffffff #00000000 std",
            "",
        ]

        # Determine default
        default_label = None
        for idx, img in enumerate(project.images):
            if img.default:
                default_label = _safe_label(renamed[idx])
                break
        if default_label is None and project.images:
            default_label = _safe_label(renamed[0])
        if default_label:
            lines.insert(1, f"DEFAULT {default_label}")

        # Entries
        for idx, img in enumerate(project.images):
            target = renamed[idx]
            lbl = _safe_label(target)
            display = img.display_label
            if img.hotkey and img.hotkey in display:
                # Insert ^ before the hotkey character (first occurrence).
                pos = display.find(img.hotkey)
                display = display[:pos] + "^" + display[pos:]
            lines.append(f"LABEL {lbl}")
            if img.default:
                lines.append("  MENU DEFAULT")
            lines.append(f"  MENU LABEL {display}")
            if img.description:
                lines.append("  TEXT HELP")
                for ln in img.description.splitlines() or [img.description]:
                    lines.append(f"  {ln}")
                lines.append("  ENDTEXT")
            lines.append(f"  KERNEL /isolinux/memdisk")
            lines.append(f"  APPEND initrd=/images/{target}")
            lines.append("")

        # Always offer reboot + boot from local disk
        lines += [
            "LABEL local",
            "  MENU LABEL Boot from ^hard disk",
            "  LOCALBOOT 0x80",
            "",
            "LABEL reboot",
            "  MENU LABEL ^Reboot",
            "  COM32 reboot.c32",
            "",
        ]
        return "\n".join(lines)


# Registry of available backends. Plugin-discovered backends extend this
# (see plugins.py).
BUILTIN_BACKENDS: dict[str, type[BootloaderBackend]] = {
    IsolinuxBackend.id: IsolinuxBackend,
}


def get_backend(backend_id: str) -> BootloaderBackend:
    cls = BUILTIN_BACKENDS.get(backend_id)
    if cls is None:
        raise ValueError(f"Unknown bootloader backend: {backend_id}")
    return cls()


def available_backends() -> Iterable[type[BootloaderBackend]]:
    return BUILTIN_BACKENDS.values()
