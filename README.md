# FloppyBootCD

[![Latest release](https://img.shields.io/github/v/release/pacnpal/floppybootcd?include_prereleases&sort=semver)](https://github.com/pacnpal/floppybootcd/releases/latest)
[![License: MIT](https://img.shields.io/github/license/pacnpal/floppybootcd)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![UI: PySide6 / Qt6](https://img.shields.io/badge/UI-PySide6%20%2F%20Qt6-41cd52.svg)](https://doc.qt.io/qtforpython-6/)
[![Platforms](https://img.shields.io/badge/platforms-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)](#quick-start)
[![Bootloader](https://img.shields.io/badge/bootloader-ISOLINUX%20%2B%20MEMDISK-orange.svg)](https://wiki.syslinux.org/wiki/index.php?title=ISOLINUX)
[![Build with uv](https://img.shields.io/badge/built%20with-uv-261230.svg)](https://docs.astral.sh/uv/)
[![Code style: PEP 8](https://img.shields.io/badge/code%20style-PEP%208-1f425f.svg)](https://peps.python.org/pep-0008/)
[![GitHub stars](https://img.shields.io/github/stars/pacnpal/floppybootcd?style=social)](https://github.com/pacnpal/floppybootcd/stargazers)

Build bootable CDs from collections of floppy disk images for vintage
computers. Like Ventoy, but for CDs and floppy images instead of USB sticks
and ISOs.

Drop in your `.img` / `.ima` / `.imz` files, give each one a menu label, hit Build,
and get a CD that boots into a menu where you pick which floppy to load.
Each image is loaded into RAM via MEMDISK and presented to the OS as if it
were sitting in a real floppy drive — so DOS, Windows 9x, and other INT 13h
operating systems boot exactly as they would from physical media.

---

## Quick start

The fastest way to get running is to grab a prebuilt binary from the
[Releases page](https://github.com/pacnpal/floppybootcd/releases/latest).
No Python, no `uv`, no `pip`. If you'd rather install from source, the
per-platform `uv tool install` instructions follow further down.

### Download a prebuilt binary (recommended)

Each tagged release publishes a self-contained bundle for every supported
platform. Pick the one that matches your machine:

| Platform | File |
|----------|------|
| macOS (Apple Silicon, M1/M2/M3/M4) | `floppybootcd-<version>-macos-arm64.zip` |
| macOS (Intel) | `floppybootcd-<version>-macos-x86_64.zip` |
| Windows (x86_64) | `floppybootcd-<version>-windows-x86_64.zip` |
| Linux (x86_64) | `floppybootcd-<version>-linux-x86_64.tar.gz` |

You will still need `xorriso` installed system-wide — see
[System dependency: xorriso](#system-dependency-xorriso). The bundle
contains FloppyBootCD itself plus the bundled Python and PySide6 runtime;
syslinux modules continue to be fetched on first build, as usual.

#### macOS

```bash
# 1. Unzip the download.
cd ~/Downloads
unzip floppybootcd-<version>-macos-arm64.zip

# 2. macOS quarantines apps downloaded from the web, and (since macOS 15
#    Sequoia) blocks them outright with no right-click "Open" bypass.
#    FloppyBootCD is unsigned and unnotarized, so strip the quarantine
#    attribute before first launch:
xattr -dr com.apple.quarantine floppybootcd.app

# 3. Move it where you like and launch it.
mv floppybootcd.app /Applications/
open /Applications/floppybootcd.app

# 4. (Required) install xorriso.
brew install xorriso
```

If you'd rather not touch the terminal: double-click the app, let macOS
block it, then go to **System Settings → Privacy & Security**, scroll to
the bottom, and click **Open Anyway** next to the FloppyBootCD entry.
Confirm in the next dialog. On macOS 15+ this flow has replaced the older
right-click → Open trick.

> Why the quarantine step? Apple's Gatekeeper requires apps to be both
> code-signed with a Developer ID and notarized through Apple's service
> before they'll launch from a downloaded zip without a warning. This
> project does not currently distribute signed builds — the binaries are
> ad-hoc signed by PyInstaller, which is enough to satisfy the macOS
> loader but not Gatekeeper. The `xattr` command above removes the
> "downloaded from the internet" flag, which is what triggers the block;
> it does not disable Gatekeeper or bypass any other security check.

#### Windows

```powershell
# 1. Unzip the download to wherever you want it (e.g. C:\Tools\).
Expand-Archive .\floppybootcd-<version>-windows-x86_64.zip -DestinationPath C:\Tools\

# 2. Run it.
C:\Tools\floppybootcd\floppybootcd.exe

# 3. (Required) install xorriso.
scoop install xorriso
```

The first time you launch it, **Windows SmartScreen** may show a
"Windows protected your PC" dialog because the binary is unsigned. Click
**More info** → **Run anyway**.

#### Linux

```bash
# 1. Extract.
tar -xzf floppybootcd-<version>-linux-x86_64.tar.gz
cd floppybootcd

# 2. Run it.
./floppybootcd

# 3. (Required) install xorriso.
sudo apt install xorriso        # Debian / Ubuntu
sudo dnf install xorriso        # Fedora / RHEL
sudo pacman -S libisoburn       # Arch
```

The Linux bundle ships with the Qt runtime and platform plugins it needs,
so no extra system Qt install is required. If `./floppybootcd` complains
about a missing X/Wayland library on a minimal distro, install the
typical desktop runtime (`libxkbcommon`, `libegl1`, `libfontconfig`,
`libxcb-cursor0`, etc.).

---

### Install from source (uv)

> **Note:** FloppyBootCD installs straight from this GitHub repo. It is
> not on PyPI. The commands below all use the
> `git+https://github.com/pacnpal/floppybootcd` source.

#### macOS

```bash
# 1. Install uv (skip if you already have it).
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Open a NEW terminal so PATH picks up uv. Then verify:
uv --version

# 3. Install xorriso (the ISO build tool).
brew install xorriso

# 4. Install FloppyBootCD into uv's tool directory.
#    Installs to: ~/.local/share/uv/tools/floppybootcd/
#    Adds executable: ~/.local/bin/floppybootcd
uv tool install git+https://github.com/pacnpal/floppybootcd

# 5. If uv warns "is not on your PATH", run this once and open a new
#    terminal:
uv tool update-shell

# 6. Run it.
floppybootcd
```

If `floppybootcd` still isn't found, you can always run it via uv directly:

```bash
uv tool run floppybootcd      # equivalent to `floppybootcd`
```

Or skip installing entirely:

```bash
uvx --from git+https://github.com/pacnpal/floppybootcd floppybootcd
```

#### Linux

```bash
# 1. Install uv (skip if you already have it).
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Open a NEW terminal so PATH picks up uv. Then verify:
uv --version

# 3. Install xorriso. Pick your distro's command:
sudo apt install xorriso         # Debian / Ubuntu
sudo dnf install xorriso         # Fedora / RHEL
sudo pacman -S libisoburn        # Arch

# 4. Install FloppyBootCD into uv's tool directory.
#    Installs to: ~/.local/share/uv/tools/floppybootcd/
#    Adds executable: ~/.local/bin/floppybootcd
uv tool install git+https://github.com/pacnpal/floppybootcd

# 5. If uv warns "is not on your PATH", run this once and open a new
#    terminal:
uv tool update-shell

# 6. Run it.
floppybootcd
```

If `floppybootcd` still isn't found, run via uv directly:

```bash
uv tool run floppybootcd
```

Or skip installing entirely:

```bash
uvx --from git+https://github.com/pacnpal/floppybootcd floppybootcd
```

#### Windows

In **PowerShell**:

```powershell
# 1. Install uv (skip if you already have it).
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Open a NEW PowerShell window so PATH picks up uv. Then verify:
uv --version

# 3. Install xorriso.
scoop install xorriso
# (or download from https://www.gnu.org/software/xorriso/ and put
#  xorriso.exe somewhere on your PATH)

# 4. Install FloppyBootCD into uv's tool directory.
#    Installs to: %LOCALAPPDATA%\uv\tools\floppybootcd\
#    Adds executable: %USERPROFILE%\.local\bin\floppybootcd.exe
uv tool install git+https://github.com/pacnpal/floppybootcd

# 5. If uv warns "is not on your PATH", run this once and open a new
#    PowerShell window:
uv tool update-shell

# 6. Run it.
floppybootcd
```

If `floppybootcd` still isn't found, run via uv directly:

```powershell
uv tool run floppybootcd
```

Or skip installing entirely:

```powershell
uvx --from git+https://github.com/pacnpal/floppybootcd floppybootcd
```

### Where uv puts everything

When you run `uv tool install git+https://github.com/pacnpal/floppybootcd`,
two things land on disk:

| What | macOS / Linux | Windows |
|------|---------------|---------|
| The isolated venv (Python + PySide6 + FloppyBootCD) | `~/.local/share/uv/tools/floppybootcd/` | `%LOCALAPPDATA%\uv\tools\floppybootcd\` |
| The launcher executable | `~/.local/bin/floppybootcd` | `%USERPROFILE%\.local\bin\floppybootcd.exe` |

You don't run anything from inside the venv directory. uv puts a small
launcher in the **executable directory** that knows how to start the venv
and run the app. As long as that executable directory is on your `PATH`,
typing `floppybootcd` in any shell works.

To check the paths yourself:

```bash
uv tool dir            # the venv directory
uv tool dir --bin      # the executable directory
uv tool list           # everything you've installed via `uv tool`
```

If `floppybootcd` isn't found after install, the executable directory
isn't on your PATH yet — see [Troubleshooting](#troubleshooting).

### Without uv (pip)

If you'd rather use pip directly:

```bash
# macOS / Linux
python -m pip install --user git+https://github.com/pacnpal/floppybootcd.git
floppybootcd

# Windows (PowerShell)
python -m pip install --user "git+https://github.com/pacnpal/floppybootcd.git"
floppybootcd
```

`pip --user` installs to a similar place: `~/.local/bin/floppybootcd` on
macOS/Linux or `%APPDATA%\Python\Python3xx\Scripts\floppybootcd.exe` on
Windows. The same PATH caveat applies — see
[Troubleshooting](#troubleshooting) if the command isn't found.

You'll still need `xorriso` installed via the platform commands shown
above.

---

## Table of contents

- [What it does](#what-it-does)
- [Installing uv](#installing-uv)
- [Installing FloppyBootCD](#installing-floppybootcd)
- [System dependency: xorriso](#system-dependency-xorriso)
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
- [Updating FloppyBootCD](#updating-floppybootcd)
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

## Installing uv

[uv](https://docs.astral.sh/uv/) is a fast Python package and project
manager. It manages its own Python and dependencies, so there's nothing to
configure beyond the install line itself.

### macOS / Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

The installer puts the `uv` binary at `~/.local/bin/uv` and adds
`~/.local/bin` to your PATH by editing your shell profile (`~/.zshenv`,
`~/.bashrc`, etc.). **Open a new terminal** so the PATH change takes
effect, then verify:

```bash
uv --version
```

Alternative methods:

```bash
brew install uv          # Homebrew
pipx install uv          # via pipx (if you already use it)
```

### Windows

In PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

The installer puts `uv.exe` at `%USERPROFILE%\.local\bin\uv.exe` and adds
that directory to your user PATH. **Open a new PowerShell window** and
verify:

```powershell
uv --version
```

Alternatives:

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

## Installing FloppyBootCD

You have two options:

1. **Download a prebuilt binary** from the
   [Releases page](https://github.com/pacnpal/floppybootcd/releases/latest).
   No Python required. See
   [Quick start → Download a prebuilt binary](#download-a-prebuilt-binary-recommended)
   above for per-platform instructions, including the macOS Gatekeeper
   workaround.
2. **Install from source** with `uv` or `pip`. FloppyBootCD installs
   directly from this Git repository — it is not published to PyPI. The
   rest of this section covers that path.

### What `uv tool install` actually does

`uv tool install` is the right command for an end-user GUI app. It:

1. Creates an **isolated virtual environment** for FloppyBootCD (so
   PySide6 doesn't pollute your system Python).
2. Installs FloppyBootCD and its dependencies into that venv.
3. Drops a small **launcher executable** into a directory that's on your
   PATH. That launcher activates the venv and runs FloppyBootCD's
   `main()` for you.

You never need to activate the venv yourself. You don't even need to know
where it is. You just type `floppybootcd` and the launcher handles the
rest.

### With uv (recommended)

```bash
uv tool install git+https://github.com/pacnpal/floppybootcd
```

After install, `uv` prints the executable path and warns if it isn't on
your PATH. If it warns:

```bash
uv tool update-shell        # adds the executable directory to your shell config
# Open a new terminal, then:
floppybootcd
```

Specific tag, branch, or commit:

```bash
uv tool install "git+https://github.com/pacnpal/floppybootcd@v0.1.0"
uv tool install "git+https://github.com/pacnpal/floppybootcd@main"
uv tool install "git+https://github.com/pacnpal/floppybootcd@<commit-sha>"
```

### Run without installing (uvx)

```bash
uvx --from git+https://github.com/pacnpal/floppybootcd floppybootcd
```

`uvx` downloads, caches, and runs FloppyBootCD in a temporary environment
under `~/.cache/uv/`. Subsequent runs use the cache. This is the right
choice for trying it once or running it occasionally without polluting
PATH.

### With pip

If you don't want uv:

```bash
python -m pip install --user git+https://github.com/pacnpal/floppybootcd.git
```

`pip --user` installs the package to your user site-packages and the
`floppybootcd` launcher to:

| Platform | Path |
|----------|------|
| macOS / Linux | `~/.local/bin/floppybootcd` |
| Windows | `%APPDATA%\Python\Python3xx\Scripts\floppybootcd.exe` (where `3xx` is your Python version) |

If that directory isn't on your PATH, the command won't be found. To check:

```bash
python -m site --user-base                # gives you the prefix
# Then add `<that path>/bin` to your PATH (Windows: `<that path>\Scripts`)
```

You can always run via the module name regardless of PATH:

```bash
python -m floppybootcd
```

Or in a virtual environment (cleanest option for pip users):

```bash
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows
pip install git+https://github.com/pacnpal/floppybootcd.git
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

Recognized extensions: `.img`, `.ima`, `.vfd`, `.flp`, and `.imz`
(WinImage compressed images, ZIP-format — extracted automatically at
build time). Files outside this list are ignored on drag-drop. The
"Add Images..." dialog defaults to showing only floppy images but
offers an "All files" filter if you need it.

The status bar shows a running total of the floppy payload against the
usable capacity of an 80-minute 700 MiB CD-R (about 692 MiB after
bootloader / ISO 9660 overhead). All sizes are reported in binary MiB
to match the underlying byte math. `.imz` images count by their
**uncompressed** inner size, since that's what actually lands on the
disc after build-time extraction. Builds that exceed the CD capacity
are flagged as a project problem before xorriso runs; either drop some
images or burn to DVD media.

Duplicate paths are silently skipped — adding the same image twice does
nothing rather than producing a confusing duplicate entry.

### Editing menu labels

Each image has its own boot menu label (what shows up at boot time). The
filename is the default label. To change it:

- **Double-click** the entry, or
- Select it and click **Edit...**

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
| **Menu style** | "Text menu" uses `menu.c32`. "Graphical menu" uses `vesamenu.c32` (a `background_image` path can be set in the saved `.fbcd` file) |
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
| Settings, window geometry, recent dirs (via `QSettings`) | `~/Library/Preferences/com.pacnpal.FloppyBootCD.plist` | Registry: `HKCU\Software\pacnpal\FloppyBootCD` | `~/.config/pacnpal/FloppyBootCD.conf` |
| Cached syslinux | `~/Library/Caches/FloppyBootCD/syslinux/<ver>/` | `%LOCALAPPDATA%\FloppyBootCD\syslinux\<ver>\` | `~/.cache/FloppyBootCD/syslinux/<ver>/` |

To wipe the syslinux cache: **Tools → Clear Syslinux Cache**.

The app itself (when installed via `uv tool install`) lives separately,
under uv's tool directory — see
[Where uv puts everything](#where-uv-puts-everything).

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

## Updating FloppyBootCD

To pull the latest version from the repo:

```bash
# With uv tool install
uv tool upgrade floppybootcd

# With pip
pip install --user --upgrade --force-reinstall \
    git+https://github.com/pacnpal/floppybootcd.git
```

`uvx` always runs the latest cached version; pass `--refresh` to re-pull
from GitHub:

```bash
uvx --refresh --from git+https://github.com/pacnpal/floppybootcd floppybootcd
```

To uninstall:

```bash
uv tool uninstall floppybootcd       # if installed via uv
pip uninstall floppybootcd           # if installed via pip
```

---

## Troubleshooting

**`floppybootcd: command not found` after `uv tool install`**
The launcher landed in uv's executable directory, but that directory isn't
on your PATH. Three options:

```bash
# Option A: let uv fix your shell config
uv tool update-shell
# Then open a new terminal and try again.

# Option B: see where it actually is, then add to PATH yourself
uv tool dir --bin
# macOS / Linux: typically prints ~/.local/bin
# Windows:       typically prints %USERPROFILE%\.local\bin

# Option C: skip PATH and run via uv
uv tool run floppybootcd
```

On macOS specifically, if `uv tool update-shell` says it already added
the entry but `floppybootcd` still isn't found, your shell may be reading
a different config file than the one uv edited. Check both `~/.zprofile`
and `~/.zshenv` for an `export PATH="$HOME/.local/bin:$PATH"` line — if
neither is being read by your terminal, add it manually to whichever one
your shell loads on startup, then `source` it or open a new terminal.

**`floppybootcd: command not found` after `pip install --user`**
Find pip's user-script directory and add it to your PATH:

```bash
# macOS / Linux
python -m site --user-base
# Add <that path>/bin to your PATH

# Windows (PowerShell)
python -m site --user-base
# Add <that path>\Scripts to your PATH
```

Or just run via the module name, which works regardless of PATH:

```bash
python -m floppybootcd
```

**"xorriso not found"**
Install xorriso (see the [system dependency](#system-dependency-xorriso)
section) and make sure the directory containing the binary is on your
`PATH`. The build searches `PATH` plus a handful of common install
locations (`/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`,
`C:\Program Files\xorriso\`, `C:\msys64\usr\bin\`, etc.). If it's
installed somewhere else entirely, point to it via
**Tools → Set xorriso Path...** — the path is remembered between runs.

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
