"""Tests for entry-point-based plugin discovery."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from floppybootcd.core import bootloader, burner, plugins
from floppybootcd.core.bootloader import BootloaderBackend, StagingResult
from floppybootcd.core.burner import BurnerBackend, OpticalDrive
from floppybootcd.core.project import Project


# ── Fakes ──────────────────────────────────────────────────────────

class _FakeBootloader(BootloaderBackend):
    id = "fake-boot"
    label = "Fake Bootloader"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def stage(self, project, iso_root, progress=None):
        return StagingResult("a", "b", [])


class _FakeBurner(BurnerBackend):
    id = "fake-burner"
    label = "Fake Burner"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def list_drives(self):
        return []

    def burn(self, iso_path, drive, verify, eject, progress, log):
        return None


class _FakeEntryPoint:
    def __init__(self, name: str, target):
        self.name = name
        self._target = target

    def load(self):
        return self._target


class _FakeEntryPoints:
    def __init__(self, mapping: dict[str, list]):
        self._mapping = mapping

    def select(self, group: str):
        return self._mapping.get(group, [])

    def get(self, group: str, default=None):  # for older importlib API
        return self._mapping.get(group, default or [])


# ── Tests ──────────────────────────────────────────────────────────

@pytest.fixture
def restore_registries():
    """Snapshot and restore the global registries around each test."""
    saved_boot = bootloader.BUILTIN_BACKENDS.copy()
    saved_burn = list(burner.ALL_BURNERS)
    yield
    bootloader.BUILTIN_BACKENDS.clear()
    bootloader.BUILTIN_BACKENDS.update(saved_boot)
    burner.ALL_BURNERS[:] = saved_burn


class TestLoadPlugins:
    def test_registers_bootloader_plugin(self, monkeypatch, restore_registries):
        eps = _FakeEntryPoints({
            "floppybootcd.bootloaders": [_FakeEntryPoint("fake-boot", _FakeBootloader)],
            "floppybootcd.burners": [],
        })
        monkeypatch.setattr(plugins.md, "entry_points", lambda: eps)
        plugins.load_plugins()
        assert bootloader.BUILTIN_BACKENDS.get("fake-boot") is _FakeBootloader

    def test_registers_burner_plugin(self, monkeypatch, restore_registries):
        eps = _FakeEntryPoints({
            "floppybootcd.bootloaders": [],
            "floppybootcd.burners": [_FakeEntryPoint("fake-burner", _FakeBurner)],
        })
        monkeypatch.setattr(plugins.md, "entry_points", lambda: eps)
        plugins.load_plugins()
        assert _FakeBurner in burner.ALL_BURNERS

    def test_burner_not_registered_twice(self, monkeypatch, restore_registries):
        eps = _FakeEntryPoints({
            "floppybootcd.bootloaders": [],
            "floppybootcd.burners": [_FakeEntryPoint("fake-burner", _FakeBurner)],
        })
        monkeypatch.setattr(plugins.md, "entry_points", lambda: eps)
        plugins.load_plugins()
        plugins.load_plugins()
        assert burner.ALL_BURNERS.count(_FakeBurner) == 1

    def test_failing_plugin_doesnt_break_others(self, monkeypatch, restore_registries):
        class _ExplodingEntryPoint:
            name = "broken"

            def load(self):
                raise RuntimeError("plugin import failed")

        eps = _FakeEntryPoints({
            "floppybootcd.bootloaders": [
                _ExplodingEntryPoint(),
                _FakeEntryPoint("fake-boot", _FakeBootloader),
            ],
            "floppybootcd.burners": [],
        })
        monkeypatch.setattr(plugins.md, "entry_points", lambda: eps)
        plugins.load_plugins()
        # The good plugin still landed even though the bad one threw.
        assert bootloader.BUILTIN_BACKENDS.get("fake-boot") is _FakeBootloader

    def test_entry_points_failure_is_swallowed(self, monkeypatch, restore_registries):
        """If entry_points() itself raises, load_plugins should return cleanly."""
        def boom():
            raise RuntimeError("metadata broken")

        monkeypatch.setattr(plugins.md, "entry_points", boom)
        # Should not raise
        plugins.load_plugins()
