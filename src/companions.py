"""
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
  FRIENDLY with owner 0; a later UNIT_CHANGED names the owner, which
  track_pet_ownership reads for every pet. A companion is known by its
  reaction or its monster id.
- Another member's companion is nearly always added under the name
  "<handle>'s Companion" (141 of 150 such UNIT_ADDED lines in the October
  2026 splits; the logging player's own is always added under its own
  name). That handle can be one the log keeps from the owner: a player
  added with neither name nor handle (the engine's ``anon``) is named only
  by their companion in 217 file and handle pairs over 117 split logs,
  199 handles. Replayed, 65 companion rows read "@handle's Companion"
  straight under an ``anon`` row, and the name reached the buff timeline,
  the penetration casters and the death recaps.
- So the log's name for a companion is never used. Every companion, the
  logging player's own included, is "<owner>'s Companion" (shown_name;
  Chris, 2026-10-29): the owner's handle, or ``anon`` for an owner the log
  gave no handle, however many anonymous players there are, and for a
  companion whose owner is not known yet. The name follows the owner: it
  is set when the owner is (CombatEncounter.name_companions), and again
  when an anonymous owner is named on joining the group (presence.py,
  rule 6). The Hide names mask hides the owner part as it hides the
  owner's own name (gui.name_mask).
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
"""

from dataclasses import dataclass, field

# Monster ids seen in the logs, with the English name for reference only
# (a companion is shown as its owner's, shown_name)
COMPANION_MONSTER_IDS = {
    "100208": "Bastian Hallix",
    "103089": "Mirri Elendis",
    "106597": "Ember",
    "106616": "Isobel Veloise",
    "112373": "Sharp-as-Night",
    "112374": "Azandar",
    "120245": "Tanlorin",
    "120246": "Zerith-var",
}

# Each companion's ultimate by ability id, with the English name for
# reference only (the window shows the name the log gave)
ULTIMATES = {
    "164191": "Raging Storm",                    # Ember
    "157259": "Impeccable Shot",                 # Mirri Elendis
    "163763": "Baneslayer",                      # Isobel Veloise
    "213169": "Blade of the Crossing",           # Zerith-var
    "186488": "Gore",                            # Sharp-as-Night
    "195103": "Vigorous Tentacular Eruption",    # Azandar
    "157016": "Unleashed Rage",                  # Bastian Hallix
    "215215": "Ruinous Outburst",                # Tanlorin
}

COMPANION_REACTION = "COMPANION"
# The icon family of companion skills (ABILITY_INFO's .dds path)
SKILL_ICON_PREFIX = "ability_companion_"
ROLE = "C"  # the role cell of a companion row
ANON = "anon"  # the engine's name for a player with neither handle nor name
NAME_SUFFIX = "'s Companion"  # after the owner's name, in every companion's name


def is_companion(monster_id: str, reaction: str) -> bool:
    """Whether a MONSTER unit is a companion: the logging player's own is
    added with reaction COMPANION, another member's is known by its id."""
    return reaction == COMPANION_REACTION or str(monster_id) in COMPANION_MONSTER_IDS


def shown_name(owner_handle: str | None) -> str:
    """The name a companion is shown under: "<owner>'s Companion", the
    owner's handle, or anon when there is no handle or no owner yet."""
    handle = str(owner_handle or "")
    return f"{handle if handle.startswith('@') else ANON}{NAME_SUFFIX}"


def row_key(owner_unit_id: str, monster_id: str) -> str:
    """The id of a companion's row: one per owner and companion, whatever
    unit ids the re-summons get. Never a unit id (those are digits only)."""
    return f"c{owner_unit_id}-{monster_id}"


def is_row_key(unit_id) -> bool:
    return str(unit_id or "").startswith("c")


def bar_ability(icon_stem: str) -> bool:
    """Whether a cast with this icon is a companion skill for its bar."""
    return str(icon_stem or "").startswith(SKILL_ICON_PREFIX)


def bar_order(ability_ids) -> list[str]:
    """A companion's bar: its skills in first-cast order, then its
    ultimate, which a bar sets apart as it does a player's sixth slot."""
    ability_ids = [str(ability_id) for ability_id in ability_ids]
    return ([ability_id for ability_id in ability_ids if ability_id not in ULTIMATES]
            + [ability_id for ability_id in ability_ids if ability_id in ULTIMATES])


@dataclass
class CompanionRecord:
    """One companion of one owner in the zone: its row's identity and the
    unit ids it has had."""
    owner_unit_id: str
    monster_id: str
    name: str
    level: int = 0
    max_health: int = 0
    unit_ids: set[str] = field(default_factory=set)

    @property
    def key(self) -> str:
        return row_key(self.owner_unit_id, self.monster_id)


def level_of(field_value: str | None) -> int:
    try:
        return int(field_value or 0)
    except ValueError:
        return 0
