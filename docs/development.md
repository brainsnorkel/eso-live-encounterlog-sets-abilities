# Development guide

How the repository is laid out, and how to run, test, build and release ESO Log Tail, and how to refresh its game data after an ESO patch. The [README](../README.md) covers installing the app, and the [user guide](user-guide.md) what it does.

## Repository layout

| Path | What it holds |
|---|---|
| `src/` | The app. Engine modules sit at the top level; the Qt frontend is the `gui/` package. |
| `data/` | Data bundled with the app: ability icons, ESO-Hub link maps, the item, buff, set, skill and client-name tables, `version.json` (the game version the tables match, and each table's date), and the LibSets workbook the gear set data is generated from. |
| `scripts/` | Scripts to build, refresh the game data, build the documentation and release, and local surveys and checks (see [Other scripts](#other-scripts)). None of them ships with the app. |
| `tests/` | The pytest suite: `unit/`, `integration/`, and `fixtures/` (a golden log and shared test data). |
| `installer/esolog-gui.iss` | The Inno Setup script for the Windows installer. |
| `esolog-tail.spec` | The PyInstaller spec, used for the Windows and Linux builds. |
| `.github/workflows/build-installers.yml` | CI: tests, builds, and the release on a version tag. |
| `.github/workflows/changelog.yml` | CI: each pull request adds a changelog fragment and leaves `CHANGELOG.md` and `docs/design.md` to the release commit. |
| `.github/workflows/pages.yml` | CI: builds and deploys the home page (see [Documentation](#documentation)). |
| `.github/workflows/stable-reminder.yml` | CI: every Monday, an issue when a beta has waited long enough to be made Stable (see [Releasing](#releasing)). |
| `changelog.d/` | The changelog fragments of the changes since the last release, one per change (see its [README](../changelog.d/README.md)). |
| `docs/` | The user guide and its pictures (`screencaps/`), this guide, the design notes built from the code (`design.md`), reference notes on the log format, research notes, and an archive. See [docs/README.md](README.md). |
| `site/` | The home page, published by GitHub Pages (see [Documentation](#documentation)). |
| `.claude/skills/` | [Claude Code](https://claude.com/claude-code) skills for this repository: `release` (cutting a beta, below), `refresh-ability-icons` and `export-esobuild-assets`. |
| `.beads/` | The configuration of the Beads (`bd`) issue tracker. The project's issues are on GitHub. |
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
| `update_check.py`, `autostart.py` | The GitHub release check on the Stable or Beta channel; the start-at-login toggle. |
| `version.py` | The version number. The only place it is defined. |
| `casts.py`, `resources.py`, `damage_kinds.py`, `pen_crit.py`, `build_issues.py`, `set_text.py` | Per player and fight: cast counts and casts per minute; magicka, stamina and ultimate spent and gained; the kinds of damage (direct or over time, area or single target, Martial or Magical); penetration and critical damage against the caps; possible build issues; a set's bonus text and the set behind a Major or Minor buff. |
| `companions.py`, `presence.py`, `boss_units.py`, `misfortunes.py` | Who is in a fight: companions on rows of their own, group members who leave and come back (on another character too), what a boss is (the game's flag, less the adds that carry it), and the Misfortunes a solo dungeon run was started with. |
| `fight_opener.py`, `waiting_hits.py`, `pull_outcome.py`, `trial_result.py`, `fight_index.py` | Around a fight: who opened it; the group's hits between fights and fighting on after one ends; kill or wipe, time dead and a boss's pulls in a row; a trial's or arena's result; every boss fight's figures across sessions, so a pull is set against the group's own earlier kills. |
| `fight_events.py`, `event_rows.py`, `fight_casts.py`, `action_rows.py` | The Events tab's data, without Qt: a fight's notable events and every group player's casts, kept on the fight entry in packed form, and the rows the tab shows, everyone's or one player's actions. |
| `fight_locator.py`, `fight_reread.py` | Where a fight's lines are in its log, kept on its entry, and re-reading that one fight's unit states from disk for the positions window, since the engine keeps no unit's place for a whole session. |
| `fight_blocks.py`, `session_splits.py`, `session_recap.py` | The fight list's instance blocks, the split files behind an instance, and the session as plain text (Copy session). |
| `review_load.py`, `log_open.py` | Opening a log for review (plain, a zipped split or an archive) and replaying it, without Qt, on a thread of its own. |
| `split_retention.py`, `recycle_bin.py`, `recent_activity.py`, `data_staleness.py` | Zipping old split logs and moving older ones to the Recycle Bin; the newest archives and splits for the pane before the first fight; the bundled game data against the game version the log names. |
| `banner_capture.py`, `desktop_duplication.py` | The trial's score banner, captured from the screen after `END_TRIAL`, through DXGI Desktop Duplication on Windows. |
| `gui/engine_worker.py`, `gui/review_runner.py` | The engine on a `QThread`, its listener callbacks turned into Qt signals; a review on a thread of its own while live monitoring polls on. |
| `gui/update_poller.py`, `gui/update_popup.py` | The 15-minute release check and the installer download on their own thread; the ⓘ popup with the release notes. |
| `gui/main_window.py`, `gui/fight_list.py`, `gui/fight_tabs.py`, `gui/fight_view.py`, `gui/events_tab.py`, `gui/dps_graph.py`, `gui/settings_dialog.py`, `gui/examples_dialog.py`, `gui/about.py` | The main window: the fight list in instance blocks, the fight's tabs (Fight, Deaths, Events, DPS graph, Instance) with the search in their corner, the page view the Fight, Deaths and Instance tabs share, and its dialogs, the example tracked-effect rules picker among them. |
| `gui/fight_render.py`, `gui/fight_deaths_render.py`, `gui/instance_render.py`, `gui/activity_render.py` | HTML and plain text for the main window's Fight, Deaths and Instance tabs, and for the pane before the first fight. They take fight data and return strings, so they are tested without a window. |
| `gui/player_window.py`, `gui/build_render.py`, `gui/damage_render.py`, `gui/taken_render.py`, `gui/death_render.py`, `gui/build_issues_popup.py` | A player's window, a tab for each of their pages, and the HTML for a build, a player's damage, their damage taken and a death recap, tested the same way; the ⓘ popup of a player's possible build issues. |
| `gui/positions_window.py`, `gui/positions_canvas.py` | The positions window: a fight from above at one moment, held still or played back, beside a table of the same units. |
| `gui/timeline_strip.py`, `gui/icon_cache.py`, `gui/glyphs.py`, `gui/name_mask.py`, `gui/text_size.py`, `gui/banner_burst.py` | The buff timeline strip, the icon cache, the small glyphs after the clickable figures, Hide names, the app-wide text size, and the GUI side of the banner capture. |

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
- Tests that create widgets set `QT_QPA_PLATFORM=offscreen` themselves, so no window opens; CI sets it for the whole run.
- `tests/conftest.py` turns Python's garbage collector off for the run and, after each test, closes any window the test left open (which stops its engine thread), deletes the app's top-level widgets and collects the garbage there, on the UI thread. Left to itself, a collection could run on an engine thread and free GUI objects off the UI thread, which can abort the process (issue #18). So a GUI test needs no teardown of its windows, and must not count on garbage being collected while it runs.
- With `pip install pytest` alone, the tests of the scripts that read the LibSets workbook are skipped: they need `openpyxl`, from `requirements-build.txt`, which CI installs with `requirements.txt`.
- `tests/integration/test_engine_golden.py` replays `tests/fixtures/golden_fight.log` and compares the fights and split files with `golden_fight_expected.json`. After a change that is meant to alter results, regenerate the expected file with `UPDATE_GOLDENS=1 python -m pytest tests/integration/test_engine_golden.py` and review its diff.
- CI runs the suite, about 2,700 tests, on Python 3.14 on Windows and Linux.

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

First see what the update broke. `scripts/check_data_staleness.py` reads a folder of logs (the app's split folder by default, `--dir` for another; about three minutes for 11 GB with `--workers 12`) and reports, game version by game version, the set ids, armor and weapon ids, bar icons and ESO-Hub set links the logs name and the bundle does not know, the sessions in which the app's status line would speak, and every id the app depends on (tracked effects, the build-issue rules, class passives and masteries, werewolf, companion, Fatecarver and cast ids) that appeared on the previous game version and in no session of the newest: a candidate for an id the game renumbered. Food is only hinted at there (effects with a food-style icon on a player with no listed food), as in `generate_food_buffs.py --check-log`. It changes nothing.

```cmd
python scripts\check_data_staleness.py --workers 12
```

The app bundles game data that goes stale when the game changes. Each table has a script in `scripts/` that rebuilds it:

```cmd
:: Ability and death-recap icons from your installed game (needs UESP's
:: EsoExtractData and Pillow; see the script's header for the paths it looks
:: for). About 2.5 minutes.
python scripts\extract_ability_icons.py --check-log "%USERPROFILE%\Documents\Elder Scrolls Online\live\Logs\Encounter.log"

:: ESO-Hub skill, set and scribing link maps, from ESO-Hub's sitemaps (network access)
python scripts\generate_esohub_links.py

:: Set names from your installed game, and a check of every bundled name
:: against it (needs UESP's EsoExtractData; about 20 seconds). It lists each
:: name that differs from the game's and exits 1 when there is one; run it
:: first, then the scripts below whose tables it names
python scripts\check_client_names.py --write-sets

:: Gear set data: names from the game (the step above), set types from
:: LibSets_SetData.xlsm in data/gear_sets/ (drop in a new one when LibSets
:: publishes it)
python scripts\generate_gear_data.py

:: Class skill line and Class Mastery passives by ability id, for the skill
:: lines and masteries beside a class, from UESP's player skill table (network
:: access; or --from a reply of theirs already saved)
python scripts\generate_class_passives.py

:: Every active skill of the six weapon skill lines by ability id, for the
:: build-issue rule that spots a weapon skill on a bar holding another weapon,
:: from UESP's player skill table (network access; or --from a reply of theirs
:: already saved)
python scripts\generate_weapon_skill_lines.py

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
:: window's two sections, and every set's bonus text, from UESP's set summary
:: (network access; or --from a reply of theirs already saved)
python scripts\generate_set_offense.py

:: The set behind a Major or Minor buff (Roaring Opportunist's Major Slayer),
:: by the buff's ability id, from your split logs and the bonus text above (no
:: network; the app's split folder, or --dir; about two minutes for 36 GB).
:: Review the table it prints before committing data/sets/set_buffs.json
python scripts\generate_set_buffs.py
```

The scripts that ask UESP send one trimmed request each; please do not run them in a loop.

Last, stamp the bundle with the game version it now matches. `data/version.json` holds that version, the date and each table's own date; the app compares the version with the one every logging session's `BEGIN_LOG` line names and shows an amber line in the status bar when the log is newer, and About lists the dates. The unit tests run `--check`, so a refreshed table whose stamp was forgotten fails them.

```cmd
:: The version as the client's log writes it, or --log <a log written today>
:: to read it from that log's BEGIN_LOG line
python scripts\stamp_data_version.py --game-version eso.live.12.2
```

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

The bundle is not committed. It is published as a release asset under a tag of its own, `esobuild-assets-<update>-<date>`, created with `gh release create ... --latest=false`: the app's Stable channel reads the repository's latest release, which must stay an app release, and its Beta channel reads the newest releases and counts only tags of exactly `vX.Y.Z`. The steps are packaged as the `export-esobuild-assets` skill.

## Documentation

Two documents are built from the app and the code rather than written by hand, so that they cannot drift:

- **User guide screenshots** (`docs/screencaps/`, shown in `docs/user-guide.md` and the README): `python scripts/capture_screenshots.py --log <a split log>` draws the app offscreen over that log, under a scratch config, and overwrites the PNG files (every one but `before-first-fight.png`, which is taken by hand). A veteran trial split log with a death and taunts gives the pictures the guide describes; `--boss` picks the fight, and the guide's are taken with `--hide-names`. Rerun it when a screen changes. The pixelated names differ from run to run, so a change to one screen is best captured with `--out` into a scratch folder, copying across only the pictures it changed. The home page shows some of the same pictures, so rerun `build_social_card.py` (below) when `main-window.png` changes.
- **Home page** (`site/`, published by GitHub Pages at https://xop.co/eso-live-encounterlog-sets-abilities/): `site/index.html` is written by hand, with `{{version}}` and the download links as placeholders. `python scripts/build_site.py` fills them from the latest GitHub release (the Stable one), adds a smaller line naming the newest beta when one is newer, and copies the page, its favicon and social card, and the screenshots it uses from `docs/screencaps/` into `_site/` (not tracked); `--release-json <file>` (and `--releases-json <file>` for the beta line) builds from saved releases for work offline, and `--site-url` changes the absolute URLs if the site ever moves. `.github/workflows/pages.yml` runs it and deploys `_site/` after a change to the page's sources on `main`, after every *Build Installers* run of a tag (a new beta), when a beta is made Stable or pulled (`scripts/promote_release.py` starts it, since the `github-pages` environment deploys from `main` only and a release event would run on the tag), and on request (`gh workflow run pages.yml`). The repository's Pages source must be *GitHub Actions*. `python scripts/build_social_card.py` draws `site/social-card.png` (1280×640, the picture a pasted link unfurls with, and the file to upload as the repository's social preview under Settings → General) and `site/favicon.png` from the icon and `docs/screencaps/main-window.png`; rerun it when the main-window screenshot changes, and commit both files.
- **Boss flag survey** (`src/boss_units.py`): `python scripts/survey_boss_flag.py <logs dir>` scans a folder of encounter logs and lists every unit the game flags as a boss, by zone, with its health as a share of the largest flagged unit of its fight and the fights it was hit in. A unit well under a tenth of its fight's boss (the Defense Prisms of Xoryn's gauntlet, the Sea Adders of Yandir's fight) belongs in `BOSS_FLAG_ADDS`; rerun it after a new trial.
- **Design notes** (`docs/design.md`): `python scripts/build_design_doc.py` collects the design notes kept in the code. The rule is that the explanation of a hard problem (what the log carries, which data source is trusted, why a rule was chosen after measuring real logs) lives in the docstring of the function or module that solves it, or in a comment block that starts with `# Design: <Title>`, next to the code it has to keep honest. The script's `TOPICS` list names the sources; add an entry for a new problem. The document holds no text of its own, and only the release commit rebuilds it (issue #134): a pull request edits the docstrings and leaves `docs/design.md` alone, so two pull requests never conflict over it. Run the script to preview the result; `--check` says whether the document matches the code, which the Linux build job requires of every tag.

## Other scripts

Local tools, run by hand; each one's docstring has its usage.

| Script | What it does |
|---|---|
| `scripts/check_fight_reread.py` | Checks the fight re-reader (`fight_reread.py`) against the engine on real split logs. Run it after any change to the engine's identity rules, the fight locator or the log format. |
| `scripts/dedupe_splits.py` | Moves byte-identical copies of split logs, which versions before 0.18.0 wrote, to the Recycle Bin (issue #85). |
| `scripts/survey_fight_opener.py`, `scripts/survey_masteries.py` | Replay a folder of logs through the engine and count who opens fights (issue #159), and which Class Masteries the fight pane shows (issue #149, for `generate_class_passives.MASTERIES_TAKEN`). |
| `scripts/simulate_eso_logging.py` | Copies a log into another file a few lines at a time, as the game writes it, to try the tailing without playing. |
| `scripts/changelog_check.py` | The *Changelog* check `.github/workflows/changelog.yml` runs on each pull request (see [Releasing](#releasing)). |

## Releasing

Every release is first a **beta**; a beta that has been used in real fights for a while with nothing found is made the **Stable** release (issue #134). The app offers Stable by default and every beta on its Beta channel; the home page's buttons name Stable, with a smaller line for a newer beta. `main` stays the only long-lived branch: no release or hotfix branches.

**Cutting a release (a beta)**

1. Each change adds its notes as a fragment, `changelog.d/<issue>-<slug>.md`, under the same `### Added` / `### Changed` / `### Fixed` headings `CHANGELOG.md` uses (or `Deprecated`, `Removed`, `Security`) ([changelog.d/README.md](../changelog.d/README.md)). The *Changelog* check on every pull request asks for one, or for the `no-changelog` label on a change that needs no entry, and refuses edits to `CHANGELOG.md` and `docs/design.md`.
2. On the branch of the last pull request of the release, or a pull request of its own (`main` takes pull requests only), `python scripts/release.py minor` (or `major`, `patch`, or `X.Y.Z`) makes the release commit: the version in `src/version.py`, the fragments gathered under `## [X.Y.Z] - YYYY-MM-DD` at the top of `CHANGELOG.md` and removed, `docs/design.md` rebuilt, committed as `chore: release X.Y.Z`. `--dry-run` shows the notes first; `--trailer "<line>"` (repeatable) ends the commit message with that line, a co-author for instance, and `--date` sets the release date (today by default). A release with only *Fixed* or *Security* entries is a patch.
3. Once that pull request is merged, `python scripts/release.py --tag X.Y.Z --push --watch` tags its merge commit after the release job's own tag checks (and its own: the design notes current, no fragment left in `changelog.d/`), pushes the tag, follows the run and checks that the beta came out as a pre-release with its three files while Stable stayed where it was. `--dry-run` runs the checks and makes nothing; without `--push` it makes the tag and prints the push command.

A fragment that reaches the release branch after the release commit (with a merge of `main`, which the branch needs before it can merge) would ship its change in this release and its note in the next. The *Changelog* check and `--tag` both refuse that; revert the release commit and run step 2 again.

The tag runs `.github/workflows/build-installers.yml`: a Windows job (the tests, then the installer and the portable zip) and a Linux job (the tests, then the tarball, with a start-up smoke test under xvfb) side by side, then the release job, which needs both. A failure in either build stops the release. A tag whose design notes lag the code fails at the start of the Linux build (`scripts/build_design_doc.py --check`). The release job first runs `scripts/release_guard.py`, which refuses a tag that is not `vX.Y.Z`, does not match the tagged commit's `src/version.py`, or is not on `main`; then it publishes the three files as a GitHub **pre-release**, with notes generated from the previous `v*` tag. A pre-release is never GitHub's latest release, so Stable users and the home page's buttons do not move.

To run the workflow without releasing, push a branch and start it by hand (`gh workflow run build-installers.yml --ref <branch>`); the release job only runs for tags. Pull requests to `main` run the builds too.

**Making a beta Stable**

`python scripts/promote_release.py --candidates` lists the betas newer than Stable and what each still lacks. A beta may be made Stable once it is newer than the Stable release and carries all three files, was published at least 48 hours ago, has been used live in at least one session with fights, and no issue labelled `regression` affects it. A regression issue names the version that brought the fault in, as the first `X.Y.Z` in its title (`Regression in v0.27.1: …`); it marks that version and every later one released before the issue was closed, and one whose title names no version blocks every beta until it does. Then:

```
python scripts/promote_release.py vX.Y.Z --used-live --dry-run   # the checks and the notes
python scripts/promote_release.py vX.Y.Z --used-live
```

The script rewrites the release notes as the changes since the previous Stable release, turns the pre-release into a full release, marks it latest, checks that `/releases/latest` names it, and starts the Pages workflow. `--force "<reason>"` makes a beta Stable before it meets the time, live-use and regression rules (a crash fix that cannot wait two days); the reason goes into the notes. Nothing overrides the first rule: a beta older than Stable, or one missing a file, is never made Stable.

A fix for Stable goes through `main` like any other change: merge it, cut a beta, run it once, then make it Stable with `--force`. If the Stable release itself is bad, `python scripts/promote_release.py --demote vX.Y.Z` pulls it: it becomes a draft again, which neither channel nor the home page shows, and the previous Stable release is latest again. Installs that already updated keep it; `gh release edit vX.Y.Z --draft=false --prerelease` publishes it again as a beta.

Sessions may point out a beta that qualifies; only the maintainer's word makes one Stable. `.github/workflows/stable-reminder.yml` runs `python scripts/promote_release.py --remind` every Monday, which opens an issue when a beta that meets the time and regression rules has waited more than 14 days.
