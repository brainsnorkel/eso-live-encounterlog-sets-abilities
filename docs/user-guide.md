# ESO Log Tail user guide

A walk through the app, screen by screen, and the reference for every setting. The pictures come from the app itself, drawn over a veteran trial log (`scripts/capture_screenshots.py` regenerates them), so they show what you will see. The [README](../README.md) has the installation steps.

- [First run](#first-run)
- [The main window](#the-main-window)
- [A player's build](#a-players-build)
- [A player's damage](#a-players-damage)
- [DPS over time](#dps-over-time)
- [Death recaps](#death-recaps)
- [Tracked effects](#tracked-effects)
- [The buff timeline](#the-buff-timeline)
- [Reviewing and copying fights](#reviewing-and-copying-fights)
- [Settings](#settings)
- [The status bar](#the-status-bar)
- [What the numbers are based on](#what-the-numbers-are-based-on)
- [When something looks wrong](#when-something-looks-wrong)
- [Where the app looks for the log](#where-the-app-looks-for-the-log)
- [Migrating from the terminal version](#migrating-from-the-terminal-version)

## First run

1. **Turn on encounter logging in ESO.** The game writes `Encounter.log` only while logging is on, and it is off by default, so there is nothing to show until it is enabled. Logging that was never turned on is the usual reason a first run stays empty.
   - **Recommended: the [Easy Stalking - Encounterlog](https://www.esoui.com/downloads/info2332-EasyStalking-Encounterlog.html) addon** (ESOUI or Minion). It turns logging on and off for you by content type (trials, dungeons, arenas, PvP), shows an on-screen indicator while logging, and adds the `/ezlog` chat command, so you never have to remember.
   - **By hand**: type `/encounterlog` in chat, or enable it under Settings → Combat → Combat Logging, before each run.
2. **Start the app**, before or during play; both work. It looks for `Encounter.log` in the usual ESO folders, including a Documents folder that OneDrive has moved, and picks the most recently written one (see [Where the app looks for the log](#where-the-app-looks-for-the-log)). If there is no log yet, it waits and attaches the moment the file appears.
3. **Check the status bar.** **Last entry** turns green as soon as new lines arrive, so you can confirm logging is on from the app.

Joining mid-raid, the app replays the logging session already in the file: the session's fights load into the history and the whole group, their gear and their bars are known, so you do not start with a half-empty group. A session over 768 MB falls back to a faster sweep that reads only the roster.

## The main window

![The main window: the fight history on the left, the selected fight on the right](screencaps/main-window.png)

### Fight history

The list on the left has one line per completed fight: `boss · duration · group DPS · zone · time`. `vet` marks veteran difficulty and `(d)` a fight in which a player died. A fight appears when combat ends. The newest fight is selected as it ends; select an older fight to read it (following pauses), and select the newest again to follow live fights.

### The fight

- **Header**: boss or mob name, then duration, group DPS, zone, start time, and player deaths. In a fight with a boss the DPS reads `boss / total`: the damage dealt to the units the game flags as bosses, then all damage dealt. The duration is the fight time; when the group's dps time (first hit to last, what the DPS divides by) reads differently, it follows in brackets: `1:40 (dps time 1:32)`. The group DPS ends in a small graph line in the link colour: click it, or **DPS graph** on the toolbar, for the [dps over time graph](#dps-over-time).
- **Buff timeline**: above the header, the [strip](#the-buff-timeline) with one row per effect across the fight, buffs above and debuffs below. A fresh install tracks how much of the fight Major Courage, Major Force, Major Slayer, Powerful Assault, Lucent Echoes and Pearlescent Ward were on anyone in the group; `Taunt:97%`, how long each boss had a taunt on it; six boss debuffs (Off-Balance, Touch of Z'en, Morag Tong, Minor Brittle, Major Brittle, Alkosh); and Crux, the mean and peak Crux you held. Each of these is a [tracked-effect rule](#tracked-effects) and has a row when its effect was up; the group buffs also show at `0%` in a group of five or more when nobody had them, and the taunt in any group. In a fight without a boss the boss rules measure the pack and say how many of its mobs they reached: `Alkosh:45% on 7 of 12 mobs`. **Copy fight** puts the same items on one text line.
- **One row per player**, ranked by damage to the bosses and then by all damage (in a fight without a boss, by all damage):
  - the role letter, **T**ank, **H**ealer or **D**PS (see [Roles](#what-the-numbers-are-based-on));
  - the account name, with `*` after the player who dealt the fight's first damage;
  - the class. A build that borrows skill lines from another class shows those lines after a plus sign, `NB +Aedric +Grave`, read from the character's passives, so a line taken for its passives alone shows too. A pure-class build names its Class Mastery passives after a colon instead, `NB: An Eye for Exploitation, Above and Beyond`. A stock build shows just the class;
  - DPS and the share of the group's damage, each `boss / total` in a fight with a boss (against the units the game flags as bosses, then against everything), and max health, magicka and stamina with the largest pool in bold. The small three-bar mark after a DPS figure says it opens something: click it for the player's [damage window](#a-players-damage); hover it for the time the figure divides by.

DPS includes what a player's pets did: a Necromancer's Blastbones and Skeletal Archer, a Warden's bear, a Sorcerer's atronachs and familiar, a companion. Damage-over-time ticks count, as in Combat Metrics; see [Damage](#what-the-numbers-are-based-on). Each figure divides by its **dps time**, the time from the first of those hits to the last (a second at least) rather than the whole fight, which is also how Combat Metrics works: a player's DPS over the span of their own hits, their boss DPS over the span of their hits on the bosses, the group's over the span of the group's.

### A player's row in detail

With **Detail view** on (the default; Tab toggles it), each row shows the player's two ability bars as the game's icons, front bar left and back bar right, the ultimate set apart.

- Hover an icon for the ability's name; click it to open the skill on [ESO-Hub](https://eso-hub.com). An ability without a bundled icon shows its name instead.
- An ability the player taunted with in this fight is ringed in purple (or its name is purple).
- A scribed skill is listed under the bars with the two scripts its name does not show, as `Skill (Signature / Affix)`: `Shocking Banner (Class Flourish / Heroism)`. The skill's name already says which grimoire and focus script it is; hover its icon on the bar for all four parts. The skill and the scripts link to their ESO-Hub pages. `(scripts not in log)` means the log does not say which scripts this player uses (see [Limitations](#limitations)); the hover says why, and lists the combinations it can be when the log narrows it down.
- A werewolf gets a third line, **Werewolf**: the bar they fought with in werewolf form and how much of the fight they spent transformed, `in form 100%`. The game never writes that bar into its log, so the app rebuilds it from the werewolf skills the player cast, in the skill line's order; a skill they slotted but never cast cannot show. At full Fury the game lists Rampage in place of the transformation ultimate for the player writing the log, and the bar shows the morph, Werewolf Berserker or Pack Leader, instead. Hovering either kind of icon says so.
- The line under the bars lists every equipped set with its piece count, `5x Deadly Strike, 2x Zaan, 1x Oakensoul Ring`; each name opens the set's ESO-Hub page.
- An `(i)` after a player's class means the app found a [possible build issue](#possible-build-issues) in the build they pulled with. Hover it for the list; click it for each finding with the rule behind it. A player without one has no `(i)`, in either view.

With Detail view off, the rows are one line each, for a quick ranking:

![Compact view: one line per player](screencaps/compact-view.png)

### Possible build issues

The `(i)` points out things in a build that are usually mistakes, read from what the log recorded as the fight began. Each finding states its rule, so you can judge it yourself; the popup links the set or skill concerned to ESO-Hub.

![The (i) popup: a player's possible build issues, each with its rule](screencaps/build-issues.png)

The rules:

- **Nirnhoned on an off-hand weapon.** The trait raises the damage of the weapon it is on, and the Dual Wield Expert passive counts only 6% of an off-hand weapon's damage, so Nirnhoned there is worth about a sixteenth of what it gives in the main hand. A shield's Nirnhoned is the armor trait and is not reported.
- **The same glyph on both weapons of a bar.** Two identical weapon glyphs on one bar share one cooldown, so the second never fires; a different glyph would add a proc of its own. The same glyph on both bars is not reported: a copy on the other bar fills the gap after a swap.
- **Two or more heavy armor pieces on a damage dealer.** Heavy Armor's passives add nothing to damage; one heavy piece is the usual Undaunted Mettle split and is not reported. The rule applies to a player whose role reads DPS and who has not taunted in this logging session, since the role is a heuristic (see [Roles](#what-the-numbers-are-based-on)).
- **A weapon skill on a bar holding another weapon**, a Two Handed skill on a staff bar, say: the skill cannot be cast from that bar, so the slot does nothing. The back bar of a player wearing Oakensoul Ring is not judged, since the ring forbids swapping, and neither is a bar whose weapon the app does not know.
- **Elemental Drain slotted.** The finding states both morphs: Drain applies Major Breach and Minor Magickasteal, Elemental Susceptibility applies Major Breach and the Burning, Chilled and Concussion status effects every 7.5 seconds.
- **Roar of Alkosh or Roaring Opportunist worn and never firing.** Alkosh's shockwave needs the wearer to activate a synergy, Roaring Opportunist's Major Slayer a fully charged heavy attack. The app counts, over the logging session, the fights of a minute or more the player wore the set in; when the set's effect never came from them in any fight of the session, the finding says how many such fights have passed. One fire anywhere in the session clears it.
- **Pearlescent Ward, Xoryn's Masterpiece or Lucent Echoes complete on one bar only.** Their five-piece bonus is a buff for the whole group that holds only while five pieces are active, so the group loses it every time the player swaps bars. A build with no back-bar weapon, or wearing Oakensoul Ring, is not judged.

The rules are fixed in this version; what each finding says is meant to be enough to act on, or to disagree with.

### Finding things in a fight

Type in the search field above the fight (Ctrl+F puts the cursor there). Every match is highlighted and counted, Enter jumps to the next one, Esc clears. Icons match by the ability they stand for, so searching `jabs` lights up every Biting Jabs icon. The search follows you as you switch fights.

![Searching a fight for an ability name](screencaps/search.png)

## A player's build

Click a player's name, in either view, to open their build for that fight. The name carries no mark, unlike the DPS figures; it is underlined while the pointer is over it. The window stays open beside the main window and keeps the fight it was opened for; clicking another name reuses it.

![The build window: mundus and food, both bars, and the gear grid](screencaps/build-window.png)

- **Header**: account and character name, race, class, champion points and role, then the fight.
- **Mundus, food and mastery**: the mundus stone, the food or drink buff the player had as combat started, and the Class Mastery passives a pure-class character has taken. `no known food or drink` means none of their effects is a food or drink the app knows; no mastery part means the character has none (a subclassed build cannot).
- **Possible build issues**: the same findings the fight pane's `(i)` opens, each with its rule, under the header; nothing there for a build without one.
- **Bars**: front bar above back bar, ultimate set apart, with the same hover names, ESO-Hub links and scribed-skill line as the fight view, and for a werewolf the rebuilt werewolf bar under them.
- **Gear**: one row per slot under Armor, Jewelry, Front bar and Back bar, with the set (a link to its ESO-Hub page), quality, trait, enchant and the enchant's quality. A slot with nothing logged shows a dash, a mythic piece is marked Mythic, and a slotted poison gets a row under its bar.
- **Type** is the armor weight, or what a weapon is: `Inferno Staff`, `Dagger`, `Greatsword`, `Shield` and so on. The Armor heading counts the pieces of each weight, `5 medium, 1 light, 1 heavy`. A dash means the app does not know the piece (see [Limitations](#limitations)).
- **Pcs** is the number of pieces of the row's set that are active, counted per weapon bar: armor and jewelry count on both bars, and each bar adds its own weapons, a two-handed one as two. `5` means five on either bar. `5/3` means five on the front bar and three on the back: that set's five-piece bonus is live on the front bar only.

## A player's damage

Click a player's DPS figure, the one with the small three-bar mark after it, to open their damage for that fight. The window stays open beside the main window and keeps the fight it was opened for; clicking another figure reuses it.

![The damage window: one player's damage by ability, and by target below](screencaps/damage-window.png)

- **Header**: the player, then the fight, then the total: the damage dealt, the dps time it was dealt in, the DPS, and the player's share of the group's damage. Under it, where the first and last hits fell in the fight, and what the DPS would read over the whole fight.
- **Abilities**: one row per ability, largest damage first, with its icon: damage, share of the player's damage, hits, critical rate, largest hit, average hit, and DPS (that ability's damage over the player's dps time). A pet's ability says `(pet)`. A shield's absorb counts as damage, not as a hit.
- **Targets**: each unit the player hit, with the damage, its share, the hits, the span from the player's first hit on it to their last, and the DPS over that span (what Combat Metrics calls the real DPS to that target). Bosses are marked.
- **Boss targets only**: in a fight with a boss, the switch at the bottom narrows every figure to the units the game flags as bosses.

## DPS over time

Click the group DPS figure in the fight header, the one ending in a small graph line, or **DPS graph** on the toolbar, for a graph of the fight: the group's dps and each player's across the fight, drawn the way Combat Metrics' graph tab draws them. The group has the upper panel and the players the lower, each on its own scale (the group's figure is as many times a player's as there are players), sharing the time axis.

![The DPS graph: the group and the players over a fight](screencaps/dps-graph.png)

- **Show** picks the curve: the average over a window of 1, 5 (the default, as in Combat Metrics), 10 or 30 seconds, or the running figure, which is the live dps as it stood at each second and ends at the fight's dps.
- **Legend**: tick the group and the players to draw. The first eight players are on to begin with, and a player past the eighth draws dashed in a reused colour, since eight is as many colours as can be told apart. Each entry shows the player's dps (`boss / total` in a fight with a boss). The choices are kept from one fight to the next while the window is open.
- **Hover** the chart for a crosshair with every drawn line's value at that second; with four lines or fewer, each line's end value is labelled.
- **Boss targets only** narrows every line to the damage on the units the game flags as bosses.

## Death recaps

A player who died has a red skull (**☠**) on their row, `☠ ×2` for two deaths. Hover it for when and to what they died; click it for the recap window, which stays open beside the fight view.

![The death recap window: the last seconds before a death](screencaps/death-recap.png)

For each death the window names the killing ability and who used it, then lists the last 5 seconds of damage and healing, oldest first:

- **Time** before the death, and the player's **health** after the event (with its share of max health).
- The **ability**, with the game's icon, and its **source**: the monster or player that hit or healed.
- The **amount** that reached or restored health, and the **result**: hit, critical hit, DoT, blocked, dodged, missed, fall damage, heal, or HoT. A hit soaked by a damage shield says how much was absorbed and by which shield, a heal eaten by a healing-absorb effect is listed as such, and the killing blow shows its overkill.

Heals that were pure overheal are left out. A death the game writes just after combat ends (the last player standing in a wipe) still counts and is added to that fight.

## Tracked effects

Every row of the buff timeline is a rule in Settings → **Tracked effects**, one per line, the group buffs and the taunt included. The rules are plain text: copy them to a friend, or paste theirs in. A fresh install starts with these:

```
Major Courage    = 109966 on group expected large
Major Force      = 61747 on group expected large
Major Slayer     = 93109 on group expected large
Powerful Assault = 61771 on group expected large
Lucent Echoes    = 220015 on group expected large
Pearlescent Ward = 172621 on group expected large
Taunt            = 38254 on boss each expected small large
Off-Balance   = 45902 62988 39077 34733 20806 130139 130145 130129 125750 62968 25256 34737 23808 137257 45834 137312 131562 on boss
Touch of Z'en = 126597 on boss dots
Crux          = 184220 on self stacks
Morag Tong    = 34384 on boss
Minor Brittle = 145975 on boss
Major Brittle = 263825 on boss
Alkosh        = 76667 on boss
```

A rule is `Name = ability ids on <scope>`, then optionally a measure (`stacks`, `each` or `dots`) and `expected <sizes>`, in any order:

- **Ids**: a rule matches any of its ids, since an effect such as Off-Balance has one id per skill that applies it. They are the ids the game logs; an addon such as HyperTools or LuiExtended shows them.
- **Scope** says whose effects count: `self` is the player whose client writes the log, `group` any group member, `pets` a group member's pet, `boss` an enemy the game flags as a boss, `enemies` any hostile.
- **Measure**: by default, the share of the fight the effect was on at least one unit of the scope, `Off-Balance:17%`. `stacks` gives the mean stack count while it was up and the peak, `Crux:2.1/3`. `each` measures every unit of the scope separately, over the time that unit was alive in the fight, and shows the mean. That is the taunt's measure: a fight with two bosses averages them, and a boss killed early is measured to its death.
- **`dots`** is for Touch of Z'en, whose stacks the game never writes to the log: while a wearer's Z'en is on the boss, it counts that wearer's damage-over-time effects on it, at most five, and shows the mean and peak, `Touch of Z'en:4.3/5`. This is how Combat Metrics counts it. An effect counts when the log shows it ticking as damage over time, so Burning, Poisoned, bleeds and set DoTs count, a ground area such as Stampede does not, and 0 means Z'en was up with no bonus.
- **When a rule shows**: a rule's row, and its item in the copied text, shows whenever its effect was up in the fight. `expected` makes it show at `0%` even when the effect never came, in the group sizes you name: `solo` (one player), `small` (two to four), `large` (five or more), or `all`; `expected` alone means all. The defaults expect the six group buffs in a large group and the taunt in small and large groups, so a missing Major Courage in a trial stands out, while a dungeon run is not a column of zeros. The boss debuffs show when someone applied them.
- **Trash packs**: in a fight without a boss, a `boss` rule measures every hostile the group fought instead, and both it and an `enemies` rule say how many of the pack's mobs the effect reached: `Alkosh:45% on 7 of 12 mobs`. In a boss fight nothing changes.
- **HyperTools**: a line that starts with `$` is a tracker exported from the [HyperTools](https://github.com/Hyperioxes/HyperTools) addon, pasted as is. Its name, ability ids and target become a rule; `stacks`, `on boss` or `expected <sizes>` after the string apply to it.

Rules saved by an earlier version are brought up to date once, when the app starts: the seven default group-buff and taunt lines get their `expected` words, and a `Touch of Z'en … stacks` line becomes `dots`. A line you renamed, or gave your own `expected`, is left as you wrote it.

Delete the lines you do not want and rename the rest as you like (`MCourage` if you prefer the short form). The box tells you how many rules it holds and which lines it cannot read. **Examples…** opens a list of example rules, each with what it tells you and its line, the default rules first: tick the ones you want and **Add to rules** puts them under yours, or **Copy** puts the ticked lines on the clipboard to share. A rule you already have starts unticked.

![The example rules picker: a checkbox per rule with what it tells you and its line](screencaps/examples-dialog.png)

Saving restarts monitoring, so new rules apply to the session's fights at once.

## The buff timeline

A compact strip above each fight shows every tracked effect across the fight's length (see the [main window picture](#the-main-window)).

- **Rows**: the strip's built-in rows, Major Slayer, Major Force, Major Courage, Major Berserk, Powerful Assault, Major Vulnerability and Taunt, then one row for each of your [tracked-effect rules](#tracked-effects) (a rule with the same name as a built-in row does not get a second one). Major Berserk and Major Vulnerability are built-in rows only; they are not in the copied text line. A rule whose effect never occurred has a row only when it is [expected](#tracked-effects) in a group of that size, an empty one reading `0%`; otherwise it is left out, and the strip disappears when there is nothing to show.
- **Buffs above, debuffs below**: rows whose effect is on your side (`group`, `self`, `pets`) come first, then the rows on the enemy (`boss`, `enemies`, `mobs`), with a thin line between the two. Each side keeps the order its rows come in: built-in rows first, then your rules in the order you wrote them.
- **Each row** is filled where the effect was up, with its uptime in the label and time ticks underneath. Beside the label a word says whose effect it is: `group`, `boss` for Major Vulnerability and the taunt, and each rule's scope (`self`, `pets`, `enemies`, or `mobs` for a boss rule measured on the pack of a fight without a boss). A stacking rule's bar rises and falls with the count, and Touch of Z'en's against its five DoTs. A group buff that reached only one or two people is dotted rather than solid.
- **Hover** a segment for who cast it and who received it at that moment. Hover a label for its full text when it is cut short.
- **Click** a row, label or bar, for a summary of the whole fight: who applied the effect (each caster's uptime, how much of it no other caster covered, and how many spans), who had it (each receiver's uptime, and for a stacking rule its peak and the time at the peak), and, when there are only a few of each, a grid of caster against receiver. A click elsewhere or Esc closes it.

## Reviewing and copying fights

**Open log for review** loads any log file, a split file or an unzipped archive, and lists its fights while live monitoring carries on underneath. A banner shows which file is open; **Back to live** returns to the live session.

![Review mode: a file's fights, with the banner and Back to live](screencaps/review-mode.png)

**Copy fight** (Ctrl+C) puts the selected fight on the clipboard as plain text, names rather than icons, ready for Discord: the header, the tracked effects on one line (`Major Courage:87% … Alkosh:45%`), each player with their bars, sets and scribed skills (`Leashing Soul (Druid's Resurgence / Cowardice)`), and for anyone who taunted, what with: `taunted with Inner Rage ×262, Inner Fire ×11`.

**About** shows the version, the project link and the credits.

## Settings

Open **Settings…** from the toolbar.

![The Settings dialog](screencaps/settings.png)

- **Encounter log**: a specific `Encounter.log`, or blank to auto-detect.
- **Per-encounter split files**: write each encounter to its own `YYMMDDHHMMSS-{Zone-Name}{-vet}.log` in a folder of your choice (blank uses the log's folder). They are handy for review, and small enough to share.
- **Automatic log archiving**: the growth threshold that triggers an archive at startup, the archive folder, and whether to delete the original after a verified archive. See [below](#automatic-log-archiving).
- **Startup**: *Start ESO Log Tail when I sign in to Windows*, a per-user login entry that needs no admin rights and is removed on uninstall. Not offered on Linux.
- **Updates**: check GitHub for a newer release at startup and offer to install it. See [below](#automatic-updates).
- **Tracked effects**: the rules behind the timeline strip. See [Tracked effects](#tracked-effects).

Saving restarts monitoring: the history clears and the current session is replayed with the new settings. Settings live in a per-user file, `%LOCALAPPDATA%\esolog-tail\config.json` (`~/.config/esolog-tail/config.json` on Linux), and survive upgrades and uninstalls.

### Automatic updates

At startup the app checks GitHub for a newer release. When one exists you are asked **Update now / Later / Skip this version**. Updating downloads the installer with a progress bar, closes the app, and hands over to the installer; settings are kept and the app restarts when it finishes. Nothing is installed without the prompt. On Linux the first button is **Open download page**, which opens the release page for you to download the new tarball.

### Automatic log archiving

ESO never truncates `Encounter.log`. With regular raiding it grows by hundreds of MB a night and can reach tens of GB. The app archives it for you.

- **When**: checked **once, at app startup**. ESO keeps the log open for the whole game session (even between `/encounterlog` toggles), so startup, usually before you launch ESO, is the safe moment.
- **Trigger**: the log has grown by more than the threshold since the last archive. The default is **1024 MB**, about five veteran trials (a vet trial run is typically 100 to 300 MB, a vet dungeon roughly 25 to 75 MB).
- **What it does**: streams the log into `Encounter-YYMMDDHHMMSS.zip` (stamped from the newest log entry) in the archive folder, by default next to the log, with progress in the status bar. The zip is written as a `.partial` file and renamed only after it verifies, so an interrupted archive never leaves a corrupt zip behind.
- **Safety**: the app takes exclusive access to the log for the whole operation. If ESO is running and holds the file, the archive is **skipped with a notification** and monitoring starts normally; nothing is ever zipped mid-write. Linux cannot lock a file that way, so there the app skips the archive when another process has the log open, and keeps the original if the log grew while it was being zipped.
- **Your original log is kept** by default. With *Delete Encounter.log after a verified archive* on, the original is removed only after the zip verifies, and ESO starts a fresh, small log.
- **Archive now** on the toolbar runs the same guarded archive at any moment, handy right after you close ESO.

## The status bar

- **Last entry**: the time of the newest log line and how long ago it was: green while **live** (under two minutes), plain while idle, amber when **stale** (over thirty minutes), and red **No log file** when nothing is monitored. A `~` means the time came from the file's clock rather than its content.
- **Zone**: the current zone and difficulty.
- A progress bar on the right while the app parses a reviewed log, catches up on a large backlog, archives, or downloads an update.

## What the numbers are based on

The [design notes](design.md), collected from the code itself, go into each of these in depth.

- **Fights**: a fight runs from the game's `BEGIN_COMBAT` line to its `END_COMBAT` line. The game also writes that pair in the middle of a fight, a fraction of a second apart, most often as you are resurrected. When combat starts again within a second of ending and an enemy the group was hitting is still alive, the app carries on with the same fight: its first part shows as a fight until the fight really ends, and that entry is then brought up to date.
- **Damage**: a player's damage is every hit of theirs or their pets' on a hostile unit: direct hits, damage-over-time ticks, what got through a block and what an enemy's damage shield absorbed, the same results Combat Metrics sums. Overkill past the target's remaining health is not counted. Boss DPS is the part dealt to units the game flags as bosses; the Infinite Archive's arc bosses carry no such flag, so those fights show the total alone. Every DPS figure divides by its dps time, first hit to last and a second at least, as Combat Metrics' does: a player's by the span of their own hits, their boss DPS by their hits on the bosses, the group's by the group's; the fight time shown beside it divides nothing. Measured on 113 split logs, that raises the group's figure by a median 1% in boss fights of a minute or more and a player's own by a median 6%. The damage window (click a DPS figure) breaks a player's damage down by ability and by target the way Combat Metrics does.
- **Roles**: the largest resource pool decides. Health is a tank and stamina a DPS. A player whose largest pool is magicka is a healer when a restoration staff is equipped on either bar, or when they healed other players for more than the damage they dealt in that fight; otherwise a DPS. When all three pools are within 10% of each other, taunt and heal abilities on the bars decide instead.
- **Builds**: `PLAYER_INFO` events carry each player's slotted abilities, gear and long-term effects. The class skill lines are read from the class passives among those effects, with the slotted abilities filling in for a line whose passives a character has not learned; a build has at most three lines. The same table names the Class Mastery passives: from the passive list for a mastery whose effect is always on, and from the effect a proc mastery fires (the player being its source) for the others, kept for the rest of the session.
- **Werewolf form**: the game writes only a player's two human bars, never the bar a werewolf fights with. The app tells a player is in werewolf form from the effects the game puts on them as they transform, and rebuilds their werewolf bar from the werewolf skills they cast in form; a Carnage counts as its Pounce, which it replaces at close range.
- **Gear sets** are mapped through the [LibSets](https://github.com/Baertram/LibSets/tree/LibSets-reworked/LibSets) database. Each equipped item comes with its trait, quality and enchant. The log does not say how heavy an armor piece is or what a weapon is, so both are looked up by item id in tables from UESP's item database. A slotted poison is named the same way. Food is recognised by the buff list of the LibFoodDrinkBuff addon.
- **Tracked effects**: every buff and debuff is an `EFFECT_CHANGED` line naming the ability, the caster, the target and the stack count. A rule's uptime is the union of its ids' spans over the units of its scope, and its stacks the highest count among them, averaged over the time it was up. The game never logs Touch of Z'en's stacks, so `dots` counts the wearer's effects that tick as damage over time, as Combat Metrics does. A rule shows when its effect was up, or when it is `expected` in the fight's group size, counted from the players in the fight.
- **Build issues**: the `(i)` rules read the same `PLAYER_INFO` gear and bars, with the weights, weapon types and weapon skill lines looked up in the bundled tables, and the role the heuristic above gives. Whether a proc set ever fired is read from the `EFFECT_CHANGED` lines the wearer is the source of, over the whole logging session.
- **Scribed skills**: the log names a scribed skill's focus, signature and affix scripts on its `ABILITY_INFO` line, directly before the `PLAYER_INFO` of the player who uses it. That is how scripts are tied to players: the ability id alone covers several focus scripts of a grimoire, so two players with the same id can run different skills.
- **Deaths**: player `DIED` events during the fight, and `KILLING_BLOW` events on a player, which is how the log records a player killed by another player. The recap comes from the `COMBAT_EVENT` lines that hit or healed that player in the 5 seconds before.
- **Icons and links**: the log names each ability's icon file, and the app ships those icons extracted from the game. ESO-Hub links come from bundled maps of ESO-Hub's sitemaps; nothing is sent to ESO-Hub until you click.

### Limitations

- Players stay anonymous ("unknown" builds) until the log has produced `ABILITY_INFO` and `PLAYER_INFO` events for them.
- Sets the bundled LibSets data does not know appear as `Set#<id>` and have no link.
- A scribed skill's scripts are not always in the log, and the skill then shows `(scripts not in log)`. The game sometimes writes a player's skill without scripts (they usually follow by a later fight), and it writes each script combination once per logging session, for the first player seen with it, so a later player with the same combination gets no line of their own. When that leaves more than one possibility, the skill shows under the grimoire's name. For the same reason, a player who re-scribes mid-session to a combination already written keeps showing their earlier scripts.
- After an ESO patch, new skills show as text until the icon set is refreshed. The ESO-Hub link maps use English page names, so logs from a non-English client will not link.
- Death recaps show what the log records: damage that reached health, blocks, dodges, and shield absorption. What armor and resistances mitigated is not in the log, and neither are health costs the player paid themselves, which appear only as a drop in the health column.
- Gear is logged per equipped slot: an empty slot (the off hand beside a two-handed weapon, say) has no entry. A piece from a set newer than the bundled tables shows a dash in the Type column until they are refreshed.
- Roles are a heuristic. A healer whose largest pool is health or stamina shows as a tank or a DPS, and a restoration staff from a set newer than the bundled weapon table is not recognised (out-healing their own damage still marks them a healer).
- The build window shows the build as combat started. The game writes it once per fight, so gear or skills swapped during the fight do not show. The build-issue rules judge that same snapshot.
- The heavy-armor rule depends on the role heuristic: a damage dealer who stacks health reads as a tank and is not judged, and a stamina-heavy tank who never taunts reads as a DPS and is. The never-fired rules count fights since the log session began, so the first long fight of a session can report a set that fires in the next; a weapon skill from a set newer than the bundled tables is not judged.
- The werewolf bar holds only the skills the player has cast in form in this logging session, in the skill line's order, as the log does not say which slot holds which skill. A skill slotted but never cast is missing, so the first fight after transforming can show only a few.
- A crafted poison is named by its primary effect (`Damage Health Poison IX`); its other effects are not in the log. A food added to the game after the bundled list was built reads as `no known food or drink`.

## When something looks wrong

- **No fights appear**: logging is off in-game (see [First run](#first-run)); **Last entry** turns green while the log is being written. A fight appears only once combat ends.
- **"Waiting for Encounter.log"**: logging has never been enabled, or the log lives somewhere unusual: point Settings → Encounter log at it.
- **DPS differs from Combat Metrics or ESO Logs**: a player's own figure counts the same hits over the same dps time as Combat Metrics, so it should agree. Check three things. In a fight with a boss, the first figure is boss DPS (`boss / total`). The group's DPS divides by the group's own first-to-last span, where Combat Metrics divides the group's damage by *your* dps time. And a fight the game split in two around a resurrection is one fight here. See [Damage](#what-the-numbers-are-based-on).
- **A set shows as `Set#123`**: the set is newer than the bundled set table, so it has no name or link until the table is refreshed in a later release.
- **An ability shows as text instead of an icon**: the icon is not in the bundled set; the name still links to ESO-Hub.
- **A weapon's Type is a dash**: the weapon is from a set newer than the bundled weapon table.
- **Archive was skipped**: ESO was running and had the log open. Close ESO and use **Archive now**, or let the next app start handle it.
- **The app closed unexpectedly**: `crash.log` next to the settings file (`%LOCALAPPDATA%\esolog-tail\` on Windows, `~/.config/esolog-tail/` on Linux) has the details; please attach it to a [GitHub issue](https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities/issues).

## Where the app looks for the log

On Windows, auto-detection picks the most recently updated of:

- `%USERPROFILE%\Documents\Elder Scrolls Online\live\Logs\Encounter.log`
- `%USERPROFILE%\Documents\Elder Scrolls Online\Logs\Encounter.log`
- `%USERPROFILE%\OneDrive\Documents\Elder Scrolls Online\live\Logs\Encounter.log`

On Linux it uses the first of these that exists (each ends in `Documents/Elder Scrolls Online/live/Logs/Encounter.log`):

- `~/.wine/drive_c/users/Public/` and `~/.wine/drive_c/users/<you>/`
- `~/.steam/steam/steamapps/compatdata/306130/pfx/drive_c/users/steamuser/`
- the same Steam path under `~/.local/share/Steam/` and, for Flatpak Steam, under `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/`

For Lutris, Bottles, a Steam library on another drive, or any other location, set the path under Settings → Encounter log.

## Migrating from the terminal version

Versions up to 0.2.7 were terminal applications launched from `.BAT` files with command-line flags. Their behaviour moved into the app:

| Old flag | Where it went |
|---|---|
| `-f, --log-file PATH` | Settings → Encounter log |
| `--tail-and-split` / `--split-dir` | Settings → Per-encounter split files |
| `--save-reports` / `--reports-dir` | Removed; fight summaries live in the app (use Copy fight) |
| `--read-all-then-tail` | Automatic: the app replays the current session on attach; use Open log for review for older fights |
| `--read-all-then-stop` (replay) | Open log for review |
| `--no-wait` | Removed: the app always waits and shows a waiting state |
| `--replay-speed` | Not needed: review mode loads at full speed |
| `--no-tui`, `--diagnostic`, `--list-hostiles` | Removed with the terminal output |
| `-v, --version` | Window title, About, or Apps & Features |

Delete your old `.BAT` files and `esolog-tail.exe`; the app is `esolog-gui.exe`.
