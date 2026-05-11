# Classic UI edition

This repository now includes a **classic compatibility UI** entry point (`floppybootcd-classic`) built with Python's standard-library Tkinter.

## Drift policy

The classic UI is allowed to drift from the Qt UI in `floppybootcd.app`.

- Qt remains the feature-first frontend.
- Classic remains the compatibility-first frontend.
- Backward compatibility and low dependency pressure are prioritized over feature parity in classic.

## Compatibility targets

Current classic targets are intentionally conservative:

- Python: **3.10+**
- GUI stack: **Tkinter only** (stdlib)
- OS baseline for CI: **Ubuntu 22.04**, **macOS 13**, **Windows 2022** runners

## Compatibility contract

The classic edition guarantees:

1. Open/save `.fbcd` projects.
2. Add floppy images/files/folders and deduplicate them.
3. Build ISOs through the shared `floppybootcd.core` backend.

The classic edition does **not** guarantee full parity with Qt-only UX features.

## Suggested branch model

If you want long-lived divergence, maintain a dedicated branch such as `classic-ui`.

- Cherry-pick core/backend fixes into both branches.
- Treat UI changes as independent unless needed for shared behavior.
- Keep tests for classic in `tests/classic/` so compatibility coverage can evolve independently.
