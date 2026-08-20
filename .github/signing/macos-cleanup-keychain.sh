#!/usr/bin/env bash
#
# Remove the temporary signing keychain created by macos-import-cert.sh.
# Runs with `if: always()` so a failed build never leaves a keychain
# holding the Developer ID private key on a (recycled) runner.

set -uo pipefail

KEYCHAIN="${RUNNER_TEMP:-/tmp}/floppybootcd-signing.keychain-db"

if [ -f "$KEYCHAIN" ]; then
  security delete-keychain "$KEYCHAIN" 2>/dev/null \
    && echo "Deleted temporary signing keychain." \
    || echo "Could not delete $KEYCHAIN (already gone?)."
else
  echo "No temporary signing keychain to clean up."
fi

rm -f "${RUNNER_TEMP:-/tmp}/floppybootcd-cert.p12" \
      "${RUNNER_TEMP:-/tmp}/floppybootcd-notary-key.p8"
exit 0
