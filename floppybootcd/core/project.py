"""Project data model. JSON-serializable for save/load (.fbcd files)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class FloppyImage:
    """One floppy image entry in a project."""
    path: str                     # absolute path to .img/.ima
    label: str = ""               # boot menu label (defaults to filename)
    description: str = ""         # optional help text shown under entry
    hotkey: str = ""              # single char, used as ^X in MENU LABEL
    default: bool = False         # is this the default entry?

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def display_label(self) -> str:
        return self.label or self.filename

    @property
    def exists(self) -> bool:
        return Path(self.path).is_file()

    @property
    def size_bytes(self) -> int:
        try:
            return Path(self.path).stat().st_size
        except OSError:
            return 0


@dataclass
class Project:
    """A FloppyBootCD project. Saveable as .fbcd (JSON)."""
    title: str = "FloppyBootCD"
    images: list[FloppyImage] = field(default_factory=list)
    timeout_secs: int = 30                # boot menu timeout (0 = no auto-boot)
    menu_style: str = "text"              # "text" (menu.c32) or "vesa" (vesamenu.c32)
    bootloader: str = "isolinux"          # plugin id; future: grub4dos
    syslinux_version: str = "6.03"
    background_image: str = ""            # path; only used when menu_style=vesa
    notes: str = ""                       # free text shown in menu help

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Project":
        # Filter unknown keys at both levels so newer .fbcd files (which may
        # have added Project or FloppyImage fields) still open in older
        # clients with the unknown bits dropped.
        img_valid = {f for f in FloppyImage.__dataclass_fields__}
        imgs = [
            FloppyImage(**{k: v for k, v in i.items() if k in img_valid})
            for i in d.get("images", [])
        ]
        valid = {f for f in cls.__dataclass_fields__}
        clean = {k: v for k, v in d.items() if k in valid and k != "images"}
        return cls(images=imgs, **clean)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def has_default(self) -> bool:
        return any(i.default for i in self.images)

    def ensure_one_default(self) -> None:
        """Pick the first image as default if none is set."""
        if self.images and not self.has_default():
            self.images[0].default = True
