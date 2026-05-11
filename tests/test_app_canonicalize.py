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


class TestDispatchBatch:
    """_dispatch_batch is the entry point used by both the CLI argv
    loop and the QFileOpenEvent flush. Tested here via a duck-typed
    stub because creating a real FloppyBootCDApplication would
    instantiate a second QApplication in the test process (Qt
    forbids two)."""

    def _make_stub(self):
        """Return a stub that captures _dispatch_canonical calls;
        binds the real _dispatch_batch implementation. We capture
        _dispatch_canonical (not _dispatch) because _dispatch_batch
        canonicalizes once up front and feeds the canonical form
        straight to _dispatch_canonical — that's the contract we
        want to lock in."""
        calls: list[str] = []

        class Stub:
            _canonicalize = staticmethod(FloppyBootCDApplication._canonicalize)

            def _dispatch_canonical(self, path: str) -> None:
                calls.append(path)

        Stub._dispatch_batch = FloppyBootCDApplication._dispatch_batch
        return Stub(), calls

    def test_no_fbcd_dispatches_every_path(self, tmp_path):
        a = tmp_path / "a.img"; a.write_bytes(b"")
        b = tmp_path / "b.imz"; b.write_bytes(b"")
        c = tmp_path / "c.vfd"; c.write_bytes(b"")
        stub, calls = self._make_stub()
        stub._dispatch_batch([str(a), str(b), str(c)])
        # All three dispatched in order.
        assert calls == [str(a.resolve()), str(b.resolve()), str(c.resolve())]

    def test_fbcd_in_batch_wins_and_ignores_rest(self, tmp_path):
        # If even one .fbcd is in the batch, it should be dispatched
        # alone — opening it replaces the project, so adding the
        # other paths first would just dirty a project the user
        # never asked to create.
        img = tmp_path / "boot.img"; img.write_bytes(b"")
        proj = tmp_path / "p.fbcd"; proj.write_bytes(b"{}")
        other = tmp_path / "more.img"; other.write_bytes(b"")
        stub, calls = self._make_stub()
        stub._dispatch_batch([str(img), str(proj), str(other)])
        # Only the .fbcd is dispatched.
        assert calls == [str(proj.resolve())]

    def test_fbcd_anywhere_in_batch_wins(self, tmp_path):
        # The .fbcd is the LAST entry — still wins.
        img = tmp_path / "first.img"; img.write_bytes(b"")
        proj = tmp_path / "last.fbcd"; proj.write_bytes(b"{}")
        stub, calls = self._make_stub()
        stub._dispatch_batch([str(img), str(proj)])
        assert calls == [str(proj.resolve())]

    def test_first_fbcd_wins_when_multiple_present(self, tmp_path):
        # Two .fbcd → only the first one (in argv order) opens.
        # Opening multiple projects sequentially would prompt the
        # user to save between each; pick one and let the user
        # File→Open the others if they want.
        a = tmp_path / "first.fbcd"; a.write_bytes(b"{}")
        b = tmp_path / "second.fbcd"; b.write_bytes(b"{}")
        stub, calls = self._make_stub()
        stub._dispatch_batch([str(a), str(b)])
        assert calls == [str(a.resolve())]

    def test_empty_batch_no_dispatch(self):
        stub, calls = self._make_stub()
        stub._dispatch_batch([])
        assert calls == []
