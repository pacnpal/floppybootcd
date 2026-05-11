from __future__ import annotations

from floppybootcd.classic_app import _parse_cli_paths, resolve_input_paths


def test_parse_cli_paths_filters_flags_like_qt_variant():
    assert _parse_cli_paths(["-psn_0_1", "disk.img"]) == ["disk.img"]


def test_parse_cli_paths_respects_dash_dash_separator():
    assert _parse_cli_paths(["--", "-dash.img", "ok.img"]) == ["-dash.img", "ok.img"]


def test_resolve_input_paths_project_wins(tmp_path):
    img = tmp_path / "boot.img"
    img.write_bytes(b"x")
    proj = tmp_path / "project.fbcd"
    proj.write_text("{}", encoding="utf-8")

    project_path, images = resolve_input_paths([str(img), str(proj)])

    assert project_path == str(proj.resolve())
    assert images == []


def test_resolve_input_paths_collects_and_dedups_images(tmp_path):
    disk1 = tmp_path / "a.img"
    disk1.write_bytes(b"x")
    disk2 = tmp_path / "b.ima"
    disk2.write_bytes(b"y")

    project_path, images = resolve_input_paths([
        str(disk1),
        str(tmp_path),
        str(disk1),
    ])

    assert project_path is None
    assert images == [str(disk1.resolve()), str(disk2.resolve())]
