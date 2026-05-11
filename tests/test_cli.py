from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from floppybootcd import cli
from floppybootcd.core.iso_builder import BuildOptions, BuildResult
from floppybootcd.core.project import FloppyImage, Project


def test_main_non_command_args_launch_gui(monkeypatch):
    seen: dict[str, list[str]] = {}

    def fake_launch(args: list[str]) -> int:
        seen["args"] = list(args)
        return 7

    monkeypatch.setattr(cli, "_launch_gui", fake_launch)
    rc = cli.main(["/tmp/example.img"])
    assert rc == 7
    assert seen["args"] == ["/tmp/example.img"]


def test_main_help_alias_returns_zero_and_prints_usage(capsys):
    rc = cli.main(["help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "usage: floppybootcd" in out


def test_main_double_dash_forwards_to_gui(monkeypatch):
    seen: dict[str, list[str]] = {}

    def fake_launch(args: list[str]) -> int:
        seen["args"] = list(args)
        return 9

    monkeypatch.setattr(cli, "_launch_gui", fake_launch)
    rc = cli.main(["--", "./-project.fbcd"])
    assert rc == 9
    assert seen["args"] == ["--", "./-project.fbcd"]


def test_main_parse_error_returns_two(capsys):
    rc = cli.main(["validate"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "the following arguments are required: project" in err


def test_validate_command_reports_problems(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_load_project", lambda _: Project())
    monkeypatch.setattr(cli, "validate_project", lambda _: ["No floppy images added."])
    rc = cli.main(["validate", "sample.fbcd"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "Project validation failed:" in out
    assert "No floppy images added." in out


def test_inspect_json_outputs_machine_readable_summary(monkeypatch, capsys, tmp_path):
    image = tmp_path / "boot.img"
    image.write_bytes(b"abc")
    project = Project(
        title="Demo",
        images=[FloppyImage(path=str(image), label="Boot", default=True)],
    )
    monkeypatch.setattr(cli, "_load_project", lambda _: project)
    rc = cli.main(["inspect", "demo.fbcd", "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["title"] == "Demo"
    assert payload["image_count"] == 1
    assert payload["existing_images"] == 1
    assert payload["default_entry"] == "Boot"


def test_build_command_invokes_builder(monkeypatch, capsys, tmp_path):
    project = Project(title="Build me")
    monkeypatch.setattr(cli, "_load_project", lambda _: project)
    calls: dict[str, object] = {}

    def fake_plugins() -> None:
        calls["plugins"] = True

    def fake_build(
        project: Project,
        options: BuildOptions,
        progress: Any = None,
        log: Any = None,
    ) -> BuildResult:
        calls["project"] = project
        calls["output_path"] = options.output_path
        calls["xorriso"] = options.xorriso_override
        calls["keep_staging"] = options.keep_staging
        assert progress is not None
        assert log is not None
        progress("Build complete.", 1.0)
        log("builder-log")
        return BuildResult(iso_path=options.output_path, staging_path=Path("/tmp/stage"))

    monkeypatch.setattr(cli, "load_plugins", fake_plugins)
    monkeypatch.setattr(cli, "build_iso", fake_build)

    out_iso = tmp_path / "out.iso"
    rc = cli.main(
        [
            "build",
            "demo.fbcd",
            str(out_iso),
            "--xorriso",
            "/usr/bin/xorriso",
            "--keep-staging",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert calls["plugins"] is True
    assert calls["project"] is project
    assert calls["output_path"] == out_iso.resolve()
    assert calls["xorriso"] == "/usr/bin/xorriso"
    assert calls["keep_staging"] is True
    assert "ISO created:" in out


def test_build_command_handles_non_runtime_errors(monkeypatch, capsys):
    project = Project(title="Build me")
    monkeypatch.setattr(cli, "_load_project", lambda _: project)
    monkeypatch.setattr(cli, "load_plugins", lambda: None)

    def boom(*_args, **_kwargs):
        raise ValueError("bad image format")

    monkeypatch.setattr(cli, "build_iso", boom)
    rc = cli.main(["build", "demo.fbcd", "out.iso"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "bad image format" in err
