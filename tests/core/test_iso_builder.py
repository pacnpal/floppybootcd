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


def _find_zip_header(
    raw: bytearray,
    signature: bytes,
    fixed_size: int,
    member_name: bytes,
) -> int:
    """Return the byte offset of the ZIP header (local file or central
    directory) whose filename matches *member_name*. Scans every
    occurrence of *signature* so the test doesn't accidentally patch
    the wrong entry if the archive gains additional members.

    *fixed_size* is the size of the fixed-width portion of the header
    (30 for local file header, 46 for central directory file header) —
    the filename immediately follows.
    """
    start = 0
    while True:
        i = raw.find(signature, start)
        if i < 0:
            raise AssertionError(
                f"No header {signature!r} for {member_name!r} found"
            )
        # Filename is at offset fixed_size; its length is the last 2
        # bytes before it... but for our purposes a prefix match is
        # enough since we control both ends.
        if raw[i + fixed_size : i + fixed_size + len(member_name)] == member_name:
            return i
        start = i + len(signature)


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

    def test_encrypted_imz_reported_at_validation(self, tmp_path):
        # stdlib zipfile can't write encrypted archives, and writestr
        # resets the flag bits. Build a normal archive, then hex-patch
        # the encryption flag (bit 0 of the general-purpose flag) in
        # both the local file header and the central directory entry
        # for the inner.ima entry so ZipInfo.flag_bits reads back with
        # bit 0 set.
        f = tmp_path / "encrypted.imz"
        member_name = b"inner.ima"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr(member_name.decode(), b"\0" * 32)
        raw = bytearray(f.read_bytes())

        # Locate the local file header for member_name. Layout:
        #   PK\x03\x04 ver(2) flag(2@6) method(2) mtime(2) mdate(2)
        #   crc(4)  compsize(4)  uncompsize(4)  namelen(2@26)  extralen(2@28)
        #   filename ...
        lfh = _find_zip_header(raw, b"PK\x03\x04", 30, member_name)
        raw[lfh + 6] |= 0x01

        # Locate the central directory entry for member_name. Layout:
        #   PK\x01\x02 vermade(2) verneeded(2) flag(2@8) method(2)
        #   mtime(2) mdate(2) crc(4) compsize(4) uncompsize(4)
        #   namelen(2@28) extralen(2@30) commentlen(2@32) ...
        #   filename ...
        cdh = _find_zip_header(raw, b"PK\x01\x02", 46, member_name)
        raw[cdh + 8] |= 0x01
        f.write_bytes(bytes(raw))

        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any("encrypted" in s.lower() for s in problems)

    def test_imz_with_empty_inner_image_reported(self, tmp_path):
        # Archive opens fine and the inner member is readable, but the
        # inner image is zero bytes — must be rejected, mirroring the
        # raw-image empty check.
        f = tmp_path / "empty_inner.imz"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("inner.ima", b"")
        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any(
            "empty" in s.lower() and "inner" in s.lower() for s in problems
        )

    def test_imz_without_floppy_member_reported(self, tmp_path):
        f = tmp_path / "nofloppy.imz"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("readme.txt", b"hello")
        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any("no floppy image" in s for s in problems)

    def test_oversized_imz_inner_image_warned(self, tmp_path):
        # Highly compressible inner image: tiny on disk, huge inflated.
        # Stream from a sparse file so we don't allocate 51 MiB in RAM.
        inner = tmp_path / "inner.ima"
        with open(inner, "wb") as fh:
            fh.seek(51 * 1024 * 1024 - 1)
            fh.write(b"\0")
        f = tmp_path / "huge.imz"
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(inner, arcname="inner.ima")
        # Sanity: the .imz on disk is *not* >50 MiB — only the inner is.
        assert f.stat().st_size < 50 * 1024 * 1024
        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any("unusually large" in s for s in problems)

    def test_total_payload_within_capacity_no_problem(self, tmp_path):
        f = tmp_path / "ok.img"
        f.write_bytes(b"\0" * (1440 * 1024))
        p = Project(images=[FloppyImage(path=str(f))])
        assert validate_project(p) == []

    def test_total_payload_exceeding_cd_capacity_reported(
        self, tmp_path, monkeypatch
    ):
        # Shrink the usable capacity for the test rather than allocating
        # a real 700 MB worth of files. Patch via the iso_builder module
        # since validate_project reads the constant through image_prep.
        from floppybootcd.core import image_prep as ip
        monkeypatch.setattr(ip, "CD_USABLE_BYTES", 4096)
        f = tmp_path / "big.img"
        f.write_bytes(b"\0" * 8192)  # 8 KB > 4 KB usable
        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any("exceeds" in s and "CD-R" in s for s in problems)

    def test_vesa_background_counts_against_capacity(
        self, tmp_path, monkeypatch
    ):
        # The VESA background image is staged onto the ISO, so it
        # should count against the CD-R budget.
        from floppybootcd.core import image_prep as ip
        monkeypatch.setattr(ip, "CD_USABLE_BYTES", 8192)
        f = tmp_path / "ok.img"
        f.write_bytes(b"\0" * 4096)  # under capacity on its own
        bg = tmp_path / "bg.png"
        bg.write_bytes(b"\0" * 8192)  # pushes total over capacity
        p = Project(
            menu_style="vesa",
            background_image=str(bg),
            images=[FloppyImage(path=str(f))],
        )
        problems = validate_project(p)
        assert any("exceeds" in s and "CD-R" in s for s in problems)

    def test_text_menu_ignores_background_for_capacity(
        self, tmp_path, monkeypatch
    ):
        # In text-menu mode the background image isn't staged, so a
        # huge background must not trip the capacity check.
        from floppybootcd.core import image_prep as ip
        monkeypatch.setattr(ip, "CD_USABLE_BYTES", 8192)
        f = tmp_path / "ok.img"
        f.write_bytes(b"\0" * 4096)
        bg = tmp_path / "bg.png"
        bg.write_bytes(b"\0" * 1024 * 1024)
        p = Project(
            menu_style="text",
            background_image=str(bg),
            images=[FloppyImage(path=str(f))],
        )
        # No problems — capacity ignores the background in text mode.
        assert validate_project(p) == []

    def test_imz_inner_size_counts_against_capacity(
        self, tmp_path, monkeypatch
    ):
        # A tiny-on-disk .imz with a large inner image should be flagged
        # by capacity check based on the inner uncompressed size.
        from floppybootcd.core import image_prep as ip
        monkeypatch.setattr(ip, "CD_USABLE_BYTES", 4096)
        f = tmp_path / "huge.imz"
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("inner.ima", b"\0" * 8192)
        # The .imz on disk is well under 4 KB; only the inner is over.
        assert f.stat().st_size < 4096
        p = Project(images=[FloppyImage(path=str(f))])
        problems = validate_project(p)
        assert any("exceeds" in s and "CD-R" in s for s in problems)

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

    def test_build_resolves_relative_output_path(self, tmp_path, monkeypatch):
        """xorriso runs with cwd=staging_root, so a relative output_path
        must be absolutized first — otherwise the ISO would land inside
        the staging tree and be wiped by the cleanup."""
        f = tmp_path / "ok.img"
        f.write_bytes(b"\0" * 1024)
        project = Project(images=[FloppyImage(path=str(f))])

        monkeypatch.chdir(tmp_path)
        opts = BuildOptions(output_path=Path("out.iso"))  # relative!
        expected_abs = (tmp_path / "out.iso").resolve()

        monkeypatch.setattr(
            iso_builder, "find_xorriso", lambda override="": "/usr/bin/xorriso"
        )

        # Stub the bootloader so we don't pull a real syslinux.
        stub_stage = iso_builder.bootloader.StagingResult(
            boot_image_relpath="isolinux/isolinux.bin",
            boot_catalog_relpath="isolinux/boot.cat",
            extra_xorriso_args=[],
        )
        fake_backend = MagicMock()
        fake_backend.label = "stub"
        fake_backend.stage.return_value = stub_stage
        monkeypatch.setattr(
            iso_builder.bootloader, "get_backend", lambda _id: fake_backend
        )

        captured: dict[str, object] = {}

        class FakeProc:
            def __init__(self, cmd, **kwargs):
                captured["cmd"] = cmd
                captured["cwd"] = kwargs.get("cwd")
                self.stdout = iter([])

                # Pretend xorriso wrote the file at the resolved location.
                Path(cmd[cmd.index("-o") + 1]).write_bytes(b"FAKE-ISO")

            def wait(self):
                return 0

        monkeypatch.setattr(subprocess, "Popen", FakeProc)

        result = iso_builder.build(project, opts)

        out_arg = captured["cmd"][captured["cmd"].index("-o") + 1]
        assert Path(out_arg).is_absolute()
        assert Path(out_arg) == expected_abs
        assert result.iso_path == expected_abs
        assert expected_abs.is_file()
