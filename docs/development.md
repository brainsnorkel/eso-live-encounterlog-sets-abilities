# Development guide

How the repository is laid out, and how to run, test, build and release ESO Log Tail. The [README](../README.md) covers what the app does.

## Repository layout

| Path | What it holds |
|---|---|
| `src/` | The app. Engine modules sit at the top level; the Qt frontend is the `gui/` package. |
| `data/` | Data bundled with the app (ability icons, ESO-Hub link maps, item and buff tables), and the LibSets workbook the gear set data is generated from. |
| `scripts/` | Build-time and data-refresh scripts. None of them ships with the app. |
| `tests/` | The pytest suite: `unit/`, `integration/`, and `fixtures/` (a golden log and shared test data). |
| `installer/esolog-gui.iss` | The Inno Setup script for the Windows installer. |
| `esolog-tail.spec` | The PyInstaller spec, used for the Windows and Linux builds. |
| `.github/workflows/build-installers.yml` | CI: tests, builds, and the release on a version tag. |
| `docs/` | This guide, reference notes on the log format, research notes, and an archive. See [docs/README.md](README.md). |
| `openspec/` | Change proposals written with [OpenSpec](https://github.com/Fission-AI/OpenSpec). Completed ones are under `changes/archive/`. |

`src/` is a folder of modules, not an installable package. The app runs with `src/` on the import path (`python src/esolog_gui.py`), PyInstaller freezes it from there, and pytest adds it through `pyproject.toml`. So modules import each other by bare name: `from fight_history import FightHistory`.

### How the code is divided

The engine knows nothing about Qt. It reads log lines, tracks the fight, and reports results through the listener interface in `engine_events.py`. The frontend subscribes to it.

| Module | Role |
|---|---|
| `esolog_gui.py` | Entry point: crash log, config, main window. |
| `esolog_tail.py` | The engine. `ESOLogAnalyzer` turns log entries into fights, `LogSplitter` writes the per-encounter split files, `LogFileMonitor` tails the log. |
| `eso_log_parser.py`, `eso_log_structures.py` | Parsing of log lines into typed entries. |
| `engine_events.py` | `AnalyzerListener`: the contract between the engine and a frontend. |
| `fight_history.py` | `FightHistoryEntry`, the summary of one fight that the engine hands to the frontend. |
| `app_startup.py` | Startup order without Qt: config, log path, archive check, monitor. |
| `app_config.py` | The per-user `config.json`. |
| `player_build.py`, `scribing.py`, `death_recap.py`, `buff_timeline.py` | Per-fight detail: gear, mundus and food; scribed skills; death recaps; the experimental buff timeline. |
| `eso_sets.py` | Skill line tables, for the subclass lines shown beside a class. |
| `gear_set_database.py`, `gear_set_data.py` | Gear set lookups. `gear_set_data.py` is generated; do not edit it. |
| `ability_icons.py` | Icon file names and ESO-Hub link lookups. |
| `log_archiver.py`, `log_freshness.py` | Archiving an oversized log; the "Last entry" indicator. |
| `update_check.py`, `autostart.py` | The GitHub release check; the start-at-login toggle. |
| `version.py` | The version number. The only place it is defined. |
| `gui/engine_worker.py` | Runs the engine on a `QThread` and turns listener callbacks into Qt signals. |
| `gui/main_window.py`, `gui/fight_view.py`, `gui/settings_dialog.py`, `gui/about.py` | The main window and its dialogs. |
| `gui/fight_render.py`, `gui/build_render.py`, `gui/death_render.py` | HTML and plain text for a fight, a build and a death recap. They take fight data and return strings, so they are tested without a window. |
| `gui/build_dialog.py`, `gui/death_recap_dialog.py`, `gui/timeline_strip.py`, `gui/icon_cache.py` | The build and death recap windows, the buff timeline strip, the icon cache. |

## Running from source

CI tests and builds with Python 3.14, so that is the version to develop on. The tests also passed on 3.11 and 3.13 when CI moved to 3.14 (October 2026); CI does not check those versions.

```cmd
pip install -r requirements.txt
python src/esolog_gui.py
```

The app reads and writes your real settings (`%LOCALAPPDATA%\esolog-tail\config.json`), including the archive options. To try a change without touching them, set `WIN_PD_OVERRIDE_LOCAL_APPDATA` to a scratch folder before starting the app; it then keeps its config there.

## Tests

```cmd
pip install pytest
python -m pytest
```

- `pyproject.toml` tells pytest where the tests are and puts `src/` and `tests/fixtures/` on the import path. Test files need no path setup of their own.
- Tests that create widgets set `QT_QPA_PLATFORM=offscreen` themselves, so no window opens.
- `tests/integration/test_engine_golden.py` replays `tests/fixtures/golden_fight.log` and compares the fights and split files with `golden_fight_expected.json`. After a change that is meant to alter results, regenerate the expected file with `UPDATE_GOLDENS=1 python -m pytest tests/integration/test_engine_golden.py` and review its diff.
- CI runs the suite on Python 3.14 on Windows and Linux.

## Building

Build tools are in `requirements-build.txt`. The installer also needs [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`).

```cmd
pip install -r requirements.txt
pip install -r requirements-build.txt

:: Gear set data, whenever data/gear_sets/LibSets_SetData.xlsm changes
python scripts/generate_gear_data.py

:: App icon -> icon.ico and icon.png at the repository root (not tracked)
python scripts/create_icon.py

:: GUI executable (onedir, windowed) -> dist\esolog-gui\
python -m PyInstaller esolog-tail.spec --noconfirm

:: Installer -> dist\esolog-tail-windows-setup-<version>.exe
iscc /DAppVersion=<version> installer\esolog-gui.iss

:: Portable zip (optional)
powershell Compress-Archive -Path dist\esolog-gui\* -DestinationPath dist\esolog-tail-windows-portable-<version>.zip
```

`dist\esolog-gui\esolog-gui.exe` should open the main window. The installer is per-user (no administrator rights), registers in Apps & Features, and upgrades in place because its `AppId` never changes. Uninstalling leaves the user's config and archived logs. Nothing is code-signed, so SmartScreen shows "unknown publisher".

A module that PyInstaller cannot find by following imports must be listed under `hiddenimports` in `esolog-tail.spec`, and a new data folder under `datas`.

On Linux the same PyInstaller command builds `dist/esolog-gui/`, which CI packs into the release tarball. Build on the oldest distribution you want to support, with Qt's X11 and Wayland libraries installed (the package list is in the workflow file): PyInstaller bundles the ones it finds.

## Refreshing bundled data

The data under `data/` and `src/gear_set_data.py` go stale when the game is patched. Each has a script in `scripts/` that rebuilds it; the commands and what each needs are in the README under [Refreshing game data after an ESO patch](../README.md#refreshing-game-data-after-an-eso-patch).

## Releasing

1. Changes add their notes under `## [Unreleased]` at the top of `CHANGELOG.md` as they are made.
2. The release commit sets the version in `src/version.py` (`__version__` and `__version_info__`), renames `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`, and updates the `iscc /DAppVersion=` example in the README.
3. Push an annotated tag `vX.Y.Z`.

The tag runs `.github/workflows/build-installers.yml`: tests, then the Windows installer and portable zip, then the Linux tarball (with a start-up smoke test under xvfb), then a GitHub release carrying all three files. A failure in either build stops the release. The app's update check reads that release, so a published tag is what users are offered.

To run the workflow without releasing, push a branch and start it by hand (`gh workflow run build-installers.yml --ref <branch>`); the release job only runs for tags. Pull requests to `main` run the builds too.
