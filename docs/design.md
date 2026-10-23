# Design notes

How ESO Log Tail solves the problems that are not obvious from the code's
shape: what the encounter log really carries, which game data is trusted
for what, and the rules chosen after measuring real logs. Every note here
is the docstring or a tagged comment of the code it describes, collected by
`scripts/build_design_doc.py`; edit the code, then rerun the script. The
link under each note is where it lives.

## The encounter log: unit states and effects

### ESOLogAnalyzer._handle_effect_changed

*[src/esolog_tail.py:1917](../src/esolog_tail.py#L1917)*

A buff or debuff coming, going or refreshing: the tracked effects
(every item of the uptime line), the experimental timeline, and
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

*[src/esolog_tail.py:67](../src/esolog_tail.py#L67)*

The game ends and restarts combat in the middle of a fight, most often when the logging player is resurrected: END_COMBAT, then BEGIN_COMBAT a moment later. 48 logs of April to October 2026 held 53 such pairs, 0 to 484 ms apart, 45 of them straight after the player accepted a resurrection. A BEGIN_COMBAT this soon after END_COMBAT continues that fight when an enemy the group hit in the fight's last seconds is still alive; none of the 51 pairs between half a second and three seconds apart was the same pull.

### ESOLogAnalyzer._continues_last_fight

*[src/esolog_tail.py:1388](../src/esolog_tail.py#L1388)*

Whether a BEGIN_COMBAT at *timestamp_ms* carries on the fight that
just ended instead of starting one (see COMBAT_RESUME_MS): it follows
the END_COMBAT closely, and an enemy the group was hitting when the
fight ended is still alive.

### ESOLogAnalyzer._resume_last_fight

*[src/esolog_tail.py:1403](../src/esolog_tail.py#L1403)*

Reopen the encounter END_COMBAT closed. Its damage, deaths and
players are kept, and the entry frontends already have is brought up
to date when the fight ends (see _publish_fight).

### A death just after END_COMBAT

*[src/esolog_tail.py:61](../src/esolog_tail.py#L61)*

The blow that kills the last player standing ends combat, and that player's death event is written after END_COMBAT (about 85 ms later in live logs). A player death this soon after END_COMBAT belongs to the fight that just ended.

## Starting mid-session

### LogFileMonitor._load_latest_session

*[src/esolog_tail.py:3036](../src/esolog_tail.py#L3036)*

Replay the log's most recent session up to the attach point.

Gives a mid-session attach the same state as having run since the
session began: full roster, this session's fights in history, and
the session's split file (created only if absent). Best-effort:
failures leave plain tailing, and oversized sessions fall back to
the roster-only preamble sweep.

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

*[src/esolog_tail.py:342](../src/esolog_tail.py#L342)*

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
the build window's mundus and food line too. Two sources name them,
because the PLAYER_INFO list holds only the passives whose effect is always
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
them. The other five (Share the Spoils, Nocturnal Inspiration,
Conservation of Energy, Bastion of Light, Devout Guardian) work through
resources, ultimate or unnamed heals and shields and stay invisible.

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
12.0, carry the werewolf bar in place of the front bar; ``logs_werewolf_bar``
tells such a row, so the bar is not shown twice. Werewolf players spent
1,234 of their 1,524 fights of 5 s or more wholly in form, 110 partly, and
180 not at all.

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
fight's end show it in 94%, which is the rule here. In the only two cases
where the game logged a werewolf bar, the rebuilt bar agreed with it. Casts
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
change here is what ships. Set names are shown as the game spells them: the
workbook's spelling differs for a few dozen sets ("Perfect" for
"Perfected", "Blood Spawn", three Cyrodiil sets one id out of place), so
NAME_CORRECTIONS carries the name from the installed client's own English
string table for each of those ids, and the script reports a correction
the workbook no longer needs. ESO-Hub links for sets are looked up by the
corrected name (see src/ability_icons.py).

## Tracked effects: the uptime line as rules anyone can paste

### src/effect_rules.py

*[src/effect_rules.py:1](../src/effect_rules.py#L1)*

Tracked effects: rules anyone can paste, and the tracker they drive
(engine side, no Qt). Issue #10.

Design: every item on the uptime line is a rule. A rule names an effect by
its ability ids and asks for its uptime or its stack count on a chosen kind
of unit, in a plain text anyone can copy to others. One rule per line::

```
    # Name = ability ids... on <scope> [stacks | each]
    Major Courage = 109966 on group
    Taunt         = 38254 on boss each
    Off-Balance   = 45902 62988 39077 34733 20806 130139 on boss
    Touch of Z'en = 126597 on boss stacks
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
in a fight reads 0% rather than being left off the line. Replaying the
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
any a tracked effect landed on). In those fights Off-Balance reached up to
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

A line that starts with ``$`` is a HyperTools export string, pasted as
is: HyperTools (the in-game tracker addon) serialises a tracker as nested
``$...&`` records, and its name, ability ids and target ("Yourself",
"Group", "Boss", "Current Target") become a rule here; ``stacks`` or
``on <scope>`` after the string override what it says.

What the logs carry (nine trial and dungeon logs of 2026): the stack
count is EFFECT_CHANGED's second field and changes arrive as UPDATED
lines, so stacks are read on GAINED and UPDATED; Off-Balance on a boss
comes under several ids at once (45902 for most sources, 62988 for
Elemental Blockade, 39077, 34733, 20806, 130139), so a union is needed,
and its uptime on a trial boss was 4 to 28% per fight; Crux stacks to 3
on the Arcanist alone; a pet-applied buff (a Glyphic's heal, Major
Protection from a netch) lands on players like any other and needs no
special case, since only the target's kind is looked at. Replaying the
bundled examples through two of those logs (Sunspire, Kyne's Aegis):
Off-Balance on the boss 12 to 28% per boss fight, to the decimal what an
independent scan of the lines gives; Crux on the logging Arcanist a mean
of 1.5 to 2.9 with a peak of 3 in every fight.

### EffectTracker

*[src/effect_rules.py:406](../src/effect_rules.py#L406)*

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

*[src/effect_rules.py:528](../src/effect_rules.py#L528)*

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

*[src/esolog_tail.py:618](../src/esolog_tail.py#L618)*

What effect_rules measures a fight's rules on, unit id -> (kind,
since_ms, gone_ms): the players ('self' or 'group'), and the
hostiles the group hit in this fight ('boss' or 'enemy', by the
game's flag) with the log time each was added and the time it died
or was removed, None when it was there throughout. Enemies carry
over from fight to fight within a zone, so a boss that only stands
in the list, dead since the last pull, is not a boss of this fight:
it has to have been hit.

### AppConfig.reload

*[src/app_config.py:78](../src/app_config.py#L78)*

Read the file over DEFAULTS. A rules text saved before the uptime
line's group buffs and taunt became rules (tracking.version absent,
0.8.0 and earlier) kept only the user's own additions, so the line
would lose those items on upgrade: the missing ones are put in
front of it, by name, so a rule the user had already written under
the same name stays theirs. Nothing is written back; the version
is saved with the next Save, and the top-up is harmless to repeat.

## Taunts

### Taunts

*[src/esolog_tail.py:76](../src/esolog_tail.py#L76)*

The game puts one Taunt debuff on a taunted enemy whatever skill taunted, and writes a TAUNTED combat event that shares its cast tracking id with that skill's own cast and hits, which is how the skill is known: no list of taunt skills is needed, and a skill logged under another id (Destructive Clench with an ice staff is logged as Frost Clench) is matched to its bar slot by the icon the two share (mark_taunt_slots). The debuff's spans on each enemy give the uptime line's Taunt item through the default rule ``Taunt = 38254 on boss each`` (effect_rules): each boss's taunted share of its time in the fight, averaged over the bosses, the pack's mobs in a fight without a boss. Checked on 1,361 taunts in twelve logs of October 2026.

### mark_taunt_slots

*[src/esolog_tail.py:392](../src/esolog_tail.py#L392)*

Put 'taunt': True on each bar slot the player taunted with: the slot
whose ability id a taunt names, or, for a taunt logged under an id no
slot has, the slot that shares its icon (Destructive Clench taunts as
Frost Clench, a separate id with the same icon).

## What counts as damage

### What counts as damage

*[src/esolog_tail.py:93](../src/esolog_tail.py#L93)*

A hit on an enemy is written with one of several results, and the dps figures sum the hit value of these: DAMAGE and CRITICAL_DAMAGE (direct hits), DOT_TICK and DOT_TICK_CRITICAL (each tick of a damage-over-time effect), BLOCKED_DAMAGE (what got through a blocking enemy) and DAMAGE_SHIELDED (what an enemy's damage shield absorbed). That is the set Combat Metrics (LibCombat) sums for damage done, and matches ESO Logs, which counts absorbed damage as damage done. Not counted: IMMUNE (the log writes a hit value the target never took), REFLECTED, FALL_DAMAGE, and the overflow field (overkill past the target's remaining health; Combat Metrics drops it too). Until 0.9.2 only the two direct-hit results counted: measured on 29 of Chris's split logs (990 dungeon and arena fights, 34 trial fights) the ticks were 26% of all damage dealt, and the top player's dps in a boss fight of a minute or more was understated by a median 35% in dungeons and 52% in trials, up to 79%. Shield absorbs were 2% and blocked hits 0.2%.

## Dps time and the damage window: parity with Combat Metrics

### Dps time

*[src/esolog_tail.py:111](../src/esolog_tail.py#L111)*

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

*[src/damage_stats.py:90](../src/damage_stats.py#L90)*

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
order (an eight-slot palette validated for colour-vision deficiency on both
the light and the dark surface), text in the pane's own text colours and
never in a series colour, and the end value of each line labelled when a
panel shows four or fewer.

## Pets: whose damage and healing they are

### CombatEncounter.track_pet_ownership

*[src/esolog_tail.py:478](../src/esolog_tail.py#L478)*

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

*[src/esolog_tail.py:569](../src/esolog_tail.py#L569)*

Credit damage dealt by *unit_id* to the player it belongs to:
the player themself, or the owner of a pet (see
track_pet_ownership). Damage from a unit that is neither is
counted for nobody: a boss's summons, trial mechanics that hit
other enemies, and the like. *to_boss* says the target is a unit
the game flags as a boss, so the hit also counts as boss damage.
With the hit's *timestamp*, *result*, *ability_id* and *target_id*
the hit also goes into the fight's damage record (damage_stats):
the spans the dps figures divide by, and the breakdowns.

## Death recaps

### src/death_recap.py

*[src/death_recap.py:1](../src/death_recap.py#L1)*

Death recap recording: what hit and healed a player in the seconds before
each death, for the GUI's per-player recap.

The analyzer passes every COMBAT_EVENT that lands on a player to record();
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

## Experimental buff timeline

### src/buff_timeline.py

*[src/buff_timeline.py:1](../src/buff_timeline.py#L1)*

EXPERIMENTAL buff/debuff timeline recording (buff-timeline spec).

Records the active intervals of a handful of raid-defining effects with
cast/receive attribution, so the GUI can draw a compact per-fight timeline
strip. Recording is opt-in (`experimental.buff_timeline`); when the analyzer's
gate is off, record() is never called and nothing is retained.

Interval times are raw log-relative milliseconds; snapshot_fight() clips them
to a fight's [start, end] window and rebases them to fight-relative ms.

### EffectTracker.record

*[src/effect_rules.py:441](../src/effect_rules.py#L441)*

An EFFECT_CHANGED line. *target_kind* is what the engine knows
the target to be: 'self', 'group', 'pet', 'boss', 'enemy' or None.

*source_id* is the caster, kept on the span so a row of the uptime
strip can say who applied it ("" when unknown). Another caster
refreshing the effect ends one span and starts the next, so each
span is credited to whoever last applied it; the spans abut, and
every measurement takes their union, so no number changes.

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

## The GUI and the engine thread

### src/gui/engine_worker.py

*[src/gui/engine_worker.py:1](../src/gui/engine_worker.py#L1)*

Engine worker: runs the analysis engine on a QThread and bridges
AnalyzerListener callbacks to Qt signals (queued to the UI thread).

Engine modules never import Qt; this adapter is the only crossing point.

### MainWindow._on_monitoring_restarting

*[src/gui/main_window.py:452](../src/gui/main_window.py#L452)*

The engine has begun the restart Settings asked for. Everything
it sent before this belonged to the analyzer being replaced, so the
history is cleared now rather than when Save was pressed: a replay
still running at that moment went on filling a list cleared too
early, and its fights showed above the new analyzer's.

### Qt objects are freed on the UI thread

*[src/gui/main_window.py:781](../src/gui/main_window.py#L781)*

Delete the closed dialog here, on the UI thread, rather than leave it to Python's garbage collector, which frees whatever is garbage on whichever thread is allocating at the time. That was the engine thread replaying the log after the restart, and freeing the dialog's Qt objects there aborted the app (settings crash, 0.6.7)

## Taunt marks that pulse in a text page

### ringed

*[src/gui/icon_cache.py:26](../src/gui/icon_cache.py#L26)*

A copy of *image* with a ring of *color* just inside its edge: about
an eighth of the icon wide (5 px on the bundled 40 px icons), a dark
hairline outside it so it reads on any icon art, and a light hairline
inside. *phase*, 0 to 1 around one glow cycle, brightens the ring from
the colour itself (0) to a paler, lighter tone (0.5) and back, which the
fight view steps through to make a taunt mark pulse (issue #12).

### FightView._pulse_step

*[src/gui/fight_view.py:205](../src/gui/fight_view.py#L205)*

Design: Taunt marks pulse. A QTextBrowser page cannot animate, but
the document asks for an image's resource each time it paints, and
one set with addResource is taken before loadResource is asked. So
every ringed icon the page has loaded is redrawn at the next phase
of the glow (IconCache keeps PULSE_STEPS images per ring colour) and
the viewport repainted: a few small images and a repaint every
PULSE_INTERVAL_MS, no layout, so the page never moves. The timer
runs only while the page holds a ringed icon and the view is shown.
