# Third-party notices

FloppyBootCD is licensed under the [MIT License](LICENSE).

The prebuilt release binaries on the [Releases page](https://github.com/pacnpal/floppybootcd/releases) bundle additional third-party software, listed below. Each component retains its own copyright and license. The bundled FloppyBootCD code itself remains MIT-licensed; the project as a whole is an *aggregation* of separately-licensed works.

---

## xorriso (GNU GPLv3)

**Project:** GNU xorriso, part of the libisoburn / libisofs / libburn family
**Upstream:** <https://www.gnu.org/software/xorriso/>
**Source download:** <https://www.gnu.org/software/xorriso/xorriso-1.5.6.tar.gz>
**License:** GNU General Public License, version 3 (or later) — see [`LICENSE-xorriso`](LICENSE-xorriso)
**Bundled binaries:** `xorriso`, `libisoburn`, `libisofs`, `libburn` (and any required runtime libraries copied alongside via `patchelf`/`dylibbundler`)
**Where it lives in the bundle:** `bin/xorriso[.exe]` (and `bin/lib/` or `bin/libs/` for shared libraries on Linux/macOS)

### Why we ship it

xorriso is the tool that assembles the bootable ISO. Bundling it removes the "install xorriso first" step that previously blocked users on macOS (where there is no first-party xorriso) and on Windows. Inside the FloppyBootCD process, xorriso runs as a *separate program* (`subprocess.Popen`) — it is not linked into the FloppyBootCD address space and does not share state with the FloppyBootCD code. This is "mere aggregation" under [GPLv3 §5](LICENSE-xorriso) (which the GPL FAQ confirms: *"in mere aggregation, two programs are placed side by side on the same CD-ROM or other media; the GPL permits you to create and distribute an aggregate"*).

### Source offer

In compliance with GPLv3 §6, we offer the complete corresponding source code for the bundled xorriso binaries:

1. **Direct download from GNU.** The exact source tarball used to build the bundled binaries is available, unmodified, from the GNU mirror network. The version is recorded in the release artifact filename suffix or in this file's revision; `xorriso --version` inside the bundle prints the version.
2. **Written offer.** For three years from the release date of any prebuilt binary, you may request the complete corresponding source code by opening an issue at <https://github.com/pacnpal/floppybootcd/issues> with the title prefix `[GPL Source Request]`. We will provide a downloadable archive matching the bundled binary version at no charge beyond the cost of physical distribution if applicable.

No modifications to xorriso are made by FloppyBootCD; the binaries are built directly from the unmodified upstream source against the platform's standard toolchain (apt for Linux, Homebrew for macOS, MSYS2/MinGW for Windows).

### Platform-specific bundling

| Platform | How xorriso is built/sourced | Runtime libs handling |
|----------|------------------------------|----------------------|
| Linux x86_64, ARM64 | `apt-get install xorriso` on the GitHub Actions runner; binary + non-glibc dependencies copied into `bin/` and `bin/lib/`. RPATH set to `$ORIGIN/lib` via `patchelf`. | Bundled (`libisoburn.so`, `libisofs.so`, `libburn.so`, `libreadline`, `libacl`, `libtinfo`); glibc is loaded from the host. |
| macOS arm64, x86_64 | `brew install xorriso` on the GitHub Actions runner; binary + dylib graph relocated into `bin/` and `bin/libs/` via `dylibbundler` with `@executable_path/libs/` rewrites. | Bundled; system libraries (libSystem) load from the host. |
| Windows x86_64 | MSYS2 MINGW64 package `mingw-w64-x86_64-libisoburn`; `xorriso.exe` plus required `*.dll` files copied alongside. | Bundled. |
| Windows ARM64 | **Not bundled.** No public MSYS2 woarm64 build of `libisoburn`. Install xorriso yourself (Windows on ARM x64 emulation can run the x86_64 build) or follow up via this issue: <https://github.com/pacnpal/floppybootcd/issues>. | n/a |

---

## syslinux (GNU GPLv2+)

**Project:** The Syslinux Project (`isolinux.bin`, `memdisk`, `*.c32`)
**Upstream:** <https://www.kernel.org/pub/linux/utils/boot/syslinux/>
**License:** GPL-2.0-or-later

syslinux binaries are *not* bundled in the FloppyBootCD release artifact. They are downloaded on demand on the user's machine the first time an ISO is built (`syslinux_fetcher.py` pulls from kernel.org and caches them in the OS-conventional cache directory). FloppyBootCD does not redistribute them.

---

## PySide6 (LGPL-3.0-only) and Qt 6

**Project:** Qt for Python (PySide6) and Qt 6
**Upstream:** <https://www.qt.io/qt-for-python>, <https://www.qt.io/>
**License:** LGPL-3.0-only (with the Qt LGPL exception). Commercial licensing available from The Qt Company.

PySide6 and the Qt runtime libraries are bundled with the FloppyBootCD prebuilt binaries via PyInstaller's standard `--collect-all PySide6` flag. LGPL §4(d) is satisfied by:

- shipping the unmodified Qt and PySide6 binaries;
- this file linking to the upstream source;
- the user's ability to relink against a different Qt build (the dynamic loader will pick up substituted libraries placed alongside the FloppyBootCD executable).

Qt source code is available from <https://download.qt.io/>.

---

## Python (PSF License v2)

The CPython runtime is bundled by PyInstaller. It is licensed under the [PSF License v2](https://docs.python.org/3/license.html).

---

## Reporting issues with this notice

If you believe this notice is incomplete, incorrect, or that any bundled component is not properly licensed, please open an issue at <https://github.com/pacnpal/floppybootcd/issues> and we will address it promptly.
