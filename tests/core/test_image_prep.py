"""Tests for the image_prep helpers (extension constants and .imz handling)."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from floppybootcd.core import image_prep


# ── Extension constants ─────────────────────────────────────────────────────

class TestExtensionSets:
    def test_floppy_exts_are_raw_image_extensions(self):
        assert image_prep.FLOPPY_EXTS == frozenset(
            {".img", ".ima", ".vfd", ".flp"}
        )

    def test_compressed_exts_contains_imz(self):
        assert ".imz" in image_prep.COMPRESSED_EXTS

    def test_all_accepted_is_union(self):
        assert image_prep.ALL_ACCEPTED_EXTS == (
            image_prep.FLOPPY_EXTS | image_prep.COMPRESSED_EXTS
        )

    def test_compressed_and_floppy_disjoint(self):
        assert not (image_prep.FLOPPY_EXTS & image_prep.COMPRESSED_EXTS)


# ── is_compressed / staged_filename ─────────────────────────────────────────

class TestIsCompressed:
    @pytest.mark.parametrize("name", ["a.imz", "a.IMZ", "a.Imz"])
    def test_imz_case_insensitive(self, name):
        assert image_prep.is_compressed(name)

    @pytest.mark.parametrize("name", ["a.img", "a.ima", "a.vfd", "a.flp", "a.zip"])
    def test_non_imz_is_not_compressed(self, name):
        assert not image_prep.is_compressed(name)


class TestStagedFilename:
    def test_imz_renamed_to_ima(self):
        assert image_prep.staged_filename("MSDOS622.imz") == "MSDOS622.ima"

    def test_imz_uppercase_renamed_to_ima(self):
        assert image_prep.staged_filename("DISK.IMZ") == "DISK.ima"

    @pytest.mark.parametrize("name", ["disk.img", "boot.ima", "x.vfd", "y.flp"])
    def test_raw_unchanged(self, name):
        assert image_prep.staged_filename(name) == name


# ── Test fixtures ───────────────────────────────────────────────────────────

INNER_BYTES = b"\x55\xaa" + b"FAKE BPB DATA " * 200  # ~2.7 KB of fake floppy


def _make_imz(path: Path, inner_name: str = "floppy.ima",
              inner_bytes: bytes = INNER_BYTES) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(inner_name, inner_bytes)
    return path


# ── stage_image ─────────────────────────────────────────────────────────────

class TestStageImageRaw:
    def test_raw_ima_round_trips(self, tmp_path):
        src = tmp_path / "in.ima"
        src.write_bytes(b"raw floppy bytes")
        dest = tmp_path / "out"
        dest.mkdir()
        image_prep.stage_image(src, dest, "in.ima")
        assert (dest / "in.ima").read_bytes() == b"raw floppy bytes"

    def test_raw_img_round_trips(self, tmp_path):
        src = tmp_path / "x.img"
        src.write_bytes(b"\x00" * 1440 * 1024)
        dest = tmp_path / "out"
        dest.mkdir()
        image_prep.stage_image(src, dest, "x.img")
        assert (dest / "x.img").stat().st_size == 1440 * 1024


class TestStageImageImz:
    def test_extracts_inner_image(self, tmp_path):
        src = _make_imz(tmp_path / "boot.imz")
        dest = tmp_path / "out"
        dest.mkdir()
        image_prep.stage_image(src, dest, "boot.ima")
        assert (dest / "boot.ima").read_bytes() == INNER_BYTES

    def test_picks_largest_member_when_multiple(self, tmp_path):
        path = tmp_path / "multi.imz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("readme.ima", b"short")
            zf.writestr("real.ima", INNER_BYTES)
        dest = tmp_path / "out"
        dest.mkdir()
        image_prep.stage_image(path, dest, "multi.ima")
        assert (dest / "multi.ima").read_bytes() == INNER_BYTES

    def test_non_zip_imz_raises_with_user_facing_message(self, tmp_path):
        src = tmp_path / "junk.imz"
        src.write_bytes(b"not a zip at all")
        dest = tmp_path / "out"
        dest.mkdir()
        with pytest.raises(ValueError, match="not a ZIP-format .imz"):
            image_prep.stage_image(src, dest, "junk.ima")

    def test_zip_without_floppy_member_raises(self, tmp_path):
        src = tmp_path / "wrong.imz"
        with zipfile.ZipFile(src, "w") as zf:
            zf.writestr("readme.txt", b"hello")
        dest = tmp_path / "out"
        dest.mkdir()
        with pytest.raises(ValueError, match="no floppy image"):
            image_prep.stage_image(src, dest, "wrong.ima")


# ── probe_uncompressed_size ─────────────────────────────────────────────────

class TestProbeUncompressedSize:
    def test_raw_returns_filesystem_size(self, tmp_path):
        src = tmp_path / "a.img"
        src.write_bytes(b"x" * 1234)
        assert image_prep.probe_uncompressed_size(src) == 1234

    def test_imz_returns_inner_member_size(self, tmp_path):
        src = _make_imz(tmp_path / "b.imz")
        assert image_prep.probe_uncompressed_size(src) == len(INNER_BYTES)

    def test_missing_file_returns_zero(self, tmp_path):
        assert image_prep.probe_uncompressed_size(tmp_path / "nope.img") == 0

    def test_corrupt_imz_returns_zero(self, tmp_path):
        src = tmp_path / "bad.imz"
        src.write_bytes(b"definitely not zip")
        assert image_prep.probe_uncompressed_size(src) == 0

    def test_imz_without_floppy_member_returns_zero(self, tmp_path):
        src = tmp_path / "empty.imz"
        with zipfile.ZipFile(src, "w") as zf:
            zf.writestr("readme.txt", b"hello")
        assert image_prep.probe_uncompressed_size(src) == 0
