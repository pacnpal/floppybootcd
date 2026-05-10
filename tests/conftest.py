"""Shared test config. Force Qt to use the offscreen platform plugin so the
suite runs in CI without a display server."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from floppybootcd.core.project import FloppyImage, Project


@pytest.fixture
def fake_floppy(tmp_path):
    """Create a small file that looks like a floppy image."""
    def _make(name: str = "boot.img", size: int = 1474560) -> str:
        p = tmp_path / name
        p.write_bytes(b"\0" * size)
        return str(p)
    return _make


@pytest.fixture
def project_with_images(fake_floppy):
    p = Project(title="Test Disc")
    p.images.append(FloppyImage(path=fake_floppy("a.img"), label="Alpha"))
    p.images.append(FloppyImage(path=fake_floppy("b.img"), label="Beta"))
    p.ensure_one_default()
    return p
