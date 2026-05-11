"""Command-line interface for FloppyBootCD."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import APP_NAME, __version__
from .core.image_prep import CD_USABLE_BYTES, total_disc_payload
from .core.iso_builder import BuildOptions, BuildResult, build as build_iso, validate_project
from .core.plugins import load_plugins
from .core.project import Project

_COMMANDS = {"gui", "validate", "inspect", "build", "help"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="floppybootcd",
        description="FloppyBootCD command-line interface",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command")

    gui = sub.add_parser(
        "gui",
        help="Launch the GUI and optionally open paths",
    )
    gui.add_argument("paths", nargs="*", help="Optional .fbcd/image/folder paths")

    validate = sub.add_parser(
        "validate",
        help="Validate a .fbcd project file",
    )
    validate.add_argument("project", help="Path to .fbcd project")

    inspect = sub.add_parser(
        "inspect",
        help="Show project metadata",
    )
    inspect.add_argument("project", help="Path to .fbcd project")
    inspect.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )

    build = sub.add_parser(
        "build",
        help="Build an ISO from a .fbcd project",
    )
    build.add_argument("project", help="Path to .fbcd project")
    build.add_argument("output", help="Output ISO path")
    build.add_argument(
        "--xorriso",
        default="",
        help="Override xorriso executable path",
    )
    build.add_argument(
        "--keep-staging",
        action="store_true",
        help="Keep temporary staging directory for debugging",
    )
    return parser


def _load_project(path: str) -> Project | None:
    project_path = Path(path).expanduser().resolve(strict=False)
    try:
        return Project.load(project_path)
    except Exception as exc:
        print(f"Failed to load project '{project_path}': {exc}", file=sys.stderr)
        return None


def _launch_gui(args: list[str]) -> int:
    from .app import main as app_main
    return app_main(["floppybootcd", *args])


def _run_validate(path: str) -> int:
    project = _load_project(path)
    if project is None:
        return 1
    problems = validate_project(project)
    if not problems:
        print("Project validation passed.")
        return 0
    print("Project validation failed:")
    for p in problems:
        print(f"- {p}")
    return 2


def _project_summary(project: Project) -> dict[str, Any]:
    existing = [img for img in project.images if Path(img.path).is_file()]
    missing = [img for img in project.images if not Path(img.path).is_file()]
    default = next((img.display_label for img in project.images if img.default), "")
    payload = total_disc_payload(
        (img.path for img in existing),
        vesa_background=project.background_image if project.menu_style == "vesa" else None,
    )
    return {
        "title": project.title,
        "bootloader": project.bootloader,
        "menu_style": project.menu_style,
        "timeout_secs": project.timeout_secs,
        "image_count": len(project.images),
        "default_entry": default,
        "existing_images": len(existing),
        "missing_images": len(missing),
        "payload_bytes": payload,
        "payload_mib": round(payload / (1024 * 1024), 1),
        "cd_usable_mib": round(CD_USABLE_BYTES / (1024 * 1024), 1),
    }


def _run_inspect(path: str, as_json: bool) -> int:
    project = _load_project(path)
    if project is None:
        return 1
    summary = _project_summary(project)
    if as_json:
        print(json.dumps(summary, indent=2))
        return 0
    print(f"Title: {summary['title']}")
    print(f"Bootloader: {summary['bootloader']}")
    print(f"Menu style: {summary['menu_style']}")
    print(f"Timeout: {summary['timeout_secs']}s")
    print(f"Images: {summary['image_count']} ({summary['existing_images']} existing, {summary['missing_images']} missing)")
    print(f"Default entry: {summary['default_entry'] or '(none)'}")
    print(
        f"Payload: {summary['payload_mib']} MiB / {summary['cd_usable_mib']} MiB usable CD budget"
    )
    return 0


def _run_build(path: str, output: str, xorriso: str, keep_staging: bool) -> int:
    project = _load_project(path)
    if project is None:
        return 1
    load_plugins()
    output_path = Path(output).expanduser().resolve(strict=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    options = BuildOptions(
        output_path=output_path,
        xorriso_override=xorriso,
        keep_staging=keep_staging,
    )

    def _progress(msg: str, percent: float) -> None:
        # iso_builder uses negative values when no numeric percentage is available.
        if percent < 0:
            print(msg)
        else:
            print(f"[{percent * 100:5.1f}%] {msg}")

    try:
        result: BuildResult = build_iso(project, options, progress=_progress, log=print)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"ISO created: {result.iso_path}")
    if result.staging_path is not None:
        print(f"Staging directory kept: {result.staging_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return _launch_gui(args)

    first = args[0]
    if first == "--":
        return _launch_gui(args)
    should_parse = first in _COMMANDS or first.startswith("-")
    if not should_parse:
        return _launch_gui(args)

    parser = _build_parser()
    if first == "help":
        args = ["--help"]
    try:
        ns = parser.parse_args(args)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1

    if ns.command in (None, "gui"):
        return _launch_gui(getattr(ns, "paths", []))
    if ns.command == "validate":
        return _run_validate(ns.project)
    if ns.command == "inspect":
        return _run_inspect(ns.project, ns.json)
    if ns.command == "build":
        return _run_build(ns.project, ns.output, ns.xorriso, ns.keep_staging)
    parser.print_help()
    return 0
