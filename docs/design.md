# Design notes

How ESO Log Tail solves the problems that are not obvious from the code's
shape: what the encounter log really carries, which game data is trusted
for what, and the rules chosen after measuring real logs. Every note here
is the docstring or a tagged comment of the code it describes, collected by
`scripts/build_design_doc.py`; edit the code, then rerun the script. The
link under each note is where it lives.

## The encounter log: unit states and effects

### ESOLogAnalyzer._handle_effect_changed

*[src/esolog_tail.py:2512](../src/esolog_tail.py#L2512)*

A buff or debuff coming, going or refreshing: the tracked effects
(every item of the uptime line), the timeline strip's built-in rows, and
enemy health.

Design: an EFFECT_CHANGED line is ``changeType, stackCount,
castTrackId, abilityId, <sourceUnitState>, <targetUnitState>``. A
unit state is ten fields (unitId, health, magicka, stamina,
ultimate, werewolf, shield, x, y, heading), so the source's id is
fields[4] and the target's fields[14]; the target state is a single
"*" when the effect is on the source itself. Reading the target from
the wrong offset (fields[10], the source's shield, nearly always
"0") made every group buff look as if it were only ever on its
caster, so the one reader, extract_effect_fields, serves every
consumer here. Enemy health is read from the target state when the
target is explicit and from the source state when it is "*"; the
source state's health is never the target's.

## Fight boundaries: fights the game cuts in two

### Fights the game cuts in two

*[src/esolog_tail.py:81](../src/esolog_tail.py#L81)*

The game ends and restarts combat in the middle of a fight, most often when the logging player is resurrected: END_COMBAT, then BEGIN_COMBAT a moment later. 48 logs of April to October 2026 held 53 such pairs, 0 to 484 ms apart, 45 of them straight after the player accepted a resurrection. A BEGIN_COMBAT this soon after END_COMBAT continues that fight when an enemy the group hit in the fight's last seconds is still alive; none of the 51 pairs between half a second and three seconds apart was the same pull.

### ESOLogAnalyzer._continues_last_fight

*[src/esolog_tail.py:1789](../src/esolog_tail.py#L1789)*

Whether a BEGIN_COMBAT at *timestamp_ms* carries on the fight that
just ended instead of starting one (see COMBAT_RESUME_MS): it follows
the END_COMBAT closely, and an enemy the group was hitting when the
fight ended is still alive.

### ESOLogAnalyzer._resume_last_fight

*[src/esolog_tail.py:1804](../src/esolog_tail.py#L1804)*

Reopen the encounter END_COMBAT closed. Its damage, deaths and
players are kept, and the entry frontends already have is brought up
to date when the fight ends (see _publish_fight).

### A death just after END_COMBAT

*[src/esolog_tail.py:75](../src/esolog_tail.py#L75)*

The blow that kills the last player standing ends combat, and that player's death event is written after END_COMBAT (about 85 ms later in live logs). A player death this soon after END_COMBAT belongs to the fight that just ended.

## Starting mid-session

### LogFileMonitor._load_latest_session

*[src/esolog_tail.py:4201](../src/esolog_tail.py#L4201)*

Replay the log's most recent session up to the attach point.

Gives a mid-session attach the same state as having run since the
session began: full roster, this session's fights in history, and
the session's split file (created only if absent). Best-effort:
failures leave plain tailing.

Every session is replayed whole, however large. Until issue #107 one
over 768 MB got only the roster-only preamble sweep, which is not
enough: who owns which companion and pet is learned from the rest
of the session, and fights rebuilt that way differed in every one
of 18 measured on a Dreadsail Reef split. The sweep is left for a
session whose BEGIN_LOG is beyond the 2 GB lookback, and for a
replay that fails.

## Log freshness

### src/log_freshness.py

*[src/log_freshness.py:1](../src/log_freshness.py#L1)*

Log freshness derivation: when was the newest entry written to an encounter log?

Every ESO encounter log line starts with a relative millisecond offset from the
session's BEGIN_LOG event, and each BEGIN_LOG carries a Unix epoch (ms):

```
    5,BEGIN_LOG,1755729685851,15,"NA Megaserver","en","eso.live.11.1"
    43016,COMBAT_EVENT,DAMAGE,...
```

latest entry time = most recent BEGIN_LOG epoch + last line's relative offset.

Derivation is exact when a BEGIN_LOG is reachable, and falls back to the file's
mtime (marked "approximate") otherwise. Logs can reach tens of GB, so the
backward BEGIN_LOG search is capped rather than unbounded.

## Roles

### infer_player_role

*[src/esolog_tail.py:352](../src/esolog_tail.py#L352)*

Infer player role (T/H/D) from resources, weapon and healing heuristics.

A player whose largest pool is magicka is a healer when they have a
restoration staff equipped, or when they healed other players for more
than the damage they dealt (which still finds a healer whose staff the
bundled list does not know yet).

Args:
    player: PlayerInfo with max_health, max_magicka, max_stamina
    player_damage: Total damage dealt by this player
    player_healing: Total healing done to OTHER players
    skill_line_role: Role from ability-based inference (fallback)
    restoration_staff: Whether a restoration staff is on either bar

Returns:
    'T' for tank, 'H' for healer, 'D' for DPS

## Class skill lines and subclassing

### src/eso_sets.py

*[src/eso_sets.py:1](../src/eso_sets.py#L1)*

Which class skill lines a player has (subclassing).

Design: since Update 46 a character can swap any of its three class skill
lines for another class's, so the class id in UNIT_ADDED no longer says
what a build is. Two things in the log do.

The passives. The first list on a player's PLAYER_INFO line is their
long-term effects, and among the mundus boon, food and set auras it carries
every class-line passive the character has learned, by ability id. A
character with Assassination, Herald of the Tome and Animal Companions
lists Hemorrhage, Executioner, Splintered Secrets, Advanced Species and so
on. Each passive belongs to one line, so the lines are read off the ids
with no guessing: skill_lines_of looks each id up in
data/skills/class_passives.json (UESP's player skill table cut down to the
203 class passives by scripts/generate_class_passives.py, masteries
included) and names a line for every passive found. The lookup is by id,
never by name or icon: the group's Combustion resource return, the Reusable
Parts ally effect and the Resolute Defense proc share a passive's name and
land in the same list, and a passive's icon does not tell it from an active
(Blessing at the Peak uses an ability_* icon). Both rank ids of a passive
are in the table; a character lists the rank they have.

The slotted abilities, as a filler. ESOSubclassAnalyzer matches the names
of the bar abilities (ABILITY_INFO) against SKILL_LINE_ABILITIES, every
class line's ultimate, actives and morphs as the game names them, exactly
(never by substring: "Carve" is Two Handed, not Fatecarver; "Swarming
Scion" is Vampire, not a Warden Swarm), and the lines with the most matches
win. It cannot see a line the player slotted nothing from, which is routine
for healers, tanks and Arcanist DPS, and the passives can miss a line whose
passives a mid-level character has not learned yet. So skill_lines_of takes
the passives' lines first and fills up to three from the slotted guess.
In 73 split logs of September and October 2026 (7,019 distinct builds) the
passives named exactly three lines for 98.5% of builds and never
contradicted the slotted guess, which had missed one or more lines in 56%
of them; 489 builds borrowed a line, and for 133 of those the lines shown
change, 18 of them borrowed purely for the passives (nothing slotted). A
character has at most three lines, since subclassing swaps lines and never
adds a fourth; a fourth line of passives, seen three times in the survey,
loses to the lines whose actives are slotted.

The fight view and build window show only the borrowed lines, each with a
plus sign before its first word ("NB +Herald" for a Nightblade who swapped
a line for Herald of the Tome), so a stock build shows just its class. A
player whose class is unknown shows every line found.

Class Mastery passives (five per class; only a character with all three of
its own lines can take them) take the same place beside the class, after a
colon ("NB: An Eye for Exploitation, Above and Beyond"), and are named on
the build window's mundus and food line too. The PLAYER_INFO list names
only some of them, because it holds only the passives whose effect is always
on: a mastery that works by a proc (Unbound Potential, Abyssal Emergence,
Wildfire Embers, Bright Harbinger...) is never in it. Such a mastery shows
in the log as an EFFECT_CHANGED the player is the source of, under one of
a few effect ids that carry its name; the table lists those 60 ids as
mastery_effects, and mastery_of_effect names the mastery of one. The
engine notes a mastery on its holder when such an effect fires, and keeps
it for the rest of the session, since a mastery does not change between
fights. In the 73 survey logs, 11,697 pure-class player rows: the list
alone named a mastery for 42% of them, the list plus the fight's own
effects for 79%, the list plus the session's effects for 90% (191 of 209
characters). Nine of the 35 masteries fire no effect of their own name;
for four of them the effect is named after the buff it grants and has an
id in the same block, sourced by one class alone in those logs: Lead from
the Front's Major Berserk and Major Protection (Dragonknights), Tundra's
Maw's Major Brittle and Bountiful Harvest's Major Heroism (Wardens), and
Cutthroat's Focus's Cutthroat's Mockery (Nightblades). The table carries
those as signature effects (scripts/generate_class_passives.py says how
each was pinned down), and mastery_of_effect checks the source's class for
them.

Three of the other five give resources and fire no effect at all, only the
gain: a COMBAT_EVENT POWER_ENERGIZE whose source is the holder, under an id
carrying the mastery's name (Conservation of Energy's Magicka and Stamina
to the Sorcerer, Nocturnal Inspiration's Ultimate to the Nightblade, Share
the Spoils' Magicka, Stamina and Ultimate to the Nightblade's group). The
engine reads a mastery from those as well. In 103 split logs of September
and October 2026, every POWER_ENERGIZE under a mastery id, about 244,000
lines over twelve ids, came from a player of that mastery's class.
Devout Guardian's shield is an effect called Hold the Line, kept as a
signature effect. Bastion of Light alone stays invisible: it heals through
Sacred Ground and gives Ultimate, and nothing in the logs names it.

The game lets a character take two masteries ("selecting two passives",
its own text). A third shown beside the class means an id fired for
someone who does not hold its mastery. Font of Power's 263878 has: three
or four gains late in a session from Sorcerers whose Calculated Defense
and Conservation of Energy fire from the first minutes to the last; most
sessions that show Font of Power show dozens to hundreds of gains.

Cycle Unending's effect (263532) is the one a pet fires: its source is the
Necromancer's Blighted Blastbones, Skeletal Archer or Grave Lord's
Sacrifice, and it lands on their owner (220 of 239 gains in twelve logs).
So the engine credits a mastery effect whose source is a player's pet to
that player (the encounter's pet_ownership). Before, 84% of Necromancer
rows showed one mastery, and no Necromancer damage dealer ever showed two;
in a replay of the 103 split logs of September and October 2026 the
change added Cycle Unending to 792 rows, all Necromancers, none of them
gaining a third, and nothing else in any fight changed (issue #149).

A character can take two masteries (MAX_MASTERIES), and a row often shows
one. After that change, 1,581 of 13,818 pure-class rows (11%) in those
logs did: 915 were fights before the second showed later in the same log,
since a proc mastery is known only once it fires (Booming Voice was never
on a session's first fight, Erudite's Rigor on 16% of them, Abyssal
Emergence 39%, Bright Harbinger and Lead from the Front 43%); the rest
came from 59 characters' logs in which it never showed, Templars the most
(Bastion of Light is never logged). Two things follow. The engine fills a
mastery it finds into the player's earlier fights of the same BEGIN_LOG
session, on rows that show fewer than two, and announces each of those
fights again: a mastery does not change within a session, which is why it
is kept for the rest of it. That leaves 674 rows (5%) showing one, none of
them before a second that shows later; Templars 23% of theirs, Sorcerers
18%, every other class 6% or less. And where one still shows, the fight
pane and build window say a second is likely, listing the class's others
the likeliest first for the player's role (likely_masteries, from the
file's mastery_order; the generator says how the order was counted); a
mastery the log never names is listed last and marked
(masteries_never_logged).

## Ability icons and ESO-Hub links

### src/ability_icons.py

*[src/ability_icons.py:1](../src/ability_icons.py#L1)*

Ability icons and ESO-Hub skill links: engine-side helpers (no Qt).

The encounter log names every ability's icon in its ABILITY_INFO line
("/esoui/art/icons/ability_arcanist_002_b.dds"). The app ships one PNG per
ability icon under data/icons/abilities (built by
scripts/extract_ability_icons.py from the installed game), so an icon is
resolved purely by that filename's stem; nothing is downloaded at runtime.

ESO-Hub page links come from data/esohub/ (built by
scripts/generate_esohub_links.py from ESO-Hub's sitemaps): a logged ability
name is slugified the way ESO-Hub slugs its pages and looked up in
skills_en.json; a LibSets set name is looked up as-is in sets_en.json. A
scribed skill ("Shocking Banner") and its scripts ("Lingering Torment") are
looked up by slug in scribing_en.json. Unknown names get no link.

### src/gui/icon_cache.py

*[src/gui/icon_cache.py:1](../src/gui/icon_cache.py#L1)*

In-memory cache of bundled ability icons for the fight view.

Icons are PNG files under data/icons/abilities, one per game icon stem
(see scripts/extract_ability_icons.py). Each image is read from disk once
and kept as a QImage; a miss is remembered too, so an ability with no bundled
icon costs a single stat() per session and then renders as text. An icon can
also be had with a colored ring drawn inside its edge (the fight view marks
the abilities a player taunted with that way); each ring color is drawn once
per icon.

### scripts/extract_ability_icons.py

*[scripts/extract_ability_icons.py:1](../scripts/extract_ability_icons.py#L1)*

Extract ESO ability icons from the installed game and convert them to PNG.

Why: the encounter log names every ability's icon
(ABILITY_INFO ... "/esoui/art/icons/ability_arcanist_002_b.dds"), so the app
can show icons offline if it ships one PNG per icon found in the game files.
Three families are extracted: ability_*.dds (player skills, for the ability
bars), death_recap_*.dds (what monster attacks use, for death recaps), and
the skill icons an update named after itself, u<NN>_ability_*.dds: Update 50
gave five werewolf skills u50_ability_werewolf_* icons, and Crypt Transfer
has had u38_ability_armor_ultimatetransfer since Update 38. A slotted skill
whose icon belongs to no such family is named in DEFAULT_STEMS: Rampage, what
the werewolf ultimate becomes at full Fury, uses an achievement icon. Run
this after each ESO update to refresh that set.

Requirements (Windows):
  * EsoExtractData v0.53+ by UESP: https://en.uesp.net/wiki/ESO_Mod:EsoExtractData
    Pass --extractor, set ESO_EXTRACT_DATA, or keep it at D:\extract-eso\.
  * Pillow for the DDS -> PNG conversion (pip install -r requirements-build.txt).
  * An installed, patched ESO client (its depot\eso.mnf). Pass --eso-dir, set
    ESO_INSTALL_DIR, or let the script probe the usual Steam/Zenimax paths.

Pipeline:
  1. Dump eso.mnf's file table without extracting anything (-k -m, ~4 s).
  2. Find every \esoui\art\icons\<prefix>*.dds row and merge their table
     indexes into a few dozen -s/-e ranges (a small gap of unrelated files is
     cheaper than another ~3 s MNF reload; -n only matches exact names).
     The extractor's -s/-e counter is offset from the table's Index column
     (2,337 on the Update 49 client), so two one-file probes calibrate it.
  3. Extract those ranges to a temp folder. Extracted files are numbered by
     table Index (<archive>\<Index>.dds), which the table maps back to names.
     Convert the matching .dds files to PNG at --size px, write
     <out>/manifest.json and report what changed against the previous
     manifest. Optionally (--check-log) verify that every icon slotted on a
     bar in an Encounter.log exists in the output.

The game folder is only read. Temp output is deleted unless --keep-temp.

## Scribed skills and their scripts

### src/scribing.py

*[src/scribing.py:1](../src/scribing.py#L1)*

Scribed skills: which scripts each player wrote into their grimoire skills
(engine side, no Qt).

A scribed skill is a grimoire (Banner Bearer, Wield Soul, ...) with a focus,
a signature and an affix script. The grimoire and the focus script give the
skill its name ("Shocking Banner" is Banner Bearer with Shock Damage); the
signature and affix scripts add effects that the name does not show. The
encounter log lists all three scripts after the two flags of the skill's
ABILITY_INFO line:

```
    ABILITY_INFO,217699,"Shocking Banner","/esoui/art/icons/ability_grimoire_support.dds",F,T,"Shock Damage","Class Flourish","Heroism"
```

The grimoire is not named, but every grimoire has its own icon (GRIMOIRES).

What the log does, as far as four logs from September 2025 to October 2026
show (225 ABILITY_INFO lines with scripts):

- An ability id does not identify the skill. One id covers several focus
  scripts of a grimoire (217699 is Fiery, Fortifying, Magical, Restorative,
  Shocking and Sundering Banner), so the name and the scripts of a bar slot
  belong to the player, not to the id.
- The game writes each (ability id, scripts) combination once per BEGIN_LOG
  session, directly before the PLAYER_INFO of the first player seen with it
  (0-1 ms earlier, with only other ABILITY_INFO lines in between). That
  PLAYER_INFO is how a combination is tied to a player.
- The game also writes the skill without scripts, as an ordinary
  seven-field line, once per session and id. Most of these lines come at
  another moment (46 of 60 in the October 2026 log, presumably when the
  skill is first used). The rest sit directly before a PLAYER_INFO, for a
  player whose scripts the game does not have; for 10 of those 11 players
  the scripts followed before a later PLAYER_INFO, 0 to 206 s on.
- A later player whose line was already written, with or without scripts,
  gets no line of their own. Their skill is then one of the lines written
  for that id: certain when there is one, otherwise a short list of options.
  The same holds for a player who re-scribes to a combination already
  written in the session; the log gives no sign of that change.

The approach follows the ESO Log Tool (github.com/sheumais/logs), which
renames scribed skills to "Name (Signature / Affix)" before uploading logs.

## Werewolf form: the bar the log never writes

### src/werewolf.py

*[src/werewolf.py:1](../src/werewolf.py#L1)*

Werewolf form: the bar the log never writes, and the ultimate it renames
(engine side, no Qt). Issue #17.

Design: since Update 50 a werewolf's skills sit on a bar of their own, which
the game switches to on transforming. PLAYER_INFO writes only the two human
bars, so a player who spends a fight in form shows bars they never used. Of
1,068 PLAYER_INFO rows written while a player was in form (55 split logs of
July to October 2026, client versions 12.0 and 12.1, about 25 characters),
1,053 carry the human bars. The other 15, from two anonymous players on
12.0, carry the werewolf bar in place of the front bar, in the slots' real
order and agreeing with their casts. A Rockgrove log of 2026-10-24 (client
12.1, issue #49) showed a third shape: all 11 rows of one player list a
single bar as both the front and the back bar, three werewolf skills beside
Razor Caltrops and Inner Fire, while the player, in form the whole log,
cast Hircine's Rage and Ferocious Roar in every fight and never those two.
The form is one bar of five skills with no swap, so that bar was stale. A
logged bar holding three or more werewolf skills (``is_werewolf_bar``) is
therefore no human bar and no trusted werewolf bar: the engine drops it
before anything reads it, and the werewolf bar is rebuilt from casts for
every werewolf alike. A human bar can hold one werewolf skill for its
while-slotted bonus (Hircine's Fortitude on one player's front bar, 18
rows), which the threshold spares. Werewolf players spent 1,234 of their
1,524 fights of 5 s or more wholly in form, 110 partly, and 180 not at all.

The bar is rebuilt from casts. Each werewolf skill is cast under the id of
the skill its slot holds, one id for all four ranks, with one exception:
within close range a Pounce morph becomes its Carnage version, cast from
the same slot, so SLOT_SKILLS maps Carnage, Brutal Carnage and Feral
Carnage to their Pounce. Feeding Frenzy is not a slot: it is Roar's
synergy, which every group member activates. The light and heavy werewolf
attacks and Devour are not slots either, though they prove the form. Of 58
player sessions with werewolf casts, 55 cast exactly five distinct bar
skills, three cast fewer, and none ever cast a sixth or two morphs of one
skill, so the casts of a whole session can be pooled. A fight's own casts
show the whole bar in only 58% of fights; the session's casts up to the
fight's end show it in 94%, which is the rule here. In the two 12.0 cases
where the game logged the werewolf bar, the rebuilt bar agreed with it; in
the 12.1 case the casts were right and the log was not. Casts
say nothing of the slots' order, so the bar follows the skill line's order
(LINE_POSITION): Pounce, Hircine's Bounty, Roar, Gnash, Rending Claws. A
skill slotted but never cast stays unknown.

The form itself is a hidden effect, 39038 "Werewolf Transformation", plus
the morph's own effect (47083 Werewolf Berserker, 47069 Pack Leader, 47028
for the unmorphed transformation in older logs). On client 12.1, 39038 is
on for 99.9% of in-form casts and for none of the casts of human-bar
skills. A log that starts mid-form has no GAINED: the werewolf casts are
the only sign, and the form is taken to have begun with the session. Death
does not end the form: after 241 of 251 deaths in form the player's next
skill was a werewolf skill, with no new transformation logged.

The ultimate: the unit state's werewolf field is Fury, from 0 to 1000. At
full Fury the transformation ultimate becomes Rampage, or Enduring Rampage
for Pack Leader, and PLAYER_INFO then lists that in the slot, but only for
the player who writes the log. For that player, 170 of 171 fight starts in
form with full Fury listed Rampage, and 1 of 181 other starts did. For
group members, 0 of 424 such starts did. So Rampage in a bar is the morph
caught at full Fury, and the bar shows the morph instead (``stand_in_for``):
the player's active morph effect names it, else the morph slotted in their
earlier rows, else STAND_INS. The client names more Rampage ids than the
two seen in a slot; the unseen ones are left unmapped.

Icons: five of the werewolf skills (Pounce, Brutal Pounce, Feral Pounce,
Rending Claws, Claw Fury) carry Update 50 icons named u50_ability_*, and
Rampage an achievement icon, all outside the ability_* family the app used
to bundle (see scripts/extract_ability_icons.py).

## Cast counts and casts per minute

### src/casts.py

*[src/casts.py:1](../src/casts.py#L1)*

Cast counts and casts per minute (engine side, no Qt). Issue #94.

Design: every player's BEGIN_CAST lines are in the log, the group's as well
as the logging player's. One cast can write two of them under one
castTrackId: a channelled heavy attack writes one at the press and one for
the channel (11 of 11 for a Lightning staff in the Tideborn Taleria fight
of 2026-10-27), and a synergy can write two ability ids (Healing
Combustion, 63507 then 95042, on the same timestamp). A cast is therefore
one castTrackId per caster, whatever the lines under it.

A fight's casts are those begun from its start to its end, the engine's
fight window (BEGIN_COMBAT to END_COMBAT). Combat Metrics counts the same
way: for the logging player in that fight it showed Force Pulse 37,
Subterranean Assault 12, light attacks (Lightning) 52 and every other skill
alike, and left out the pre-buffs cast in the ten seconds before the pull
(Blockade of Frost 7 in both). Its light attacks (Ice) read 15 against the
log's 14. Over 12 trial and arena splits (193 fights, 66,244 casts), 3% of
casts began in the 3 s before BEGIN_COMBAT; those are not counted.

A count sits under a bar slot when the cast's id is the slot's, or its name
is (Venom Skull is slotted as 117624 and cast as 123704, Incapacitating
Strike as 36508 and 113105, Crystal Fragments' instant proc is 114716), or
both are in one of the families of SKILL_FAMILIES. The Destruction Staff
families are there because the bar lists those skills under a base id
(Elemental Blockade 39011) or the element of the staff equipped when
PLAYER_INFO was written, while the cast
carries the element of the staff in hand: over the October splits,
Elemental Blockade was cast as Blockade of Fire 2,651 times, Frost 2,391,
Storms 1,257, and a bar listing Blockade of Storms was cast as Blockade of
Frost 253 times. A skill slotted on both bars shows its total under each
(Chris's choice: totals per skill, not per active bar).

One skill writes no BEGIN_CAST at all: the Arcanist's Fatecarver, matched
in 0 of 1,514 player-fights with Pragmatic Fatecarver slotted and 0 of 68
with Exhausting Fatecarver (no other slotted skill is systematically
unmatched; those that are never cast are slotted for their passives,
banners cast before the pull, or rarely used ultimates). Each use instead
gains its channel effects on the caster under one castTrackId: Pragmatic
writes 186369, 189533, 201265 and 201273 (6,867 casts in the October
splits; 201265 also comes alone, a shield), Exhausting 186780, sometimes
with 184291. CHANNEL_EFFECTS turns such a GAINED into a cast of the morph,
one per castTrackId like any cast. No log had the unmorphed Fatecarver.

Casts per minute counts every cast (Chris's choice), extras included,
over the fight's duration; a player who left during the fight over the
share of it they were there for.

The extras are the casts no slot holds, by kind (EXTRA_KINDS): light and
heavy attacks (every id the client's own name table, en.lang table
198758357 of Update 51, names "Light Attack (…)" or "Heavy Attack (…)"),
bashes, weapon swaps, dodges, synergies, potions and Break Free. The log
marks neither a synergy nor a potion: a synergy writes only its own
effects, and a potion is cast under its first trait's effect (Restore
Health, Major Brutality) with the generic icon Recall and Mount Up also
carry. Both come from the ids seen in the October splits: SYNERGIES holds
the skill-line synergies (class, guild, Undaunted, werewolf), not the
trials' mechanics; POTIONS the alchemy block 45221 to 45241, the vendor,
Alliance War and Crown potions. Werewolf light and heavy attacks count as
light and heavy attacks.

A companion's casts are counted the same way, under its row key
(companions.py) and over the whole fight (issue #130). Its light attacks,
block, dodge, bash and break free have ids of their own, none of them in
the player's sets (its light attacks are plain "Light Attack", one id per
weapon look), and it never heavy attacks, swaps weapons, takes a synergy
or drinks a potion: over 214 split logs with a companion its casts that
are not skills were those ids and Mount Up. So its extras line has kinds
of its own (COMPANION_EXTRA_KINDS), Block among them, which a player's
never needs (a player's block writes no cast), and a player's 'casts'
stays as it was.

## Magicka, stamina and ultimate spent and gained

### src/resources.py

*[src/resources.py:1](../src/resources.py#L1)*

Magicka, stamina and ultimate spent and gained in a fight (engine side, no
Qt). Issue #125.

Design: every unit state in the log is ``unitId, health, magicka, stamina,
ultimate, werewolf, shield, x, y, heading`` with each pool as
``current/max``, and every group member's pools are real values, not only
the logging player's (each of 12 players in an Aetherian Archive split of
2026-10-24 had 1,100 to 2,600 distinct states, sampled in combat at a p95
gap of about 100 ms). Nothing logs a cost: a skill's cost is a drop in the
caster's state, nearly always already in the state its BEGIN_CAST line
carries (Stampede -3,443 stamina 141 of 141 times), and sometimes on a line
written at the same millisecond just before it. So the figures are read
from the states:

- Spent is the sum of the drops between a player's consecutive states, and
  a drop at the millisecond of one of the player's casts is that cast's
  cost; light and heavy attacks and weapon swaps cost nothing and are never
  charged. Over the AA and Sunspire splits that put 70 to 91% of magicka
  and 60 to 78% of stamina spending on casts; the rest (blocking,
  sprinting, a cost written later, like Killer's Blade's on the next line)
  leaves no line of its own and is shown as other spending, not guessed.
- A gain the game logs is a COMBAT_EVENT POWER_ENERGIZE, whose powerType
  is a flag (1 magicka, 2 werewolf, 4 stamina, 8 ultimate) and whose unit
  state is the one after the gain (8,455 of 9,262 rows moved the pool by
  the logged amount). Its ``overflow`` is always 0, so the gain booked to
  the row's ability is the pool's own rise there, and a row arriving at a
  full pool is waste (logged amount less the rise). The giver is the row's
  source when that is another player (Pillager's Profit, Bountiful
  Harvest); a source that is not a player, like the enemy carrying Minor
  Magickasteal, names nobody.
- Every other rise is "regeneration and unlogged": base regeneration, base
  ultimate generation and ultimate on hit have no line (only 38 to 55% of
  magicka and stamina rises, and a quarter of ultimate rises, were on an
  energize row). It is a residual, not a measurement of regeneration.
- Logged ultimate never arrived at a full pool (0 of 5,728 points), so lost
  ultimate cannot be counted; the time at full ultimate is the figure (0 to
  46% of combat across the AA group). A state's current can exceed its max
  (19,062 magicka states in AA: the max lags), so "full" is current >= max.

The figures are net per observation: a cost and a gain inside one gap
cancel. On trial logs that is a few percent; reading the effect lines'
source states too, as the engine does, keeps it there (a solo March of
Sacrifices split read stamina spent 29k without them, 41k with).

The engine can resume a fight the game cut in two (COMBAT_RESUME_MS), so
the figures are kept in one-second buckets per player and summed over the
fight's window, then pruned at fight end as casts.py prunes its casts. A
step between two states is capped at MAX_STEP_MS for the time at full, so
the first state of a fight does not carry the idle time before it.

## Companions: a row of their own under their owner

### src/companions.py

*[src/companions.py:1](../src/companions.py#L1)*

Companions: a line of their own under the player they belong to (engine
side, no Qt). Issue #74.

Design: a companion (Mirri, Bastian, Ember, Isobel, Sharp-as-Night,
Azandar, Tanlorin, Zerith-var) used to be one more pet: its damage and
healing were folded into its owner's figures. It is a character with its
own skills, health and deaths, so each companion that is out during a fight
now gets a row of its own on the group list, straight under its owner, with
the name and dps links a player's row has. A setting
(``companions.accrue_to_owner``, off by default, Chris 2026-10-27) also
counts its damage and healing as the owner's, as before; the group total
counts every hit once either way. Combat Metrics (LibCombat 89) counts the
player and their pets, COMBAT_UNIT_TYPE_PLAYER_PET, and never the game's
COMBAT_UNIT_TYPE_PLAYER_COMPANION, so the default also matches what a
player's own Combat Metrics shows them.

What the log writes, from a survey of the split logs (386 unique sessions,
October 2026):

- A companion is a MONSTER unit with a fixed monsterId per companion
  (COMPANION_MONSTER_IDS), no handle or character id, its companion level
  in the level field and a health pool only.
- The logging player's own companion is added with reaction COMPANION and
  ownerUnitId set to the logging player. Another member's is added as
  FRIENDLY with owner 0; a later UNIT_CHANGED names the owner (sometimes
  renaming the unit "<handle>'s Companion"), which track_pet_ownership
  reads for every pet. A companion is known by its reaction or its monster
  id, and its name is taken from its UNIT_ADDED, never from the rename.
- A companion gets a new unit id every time it is summoned again (after a
  death, a zone change, a dismissal): four unit ids for one Isobel in a
  solo Moon Hunter Keep run of 2026-10-26, where she died five times, so
  its row is keyed by owner and monster id (row_key), not by unit id: the
  re-summons of one companion within a zone are one row.
- PLAYER_INFO never names a companion, so the log has no bar or gear for
  it. Its casts carry its own ability ids, whose icons are the game's
  ability_companion_* family (124 of them bundled): the row's bar is the
  skills it was seen casting this session, in first-cast order
  (bar_ability), the way werewolf.py rebuilds a werewolf's bar, with its
  ultimate set apart at the end (bar_order). Light attacks, block, bash,
  dodge roll and break free have other icons and are left out.
- A companion's death is a DIED line naming it as the dying unit; it is
  shown on its row, not counted in the fight's Deaths, which stay player
  deaths.
- Only 15 companion lines in 386 sessions fall inside a fight (trials while
  members leave, arena stage transitions, a solo summon at the pull); the
  rest come and go between fights.

The effect rules still see a companion as a pet (ESOLogAnalyzer._unit_kind),
so ``pets`` rules, the group size an expectation reads and the pen/crit
figures do not move with the companion rows.

Casts, ultimates and healing (issue #130), from a second survey of 214
split logs with a companion, January to October 2026, that forgets a
companion's unit id at its UNIT_REMOVED (the game hands those ids to
players later, and the first survey counted those players' casts as the
companion's):

- Every cast of a companion is a BEGIN_CAST under its unit id, as a
  player's is, so the cast counter (casts.py) counts a companion's casts
  under its row key: the re-summons of one companion are one row's casts.
  Besides its skills it casts light attacks, Block, Roll Dodge, Bash and
  CPN Break Free under ids of its own; it never heavy attacks, swaps
  weapons, takes a synergy or drinks a potion (casts.COMPANION_EXTRA_KINDS).
- Each companion has one ultimate (ULTIMATES). Each id was cast by its own
  companion's monster id only: 213 casts, Raging Storm 76, Impeccable
  Shot 63, Baneslayer 23, Blade of the Crossing 18, Gore 11, Vigorous
  Tentacular Eruption 10, Unleashed Rage 7, Ruinous Outburst 5.
- Every line a companion is the source of carries an ultimate pool out of
  500, and an ultimate costs about 200 of it; but the cost is not always
  written after the cast (a Baneslayer's own BEGIN_CAST often reads 0 or 1
  already), so the ultimates are counted by their cast ids, not from the
  pool. The other way round, every fall of 150 or more in a companion's
  pool is one of these casts: one in 214 logs is not within 4 s of one, a
  Raging Storm cost written 5.5 s late. So no ultimate goes unlogged.
- An ultimate is counted as any cast is, on its BEGIN_CAST. Of the 213,
  206 ended COMPLETED, one INTERRUPTED, one PLAYER_CANCELLED and five
  have no END_CAST (two with no effect, damage or cost: the fight ended
  under them), so the count can be about 2% over the ultimates that went
  off. The parser drops an END_CAST with a cancel reason, which a rule on
  the outcome would need.
- Its healing is the engine's healing to others
  (CombatEncounter.add_healing_to_player): the heals that landed on a
  player, its owner included; not its heals on itself or on pets, and not
  the overheal.
- Two skills carry the game's generic icon (Storm Barricade 157226 and
  Fire Barricade 157145, 42 casts in combat in the 214 logs), so
  bar_ability leaves them off the bar: they count in the casts and the
  cpm only. Sepulchral Chill writes a second id (213284, the generic
  icon) under its own cast's castTrackId, which the counter counts once.
- A UNIT_CHANGED that sets a companion's owner to 0 is it leaving: 189 of
  them, after which came 3 casts and 0.04% of companion damage. None cast
  in combat before its owner was known.

## Members who leave, come back, or come back on another character

### src/presence.py

*[src/presence.py:1](../src/presence.py#L1)*

Group members who leave, come back, or come back on another character
(engine side, no Qt). Issue #78.

Design: a group list should name the people who were in the fight, once
each. Before this, a member who left stayed on the list at 0 dps in every
later fight of the zone (656 of 9,435 fights in the split logs, 1,256 stale
rows), a member who came back on a new unit id got a second row, and a
member back on another character had no row in the fight they came back to
while their damage was in the group total. The rules below were chosen so
that a player with no UNIT_REMOVED and no second UNIT_ADDED in the zone
keeps every figure they had.

What the log writes, from 386 unique sessions (October 2026):

- ``Offline`` is a loading placeholder: a UNIT_ADDED named ``Offline`` with
  the handle and character id intact, replaced by the real unit (a new unit
  id) within 0 to 29 s. It is skipped.
- Leaving is UNIT_REMOVED. Coming back is always a fresh UNIT_ADDED: the
  same character keeps its character id, and its unit id only on an
  instance reload (a ZONE_CHANGED between, which starts the zone afresh
  anyway). Without a zone change the id is always new.
- Another character of the same account is the same handle with a new
  character id (and a new per-session id); its PLAYER_INFO comes at the
  next pull, or never. In 14 of 17 cases the old character's unit was never
  removed.
- A player's UNIT_CHANGED never changes who they are, except an anonymous
  member (empty name and handle) becoming named on joining the group.
- A departed player's unit id can be handed to a monster.

The rules (Chris, 2026-10-27):

1. A player is their character: handle and character id, the character id
   alone being unique. Rows stay per character.
2. UNIT_REMOVED marks the player gone (``left_at``). The fight in progress
   keeps their row, greyed, with the share of the fight they were there for
   (present_share); from the next BEGIN_COMBAT they are off the list. A
   MONSTER added on their unit id marks them gone too, and that id is no
   longer theirs.
3. The same character back in the zone is the same row: the new unit id is
   an alias of the record, so the damage before and after the drop goes to
   one row and its dps time spans both, the gap included (as Combat Metrics
   counts it). At the next BEGIN_COMBAT the record takes the new id as its
   own, its companion and pets following, so later fights are keyed as for
   anyone else.
4. Another character is a new row, and the old character is gone. Until its
   PLAYER_INFO arrives it has no build; it is listed anyway, with the class
   from UNIT_ADDED and empty bars, when the log says it is grouped with the
   logging player, so the fight's rows add up to its group total. Anyone
   else without a build stays off the list, as before (passers-by in the
   Infinite Archive and overland).
5. Offline stays skipped.
6. An anonymous member named by a UNIT_CHANGED takes that name and handle.
7. A companion follows its owner: its row is keyed by the owner's record,
   so a re-summon, or a summon on the owner's new unit id, is the same row,
   and it leaves the list with its owner.

What is per unit id and not merged in the fight a member comes back to:
the timeline strip, the uptime spans and the pen/crit buffs on them, which
the trackers keep by the unit id the log names. From the next pull they
are keyed as for anyone else.

## Builds: gear, weapon types, armor weights, mundus and food

### src/player_build.py

*[src/player_build.py:1](../src/player_build.py#L1)*

Player builds: the gear, mundus stone and food a player started a fight with
(engine side, no Qt).

The encounter log writes one PLAYER_INFO line per group member as combat
starts. Besides the two ability bars it lists the player's long-term effects
(passives, set auras, the mundus boon, food) and one entry per equipped item:

```
    slot, id, isCP, level, trait, displayQuality, setId,
    enchantType, isEnchantCP, enchantLevel, enchantQuality
```

```
    [MAIN_HAND,133257,T,16,WEAPON_CHARGED,LEGENDARY,361,POISONED_WEAPON,T,16,LEGENDARY]
```

What 4,279 such lines from 32 logs of October 2026 show:

- Seventeen slot names occur. An empty slot is left out of the list, so a
  two-handed weapon is a main hand with no off hand beside it. COSTUME is
  cosmetic and skipped here.
- A slotted poison (POISON, BACKUP_POISON) is an item id and a quality. Its
  name comes from data/items/poisons_en.json, built by
  scripts/generate_poison_names.py.
- A mythic item is logged as LEGENDARY; only its set's LibSets type says it
  is mythic.
- The line is written once per fight, so a build is the one the player
  pulled with. Item names, weapon types and armor weights are not logged.

build_fields turns a player's line into the 'gear', 'mundus' and 'food' keys
of their fight-entry dict. The label functions name the log's values for
display; a value they do not know is shown in a readable form of itself.

Two things the log leaves out are looked up by item id in tables built from
UESP's item database. armor_weight says whether an armor piece is light,
medium or heavy (data/items/armor_weights.json, built by
scripts/generate_armor_weights.py). weapon_type says what a weapon or shield
is, an inferno staff or a dagger (data/items/weapon_types.json, built by
scripts/generate_weapon_types.py); has_restoration_staff puts the role
heuristic's question to it.

### scripts/generate_weapon_types.py

*[scripts/generate_weapon_types.py:1](../scripts/generate_weapon_types.py#L1)*

Generate data/items/weapon_types.json: the item ids of every weapon and
shield, one sorted list per type, for the Type column of the build window's
gear grid and for the healer role's restoration staff check.

The encounter log gives a weapon as an item id and never names its type
([MAIN_HAND,133257,T,16,WEAPON_CHARGED,LEGENDARY,361,...]). UESP's item
database lists every weapon and shield with its type in one request (about
63,000 items, 2.5 MB). Each type's ids are kept here under the name the game
uses for the type (an inferno staff, a battle axe, a shield).

Checked against 20 logs of October 2026: all 174 weapon ids in them were in
UESP's list. A weapon from a set added to the game after this file was built
shows a dash in the build window until it is regenerated.

Run after an ESO update that adds gear (needs network access):
    python scripts/generate_weapon_types.py
A reply from UESP already saved to disk can be used instead of fetching it
again (UESP asks for sparing use of its export):
    python scripts/generate_weapon_types.py --from <saved reply>.json

### scripts/generate_armor_weights.py

*[scripts/generate_armor_weights.py:1](../scripts/generate_armor_weights.py#L1)*

Generate data/items/armor_weights.json: the item ids of every light, medium
and heavy armor piece, for the Weight column of the build window's gear grid.

The encounter log gives an armor piece as an item id and never says how heavy
it is ([HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,...]). UESP's item
database lists every armor item with its armor type in one request (about
60,000 items, 5 MB). The ones of armor type 1, 2 and 3 (light, medium and
heavy) are kept here as three sorted lists of ids. The rest of that export,
jewelry among it, has no weight.

Checked against 48 logs of April to October 2026: all 905 item ids in their
armor slots had a weight in UESP's list. A piece from a set added to
the game after this file was built shows no weight until it is regenerated.

Run after an ESO update that adds gear (needs network access):
    python scripts/generate_armor_weights.py

## Set names

### src/gear_set_database.py

*[src/gear_set_database.py:1](../src/gear_set_database.py#L1)*

Gear set database: set lookups over the generated LibSets data.

The data lives in gear_set_data.py, which scripts/generate_gear_data.py writes
from data/gear_sets/LibSets_SetData.xlsm. Nothing is parsed at runtime.

### scripts/generate_gear_data.py

*[scripts/generate_gear_data.py:1](../scripts/generate_gear_data.py#L1)*

Generate src/gear_set_data.py, the set table the app ships, from the LibSets
addon's workbook (data/gear_sets/LibSets_SetData.xlsm).

Design: the encounter log names a gear piece's set only by its set id
(PLAYER_INFO ... setId). LibSets, the addon the ESO community keeps for
exactly this mapping, publishes a workbook with every set's id, name, type
(crafted, trial, mythic, ...) and item ids; this script reads it at build
time with openpyxl and writes a Python module, so nothing is parsed at run
time and the workbook is not bundled. The CI build runs the script, so a
change here is what ships. Set names are the game's own (issue #79): the
installed client's English string table, committed as
data/client/set_names_en.json by scripts/check_client_names.py, names every
set, and the workbook's spelling differed for 26 of them on Update 51
("Perfect" for "Perfected", "Blood Spawn", three Cyrodiil sets one id out of
place). The workbook gives the set type, the one field the app reads from it
(the five-piece reading in esolog_tail.has_five_piece_bonus, the mythic one
in player_build.is_mythic_set), and the names of the template and "(OLD)"
rows the client lacks. A set the client has and the workbook does not yet is
included under its client name with no type, so it reads as a five-piece,
non-mythic set until the workbook catches up. ESO-Hub links for sets are
looked up by name (see src/ability_icons.py).

### scripts/check_client_names.py

*[scripts/check_client_names.py:1](../scripts/check_client_names.py#L1)*

Compare every name the app bundles by game id with the installed client's own
English text, and keep the committed snapshot of the client's set names.

Design (issue #79): the client's language file, gamedata\lang\en.lang in
depot\eso.mnf, holds the game's name for every set, ability and item, keyed
by id, and it is right on patch day. It holds no structure: not which items
are poisons, not a set's type or bonuses, not an ability's skill line. So the
external sources (the LibSets workbook, UESP, LibFoodDrinkBuff) stay for
structure, and this script checks their names against the client:

  table      Index      what is checked against it
  38727365   set id     src/gear_set_data.py, the set ids named in
                        src/build_issues.py, data/sets/offense.json, and the
                        names data/esohub/sets_en.json is keyed by
  198758357  ability    data/skills/class_passives.json (a mastery's effect
                        by the buff it grants, which is the effect's own
                        name), data/skills/weapon_skill_lines.json, and the
                        skill id lists in src/build_issues.py against their
                        name lists
  242841733  item id    data/items/poisons_en.json (the client writes a tiered
                        poison without its numeral, as the table does)

Item names carry grammar markers ("battle axe^n"); they are cut at the caret
before comparing. The code lists are read with ast, so nothing in src/ is
imported. Food and drink buffs are not checked: data/buffs/food_drink.json
holds ids and kinds only, no names.

Two kinds of finding. A name that differs from the client's, or a name the
client does not have at all, is a difference and makes the run exit 1. An id
the client has no name for is counted, not failed: UESP's tables keep the
rank II to IV ids that skills had before Update 34, which the client no
longer names (432 in weapon_skill_lines.json and 39 in build_issues.py's
skill lists on Update 51), and the LibSets workbook keeps template and
"(OLD)" rows (11). They are harmless in a lookup table, and failing on them
would make the check fail for good. The set lists are stricter: a set id in
build_issues.py or offense.json that the client does not name is a
difference, since every set there was chosen by hand.

Set names are also written to data/client/set_names_en.json with --write-sets.
scripts/generate_gear_data.py takes its set names from that snapshot (CI has
no game client, so the client's names have to be committed) and only the set
type from the LibSets workbook. Refresh it after every ESO update:

```
    python scripts/check_client_names.py --write-sets
```

The run extracts en.lang into a temporary folder with UESP's EsoExtractData
(about 20 s, read-only on the game folder; see scripts/extract_ability_icons.py
for how the extractor and the client are found), or reads an extracted
en.lang.csv given with --lang-csv. Then rerun scripts/generate_gear_data.py,
which reports the sets the snapshot added.

## Set buffs: which set a Major or Minor buff came from

### scripts/generate_set_buffs.py

*[scripts/generate_set_buffs.py:1](../scripts/generate_set_buffs.py#L1)*

Generate data/sets/set_buffs.json: the Major and Minor buffs a set's bonus
grants, by the ability id the encounter log writes for them, so the uptime
line can name the set behind a "Major Slayer" or a "Major Courage" (issue
#79, decision 5).

The log names a buff and never the set it came from, and the game's files
hold no link between the two. UESP's mined skills were the first plan:
findSetBonusSkills.php writes a set's name into minedSkills.setName by
matching the bonus text against ability descriptions. Checked on 2026-10-31
against 395 split logs, that column ties each set to the effect named after
the set ("Pillager's Profit", 184 of 216 sets worn), which the uptime line
already shows under the set's name, and misses the generic buffs: of 58
Major or Minor buffs the logs tie to one set, one was in UESP's table
(Roaring Opportunist got 135920, while its Major Slayer is 93109 and
135923). A generic buff's description never matches a bonus's text.

So this script reads split logs instead. Most sources write a Major or
Minor buff under an id of their own: Roaring Opportunist's Major Slayer is
135923, War Machine's 93442, Master Architect's 93120. Some ids are shared:
the wearers of all three also write 93109 (in 96%, 91% and 91% of their
sessions). Only an id that one set writes can name it. Per log session and player it
takes the sets the player had active (``piece_counts``, a perfected set and
its base counted together, as the game counts them) and every effect id the
player was the source of (EFFECT_CHANGED). A buff id is tied to a set when
all of these hold:

1. Its name ("Major Courage") is in that set's bonus text
   (data/sets/bonuses_en.json), on a bonus whose pieces the player wears.
   This drops the buffs that only ride along with what is worn beside the
   set: Jorvuld's Guidance wearers source Roaring Opportunist's Major Slayer
   in 86% of sessions, because the two are worn together.
2. At least WEARER_SHARE of the sessions wearing the set source it.
3. At most OTHER_SHARE of the sessions wearing no set that names the buff
   source it, so an id that something else writes too is not taken:
   Mender's Ward wearers source Major Vitality 61713 in 95% of sessions, but
   so do 3.8% of everyone else; the set's own 113653 is sourced by no one
   else. Every link that reads right sat at 0.7% or below. Leaving out every
   set that names the buff lets two sets share a buff name with their own
   ids (Spell Power Cure's Major Courage 66902, Olorime's 109994).
4. At least MIN_SESSIONS sessions wear the set.

An id that passes for two sets names neither and is left out (printed, not
written).

It knows only sets someone in the logs wore MIN_SESSIONS times, and reads
the bonus text of the bundled snapshot. Byte-identical copies of one split
(issue #85) are read once. The output holds ids and the game's names only,
nothing about the players.

Run after a patch, or when the logs hold more sets, then review the printed
table before committing the file:
    python scripts/generate_set_buffs.py                    # the app's split folder
    python scripts/generate_set_buffs.py --dir D:/esologs/splits

## Solo dungeons: the run's Misfortunes

### src/misfortunes.py

*[src/misfortunes.py:1](../src/misfortunes.py#L1)*

The Misfortunes a solo dungeon run was started with (engine side, no Qt).
Issue #70.

The solo dungeons of October 2026 (pen_crit.SOLO_DUNGEON_ZONES: March of
Sacrifices 1592, Moon Hunter Keep 1593) let the player pick Misfortunes at
the door, each one making the run harder. The log writes each picked
Misfortune as a DEBUFF on the player, gained at the door and never faded,
and every PLAYER_INFO line of the run lists its id among the player's
long-term effects (the 2026-10-26 solo Moon Hunter Keep run: six lines, six
hits for each of the three), so the logging player's long_term_effects at
BEGIN_COMBAT, the list the food rule and the passives already read, carry
them at every pull and no new parsing is needed.

Known ids: Warm Welcome 269749, Revoke of Respite 269803 and Alleviating
Assault 269792 from that run; Weary Submission 269799 and Pulled Punches
269804 from the 2026-10-25 solo March of Sacrifices run, which picked those
two and Warm Welcome (each of its PLAYER_INFO lines lists all three). The
texts are the game's own descriptions (the client's en.lang, table
132143172 by ability id), shortened; where the game leaves the figure to a
placeholder, the figure is the hyperioxes.com guide's (Revoke of Respite's
50%), the log's (Alleviating Assault's heals: 5,100 on trash, 8,160 on a
boss) or left out (Weary Submission's). Every ABILITY_INFO icon of these
effects starts with ``debuff_solodungeon_`` (``..._monster_warmwelcome``,
``..._player_pulledpunches``, ``..._player_wearywarriorssubmission``), so a
long-term effect whose icon stem starts with that is named by its logged
name, with no text, until its id goes in the table.

The engine stores them on the fight entry (entry.misfortunes, a list of
[name, text]), in the table's order whatever order the log lists them in
(it differed between pulls of one run): None outside a solo dungeon, so the
fight pane shows nothing there and an entry built before this renders as
before; [] in a solo dungeon run without Misfortunes, which the pane shows
as ``Misfortunes: none``.

## Penetration and critical damage: the spreadsheet from the log

### src/pen_crit.py

*[src/pen_crit.py:1](../src/pen_crit.py#L1)*

Penetration and critical damage: where each player's and the group's come
from, against the caps (issue #37). Engine side, no Qt.

Design. Two stats decide how much of a hit reaches a trial boss: Offensive
Penetration, which cancels the target's resistance (18,200 on the bosses
and mobs of dungeons, trials and arenas, 9,100 overland; a point past the
cap does nothing), and Critical Damage, 50% to begin with and capped at
125% (155% with the Nightblade mastery Above and Beyond). Raid leads check
both with a spreadsheet of checkboxes (LunaCairu's PenCrit Calc, and the
calculators at hyperioxes.com that skinnycheeks.gg recommends): every
source has a fixed value and they add up. This module does the sum from
the log, in two parts.

The player's own part is read from PLAYER_INFO: the passives in the
long-term list by id (Concentration 939 per light piece, Dexterity 2% per
medium piece, Hemorrhage 10%, Piercing Spear 12%, Fated Fortune 12%,
Advanced Species 5% per Animal Companions ability on the bar, Splintered
Secrets 1,240 per Herald of the Tome ability, Dismember 3,271, Feline
Ambush 12%, Hunter's Eye 950, Twin Blade and Blunt 6% per axe and 1,487
per mace, Heavy Weapons 12% for a battle axe and 2,974 for a maul, Blessing
at the Peak 10%, Above and Beyond 25%; every value is the game's own text
on UESP's skill tree, and a lower rank's id carries that rank's value), the
mundus boon with the Divines pieces that scale it (the Lover 2,744 and the
Shadow 11%, each piece of gold Divines adding 9.085%, rounded down as the
spreadsheet rounds), the sets at their worn piece counts
(data/sets/offense.json, generated from UESP's set texts by
scripts/generate_set_offense.py: "Adds 1487 Offensive Penetration",
Velothi's 1,650, Order's Wrath's 8%, Malacath's -50%), a Sharpened weapon,
and the weapon kinds and armor weights from the bundled item tables. A
value that depends on the bar (weapons, slotted abilities, set pieces with
a two-handed weapon) is kept per bar, so a total reads "14,095 / 11,121"
when the bars differ. A conditional bonus (Sul-Xan's 12% after a soul,
Stuhn's 5,312 against Off Balance, Dismember's 3,271 while a Grave Lord
ability is active) is listed with its condition and never added. A set
that gives a buff at all times (Medusa's or Velothi's Minor Force) is
credited with that buff for the whole fight: the game writes neither a
GAINED line nor a PLAYER_INFO entry for a mythic's permanent buff (four
trial logs: Velothi's aura 193447 on 917 PLAYER_INFO rows, Minor Force
61746 on none), so measuring it would read the other Minor Force sources
alone. A set that gives a buff under a condition (Tzogvin's at ten stacks)
is named as a possible source, and the buff measured like any other.

The group's part is what was on the target and on the player during the
fight, valued as Combat Metrics values the same debuffs (its StatDebuffs
table in CombatMetrics.lua): Major Breach 5,948, Minor Breach 2,974,
Crusher 2,108 (1,622 for the gold glyph, times 1.3 Infused, times 1.45
Torug's Pact, read from the caster's weapon), Roar of Alkosh 6,000, Crimson
Oath's Rive 3,541, Runic Sunder 2,200, Crystal Weapon 1,000, Tremorscale
2,640; Minor Brittle 10%, Major Brittle 20%, each Elemental Weakness 5%;
Major Force 20%, Minor Force 10%, Lucent Echoes 11%, Fated Fortune's 7 s
proc 12%. Combat Metrics adds those to the player's stat at every hit and
buckets the damage by the result, then shows the damage-weighted average
with each hit capped, the maximum, and the share of damage dealt over the
cap. The log has every hit with its time and target and every effect's
span on every unit, so the same is done here per second: for each second
and each target hit, the debuffs on that target (a fraction of the second
counts as that fraction) and the buffs on the player, times the damage
dealt that second, kept as a histogram of (penetration value, status
effects on the target, damage), so a reader can add any static part and
any cap and get the capped average (the effective figure) and the share
over the cap. In a fight with a boss only the bosses are measured; in a
trash fight every hostile hit.

Not in the log, and the reason the renderer adds "assumed" rows from the
Settings rather than this module: the Champion Point stars that only change
a stat. Four trial logs (2,292 PLAYER_INFO rows) never list Piercing (700
penetration), Fighting Finesse (8%), Deadly Aim or Master-at-Arms, and show
Backstabber (10% while flanking) only as 35 self-applied GAINED lines;
stars that are effects (Exploiter, Bulwark, Reaving Blows) are listed, so
the game simply has no effect for a stat star. Force of Nature (660
penetration per unique status effect on the target in Combat Metrics'
table, the star it calls wrathCP) is the same, but the status effects on
the target are logged (9,522 GAINED lines in one Sunspire log), so when the
reader assumes the star its value is the measured count of effects times
660. The Settings toggles only change the rendering, so a change needs no
engine restart and a fight entry holds nothing but what the log said.

What else the survey showed: Divines is the trait on 13,620 armor pieces
and no weapon of 2,292 builds is Sharpened; every Crusher glyph (302
weapons) is gold at CP 160; Fated Fortune's proc fired 2,374 times, so its
real uptime is measured, not assumed; the trial dummy applies the trial's
own debuffs to itself (Crusher 120007, Alkosh 120018, Breach 120010 and
120019, Minor Brittle, Elemental Catalyst), which is how a parse at a
dummy is known to be against 18,200 resistance in a house zone whose
difficulty reads NONE. It applies them once, as it spawns, and keeps them,
so a session begun after the spawn has no line for them and the log alone
would read the player's own penetration against an overland cap; a fight
against a unit named "Target Iron Atronach, Trial" therefore credits them
for the whole fight (TRIAL_DUMMY_DEBUFFS), as Combat Metrics reads them
from the game at the pull. Checked against a Combat Metrics report of a
25 s parse (2026-10-24): own penetration 3,126 (one light piece, Aerie's
Cry's two pieces, Piercing) plus the dummy's 17,030 is its maximum of
20,156 exactly, damage and dps agreed within 0.5%, and the ability table
row for row.

Solo dungeons and the Armour row (issue #55). The solo dungeons of October
2026 are the group dungeons' layouts and bosses at a zone id of their own,
with the dungeon's name and difficulty NONE on the ZONE_CHANGED line (the
solo March of Sacrifices is zone 1592, the group dungeon 1055, logged on
2026-10-25 and 2026-09-22; the solo Moon Hunter Keep is 1593, the group
dungeon 1052, logged on 2026-10-26 and 2026-06-11); nothing else in the log
says solo. The Misfortunes picked at the door were absent from the March of
Sacrifices log and present in the Moon Hunter Keep one: each is a DEBUFF the
player carries from the door to the end (Warm Welcome 269749, Revoke of
Respite 269803, Alleviating Assault 269792), every enemy spawns with a
"Misfortune Level Three" BUFF (267457 and 267460 on trash, 272449 and 272450
on the boss), and Alleviating Assault works as a HEAL event from the player
to the enemy hit, 5,100 on trash and 8,160 on a boss at most every 3 s, so
the player's heal events include heals on hostile units. None of the three
touches armour (double enemy damage, half the healing received, the heal),
so the figures here hold under any Misfortune; the boss's logged health,
2,157,795 for Jailer Melitus, is the guide's figure for three Misfortunes,
which is why the guide's armour figures are trusted. The solo bosses have
monster ids of their own (Jailer Melitus 132991, where the group dungeon's
bosses are 83219 to 83223), so a per-boss table could not reuse the group
ids. Read by difficulty alone a solo dungeon is overland, 9,100, so
SOLO_DUNGEON_ZONES names the ids and zone_kind reads it first; the figures
are the hyperioxes.com Moon Hunter Keep guide's: trash 18,200 like any
instance, bosses 27,300, the final boss 36,400, and the game's cap of 25,000
on an enemy's armour, above which penetration changes nothing until the
debuffs bring the armour under. Every boss is taken at 27,300 (the
maintainer's choice, 2026-10-26); the labels say the final boss has more.
The buff timeline's Armour row (armour_row) draws the target's armour less
the group's armour debuffs on it, second by second, from a series
fight_fields keeps on the target the group damaged most: spans of equal
debuff sum and names, the sum rather than the remainder so the Settings' cap
override can restate the estimate. The remainder is averaged over time for
the label, where the build window's effective figures weigh each second by
the damage dealt; the two are different questions (how long the armour was
down, and how much of the damage met it down).

The row's window (issue #64). A fight runs from BEGIN_COMBAT to
END_COMBAT, and the target the row follows need not be there for all of
it: the combat that ends at Xoryn starts at the Defense Prisms and runs
through Baron Rize and the gauntlet, and over 33 Lucent Citadel logs
Xoryn was added a median 435 s into a median 549 s fight; Nahviintaas
lands as a new unit id each time and is hit for about 20 s per landing;
a trash pack's mob lives for a third of its fight. Drawn over the whole
fight the row stood full for the time before the boss, the label read
14,500 to 16,000 left on Xoryn pulls and the click said 77 to 83% without
a debuff, when over the time the group was hitting him it was 2,565 to
5,978 and 0 to 1%. So the row is measured over the seconds the group
damaged its target (the hits the engine buckets per target per second,
_armour_window), a gap of up to ARMOUR_GAP_S seconds between hits bridged
and a longer one left blank (a dragon in the air), and nothing is drawn
before the first hit or after the last; the label's average, the lowest
point and the no-debuff share are over the drawn time, the click summary
names the window, and the damage-weighted figure (weighted_pen) sits
beside it so the row and the build window can be seen to agree. A boss in
several unit ids shares the row: every boss-flagged unit of the row
target's name, each second read on the one hit hardest that second
(_armour_series). Among a pack's equal-damage mobs (each takes its
health) the row follows the one hit over the longest window, then the
first hit (_row_target), where the largest unit id, the last spawned, was
taken before. The boss-scoped uptime rows above it still measure over the
whole fight (issue #64 lists that choice). The engine's boss_window was no
window for the row while the Prisms and the Baron carried the game's boss
flag into the fight's bosses; since issue #67 they are adds (boss_units),
so the row's target on a Xoryn pull is Xoryn alone either way.

The pack reading (issue #66). Windowed to its target, the row left the
first seven minutes of a Xoryn pull blank, where the group hit 245 to 279
units and the armour debuffs on them mattered as much, and on a trash
fight it followed one mob of a pack of twenty. The question the row could
not answer was what armour the group's damage was going into, second by
second, whatever it was hitting. So fight_fields now keeps the armour
debuffs' coverage on every hostile the group hit, not only the bosses (the
crit debuffs, the status effects, the debuff rows and the histograms stay
the targets'), and _pack_series reads each second on the hostile hit
hardest that second, ties to a boss among them, then to the unit read the
second before so a pack of equals does not flicker, then to the lowest
unit id; a gap of up to ARMOUR_GAP_S seconds carries the last unit's
reading, as the boss row bridges its own, except across the boss row's
own time. In a boss fight the reading
fills the row outside the boss's window, drawn paler so the two are told
apart, the hover naming the unit of the moment and the label keeping the
boss's figure (the pack reading is lower, since adds carry fewer debuffs
for less time, and a second spent on an add while the boss stands
debuffed reads on the add: a different question, not a better answer to
the boss's); in a fight without a boss it is the row, and the label is its
average. The estimate is held at one value per row (a solo dungeon's boss
at 27,300 against its trash at 18,200 would otherwise change the bar's
scale mid-row), and an interval read on a unit whose armour differs
carries that figure for the hover. From the #64 replays: a Xoryn pull
read this way averages 3,200 to 6,200 left with 7 to 15% of the damaged
seconds undebuffed over 130 to 210 switches of unit, Xoryn himself the
hardest-hit unit in 19 to 25% of them; a trash fight 2,700 to 10,400 left
where the one-mob row read 10,317 to 16,800; a clean boss fight's pack
seconds are few and read lower than the boss (Count Ryelaz 1,053 against
6,348).

### scripts/generate_set_offense.py

*[scripts/generate_set_offense.py:1](../scripts/generate_set_offense.py#L1)*

Generate data/sets/offense.json: what each gear set does for penetration and
critical damage, by the set id the encounter log writes, for the build
window's Penetration and Critical damage sections (pen_crit.py, issue #37).

The log gives an equipped item's set id and nothing about the set's bonuses.
UESP's set summary lists every set with its bonus texts, one request (714
sets, 0.8 MB); the texts are the game's own. This script keeps, per set and
per piece count, the lines that matter here:

- a flat Offensive Penetration line ("(2 items) Adds 34-1487 Offensive
  Penetration": the second figure is the value at CP 160), kept as 'pen';
- a flat Critical Damage line ("(5 items) Increases your Critical Damage and
  Critical Healing by 8%"), kept as 'crit' (Malacath's "decreases ... by 50%"
  as -50); a sentence after it that doubles or adds to the bonus under a
  condition is kept as 'note';
- a buff the wearer always has ("Gain Minor Force at all times", Oakensoul's
  list), kept under 'gives': the game writes no GAINED line and no PLAYER_INFO
  entry for such a buff (four trial logs: Velothi's aura 193447 is listed on
  917 rows, Minor Force 61746 on none), so the wearer is credited with it for
  the whole fight; a buff the wearer gets under a condition ("After dealing
  direct damage, you gain Minor Force", Tzogvin's at ten stacks) is kept
  under 'gives_when' with the text as 'when', named but measured from the
  log like any other buff;
- a conditional bonus to the wearer ("When you deal damage to an enemy who is
  Off Balance, your Offensive Penetration is increased by 123-5312 for 10
  seconds"), kept as 'pen_up_to' or 'crit_up_to' with the text as 'when',
  shown but never added to a total;
- a debuff or group buff the set puts on others (Roar of Alkosh, Crimson
  Oath's Rive and Tremorscale reducing Armor or Resistance, Night Mother's
  Gaze's Major Breach, Nunatak's Major Brittle, Elemental Catalyst's
  weaknesses, Lucent Echoes, Saxhleel Champion's Major Force), kept under
  'provides' so a group row can name the wearer's set as its source.

Of the 714 sets on the Update 51 export, 65 carry a flat 1487 line, seven
arena weapons 1190, Spriggan's Thorns and Spinner's Garments 3460; 72 sets
mention Offensive Penetration and 52 Critical Damage in some form. The
texts are classified by sentence: a first sentence that is nothing but
"Adds N Offensive Penetration" or "Increases your Critical Damage ... by N%"
is flat; a sentence that opens with a condition (When, While, After,
Whenever, Dealing, Touching, On, If, Each, Every) is conditional. A set the
export does not describe, or a bonus worded in a way this script does not
read, is simply absent: the section then shows nothing for it.

The same reply also gives data/sets/bonuses_en.json (issue #79): every set's
bonus lines as the game words them, by set id, for a set's description in the
app. The game's client files do not hold this text (the client assembles a
set's tooltip from server data at run time), so UESP's copy, which its
uespLog addon reads from the game, is the source; it is bundled so nothing
is asked of UESP at run time, and it carries UESP's CC-BY-SA 2.5 attribution
like this file. Each line keeps its piece count, whether it is a perfected
bonus ("(2 perfected items)"), and its text with runs of spaces closed up;
the figures stay as written ("Adds 15-657 Critical Chance": the second value
is the one at Champion Point 160). Set names in it are UESP's; the app names
a set from its own table by id.

Run after an ESO update that adds or changes sets (one request to UESP; UESP
asks heavy users to go lightly, so do not loop it):
    python scripts/generate_set_offense.py
or from a reply already on disk, such as the one the esobuild export keeps:
    python scripts/generate_set_offense.py --from build/esobuild-assets/sources/set_summary.json

### _pen_crit_html

*[src/gui/build_render.py:691](../src/gui/build_render.py#L691)*

The Penetration and Critical damage sections (pen_crit): the player's
own rows and the assumed Champion Point rows, the fight's debuffs on
the boss (uptime, value, casters) and the buffs on the player, then the
totals: own, with every debuff at full uptime, and effective (each
second of the player's damage capped, as Combat Metrics caps each
hit), against the cap. The effective line is the conclusion, so it
sits in a framed row of its own with a 3 px bar at its left edge
(issue #143): a box rather than an underline, because the app's one
underline is the hover cue on a clickable name or figure; a table
cell rather than a <p>, because Qt rich text draws borders on cells
only; the frame is the build card's hairline, and the bar in the muted
colour gives the cue the contrast a hairline lacks (about 6:1 against
the page in either theme), so it is seen without colour vision. The
muted 'no damage measured' line stays in the plain row: a frame round
an absence would draw the eye to nothing.

## Section headings: the one element Qt rich text draws a rule on

### _heading_html

*[src/gui/build_render.py:524](../src/gui/build_render.py#L524)*

A section heading with its rule, as a one-cell table head: Qt rich
text draws borders on table cells and never on a <p>, so the Damage
dealt and Resources headings, <p> elements with a border-bottom until
issue #143, had no rule while the gear grid and the Penetration and
Critical damage heads (the same form inside their tables) had one; the
damage taken window's section titles (taken_render) take this form too.
*extra* follows the title (a link, a caption); the anchor, when there
is one, goes first, where scrollToAnchor finds it: Qt hangs an empty
named anchor on the next text it lays out, the heading cell.

## Possible build issues: what the log proves about a build

### src/build_issues.py

*[src/build_issues.py:1](../src/build_issues.py#L1)*

Possible build issues: what a player's logged build and their fights say
about likely mistakes, shown behind an (i) on their row of the fight pane
and repeated in the build window (engine side, no Qt). Issue #16.

Design: a finding is something the log proves about the build the player
pulled with, and every finding carries the rule it comes from in plain
words, so the reader learns the rule from the finding. The rules are the
maintainer's (decided 2026-10-24), checked against 83 split logs of
September and October 2026 (1,615 fights, 13,998 player-fights, 393
characters); with them, 17% of the characters seen would carry a note. Per
rule, player-fights / distinct characters in that survey:

- **Nirnhoned on an off-hand weapon** (429 / 17, every one a DPS; the
  classic form is a Precise main hand beside a Nirnhoned off hand). The
  trait raises the damage of the weapon it is on, and UESP's Dual Wield
  page gives Dual Wield Expert as Weapon and Spell Damage equal to 6% of
  the off-hand weapon's damage, so an off-hand Nirnhoned is worth about a
  sixteenth of a main-hand one. A shield's Nirnhoned (ARMOR_NIRNHONED, 4
  tank fights) is the armor trait and is not reported.
- **The same glyph on both weapons of a bar** (421 / 22: Absorb Stamina,
  Berserker, Poisoned, Weakening, Absorb Health), whatever the glyph.
  Identical glyphs share one cooldown: measured on every dual-wield front
  bar of those logs, the same glyph from one player never fired twice
  within 4.0 s whether the bar carried it once or twice, and the proc rate
  was the same (Absorb Stamina 6.0 against 6.5 per minute, Poisoned 6.2
  against 7.2, Berserker 9 s gaps either way), so the second glyph never
  fires. The same glyph on both bars (112 / 7: a tank's Hardening or
  Crusher on both bars, Berserker on both bars of a DPS) is not reported:
  with a cooldown twice the buff's duration, a copy on the other bar fills
  the gap after a swap.
- **Two or more heavy armor pieces on a damage dealer** (218 / 9; five or
  more 103 / 4). Heavy Armor's passives add nothing to damage. One heavy
  piece is the usual Undaunted Mettle split (618 of 8,766 DPS
  player-fights) and is not reported. The role is the app's heuristic
  (infer_player_role), which reads the dominant resource, so a
  health-stacked DPS reads as a tank and a stamina-heavy fake tank as a
  DPS: 363 "tank" player-fights wore no heavy at all. The rule therefore
  asks for the DPS role and that the player has not taunted this session.
- **A weapon skill on a bar holding another weapon** (235 / 14 with the
  bar in use; Stampede left on a staff back bar is the commonest). The
  skill's line comes from the bundled weapon_skill_lines.json (UESP's
  player skill table, scripts/generate_weapon_skill_lines.py), or from the
  grimoire a scribed skill's icon names; the bar's line from the weapon
  types of its two slots. The back bar under Oakensoul Ring (set 658; 55
  more player-fights) is skipped, since the ring forbids swapping, and a
  bar whose weapon the bundled table does not know is not judged.
- **Elemental Drain** (124 / 5: tanks 69, healers 50, DPS 5, all in
  trials), per player, the maintainer's decision. The finding states both
  morphs: Drain (ids 39095, 41559, 41563, 41567) applies Major Breach and
  Minor Magickasteal; Elemental Susceptibility applies Major Breach and
  the Burning, Chilled and Concussion status effects every 7.5 seconds.
- **A proc set that never fires** (Roar of Alkosh 12 / 3 and Roaring
  Opportunist 19 / 8 at the 60 s floor). Judged per logging session, not
  per fight: in fights of 90 s or more Alkosh fired for 112 of 117
  wearer-fights, yet 30 of 219 wearer-fights under 30 s had no proc though
  the set worked. So the tracker counts, per player and set, the fights of
  a minute or more the set was worn in, and whether the set's effect was
  ever sourced by the player in any fight of the session; one fire clears
  the finding for the session. In those logs Alkosh wearers sourced Roar
  of Alkosh as 76667 and 75751, Roaring Opportunist wearers Major Slayer as
  93109 and 135923 (the other Major Slayer ids, 93120, 93442 and 177886,
  came from other sets). The one wearer who never fired Alkosh never used a
  synergy through a whole Halls of Fabrication run, 240 s fight included.
- **Huntsman's Warmask that never fires** (issue #47, the same session
  rule, the mythic's one piece being the set): its Mark of Hircine
  (252048, GAINED with the wearer as source) is placed by a bash or a fully
  charged heavy attack, and a wearer who places none has a mythic doing
  nothing. The issue was filed the other way round, as a flag on a wearer
  who bashes (a bash can move the mark from the boss to an add, where it
  halves the wearer's damage to everything else for up to a minute), and
  the survey over the same 91 logs of September and October 2026 decided
  it: 29 of the 30 wearers bash, in 96% of their fights of a minute or
  more (393 of 515 wearer-fights had a damaging bash, a median 3 a fight),
  1,292 of the 1,401 marks followed a bash and 55 a heavy attack, and in
  132 of 396 boss wearer-fights (18 of 29 wearers) the mark sat on a unit
  that is not a boss for a median 11% of the fight. Half of those units
  were Sunspire's Eternal Servants and Kyne's Aegis's Lieutenant Njordal,
  which a group kills on purpose, so a flag on bashing would have been a
  permanent note on every wearer and a wrong verdict a third of the time;
  the maintainer chose the inverse on 2026-10-26, and the mark, which a
  heavy attack places too, is the fact the log carries (his own Aetherian
  Archive session marked by heavy attacks alone). In those logs no
  wearer-session with a fight of a minute or more was without a mark, so
  the rule is quiet until a wearer who never triggers the set turns up.
- **A group buff set complete on one bar only** (80 / 3), for Pearlescent
  Ward, Xoryn's Masterpiece and Lucent Echoes, whose five-piece bonus is a
  buff for the whole group that holds only while five pieces are active.
  The rule cannot be general: 38% of all five-piece wearings in the survey
  were one-bar, which is normal for proc sets and front-bar damage sets.
  Piece counts per bar come from player_build.piece_counts (a two-hander
  counts as two). A build without a back-bar weapon, or wearing Oakensoul
  Ring, is not reported.
- **A tank with no taunt or pull** (95 / 3 with the gates below; added the
  same day at the maintainer's request). The health pool alone is not a
  tank: of 3,154 health-dominant player-fights in the same logs, 762 had
  neither a taunt nor a pull on their bars and never taunted, but 519 of
  those wore at most one heavy piece and were damage dealers or healers
  whose health happened to be their largest pool, and 40 more taunted
  through the Tormentor set's charges and chains. Real tanks (a taunt
  slotted and taunting) dealt a median 0.10 of an equal share of the
  group's damage, 0.22 at the 90th percentile and 0.27 at the 95th. So
  besides the role, the bars and the session's taunts the rule asks for
  tank gear (a shield, an ice staff or five heavy pieces), at most half an
  equal share of the damage, and no healer sign (a restoration staff on a
  bar, or more healing to others than damage dealt: a heavy-armor healer in
  Sunspire would otherwise be flagged). Taunt and pull ids are UESP's for
  every rank plus the ids the bars carried in the logs; names count too,
  since the game now calls the chains Chains of Flame, Dominance and
  Devastation and the Arcanist's rank ids differ from UESP's. A scribed
  skill taunts or pulls by its focus script, Taunt or Pull, which names it
  Goading or Leashing. Destructive Clench taunts only with an ice staff in
  hand, when it is cast as Frost Clench.
- **No food or drink at combat start** (issue #54; 535 player-fights, 3.6%,
  and 39 named characters in 91 split logs of September and October 2026
  with 1,681 fights and 14,895 player-fights, the maintainer's own character
  the most frequent case, in casual content). The long-term effects the
  PLAYER_INFO line lists are matched against the bundled LibFoodDrinkBuff
  table (player_build.food_buff, data/buffs/food_drink.json, 92 ids), the
  way the build window's Food line is; a player with no match fought
  without a consumable's maximum stats or recovery. The check is by id, not
  icon: the foods in those logs carried 18 different icon stems
  (crafting_cooking_, crafting_meat_, plate_of_sugarskulls, event_jester_,
  store_magickafood_, crafting_poisonmaking_reagent_troll_fat...), unlike
  mundus boons, so a consumable newer than the table reads as none, which
  the finding says. No player without a match carried an effect with a
  consumable-looking icon, so the gap was a missing meal every time. A meal
  eaten during the fight is noted with its time. A player whose food was
  listed at combat start and faded during the fight, with nothing eaten
  before the end, gets the second form, "{food} ran out 2m10 into the
  fight" (13 player-fights in those logs): the engine keeps each player's
  food ids as combat starts and follows their GAINED and FADED lines
  (CombatEncounter.note_food), and a drink logged as several effects
  (Witchmother's Potent Brew) is only out when all of them have faded.
  Judged per fight with no floor: the fact is about combat start, and the
  cue clears once the player eats. Not judged when the table cannot be
  loaded (the player dict then has no 'food' key).
- **No Minor Slayer in a veteran trial group** (issue #62; 787 of 10,572
  veteran DPS player-fights, 7%, and 29 of 225 characters, in the 84 newest
  trial split logs of May to October 2026 with 1,581 fights and 18,684
  player-fights). Minor Slayer is 5% more damage to dungeon, trial and
  arena monsters. Every trial's sets grant it at three pieces and Oakensoul
  Ring grants it outright: SLAYER_SETS holds the
  38 three-piece sets by game set id, from UESP's set summary (the
  esobuild asset export's set_summary.json, its gameId field), and the ring
  is OAKENSOUL_SET_ID. The maintainer's scope (2026-10-26): damage dealers
  only, since healers carried a source in 47% of their player-fights and
  tanks in 13%; large groups only (five or more players,
  effect_rules.group_size_class, the class the uptime line's "expected
  large" reads); veteran difficulty only, since in the 113 normal-difficulty
  fights 46% of the DPS lacked one; and a listed set at three pieces on
  one bar is enough (1% of DPS player-fights: a body piece of Relequen with
  a back-bar staff). With the heavy-armor rule's never-taunted guard, for
  the same reason. Judged from the gear, not the effect: the set bonus is
  ability 147226 in the PLAYER_INFO effects (listed for 10,935 of the
  10,936 wearers with three pieces on both bars), but the ring's is not
  (1,110 of 1,349 ring wearers listed no 147226; the 45596 "Slayer" they
  carry is the Fighters Guild passive). A PLAYER_INFO with an empty gear
  list (130 player-fights, 58 of them listing 147226: the empty-equipped-set
  trap of issue #49) is not judged. Per fight, no floor: the gear at combat
  start is the fact, and a changed build clears it next fight. The builds
  without were Deadly Strike with Tide-Born Wildstalker or Spattering
  Disjunction, Azureblight Reaper with Corpseburster, Savage Werewolf with
  Order's Wrath. The finding is one sentence (issue #127 trimmed it): it
  once named the complete sets worn instead, which read as noise.

The lists a later rules text could lift out (the maintainer's separate
issue) are module data: GROUP_SETS, PROC_SETS, SLAYER_SETS,
ELEMENTAL_DRAIN_IDS, OAKENSOUL_SET_ID, the taunt and pull tables, the
weapon lines table. The checks themselves are code.

### BuildIssueTracker

*[src/build_issues.py:710](../src/build_issues.py#L710)*

The rules judged over a logging session rather than a fight: the
proc sets that never fire, and who has taunted (the heavy-armor rule's
guard). Keyed by the engine's per-session player key; a fight is keyed
by its start, so a fight the game cut in two and republished replaces
its own record instead of counting twice. reset() at BEGIN_LOG.

### scripts/generate_weapon_skill_lines.py

*[scripts/generate_weapon_skill_lines.py:1](../scripts/generate_weapon_skill_lines.py#L1)*

Generate data/skills/weapon_skill_lines.json: every active skill of the six
weapon skill lines (Two Handed, One Hand and Shield, Dual Wield, Bow,
Destruction Staff, Restoration Staff) by game ability id, with its line and
name, for the build-issue rule that spots a weapon skill slotted on a bar
holding another weapon (build_issues.py).

The encounter log lists a bar's skills by ability id and never says which
skill line a skill belongs to. UESP's player skill table does: one request
(about 4,400 rows, 2 MB) lists every player skill with its line, rank and
whether it is a passive. The rows kept here are the non-passive rows of
the six lines with a rank of 1 or more: every rank of every morph (the log
writes the id of the rank the player has: Stampede is 38788, 39797, 39802
or 39807), the scribed grimoire skills of those lines included (Elemental
Explosion is logged as 217228 and a dozen other ids, one per focus script).
Left out: the passives (never in a bar), the rank -1 rows, which are
internal effects such as Bash and Follow Up, and UESP's own rank ids for
crafted skills (20217228 for rank 2 of 217228), which no log ever carries.
605 ids on the Update 51 client.

Run after an ESO update that adds a weapon skill or a grimoire (one request
to UESP, which asks heavy users to go lightly, so do not loop it):
    python scripts/generate_weapon_skill_lines.py
or from a reply already on disk, such as the one the esobuild export keeps:
    python scripts/generate_weapon_skill_lines.py --from build/esobuild-assets/sources/player_skills.json

## Tracked effects: the uptime line as rules anyone can paste

### src/effect_rules.py

*[src/effect_rules.py:1](../src/effect_rules.py#L1)*

Tracked effects: rules anyone can paste, and the tracker they drive
(engine side, no Qt). Issue #10.

Design: every item on the uptime line is a rule. A rule names an effect by
its ability ids and asks for its uptime or its stack count on a chosen kind
of unit, in a plain text anyone can copy to others. One rule per line::

```
    # Name = ability ids... on <scope> [stacks | each | dots] [expected <sizes>]
    Major Courage = 109966 on group expected large
    Taunt         = 38254 on boss each expected small large
    Off-Balance   = 45902 62988 39077 34733 20806 130139 on boss
    Touch of Z'en = 126597 on boss dots
    Crux          = 184220 on self stacks
```

A rule matches any of its ids (an effect such as Off-Balance has one id
per skill that applies it). The scope says whose effects count: ``self``
is the player who writes the log, ``group`` any group member, ``pets`` a
group member's pet, ``boss`` an enemy the game flags as a boss, ``enemies``
any hostile. Three measurements: ``uptime`` (the default) is the share of
the fight the effect was on at least one unit in scope, the question "was
it up?"; ``stacks`` is the mean stack count while it was up, with the peak,
for effects that stack (Crux, Touch of Z'en, Arms of Relequen); ``each``
measures the effect on every unit of the scope separately, over the time
that unit was alive in the fight, and shows the mean of those shares, the
question "was each boss taunted?". ``each`` is the taunt's measure since
issue #9: a fight with two bosses averages them, and a boss killed before
the fight ends is measured to its death. The difference is not academic:
in 95 boss fights of twelve 2026 logs, the taunt's union to the fight's
end differed from its per-boss mean in 39, reading lower by up to 83
points where a boss died early and the fight ran on against its adds.

The uptime line's six group buffs (Major Courage, Major Force, Major
Slayer, Powerful Assault, Lucent Echoes, Pearlescent Ward) and the taunt
were tracked in code until 0.8.0; they are the first seven of
DEFAULT_RULES now, so anyone can rename, edit or delete them, and the
example picker holds them for whoever wants one back. As rules they read
the same, with two differences: a group buff is measured whatever the
group size (the code needed three players), and one that never appeared
in a fight read 0% rather than being left off the line (until 0.12, when
``expected`` decided that per group size; see below). Replaying the
twelve logs (376 fights) through both: the six buffs agreed in 690 of 745
readings; in the other 55 (46 of them Major Courage, the buff refreshed
most) the rule read higher, never lower, because the code ignored an
UPDATED refresh when it had missed the GAINED before it, though the buff
was up: a 12 s fight that read 7% reads 100%. The taunt agreed in 52 of 79
boss fights and read higher in 27 (lower in one, by 5 points): the code
kept its taunt spans in the encounter, which BEGIN_COMBAT replaces, so a
taunt already on the boss at the pull was lost until the tank's next
refresh (twelve fights, a 7.7 s fight reading 0% that reads 100%), and it
measured every boss from the fight's start whether or not it had arrived,
where ``each`` measures a unit over the time it was there.

Fights without a boss: trash packs are most fights (281 of the 376, with
up to 71 mobs hit). A ``boss`` rule has nothing to measure there, so it
measures every hostile the group fought instead, and both it and an
``enemies`` rule then say how many of the pack's mobs the effect reached,
``Alkosh:45% on 7 of 12 mobs`` (the pack is the mobs the group hit, plus
any a tracked effect was applied to). In those fights Off-Balance reached up to
27 of 32 mobs with 7 at once, Major Vulnerability 7 of 18, Minor Brittle
18 of 32, the taunt 20 of 32. In a boss fight nothing changes: the boss
rule reads the boss alone (its effect was on the adds too in about half
the boss fights, almost never on the adds alone).

Dead units: the game does not always write FADED for an effect on a unit
that dies or is removed. 124 of the 376 fights ended with a span still
open on a dead or removed mob, and such a span runs into every later fight
of the zone. The engine tells the tracker when a unit dies or is removed
(forget_unit) and when the zone changes (zone_changed), which ends those
spans there.

Seen or expected (issue #13): an item is shown, as a row of the timeline
strip and in the copied text, when its effect was on a unit in scope
during the fight, or when its rule is ``expected`` in the fight's group
size: ``solo`` (one player), ``small`` (two to four) or ``large`` (five or
more), counted from the players the engine lists for the fight;
``expected`` alone, or ``all``, is every size. An expected rule whose
effect never came reads 0% on an empty row, so a missing Major Courage in
a trial stands out; a rule that is neither seen nor expected is left off.
The survey behind the defaults (2026-10-10, every tenth split log by name
within 1.5 GB: 13 logs, 196 fights of 2026): of the fourteen default
items, the number reading 0 per fight averaged 13.0 in the three solo
fights, 10.0 in the 71 four-player fights and 5.9 in the 122 trial fights.
In the trial fights the six group buffs were there most of the time
(Major Courage 96%, Lucent Echoes 86%, Pearlescent Ward 82%, Major Slayer
71%, Major Force and Powerful Assault 52%), in the four-player fights
mostly not (Pearlescent Ward 54%, Major Courage 38%, Major Force 21%, the
other three never), and the taunt in 70 of 71 four-player fights and every
trial fight. So five of the six group buffs are ``expected large``, the
taunt ``expected small large``, and the boss debuffs and Crux nothing:
they depend on who is in the group, and show when they happened.
Powerful Assault was expected too until issue #48: the set's buff is
usual in a trial group, but no role has to bring it, so a fight without
it is not a mistake worth a red 0% row, and its rule shows when the buff
was seen, like the debuffs (tracking version 4 takes the words off a
saved line again, see upgrade_rules_text). The tracker alone, without the
engine's units, knows no group size and shows every item.

Elemental Catalyst (issue #53): the set's three weaknesses (Flame 142610,
Frost 142652, Shock 142653; critical damage taken up 5% each, as pen_crit
values them) are one default rule on the boss, shown when someone applied
them and not expected. The set is an alternative to Lucent Echoes for a
group's critical damage, run where Echoes is not, so a group running it
should see it; in these logs it is rare. Every split log of 2026 (891 log
files with a fight, 607 of them veteran trials): the weaknesses appear in
4 files, two Kyne's Aegis sessions (three files are the splitter's copies
of one), both also running Lucent Echoes, which 515 of the 607 trial logs
have; no dungeon or arena log has them, and none of the 92 trial logs
without Echoes has Catalyst instead. In the two sessions the wearer was a
DPS in January (22 of 24 fights, median uptime 53%, all three weaknesses
up together 7% of a fight) and a tank in May (one fight, 78% and 51%): the
rule's uptime, any weakness up, is well above the time the full 15% is in
effect, one weakness being the usual state. A measure counting the ids up
at once, and a way to say a group needs one of Echoes and Catalyst, are
left for when the logs show the set in use.

Touch of Z'en (issue #27): the game never writes its stacks. Every
EFFECT_CHANGED line for 126597 carries a stack count of 1 (3,577 lines in
four 2026 trial logs), refreshed as a FADED and a GAINED in the same
millisecond each time the wearer applies a damage-over-time effect.
Combat Metrics derives the count instead (LibCombat's UpdateZenData):
while the player's own Z'en is on a unit, the number of that player's
effects on the unit whose ability type is damage, GAINED up and FADED
down, at most five, 0 being a reading (Z'en up, no bonus). The ``dots``
measure does the same for every wearer the log shows. The log has no
ability type, so an effect counts as damage over time when its ability id
also ticks as DOT_TICK or DOT_TICK_CRITICAL (EffectTracker.dot_tick): on
those four logs that picks out Burning, Poisoned, Hemorrhaging, Roar of
Alkosh and the class and weapon DoTs, and leaves out Off-Balance, Breach,
Brittle and the other debuffs that deal no damage. A ground area such as
Stampede ticks without an effect on the target and counts for neither.
Each wearer's Z'en is their own span (two wearers on one boss do not end
each other's), and the reading at a moment is the highest count among
them, as for ``stacks``.

A line that starts with ``$`` is a HyperTools export string, pasted as
is: HyperTools (the in-game tracker addon) serialises a tracker as nested
``$...&`` records, and its name, ability ids and target ("Yourself",
"Group", "Boss", "Current Target") become a rule here; ``stacks`` or
``on <scope>`` after the string override what it says, and ``expected
<sizes>`` after it applies to every rule it gives.

What the logs carry (nine trial and dungeon logs of 2026): the stack
count is EFFECT_CHANGED's second field and changes arrive as UPDATED
lines, so stacks are read on GAINED and UPDATED; Off-Balance on a boss
comes under several ids at once (45902 for most sources, 62988 for
Elemental Blockade, 39077, 34733, 20806, 130139), so a union is needed,
and its uptime on a trial boss was 4 to 28% per fight; Crux stacks to 3
on the Arcanist alone; a pet-applied buff (a Glyphic's heal, Major
Protection from a netch) is applied to players like any other and needs no
special case, since only the target's kind is looked at. Replaying the
bundled examples through two of those logs (Sunspire, Kyne's Aegis):
Off-Balance on the boss 12 to 28% per boss fight, to the decimal what an
independent scan of the lines gives; Crux on the logging Arcanist a mean
of 1.5 to 2.9 with a peak of 3 in every fight.

### EffectTracker

*[src/effect_rules.py:616](../src/effect_rules.py#L616)*

Open and closed spans of each rule's effect on each unit in scope,
with the stack count and the unit's kind, in raw log milliseconds;
snapshot() reads a fight's window out of them, as the timeline
recorder does.

Each id of a rule runs its own span on a unit, so overlapping ids do
not cut each other short, and the measurement merges them. A span is
closed by FADED, by a stack change (one span ends, the next begins),
by the unit's death or removal (forget_unit: the game does not always
write FADED for a corpse's effects) or by a zone change for hostiles
and pets (zone_changed: unit ids are handed out afresh). Closed spans
are pruned once the fight they belong to has been published.

### EffectTracker.snapshot

*[src/effect_rules.py:812](../src/effect_rules.py#L812)*

One entry per rule for the fight window: name, scope, kind, what
it was measured on ('units': the scope, or 'mobs' for a hostile
rule in a fight without a boss), the uptime percentage, the mean
and peak stacks while up, how many of the pack's mobs it reached
and how many there were, the text the uptime line shows, and
fight-relative intervals for a timeline.

*units* is what the engine knows of the fight's units, unit id ->
(kind, since_ms, gone_ms): the players ('self' or 'group'), and the
hostiles the group hit ('boss' or 'enemy') with the log time each
was added and the time it died or was removed, None when not in
the fight. It says whether the fight had a boss, which mobs make
up the pack, and the window an ``each`` rule measures each unit
over. Without it (the tracker alone) the spans tell: a span on a
boss means a boss fight, and a unit is measured from the fight's
start to its death as forget_unit reported it, or the fight's end.

### CombatEncounter.fight_units

*[src/esolog_tail.py:878](../src/esolog_tail.py#L878)*

What effect_rules measures a fight's rules on, unit id -> (kind,
since_ms, gone_ms): the players ('self' or 'group'), and the
hostiles the group hit in this fight ('boss' or 'enemy', by the
game's flag less boss_units' exceptions) with the log time each
was added and the time it died
or was removed, None when it was there throughout. Enemies carry
over from fight to fight within a zone, so a boss that only stands
in the list, dead since the last pull, is not a boss of this fight:
it has to have been hit.

### AppConfig.reload

*[src/app_config.py:123](../src/app_config.py#L123)*

Read the file over DEFAULTS. A rules text saved before the uptime
line's group buffs and taunt became rules (tracking.version absent,
0.8.0 and earlier) kept only the user's own additions, so the line
would lose those items on upgrade: the missing ones are put in
front of it, by name, so a rule the user had already written under
the same name stays theirs. A text saved before version 3 then has
the default rules that are expected given their ``expected`` words
and Touch of Z'en's ``stacks`` turned into ``dots``, by name (upgrade_rules_text:
a renamed or already-flagged line is left alone), so a trial fight
still shows a missing group buff at 0% after the upgrade. A text
saved before version 4 has the ``expected large`` that version 3
put on its Powerful Assault line taken off again (issue #48: the
one default no longer expected). A text saved before version 5 has
the default Crux line commented out (issue #80). Nothing is written back; the
version is saved with the next Save, and every step is harmless to
repeat.

The timeline strip's old switch (experimental.buff_timeline, until
issue #25 made the strip the only view of the rules) is dropped
here, so the next Save leaves it out of the file.

## Taunts

### Taunts

*[src/esolog_tail.py:90](../src/esolog_tail.py#L90)*

The game puts one Taunt debuff on a taunted enemy whatever skill taunted, and writes a TAUNTED combat event that shares its cast tracking id with that skill's own cast and hits, which is how the skill is known: no list of taunt skills is needed, and a skill logged under another id (Destructive Clench with an ice staff is logged as Frost Clench) is matched to its bar slot by the icon the two share (mark_taunt_slots). The debuff's spans on each enemy give the uptime line's Taunt item through the default rule ``Taunt = 38254 on boss each`` (effect_rules): each boss's taunted share of its time in the fight, averaged over the bosses, the pack's mobs in a fight without a boss. Checked on 1,361 taunts in twelve logs of October 2026.

### mark_taunt_slots

*[src/esolog_tail.py:402](../src/esolog_tail.py#L402)*

Put 'taunt': True on each bar slot the player taunted with: the slot
whose ability id a taunt names, or, for a taunt logged under an id no
slot has, the slot that shares its icon (Destructive Clench taunts as
Frost Clench, a separate id with the same icon).

## What a boss is: the game's flag and its exceptions

### src/boss_units.py

*[src/boss_units.py:1](../src/boss_units.py#L1)*

What a boss is: the game's flag, and the units that carry it without being
the fight's boss (issue #67).

The encounter log flags a boss on its UNIT_ADDED line (isBoss, the sixth
field after the unit id), and the engine takes that flag as the word on
what a boss is: EnemyInfo.is_boss feeds the boss damage and boss dps time
(damage_stats), each player's boss share, the ``boss`` scope of the tracked
rules (effect_rules), the targets of the penetration figures and the
Armour row (pen_crit), and the damage window's boss-only switch. The flag
is the game's own boss health bar: it is reliable in dungeons and trials
(Z'Maja and her shade, the Lucent twins, Opulent Ordeal's three, every
dungeon boss), and the only boss definition that needs no list.

It is wrong for a few units. In Lucent Citadel the gauntlet before Xoryn
is one combat with him: the group hits five Defense Prisms (2,910,773
health, 10 to 20 s apiece) and Baron Rize (13,971,720, hit for 21 to 41 s
at about 110 s in) before Xoryn (69,858,576) is added a median 435 s into
a median 549 s fight, and all three carry the flag. Read as bosses, the
boss dps time of a Xoryn pull ran from the first hit on a Prism to the end
(a median 531 s of 561 s over 23 full pulls in 899 split logs) and divided
his damage, the Baron's and the Prisms' together; every player's boss
share counted Prism and Baron damage; a boss-scoped rule was measured on
every Prism (the taunt's ``each`` averaged over seven units); and the
penetration figures weighed the Prisms' seconds. In Kyne's Aegis the Sea
Adders of Yandir the Butcher's fight carry it too (4,657,240 health, 8%
of Yandir's, hit for about 22 s in every one of the 32 Yandir fights
logged), so the taunt was averaged over Yandir and his adders and 10% of
the "boss" damage was adder damage.

A survey over every split log on the maintainer's machine (899 logs,
9,177 fights, 2,943 that hit a flagged unit, 2026-01 to 2026-10;
scripts/survey_boss_flag.py) found no other flagged unit under a tenth of
its fight's largest flagged unit: after the Prisms (4%) and the adders
(8%) the next lowest is 20% (Baron Rize against Xoryn, and one Dreadsail
Reef pull of the Reef Guardians), then Spindleclutch's chain-pulled bosses
at 23% and Cloudrest's Shade of Z'Maja at 40%, all bosses in their own
right. The issue offered a rule instead of a list, a flagged unit under a
tenth of the largest flagged unit of its fight being an add. The survey
shows the threshold would hold, but the rule cannot be applied where the
flag is read: the largest unit, Xoryn, arrives seven minutes after the
Prisms, the tracked rules keep each span's unit kind from the moment the
effect was recorded, and the damage record keeps per-ability rows for the
bosses alone, so the fight would have to be re-kinded at its end. It would
also make the Prisms bosses on the 15 gauntlet wipes at the Baron (21% of
him) and on the wipes at the Prisms alone. A bundled list of monster ids
is read once, on the UNIT_ADDED line, so every consumer agrees.

Baron Rize is on the list, against the issue's first thought (he has a
name, a health bar and a phase of his own). The boss dps time runs from
the first hit on any boss to the last (Combat Metrics' GetBossTargetDamage,
see damage_stats), so with the Baron a boss a Xoryn pull's boss dps time
would still have been a median 446 s of 561 s, the Baron's half minute at
110 s stretching it over the gauntlet, against 129 s with him an add. The
other way out, a union of each boss's own hit window, would have changed
Nahviintaas, who lands as a new unit each time, in 27 of 136 Sunspire
fights, away from Combat Metrics' figure for a fight with one boss. A
wipe in the gauntlet before Xoryn is therefore a fight without a boss,
still named after the Baron when he took the most damage (the name follows
the most damaged hostile, flagged or not); removing his id from the list
reverses the choice.

Combat Metrics counts these units as bosses, since it reads the same boss
health bar, so its boss figures and this app's differ on Xoryn and Yandir
pulls, by design. A new trial can bring a new unit of this kind; the
survey script lists every flagged unit by zone with its health as a share
of the fight's largest, and a line here is all it takes.

## What counts as damage

### What counts as damage

*[src/esolog_tail.py:107](../src/esolog_tail.py#L107)*

A hit on an enemy is written with one of several results, and the dps figures sum the hit value of these: DAMAGE and CRITICAL_DAMAGE (direct hits), DOT_TICK and DOT_TICK_CRITICAL (each tick of a damage-over-time effect), BLOCKED_DAMAGE (what got through a blocking enemy) and DAMAGE_SHIELDED (what an enemy's damage shield absorbed). That is the set Combat Metrics (LibCombat) sums for damage done, and matches ESO Logs, which counts absorbed damage as damage done. Not counted: IMMUNE (the log writes a hit value the target never took), REFLECTED, FALL_DAMAGE, and the overflow field (overkill past the target's remaining health; Combat Metrics drops it too). Until 0.9.2 only the two direct-hit results counted: measured on 29 of Chris's split logs (990 dungeon and arena fights, 34 trial fights) the ticks were 26% of all damage dealt, and the top player's dps in a boss fight of a minute or more was understated by a median 35% in dungeons and 52% in trials, up to 79%. Shield absorbs were 2% and blocked hits 0.2%.

## Dps time and the damage window: parity with Combat Metrics

### Dps time

*[src/esolog_tail.py:125](../src/esolog_tail.py#L125)*

Every dps figure divides by the span of the hits it sums, first hit to last, floored at one second, and not by the fight time (BEGIN_COMBAT to END_COMBAT), because that is Combat Metrics' definition (LibCombat's dpstime) and the number players compare against. A player's dps is their damage over the span of their own hits, a boss figure the boss damage over the span of the hits on the bosses, the group's over the span of the group's. The fight time is still what the history line and header show; the header adds the group's dps time when it differs. The long form, with what Combat Metrics does about overkill, shields, pets and the breakdown by ability, is damage_stats' module docstring.

### src/damage_stats.py

*[src/damage_stats.py:1](../src/damage_stats.py#L1)*

Damage accounting per fight, the way Combat Metrics does it.

Combat Metrics (the LibCombat library behind it) is the addon ESO players
quote dps from, so this app's figures follow its definitions. The parts
that matter, read from LibCombat.lua and CombatMetrics.lua (October 2026):

- **DPS time, not combat time.** A fight's ``dpstime`` is the time between
  the player's first and last damage event, floored at one second
  (``max((dpsend - dpsstart) / 1000, 1)``), and every dps figure divides by
  it: ``DPSOut = damageOutTotal / dpstime``. The combat time (combat state
  on to off) is kept beside it and shown, but divides nothing. The live
  number during a fight is the same quotient, so it does not sink while
  the player stands still: ``dpsend`` is the last hit, not now. Here the
  fight time stays what the history line and header show (BEGIN_COMBAT to
  END_COMBAT, with the game's cuts healed, see COMBAT_RESUME_MS), and each
  dps figure divides by a dps time of its own: a player's by the span of
  their own hits, the group's by the span of the group's, a boss figure by
  the span of the hits on the bosses. That is what each player's own
  Combat Metrics shows them, and what they post in chat.
- **Boss dps** divides the damage dealt to the boss units by the span of the
  hits on those units (``GetBossTargetDamage``: ``bossTime`` from the boss
  units' own first and last event), and falls back to the fight's dps time
  only when that span is empty.
- **What counts** is the six results in DAMAGE_RESULTS (esolog_tail), from
  the player and the player's pets, to any unit that is not a player pet.
  Overkill is dropped: LibCombat overwrites the game's overflow value with
  the shield amount it pairs to the hit. A damage shield's absorb is added
  to the hit it absorbed (``DAMAGE_SHIELDED`` events buffered and matched on
  source and target within 100 ms); the encounter log writes the absorb as
  its own line, so summing those lines is the same total.
- **Group dps** in Combat Metrics is the group's damage over the *logging
  player's* dps time (``UpdateGrpStats``: ``groupDamageOut / self.dpstime``),
  a limit of an addon that sees one client's combat state. The log sees
  every player's hits, so here the group's dps time is the span of the
  group's own hits, which is what that quotient means.
- **The breakdown by ability** (``ProcessLogDamage`` / ``AccumulateStats``)
  keys on the ability id and whether a pet cast it, and keeps per key the
  damage by result (normal, critical, blocked, shielded), the hit counts by
  result, and the largest and smallest hit; a row's dps is its damage over
  the fight's dps time, its crit rate is critical hits over hits, and its
  average is damage over hits. The window here keeps the same figures per
  player, for all targets and for the boss units alone, and the damage per
  target unit with its own first-to-last span ("the damage per second
  between your first and your last hit to that target").
- **The graph** (``CombatMetricsUI.lua``, ``Smoothed`` and ``Total``) works
  from the damage summed into one bucket per second of the fight
  (``calculated.graph``, filled by ``ProcessLogDamage``). Its dps curve is a
  centred moving average over ``SmoothWindow`` seconds (5 by default): a
  point at ``t + w/2`` with the mean of the buckets ``t .. t+w-1``, the
  first and last points carried to the fight's edges. Its total curve is
  the live figure as it stood: the damage so far over the dps time so far
  (``sum / (min(dpsend, t) - dpsstart)``), from half a window after the
  first hit on. The graph window draws both (smoothed_dps, running_dps),
  for the group and for each player, from the same per-second buckets
  (PlayerDamage.buckets, FightDamage.buckets).

Differences left in place, on purpose: a hit a shield absorbed in full is
written as a DAMAGE line of value 0 beside its DAMAGE_SHIELDED line (two
thirds of the shield lines in two logs of 2026; the rest sit beside a
partial hit or alone), and the engine drops every zero hit, so such a hit
counts as absorbed damage but not as a hit where Combat Metrics counts it
as one; and dps figures are kept as floats where Combat Metrics rounds to
the integer.

Measured on 113 split logs of 2026 (1,941 fights with damage, 564 with a
boss), dividing by the dps time instead of the fight time raises the group's
dps by a median 1.0% in boss fights of a minute or more (p90 5.9%), each
player's own dps by a median 5.8% (p90 41%) and their boss dps by a median
9.7% (p90 75%): the group's first hit comes a median 0.5 s after
BEGIN_COMBAT and END_COMBAT a median 0.5 s (p90 6 s) after its last, and a
player's own span is more than 10% shorter than the group's in 29% of
player-fights (died, arrived late, stopped hitting). What the engine does
not count stays negligible: hits on units the log never added 0.07% of all
damage, on non-hostile units 0.00%, in the two seconds before BEGIN_COMBAT
0.04%, in the 1.3 s after END_COMBAT 0.02%.

### dps_time_s

*[src/damage_stats.py:94](../src/damage_stats.py#L94)*

A dps time: the span in seconds, floored at a second like LibCombat.

A span of 0 (one hit, or none) is a second, so a single hit reads as
its own damage per second rather than infinity.

### src/gui/damage_render.py

*[src/gui/damage_render.py:1](../src/gui/damage_render.py#L1)*

The damage window's HTML: one player's damage in a fight, broken down by
ability and by target the way Combat Metrics' fight report breaks it down.

The data is the fight entry's player dict, key 'damage', as
damage_stats.PlayerDamage.snapshot built it: totals, the spans the dps
figures divide by, one row per ability (and per pet ability), the same rows
for the boss units alone, and the targets hit. The figures follow
damage_stats: a row's dps is its damage over the player's dps time (over
their boss dps time in the boss view), crit % is critical hits over hits,
the average is damage over hits, and a target's dps divides by the span of
the player's hits on that target. Colors are theme-aware like the rest of
the fight pane.

### src/gui/dps_graph.py

*[src/gui/dps_graph.py:1](../src/gui/dps_graph.py#L1)*

DPS over time: a line chart of the group's and each player's dps across a
fight, drawn the way Combat Metrics' graph tab draws it (see damage_stats
for the two curves: the centred moving average over a window of seconds,
Combat Metrics' default 5 s, and the running figure, the live dps as it
stood at each second).

The data is the fight entry's group series (FightHistoryEntry.damage_series)
and each player's (the 'series' and 'boss_series' of their 'damage' dict),
damage summed per second of the fight. The window offers the window length
(1, 5, 10 or 30 s) or the running figure, the boss units alone in a fight
with a boss, and a legend of checkboxes for the group and every player. The
first eight players (in the fight's ranking) are on to begin with and the
rest off, because eight is as many hues as can be told apart; a player past
the eighth reuses a hue with a dashed line. A player's hue is their rank in
the fight, so hiding others never repaints them.

Two panels, one scale each: the group's figure is as many times a player's
as there are players, so on one scale the players' lines lie flat along
the floor, and a second axis on the same plot is the classic way to mislead.
The group's line gets the upper panel and the players the lower, sharing
the time axis, the crosshair and the tooltip. Drawing otherwise: hairline
solid gridlines a step off the surface, 2 px lines with round joins, the
group's heavier in the pane's text colour, the categorical hues in a fixed
order (eight hues with a light and a dark step; Settings' colour-blind
option swaps in seven measured to stay apart for the dichromacies, with a
cycle of four strokes), text in the pane's own text colours and
never in a series colour, and the end value of each line labelled when a
panel shows four or fewer.

## Pets: whose damage and healing they are

### CombatEncounter.track_pet_ownership

*[src/esolog_tail.py:618](../src/esolog_tail.py#L618)*

Record *pet_unit_id* as a pet of the player who owns it, so its
damage and healing count as that player's; forget it when the owner
is nobody ("0") or not a player (a boss's summons), which also
covers a unit id handed out again.

Design: the log names the owner of every summoned unit, as
ownerUnitId in UNIT_ADDED (fields[13]) and UNIT_CHANGED (fields[8]).
A survey of nine trial and dungeon logs (October 2026) found 1,142
player-owned units, all MONSTER with reaction NPC_ALLY or FRIENDLY
(Blighted Blastbones, Skeletal Archer, Wild Guardian, Gloom Wraith,
atronachs, Clannfear, Glyphic of the Tides, companions), and 1,283
boss-owned ones; 18 unit ids were handed out again with a different
owner; and the owner field dropped to 0 on 106 pets, none of which
dealt damage afterwards (0.3 to 11 s before its UNIT_REMOVED). So
ownership follows the log exactly, and is carried into the next
fight with the players and enemies, since pets are summoned before
the pull. Pets were 0 to 8% of a group's damage per log. Earlier
code guessed pets from EFFECT_CHANGED targets and never found one.

### CombatEncounter.add_damage_to_player

*[src/esolog_tail.py:744](../src/esolog_tail.py#L744)*

Credit damage dealt by *unit_id* to the player it belongs to:
the player themself, or the owner of a pet (see
track_pet_ownership). Damage from a unit that is neither is
counted for nobody: a boss's summons, trial mechanics that hit
other enemies, and the like. *to_boss* says the target is a unit
the game flags as a boss, so the hit also counts as boss damage.
With the hit's *timestamp*, *result*, *ability_id* and *target_id*
the hit also goes into the fight's damage record (damage_stats):
the spans the dps figures divide by, and the breakdowns. With its
*damage_type*, *cast_id* and the analyzer's *cast_index* the record
also keeps the kinds of the damage (damage_kinds): the area rule
reads the cast, the session and the player-skill table, and a hit
counted single is moved to area should its cast strike a second
unit later.

A companion's damage is its own row's (companions.py), keyed by
the companion's row key, with its kinds like a player's; with
*accrue_companions* (the setting companions.accrue_to_owner) it is
its owner's as well.

## Split files: one per session, continued rather than copied

### LogSplitter

*[src/esolog_tail.py:3403](../src/esolog_tail.py#L3403)*

Handles automatic splitting of encounter logs into individual encounter files.

Design: one split per session, continued rather than copied (issue #85).
A session's split is named at its first BEGIN_COMBAT from the BEGIN_LOG
stamp and the zone, so a session split again meets its own file at the
rename. Until 0.18.0 the two were compared by whole-file MD5, which can
never match there (the temp file holds the lines up to that BEGIN_COMBAT,
the file on disk the whole session), so the session was written out
again under the next ``-N``: 513 of the 899 files in the maintainer's
split folder were byte-identical copies, 512 of them written by the
pre-GUI tool's ``--read-all-then-tail`` between January and April 2026,
which re-split the whole log at every start. Now the file on disk is the
same session when it begins with the temp file's bytes; the temp file is
dropped and the existing file is continued: incoming lines are counted
and skipped until the count reaches the file's size and the file's last
line has gone past, then appended, so a split cut short by a restart,
a crash or a Settings save (which rebuilds the monitor) is completed
rather than left truncated, and a split already complete gains nothing.
A file that ends mid-line (a crash) is trimmed to its last whole line
first. Only a file whose head differs is a different session of the same
second and gets the suffix. At the session's end a copy that still
matches another file of the same stamp byte for byte is removed; a
continued file never is. Two instances of the app on one split folder
(the installed app beside a launch from the source tree, which wrote
the one copy of 2026-10-25) would append to one file from two sides, so
the splitter takes a lock file in the folder, ``.esolog-tail-split.lock``
with its process id, and a second instance that finds it held by a live
process writes no splits at all and says so. Every line of the session
is written, the ones the parser rejects included (an END_CAST with a
cancel reason, an OBJECT unit), so a split is the session's bytes; the
older splits are a few hundred bytes to 57 KB short of that, which the
continuation tolerates.

### scripts/dedupe_splits.py

*[scripts/dedupe_splits.py:1](../scripts/dedupe_splits.py#L1)*

Move the byte-identical copies of split logs to the Recycle Bin (issue #85).

Until 0.18.0 a session split again was written out again under the next
``-N`` suffix: the pre-GUI tool's ``--read-all-then-tail`` did that to every
session in the log at every start, and 513 of the 899 files in the
maintainer's split folder were copies of another file, several GB in all.
The splitter no longer makes them (see LogSplitter in src/esolog_tail.py);
this script clears the ones already on disk.

A copy is a file with the same session stamp as another, the same size and
the same bytes (whole-file SHA-256, not a head hash). Of each group the file
with the lowest suffix is kept, the plain name before ``-1`` before ``-2``,
and the rest go to the Recycle Bin, never deleted outright, so a mistake can
be undone. Zipped splits and the ``keep`` folder are left alone.

```
    python scripts/dedupe_splits.py                      # list what would move
    python scripts/dedupe_splits.py --recycle            # move the copies
    python scripts/dedupe_splits.py --dir D:/esologs/splits --recycle
```

Without --dir the split folder from the app's config is used.

## A trial's result, and the fight list in blocks by instance

### src/trial_result.py

*[src/trial_result.py:1](../src/trial_result.py#L1)*

A trial's result as the game writes it: vitality left, score and time.

Design: when a trial (or an arena) is completed the log writes one line,

```
    END_TRIAL,id,durationMS,success,finalScore,finalVitalityBonus
```

e.g. ``1415661,END_TRIAL,12,1351407,T,253117,35000``: Sunspire (id 12) in
22:31, score 253,117, 35 of 36 vitality left. What the line tells, measured
on every completed run in a year of split logs (146 runs, 2026-01 to -10):

- Vitality left is finalVitalityBonus / 1000. The bonus is always a
  multiple of 1,000, at most 36,000 (a deathless Maw of Lorkhaj) and at
  least 0 (87 runs with 36 deaths or more). The 35/36 Sunspire run of
  2026-10-21 wrote 35000 with one player death in the log.
- The maximum is 36 in the 12-player trials, all of which were veteran
  runs; an arena's is not (a Dragonstar Arena run with 7 deaths kept 14),
  and a normal trial's was never seen. So the maximum is shown only for a
  veteran run of a trial in TRIALS, and an arena's or an unknown run's
  vitality as the points alone.
- success is T in every END_TRIAL: a run that fails or is abandoned writes
  none, so there is never a failed result to show.
- Vitality is the log's figure, never 36 less the deaths the engine counts.
  In 38 runs the log holds fewer player deaths than the game charged (3
  logged against 13 in an Aetherian Archive run, 8 against 23 in Hel Ra):
  the log carries the events around the player writing it, so after a wipe
  in which that player released, the others' deaths are not all there.
  Eight runs also began in an earlier split than the one with END_TRIAL.
- The name is the zone's at the time (ZONE_CHANGED), the id's from
  TRIAL_NAMES only when there is none. A split's file name can be another
  trial's: one named for Dreadsail Reef ends Kyne's Aegis (id 13).

The line comes inside the final fight in 144 of the 146 runs (33 ms after
the last hit of a Sunspire run) and so belongs to that fight. In the other
two, both Blackrose Prison, it comes about 4 seconds after END_COMBAT, and
the engine gives it to the fight it has just sent (ESOLogAnalyzer.
_handle_end_trial), which frontends then redraw.

### src/gui/fight_list.py

*[src/gui/fight_list.py:1](../src/gui/fight_list.py#L1)*

The fight list: the session's fights in blocks, one per instance.

Design (issue #129): the fights fought one after another in the same
instance form a block. A header row above it names the zone and its
difficulty, so the fight rows leave the zone out; when the block ended a
trial or an arena, an inert row under its last fight gives the run's
result (trial_result: vitality, score, time); and the blocks lie on
alternate backgrounds, a faint band and none, so neighbours stand apart.

A new block starts at a fight in another zone or at another difficulty
than the fight before, or at the first fight after a completed run, even
in the same zone. A wipe and a walk back in through the same door keep the
block: the zone and difficulty are the same and no run was completed. The
zone is told by its id (a solo dungeon shares its name with the group
dungeon, pen_crit.zone_kind) and by its name only when the entry has none.

Header and result rows are not enabled, so a click or a key never makes
one current: the arrow keys step from fight to fight over them, and Home,
End and the page keys go on to the nearest fight (moveCursor). Their text
takes the list's own text colour, which a disabled row would otherwise
grey out. The list therefore maps rows to fights itself (entry_at,
row_of) and offers the fight-index calls the window and tests use
(select_fight, fight_item, current_fight_index).

The band is the list's base colour moved BAND_MIX of the way towards its
text colour, so it follows the theme and keeps the text's contrast; it is
worked out again, with the header's bold font, whenever the palette or the
font changes (a theme switch, a new text size).

The (i) on a fight row (issue #147): hovering it shows who in that fight
has a possible build issue and what (fight_render.fight_issues_tooltip),
so a session's flagged fights can be read without selecting each one and
looking for the marks on the pane's rows. The row is plain text, so the
mark has no anchor of its own: viewportEvent takes the ToolTip event and
works out where the mark is drawn (issues_mark_rect), the way the style
lays the row out: the style's text rectangle, the margin every style keeps
inside it, then the width of the text before the mark. The text rectangle
matters: Windows 11's style starts it 6 px in, leaving room for its
selection bar, where Fusion and windowsvista start at the row's edge
(measured 2026-10-31 on all three and offscreen, the mark's first painted
column within a pixel of the computed one). The pointer gets MARK_SLACK
pixels either side, and the tooltip closes once it leaves that band. The
rest of a row shows no tooltip, as before. The text is built at hover
time from the hovered row's own fight, usually not the one on screen,
with the window's Hide names switch (hide_names), so it follows the switch
without a rebuild. A screen reader hears the mark as the
row's description (fight_render.issues_description), which names nobody.

## Death recaps

### src/death_recap.py

*[src/death_recap.py:1](../src/death_recap.py#L1)*

Death recap recording: what hit and healed a player in the seconds before
each death, for the GUI's per-player recap.

The analyzer passes every COMBAT_EVENT whose target is a player to record();
a short per-player history is kept, and note_death() turns that history into
the recap a frontend renders. Times are raw log-relative milliseconds.

How the log writes a death (checked against live trial, arena and dungeon
logs):

- The dying unit's event is DIED, or KILLING_BLOW when the killer is a player
  (friendly fire, PvP). Its source and ability name the killer.
- The killing blow's own damage line usually comes *after* that event, 0-2 ms
  later, carrying the overkill in the overflow field.
- hitValue is what actually reached (or restored) health; the target's unit
  state on the line is the state after the event.
- DAMAGE_SHIELDED lines come just before the hit they absorbed, with the
  attacker as source, the same castTrackId, and the shield as the ability.
  Several shields can soak one hit, and the death event can sit between the
  shields and the hit.

Each row also carries the kinds of the hit (damage_kinds, issue #73): its
damage type, and whether it was an area hit, read from the cast index the
analyzer shares with the recorder (a cast that struck two or more units),
with the rule that decided and the number of players the cast struck. Rows
are classed when the recap is built or refilled, and once more when the
fight ends (refresh_fight), so a ground effect that reached a second player
seconds after the death still reads as area. Pure overheals (a heal line
whose hit value is zero) are kept in the window for the recap's overheal
sum but never become rows.

The window is a setting (issue #95): 5 seconds by default, up to 10, read
from the config when the engine is built (app_startup), so a Settings save,
which rebuilds the engine and replays the session, rebuilds the fights
already listed with the new window. Each recap records the window it was
built with ('window_ms'), so a frontend names the right number of seconds
for a fight recorded under another setting, and a recap from before the key
existed reads as the old fixed five.

## Kinds of damage: direct or over time, area or single target, Martial or Magical

### src/damage_kinds.py

*[src/damage_kinds.py:1](../src/damage_kinds.py#L1)*

The kinds of damage: direct or over time, area or single target, Martial or
Magical, and what shields, blocks, heals and overheal did (issue #73).
Engine side, no Qt. The death recap and the build window draw the same
summary from the same rules, so a reader learns one vocabulary.

Design. The Warfare champion point stars act on four splits of a hit, and
the encounter log carries three of them on every COMBAT_EVENT line:

- **Direct or over time** is the result: DAMAGE, CRITICAL_DAMAGE and
  BLOCKED_DAMAGE are direct, DOT_TICK and DOT_TICK_CRITICAL are over time
  (Master-at-Arms and Thaumaturge for damage dealt, Ironclad and Enduring
  Resolve for damage taken). FALL_DAMAGE is neither and is named "fall".
- **Martial or Magical** is the damage type: PHYSICAL, BLEED, POISON and
  DISEASE are Martial (Mighty, Hardy), MAGIC, FIRE, COLD and SHOCK are
  Magical (War Mage, Elemental Aegis). OBLIVION belongs to neither and no
  star reduces it; DROWN, GENERIC, NONE, EARTH and any type a later patch
  adds are "untyped" and shown under the log's own word, never refused.
  Over 87 of Chris's split logs (11.6 million combat lines, 6,831 player
  deaths; 2026-10-27) the damage that reached players' health was 885M
  Magical, 411M Martial, 44M Oblivion and 20M fall, drowning or untyped,
  89% of it direct and 11% ticks; the death lines by type were MAGIC 1,434,
  PHYSICAL 1,391, SHOCK 1,257, FIRE 1,053, OBLIVION 770, COLD 587, POISON
  243, GENERIC 59, BLEED 17, DISEASE 17, DROWN 3. EARTH appeared on five
  hits, NONE on REFLECTED lines and on the zero-value DAMAGE line the game
  writes beside a DAMAGE_SHIELDED line when a shield took the whole hit.
- **Blocked, absorbed, avoided.** A BLOCKED_DAMAGE hit value is what got
  through the block and counts as direct damage; how much the block
  prevented is not in the log, so it is never stated. A DAMAGE_SHIELDED
  line is what a shield absorbed and is never added to the damage that
  reached health (shields absorbed 726M on players in the survey, more than
  any one damage type reached health). DODGED and MISS are counted, not
  summed. IMMUNE and REFLECTED are not counted.
- **Healing.** HEAL and CRITICAL_HEAL are direct heals, HOT_TICK and
  HOT_TICK_CRITICAL heals over time (Focused Mending, Swift Renewal); the hit
  value is healing received and the overflow is overheal (1.17B received against 12.4B
  overheal in the survey; 3.1M of 3.6M heal lines were pure overheal).
  HEAL_ABSORBED is healing a healing-absorb effect ate. The killing blow's
  overflow is overkill (written on 6,039 of 6,398 killing blows; a blow
  written as BLOCKED_DAMAGE or FALL_DAMAGE carries none).

**Area or single target is not in the log** (Biting Aura and Deadly Aim,
Unassailable and Duelist's Rebuff), and is read from the cast id. Every
hostile hit on a player in the survey carried a non-zero castTrackId, and
grouping hits by (source unit, cast id) separates the mechanics that kill
groups from the attacks that pick one player: Maelstrom's 147 casts struck
up to 12 players each, Grievous Pulse's 38 casts struck more than one player
every time, Oppressive Bolts' 266 casts 98% of the time; Piercing Hailstone,
Venom Injection, Temporal Splinters, Swipe, Claw and Clash struck one unit
per cast, always. So a hit is area when its cast struck two or more distinct
units in the fight, counting hits before and after it; a hit of a cast that
struck one unit is area when a cast of the same ability struck two or more
earlier in the zone session (a repeat pull of the same boss); for a player's
or pet's own ability with no such evidence the bundled table of player
skills' target kinds decides (data/skills/ability_targets.json, Area, Cone
and Ground against Enemy, from UESP's skill table); otherwise single target.
Monster abilities never consult the table: UESP's target field calls
Oppressive Bolts and other group-wide mechanics "Enemy", and knew only 74%
of the hostile damage in the survey, so for monsters the log is the better
judge. The rule that classed a hit is kept beside it, so a reader can be
told "this cast hit 8 players" or "no cast of this ability struck two
players this session". Melee against ranged is not attempted: the log has no
range, its unit positions are normalised map coordinates whose scale differs
by map, and no Warfare star reads it.

A session's cast index and a fight's damage-taken tallies cost a few
dictionaries: the (source, cast) map is cleared at each fight's end, the
per-ability memory with the zone session (unit ids start over), and a cast's
pending amounts are dropped the moment it hits a second target.

## The damage taken window: by source and by healer, over the whole fight

### src/gui/taken_render.py

*[src/gui/taken_render.py:1](../src/gui/taken_render.py#L1)*

Damage taken window: one player's damage taken and healing received over a
whole fight, by kind, by the unit that did it and by the unit that healed
(issue #98). The death recap keeps the last seconds before each death and
is only there for a player who died; this window has no event table, only
the fight's totals, so it opens for any player.

Design. What a tank wants to know after a pull is what hit them, who hit
them and whether the healing kept up, none of which the fight pane or the
build window says. The data is the player dict's 'taken' key, as
damage_kinds.TakenTally.snapshot writes it for every player in every fight.
The shape follows a survey of three veteran trial logs (Dreadsail Reef,
Sunspire, Halls of Fabrication; 48 boss fights of a minute or more, 561
player-fights with damage taken; 2026-10-27):

- Every ability is listed, no cap. A tank took damage from a median 11
  distinct abilities (at most 26) and 8 units (at most 29), a DPS from 7
  and 5 or 6; the ten largest abilities carried everything in the median
  fight, so the table is short enough to read whole.
- Damage is grouped by the unit that did it, bosses first. The largest
  source carried about half the damage and the second a fifth, so "the
  boss against the adds" is the first question; units of one name are one
  row with their count, since adds come in packs (four Alkosh's Will on
  Nahviintaas). Bosses carried a median 44% of the damage taken in every
  role. The unit the log leaves unnamed (id 0: the environment, fall
  damage, some set procs) is its own row.
- The per-second figure divides by the fight time, pull to end, not the
  span of hits as the dps figures do: it is for comparing pulls, a quiet
  stretch is part of the answer, and the hits spanned only 64-80% of the
  fight (tanks most). Tanks took a median 1,016 a second, DPS 545, healers
  512.
- Healing is grouped by healer, with the healer's abilities under them.
  Six to eight units healed each player in the median fight (every group
  HoT counts) with 15-19 abilities between them; the largest healer gave
  51-65%, a tank's own heals 23% of what they received, a healer's own
  61%. A pet's heals (a Twilight Matriarch's) are a row of their own named
  after the owner, since the log names no pet.
- Overheal is a share per row, never an amount: 91-96% of all healing on a
  player overflowed, so the amounts would be ten to twenty times the received
  figures and bury them. Healing received is the headline; the share tells a
  healer which HoTs were wasted on this player.
- Shields absorbed 54-67% as much again as the damage that reached health
  (tanks most), so the header gives the absorbed amount with that ratio,
  and the blocked hits as a count of the direct hits that reached health
  (tanks blocked 1,818 of 5,729 in the survey). What a block, armour or
  resistances prevented is not in the log and is never stated.

The kinds bars are the death recap's block (death_render.kinds_block_html)
so the two windows read alike; the player names go through the Hide names
mask (gui.name_mask), the sources and healers included.

## Experimental buff timeline

### src/buff_timeline.py

*[src/buff_timeline.py:1](../src/buff_timeline.py#L1)*

Buff/debuff timeline recording (buff-timeline spec).

Records the active intervals of a handful of raid-defining effects with
cast/receive attribution, for the built-in rows of the per-fight timeline
strip (the tracked-effect rules bring the rest, effect_rules). Recording is
always on since the strip became the only view of the rules (issue #25);
the analyzer's track_buff_timeline gate remains for tests.

Interval times are raw log-relative milliseconds; snapshot_fight() clips them
to a fight's [start, end] window and rebases them to fight-relative ms.

### EffectTracker.record

*[src/effect_rules.py:689](../src/effect_rules.py#L689)*

An EFFECT_CHANGED line. *target_kind* is what the engine knows
the target to be: 'self', 'group', 'pet', 'boss', 'enemy' or None.

*source_id* is the caster, kept on the span so a row of the uptime
strip can say who applied it ("" when unknown). Another caster
refreshing the effect ends one span and starts the next, so each
span is credited to whoever last applied it; the spans abut, and
every measurement takes their union, so no number changes.

A ``dots`` rule's spans are kept per caster (each wearer's Touch of
Z'en is their own debuff), and while one is held every effect a
caster has on a hostile is followed too (_record_effect).

### src/effect_summary.py

*[src/effect_summary.py:1](../src/effect_summary.py#L1)*

Who applied an effect and who had it, over a whole fight (issue #19).

A row of the uptime strip is a list of intervals, each naming its caster
('source') and receiver ('target'): the built-in rows from the buff
timeline recorder, the tracked rows from the effect tracker. Hovering the
strip shows the intervals at one instant; summarise() adds them up over
the fight for the pop-up a click on the row opens.

Every figure is a union of intervals as a share of the fight, the rule the
row's own uptime uses (timeline_strip.uptime_pct), so the receivers' lines
and the casters' lines each union back to the headline:

- a caster's *uptime* is the time any of their intervals was up, and their
  *sole* time the part of it no other caster's interval covered; two
  supports keeping Major Courage up between them show the overlap in the
  gap between the two;
- a receiver's *uptime* is the time the effect was on that unit;
- *spans* counts intervals, not casts: the recorders merge a recast that
  follows a fade within moments into the span before it.

An interval without a caster (an old saved fight, or a proc the log writes
without a unit) is counted under UNKNOWN_SOURCE rather than dropped.

### paint_sparse_span

*[src/gui/timeline_strip.py:220](../src/gui/timeline_strip.py#L220)*

Paint one span of a group buff that reached only one or two receivers
(issue #45): the effect's colour at SPARSE_BASE_ALPHA over the row's
full height, under a cross-hatch of the full colour, so the span is
unbroken along the time axis and textured across it.

Up to 0.13.1 such a span was a dotted line down the row's middle, and a
row of dots is exactly what a solid bar looks like when the effect
comes and goes every few seconds: at a glance, up the whole time on
one person read as up half the time on everyone, and the two call for
different fixes (whom the buff reaches against how long it lasts). A
fill with no gaps keeps up reading as up; the hatch says not the whole
group. The lines are drawn here rather than with one of Qt's pattern
brushes so that their spacing suits a ten-pixel row (a step no larger
than the row's height puts a line through every column) and so that
they fall on a grid anchored at the track's left edge, the same
wherever a span starts. The caller paints the union of the row's
intervals, one call per merged span, so overlapping receivers do not
double the translucent base and abutting spans show no seam.

## Split log retention: zipping old splits and moving older ones to the Recycle Bin

### src/split_retention.py

*[src/split_retention.py:1](../src/split_retention.py#L1)*

Split log retention: zip split logs older than N weeks (issue #86) and
move those older than M weeks to the Recycle Bin (issue #87).

Which files. Only the splitter's own names are touched:
``YYMMDDHHMMSS-<Zone-Name>[-vet][-N].log`` and the same with ``.zip``
added. The split folder defaults to the log's folder, which also holds
Encounter.log and the archiver's ``Encounter-*.zip``, and Chris's split
folder holds ``*-report.txt`` files another tool writes; none of those
match. ``-temp.log`` (a split still waiting for its zone) never matches,
subfolders are never entered, and symbolic links are skipped. That makes a
``keep`` folder inside the split folder a place where nothing is ever
zipped; the job creates it so it is there to use.

How old. A split's age runs from the later of the session stamp in its name
and its modification time. On the 899 splits in Chris's folder
(2026-10-27), 433 had a modification time more than two days off their
stamp, because the splitter wrote some sessions out again long after they
were played (issue #85). The later of the two never makes a file look older
than it is, and a session that stays open for days, with an old stamp and a
file still growing, stays young.

The latest session. The split of the live log's newest session (its last
BEGIN_LOG) is never touched: it may be the file the splitter has open, and
it is the one session the app replays at every start, so deleting its
split would only have it written out again. The newest session in the
folder is spared too: it is almost always the same one, and Settings can
find it without reading the log, so its preview counts what a run does.

Deleting (issue #87) moves files to the Recycle Bin (recycle_bin), never
deletes outright; a file the bin cannot take is left and reported. M must
be more than N while zipping is on, so a split is zipped before it can be
deleted; settings_from_config holds to that even for a hand-edited config.
A run deletes first and zips what is left, since zipping a file about to
be deleted is wasted work. Settings asks before saving a change that
deletes: turning it on, lowering M, or pointing it at another folder; the
daily run deletes only within what was confirmed and asks nothing.

Zipped splits are still splits. ``<stem>.log.zip`` holds one member,
``<stem>.log``, so the original name stays visible and a ``*.zip`` pattern
cannot mix it up with the archives. The splitter's checks for "this session
already has a split" (LogSplitter._scan_existing_splits and
LogFileMonitor._session_split_exists) accept the zipped form, indexed by
the member's size; without that, zipping the newest split of someone who
had not played for N weeks would have it written out again at the next
start, and zipped again under a ``-1`` name.

Writing safely, as the log archiver does: the zip is written to
``.partial``, read back in full (CRC and size), given its final name, and
only then is the log removed, so an interrupted run leaves the log or a
verified zip, never neither. A ``.partial`` left by an interrupted run is
removed at the start of the next. The zip and its member keep the log's
modification time. A zip of the same name that already exists is either
the same log (the log is then removed as a copy) or a different one (the
log is left and reported).

What it saves. Deflate at level 6 brings a split to about 6% of its size
(a 95 MB Hel Ra split to 6.0 MB in 1.0 s, a 573 MB Dreadsail split to
34.8 MB in 5.7 s, both read back in under 2 s). On a folder Windows
already compresses (Chris's: 105 GB stored in 32 GB) the saving is
smaller: about 26 GB there rather than 92.

When. At startup and once a day while the app is open, on a thread of its
own (RetentionRunner), one file at a time with a check for cancel between
chunks: the first run over a large folder takes minutes, and the engine
thread that polls the live log must not wait for it.

### src/recycle_bin.py

*[src/recycle_bin.py:1](../src/recycle_bin.py#L1)*

Moving a file to the Recycle Bin (the trash on Linux and macOS), never
deleting it outright (issue #87).

Why not send2trash on Windows. Both its Windows backends ask the shell to
delete with "allow undo" and "no confirmation". When the Recycle Bin cannot
take a file (a network or removable drive, the bin turned off for the
drive, a file larger than the bin's limit), Windows then deletes it
outright without a word; its pywin32 backend's progress sink returns
E_FAIL in that case, but its own comment says the delete goes ahead. So on
Windows this module:

1. Checks the bin can take the file: a fixed local drive, no
   NoRecycleFiles policy, the drive's bin not set to delete at once
   (NukeOnDelete), and the file no larger than the drive's bin limit
   (MaxCapacity in MB, under HKCU\...\Explorer\BitBucket\Volume\{guid};
   a RecycleBinSize policy, a percentage of the drive, wins; a drive with
   neither gets Windows' default of 5%). A file that fails the check is
   left where it is and reported.
2. Asks the shell (SHFileOperationW) with FOF_WANTNUKEWARNING as well, so
   should the check ever be wrong, Windows asks before deleting outright
   rather than doing it.

Elsewhere send2trash moves the file to the freedesktop trash (Linux) or the
Finder's (macOS); both fail rather than delete outright when there is no
trash for the file.

### src/log_open.py

*[src/log_open.py:1](../src/log_open.py#L1)*

Opening a log for review: a plain log, a split the retention job zipped
(``<stem>.log.zip``, issue #86) or an archive the log archiver wrote
(``Encounter-*.zip``).

A zip is read as a stream through its member, never extracted to disk or
read whole into memory: an archive can hold a log of more than a gigabyte.
The size reported for progress is the member's own, since the zip's is
about a sixteenth of it. A zip is recognised by its content, not its name.

## The GUI and the engine thread

### src/gui/engine_worker.py

*[src/gui/engine_worker.py:1](../src/gui/engine_worker.py#L1)*

Engine worker: runs the analysis engine on a QThread and bridges
AnalyzerListener callbacks to Qt signals (queued to the UI thread).

Engine modules never import Qt; this adapter is the only crossing point.

Design: the worker is a Python-created QObject, so it is freed on the UI
thread and never by Python's garbage collector, which frees whatever is
garbage on whichever thread happens to be allocating. As the worker's thread
finishes, QThread.finished calls leave_thread on that thread (a direct
connection): the timers stop and the worker moves itself to the UI thread,
since only the thread an object lives in may move it. The window then
deletes it there (MainWindow._discard_worker). The listener holds the worker
weakly, so a worker nobody holds is freed at once.

Until issue #18 the window tried to pull the worker over from the UI thread
after the thread had ended. Qt refuses that ("Cannot move to target thread",
printed at every close), so the deletion went to a thread that would never
run it. The listener also held the worker in a reference cycle, so only the
garbage collector could free it. In the test suite, where every GUI test
leaves windows and workers behind, a collection was seen running on an
engine thread; one that found GUI objects there would free them off the UI
thread, which is how Settings crashed in 0.6.x.

### MainWindow._on_monitoring_restarting

*[src/gui/main_window.py:781](../src/gui/main_window.py#L781)*

The engine has begun the restart Settings asked for. Everything
it sent before this belonged to the analyzer being replaced, so the
history is cleared now rather than when Save was pressed: a replay
still running at that moment went on filling a list cleared too
early, and its fights showed above the new analyzer's.

### Qt objects are freed on the UI thread

*[src/gui/main_window.py:1334](../src/gui/main_window.py#L1334)*

Delete the closed dialog here, on the UI thread, rather than leave it to Python's garbage collector, which frees whatever is garbage on whichever thread is allocating at the time. That was the engine thread replaying the log after the restart, and freeing the dialog's Qt objects there aborted the app (settings crash, 0.6.7)

## Reviews: a thread of their own, and where a large log is cut

### src/review_load.py

*[src/review_load.py:1](../src/review_load.py#L1)*

Replaying a log for review (issue #107): the engine side of "Open log for
review…", with no Qt in it, so it runs on a thread of its own while live
monitoring keeps its poll.

A large log is first outlined: one pass over the line heads that finds each
session's start (``BEGIN_LOG``) and counts its fights (``BEGIN_COMBAT``),
so the window can offer the whole log or only its most recent sessions.
The cut is always at a session start. Starting in the middle of a session
was measured and rejected: the roster lines alone do not carry what the
engine learns from the rest of the session (who owns which companion and
pet), and on a Dreadsail Reef split every one of the last 18 fights came
out different. A replay from a ``BEGIN_LOG`` matched a replay of the whole
file in 75 of 75 fights (once champion points followed the log).

Lines before the first session read are skipped unparsed, so a cut log
costs a pass over its head plus the engine's time for the rest. The engine
runs at about 10 MB/s on the maintainer's machine, which the time estimate
uses.

### src/gui/review_runner.py

*[src/gui/review_runner.py:1](../src/gui/review_runner.py#L1)*

A review on a thread of its own (issue #107). Until 0.21 a review ran on
the engine thread, whose poll timer then waited for it: a month-sized log
took 8.6 minutes with no live fights shown. Now the engine polls on while a
review replays through an analyzer of its own.

The thread holds no Qt object. It reports through *notify*, which the
window turns into a signal on an object living on the UI thread (as split
retention does), so nothing Qt is created or freed here; the analyzer and
its fights are plain Python. The settings are a snapshot taken when the
review starts, since Settings may change them meanwhile.

## Updates: the schedule, the conditional request and the button

### src/update_check.py

*[src/update_check.py:1](../src/update_check.py#L1)*

Update check against GitHub releases (stdlib only, no extra dependencies).

Queries the repository's latest release and compares its tag against the
running version. Network problems are never fatal: every failure is a
result the caller can read, and the app carries on.

Design: the check repeats every 15 minutes while the app runs (issue #56,
2026-10-26; gui/update_poller.py has the schedule), so it is conditional.
GitHub returns an ``ETag`` with every reply; sent back as
``If-None-Match``, an unchanged release is answered ``304 Not Modified``
with no body. GitHub limits unsigned requests to 60 an hour per address
and does not count a 304 against that limit, so four checks an hour cost
nothing while nothing changes, and a household of several copies behind
one address stays far under the limit; a plain GET each time would spend
four of the 60 per copy for a few KB of unchanged JSON. A limit reply
(403 or 429) names a reset time in ``X-RateLimit-Reset`` (epoch seconds)
or ``Retry-After`` (seconds); the result carries it, capped at an hour
from now, and the poller makes no request before then. The ETag is kept
for the run only, so each start sends one full request.

The release body is GitHub's generated notes (one line per pull request
and a compare link), shown in the ⓘ popup beside the Update button; the
release date comes from ``published_at``.

Two channels (issue #134, 2026-10-29). Stable reads ``/releases/latest``,
which GitHub never points at a prerelease or a draft, so it follows a
release made Stable, or taken back, exactly. Beta reads the newest ten
releases (``/releases?per_page=10``, about 80 KB for a full reply, then
304s like the latest endpoint) and offers the highest version among them,
prerelease or not. Every release is published as a prerelease, a beta, and
a promotion makes one a full release (scripts/promote_release.py), so Beta
gets each release at once and Stable the ones made Stable; until the first
beta (0.26.0 and before) every release was a full one. A demoted release
is a draft again, which neither endpoint shows without a login. A release
counts only when its tag is exactly
``vX.Y.Z``: the list also carries data releases (``esobuild-assets-<update>-
<date>``), and a search for three dotted numbers anywhere in a tag would
read any such tag as a version. Neither channel offers a version lower
than the one running, so someone who leaves Beta keeps the version they
have until a Stable release passes it.

### src/gui/update_poller.py

*[src/gui/update_poller.py:1](../src/gui/update_poller.py#L1)*

The update poller: when the app asks GitHub for a newer release, and on
which thread.

Design: the check runs 3 s after the window is built and then every
``update.check_interval_min`` minutes (default 15), for as long as the
Settings box is ticked, so an app that runs through a raid night learns of
a release published after it started. Issue #56 (2026-10-26) asked for
this in place of the one check at startup and the pop-up it opened.

Each check is a conditional request: the ETag GitHub returned with the last
full reply goes back as If-None-Match, and an unchanged release is answered
304 with no body, which GitHub does not count against its limit of 60
unsigned requests an hour per address (update_check has the figures). A
rate-limit reply names a reset time, and no check runs until then.

The network call and the installer download run on a daemon Python thread,
not on the engine thread as they did until 0.14.2: there a wedged network
stalled fight updates for the 10-second timeout, and a download for its
whole length; once per run that was bearable, every 15 minutes it is not.
The thread calls update_check functions only, creates no Qt object and
holds no widget, and hands its result back through a signal carrying plain
data, which Qt queues to this object's thread, the UI thread (see
engine_worker.py and the 0.6.x settings crash for why a Qt object must
never be freed off the UI thread). One check or download runs at a time; a
tick during one is skipped. A result that arrives after stop() is dropped
(the generation counter), so a closing window never hears from a late
thread.

start() clears the ETag so its first request is a full one: Settings saved
with the check on also clears a skipped version, and a 304 would otherwise
hide the release that was skipped and is wanted again.

Each check reads the channel from the config (``update.channel``, issue
#134). The two channels ask different endpoints, and the channel changes
only through a Settings save, which calls start(): that clears the ETag, so
no validator is ever sent to the other endpoint. start() also withdraws an
offer the previous channel made at once, rather than when (or if) the
first check on the new channel succeeds: someone who leaves Beta while
offline or rate limited must not be left one click from the beta they
opted out of.

### src/gui/update_popup.py

*[src/gui/update_popup.py:1](../src/gui/update_popup.py#L1)*

The ⓘ popup beside the Update button: the release on offer, its date, its
notes as GitHub publishes them, links to the release page and the
changelog, and the way to skip the version. A Qt.Popup frame like
BuildIssuesPopup: it closes on a click elsewhere or Esc and deletes itself,
and nothing keeps a reference to it.

The notes are GitHub's generated release notes (one line per pull request
with its link, and a compare link), rendered from markdown; the
maintainer chose them on 2026-10-26 over the CHANGELOG entries, which run
to a dozen lines each and are one click away through the Changelog link.
The notes are the offered release's own, so someone several releases
behind (a Stable user, issue #134, skips every beta in between) would see
only the last step; the "Changes since" link compares the running version
with the offered one on GitHub, however many releases lie between.

## Releases: every tag a beta, and a beta made Stable

### scripts/release.py

*[scripts/release.py:1](../scripts/release.py#L1)*

Make a release's commit, or tag a release once its pull request is merged.

Design (issue #134, task 2.5; the maintainer's decisions 11 and 12 of
2026-10-29): every session cut releases its own way, and almost every pull
request edited the same lines of two shared files, the top of
CHANGELOG.md and docs/design.md, so each merge put every other open pull
request in conflict (24 merges of main into PR branches in five days).
Three changes together end that:

- A change adds its notes as a fragment, ``changelog.d/<issue>-<slug>.md``,
  written under the same ``### Added`` / ``### Changed`` / ``### Fixed``
  headings CHANGELOG.md uses. Two pull requests never edit the same file,
  and the CI check (scripts/changelog_check.py) asks every pull request for
  one.
- ``docs/design.md`` is rebuilt in the release commit only. Between
  releases the docstrings it is built from are the source; a tag whose
  design notes lag the code is refused, here before the tag is made and in
  the tag's workflow run before either build (build_design_doc --check).
- This script makes the release commit's edits the same way every time:
  the version in src/version.py, the fragments gathered under
  ``## [X.Y.Z] - YYYY-MM-DD`` at the top of CHANGELOG.md (an
  ``[Unreleased]`` section a branch from before fragments still carries at
  the top is folded in, not lost), the fragments removed, the design notes
  rebuilt, and one commit, ``chore: release X.Y.Z``. Sections come out in
  Keep a Changelog's order and, within a section, in fragment file name
  order, so the same fragments always give the same text. Everything that
  can refuse (an unreadable fragment, one git does not track yet, a design
  note that cannot be built) is checked before the first file is written,
  so a refusal never leaves a release half made.

The release commit goes inside the last pull request of the release, or one
of its own, since main takes pull requests only. The script refuses to
commit on main or over uncommitted changes, and the version must be higher
than the current one. ``minor`` or ``patch`` picks the next number; the
choice stays the releasing session's (a release with only Fixed entries is
a patch).

A fragment can reach the release branch after the release commit: the
branch must be up to date with main to merge, and a merge of main brings in
whatever merged meanwhile. Its change would ship in the build while its
note waited for the next release. The Changelog check refuses a release
pull request that still holds fragments, and ``--tag`` refuses such a merge
commit; the remedy is to drop the release commit (``git revert``) and run
the script again.

Once the pull request is merged, ``--tag X.Y.Z`` finds the commit on
origin/main that first carries the version (the merge commit, on main's
first-parent line), runs the release job's tag checks on it
(scripts/release_guard.py), checks its design notes and its changelog.d/,
and makes the annotated tag. Pushing the tag publishes a beta to every
install on the Beta channel, so it happens only with ``--push``, and
``--dry-run`` runs every check and makes nothing. ``--watch`` then follows
the tag's workflow run and checks what it published: a pre-release with
all three files, and ``/releases/latest`` (Stable) not moved. Making a beta
Stable stays scripts/promote_release.py's, on the maintainer's word.

Needs git; ``--watch`` needs the GitHub CLI, logged in.

```
    python scripts/release.py minor|patch|X.Y.Z [--date YYYY-MM-DD] [--trailer TEXT] [--dry-run]
    python scripts/release.py --tag X.Y.Z [--dry-run | --push [--watch]]
```

### scripts/changelog_check.py

*[scripts/changelog_check.py:1](../scripts/changelog_check.py#L1)*

Check a pull request's changelog fragment and its hands-off files.

Design (issue #134, task 2.5): changes write their notes as fragments in
changelog.d/ and the release commit (scripts/release.py) gathers them into
CHANGELOG.md and rebuilds docs/design.md. A pull request that is not a
release is refused when it:

- adds no fragment of its own (a new ``changelog.d/<name>.md``, directly in
  the folder, not the README), unless it carries the ``no-changelog``
  label: its change would reach the release notes only if someone
  remembered. Editing a fragment already there is not a note of its own,
  and a file in a subfolder is one the release script never reads;
- edits CHANGELOG.md: that edit is what put every open pull request in
  conflict with the others;
- edits docs/design.md: the same, for the design notes, which the release
  commit rebuilds from the docstrings.

The label waives the first rule only: the other two are the conflicts the
whole change exists to end.

A release is a pull request that changes ``__version__`` (read from the
merge base and the head, so an unrelated edit of src/version.py is not
one). It does all three by design and passes, unless changelog.d/ still
holds fragments at its head: they came in with a merge of main after the
release commit, their changes would ship in the release and their notes
in the next one. Reverting the release commit and running the release
script again gathers them.

The fragment's text is not checked here: scripts/release.py refuses one it
cannot read when the release is cut, and the unit tests run the same parser
over every fragment on the branch.

```
    python3 scripts/changelog_check.py <base sha> <head sha> [--labels a,b]
```

### scripts/release_guard.py

*[scripts/release_guard.py:1](../scripts/release_guard.py#L1)*

Check a version tag before the release job publishes it, and name the
tag its notes start from.

Design (issue #134, 2026-10-29): the release job publishes whatever tag
reaches it, and nothing checked the tag until now. Three refusals, each
before anything is published:

- the tag must be exactly ``vX.Y.Z``: the app's update check counts only
  such tags, and data releases (``esobuild-assets-<update>-<date>``) are
  created by hand, never by this job;
- it must equal ``v`` + ``__version__`` in the tagged commit's
  ``src/version.py`` (read from the commit, not the checkout): the assets
  are named from that file, and the app compares its own version with the
  tag, so a mismatch would offer an installer that reports the wrong
  version (a tag pushed on the wrong commit, or a release commit missing);
- its commit must be on ``main`` (``git merge-base --is-ancestor``): tags
  are outside the branch ruleset, so a tag on an unmerged branch would
  publish code no pull request merged.

The previous ``v*`` tag (``git describe`` from the tagged commit's first
parent, which for a merge commit is main as it was) goes to the job's
output as ``previous``: GitHub's generated notes then cover the changes
since the release before this one, whichever release GitHub would
otherwise have picked as the base. Every release is now born a beta, and
with a Stable release as the latest GitHub may compare against that.

Standard library and git only; the job runs it on the runner's own Python.

```
    python3 scripts/release_guard.py <tag> <commit> [--main-ref origin/main]
```

### scripts/promote_release.py

*[scripts/promote_release.py:1](../scripts/promote_release.py#L1)*

Make a beta the Stable release, take a Stable release back, list the
betas that could be promoted, or open a reminder when Stable falls behind.

Design (issue #134, the maintainer's decisions of 2026-10-29): every tag is
published as a GitHub pre-release, a beta. Promoting turns that same
release into a full one and marks it latest, so Stable users run exactly
the build beta users ran, and ``/releases/latest``, which the app's Stable
channel and the home page read, moves to it. Nothing is rebuilt or
retagged.

A beta may be promoted when:

- it is newer than the Stable release and carries all three files;
- it was published at least 48 hours ago;
- the maintainer used it live, in at least one session with fights; the
  script cannot see that, so ``--used-live`` says so;
- no issue labelled ``regression`` affects it. A regression issue names the
  version that brought the fault in as the first ``X.Y.Z`` in its title
  (never its body, where a pasted "Python 3.14.10" would read as a
  version). While open it affects that version and every later one; once
  closed, those published before it was closed, since the fix can only be
  in a later release. So a fixed regression still marks the versions that
  carried it, which is the rule "no later beta fixes a fault in it". A
  regression whose title names no version affects every release until its
  title does: a rule that cannot be read must stop a promotion, not let it
  through. An issue that turns out not to be a regression loses the label.

``--force "<reason>"`` overrides the last three rules and writes the reason
into the release notes (a crash fix that cannot wait two days); the first
is never overridden.

The release notes are rewritten as the changes since the previous Stable
release: every pull request line of the releases in between, oldest first,
without repeats, and the compare link. The app's update popup shows a
Stable user these notes, and a Stable user skips every beta in between.

``/releases/latest`` can lag a minute behind a change (seen on
2026-10-28), so the check of it retries once. The script then starts the
Pages workflow, which rebuilds the home page's buttons on main: a
``release`` event would run on the tag, and the github-pages environment
deploys from main only.

``--demote`` pulls a bad Stable release: it becomes a draft again and the
previous Stable release is marked latest. A draft is invisible to the app
(both channels read without a login, which never sees drafts), to the home
page and to ``--candidates``; left a pre-release it would still be the
newest beta, offered on Beta and on the home page. Installs that already
updated keep it. ``gh release edit <tag> --draft=false --prerelease``
publishes it again as a beta.

``--candidates`` lists the betas newer than Stable and what each still
lacks: a session uses it to propose a promotion, never to make one.
``--remind`` (the weekly workflow) opens an issue when the oldest beta that
meets the time and regression rules was published more than 14 days ago,
which is a beta that has waited two weeks for a decision, unless one is
open already.

Needs the GitHub CLI, logged in (``GH_TOKEN`` in a workflow).

```
    python scripts/promote_release.py vX.Y.Z --used-live [--dry-run]
    python scripts/promote_release.py vX.Y.Z --force "crash fix" [--dry-run]
    python scripts/promote_release.py --demote vX.Y.Z [--dry-run]
    python scripts/promote_release.py --candidates
    python scripts/promote_release.py --remind [--dry-run]
```

### scripts/build_site.py

*[scripts/build_site.py:1](../scripts/build_site.py#L1)*

Build the home page (site/) into _site/ for GitHub Pages.

The page is a hand-written index.html whose download buttons need the
current release: the release assets carry the version in their names
(esolog-tail-windows-setup-0.13.3.exe), so no fixed link can point at the
latest installer. This script reads the latest release from the GitHub API,
fills the page's placeholders, and copies the page, its favicon and social
card, and the screenshots it uses from docs/screencaps/ into _site/.
.github/workflows/pages.yml runs it and publishes _site/.

Placeholders in index.html are {{name}} for the names in release_values()
plus {{site_url}} and {{beta_line}}. A placeholder left unfilled, a missing
asset or an unreadable release fails the build: a page with holes must not
be published.

The buttons name the latest release, which is the Stable one: every release
is published as a pre-release, a beta, and only a promotion makes one the
latest (issue #134). {{beta_line}} is a smaller line under them naming the
newest beta when one is newer than Stable (the maintainer's choice of
2026-10-29), and nothing otherwise. It is a nicety: if the release list
cannot be read, the page is built without it rather than not at all. It
says to choose Beta in Settings, since the app starts on Stable whichever
installer it came from. The beta is picked by the app's own
``update_check.newest_release`` (src/, standard library only), so the page
and the app's Beta channel cannot disagree on which release is the beta.

Standard library only, so the Pages job installs nothing.

## Taunt marks that pulse in a text page

### ringed

*[src/gui/icon_cache.py:26](../src/gui/icon_cache.py#L26)*

A copy of *image* with a ring of *color* just inside its edge: about
an eighth of the icon wide (8 px on the bundled 64 px icons), a dark
hairline outside it so it reads on any icon art, and a light hairline
inside. *phase*, 0 to 1 around one glow cycle, brightens the ring from
the colour itself (0) to a paler, lighter tone (0.5) and back, which the
fight view steps through to make a taunt mark pulse (issue #12).

### FightView._pulse_step

*[src/gui/fight_view.py:347](../src/gui/fight_view.py#L347)*

Design: Taunt marks pulse. A QTextBrowser page cannot animate, but
the document asks for an image's resource each time it paints, and
one set with addResource is taken before loadResource is asked. So
every ringed icon the page has loaded is redrawn at the next phase
of the glow (IconCache keeps PULSE_STEPS images per ring colour) and
the viewport repainted: a few small images and a repaint every
PULSE_INTERVAL_MS, no layout, so the page never moves. The timer
runs only while the page holds a ringed icon and the view is shown.

## Hidden names: the stand-in behind the blur

### src/gui/name_mask.py

*[src/gui/name_mask.py:1](../src/gui/name_mask.py#L1)*

Design: Hidden names. A screenshot of a fight, or a fight pasted into a
chat, shows the handles and character names of everyone in the group. The
Hide names switch (issue #72) keeps the name of the player whose client
writes the log and hides everyone else's, in every place the app shows a
name: the fight pane's rows and hover texts, the build, damage and
death-recap windows, the dps graph's legend, the timeline strip's hover
and pop-ups, and the Copy fight text. Enemy, pet, set and ability names
are never hidden.

Who is kept is read from the log, not configured: the game writes
``isLocalPlayer`` on every player's UNIT_ADDED line, ``T`` for the one
client writing the log (checked over 899 split logs: exactly one per log,
the same handle on 14 characters, the flag in the same place since the
oldest log of 2025). The engine puts it on each fight entry's player as
``is_local``. A reviewed log written by a friend therefore keeps the
friend, which is what "the handle of the person logging" means.

Which names are player names: a name is hidden when it is not the local
player's handle or character name and either starts with ``@`` or is the
character name of another player of the fight. The ``@`` rule reaches
every nested place a handle appears (the source of a heal in a death recap,
a caster in the penetration section, a timeline interval's source and
target) without threading the player list into each; the character-name
set reaches a player the log gave no handle. That set is read from the
entry's ``player_names``, every player unit the engine saw, rows or not:
a player whose PLAYER_INFO never reached the log has no row in the table
but still casts, heals and dies in the fight's other data (the review of
2026-10-27 found the gap when the set was read from the rows alone).
``anon`` (the engine's word for a player with neither handle nor name)
and enemy names fall through, as no enemy, pet, set or ability name
starts with ``@``. An entry with no local player at all hides every name,
the safe direction.

How a hidden name looks: the maintainer asked for a blurred or pixelated
name, the look of a screenshot with the names smudged out. The pages
drawn as rich text (the fight pane and the three windows) get a pixelated
word of the hidden name's length, its ``@`` left readable as text so the
row still reads as a handle. That word is **not** the real name pixelated.
Pixelated or blurred text can be read back when the font, the size and
the rendering are known (they are all public here) and the words are
short, so a picture meant to hide a handle would carry it. Instead the
mask makes a stand-in word from a keyed hash of the name (``stand_in``:
the key is random per run, so the same name gives the same word in every
row, window and pop-up of a run, and nothing persists), draws it in the
page's font at the requested size and weight, downscales it smoothly by
the block size and scales it back with nearest-neighbour. The result has
the blocky texture of a pixelated word, the ascender and descender
pattern of a word nobody has ever seen. The length is kept so the row's
columns stay where they were; a handle's length identifies nobody.

Where text is all there is (a tooltip, the strip's pop-up, the graph's
legend, a window title, the clipboard) a hidden name is ``@`` followed by
one shade block per hidden character: a QLabel cannot ask a view for an
image.

The page asks for the image by URL, ``mask:<word>?color=rrggbb&pt=<n>&b=<0|1>``
(``image_html``), answered by ``FightView.loadResource`` from
``mask_image`` with the view's font family and device pixel ratio, cached
for the run by its parameters, as the link glyphs are (see gui.glyphs).
The word is lower-case letters and underscores for spaces, so the URL
needs no escaping and a malformed one is refused.

## Links in the fight pane: the hover cue and the dps glyphs

### FightView._show_hover_cue

*[src/gui/fight_view.py:219](../src/gui/fight_view.py#L219)*

Design: the hover cue. Underline the hovered player name or dps
figure in the link color; any other target, or none, clears the cue.

A name or dps figure keeps the look of plain text in the page (the
figures carry a glyph beside them, see gui.glyphs; the names do not,
since twelve underlined or blue names would be clutter). Qt rich text
has no hover styling, and changing the document's own character
format on hover would enter the undo stack, relayout the page and
invalidate the cursors the in-fight search holds. So the cue is an
extra selection: a format painted over a text range without touching
the document. The search's highlights are extra selections too, and
setting one list replaces the other, so the view owns both lists and
applies their union. The selection covers the anchor's text and stops
at its glyph, which is an image fragment of the same anchor; the
glyph still triggers the cue and the tooltip, since the pointer on it
is the pointer on the anchor.

### src/gui/glyphs.py

*[src/gui/glyphs.py:1](../src/gui/glyphs.py#L1)*

Design: Link glyphs. The fight pane has three kinds of link that are not
ESO-Hub pages: a player's name opens their build window, their dps figure
their damage window, and the header's group dps figure the dps over time
graph. All three are drawn as plain text in the pane's own colours, by
choice: twelve underlined or blue names in a trial fight would be clutter,
and the name is the row's identity. The cost is that nothing says they can
be clicked until the pointer is on them (the hover cue, see
FightView._show_hover_cue), and the two dps figures suffered most: the
group figure sits in the muted stats line where nothing else is clickable,
and the damage window has no other way in at all (issue #34).

So the two figures carry a small glyph inside their anchor, drawn here with
QPainter rather than shipped as a file: after the group figure, a short
polyline in the graph's own line style (about 2 px, round joins) in the
theme's link colour, the one coloured mark in that grey line; after each
player's figure, three bars, longest on top, in the muted colour, since
there are up to twelve of them. Being inside the anchor, a glyph is part
of the click target and of the hover: the view underlines the text beside
it and shows the same tooltip. The glyph follows the pane's font size and
is drawn at the view's device pixel ratio, so it stays crisp on a scaled
display (Qt lays out an image that carries a device pixel ratio at its
logical size). Names stay plain, with their hover cue.

The (i) of possible build issues is drawn here too (issue #140). It was the
font's ⓘ in the link colour after the class text, where it drifted right
with the text's length, thin and among muted words, and was easy to miss;
the first-damage * after the name was the mark people saw. It now sits on
the name, after the *, bold with a faint halo of its own colour. Qt rich
text has no text-shadow, filter or opacity, so the glow cannot come from
the page: the glyph is a ring about the size of the font's ⓘ (11.5 px of
11 at 9 pt), half again as heavy, over a radial gradient that is clear
inside the ring, about two fifths opaque at its outer edge and nothing at
the image's edge; the clear inside keeps the i at the link colour's full
contrast (issue #77). The image is as tall as the text line, so the halo
has 2 to 3 px around the ring, and aligned to the line's top: Qt centres
a middle-aligned image on half the x-height above the baseline, which
pushed a line-tall image 2 px under the line and made each marked row
taller. The main window passes the fight view's line height into the page
(render_html's line_px), so the image fits whatever font the system gives;
without it the page estimates the line as 1.3 em, Segoe UI's. A death
chip or a hidden name's stand-in on the same line adds only descent, so
the line's top, and the ring with it, stays level with the name. At 100%
scaling the ring's inside is 8 px tall, and a dot and stem placed freely
ran together into a bar touching the ring, so the i is laid out in whole
device pixels from the image's own width (issues_i_layout): a 2 px dot, a
clear pixel, a 3 px stem, and a clear pixel above and below. No
pulse: a still mark, so Reduce motion has nothing to stop. The fight
list's ⓘ is list text, which cannot be bold or glow without a delegate,
and the popup is a label that cannot serve these images; the build window
shows the popup's list, so all three keep the font's ⓘ.

The page asks for a glyph by URL, ``glyph:<kind>?color=rrggbb&px=<n>``
(fight_render.glyph_html), which FightView.loadResource answers from here:
one image per kind, colour, size and ratio, kept for the session.

## The text size

### src/gui/text_size.py

*[src/gui/text_size.py:1](../src/gui/text_size.py#L1)*

The app-wide text size (issue #77): one percentage of the system font,
saved as display.text_scale, set from Settings or with Ctrl+=, Ctrl+- and
Ctrl+0.

Design: the size is applied with QApplication.setFont, so every widget
that has not set a font of its own follows it, and every rendered page,
which sizes its text from its view's font (base_pt), follows it on the
next render. What is drawn in pixels rather than points (the timeline
strip's rows and label column, the dps graph's margins and legend, the
icons in rendered pages) asks scale() and grows with it, but never
shrinks below its size at 100%: icons and rows that small stay legible,
and at 100% everything is drawn exactly as before the setting existed.

The system font is read once, before the first change, and every
percentage is of that font, so stepping up and back down returns to the
same size rather than drifting with rounding. Qt is imported only where a
font is set, so the page renderers can ask scale() without it.

QApplication.setFont posts the change to each widget rather than sending
it, so straight after it every view still reports the old font, and a page
rendered then from its view's font comes out at the old size (the
Settings path did just that: Save, redraw, old size). apply() delivers the
posted font changes before it returns.
