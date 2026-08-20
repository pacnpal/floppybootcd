#!/usr/bin/env bash
#
# Sign a macOS .app bundle inside-out.
#
#   usage: macos-sign.sh <path-to-.app>
#
# Reads:
#   MACOS_SIGN_IDENTITY  e.g. "Developer ID Application: Name (TEAMID)".
#                        Unset  -> ad-hoc signature (the pre-signing
#                                  behaviour: loadable, but Gatekeeper
#                                  still requires the xattr workaround).
#                        Set    -> hard failure if the identity isn't in
#                                  the keychain, so a misconfigured secret
#                                  can never silently ship an unsigned
#                                  release.
#
# This has to run as the LAST step before the bundle is zipped. Every
# mutation of the bundle after signing (Info.plist edits, copying xorriso
# into Contents/Resources, lipo-merging Mach-O files) invalidates the
# signature, so signing earlier — including via PyInstaller's
# --codesign-identity — would be undone by the steps that follow it.

set -euo pipefail

APP="${1:?usage: macos-sign.sh <path-to-.app>}"
SIGNING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENTITLEMENTS="$SIGNING_DIR/floppybootcd.entitlements"

if [ ! -d "$APP" ]; then
  echo "ERROR: no such bundle: $APP" >&2
  exit 1
fi
if [ ! -f "$ENTITLEMENTS" ]; then
  echo "ERROR: entitlements file not found: $ENTITLEMENTS" >&2
  exit 1
fi

IDENTITY="${MACOS_SIGN_IDENTITY:-}"

if [ -n "$IDENTITY" ]; then
  if ! security find-identity -v -p codesigning | grep -qF "$IDENTITY"; then
    echo "ERROR: MACOS_SIGN_IDENTITY is set to:" >&2
    echo "         $IDENTITY" >&2
    echo "       but no such code-signing identity is in the keychain." >&2
    echo "       Available identities:" >&2
    security find-identity -v -p codesigning >&2 || true
    echo "       Check the MACOS_SIGN_IDENTITY / MACOS_CERT_P12 secrets." >&2
    exit 1
  fi
  echo "Signing $APP with: $IDENTITY"
  # --timestamp and --options runtime are both mandatory for notarization.
  SIGN_ARGS=(--force --timestamp --options runtime
             --entitlements "$ENTITLEMENTS" --sign "$IDENTITY")
else
  echo "MACOS_SIGN_IDENTITY not set — applying an ad-hoc signature."
  echo "The bundle will load, but Gatekeeper will still require:"
  echo "  xattr -dr com.apple.quarantine $(basename "$APP")"
  SIGN_ARGS=(--force --sign -)
fi

# Finder metadata and resource forks make codesign fail with "resource fork,
# Finder information, or similar detritus not allowed".
xattr -cr "$APP"

# Inside-out, in three passes. --deep is deliberately NOT used: Apple
# deprecates it, and it does not apply entitlements to nested binaries.
#
# Pass 1 — every Mach-O file in the bundle.
files_signed=0
while IFS= read -r -d '' f; do
  if ! file -b "$f" 2>/dev/null | grep -q 'Mach-O'; then
    continue
  fi
  codesign "${SIGN_ARGS[@]}" "$f"
  files_signed=$((files_signed + 1))
done < <(find "$APP" -type f -not -type l -print0)

# Pass 2 — nested bundles (Qt .frameworks, helper .apps), deepest first, so
# each one's Info.plist and Resources are re-sealed after its binaries were
# signed in pass 1. -depth makes find emit a directory after its contents.
#
# PyInstaller sometimes emits a flattened framework layout that codesign
# refuses to treat as a bundle ("bundle format unrecognized, invalid, or
# unsuitable"). That is not fatal: the binary inside was already signed in
# pass 1, which is what PyInstaller's own signing does. Warn and continue
# rather than failing the release — notarization is the backstop and it
# reports precisely which component it objected to.
bundles_signed=0
bundles_skipped=0
while IFS= read -r -d '' d; do
  [ "$d" = "$APP" ] && continue
  if codesign "${SIGN_ARGS[@]}" "$d" 2>/tmp/codesign-nested.err; then
    bundles_signed=$((bundles_signed + 1))
  else
    echo "WARNING: could not seal nested bundle ${d#"$APP/"}:"
    sed 's/^/         /' /tmp/codesign-nested.err
    echo "         Its Mach-O binaries are signed; continuing."
    bundles_skipped=$((bundles_skipped + 1))
  fi
done < <(find "$APP" -depth -type d \( -name '*.framework' -o -name '*.app' \) -print0)
rm -f /tmp/codesign-nested.err

# Pass 3 — the bundle itself, last.
codesign "${SIGN_ARGS[@]}" "$APP"

echo "Signed $files_signed Mach-O file(s), $bundles_signed nested bundle(s) ($bundles_skipped skipped), plus $APP."

echo "--- codesign --verify ---"
codesign --verify --deep --strict --verbose=2 "$APP"

echo "--- codesign -dv ---"
codesign -dv --verbose=4 "$APP" 2>&1 | sed -n '1,15p'
