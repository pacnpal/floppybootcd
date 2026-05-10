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

    def test_spaces_replaced_with_underscores(self):
        # SYSLINUX APPEND parses on whitespace; a space in the on-disc
        # filename truncates the path and MEMDISK can't find the image.
        # See bug report: "Acronis OS Selector SE.img" failed to boot.
        assert image_prep.staged_filename("Acronis OS Selector SE.img") \
            == "Acronis_OS_Selector_SE.img"

    def test_imz_spaces_replaced(self):
        assert image_prep.staged_filename("My Old Boot Disk.imz") \
            == "My_Old_Boot_Disk.ima"

    @pytest.mark.parametrize("name,expected", [
        ("a#b.img", "a_b.img"),       # # is a SYSLINUX comment marker
        ("a;b.img", "a_b.img"),       # ; / , can confuse some loaders
        ("a,b.img", "a_b.img"),
        ("a\tb.img", "a_b.img"),      # tabs are whitespace too
        ("a   b.img", "a_b.img"),     # collapse runs
        ("__a__b__.img", "a_b.img"),  # trim/collapse underscores
    ])
    def test_unsafe_chars_sanitized(self, name, expected):
        assert image_prep.staged_filename(name) == expected

    def test_extension_preserved_case(self):
        assert image_prep.staged_filename("BOOT.IMG") == "BOOT.IMG"


class TestWalkFloppyImages:
    """Drag-drop folder recursion: walk_floppy_images() flattens a
    dropped path into a deduped, deterministic list of floppy-ext
    file paths."""

    def test_single_file_returned_as_one_element_list(self, tmp_path):
        f = tmp_path / "boot.img"
        f.write_bytes(b"")
        assert image_prep.walk_floppy_images(f) == [str(f)]

    def test_single_file_with_unknown_ext_returns_empty(self, tmp_path):
        f = tmp_path / "boot.txt"
        f.write_bytes(b"")
        assert image_prep.walk_floppy_images(f) == []

    def test_folder_recursed_for_floppy_images(self, tmp_path):
        # tmp_path/
        #   a.img
        #   nested/
        #     b.ima
        #     c.imz
        #     deep/d.vfd
        (tmp_path / "a.img").write_bytes(b"")
        nested = tmp_path / "nested"
        nested.mkdir()
        (nested / "b.ima").write_bytes(b"")
        (nested / "c.imz").write_bytes(b"")
        deep = nested / "deep"
        deep.mkdir()
        (deep / "d.vfd").write_bytes(b"")
        # Unrelated files
        (tmp_path / "readme.txt").write_bytes(b"")
        (nested / "thumbs.db").write_bytes(b"")

        found = image_prep.walk_floppy_images(tmp_path)
        names = [Path(p).name for p in found]
        assert sorted(names) == ["a.img", "b.ima", "c.imz", "d.vfd"]

    def test_folder_skips_hidden_files_and_dirs(self, tmp_path):
        (tmp_path / ".hidden.img").write_bytes(b"")
        (tmp_path / "good.img").write_bytes(b"")
        hidden_dir = tmp_path / ".cache"
        hidden_dir.mkdir()
        (hidden_dir / "evicted.img").write_bytes(b"")

        found = image_prep.walk_floppy_images(tmp_path)
        names = [Path(p).name for p in found]
        assert names == ["good.img"]

    def test_folder_skips_apple_double_and_recycle_dirs(self, tmp_path):
        (tmp_path / "real.img").write_bytes(b"")
        for trash in (".AppleDouble", "$RECYCLE.BIN", "System Volume Information"):
            d = tmp_path / trash
            d.mkdir()
            (d / "evicted.img").write_bytes(b"")
        found = image_prep.walk_floppy_images(tmp_path)
        names = [Path(p).name for p in found]
        assert names == ["real.img"]

    def test_nonexistent_path_returns_empty(self, tmp_path):
        assert image_prep.walk_floppy_images(tmp_path / "missing") == []

    def test_results_are_sorted_deterministic(self, tmp_path):
        # Add files in reverse alpha order; expect sorted output back.
        for name in ("z.img", "y.img", "a.img", "m.img"):
            (tmp_path / name).write_bytes(b"")
        found = image_prep.walk_floppy_images(tmp_path)
        names = [Path(p).name for p in found]
        assert names == sorted(names)

    def test_recursion_depth_limit_truncates(self, tmp_path):
        """Folders deeper than _DROP_RECURSION_LIMIT are not descended
        into — a wrong-folder drop on a deep tree (e.g. ~/) doesn't
        spend minutes walking the entire filesystem."""
        # One image at every depth from 0 up to limit + 3.
        limit = image_prep._DROP_RECURSION_LIMIT
        cur = tmp_path
        for d in range(limit + 4):
            (cur / f"at-depth-{d}.img").write_bytes(b"")
            sub = cur / f"d{d}"
            sub.mkdir()
            cur = sub
        # The leaf gets one more file too, so we have a file at
        # depth = limit + 4 — definitively past the cap.
        (cur / "way-too-deep.img").write_bytes(b"")

        found = image_prep.walk_floppy_images(tmp_path)
        depths_found = sorted({int(Path(p).name.split("-")[2].split(".")[0])
                               for p in found if Path(p).name.startswith("at-depth-")})
        # Everything at depth 0..limit must be in the result; anything
        # past the cap must NOT be.
        assert depths_found == list(range(limit + 1))
        assert not any("way-too-deep" in p for p in found)

    def test_file_cap_truncates(self, tmp_path, monkeypatch):
        """A drop can pull at most _DROP_FILE_LIMIT files in. Lower the
        cap so the test stays fast; the real cap (1024) lives in the
        module constant."""
        monkeypatch.setattr(image_prep, "_DROP_FILE_LIMIT", 5)
        for i in range(20):
            (tmp_path / f"f{i:02d}.img").write_bytes(b"")
        found = image_prep.walk_floppy_images(tmp_path)
        assert len(found) == 5


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

    def test_encrypted_imz_returns_zero(self, tmp_path):
        # Build a normal archive then hex-patch the encryption flag
        # in both headers (stdlib zipfile resets flag_bits on writestr,
        # so we have to set them after the fact). probe_uncompressed_size
        # must report 0 for encrypted members so the UI flags them as
        # invalid rather than displaying the central-directory size.
        src = tmp_path / "encrypted.imz"
        with zipfile.ZipFile(src, "w") as zf:
            zf.writestr("inner.ima", b"\0" * 32)
        raw = bytearray(src.read_bytes())
        raw[raw.index(b"PK\x03\x04") + 6] |= 0x01  # local file header flag
        raw[raw.index(b"PK\x01\x02") + 8] |= 0x01  # central directory flag
        src.write_bytes(bytes(raw))
        assert image_prep.probe_uncompressed_size(src) == 0

    def test_imz_without_floppy_member_returns_zero(self, tmp_path):
        src = tmp_path / "empty.imz"
        with zipfile.ZipFile(src, "w") as zf:
            zf.writestr("readme.txt", b"hello")
        assert image_prep.probe_uncompressed_size(src) == 0


# ── total_payload_size ──────────────────────────────────────────────────────

class TestTotalPayloadSize:
    def test_empty_iterable_returns_zero(self):
        assert image_prep.total_payload_size([]) == 0

    def test_sums_raw_image_sizes(self, tmp_path):
        a = tmp_path / "a.img"
        b = tmp_path / "b.img"
        a.write_bytes(b"x" * 1000)
        b.write_bytes(b"y" * 2500)
        assert image_prep.total_payload_size([a, b]) == 3500

    def test_uses_inner_size_for_imz(self, tmp_path):
        # Tiny-on-disk archive with a relatively large inner image.
        src = tmp_path / "boot.imz"
        with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("inner.ima", b"\0" * 1440 * 1024)
        # Sanity: archive much smaller than inner.
        assert src.stat().st_size < 100 * 1024
        assert image_prep.total_payload_size([src]) == 1440 * 1024

    def test_mixes_raw_and_imz(self, tmp_path):
        raw = tmp_path / "a.img"
        raw.write_bytes(b"\0" * 1024)
        imz = tmp_path / "b.imz"
        with zipfile.ZipFile(imz, "w") as zf:
            zf.writestr("b.ima", b"\0" * 4096)
        assert image_prep.total_payload_size([raw, imz]) == 1024 + 4096

    def test_missing_files_contribute_zero(self, tmp_path):
        ok = tmp_path / "ok.img"
        ok.write_bytes(b"\0" * 500)
        assert image_prep.total_payload_size(
            [ok, tmp_path / "missing.img"]
        ) == 500


class TestCdCapacityConstants:
    def test_cd_r_capacity_is_700_mib(self):
        assert image_prep.CD_R_CAPACITY_BYTES == 700 * 1024 * 1024

    def test_overhead_is_subtracted_from_usable(self):
        assert image_prep.CD_USABLE_BYTES == (
            image_prep.CD_R_CAPACITY_BYTES - image_prep.CD_OVERHEAD_BYTES
        )

    def test_usable_is_positive_and_below_total(self):
        assert 0 < image_prep.CD_USABLE_BYTES < image_prep.CD_R_CAPACITY_BYTES


class TestTotalDiscPayload:
    """The single source of truth for the disc-budget calculation."""

    def test_no_background_matches_total_payload_size(self, tmp_path):
        a = tmp_path / "a.img"
        b = tmp_path / "b.img"
        a.write_bytes(b"\0" * 1024)
        b.write_bytes(b"\0" * 4096)
        # vesa_background=None must yield the floppy-only sum.
        assert image_prep.total_disc_payload([a, b]) == 5120

    def test_vesa_background_added_to_total(self, tmp_path):
        a = tmp_path / "a.img"
        a.write_bytes(b"\0" * 1024)
        bg = tmp_path / "bg.png"
        bg.write_bytes(b"\0" * 2048)
        assert image_prep.total_disc_payload(
            [a], vesa_background=bg
        ) == 1024 + 2048

    def test_missing_background_silently_skipped(self, tmp_path):
        a = tmp_path / "a.img"
        a.write_bytes(b"\0" * 1024)
        assert image_prep.total_disc_payload(
            [a], vesa_background=tmp_path / "no-such.png"
        ) == 1024

    def test_imz_inner_size_counts_in_disc_payload(self, tmp_path):
        src = _make_imz(tmp_path / "boot.imz")
        assert image_prep.total_disc_payload([src]) == len(INNER_BYTES)


class TestVerifyImzReadable:
    """End-to-end inner-stream validation, not just the central directory."""

    def test_valid_imz_returns_inner_size(self, tmp_path):
        src = _make_imz(tmp_path / "ok.imz")
        err, size = image_prep.verify_imz_readable(src)
        assert err is None
        assert size == len(INNER_BYTES)

    def test_truncated_imz_detected(self, tmp_path):
        # Build a valid .imz, then chop trailing bytes off the
        # compressed stream so a full decompression fails. We keep
        # the central directory + EOCD intact (last ~80 bytes) so
        # zipfile's structural check at open time still passes.
        src = tmp_path / "truncated.imz"
        with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("inner.ima", INNER_BYTES)
        raw = src.read_bytes()
        # Drop bytes from the middle of the compressed payload (after
        # the local file header signature, before the central
        # directory) by truncating just before the central directory.
        cdh = raw.index(b"PK\x01\x02")
        truncated = raw[: cdh - 16] + raw[cdh:]  # remove 16 payload bytes
        src.write_bytes(truncated)
        err, size = image_prep.verify_imz_readable(src)
        assert err is not None
        assert size == 0

    def test_filename_prefix_stripped_from_messages(self, tmp_path):
        src = tmp_path / "broken.imz"
        src.write_bytes(b"this is not a zip")
        err, size = image_prep.verify_imz_readable(src)
        assert err is not None
        # The message must NOT start with "broken.imz: " — callers add
        # their own context.
        assert not err.startswith("broken.imz")
        assert size == 0

    def test_empty_inner_member_rejected(self, tmp_path):
        src = tmp_path / "empty_inner.imz"
        with zipfile.ZipFile(src, "w") as zf:
            zf.writestr("inner.ima", b"")
        err, size = image_prep.verify_imz_readable(src)
        assert err is not None
        assert "empty" in err.lower()
        assert size == 0
