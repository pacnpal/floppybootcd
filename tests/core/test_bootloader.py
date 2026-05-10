"""Tests for ISOLINUX bootloader staging and config generation."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from floppybootcd.core import bootloader, syslinux_fetcher
from floppybootcd.core.bootloader import (
    BUILTIN_BACKENDS,
    IsolinuxBackend,
    _safe_label,
    available_backends,
    get_backend,
)
from floppybootcd.core.project import FloppyImage, Project


class TestSafeLabel:
    def test_alphanumeric_passthrough(self):
        assert _safe_label("MSDOS622") == "MSDOS622"

    def test_replaces_non_alnum(self):
        assert _safe_label("Win 95.img") == "Win_95_img"

    def test_empty_falls_back(self):
        assert _safe_label("") == "entry"

    def test_all_punctuation_falls_back(self):
        # Replacement chars are still chars, so we get underscores.
        assert _safe_label("!!!") == "___"

    def test_unicode_alnum_kept(self):
        # str.isalnum() considers many unicode letters alnum.
        assert _safe_label("DOSé") == "DOSé"


class TestRegistry:
    def test_get_backend_returns_isolinux_instance(self):
        b = get_backend("isolinux")
        assert isinstance(b, IsolinuxBackend)

    def test_get_backend_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown bootloader backend"):
            get_backend("does-not-exist")

    def test_isolinux_is_registered(self):
        assert "isolinux" in BUILTIN_BACKENDS
        assert IsolinuxBackend in list(available_backends())

    def test_isolinux_is_available(self):
        assert IsolinuxBackend.is_available() is True


class TestWriteConfig:
    """Cover the isolinux.cfg generator. This is the most ISO-correctness-
    critical pure logic in the codebase."""

    def _renamed(self, project: Project) -> dict[int, str]:
        return {idx: Path(img.path).name for idx, img in enumerate(project.images)}

    def _cfg(self, project: Project) -> str:
        return IsolinuxBackend()._write_config(project, self._renamed(project))

    def test_text_menu_uses_menu_c32(self):
        p = Project(menu_style="text", images=[FloppyImage(path="/x/a.img")])
        cfg = self._cfg(p)
        assert "UI menu.c32" in cfg
        assert "vesamenu.c32" not in cfg

    def test_vesa_menu_uses_vesamenu_c32(self):
        p = Project(menu_style="vesa", images=[FloppyImage(path="/x/a.img")])
        cfg = self._cfg(p)
        assert "UI vesamenu.c32" in cfg

    def test_vesa_with_background_emits_menu_background(self):
        p = Project(
            menu_style="vesa",
            background_image="/some/bg.png",
            images=[FloppyImage(path="/x/a.img")],
        )
        cfg = self._cfg(p)
        assert "MENU BACKGROUND background.png" in cfg

    def test_vesa_without_background_omits_menu_background(self):
        p = Project(menu_style="vesa", images=[FloppyImage(path="/x/a.img")])
        assert "MENU BACKGROUND" not in self._cfg(p)

    def test_text_menu_never_emits_menu_background(self):
        p = Project(
            menu_style="text",
            background_image="/some/bg.png",
            images=[FloppyImage(path="/x/a.img")],
        )
        assert "MENU BACKGROUND" not in self._cfg(p)

    def test_timeout_in_tenths_of_a_second(self):
        p = Project(timeout_secs=30, images=[FloppyImage(path="/x/a.img")])
        assert "TIMEOUT 300" in self._cfg(p)

    def test_timeout_zero(self):
        p = Project(timeout_secs=0, images=[FloppyImage(path="/x/a.img")])
        assert "TIMEOUT 0" in self._cfg(p)

    def test_negative_timeout_clamped_to_zero(self):
        p = Project(timeout_secs=-5, images=[FloppyImage(path="/x/a.img")])
        assert "TIMEOUT 0" in self._cfg(p)

    def test_menu_title_is_fixed_floppybootcd_attribution(self):
        # MENU TITLE is reserved for the FloppyBootCD v<ver> banner so
        # every produced disc carries a fixed, non-editable attribution
        # at the top. The project's own title is rendered separately as
        # a disabled subtitle banner (see test below).
        from floppybootcd import __version__
        p = Project(title="My Cool Disc", images=[FloppyImage(path="/x/a.img")])
        cfg = self._cfg(p)
        assert f"MENU TITLE FloppyBootCD v{__version__}" in cfg
        assert "MENU TITLE My Cool Disc" not in cfg

    def test_disc_title_rendered_as_disabled_banner(self):
        p = Project(title="My Cool Disc", images=[FloppyImage(path="/x/a.img")])
        cfg = self._cfg(p)
        assert "MENU SEPARATOR" in cfg
        assert "LABEL __disc_title__" in cfg
        assert "MENU LABEL My Cool Disc" in cfg
        assert "MENU DISABLE" in cfg

    def test_no_disc_title_banner_when_title_empty(self):
        p = Project(title="", images=[FloppyImage(path="/x/a.img")])
        cfg = self._cfg(p)
        assert "__disc_title__" not in cfg

    def test_shutdown_entry_uses_poweroff_c32(self):
        p = Project(images=[FloppyImage(path="/x/a.img")])
        cfg = self._cfg(p)
        assert "LABEL shutdown" in cfg
        assert "COM32 poweroff.c32" in cfg
        assert "Shutdown" in cfg

    def test_builtins_emitted_in_order(self):
        # local, reboot, shutdown — present, in that order, after the
        # user images.
        p = Project(images=[FloppyImage(path="/x/a.img")])
        cfg = self._cfg(p)
        i_local = cfg.index("LABEL local")
        i_reboot = cfg.index("LABEL reboot")
        i_shutdown = cfg.index("LABEL shutdown")
        assert i_local < i_reboot < i_shutdown

    def test_all_editable_omits_allowoptions(self):
        # Syslinux defaults to Tab-edit enabled; the only reason we'd
        # touch ALLOWOPTIONS is to lock things down.
        p = Project(images=[
            FloppyImage(path="/x/a.img", editable=True),
            FloppyImage(path="/x/b.img", editable=True),
        ])
        cfg = self._cfg(p)
        assert "ALLOWOPTIONS" not in cfg
        assert "MENU NOTABMSG" not in cfg

    def test_any_non_editable_emits_allowoptions_zero(self):
        # Syslinux's Tab-edit lock is global only — `ALLOWOPTIONS 0`
        # affects every entry. We treat any FloppyImage(editable=False)
        # as the user's signal to lock the whole disc (the alternative
        # — silently doing nothing — would be worse).
        p = Project(images=[
            FloppyImage(path="/x/a.img", editable=True),
            FloppyImage(path="/x/b.img", editable=False),
        ])
        cfg = self._cfg(p)
        assert "ALLOWOPTIONS 0" in cfg
        # And we replace the default "Press [Tab] to edit options"
        # status bar message so users aren't told about a key that
        # doesn't work.
        assert "MENU NOTABMSG" in cfg

    def test_default_falls_back_to_first_image(self):
        p = Project(images=[
            FloppyImage(path="/x/first.img"),
            FloppyImage(path="/x/second.img"),
        ])
        cfg = self._cfg(p)
        assert "DEFAULT first_img" in cfg

    def test_default_uses_explicit_default(self):
        p = Project(images=[
            FloppyImage(path="/x/first.img"),
            FloppyImage(path="/x/second.img", default=True),
        ])
        cfg = self._cfg(p)
        assert "DEFAULT second_img" in cfg

    def test_default_image_emits_menu_default(self):
        p = Project(images=[
            FloppyImage(path="/x/a.img", default=True),
        ])
        cfg = self._cfg(p)
        assert "  MENU DEFAULT" in cfg

    def test_no_default_line_when_no_images(self):
        p = Project()
        cfg = self._cfg(p)
        assert "DEFAULT" not in cfg

    def test_hotkey_inserts_caret_before_char(self):
        p = Project(images=[
            FloppyImage(path="/x/a.img", label="Boot DOS", hotkey="D"),
        ])
        cfg = self._cfg(p)
        assert "MENU LABEL Boot ^DOS" in cfg

    def test_hotkey_not_in_label_is_noop(self):
        p = Project(images=[
            FloppyImage(path="/x/a.img", label="Linux", hotkey="Z"),
        ])
        cfg = self._cfg(p)
        assert "MENU LABEL Linux" in cfg
        assert "^" not in cfg.split("MENU LABEL Linux")[1].split("\n")[0]

    def test_hotkey_inserts_at_first_occurrence(self):
        p = Project(images=[
            FloppyImage(path="/x/a.img", label="banana", hotkey="a"),
        ])
        cfg = self._cfg(p)
        # First 'a' is at index 1
        assert "MENU LABEL b^anana" in cfg

    def test_description_emits_text_help_block(self):
        p = Project(images=[
            FloppyImage(
                path="/x/a.img",
                description="line one\nline two",
            ),
        ])
        cfg = self._cfg(p)
        assert "  TEXT HELP" in cfg
        assert "  line one" in cfg
        assert "  line two" in cfg
        assert "  ENDTEXT" in cfg

    def test_no_description_omits_text_help_block(self):
        p = Project(images=[FloppyImage(path="/x/a.img")])
        cfg = self._cfg(p)
        assert "TEXT HELP" not in cfg
        assert "ENDTEXT" not in cfg

    def test_kernel_and_append_lines_present(self):
        p = Project(images=[FloppyImage(path="/x/disk.img")])
        cfg = self._cfg(p)
        assert "  KERNEL /isolinux/memdisk" in cfg
        assert "  APPEND initrd=/images/disk.img" in cfg

    def test_localboot_and_reboot_entries_always_present(self):
        p = Project(images=[FloppyImage(path="/x/a.img")])
        cfg = self._cfg(p)
        assert "LABEL local" in cfg
        assert "  LOCALBOOT 0x80" in cfg
        assert "LABEL reboot" in cfg
        assert "  COM32 reboot.c32" in cfg

    def test_localboot_and_reboot_present_even_without_images(self):
        p = Project()
        cfg = self._cfg(p)
        assert "LABEL local" in cfg
        assert "LABEL reboot" in cfg

    def test_label_comes_from_safe_filename(self):
        p = Project(images=[FloppyImage(path="/x/Win 95.img")])
        # filename is "Win 95.img" → _safe_label → "Win_95_img"
        cfg = self._cfg(p)
        assert "LABEL Win_95_img" in cfg


class TestStageDedup:
    """Verify the rename-on-collision logic in IsolinuxBackend.stage()."""

    def _stub_syslinux_dir(self, tmp_path) -> Path:
        d = tmp_path / "sl"
        d.mkdir()
        for f in syslinux_fetcher.REQUIRED_BIOS_FILES:
            (d / f).write_bytes(b"\0")
        return d

    def test_duplicate_filenames_get_renamed(self, tmp_path, monkeypatch):
        sl_dir = self._stub_syslinux_dir(tmp_path)
        monkeypatch.setattr(
            syslinux_fetcher, "fetch_syslinux",
            lambda version, progress=None: sl_dir,
        )

        # Two source files with the same basename in different dirs
        d1 = tmp_path / "src1"
        d2 = tmp_path / "src2"
        d1.mkdir()
        d2.mkdir()
        (d1 / "boot.img").write_bytes(b"first")
        (d2 / "boot.img").write_bytes(b"second")

        project = Project(images=[
            FloppyImage(path=str(d1 / "boot.img")),
            FloppyImage(path=str(d2 / "boot.img")),
        ])

        iso_root = tmp_path / "iso"
        iso_root.mkdir()
        IsolinuxBackend().stage(project, iso_root)

        images_dir = iso_root / "images"
        names = sorted(p.name for p in images_dir.iterdir())
        assert names == ["boot.img", "boot_1.img"]
        # Contents should be preserved (not collapsed)
        assert (images_dir / "boot.img").read_bytes() == b"first"
        assert (images_dir / "boot_1.img").read_bytes() == b"second"

    def test_dedup_is_case_insensitive(self, tmp_path, monkeypatch):
        sl_dir = self._stub_syslinux_dir(tmp_path)
        monkeypatch.setattr(
            syslinux_fetcher, "fetch_syslinux",
            lambda version, progress=None: sl_dir,
        )
        d1 = tmp_path / "x"
        d2 = tmp_path / "y"
        d1.mkdir()
        d2.mkdir()
        (d1 / "Boot.IMG").write_bytes(b"a")
        (d2 / "boot.img").write_bytes(b"b")

        project = Project(images=[
            FloppyImage(path=str(d1 / "Boot.IMG")),
            FloppyImage(path=str(d2 / "boot.img")),
        ])
        iso_root = tmp_path / "iso"
        iso_root.mkdir()
        IsolinuxBackend().stage(project, iso_root)

        names = {p.name.lower() for p in (iso_root / "images").iterdir()}
        # One stays "Boot.IMG", second gets "boot_1.img"
        assert "boot.img" in names
        assert "boot_1.img" in names

    def test_stage_writes_isolinux_cfg(self, tmp_path, monkeypatch):
        sl_dir = self._stub_syslinux_dir(tmp_path)
        monkeypatch.setattr(
            syslinux_fetcher, "fetch_syslinux",
            lambda version, progress=None: sl_dir,
        )
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.img").write_bytes(b"a")

        project = Project(
            title="StageTest",
            images=[FloppyImage(path=str(src / "a.img"))],
        )
        iso_root = tmp_path / "iso"
        iso_root.mkdir()
        result = IsolinuxBackend().stage(project, iso_root)

        cfg = (iso_root / "isolinux" / "isolinux.cfg").read_text()
        # MENU TITLE is always the FloppyBootCD attribution; project
        # title shows up as the disabled subtitle banner below it.
        assert "MENU TITLE FloppyBootCD v" in cfg
        assert "MENU LABEL StageTest" in cfg
        assert result.boot_image_relpath == "isolinux/isolinux.bin"
        assert result.boot_catalog_relpath == "isolinux/boot.cat"
        assert "-no-emul-boot" in result.extra_xorriso_args

    def test_imz_source_extracted_and_renamed_to_ima(self, tmp_path, monkeypatch):
        sl_dir = self._stub_syslinux_dir(tmp_path)
        monkeypatch.setattr(
            syslinux_fetcher, "fetch_syslinux",
            lambda version, progress=None: sl_dir,
        )
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        imz = src_dir / "MSDOS622.imz"
        inner = b"\x55\xaa" + b"BOOT" * 100
        with zipfile.ZipFile(imz, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("MSDOS622.ima", inner)

        project = Project(images=[FloppyImage(path=str(imz))])
        iso_root = tmp_path / "iso"
        iso_root.mkdir()
        IsolinuxBackend().stage(project, iso_root)

        staged = iso_root / "images" / "MSDOS622.ima"
        assert staged.is_file()
        assert staged.read_bytes() == inner
        assert not (iso_root / "images" / "MSDOS622.imz").exists()

        cfg = (iso_root / "isolinux" / "isolinux.cfg").read_text()
        assert "APPEND initrd=/images/MSDOS622.ima" in cfg
        assert "initrd=/images/MSDOS622.imz" not in cfg

    def test_imz_collides_with_ima_gets_renamed(self, tmp_path, monkeypatch):
        sl_dir = self._stub_syslinux_dir(tmp_path)
        monkeypatch.setattr(
            syslinux_fetcher, "fetch_syslinux",
            lambda version, progress=None: sl_dir,
        )
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        ima = src_dir / "boot.ima"
        ima.write_bytes(b"raw")
        imz = src_dir / "boot.imz"
        with zipfile.ZipFile(imz, "w") as zf:
            zf.writestr("boot.ima", b"compressed")

        project = Project(images=[
            FloppyImage(path=str(ima)),
            FloppyImage(path=str(imz)),
        ])
        iso_root = tmp_path / "iso"
        iso_root.mkdir()
        IsolinuxBackend().stage(project, iso_root)

        names = sorted(p.name for p in (iso_root / "images").iterdir())
        assert names == ["boot.ima", "boot_1.ima"]
        assert (iso_root / "images" / "boot.ima").read_bytes() == b"raw"
        assert (iso_root / "images" / "boot_1.ima").read_bytes() == b"compressed"

    def test_stage_copies_background_image_when_vesa(self, tmp_path, monkeypatch):
        sl_dir = self._stub_syslinux_dir(tmp_path)
        monkeypatch.setattr(
            syslinux_fetcher, "fetch_syslinux",
            lambda version, progress=None: sl_dir,
        )
        bg = tmp_path / "background.png"
        bg.write_bytes(b"\x89PNG\r\n\x1a\n")
        src = tmp_path / "s"
        src.mkdir()
        (src / "x.img").write_bytes(b"x")

        project = Project(
            menu_style="vesa",
            background_image=str(bg),
            images=[FloppyImage(path=str(src / "x.img"))],
        )
        iso_root = tmp_path / "iso"
        iso_root.mkdir()
        IsolinuxBackend().stage(project, iso_root)

        assert (iso_root / "isolinux" / "background.png").is_file()
