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
  (bar_ability), the way werewolf.py rebuilds a werewolf's bar. Light and
  heavy attacks, block, bash, dodge roll and break free have other icons
  and are left out.
- A companion's death is a DIED line naming it as the dying unit; it is
  shown on its row, not counted in the fight's Deaths, which stay player
  deaths.
- Only 15 companion lines in 386 sessions fall inside a fight (trials while
  members leave, arena stage transitions, a solo summon at the pull); the
  rest come and go between fights.

The effect rules still see a companion as a pet (ESOLogAnalyzer._unit_kind),
so ``pets`` rules, the group size an expectation reads and the pen/crit
figures do not move with the companion rows.
"""

from dataclasses import dataclass, field

# Monster ids seen in the logs, with the English name for reference only
# (the row shows the name the log gave, in the client's language)
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

COMPANION_REACTION = "COMPANION"
# The icon family of companion skills (ABILITY_INFO's .dds path)
SKILL_ICON_PREFIX = "ability_companion_"
ROLE = "C"  # the role cell of a companion row


def is_companion(monster_id: str, reaction: str) -> bool:
    """Whether a MONSTER unit is a companion: the logging player's own is
    added with reaction COMPANION, another member's is known by its id."""
    return reaction == COMPANION_REACTION or str(monster_id) in COMPANION_MONSTER_IDS


def row_key(owner_unit_id: str, monster_id: str) -> str:
    """The id of a companion's row: one per owner and companion, whatever
    unit ids the re-summons get. Never a unit id (those are digits only)."""
    return f"c{owner_unit_id}-{monster_id}"


def is_row_key(unit_id) -> bool:
    return str(unit_id or "").startswith("c")


def bar_ability(icon_stem: str) -> bool:
    """Whether a cast with this icon is a companion skill for its bar."""
    return str(icon_stem or "").startswith(SKILL_ICON_PREFIX)


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
