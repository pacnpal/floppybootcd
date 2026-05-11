"""Classic compatibility UI based on Tkinter.

This frontend intentionally favors broad runtime compatibility and a
minimal dependency footprint over feature parity with the Qt UI.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Sequence

from . import APP_NAME
from .core.image_prep import ALL_ACCEPTED_EXTS, normalize_for_dedup, walk_floppy_images
from .core.iso_builder import BuildOptions, build, validate_project
from .core.plugins import load_plugins
from .core.project import FloppyImage, PROJECT_EXT, Project

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except ModuleNotFoundError:  # pragma: no cover - platform packaging issue
    tk = None
    filedialog = None
    messagebox = None


def _canonicalize(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve(strict=False))


def _parse_cli_paths(argv: Sequence[str]) -> list[str]:
    """Filter argv with POSIX `--` semantics (same behavior as Qt app)."""
    result: list[str] = []
    past_sep = False
    for a in argv:
        if not past_sep and a == "--":
            past_sep = True
        elif past_sep:
            if a:
                result.append(a)
        elif a and not a.startswith("-"):
            result.append(a)
    return result


def resolve_input_paths(paths: Sequence[str]) -> tuple[str | None, list[str]]:
    """Resolve startup paths into either a project load or image-add batch.

    If any .fbcd path appears, only the first one is returned (project-wins
    semantics), and any subsequent .fbcd paths in the same batch are ignored.
    Otherwise, all discovered floppy image paths are returned, deduplicated
    in left-to-right order.
    """
    canonical = [_canonicalize(p) for p in paths]
    for cp in canonical:
        if Path(cp).suffix.lower() == PROJECT_EXT:
            return cp, []

    images: list[str] = []
    seen: set[str] = set()
    for cp in canonical:
        found = walk_floppy_images(cp)
        for raw in found:
            norm = normalize_for_dedup(raw)
            if norm in seen:
                continue
            seen.add(norm)
            images.append(_canonicalize(raw))
    return None, images


def _accepted_file_dialog_pattern() -> str:
    return " ".join(f"*{ext}" for ext in sorted(ALL_ACCEPTED_EXTS))


class ClassicMainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} (Classic)")
        self.root.geometry("760x520")

        self.project = Project()
        self.project_path: Path | None = None

        self._title_var = tk.StringVar(value=self.project.title)
        self._status_var = tk.StringVar(value="Ready")

        self._build_ui()
        self._refresh_image_list()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = tk.Frame(self.root)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        top.columnconfigure(1, weight=1)

        tk.Label(top, text="Title:").grid(row=0, column=0, sticky="w")
        title_entry = tk.Entry(top, textvariable=self._title_var)
        title_entry.grid(row=0, column=1, sticky="ew", padx=(6, 8))
        title_entry.bind("<KeyRelease>", lambda _: self._on_title_changed())

        tk.Button(top, text="Build ISO...", command=self.build_iso).grid(row=0, column=2, sticky="e")

        center = tk.Frame(self.root)
        center.grid(row=1, column=0, sticky="nsew", padx=8)
        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=1)

        list_frame = tk.Frame(center, bd=1, relief=tk.SUNKEN)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.image_list = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        self.image_list.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.image_list.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.image_list.configure(yscrollcommand=sb.set)

        buttons = tk.Frame(center)
        buttons.grid(row=0, column=1, sticky="ns", padx=(8, 0))

        tk.Button(buttons, text="Add Files...", width=18, command=self.add_files_dialog).pack(pady=(0, 4))
        tk.Button(buttons, text="Add Folder...", width=18, command=self.add_folder_dialog).pack(pady=4)
        tk.Button(buttons, text="Remove", width=18, command=self.remove_selected).pack(pady=(12, 4))
        tk.Button(buttons, text="Move Up", width=18, command=lambda: self.move_selected(-1)).pack(pady=4)
        tk.Button(buttons, text="Move Down", width=18, command=lambda: self.move_selected(1)).pack(pady=4)

        status = tk.Label(self.root, textvariable=self._status_var, anchor="w")
        status.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))

        self._build_menu()

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)

        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="New Project", command=self.new_project)
        file_menu.add_command(label="Open Project...", command=self.open_project_dialog)
        file_menu.add_command(label="Save Project", command=self.save_project)
        file_menu.add_command(label="Save Project As...", command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="Build ISO...", command=self.build_iso)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)

        menu.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menu)

    def _set_status(self, text: str) -> None:
        self._status_var.set(text)

    def _on_title_changed(self) -> None:
        self.project.title = self._title_var.get() or APP_NAME
        self._refresh_window_title()

    def _refresh_window_title(self) -> None:
        name = self.project_path.name if self.project_path else "Untitled"
        self.root.title(f"{APP_NAME} (Classic) - {name}")

    def _refresh_image_list(self) -> None:
        self.image_list.delete(0, tk.END)
        for i, img in enumerate(self.project.images, 1):
            mark = "*" if img.default else " "
            self.image_list.insert(tk.END, f"{i:03d}{mark} {Path(img.path).name}  [{img.path}]")
        self._set_status(f"{len(self.project.images)} image(s)")
        self._refresh_window_title()

    def _replace_project(self, project: Project, path: str | None = None) -> None:
        project.ensure_one_default()
        self.project = project
        self.project_path = Path(path) if path else None
        self._title_var.set(self.project.title)
        self._refresh_image_list()

    def new_project(self) -> None:
        self._replace_project(Project())

    def open_project_path(self, path: str) -> None:
        try:
            project = Project.load(path)
        except Exception as e:
            messagebox.showerror("Open failed", f"Failed to open project:\n{e}")
            return
        self._replace_project(project, path=path)

    def open_project_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Open project",
            filetypes=[("FloppyBootCD projects", f"*{PROJECT_EXT}"), ("All files", "*.*")],
        )
        if path:
            self.open_project_path(path)

    def save_project(self) -> bool:
        if self.project_path is None:
            return self.save_project_as()
        try:
            self.project.title = self._title_var.get() or APP_NAME
            self.project.save(self.project_path)
        except Exception as e:
            messagebox.showerror("Save failed", f"Failed to save project:\n{e}")
            return False
        self._set_status(f"Saved: {self.project_path}")
        return True

    def save_project_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            title="Save project",
            defaultextension=PROJECT_EXT,
            filetypes=[("FloppyBootCD projects", f"*{PROJECT_EXT}"), ("All files", "*.*")],
        )
        if not path:
            return False
        if not path.lower().endswith(PROJECT_EXT):
            path += PROJECT_EXT
        self.project_path = Path(path)
        return self.save_project()

    def _add_paths(self, paths: Iterable[str]) -> int:
        existing = {normalize_for_dedup(img.path) for img in self.project.images}
        added = 0
        for p in paths:
            cp = _canonicalize(p)
            norm = normalize_for_dedup(cp)
            if norm in existing:
                continue
            if not Path(cp).is_file():
                continue
            self.project.images.append(FloppyImage(path=cp))
            existing.add(norm)
            added += 1
        if added:
            self.project.ensure_one_default()
            self._refresh_image_list()
        return added

    def add_paths(self, paths: Sequence[str]) -> None:
        added = self._add_paths(paths)
        self._set_status(f"Added {added} image(s)")

    def add_files_dialog(self) -> None:
        raw = filedialog.askopenfilenames(
            title="Add floppy images",
            filetypes=[("Floppy images", _accepted_file_dialog_pattern()), ("All files", "*.*")],
        )
        if not raw:
            return
        self.add_paths(list(raw))

    def add_folder_dialog(self) -> None:
        folder = filedialog.askdirectory(title="Add folder")
        if not folder:
            return
        self.add_paths(walk_floppy_images(folder))

    def remove_selected(self) -> None:
        indexes = list(self.image_list.curselection())
        if not indexes:
            return
        for idx in reversed(indexes):
            del self.project.images[idx]
        self.project.ensure_one_default()
        self._refresh_image_list()

    def move_selected(self, delta: int) -> None:
        selected = list(self.image_list.curselection())
        if len(selected) != 1:
            return
        i = selected[0]
        j = i + delta
        if j < 0 or j >= len(self.project.images):
            return
        self.project.images[i], self.project.images[j] = self.project.images[j], self.project.images[i]
        self._refresh_image_list()
        self.image_list.selection_set(j)

    def build_iso(self) -> None:
        self.project.title = self._title_var.get() or APP_NAME
        problems = validate_project(self.project)
        if problems:
            messagebox.showerror("Build blocked", "Project has problems:\n\n- " + "\n- ".join(problems))
            return

        out = filedialog.asksaveasfilename(
            title="Build ISO",
            defaultextension=".iso",
            filetypes=[("ISO images", "*.iso"), ("All files", "*.*")],
        )
        if not out:
            return

        self.root.config(cursor="watch")
        self.root.update_idletasks()

        logs: list[str] = []
        try:
            result = build(
                self.project,
                BuildOptions(output_path=Path(out)),
                log=lambda line: logs.append(line),
            )
        except Exception as e:
            tail = "\n".join(logs[-12:])
            msg = f"Build failed:\n{e}"
            if tail:
                msg += f"\n\nRecent log:\n{tail}"
            messagebox.showerror("Build failed", msg)
            self._set_status("Build failed")
            return
        finally:
            self.root.config(cursor="")

        messagebox.showinfo("Build complete", f"ISO written to:\n{result.iso_path}")
        self._set_status(f"Built: {result.iso_path}")

    def dispatch_cli_paths(self, paths: Sequence[str]) -> None:
        project_path, images = resolve_input_paths(paths)
        if project_path:
            self.open_project_path(project_path)
            return
        if images:
            self.add_paths(images)


def _require_tk() -> None:
    if tk is None or filedialog is None or messagebox is None:
        raise RuntimeError(
            "Tkinter is not available in this Python build. Ensure your Python "
            "installation includes Tk support, or use the Qt frontend."
        )


def main(argv: Sequence[str] | None = None) -> int:
    _require_tk()
    load_plugins()

    args = list(sys.argv if argv is None else argv)
    root = tk.Tk()
    app = ClassicMainWindow(root)
    cli_paths = _parse_cli_paths(args[1:])
    if cli_paths:
        app.dispatch_cli_paths(cli_paths)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
