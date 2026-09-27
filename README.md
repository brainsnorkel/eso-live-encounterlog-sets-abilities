# ESO Log Tail

Live monitoring of Elder Scrolls Online encounter logs in a desktop app. ESO Log Tail watches your `Encounter.log` and shows a summary of every fight as soon as combat ends: who's in the group, how they're built, and how they performed.

- Fight summaries the moment combat ends (zone, boss, duration, group DPS)
- Subclass/build inference and gear set identification (722 LibSets sets)
- Players sorted by DPS with damage share, resources, and role (Tank/Healer/DPS)
- Group buff uptimes (Major Courage, Major Force, Major Slayer, PA, LE, PW)
- Per-encounter split log files and saved zone reports
- Automatic archiving of oversized encounter logs (they grow into the tens of GB)
- "Last entry" freshness indicator so you can tell at a glance that logging is on

> **v0.3.0 is a breaking release**: the terminal UI and command-line options are gone; ESO Log Tail is now a windowed app. See [Migrating from the terminal version](#migrating-from-the-terminal-version).

## Installation

### Option 1: Installer (recommended)

1. Download `esolog-tail-windows-setup-<version>.exe` from the [latest release](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/releases).
2. Run it. No administrator rights are needed (per-user install). If Windows SmartScreen shows "unknown publisher", choose **More info → Run anyway** — the installer is not code-signed.
3. Launch **ESO Log Tail** from the Start Menu. Installing a newer version later upgrades in place; your settings are kept.

### Option 2: Portable zip

Download `esolog-tail-windows-portable-<version>.zip`, extract it anywhere, and run `esolog-gui.exe`.

### Option 3: From source

```bash
git clone https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities.git
cd eso-live-encounterlog-sets-abilities
pip install -r requirements.txt
python src/esolog_gui.py
```

## Enable ESO encounter logging

ESO only writes `Encounter.log` when encounter logging is on.

- **Automatic (recommended)**: install the [Easy Stalking - Encounterlog](https://www.esoui.com/downloads/info2332-EasyStalking-Encounterlog.html) addon to start/stop logging by content type, with an on-screen indicator and `/ezlog` chat command.
- **Manual**: type `/encounterlog` in-game, or enable it under Settings → Combat → Combat Logging.

## Using the app

Launch ESO Log Tail (before or during play — both work). It auto-detects `Encounter.log` across the known ESO locations (including OneDrive-relocated Documents folders) and picks the most recently updated one. If no log exists yet, the app waits and attaches automatically when it appears.

- **Live view**: each completed fight appears in the history list; the newest is shown automatically. Selecting an older fight pauses following; selecting the newest resumes it.
- **Detail view** (toolbar toggle): expands each player with skill lines, both ability bars, and full gear sets.
- **Copy fight**: copies the selected fight summary as plain text to the clipboard.
- **Open log for review**: load any log file — a split file, an unzipped archive — and browse its fights without disturbing live monitoring. "Back to live" returns to the live session.
- **Status bar**: shows the current zone and the log freshness indicator:
  - `Last entry: 2026-09-27 14:33:02 (40s ago)` — **live** (green) under 2 minutes, normal up to 30 minutes, **stale** (amber) beyond that, and **No log file** (red) when nothing is being monitored. A `~` prefix means the time came from the file clock rather than log content.

### Settings

Open **Settings…** from the toolbar:

- **Encounter log**: pick a specific `Encounter.log`, or leave blank to auto-detect.
- **Split files**: write each encounter to its own `YYMMDDHHMMSS-{Zone-Name}{-vet}.log` in a folder of your choice.
- **Reports**: save per-zone text reports named `YYMMDDHHMMSS-{Zone-Name}{-vet}-report.txt`.
- **Archiving**: see below.

Settings persist in a per-user config file and survive upgrades and uninstalls.

### Automatic updates

At startup the app checks GitHub for a newer release (Settings → Updates to disable). When one exists you're prompted with **Update now / Later / Skip this version**; updating downloads the installer with a progress bar, closes the app, and hands over to the installer — settings are kept and the app relaunches when it finishes. Nothing is ever installed without the prompt.

### Experimental: buff timeline

Settings → Experimental → *Buff timeline* (off by default) adds a very compact strip above each fight summary: one thin colored line per tracked effect — Major Slayer, Major Force, Major Courage, Major Berserk, Powerful Assault, and Major Vulnerability — filled where the effect was active, with the effect's uptime % in its label and time tick marks. A group buff that only reached one or two people renders dotted rather than solid. Hover a segment to see who cast it and who received it. When the strip is shown it replaces the text uptime line on the fight header; rows for effects that never occurred are omitted, and the strip disappears entirely when there's nothing to show. Being experimental, its look and behavior may change or it may be removed.

## Automatic log archiving

ESO never truncates `Encounter.log`; with regular raiding it grows by hundreds of MB per night and can reach tens of GB. ESO Log Tail archives it for you:

- **When**: checked **once, at app startup**. ESO keeps the log file open for the entire game session (even between `/encounterlog` toggles), so start-up — typically before you launch ESO — is the safe moment to archive.
- **Trigger**: the log has grown more than the configured threshold since the last archive. Default **1024 MB ≈ five veteran trials** (a vet trial run is typically 100–300 MB; a vet dungeon roughly 25–75 MB).
- **What it does**: streams the log into `Encounter-YYMMDDHHMMSS.zip` (timestamped from the newest log entry) in the archive folder (default: next to the log), showing progress in the status bar. The archive is verified before being reported as complete.
- **Safety**: the app takes exclusive access to the log for the whole operation. If ESO is running and holds the file, the archive is **skipped with a notification** and monitoring starts normally — nothing is ever zipped mid-write.
- **Your original log is kept** by default. If you enable *Delete Encounter.log after a verified archive* in Settings, the original is removed only after the zip verifies — from then on ESO starts a fresh, small log.
- **Archive now** (toolbar): runs the same guarded archive at any moment — handy right after you close ESO, without restarting the app.

## Migrating from the terminal version

Versions up to 0.2.7 were terminal applications launched from `.BAT` files with CLI flags. Those flags are gone; their behavior moved into the GUI:

| Old CLI flag | Where it went |
|---|---|
| `-f, --log-file PATH` | Settings → Encounter log |
| `--tail-and-split` / `--split-dir` | Settings → Split files |
| `--save-reports` / `--reports-dir` | Settings → Reports |
| `--read-all-then-tail` | Automatic: the app attaches to the live log; use *Open log for review* to inspect older fights |
| `--read-all-then-stop` (replay) | *Open log for review* |
| `--no-wait` | Removed: the app always waits and shows a waiting state |
| `--replay-speed` | Not needed: review mode loads at full speed |
| `--no-tui` | Removed with the terminal output |
| `--diagnostic`, `--list-hostiles` | Removed (diagnostics surface in the status bar) |
| `-v, --version` | Window title / Apps & Features |

Delete your old `.BAT` files and `esolog-tail.exe`; the app is `esolog-gui.exe`.

## ESO log file locations

Auto-detection searches, and picks the most recently updated of:

**Windows**
- `%USERPROFILE%\Documents\Elder Scrolls Online\live\Logs\Encounter.log`
- `%USERPROFILE%\Documents\Elder Scrolls Online\Logs\Encounter.log`
- `%USERPROFILE%\OneDrive\Documents\Elder Scrolls Online\live\Logs\Encounter.log`

## What the analysis shows

For each completed fight:

- **Header**: zone (with VETERAN tag), primary boss, start time, duration, group DPS, deaths
- **Group buffs**: uptime percentages for Major Courage, Major Force, Major Slayer, Powerful Assault, Lucent Echoes, Pearlescent Ward
- **Per player** (sorted by damage share): role (T/H/D, inferred from resources and healing output), name and class, DPS and damage %, max health/magicka/stamina, inferred skill lines (e.g. `Herald/Aedric/Ardent`), both ability bars, and equipped gear sets with piece counts

### How it works

- **Skill line detection** analyzes equipped abilities against UESP's ability-to-skill-line mappings (class, weapon, and guild lines).
- **Gear set identification** maps item set IDs through the [LibSets](https://github.com/Baertram/LibSets/tree/LibSets-reworked/LibSets) database (722 sets).
- **Role inference** classifies Tank/Healer/DPS from resource pools, healing-vs-damage output, and taunt/heal ability fallbacks.

### Limitations

- Players are anonymous ("unknown" builds) until ABILITY_INFO/PLAYER_INFO events are observed for them
- Set identification is limited to sets present in the LibSets database
- ESO logs track 13 gear slots (the backup off-hand slot is not logged)

## Building from source

Prerequisites: Python 3.9+ (3.11 recommended) on Windows.

```cmd
pip install -r requirements.txt
pip install -r requirements-build.txt

:: Regenerate gear data whenever data/gear_sets/LibSets_SetData.xlsm is updated
python scripts/generate_gear_data.py

:: Icon (writes icon.ico)
python scripts/create_icon.py

:: Tests
python -m pytest tests/ -q

:: GUI executable (onedir, windowed) -> dist/esolog-gui/
python -m PyInstaller esolog-tail.spec --noconfirm

:: Installer (requires Inno Setup 6) -> dist/esolog-tail-windows-setup-<version>.exe
iscc /DAppVersion=0.3.0 installer\esolog-gui.iss
```

Tagged releases (`v*`) build both artifacts automatically via GitHub Actions.

## Troubleshooting

**SmartScreen warning on the installer** — the installer is not code-signed; choose *More info → Run anyway*.

**No fights appear** — make sure encounter logging is on in-game (the status bar's *Last entry* indicator should turn green during combat). The analyzer needs complete `BEGIN_COMBAT`/`END_COMBAT` events, so fights only appear once combat ends.

**"Waiting for Encounter.log"** — logging has never been enabled, or your log lives somewhere unusual: point Settings → Encounter log at it directly.

**Archive was skipped** — ESO was running and had the log open. Close ESO and use *Archive now*, or let the next app start handle it.

## Requirements

- Windows 10/11 (the engine is cross-platform Python, but packaging is Windows-only)
- Runtime: `PySide6`, `platformdirs` (see `requirements.txt`)
- ESO encounter logging enabled in-game

## License

This project is for educational and research purposes. ESO game data belongs to ZeniMax Online Studios.

## Acknowledgments

- **[LibSets](https://github.com/Baertram/LibSets/tree/LibSets-reworked/LibSets)** by Baertram — the gear set database behind set identification
- **[ESO Log Tool](https://github.com/sheumais/logs)** by sheumais — insights into ESO log format parsing
- **UESP** — authoritative skill line and ability information
- **ESO community** — encounter log format documentation and testing feedback
