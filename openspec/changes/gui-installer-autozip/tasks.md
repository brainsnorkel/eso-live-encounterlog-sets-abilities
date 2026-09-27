# Tasks

## 1. Engine Extraction (TUI/CLI removal)

- [x] 1.1 Create an engine-level golden test: replay a fixture log through the current analyzer capturing fight summary data (players, DPS%, sets, buffs), split-file names, and report contents; verify it passes against unmodified code (create/trim a fixture log if `data/example_logs/` is absent)
- [x] 1.2 Create `src/engine_events.py` with the `AnalyzerListener` protocol and `LogStatus`/`ArchiveEvent` dataclasses; verify with unit tests using a recording stub listener
- [x] 1.3 Move `FightHistory`/`FightHistoryEntry` to `src/fight_history.py` with no curses/colorama imports; verify import succeeds in isolation and existing history/dedup unit tests pass
- [x] 1.4 Replace `self.tui` calls and terminal printing in `ESOLogAnalyzer`/`LogFileMonitor`/`LogSplitter` with listener notifications; delete `TuiDisplay` and the Click `main()`; verify golden tests from 1.1 still pass and no engine module imports curses/click/colorama (grep check)
- [x] 1.5 Update `requirements.txt` (drop `windows-curses`, `click`, `colorama`; add `PySide6`, `platformdirs`) and prune/convert TUI- or CLI-dependent tests; verify the full test suite passes

## 2. Log Freshness (engine)

- [x] 2.1 Implement latest-entry tracking while tailing (`BEGIN_LOG` epoch + latest relative offset) emitting `on_log_status`; verify with unit tests covering exact derivation, epoch rollover on a new `BEGIN_LOG`, and updates as lines arrive
- [x] 2.2 Implement startup freshness (trailing-chunk scan for last complete line + `BEGIN_LOG` lookback, mtime fallback marked approximate, missing-file case) as a standalone function the archiver can call; verify with unit tests for mid-file start, no reachable `BEGIN_LOG`, and missing file

## 3. Startup Log Archiver

- [x] 3.1 Implement the in-use guard in `src/log_archiver.py`: exclusive-share open via `CreateFileW` (ctypes), held across the operation, clean skip on sharing violation; verify with a unit test that holds the file open from another handle and asserts skip behavior
- [x] 3.2 Implement chunk-streamed zip creation (zip64, deflate) with dated naming from the freshness derivation (mtime fallback), collision suffixes, progress callbacks via `on_archive_event`, and `testzip` + size verification; verify with unit tests including a >4 GB sparse-ish fixture or mocked size boundary for zip64
- [x] 3.3 Implement size-based trigger + re-trigger marker (`size_at_last_archive` in JSON config via `platformdirs`, reset on shrink/replace) and default-keep vs opt-in delete-after-verify; verify with unit tests for each log-archiving spec scenario
- [x] 3.4 Wire the archiver into app startup sequencing (config → archive check → monitoring) as an engine-level `startup()` routine independent of Qt; verify with an integration test using a temp log over a small threshold producing a verified zip before monitoring attaches

## 4. GUI Application

- [x] 4.1 Create the `src/gui/` package with an `esolog-gui` entry point and main window skeleton; verify it launches and closes cleanly
- [x] 4.2 Implement the engine worker thread (QThread) with a listener→Qt-signal adapter; verify with a replay-driven test that fight events arrive on the UI thread and that engine modules don't import Qt (grep check in tests)
- [x] 4.3 Implement the live fight view and fight history list (role colors, compact/detail toggle, return-to-live, clipboard copy); verify by replaying the fixture log and comparing displayed fights against golden data per the gui-application spec
- [x] 4.4 Implement split-file and report-saving toggles/directories driven by settings, reusing `LogSplitter` and report writing; verify produced files match the golden naming/content tests from 1.1
- [x] 4.5 Implement the settings dialog (log path, split/report options, archive threshold with sizing guide text, archive dir, delete-original opt-in) persisted to the JSON config; verify settings survive an app restart
- [x] 4.6 Implement the status bar: freshness display with 1 s age ticker and live/idle/stale/no-log states, archive notifications, archive progress bar, and the "Archive now" action; verify states by manipulating a temp log's content and mtime, and verify "Archive now" end-to-end
- [x] 4.7 Implement waiting-for-log state, log auto-detection reuse, and "Open log for review" mode; verify auto-detect selects the newest known-location log and reviewing a split file shows its fights then returns to live

## 5. Packaging & Installer (Windows-only)

- [x] 5.1 Replace the onefile CLI target in `esolog-tail.spec` with an `esolog-gui` onedir windowed target (icon, Qt module exclusions); verify a local build launches from `dist/`
- [x] 5.2 Write `installer/esolog-gui.iss` (per-user install, Start Menu + optional Desktop shortcut, uninstaller, stable AppId, version from `src/version.py`); verify `iscc` compiles it and the setup exe installs, launches, and uninstalls
- [x] 5.3 Verify in-place upgrade: build two installer versions, install N then N+1, confirm replacement install with working shortcuts and preserved JSON config
- [x] 5.4 Rework `.github/workflows/build-installers.yml`: Windows job builds GUI target, compiles installer, zips a portable build, attaches both to releases; remove macOS/Linux jobs; verify via workflow_dispatch run that artifacts match the installer-packaging spec

## 6. Cleanup, Docs & Final Integration

- [x] 6.1 Delete the abandoned `gui/` Tauri scaffold; verify no references remain (`grep -r "src-tauri"` clean) and builds/tests pass
- [x] 6.2 Rewrite README.md (GUI install/usage, breaking-change notice with flag→setting migration table, auto-archive with sizing guide, freshness, SmartScreen note), update BUILD_WINDOWS.md and CHANGELOG.md; verify documented steps run as written
- [x] 6.3 Full integration pass: run the complete test suite, replay-verify GUI display against golden data, and exercise startup auto-archive end-to-end (oversized temp log → in-use skip case → free-file archive with progress → dated zip → marker persisted); verify all spec scenarios have a passing test or a recorded manual check
