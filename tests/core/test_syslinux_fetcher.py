"""Tests for the syslinux tarball fetcher / extractor."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from floppybootcd.core import syslinux_fetcher
from floppybootcd.core.syslinux_fetcher import (
    REQUIRED_BIOS_FILES,
    clear_cache,
    fetch_syslinux,
    have_syslinux_files,
    syslinux_cache_dir,
    syslinux_tarball_url,
)


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Redirect the cache_dir to a temp path."""
    monkeypatch.setattr(
        syslinux_fetcher, "cache_dir", lambda app_name="FloppyBootCD": tmp_path
    )
    return tmp_path


class TestPaths:
    def test_cache_dir_creates_versioned_subdir(self, isolated_cache):
        d = syslinux_cache_dir("6.03")
        assert d.is_dir()
        assert d.name == "6.03"

    def test_tarball_url_includes_version(self):
        url = syslinux_tarball_url("6.04")
        assert "syslinux-6.04.tar.gz" in url
        assert url.startswith("https://")


class TestHaveSyslinuxFiles:
    def test_false_when_empty(self, isolated_cache):
        assert have_syslinux_files("6.03") is False

    def test_true_when_all_present(self, isolated_cache):
        d = syslinux_cache_dir("6.03")
        for f in REQUIRED_BIOS_FILES:
            (d / f).write_bytes(b"\0")
        assert have_syslinux_files("6.03") is True

    def test_false_when_one_missing(self, isolated_cache):
        d = syslinux_cache_dir("6.03")
        for f in REQUIRED_BIOS_FILES[:-1]:
            (d / f).write_bytes(b"\0")
        assert have_syslinux_files("6.03") is False


def _make_tarball(path: Path, members: dict[str, bytes]) -> None:
    """Build a .tar.gz with the given {member_path: bytes}."""
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            buf = io.BytesIO(data)
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, buf)


class TestFetchSyslinux:
    def test_uses_cache_when_present(self, isolated_cache, monkeypatch):
        """If files are already cached, fetch must not download."""
        d = syslinux_cache_dir("6.03")
        for f in REQUIRED_BIOS_FILES:
            (d / f).write_bytes(b"\0")

        def boom(*args, **kwargs):
            raise AssertionError("Should not download when cached")

        monkeypatch.setattr(syslinux_fetcher.urllib.request, "urlretrieve", boom)
        result = fetch_syslinux("6.03")
        assert result == d

    def test_downloads_and_extracts(self, isolated_cache, monkeypatch):
        d = syslinux_cache_dir("6.03")

        def fake_urlretrieve(url, dest, hook=None):
            members = {
                # The fetcher only uses basenames and skips efi32/efi64
                f"syslinux-6.03/bios/core/{f}": b"BIOS-" + f.encode()
                for f in REQUIRED_BIOS_FILES
            }
            _make_tarball(Path(dest), members)
            if hook:
                hook(1, 1024, 1024)

        monkeypatch.setattr(
            syslinux_fetcher.urllib.request, "urlretrieve", fake_urlretrieve
        )
        result = fetch_syslinux("6.03")
        assert result == d
        for f in REQUIRED_BIOS_FILES:
            assert (d / f).is_file()
            assert (d / f).read_bytes() == b"BIOS-" + f.encode()

    def test_skips_efi_variants(self, isolated_cache, monkeypatch):
        """efi32/efi64 paths must be ignored even when basename matches."""
        d = syslinux_cache_dir("6.03")

        def fake_urlretrieve(url, dest, hook=None):
            members = {}
            # Add EFI variants FIRST so they would win if not filtered
            for f in REQUIRED_BIOS_FILES:
                members[f"syslinux-6.03/efi64/com32/{f}"] = b"EFI-WRONG"
            # Then BIOS variants
            for f in REQUIRED_BIOS_FILES:
                members[f"syslinux-6.03/bios/com32/{f}"] = b"BIOS-OK"
            _make_tarball(Path(dest), members)

        monkeypatch.setattr(
            syslinux_fetcher.urllib.request, "urlretrieve", fake_urlretrieve
        )
        fetch_syslinux("6.03")
        for f in REQUIRED_BIOS_FILES:
            assert (d / f).read_bytes() == b"BIOS-OK", f"EFI variant leaked for {f}"

    def test_missing_files_raises_clear_error(self, isolated_cache, monkeypatch):
        def fake_urlretrieve(url, dest, hook=None):
            # Only put one of the required files in the tarball.
            _make_tarball(Path(dest), {"syslinux-6.03/bios/isolinux.bin": b"x"})

        monkeypatch.setattr(
            syslinux_fetcher.urllib.request, "urlretrieve", fake_urlretrieve
        )
        with pytest.raises(RuntimeError, match="Could not find these files"):
            fetch_syslinux("6.03")

    def test_download_failure_cleans_up_partial_tarball(self, isolated_cache, monkeypatch):
        d = syslinux_cache_dir("6.03")
        partial = d / "syslinux-6.03.tar.gz"

        def failing_urlretrieve(url, dest, hook=None):
            Path(dest).write_bytes(b"partial")
            raise OSError("network down")

        monkeypatch.setattr(
            syslinux_fetcher.urllib.request, "urlretrieve", failing_urlretrieve
        )
        with pytest.raises(RuntimeError, match="Failed to download"):
            fetch_syslinux("6.03")
        assert not partial.exists()

    def test_progress_callback_called(self, isolated_cache, monkeypatch):
        d = syslinux_cache_dir("6.03")
        for f in REQUIRED_BIOS_FILES:
            (d / f).write_bytes(b"\0")

        events = []
        fetch_syslinux("6.03", progress=lambda m, f: events.append((m, f)))
        assert any("cached" in m.lower() for m, _ in events)


class TestClearCache:
    def test_removes_specific_version(self, isolated_cache):
        d = syslinux_cache_dir("6.03")
        (d / "x").write_bytes(b"x")
        clear_cache("6.03")
        assert not d.exists()

    def test_removes_all_versions_when_no_arg(self, isolated_cache):
        d1 = syslinux_cache_dir("6.03")
        d2 = syslinux_cache_dir("6.04")
        (d1 / "x").write_bytes(b"x")
        (d2 / "y").write_bytes(b"y")
        clear_cache()
        assert not d1.exists()
        assert not d2.exists()

    def test_clear_when_nothing_cached_is_noop(self, isolated_cache):
        # Shouldn't raise even when the syslinux dir doesn't exist.
        clear_cache()
        clear_cache("6.03")
