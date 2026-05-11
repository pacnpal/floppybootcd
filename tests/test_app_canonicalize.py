"""Tests for FloppyBootCDApplication._canonicalize() and _parse_cli_paths().

Lives at the test root (not under tests/ui/) because it's a pure
function test that doesn't need QApplication / qtbot — calling the
static method directly is enough.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from floppybootcd.app import FloppyBootCDApplication, _parse_cli_paths


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
        a = tmp_path / "a.img"
        a.write_bytes(b"")
        b = tmp_path / "b.imz"
        b.write_bytes(b"")
        c = tmp_path / "c.vfd"
        c.write_bytes(b"")
        stub, calls = self._make_stub()
        stub._dispatch_batch([str(a), str(b), str(c)])
        # All three dispatched in order.
        assert calls == [str(a.resolve()), str(b.resolve()), str(c.resolve())]

    def test_fbcd_in_batch_wins_and_ignores_rest(self, tmp_path):
        # If even one .fbcd is in the batch, it should be dispatched
        # alone — opening it replaces the project, so adding the
        # other paths first would just dirty a project the user
        # never asked to create.
        img = tmp_path / "boot.img"
        img.write_bytes(b"")
        proj = tmp_path / "p.fbcd"
        proj.write_bytes(b"{}")
        other = tmp_path / "more.img"
        other.write_bytes(b"")
        stub, calls = self._make_stub()
        stub._dispatch_batch([str(img), str(proj), str(other)])
        # Only the .fbcd is dispatched.
        assert calls == [str(proj.resolve())]

    def test_fbcd_anywhere_in_batch_wins(self, tmp_path):
        # The .fbcd is the LAST entry — still wins.
        img = tmp_path / "first.img"
        img.write_bytes(b"")
        proj = tmp_path / "last.fbcd"
        proj.write_bytes(b"{}")
        stub, calls = self._make_stub()
        stub._dispatch_batch([str(img), str(proj)])
        assert calls == [str(proj.resolve())]

    def test_first_fbcd_wins_when_multiple_present(self, tmp_path):
        # Two .fbcd → only the first one (in argv order) opens.
        # Opening multiple projects sequentially would prompt the
        # user to save between each; pick one and let the user
        # File→Open the others if they want.
        a = tmp_path / "first.fbcd"
        a.write_bytes(b"{}")
        b = tmp_path / "second.fbcd"
        b.write_bytes(b"{}")
        stub, calls = self._make_stub()
        stub._dispatch_batch([str(a), str(b)])
        assert calls == [str(a.resolve())]

    def test_empty_batch_no_dispatch(self):
        stub, calls = self._make_stub()
        stub._dispatch_batch([])
        assert calls == []

    def test_missing_fbcd_still_dispatches_to_project_path(self, tmp_path):
        """Regression: routing on ``is_file() AND suffix == .fbcd``
        meant ``floppybootcd missing.fbcd`` silently no-op'd — the
        path isn't a file, so the batch pre-scan fell through to the
        generic image-walk branch, which finds nothing. Users got an
        empty Untitled window with no clue that their path was wrong.

        Suffix-only routing hands the path straight to
        ``_dispatch_canonical`` (and thence to ``open_project_path``),
        which surfaces the underlying ``FileNotFoundError`` via the
        "Open failed" dialog."""
        missing = tmp_path / "nope.fbcd"
        # File deliberately not written.
        stub, calls = self._make_stub()
        stub._dispatch_batch([str(missing)])
        # Still dispatched (canonicalized) — the actual file-not-found
        # error is surfaced downstream by open_project_path.
        assert calls == [str(missing.resolve())]


class TestDispatchCanonical:
    """``_dispatch_canonical`` is the single funnel every entry point
    (CLI argv, QFileOpenEvent, set_main_window flush) reaches via
    ``_dispatch_batch``. Its routing rule changed from "is_file() AND
    suffix" to "suffix only" so missing .fbcd paths surface an error
    instead of silently no-op'ing through the walk-images branch."""

    def _make_stub_with_win(self):
        opened: list[str] = []
        added: list[list[str]] = []

        class FakeWin:
            def open_project_path(self, p):
                opened.append(p)

            def add_paths(self, ps):
                added.append(list(ps))

        class Stub:
            _canonicalize = staticmethod(FloppyBootCDApplication._canonicalize)
            _pending_open_paths: list[str] = []
            _main_window = FakeWin()

        Stub._dispatch_canonical = FloppyBootCDApplication._dispatch_canonical
        return Stub(), opened, added

    def test_missing_fbcd_routes_to_open_project_path(self, tmp_path):
        """A canonical .fbcd path that doesn't exist on disk still goes
        to open_project_path so the user sees an error dialog rather
        than a silent no-op."""
        missing = tmp_path / "ghost.fbcd"
        stub, opened, added = self._make_stub_with_win()
        stub._dispatch_canonical(str(missing))
        assert opened == [str(missing)]
        assert added == []

    def test_existing_fbcd_routes_to_open_project_path(self, tmp_path):
        proj = tmp_path / "real.fbcd"
        proj.write_bytes(b"{}")
        stub, opened, added = self._make_stub_with_win()
        stub._dispatch_canonical(str(proj))
        assert opened == [str(proj)]
        assert added == []


class TestParseCliPaths:
    """_parse_cli_paths filters sys.argv[1:] into the list of paths to
    dispatch. Key rules:
      - Empty strings are dropped (Path("") resolves to CWD).
      - Args starting with '-' before '--' are treated as flags and dropped.
        Note: Qt strips its own paired flags (e.g. -platform xcb) from
        sys.argv during QApplication.__init__, so in practice only
        unpaired OS-injected flags (like macOS's -psn_*) remain.
      - '--' is the POSIX end-of-options terminator: everything after it
        is treated as a path, even if it starts with '-'.
    """

    def test_normal_paths_pass_through(self):
        assert _parse_cli_paths(["/tmp/a.img", "/tmp/b.fbcd"]) == [
            "/tmp/a.img",
            "/tmp/b.fbcd",
        ]

    def test_empty_string_filtered_out(self):
        assert _parse_cli_paths([""]) == []

    def test_dash_prefixed_flags_filtered_out(self):
        # Only the flag itself ('-psn_*') is filtered; Qt removes paired
        # flags like '-platform xcb' itself before main() runs.
        assert _parse_cli_paths(["-psn_0_12345", "/tmp/a.img"]) == ["/tmp/a.img"]

    def test_dash_dash_separator_paths_pass_through(self):
        # Paths starting with '-' can be passed after '--'.
        assert _parse_cli_paths(["--", "./-project.fbcd"]) == ["./-project.fbcd"]

    def test_flags_before_separator_filtered_paths_after(self):
        # '-psn_*' before '--' is filtered; '-dash.img' after '--' passes through.
        result = _parse_cli_paths(["-psn_0_1", "--", "-dash.img", "boot.img"])
        assert result == ["-dash.img", "boot.img"]

    def test_empty_string_after_separator_filtered(self):
        # Empty strings after '--' are still filtered: an empty string passed
        # to _canonicalize() resolves to CWD, which would trigger an
        # unintended whole-directory walk.
        result = _parse_cli_paths(["--", ""])
        assert result == []

    def test_nonempty_path_after_separator_kept(self):
        # Non-empty paths after '--' that start with '-' are kept intact.
        result = _parse_cli_paths(["--", "-dash.fbcd"])
        assert result == ["-dash.fbcd"]

    def test_no_args_returns_empty(self):
        assert _parse_cli_paths([]) == []

    def test_only_separator_returns_empty(self):
        assert _parse_cli_paths(["--"]) == []

    def test_psn_flag_filtered(self):
        # macOS passes -psn_* to every GUI app; it must not be dispatched.
        assert _parse_cli_paths(["-psn_0_12345", "/tmp/x.img"]) == ["/tmp/x.img"]

    def test_mixed_order_preserved(self):
        # Pre- and post-'--' paths are returned in original left-to-right
        # order, not reordered (post-'--' first).
        assert _parse_cli_paths(["foo.img", "--", "bar.img"]) == ["foo.img", "bar.img"]
