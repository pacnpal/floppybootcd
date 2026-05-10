"""Tests for project validation and xorriso discovery."""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from floppybootcd.core import iso_builder
from floppybootcd.core.iso_builder import (
    BuildOptions,
    find_xorriso,
    install_hint,
    validate_project,
)
from floppybootcd.core.project import FloppyImage, Project


class TestValidateProject:
    def test_empty_project_reports_no_images(self):
        problems = validate_project(Project())
        assert any("No floppy images" in p for p in problems)

    def test_missing_image_file_reported(self, tmp_path):
        p = Project(images=[FloppyImage(path=str(tmp_path / "missing.img"))])
        problems = validate_project(p)
        assert any("not found" in s for s in problems)

    def test_empty_image_reported(self, tmp_path):
        f = tmp_path / "empty.img"
        f.write_bytes(b"")
        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any("is empty" in s for s in problems)

    def test_oversized_image_warned(self, tmp_path):
        # 51 MiB sparse-style file
        f = tmp_path / "big.img"
        with open(f, "wb") as fh:
            fh.seek(51 * 1024 * 1024)
            fh.write(b"\0")
        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any("unusually large" in s for s in problems)

    def test_normal_image_no_problems(self, tmp_path):
        f = tmp_path / "ok.img"
        f.write_bytes(b"\0" * 1024)
        p = Project(images=[FloppyImage(path=str(f))])
        assert validate_project(p) == []

    def test_vesa_missing_background_reported(self, tmp_path):
        f = tmp_path / "ok.img"
        f.write_bytes(b"\0" * 1024)
        p = Project(
            menu_style="vesa",
            background_image=str(tmp_path / "no-such-bg.png"),
            images=[FloppyImage(path=str(f))],
        )
        problems = validate_project(p)
        assert any("Background image not found" in s for s in problems)

    def test_vesa_present_background_no_problem(self, tmp_path):
        f = tmp_path / "ok.img"
        f.write_bytes(b"\0" * 1024)
        bg = tmp_path / "bg.png"
        bg.write_bytes(b"\x89PNG")
        p = Project(
            menu_style="vesa",
            background_image=str(bg),
            images=[FloppyImage(path=str(f))],
        )
        assert validate_project(p) == []

    def test_valid_imz_no_problems(self, tmp_path):
        f = tmp_path / "boot.imz"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("boot.ima", b"\0" * 1024)
        p = Project(images=[FloppyImage(path=str(f))])
        assert validate_project(p) == []

    def test_corrupt_imz_reported(self, tmp_path):
        f = tmp_path / "broken.imz"
        f.write_bytes(b"this is not a zip")
        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any("not a ZIP-format .imz" in s for s in problems)

    def test_oversized_imz_inner_image_warned(self, tmp_path):
        # Highly compressible inner image: tiny on disk, huge inflated.
        f = tmp_path / "huge.imz"
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("inner.ima", b"\0" * (51 * 1024 * 1024))
        # Sanity: the .imz on disk is *not* >50 MiB — only the inner is.
        assert f.stat().st_size < 50 * 1024 * 1024
        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any("unusually large" in s for s in problems)

    def test_text_menu_ignores_background(self, tmp_path):
        f = tmp_path / "ok.img"
        f.write_bytes(b"\0" * 1024)
        # Background path is invalid — should NOT be reported in text mode.
        p = Project(
            menu_style="text",
            background_image="/no/such/bg.png",
            images=[FloppyImage(path=str(f))],
        )
        assert validate_project(p) == []


class TestFindXorriso:
    def test_override_wins_when_file_exists(self, tmp_path):
        fake = tmp_path / "xorriso"
        fake.write_bytes(b"")
        assert find_xorriso(str(fake)) == str(fake)

    def test_override_ignored_when_file_missing(self, tmp_path, monkeypatch):
        # Falls through to PATH lookup, which we mock.
        monkeypatch.setattr(iso_builder.shutil, "which", lambda name: "/usr/bin/xorriso")
        result = find_xorriso(str(tmp_path / "no-such"))
        assert result == "/usr/bin/xorriso"

    def test_returns_path_lookup(self, monkeypatch):
        calls = []

        def fake_which(name):
            calls.append(name)
            return "/usr/local/bin/xorriso" if name == "xorriso" else None

        monkeypatch.setattr(iso_builder.shutil, "which", fake_which)
        assert find_xorriso() == "/usr/local/bin/xorriso"
        assert calls[0] == "xorriso"

    def test_falls_back_to_xorrisofs(self, monkeypatch):
        def fake_which(name):
            return "/usr/bin/xorrisofs" if name == "xorrisofs" else None

        monkeypatch.setattr(iso_builder.shutil, "which", fake_which)
        assert find_xorriso() == "/usr/bin/xorrisofs"

    def test_returns_none_when_nothing_found(self, monkeypatch):
        monkeypatch.setattr(iso_builder.shutil, "which", lambda name: None)
        # Also pretend no candidate path exists.
        monkeypatch.setattr(iso_builder.Path, "is_file", lambda self: False)
        assert find_xorriso() is None


class TestInstallHint:
    def test_mentions_all_three_platforms(self):
        hint = install_hint()
        assert "macOS" in hint
        assert "Linux" in hint
        assert "Windows" in hint

    def test_mentions_brew_apt_and_url(self):
        hint = install_hint()
        assert "brew install xorriso" in hint
        assert "apt install xorriso" in hint
        assert "gnu.org" in hint or "scoop install" in hint


class TestBuildErrors:
    """The full build path runs xorriso. We don't run it, but we test the
    failure paths that are pure logic."""

    def test_build_raises_on_validation_problems(self, tmp_path):
        project = Project()  # no images → validation fails
        opts = BuildOptions(output_path=tmp_path / "out.iso")
        with pytest.raises(RuntimeError, match="Project has problems"):
            iso_builder.build(project, opts)

    def test_build_raises_when_xorriso_missing(self, tmp_path, monkeypatch):
        f = tmp_path / "ok.img"
        f.write_bytes(b"\0" * 1024)
        project = Project(images=[FloppyImage(path=str(f))])
        opts = BuildOptions(output_path=tmp_path / "out.iso")
        monkeypatch.setattr(iso_builder, "find_xorriso", lambda override="": None)
        with pytest.raises(RuntimeError, match="xorriso is required"):
            iso_builder.build(project, opts)
