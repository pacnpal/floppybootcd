"""Tests for the Project / FloppyImage data model."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from floppybootcd.core.project import FloppyImage, Project


class TestFloppyImage:
    def test_filename_is_basename(self):
        img = FloppyImage(path="/abs/path/disk.img")
        assert img.filename == "disk.img"

    def test_display_label_falls_back_to_filename(self):
        img = FloppyImage(path="/x/disk.img")
        assert img.display_label == "disk.img"

    def test_display_label_uses_label_when_set(self):
        img = FloppyImage(path="/x/disk.img", label="Boot Disk")
        assert img.display_label == "Boot Disk"

    def test_exists_true_when_file_present(self, tmp_path):
        p = tmp_path / "x.img"
        p.write_bytes(b"x")
        assert FloppyImage(path=str(p)).exists is True

    def test_exists_false_when_missing(self, tmp_path):
        assert FloppyImage(path=str(tmp_path / "missing.img")).exists is False

    def test_size_bytes(self, tmp_path):
        p = tmp_path / "x.img"
        p.write_bytes(b"abcd")
        assert FloppyImage(path=str(p)).size_bytes == 4

    def test_size_bytes_returns_zero_when_missing(self, tmp_path):
        # Should not raise OSError; should return 0.
        img = FloppyImage(path=str(tmp_path / "no-such-file.img"))
        assert img.size_bytes == 0


class TestProjectSerialization:
    def test_to_dict_round_trip(self):
        p = Project(
            title="My Disc",
            images=[FloppyImage(path="/x/a.img", label="A", default=True)],
            timeout_secs=15,
            menu_style="vesa",
        )
        d = p.to_dict()
        assert d["title"] == "My Disc"
        assert d["timeout_secs"] == 15
        assert d["menu_style"] == "vesa"
        assert d["images"][0]["label"] == "A"
        assert d["images"][0]["default"] is True

    def test_from_dict_round_trip(self):
        p = Project(
            title="My Disc",
            images=[FloppyImage(path="/x/a.img", label="A", hotkey="A")],
            timeout_secs=42,
        )
        p2 = Project.from_dict(p.to_dict())
        assert p2.title == p.title
        assert p2.timeout_secs == 42
        assert len(p2.images) == 1
        assert p2.images[0].label == "A"
        assert p2.images[0].hotkey == "A"

    def test_from_dict_ignores_unknown_keys(self):
        """Forward compat: unknown future keys must not crash load."""
        d = {
            "title": "Future",
            "images": [],
            "future_unknown_field": "ignore me",
            "another_future_key": [1, 2, 3],
        }
        p = Project.from_dict(d)
        assert p.title == "Future"

    def test_from_dict_raises_on_unknown_image_keys(self):
        """FloppyImage uses **kwargs unpack so unknown keys WILL raise. That's
        the documented contract for image entries — only the project-level
        dict is forward-compat. This test pins the current behavior."""
        d = {"title": "T", "images": [{"path": "/x", "future_field": True}]}
        with pytest.raises(TypeError):
            Project.from_dict(d)

    def test_save_load_round_trip(self, tmp_path):
        p = Project(
            title="Round Trip",
            images=[
                FloppyImage(path="/x/a.img", label="A", default=True),
                FloppyImage(path="/x/b.img", label="B", description="help"),
            ],
            timeout_secs=10,
            menu_style="vesa",
            background_image="/x/bg.png",
            notes="some notes",
        )
        out = tmp_path / "p.fbcd"
        p.save(out)
        loaded = Project.load(out)
        assert loaded.title == "Round Trip"
        assert loaded.menu_style == "vesa"
        assert loaded.background_image == "/x/bg.png"
        assert loaded.notes == "some notes"
        assert [i.label for i in loaded.images] == ["A", "B"]
        assert loaded.images[0].default is True
        assert loaded.images[1].description == "help"

    def test_save_writes_pretty_json(self, tmp_path):
        p = Project(title="X")
        out = tmp_path / "p.fbcd"
        p.save(out)
        text = out.read_text(encoding="utf-8")
        # Pretty-printed: contains newlines and indentation
        assert "\n" in text
        assert "  " in text
        # And is valid JSON
        json.loads(text)


class TestDefaultLogic:
    def test_has_default_empty(self):
        assert Project().has_default() is False

    def test_has_default_no_default_image(self):
        p = Project(images=[FloppyImage(path="/x/a.img")])
        assert p.has_default() is False

    def test_has_default_true(self):
        p = Project(images=[FloppyImage(path="/x/a.img", default=True)])
        assert p.has_default() is True

    def test_ensure_one_default_on_empty_project(self):
        p = Project()
        p.ensure_one_default()
        assert p.images == []

    def test_ensure_one_default_picks_first(self):
        p = Project(images=[
            FloppyImage(path="/x/a.img"),
            FloppyImage(path="/x/b.img"),
        ])
        p.ensure_one_default()
        assert p.images[0].default is True
        assert p.images[1].default is False

    def test_ensure_one_default_leaves_existing_default(self):
        p = Project(images=[
            FloppyImage(path="/x/a.img"),
            FloppyImage(path="/x/b.img", default=True),
        ])
        p.ensure_one_default()
        assert p.images[0].default is False
        assert p.images[1].default is True
