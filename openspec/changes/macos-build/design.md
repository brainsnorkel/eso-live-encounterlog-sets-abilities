# Design: a signed macOS build in every release

## Context

Issue #32 holds the first plan (2026-10-24) and the note that parked it (2026-10-31). This document replaces that plan. It rests on a spike of 2026-11-15 on the maintainer's Mac: Apple Silicon, macOS 27.2.1, Homebrew Python 3.14.10, PySide6-Essentials 6.12.0, PyInstaller 6.22.3, in the worktree `macos-port-32`. An independent review the same day, in two passes, found no fault in the measurements, five in the first draft's CI and release steps, and two in the revision (the unsigned zip could be published; the guard needs the full history). This version carries all of its corrections; the last of them have not been reviewed again.

Each fact below is marked **measured** (run in the spike), **read** (from the code or a vendor's page), or **unverified** (nobody has checked it; a task or a manual check covers it).

## What the spike measured

| What | Result |
|---|---|
| The test suite on macOS, offscreen | 2,688 passed, 17 skipped, **10 failed**, in 60 s (run twice, by the author and the reviewer) |
| The 10 failures | Two causes. Six: Alt-letter tab keys do nothing (Qt turns mnemonics off on macOS). Four: Return on a table row does nothing (on macOS Qt's item views treat Return as "edit" and do not emit `activated`). With `qt_set_sequence_auto_mnemonic(True)` the six pass and the four remain. |
| A `BUNDLE` added to the spec | Builds `ESO Log Tail.app`, 103 MB, 2,237 files and 59 symlinks; 52 MB zipped with `ditto`; ad-hoc signed; `codesign --verify --deep --strict` passes |
| The frozen app against `tests/fixtures/golden_fight.log` | Up after 15 s, 220 MB resident, `crash.log` holds only its session line |
| The frozen app against a real 496 MB log, last 50 MB loaded | Up after 30 s, 289 MB resident, `fights.jsonl` written, no crash |
| Built with `codesign_identity` set to the Developer ID certificate | PyInstaller signs every binary and the bundle with the hardened runtime and a timestamp (about 100 s more); verification passes; **it starts with no entitlements file** |
| The ad-hoc zip expanded and signed afterwards (`codesign --force --deep --options runtime --timestamp`) | 5 s; verification passes; no binary keeps its ad-hoc signature; it starts. So signing can be a job of its own. |
| Gatekeeper's view (`spctl --assess`) | Ad-hoc: `rejected`. Developer ID: `rejected, source=Unnotarized Developer ID`. Only notarization opens the door. |
| `lsof -t -- <path>` as the holder check | Finds a child process holding the file; lists our own process too; 0.24 to 0.36 s with 868 processes running. It exits 1 both for "nobody holds it" (nothing on either stream) and for a failure (a message on stderr). |
| `recycle_bin.move_to_trash` | Works (Send2Trash 2.2.0, its ctypes backend), 0.08 s |
| Minimum macOS recorded in the binaries | Qt's frameworks and plugins: 14.4. **PySide6's and shiboken6's own libraries (`QtCore.abi3.so`, `libpyside6`, `libshiboken6`): 26.0**, in both slices of the wheel, though the wheel is tagged `macosx_14_0`. Homebrew's Python and OpenSSL: 27.0. |
| Screens drawn by the native `cocoa` platform (`scripts/capture_screenshots.py`) | 25 written, every one the fixture log allows. The app is usable. The checked *Detail view* button's text is nearly unreadable, and every tooltip and the search field's hint name Ctrl and Alt keys. |
| The same screens with Qt's Fusion style | Clean, and the same look as Linux |
| Fonts asked for by name | Qt warns at start-up that *Segoe UI Symbol* is missing (67 ms); the skull's font list resolves to the system font, which has no U+2620, and *Apple Symbols* has it. Adding *Apple Symbols* to the list does not stop the warning (the reviewer's run); `text_size.fixed_font()` draws the same warning for *Consolas*. |
| `QApplication.setWindowIcon` and the Dock | `NSApp.applicationIconImage` is the same object before and after the call (`build/spike/dock_icon_probe.py`). Qt's source says the call sets it. Unresolved; see row f. |

Checked by a documentation search on 2026-11-15 (**read**):

- Hosted runners: `macos-15` (arm64), `macos-26` and `macos-latest` (arm64, macOS 26), `xcode-27` (arm64, generally available since 2026-10-15). `xcode-27` is an image named for its Xcode, not a pinned macOS; there is no `macos-27` label. `macos-14` was retired on 2026-11-02. Intel: `macos-15-intel`, `macos-26-intel`.
- `actions/setup-python` has arm64 and x64 builds of Python 3.14 for macOS, no universal2.
- PyInstaller, given a `codesign_identity`, signs every collected binary with the hardened runtime and signs the bundle. It adds no entitlements by itself, and it calls `codesign` without naming a keychain.
- `notarytool submit` takes a zip, a dmg or a pkg. A ticket is stapled to the `.app`, never to a zip, so the order is: zip, notarize, staple the app, zip again.
- macOS identifies an app to its privacy system by its signature's designated requirement. A Developer ID signature's requirement names the team and the bundle identifier, so a permission survives an update. An ad-hoc signature's requirement is the build's own hash, so every update is asked again.
- Apple's Rosetta notice of 2026-09-01 calls macOS 27 the last release to support it. ZeniMax announced a native Apple Silicon client for summer 2027.
- The repository has one ruleset, `main prot`, on branches. **No rule restricts who may create a tag.**

## Decisions

### 1. Architecture: arm64 only

ESO's Mac client is an Intel binary, so Intel Mac players exist, but macOS 27 runs only on Apple Silicon and the game is moving there. A universal2 or Intel build needs python.org's universal2 installer in place of `setup-python` and a second smoke run on `macos-15-intel`. That is a follow-up when a player asks. The asset's name carries `arm64`, so a second asset can sit beside it later.

### 2. Sign with the Developer ID certificate and notarize, in a job of its own

The issue recommended shipping unsigned, for want of a Developer Program membership. The membership exists. Signing changes two things for a user:

- **Opening the app.** Unsigned or ad-hoc, a downloaded app is blocked, and on macOS 15 and later the way past is a blocked attempt and then System Settings → Privacy & Security → *Open Anyway*, or a Terminal command. Notarized, it opens with the ordinary "downloaded from the internet" confirmation.
- **The Documents permission.** The app reads `~/Documents/Elder Scrolls Online/`, which macOS guards. With an ad-hoc signature every update would be a new app to the privacy system, asked again each time. With Developer ID the answer is kept.

Which certificate: the keychain holds two with the same name. `A224A481…` expires on **2027-02-01**; `B02AF647…` runs to 2031-03-29. Export the second.

Entitlements: none. The hardened-runtime build started and ran without any (measured), and Apple's guidance is to add an entitlement only for a failure it explains. If the notarized app fails to start on some machine, `com.apple.security.cs.allow-unsigned-executable-memory` is the first to try.

**Where the key is used.** Not in the build job: that job installs packages from PyPI without hashes and runs 2,700 tests, and none of that code should run beside the key. `build-macos` makes an ad-hoc-signed zip, as it does for a pull request. A separate job, `sign-macos`, takes that zip and runs only Apple's tools on it: expand, `codesign`, zip, `notarytool`, `stapler`, zip. Measured: signing the expanded zip this way takes 5 s and the app starts.

**Who can reach the key.** Five secrets, in a GitHub environment `release-signing`:

| Secret | What |
|---|---|
| `MACOS_CERTIFICATE_P12` | The certificate and its key, exported from Keychain Access, base64 |
| `MACOS_CERTIFICATE_PASSWORD` | The export's password |
| `NOTARY_KEY_P8` | An App Store Connect API key (team key, Developer role), base64 |
| `NOTARY_KEY_ID`, `NOTARY_ISSUER_ID` | The key's ids |

A workflow that runs for a tag is the copy in the tagged commit, so whoever can push a `v*` tag on any commit can run an edited workflow with the secrets. The controls, all part of PR 3:

1. A **tag ruleset**: only the maintainer may create `v*` tags. None exists today. This is the one control that stops a hostile tag; the other two can be edited out of the tagged commit by whoever pushes it.
2. The environment deploys only from `v*` tags and from `main` (for the dry run below). Only `sign-macos` names the environment, so pull-request jobs never ask for it.
3. Against mistakes, not attacks: `sign-macos` runs `scripts/release_guard.py` before it imports the key, so a tag pushed by accident on a branch, or one that does not match `src/version.py`, signs nothing. Today the guard runs only in the release job, after signing would already have happened. The guard compares against `origin/main` and reads the tags, so `sign-macos` must check out with `fetch-depth: 0`, as the release job does; with the default depth every tag would be refused as "not on main".

A required reviewer on the environment would add a click to every release and stop an unattended one. It is the maintainer's choice.

**A dry run before the first tag.** `workflow_dispatch` gains a `sign` input. Started on `main` with it on, the run signs, notarizes and smoke-tests, and publishes nothing. It runs the guard too, with `v<the version in src/version.py>` and the commit, so the guard's checkout and its `origin/main` are proven before a tag depends on them. Without the dry run the CI-only steps (the guard in this job, the base64 decode, the temporary keychain, `notarytool` with an API key, the staple and second zip) would run for the first time on a release tag, and a fault in the workflow would cost a version number.

**Signing after the build, and its two risks.** `codesign --deep` is not what Apple recommends for signing, though PyInstaller uses it on the bundle too. It signs what it finds in the bundle's standard code folders, where PyInstaller 6 puts every binary today. So after signing, a step walks every Mach-O file in the app and fails unless each one has the Developer ID authority and the runtime flag. And if an entitlements file is ever needed, it goes to the main executable alone, in a second `codesign` call, not through `--deep`.

Unverified: that Apple's notary accepts this bundle. PyInstaller's handling of Qt's `.framework` folders has failed signing for others in the past; both ways of signing passed `codesign --verify --strict` here. Task 3.1 notarizes one build by hand before the workflow is written.

### 3. The Mac jobs block a release, from PR 3

The same rule as Linux: a release is all its files or none. Notarization is part of it, so an outage of Apple's notary service holds a release until the job is run again; a release with an un-notarized Mac app would be worse than a late one.

Until PR 3 the Mac jobs **do not run for tags at all** (`if: ${{ !startsWith(github.ref, 'refs/tags/') }}`). Leaving them out of the release job's `needs` is not enough: a red Mac job would still make the tag's run a failure, and two things read that. `scripts/release.py --watch` would report "run failed; nothing was published" for a release that was published, and the Pages workflow rebuilds only after a successful run, so the home page's beta line would go stale.

PR 3 joins them once they have been green on at least five pull-request runs and the dry run of decision 2 has passed.

### 4. A zip, made with `ditto`

`ditto -c -k --sequesterRsrc --keepParent "dist/ESO Log Tail.app" <zip>`. Safari and Finder expand it; `zip` and `actions/upload-artifact` on the bare folder both lose symlinks and permissions, and with them the signature. A `.dmg` is the Mac convention and one more step; nothing here needs it.

The app must run from wherever the user leaves it. A downloaded app opened from Downloads is run by macOS from a read-only copy (translocation). The app writes nothing beside itself (config, `crash.log`, `fights.jsonl` and `banner.log` are under `~/Library/Application Support/esolog-tail/`; **read**), so that is harmless.

### 5. The maintainer tests it, on this Mac

Two rounds. During PR 1 and PR 2, from the source and from a locally built bundle: the look, the keys, the archive guard against the running game. After the first beta, from the zip downloaded in a browser, because Gatekeeper and the privacy prompts act only on a downloaded app that Finder starts; the spike started the binary from a shell, where the permission belongs to the terminal. The checklist is under "Manual checks".

The build stays labelled experimental, as Linux is, until a live session with fights has been run on it.

### 6. Qt style: decide on screen, Fusion if in doubt

**Decided (the maintainer, 2026-11-16): the native macOS style.** Native and Fusion were on screen side by side, in light and dark (`build/spike/style_look.py`, a scratch home and the fixture log). The app sets no style on macOS. Captures of those windows, which draw them as inactive, still show the checked *Detail view* button close to unreadable in light and the selected tab hard to tell from the others; if either troubles a user, the fix is to that control, not a change of style.

The captures of the native style show a checked toolbar button whose text cannot be read, and a tab bar and search field that look heavier than the rest. A capture is not the screen: `QWidget.grab()` draws a window that is not the active one, and macOS draws controls of inactive windows differently. So PR 1 starts with a look at the real window, in light and dark.

If the native style has a defect, set Fusion on macOS (`app.setStyle("Fusion")` before the window is made). Fusion is what the Linux build and the offscreen tests already draw, it follows the system's dark mode through Qt's palette, and its metrics are the ones the layouts were measured with. The cost is an app that looks like Qt and not like a Mac app.

### 7. The oldest macOS is what CI proves

The issue says macOS 14, from the wheel's tag. Qt's own minimum is 14.4, and the wheel's binding libraries are stamped 26.0. Whether those run on macOS 15 is **unverified** and cannot be reasoned out: macOS does not refuse a library for its stamp, but code compiled for 26.0 may call what 15 lacks.

`build-macos` starts on `macos-15`, the oldest hosted image, and runs the whole test suite there on the same PySide6 binaries before it builds; `smoke-macos` then starts the zip on `macos-15`, `macos-26` and `xcode-27`. PR 2's first runs settle the floor, one way or the other, and PR 2 is finished only in the settled state. It can take two runs: when `build-macos` fails on `macos-15`, `smoke-macos` is skipped and says nothing about the newer images until the build has moved.

- **The suite and the smoke test pass on `macos-15`:** `LSMinimumSystemVersion` is `15.0`.
- **Either fails there:** `build-macos` moves to `macos-26`, `macos-15` leaves the matrix, the floor is `26.0`, and the README says so. A leg that is expected to fail is never left in the matrix: from PR 3 every leg is in the release job's `needs`.

macOS 14 cannot be tested (its runner is retired) and is not claimed.

**Settled (2026-11-16, the first run of pull request #240): the floor is 15.0.** On `macos-15` (macOS 15.8.2) the suite passed on the same PySide6 binaries (2,778 passed, 17 skipped, 87 s) and the zip started and stayed up; it did the same on `macos-26` (26.7.2) and `xcode-27` (27.0.1). So the binding libraries stamped 26.0 run on macOS 15, as far as the suite and a start can show. `build-macos` stays on `macos-15` and all three legs stay in the matrix. In the CI bundle, 49 files are stamped 11.0 (setup-python's Python and its libraries), 23 are 14.4 (Qt) and 7 are 26.0 (the binding libraries).

The build job uses `setup-python`'s Python, never Homebrew's: a bundle built on the maintainer's Mac carries a Python stamped 27.0 and is for that Mac only. A step lists every binary's stamp and fails when Python's or OpenSSL's is above the floor. PySide6's own stamp is printed, not enforced: the runs above are its test.

## What differs on macOS, and what PR 1 does about it

| # | Difference | Evidence | Change |
|---|---|---|---|
| a | Return and Enter on a table row do nothing | 4 failing tests | A helper in a new `gui/keys.py`, `on_row_activated(view, slot)`: connects `activated`, and on macOS also calls the slot for Return and Enter on the current row. `events_tab.py` and `positions_window.py` use it. |
| b | Alt-letter tab keys do nothing | 6 failing tests | `qt_set_sequence_auto_mnemonic(True)` in `esolog_gui.py` on macOS, and in `tests/conftest.py` so the tests run as the app does (harmless on Windows and Linux, where it is already on). Unverified on a real keyboard: Option-letter also types a character (Option-F is ƒ), so the search field may take the key first. If it does, add ⌘1 to ⌘5 for the tabs on macOS. |
| c | Three shortcuts land on keys macOS gives a meaning | Qt maps Ctrl to ⌘ (**measured**: `QKeySequence("Ctrl+H")` reads ⌘H). `Ctrl+H` (*Hide names*) becomes ⌘H, *Hide application*; `Ctrl+,` and `Ctrl+.` (playback speed in the positions window) become ⌘, (*Settings*) and ⌘. (*Cancel*). Whether Qt or the system wins is unverified. | On macOS: *Hide names* is `Ctrl+Shift+H` (⇧⌘H); the speed keys are `Meta+,` and `Meta+.` (⌃, and ⌃.). |
| d | Tooltips, the search hint and status texts say "Ctrl+F", "Alt+I", "Ctrl+PgDn" | **read**: about 100 mentions in 13 files, most in comments and `QKeySequence("…")` specs | `keys.key_text("Ctrl+F")` returns `QKeySequence(...).toString(QKeySequence.NativeText)`: "⌘F" on macOS, "Ctrl+F" elsewhere. Every text given to `setToolTip`, `setPlaceholderText`, `setStatusTip`, `setAccessibleName` and `setAccessibleDescription`, and the `*_TIP`, `*_CUE` and `*_DESCRIPTION` constants, is built with it. Three existing tests assert the Windows wording and must compare against `key_text` instead: `test_keyboard_gui.py:145`, `test_events_tab_gui.py:717`, `test_hide_names_gui.py:234`. **Built (2026-11-16):** off macOS `key_text` returns Qt's portable name with "PgDown" written "PgDn", not `NativeText`, so every Windows and Linux text is what it was. A fourth test asserted the Windows wording, `test_accessibility_gui.py:177`. Keys given by name are bound through `keys.sequence`, which also holds the three moved keys of row c, so a text cannot name a key that was not bound. |
| e | *Settings…* and *About…* are not in the application menu | The actions are in a toolbar; Qt moves only menu-bar actions (the issue assumed otherwise) | Leave them in the toolbar. No menu bar in this change. |
| f | `setWindowIcon(icon.ico)` may replace the Dock icon with the `.ico` picture | Qt's source says it does; the probe measured no change | Skip the call on macOS: macOS shows no icon in a window's title bar, so the call does nothing useful there, and skipping it ends the question. |
| g | The icon is a bare shape on a transparent ground | **read**; macOS 26 and later are reported to put an icon that does not fill the rounded square on a grey plate (unverified on this build) | `create_icon.py` draws the d12 on a rounded-square plate for the `.icns` only. Check in Finder and the Dock. |
| h | Fonts are asked for by their Windows names | **measured**, above | The skull's font list and the fixed font's are chosen per platform: on macOS *Apple Symbols* and *Menlo*, with no Windows or Linux name in the list. The death chip's skull in the fight text takes whatever font macOS falls back to, possibly the colour emoji; manual check 3 looks at it. |
| i | *Show in folder* opens the folder without selecting the file | **read**, `reveal_file` | On macOS run `open -R <path>`. |
| j | The archive's in-use guard always says "free" | **read**: the guard scans `/proc` | See "The archive guard". |
| k | The update check has no Mac asset | **read** | `PLATFORM_ASSETS["darwin"] = ("esolog-tail-macos-arm64", ".zip")`. The download runs only where there is an installer (`HAS_INSTALLER`), so on macOS the button opens the release page, as on Linux. |

Page Up and Page Down are Fn-↑ and Fn-↓ on a Mac laptop; the user guide says so. No key changes for it.

Already right, and left alone: where the log is looked for (the `darwin` branch has the native path, **measured** to be where the Steam client keeps its files); config and `crash.log` under `~/Library/Application Support/esolog-tail/` (**measured**); the split folder's lock (`os.kill(pid, 0)`); *Start at login* and the score banner, both hidden off Windows. The reviewer's search of `src/` for other platform-specific code found none unhandled.

## The archive guard

With *Delete Encounter.log after a verified archive* on (off by default), deleting a log the game still has open loses the rest of the session: on macOS the delete succeeds and the game keeps writing to a file with no name.

The issue's plan was `lsof`, "falling back to `False` as today". That fallback is the unsafe way round. This change:

1. A function defined on every platform, so every platform's CI can test it, runs `/usr/sbin/lsof -t -- <path>` with a 5 s limit and reads the result into one of three answers. *Held*: process ids on stdout other than our own. *Free*: exit 1 with nothing on stdout and nothing on stderr. *Unknown*: anything else, including a missing `lsof`, a message on stderr, and a timeout. **Built (2026-11-16):** *free* is also exit 0 naming this process alone with nothing on stderr. At the moment of the delete the archive's own read handle is open, so `lsof` names us and exits 0; without this no delete could ever happen on macOS. Measured on macOS 27.2 (lsof 4.91): a free file gives exit 1 with both streams empty, a held file gives the process id and exit 0, a missing file gives exit 1 with a message on stderr; one call takes about 0.17 s. The call is `lsof -t +w -- <path>`: `-t` alone turns lsof's warnings off, so something it could not look into would have read as *free*; with `+w` the three measurements are the same.
2. On macOS, at the start of an archive, *held* skips it with the in-use notice, as on Linux. *Unknown* lets the zip be made, as today.
3. The delete is decided where it already is, in the POSIX `_ExclusiveFile.mark_delete_on_close`, whose return value `archive()` already reports as `original_deleted`. On macOS it asks the holder check **again**, at that moment, and returns `False` unless the answer is *free*. The zip is kept and the original stays. Asking again matters: today the only guard between the first check and the delete is that a log which grew *while being zipped* fails verification (`_verify` compares against the size at the start). A game that has the log open and writes nothing for those seconds, between two fights, passes it. **Built (2026-11-16):** on macOS the log is removed there too, straight after the *free* answer, not when the handle is closed: the config's save and the listeners run in between. A log that cannot be removed is reported as kept ("the log could not be deleted").
4. The user is told. The completed event gains a `kept_reason`, and the status bar's line for a completed archive, which today reads the event's `original_deleted` only, says "original kept: could not check whether the log is in use" (or "…: the log is in use").
5. Linux keeps its `/proc` scan and its behaviour.

**Measured (2026-11-16, manual check 4):** the Mac client keeps `Encounter.log` open between writes, as the Windows client does. With the game running from Steam on macOS 27.2 and `/encounterlog` on, `lsof -t +w -- <path>` named one process, the client (`eso`, a write handle), at three moments over 45 s; the file did not grow between two of them, so the handle is kept and not opened for each write. The client also holds `client.log` and `interface.log` in the same folder. `holder_check()` answered *held* in 0.22 s, and `LogArchiver.archive()` on the live log, with a scratch folder to write to and the delete off, sent "skipped: Encounter.log is in use (is ESO running?)", wrote nothing and left the log as it was. The log is at `~/Documents/Elder Scrolls Online/live/Logs/Encounter.log`, a local folder and the first place the app looks. Not seen: the *Archive now* button itself pressed in the window with the game running; it calls the same `archive()`.

## The release scripts: three places count files

Adding the Mac zip the way the issue describes would break things that work today:

- `scripts/build_site.py` stops the Pages build when the **Stable** release lacks a listed asset, and Pages builds on every change to the page on `main`. The Stable release will not carry a Mac zip until a beta that has one is promoted. So `macos_url` is an **optional** asset: while Stable lacks it, the page's Mac link is left out (`{{macos_link}}` is empty), and the build passes.
- `scripts/promote_release.py` promotes a beta only when it "carries all three files". Requiring a fourth of every beta would make the betas already published unpromotable. The rule that needs no constant: **a beta must carry the Mac zip when the Stable release does**. Before the first Mac build is Stable, a beta with three files or four may be promoted; after it, never one without.
- `scripts/release.py` imports the same `ASSETS` from `promote_release.py` for its check after a tag. It tags only new releases, so it requires all four. The two scripts therefore need the base three and the Mac zip as separate names, not one tuple.

## Workflow shape

After PR 3 (in PR 2, `build-macos` and `smoke-macos` exist, run for pull requests and manual runs only, and nothing depends on them):

```
build-windows ───────────────────────────────────┐
build-linux  ────────────────────────────────────┤
build-macos ──> sign-macos ──> smoke-macos ──────┴──> release (tags only)
 (ad-hoc zip)   (tags, and a    (macos-15 if it
                 dry run on      passed, macos-26,
                 main)           xcode-27)
```

- `build-macos`: setup-python 3.14, requirements, gear data, the icon, the tests (`QT_QPA_PLATFORM=offscreen`), PyInstaller, the stamp check, `ditto`, the upload. Its zip is named `esolog-tail-macos-arm64-<version>-unsigned.zip`, in an artifact named `unsigned-macos-arm64`.
- `sign-macos`, environment `release-signing`: a full-depth checkout and the guard; the certificate into a temporary keychain that is unlocked, given `set-key-partition-list`, and put on the search list (`codesign` is not told which keychain); `codesign`; the check of every Mach-O file; zip; `notarytool submit --wait`; `stapler staple`; zip again as `esolog-tail-macos-arm64-<version>.zip`; the keychain deleted (`if: always()`). It runs for tags and for the dry run, and is skipped for a pull request.
- **The two zips never share a name.** The release job downloads every artifact into one folder (`merge-multiple: true`), where two files of one name would overwrite each other and the release could publish the unsigned one. The release job downloads by pattern (`esolog-tail-*`), which the unsigned artifact's name does not match, and its `files` list names the signed zip only.
- `smoke-macos` takes the signed zip when `sign-macos` ran and the unsigned one when it was skipped. A job that needs a skipped job is itself skipped, so its condition is written out: `if: ${{ !cancelled() && needs.build-macos.result == 'success' && contains(fromJSON('["success","skipped"]'), needs.sign-macos.result) }}`. The release job keeps the plain rule, with `sign-macos` and `smoke-macos` in its `needs` and no `always()`: a failed or skipped signing job means no release.
- `smoke-macos`, each leg: download, `ditto -x -k` (so the test covers the round trip a user's download makes), `codesign --verify --deep --strict`, and for a signed zip `xcrun stapler validate` and `spctl --assess --type execute -vv`, whose output must contain `Notarized Developer ID`. Then `scripts/smoke_macos.py`, the spike's script made permanent: a scratch `HOME` holding a config whose `log_path` is the fixture, `Contents/MacOS/esolog-gui` started with its output sent to a file (a pipe nobody reads would let a blocked app pass as running), 20 s, and a pass when the process is still up and `crash.log` has no `Unhandled exception` or `Fatal Python error`. A scratch `HOME` keeps the run out of the runner's `~/Documents`, where nobody could answer a permission prompt. Each leg prints `sw_vers`, since `xcode-27` names an Xcode and not a macOS.

Unverified, and answered by PR 2's first run: that a hosted runner has a window session the `cocoa` platform can use (if not, the smoke test runs with `QT_QPA_PLATFORM=offscreen`, which still proves the frozen Python, the data and the signature but not the platform plugin, and the workflow's comment says so); and that Gatekeeper is on there (`spctl --status`), without which the `spctl` check means nothing. **Answered (2026-11-16, the same run):** both hold. The app started with the `cocoa` platform on every leg, with no `QT_QPA_PLATFORM` set, so the smoke test covers the platform plugin and needs no `offscreen` fallback. `spctl --status` printed `assessments enabled` on every leg, so the `spctl` check of task 3.3 stays.

## Built in PR 2 (2026-11-16)

Measured on the maintainer's Mac (macOS 27.2, Homebrew Python 3.14.10, PyInstaller 6.22.3, Pillow 13.0.0), before any CI run:

- **The bundle.** `dist/ESO Log Tail.app`, 103 MB, 81 Mach-O files. Its Info.plist has `CFBundleShortVersionString` and `CFBundleVersion` from `src/version.py`, `LSMinimumSystemVersion` 15.0 and the six usage descriptions. `codesign --verify --deep --strict` passes on it and again after `ditto` zips it (52 MB) and expands it. The signature is ad-hoc.
- **One sentence for every folder question**, not the Documents sentence repeated: "ESO Log Tail reads the Encounter.log the game writes, and the logs you open for review." The Documents sentence would have been wrong when macOS asks about Downloads.
- **The stamp check is stricter than planned.** `scripts/check_macos_stamps.py` fails on *any* binary above the floor except PySide6's and shiboken6's binding libraries, not only on Python's and OpenSSL's: a Homebrew build also brings `liblzma`, `libzstd` and `libmpdec` stamped 26.0, and a rule that names two libraries would have passed them. The floor is read from the bundle's own Info.plist. On the local bundle it lists 23 files at 14.4 (Qt), 7 binding libraries at 26.0 (reported), and fails on 50 at 26.0 and 27.0, as it should for a Homebrew build.
- **The smoke test asks for one thing more than the plan:** the app must have written its `crash.log`. A bootloader that hangs before Python starts is "still running" and has no crash line; the session line the app writes at start-up shows Python got that far. The script runs under the runner's own `python3` (tried with 3.9.6). The local bundle passes it with the `cocoa` platform.
- **The icon** is written by Pillow, which makes an `.icns` of 32 to 1024 px (16 pt at 2x up to 512 pt at 2x). It has no 16 px image at 1x; macOS scales the 32 px one. `iconutil` reads the file.
- **After an independent review** (nothing above medium): the stamp check runs `otool -arch all`, since plain `otool -l` prints a fat file's slice for the machine it runs on only; it reads "15" and "15.0" as one version; a file that starts as a Mach-O file does and that `otool` refuses fails the check by name. The smoke test also looks for a crash in what the app printed. The stand-in tests wait 5 s where the stand-in must write in time, after the review judged 2 s too short for a cold Windows runner.
- **Not built here:** the app-nap key (manual check 8 decides whether one is needed).

## Manual checks

**During PR 1**, from the source (`python src/esolog_gui.py`):

1. The native style, light and dark: the checked toolbar buttons, the tab bars, the search field. Decide decision 6.
2. Keys: Return on an Events row and on a Positions row; Option-letter on each tab with the focus in the page and in the search field; ⇧⌘H; ⌘H hides the app; ⌃, and ⌃. in the positions window; ⌘= and ⌘-; ⌘Q and the red button both save the window's geometry. **Skipped (the maintainer, 2026-11-16).** No key was pressed in the real window on macOS; the tests in `tests/unit/test_keys.py` and the windows' own tests press them offscreen.
3. The skull glyph and the death chip; the ability icons and the timeline strip on a Retina display. **Skipped (the maintainer, 2026-11-16).** Not looked at on screen: the skull in the fight list and the death chip (which font macOS gives them is still unverified, row h above), and the icons and the strip at Retina scale. Seen only in an offscreen capture at 1x during check 5: the ability icons and the timeline strip draw.
4. With the game running and `/encounterlog` on: `lsof -t -- ~/Documents/Elder\ Scrolls\ Online/live/Logs/Encounter.log` names the game or does not; record which. *Archive now* is skipped with the in-use notice when it does. **Done 2026-11-16: it names the game; see "The archive guard".**
5. A live session: a fight, the summary as combat ends. **Done 2026-11-16:** the app, started from the source with no settings on this Mac, found `~/Documents/Elder Scrolls Online/live/Logs/Encounter.log` by itself and followed it while the game (eso.live.12.1, from Steam) wrote it: two zone changes and a 12 s fight on a trial dummy. The maintainer saw the fight and its summary in the window. The app closed with exit 0, saved the window's geometry and wrote nothing to the Logs folder; crash.log held only its session line. A copy of the same log replayed offscreen lists the fight the same way ("Target Iron Atronach, Trial · 12s · 22.8k gdps", the bars and the sets).
6. *Show in folder* selects the file; split-log retention moves an old split to the Trash. **Skipped (the maintainer, 2026-11-16).** Neither was tried on macOS: `open -R` from the app, and a split moved to the Trash, are unverified there.

**During PR 2**, from a locally built bundle:

7. The Dock and Finder icon.
8. A live session with the game full screen over the app for several minutes, then back: is the list current at once? If the app was held back (App Nap), the bundle asks macOS not to nap it. Which Info.plist key or call does that on macOS 27 is unverified, so it is tried here and not assumed.

**After the first beta**, from the zip downloaded in a browser:

9. The zip expands by double-click; the app moves to Applications; the first open shows the ordinary download confirmation, not a block.
10. The first start asks for the Documents folder with the app's own sentence; after *Allow*, the log is found. After *Don't Allow*, the app says where it looked. Record whether a file chosen under Settings is still readable after a restart: for an app outside the sandbox that is not certain.
11. A log under `~/Library/CloudStorage/OneDrive-Personal/…` opens for review (macOS asks separately for a cloud provider's files).
12. The next beta: the **Get** button opens the release page; after replacing the app, macOS does not ask for Documents again.

## Risks

- **Notarization rejects the bundle, or the notarized app fails under the hardened runtime on another machine.** Task 3.1 notarizes by hand first. The first entitlement to try is named above.
- **The floor is 26.** Then the Mac build serves fewer players than hoped until PySide6 ships bindings built for an older macOS. Capping PySide6 below 6.12.0 is not a way out: 6.9.0 to 6.11.2 carry the October 2026 advisories (`requirements.txt`).
- **The certificate's key in CI.** Decision 2's controls. Only the tag ruleset stops someone with push rights; until it exists the secrets must not be stored.
- **A second release pipeline to keep alive.** Runner images retire (`macos-15` will); Apple changes notarization rules; the certificate expires in 2031. The workflow's comments carry the dates, as the Linux job's do.
- **Option-letter keys** may not work as tab keys on a real keyboard. The fallback is in row b.
- **App Nap** may delay the list while the game covers the app. Manual check 8.
- **Rosetta's end.** If the Intel client stops running on a later macOS before the native client arrives, there is a gap with no Mac players. Nothing here depends on it.

## Found on the way

Not part of this change; each wants an issue of its own.

- **No frozen build finds `data/skills/ability_targets.json`, on any platform.** `damage_kinds.TARGET_TABLE_PATH` is `Path(__file__).resolve().parent.parent / "data" / …`. In a frozen build that is the folder *above* the bundle's data (**measured** with a probe build: it looks in `dist/<app>/data/`, and the data is in `dist/<app>/_internal/data/`; the reviewer confirmed it for the `.app` too). `_load_targets` returns `{}` without a word, so `table_target` is `None` for every skill in every released build. `ability_icons.bundle_root()` is the path the other tables use.
- **CrossOver and Whisky bottles** are not among the places the log is looked for on macOS. Nobody has asked.
- **One of the two Developer ID certificates expires on 2027-02-01.**

## Not doing

- A menu bar, a login item, the score banner (it needs macOS's own text recognition), an in-app updater, a `.dmg`, an Intel build, the Mac App Store.
