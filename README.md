# FloppyBootCD

Build bootable CDs from collections of floppy disk images for vintage
computers. Like Ventoy, but for CDs and floppy images instead of USB sticks
and ISOs.

Drop in your `.img` / `.ima` files, give each one a menu label, hit Build,
and get a CD that boots into a menu where you pick which floppy to load.
Each image is loaded into RAM via MEMDISK and presented to the OS as if it
were sitting in a real floppy drive — so DOS, Windows 9x, and other INT 13h
operating systems boot exactly as they would from physical media.

---

## Table of contents

- [What it does](#what-it-does)
- [Install uv (recommended)](#install-uv-recommended)
- [Install FloppyBootCD](#install-floppybootcd)
- [System dependency: xorriso](#system-dependency-xorriso)
- [Quick start](#quick-start)
- [The interface](#the-interface)
- [Features in depth](#features-in-depth)
  - [Adding images](#adding-images)
  - [Editing menu labels](#editing-menu-labels)
  - [Reordering and the default entry](#reordering-and-the-default-entry)
  - [Project settings](#project-settings)
  - [Saving and loading projects](#saving-and-loading-projects)
  - [Building an ISO](#building-an-iso)
  - [Burning to disc](#burning-to-disc)
  - [Verification](#verification)
- [Where files live](#where-files-live)
- [Supported file types](#supported-file-types)
- [Extending FloppyBootCD](#extending-floppybootcd)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [How it works under the hood](#how-it-works-under-the-hood)
- [License](#license)

---

## What it does

- Takes a list of floppy images (any common size, 360 KB through 2.88 MB
  and beyond)
- Generates a boot menu (text or graphical) with one entry per image
- Builds a bootable El Torito ISO 9660 disc image
- Burns it to physical media using your platform's native CD burner:
  - **macOS** → `hdiutil burn` (with verify-after-burn on by default)
  - **Windows** → `isoburn.exe` (the native Windows burn dialog with verify
    checkbox)
  - **Linux** → `xorriso -as cdrecord` (with byte-level verify)

---

## Install uv (recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package and project
manager. It's the easiest way to get FloppyBootCD running because it
manages its own Python and dependencies.

### macOS / Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal afterward so the `PATH` change takes effect, then check
it works:

```bash
uv --version
```

Alternative methods on macOS / Linux:

```bash
brew install uv          # Homebrew
pipx install uv          # via pipx (if you already use it)
```

### Windows

In PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new PowerShell window and verify:

```powershell
uv --version
```

Alternatives on Windows:

```powershell
winget install --id=astral-sh.uv -e
scoop install main/uv
```

### Updating uv later

```bash
uv self update
```

(If you installed via Homebrew, winget, or scoop, use that tool's update
command instead.)

---

## Install FloppyBootCD

### With uv (recommended)

Install once and run from anywhere:

```bash
uv tool install floppybootcd
floppybootcd
```

Or run without installing globally:

```bash
uvx floppybootcd
```

`uvx` downloads, caches, and runs FloppyBootCD in an isolated environment.
Subsequent runs use the cache.

### With pip

If you don't want uv, the standard pip path works fine:

```bash
python -m pip install --user floppybootcd
floppybootcd
```

Or with a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows
pip install floppybootcd
floppybootcd
```

---

## System dependency: xorriso

FloppyBootCD uses `xorriso` to assemble the ISO. Install it once:

| Platform | Command |
|----------|---------|
| macOS | `brew install xorriso` |
| Debian / Ubuntu | `sudo apt install xorriso` |
| Fedora / RHEL | `sudo dnf install xorriso` |
| Arch | `sudo pacman -S libisoburn` |
| Windows | `scoop install xorriso`, or grab a build from the [xorriso site](https://www.gnu.org/software/xorriso/) |

The syslinux binaries (`isolinux.bin`, `memdisk`, `menu.c32`, and the
required support modules) are downloaded automatically from kernel.org on
first build and cached locally. No manual setup needed.

---

## Quick start

1. Launch FloppyBootCD
2. Drag a few `.img` files onto the window (or click **Add Images**)
3. Click each one and edit its menu label
4. Pick one as the **default** entry
5. Click **Save ISO...** to write a `.iso` file, or **Burn to Disc...** to
   write directly to a blank CD-R / CD-RW

That's the whole workflow.

---

## The interface

A rough ASCII map of the main window:

```
┌─ FloppyBootCD — my_dos_collection.fbcd ────────────────────────────┐
│ File   Edit   Tools   Help                                          │
├─────────────────────────────────────────────────────────────────────┤
│ [Add Images]  │ [Save ISO]  [Burn]                                   │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─ Project ─────────────────────────────────────────────────────┐   │
│ │ Disc title:   [DOS Boot Collection                          ]  │   │
│ │ Bootloader:   [ISOLINUX (BIOS)                            ▾]  │   │
│ │ Menu style:   [Text menu (menu.c32)                       ▾]  │   │
│ │ Boot timeout: [  30 s ]                                       │   │
│ └───────────────────────────────────────────────────────────────┘   │
│                                                                     │
│ ┌─────────────────────────────────────────────┐ ┌───────────────┐   │
│ │ ★  MS-DOS 6.22       [dos622.img,  1440 KB] │ │[Add Images...]│   │
│ │    Windows 98 SE     [win98.img,   1440 KB] │ │[Edit...     ] │   │
│ │    DR-DOS 7.03       [drdos.img,   1440 KB] │ │[Remove      ] │   │
│ │    PC-DOS 2000       [pcdos.img,   1440 KB] │ │               │   │
│ │    FreeDOS 1.3       [freedos.img, 2880 KB] │ │[Set Default  ]│   │
│ │                                             │ │               │   │
│ └─────────────────────────────────────────────┘ └───────────────┘   │
│                                                                     │
│ Log:                                                    [Clear]     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ === Building /Users/talor/dos.iso ===                           │ │
│ │ Using xorriso: /opt/homebrew/bin/xorriso                        │ │
│ │ Bootloader: ISOLINUX (BIOS)                                     │ │
│ │ Using cached syslinux binaries.                                 │ │
│ │ Copied dos622.img                                               │ │
│ │ ...                                                             │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ [████████████████████████████████░░░░░] 78%   [Save ISO]  [Burn]   │
│ ─ Building ISO...                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

The star (★) marks the default boot entry.

---

## Features in depth

### Adding images

Three ways:

- **Drag from Finder/Explorer** onto the window or the image list
- **Click "Add Images..."** in the side panel, toolbar, or **Edit** menu
  (Ctrl/Cmd+I)
- **Open a saved `.fbcd` project file**

Recognized extensions: `.img`, `.ima`, `.vfd`, `.flp`. Files outside this
list are ignored on drag-drop. The "Add Images..." dialog defaults to
showing only floppy images but offers an "All files" filter if you need it.

Duplicate paths are silently skipped — adding the same image twice does
nothing rather than producing a confusing duplicate entry.

### Editing menu labels

Each image has its own boot menu label (what shows up at boot time). The
filename is the default label. To change it:

- **Double-click** the entry, or
- Select it and click **Edit...**, or
- Select it and press Enter

The label can include a hotkey marker: in the menu, the character after a
`^` becomes a keyboard shortcut and is highlighted. For example,
`^Windows 98` sets `W` as the hotkey.

### Reordering and the default entry

- **Drag entries up and down** within the list to reorder them. The order
  is the order they appear in the boot menu.
- **Set as Default** marks the selected entry as the one auto-booted after
  the timeout expires. The default entry is shown with a ★ marker. If you
  don't pick one, the first entry is used.

### Project settings

The **Project** panel at the top controls disc-wide settings:

| Setting | What it does |
|---------|--------------|
| **Disc title** | Shows up as the ISO 9660 volume label and as the menu title at boot |
| **Bootloader** | Which bootloader to use. ISOLINUX (BIOS) is the default; plugins can register more (e.g. GRUB4DOS) |
| **Menu style** | "Text menu" uses `menu.c32`. "Graphical menu" uses `vesamenu.c32` and supports a background image |
| **Boot timeout** | Seconds to wait before auto-booting the default entry. Set to 0 ("No auto-boot") to wait forever |

### Saving and loading projects

A **project** captures everything: the image list, labels, default,
timeout, title, menu style. Projects are saved as `.fbcd` files (plain
JSON, easily diffable).

- **File → Save Project** (Ctrl/Cmd+S) — save to the current `.fbcd` file
- **File → Save Project As...** — save under a new name
- **File → Open Project** (Ctrl/Cmd+O) — load an existing `.fbcd`
- **File → New Project** (Ctrl/Cmd+N) — start fresh

A `•` in the title bar means there are unsaved changes. Closing the window
or starting a new project prompts you to save first if there's anything
unsaved.

### Building an ISO

**File → Save ISO...** (Ctrl+B), or the **Save ISO** button.

Pick a destination, hit save, and the ISO is built in the background. The
log panel streams xorriso's output. The status bar and progress bar show
where it is:

1. Preparing bootloader (downloading/extracting syslinux on first run)
2. Copying floppy images into staging
3. Writing the boot config
4. Calling xorriso to assemble the ISO

When done, you get a notification with the output path. The ISO is
immediately bootable in QEMU/VirtualBox/VMware and on real hardware that
has a BIOS-compatible CD drive.

### Burning to disc

**File → Burn to Disc...** (Ctrl+Shift+B), or the **Burn** button.

This builds an ISO to a temp file, then opens the **Burn dialog**:

```
┌─ Burn ISO to Disc ─────────────────────────────────────┐
│ ISO:      floppybootcd_temp.iso                         │
│ Backend:  Linux xorriso/cdrecord                        │
│                                                         │
│ Drive:    [/dev/sr0 — HL-DT-ST DVDRAM GUD0N      ▾] [Refresh] │
│           [✓] Verify after burning                      │
│           [✓] Eject when done                           │
│                                                         │
│ [████████████░░░░░░░░░░░░░░░░░░░░░░░░] 35%             │
│ Burning...                                              │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ $ xorriso -as cdrecord -v dev=/dev/sr0 -dao ...     │ │
│ │ Track 01: 18 of 52 MB written.                      │ │
│ │ ...                                                 │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│                                       [Burn]  [Close]   │
└─────────────────────────────────────────────────────────┘
```

The drive picker auto-fills with detected optical burners. If you're on
Windows and `isoburn.exe` is the backend, picking a drive is optional —
the native Windows burn dialog will let you confirm or change the target
when it appears.

### Verification

| Backend | How verify works |
|---------|------------------|
| macOS `hdiutil` | Verify is on by default. Uncheck the box to skip with `-noverifyburn` |
| Windows `isoburn.exe` | The native dialog includes a verify checkbox you can toggle |
| Linux `xorriso/cdrecord` | FloppyBootCD reads the burned disc back, sector by sector, and SHA1-compares it against the source ISO |

If verify fails, you'll see a clear error in the log and a dialog. The
disc is left in the drive so you can examine it.

> **Linux note:** Verify needs read access to the optical device
> (`/dev/sr0`, etc.). If your user isn't in the `cdrom` group, you'll see a
> permission denied warning. Add yourself with `sudo usermod -aG cdrom $USER`
> then log out and back in.

---

## Where files live

FloppyBootCD respects each OS's conventions:

| Data | macOS | Windows | Linux |
|------|-------|---------|-------|
| Settings | `~/Library/Application Support/FloppyBootCD/` | `%APPDATA%\FloppyBootCD\` | `~/.config/FloppyBootCD/` |
| Cached syslinux | `~/Library/Caches/FloppyBootCD/syslinux/<ver>/` | `%LOCALAPPDATA%\FloppyBootCD\syslinux\<ver>\` | `~/.cache/FloppyBootCD/syslinux/<ver>/` |
| Window geometry & preferences | Native (plist / registry / config file) via QSettings | | |

To wipe the syslinux cache: **Tools → Clear Syslinux Cache**.

---

## Supported file types

**Floppy images:** any raw sector dump. The standard sizes work without
any configuration:

| Disk type | Bytes |
|-----------|-------|
| 360 KB 5.25" | 368,640 |
| 720 KB 3.5" | 737,280 |
| 1.2 MB 5.25" | 1,228,800 |
| 1.44 MB 3.5" | 1,474,560 |
| 2.88 MB 3.5" | 2,949,120 |

Oversized "fat floppy" images (up to ~50 MB) are also supported — MEMDISK
can present them as a floppy-shaped device, but boot time scales with
size since the whole image is loaded into RAM.

**Output:** ISO 9660 + Joliet + Rock Ridge. Bootable on any machine with a
BIOS-compatible CD drive (most pre-UEFI hardware, plus most UEFI machines
in legacy/CSM mode).

---

## Extending FloppyBootCD

FloppyBootCD discovers plugins via Python entry points, so adding a new
bootloader or burner is a pip-installable package away.

### Example: adding a GRUB4DOS bootloader

In your plugin package's `pyproject.toml`:

```toml
[project.entry-points."floppybootcd.bootloaders"]
grub4dos = "my_pkg.grub:Grub4DosBackend"
```

Implement the interface from `floppybootcd/core/bootloader.py`:

```python
from floppybootcd.core.bootloader import BootloaderBackend, StagingResult

class Grub4DosBackend(BootloaderBackend):
    id = "grub4dos"
    label = "GRUB4DOS"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def stage(self, project, iso_root, progress=None) -> StagingResult:
        # ... lay out grldr, menu.lst, and floppy images ...
        return StagingResult(
            boot_image_relpath="boot/grldr",
            boot_catalog_relpath="boot/boot.cat",
            extra_xorriso_args=["-no-emul-boot", "-boot-load-size", "4"],
        )
```

Install your plugin alongside FloppyBootCD and it shows up in the
**Bootloader** dropdown automatically.

### Example: adding a custom burner

```toml
[project.entry-points."floppybootcd.burners"]
my_burner = "my_pkg.burner:MyBurner"
```

Subclass `BurnerBackend` from `floppybootcd/core/burner.py` and implement
`is_available()`, `list_drives()`, and `burn()`.

---

## Troubleshooting

**"xorriso not found"**
Install xorriso (see the [system dependency](#system-dependency-xorriso)
section). Or if it's installed in a non-standard location, point to it via
the **xorriso path** field in settings.

**"Failed to load libcom32.c32" at boot**
The `lib*.c32` modules didn't end up on the disc. Run **Tools → Clear
Syslinux Cache** and rebuild — the next build will re-download a fresh,
complete set of modules.

**Boots to "MEMDISK: image seems to have fractional end cylinder"**
Your floppy image isn't a standard size. Usually harmless (MEMDISK falls
back to treating it as a hard disk image), but if the OS complains, pad
the image to exactly 1,474,560 bytes for 1.44 MB or 2,949,120 for 2.88 MB.

**"Permission denied" reading optical device on Linux**
Add yourself to the `cdrom` group:
```bash
sudo usermod -aG cdrom $USER
```
Log out and back in.

**Burn dialog says "no drives detected"**
Make sure the disc drive is connected (most modern Macs and many laptops
don't have one). On Linux make sure your user has read access to
`/dev/sr*`. On Windows, plug in the drive and click **Refresh**.

---

## Development

### With uv

```bash
git clone https://github.com/pacnpal/floppybootcd
cd floppybootcd
uv sync                  # creates .venv, installs deps from pyproject.toml
uv run floppybootcd      # run without activating the venv
```

Common commands:

```bash
uv add <package>         # add a dependency
uv remove <package>      # remove one
uv lock --upgrade        # bump pinned versions
```

### With pip

```bash
git clone https://github.com/pacnpal/floppybootcd
cd floppybootcd
python -m venv .venv
source .venv/bin/activate                   # or .venv\Scripts\activate on Windows
pip install -e .
floppybootcd
```

### Repository layout

```
floppybootcd/
├── pyproject.toml
├── README.md
└── floppybootcd/
    ├── __init__.py
    ├── __main__.py             # python -m floppybootcd entry
    ├── app.py                  # main(), platform setup, plugin loading
    ├── core/                   # no Qt dependency in here
    │   ├── platform.py         # platform detection + native paths
    │   ├── project.py          # Project / FloppyImage data model
    │   ├── syslinux_fetcher.py # download + extract syslinux binaries
    │   ├── bootloader.py       # bootloader plugin interface + ISOLINUX
    │   ├── iso_builder.py      # staging dir + xorriso runner
    │   ├── burner.py           # burner plugin interface + 3 native impls
    │   └── plugins.py          # entry-point discovery
    └── ui/                     # PySide6 lives only here
        ├── image_list.py
        ├── burn_dialog.py
        └── main_window.py
```

The `core/` package has no UI dependency — you can write a CLI on top of
it without touching `ui/`.

---

## How it works under the hood

When you build an ISO, FloppyBootCD:

1. **Validates the project.** Checks that all images exist, none are zero
   bytes, and warns on absurdly large images.
2. **Ensures syslinux binaries are cached.** On first build, downloads
   `syslinux-<version>.tar.gz` from kernel.org and extracts the BIOS
   variants of `isolinux.bin`, `memdisk`, `ldlinux.c32`, `libcom32.c32`,
   `libutil.c32`, `libmenu.c32`, `libgpl.c32`, `menu.c32`, `vesamenu.c32`,
   `chain.c32`, and `reboot.c32`. (All those `lib*.c32` files are required
   since syslinux 5.x — missing any one is the #1 cause of "failed to load
   menu.c32" boot errors.)
3. **Stages the disc tree.** In a temp dir, lays out:
   ```
   iso/
   ├── isolinux/
   │   ├── isolinux.bin        ← the El Torito boot record
   │   ├── memdisk             ← the floppy emulator
   │   ├── menu.c32 + libs     ← the boot menu
   │   ├── isolinux.cfg        ← generated config
   │   └── (vesa background)   ← if graphical menu enabled
   └── images/
       ├── dos622.img
       ├── win98.img
       └── ...
   ```
4. **Generates `isolinux.cfg`.** One `LABEL` block per floppy image plus
   built-in entries for "Boot from hard disk" (`LOCALBOOT 0x80`) and
   "Reboot" (`COM32 reboot.c32`).
5. **Calls xorriso** to roll the staging tree into a bootable ISO 9660
   image with Joliet and Rock Ridge extensions, marked El Torito bootable
   via `isolinux.bin`.

At boot time:

1. BIOS reads `isolinux.bin` from the El Torito boot record
2. ISOLINUX loads `menu.c32` + libs and shows your menu
3. You pick an entry; ISOLINUX loads `memdisk` with the floppy `.img` as
   its initrd
4. MEMDISK installs INT 13h hooks so the OS sees the floppy image as a
   real floppy drive (`A:`)
5. The OS boots normally, fully unaware it's running off a CD

---

## License

MIT.
