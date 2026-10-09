# Design notes

How ESO Log Tail solves the problems that are not obvious from the code's
shape: what the encounter log really carries, which game data is trusted
for what, and the rules chosen after measuring real logs. Every note here
is the docstring or a tagged comment of the code it describes, collected by
`scripts/build_design_doc.py`; edit the code, then rerun the script. The
link under each note is where it lives.

## The encounter log: unit states and effects

### ESOLogAnalyzer._handle_effect_changed

*[src/esolog_tail.py:1810](../src/esolog_tail.py#L1810)*

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

*[src/esolog_tail.py:66](../src/esolog_tail.py#L66)*

The game ends and restarts combat in the middle of a fight, most often when the logging player is resurrected: END_COMBAT, then BEGIN_COMBAT a moment later. 48 logs of April to October 2026 held 53 such pairs, 0 to 484 ms apart, 45 of them straight after the player accepted a resurrection. A BEGIN_COMBAT this soon after END_COMBAT continues that fight when an enemy the group hit in the fight's last seconds is still alive; none of the 51 pairs between half a second and three seconds apart was the same pull.

### ESOLogAnalyzer._continues_last_fight

*[src/esolog_tail.py:1291](../src/esolog_tail.py#L1291)*

Whether a BEGIN_COMBAT at *timestamp_ms* carries on the fight that
just ended instead of starting one (see COMBAT_RESUME_MS): it follows
the END_COMBAT closely, and an enemy the group was hitting when the
fight ended is still alive.

### ESOLogAnalyzer._resume_last_fight

*[src/esolog_tail.py:1306](../src/esolog_tail.py#L1306)*

Reopen the encounter END_COMBAT closed. Its damage, deaths and
players are kept, and the entry frontends already have is brought up
to date when the fight ends (see _publish_fight).

### A death just after END_COMBAT

*[src/esolog_tail.py:60](../src/esolog_tail.py#L60)*

The blow that kills the last player standing ends combat, and that player's death event is written after END_COMBAT (about 85 ms later in live logs). A player death this soon after END_COMBAT belongs to the fight that just ended.

## Starting mid-session

### LogFileMonitor._load_latest_session

*[src/esolog_tail.py:2861](../src/esolog_tail.py#L2861)*

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

*[src/esolog_tail.py:302](../src/esolog_tail.py#L302)*

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

Which class skill lines a player's abilities come from (subclassing).

Design: since Update 46 a character can swap any of its three class skill
lines for another class's, so the class id in UNIT_ADDED no longer says
what a build is. The log names each slotted ability (ABILITY_INFO), and
every class ability, morphs included, belongs to exactly one skill line, so
the lines are inferred from the names: SKILL_LINE_ABILITIES lists every
class line with its ultimate, actives and morphs, as the game names them.
A player's slotted abilities are matched to those names exactly (never by
substring: "Carve" is Two Handed, not Fatecarver; "Swarming Scion" is
Vampire, not a Warden Swarm) and the lines with the most matches win, at
most three, since subclassing swaps lines and never adds a fourth. Weapon,
guild, world and alliance abilities match nothing and are ignored. The
fight view shows the inferred lines beside the class only when they differ
from the class's own three (PlayerInfo.get_class_skill_lines), so a stock
build shows just its class. A player with no class ability slotted shows no
lines.

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
Two families are extracted: ability_*.dds (player skills, for the ability
bars) and death_recap_*.dds (what monster attacks use, for death recaps).
Run this after each ESO update to refresh that set.

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

*[src/effect_rules.py:512](../src/effect_rules.py#L512)*

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

*[src/esolog_tail.py:565](../src/esolog_tail.py#L565)*

What effect_rules measures a fight's rules on, unit id -> (kind,
since_ms, gone_ms): the players ('self' or 'group'), and the
hostiles the group hit in this fight ('boss' or 'enemy', by the
game's flag) with the log time each was added and the time it died
or was removed, None when it was there throughout. Enemies carry
over from fight to fight within a zone, so a boss that only stands
in the list, dead since the last pull, is not a boss of this fight:
it has to have been hit.

### AppConfig.reload

*[src/app_config.py:74](../src/app_config.py#L74)*

Read the file over DEFAULTS. A rules text saved before the uptime
line's group buffs and taunt became rules (tracking.version absent,
0.8.0 and earlier) kept only the user's own additions, so the line
would lose those items on upgrade: the missing ones are put in
front of it, by name, so a rule the user had already written under
the same name stays theirs. Nothing is written back; the version
is saved with the next Save, and the top-up is harmless to repeat.

## Taunts

### Taunts

*[src/esolog_tail.py:75](../src/esolog_tail.py#L75)*

The game puts one Taunt debuff on a taunted enemy whatever skill taunted, and writes a TAUNTED combat event that shares its cast tracking id with that skill's own cast and hits, which is how the skill is known: no list of taunt skills is needed, and a skill logged under another id (Destructive Clench with an ice staff is logged as Frost Clench) is matched to its bar slot by the icon the two share (mark_taunt_slots). The debuff's spans on each enemy give the uptime line's Taunt item through the default rule ``Taunt = 38254 on boss each`` (effect_rules): each boss's taunted share of its time in the fight, averaged over the bosses, the pack's mobs in a fight without a boss. Checked on 1,361 taunts in twelve logs of October 2026.

### mark_taunt_slots

*[src/esolog_tail.py:352](../src/esolog_tail.py#L352)*

Put 'taunt': True on each bar slot the player taunted with: the slot
whose ability id a taunt names, or, for a taunt logged under an id no
slot has, the slot that shares its icon (Destructive Clench taunts as
Frost Clench, a separate id with the same icon).

## Pets: whose damage and healing they are

### CombatEncounter.track_pet_ownership

*[src/esolog_tail.py:430](../src/esolog_tail.py#L430)*

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

*[src/esolog_tail.py:521](../src/esolog_tail.py#L521)*

Credit damage dealt by *unit_id* to the player it belongs to:
the player themself, or the owner of a pet (see
track_pet_ownership). Damage from a unit that is neither is
counted for nobody: a boss's summons, trial mechanics that hit
other enemies, and the like.

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

## The GUI and the engine thread

### src/gui/engine_worker.py

*[src/gui/engine_worker.py:1](../src/gui/engine_worker.py#L1)*

Engine worker: runs the analysis engine on a QThread and bridges
AnalyzerListener callbacks to Qt signals (queued to the UI thread).

Engine modules never import Qt; this adapter is the only crossing point.

### MainWindow._on_monitoring_restarting

*[src/gui/main_window.py:386](../src/gui/main_window.py#L386)*

The engine has begun the restart Settings asked for. Everything
it sent before this belonged to the analyzer being replaced, so the
history is cleared now rather than when Save was pressed: a replay
still running at that moment went on filling a list cleared too
early, and its fights showed above the new analyzer's.

### Qt objects are freed on the UI thread

*[src/gui/main_window.py:687](../src/gui/main_window.py#L687)*

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

*[src/gui/fight_view.py:199](../src/gui/fight_view.py#L199)*

Design: Taunt marks pulse. A QTextBrowser page cannot animate, but
the document asks for an image's resource each time it paints, and
one set with addResource is taken before loadResource is asked. So
every ringed icon the page has loaded is redrawn at the next phase
of the glow (IconCache keeps PULSE_STEPS images per ring colour) and
the viewport repainted: a few small images and a repaint every
PULSE_INTERVAL_MS, no layout, so the page never moves. The timer
runs only while the page holds a ringed icon and the view is shown.
