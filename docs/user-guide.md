# ESO Log Tail user guide

A walk through the app, screen by screen. The pictures are taken from the app itself over a veteran Sunspire log (`scripts/capture_screenshots.py` regenerates them), so they show what you will see. The [README](../README.md) has the installation steps and the full reference of every setting; this guide is about using the app during and after a raid.

## First run

1. Install or unzip the app and start it. It looks for `Encounter.log` in the usual ESO folders, including a Documents folder that OneDrive has moved, and picks the most recently written one. If there is no log yet, it waits and attaches the moment the file appears.
2. In ESO, turn logging on with `/encounterlog` (or let an addon such as Easy Stalking do it when you enter a trial or dungeon). The status bar's **Last entry** turns green as soon as new lines arrive.
3. Start the app before or during play; both work. Joining mid-raid, it replays the session already in the log, so the group, their gear and their bars are complete and the fights so far are in the history.

## The main window

![The main window: the fight history on the left, the selected fight on the right](screencaps/main-window.png)

- **Left**: the history, one line per completed fight: `boss · duration · group DPS · zone · time`. `vet` marks veteran difficulty and `(d)` a fight in which a player died. The newest fight is selected as it ends; select an older fight to read it, and the newest again to follow live fights.
- **Right**: the selected fight. The header names the boss, the duration, the group DPS, the zone, the start time and the deaths. Under it the uptime line, one item per tracked-effect rule: a fresh install shows how much of the fight Major Courage, Major Force, Major Slayer, Powerful Assault, Lucent Echoes and Pearlescent Ward were on anyone in the group, `Taunt:NN%`, how long each boss had a taunt on it, and seven boss debuffs. In a fight without a boss the boss rules measure the pack and say how many of its mobs they reached: `Alkosh:45% on 7 of 12 mobs`.
- **One row per player**, ranked by damage to the bosses and then by all damage: the role letter (**T**ank, **H**ealer, **D**PS), the account name, the class, and when a build borrows skill lines from another class, those lines beside it with a plus sign (`NB +Herald`), read from the character's passives so a line taken for its passives alone shows too, or for a pure-class build its Class Mastery passives after a colon (`NB: An Eye for Exploitation, Above and Beyond`); then DPS and the player's share of the group's damage, each reading `boss / total` in a fight with a boss (against the units the game flags as bosses, then against everything), and the player's health, magicka and stamina with the largest pool in bold. A `*` after a name marks the player who dealt the fight's first damage. Click a DPS figure for the player's damage window; hover it for the time the figure divides by.

The DPS numbers count every hit of the player's and of their pets' (a Necromancer's Blastbones and Skeletal Archer, a Warden's bear, a Sorcerer's atronachs and familiar, a companion): direct hits, damage-over-time ticks, what got through a block and what a damage shield absorbed, as Combat Metrics counts them. Each figure divides by its **dps time**, the time from the first of those hits to the last (a second at least) rather than the whole fight, which is also how Combat Metrics works: a player's DPS over the span of their own hits, their boss DPS over the span of their hits on the bosses, the group's over the span of the group's. The header shows the fight time and, when it reads differently, the group's dps time beside it: `1:40 (dps time 1:32)`.

### A player's row in detail

With **Detail view** on (the default, Tab toggles it), each row shows the player's two ability bars as the game's icons, front bar left and back bar right, the ultimate set apart.

- Hover an icon for the ability's name; click it to open the skill on ESO-Hub.
- An ability the player taunted with in this fight is ringed in purple.
- A scribed skill is listed under the bars with the two scripts its name does not show, as `Shocking Banner (Class Flourish / Heroism)`.
- The line under the bars lists every equipped set with its piece count, `5x Deadly Strike, 2x Zaan, 1x Oakensoul Ring`; each name opens the set's ESO-Hub page.

With Detail view off, the rows are one line each, for a quick ranking:

![Compact view: one line per player](screencaps/compact-view.png)

### Finding things in a fight

Type in the search field above the fight (Ctrl+F puts the cursor there). Every match is highlighted and counted, Enter jumps to the next one, Esc clears. Icons match by the ability they stand for, so searching `jabs` lights up every Biting Jabs icon:

![Searching a fight for an ability name](screencaps/search.png)

## A player's build

Click a player's name to open their build for that fight. The window stays open beside the main window and keeps the fight it was opened for; clicking another name reuses it.

![The build window: mundus and food, both bars, and the gear grid](screencaps/build-window.png)

- **Header**: account and character name, race, class, champion points and role, then the fight.
- **Mundus, food and mastery**: the mundus stone, the food or drink buff the player had as combat started, and the Class Mastery passives a pure-class character has taken (none shown for a subclassed build).
- **Bars**: as in the fight view, with the same hover names, ESO-Hub links and scribed-skill line.
- **Gear**: one row per slot under Armor, Jewelry, Front bar and Back bar. **Type** is the armor weight, or what a weapon is (Inferno Staff, Dagger, Greatsword, Shield). **Pcs** is how many pieces of that row's set are active: `5` on either bar; `5/3` means five on the front bar and three on the back, so the set's five-piece bonus is live on the front bar only. Quality, trait, enchant and the enchant's quality follow. A mythic piece is marked, a slotted poison gets a row under its bar, and a dash means the log did not say.

## A player's damage

Click a player's DPS figure to open their damage for that fight. The window stays open beside the main window and keeps the fight it was opened for; clicking another figure reuses it.

![The damage window: one player's damage by ability, and by target below](screencaps/damage-window.png)

- **Header**: the player, then the fight, then the total: the damage dealt, the dps time it was dealt in, the DPS, and the player's share of the group's damage. Under it, where the first and last hits fell in the fight, and what the DPS would read over the whole fight.
- **Abilities**: one row per ability, largest damage first, with its icon: damage, share of the player's damage, hits, critical rate, largest hit, average hit, and DPS (that ability's damage over the player's dps time). A pet's ability says `(pet)`. A shield's absorb counts as damage, not as a hit.
- **Targets**: each unit the player hit, with the damage, its share, the hits, the span from the player's first hit on it to their last, and the DPS over that span (what Combat Metrics calls the real DPS to that target). Bosses are marked.
- **Boss targets only**: in a fight with a boss, the switch at the bottom narrows every figure to the units the game flags as bosses.

## Death recaps

A player who died has a red skull (**☠**) on their row, `☠ ×2` for two deaths. Hover it for when and to what they died; click it for the recap window.

![The death recap window: the last seconds before a death](screencaps/death-recap.png)

For each death it names the killing ability and who used it, then lists the last five seconds of damage and healing, oldest first: the time before the death, the health left after each event, the ability with its icon and its source, the amount, and whether the hit was a critical, a DoT tick, blocked, dodged, absorbed by a shield (and which), or a heal. The killing blow shows its overkill.

## Tracking effects of your own

Every item of the uptime line is a rule in Settings → **Tracked effects**, one per line, the group buffs and the taunt included:

```
Major Courage = 109966 on group
Taunt         = 38254 on boss each
Off-Balance   = 45902 62988 39077 34733 20806 130139 on boss
Touch of Z'en = 126597 on boss stacks
Crux          = 184220 on self stacks
```

Each rule is an item on the uptime line of every fight: `Major Courage:87%` is how much of the fight anyone in the group had Major Courage, `Off-Balance:17%` how much of it the boss was off balance under any of those ids, and `Crux:2.1/3` the mean and peak Crux you held. The scope after `on` says whose effects count (`self`, `group`, `pets`, `boss` or `enemies`); `stacks` asks for the count instead of the uptime, and `each` for the mean over the units, each measured for as long as it was alive in the fight, which is how the taunt is measured: a fight with two bosses averages them, and a boss killed early is measured to its death. In a fight without a boss, a trash pack, a `boss` rule measures every hostile the group fought instead and says how many of the pack's mobs the effect reached: `Alkosh:45% on 7 of 12 mobs`. Delete the lines you do not want to see, rename them as you like; the box tells you how many rules it holds and which lines it cannot read. **Examples…** opens a list of example rules, each with what it tells you and its line, the uptime line's own items first: tick the ones you want and **Add to rules** puts them under yours, or **Copy** puts the ticked lines on the clipboard to share. A rule you already have starts unticked.

![The example rules picker: a checkbox per rule with what it tells you and its line](screencaps/examples-dialog.png)

The rules are plain text: copy them to a friend, or paste theirs in. A tracker exported from the HyperTools addon works too: paste its `$...` string as a line and its name, ability ids and target become a rule. Save restarts monitoring, so the rules apply to the session's fights at once.

## The buff timeline (experimental)

Settings → Tracked effects → **Show these as a per-fight timeline strip** adds a strip above the fight: one thin row per tracked effect (Major Slayer, Major Force, Major Courage, Major Berserk, Powerful Assault, Major Vulnerability, Taunt), filled where the effect was up, with the uptime in the row label and time ticks underneath. A group buff that reached only one or two people is dotted rather than solid. Hover a segment for who cast it and who received it. Beside each row's label a word says whose effect it is: `group` for the group buffs, `boss` for Major Vulnerability and the taunt, and the scope of each tracked rule (`self`, `pets`, `enemies`, or `mobs` for a boss rule measured on the pack of a fight without a boss). The strip replaces the text uptime line.

![The main window with the buff timeline strip](screencaps/main-window-buff-timeline.png)

## Reviewing a log

**Open log for review** loads any log file, a split file or an unzipped archive, and lists its fights while live monitoring carries on underneath. A banner shows which file is open; **Back to live** returns to the live session.

![Review mode: a file's fights, with the banner and Back to live](screencaps/review-mode.png)

## Copying a fight

**Copy fight** (Ctrl+C) puts the selected fight on the clipboard as plain text, names rather than icons, ready for Discord: the header, the uptime line, each player with their bars, sets and scribed skills, and for anyone who taunted, what with: `taunted with Inner Rage ×262`.

## Settings

![The Settings dialog](screencaps/settings.png)

- **Encounter log**: a specific file, or blank to auto-detect.
- **Per-encounter split files**: one `YYMMDDHHMMSS-Zone-Name-vet.log` per encounter, in a folder of your choice. These are handy for review, and small enough to share.
- **Automatic log archiving**: ESO never truncates `Encounter.log`, so it grows by hundreds of MB a night. Once it has grown past the threshold, the app zips it at startup (before ESO has the file open), and can delete the original after the zip has verified, so ESO starts a fresh, small log. **Archive now** on the toolbar does the same at any moment, for instance right after you close ESO.
- **Startup**: start the app when you sign in to Windows.
- **Updates**: check GitHub for a newer release at startup and offer to install it; nothing is installed without the prompt.
- **Tracked effects**: the uptime line's rules, and the checkbox that shows them as a per-fight timeline strip instead.

Saving restarts monitoring: the history clears and the current session is replayed with the new settings.

## The status bar

- **Last entry**: the time of the newest log line and how long ago: green while live (under two minutes), plain while idle, amber when stale (over thirty minutes), red **No log file** when nothing is monitored. A `~` means the time came from the file's clock rather than its content.
- **Zone**: the current zone and difficulty.
- A progress bar on the right while the app parses a reviewed log, catches up on a backlog, archives, or downloads an update.

## When something looks wrong

- **A set shows as `Set#123`**: the set is newer than the bundled set table; it will be named after the next release.
- **An ability shows as text instead of an icon**: the icon is not in the bundled set; the name still links to ESO-Hub.
- **A weapon's Type is a dash**: the weapon is from a set newer than the bundled weapon table.
- **The app crashed**: `crash.log` next to the settings file (`%LOCALAPPDATA%\esolog-tail\` on Windows, `~/.config/esolog-tail/` on Linux) has the details; please attach it to a GitHub issue.
- **How the numbers are made**: the [design notes](design.md) explain what the log carries and how buffs, taunts, pets, roles, skill lines, icons and set names are worked out.
