"""Plugin discovery.

Third-party packages can register additional bootloader or burner backends
via entry points:

    [project.entry-points."floppybootcd.bootloaders"]
    grub4dos = "my_pkg.grub:Grub4DosBackend"

We discover and merge them into the registries at startup.
"""
from __future__ import annotations

import importlib.metadata as md
import logging

from . import bootloader, burner

log = logging.getLogger(__name__)


def load_plugins() -> None:
    """Discover and register entry-point-based plugins."""
    try:
        eps = md.entry_points()
    except Exception:
        return

    for group, registry in (
        ("floppybootcd.bootloaders", bootloader.BUILTIN_BACKENDS),
        ("floppybootcd.burners", None),  # burners use a list, not dict
    ):
        try:
            entries = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
        except Exception:
            continue
        for ep in entries:
            try:
                cls = ep.load()
            except Exception as e:
                log.warning("Failed to load plugin %s: %s", ep.name, e)
                continue
            if group == "floppybootcd.bootloaders":
                bootloader.BUILTIN_BACKENDS[getattr(cls, "id", ep.name)] = cls
            else:
                if cls not in burner.ALL_BURNERS:
                    burner.ALL_BURNERS.append(cls)
