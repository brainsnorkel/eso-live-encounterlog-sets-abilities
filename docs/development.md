# Development guide

How the repository is laid out, and how to run, test, build and release ESO Log Tail, and how to refresh its game data after an ESO patch. The [README](../README.md) covers installing the app, and the [user guide](user-guide.md) what it does.

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
| `damage_stats.py` | Dps time and each player's damage by ability and by target, as Combat Metrics defines them. |
| `app_startup.py` | Startup order without Qt: config, log path, archive check, monitor. |
| `app_config.py` | The per-user `config.json`. |
| `player_build.py`, `scribing.py`, `death_recap.py`, `buff_timeline.py` | Per-fight detail: gear, mundus and food; scribed skills; death recaps; the buff timeline's built-in rows. |
| `werewolf.py` | Werewolf form: the bar the log never writes, rebuilt from the skills cast in form, the share of a fight spent in form, and the morph a Rampage in a bar stands in for. |
| `effect_rules.py` | Tracked effects: the rule text format (scopes, measures, `expected` group sizes), the HyperTools import, the default and example rules, the once-only upgrade of a saved rules text, and `EffectTracker`, which measures each rule per fight, Touch of Z'en's DoT count included. |
| `effect_summary.py` | Who applied an effect and who had it over a fight, for the timeline strip's click popup. |
| `eso_sets.py` | Skill line tables and the class passive data (`data/skills/class_passives.json`), for the skill lines and Class Mastery passives shown beside a class. |
| `gear_set_database.py`, `gear_set_data.py` | Gear set lookups. `gear_set_data.py` is generated; do not edit it. |
| `ability_icons.py` | Icon file names and ESO-Hub link lookups. |
| `log_archiver.py`, `log_freshness.py` | Archiving an oversized log; the "Last entry" indicator. |
| `update_check.py`, `autostart.py` | The GitHub release check; the start-at-login toggle. |
| `version.py` | The version number. The only place it is defined. |
| `gui/engine_worker.py` | Runs the engine on a `QThread` and turns listener callbacks into Qt signals. |
| `gui/update_poller.py`, `gui/update_popup.py` | The 15-minute release check and the installer download on their own thread; the ⓘ popup with the release notes. |
| `gui/main_window.py`, `gui/fight_view.py`, `gui/settings_dialog.py`, `gui/examples_dialog.py`, `gui/about.py` | The main window and its dialogs, the example tracked-effect rules picker among them. |
| `gui/fight_render.py`, `gui/build_render.py`, `gui/damage_render.py`, `gui/death_render.py` | HTML and plain text for a fight, a build, a player's damage and a death recap. They take fight data and return strings, so they are tested without a window. |
| `gui/build_dialog.py`, `gui/damage_dialog.py`, `gui/death_recap_dialog.py`, `gui/dps_graph.py`, `gui/timeline_strip.py`, `gui/icon_cache.py`, `gui/glyphs.py` | The build, damage and death recap windows, the dps over time graph, the buff timeline strip, the icon cache, and the small glyphs drawn after the dps figures to show they can be clicked. |

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

## Refreshing game data after an ESO patch

The app bundles nine data sets that go stale when the game changes. Each has a script in `scripts/` that rebuilds it:

```cmd
:: Ability and death-recap icons from your installed game (needs UESP's
:: EsoExtractData and Pillow; see the script's header for the paths it looks
:: for). About 2.5 minutes.
python scripts\extract_ability_icons.py --check-log "%USERPROFILE%\Documents\Elder Scrolls Online\live\Logs\Encounter.log"

:: ESO-Hub skill, set and scribing link maps, from ESO-Hub's sitemaps (network access)
python scripts\generate_esohub_links.py

:: Gear set data, after dropping a new LibSets_SetData.xlsm into data/gear_sets/
python scripts\generate_gear_data.py

:: Class skill line and Class Mastery passives by ability id, for the skill
:: lines and masteries beside a class, from UESP's player skill table (network
:: access; or --from a reply of theirs already saved)
python scripts\generate_class_passives.py

:: Poison names for the build window, from UESP's item database (network access)
python scripts\generate_poison_names.py

:: Food and drink buff ids for the build window, from the LibFoodDrinkBuff addon
:: (your installed copy, else its ESOUI download)
python scripts\generate_food_buffs.py

:: Weapon types (inferno staff, dagger, shield, ...) for the build window and
:: the healer role, from UESP's item database (network access; or --from a
:: reply of theirs already saved)
python scripts\generate_weapon_types.py

:: Armor weights (light, medium, heavy) for the build window, from UESP's item
:: database (network access)
python scripts\generate_armor_weights.py

:: Player skills' target kinds (area or single target) for the kinds of damage
:: in the death recap and build windows, from the UESP skill table the esobuild
:: export caches under build\esobuild-assets\sources (no request; --fetch makes one)
python scripts\generate_ability_targets.py

:: What each set does for penetration and critical damage, for the build
:: window's two sections, from UESP's set summary (network access; or --from a
:: reply of theirs already saved)
python scripts\generate_set_offense.py
```

The scripts that ask UESP send one trimmed request each; please do not run them in a loop.

After a patch, `python scripts\generate_food_buffs.py --check-log <path to Encounter.log>` lists food-style effects in a recent log that the bundled table does not know yet, so a new food is noticed before it reads as "no food" in the build window.

The icon step is also packaged as the `refresh-ability-icons` skill for Claude Code users of this repository. The icon script reports which icons were added or removed and, with `--check-log`, verifies that every ability slotted in that log has an icon.

## Exporting game data for esobuild.com

[esobuild.com](https://esobuild.com) shows the game's ability icons and names each build by its class skill lines, so it needs the icons under the game's file names and tables keyed by the game's ids. `scripts/export_esobuild_assets.py` builds both into one zip after a patch: every `ability_*` icon at 64 px, an ability table (game ability id to name, icon, skill line and type), the skill lines, the mundus boons and the sets with their ESO-Hub pages.

```cmd
:: The ESO-Hub maps the bundle copies (network access)
python scripts\generate_esohub_links.py

:: Tables and checks only: no icons extracted, nothing written. About 15 seconds.
python scripts\export_esobuild_assets.py --update u51 --dry-run

:: The bundle, in build\esobuild-assets\. About 3 minutes. --previous lists what
:: the patch added, removed and changed.
python scripts\export_esobuild_assets.py --update u51 --previous <the last bundle.zip>
```

`--update` is the site's tag for the update the client is on; it is never guessed. The client version in the bundle's manifest comes from the game's own build stamp. Icons come from the installed game, as for the app's own icons. Abilities and sets come from [UESP's ESO log export](https://esolog.uesp.net) (CC-BY-SA 2.5): four requests per run, a few seconds apart, with the replies kept under `build\esobuild-assets\sources\` and reused for a day, so further runs ask UESP nothing; if UESP refuses a request the script stops and does not retry. `--check-fixtures <folder>` runs the site's hand-over checks against its fixture files, and `--check-log <Encounter.log>` compares the tables with what the client itself logged, which shows whether UESP has caught up with a new update.

The bundle is not committed. It is published as a release asset under a tag of its own, `esobuild-assets-<update>-<date>`, created with `gh release create ... --latest=false`: the app's update check reads the repository's latest release, which must stay an app release. The steps are packaged as the `export-esobuild-assets` skill.

## Documentation

Two documents are built from the app and the code rather than written by hand, so that they cannot drift:

- **User guide screenshots** (`docs/screencaps/`, shown in `docs/user-guide.md` and the README): `python scripts/capture_screenshots.py --log <a split log>` draws the app offscreen over that log, under a scratch config, and overwrites the PNG files. A veteran trial split log with a death and taunts gives the pictures the guide describes; `--boss` picks the fight. Rerun it when a screen changes.
- **Home page** (`site/`, published by GitHub Pages at https://xop.co/eso-live-encounterlog-sets-abilities/): `site/index.html` is written by hand, with `{{version}}` and the download links as placeholders. `python scripts/build_site.py` fills them from the latest GitHub release and copies the page, its favicon and social card, and the screenshots it uses from `docs/screencaps/` into `_site/` (not tracked); `--release-json <file>` builds from a saved release for work offline, and `--site-url` changes the absolute URLs if the site ever moves. `.github/workflows/pages.yml` runs it and deploys `_site/` after a change to the page's sources on `main`, after every *Build Installers* run of a tag (the release the buttons point at), and on request (`gh workflow run pages.yml`). The repository's Pages source must be *GitHub Actions*. `python scripts/build_social_card.py` draws `site/social-card.png` (1280×640, the picture a pasted link unfurls with, and the file to upload as the repository's social preview under Settings → General) and `site/favicon.png` from the icon and `docs/screencaps/main-window.png`; rerun it when the main-window screenshot changes, and commit both files.
- **Boss flag survey** (`src/boss_units.py`): `python scripts/survey_boss_flag.py <logs dir>` scans a folder of encounter logs and lists every unit the game flags as a boss, by zone, with its health as a share of the largest flagged unit of its fight and the fights it was hit in. A unit well under a tenth of its fight's boss (the Defense Prisms of Xoryn's gauntlet, the Sea Adders of Yandir's fight) belongs in `BOSS_FLAG_ADDS`; rerun it after a new trial.
- **Design notes** (`docs/design.md`): `python scripts/build_design_doc.py` collects the design notes kept in the code. The rule is that the explanation of a hard problem (what the log carries, which data source is trusted, why a rule was chosen after measuring real logs) lives in the docstring of the function or module that solves it, or in a comment block that starts with `# Design: <Title>`, next to the code it has to keep honest. The script's `TOPICS` list names the sources; add an entry for a new problem, and rerun the script whenever one of those docstrings changes. The document holds no text of its own.

## Releasing

1. Changes add their notes under `## [Unreleased]` at the top of `CHANGELOG.md` as they are made.
2. The release commit sets the version in `src/version.py` (`__version__` and `__version_info__`) and renames `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`.
3. Push an annotated tag `vX.Y.Z`.

The tag runs `.github/workflows/build-installers.yml`: tests, then the Windows installer and portable zip, then the Linux tarball (with a start-up smoke test under xvfb), then a GitHub release carrying all three files. A failure in either build stops the release. The app's update check reads that release, so a published tag is what users are offered.

To run the workflow without releasing, push a branch and start it by hand (`gh workflow run build-installers.yml --ref <branch>`); the release job only runs for tags. Pull requests to `main` run the builds too.
