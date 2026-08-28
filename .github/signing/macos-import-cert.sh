#!/usr/bin/env bash
#
# Import the Developer ID Application certificate into a throwaway keychain
# for the duration of this CI job.
#
# Reads (all optional — absence is a clean no-op so fork PRs and
# secret-less repos still build):
#   MACOS_CERT_P12       base64 of the exported .p12
#   MACOS_CERT_PASSWORD  export password for that .p12
#   KEYCHAIN_PASSWORD    password for the temporary keychain
#
#   MACOS_SIGNING_REQUIRED  set non-empty to turn that no-op into a hard
#                        failure. release.yml sets it for pushed v* tags,
#                        so a release can never silently ship unsigned.
#
# The keychain lives in $RUNNER_TEMP and is removed again by
# macos-cleanup-keychain.sh. The login keychain is never touched.

set -euo pipefail

if [ -z "${MACOS_CERT_P12:-}" ]; then
  if [ -n "${MACOS_SIGNING_REQUIRED:-}" ]; then
    echo "ERROR: MACOS_CERT_P12 is not set, but signing is required for" >&2
    echo "       this build (MACOS_SIGNING_REQUIRED is set). Falling back" >&2
    echo "       to an ad-hoc signature would publish a release that" >&2
    echo "       Gatekeeper blocks. Check the repo's signing secrets." >&2
    exit 1
  fi
  echo "MACOS_CERT_P12 is not set — skipping certificate import."
  echo "Builds will fall back to an ad-hoc signature."
  exit 0
fi

: "${RUNNER_TEMP:?RUNNER_TEMP must be set}"
KEYCHAIN="$RUNNER_TEMP/floppybootcd-signing.keychain-db"
KEYCHAIN_PASSWORD="${KEYCHAIN_PASSWORD:?KEYCHAIN_PASSWORD must be set}"
CERT_PATH="$RUNNER_TEMP/floppybootcd-cert.p12"

cleanup_cert() { rm -f "$CERT_PATH"; }
trap cleanup_cert EXIT

printf '%s' "$MACOS_CERT_P12" | base64 --decode > "$CERT_PATH"

# Recreate from scratch so a re-run of the job is idempotent.
security delete-keychain "$KEYCHAIN" 2>/dev/null || true
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
# -lut 21600: auto-lock after 6h idle, which is far longer than any job.
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"

security import "$CERT_PATH" \
  -k "$KEYCHAIN" \
  -P "${MACOS_CERT_PASSWORD:-}" \
  -T /usr/bin/codesign \
  -T /usr/bin/security

# Without this, codesign hits an interactive "allow access to key?" prompt
# that no one is there to click, and the job hangs until it times out.
security set-key-partition-list \
  -S apple-tool:,apple:,codesign: \
  -s -k "$KEYCHAIN_PASSWORD" \
  "$KEYCHAIN" >/dev/null

# Prepend our keychain to the search list, keeping the existing entries so
# nothing else on the runner breaks.
existing=$(security list-keychains -d user | sed -e 's/^[[:space:]]*"//' -e 's/"$//')
# shellcheck disable=SC2086
security list-keychains -d user -s "$KEYCHAIN" $existing

echo "Imported signing identities:"
security find-identity -v -p codesigning "$KEYCHAIN"
