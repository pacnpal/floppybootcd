# FloppyBootCD

FloppyBootCD turns old boot floppy images into a bootable CD. You feed it one
or more floppy images, it builds a boot menu with one entry per image, and it
writes a bootable ISO you can burn to a CD-R or attach to a VM. It uses
`xorriso` to do the El Torito work and bundles a known-good `xorriso` so you do
not have to chase down dependencies.

It is useful when you have 90s hardware that boots from CD but no longer has a
working floppy drive, which by now is most of it.

There is a GUI and a real CLI. The GUI is the main way to use it; the CLI is
there for scripting and headless builds.

## What it does

- Takes floppy images: raw `.img`, `.ima`, `.vfd`, `.flp` in any common size
  (360 KB through 2.88 MB and up), plus WinImage `.imz` (ZIP-compressed,
  extracted at build time).
- Builds a boot menu, text or graphical, with one entry per image.
- Emits a bootable El Torito ISO 9660 disc image.
- Shows a live CD-R capacity meter in the status bar so you can see your
  project's total against the 700 MiB budget before you build, with warnings as
  you get close.
- Burns the ISO to physical media with your platform's native burner: `hdiutil
  burn` on macOS, `isoburn.exe` on Windows, `xorriso -as cdrecord` on Linux.

The syslinux pieces the boot menu needs (`isolinux.bin`, `menu.c32`, and
friends) are downloaded from kernel.org on the first build and cached locally.
No manual setup.

## Install

The fastest path is a prebuilt binary. No Python, no `pip`, no `uv`.

### Prebuilt binary (recommended)

Grab the build for your platform from the
[Releases page](https://github.com/pacnpal/floppybootcd/releases/latest).
`xorriso` is already inside every prebuilt, so there is nothing else to
install.

**macOS.** Pick `macos-universal2` if you are not sure which Mac you have; it
runs natively on both Apple Silicon and Intel. As of **v1.3.2** every macOS zip
is code-signed with an Apple Developer ID and notarized by Apple, so there is
nothing to strip: unzip it, move it wherever you like, and open it. Gatekeeper
lets it through on the first double-click.

Verify the signature yourself if you want to:

```bash
spctl --assess --type exec --verbose=4 FloppyBootCD.app
# source=Notarized Developer ID
```

On **v1.3.1 and older** the builds were unsigned and macOS 15 blocks unsigned
downloads outright, so those need the quarantine flag stripped once before the
first launch:

```bash
xattr -dr com.apple.quarantine FloppyBootCD.app
```

**Windows.** Unzip it somewhere (for example `C:\Tools\`) and run it. There are
separate x86_64 and ARM64 builds; the ARM64 build runs the x86_64 `xorriso`
under Windows 11's built-in x64 emulator, which is the supported setup.

**Linux.** Four formats, pick one:

- `.AppImage`, universal, no install. `chmod +x` it and run.
- `.deb` for Debian, Ubuntu, Raspberry Pi OS, Mint, Pop!_OS.
- `.rpm` for Fedora, RHEL, Rocky, Alma, openSUSE.
- a raw `.tar.gz`, any distro, no package manager.

The x86_64 build needs glibc 2.35 or newer (Ubuntu 22.04, Debian 12, Fedora 36).
The ARM64 build needs glibc 2.39 (Ubuntu 24.04, Debian 13). Older distros should
install from source.

### From source (uv)

Works on any platform with Python. Install [uv](https://docs.astral.sh/uv/),
install `xorriso`, then install FloppyBootCD as a uv tool:

```bash
uv tool install floppybootcd
```

`xorriso` is the one system dependency when you install from source:

- macOS: `brew install xorriso`
- Debian / Ubuntu / Raspberry Pi OS: `sudo apt install xorriso`
- Fedora / RHEL: `sudo dnf install xorriso`
- Arch: `sudo pacman -S libisoburn`
- Windows: `scoop install xorriso`

## Using the GUI

Launch the app (or run `floppybootcd` with no arguments). The flow is:

1. Add your floppy images. Drag them in, or use the Add button. Drop a folder
   and it picks up the images inside.
2. Edit the menu label for each entry if you want something friendlier than the
   filename.
3. Reorder the entries and pick which one boots by default.
4. Watch the capacity meter so you stay under 700 MiB.
5. Build the ISO, then burn it or attach it to a VM.

Projects save as `.fbcd` files, so you can come back and rebuild or tweak a
collection later.

## Using the CLI

```text
floppybootcd [PATH ...]                       launch the GUI, optionally opening paths
floppybootcd gui [PATH ...]                   explicit GUI launch
floppybootcd validate <project.fbcd>          run the pre-build project checks
floppybootcd inspect <project.fbcd> [--json]  print a project summary
floppybootcd build <project.fbcd> <out.iso>   build an ISO without the GUI
floppybootcd --help
floppybootcd --version
```

`build` takes two options: `--xorriso <path>` to use a specific `xorriso`, and
`--keep-staging` to leave the temporary build directory in place for debugging.

Examples:

```bash
# Validate a project in a script
floppybootcd validate my-collection.fbcd

# Machine-readable summary
floppybootcd inspect my-collection.fbcd --json

# Headless build
floppybootcd build my-collection.fbcd ./dist/my-collection.iso
```

Exit codes: `0` success, `1` a command failure such as a load or build error,
`2` validation failed or a CLI usage error.

## Links

- Source: <https://github.com/pacnpal/floppybootcd>
- Releases: <https://github.com/pacnpal/floppybootcd/releases>
- Issues: <https://github.com/pacnpal/floppybootcd/issues>
