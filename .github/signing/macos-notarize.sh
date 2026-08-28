#!/usr/bin/env bash
#
# Notarize a zipped .app with Apple, staple the ticket to the bundle, and
# re-zip so the published asset carries the ticket.
#
#   usage: macos-notarize.sh <path-to-.app> <path-to-zip>
#
# Reads (all three required to do anything — absence is a clean no-op):
#   APPLE_API_KEY_P8      base64 of the App Store Connect .p8 private key
#   APPLE_API_KEY_ID      the key's Key ID
#   APPLE_API_ISSUER_ID   the issuer UUID of the App Store Connect team
#
#   MACOS_SIGNING_REQUIRED  set non-empty to turn that no-op into a hard
#                       failure. release.yml sets it for pushed v* tags, so
#                       a release can never silently ship un-notarized.
#
# Why re-zip: notarytool accepts a zip, but the ticket staples to the .app,
# not to the archive around it. Stapling then re-zipping is what makes the
# download work on a Mac that is offline or behind a firewall — without a
# stapled ticket Gatekeeper has to reach Apple to verify on first launch.

set -euo pipefail

APP="${1:?usage: macos-notarize.sh <path-to-.app> <path-to-zip>}"
ZIP="${2:?usage: macos-notarize.sh <path-to-.app> <path-to-zip>}"

if [ ! -d "$APP" ]; then
  echo "ERROR: no such bundle: $APP" >&2
  exit 1
fi
if [ ! -f "$ZIP" ]; then
  echo "ERROR: no such archive: $ZIP" >&2
  exit 1
fi

if [ -z "${APPLE_API_KEY_P8:-}" ] || [ -z "${APPLE_API_KEY_ID:-}" ] \
   || [ -z "${APPLE_API_ISSUER_ID:-}" ]; then
  if [ -n "${MACOS_SIGNING_REQUIRED:-}" ]; then
    echo "ERROR: notarization credentials are not configured, but this" >&2
    echo "       build requires them (MACOS_SIGNING_REQUIRED is set)." >&2
    echo "       Gatekeeper blocks a signed-but-un-notarized app on first" >&2
    echo "       launch, so publishing this would break the install docs." >&2
    echo "       Check APPLE_API_KEY_P8 / APPLE_API_KEY_ID /" >&2
    echo "       APPLE_API_ISSUER_ID." >&2
    exit 1
  fi
  echo "Notarization credentials not configured — skipping notarization."
  if [ -n "${MACOS_SIGN_IDENTITY:-}" ]; then
    echo "This artifact is Developer ID signed but NOT notarized;"
    echo "Gatekeeper will still block it on first launch."
  else
    echo "This artifact is ad-hoc signed only."
  fi
  exit 0
fi

: "${RUNNER_TEMP:=${TMPDIR:-/tmp}}"
KEY_PATH="$RUNNER_TEMP/floppybootcd-notary-key.p8"
SUBMIT_LOG="$RUNNER_TEMP/floppybootcd-notarytool.log"

cleanup_key() { rm -f "$KEY_PATH"; }
trap cleanup_key EXIT

printf '%s' "$APPLE_API_KEY_P8" | base64 --decode > "$KEY_PATH"

echo "Submitting $ZIP to Apple's notary service..."
if ! xcrun notarytool submit "$ZIP" \
      --key "$KEY_PATH" \
      --key-id "$APPLE_API_KEY_ID" \
      --issuer "$APPLE_API_ISSUER_ID" \
      --wait \
      --timeout 30m 2>&1 | tee "$SUBMIT_LOG"; then
  echo ""
  echo "ERROR: notarization failed. Fetching the notary log..." >&2
  submission_id=$(grep -Eo '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}' \
                    "$SUBMIT_LOG" | head -1 || true)
  if [ -n "$submission_id" ]; then
    xcrun notarytool log "$submission_id" \
      --key "$KEY_PATH" \
      --key-id "$APPLE_API_KEY_ID" \
      --issuer "$APPLE_API_ISSUER_ID" >&2 || true
  fi
  exit 1
fi

# `--wait` returns 0 for a completed submission even when Apple rejected
# it, so check the status text rather than trusting the exit code alone.
if ! grep -q 'status: Accepted' "$SUBMIT_LOG"; then
  echo "ERROR: notarization did not come back Accepted." >&2
  submission_id=$(grep -Eo '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}' \
                    "$SUBMIT_LOG" | head -1 || true)
  if [ -n "$submission_id" ]; then
    xcrun notarytool log "$submission_id" \
      --key "$KEY_PATH" \
      --key-id "$APPLE_API_KEY_ID" \
      --issuer "$APPLE_API_ISSUER_ID" >&2 || true
  fi
  exit 1
fi

echo "Stapling the notarization ticket to $APP..."
xcrun stapler staple "$APP"
xcrun stapler validate "$APP"

echo "Re-zipping $ZIP so the published asset carries the stapled ticket..."
zip_dir="$(cd "$(dirname "$ZIP")" && pwd)"
zip_name="$(basename "$ZIP")"
app_dir="$(cd "$(dirname "$APP")" && pwd)"
app_name="$(basename "$APP")"
rm -f "$zip_dir/$zip_name"
( cd "$app_dir" && ditto -c -k --keepParent --sequesterRsrc "$app_name" "$zip_dir/$zip_name" )

echo "--- Gatekeeper assessment ---"
spctl --assess --type exec --verbose=4 "$APP"
echo "Notarized, stapled and re-packaged: $zip_dir/$zip_name"
