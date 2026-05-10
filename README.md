<div align="center"><img src="./floppybootcd/resources/icon.png" alt="FloppyBootCD Icon" width="200" style="float: left; margin-right: 15px;"></div>

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

Drop in your `.img` / `.ima` / `.vfd` / `.flp` / `.imz` files, give each one a menu label, hit Build,
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

### Supported operating systems

The prebuilt v1.1.0+ bundles target these baselines. Newer versions of
each OS work too. Older versions need [install from source](#install-from-source-uv).

| Bundle | Runs on | Minimum version | Notes |
|--------|---------|-----------------|-------|
| `macos-arm64` | macOS on Apple Silicon (M1/M2/M3/M4 etc.) | **macOS 13 (Ventura)** | Built on macOS 15 against the macOS 13.0 SDK |
| `macos-x86_64` | macOS on Intel | **macOS 13 (Ventura)** | Built on macOS 15 (Intel) against the macOS 13.0 SDK |
| `windows-x86_64` | Windows on Intel/AMD x86_64 | **Windows 10 1809** (Oct 2018) | Native build; runs on Windows 10, 11, Server 2019/2022/2025 |
| `windows-arm64` | Windows on ARM (Surface Pro X / Surface Pro 9+ / Snapdragon X / Copilot+ PCs) | **Windows 11 22H2** | Native ARM64 PyInstaller bundle; the bundled xorriso is the x86_64 build, run via Windows 11's built-in x64 emulator |
| `linux-x86_64` | Linux on Intel/AMD x86_64 | **glibc 2.35** (Ubuntu 22.04, Debian 12, Fedora 36+, Raspberry Pi OS Bookworm) | Built on Ubuntu 22.04. RHEL/Rocky/Alma 9 ship glibc 2.34 and the prebuilt won't load — install from source via uv. |
| `linux-arm64` | Linux on aarch64 — Raspberry Pi 3/4/5/CM3+/CM4/Zero 2 W (64-bit OS), AWS Graviton, Ampere Altra, Apple Silicon under Linux, etc. | **glibc 2.39** (Ubuntu 24.04, Debian 13 Trixie, Fedora 40+, RHEL 10) | Built on Ubuntu 24.04. PySide6's manylinux_2_39_aarch64 wheel pins this floor — for older ARM64 distros (Raspberry Pi OS Bookworm, glibc 2.36) install from source via uv (PySide6 comes from [piwheels](https://www.piwheels.org/)) |

**Not yet supported:** 32-bit Windows (Win32), 32-bit Linux (i686 /
i386), 32-bit ARM Linux (armhf / armv7l, used by older Raspberry Pis and
Pi Zero W), Linux on RISC-V, Solaris, BSD. See [Roadmap](#roadmap) for
the constraints — the blocker is upstream PySide6 wheel availability.

### Download a prebuilt binary (recommended)

Each tagged release publishes a self-contained bundle for every supported
platform. Pick the one that matches your machine:

| Platform | File | xorriso bundled? |
|----------|------|------------------|
| macOS (Apple Silicon, M1/M2/M3/M4) | `floppybootcd-<version>-macos-arm64.zip` | yes (native arm64) |
| macOS (Intel) | `floppybootcd-<version>-macos-x86_64.zip` | yes (native x86_64) |
| Windows (x86_64) | `floppybootcd-<version>-windows-x86_64.zip` | yes (native x86_64) |
| Windows (ARM64) | `floppybootcd-<version>-windows-arm64.zip` | yes (x86_64, runs under Win11 ARM x64 emulation) |
| Linux AppImage (x86_64) | `floppybootcd-<version>-linux-x86_64.AppImage` | yes (native x86_64) |
| Linux AppImage (ARM64) | `floppybootcd-<version>-linux-arm64.AppImage` | yes (native aarch64) |
| Debian / Ubuntu / Pi OS (x86_64) | `floppybootcd-<version>-linux-x86_64.deb` | yes (native x86_64) |
| Debian / Ubuntu / Pi OS (ARM64) | `floppybootcd-<version>-linux-arm64.deb` | yes (native aarch64) |
| Fedora / RHEL / openSUSE (x86_64) | `floppybootcd-<version>-linux-x86_64.rpm` | yes (native x86_64) |
| Fedora / RHEL / openSUSE (aarch64) | `floppybootcd-<version>-linux-arm64.rpm` | yes (native aarch64) |
| Linux tarball (x86_64) | `floppybootcd-<version>-linux-x86_64.tar.gz` | yes (native x86_64) |
| Linux tarball (ARM64 / Raspberry Pi 3-5) | `floppybootcd-<version>-linux-arm64.tar.gz` | yes (native aarch64) |

Linux ships in four flavors per arch: an **AppImage** (single-file
portable, works on any distro at or above the glibc baseline below),
a **`.deb`** for the Debian/Ubuntu/Raspberry Pi OS family, a **`.rpm`**
for the Fedora/RHEL/openSUSE family, and a raw **`.tar.gz`** of the
PyInstaller bundle for read-only filesystems or distros without
package managers. All four contain the same binary — pick whichever
matches your install habits.

Since v1.1.0, every prebuilt bundle ships with `xorriso` already
inside, so you don't need to install it separately. The Windows ARM64
artifact bundles the x86_64 xorriso instead of a native ARM64 build —
that's because there's no public MSYS2 woarm64 build of `libisoburn`
yet. Windows 11 on ARM ships a built-in x64 emulator that runs the
x86_64 binary fine for our subprocess use case.

The bundle contains FloppyBootCD itself, the Python + PySide6 runtime,
and `xorriso` plus its required shared libraries. syslinux modules
continue to be fetched on first build, as usual.

xorriso is licensed under [GPLv3](LICENSE-xorriso) and is shipped
unmodified, side-by-side with FloppyBootCD (which remains MIT). See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the source-offer
and the full attribution.

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

# 4. (Optional) install xorriso. The macOS prebuilt binary already ships
#    one. Install only if FloppyBootCD reports it can't find xorriso, or
#    if you'd rather use the Homebrew copy.
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

# 3. (Optional) install xorriso. Both the x86_64 and ARM64 prebuilts
#    already include xorriso. The ARM64 bundle uses the x86_64 xorriso
#    via Windows 11's built-in x64 emulator — that's the supported
#    configuration. Override only if you want a system-installed copy:
scoop install xorriso
```

The first time you launch it, **Windows SmartScreen** may show a
"Windows protected your PC" dialog because the binary is unsigned. Click
**More info** → **Run anyway**.

#### Linux (including Raspberry Pi)

Linux ships in four flavors. Pick whichever matches your distro and
arch — they all contain the same binary.

```bash
# A. AppImage — universal, no install, just chmod and run.
#    Works on any distro at or above the glibc baseline below.
chmod +x floppybootcd-<version>-linux-<arch>.AppImage
./floppybootcd-<version>-linux-<arch>.AppImage

# B. .deb — Debian, Ubuntu, Raspberry Pi OS, Pop!_OS, Mint, ...
sudo apt install ./floppybootcd-<version>-linux-<arch>.deb
floppybootcd

# C. .rpm — Fedora, RHEL, Rocky, Alma, openSUSE, ...
sudo dnf install ./floppybootcd-<version>-linux-<arch>.rpm
floppybootcd

# D. Raw tarball — any distro, no package manager involvement.
tar -xzf floppybootcd-<version>-linux-<arch>.tar.gz
cd floppybootcd
./floppybootcd
```

Arch values: `x86_64` (Intel/AMD) or `arm64` (Raspberry Pi 3/4/5/Zero
2 W on a 64-bit OS, AWS Graviton, Ampere Altra, etc.).

xorriso is bundled in all four formats; you only need to install a
system copy if you want to override the bundled version (`sudo apt
install xorriso`, `sudo dnf install xorriso`, `sudo pacman -S
libisoburn`).

The Linux bundle ships with the Qt runtime, platform plugins, and
xorriso it needs, so no extra system installs are required on a
desktop-flavored distro. glibc baselines differ by arch:

- **`linux-x86_64`** is built on Ubuntu 22.04 → **glibc 2.35**. Covers
  Ubuntu 22.04+ (2.35+), Debian 12 (Bookworm, 2.36), Raspberry Pi OS
  Bookworm (2.36), Fedora 36+ (2.35+), and most other modern distros.
  Does **not** cover RHEL/Rocky/Alma 9 (glibc 2.34) — install from
  source via `uv` on that family. glibc is forward-compatible only,
  so a binary linked against 2.35 won't load on 2.34.
- **`linux-arm64`** is built on Ubuntu 24.04 → **glibc 2.39**. This
  floor is set by upstream PySide6's `manylinux_2_39_aarch64` wheel —
  the wheel won't install on older glibc, so we can't build against
  it. Covers Ubuntu 24.04+ (2.39), Debian 13 Trixie+ (2.40), Fedora 40+
  (2.39), RHEL 10. **Does not cover Raspberry Pi OS Bookworm** (glibc
  2.36); on that distro install from source via `uv`, which uses
  [piwheels](https://www.piwheels.org/) for PySide6.

Older distros (Ubuntu 20.04, Debian 11, RHEL 8, Raspberry Pi OS
Bullseye) won't load the prebuilt either way — install from source via
`uv` instead. See [Roadmap](#roadmap) for the long-term plan.

If `./floppybootcd` complains about a missing X/Wayland library on a
minimal distro, install the typical desktop runtime (`libxkbcommon`,
`libegl1`, `libfontconfig`, `libxcb-cursor0`, etc.).

##### Raspberry Pi compatibility

| Pi model | CPU | Recommended OS | Prebuilt binary works? |
|----------|-----|----------------|------------------------|
| Pi 5, CM5 | Cortex-A76 (ARMv8.2-A) | Raspberry Pi OS 64-bit, Trixie+ | `linux-arm64` ✅ |
| Pi 5, CM5 | Cortex-A76 | Raspberry Pi OS 64-bit, Bookworm | ❌ — glibc 2.36 < 2.39; install from source |
| Pi 4, 400, CM4 | Cortex-A72 | Raspberry Pi OS 64-bit, Trixie+ | `linux-arm64` ✅ |
| Pi 4, 400, CM4 | Cortex-A72 | Raspberry Pi OS 64-bit, Bookworm | ❌ — glibc 2.36 < 2.39; install from source |
| Pi 3, 3+, CM3, CM3+, Zero 2 W | Cortex-A53 | Raspberry Pi OS 64-bit | depends on Pi OS release (see above) |
| Pi 2 v1.2 | Cortex-A53 (can run 64-bit) | Raspberry Pi OS 64-bit | depends on Pi OS release (see above) |
| Pi 2 v1.1 | Cortex-A7 (ARMv7, 32-bit only) | Raspberry Pi OS 32-bit | ❌ no armhf prebuilt — install from source |
| Pi 1, Zero, Zero W, CM1 | ARM1176JZF-S (ARMv6, 32-bit only) | Raspberry Pi OS 32-bit | ❌ no armv6/armhf prebuilt — install from source |

The `linux-arm64` prebuilt requires **glibc 2.39+** because that's
what upstream PySide6's `manylinux_2_39_aarch64` wheel demands. The
quick way to check on your Pi:

```bash
ldd --version | head -1
```

If it prints `ldd (Debian GLIBC ...) 2.39` or higher, you can run the
prebuilt. Bookworm (`2.36`) and earlier need install-from-source via
`uv`:

```bash
sudo apt install xorriso
curl -LsSf https://astral.sh/uv/install.sh | sh
# Open a new shell so PATH picks up uv, then:
uv tool install git+https://github.com/pacnpal/floppybootcd
floppybootcd
```

That route uses [piwheels](https://www.piwheels.org/) automatically
for PySide6, which is built per Pi OS release with the right glibc.

For **32-bit Raspberry Pis** (Pi 1, Zero, Zero W, Pi 2 v1.1, Pi Zero 2
W on a 32-bit Pi OS), no prebuilt is available — there is no upstream
PySide6 wheel for armhf. Install from source via `uv` and hope
piwheels has a wheel for your Pi OS version. See
[Roadmap](#roadmap) for the long-term armhf plan.

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
- [Roadmap](#roadmap)
- [License](#license)

---

## What it does

- Takes a list of floppy images — raw `.img` / `.ima` / `.vfd` / `.flp`
  in any common size (360 KB through 2.88 MB and beyond), plus
  WinImage `.imz` ZIP-compressed images (extracted at build time)
- Live **CD-R capacity meter** in the status bar — see the project's
  total in MiB against the 700 MiB usable budget before you click
  Build, with amber/red warnings as you approach or exceed the limit
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

FloppyBootCD uses `xorriso` to assemble the ISO.

**If you downloaded a v1.1.0+ prebuilt binary**, xorriso is already
inside the bundle for every platform — including Windows ARM64, which
ships the x86_64 xorriso and runs it under Windows 11's built-in x64
emulator. You don't need to install it separately. FloppyBootCD will
prefer the bundled copy unless you point `xorriso_override` (in code)
at a different one. xorriso ships under [GPLv3](LICENSE-xorriso); see
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the upstream
source link and the source-offer.

**If you installed from source** (uv/pip), install xorriso once:

| Platform | Command |
|----------|---------|
| macOS | `brew install xorriso` |
| Debian / Ubuntu / Raspberry Pi OS | `sudo apt install xorriso` |
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
bootloader / ISO 9660 overhead). The status-bar disc-usage indicator
is reported in binary **MiB** to match the underlying byte math (the
per-image size column elsewhere uses the conventional KB/MB labels).
`.imz` images count by their **uncompressed** inner size, since that's
what actually lands on the disc after build-time extraction. Builds
that exceed the CD capacity are flagged as a project problem before
xorriso runs; either drop some images or burn to DVD media.

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
| Settings, window geometry, recent dirs (via `QSettings`) | `~/Library/Preferences/floppybootcd.plist` (PyInstaller `.app`) or `~/Library/Preferences/al.pacnp.FloppyBootCD.plist` (uv/pip install) | Registry: `HKCU\Software\pacnpal\FloppyBootCD` | `~/.config/pacnpal/FloppyBootCD.conf` |
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

## Roadmap

Possible future features, with the actual constraints surfaced. None
are committed; if you have a strong opinion on prioritization, open an
issue.

### Older glibc Linux ARM64 (Raspberry Pi OS Bookworm and earlier)

The `linux-arm64` prebuilt requires **glibc 2.39** because that's what
PySide6's `manylinux_2_39_aarch64` wheel demands. This excludes
Raspberry Pi OS Bookworm (glibc 2.36) and any older distro. Users on
those distros can install from source via `uv`, which pulls PySide6
from [piwheels](https://www.piwheels.org/) where the wheels are built
against the local distro's glibc.

A path to a more permissive prebuilt: rebuild PySide6 from source on
Ubuntu 22.04 (glibc 2.35) in CI. Cost: 2-4 hours of CI per release.
On the table if there's demand.

### 32-bit ARM Linux (armhf / armv7l) — Raspberry Pi 1, Zero, Zero W, Pi 2 v1.1, 32-bit Pi OS on newer boards

There is **no upstream PySide6 wheel for armhf** on PyPI, and there is
no realistic path to one without building Qt + PySide6 from source.

- `xorriso` for armhf is easy (`apt install xorriso` on 32-bit Pi OS).
- `PyInstaller` for armhf works fine under QEMU emulation in CI.
- `PySide6` is the blocker. [piwheels](https://www.piwheels.org/) ships
  armhf PySide6 wheels intermittently, tied to specific Raspberry Pi
  OS versions (so a wheel built for Bookworm won't necessarily install
  on Bullseye), and not for every PySide6 release.

Realistic path: a `linux-armhf` artifact built per Raspberry Pi OS
version inside a QEMU `arm/v7` container, pulling PySide6 from
piwheels. Each build is slow (10-30 min) and brittle. On the table if
the demand exists; otherwise armhf users should install from source
via `uv` and accept whatever PySide6 piwheels has for their Pi OS.

### 32-bit Windows (Win32) and 32-bit x86 Linux (i686 / i386)

There are **no upstream PySide6 wheels for `win32` or `manylinux*_i686`
/ `manylinux*_i386`** on PyPI. To ship 32-bit prebuilts we'd need to
build Qt and PySide6 from source for those targets, which is a
multi-hour CI investment and adds maintenance overhead for a tiny
install base.

If you specifically need 32-bit, the install-from-source path with
`uv` works as long as you have a 32-bit PySide6 wheel from somewhere
(piwheels for Linux, or a custom build).

### Native Windows ARM64 xorriso

The `windows-arm64` bundle currently ships the **x86_64 xorriso** and
relies on Windows 11's built-in x64 emulator (works fine). A native
ARM64 xorriso would be ~3 MB smaller and avoid the emulator entirely.

It needs cross-compiling the libisoburn / libisofs / libburn stack
with LLVM-MinGW targeting `aarch64-w64-mingw32`. The toolchain is
functional but young; CI reproducibility is the concern. Track
[Windows-on-ARM-Experiments / msys2-woarm64-build](https://github.com/Windows-on-ARM-Experiments/msys2-woarm64-build)
— if `mingw-w64-aarch64-libisoburn` lands upstream, we can swap to a
native build the same way the x86_64 build works today.

### Code-signed and notarized macOS / Windows builds

The current binaries are unsigned, which is why the README has a
Gatekeeper / SmartScreen workaround section. Signing requires paid
developer accounts (Apple: $99/year, Windows EV cert: ~$300/year). On
the table if there's enough demand to justify the cost.

### Flatpak / Snap for Linux

Since v1.2.0, every Linux release ships **AppImage**, **`.deb`**,
**`.rpm`**, and a raw **`.tar.gz`** for both x86_64 and arm64. That
covers the vast majority of distros. **Flatpak** (cross-distro
software store integration) and **Snap** (Canonical's universal
format) are the remaining gaps. Both require publisher accounts and
ongoing manifest maintenance — on the table if there's enough demand
to justify the upkeep.

---

## License

MIT.

The prebuilt release artifacts also include `xorriso` (GPLv3,
unmodified, separate program) and the Qt + PySide6 runtime
(LGPL-3.0-only). See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
and [`LICENSE-xorriso`](LICENSE-xorriso) for full attribution and
source-offer terms.
