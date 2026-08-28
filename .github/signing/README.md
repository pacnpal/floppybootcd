# macOS code signing and notarization

This directory holds everything the release workflow needs to ship
Developer ID–signed, Apple-notarized macOS builds:

| File | Purpose |
|------|---------|
| `floppybootcd.entitlements` | Hardened-runtime exceptions CPython + PySide6 need to launch at all. |
| `macos-import-cert.sh` | Imports the Developer ID certificate into a throwaway CI keychain. |
| `macos-sign.sh` | Signs a `.app` inside-out (nested Mach-O → nested bundles → the app). |
| `macos-notarize.sh` | Submits the zip to Apple, staples the ticket to the `.app`, re-zips. |
| `macos-cleanup-keychain.sh` | Deletes the temporary keychain, always. |

**Nothing here is required to build.** With no secrets configured — fork
PRs, or before the maintainer sets them up — the import is a no-op, the
bundle gets the same ad-hoc signature it always had, and notarization is
skipped with a log message. Signing turns itself on when the secrets
exist.

**Except on a release.** `release.yml` sets `MACOS_SIGNING_REQUIRED=1` for
a pushed `v*` tag, and every script above turns its clean no-op into a
hard failure when that is set. A tag build therefore fails fast — before
anything reaches the Release page — if the signing tooling is missing or
any of `MACOS_CERT_P12`, `MACOS_SIGN_IDENTITY`, `APPLE_API_KEY_P8`,
`APPLE_API_KEY_ID`, or `APPLE_API_ISSUER_ID` is unset. This is what lets
the install docs state flatly that v1.3.2 and later are signed and
notarized: the fallback that would quietly contradict them can't happen on
a release. Every other trigger — pull requests, `workflow_dispatch`
smoke-tests, forks — keeps the graceful degradation described above.

## What you need before any of this works

An **Apple Developer Program** membership: <https://developer.apple.com/programs/enroll/>
— **$99/year**, and there is no free tier that can notarize. Enrollment
takes anywhere from a few hours to a few days (Apple verifies your
identity, and for an organization, your D-U-N-S number).

## Step 1 — Create the Developer ID Application certificate

The certificate type must be **Developer ID Application**. *Apple
Development* and *Apple Distribution* certificates cannot notarize apps
distributed outside the Mac App Store.

On a Mac:

1. **Keychain Access → Certificate Assistant → Request a Certificate From
   a Certificate Authority.** Enter your email, leave "CA Email Address"
   blank, choose **Saved to disk**, and check **Let me specify key pair
   information** (2048 bits, RSA). Save the `.certSigningRequest` file.
2. Go to <https://developer.apple.com/account/resources/certificates/list>
   → **+** → **Developer ID Application** → upload the CSR → **Download**
   the resulting `.cer`.
3. Double-click the `.cer` to add it to your login keychain.
4. In Keychain Access, find **Developer ID Application: … (TEAMID)**,
   expand it so both the certificate *and* its private key are selected,
   right-click → **Export 2 items…** → save as `.p12` and set a password.
   *Remember that password* — it becomes `MACOS_CERT_PASSWORD`.

Then base64-encode the `.p12` for GitHub (it must be one line, no
newlines):

```bash
base64 -i DeveloperID.p12 | tr -d '\n' | pbcopy   # now in your clipboard
```

And get the exact identity string to use as `MACOS_SIGN_IDENTITY`:

```bash
security find-identity -v -p codesigning
#   1) ABCD…  "Developer ID Application: Your Name (A1B2C3D4E5)"
#                ^ copy the text inside the quotes, exactly
```

## Step 2 — Create an App Store Connect API key for notarization

An API key is used instead of an Apple ID + app-specific password so CI
never holds account credentials and nothing breaks when 2FA changes.

1. Go to <https://appstoreconnect.apple.com/access/integrations/api>
   (**Users and Access → Integrations → App Store Connect API → Team
   Keys**).
2. **+** → name it e.g. `floppybootcd-notarization` → access role
   **Developer** → **Generate**.
3. Download the `AuthKey_XXXXXXXXXX.p8`. **Apple lets you download it
   once.** Save it somewhere safe.
4. From that page, note the **Key ID** (the `XXXXXXXXXX` in the filename)
   and the **Issuer ID** (a UUID shown above the key list).

Base64-encode the key the same way:

```bash
base64 -i AuthKey_XXXXXXXXXX.p8 | tr -d '\n' | pbcopy
```

## Step 3 — Add the repository secrets

**Settings → Secrets and variables → Actions → New repository secret**
(<https://github.com/pacnpal/floppybootcd/settings/secrets/actions>):

| Secret | Value | From |
|--------|-------|------|
| `MACOS_CERT_P12` | base64 of the `.p12` | Step 1.4 |
| `MACOS_CERT_PASSWORD` | the `.p12` export password | Step 1.4 |
| `MACOS_SIGN_IDENTITY` | `Developer ID Application: Your Name (TEAMID)` | Step 1, `security find-identity` |
| `APPLE_API_KEY_P8` | base64 of the `.p8` | Step 2.3 |
| `APPLE_API_KEY_ID` | the 10-character Key ID | Step 2.4 |
| `APPLE_API_ISSUER_ID` | the issuer UUID | Step 2.4 |

Signing and notarization are independent: set only the first three and
builds are signed but not notarized (Gatekeeper still blocks them — the
workflow says so in its log). Set all six for the full path.

## Step 4 — Test without cutting a release

`workflow_dispatch` runs never publish to a Release — the publish job
requires `github.event_name == 'push'` *and* a `refs/tags/v*` ref, so even
dispatching the workflow with a tag as its ref (`gh workflow run --ref
v1.2.0`) can't touch an existing Release. A manual run is therefore a safe
end-to-end test:

**Actions → Release Binaries → Run workflow**, leaving the tag input
blank. Then check:

- *Codesign macOS .app* logs `Signing … with: Developer ID Application: …`
  and `codesign --verify` passes.
- *Notarize and staple …* logs `status: Accepted`, then
  `spctl --assess` prints `source=Notarized Developer ID`.
- Download the run's artifact on a Mac and confirm it opens by
  double-click with no Gatekeeper warning and no `xattr` step.

If the app is notarized but **crashes on launch** with a message citing
`code signature ... library load disallowed` (or Console shows a
`CODESIGNING` kill), a bundled library is being loaded that isn't signed
with your Team ID. The scripts sign every Mach-O they can identify, so
this means a new dependency ships code `file` doesn't report as Mach-O, or
loads something from outside the bundle. The escape hatch is adding

```xml
<key>com.apple.security.cs.disable-library-validation</key>
<true/>
```

to `floppybootcd.entitlements` — but find out which library first: that
entitlement is deliberately absent (see the comment in that file), because
re-signing dependencies is Apple's recommended alternative and this
pipeline already does it.

If notarization is rejected, the workflow prints Apple's full notary log,
which names the offending binary and reason (almost always a missing
`--options runtime`, a missing secure timestamp, or an unsigned nested
binary — all three are handled by `macos-sign.sh`, so a failure here
usually means a new binary got copied into the bundle *after* the signing
step).

## Where signing sits in the pipeline, and why

The signing scripts are checked out separately from the source tree, into
`.signing-tooling/`, at `github.ref` rather than at the revision being
built. A `workflow_dispatch` run can select a historical tag that predates
signing; without the separate checkout the scripts would simply be absent
from the workspace. When they are unavailable anyway (dispatching *on* a
pre-signing ref), the macOS steps skip with a warning and the bundles keep
their ad-hoc signature — except universal2, which falls back to an explicit
ad-hoc signature, since the `lipo`-merged bundle is unsigned at that point
and an unsigned bundle will not launch on Apple Silicon at all.

`release.yml` mutates the `.app` after PyInstaller builds it: it patches
`Contents/Info.plist` with the `.fbcd` document types, copies the xorriso
bundle into `Contents/Resources/bin/`, and (for universal2) `lipo`-merges
every Mach-O. **Each of those invalidates a signature.** So signing is
always the last thing before `ditto`, and PyInstaller's own
`--codesign-identity` flag is deliberately unused.

The universal2 bundle is signed and notarized separately from the two
per-arch bundles: `lipo`-merging two already-signed thin binaries does not
produce a validly signed fat one, and Apple issues a notarization ticket
per artifact.

## Rotation and expiry

Developer ID certificates last 5 years; App Store Connect keys don't
expire but can be revoked. When either is replaced, redo the relevant
step above and update the secrets — nothing in the workflow needs to
change. Already-notarized releases keep working: a stapled ticket
survives the certificate's expiry.
