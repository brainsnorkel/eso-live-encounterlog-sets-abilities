"""
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
- **A second copy of a group buff set that gave the group next to nothing**
  (issue #172; 21 copies, by player and set, in 17 of the 379 unique split
  logs of 12 January to 1 November 2026, on 80 fights; the scans below that
  read 378 of them ran before the 379th, a solo dungeon run with no group
  set, was written). The issue proposed each wearer's
  loss: the group's uptime of the set's buff less the same without that
  wearer's spans. The log does not support the reading the issue gave it.
  The game writes one instance of a set's buff per receiver, credited to
  one wearer at a time: in five fights with two full wearers of Pearlescent
  Ward, Lucent Echoes, Spell Power Cure, Master Architect or Powerful
  Assault, no second wearer's GAINED arrived while the first wearer's
  instance was on that receiver (0 of 6,259 lines; over the corpus, 3,797
  of 3.78 million for the three whole-group sets, 0.1%, at handovers). Two
  wearers split the group between them (two Wards, six players each, in a
  Lucent Citadel fight), so what a wearer is credited with is not what the
  group would lose without them. Nor does one wearer of a whole-group set
  reach everyone: with one wearer, living players had Pearlescent Ward a
  median 89.6% of their living time in groups of 9 to 12 (698 fights),
  Lucent Echoes 88.7% (737), Xoryn's Masterpiece 87.3% (341), and within
  the same sessions a second Ward added 9 points (two sessions), a second
  Echoes a median 6 (four), when the group spread. What the crediting does
  prove is an upper bound: a receiver's buff is one wearer's at a time, so a
  wearer credited with almost none of the other players' time added almost
  nothing. The rule reads each full wearer's credited share of the other
  group members' time, each for the part of the fight they were there (for
  Lucent Echoes the members not wearing it, since its wearers never
  benefit); a player of the zone outside the group is no receiver, or a
  city or Cyrodiil would dilute the share to nothing. A set's buff ids are
  joined per receiver first, so two of its buffs on a player at once
  (Magma Incarnate's Minor Courage and Minor Resolve) count the time once.
  It flags a wearer whose share stayed under
  SECOND_SOURCE_SHARE (2%) in every fight of a minute or more of the
  session that another full wearer was in, provided another wearer's copy
  reached the group in at least one of them: two Master Architects in a
  fight with no ultimate cast both read 0.0, and neither is a second copy
  beside a working one. In those logs' fights of a minute or more with two
  or more full wearers, the lesser copy's share is a median 22% for Spell
  Power Cure, 21% for Lucent Echoes, 28% for Pearlescent Ward, 11% for
  Master Architect and Roaring Opportunist, 8% for Saxhleel Champion and 6%
  for Powerful Assault and Ozezan the Inferno. The rule finds Saxhleel
  Champion and Powerful Assault five times each, Spell Power Cure and Lucent
  Echoes three, Ozezan the Inferno twice, Master Architect, Roaring
  Opportunist and Xoryn's Masterpiece once, and Pearlescent Ward never; one
  is an Echoes and Powerful Assault wearer whose copies reached no one in
  17 Dreadsail Reef fights. A survey that read each player's last
  PLAYER_INFO line found more, among them members who had left or changed
  sets (a Ward "wearer" in four Cloudrest fights who no longer wore it); the
  engine judges each fight's own build. The sets judged are those
  whose value is the buff they give others (GROUP_BUFF_SETS); a set whose
  buff is its wearer's own (Kinras's Wrath, Huntsman's Warmask) or a
  debuff on enemies is never judged, though data/sets/set_buffs.json lists
  it, since a second copy of a damage set stacks. The buff's spans are kept
  per wearer and receiver (GroupBuffCredit), not taken from the uptime
  rules, which the reader can edit away.
- **A second Enlivening Overflow or From the Brink slotted** (issue #172).
  A player who slots either Champion Point star lists it in the PLAYER_INFO
  long-term effects (156008, 156017), and its procs name the holder as
  source: Enlivening Overflow writes 156012, the 6 s buff on the healed
  player, and 156011, a hidden effect of 12.0 s (231,505 of 250,241 lasted
  11 to 13 s, the rest ended with a death); From the Brink 156020, the
  shield (its value in the target's shield field), and 156019, hidden, 30.0
  s (2,707 of 4,573). The hidden effect is the per-target cooldown, and every
  holder shares it: of 282,366 Enlivening Overflow procs, 2 landed on a
  player while another holder's stood on them (105 while the same
  holder's did); of 4,572 From the Brink procs, none. Holders take turns.
  With one holder the 6 s buff covered a median 32% of a 12-player group's
  time (578 boss fights), with two 36% (295): a second adds about four
  points against a ceiling of 50%. So the rule counts each holder's procs
  over the session's fights of a minute or more that had two or more
  holders: an Enlivening Overflow holder whose procs stayed under
  STAR_EVEN_SHARE (30%) of an even share of them (15% of the procs with
  two holders, 10% with three; seven holders sharing evenly are never
  flagged, where a fixed 15% would flag all of them) is flagged, and a From
  the Brink holder who never procced while another did (the star needs a
  heal on a player under 25% health, which a damage dealer who slots it
  rarely gives). Either is judged only once the other holders have procced
  STAR_MIN_OTHER_PROCS (5) times in the fights counted: of the 10 From the
  Brink holders still at no proc when their session ended, five sat beside
  a holder with one or two procs, which two equal holders leave half the
  time. The procs are counted per fight (CombatEncounter.note_star_proc)
  from the fight's BEGIN_COMBAT: the zone's first encounter is made before
  the pull and reused, and the procs while the group buffed up are not
  the fight's. A player key that names a unit only until the zone changes
  ('unit:<id>') is retired then (BuildIssueTracker.retire_players), so a
  new player on that unit id inherits none of these records.

The lists a later rules text could lift out (the maintainer's separate
issue) are module data: GROUP_SETS, GROUP_BUFF_SETS, PROC_SETS, SLAYER_SETS,
STARS, ELEMENTAL_DRAIN_IDS, OAKENSOUL_SET_ID, the taunt and pull tables,
the weapon lines table. The checks themselves are code.
"""

import json
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

from ability_icons import bundle_root
from damage_kinds import ESOHUB_CP
from effect_rules import group_size_class
from player_build import (
    ARMOR_SLOTS,
    NO_VALUE,
    armor_weight,
    enchant_label,
    food_buff,
    food_table,
    piece_counts,
    weapon_type,
    weapon_type_label,
)
from scribing import GRIMOIRE_ICON_PREFIX, GRIMOIRES

WEAPON_LINES = ("Two Handed", "One Hand and Shield", "Dual Wield", "Bow",
                "Destruction Staff", "Restoration Staff")
# The two bars: (name, main-hand slot, off-hand slot)
BARS = (("front", "MAIN_HAND", "OFF_HAND"), ("back", "BACKUP_MAIN", "BACKUP_OFF"))
_TWO_HANDED_TYPES = frozenset({"greatsword", "battle_axe", "maul"})
_ONE_HANDED_TYPES = frozenset({"axe", "mace", "sword", "dagger"})
_STAFF_LINES = {"inferno_staff": "Destruction Staff", "ice_staff": "Destruction Staff",
                "lightning_staff": "Destruction Staff", "restoration_staff": "Restoration Staff"}
# The weapon line of each grimoire whose skills need a weapon (scribing.GRIMOIRES)
GRIMOIRE_LINES = {
    "Shield Throw": "One Hand and Shield", "Smash": "Two Handed", "Vault": "Bow",
    "Traveling Knife": "Dual Wield", "Elemental Explosion": "Destruction Staff",
    "Mender's Bond": "Restoration Staff",
}
NIRNHONED_WEAPON_TRAIT = "WEAPON_NIRNHONED"
# Elemental Drain at ranks I to IV (UESP playerSkills)
ELEMENTAL_DRAIN_IDS = frozenset({"39095", "41559", "41563", "41567"})
OAKENSOUL_SET_ID = "658"
HEAVY_PIECES_FLAGGED = 2  # the maintainer's threshold; one piece is the Undaunted Mettle norm
LONG_FIGHT_S = 60.0  # a fight long enough for a proc set to have had its chance
# The group buff sets that must be active on both bars, by set id
GROUP_SETS = {
    "648": "Pearlescent Ward", "651": "Perfected Pearlescent Ward",
    "768": "Lucent Echoes", "771": "Perfected Lucent Echoes",
    "769": "Xoryn's Masterpiece", "770": "Perfected Xoryn's Masterpiece",
}
# The sets whose three-piece bonus is Minor Slayer, by set id (UESP's set
# summary by game id): every trial's sets. Oakensoul Ring (OAKENSOUL_SET_ID)
# grants the buff at one piece
SLAYER_PIECES = 3
SLAYER_SETS = {
    "172": "Infallible Mage", "173": "Vicious Serpent",
    "230": "Moondancer", "232": "Roar of Alkosh",
    "331": "War Machine", "332": "Master Architect",
    "389": "Arms of Relequen", "393": "Perfected Arms of Relequen",
    "390": "Mantle of Siroria", "394": "Perfected Mantle of Siroria",
    "444": "False God's Devotion", "449": "Perfected False God's Devotion",
    "445": "Tooth of Lokkestiiz", "450": "Perfected Tooth of Lokkestiiz",
    "496": "Roaring Opportunist", "497": "Perfected Roaring Opportunist",
    "498": "Yandir's Might", "499": "Perfected Yandir's Might",
    "586": "Sul-Xan's Torment", "590": "Perfected Sul-Xan's Torment",
    "587": "Bahsei's Mania", "591": "Perfected Bahsei's Mania",
    "646": "Whorl of the Depths", "653": "Perfected Whorl of the Depths",
    "647": "Coral Riptide", "652": "Perfected Coral Riptide",
    "701": "Peace and Serenity", "708": "Perfected Peace and Serenity",
    "702": "Ansuul's Torment", "707": "Perfected Ansuul's Torment",
    "766": "Mora Scribe's Thesis", "773": "Perfected Mora Scribe's Thesis",
    "767": "Slivers of the Null Arca", "772": "Perfected Slivers of the Null Arca",
    "814": "Harmony in Chaos", "821": "Perfected Harmony in Chaos",
    "815": "Kazpian's Cruel Signet", "820": "Perfected Kazpian's Cruel Signet",
}

# Taunts and pulls, by the ids a bar can carry (UESP playerSkills for every
# rank, plus the ids the bars held in the September and October 2026 logs)
# and by name, for a rank id neither list has
TAUNT_SKILL_IDS = frozenset({
    "28306", "41473", "41475", "41477",  # Puncture
    "38256", "41479", "41483", "41487",  # Ransack
    "38250", "41491", "41494", "41497",  # Pierce Armor
    "39475", "43353", "43358", "43363",  # Inner Fire
    "42056", "43368", "43373", "43378",  # Inner Rage
    "42060", "43383", "43388", "43393",  # Inner Beast
    "183165", "178447",                  # Runic Jolt
    "183430", "187741", "187742",        # Runic Sunder
    "186531",                            # Runic Embrace
})
TAUNT_SKILL_NAMES = frozenset({
    "Puncture", "Ransack", "Pierce Armor", "Inner Fire", "Inner Rage", "Inner Beast",
    "Runic Jolt", "Runic Sunder", "Runic Embrace",
})
# Destructive Clench taunts with an ice staff in hand (it is cast as Frost
# Clench then), and does nothing of the kind with another staff
CLENCH_SKILL_IDS = frozenset({"38984", "40977", "40995", "41006"})
CLENCH_SKILL_NAMES = frozenset({"Destructive Clench"})
PULL_SKILL_IDS = frozenset({
    "20492", "23736", "23740", "23744", "29446",  # Chains of Flame
    "20496", "23770", "23774", "23778",           # Chains of Dominance
    "20499", "32215", "32222", "32229",           # Chains of Devastation
    "40336", "42677", "42687", "42696", "40340",  # Silver Leash
    "86175", "86176", "86177", "86178",           # Frozen Gate
    "86179", "86180", "86181", "86182",           # Frozen Device
    "86183", "86184", "86185", "86186",           # Frozen Retreat
})
PULL_SKILL_NAMES = frozenset({
    "Chains of Flame", "Chains of Dominance", "Chains of Devastation",
    "Fiery Grip", "Unrelenting Grip", "Empowering Chains",  # the chains' older names
    "Silver Leash", "Frozen Gate", "Frozen Device", "Frozen Retreat",
})
# A scribed skill taunts or pulls by its focus script, which names it
TAUNT_FOCUS, TAUNT_PREFIX = "Taunt", "Goading "
PULL_FOCUS, PULL_PREFIX = "Pull", "Leashing "
TANK_HEAVY_PIECES = 5  # heavy pieces that read as a tank's armor
TANK_DAMAGE_RATIO = 0.5  # of an equal share of the group's damage; real tanks sit near 0.1


class ProcSet(NamedTuple):
    name: str
    effect_ids: frozenset  # the effect ids the wearer sources when the set fires
    effect: str  # the effect's name, for the finding
    trigger: str  # what makes the set fire, for the finding
    pieces: int = 5  # worn pieces that make the bonus active (a mythic's one)
    bonus: str = "five-piece bonus"  # how the finding names the bonus


_ALKOSH_EFFECTS = frozenset({"76667", "75751", "75752", "120018"})
_SLAYER_EFFECTS = frozenset({"93109", "135923"})
MARK_OF_HIRCINE_ID = "252048"  # the debuff a Huntsman's Warmask wearer puts on their target
# The proc sets judged over the session, by set id
PROC_SETS = {
    "232": ProcSet("Roar of Alkosh", _ALKOSH_EFFECTS, "Roar of Alkosh",
                   "the wearer activates a synergy"),
    "496": ProcSet("Roaring Opportunist", _SLAYER_EFFECTS, "Major Slayer",
                   "the wearer completes a fully charged heavy attack"),
    "497": ProcSet("Perfected Roaring Opportunist", _SLAYER_EFFECTS, "Major Slayer",
                   "the wearer completes a fully charged heavy attack"),
    "845": ProcSet("Huntsman's Warmask", frozenset({MARK_OF_HIRCINE_ID}), "Mark of Hircine",
                   "the wearer deals damage with a bash or a fully charged heavy attack",
                   pieces=1, bonus="mark"),
}
PROC_EFFECT_IDS = frozenset().union(*(proc.effect_ids for proc in PROC_SETS.values()))


class GroupBuffSet(NamedTuple):
    name: str
    set_ids: frozenset  # the set's ids, perfected and not, counted together
    effect_ids: frozenset  # the buff its wearers give other players
    pieces: int = 5  # worn pieces that make the bonus
    wearers_excluded: bool = False  # the buff never counts for the set's own wearers


# The group buff sets judged for a second copy (issue #172; see the module
# notes): sets whose value is the buff they give others. The effect ids are
# the named Major and Minor buffs of data/sets/set_buffs.json, and for the
# sets whose buff is named after the set, the default uptime rules' ids
# (Powerful Assault, Pearlescent Ward, Lucent Echoes) and the logs' own
# (Xoryn's Masterpiece 220010 and 220011; Roaring Opportunist's 93109 beside
# its 135923, as PROC_SETS has it)
GROUP_BUFF_SETS = (
    GroupBuffSet("Spell Power Cure", frozenset({"185"}), frozenset({"66902"})),
    GroupBuffSet("Vestment of Olorime", frozenset({"391", "395"}), frozenset({"109994"})),
    GroupBuffSet("War Machine", frozenset({"331"}), frozenset({"93442"})),
    GroupBuffSet("Master Architect", frozenset({"332"}), frozenset({"93120"})),
    GroupBuffSet("Roaring Opportunist", frozenset({"496", "497"}), _SLAYER_EFFECTS),
    GroupBuffSet("Saxhleel Champion", frozenset({"585", "589"}), frozenset({"154830"})),
    GroupBuffSet("Claw of Yolnahkriin", frozenset({"446", "451"}), frozenset({"121878"})),
    GroupBuffSet("Powerful Assault", frozenset({"180"}), frozenset({"61771"})),
    GroupBuffSet("Pearlescent Ward", frozenset({"648", "651"}), frozenset({"172621"})),
    GroupBuffSet("Lucent Echoes", frozenset({"768", "771"}), frozenset({"220015"}),
                 wearers_excluded=True),
    GroupBuffSet("Xoryn's Masterpiece", frozenset({"769", "770"}),
                 frozenset({"220010", "220011"})),
    GroupBuffSet("Transformative Hope", frozenset({"704", "705"}),
                 frozenset({"194148", "194149"})),
    GroupBuffSet("Magma Incarnate", frozenset({"609"}),
                 frozenset({"159310", "159341", "159352", "159356",    # Minor Courage
                            "159311", "159340", "159350", "159358"}),  # Minor Resolve
                 pieces=2),
    GroupBuffSet("Mender's Ward", frozenset({"416", "428"}), frozenset({"113653"}), pieces=2),
    GroupBuffSet("Ozezan the Inferno", frozenset({"687"}), frozenset({"188505"}), pieces=2),
    GroupBuffSet("The Blind", frozenset({"738"}), frozenset({"214863"}), pieces=2),
)
GROUP_BUFF_EFFECT_IDS = frozenset().union(*(s.effect_ids for s in GROUP_BUFF_SETS))
# Each buff id to its set: a set's ids are measured together, so a copy that
# puts two of them on a player at once (Magma Incarnate's Minor Courage and
# Minor Resolve) is credited once for that time
GROUP_BUFF_SET_OF_EFFECT = {effect_id: group_set.name
                            for group_set in GROUP_BUFF_SETS for effect_id in group_set.effect_ids}
# A copy credited with less of the other players' time than this added
# almost nothing: the group had the buff from another wearer
SECOND_SOURCE_SHARE = 0.02


class Star(NamedTuple):
    name: str
    slotted_id: str  # in the PLAYER_INFO long-term effects of a player who slots it
    proc_id: str  # the effect a proc puts on the player it helps, the holder its source
    cooldown_s: int  # per player, shared by every holder
    does: str  # what a proc does, for the finding
    url: str  # its ESO-Hub page
    # A holder is flagged under this fraction of an even share of the
    # holders' procs over the session; 0 means only a holder whose star
    # never procced
    min_of_even: float = 0.0


# An Enlivening Overflow holder with less than this fraction of an even
# share of the holders' procs rarely got the chance: the others' procs had
# the players on cooldown. With two holders it is 15% of the procs; with
# seven sharing evenly (1/7 each) none is flagged
STAR_EVEN_SHARE = 0.3
# A star is judged only once the other holders have procced this often in
# the fights counted: with fewer, one holder's none is chance (two equal
# holders sharing one or two procs leave one with none half the time)
STAR_MIN_OTHER_PROCS = 5
# The Champion Point stars judged for a second holder (issue #172)
STARS = (
    Star("Enlivening Overflow", "156008", "156012", 12,
         "gives Health, Magicka and Stamina Recovery to a player its holder overheals",
         ESOHUB_CP + "enlivening-overflow", min_of_even=STAR_EVEN_SHARE),
    Star("From the Brink", "156017", "156020", 30,
         "shields a player its holder heals under 25% Health",
         ESOHUB_CP + "from-the-brink"),
)
STAR_PROC_IDS = {star.proc_id: star.name for star in STARS}

# The rule behind each finding, as the finding states it
NIRNHONED_DETAIL = (
    "Nirnhoned raises the damage of the weapon it is on, and the Dual Wield Expert passive "
    "counts only 6% of an off-hand weapon's damage, so the trait gives about a sixteenth "
    "there of what it gives a main-hand weapon. Precise, Charged or Infused serve an off "
    "hand better.")
GLYPH_DETAIL = (
    "Two identical weapon glyphs on one bar share one cooldown, so the second never fires. "
    "A different glyph on the other weapon would add a proc of its own.")
HEAVY_DETAIL = (
    "Heavy Armor's passives add health, resistance and sustain, nothing to damage. One heavy "
    "piece is the usual Undaunted Mettle split; every further one replaces a medium or light "
    "piece whose passives add damage, critical chance or penetration.")
WRONG_WEAPON_DETAIL = (
    "{skill} is a {line} skill and the {bar} bar holds {held}. A weapon skill works only "
    "with its own weapon type in hand, so the slot does nothing until the skill or the "
    "weapon changes.")
DRAIN_DETAIL = (
    "Elemental Drain applies Major Breach and Minor Magickasteal. The other morph, Elemental "
    "Susceptibility, applies Major Breach and the Burning, Chilled and Concussion status "
    "effects every 7.5 seconds; unless the group needs the magicka, Susceptibility is the "
    "morph to run.")
ONE_BAR_DETAIL = (
    "{set}'s five-piece bonus is a buff for the whole group that holds only while five "
    "pieces are active, so the group loses it every time this player swaps to the other "
    "bar. Five body pieces, or three with the two weapons of each bar, keep it on both.")
PROC_DETAIL = (
    "The {bonus} of {set} fires when {trigger}; this player's {effect} never appeared "
    "this session, so the set is dead weight until that changes.")
TANK_TITLE = "Tank with no taunt or pull on either bar"
TANK_DETAIL = (
    "This player reads as a tank: health is the largest pool, they hold {gear}, and they "
    "dealt {share} of an equal share of the group's damage. Yet neither bar holds a taunt "
    "(Puncture, Inner Fire or Runic Jolt and their morphs, Destructive Clench on an ice "
    "staff, a scribed skill with the Taunt focus) or a pull (Chains of Flame and its morphs, "
    "Silver Leash, Frozen Gate and its morphs, a scribed skill with the Pull focus), and no "
    "taunt of theirs was logged this session, so nothing holds the boss on them.")
FOOD_TITLE = "No food or drink at combat start"
FOOD_DETAIL = (
    "No food or drink buff was on this player as the fight began, so they fought without a "
    "consumable's maximum stats or recovery. The check is against the app's list of the "
    "game's food and drink effects (LibFoodDrinkBuff); a consumable newer than that list "
    "reads the same way.")
FOOD_ATE_NOTE = " They ate {food} at {at}."
FOOD_RAN_OUT_TITLE = "{food} ran out {at} into the fight"
FOOD_RAN_OUT_DETAIL = (
    "The player's {food} faded at {at} and nothing was eaten before the fight ended, so the "
    "rest of it was fought without the consumable's maximum stats or recovery.")
SLAYER_TITLE = "No Minor Slayer in a veteran trial group"
SLAYER_DETAIL = (
    "No trial set at three pieces and no Oakensoul Ring, so no Minor Slayer: 5% more damage "
    "to dungeon, trial and arena monsters.")
SECOND_SET_TITLE = "Second {set} gave the others {amount} ({fights})"
SECOND_SET_DETAIL = (
    "Another player wears {set} complete too. A player has the set's buff from one wearer "
    "at a time, and in {fights} of a minute or more with both, the log credited this "
    "player's copy with {share} of the other players' time{excluded}, so it added next to "
    "nothing beside the other. Another set would add more.")
SECOND_SET_EXCLUDED = " (the buff never counts for the set's own wearers)"
SECOND_STAR_TITLE = "Second {star}: {share} of its procs ({fights})"
SECOND_STAR_NEVER_TITLE = "Second {star}: no proc in {fights}"
SECOND_STAR_DETAIL = (
    "{star} {does}, once every {cooldown} seconds per player, and that cooldown is shared "
    "by everyone who slots the star: once any holder's has procced on a player, no holder's "
    "can for {cooldown} seconds. Another player slots it too, and in {fights} of a minute "
    "or more with both, {result}. Another star would add more.")
SECOND_STAR_SHARE = "this player's procs were {share} of the holders', where an even share was {even}"
SECOND_STAR_NEVER = "this player's never procced while the other holder's did"


def _clock(ms: int) -> str:
    """A moment of the fight as the timeline strip's ticks read it: '45s',
    '1m05', '2m'."""
    total = max(0, int(ms)) // 1000
    if total < 60:
        return f"{total}s"
    return f"{total // 60}m" if total % 60 == 0 else f"{total // 60}m{total % 60:02d}"


def _finding(rule: str, title: str, detail: str, set_name: str = "", skill: str = "",
             star: Optional["Star"] = None) -> dict:
    """One finding: the rule's id, what was found, the rule behind it, and
    the set or skill it is about (for a link), '' when none. A finding
    about a Champion Point star adds 'star' and 'star_url', its ESO-Hub
    page, since the bundled link maps hold no stars."""
    finding = {"rule": rule, "title": title, "detail": detail, "set": set_name, "skill": skill}
    if star is not None:
        finding.update(star=star.name, star_url=star.url)
    return finding


def _fights_text(count: int) -> str:
    return f"{count} fight" if count == 1 else f"{count} fights"


def _union_ms(pairs: Iterable[tuple[int, int]]) -> int:
    """The time the (start, end) spans cover, overlaps counted once."""
    covered = 0
    cur_start = cur_end = None
    for start, end in sorted(pairs):
        if cur_end is None or start > cur_end:
            if cur_end is not None:
                covered += cur_end - cur_start
            cur_start, cur_end = start, end
        elif end > cur_end:
            cur_end = end
    if cur_end is not None:
        covered += cur_end - cur_start
    return covered


def _share_text(share: float) -> str:
    """'0.4%', '12%': one decimal under ten percent, where the rules' figures sit."""
    pct = 100 * max(0.0, share)
    return f"{pct:.1f}%" if pct < 10 else f"{pct:.0f}%"


def _an(label: str) -> str:
    """'an Inferno Staff', 'a Dagger'."""
    return f"an {label}" if label[:1].lower() in "aeiou" else f"a {label}"


@lru_cache(maxsize=1)
def _bundled_weapon_skills() -> Dict[str, dict]:
    """Ability id -> {'line', 'name'} for every weapon-line skill in the
    bundled table; {} when the table is absent."""
    try:
        data = json.loads(bundle_root().joinpath("data", "skills", "weapon_skill_lines.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    skills = data.get("skills") if isinstance(data, dict) else None
    return {str(k): v for k, v in (skills or {}).items() if isinstance(v, dict)}


def skill_line_of_slot(slot: dict, table: Optional[Dict[str, dict]] = None) -> str:
    """The weapon skill line a bar slot's skill belongs to ('Two Handed'),
    '' for a skill of no weapon line or one the table does not know. A
    scribed skill whose id the table lacks is known by its grimoire's icon.
    *table* overrides the bundled one; tests use it."""
    known = _bundled_weapon_skills() if table is None else table
    entry = known.get(str(slot.get("id", "")))
    if entry:
        return str(entry.get("line") or "")
    icon = str(slot.get("icon") or "")
    if icon.startswith(GRIMOIRE_ICON_PREFIX):
        return GRIMOIRE_LINES.get(GRIMOIRES.get(icon, ""), "")
    return ""


def bar_weapon_line(gear: Dict[str, List[str]], main_slot: str, off_slot: str,
                    types: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """(weapon line, what the bar holds) for a bar: ('Destruction Staff',
    'an Inferno Staff'), ('Dual Wield', 'two Daggers'), ('One Hand and
    Shield', 'a Sword and a Shield'). ('', '') when the bar is empty, the
    main hand is not in the bundled weapon table, or a one-hander has no
    partner the rule can read."""
    main = gear.get(main_slot)
    if not main or len(main) < 2:
        return "", ""
    main_type = weapon_type(main[1], types)
    if not main_type:
        return "", ""
    main_label = weapon_type_label(main_type) or "weapon"
    if main_type in _TWO_HANDED_TYPES:
        return "Two Handed", _an(main_label)
    if main_type == "bow":
        return "Bow", _an(main_label)
    if main_type in _STAFF_LINES:
        return _STAFF_LINES[main_type], _an(main_label)
    if main_type not in _ONE_HANDED_TYPES:
        return "", ""
    off = gear.get(off_slot)
    off_type = weapon_type(off[1], types) if off and len(off) > 1 else ""
    if off and not off_type and len(off) > 4 and str(off[4]).startswith("ARMOR_"):
        off_type = "shield"  # a shield from a set newer than the table
    if off_type == "shield":
        return "One Hand and Shield", f"{_an(main_label)} and a Shield"
    if off_type in _ONE_HANDED_TYPES:
        off_label = weapon_type_label(off_type)
        held = (f"two {main_label}s" if off_type == main_type
                else f"{_an(main_label)} and {_an(off_label)}")
        return "Dual Wield", held
    return "", ""


def heavy_pieces(gear: Dict[str, List[str]], weights: Optional[Dict[str, str]] = None) -> int:
    """How many of the seven armor slots hold a heavy piece the bundled
    weight table knows."""
    return sum(1 for slot in ARMOR_SLOTS
               if slot in gear and len(gear[slot]) > 1
               and armor_weight(gear[slot][1], weights) == "heavy")


def wears_oakensoul(gear: Dict[str, List[str]]) -> bool:
    return any(len(item) > 6 and str(item[6]) == OAKENSOUL_SET_ID for item in gear.values())


def slayer_sets(gear: Dict[str, List[str]]) -> Set[str]:
    """The SLAYER_SETS ids this build has at three or more active pieces on
    either bar: each is a Minor Slayer source, on that bar at least."""
    return {set_id for set_id, (front, back) in piece_counts(gear or {}).items()
            if set_id in SLAYER_SETS
            and (front >= SLAYER_PIECES or (back or 0) >= SLAYER_PIECES)}


def _slot_is(slot: dict, names: frozenset, ids: frozenset, focus: str, prefix: str) -> bool:
    """Whether a bar slot is one of the skills *ids* or *names*, or a
    scribed skill whose focus script is *focus* (which gives it a name
    starting with *prefix*); a scribed skill with several possible lines
    counts when any of them has that focus."""
    name = str(slot.get("name") or "")
    if str(slot.get("id", "")) in ids or name in names or name.startswith(prefix):
        return True
    scripts = slot.get("scripts") or []
    if scripts and str(scripts[0]) == focus:
        return True
    return any(len(option) > 1 and str(option[1]) == focus
               for option in slot.get("script_options") or [])


def taunts_and_pulls(gear: Dict[str, List[str]], front_slots: Optional[List[dict]],
                     back_slots: Optional[List[dict]],
                     types: Optional[Dict[str, str]] = None) -> Set[str]:
    """{'taunt', 'pull'}, those of the two the bars hold: a taunt skill, a
    Destructive Clench on a bar whose main hand is an ice staff, a pull skill,
    or a scribed skill with the Taunt or Pull focus."""
    found: Set[str] = set()
    for (_bar, main_slot, _off_slot), slots in zip(BARS, (front_slots, back_slots)):
        main = gear.get(main_slot)
        ice = bool(main) and len(main) > 1 and weapon_type(main[1], types) == "ice_staff"
        for slot in slots or []:
            clench = (str(slot.get("id", "")) in CLENCH_SKILL_IDS
                      or str(slot.get("name") or "") in CLENCH_SKILL_NAMES)
            if (_slot_is(slot, TAUNT_SKILL_NAMES, TAUNT_SKILL_IDS, TAUNT_FOCUS, TAUNT_PREFIX)
                    or (ice and clench)):
                found.add("taunt")
            elif _slot_is(slot, PULL_SKILL_NAMES, PULL_SKILL_IDS, PULL_FOCUS, PULL_PREFIX):
                found.add("pull")
    return found


def tank_gear(gear: Dict[str, List[str]], weights: Optional[Dict[str, str]] = None,
              types: Optional[Dict[str, str]] = None) -> str:
    """What makes the gear a tank's, for the finding: 'a shield', 'an ice
    staff' or '5 heavy pieces'; '' when nothing does."""
    for _bar, _main_slot, off_slot in BARS:
        off = gear.get(off_slot)
        if off and len(off) > 4 and (weapon_type(off[1], types) == "shield"
                                     or str(off[4]).startswith("ARMOR_")):
            return "a shield"
    for _bar, main_slot, _off_slot in BARS:
        main = gear.get(main_slot)
        if main and len(main) > 1 and weapon_type(main[1], types) == "ice_staff":
            return "an ice staff"
    heavy = heavy_pieces(gear, weights)
    return f"{heavy} heavy pieces" if heavy >= TANK_HEAVY_PIECES else ""


def _has_restoration_staff(gear: Dict[str, List[str]],
                           types: Optional[Dict[str, str]] = None) -> bool:
    return any(len(gear.get(main_slot, ())) > 1
               and weapon_type(gear[main_slot][1], types) == "restoration_staff"
               for _bar, main_slot, _off_slot in BARS)


def worn_proc_sets(gear: Dict[str, List[str]]) -> Set[str]:
    """The proc sets (PROC_SETS ids) this build has active on either bar:
    five pieces, or a mythic's one."""
    counts = piece_counts(gear or {})
    return {set_id for set_id, (front, back) in counts.items()
            if set_id in PROC_SETS
            and (front >= PROC_SETS[set_id].pieces or (back or 0) >= PROC_SETS[set_id].pieces)}


def fired_proc_sets(worn: Iterable[str], sourced_effect_ids: Iterable[str]) -> Set[str]:
    """Of the proc sets *worn*, those whose effect the player sourced
    (*sourced_effect_ids*, the ids they were the source of in the fight)."""
    sourced = {str(i) for i in sourced_effect_ids}
    return {set_id for set_id in worn
            if set_id in PROC_SETS and PROC_SETS[set_id].effect_ids & sourced}


def group_buff_sets_worn(gear: dict[str, list[str]]) -> list[GroupBuffSet]:
    """The GROUP_BUFF_SETS this build wears complete: its pieces of the
    set, perfected and not counted together, at the bonus's count on
    either bar (player_build.piece_counts; a two-hander counts two)."""
    counts = piece_counts(gear or {})
    worn = []
    for group_set in GROUP_BUFF_SETS:
        front = sum(counts[s][0] for s in group_set.set_ids if s in counts)
        back = sum(counts[s][1] or 0 for s in group_set.set_ids if s in counts)
        if max(front, back) >= group_set.pieces:
            worn.append(group_set)
    return worn


def stars_slotted(long_term_effects: Iterable[str]) -> list[Star]:
    """The STARS a player slots, read from their PLAYER_INFO long-term effects."""
    ids = {str(i) for i in long_term_effects or ()}
    return [star for star in STARS if star.slotted_id in ids]


def group_buff_shares(wearers: dict[str, list[tuple[str, str]]],
                      credited: dict[tuple[str, str, str], int],
                      present: dict[str, int]
                      ) -> dict[str, dict[str, tuple[int, int]]]:
    """For each set with two or more full wearers in a fight (*wearers*:
    set name -> [(player id, player key)]), each wearer's (ms of the other
    players' time the log credited to their copy of the buff, those
    players' time in the fight): *credited* is GroupBuffCredit.credited's
    map by set (group_of=GROUP_BUFF_SET_OF_EFFECT.get), *present* the
    fight's group members, player id -> ms they were there (a member who
    joined late or left counts for that part). The other players are every
    member but the wearer, and for a set whose buff never counts for its
    wearers (Lucent Echoes) every member who does not wear it. A player of
    the zone outside the group (a city, Cyrodiil, a world boss) is no
    receiver, so the share is of the group's own time."""
    present = {str(p): max(0, int(ms)) for p, ms in present.items()}
    by_name = {group_set.name: group_set for group_set in GROUP_BUFF_SETS}
    shares: dict[str, dict[str, tuple[int, int]]] = {}
    for name, worn_by in wearers.items():
        group_set = by_name.get(name)
        if group_set is None or len(worn_by) < 2:
            continue
        wearing = {str(player_id) for player_id, _key in worn_by}
        per: dict[str, tuple[int, int]] = {}
        for player_id, key in worn_by:
            player_id = str(player_id)
            others = {p for p in present if p != player_id
                      and not (group_set.wearers_excluded and p in wearing)}
            got = sum(ms for (group, source, target), ms in credited.items()
                      if group == name and source == player_id and target in others)
            per[key] = (got, sum(present[p] for p in others))
        shares[name] = per
    return shares


class GroupBuffCredit:
    """Whose copy of a group buff set's buff each player had, over time
    (issue #172): the spans of GROUP_BUFF_EFFECT_IDS per (effect, source,
    target) unit, in raw log milliseconds.

    The game writes one instance of such a buff per receiver, credited to
    one wearer at a time (see the module notes), so a span is that wearer's
    credit for that player. GAINED or UPDATED opens a span when none is
    open (a refresh after a missed GAINED), FADED closes it, and a span
    that resumes within MERGE_GAP_MS of its last close is the same span
    (Pearlescent Ward is written as a FADED and a GAINED every second). A
    zone change ends the open spans (zone_changed: unit ids are handed out
    afresh), so does a unit's removal for its own (forget_unit), BEGIN_LOG
    drops everything (reset), and spans that ended before a published fight
    are pruned (prune_before), as the uptime rules' are.
    """

    MERGE_GAP_MS = 500

    def __init__(self):
        # (effect id, source unit, target unit) -> start ms of the open span
        self._open: dict[tuple[str, str, str], int] = {}
        # the same key -> [[start, end], ...] closed, oldest first
        self._closed: dict[tuple[str, str, str], list[list[int]]] = {}

    def reset(self) -> None:
        self._open.clear()
        self._closed.clear()

    def record(self, effect_type: str, ability_id: str, source_id: str, target_id: str,
               timestamp_ms: int) -> None:
        ability_id = str(ability_id)
        if ability_id not in GROUP_BUFF_EFFECT_IDS:
            return
        key = (ability_id, str(source_id), str(target_id))
        if effect_type in ("GAINED", "UPDATED"):
            self._open.setdefault(key, int(timestamp_ms))
        elif effect_type == "FADED":
            start = self._open.pop(key, None)
            if start is not None:
                self._close(key, start, int(timestamp_ms))

    def _close(self, key: tuple[str, str, str], start: int, end: int) -> None:
        if end <= start:
            return
        spans = self._closed.setdefault(key, [])
        if spans and 0 <= start - spans[-1][1] <= self.MERGE_GAP_MS:
            spans[-1][1] = max(spans[-1][1], end)
        else:
            spans.append([start, end])

    def zone_changed(self, timestamp_ms: int) -> None:
        for key, start in list(self._open.items()):
            self._close(key, start, int(timestamp_ms))
        self._open.clear()

    def forget_unit(self, unit_id: str, timestamp_ms: int) -> None:
        """The unit was removed (UNIT_REMOVED): its spans, as wearer or as
        receiver, end here. The game writes no FADED for a unit that has
        gone, so a span would otherwise run on, and a unit id handed to
        someone new would inherit it (a group member who left before a
        Lucent Citadel pull kept a second Echoes wearer's span open
        through the whole fight)."""
        unit_id = str(unit_id)
        for key in [key for key in self._open if unit_id in (key[1], key[2])]:
            self._close(key, self._open.pop(key), int(timestamp_ms))

    def credited(self, start_ms: int, end_ms: int,
                 player_of: Callable[[str], str | None],
                 group_of: Callable[[str], str | None] | None = None
                 ) -> dict[tuple[str, str, str], int]:
        """(effect, source player, target player) -> the ms of the window
        [start_ms, end_ms] that the source's copy of the effect was on the
        target. *player_of* turns a unit id into its player's id, None for a
        unit that is no player of the fight (a pet, a companion, an enemy).
        *group_of* names the effect a buff id is measured as (its set, by
        GROUP_BUFF_SET_OF_EFFECT.get); the spans of one group, and of a
        player's several unit ids, are joined, so time when two of a set's
        buffs were on a player at once counts once."""
        if end_ms <= start_ms:
            return {}
        spans: dict[tuple[str, str, str], list[tuple[int, int]]] = {}
        for key in set(self._closed) | set(self._open):
            source, target = player_of(key[1]), player_of(key[2])
            if source is None or target is None:
                continue
            group = (group_of(key[0]) if group_of else None) or key[0]
            joined = spans.setdefault((group, str(source), str(target)), [])
            pairs = list(self._closed.get(key, ()))
            if key in self._open:
                pairs.append([self._open[key], end_ms])
            for start, end in pairs:
                start, end = max(start, start_ms), min(end, end_ms)
                if end > start:
                    joined.append((start, end))
        out: dict[tuple[str, str, str], int] = {}
        for merged, pairs in spans.items():
            ms = _union_ms(pairs)
            if ms:
                out[merged] = ms
        return out

    def prune_before(self, timestamp_ms: int) -> None:
        """Free closed spans that ended before *timestamp_ms*."""
        for key in list(self._closed):
            kept = [span for span in self._closed[key] if span[1] > timestamp_ms]
            if kept:
                self._closed[key] = kept
            else:
                del self._closed[key]


def structural_findings(gear: Dict[str, List[str]], front_slots: Optional[List[dict]],
                        back_slots: Optional[List[dict]], role: str, taunted: bool = False,
                        set_name_of: Optional[Callable[[str], Optional[str]]] = None,
                        weights: Optional[Dict[str, str]] = None,
                        types: Optional[Dict[str, str]] = None,
                        skills: Optional[Dict[str, dict]] = None,
                        damage_ratio: Optional[float] = None,
                        out_heals: bool = False, players: Optional[int] = None,
                        veteran: bool = False) -> List[dict]:
    """The per-fight rules on one build: Nirnhoned off hand, duplicate
    glyph, heavy armor on a DPS who has not taunted, no Minor Slayer on a
    DPS in a veteran trial group, a tank with no taunt or pull, weapon
    skill on the wrong bar, Elemental Drain, a group set on one bar; in
    that order.

    *gear* is slot -> the item's eleven log fields, the bar slots the
    engine's {'id', 'name', 'icon'} dicts, *role* the app's 'T', 'H' or
    'D', *taunted* whether the player taunted this session, *damage_ratio*
    the player's damage this fight over an equal share of the group's (1.0
    is an equal share; None when the fight had no damage), *out_heals*
    whether they healed others for more than they dealt, *players* how
    many players the fight's group had (None when unknown), *veteran*
    whether the zone is at veteran difficulty. *set_name_of* names a set
    id (the bundled set data by default); *weights*, *types* and *skills*
    override the bundled tables for tests.
    """
    gear = gear or {}
    findings: List[dict] = []
    oakensoul = wears_oakensoul(gear)

    for bar, _main_slot, off_slot in BARS:
        off = gear.get(off_slot)
        if off and len(off) > 4 and str(off[4]) == NIRNHONED_WEAPON_TRAIT:
            weapon = weapon_type_label(weapon_type(off[1], types)) or "weapon"
            findings.append(_finding(
                "nirnhoned-off-hand", f"Nirnhoned on the off-hand {weapon} ({bar} bar)",
                NIRNHONED_DETAIL))

    for bar, main_slot, off_slot in BARS:
        main, off = gear.get(main_slot), gear.get(off_slot)
        if not (main and off and len(main) > 7 and len(off) > 7):
            continue
        if str(off[4]).startswith("ARMOR_"):
            continue  # a shield's glyph is an armor glyph
        glyph = str(main[7])
        if glyph == str(off[7]) and glyph not in NO_VALUE:
            label = enchant_label(glyph) or glyph
            findings.append(_finding(
                "duplicate-glyph", f"Two {label} glyphs on the {bar} bar", GLYPH_DETAIL))

    if role == "D" and not taunted:
        heavy = heavy_pieces(gear, weights)
        if heavy >= HEAVY_PIECES_FLAGGED:
            findings.append(_finding(
                "heavy-armor", f"{heavy} heavy armor pieces on a damage dealer", HEAVY_DETAIL))

    # No Minor Slayer on a damage dealer in a veteran trial group (see the
    # module notes): judged from the gear, since Oakensoul's buff is not in
    # the PLAYER_INFO effects, and never on an empty gear list
    if (role == "D" and not taunted and veteran and gear
            and group_size_class(players or 0) == "large"
            and not oakensoul and not slayer_sets(gear)):
        findings.append(_finding("no-minor-slayer", SLAYER_TITLE, SLAYER_DETAIL))

    # A tank with nothing to hold the boss. The role's health pool alone is
    # not a tank (see the module notes), so tank gear, a small share of the
    # damage and no healer sign are asked for as well
    gear_sign = tank_gear(gear, weights, types) if role == "T" and not taunted else ""
    if (gear_sign and (front_slots or back_slots)
            and damage_ratio is not None and damage_ratio <= TANK_DAMAGE_RATIO
            and not out_heals and not _has_restoration_staff(gear, types)
            and not taunts_and_pulls(gear, front_slots, back_slots, types)):
        findings.append(_finding(
            "tank-no-taunt", TANK_TITLE,
            TANK_DETAIL.format(gear=gear_sign, share=f"{damage_ratio:.0%}")))

    for (bar, main_slot, off_slot), slots in zip(BARS, (front_slots, back_slots)):
        if bar == "back" and oakensoul:
            continue
        line, held = bar_weapon_line(gear, main_slot, off_slot, types)
        if not line:
            continue
        for slot in slots or []:
            skill_line = skill_line_of_slot(slot, skills)
            if skill_line and skill_line != line:
                name = str(slot.get("name") or f"Ability {slot.get('id', '')}")
                findings.append(_finding(
                    "wrong-weapon", f"{name} cannot be cast from the {bar} bar",
                    WRONG_WEAPON_DETAIL.format(skill=name, line=skill_line, bar=bar, held=held),
                    skill=name))

    for (bar, _main_slot, _off_slot), slots in zip(BARS, (front_slots, back_slots)):
        if any(str(slot.get("id", "")) in ELEMENTAL_DRAIN_IDS for slot in slots or []):
            findings.append(_finding(
                "elemental-drain", f"Elemental Drain slotted ({bar} bar)", DRAIN_DETAIL,
                skill="Elemental Drain"))

    if not oakensoul:
        for set_id, (front, back) in sorted(piece_counts(gear).items()):
            if set_id not in GROUP_SETS or back is None or (front >= 5) == (back >= 5):
                continue
            name = (set_name_of(set_id) if set_name_of else None) or GROUP_SETS[set_id]
            bar = "front" if front >= 5 else "back"
            findings.append(_finding(
                "set-on-one-bar",
                f"{name} is complete only on the {bar} bar ({front}/{back} pieces)",
                ONE_BAR_DETAIL.format(set=name), set_name=name))
    return findings


def food_findings(food: Optional[dict], state: Optional[dict], fight_start_ms: int,
                  name_of: Optional[Callable[[str], Optional[str]]] = None,
                  table: Optional[Dict[str, dict]] = None) -> List[dict]:
    """The food rules on one player's fight: no food or drink at combat
    start, or a meal that ran out during it.

    *food* is the player dict's 'food' as player_build.build_fields set it:
    the consumable listed at combat start, or None when none matched the
    table (the caller does not call when the table could not be loaded).
    *state* is the encounter's record of the player's food effects during
    the fight (CombatEncounter.note_food): {'up': the food ids on them now,
    'seen': every food id on them at any point, 'empty_since': the log ms
    the last of them faded, None while one is up or none ever was, 'ate':
    the log ms a food was gained while none had been up since combat
    start, else None}; None when nothing was recorded. *name_of* names an
    ability id, *table* overrides the bundled food table; both name a meal
    the record knows only by its ids.

    A fight the game cut in two lists the player's effects again on its
    second line, and a food that ran out in the first half is gone from
    it, so *food* is None there although the record saw it fade: the
    ran-out form is used, named from the ids the record saw.
    """
    state = state or {}
    ate = state.get("ate")
    empty_since = state.get("empty_since")
    known = food_table() if table is None else table

    def named(ids):
        meal = food_buff(ids or (), name_of or (lambda _id: None), known or {})
        return meal["name"] if meal else ""

    if food is None and (ate is not None or empty_since is None):
        detail = FOOD_DETAIL
        if ate is not None:
            # Named from every id the record saw, so a meal that faded again
            # before the end still has its name
            detail += FOOD_ATE_NOTE.format(
                food=named(state.get("seen") or state.get("up")) or "a meal",
                at=_clock(ate - fight_start_ms))
        return [_finding("no-food", FOOD_TITLE, detail)]
    if empty_since is not None:
        if food is not None:
            name = str(food.get("name") or ("drink" if food.get("kind") == "drink" else "food"))
        else:
            name = named(state.get("seen")) or "food"
        at = _clock(empty_since - fight_start_ms)
        return [_finding("food-ran-out", FOOD_RAN_OUT_TITLE.format(food=name, at=at),
                         FOOD_RAN_OUT_DETAIL.format(food=name, at=at))]
    return []


class BuildIssueTracker:
    """The rules judged over a logging session rather than a fight: the
    proc sets that never fire, a second copy of a group buff set or a
    second holder of a Champion Point star that added next to nothing
    (issue #172), and who has taunted (the heavy-armor rule's guard). Keyed
    by the engine's per-session player key; a fight is keyed by its start,
    so a fight the game cut in two and republished replaces its own record
    instead of counting twice. reset() at BEGIN_LOG."""

    def __init__(self):
        # (player key, set id) -> {fight start ms: (long enough, fired)}
        self._fights: Dict[Tuple[str, str], Dict[int, Tuple[bool, bool]]] = {}
        self._taunters: set[str] = set()
        # Fights with two or more full wearers of a group buff set: set name
        # -> {fight start ms: (long enough, {player key: (credited ms,
        # the other players' ms)})}
        self._group_buffs: dict[str, dict[int, tuple[bool, dict[str, tuple[int, int]]]]] = {}
        # Fights with two or more holders of a star: star name -> {fight
        # start ms: (long enough, {player key: procs})}
        self._stars: dict[str, dict[int, tuple[bool, dict[str, int]]]] = {}
        # _quiet_copies by set, until the records change: one answer serves
        # every row of a fight
        self._quiet: dict[str, dict[str, tuple[int, int, int]]] = {}
        self._retired = 0

    def reset(self) -> None:
        self._fights.clear()
        self._taunters.clear()
        self._group_buffs.clear()
        self._stars.clear()
        self._quiet.clear()

    def note_second_sources(self, fight_start_ms: int, duration_s: float,
                            group_buffs: dict[str, dict[str, tuple[int, int]]],
                            stars: dict[str, dict[str, int]]) -> None:
        """A fight ended: per group buff set with two or more full wearers,
        each wearer's credited and possible ms of the other players' time
        (group_buff_shares), and per star with two or more holders, each
        holder's procs. A fight republished replaces its own records."""
        start = int(fight_start_ms)
        long = float(duration_s) >= LONG_FIGHT_S
        for records in (*self._group_buffs.values(), *self._stars.values()):
            records.pop(start, None)
        for name, per in (group_buffs or {}).items():
            if len(per) >= 2:
                self._group_buffs.setdefault(name, {})[start] = (long, dict(per))
        for name, per in (stars or {}).items():
            if len(per) >= 2:
                self._stars.setdefault(name, {})[start] = (long, dict(per))
        self._quiet.clear()

    def retire_players(self, prefix: str) -> None:
        """The zone changed, and the player keys starting with *prefix*
        (the engine's 'unit:<id>' fallback, a unit id that names a player
        only until then) may go to someone else. Their second-copy records
        move to a key no later player can have, so a new player on the same
        unit id does not inherit them, while the fights they shared still
        count for the other wearers (scribing.forget_players does the same
        for script combinations)."""
        self._retired += 1
        suffix = f"#retired{self._retired}"
        for table in (self._group_buffs, self._stars):
            for records in table.values():
                for start, (long, per) in list(records.items()):
                    if any(key.startswith(prefix) for key in per):
                        records[start] = (long, {
                            (key + suffix if key.startswith(prefix) else key): value
                            for key, value in per.items()})
        self._quiet.clear()

    def _quiet_copies(self, name: str) -> dict[str, tuple[int, int, int]]:
        """The wearers of a group buff set whose copy stayed under
        SECOND_SOURCE_SHARE of the other players' time in every fight of a
        minute or more this session with another full wearer, while another
        wearer's copy reached the group in at least one of those fights:
        player key -> (those fights, credited ms, possible ms over them).
        Two copies that both reached no one (no ultimate cast, say) are
        not a second copy beside a working one, and neither is listed.
        Worked out once per set until the records change."""
        if name in self._quiet:
            return self._quiet[name]
        per_player: dict[str, list[tuple[int, int]]] = {}
        beside_working: set[str] = set()
        for long, per in self._group_buffs.get(name, {}).values():
            if not long:
                continue
            for key, (got, possible) in per.items():
                if possible <= 0:
                    continue
                per_player.setdefault(key, []).append((got, possible))
                if any(other != key and other_possible > 0
                       and other_got >= SECOND_SOURCE_SHARE * other_possible
                       for other, (other_got, other_possible) in per.items()):
                    beside_working.add(key)
        quiet = {key: (len(fights), sum(g for g, _p in fights), sum(p for _g, p in fights))
                 for key, fights in per_player.items()
                 if key in beside_working
                 and all(got < SECOND_SOURCE_SHARE * possible for got, possible in fights)}
        self._quiet[name] = quiet
        return quiet

    def second_source_findings(self, fight_start_ms: int, player_key: str) -> list[dict]:
        """The second-copy findings on *player_key* in the fight that began
        at *fight_start_ms*: a group buff set they wear whose copy added
        next to nothing this session beside another wearer's that reached
        the group (so the finding is always on the smaller contributor),
        and a star they slot beside other holders whose procs left theirs
        too few, in GROUP_BUFF_SETS and STARS order. Only a fight of a
        minute or more is judged, as the session's record is read."""
        start = int(fight_start_ms)
        out: list[dict] = []
        for group_set in GROUP_BUFF_SETS:
            this = self._group_buffs.get(group_set.name, {}).get(start)
            if not this or not this[0] or player_key not in this[1]:
                continue
            quiet = self._quiet_copies(group_set.name)
            if player_key not in quiet:
                continue
            fights, got, possible = quiet[player_key]
            share = got / possible if possible else 0.0
            amount = "nothing" if share < 0.0005 else f"{_share_text(share)} of their time"
            out.append(_finding(
                "second-group-set",
                SECOND_SET_TITLE.format(set=group_set.name, amount=amount,
                                        fights=_fights_text(fights)),
                SECOND_SET_DETAIL.format(
                    set=group_set.name, fights=_fights_text(fights), share=_share_text(share),
                    excluded=SECOND_SET_EXCLUDED if group_set.wearers_excluded else ""),
                set_name=group_set.name))
        for star in STARS:
            records = self._stars.get(star.name, {})
            this = records.get(start)
            if not this or not this[0] or player_key not in this[1]:
                continue
            # The player's procs against an even share: in each fight the
            # holders' procs over the holders, summed over the fights
            fights = mine = total = 0
            even = 0.0
            for long, per in records.values():
                if long and player_key in per:
                    fights += 1
                    mine += per[player_key]
                    fight_total = sum(per.values())
                    total += fight_total
                    even += fight_total / len(per)
            if total - mine < STAR_MIN_OTHER_PROCS:
                continue
            if mine > 0 and mine >= star.min_of_even * even:
                continue
            if mine == 0:
                title = SECOND_STAR_NEVER_TITLE.format(star=star.name, fights=_fights_text(fights))
                result = SECOND_STAR_NEVER
            else:
                share = mine / total
                title = SECOND_STAR_TITLE.format(star=star.name, share=_share_text(share),
                                                 fights=_fights_text(fights))
                result = SECOND_STAR_SHARE.format(share=_share_text(share),
                                                  even=_share_text(even / total))
            out.append(_finding(
                "second-star", title,
                SECOND_STAR_DETAIL.format(star=star.name, does=star.does,
                                          cooldown=star.cooldown_s,
                                          fights=_fights_text(fights), result=result),
                star=star))
        return out

    def note_taunt(self, player_key: str) -> None:
        self._taunters.add(player_key)

    def has_taunted(self, player_key: str) -> bool:
        return player_key in self._taunters

    def note_fight(self, player_key: str, fight_start_ms: int, duration_s: float,
                   worn: Iterable[str], fired: Iterable[str]) -> None:
        """A fight ended: the proc sets *worn* at five pieces, and those of
        them that *fired* (the player sourced the set's effect)."""
        fired = set(fired)
        for set_id in worn:
            records = self._fights.setdefault((player_key, str(set_id)), {})
            records[int(fight_start_ms)] = (float(duration_s) >= LONG_FIGHT_S, set_id in fired)

    def long_fights(self, player_key: str, set_id: str) -> Tuple[int, bool]:
        """(fights of a minute or more the set was worn in, whether it ever
        fired) this session."""
        records = self._fights.get((player_key, str(set_id)), {})
        return (sum(1 for long, _fired in records.values() if long),
                any(fired for _long, fired in records.values()))

    def findings(self, player_key: str, worn: Iterable[str]) -> List[dict]:
        """The never-fired findings for the proc sets *worn* in this fight,
        in PROC_SETS order."""
        out = []
        worn = {str(set_id) for set_id in worn}
        for set_id, proc in PROC_SETS.items():
            if set_id not in worn:
                continue
            long, fired = self.long_fights(player_key, set_id)
            if long < 1 or fired:
                continue
            plural = "" if long == 1 else "s"
            out.append(_finding(
                "set-never-fired",
                f"{proc.name} never fired in {long} fight{plural} of a minute or more",
                PROC_DETAIL.format(set=proc.name, bonus=proc.bonus, trigger=proc.trigger,
                                   effect=proc.effect),
                set_name=proc.name))
        return out
