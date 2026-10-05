# Design: GUI Replacement with Installer, Startup Log Auto-Archiving, and Log Freshness

## Context

The application today is a single ~5,000-line module (`src/esolog_tail.py`) containing:

- `ESOLogAnalyzer` — parses entries, tracks encounters/zones/players, builds reports
- `TuiDisplay` + `FightHistory`/`FightHistoryEntry` — curses full-screen frontend
- `LogSplitter` — per-encounter split files
- `LogFileMonitor` — polling tail loop that drives the analyzer
- Click-based `main()` — CLI wiring, log auto-detection, replay modes

Presentation is entangled with analysis: the analyzer calls `self.tui.render_fight(...)` directly (esolog_tail.py:2954) and prints colorama-formatted text throughout. Timestamps for log entries are derived as `log_start_unix_timestamp` (from the `BEGIN_LOG` event, esolog_tail.py:1998-2003) plus each line's relative millisecond offset (esolog_tail.py:1980-1982).

Real-world scale (measured on the maintainer's machine, 2026-09-26): the active `Encounter.log` is **21.2 GB**; per-trial split files run 87–305 MB for veteran trials (Hel-Ra 87 MB, Kyne's Aegis 189 MB, Lucent Citadel 243 MB, Maw of Lorkhaj 305 MB). ESO keeps `Encounter.log` open for the entire game session — while logging and between logging sessions — so the file is only free of writers when the game is not running.

Distribution today is a PyInstaller onefile exe zipped with a README and a generated `.BAT` file (`.github/workflows/build-installers.yml`); users hand-edit batch files to configure paths. A `gui/` directory at the repo root contains an abandoned Tauri scaffold (only `node_modules/` and generated schema stubs) and should be removed.

Maintainer decisions: the GUI **replaces** the TUI and CLI (features preserved in the GUI); auto-archive runs **only at app startup**; the archive trigger is **size-based** (clearer to reason about than trial counting, and covers dungeon-only players); **Windows-only** distribution; **no code signing**.

## Goals / Non-Goals

**Goals:**

- A windowed GUI as the sole frontend, with feature parity: live fight view, fight history (compact/detail, clipboard copy), split files, saved reports, log auto-detection, opening a past log for review, settings dialog.
- Engine extraction so analysis code has no presentation dependencies (no curses/click/colorama) and is driven through a listener interface.
- A Windows installer (wizard, shortcuts, uninstall, in-place upgrade) plus a portable zip, built in CI.
- Startup-only auto-archive: dated zip of the active `Encounter.log` when it has grown past a configurable size threshold since the last archive, safe against ESO holding the file open, with progress UI for multi-GB files.
- Log freshness: latest-entry timestamp + live "how long ago" indicator in the GUI status bar.

**Non-Goals:**

- Keeping any terminal frontend (TUI and CLI are deleted; **BREAKING**).
- macOS/Linux packaging or CI builds (dropped per maintainer decision).
- Code signing (accepted SmartScreen "unknown publisher" prompt, as with today's exe).
- Archiving while the game session is running (impossible/unsafe: ESO holds the file open); no idle-wait/retry loop during tailing.
- Historical encounter database, web interface, or other Future Enhancements from the README.

## Decisions

### D1: GUI framework — PySide6 (Qt for Python)

The engine is pure Python, so the frontend should be too — one language, one packaging pipeline.

- **PySide6 (chosen)**: mature widget set (lists, rich-text views, status bar, dialogs), QSS theming to reproduce the TUI's role-color scheme, signals/slots fit an event-driven engine, LGPL, well-trodden PyInstaller path.
- *tkinter*: stdlib and small, but poor fit for the dense, color-coded fight report layout.
- *pywebview/Eel*: adds a JS layer and depends on the OS WebView2 runtime.
- *Tauri (existing scaffold)*: Rust + Node toolchains plus a Python sidecar protocol — highest complexity; the scaffold is abandoned and empty of real project files.

Installed-size cost of Qt (~80–120 MB) is acceptable for a desktop install; unused Qt modules (WebEngine, Qml, etc.) are excluded from the PyInstaller build.

### D2: Engine extraction with a listener interface

Split `src/esolog_tail.py` into engine modules with no presentation imports:

- `src/engine_events.py` — `AnalyzerListener` protocol plus `LogStatus`/`ArchiveEvent` dataclasses. Callbacks: `on_fight_completed(entry: FightHistoryEntry)`, `on_zone_changed(zone, difficulty)`, `on_log_status(status)`, `on_archive_event(event)`, `on_diagnostic(message)`.
- `src/fight_history.py` — `FightHistory`/`FightHistoryEntry` moved as-is (they already model exactly what a frontend needs).
- Analyzer/splitter/monitor keep their behavior but emit through `listeners: list[AnalyzerListener]` instead of touching `self.tui` or printing. `TuiDisplay` (~400 lines) and the Click `main()` are deleted, along with the `windows-curses`, `click`, and `colorama` dependencies.

Feature parity is protected by **engine-level characterization tests**: before the refactor, golden outputs (fight summary data, split-file names, report contents) are captured by replaying a fixture log through the current code; after extraction, the same goldens must hold. Terminal-output parity tests are irrelevant since the terminals are removed — the data is the contract.

The GUI runs `LogFileMonitor` + analyzer on a `QThread` worker; a thin adapter converts listener callbacks into Qt signals (queued connections) so all widget updates happen on the UI thread. Engine modules never import Qt.

### D3: Packaging — PyInstaller onedir GUI app + Inno Setup installer, Windows-only

- The PyInstaller spec's onefile CLI target is replaced by an `esolog-gui` onedir windowed target (onedir starts faster and triggers fewer antivirus false positives).
- **Inno Setup (chosen)** compiles `installer/esolog-gui.iss`: per-user install (no admin) to `{localappdata}\Programs\ESO Log Tail`, Start Menu entry, optional Desktop shortcut, uninstaller, stable `AppId` GUID so upgrades install in place. Inno Setup is preinstalled on GitHub `windows-latest` runners (`iscc` on PATH).
- *WiX/MSI*: heavier authoring model, no benefit at this scale. *MSIX*: hard signing requirements (and signing is out). *NSIS*: no advantage over Inno.
- `.github/workflows/build-installers.yml` keeps only the Windows job: build GUI target → compile installer → attach `esolog-tail-windows-setup-<version>.exe` and a portable `esolog-tail-windows-portable-<version>.zip` to the release. macOS/Linux jobs are removed.

### D4: Auto-archive — startup-only, size-based, in-use-guarded

**When**: exactly once, during app startup, *before* the tail/monitor attaches to the log. Rationale: ESO holds `Encounter.log` open for the whole game session, so mid-session archiving can never be safe; users start this app before (or without) the game far more often than mid-session.

**Trigger metric**: growth in file size since the last archive. `archive.size_threshold_mb` defaults to **1024 MB (1 GB ≈ five veteran trials)**. The settings dialog shows a sizing guide next to the field, calibrated from measured data: *"Veteran trial run ≈ 100–300 MB · veteran dungeon ≈ 25–75 MB · 1 GB ≈ ~5 trials"*. Size-based beats trial-counting: it needs no log scanning at startup (a 21 GB scan is minutes of I/O), it covers dungeon/PvP-only players, and its threshold is directly explainable in the UI.

**In-use guard**: before archiving, attempt to open the log with exclusive sharing via `CreateFileW(..., dwShareMode=0, OPEN_EXISTING, ...)` through `ctypes`. If the open fails with a sharing violation, ESO (or another process) has the file open → skip the archive, notify in the status area ("Archive skipped — Encounter.log is in use; close ESO and restart to archive"), and proceed to normal monitoring. The exclusive handle is held for the duration of the zip so ESO starting mid-archive cannot write to the file under us (ESO's own open attempt would then fail until we release — an accepted, short race documented in the code; the handle is released immediately after zipping).

**Archive operation** (new `src/log_archiver.py`):

1. Compute archive name `Encounter-YYMMDDHHMMSS.zip` from the latest log entry's timestamp (via the freshness derivation, D5), falling back to file mtime; write into `archive.dir` (default: the log's directory). Name collisions get `-1`, `-2` suffixes like split files.
2. Stream the file into the zip (`zipfile`, deflate, `allowZip64=True` — sources exceed 4 GB) in chunks, reporting progress (bytes done / total) through `on_archive_event`; the GUI shows a progress bar. A 21 GB source is minutes of work — the GUI stays responsive (archiver runs on the worker thread) and monitoring starts as soon as the archive finishes.
3. Verify: `ZipFile.testzip()` plus uncompressed-size match against the source.
4. Original: kept by default. `archive.delete_original` (opt-in, with explicit warning in settings) deletes only after verification passes — safe because we still hold the exclusive handle (delete-on-close semantics via re-open with `FILE_SHARE_DELETE`or plain `os.remove` after releasing, then re-verify absence).

**Re-trigger control**: persist `size_at_last_archive` (plus archive timestamp) in the app config. Auto-archive fires when `current_size - size_at_last_archive > threshold`. If the log shrank or vanished (user deleted/rotated), the marker resets to 0. With `delete_original` on, the marker naturally resets because a fresh log starts small.

**Manual action**: an "Archive now" button performs the same operation (same guard, no threshold check) at any time — useful when the user closes ESO and wants to archive without restarting the app.

### D5: Log freshness — derived from log content, not file mtime

`LogStatus` dataclass: `latest_entry_time: datetime | None`, `source: "exact" | "approximate" | "none"`, plus log path and size.

- While reading/tailing, latest entry time = most recent `BEGIN_LOG` epoch + last line's relative offset — the existing conversion at esolog_tail.py:1980-1982 (`source="exact"`).
- On startup before any read (or when attaching mid-file), read the trailing ~64 KB, take the last complete line's offset, and pair it with the most recent `BEGIN_LOG` epoch found by the existing lookback scan; if no `BEGIN_LOG` is reachable, fall back to file mtime with `source="approximate"`.
- Missing file → `source="none"`.

The GUI status bar shows `Last entry: 2026-09-27 14:33:02 (3m ago)`; the age re-renders on a 1 s UI timer from wall clock (no engine polling between entries). Visual states: **live** (< 2 min), **idle** (2–30 min), **stale** (> 30 min, amber), **no log** (red).

### D6: Settings — JSON config via platformdirs

Settings (log path, split/report dirs, archive options) persist to `platformdirs.user_config_dir("esolog-tail")/config.json`. JSON keeps the config human-readable and toolkit-independent (vs `QSettings`), and the installer's uninstall step leaves it untouched. Startup reads config → applies defaults (auto-detected log path via the existing `_find_eso_log_file` logic) → runs the archive check → starts monitoring. Runtime deps added: `PySide6`, `platformdirs`; removed: `windows-curses`, `click`, `colorama`.

Default monitoring mode is the equivalent of today's `--read-all-then-tail` for the fight history—except that fully re-parsing a 21 GB log at startup is unacceptable, so the default is **attach at end** (today's default tail mode with zone lookback) and a setting/history menu offers "Load recent history" (parse the trailing N MB). Opening a split/archived log for review replaces `--read-all-then-stop` replay.

## Risks / Trade-offs

- [Refactoring a 5,000-line module regresses analysis behavior] → Engine-level golden tests captured before the refactor; the existing test suite (updated to drop TUI/CLI cases) runs after each mechanical step.
- [BREAKING: users' `.BAT` workflows stop working] → README migration section maps every old flag to its GUI setting; CHANGELOG carries a prominent notice; version bumps to signal the break.
- [Zipping a file ESO may open mid-operation] → Exclusive-share handle held for the whole zip; skip-with-notification when the file is already in use; verification before any deletion.
- [Multi-GB archive blocks or appears to hang the app] → Chunked streaming with progress events on the worker thread; UI shows a progress bar and stays responsive; monitoring starts right after.
- [Size threshold misestimates content ("5 trials")] → It's a guide, not a contract: the settings UI shows measured per-trial sizes and the threshold is user-configurable.
- [PySide6 bloats the installer (~40 MB download)] → Accepted; onedir + Qt module exclusions keep it minimal.
- [Unsigned installer triggers SmartScreen "unknown publisher"] → Accepted per maintainer decision; documented in README (same situation as today's exe).

## Migration Plan

1. Land engine-level golden tests, then the engine extraction (TUI/CLI deleted, deps swapped); tests green.
2. Land freshness + startup archiver in the engine — unit-testable without the GUI.
3. Land the GUI package `src/gui/` and the `esolog-gui` build target.
4. Land installer script + CI rework (Windows-only); verify install/upgrade/uninstall on a clean Windows VM; tag a release candidate.
5. Rewrite README (GUI usage + flag→setting migration table), update BUILD_WINDOWS.md and CHANGELOG.md; delete the stale `gui/` Tauri scaffold.

Rollback: revert the release; the last CLI/TUI release remains downloadable. The engine refactor is guarded by the golden tests.

## Open Questions

- None blocking. (Resolved by maintainer: GUI replaces TUI/CLI; startup-only archiving; size-based trigger with in-UI sizing guide; Windows-only; no code signing.)
