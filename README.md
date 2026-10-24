# ESO Log Tail

Live fight summaries from Elder Scrolls Online encounter logs, in a desktop app for Windows, with an experimental Linux build. ESO Log Tail watches your `Encounter.log` and, the moment combat ends, shows who was in the group, how each player was built, and how they performed.

![Main window: fight history on the left; on the right the buff timeline strip, a fight header, and one row per player with ability-bar icons and gear sets](docs/screencaps/main-window.png)

The **[user guide](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/blob/main/docs/user-guide.md)** walks through every screen and setting. The **[design notes](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/blob/main/docs/design.md)** explain what the log carries and how buffs, taunts, pets, roles, skill lines, icons and set names are worked out.

## Features

- **Fight summaries as combat ends**: boss or mob name, duration, group DPS, zone, time and deaths, with every fight of the session kept in a history list.
- **Players ranked by boss damage, then all damage**, with role (Tank/Healer/DPS), class and borrowed skill lines or Class Mastery passives, boss DPS beside total DPS, damage share, and resource pools.
- **Builds at a glance**: both ability bars as the game's own icons, scribed skills with their scripts (`Chilling Contingency (Lingering Torment / Intellect and Endurance)`), and every equipped gear set with piece counts.
- **Full build per player**: click a name for gear slot by slot (set, type, quality, trait, enchant, slotted poison), both bars, mundus stone, food and Class Mastery passives.
- **Penetration and critical damage against the caps**: the build window lists where each player's penetration and crit damage come from (passives, mundus and Divines, sets at their piece counts, weapon kinds and traits), which group debuffs were on the boss and who applied them with what, and the buffs on the player, then the totals: at full uptime, as the raid lead's spreadsheet would have it, and effective over the fight's damage, as Combat Metrics would show it. Champion Point stars the log cannot see are assumed rows you choose in Settings.
- **DPS the way Combat Metrics counts it**: each figure over its dps time (first hit to last); click a player's DPS for their damage by ability and by target, or the group's for a graph of everyone's dps across the fight; a small mark after each figure says it opens something.
- **Death recaps**: a ☠ on the row of a player who died opens the last 5 seconds before each death: every hit and heal with its source, the health left after it, and whether it was blocked, dodged or absorbed by a shield.
- **Buff and debuff timeline**: a strip across each fight, buffs above and debuffs below, one row per effect with its uptime. Hover for who cast what on whom; click a row for each caster's and receiver's share of the fight.
- **Tracked effects you define**: the strip's rows are plain-text rules, `Off-Balance = 45902 62988 on boss`. They start with the group buffs, the taunt on the boss and six boss debuffs, Touch of Z'en's stacks among them, counted as Combat Metrics counts them. A rule shows when its effect was up, or at `0%` in the group sizes you say it is expected in, so a missing buff stands out in a trial without a dungeon run filling with zeros. Edit them, add any effect the log carries, share the rules as text, paste HyperTools trackers, or pick from the Examples list. In a trash pack, boss rules measure the pack.
- **Taunts**: how long each boss had a taunt on it, and the abilities each player taunted with ringed on their bars.
- **ESO-Hub links**: hover an ability icon for its name, click it for the skill's ESO-Hub page; set names open their set pages. Nothing is sent to ESO-Hub until you click.
- **Search within a fight** (Ctrl+F), including ability icons by name; **copy any fight** as plain text for Discord; **review any log file** without interrupting live monitoring.
- **Log housekeeping**: per-encounter split files, automatic archiving of the ever-growing log, and a freshness indicator so you can tell at a glance that logging is on.
- **Zero-friction startup**: finds the log (including OneDrive-relocated Documents folders), replays the current session so the group is complete when you start mid-raid, can start with Windows, and offers updates from GitHub.

## Installation

### Option 1: Installer (recommended)

1. Download `esolog-tail-windows-setup-<version>.exe` from the [latest release](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/releases/latest).
2. Run it. No administrator rights are needed (per-user install). If Windows SmartScreen shows "unknown publisher", choose **More info → Run anyway**; the installer is not code-signed.
3. Launch **ESO Log Tail** from the Start Menu. Installing a newer version later upgrades in place and keeps your settings.

### Option 2: Portable zip

Download `esolog-tail-windows-portable-<version>.zip`, extract it anywhere, and run `esolog-gui.exe`.

### Option 3: Linux tarball (experimental)

The Linux build is built and start-tested automatically, but it has not been run against a live game, so treat it as a test build and please report what you find.

```bash
tar -xzf esolog-tail-linux-x86_64-<version>.tar.gz
./esolog-tail-<version>/esolog-gui
```

It needs a 64-bit x86 desktop (X11 or Wayland) with glibc 2.35 or newer: Ubuntu 22.04, Debian 12, Fedora 36, or later. Nothing is installed; delete the folder to remove it. What differs from Windows:

- **Finding the log**: the app looks in ESO's Steam (Proton) prefix, including Flatpak Steam, and in the default `~/.wine` prefix. For anything else, set the path under Settings → Encounter log.
- **Updates**: the update prompt opens the release page for you to download the new tarball.
- **Start at login** is not offered.
- Settings and `crash.log` live in `~/.config/esolog-tail/`.

### Option 4: From source

```bash
git clone https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities.git
cd eso-live-encounterlog-sets-abilities
pip install -r requirements.txt
python src/esolog_gui.py
```

## Turn on encounter logging in ESO

ESO writes `Encounter.log` only while encounter logging is on, and it is off by default. There is nothing for the app to show until it is enabled.

- **Recommended: the [Easy Stalking - Encounterlog](https://www.esoui.com/downloads/info2332-EasyStalking-Encounterlog.html) addon** (ESOUI or Minion). It turns logging on and off for you by content type, shows an on-screen indicator while logging, and adds the `/ezlog` chat command.
- **By hand**: type `/encounterlog` in chat, or enable it under Settings → Combat → Combat Logging, before each run.

Then start ESO Log Tail, before or during play. The status bar's **Last entry** turns green while the log is being written. The [user guide](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/blob/main/docs/user-guide.md#first-run) takes it from there.

## Troubleshooting

- **SmartScreen warning on the installer**: the installer is not code-signed; choose *More info → Run anyway*.
- **No fights appear**: make sure encounter logging is on in-game (**Last entry** turns green while the log is written). A fight appears once combat ends.
- **"Waiting for Encounter.log"**: logging has never been enabled, or your log lives somewhere unusual: point Settings → Encounter log at it.
- **DPS differs from Combat Metrics or ESO Logs**: a player's figure counts the same hits over the same dps time as Combat Metrics. In a boss fight the first figure is boss DPS, and the group's DPS uses the group's own span rather than yours. See [when something looks wrong](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/blob/main/docs/user-guide.md#when-something-looks-wrong).
- **The app closed unexpectedly**: unhandled errors are written to `%LOCALAPPDATA%\esolog-tail\crash.log` (`~/.config/esolog-tail/crash.log` on Linux); please attach it to a [bug report](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/issues).
- **Linux: the app does not start**: run `./esolog-gui` from a terminal to see Qt's message, and include it in a bug report with your distribution and whether the desktop is X11 or Wayland.

More in the user guide under [When something looks wrong](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/blob/main/docs/user-guide.md#when-something-looks-wrong).

## Requirements

- Windows 10/11, or 64-bit Linux with glibc 2.35 or newer (experimental build)
- ESO encounter logging enabled in-game

## Contributing

The [development guide](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/blob/main/docs/development.md) covers the repository layout, the tests, building the installer, refreshing game data after an ESO patch, and releasing.

## License

Released under the [MIT License](LICENSE). ESO game data belongs to ZeniMax Online Studios.

## Credits

The same credits are shown in the app under **About…**.

- **[ESO-Hub.com](https://eso-hub.com)**: the skill and gear set links in the detail view open pages on ESO-Hub, and the hover (popup) text names those targets. Thanks to the ESO-Hub team for supporting community tools that link to their site. The app sends nothing to ESO-Hub until you click a link; the hover text is built from the app's own data and the link target.
- **[Combat Metrics](https://www.esoui.com/downloads/info1360-CombatMetrics.html)** by Solinur, and its [LibCombat](https://github.com/Solinur/LibCombat) library: the addon ESO players measure dps with, and the reference for this app's dps figures. The dps time (first hit to last, a second at least), the boss and per-target spans, what counts as damage, the breakdown by ability and the graph's curves follow its definitions, read from the [Combat Metrics source](https://github.com/Solinur/CombatMetrics), so the figures here agree with it. No code is shared.
- **Game icons**: the ability icons shown on the bars and in death recaps are extracted from your own ESO installation (see `scripts/extract_ability_icons.py`) and bundled for display only. They are © ZeniMax Online Studios and are not the property of this application. The Elder Scrolls Online and its artwork are © ZeniMax Online Studios; ESO Log Tail is an unofficial fan tool, not affiliated with or endorsed by ZeniMax.
- **[LibSets](https://github.com/Baertram/LibSets/tree/LibSets-reworked/LibSets)** by Baertram: the gear set database behind set identification.
- **[LibFoodDrinkBuff](https://www.esoui.com/downloads/info1902-LibFoodDrinkBuff.html)** by Scootworks and Baertram: the list of food and drink buffs behind the build window's food line.
- **[EsoExtractData](https://en.uesp.net/wiki/ESO_Mod:EsoExtractData)** by UESP: the tool that extracts the icons from the game files.
- **[Easy Stalking - Encounterlog](https://www.esoui.com/downloads/info2332-EasyStalking-Encounterlog.html)**: the addon that makes turning logging on a non-event.
- **[ESO Log Tool](https://github.com/sheumais/logs)** by sheumais: insights into ESO log format parsing, and the idea of showing a scribed skill with its scripts as `Name (Signature / Affix)`.
- **[UESP](https://en.uesp.net/wiki/Online:Online)**: authoritative skill line and ability information, and the item database behind the build window's poison names, armor weights and weapon types (the restoration staff that marks a healer among them), and the set bonus texts behind its penetration and critical damage rows (CC-BY-SA 2.5).
- **[PenCrit Calc](https://docs.google.com/spreadsheets/d/1zMu5fFh-0ELdQUgShoG13TzMmSoPtRm-W25oAqNiZE0/)** by LunaCairu ([Night Harrow Gaming](https://nightharrowgaming.com/)), the [Crit Damage and Penetration](https://skinnycheeks.gg/crit-damage-and-penetration) page on skinnycheeks.gg and the [Penetration](https://hyperioxes.com/eso/tools/penetration-calculator) and [Crit](https://hyperioxes.com/eso/tools/crit-calculator) calculators by Hyperioxes it recommends (built on a spreadsheet by SparkRip): the model the build window's penetration and critical damage sections follow, every source a value, summed against the cap. The group debuffs are valued as Combat Metrics values them.
- **ESO community**: encounter log format documentation and testing feedback.
