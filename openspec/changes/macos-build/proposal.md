# Proposal: a signed macOS build in every release

## Why

Issue #32: ESO has a Mac client that writes the same `Encounter.log`, and the app offers Mac players nothing. The issue's plan of 2026-10-24 was parked on 2026-10-31 "until a Mac player can test a build", with five decisions open.

This change picks it up on 2026-11-15 with a spike on the maintainer's own Mac (Apple Silicon, macOS 27.2.1), which changes three of the issue's premises and adds work it did not list:

- **There is a Mac to test on.** ESO is installed on it through Steam (`appmanifest_306130.acf`, `The Elder Scrolls Online (Steam).app`), Rosetta works, and `~/Documents/Elder Scrolls Online/live/` exists. Logging has never been on there: it has no `Logs` folder.
- **The app can be signed and notarized.** The keychain holds a `Developer ID Application: Christopher Gentle (6PYDVRQUV5)` certificate valid until 2031-03-29. The issue assumed an unsigned build and the "damaged" Gatekeeper route.
- **The app builds and starts today.** With a `BUNDLE` added to the spec, PyInstaller 6.22.3 makes a 103 MB `ESO Log Tail.app` (52 MB zipped) that stays up against the test fixture and against a real 496 MB log, with a clean `crash.log`.
- **It does not yet behave right.** Ten of the suite's 2,715 tests fail on macOS, from two causes in the keyboard handling, and the spike found more differences the issue does not mention (see [design.md](design.md)).
- **The oldest macOS it runs on is not known.** The issue says 14. The PySide6 wheel's own libraries are built for 26.

An independent review of the first draft found five faults in its CI and release steps; this version carries the corrections.

## What Changes

Three pull requests, in this order, so that a new and unproven build job never stands between a Windows fix and its release:

**PR 1, the app behaves right on macOS** (no release asset yet):

- Return and Enter open a table row on macOS; Alt-letter tab keys work; shortcut texts name the Mac's keys; three shortcuts move off keys macOS gives a meaning (⌘H, ⌘, and ⌘.).
- Fonts are chosen per platform; *Show in folder* selects the file in Finder.
- The archive's in-use guard works on macOS, and an opt-in delete is refused, and said to be, when the guard cannot tell.
- The update check knows the Mac asset. The tests pass on macOS.

**PR 2, CI builds the app** (not part of a release, and not run for tags):

- `esolog-tail.spec` makes `ESO Log Tail.app` on macOS; `scripts/create_icon.py` writes `icon.icns`.
- A `build-macos` job runs the tests and builds an ad-hoc-signed zip on every pull request; a `smoke-macos` job starts that zip on each hosted macOS version. Its first run settles the oldest macOS the build supports.

**PR 3, releases carry it** (after the secrets and a tag rule exist and PR 2's jobs have been green on several runs):

- A `sign-macos` job, the only one that sees the certificate, signs the built zip with the Developer ID certificate, notarizes and staples it. It is tried on `main` by hand before any tag depends on it.
- The release publishes `esolog-tail-macos-arm64-<version>.zip` as a fourth file.
- `scripts/promote_release.py`, `scripts/release.py` and `scripts/build_site.py` learn the fourth file without blocking the betas and the Stable release that predate it.
- README, user guide, development guide, home page, changelog fragment. The build is labelled experimental until the maintainer has run a live session on it.

## Decisions needed from the maintainer

The issue's five, with what the spike now recommends, and two new ones. [design.md](design.md) has the reasoning.

| # | Decision | Recommendation |
|---|---|---|
| 1 | Architecture | arm64 only. An Intel or universal2 build needs python.org's universal2 Python in CI; add it when someone asks. |
| 2 | Signing | **Changed:** sign with the Developer ID certificate and notarize. Needs from the maintainer: a `.p12` export, an App Store Connect API key, a GitHub environment for the five secrets, and a rule that only the maintainer may create `v*` tags (none exists today). Optional: a required reviewer on that environment, one click per release. |
| 3 | Blocking | The Mac jobs block a release, as Linux does, but only from PR 3. Until then they do not run for tags at all. |
| 4 | Format | A zip of the `.app` made with `ditto`. |
| 5 | Who tests | **Changed:** the maintainer, on this Mac: the look, keys and a live session during PR 1 and 2, Gatekeeper and the privacy prompts from the first beta's downloaded zip. |
| 6 | Qt style (new) | Decide on screen in PR 1: the native style, or Fusion if the native one shows the defects the spike's captures suggest. |
| 7 | Oldest macOS (new) | Whatever CI proves: macOS 15 if the tests and the built app pass on the `macos-15` runner, otherwise macOS 26. Not the 14 the issue states. |

**Answered by the maintainer on 2026-11-16:** decisions 1 to 5 as recommended. Decision 6 was answered the same day by task 1.1: the native style. Decision 7 is answered by task 2.6. For decision 2, the Developer Program agreement for team `6PYDVRQUV5` was signed that day and the account is not yet active: the certificate in the keychain is valid and signs locally, and notarization and the App Store Connect API key wait for activation.

## Capabilities

### New Capabilities

- `macos-build`: the app as a signed, notarized macOS bundle in every release, and the behaviour that differs on macOS.

### Modified Capabilities

(none; `app-updates` gains a platform, which its requirements already cover: "this platform's asset")

## Impact

- PR 1: `src/esolog_gui.py`, `src/gui/main_window.py`, `src/gui/fight_tabs.py`, `src/gui/player_window.py`, `src/gui/events_tab.py`, `src/gui/positions_window.py`, `src/gui/fight_list.py`, `src/gui/settings_dialog.py`, `src/gui/text_size.py`, `src/gui/glyphs.py`, `src/gui/death_render.py`, `src/log_archiver.py`, `src/update_check.py`; a new `src/gui/keys.py`; their tests.
- PR 2: `esolog-tail.spec`, `scripts/create_icon.py`, `.gitignore`, `.github/workflows/build-installers.yml`, a new `scripts/smoke_macos.py`.
- PR 3: the workflow again, `scripts/promote_release.py`, `scripts/release.py`, `scripts/build_site.py`, `site/index.html`, `README.md`, `docs/user-guide.md`, `docs/development.md`, `changelog.d/32-macos-build.md`; a GitHub environment with five secrets and a tag ruleset, both set up by the maintainer.
- Not in this change: a fix for `damage_kinds.TARGET_TABLE_PATH`, which no frozen build on any platform can find (a separate issue; see design.md, "Found on the way").
