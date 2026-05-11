"""Tests for FloppyBootCDApplication._canonicalize().

Lives at the test root (not under tests/ui/) because it's a pure
function test that doesn't need QApplication / qtbot — calling the
static method directly is enough.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from floppybootcd.app import FloppyBootCDApplication


canon = FloppyBootCDApplication._canonicalize


class TestCanonicalize:
    """FloppyImage.path is documented as absolute; the CLI /
    QFileOpenEvent / Explorer-after-association entry points can hand
    in relative paths, so we normalize at the boundary."""

    def test_absolute_path_passes_through(self, tmp_path):
        f = tmp_path / "boot.img"
        f.write_bytes(b"x")
        assert canon(str(f)) == str(f.resolve())

    def test_relative_path_becomes_absolute(self, tmp_path, monkeypatch):
        f = tmp_path / "boot.img"
        f.write_bytes(b"x")
        monkeypatch.chdir(tmp_path)
        result = canon("boot.img")
        assert os.path.isabs(result)
        assert Path(result).resolve() == f.resolve()

    def test_tilde_expanded(self):
        result = canon("~/floppy.img")
        # Must not contain the literal '~' after canonicalization.
        assert "~" not in result
        assert result.startswith(str(Path.home()))

    def test_dotdot_collapsed(self, tmp_path):
        # /tmp/foo/../bar → /tmp/bar (lexical resolve)
        weird = tmp_path / "foo" / ".." / "bar.img"
        result = canon(str(weird))
        assert ".." not in result
        # Either /private/tmp/bar.img on macOS or /tmp/bar.img elsewhere
        assert result.endswith("bar.img")

    def test_nonexistent_path_does_not_raise(self, tmp_path):
        # resolve(strict=False) (3.6+ default) must NOT raise on a
        # path whose tail doesn't exist. The CLI may dispatch a path
        # before the file is created (e.g. "open it on next save").
        target = tmp_path / "does-not-exist.fbcd"
        result = canon(str(target))
        assert result.endswith("does-not-exist.fbcd")

    def test_idempotent(self, tmp_path):
        # Canonicalizing twice should produce the same result.
        f = tmp_path / "x.img"
        f.write_bytes(b"x")
        once = canon(str(f))
        twice = canon(once)
        assert once == twice
