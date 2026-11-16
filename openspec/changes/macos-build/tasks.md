# Tasks

The spike's files are in the worktree `macos-port-32`, uncommitted: the `BUNDLE` in `esolog-tail.spec` (marked `SPIKE`), an untracked `icon.icns`, and under `build/spike/` (ignored) `smoke.py`, `lsof_probe.py`, `dock_icon_probe.py` and the captures. Build a local bundle with `.venv/bin/python -m PyInstaller esolog-tail.spec --noconfirm`; it is for this Mac only (design.md, decision 7).

## 0. Before any code

- [x] 0.1 The maintainer answers the seven decisions in proposal.md. Decisions 6 and 7 are answered by tasks 1.1 and 2.6; decision 2 is needed before PR 3. (Answered 2026-11-16: 1 to 5 as recommended.)
- [x] 0.2 Open an issue for `damage_kinds.TARGET_TABLE_PATH` (design.md, "Found on the way"). It affects the Windows and Linux builds released today, so it should not wait for this change. (#237)

## 1. PR 1: the app behaves right on macOS

Done when: `python -m pytest tests/ -q` passes on macOS (run by hand; CI has no Mac job yet) and on Windows and Linux CI; manual checks 1 to 6 are recorded on issue #32.

State on 2026-11-16: 1.2 to 1.11 are written; the suite passes on this Mac (2759 passed, 17 skipped; 10 failed before). Not yet run on Windows or Linux. An independent review found nothing above low; its findings are fixed except one that predates this change (an archive whose config save or listener raises after the delete was marked says "failed" though the log is gone, on every platform). Manual checks 1, 4 and 5 are done; 2, 3 and 6 are skipped on the maintainer's word (design.md, "Manual checks"), so what they cover is unverified on a real Mac window until the second round after the first beta.

- [x] 1.1 Run `python src/esolog_gui.py` on the Mac and look at the native style, light and dark (manual check 1). Record the choice; if Fusion, `app.setStyle("Fusion")` on macOS in `src/esolog_gui.py`. (2026-11-16: the native style; no code. The maintainer chose it with the four combinations side by side on screen.)
- [x] 1.2 `src/gui/keys.py`: `on_row_activated(view, slot)` and `key_text(sequence)`; unit tests for both that patch `sys.platform`, so they run on every CI platform.
- [x] 1.3 `events_tab.py` and `positions_window.py` connect their rows through `on_row_activated`. The four Return tests pass on macOS.
- [x] 1.4 `qt_set_sequence_auto_mnemonic(True)` on macOS in `src/esolog_gui.py`, and in `tests/conftest.py`. The six Alt-letter tests pass on macOS.
- [x] 1.5 On macOS: *Hide names* is `Ctrl+Shift+H`; the positions window's speed keys are `Meta+,` and `Meta+.`. A test of each shortcut with `sys.platform` patched both ways.
- [x] 1.6 Every text given to `setToolTip`, `setPlaceholderText`, `setStatusTip`, `setAccessibleName` and `setAccessibleDescription`, and every `*_TIP`, `*_CUE` and `*_DESCRIPTION` constant, that names a key is built with `key_text`. The three tests that assert the Windows wording (`test_keyboard_gui.py:145`, `test_events_tab_gui.py:717`, `test_hide_names_gui.py:234`) compare against `key_text`. Two new tests. One runs on every platform: it reads `src/gui/` as syntax trees and fails on a string literal holding `Ctrl+` or `Alt+` passed to one of those setters, to `showMessage`, or assigned to one of those constants. The other runs on macOS, where native and Windows wording differ: it walks the widgets of the main window, the player window and the positions window and fails on a tooltip, placeholder or accessible name that still holds `Ctrl+` or `Alt+`.
- [x] 1.7 Skip `setWindowIcon` on macOS (design.md, row f).
- [x] 1.8 The skull's font list in `glyphs.py` and the fixed font in `text_size.py` are chosen per platform. On macOS no start-up warning names *Segoe UI Symbol* or *Consolas* (assert on Qt's log in a test that runs on macOS).
- [x] 1.9 `reveal_file`: `open -R` on macOS; a test with the process call patched.
- [x] 1.10 `log_archiver.py`, as design.md's "The archive guard":
  - a holder check defined on every platform, with tests on every platform that patch `subprocess.run`: process ids, our own id only, exit 1 with both streams empty, exit 1 with a message on stderr, `FileNotFoundError`, a timeout;
  - the POSIX `_ExclusiveFile` uses it on macOS, and `mark_delete_on_close` asks again; tests on macOS beside the Linux ones (a child process holds the log; the holder gone; our own handle does not count; the check failing at delete time keeps the original);
  - `ArchiveEvent.kept_reason` and the status bar's line; a test of the line.
- [x] 1.11 `update_check.PLATFORM_ASSETS["darwin"]`; `tests/unit/test_update_check.py` asserts the Mac zip is chosen for `darwin`, and the "platform without a build" test moves to another platform name.
- [x] 1.12 Manual check 4 (does the Mac client hold the log open?) with the game running; record the answer in design.md. (2026-11-16: it does. `lsof` names the client, and the archive step skips with the in-use notice. Under "The archive guard" in design.md.)
- [x] 1.13 The `no-changelog` label: nothing changes for a Windows or Linux user, and no Mac build exists yet. If Fusion or a key change turns out to show on another platform, a fragment instead.

## 2. PR 2: CI builds the app

Done when: `build-macos` and every leg of `smoke-macos` are green on the pull request, with the matrix in the state task 2.6 settles; a tag's run is unchanged (the Mac jobs do not run for tags).

State on 2026-11-16: 2.1 to 2.5, 2.7 and 2.9 are written and pass on this Mac (design.md, "Built in PR 2"). 2.6 is settled by the first run of #240: every job passed. Open: 2.8, the maintainer's two checks on a locally built bundle.

- [x] 2.1 `esolog-tail.spec`: the `BUNDLE` for macOS (name, `icon.icns`, `com.brainsnorkel.esolog-tail`, version from `src/version.py`, `CFBundleVersion`, `NSHighResolutionCapable`, `LSMinimumSystemVersion`, `NSDocumentsFolderUsageDescription`, and the same sentence for Desktop, Downloads, removable and network volumes and cloud-provider files). No signing identity in the spec: the bundle is ad-hoc signed and `sign-macos` signs it later. Remove the `SPIKE` marks and the spike's two environment variables.
- [x] 2.2 `scripts/create_icon.py` writes `icon.icns` (16 to 1024 px) on a rounded-square plate; `icon.icns` in `.gitignore`.
- [x] 2.3 `scripts/smoke_macos.py` from `build/spike/smoke.py`: a scratch `HOME`, the fixture log, the update check off, the app's output to a file, 20 s, exit 1 on an early exit or a crash line, the output and `crash.log` printed either way. A unit test of its verdict on a stand-in executable that exits early, one that stays up, and one that writes a crash line.
- [x] 2.4 `build-macos` on `macos-15`, `if: ${{ !startsWith(github.ref, 'refs/tags/') }}`: the Linux job's steps, the stamp check (2.7), `ditto` to `esolog-tail-macos-arm64-<version>-unsigned.zip`, uploaded as the artifact `unsigned-macos-arm64` with `if-no-files-found: error`.
- [x] 2.5 `smoke-macos`, same `if`, a matrix of `macos-15`, `macos-26` and `xcode-27`, `fail-fast: false`: `sw_vers`, `spctl --status`, download, `ditto -x -k`, `codesign --verify --deep --strict`, `scripts/smoke_macos.py`.
- [x] 2.6 Read the first runs and settle three things, each recorded in design.md (a build that fails on `macos-15` skips the smoke job, so the newer images report only on the run after the build has moved):
  - `cocoa` starts on a hosted runner, or the smoke test uses `offscreen` with the comment design.md asks for;
  - Gatekeeper is on there, or the `spctl` check of task 3.3 is dropped;
  - the suite and the smoke test pass on `macos-15`, and `LSMinimumSystemVersion` is `15.0`; or they do not, and `build-macos` moves to `macos-26`, `macos-15` leaves the matrix, and the floor is `26.0`.
  - (2026-11-16, the first run of #240: `cocoa` starts on every leg; Gatekeeper is on on every leg; the suite and the smoke test pass on `macos-15`, so the floor is `15.0` and nothing moves. design.md, decision 7 and "Workflow shape".)
- [x] 2.7 The stamp check: list every binary's minimum macOS (`otool -l`), fail when Python's or OpenSSL's is above the floor, print PySide6's.
- [ ] 2.8 Manual checks 7 and 8 on a locally built bundle. If App Nap holds the app back, find the Info.plist key or call that stops it on macOS 27, add it to 2.1, and check again.
- [x] 2.9 `docs/development.md`: the spec row and the build section name macOS; how to build locally and why that bundle is not for distribution. `no-changelog`.

## 3. PR 3: releases carry it

Done when: the dry run on `main` produces a zip that `spctl` calls *Notarized Developer ID*; a tag then publishes four files; the home page still builds from the current Stable release; an older beta can still be promoted.

- [ ] 3.1 By hand, before the workflow is written: sign a local bundle with the Developer ID certificate, `ditto`, `xcrun notarytool submit --wait`, `xcrun stapler staple`; `spctl --assess --type execute -vv` says *Notarized Developer ID*. If the notary refuses, its log names the files; fix the signing before going on. (This uploads the app to Apple; it needs the maintainer's notary credentials, and the Developer Program account active: the agreement was signed on 2026-11-16 and activation was still to come.)
- [ ] 3.2 The maintainer: export certificate `B02AF647…` as a `.p12`; create the App Store Connect API key; create the `release-signing` environment, deploying from `v*` tags and `main`, with the five secrets; add a ruleset that lets only the maintainer create `v*` tags, before the secrets are stored; decide on a required reviewer.
- [ ] 3.3 `sign-macos` (design.md, "Workflow shape"): a checkout with `fetch-depth: 0`, the guard (on a tag with the tag; on the dry run with `v<version>` and the commit), the temporary keychain, `codesign --force --deep --options runtime --timestamp`, the check that every Mach-O file has the Developer ID authority and the runtime flag, zip, notarize, staple, zip as `esolog-tail-macos-arm64-<version>.zip`, the keychain deleted. `smoke-macos` gets the condition design.md writes out, takes the signed zip when `sign-macos` ran, and adds `stapler validate` and the `spctl` check for *Notarized Developer ID*.
- [ ] 3.4 `workflow_dispatch` gains the `sign` input; run it on `main`. Fix what it finds before any tag.
- [ ] 3.5 The Mac jobs run for tags; the release job has `build-macos`, `sign-macos` and `smoke-macos` in `needs`, downloads artifacts by the pattern `esolog-tail-*` (which leaves the unsigned zip out), and names the signed zip in `files`. A step before publishing fails if `dist/` holds a file ending `-unsigned.zip`.
- [ ] 3.6 `scripts/promote_release.py`: the base three files and the Mac zip as separate names; a beta must carry the Mac zip when the Stable release does; "three files" in its messages and docstring becomes "its files". Tests: Stable without a Mac zip, a beta with three files is promotable, and one with four; Stable with one, a beta with three is not.
- [ ] 3.7 `scripts/release.py`: the check after a tag asks for four files. Its test.
- [ ] 3.8 `scripts/build_site.py`: `macos_url` optional, `{{macos_link}}` empty when the Stable release has no Mac zip; `site/index.html` gains the placeholder in the "Also" line and the install paragraph. Tests: a release without the zip builds a page with no Mac link; one with it has the link. The page's "Windows and Linux" descriptions change in the pull request that follows the first Stable Mac build, not here.
- [ ] 3.9 README: an install option for macOS, marked experimental and "in beta releases until a Stable release carries it"; Requirements with the floor from 2.6; Troubleshooting. `docs/user-guide.md`: the config and crash-log folder, where the log is looked for, the Documents question, the Mac's keys (and Fn-↑ and Fn-↓ for Page Up and Down), *Start at login* and the score banner not offered, the update button opens the release page, the archive guard. `docs/development.md`: the release section names the build, sign and smoke jobs and four files, the environment and its secrets, the tag ruleset, the dry run, and the certificate's expiry (2031-03-29).
- [ ] 3.10 `changelog.d/32-macos-build.md`, with 0.5.1's Linux entry as the model.
- [ ] 3.11 Cut the beta. `python scripts/release.py --tag X.Y.Z --push --watch` reports four files.

## 4. After the first beta

- [ ] 4.1 The maintainer runs manual checks 9 to 12 from the downloaded zip and records each result on issue #32.
- [ ] 4.2 Fix what they find.
- [ ] 4.3 When a live session has run clean on a released build, it may be promoted like any other, and the page's Mac link appears with it. Then the page's descriptions name macOS. The "experimental" label comes off when the maintainer says so.
- [ ] 4.4 Archive this change; close #32.
