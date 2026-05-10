"""FloppyBootCD - build bootable CDs from floppy disk images."""
from importlib.metadata import PackageNotFoundError, version as _pkg_version

# Sourced from package metadata so it stays in sync with pyproject.toml
# automatically. Falls back to "0.0.0-dev" for in-tree runs before the
# package has been installed (rare; covers `python -m floppybootcd` from
# a fresh checkout without `pip install -e .`).
try:
    __version__ = _pkg_version("floppybootcd")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

APP_NAME = "FloppyBootCD"
APP_ID = "com.pacnpal.floppybootcd"
