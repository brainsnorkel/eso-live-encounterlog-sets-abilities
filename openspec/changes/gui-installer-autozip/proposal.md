# Proposal: GUI Replacement with Installer, Startup Log Auto-Archiving, and Log Freshness Display

## Why

ESO Log Tail is currently a terminal application (curses TUI + CLI flags) that users launch via hand-written `.BAT` files, which is a high barrier for the typical ESO player. Replacing the terminal frontends with a windowed GUI application and a proper installer makes the tool approachable: double-click to install, double-click to run, configure paths in a settings dialog instead of editing batch files. Maintaining one frontend instead of three (TUI, plain stdout, GUI) also keeps the codebase smaller.

At the same time, two quality-of-life gaps hurt daily use: (1) `Encounter.log` grows unboundedly (48MB+ observed) and users have no automated way to archive it, and (2) there is no at-a-glance indication of whether the log is actually receiving fresh data — users can't tell "is logging on?" without checking file timestamps by hand.

## What Changes

- **New desktop GUI application** that becomes the sole frontend, reusing the existing analysis engine (`ESOLogAnalyzer`, `LogSplitter`, `LogFileMonitor`). All user-facing features are preserved in the GUI: live fight summaries, fight history browsing, compact/detail views, clipboard copy, per-encounter split files, saved reports, log auto-detection, and opening a past log file for review.
- **BREAKING: the curses TUI and the CLI surface are removed.** Existing `.BAT` workflows are replaced by GUI settings (log path, split directory, reports directory). The README documents the migration.
- **Engine extraction refactor**: the analysis pipeline is separated from all presentation code in `src/esolog_tail.py`; the engine emits events through a listener interface consumed by the GUI (and by tests).
- **Windows installer**: a wizard-style installer that installs the GUI app, creates Start Menu/Desktop shortcuts, and supports clean uninstall and in-place upgrade. Built in CI.
- **Startup auto-archive (auto-zip) of the active encounter log**: at application startup only, if the active `Encounter.log` has grown beyond a configurable size threshold since the last archive (default 1 GB ≈ five veteran trials; settings show a size guide: a vet trial run is typically 100–300 MB, a vet dungeon roughly 25–75 MB), the app creates a dated zip archive (e.g. `Encounter-YYMMDDHHMMSS.zip`) with progress display, since real logs reach tens of GB. ESO holds the log file open for the entire game session (while logging and between logging sessions), so archiving is only attempted at startup and is skipped with a notification if the file is in use. Removal of the original after archiving is opt-in.
- **Log freshness display**: the GUI status bar shows the date/time of the latest log entry and a live-updating "how long ago" indicator (e.g. "Last entry: 2026-09-27 14:33:02 — 3m ago") with live/idle/stale/no-log visual states.
- **Dependency changes**: add `PySide6` and `platformdirs`; drop `windows-curses`, `click`, and `colorama`.
- Remove the abandoned Tauri scaffold under `gui/` (contains only `node_modules` and generated schema stubs; no project files).

## Capabilities

### New Capabilities

- `gui-application`: Windowed desktop UI as the sole frontend — live monitoring, fight history, split files, saved reports, settings, status display, and feature parity with the retired terminal frontends.
- `installer-packaging`: Building and distributing the GUI app as a Windows installer (shortcuts, uninstall, upgrade-in-place) plus portable archives, with CI release automation.
- `log-archiving`: Startup-time, size-based detection of an oversized active `Encounter.log` and safe creation of a dated zip archive, guarded against ESO holding the file open, with a configurable threshold (plus in-app sizing guide), progress reporting, and opt-in post-archive cleanup.
- `log-freshness`: Deriving the timestamp of the most recent log entry (BEGIN_LOG epoch + relative offset) and exposing it, plus its age, for display in the GUI.

### Modified Capabilities

<!-- none: openspec/specs/ is empty; no existing capability specs to modify -->

## Impact

- **Code**: new `src/gui/` package; `src/esolog_tail.py` (~5,000 lines) split into engine modules with the `TuiDisplay` class (~400 lines) and Click-based `main()` deleted; new `src/log_archiver.py`; freshness tracking in the monitor path; deletion of the stale `gui/` Tauri directory.
- **BREAKING**: all documented CLI flags and the terminal UI are removed. Users launching `esolog-tail.exe` from `.BAT` files must switch to the GUI app; equivalent behavior is available via GUI settings.
- **Dependencies**: `requirements.txt` gains `PySide6` and `platformdirs`; loses `windows-curses`, `click`, `colorama`.
- **Build/CI**: `esolog-tail.spec` replaces the onefile CLI target with an onedir windowed GUI target; GitHub Actions release workflow builds the installer (plus a portable zip) on the Windows runner; the macOS/Linux build jobs are removed (Windows-only distribution, per maintainer decision; no code signing).
- **Tests**: tests exercising CLI/TUI behavior are converted to engine-level tests; feature parity is verified against engine output rather than terminal output.
- **Docs**: README (rewritten installation/usage), BUILD_WINDOWS.md, CHANGELOG.md (breaking-change notice and migration guide).
