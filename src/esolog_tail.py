#!/usr/bin/env python3
"""
ESO Encounter Log Analyzer engine.

Monitors ESO encounter logs and analyzes combat encounters. This module is
presentation-free: results are emitted through the AnalyzerListener interface
(see engine_events.py) for the GUI frontend and tests to consume.
"""


import os
import sys
import time
import csv
import io
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, FrozenSet, List, Optional, Tuple, Set
from datetime import datetime
from gear_set_database import gear_set_db
from fight_history import FightHistory, FightHistoryEntry
from engine_events import AnalyzerListener, ArchiveEvent, ListenerMixin, LogStatus
from log_freshness import parse_relative_ms, status_from_tracking
from buff_timeline import BuffTimelineRecorder, extract_effect_fields
from damage_kinds import CAST_RESULTS, HEALTH_RESULTS, CastIndex, TakenTally, area_of
from data_staleness import DataCheckTracker
from death_recap import DeathRecapRecorder, HEAL_RESULTS, RECAP_RESULTS
from effect_rules import EffectTracker
from boss_units import is_fight_boss
from build_issues import (
    BuildIssueTracker, PROC_EFFECT_IDS, fired_proc_sets, food_findings, structural_findings,
    worn_proc_sets,
)
from scribing import ScribingTracker, slot_fields
from player_build import build_fields, food_ids, has_restoration_staff, is_mythic_set, is_two_handed, race_name
from misfortunes import run_misfortunes
from presence import present_share
import casts
import companions
import fight_opener
import pen_crit
import resources
import split_retention
import trial_result
import werewolf


class _PlainAnsi:
    """No-op stand-in for colorama: every attribute is an empty string.

    Legacy format strings reference Fore/Style heavily; with no terminal
    frontend the codes are dead weight, and reports were already saved
    ANSI-stripped.
    """
    def __getattr__(self, name):
        return ''


Fore = _PlainAnsi()
Style = _PlainAnsi()


def _console(*args, **kwargs):
    """Best-effort console output for diagnostics.

    Safe in windowed (no-console) builds where stdout may be unusable.
    """
    try:
        print(*args, **kwargs)
    except Exception:
        pass

from version import __version__

# Design: A death just after END_COMBAT. The blow that kills the last player
# standing ends combat, and that player's
# death event is written after END_COMBAT (about 85 ms later in live logs).
# A player death this soon after END_COMBAT belongs to the fight that just ended.
LATE_DEATH_GRACE_MS = 1000

# Design: Fights the game cuts in two. The game ends and restarts combat in
# the middle of a fight, most often when
# the logging player is resurrected: END_COMBAT, then BEGIN_COMBAT a moment
# later. 48 logs of April to October 2026 held 53 such pairs, 0 to 484 ms
# apart, 45 of them straight after the player accepted a resurrection. A
# BEGIN_COMBAT this soon after END_COMBAT continues that fight when an enemy
# the group hit in the fight's last seconds is still alive; none of the 51
# pairs between half a second and three seconds apart was the same pull.
COMBAT_RESUME_MS = 1000
# Design: Taunts. The game puts one Taunt debuff on a taunted enemy whatever
# skill taunted, and writes a TAUNTED combat event that shares its cast
# tracking id with that skill's own cast and hits, which is how the skill is
# known: no list of taunt skills is needed, and a skill logged under another
# id (Destructive Clench with an ice staff is logged as Frost Clench) is
# matched to its bar slot by the icon the two share (mark_taunt_slots). The
# debuff's spans on each enemy give the uptime line's Taunt item through the
# default rule ``Taunt = 38254 on boss each`` (effect_rules): each boss's
# taunted share of its time in the fight, averaged over the bosses, the
# pack's mobs in a fight without a boss. Checked on 1,361 taunts in twelve
# logs of October 2026.
TAUNTED = "TAUNTED"
CAST_MEMORY = 4096  # casts remembered by tracking id; a taunt follows its cast within ms
ENGAGED_ENEMY_MS = 10000
# The results that count as the group hitting an enemy
ENEMY_HIT_RESULTS = frozenset(
    ('DAMAGE', 'CRITICAL_DAMAGE', 'DOT_TICK', 'DOT_TICK_CRITICAL', 'BLOCKED_DAMAGE'))
# Design: What counts as damage. A hit on an enemy is written with one of
# several results, and the dps figures sum the hit value of these: DAMAGE
# and CRITICAL_DAMAGE (direct hits), DOT_TICK and DOT_TICK_CRITICAL (each
# tick of a damage-over-time effect), BLOCKED_DAMAGE (what got through a
# blocking enemy) and DAMAGE_SHIELDED (what an enemy's damage shield
# absorbed). That is the set Combat Metrics (LibCombat) sums for damage
# done, and matches ESO Logs, which counts absorbed damage as damage done.
# Not counted: IMMUNE (the log writes a hit value the target never took),
# REFLECTED, FALL_DAMAGE, and the overflow field (overkill past the target's
# remaining health; Combat Metrics drops it too). Until 0.9.2 only the two
# direct-hit results counted: measured on 29 of Chris's split logs (990
# dungeon and arena fights, 34 trial fights) the ticks were 26% of all
# damage dealt, and the top player's dps in a boss fight of a minute or
# more was understated by a median 35% in dungeons and 52% in trials,
# up to 79%. Shield absorbs were 2% and blocked hits 0.2%.
DAMAGE_RESULTS = frozenset(
    ('DAMAGE', 'CRITICAL_DAMAGE', 'DOT_TICK', 'DOT_TICK_CRITICAL',
     'BLOCKED_DAMAGE', 'DAMAGE_SHIELDED'))
# Design: Dps time. Every dps figure divides by the span of the hits it
# sums, first hit to last, floored at one second, and not by the fight time
# (BEGIN_COMBAT to END_COMBAT), because that is Combat Metrics' definition
# (LibCombat's dpstime) and the number players compare against. A player's
# dps is their damage over the span of their own hits, a boss figure the
# boss damage over the span of the hits on the bosses, the group's over the
# span of the group's. The fight time is still what the history line and
# header show; the header adds the group's dps time when it differs. The
# long form, with what Combat Metrics does about overkill, shields, pets
# and the breakdown by ability, is damage_stats' module docstring.

# Import our ESO analysis modules
from damage_stats import FightDamage, dps as dps_over
from eso_sets import (MAX_MASTERIES, ESOSubclassAnalyzer, lines_from_passives, mastery_effect_table,
                      mastery_of_effect, skill_lines_of)

# Set types that typically only have 1-2 piece bonuses (no 5pc bonus)
NO_FIVE_PIECE_SET_TYPES = {
    "LIBSETS_SETTYPE_MYTHIC",      # 1 piece only
    "LIBSETS_SETTYPE_MONSTER",     # 2 pieces only
    "LIBSETS_SETTYPE_ARENA",       # Usually 2 pieces (weapon sets)
}

def has_five_piece_bonus(set_name: str) -> bool:
    """Check if a set has a 5-piece bonus using the gear set database."""
    from gear_set_data import SET_INFO

    # Remove "Perfected " prefix for lookup
    clean_name = set_name
    if clean_name.startswith('Perfected '):
        clean_name = clean_name[10:]

    # Look up set type from the pre-generated database
    info = SET_INFO.get(clean_name) or SET_INFO.get(set_name)
    if info:
        return info.get('set_type', '') not in NO_FIVE_PIECE_SET_TYPES

    # Default: assume it has 5pc bonus unless proven otherwise
    return True

class ESOLogEntry:
    """Represents a single log entry from the ESO encounter log."""

    def __init__(self, timestamp: int, event_type: str, fields: List[str], original_line: str = ""):
        self.timestamp = timestamp
        self.event_type = event_type
        self.fields = fields
        self.original_line = original_line

    @classmethod
    def parse(cls, line: str) -> Optional['ESOLogEntry']:
        """Parse a single log line into an ESOLogEntry."""
        try:
            # Split on comma, handle potential quoting
            reader = csv.reader(io.StringIO(line))
            fields = next(reader)

            if len(fields) < 2:
                return None

            event_type = fields[1]

            # Check if the third field is a timestamp (numeric)
            if len(fields) >= 3:
                try:
                    timestamp = int(fields[2])
                    # For certain events, the third field is not a timestamp
                    if event_type in ["UNIT_ADDED", "UNIT_CHANGED", "COMBAT_EVENT", "EFFECT_CHANGED", "BEGIN_CAST", "END_CAST", "ABILITY_INFO", "HEALTH_REGEN", "ENDLESS_DUNGEON_BEGIN", "ENDLESS_DUNGEON_STAGE_END", "ENDLESS_DUNGEON_BUFF_ADDED", "ENDLESS_DUNGEON_BUFF_REMOVED"]:
                        # These events don't have timestamps, use line number as timestamp
                        line_number = int(fields[0]) if fields[0].isdigit() else 0
                        return cls(line_number, event_type, fields[2:], line)
                    else:
                        # These events have timestamps
                        return cls(timestamp, event_type, fields[3:], line)
                except ValueError:
                    # Third field is not a timestamp, treat as data field
                    return cls(0, event_type, fields[2:], line)
            else:
                # No timestamp field, use line number as relative timestamp
                line_number = int(fields[0]) if fields[0].isdigit() else 0
                return cls(line_number, event_type, fields[2:], line)
        except (ValueError, IndexError, StopIteration):
            return None

class PlayerInfo:
    """Stores information about a player character."""

    def __init__(self, unit_id: str, name: str, handle: str, class_id: str = None):
        self.unit_id = unit_id  # Short unit ID from UNIT_ADDED
        self.name = name
        self.handle = handle
        self.class_id = class_id
        self.equipped_abilities: Set[str] = set()
        self.front_bar_abilities: List[str] = []
        self.back_bar_abilities: List[str] = []
        # Per-slot detail for the GUI ({'id', 'name', 'icon'}, plus the
        # scribing.slot_fields of a scribed skill), aligned with the name
        # lists above
        self.front_bar_slots: List[Dict[str, str]] = []
        self.back_bar_slots: List[Dict[str, str]] = []
        self.gear: Dict[str, List[str]] = {}
        # Ability ids of the long-term effects PLAYER_INFO lists (mundus
        # boon, food, passives), for the build window
        self.long_term_effects: List[str] = []
        # Class Mastery names seen firing from this player this session: a
        # proc mastery is never in the list above (eso_sets)
        self.masteries_seen: List[str] = []
        self.race_id: str = ""  # from UNIT_ADDED
        # The game's isLocalPlayer flag on UNIT_ADDED: the player whose
        # client writes the log (the "self" scope of effect_rules)
        self.is_local: bool = False
        self.last_seen = 0
        self.long_unit_ids: Set[str] = set()
        # Who the player is and when they were here (presence.py): the
        # character id from UNIT_ADDED, the game's isGroupedWithLocalPlayer
        # flag, the log time of the UNIT_ADDED that brought them into the
        # zone, and of the UNIT_REMOVED that took them out (None while here)
        self.character_id: str = ""
        self.grouped: bool = False
        self.joined_at: int | None = None
        self.left_at: int | None = None
        # The unit ids the player came back on in this fight (rule 3), the
        # latest of their unit ids, and whether a monster was given the
        # record's own unit id (rule 2)
        self.alias_ids: set[str] = set()
        self.latest_unit_id: str = unit_id
        self.id_released: bool = False
        # Back on another character of the same account: listed before its
        # PLAYER_INFO when grouped with the logging player (rule 4)
        self.switched_character: bool = False

        # Resource tracking (maximum values seen)
        self.max_health: int = 0
        self.max_magicka: int = 0
        self.max_stamina: int = 0
        
        # Champion Points
        self.champion_points: int = 0

    def update_resources(self, health: int = None, magicka: int = None, stamina: int = None):
        """Update maximum resource values."""
        if health is not None and health > self.max_health:
            self.max_health = health
        if magicka is not None and magicka > self.max_magicka:
            self.max_magicka = magicka
        if stamina is not None and stamina > self.max_stamina:
            self.max_stamina = stamina

    def reset_resources(self):
        """Reset resource tracking."""
        self.max_health = 0
        self.max_magicka = 0
        self.max_stamina = 0

    def get_class_name(self) -> str:
        class_mapping = {
            "1": "Dragonknight",
            "2": "Sorcerer", 
            "3": "Nightblade",
            "4": "Warden",
            "5": "Necromancer",
            "6": "Templar",
            "117": "Arcanist"
        }
        return class_mapping.get(self.class_id, "Unknown")
    
    def get_class_skill_lines(self) -> List[str]:
        class_skill_lines = {
            "1": ["Ardent Flame", "Draconic Power", "Earthen Heart"],  # Dragonknight
            "2": ["Dark Magic", "Daedric Summoning", "Storm Calling"],  # Sorcerer
            "3": ["Assassination", "Shadow", "Siphoning"],  # Nightblade
            "4": ["Animal Companions", "Green Balance", "Winter's Embrace"],  # Warden
            "5": ["Bone Tyrant", "Grave Lord", "Living Death"],  # Necromancer
            "6": ["Aedric Spear", "Dawn's Wrath", "Restoring Light"],  # Templar
            "117": ["Herald of the Tome", "Soldier of Apocrypha", "Curative Runeforms"]  # Arcanist
        }
        return class_skill_lines.get(self.class_id, [])


    def masteries(self) -> List[str]:
        """The player's Class Mastery passives: those in the PLAYER_INFO
        list, then those seen firing this session (eso_sets)."""
        names = list(lines_from_passives(self.long_term_effects)[1])
        names.extend(name for name in self.masteries_seen if name not in names)
        return names

    def set_equipped_abilities(self, ability_names: Set[str]):
        """Set the equipped abilities from PLAYER_INFO."""
        self.equipped_abilities = ability_names

    def set_front_back_bar_abilities(self, front_bar: List[str], back_bar: List[str],
                                     front_slots: Optional[List[Dict[str, str]]] = None,
                                     back_slots: Optional[List[Dict[str, str]]] = None):
        """Set the front and back bar abilities from PLAYER_INFO."""
        self.front_bar_abilities = front_bar
        self.back_bar_abilities = back_bar
        self.front_bar_slots = list(front_slots or [])
        self.back_bar_slots = list(back_slots or [])

    def set_gear(self, gear_data: List[List[str]]):
        """Set the gear data from PLAYER_INFO."""
        self.gear = {}
        for gear_item in gear_data:
            if len(gear_item) >= 2:
                slot = gear_item[0]
                self.gear[slot] = gear_item

    def add_long_unit_id(self, long_unit_id: str):
        """Add a long unit ID that maps to this player."""
        self.long_unit_ids.add(long_unit_id)


    def has_unit_id(self, unit_id: str) -> bool:
        """Check if this unit ID (short or long) belongs to this player."""
        if unit_id == self.unit_id:
            return not self.id_released
        return unit_id in self.alias_ids or unit_id in self.long_unit_ids

    def get_display_name(self) -> str:
        """Get the display name for this player (handle or 'anon')."""
        if self.handle and self.handle not in ['""', '', '0']:
            return self.handle
        elif self.name and self.name not in ['""', '', '0']:
            return self.name
        else:
            return "anon"

def infer_player_role(player: PlayerInfo, player_damage: int = 0, player_healing: int = 0, skill_line_role: str = None,
                      restoration_staff: bool = False) -> str:
    """Infer player role (T/H/D) from resources, weapon and healing heuristics.

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
    """
    h, m, s = player.max_health, player.max_magicka, player.max_stamina
    max_val = max(h, m, s)

    if max_val == 0:
        return skill_line_role[0].upper() if skill_line_role else 'D'

    # Check if ALL three resources are within 10% of the max — only then fall back
    # to ability-based role. Two-way near-ties fall through to the dominant-resource
    # checks below (e.g. h=30k, m=29.5k, s=5k should still read as tank).
    sorted_resources = sorted([h, m, s], reverse=True)
    if (sorted_resources[0] > 0
            and sorted_resources[1] / sorted_resources[0] >= 0.9
            and sorted_resources[2] / sorted_resources[0] >= 0.9):
        if skill_line_role:
            role_map = {'tank': 'T', 'healer': 'H', 'dps': 'D'}
            return role_map.get(skill_line_role.lower(), 'D')
        return 'D'

    if h == max_val:
        return 'T'
    if s == max_val:
        return 'D'
    if m == max_val:
        if restoration_staff:
            return 'H'
        if player_healing > player_damage and player_healing > 0:
            return 'H'
        return 'D'
    return 'D'


def mark_taunt_slots(slots: List[dict], taunts: List[dict]) -> None:
    """Put 'taunt': True on each bar slot the player taunted with: the slot
    whose ability id a taunt names, or, for a taunt logged under an id no
    slot has, the slot that shares its icon (Destructive Clench taunts as
    Frost Clench, a separate id with the same icon)."""
    slotted = {str(slot.get("id", "")) for slot in slots}
    ids = {t["id"] for t in taunts}
    icons = {t["icon"] for t in taunts if t["icon"] and t["id"] not in slotted}
    for slot in slots:
        if str(slot.get("id", "")) in ids or (slot.get("icon") and slot["icon"] in icons):
            slot["taunt"] = True


class EnemyInfo:
    """Stores information about an enemy unit."""

    def __init__(self, unit_id: str, name: str, unit_type: str):
        self.unit_id = unit_id
        self.name = name
        self.unit_type = unit_type
        self.max_health: int = 0
        self.current_health: int = 0
        self.is_hostile: bool = False
        self.monster_id: str = ""  # the game's monster id on UNIT_ADDED
        self.boss_flag: bool = False  # the game's own boss flag on UNIT_ADDED
        # A boss of the fight: the flag less the units that carry it without
        # being one (boss_units.is_fight_boss, issue #67)
        self.is_boss: bool = False
        self.added_at: Optional[int] = None  # log time of its UNIT_ADDED
        self.died_at: Optional[int] = None  # log time of its DIED, when seen
        self.removed_at: Optional[int] = None  # log time of its UNIT_REMOVED
        # A player's companion (companions.is_companion) and its level
        self.is_companion: bool = False
        self.level: int = 0
        # It has had a player owner: a pet released at its end turns HOSTILE
        # with owner 0, and is never a monster (fight_opener)
        self.was_owned: bool = False

class CombatEncounter:
    """Represents a single combat encounter."""

    def __init__(self):
        self.start_time: int = 0
        self.end_time: int = 0
        self.players: Dict[str, PlayerInfo] = {}  # Keyed by short unit ID
        # The unit ids a player came back on in this fight, to the key of
        # their record in players (presence.py, rule 3)
        self.player_aliases: dict[str, str] = {}
        self.enemies: Dict[str, EnemyInfo] = {}  # Track enemy units
        self.abilities_used: Dict[str, Set[str]] = defaultdict(set)
        self.total_damage: int = 0  # Track total damage dealt
        self.player_damage: Dict[str, int] = {}  # Track damage per player (including pets)
        # The part of that damage dealt to units the game flags as bosses
        # (UNIT_ADDED isBoss), so a player's boss dps can sit beside their
        # total: a trash fight has none
        self.boss_damage: int = 0
        self.player_boss_damage: Dict[str, int] = {}
        # When the hits happened (the spans the dps figures divide by) and
        # each player's breakdown by ability and target (damage_stats)
        self.damage = FightDamage()
        # Each player's damage taken and healing received by kind, for the
        # death recap window's whole-fight block (damage_kinds.TakenTally)
        self.taken: Dict[str, TakenTally] = {}
        self.player_healing: Dict[str, int] = {}  # Track healing done to OTHER players
        self.enemy_damage: Dict[str, int] = {}  # Track damage dealt to each enemy
        self.total_health_damaged: int = 0  # Track total health of all damaged enemies
        self.player_deaths: int = 0  # Track player deaths
        self.in_combat = False
        self.finalized = False  # Track if encounter has been finalized (ended)
        
        # Pet ownership tracking
        self.pet_ownership: Dict[str, str] = {}
        # Companions (companions.py): each owner's companion by its row key,
        # and the row key of each companion unit while it has an owner.
        # Both carry over to the next fight like pet_ownership; the deaths
        # are this fight's
        self.companions: dict[str, companions.CompanionRecord] = {}
        self.companion_units: dict[str, str] = {}
        self.companion_deaths: dict[str, int] = defaultdict(int)

        # Track combat end time
        self.combat_ended_at: Optional[int] = None
        
        # Grace period logic removed - encounters are finalized immediately on END_COMBAT
        
        # Track highest health hostile monster in this fight
        self.highest_health_hostile: Optional[EnemyInfo] = None
        self.most_damaged_hostile: Optional[EnemyInfo] = None

        # The run's result when this fight completed a trial (trial_result)
        self.trial_result: Optional[Dict] = None
        
        # Who opened the fight and the monster's act before it, decided by
        # the analyzer's fight_opener.OpenerRecorder from BEGIN_COMBAT on;
        # None for a fight that had no BEGIN_COMBAT
        self.opening: fight_opener.FightOpening | None = None

        # Taunts: per player the abilities they taunted with (ability id ->
        # times); the debuff's spans are the Taunt rule's (effect_rules)
        self.player_taunts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # Proc-set effects by the unit that sourced them this fight, for the
        # build-issue rule on a set that never fires (build_issues)
        self.proc_effects: Dict[str, Set[str]] = defaultdict(set)
        # Each player's food and drink effects through the fight, for the
        # build-issue rules on a meal (build_issues.food_findings): unit id
        # -> {'up': the food ids on them, 'seen': every food id on them at
        # any point of the fight, 'empty_since': the log ms the last faded
        # (None while one is up or none ever was), 'ate': the log ms one
        # was gained while none had been up since combat start}
        self.food: Dict[str, dict] = {}

    def add_player(self, unit_id: str, name: str, handle: str, class_id: str = None, champion_points: int = 0):
        """Add a player to this encounter."""
        # Skip offline players
        if name == "Offline":
            return
        player = PlayerInfo(unit_id, name, handle, class_id)
        player.champion_points = champion_points
        self.players[unit_id] = player

    def player_of(self, unit_id: str) -> PlayerInfo | None:
        """The player whose unit *unit_id* is: their record's own id, or one
        they came back on in this fight (presence.py). Not a long unit id."""
        player = self.players.get(unit_id)
        if player is not None and not player.id_released:
            return player
        key = self.player_aliases.get(unit_id)
        return self.players.get(key) if key is not None else None

    def record_id(self, unit_id: str) -> str:
        """The key a unit's figures are kept under: its player's record for
        a player unit, else the unit id itself."""
        player = self.player_of(unit_id)
        return player.unit_id if player is not None else unit_id

    def player_by_character(self, character_id: str) -> PlayerInfo | None:
        """The record of the character *character_id* in this zone."""
        if not character_id or character_id == "0":
            return None
        for player in self.players.values():
            if player.character_id == character_id:
                return player
        return None

    def alias_player(self, player: PlayerInfo, unit_id: str) -> None:
        """The same character back on a new unit id (presence.py, rule 3):
        the id resolves to the record, which is no longer gone."""
        if unit_id != player.unit_id:
            player.alias_ids.add(unit_id)
            self.player_aliases[unit_id] = player.unit_id
        player.latest_unit_id = unit_id
        player.left_at = None

    def player_left(self, unit_id: str, timestamp_ms: int) -> None:
        """A player's UNIT_REMOVED (presence.py, rule 2). Only their latest
        unit counts: an older one going is no news."""
        player = self.player_of(unit_id)
        if player is not None and unit_id == player.latest_unit_id and player.left_at is None:
            player.left_at = timestamp_ms

    def release_player_id(self, unit_id: str, timestamp_ms: int) -> None:
        """A MONSTER added on a player's unit id (presence.py, rule 2): the
        player is gone, and the id is no longer theirs."""
        player = self.player_of(unit_id)
        if player is None:
            return
        if player.left_at is None:
            player.left_at = timestamp_ms
        if unit_id == player.unit_id:
            player.id_released = True
        else:
            player.alias_ids.discard(unit_id)
            self.player_aliases.pop(unit_id, None)

    def start_fight_roster(self) -> None:
        """At BEGIN_COMBAT (presence.py): players who are gone leave the
        list, with their companions and pets; one who came back on a new
        unit id takes it as the record's own, so the new fight's figures
        are keyed as for anyone else."""
        for key, player in list(self.players.items()):
            if player.left_at is not None:
                del self.players[key]
                self._drop_owner(key)
        for key, player in list(self.players.items()):
            if player.latest_unit_id != key and player.latest_unit_id not in self.players:
                self._rekey_player(player, player.latest_unit_id)
            player.alias_ids = set()
        self.player_aliases = {}

    def _drop_owner(self, owner_id: str) -> None:
        for pet, owner in list(self.pet_ownership.items()):
            if owner == owner_id:
                del self.pet_ownership[pet]
        for key, record in list(self.companions.items()):
            if record.owner_unit_id == owner_id:
                del self.companions[key]
        self.companion_units = {unit: key for unit, key in self.companion_units.items()
                                if key in self.companions}

    def _rekey_player(self, player: PlayerInfo, new_id: str) -> None:
        old_id = player.unit_id
        del self.players[old_id]
        player.unit_id = new_id
        player.alias_ids = set()
        player.id_released = False
        self.players[new_id] = player
        for pet, owner in self.pet_ownership.items():
            if owner == old_id:
                self.pet_ownership[pet] = new_id
        renamed = {}
        for key, record in list(self.companions.items()):
            if record.owner_unit_id == old_id:
                del self.companions[key]
                record.owner_unit_id = new_id
                self.companions[record.key] = record
                renamed[key] = record.key
        if renamed:
            self.companion_units = {unit: renamed.get(key, key)
                                    for unit, key in self.companion_units.items()}

    def track_pet_ownership(self, pet_unit_id: str, owner_unit_id: str):
        """Record *pet_unit_id* as a pet of the player who owns it, so its
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
        """
        owner = self.find_player_by_unit_id(owner_unit_id) if owner_unit_id != "0" else None
        if owner is not None:
            # Keyed by the owner's record, which an owner back on a new unit
            # id keeps (presence.py, rule 7)
            self.pet_ownership[pet_unit_id] = owner.unit_id
            self._link_companion(pet_unit_id, owner.unit_id)
            unit = self.enemies.get(pet_unit_id)
            if unit is not None:
                unit.was_owned = True
        else:
            self.pet_ownership.pop(pet_unit_id, None)
            self.companion_units.pop(pet_unit_id, None)

    def _link_companion(self, unit_id: str, owner_unit_id: str) -> None:
        """A companion unit that has an owner joins its owner's record for
        that companion (companions.py): one record, and one row, for every
        unit id the companion gets in the zone. Any other pet is left as it
        is."""
        unit = self.enemies.get(unit_id)
        if unit is None or not unit.is_companion:
            self.companion_units.pop(unit_id, None)
            return
        key = companions.row_key(owner_unit_id, unit.monster_id)
        record = self.companions.get(key)
        if record is None:
            record = self.companions[key] = companions.CompanionRecord(
                owner_unit_id, unit.monster_id, unit.name, unit.level)
        record.unit_ids.add(unit_id)
        if unit.level:
            record.level = unit.level
        self.companion_units[unit_id] = key
        self.name_companions(owner_unit_id)

    def name_companions(self, owner_unit_id: str) -> None:
        """Name every companion of the player *owner_unit_id* after them,
        "<handle>'s Companion" or "anon's Companion" (companions.shown_name):
        when the owner is known, and again when an anonymous owner is
        named."""
        owner = self.players.get(owner_unit_id)
        name = companions.shown_name(owner.handle if owner is not None else None)
        for record in self.companions.values():
            if record.owner_unit_id != owner_unit_id:
                continue
            record.name = name
            for unit_id in record.unit_ids:
                unit = self.enemies.get(unit_id)
                if unit is not None and unit.is_companion and unit.monster_id == record.monster_id:
                    unit.name = name

    def companion_key(self, unit_id: str) -> str | None:
        """The row key of the companion *unit_id* while it has an owner."""
        return self.companion_units.get(unit_id)

    def is_friendly_unit(self, unit_id: str) -> bool:
        """Check if a unit ID belongs to a friendly player or their pet."""
        # Check if it's a known player
        if self.find_player_by_unit_id(unit_id):
            return True
        
        # Check if it's a known pet of a friendly player
        if unit_id in self.pet_ownership:
            owner_id = self.pet_ownership[unit_id]
            return self.find_player_by_unit_id(owner_id) is not None
        
        # Note: Removed overly broad 1-50 fallback as it was filtering out legitimate hostile enemies
            
        return False
    
    def update_highest_health_hostile(self, enemy: EnemyInfo):
        """Update the highest health hostile monster if this enemy has more health."""
        # Only consider HOSTILE monsters (not players or pets)
        if (not self.is_friendly_unit(enemy.unit_id) and 
            enemy.max_health > 0 and 
            hasattr(enemy, 'is_hostile') and enemy.is_hostile):
            if (self.highest_health_hostile is None or 
                enemy.max_health > self.highest_health_hostile.max_health or
                (enemy.max_health == self.highest_health_hostile.max_health and "Stormreeve" in enemy.name)):
                self.highest_health_hostile = enemy
    
    def update_most_damaged_hostile(self, unit_id: str):
        """Update the most damaged hostile monster based on player damage."""
        if unit_id in self.enemies:
            enemy = self.enemies[unit_id]
            if (hasattr(enemy, 'is_hostile') and enemy.is_hostile and 
                unit_id in self.enemy_damage):
                damage = self.enemy_damage[unit_id]
                if (self.most_damaged_hostile is None or 
                    damage > self.enemy_damage.get(self.most_damaged_hostile.unit_id, 0)):
                    self.most_damaged_hostile = enemy
    
    def update_enemy_health(self, unit_id: str, current_health: int, max_health: int):
        """Update an enemy's health values and check if it's now the highest health hostile."""
        if unit_id in self.enemies:
            enemy = self.enemies[unit_id]
            # Update health values
            enemy.current_health = current_health
            enemy.max_health = max_health
            
            # Update highest health hostile if this is a hostile monster
            self.update_highest_health_hostile(enemy)

    def add_ability_use(self, unit_id: str, ability_name: str):
        """Record an ability use by a player (for tracking purposes only)."""
        player = self.find_player_by_unit_id(unit_id)
        if player:
            self.abilities_used[player.unit_id].add(ability_name)

    def find_player_by_unit_id(self, unit_id: str) -> Optional[PlayerInfo]:
        """Find a player by either short or long unit ID."""
        for player in self.players.values():
            if player.has_unit_id(unit_id):
                return player
        return None

    def associate_long_unit_id(self, short_unit_id: str, long_unit_id: str):
        """Associate a long unit ID with a player's short unit ID."""
        if short_unit_id in self.players:
            self.players[short_unit_id].add_long_unit_id(long_unit_id)

    def taken_for(self, player_unit_id: str) -> TakenTally:
        """The player's tally of damage taken in this fight, started empty."""
        tally = self.taken.get(player_unit_id)
        if tally is None:
            tally = self.taken[player_unit_id] = TakenTally()
        return tally

    def add_damage_to_player(self, unit_id: str, damage: int, to_boss: bool = False,
                             timestamp: Optional[int] = None, result: str = 'DAMAGE',
                             ability_id: str = '', target_id: str = '',
                             accrue_companions: bool = False,
                             damage_type: str = '', cast_id: str = '', cast_index=None):
        """Credit damage dealt by *unit_id* to the player it belongs to:
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
        its owner's as well."""
        # Find the player this unit belongs to
        player = self.find_player_by_unit_id(unit_id)
        companion = None
        if player is None and unit_id in self.pet_ownership:
            # A pet's damage is its owner's
            player = self.find_player_by_unit_id(self.pet_ownership[unit_id])
            companion = self.companion_key(unit_id)
        if player is None and companion is None:
            return
        # The kinds of the hit (damage_kinds), the same for a player's own
        # hit, a pet's and a companion's
        area = watch = cast_key = None
        if timestamp is not None and cast_index is not None:
            is_area, rule, _targets = area_of(cast_index, unit_id, cast_id,
                                              str(ability_id), True)
            area = (is_area, rule)
            cast_key = (str(unit_id), str(cast_id))
            watch = lambda callback: cast_index.watch(unit_id, cast_id, callback)  # noqa: E731
        if companion is not None:
            owner = player.unit_id if (player is not None and accrue_companions) else None
            for record_id in (companion, owner):
                if record_id is not None:
                    self._credit_damage(record_id, damage, to_boss)
            if timestamp is not None:
                self.damage.note(companion, timestamp, damage, result, str(ability_id),
                                 False, target_id, to_boss, damage_type, area, cast_key,
                                 watch, also=owner)
            return
        self._credit_damage(player.unit_id, damage, to_boss)
        if timestamp is not None:
            self.damage.note(player.unit_id, timestamp, damage, result, str(ability_id),
                             not player.has_unit_id(unit_id), target_id, to_boss,
                             damage_type, area, cast_key, watch)

    def _credit_damage(self, record_id: str, damage: int, to_boss: bool) -> None:
        self.player_damage[record_id] = self.player_damage.get(record_id, 0) + damage
        if to_boss:
            self.player_boss_damage[record_id] = (
                self.player_boss_damage.get(record_id, 0) + damage)

    def add_healing_to_player(self, source_unit_id: str, target_unit_id: str, heal_value: int,
                              accrue_companions: bool = False):
        """Track healing done by source player to a DIFFERENT player. A
        companion's heal on a player is its own row's, its owner included;
        with *accrue_companions* it is the owner's too, unless it healed
        the owner (a self-heal for the owner)."""
        source_player = self.find_player_by_unit_id(source_unit_id)
        companion = None
        if not source_player:
            # Check pet ownership
            if source_unit_id in self.pet_ownership:
                owner_id = self.pet_ownership[source_unit_id]
                source_player = self.find_player_by_unit_id(owner_id)
                companion = self.companion_key(source_unit_id)
        if not source_player:
            return
        target_player = self.find_player_by_unit_id(target_unit_id)
        if not target_player:
            return
        if companion is not None:
            self.player_healing[companion] = self.player_healing.get(companion, 0) + heal_value
            if not accrue_companions:
                return
        # Only count healing to other players (not self-heals)
        if target_player.unit_id == source_player.unit_id:
            return
        if source_player.unit_id not in self.player_healing:
            self.player_healing[source_player.unit_id] = 0
        self.player_healing[source_player.unit_id] += heal_value

    def note_taunt(self, player_unit_id: str, ability_id: str):
        """A player taunted with an ability ('' when the log did not say which)."""
        self.player_taunts[player_unit_id][ability_id] += 1

    def note_proc(self, source_unit_id: str, ability_id: str):
        """A proc set's effect was sourced by a unit this fight (build_issues)."""
        self.proc_effects[source_unit_id].add(ability_id)

    def _food_record(self, unit_id: str) -> dict:
        return self.food.setdefault(
            unit_id, {"up": set(), "seen": set(), "empty_since": None, "ate": None})

    def seed_food(self, unit_id: str, ability_ids) -> None:
        """The food ids a PLAYER_INFO line lists on a player as combat
        starts. A fight the game cut in two writes the line again on the
        same encounter: the ids are added to the record, which keeps what
        it saw of the first half (build_issues)."""
        record = self._food_record(unit_id)
        ids = {str(a) for a in ability_ids}
        record["up"].update(ids)
        record["seen"].update(ids)

    def note_food(self, unit_id: str, change: str, ability_id: str, timestamp_ms: int) -> None:
        """A food or drink effect gained or faded on a player during the
        fight. A consumable logged as several effects is out only when the
        last of them has faded; a meal gained while none had been up since
        combat start is the one the no-food finding notes (build_issues)."""
        record = self._food_record(unit_id)
        up = record["up"]
        if change == "GAINED":
            if not up and record["ate"] is None and record["empty_since"] is None:
                record["ate"] = timestamp_ms
            up.add(str(ability_id))
            record["seen"].add(str(ability_id))
            record["empty_since"] = None
        elif change == "FADED":
            up.discard(str(ability_id))
            if not up and record["empty_since"] is None:
                record["empty_since"] = timestamp_ms

    def fight_units(self) -> Dict[str, tuple]:
        """What effect_rules measures a fight's rules on, unit id -> (kind,
        since_ms, gone_ms): the players ('self' or 'group'), and the
        hostiles the group hit in this fight ('boss' or 'enemy', by the
        game's flag less boss_units' exceptions) with the log time each
        was added and the time it died
        or was removed, None when it was there throughout. Enemies carry
        over from fight to fight within a zone, so a boss that only stands
        in the list, dead since the last pull, is not a boss of this fight:
        it has to have been hit."""
        units: Dict[str, tuple] = {}
        for unit_id, player in self.players.items():
            units[unit_id] = ("self" if player.is_local else "group", None, None)
        for unit_id in self.enemy_damage:
            enemy = self.enemies.get(unit_id)
            if enemy is None or not enemy.is_hostile:
                continue
            gone = [at for at in (enemy.died_at, enemy.removed_at) if at is not None]
            units[unit_id] = ("boss" if enemy.is_boss else "enemy", enemy.added_at,
                              min(gone) if gone else None)
        return units

    def get_combat_start_time_formatted(self, log_file_path: str = None, log_start_unix: int = None) -> str:
        """Get the combat start time formatted as local date/time."""
        if not self.start_time:
            return "Unknown Time"
        
        # Use the analyzer's absolute timestamp conversion method if available
        if hasattr(self, 'analyzer') and self.analyzer:
            return self.analyzer.get_absolute_timestamp_formatted(self.start_time)
        
        # Fallback: if we have log_start_unix, use it to convert relative timestamp to absolute
        if log_start_unix and self.start_time > 0:
            try:
                import datetime
                # log_start_unix is in seconds, self.start_time is relative milliseconds
                absolute_timestamp = log_start_unix + (self.start_time / 1000)
                dt = datetime.datetime.fromtimestamp(absolute_timestamp)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                pass
        
        # Final fallback: treat as absolute timestamp (for backward compatibility)
        try:
            import datetime
            # Convert milliseconds to seconds and create datetime
            dt = datetime.datetime.fromtimestamp(self.start_time / 1000)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            return "Unknown Time"

class ESOLogAnalyzer(ListenerMixin):
    """Main analyzer class for processing ESO encounter logs."""

    def __init__(self, list_hostiles: bool = False, diagnostic: bool = False):
        ListenerMixin.__init__(self)
        self.current_encounter: Optional[CombatEncounter] = None
        self.ability_cache: Dict[str, str] = {}  # ability_id -> ability_name
        self.ability_icons: Dict[str, str] = {}  # ability_id -> icon stem (data/icons/abilities/<stem>.png)
        self.scribing = ScribingTracker()  # each player's scripts for their scribed skills
        self.werewolf = werewolf.WerewolfTracker()  # each player's werewolf form, bar and morph
        self.casts = casts.CastRecorder()  # each player's casts, for the counts and cpm
        # Each player's magicka, stamina and ultimate spent and gained
        self.resources = resources.ResourceRecorder()
        # Companions (companions.py): whether their damage and healing are
        # their owner's too (the setting companions.accrue_to_owner), and
        # the skills each one cast this session, by (owner's player key,
        # monster id), in first-cast order
        self.companion_accrual = False
        self.companion_casts: dict[tuple[str, str], list[str]] = {}
        self.scribing_keys: Dict[str, str] = {}  # unit_id -> the tracker's key for that player
        self._scribing_characters: Dict[str, str] = {}  # tracker key -> character id last seen
        self.gear_cache: Dict[str, str] = {}  # gear_item_id -> gear_set_name
        self.current_zone: Optional[str] = None  # Track current zone name
        # The zone's id from ZONE_CHANGED: a solo dungeon is known by it
        # alone, its name being the group dungeon's (pen_crit.zone_kind)
        self.current_zone_id: str = ""
        self.current_difficulty: Optional[str] = None  # Track current difficulty
        self.zone_deaths: int = 0  # Track total deaths since entering current zone
        self.fight_deaths: int = 0  # Player deaths in the current fight (reset at BEGIN_COMBAT)
        self.subclass_analyzer = ESOSubclassAnalyzer()
        self.current_log_file: Optional[str] = None  # Track current log file path
        self.log_start_unix_timestamp: Optional[int] = None  # Unix timestamp from BEGIN_LOG event
        
        # Testing flag for listing hostile monsters
        self.list_hostiles = list_hostiles
        self.hostile_monsters: List[Tuple[str, str, str]] = []  # (unit_id, name, unit_type)
        self.engaged_monsters: Set[str] = set()  # Track monsters that appear in combat events
        
        # Diagnostic mode for debugging data flow and timing
        self.diagnostic = diagnostic

        # Zone history tracking for rewind functionality
        # (timestamp, zone_name, zone_id, difficulty)
        self.zone_history: List[Tuple[int, str, str, str]] = []
        self.max_zone_history = 10  # Keep last 10 zone changes

        # A player's gear rows as fight entries share them, by content
        # (issue #110): the same gear pull after pull is one list, not a
        # copy per fight (455 copies of 40 gear sets in a Sunspire night).
        # The rows are only read once built
        self._shared_gear: Dict[str, list] = {}
        
        
        # Session tracking for players going offline/online
        self.player_sessions: Dict[str, Dict] = {}  # handle+name -> {unit_id, name, equipped_abilities, gear_data, last_seen}
        # Each player's rows of this BEGIN_LOG session's fights, [(entry,
        # row)] by _mastery_key, to fill in a mastery found later
        self._mastery_rows: Dict[object, List[Tuple[FightHistoryEntry, dict]]] = {}
        # The character each handle was last seen on in this zone, which
        # tells a member back on another character (presence.py, rule 4)
        self._zone_characters: dict[str, str] = {}
        self.unit_id_to_handle: Dict[str, str] = {}  # unit_id -> handle
        
        # The per-fight buff/debuff timeline the fight pane's strip draws
        # (buff-timeline spec). Always on; a test may turn it off
        self.track_buff_timeline = True
        self.buff_timeline_recorder = BuffTimelineRecorder()
        # The user's tracked effects (effect_rules); build_analyzer sets the
        # rules from the config, an empty tracker records nothing
        self.effect_tracker = EffectTracker([])
        # The penetration and crit debuffs, buffs and status effects
        # (pen_crit): fixed rules of their own, so the user's rules text
        # cannot break the build window's figures. Fed wherever
        # effect_tracker is
        self.pen_crit_tracker = pen_crit.new_tracker()
        # A trial dummy's own debuffs were seen in this zone: a parse, so
        # the target has a trial boss's 18,200 resistance (pen_crit)
        self._dummy_seen = False
        # The build-issue rules judged over the session: the proc sets that
        # never fire, and who has taunted (build_issues)
        self.build_issues = BuildIssueTracker()
        # What the log names that the bundled game data does not know, and
        # the session's game version against the data's (data_staleness,
        # issue #173): sent to the listeners as it changes
        self.data_check = DataCheckTracker()

        # Which ability each of the players' recent casts was, by cast
        # tracking id: a TAUNTED event names its skill through it
        self._cast_abilities: Dict[str, str] = {}
        # Who opened each fight, and with what: the line under the fight
        # pane's table (fight_opener, issue #159)
        # (the cache's own get, not a lambda over self, which would tie the
        # analyzer in a reference cycle that only the cyclic GC frees)
        self.opener = fight_opener.OpenerRecorder(self.ability_cache.get, DAMAGE_RESULTS)

        # Which units each cast struck, for the area rule of the kinds of
        # damage (damage_kinds): shared by the recap recorder, the damage
        # record and the per-player tally of damage taken
        self.cast_index = CastIndex()
        # Death recaps: the last seconds before each player death
        self.death_recap_recorder = DeathRecapRecorder(
            self._resolve_recap_unit, self._resolve_recap_ability, self.cast_index)
        self.fight_death_recaps: List[dict] = []  # this fight's (reset with fight_deaths)
        # The fight entry just emitted and its start time, for a death that
        # is logged after END_COMBAT (see LATE_DEATH_GRACE_MS)
        self._last_fight_entry: Optional[FightHistoryEntry] = None
        self._last_fight_start: int = 0
        # A fight the game cut in two (see COMBAT_RESUME_MS): the entry
        # already emitted for its first part, brought up to date when the
        # fight really ends; when the group last hit each living enemy; and
        # the ones it was still hitting as END_COMBAT came
        self._resumed_fight_entry: Optional[FightHistoryEntry] = None
        self._enemy_last_hit: Dict[str, int] = {}
        self._engaged_at_end: FrozenSet[str] = frozenset()

        # Initialize the robust log parser
        from eso_log_parser import ESOLogParser
        self.log_parser = ESOLogParser()
        
        # Initialize gear set mapping database
        self._initialize_gear_database()

    def get_trial_name(self, trial_id: int) -> str:
        """Get trial name from trial ID."""
        return trial_result.trial_name(trial_id)

    def _add_zone_to_history(self, timestamp: int, zone_name: str, zone_id: str = "",
                             difficulty: str = ""):
        """Add a zone change to the history for rewind functionality."""
        self.zone_history.append((timestamp, zone_name, str(zone_id or ""), str(difficulty or "")))
        # Keep only the most recent zone changes
        if len(self.zone_history) > self.max_zone_history:
            self.zone_history.pop(0)

    def _rewind_to_last_zone(self) -> bool:
        """Rewind to the last known zone when combat events are encountered without current zone."""
        if not self.zone_history:
            return False

        # Get the most recent zone, with its id and difficulty
        last_timestamp, last_zone, last_zone_id, last_difficulty = self.zone_history[-1]

        _console(f"{Fore.YELLOW}No current zone detected. Rewinding to last zone: {last_zone}{Style.RESET_ALL}")

        # Set the current zone to the last known zone
        self.current_zone = last_zone
        self.current_zone_id = last_zone_id
        self.current_difficulty = last_difficulty
        
        # Create a new encounter for this zone
        self.current_encounter = CombatEncounter()
        self.current_encounter.start_time = last_timestamp
        
        return True

    def _process_log_file_from_position(self, log_file: Path, start_position: int = 0, end_position: Optional[int] = None) -> List[ESOLogEntry]:
        """Process a portion of the log file to find zone changes and combat events."""
        entries = []
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                if start_position > 0:
                    f.seek(start_position)
                
                for line in f:
                    if end_position and f.tell() > end_position:
                        break
                        
                    line = line.strip()
                    if line:
                        entry = self.log_parser.parse_line(line)
                        if entry:
                            entries.append(entry)
        except (IOError, UnicodeDecodeError) as e:
            _console(f"{Fore.RED}Error reading log file for rewind: {e}{Style.RESET_ALL}")
        
        return entries

    def _initialize_gear_database(self):
        """Initialize gear item ID to gear set name mapping."""
        # Use the gear set database instead of hardcoded data
        self.gear_cache = gear_set_db.item_to_set
        self.gear_set_abilities = gear_set_db.ability_to_set

    def _is_two_handed_weapon(self, gear_item: List[str], player_gear: Dict[str, List[str]]) -> bool:
        """
        Check if a gear item is a 2-handed weapon (staff, bow, 2H axe, 2H mace, 2H sword).

        Args:
            gear_item: List containing gear item data [slot, item_id, ...]
            player_gear: Complete gear dictionary for the player

        Returns:
            True if the item is a 2-handed weapon, False otherwise
        """
        if len(gear_item) < 2:
            return False
        # One rule for the fight view's piece counts and the build window's
        return is_two_handed(gear_item[0], gear_item[1], player_gear)

    def process_log_entry(self, entry: ESOLogEntry):
        """Process a single log entry."""
        # Skip None entries (failed to parse)
        if entry is None:
            return
            
        # Check grace period before processing any events
        # Grace period logic removed - encounters are finalized immediately on END_COMBAT
        
        if self.diagnostic and entry.event_type in ["ZONE_CHANGED", "UNIT_ADDED", "UNIT_CHANGED", "BEGIN_COMBAT", "END_COMBAT", "PLAYER_INFO", "COMBAT_EVENT", "EFFECT_CHANGED", "HEALTH_REGEN", "ENDLESS_DUNGEON_BEGIN", "ENDLESS_DUNGEON_STAGE_END", "ENDLESS_DUNGEON_BUFF_ADDED", "ENDLESS_DUNGEON_BUFF_REMOVED"]:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Processing {entry.event_type} at {entry.timestamp}{Style.RESET_ALL}")
        
        if entry.event_type == "UNIT_ADDED":
            self._handle_unit_added(entry)
        elif entry.event_type == "UNIT_CHANGED":
            self._handle_unit_changed(entry)
        elif entry.event_type == "UNIT_REMOVED":
            # Gone without a death line (a summoned add whose summoner died):
            # no longer an enemy the group is fighting, and the effects
            # still on it end here (the game writes no FADED for them)
            if entry.fields:
                self._enemy_last_hit.pop(entry.fields[0], None)
                self.effect_tracker.forget_unit(entry.fields[0], entry.timestamp)
                self.pen_crit_tracker.forget_unit(entry.fields[0], entry.timestamp)
                if self.current_encounter:
                    # A player who left: off the list from the next fight
                    # (presence.py)
                    self.current_encounter.player_left(entry.fields[0], entry.timestamp)
                    self.current_encounter.pet_ownership.pop(entry.fields[0], None)
                    self.current_encounter.companion_units.pop(entry.fields[0], None)
                    enemy = self.current_encounter.enemies.get(entry.fields[0])
                    if enemy is not None and enemy.removed_at is None:
                        enemy.removed_at = entry.timestamp
        elif entry.event_type == "ABILITY_INFO":
            self._handle_ability_info(entry)
        elif entry.event_type == "PLAYER_INFO":
            self._handle_player_info(entry)
        elif entry.event_type == "ZONE_CHANGED":
            self._handle_zone_changed(entry)
        elif entry.event_type == "BEGIN_CAST":
            if self.current_encounter:
                self._handle_begin_cast(entry)
        elif entry.event_type == "EFFECT_CHANGED":
            self._handle_effect_changed(entry)
        elif entry.event_type == "COMBAT_EVENT":
            if self.current_encounter:
                self._handle_combat_event(entry)
        elif entry.event_type == "BEGIN_COMBAT":
            self._handle_begin_combat_event(entry)
        elif entry.event_type == "END_COMBAT":
            self._handle_end_combat_event(entry)
        elif entry.event_type == "BEGIN_LOG":
            self._handle_begin_log_event(entry)
        elif entry.event_type == "TRIAL_INIT":
            self._handle_trial_init(entry)
        elif entry.event_type == "BEGIN_TRIAL":
            self._handle_begin_trial(entry)
        elif entry.event_type == "END_TRIAL":
            self._handle_end_trial(entry)
        elif entry.event_type == "END_LOG":
            self._handle_end_log_event(entry)
        elif entry.event_type == "HEALTH_REGEN":
            self._handle_health_regen(entry)
        elif entry.event_type == "ENDLESS_DUNGEON_BEGIN":
            self._handle_endless_dungeon_begin(entry)
        elif entry.event_type == "ENDLESS_DUNGEON_STAGE_END":
            self._handle_endless_dungeon_stage_end(entry)
        elif entry.event_type == "ENDLESS_DUNGEON_BUFF_ADDED":
            self._handle_endless_dungeon_buff_added(entry)
        elif entry.event_type == "ENDLESS_DUNGEON_BUFF_REMOVED":
            self._handle_endless_dungeon_buff_removed(entry)

    def _handle_unit_added(self, entry: ESOLogEntry):
        """Handle UNIT_ADDED events to track players and enemies."""
        # UNIT_ADDED format: timestamp,UNIT_ADDED,unit_id,unit_type,F/T,unknown,unknown,F/T,unknown,unknown,"name","@handle",...
        # After parsing, fields[0] = unit_id, fields[1] = unit_type, etc.
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: _handle_unit_added called with {len(entry.fields)} fields{Style.RESET_ALL}")
        
        if len(entry.fields) >= 10:
            # Correct field indexing after ESOLogEntry.parse() processing
            # fields[2:] was used in parsing, so indices are shifted
            unit_id = entry.fields[0]  # unit_id is in field 0
            unit_type = entry.fields[1]  # unit_type is in field 1
            
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: UNIT_ADDED unit_id={unit_id}, unit_type={unit_type}{Style.RESET_ALL}")
            
            # Handle player units
            if unit_type == "PLAYER":
                name = entry.fields[8] if len(entry.fields) > 8 else ""  # Name is in field 8
                handle = entry.fields[9] if len(entry.fields) > 9 else ""  # Handle is in field 9
                long_unit_id = entry.fields[10] if len(entry.fields) > 10 else ""  # Long unit ID is in field 10
                class_id = entry.fields[6] if len(entry.fields) > 6 else ""  # Class ID is in field 6
                champion_points = int(entry.fields[12]) if len(entry.fields) > 12 and entry.fields[12].isdigit() else 0  # Champion Points is in field 12
                self._note_scribing_identity(unit_id, entry.fields[3], long_unit_id)  # playerPerSessionId is in field 3
                race_id = entry.fields[7] if len(entry.fields) > 7 else ""  # Race ID is in field 7

                # Create encounter if it doesn't exist (UNIT_ADDED can happen before ZONE_CHANGED)
                if not self.current_encounter:
                    self.current_encounter = CombatEncounter()
                    self.current_encounter.start_time = entry.timestamp
                    if self.diagnostic:
                        timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                        _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: UNIT_ADDED created new encounter at {entry.timestamp}{Style.RESET_ALL}")
                
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: UNIT_ADDED player {unit_id}, encounter exists: {self.current_encounter is not None}{Style.RESET_ALL}")
                
                # Clean up name and handle (remove quotes if present)
                clean_name = name.strip('"') if name else ""
                clean_handle = handle.strip('"') if handle else ""
                # A loading placeholder: the real unit follows (presence.py)
                if self.current_encounter and clean_name != "Offline":
                    enc = self.current_encounter
                    if self.diagnostic:
                        timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                        _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Adding player {unit_id} ({clean_name}) to encounter{Style.RESET_ALL}")

                    # The same character back in the zone is the same row
                    # (presence.py, rule 3)
                    returning = enc.player_by_character(long_unit_id)
                    if returning is not None:
                        enc.alias_player(returning, unit_id)
                        added_player = returning
                    else:
                        # Another character of a handle seen in this zone:
                        # the old character is gone (rule 4)
                        switched = False
                        if clean_handle and long_unit_id and long_unit_id != "0":
                            switched = self._zone_characters.get(clean_handle, long_unit_id) != long_unit_id
                            for other in enc.players.values():
                                if (other.handle == clean_handle and other.character_id
                                        and other.character_id != long_unit_id):
                                    enc.player_left(other.latest_unit_id, entry.timestamp)
                        # Check if this is a returning player from session data
                        session_key = f"{clean_handle}+{clean_name}"
                        if session_key in self.player_sessions:
                            # Restore player from session data
                            self._restore_player_from_session(unit_id, clean_name, clean_handle)
                        else:
                            # New player - add normally with class ID and champion points
                            enc.add_player(unit_id, clean_name, clean_handle, class_id, champion_points)
                        added_player = enc.players.get(unit_id)
                        if added_player is not None:
                            added_player.joined_at = entry.timestamp
                            added_player.switched_character = switched
                            # A companion kept for this unit id is named
                            # after the player who has it now
                            enc.name_companions(unit_id)
                    if clean_handle and long_unit_id and long_unit_id != "0":
                        self._zone_characters[clean_handle] = long_unit_id

                    # Update session data
                    self._update_player_session(unit_id, clean_name, clean_handle, class_id=class_id, champion_points=champion_points)
                    # The race is not kept in session data: every UNIT_ADDED carries it
                    if added_player is not None:
                        added_player.race_id = race_id
                        # A returning player is restored with the champion
                        # points stored when first seen; this line's are newer
                        if champion_points > 0:
                            added_player.champion_points = champion_points
                        added_player.is_local = len(entry.fields) > 2 and entry.fields[2] == "T"
                        added_player.grouped = len(entry.fields) > 15 and entry.fields[15] == "T"
                        if long_unit_id and long_unit_id != "0":
                            added_player.character_id = long_unit_id

                    # Associate the long unit ID with the player
                    if long_unit_id and long_unit_id != "0":
                        enc.associate_long_unit_id(unit_id, long_unit_id)
            
            # Handle enemy units (MONSTER, NPC, etc.)
            elif unit_type in ["MONSTER", "NPC"]:
                name = entry.fields[8] if len(entry.fields) > 8 else ""
                health = 0
                is_hostile = False

                # Field [4] is the game's monster id (105634 in the
                # example), not a health figure; it has stood in for the
                # unit's max health until the first combat event on it
                # updates that, and the highest-health fallback name is
                # the only reader, so it is left as it was
                monster_id = entry.fields[4] if len(entry.fields) > 4 else ""
                if monster_id.isdigit():
                    health = int(monster_id)
                
                # Check if this is a HOSTILE monster (field [14] in the example)
                if len(entry.fields) > 14 and entry.fields[14] == "HOSTILE":
                    is_hostile = True
                
                # Add ALL monsters (including FRIENDLY) so they can be updated later via UNIT_CHANGED
                if self.current_encounter and name and name != '0':
                    clean_name = name.strip('"') if name else ""
                    
                    
                    enemy = EnemyInfo(unit_id, clean_name, unit_type)
                    enemy.max_health = health
                    enemy.current_health = health
                    # A unit id handed out again is a unit nobody has hit yet
                    self._enemy_last_hit.pop(unit_id, None)
                    enemy.is_hostile = is_hostile
                    enemy.monster_id = monster_id
                    enemy.boss_flag = len(entry.fields) > 5 and entry.fields[5] == "T"
                    # The game's flag, less the units that carry it without
                    # being the fight's boss (boss_units, issue #67)
                    enemy.is_boss = is_fight_boss(enemy.boss_flag, monster_id)
                    enemy.added_at = entry.timestamp
                    # A player's companion (companions.py): by its reaction,
                    # or by its monster id when it is another member's
                    enemy.is_companion = companions.is_companion(
                        monster_id, entry.fields[14] if len(entry.fields) > 14 else "")
                    if enemy.is_companion:
                        enemy.level = companions.level_of(
                            entry.fields[11] if len(entry.fields) > 11 else "")
                        # Never the log's name, which may carry a handle the
                        # log keeps from an anonymous owner: anon's until
                        # its owner is known (name_companions)
                        enemy.name = companions.shown_name(None)

                    self.current_encounter.enemies[unit_id] = enemy
                    # A departed player's unit id handed to this unit: the
                    # player is gone, and the id is not theirs (presence.py)
                    self.current_encounter.release_player_id(unit_id, entry.timestamp)
                    # The game names the owner of a summoned unit
                    # (ownerUnitId): a player's pet, whose damage and healing
                    # are that player's
                    self.current_encounter.track_pet_ownership(
                        unit_id, entry.fields[13] if len(entry.fields) > 13 else "0")

                    # Update highest health hostile monster (only if currently hostile)
                    if is_hostile:
                        self.current_encounter.update_highest_health_hostile(enemy)
                        
                        # Track hostile monsters for testing flag
                        if self.list_hostiles:
                            self.hostile_monsters.append((unit_id, clean_name, unit_type))

    def _handle_unit_changed(self, entry: ESOLogEntry):
        """Handle UNIT_CHANGED events to track when monsters become hostile."""
        # UNIT_CHANGED format: timestamp,UNIT_CHANGED,unit_id,class_id,race_id,name,display_name,character_id,level,champion_points,owner_unit_id,reaction,is_grouped_with_local_player
        # After parsing: fields[0]=unit_id, fields[3]=name, fields[8]=owner_unit_id, fields[9]=reaction
        if self.current_encounter and len(entry.fields) >= 10:
            unit_id = entry.fields[0]
            name = entry.fields[3] if len(entry.fields) > 3 else ""
            new_state = entry.fields[9] if len(entry.fields) > 9 else ""

            # An anonymous member named on joining the group takes the name
            # and handle (presence.py, rule 6); a player is otherwise who
            # they were added as
            player = self.current_encounter.player_of(unit_id)
            if player is not None:
                clean_name = name.strip('"')
                clean_handle = entry.fields[4].strip('"')
                if not player.handle and clean_handle and clean_handle != "0":
                    player.handle = clean_handle
                    if clean_name and clean_name != "0":
                        player.name = clean_name
                    self._update_player_session(unit_id, player.name, player.handle,
                                                class_id=player.class_id)
                    # Their companion is named after them from now on
                    self.current_encounter.name_companions(player.unit_id)
                # A champion point earned mid-session (fields[7])
                cp = entry.fields[7]
                if cp.isdigit() and int(cp) > 0 and int(cp) != player.champion_points:
                    player.champion_points = int(cp)
                    if player.handle:
                        self._update_player_session(unit_id, player.name, player.handle,
                                                    champion_points=int(cp))
                if len(entry.fields) > 10:
                    player.grouped = entry.fields[10] == "T"
                return

            # The owner can change after the unit was added: a pet that has
            # expired loses its owner a moment before its UNIT_REMOVED
            if unit_id in self.current_encounter.enemies:
                self.current_encounter.track_pet_ownership(unit_id, entry.fields[8])
            
            # Only process if this is a known enemy and it's becoming HOSTILE
            if (unit_id in self.current_encounter.enemies and 
                new_state == "HOSTILE" and name and name != '0'):
                
                enemy = self.current_encounter.enemies[unit_id]
                enemy.is_hostile = True
                
                # Update the enemy name to the new name from UNIT_CHANGED;
                # never a companion's, whose log name can carry an anonymous
                # owner's handle (companions.shown_name)
                clean_name = name.strip('"') if name else ""
                if not enemy.is_companion:
                    enemy.name = clean_name
                
                # Update highest health hostile monster now that this enemy is hostile
                self.current_encounter.update_highest_health_hostile(enemy)
                
                # Track hostile monsters for testing flag
                if self.list_hostiles:
                    self.hostile_monsters.append((unit_id, clean_name, enemy.unit_type))

    def _bar_slots(self, ability_ids: List[str],
                   scribed: Optional[Dict[str, Dict]] = None,
                   player_key: Optional[str] = None) -> List[Dict[str, str]]:
        """[{'id', 'name', 'icon'}] for a bar's ability ids, in slot order.

        Ids without a cached name are skipped, so the bar's name list (built
        from these slots) lines up with them one-to-one. *scribed* holds this
        player's scribing.slot_fields per scribed ability id: the id alone
        gives neither the skill's name nor its scripts. A Rampage, which the
        game lists for the logging player caught at full Fury, is shown as
        the werewolf morph it stands in for, its 'stand_in' naming what the
        log listed (werewolf.py); *player_key* says whose morph.
        """
        slots = []
        for ability_id in ability_ids:
            morph = self.werewolf.stand_in_for(player_key, str(ability_id)) if player_key else None
            if morph:
                slot = self._ability_slot(morph)
                slot['stand_in'] = self.log_parser.get_ability_name(ability_id) or 'Rampage'
                slots.append(slot)
                continue
            name = self.log_parser.get_ability_name(ability_id)
            if name:
                slot = {'id': str(ability_id), 'name': name,
                        'icon': self.ability_icons.get(str(ability_id), '')}
                if scribed:
                    slot.update(scribed.get(str(ability_id), {}))
                slots.append(slot)
        return slots

    def _note_companion_cast(self, companion: str, ability_id: str) -> None:
        """A cast by a companion: a companion skill (by its icon) joins the
        companion's bar for the session, in first-cast order. Keyed by the
        owner's player key, which outlives the zone's unit ids."""
        if not companions.bar_ability(self.ability_icons.get(str(ability_id), "")):
            return
        record = self.current_encounter.companions.get(companion)
        if record is None:
            return
        key = (self._scribing_player_key(record.owner_unit_id), record.monster_id)
        casts = self.companion_casts.setdefault(key, [])
        if ability_id not in casts:
            casts.append(ability_id)

    def _ability_slot(self, ability_id: str) -> Dict[str, str]:
        """A bar slot for *ability_id*: the log's name and icon for it, else
        the bundled werewolf table's (werewolf.SKILLS)."""
        name, icon = werewolf.SKILLS.get(ability_id, ("", ""))
        return {'id': ability_id,
                'name': self.log_parser.get_ability_name(ability_id) or name,
                'icon': self.ability_icons.get(ability_id) or icon}

    def _werewolf_fields(self, player, enc) -> Dict[str, object]:
        """The fight entry's werewolf fields for *player*, {} for one never
        in form during the fight: 'werewolf_share', the share of the fight
        spent in form, and 'werewolf_bar_slots', the bar rebuilt from the
        skills cast in form this session with the morph as its ultimate.
        A werewolf bar the log wrote is never used; _handle_player_info
        drops it."""
        bar = self.werewolf.fight_bar(self._scribing_player_key(player.unit_id),
                                      enc.start_time, enc.end_time)
        if bar is None:
            return {}
        fields: Dict[str, object] = {'werewolf_share': bar.share}
        slots = [dict(self._ability_slot(skill), werewolf=True) for skill in bar.skills]
        if bar.ultimate:
            slots.append(dict(self._ability_slot(bar.ultimate), werewolf=True, ultimate=True))
        fields['werewolf_bar_slots'] = slots
        return fields

    def _note_scribing_identity(self, unit_id: str, session_id: str, character_id: str):
        """Remember who a player unit is for the scribing tracker.

        UNIT_ADDED's playerPerSessionId stays with a player for the whole
        BEGIN_LOG session, anonymous players included; unit ids are handed
        out afresh in each zone.
        """
        if not session_id or session_id == "0":
            return
        key = f"session:{session_id}"
        self.scribing_keys[unit_id] = key
        if character_id and character_id != "0":
            # Another character under the same session id has its own skills
            if self._scribing_characters.get(key, character_id) != character_id:
                self.scribing.forget_player(key)
            self._scribing_characters[key] = character_id

    def _scribing_player_key(self, unit_id: str) -> str:
        """Who a script combination is tied to: the player's per-session id,
        else the unit id (valid until the next zone change)."""
        return self.scribing_keys.get(unit_id) or f"unit:{unit_id}"

    def _handle_ability_info(self, entry: ESOLogEntry):
        """Handle ABILITY_INFO events to cache ability names and gear sets."""
        # Check if entry is already a AbilityInfoEntry
        if hasattr(entry, 'ability_id') and hasattr(entry, 'ability_name'):
            # Entry is already parsed as AbilityInfoEntry
            parsed = entry
        else:
            # Entry needs to be parsed
            parsed = self.log_parser.parse_ability_info(entry)
            
        if parsed:
            # Update both caches with the parsed ability info
            self.ability_cache[parsed.ability_id] = parsed.ability_name
            self.log_parser.ability_cache[parsed.ability_id] = parsed.ability_name
            # Icon stem for the GUI's bundled icon set (empty when the line
            # carries no .dds path)
            from ability_icons import icon_stem
            stem = icon_stem(getattr(parsed, 'icon_path', ''))
            if stem:
                self.ability_icons[parsed.ability_id] = stem
            # A scribed skill's line (with its scripts, or without when the
            # game has none) is tied to the player whose PLAYER_INFO follows
            self.scribing.note_ability(parsed.ability_id, parsed.ability_name, stem,
                                       getattr(parsed, 'scribing', None),
                                       getattr(parsed, 'timestamp', None))

            # Check if this ability is actually a gear set (some gear sets appear as abilities)
            ability_name_lower = parsed.ability_name.lower()
            if any(set_name in ability_name_lower for set_name in ['bahsei', 'mother', 'sorrow', 'relequen', 'spell power', 'false god', 'deadly strike']):
                # This is a gear set ability - we can use it for gear set identification
                # Debug output removed for clean operation
                pass

    def _handle_player_info(self, entry: ESOLogEntry):
        """Handle PLAYER_INFO events to get equipped abilities and gear."""
        if self.diagnostic:
            _console(f"{Fore.MAGENTA}[DIAGNOSTIC] _handle_player_info called for unit_id: {entry.fields[0] if entry.fields else 'unknown'}{Style.RESET_ALL}")
        
        # Use the shared robust parser to handle the complex PLAYER_INFO format
        # Ensure caches are synchronized (both directions)
        self.log_parser.ability_cache = self.ability_cache  # Sync analyzer -> parser
        self.ability_cache.update(self.log_parser.ability_cache)  # Sync parser -> analyzer
        
        
        # Always use the parser to ensure we get the legacy format
        # The structured parser returns structured objects, but we need legacy format for compatibility
        player_info = self.log_parser.parse_player_info(entry)
            
        if player_info:
            if self.diagnostic:
                _console(f"{Fore.MAGENTA}[DIAGNOSTIC] player_info found for unit_id: {player_info.unit_id}{Style.RESET_ALL}")
            
            # This player's scribed skills: their name and scripts are the
            # player's own, not a property of the ability id
            scribed = {
                ability_id: slot_fields(resolution)
                for ability_id, resolution in self.scribing.resolve(
                    self._scribing_player_key(player_info.unit_id),
                    player_info.champion_points + player_info.additional_data,
                    player_info.timestamp).items()}
            # A transformation ultimate in the bars is the player's werewolf
            # morph, which a Rampage there stands in for (werewolf.py)
            player_key = self._scribing_player_key(player_info.unit_id)
            self.werewolf.note_bars(player_key,
                                    player_info.champion_points + player_info.additional_data)
            # Per-slot detail (id, name, icon stem) for the front and back
            # bar. A werewolf bar the game wrote in place of a human bar is
            # no human bar, and can be stale: it is dropped here, before any
            # reader of the bars sees it, and the werewolf bar is rebuilt
            # from casts as for every werewolf (werewolf.py, issue #49)
            logged_front = self._bar_slots(player_info.champion_points, scribed, player_key)
            logged_back = self._bar_slots(player_info.additional_data, scribed, player_key)
            front_bar_slots = [] if werewolf.is_werewolf_bar(player_info.champion_points) else logged_front
            back_bar_slots = [] if werewolf.is_werewolf_bar(player_info.additional_data) else logged_back
            # Sets, items and icons the bundled data does not know (issue #173)
            if self.data_check.note_player(player_info.gear_data, logged_front + logged_back):
                self._notify('on_data_check', self.data_check.check())
            # Ability names per bar, and all equipped names. The equipped
            # names keep every slot the log wrote, dropped bar included: a
            # player with none is one the log has not described, and is
            # left out of the fight entry
            front_bar_abilities = [slot['name'] for slot in front_bar_slots]
            back_bar_abilities = [slot['name'] for slot in back_bar_slots]
            equipped_ability_names = {slot['name'] for slot in logged_front + logged_back}

            # Find the player and set their equipped abilities and gear
            info_player = (self.current_encounter.player_of(player_info.unit_id)
                           if self.current_encounter else None)
            if info_player is not None:
                player = info_player
                if self.diagnostic:
                    _console(f"{Fore.MAGENTA}[DIAGNOSTIC] Found player {player.name} in current encounter, setting abilities{Style.RESET_ALL}")
                player.set_equipped_abilities(equipped_ability_names)
                player.set_front_back_bar_abilities(front_bar_abilities, back_bar_abilities,
                                                    front_bar_slots, back_bar_slots)
                player.set_gear(player_info.gear_data)
                player.long_term_effects = list(player_info.ability_ids)
                # The food and drink effects on the player as combat starts,
                # for the rule on a meal that runs out (build_issues)
                self.current_encounter.seed_food(
                    player.unit_id,
                    [a for a in player_info.ability_ids if str(a) in food_ids()])
                # Buffs on the player as combat starts, with no GAINED line
                # of their own (Lucent Echoes at the pull): the pen/crit
                # tracker opens their spans here (pen_crit)
                self.pen_crit_tracker.seed(player_info.ability_ids, player_info.unit_id,
                                           player_info.timestamp,
                                           self._unit_kind(player_info.unit_id))
                # Store equipped ability IDs for gear set detection (both bars)
                player._equipped_ability_ids = set(player_info.champion_points + player_info.additional_data)
            else:
                if self.diagnostic:
                    _console(f"{Fore.MAGENTA}[DIAGNOSTIC] No current encounter or player {player_info.unit_id} not in encounter{Style.RESET_ALL}")
            
            # Always update session data with new player info, regardless of encounter status
            # This ensures player data is available when they join encounters later
            # Get player name and handle from unit ID mapping or current encounter
            player_name = ""
            player_handle = ""
            player_class_id = None
            
            if info_player is not None:
                player = info_player
                player_name = player.name
                player_handle = player.handle
                player_class_id = player.class_id
            elif player_info.unit_id in self.unit_id_to_handle:
                player_handle = self.unit_id_to_handle[player_info.unit_id]
                # Try to find player name from existing sessions
                for session_key, session_data in self.player_sessions.items():
                    if session_data.get('unit_id') == player_info.unit_id:
                        player_name = session_data.get('name', '')
                        player_class_id = session_data.get('class_id')
                        break
            
            if player_handle:  # Only update if we have a handle
                self._update_player_session(
                    player_info.unit_id,
                    player_name,
                    player_handle,
                    equipped_ability_names,
                    player_info.gear_data,
                    player_class_id,
                    long_term_effects=list(player_info.ability_ids)
                )
                

    def _handle_zone_changed(self, entry: ESOLogEntry):
        """Handle ZONE_CHANGED events to reset all known players."""
        # ZONE_CHANGED format: zone_id, zone_name, difficulty
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: _handle_zone_changed called{Style.RESET_ALL}")
        
        if len(entry.fields) >= 3:
            zone_id = entry.fields[0].strip('"')
            zone_name = entry.fields[1].strip('"')
            difficulty = entry.fields[2].strip('"')
            
            _console(f"\n{Fore.YELLOW}=== ZONE CHANGED ==={Style.RESET_ALL}")
            _console(f"{Fore.YELLOW}Zone: {zone_name} ({difficulty}){Style.RESET_ALL}")
            
            # If there's an active encounter when zone changes, display it if it ended but wasn't shown
            if (self.current_encounter and self.current_encounter.combat_ended_at and 
                not self.current_encounter.finalized and self.current_encounter.players):
                self.current_encounter.finalized = True
                self._publish_fight(self.current_zone)
            
            # Reset any existing encounter
            if self.current_encounter:
                self.current_encounter = None
            
            # Update current zone and difficulty after processing previous zone's combat
            self.current_zone = zone_name
            self.current_zone_id = zone_id
            self.current_difficulty = difficulty
            self._notify('on_zone_changed', zone_name, difficulty)

            # Add this zone change to history for rewind functionality
            self._add_zone_to_history(entry.timestamp, zone_name, zone_id, difficulty)
            
            # Clean up offline players
            self._cleanup_offline_players()
            self._zone_characters = {}

            # Reset death counters for new zone
            self.zone_deaths = 0
            self.fight_deaths = 0
            self.fight_death_recaps = []
            self._last_fight_entry = None
            self._resumed_fight_entry = None
            # Unit ids are handed out afresh in each zone: the tracked
            # effects on hostiles and pets end here
            self.effect_tracker.zone_changed(entry.timestamp)
            self.pen_crit_tracker.zone_changed(entry.timestamp)
            self._dummy_seen = False
            self._enemy_last_hit.clear()
            self._engaged_at_end = frozenset()
            self.death_recap_recorder.reset()
            self.cast_index.reset()
            self.scribing.forget_players("unit:")
            # The opener's memory starts again (the entry's timestamp is the
            # zone id: the line's own time is its first field)
            self.opener.reset(casts.line_time(entry.original_line))

            # Reset all tracking - create new encounter for this zone
            self.current_encounter = CombatEncounter()
            self.current_encounter.start_time = entry.timestamp
            
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: ZONE_CHANGED created new encounter at {entry.timestamp}{Style.RESET_ALL}")

    def _handle_begin_combat_event(self, entry: ESOLogEntry):
        """Handle BEGIN_COMBAT events to start combat tracking."""
        # BEGIN_COMBAT format: timestamp,BEGIN_COMBAT (no additional data)
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: BEGIN_COMBAT at {entry.timestamp}, encounter exists: {self.current_encounter is not None}, players: {len(self.current_encounter.players) if self.current_encounter else 0}{Style.RESET_ALL}")
        
        # Check if we need to rewind to a previous zone
        if not self.current_zone and self.zone_history:
            self._rewind_to_last_zone()

        # The fight that just ended, cut in two by the game: carry on with it
        if self._continues_last_fight(entry.timestamp):
            self._resume_last_fight()
            return

        # Per-fight death counter starts fresh with each combat; so do the
        # fight's casts in the kinds index and the recorder's list of recaps
        self.fight_deaths = 0
        self.fight_death_recaps = []
        self.cast_index.new_fight()
        self.death_recap_recorder.new_fight()
        self._last_fight_entry = None
        self._resumed_fight_entry = None
        self._enemy_last_hit.clear()
        self._engaged_at_end = frozenset()

        # Grace period logic removed - encounters are finalized immediately on END_COMBAT

        # If we have a previous encounter that ended but wasn't displayed, display it now
        if (self.current_encounter and self.current_encounter.combat_ended_at and
            not self.current_encounter.finalized and self.current_encounter.players):
            self.current_encounter.finalized = True
            self._publish_fight(self.current_zone)
            # Don't reset to None - we'll reuse the encounter and preserve players
        
        # Create a new encounter if we don't have one or if the previous one was finalized
        if not self.current_encounter or self.current_encounter.finalized:
            # Create new encounter but preserve players and enemies from previous encounter in same zone
            old_players = {}
            old_enemies = {}
            old_pets = {}
            old_companions = {}
            old_companion_units = {}
            if self.current_encounter:
                if self.current_encounter.players:
                    old_players = self.current_encounter.players.copy()
                if self.current_encounter.enemies:
                    old_enemies = self.current_encounter.enemies.copy()
                old_pets = self.current_encounter.pet_ownership.copy()
                old_companions = self.current_encounter.companions.copy()
                old_companion_units = self.current_encounter.companion_units.copy()

            self.current_encounter = CombatEncounter()

            # Restore players, enemies and pets from previous encounter (they persist across combats in same zone)
            self.current_encounter.players = old_players
            self.current_encounter.enemies = old_enemies
            self.current_encounter.pet_ownership = old_pets
            self.current_encounter.companions = old_companions
            self.current_encounter.companion_units = old_companion_units

            # Reset resource tracking for all players for the new encounter
            for player in self.current_encounter.players.values():
                player.reset_resources()

        # Players who left are off the new fight's list; one who came back
        # on a new unit id is keyed by it from here (presence.py)
        self.current_encounter.start_fight_roster()

        # Mark combat as active and set start time to BEGIN_COMBAT timestamp
        self.current_encounter.in_combat = True
        self.current_encounter.start_time = entry.timestamp
        # The opener: the memory of the moments before the line becomes
        # the fight's candidates (fight_opener)
        self.current_encounter.opening = self.opener.begin_combat(entry.timestamp)
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: After BEGIN_COMBAT, players: {len(self.current_encounter.players)}{Style.RESET_ALL}")

    def _continues_last_fight(self, timestamp_ms: int) -> bool:
        """Whether a BEGIN_COMBAT at *timestamp_ms* carries on the fight that
        just ended instead of starting one (see COMBAT_RESUME_MS): it follows
        the END_COMBAT closely, and an enemy the group was hitting when the
        fight ended is still alive."""
        enc = self.current_encounter
        if (self._last_fight_entry is None or enc is None or not enc.finalized
                or enc.combat_ended_at is None):
            return False
        if not 0 <= timestamp_ms - enc.combat_ended_at <= COMBAT_RESUME_MS:
            return False
        # Not any enemy hit since: the group's damage often reaches the next
        # pack between the two lines, and that is a new fight
        return any(unit_id in self._enemy_last_hit for unit_id in self._engaged_at_end)

    def _resume_last_fight(self):
        """Reopen the encounter END_COMBAT closed. Its damage, deaths and
        players are kept, and the entry frontends already have is brought up
        to date when the fight ends (see _publish_fight)."""
        enc = self.current_encounter
        enc.finalized = False
        enc.in_combat = True
        enc.combat_ended_at = None
        enc.end_time = 0
        # A combat event between the two lines moved the start
        # (see _handle_combat_event)
        enc.start_time = self._last_fight_start
        self._resumed_fight_entry = self._last_fight_entry
        # The opener stands; what came between the two lines is dropped
        self.opener.resume()

    def _note_enemy_hit(self, entry: ESOLogEntry):
        """Remember when the group last hit each living enemy, which tells a
        fight the game cut in two from a new one (see _continues_last_fight)."""
        enc = self.current_encounter
        target_unit_id = entry.fields[17]
        enemy = enc.enemies.get(target_unit_id)
        if enemy is None or not enemy.is_hostile:
            return
        source_unit_id = entry.fields[7]
        if not (enc.find_player_by_unit_id(source_unit_id)
                or source_unit_id in enc.pet_ownership):
            return
        # The target's health after the hit: "current/max"
        health = entry.fields[18].split("/")[0] if len(entry.fields) > 18 else ""
        if health == "0":
            self._enemy_last_hit.pop(target_unit_id, None)
        else:
            self._enemy_last_hit[target_unit_id] = entry.timestamp

    def _handle_end_combat_event(self, entry: ESOLogEntry):
        """Handle END_COMBAT events to start grace period for combat tracking."""
        # END_COMBAT format: timestamp,END_COMBAT (no additional data)
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_COMBAT at {entry.timestamp}, encounter exists: {self.current_encounter is not None}, players: {len(self.current_encounter.players) if self.current_encounter else 0}{Style.RESET_ALL}")
        
        # The opener's pending millisecond settles into the fight before it
        # is built, and a new memory starts (fight_opener)
        self.opener.end_combat(entry.timestamp)

        # The living enemies the group hit in the fight's last seconds: if
        # combat starts again at once, they tell whether it is the same fight
        self._engaged_at_end = frozenset(
            unit_id for unit_id, hit in self._enemy_last_hit.items()
            if entry.timestamp - hit <= ENGAGED_ENEMY_MS)

        # Immediately finalize encounter if there are any players
        if self.current_encounter and self.current_encounter.players:
            self.current_encounter.end_time = entry.timestamp
            self.current_encounter.combat_ended_at = entry.timestamp
            self.current_encounter.in_combat = False
            # Immediately display summary and finalize encounter
            self.current_encounter.finalized = True
            self._publish_fight(self.current_zone)

    # Grace period logic removed - encounters are finalized immediately on END_COMBAT


    def get_absolute_timestamp(self, relative_timestamp_ms: int) -> Optional[int]:
        """Convert a relative timestamp (milliseconds since logging began) to absolute Unix timestamp."""
        if self.log_start_unix_timestamp and relative_timestamp_ms >= 0:
            # log_start_unix_timestamp is in seconds, relative_timestamp_ms is in milliseconds
            return self.log_start_unix_timestamp + (relative_timestamp_ms / 1000)
        return None

    def get_absolute_timestamp_formatted(self, relative_timestamp_ms: int) -> str:
        """Convert a relative timestamp to formatted absolute time string."""
        absolute_timestamp = self.get_absolute_timestamp(relative_timestamp_ms)
        if absolute_timestamp:
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(absolute_timestamp)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                pass
        return "Unknown Time"

    def _handle_begin_log_event(self, entry: ESOLogEntry):
        """Handle BEGIN_LOG events to extract Unix timestamp."""
        # BEGIN_LOG format: timestamp,BEGIN_LOG,unix_timestamp,version,"server","language","build"
        # The Unix timestamp is in the entry.timestamp field (fields[2] from original line)
        # Note: The timestamp in the log is in milliseconds, convert to seconds for Unix timestamp
        if entry.timestamp > 0:
            self.log_start_unix_timestamp = entry.timestamp // 1000  # Convert milliseconds to seconds
        # Relative-ms offsets restart with each BEGIN_LOG session (the
        # entry's timestamp is the Unix time: the line's own is its first
        # field)
        self.opener.reset(casts.line_time(entry.original_line), new_session=True)
        self.buff_timeline_recorder.reset()
        self.effect_tracker.reset()
        self.pen_crit_tracker.reset()
        self.death_recap_recorder.reset()
        self.cast_index.reset()
        self._last_fight_entry = None
        self._resumed_fight_entry = None
        self._enemy_last_hit.clear()
        self._engaged_at_end = frozenset()
        # A mastery found from here on is not filled into the last
        # session's fights: a character may have changed between sessions
        self._mastery_rows.clear()
        # The game lists every script combination again in a new session,
        # and numbers its players anew
        self.scribing.reset()
        self.scribing_keys.clear()
        self._scribing_characters.clear()
        self.werewolf.reset()
        self.casts.reset()
        self.resources.reset()
        self.build_issues.reset()
        # The game version that wrote this session, the line's last field
        # ("eso.live.12.1"), against the bundled data's (data_staleness)
        self.data_check.reset(entry.fields[4] if len(entry.fields) > 4 else "")
        self._notify('on_data_check', self.data_check.check())

    def _handle_trial_init(self, entry: ESOLogEntry):
        """TRIAL_INIT: the state of the instance's trial on entering it.
        Only reported: a completed=T here is a run finished before this
        session or split, not one of its fights' (trial_result)."""
        # TRIAL_INIT format: timestamp,TRIAL_INIT,id,inProgress,completed,startTimeMS,durationMS,success,finalScore
        if len(entry.fields) >= 8 and self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: TRIAL_INIT - ID: {entry.fields[0]}, "
                     f"Completed: {entry.fields[2]}, Success: {entry.fields[5]}, "
                     f"Score: {entry.fields[6]}{Style.RESET_ALL}")

    def _handle_begin_trial(self, entry: ESOLogEntry):
        """BEGIN_TRIAL: the trial's timer started. Only reported."""
        # BEGIN_TRIAL format: timestamp,BEGIN_TRIAL,id,startTimeMS
        if len(entry.fields) >= 2 and self.diagnostic:
            trial_id = int(entry.fields[0]) if entry.fields[0].isdigit() else 0
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: BEGIN_TRIAL - "
                     f"{self.current_zone or self.get_trial_name(trial_id)} (ID: {trial_id}), "
                     f"Start: {entry.fields[1]}{Style.RESET_ALL}")

    def _handle_end_trial(self, entry: ESOLogEntry):
        """END_TRIAL: the run's result (trial_result), for the fight it
        ended. The line comes inside the final fight, which carries it from
        END_COMBAT on; when it comes after that fight was sent (an arena's,
        about 4 seconds later), the sent entry takes it and frontends are
        told. A run that did not succeed has no result."""
        # END_TRIAL format: timestamp,END_TRIAL,id,durationMS,success,finalScore,finalVitalityBonus
        result = trial_result.from_end_trial(entry.fields, self.current_zone,
                                             self.current_difficulty)
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_TRIAL - "
                     f"{trial_result.result_text(result) if result else entry.fields}{Style.RESET_ALL}")
        if result is None:
            return
        # The line's own moment, for the frontends that act on the result
        # before the fight carrying it is delivered (the score banner,
        # issue #167): END_COMBAT trails a successful END_TRIAL by up to
        # 6 s on the real logs (median 0 s, p90 5.9 s over 148 runs), and
        # the banner is on screen for ten seconds from this line
        result['ended_epoch'] = self.get_absolute_timestamp(entry.timestamp)
        self._notify('on_trial_result', result)
        enc = self.current_encounter
        if enc is None:
            return
        # Finalized, not in_combat, tells a fight already sent: any combat
        # event after END_COMBAT sets in_combat again (Blackrose Prison's
        # END_TRIAL follows a few such events)
        if enc.finalized:
            if self._last_fight_entry is not None:
                # On the encounter too: should the fight carry on (see
                # COMBAT_RESUME_MS), its entry is built again from it
                enc.trial_result = result
                self._last_fight_entry.trial_result = result
                self._notify('on_fight_updated', self._last_fight_entry)
        elif enc.in_combat:
            enc.trial_result = result

    def _handle_end_log_event(self, entry: ESOLogEntry):
        """Handle END_LOG events."""
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_LOG detected{Style.RESET_ALL}")

    def _handle_begin_cast(self, entry: ESOLogEntry):
        """Handle BEGIN_CAST events."""
        if not self.current_encounter:
            self.current_encounter = CombatEncounter()

        # Only set combat start time if we're not already in combat and not finalized
        # This prevents BEGIN_CAST from overriding BEGIN_COMBAT timestamps or finalized encounters
        if not self.current_encounter.in_combat and not self.current_encounter.finalized:
            self.current_encounter.in_combat = True
            self.current_encounter.start_time = entry.timestamp

        # BEGIN_CAST format: durationMS, channeled, castTrackId, abilityId, <sourceUnitState>, <targetUnitState>
        # sourceUnitState: unitId, health/max, magicka/max, stamina/max, ultimate/max, werewolf/max, shield, x, y, heading
        if len(entry.fields) >= 7:
            ability_id = entry.fields[3]  # abilityId
            caster_unit_id = entry.fields[4]  # sourceUnitState.unitId

            # The opener (fight_opener): every cast names its cast id; a
            # player-side cast at a hostile, or a hostile's at a player-side
            # unit, is weighed
            self.opener.note_cast(entry.fields[2], ability_id)
            if self.opener.listening and len(entry.fields) > 15:
                self._feed_opener_cast(entry, ability_id, caster_unit_id)

            # Remembered for the taunt the cast may land (see TAUNTED in
            # _handle_combat_event)
            caster = self.current_encounter.player_of(caster_unit_id)
            if caster is not None:
                self._remember_cast(entry.fields[2], ability_id)
                # Counted for the build window and the cpm (casts.py)
                cast_time = casts.line_time(entry.original_line)
                self.casts.note_cast(caster.unit_id, entry.fields[2], ability_id, cast_time)
                # The cast's cost is in the state it carries (resources.py)
                self.resources.note_cast(caster.unit_id, cast_time, entry.fields[2], ability_id)
                if len(entry.fields) >= 9:
                    self.resources.observe(caster.unit_id, cast_time, entry.fields[6],
                                           entry.fields[7], entry.fields[8])
                # Werewolf form: the skills of the bar the log never writes,
                # and the morph (werewolf.py)
                if ability_id in werewolf.CAST_IDS:
                    self.werewolf.note_cast(self._scribing_player_key(caster_unit_id),
                                            ability_id, entry.timestamp)

            if self.diagnostic and caster_unit_id == "31":
                _console(f"{Fore.MAGENTA}[DIAGNOSTIC] BEGIN_CAST for unit_id 31: {entry.fields[5:8] if len(entry.fields) >= 8 else 'insufficient fields'}{Style.RESET_ALL}")

            # A companion's skills, for the bar on its row, and its casts,
            # counted like a player's under its row key (companions.py)
            companion = self.current_encounter.companion_key(caster_unit_id)
            if companion is not None:
                self._note_companion_cast(companion, ability_id)
                self.casts.note_cast(companion, entry.fields[2], ability_id,
                                     casts.line_time(entry.original_line))

            if ability_id in self.ability_cache:
                ability_name = self.ability_cache[ability_id]
                self.current_encounter.add_ability_use(caster_unit_id, ability_name)

            # Parse resource information: health/max, magicka/max, stamina/max in fields 5, 6, 7
            if len(entry.fields) >= 8:
                self._parse_and_update_player_resources(caster_unit_id, entry.fields[5:8])
                # Also update enemy health if the caster is an enemy
                self._parse_and_update_enemy_health(caster_unit_id, entry.fields[5:8])


    def _note_mastery(self, source_unit_id: str, ability_id: str):
        """Note the Class Mastery a gained effect or a resource gain names on
        its source, when that is a player of the mastery's class, or a pet
        of one (eso_sets.mastery_of_effect; Cycle Unending is fired by the
        Necromancer's pets). Kept on the player and in their session for
        the rest of the session, a mastery not changing between fights, and
        filled into their earlier fights of the session
        (_backfill_mastery). Any other id returns at once: resource gains
        are among the commonest lines."""
        if str(ability_id) not in mastery_effect_table():
            return
        holder = self.current_encounter.player_of(source_unit_id)
        if holder is None:
            owner = self.current_encounter.pet_ownership.get(source_unit_id)
            holder = self.current_encounter.player_of(owner) if owner else None
        if holder is None:
            return
        holder_class = holder.get_class_name()
        mastery = mastery_of_effect(ability_id, None if holder_class == "Unknown" else holder_class)
        if mastery and mastery not in holder.masteries_seen:
            holder.masteries_seen.append(mastery)
            self._update_player_session(holder.unit_id, holder.name, holder.handle,
                                        masteries=holder.masteries_seen)
            self._backfill_mastery(holder, mastery)

    @staticmethod
    def _mastery_key(player: PlayerInfo):
        """Who a fight row's masteries belong to over the session: the
        handle+name key a named player's masteries are kept under
        (_update_player_session), else the player's own record, which an
        anonymous player keeps until the zone changes."""
        handle = (player.handle or "").strip('"')
        name = (player.name or "").strip('"')
        return f"{handle}+{name}" if handle and name else player

    def _index_mastery_rows(self, entry: FightHistoryEntry):
        """Keep each player's row of a fight just delivered under who they
        are (_mastery_key), for _backfill_mastery. A fight the game cut in
        two comes again with new rows, which replace its old ones."""
        enc = self.current_encounter
        for row in entry.players:
            player = None if row.get('companion') else enc.players.get(str(row.get('unit_id', '')))
            if player is None:
                continue
            rows = self._mastery_rows.setdefault(self._mastery_key(player), [])
            rows[:] = [(fight, old) for fight, old in rows if fight is not entry]
            rows.append((entry, row))

    def _backfill_mastery(self, holder: PlayerInfo, mastery: str):
        """Fill a mastery just found into the holder's rows of the earlier
        fights of this BEGIN_LOG session that show fewer than two, and
        announce each of those fights again (eso_sets: a proc mastery is
        known only once it fires, and a mastery does not change within a
        session). A row that already shows two keeps them: a third would
        be an id credited by mistake. The row gets a new list, as the
        frontends may be reading the old one."""
        changed = {}
        for entry, row in self._mastery_rows.get(self._mastery_key(holder), ()):
            shown = list(row.get('masteries') or [])
            if mastery in shown or len(shown) >= MAX_MASTERIES:
                continue
            row['masteries'] = shown + [mastery]
            changed[id(entry)] = entry
        for entry in changed.values():
            self._notify('on_fight_updated', entry)

    def _observe_resources(self, entry: ESOLogEntry):
        """A COMBAT_EVENT's source and target states for the players' pools
        (resources.py). Fields after the time and event type: [7] the
        source unit state's id, [9..11] its magicka, stamina and ultimate,
        [17] the target's id or "*" (the source itself), [19..21] its
        pools. A POWER_ENERGIZE's pool is the target's, given by the source
        when that is another player."""
        fields = entry.fields
        enc = self.current_encounter
        source = enc.player_of(fields[7])
        target = enc.player_of(fields[17]) if fields[17] != "*" else source
        energize = resources.energize_of(fields)
        # A channel tick that carries its skill's cost (Fatecarver)
        if source is not None and fields[6] in resources.CHANNEL_TICKS:
            self.resources.note_cast(source.unit_id, entry.timestamp, fields[5],
                                     resources.CHANNEL_TICKS[fields[6]], counted=False)
        # The same player twice is observed once, with the gain
        same = target is source
        if source is not None:
            self.resources.observe(
                source.unit_id, entry.timestamp, fields[9], fields[10], fields[11],
                energize + ("",) if energize is not None and same else None)
        if not same and target is not None and len(fields) > 21:
            giver = ""
            if energize is not None and source is not None and source is not target:
                giver = source.unit_id
            self.resources.observe(
                target.unit_id, entry.timestamp, fields[19], fields[20], fields[21],
                energize + (giver,) if energize is not None else None)

    def _parse_and_update_enemy_health(self, unit_id: str, resource_fields: List[str]):
        """Parse health information and update the corresponding enemy's maximum health."""
        if not self.current_encounter:
            return

        # Check if this unit is an enemy
        enemy = self.current_encounter.enemies.get(unit_id)
        if not enemy:
            return

        # A companion's health pool, for its row: the unit's own max_health
        # starts at its monster id (see _handle_unit_added) and only grows
        companion = self.current_encounter.companion_key(unit_id)
        if companion is not None and resource_fields and "/" in resource_fields[0]:
            try:
                pool = int(resource_fields[0].split("/")[1])
            except (ValueError, IndexError):
                pool = 0
            record = self.current_encounter.companions.get(companion)
            if record is not None and pool > record.max_health:
                record.max_health = pool

        # Parse health field: "current/max" - we want the max (second number)
        try:
            if len(resource_fields) >= 1 and "/" in resource_fields[0]:
                current_health, max_health = resource_fields[0].split("/")
                max_health = int(max_health)
                if max_health > 0 and max_health > enemy.max_health:
                    enemy.max_health = max_health
                    enemy.current_health = int(current_health)
                    # Update highest health hostile if this enemy is hostile
                    if enemy.is_hostile:
                        self.current_encounter.update_highest_health_hostile(enemy)
        except (ValueError, IndexError):
            pass  # Skip invalid health data

    def _parse_and_update_player_resources(self, unit_id: str, resource_fields: List[str]):
        """Parse resource information and update the corresponding player's maximum values."""
        if not self.current_encounter:
            return

        # Find the player by unit ID (handles both short and long unit IDs)
        player = self.current_encounter.find_player_by_unit_id(unit_id)

        if not player:
            return

        # Parse resource fields: [health_current/health_max, magicka_current/magicka_max, stamina_current/stamina_max]
        try:
            if len(resource_fields) >= 1 and "/" in resource_fields[0]:
                # Health format: "current/max" - we want the max (second number)
                current_health, max_health = resource_fields[0].split("/")
                max_health = int(max_health)
                player.update_resources(health=max_health)

            if len(resource_fields) >= 2 and "/" in resource_fields[1]:
                # Magicka format: "current/max" - we want the max (second number)
                current_magicka, max_magicka = resource_fields[1].split("/")
                max_magicka = int(max_magicka)
                # Only update if max is not 0 (0/0 means empty resource, not max=0)
                if max_magicka > 0:
                    player.update_resources(magicka=max_magicka)

            if len(resource_fields) >= 3 and "/" in resource_fields[2]:
                # Stamina format: "current/max" - we want the max (second number)
                current_stamina, max_stamina = resource_fields[2].split("/")
                max_stamina = int(max_stamina)
                # Only update if max is not 0 (0/0 means empty resource, not max=0)
                if max_stamina > 0:
                    player.update_resources(stamina=max_stamina)

        except (ValueError, IndexError):
            pass  # Skip invalid resource data

    def _handle_combat_event(self, entry: ESOLogEntry):
        """Handle COMBAT_EVENT events."""
        
        # Check if we need to rewind to a previous zone
        if not self.current_zone and self.zone_history:
            self._rewind_to_last_zone()
        
        if not self.current_encounter:
            self.current_encounter = CombatEncounter()
            self.current_encounter.start_time = entry.timestamp

        if not self.current_encounter.in_combat:
            self.current_encounter.in_combat = True
            self.current_encounter.start_time = entry.timestamp

        # The players' pools in the source and target states, and a gain the
        # row logs (resources.py)
        if len(entry.fields) > 17:
            self._observe_resources(entry)

        # A mastery that gives resources is logged only as the gain, the
        # source its holder (Conservation of Energy, Share the Spoils)
        if len(entry.fields) > 7 and entry.fields[0] == resources.ENERGIZE:
            self._note_mastery(entry.fields[7], entry.fields[6])

        # Track damage events for DPS calculation (only friendly damage)
        # COMBAT_EVENT format: timestamp,COMBAT_EVENT,event_type,damage_type,source_unit_id,damage_value,...
        if len(entry.fields) >= 4:
            combat_event_type = entry.fields[0]  # DAMAGE/CRITICAL_DAMAGE is at index 0

            # A damage-over-time tick tells the tracked effects that its
            # ability is a DoT, which a ``dots`` rule (Touch of Z'en) counts
            if (combat_event_type in ('DOT_TICK', 'DOT_TICK_CRITICAL')
                    and self.effect_tracker and len(entry.fields) > 6):
                self.effect_tracker.dot_tick(entry.fields[6])

            if self.diagnostic and len(entry.fields) >= 10:
                unit_id = entry.fields[0]
                if unit_id == "31":
                    _console(f"{Fore.MAGENTA}[DIAGNOSTIC] COMBAT_EVENT for unit_id 31: {entry.fields[9:12] if len(entry.fields) >= 12 else 'insufficient fields'}{Style.RESET_ALL}")
            
            # Track any monster that appears in combat events as "engaged"
            if self.list_hostiles and self.current_encounter:
                # COMBAT_EVENT format: timestamp,COMBAT_EVENT,actionResult,damageType,powerType,hitValue,overflow,castTrackId,abilityId,sourceUnitState,targetUnitState
                # After parsing: fields[0]=actionResult, fields[1]=damageType, ..., fields[8]=sourceUnitId, fields[17]=targetUnitId
                if combat_event_type in ['DAMAGE', 'CRITICAL_DAMAGE']:
                    if len(entry.fields) > 17:
                        source_unit_id = entry.fields[7]  # Source unit (dealing damage)
                        target_unit_id = entry.fields[17]  # Target unit (receiving damage)
                        
                        # Track when players damage hostile monsters
                        if (target_unit_id and target_unit_id in self.current_encounter.enemies):
                            enemy = self.current_encounter.enemies[target_unit_id]
                            if enemy.is_hostile:
                                # Check if source is a player or player's pet
                                if (self.current_encounter.find_player_by_unit_id(source_unit_id) or 
                                    source_unit_id in self.current_encounter.pet_ownership):
                                    self.engaged_monsters.add(target_unit_id)
            
            if combat_event_type in ENEMY_HIT_RESULTS and len(entry.fields) > 17:
                self._note_enemy_hit(entry)

            # The opener (fight_opener): any line between the group and a
            # hostile, whatever its result or value, since a shield absorb's
            # partner can carry 0
            if self.opener.listening and len(entry.fields) > 17:
                self._feed_opener_event(entry, combat_event_type)

            # Taunts: a TAUNTED result shares its cast tracking id with the
            # taunting skill's own cast and hits, which name the skill
            if (len(entry.fields) > 17
                    and self.current_encounter.player_of(entry.fields[7]) is not None):
                if combat_event_type == TAUNTED:
                    self.current_encounter.note_taunt(
                        self.current_encounter.record_id(entry.fields[7]),
                        self._cast_abilities.get(entry.fields[5], ""))
                else:
                    self._remember_cast(entry.fields[5], entry.fields[6])

            # Death recap: keep what each player receives (damage, heals,
            # shields, dodges) for the seconds before a death
            if combat_event_type in RECAP_RESULTS and len(entry.fields) > 17:
                recap_target = entry.fields[17] if entry.fields[17] != '*' else entry.fields[7]
                if self.current_encounter.player_of(recap_target) is not None:
                    self._note_hit_on_player(entry, combat_event_type, recap_target)

            # Track death events.
            # Player deaths arrive as DIED, or as KILLING_BLOW when the killer
            # is another player (friendly fire, PvP): the log then writes no
            # DIED for that death. DIED_XP is an enemy death that grants XP
            # (its dying unit is the monster, never a player).
            if combat_event_type in ('DIED', 'DIED_XP', 'KILLING_BLOW'):
                # Dying unit is the target unit-state block (fields[17]);
                # a '*' target means self-inflicted: dying unit is the
                # source (fields[7]).
                if len(entry.fields) > 17 and entry.fields[-1] != '*':
                    dying_unit_id = str(entry.fields[17])
                elif len(entry.fields) > 7:
                    dying_unit_id = str(entry.fields[7])
                else:
                    dying_unit_id = ""
                dying_player = None
                if combat_event_type != 'DIED_XP' and self.current_encounter:
                    dying_player = self.current_encounter.find_player_by_unit_id(dying_unit_id)
                if dying_player:
                    self._record_player_death(dying_player, dying_unit_id, entry)

                # If it's a hostile enemy death, mark it as damaged by players
                elif (combat_event_type != 'KILLING_BLOW' and self.current_encounter and
                      dying_unit_id in self.current_encounter.enemies):
                    self._enemy_last_hit.pop(dying_unit_id, None)
                    enemy = self.current_encounter.enemies[dying_unit_id]
                    if enemy.died_at is None:
                        enemy.died_at = entry.timestamp
                    # A companion's death is shown on its row, and is not
                    # one of the fight's (player) deaths (companions.py)
                    companion = self.current_encounter.companion_key(dying_unit_id)
                    if companion is not None and self.current_encounter.in_combat:
                        self.current_encounter.companion_deaths[companion] += 1
                    # Its effects end with it: the game does not always
                    # write FADED for a corpse's (see effect_rules)
                    self.effect_tracker.forget_unit(dying_unit_id, entry.timestamp)
                    self.pen_crit_tracker.forget_unit(dying_unit_id, entry.timestamp)
                    # Only track deaths of hostile monsters, not friendly pets or NPCs
                    if enemy.is_hostile:
                        # Mark this enemy as damaged (even if we didn't track individual damage events)
                        if dying_unit_id not in self.current_encounter.enemy_damage:
                            self.current_encounter.enemy_damage[dying_unit_id] = 0
                            # Add enemy's max health to total when first damaged
                            if enemy.max_health > 0:
                                self.current_encounter.total_health_damaged += enemy.max_health
                        # Set a minimum damage amount to indicate it was killed
                        if self.current_encounter.enemy_damage[dying_unit_id] == 0:
                            self.current_encounter.enemy_damage[dying_unit_id] = 1
                        # Update the most damaged hostile monster
                        self.current_encounter.update_most_damaged_hostile(dying_unit_id)
            
            
            # Track damage events (see DAMAGE_RESULTS for what counts)
            elif combat_event_type in DAMAGE_RESULTS:
                try:
                    # COMBAT_EVENT format: timestamp,COMBAT_EVENT,actionResult,damageType,powerType,hitValue,overflow,castTrackId,abilityId,sourceUnitState,targetUnitState
                    # After parsing: fields[0]=actionResult, fields[1]=damageType, fields[3]=hitValue, fields[7]=sourceUnitId, fields[17]=targetUnitId
                    hit_value = int(entry.fields[3])  # hitValue is at index 3
                    source_unit_id = entry.fields[7] if len(entry.fields) > 7 else ""  # source unit ID
                    target_unit_id = entry.fields[17] if len(entry.fields) > 17 else ""  # target unit ID
                    
                    # Track damage dealt by players to hostile monsters
                    if hit_value > 0 and self.current_encounter:
                        if target_unit_id and target_unit_id in self.current_encounter.enemies:
                            enemy = self.current_encounter.enemies[target_unit_id]
                            if enemy.is_hostile:
                                # Check if source is a player or player's pet
                                if (self.current_encounter.find_player_by_unit_id(source_unit_id) or 
                                    source_unit_id in self.current_encounter.pet_ownership):
                                    
                                    if target_unit_id not in self.current_encounter.enemy_damage:
                                        self.current_encounter.enemy_damage[target_unit_id] = 0
                                        # Add enemy's max health to total when first damaged
                                        if target_unit_id in self.current_encounter.enemies:
                                            enemy = self.current_encounter.enemies[target_unit_id]
                                            if enemy.max_health > 0:
                                                self.current_encounter.total_health_damaged += enemy.max_health
                                    self.current_encounter.enemy_damage[target_unit_id] += hit_value
                                    # Update total group damage
                                    self.current_encounter.total_damage += hit_value
                                    if enemy.is_boss:
                                        self.current_encounter.boss_damage += hit_value

                                    # Track individual player damage, and
                                    # the hit's time, result, ability and
                                    # target for the dps time and breakdown;
                                    # the cast index tells area from single
                                    # target for the kinds (damage_kinds)
                                    if combat_event_type in CAST_RESULTS:
                                        self.cast_index.note_hit(
                                            source_unit_id, entry.fields[5], entry.fields[6],
                                            target_unit_id)
                                    self.current_encounter.add_damage_to_player(
                                        source_unit_id, hit_value, to_boss=enemy.is_boss,
                                        timestamp=entry.timestamp, result=combat_event_type,
                                        ability_id=entry.fields[6], target_id=target_unit_id,
                                        accrue_companions=self.companion_accrual,
                                        damage_type=entry.fields[1], cast_id=entry.fields[5],
                                        cast_index=self.cast_index)
                                    
                                    # Update the most damaged hostile monster
                                    self.current_encounter.update_most_damaged_hostile(target_unit_id)
                except (ValueError, IndexError):
                    pass  # Skip invalid damage values

            # Track healing events for role heuristic (a plain heal is HEAL in
            # the log; this used to look for HEALED, which is never written)
            elif combat_event_type in HEAL_RESULTS:
                try:
                    hit_value = int(entry.fields[3])
                    source_unit_id = entry.fields[7] if len(entry.fields) > 7 else ""
                    target_unit_id = entry.fields[17] if len(entry.fields) > 17 else ""
                    if hit_value > 0 and self.current_encounter and source_unit_id and target_unit_id:
                        self.current_encounter.add_healing_to_player(
                            source_unit_id, target_unit_id, hit_value,
                            accrue_companions=self.companion_accrual)
                except (ValueError, IndexError):
                    pass

            # Parse health information from COMBAT_EVENT (similar to EFFECT_CHANGED)
            # COMBAT_EVENT format can include health info in various positions depending on event type
            if len(entry.fields) > 17:  # Check if we have enough fields for health info
                # Look for health info in the format "current_health/max_health"
                for i, field in enumerate(entry.fields):
                    if "/" in field and field.count("/") == 1:
                        try:
                            current_health, max_health = field.split("/")
                            current_health = int(current_health)
                            max_health = int(max_health)
                            
                            # If this looks like valid health data (reasonable values)
                            if 1000 <= max_health <= 100000000:  # Reasonable health range
                                # Try to find the target unit ID - it's usually a few fields before health
                                target_unit_id = None
                                for j in range(max(0, i-5), i):
                                    if entry.fields[j].isdigit() and len(entry.fields[j]) > 3:  # Unit IDs are usually longer
                                        target_unit_id = entry.fields[j]
                                        break
                                
                                # Update enemy health if this is a known enemy
                                if (target_unit_id and self.current_encounter and 
                                    target_unit_id in self.current_encounter.enemies):
                                    self.current_encounter.update_enemy_health(target_unit_id, current_health, max_health)
                                    
                        except (ValueError, IndexError):
                            pass  # Skip invalid health data

    def _note_hit_on_player(self, entry: ESOLogEntry, result: str, target_id: str):
        """A recap-result event on the player *target_id*: feed the cast
        index (the area rule), the player's tally of damage taken by kind,
        and the death recap recorder (damage_kinds, death_recap)."""
        enc = self.current_encounter
        fields = entry.fields
        source_id = fields[7]
        player_source = bool(enc.find_player_by_unit_id(source_id)
                             or source_id in enc.pet_ownership)
        record = enc.record_id(target_id)
        tally = enc.taken_for(record)
        hit = int(fields[3]) if fields[3].isdigit() else 0
        overflow = int(fields[4]) if fields[4].isdigit() else 0
        if result in HEALTH_RESULTS:
            cast_id, ability_id = fields[5], fields[6]
            if result in CAST_RESULTS:
                self.cast_index.note_hit(source_id, cast_id, ability_id, target_id)
            area, rule, _targets = area_of(self.cast_index, source_id, cast_id,
                                           ability_id, player_source)
            if hit:
                enemy = enc.enemies.get(source_id)
                tally.note_damage(entry.timestamp, result, fields[1], hit, ability_id,
                                  source_id, area, rule, self.cast_index, cast_id,
                                  source_boss=bool(enemy is not None and enemy.is_boss))
            # The killing blow: the target's health after it is 0 and the
            # line carries the overkill
            health_at = 18 if fields[17] != '*' else 8
            if overflow and str(fields[health_at]).startswith('0/'):
                tally.note_overkill(overflow)
        else:
            # A heal is kept by healer for the damage taken window: a
            # player's heals under their record whatever unit id they are
            # on, a pet's under the pet with its owner for the name
            pet_owner = enc.pet_ownership.get(source_id, "")
            healer_id = source_id if pet_owner else enc.record_id(source_id)
            tally.note_other(result, hit, overflow, source_id=healer_id, ability_id=fields[6],
                             self_source=(healer_id == record), pet_owner=pet_owner)
        self.death_recap_recorder.record(entry.timestamp, fields, target_id,
                                         player_source=player_source)

    def _record_player_death(self, player: PlayerInfo, dying_unit_id: str, entry: ESOLogEntry):
        """Count a player's death and capture its recap (see death_recap.py)."""
        self.zone_deaths += 1
        self.fight_deaths += 1

        late_entry = self._late_death_fight_entry(entry.timestamp)
        fight_start = (self._last_fight_start if late_entry is not None
                       else self.current_encounter.start_time)
        recap = self.death_recap_recorder.note_death(
            dying_unit_id, entry.timestamp, entry.fields)
        recap['unit_id'] = player.unit_id
        recap['name'] = player.get_display_name()
        recap['time_ms'] = max(0, entry.timestamp - fight_start)
        self.fight_death_recaps.append(recap)

        if late_entry is not None:
            late_entry.deaths += 1
            late_entry.death_recaps = late_entry.death_recaps + [recap]
            self._notify('on_fight_updated', late_entry)

    def _late_death_fight_entry(self, timestamp_ms: int) -> Optional[FightHistoryEntry]:
        """The fight entry just emitted, when a death at *timestamp_ms* still
        belongs to it (see LATE_DEATH_GRACE_MS); else None."""
        enc = self.current_encounter
        if (self._last_fight_entry is None or enc is None or not enc.finalized
                or enc.combat_ended_at is None):
            return None
        if 0 <= timestamp_ms - enc.combat_ended_at <= LATE_DEATH_GRACE_MS:
            return self._last_fight_entry
        return None

    def _handle_effect_changed(self, entry: ESOLogEntry):
        """A buff or debuff coming, going or refreshing: the tracked effects
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
        """
        # EFFECT_CHANGED format: changeType, stackCount, castTrackId, abilityId, <sourceUnitState>, <targetUnitState>, playerInitiatedRemoveCastTrackId:optional
        # Where <targetUnitState> is replaced with * if the target unit is the same as the source unit (self-cast)
        # Note: entry.fields starts after line_number and event_type, so indices are shifted
        if len(entry.fields) >= 4:
            effect_type = entry.fields[0]  # changeType (GAINED/FADED/UPDATED)
            stack_count = entry.fields[1]  # stackCount
            cast_track_id = entry.fields[2]  # castTrackId
            ability_id = entry.fields[3]  # abilityId
            
            # Source and target unit ids. A unit state is ten fields wide
            # (unitId, health, magicka, stamina, ultimate, werewolf, shield,
            # x, y, heading), so an explicit target id is fields[14], and "*"
            # there means the target is the source (see extract_effect_fields)
            extracted = extract_effect_fields(entry.fields)
            source_unit_id = extracted[2] if extracted else "0"
            target_unit_id = extracted[3] if extracted else source_unit_id
            self_target = target_unit_id == source_unit_id

            # The source's pools (resources.py): [6..8] of its unit state
            if extracted is not None and len(entry.fields) > 8 and self.current_encounter:
                source_player = self.current_encounter.player_of(source_unit_id)
                if source_player is not None:
                    self.resources.observe(source_player.unit_id, entry.timestamp,
                                           entry.fields[6], entry.fields[7], entry.fields[8])

            if self.diagnostic and target_unit_id == "31":
                _console(f"{Fore.MAGENTA}[DIAGNOSTIC] EFFECT_CHANGED for unit_id 31: {entry.fields[9:12] if len(entry.fields) >= 12 else 'insufficient fields'}{Style.RESET_ALL}")

            # The timeline strip's built-in rows
            if self.track_buff_timeline and extracted is not None:
                self.buff_timeline_recorder.record(
                    effect_type, ability_id, source_unit_id, target_unit_id,
                    entry.timestamp)

            # The tracked effects, every item of the uptime line: any id,
            # judged by the target's kind
            if self.effect_tracker and extracted is not None:
                self.effect_tracker.record(
                    effect_type, ability_id, target_unit_id, stack_count,
                    entry.timestamp, self._unit_kind(target_unit_id),
                    source_id=source_unit_id)
            # The penetration and crit effects, for the build window's
            # sections (pen_crit); a trial dummy's own debuffs mark a parse
            if extracted is not None:
                self.pen_crit_tracker.record(
                    effect_type, ability_id, target_unit_id, stack_count,
                    entry.timestamp, self._unit_kind(target_unit_id),
                    source_id=source_unit_id)
                if ability_id in pen_crit.DUMMY_IDS:
                    self._dummy_seen = True

            # Werewolf form begins and ends with these effects on the player
            # (werewolf.py)
            if (ability_id in werewolf.EFFECT_IDS and extracted is not None
                    and self._unit_kind(target_unit_id) in ("self", "group")):
                self.werewolf.note_effect(self._scribing_player_key(target_unit_id),
                                          effect_type, ability_id, entry.timestamp)

            # A skill the log writes no BEGIN_CAST for (Fatecarver): its
            # channel effect on the caster is the cast (casts.py)
            if (effect_type == "GAINED" and ability_id in casts.CHANNEL_EFFECTS
                    and extracted is not None and self.current_encounter):
                caster = self.current_encounter.player_of(source_unit_id)
                if caster is not None:
                    self.casts.note_cast(caster.unit_id, cast_track_id,
                                         casts.CHANNEL_EFFECTS[ability_id], entry.timestamp)
                    self.resources.note_cast(caster.unit_id, entry.timestamp, cast_track_id,
                                             casts.CHANNEL_EFFECTS[ability_id])

            # A proc set's effect, sourced by its wearer: the build-issue
            # rule for a set that never fires (build_issues)
            if (effect_type == "GAINED" and ability_id in PROC_EFFECT_IDS
                    and extracted is not None and self.current_encounter):
                self.current_encounter.note_proc(
                    self.current_encounter.record_id(source_unit_id), ability_id)

            # A food or drink effect coming or going on a player: the
            # build-issue rules on a meal (build_issues.food_findings)
            if (effect_type in ("GAINED", "FADED") and ability_id in food_ids()
                    and extracted is not None and self.current_encounter
                    and self._unit_kind(target_unit_id) in ("self", "group")):
                self.current_encounter.note_food(self.current_encounter.record_id(target_unit_id),
                                                 effect_type, ability_id,
                                                entry.timestamp)

            # A Class Mastery effect names its holder, the source: a proc
            # mastery is never in the PLAYER_INFO passive list (eso_sets)
            if effect_type == "GAINED" and self.current_encounter:
                self._note_mastery(source_unit_id, ability_id)

            # Enemy health from the unit states: the target's own ten fields
            # when the target is explicit, the source's when it is "*"
            
            # Only process health parsing if we have an active encounter
            if self.current_encounter:
                # Look for the second target_unit_id (field 15) and its corresponding health (field 16)
                if len(entry.fields) >= 16:
                    second_target_unit_id = str(entry.fields[14])  # Field 15 (0-indexed)
                    target_health_info = str(entry.fields[15])     # Field 16 (0-indexed)
                    
                    if "/" in target_health_info and second_target_unit_id in self.current_encounter.enemies:
                        try:
                            current_health, max_health = target_health_info.split("/")
                            current_health = int(current_health)
                            max_health = int(max_health)
                            
                            if max_health > 0 and max_health > 100:  # Filter out small health values
                                self.current_encounter.update_enemy_health(second_target_unit_id, current_health, max_health)
                                
                        except (ValueError, IndexError):
                            pass  # Skip invalid health data
            
            # A self-targeted effect on an enemy: the source state is the
            # enemy's, so its health is fields[5]
            if self_target and self.current_encounter and len(entry.fields) >= 6:
                first_target_health_info = str(entry.fields[5])  # Field 6 (0-indexed)
                if "/" in first_target_health_info and target_unit_id in self.current_encounter.enemies:
                    try:
                        current_health, max_health = first_target_health_info.split("/")
                        current_health = int(current_health)
                        max_health = int(max_health)

                        if max_health > 0 and max_health > 100:  # Filter out small health values
                            self.current_encounter.update_enemy_health(target_unit_id, current_health, max_health)

                    except (ValueError, IndexError):
                        pass  # Skip invalid health data

            # Only track GAINED effects to avoid spam, and only from valid source units
            if (self.current_encounter and effect_type == "GAINED" and source_unit_id != "0" and
                ability_id in self.ability_cache):
                ability_name = self.ability_cache[ability_id]
                self.current_encounter.add_ability_use(source_unit_id, ability_name)

            # Check if this is a health-related effect (field [7] contains health info)
            if self.current_encounter and len(entry.fields) >= 8:
                health_info = entry.fields[7] if len(entry.fields) > 7 else ""

                # Look for health information in format "current/max"
                if '/' in health_info and target_unit_id:
                    try:
                        current_health, max_health = health_info.split('/')
                        current_health = int(current_health)
                        max_health = int(max_health)

                        # Update enemy health if this is an enemy unit
                        enemy = self.current_encounter.enemies.get(target_unit_id)
                        if enemy and max_health > 0:
                            # Update with the highest max health we've seen
                            if max_health > enemy.max_health:
                                enemy.max_health = max_health
                                enemy.current_health = current_health
                    except (ValueError, IndexError):
                        pass  # Skip invalid health data

            # Only mark combat activity if we're already in combat (after BEGIN_COMBAT)
            # Don't start combat from EFFECT_CHANGED events alone

    def _publish_fight(self, zone_name: str = None):
        """Hand the encounter that just ended to the frontends: a new entry in
        the fight history, or, for a fight the game cut in two, the entry it
        already has brought up to date (see COMBAT_RESUME_MS)."""
        if not self.current_encounter:
            return

        # Clear the hostile monsters list and engaged monsters set for the next encounter
        self.hostile_monsters.clear()
        self.engaged_monsters.clear()

        if hasattr(self, 'fight_history') and self.fight_history is not None:
            fight_entry = self._build_fight_entry(zone_name)
            if fight_entry:
                resumed, self._resumed_fight_entry = self._resumed_fight_entry, None
                if resumed is not None:
                    # The fight the game cut in two (see COMBAT_RESUME_MS):
                    # frontends hold its entry already, so that one is brought
                    # up to date instead of a second fight being added
                    for field in FightHistoryEntry.__slots__:
                        setattr(resumed, field, getattr(fight_entry, field))
                    fight_entry = resumed
                else:
                    self.fight_history.append(fight_entry)
                self._last_fight_entry = fight_entry
                self._last_fight_start = self.current_encounter.start_time
                self._index_mastery_rows(fight_entry)
                self._notify('on_fight_updated' if resumed is not None
                             else 'on_fight_completed', fight_entry)

    def _unit_kind(self, unit_id: str) -> Optional[str]:
        """What the encounter knows a unit to be, for effect_rules scopes:
        'self' (the player writing the log), 'group' (another player),
        'pet' (a group member's pet), 'boss' (a hostile the game flags as a
        boss, less boss_units' exceptions), 'enemy' (any other hostile), or
        None."""
        enc = self.current_encounter
        if enc is None:
            return None
        player = enc.player_of(unit_id)
        if player is not None:
            return "self" if player.is_local else "group"
        if unit_id in enc.pet_ownership:
            return "pet"
        enemy = enc.enemies.get(unit_id)
        if enemy is not None and enemy.is_hostile:
            return "boss" if enemy.is_boss else "enemy"
        return None

    def _resolve_timeline_name(self, unit_id: str) -> str:
        """Display name for a timeline unit: player handle, enemy name, or id."""
        if unit_id == "0":
            # Environment/untracked source (e.g. set procs logged without a unit)
            return "unknown"
        enc = self.current_encounter
        if enc is not None:
            player = enc.player_of(unit_id)
            if player is not None:
                return player.get_display_name()
            enemy = enc.enemies.get(unit_id)
            if enemy is not None and getattr(enemy, 'name', None):
                return enemy.name
        return f"unit {unit_id}"

    def _resolve_recap_unit(self, unit_id: str) -> str:
        """Display name for a death-recap source: player handle or monster
        name; '' when the log names no unit (environment, fall damage)."""
        enc = self.current_encounter
        if enc is None or unit_id == "0":
            return ""
        player = enc.player_of(unit_id)
        if player is not None:
            return player.get_display_name()
        enemy = enc.enemies.get(unit_id)
        if enemy is not None and enemy.name:
            return enemy.name
        return ""

    def _resolve_recap_ability(self, ability_id: str) -> Tuple[str, str]:
        """(name, icon stem) for a death-recap ability id."""
        ability_id = str(ability_id)
        return (self.ability_cache.get(ability_id) or f"Ability {ability_id}",
                self.ability_icons.get(ability_id, ''))

    def _remember_cast(self, cast_id: str, ability_id: str):
        """Keep which ability a cast tracking id belongs to (see TAUNTED in
        _handle_combat_event). The first word stands: a BEGIN_CAST precedes
        its hits. Bounded: the oldest half goes when the memory is full."""
        casts = self._cast_abilities
        if cast_id in casts:
            return
        if len(casts) >= CAST_MEMORY:
            for key in list(casts)[:CAST_MEMORY // 2]:
                del casts[key]
        casts[cast_id] = ability_id

    def _opener_side(self, enc: CombatEncounter, unit_id: str) -> fight_opener.Side | None:
        """A unit as the opener sees it: a player, a player's pet or a
        companion (fight_opener.Side), else None."""
        player = enc.player_of(unit_id)
        if player is not None:
            return fight_opener.Side(unit_id, 'player', player.unit_id, player.unit_id,
                                     player.get_display_name())
        # A pet's or companion's owner is kept by its record id
        # (track_pet_ownership), so the lookup is direct
        companion = enc.companion_key(unit_id)
        if companion is not None:
            record = enc.companions.get(companion)
            owner = enc.players.get(record.owner_unit_id) if record else None
            if owner is None:
                return None
            return fight_opener.Side(unit_id, 'companion', companion, owner.unit_id,
                                     owner.get_display_name())
        owner_id = enc.pet_ownership.get(unit_id)
        owner = enc.players.get(owner_id) if owner_id is not None else None
        if owner is None:
            return None
        pet = enc.enemies.get(unit_id)
        return fight_opener.Side(unit_id, 'pet', owner.unit_id, owner.unit_id,
                                 owner.get_display_name(), pet.name if pet is not None else "")

    def _opener_enemy(self, enc: CombatEncounter, unit_id: str) -> EnemyInfo | None:
        """A hostile unit that counts as an enemy, hit or acting: never a
        companion, and never a unit that had a player owner (a pet released
        at its end turns HOSTILE with owner 0)."""
        enemy = enc.enemies.get(unit_id)
        if enemy is None or not enemy.is_hostile or enemy.is_companion or enemy.was_owned:
            return None
        return enemy

    @staticmethod
    def _zero_health(health: str) -> bool:
        """A unit state's 'current/max' health reads 0 of more than 0."""
        current, _, maximum = health.partition("/")
        return current == "0" and maximum not in ("", "0")

    def _feed_opener_cast(self, entry: ESOLogEntry, ability_id: str, caster_unit_id: str):
        """A BEGIN_CAST for the opener: a player-side cast at a hostile, or
        a hostile's cast at a player-side unit (fields: castTrackId 2,
        caster 4 and its health 5, target 14 and its health 15)."""
        enc = self.current_encounter
        target_id = entry.fields[14]
        if target_id == '*':
            return
        cast_time = casts.line_time(entry.original_line)
        target = self._opener_enemy(enc, target_id)
        if target is not None:
            caster = self._opener_side(enc, caster_unit_id)
            if caster is not None:
                self.opener.note_player_cast(cast_time, entry.fields[2], ability_id, caster,
                                             target_id, target.name, target,
                                             target_dead=self._zero_health(entry.fields[15]))
            return
        monster = self._opener_enemy(enc, caster_unit_id)
        if monster is not None:
            side = self._opener_side(enc, target_id)
            if side is not None:
                self.opener.note_monster_event(
                    cast_time, fight_opener.CAST, entry.fields[2], ability_id, caster_unit_id,
                    monster.name, monster.monster_id, monster, side,
                    source_dead=self._zero_health(entry.fields[5]))

    def _feed_opener_event(self, entry: ESOLogEntry, result: str):
        """A COMBAT_EVENT for the opener: a player-side unit's on a hostile,
        or a hostile's on a player-side unit, of any result (fields:
        hitValue 3, castTrackId 5, abilityId 6, source 7 and its health 8,
        target 17)."""
        enc = self.current_encounter
        fields = entry.fields
        source_id, target_id = fields[7], fields[17]
        if target_id == '*':
            return
        target = self._opener_enemy(enc, target_id)
        if target is not None:
            actor = self._opener_side(enc, source_id)
            if actor is not None:
                try:
                    hit_value = int(fields[3])
                except ValueError:
                    hit_value = 0
                self.opener.note_player_event(entry.timestamp, result, hit_value, fields[5],
                                              fields[6], actor, target_id, target.name, target)
            return
        monster = self._opener_enemy(enc, source_id)
        if monster is not None:
            side = self._opener_side(enc, target_id)
            if side is not None:
                self.opener.note_monster_event(
                    entry.timestamp, result, fields[5], fields[6], source_id, monster.name,
                    monster.monster_id, monster, side, source_dead=self._zero_health(fields[8]))

    def _opener_player_name(self, record_id: str, fallback: str) -> str:
        """A player's display name for the opener line, as the fight ends:
        an anonymous member may have been named since the act."""
        enc = self.current_encounter
        player = (enc.player_of(record_id) or enc.find_player_by_unit_id(record_id)) if enc else None
        return player.get_display_name() if player is not None else fallback

    def _taunts_of(self, enc: CombatEncounter, unit_id: str) -> List[dict]:
        """The abilities a player taunted with in this fight, most used
        first: {'id', 'name', 'icon', 'count'} each. A taunt the log did not
        tie to a cast is left out."""
        taunts = []
        for ability_id, count in (enc.player_taunts.get(unit_id) or {}).items():
            if not ability_id:
                continue
            name = self.log_parser.get_ability_name(ability_id) or f"Ability {ability_id}"
            taunts.append({'id': str(ability_id), 'name': name,
                           'icon': self.ability_icons.get(str(ability_id), ''),
                           'count': count})
        taunts.sort(key=lambda t: (-t['count'], t['name']))
        return taunts

    def _build_fight_entry(self, zone_name: str = None):
        """Build a FightHistoryEntry from the current encounter."""
        if not self.current_encounter:
            return None

        entry = FightHistoryEntry()
        enc = self.current_encounter

        entry.ended_at = time.time()
        entry.timestamp = enc.get_combat_start_time_formatted(self.current_log_file, self.log_start_unix_timestamp)
        entry.zone_name = zone_name or self.current_zone or "Unknown"
        entry.zone_id = self.current_zone_id
        entry.difficulty = (self.current_difficulty or "").upper()
        entry.is_vet = entry.difficulty == "VETERAN"

        duration = (enc.end_time - enc.start_time) / 1000.0
        entry.duration_s = duration
        # Dps divides by dps time, the span of the hits, not the fight time
        # (see "Dps time" by DAMAGE_RESULTS): the group's by the span of the
        # group's hits, the boss figure by the span of the hits on the bosses
        damage = enc.damage
        entry.dps_time_s = damage.window.span_ms / 1000.0
        entry.boss_dps_time_s = damage.boss_window.span_ms / 1000.0
        entry.group_dps = dps_over(enc.total_damage, damage.window.span_ms)
        entry.group_boss_dps = dps_over(enc.boss_damage, damage.boss_window.span_ms)
        # The group's damage per second, for the graph window
        entry.damage_series = damage.series(enc.start_time)
        entry.deaths = self.fight_deaths  # this fight's player deaths
        # The recaps' rows are classed once more with every cast of the
        # fight known (an area cast's hit on a second target may come late)
        self.death_recap_recorder.refresh_fight()
        entry.death_recaps = list(self.fight_death_recaps)
        # Who opened the fight and with what, and the monster's act before
        # it, names resolved now (fight_opener)
        entry.opener, entry.monster_first = fight_opener.opener_records(
            enc.opening, lambda ability_id: (self.ability_cache.get(ability_id)
                                             or self.log_parser.get_ability_name(ability_id)
                                             or ""),
            self._opener_player_name)
        # Every player unit, rows or not (a player with no PLAYER_INFO gets
        # no row below but still appears in the timeline, the recaps and
        # the casters): the roster the Hide names mask reads
        entry.player_names = [{'name': p.get_display_name(), 'character': p.name,
                               'is_local': bool(p.is_local)} for p in enc.players.values()]

        # The buff/debuff timeline (None when none of its effects was up)
        if self.track_buff_timeline:
            entry.buff_timeline = self.buff_timeline_recorder.snapshot_fight(
                enc.start_time, enc.end_time, self._resolve_timeline_name)
            # Not before the end: this fight's intervals are needed once more
            # if it turns out to carry on (see COMBAT_RESUME_MS)
            self.buff_timeline_recorder.prune_before(enc.start_time)

        # Boss name: prefer most damaged hostile, fall back to highest health
        if enc.most_damaged_hostile and enc.most_damaged_hostile.name:
            entry.boss_name = enc.most_damaged_hostile.name
        elif enc.highest_health_hostile and enc.highest_health_hostile.name:
            entry.boss_name = enc.highest_health_hostile.name

        CLASS_ABBR = {
            "1": "DK", "2": "Sorc", "3": "NB", "4": "Warden",
            "5": "Necro", "6": "Templar", "117": "Arcanist"
        }

        players_with_damage = []
        for player in enc.players.values():
            # A player the log has not described is left out, unless they
            # came back on another character grouped with the logging
            # player during this fight (presence.py, rule 4)
            if not player.equipped_abilities and not (
                    player.switched_character and player.grouped
                    and (player.joined_at is None or player.joined_at <= enc.end_time)):
                continue
            player_damage = enc.player_damage.get(player.unit_id, 0)
            players_with_damage.append((player, player_damage))

        # Ranked by damage to the bosses first, then by all damage: in a
        # fight without a boss every boss figure is 0 and all damage decides
        players_with_damage.sort(
            key=lambda x: (enc.player_boss_damage.get(x[0].unit_id, 0), x[1]), reverse=True)

        def ability_name(ability_id):
            return (self.ability_cache.get(ability_id)
                    or self.log_parser.get_ability_name(ability_id)
                    or f"Ability {ability_id}")

        def ability_icon(ability_id):
            return self.ability_icons.get(str(ability_id), '')

        for player, player_damage in players_with_damage:
            # Each player's dps over the span of their own hits, the boss
            # figure over the span of their hits on the bosses
            record = damage.player(player.unit_id)
            player_dps = record.dps()
            boss_damage = enc.player_boss_damage.get(player.unit_id, 0)
            player_boss_dps = record.boss_dps()
            dmg_pct = (player_damage / enc.total_damage * 100) if enc.total_damage > 0 else 0
            boss_pct = (boss_damage / enc.boss_damage * 100) if enc.boss_damage > 0 else 0
            player_healing = enc.player_healing.get(player.unit_id, 0)

            # The ability-based role, for the role fallback
            analysis = self.subclass_analyzer.analyze_subclass(player.equipped_abilities) if player.equipped_abilities else None
            skill_line_role = analysis.get('role') if analysis else None
            # The class skill lines: from the passives PLAYER_INFO lists,
            # the slotted abilities filling in (eso_sets)
            skill_lines = skill_lines_of(player.long_term_effects, player.equipped_abilities)

            role = infer_player_role(player, player_damage=player_damage,
                                     player_healing=player_healing,
                                     skill_line_role=skill_line_role,
                                     restoration_staff=has_restoration_staff(player.gear))

            # Extract gear sets: mythic and 5-piece sets for compact display
            player_sets = []  # list of (count, name, is_mythic)
            all_sets = []     # list of (count, name) for detail view
            if player.gear:
                set_counts = {}
                for slot, gear_item in player.gear.items():
                    if len(gear_item) > 6:
                        set_id = str(gear_item[6])
                        if set_id in ("0", "", "nan"):
                            continue
                        set_name = gear_set_db.get_set_name_by_set_id(set_id)
                        if not set_name:
                            set_name = f"Set#{set_id}"
                        pc = 1
                        if slot in ('MAIN_HAND', 'BACKUP_MAIN') and self._is_two_handed_weapon(gear_item, player.gear):
                            pc = 2
                        set_counts[set_name] = set_counts.get(set_name, 0) + pc
                for sn, cnt in sorted(set_counts.items(), key=lambda x: -x[1]):
                    is_mythic = is_mythic_set(sn)
                    all_sets.append((cnt, sn))
                    if is_mythic or (has_five_piece_bonus(sn) and cnt >= 5):
                        player_sets.append((cnt, sn, is_mythic))

            entry.players.append({
                'role': role,
                'name': player.get_display_name(),
                'class_abbr': CLASS_ABBR.get(player.class_id, '?'),
                'dps': player_dps,
                'boss_dps': player_boss_dps,
                'dmg_pct': dmg_pct,
                'boss_pct': boss_pct,
                # The damage window's data: totals, the spans, and the
                # breakdowns by ability and by target (damage_stats)
                'damage': record.snapshot(ability_name, ability_icon,
                                          self._resolve_timeline_name, enc.start_time),
                'h': player.max_health,
                'm': player.max_magicka,
                's': player.max_stamina,
                'healing': player_healing,
                # The damage the player took and the healing they received,
                # by kind, for the death recap window (damage_kinds)
                'taken': enc.taken_for(player.unit_id).snapshot(
                    ability_name, ability_icon, self._resolve_timeline_name),
                'skill_line_role': skill_line_role or '',
                'unit_id': player.unit_id,
                'sets': player_sets,
                'all_sets': all_sets,
                'skill_lines': skill_lines,
                'class_lines': player.get_class_skill_lines(),
                # The Class Mastery passives: listed, or seen firing
                'masteries': player.masteries(),
                'front_bar': list(player.front_bar_abilities) if player.front_bar_abilities else [],
                'back_bar': list(player.back_bar_abilities) if player.back_bar_abilities else [],
                'front_bar_slots': [dict(s) for s in player.front_bar_slots],
                'back_bar_slots': [dict(s) for s in player.back_bar_slots],
                'class_name': player.get_class_name(),
                'cp': player.champion_points,
                'character': player.name,
                'race': race_name(player.race_id),
                # The player whose client writes the log (the game's
                # isLocalPlayer flag): the one the Hide names switch keeps
                'is_local': bool(player.is_local),
            })
            # A player who left during the fight: their row stays, greyed,
            # with the share of the fight they were there for (presence.py)
            if player.left_at is not None and player.left_at <= enc.end_time:
                entry.players[-1]['left'] = True
                entry.players[-1]['present_pct'] = present_share(
                    enc.start_time, enc.end_time, player.joined_at, player.left_at)
            # The fight's casts: the total, cpm and extras (casts.py)
            cast_counts = self.casts.fight_counts(player.unit_id, enc.start_time, enc.end_time)
            entry.players[-1]['casts'] = casts.cast_summary(
                cast_counts, duration, entry.players[-1].get('present_pct'))
            # Magicka, stamina and ultimate spent and gained (resources.py)
            entry.players[-1]['resources'] = self.resources.fight_summary(
                player.unit_id, enc.start_time, enc.end_time, duration,
                entry.players[-1].get('present_pct'), ability_name,
                self._resolve_timeline_name)
            if not player.equipped_abilities:
                # Back on another character whose build is not in the log
                # yet: the class and the figures, nothing to judge
                entry.players[-1]['no_build'] = True
                entry.players[-1]['build_issues'] = []
                continue
            # Per-slot gear, mundus and food for the build window
            entry.players[-1].update(build_fields(
                player.gear, player.long_term_effects,
                self.ability_cache.get, self.ability_icons.get))
            gear_rows = entry.players[-1].get('gear')
            if gear_rows:
                key = json.dumps(gear_rows, sort_keys=True, default=str)
                entry.players[-1]['gear'] = self._shared_gear.setdefault(key, gear_rows)
            # The werewolf bar the log never writes, rebuilt from casts, and
            # the share of the fight spent in form (werewolf.py)
            entry.players[-1].update(self._werewolf_fields(player, enc))
            # Each slot's casts in the fight, under its icon in the build
            # window (casts.py)
            casts.mark_slot_casts(cast_counts, (entry.players[-1]['front_bar_slots'],
                                                entry.players[-1]['back_bar_slots'],
                                                entry.players[-1].get('werewolf_bar_slots')),
                                  ability_name)
            # The abilities this player taunted with, marked on their bars
            taunts = self._taunts_of(enc, player.unit_id)
            entry.players[-1]['taunts'] = taunts
            if taunts:
                mark_taunt_slots(entry.players[-1]['front_bar_slots']
                                 + entry.players[-1]['back_bar_slots']
                                 + entry.players[-1].get('werewolf_bar_slots', []), taunts)
            # Possible build issues (build_issues): the per-fight rules on
            # this build, then the proc sets judged over the session. Any
            # taunt this fight, named or not, marks the player a taunter
            # for the session first
            player_key = self._scribing_player_key(player.unit_id)
            if enc.player_taunts.get(player.unit_id):
                self.build_issues.note_taunt(player_key)
            worn = worn_proc_sets(player.gear)
            self.build_issues.note_fight(
                player_key, enc.start_time, duration, worn,
                fired_proc_sets(worn, enc.proc_effects.get(player.unit_id, ())))
            # The tank rule reads the player's damage against an equal share
            # of the group's, and whether they healed others for more than
            # they dealt (a healer whose largest pool is health)
            damage_ratio = ((player_damage / enc.total_damage) * len(players_with_damage)
                            if enc.total_damage > 0 and players_with_damage else None)
            entry.players[-1]['build_issues'] = (
                structural_findings(player.gear, player.front_bar_slots, player.back_bar_slots,
                                    role, taunted=self.build_issues.has_taunted(player_key),
                                    set_name_of=gear_set_db.get_set_name_by_set_id,
                                    damage_ratio=damage_ratio,
                                    out_heals=player_healing > player_damage,
                                    players=len(enc.players), veteran=entry.is_vet)
                + self.build_issues.findings(player_key, worn))
            # The rules on a meal: none at combat start, or one that ran out
            # (build_issues); not judged when the food table could not load
            if 'food' in entry.players[-1]:
                entry.players[-1]['build_issues'] += food_findings(
                    entry.players[-1]['food'], enc.food.get(player.unit_id), enc.start_time,
                    name_of=ability_name)

        # Each companion that was out during the fight, on a row of its own
        # straight under its owner's (companions.py); one whose owner has
        # no row is left out, like a player whose build never reached the log
        by_owner = self._companion_rows(enc, ability_name, ability_icon, duration)
        if by_owner:
            ordered = []
            for row in entry.players:
                ordered.append(row)
                ordered.extend(by_owner.get(row['unit_id'], []))
            entry.players = ordered
        # Not before the end: this fight's casts are needed once more if it
        # turns out to carry on (see COMBAT_RESUME_MS)
        self.casts.prune_before(enc.start_time)
        self.resources.prune_before(enc.start_time)

        # The uptime line: every item is a rule (effect_rules), measured on
        # the fight's players and the hostiles the group hit, whatever the
        # group size (a rule can be about the logging player alone)
        entry.tracked = (self.effect_tracker.snapshot(
            enc.start_time, enc.end_time, self._resolve_timeline_name, enc.fight_units())
            if self.effect_tracker else [])
        # The copied line: the items shown, seen or expected (issue #13)
        entry.buff_summary = " ".join(item["text"] for item in entry.tracked
                                      if item.get("shown", True))
        if entry.tracked:
            # Not before the end: this fight's spans are needed once more
            # if it turns out to carry on (see COMBAT_RESUME_MS)
            self.effect_tracker.prune_before(enc.start_time)

        # Penetration and critical damage (pen_crit): each player's own
        # sources from their build, and the fight's debuffs and buffs
        # weighed by the damage dealt while they were up
        self._pen_crit_fields(entry, enc)
        self.pen_crit_tracker.prune_before(enc.start_time)

        # A solo dungeon run's Misfortunes, from the logging player's
        # long-term effects (misfortunes.py, issue #70)
        if pen_crit.zone_kind(self.current_zone_id, self.current_difficulty) == "solo_dungeon":
            local = next((p for p in enc.players.values() if p.is_local), None)
            entry.misfortunes = [list(item) for item in run_misfortunes(
                local.long_term_effects if local is not None else [],
                lambda ability_id: self.ability_icons.get(ability_id, ""),
                lambda ability_id: self.ability_cache.get(ability_id, ""))]

        entry.trial_result = enc.trial_result

        return entry


    def _companion_out(self, enc: 'CombatEncounter', record: companions.CompanionRecord) -> bool:
        """Whether one of the companion's units was out during the fight:
        added before its end and not removed before its start."""
        for unit_id in record.unit_ids:
            unit = enc.enemies.get(unit_id)
            if (unit is None or not unit.is_companion or unit.monster_id != record.monster_id
                    or unit.added_at is None):
                continue  # the unit id was handed to another unit since
            if unit.added_at <= enc.end_time and (unit.removed_at is None
                                                  or unit.removed_at >= enc.start_time):
                return True
        return False

    def _companion_rows(self, enc: 'CombatEncounter', ability_name, ability_icon,
                        duration: float) -> dict[str, list[dict]]:
        """The fight's companion rows by owner unit id (companions.py): every
        companion that was out during the fight or dealt damage, healed or
        died in it. A row has the keys a player's row has that make sense
        for a companion (the dps figures and shares, the damage window's
        data, health, healing, the bar of skills it cast this session with
        this fight's casts of each, the casts and cpm over the fight) and
        'companion': True, 'owner_unit_id', 'level' and 'ultimates', its
        ultimate's casts this fight: {'id', 'name', 'at'} with 'at' the
        seconds into the fight of each, [] when it cast none (issue #130)."""
        damage = enc.damage
        rows: dict[str, list[dict]] = {}
        total = enc.total_damage
        for key, record in enc.companions.items():
            active = (key in damage.players or enc.player_healing.get(key)
                      or enc.companion_deaths.get(key))
            if not active and not self._companion_out(enc, record):
                continue
            dealt = enc.player_damage.get(key, 0)
            boss = enc.player_boss_damage.get(key, 0)
            figures = damage.player(key)
            skills = self.companion_casts.get(
                (self._scribing_player_key(record.owner_unit_id), record.monster_id), [])
            slots = [self._ability_slot(ability_id) for ability_id in companions.bar_order(skills)]
            for slot in slots:
                if slot['id'] in companions.ULTIMATES:
                    slot['ultimate'] = True
            # This fight's casts, under each skill of the bar, and the
            # ultimate's with their times (casts.py)
            cast_counts = self.casts.fight_counts(key, enc.start_time, enc.end_time)
            casts.mark_slot_casts(cast_counts, (slots,), ability_name)
            ultimates: dict[str, dict] = {}
            for at, ability_id in self.casts.fight_times(key, enc.start_time, enc.end_time,
                                                         companions.ULTIMATES):
                ultimate = ultimates.setdefault(ability_id, {
                    'id': ability_id, 'name': ability_name(ability_id), 'at': []})
                ultimate['at'].append(round((at - enc.start_time) / 1000.0, 1))
            rows.setdefault(record.owner_unit_id, []).append({
                'companion': True,
                'owner_unit_id': record.owner_unit_id,
                'role': companions.ROLE,
                'name': record.name,
                'character': '',
                'level': record.level,
                'class_abbr': f"lvl {record.level}" if record.level else '',
                'class_name': f"level {record.level}" if record.level else '',
                'dps': figures.dps(),
                'boss_dps': figures.boss_dps(),
                'dmg_pct': (dealt / total * 100) if total > 0 else 0,
                'boss_pct': (boss / enc.boss_damage * 100) if enc.boss_damage > 0 else 0,
                'damage': figures.snapshot(ability_name, ability_icon,
                                           self._resolve_timeline_name, enc.start_time),
                'h': record.max_health, 'm': 0, 's': 0,
                'healing': enc.player_healing.get(key, 0),
                'deaths': enc.companion_deaths.get(key, 0),
                'unit_id': key,
                'front_bar_slots': slots,
                'front_bar': [slot['name'] for slot in slots],
                'back_bar_slots': [], 'back_bar': [],
                'sets': [], 'all_sets': [], 'skill_lines': [], 'class_lines': [],
                'masteries': [], 'taunts': [], 'build_issues': [],
                'casts': casts.cast_summary(cast_counts, duration,
                                            kinds=casts.COMPANION_EXTRA_KINDS),
                'ultimates': list(ultimates.values()),
            })
        return rows

    def _pen_crit_fields(self, entry: FightHistoryEntry, enc: 'CombatEncounter') -> None:
        """Set entry.pen_crit and each player's 'pen_crit' (pen_crit.py): the
        player's own rows from their PLAYER_INFO line, the fight's debuffs
        on the bosses with uptime and casters, each player's buffs, and the
        damage-weighted histograms the build window reads against the cap.
        The zone's kind (pen_crit.zone_kind) sets the target's armour: a
        solo dungeon by its zone id, instanced content when the difficulty
        is NORMAL or VETERAN, a trial dummy's own debuffs seen in this zone,
        or the fight against the Trial dummy by name, whose permanent
        debuffs are then credited in full (pen_crit.TRIAL_DUMMY_DEBUFFS)."""
        zone = pen_crit.zone_kind(self.current_zone_id, self.current_difficulty)
        damage = enc.damage
        # A companion's row has no build to read and no buffs of its own to
        # weigh (companions.py): its damage is in the group's buckets only
        player_buckets = {p['unit_id']: damage.player(p['unit_id']).target_buckets
                          for p in entry.players if not p.get('companion')}
        units = enc.fight_units()
        # The Trial dummy keeps a trial group's debuffs on itself from its
        # spawn; a session begun later never sees them applied (pen_crit)
        permanent = {uid: list(pen_crit.TRIAL_DUMMY_DEBUFFS) for uid in units
                     if uid in enc.enemies and enc.enemies[uid].name == pen_crit.TRIAL_DUMMY_NAME}

        def gear_of(unit_id: str):
            player = enc.player_of(unit_id)
            return player.gear if player is not None else {}

        try:
            # Each player's own rows first: the buffs their sets give at all
            # times are credited for the whole fight by the group part
            own_rows = {}
            for row in entry.players:
                player = enc.players.get(row['unit_id'])
                if player is not None:
                    own_rows[row['unit_id']] = pen_crit.player_rows(
                        player.gear, player.long_term_effects,
                        player.front_bar_abilities, player.back_bar_abilities)
            group, per_player = pen_crit.fight_fields(
                self.pen_crit_tracker, enc.start_time, enc.end_time, units,
                damage.target_buckets, player_buckets, self._resolve_timeline_name,
                gear_of, zone, self._dummy_seen or bool(permanent),
                always_on={uid: own["gives"] for uid, own in own_rows.items() if own.get("gives")},
                permanent_debuffs=permanent)
        except Exception as exc:  # a figure must never cost the fight entry
            if self.diagnostic:
                _console(f"pen_crit failed: {exc}")
            return
        entry.pen_crit = group
        for row in entry.players:
            own = own_rows.get(row['unit_id'])
            if own is None:
                continue
            own.update(per_player.get(row['unit_id'], {}))
            row['pen_crit'] = own

    def _update_player_session(self, unit_id: str, name: str, handle: str, equipped_abilities: List[str] = None, gear_data: List = None, class_id: str = None, champion_points: int = 0, long_term_effects: List[str] = None, masteries: List[str] = None):
        """Update or create a player session with their current data."""
        if not handle or handle == "" or not name or name == "":
            return
            
        # Clean up handle and name (remove quotes if present)
        clean_handle = handle.strip('"') if handle else ""
        clean_name = name.strip('"') if name else ""
        if not clean_handle or not clean_name:
            return
            
        # Create composite key for character-specific sessions
        session_key = f"{clean_handle}+{clean_name}"
        
        # Update unit ID mapping
        self.unit_id_to_handle[unit_id] = clean_handle
        
        # Update or create session data
        if session_key not in self.player_sessions:
            self.player_sessions[session_key] = {
                'unit_id': unit_id,
                'name': clean_name,
                'class_id': class_id,
                'champion_points': champion_points,
                'equipped_abilities': equipped_abilities or [],
                'gear_data': gear_data or [],
                'long_term_effects': long_term_effects or [],
                'masteries': list(masteries or []),
                'last_seen': 0
            }
        else:
            # Update existing session
            self.player_sessions[session_key]['unit_id'] = unit_id
            self.player_sessions[session_key]['name'] = clean_name
            if class_id:
                self.player_sessions[session_key]['class_id'] = class_id
            if champion_points > 0:
                self.player_sessions[session_key]['champion_points'] = champion_points
            if equipped_abilities:
                self.player_sessions[session_key]['equipped_abilities'] = equipped_abilities
            if gear_data:
                self.player_sessions[session_key]['gear_data'] = gear_data
            if long_term_effects:
                self.player_sessions[session_key]['long_term_effects'] = long_term_effects
            if masteries:
                known = self.player_sessions[session_key].setdefault('masteries', [])
                known.extend(name for name in masteries if name not in known)
            self.player_sessions[session_key]['last_seen'] = 0

    def _get_player_from_session(self, unit_id: str, name: str, handle: str) -> Optional[PlayerInfo]:
        """Get player info from session data if available."""
        if not handle or not name:
            return None
            
        # Clean up handle and name (remove quotes if present)
        clean_handle = handle.strip('"') if handle else ""
        clean_name = name.strip('"') if name else ""
        if not clean_handle or not clean_name:
            return None
            
        # Create composite key for character-specific sessions
        session_key = f"{clean_handle}+{clean_name}"
        
        if session_key not in self.player_sessions:
            return None
            
        session_data = self.player_sessions[session_key]
        
        # Create PlayerInfo from session data
        player = PlayerInfo(unit_id, clean_name, clean_handle, session_data.get('class_id'))
        player.champion_points = session_data.get('champion_points', 0)
        player.equipped_abilities = session_data['equipped_abilities']
        player.set_gear(session_data['gear_data'])
        player.long_term_effects = list(session_data.get('long_term_effects') or [])
        player.masteries_seen = list(session_data.get('masteries') or [])

        return player

    def _restore_player_from_session(self, unit_id: str, name: str, handle: str):
        """Restore a player from session data when they come back online."""
        if not self.current_encounter:
            return

        # Get session data
        player = self._get_player_from_session(unit_id, name, handle)
        if not player:
            return

        # Update session with current unit_id
        self._update_player_session(unit_id, name, handle, player.equipped_abilities,
                                    self.player_sessions[f"{handle}+{name}"]['gear_data'], player.class_id,
                                    long_term_effects=player.long_term_effects, masteries=player.masteries_seen)

        # Add player to current encounter with session data
        self.current_encounter.players[unit_id] = player

        # Associate long unit ID if available
        if hasattr(self.current_encounter, 'unit_id_mapping') and unit_id in self.current_encounter.unit_id_mapping:
            long_unit_id = self.current_encounter.unit_id_mapping[unit_id]
            if hasattr(self.current_encounter, 'associate_long_unit_id'):
                self.current_encounter.associate_long_unit_id(unit_id, long_unit_id)

    def _cleanup_offline_players(self):
        """Clean up session data for players who are no longer in the current encounter."""
        if not self.current_encounter:
            return
            
        current_unit_ids = set(self.current_encounter.players.keys())
        
        # Find handles for players no longer in current encounter
        offline_handles = []
        for handle, session_data in self.player_sessions.items():
            if session_data['unit_id'] not in current_unit_ids:
                offline_handles.append(handle)
        
        # Remove offline players from unit_id mapping but keep session data
        for handle in offline_handles:
            if handle in self.player_sessions:
                old_unit_id = self.player_sessions[handle]['unit_id']
                if old_unit_id in self.unit_id_to_handle:
                    del self.unit_id_to_handle[old_unit_id]

    def _handle_health_regen(self, entry: ESOLogEntry):
        """Handle HEALTH_REGEN events."""
        # For now, just log that we're processing health regen events
        # In the future, this could track health regeneration patterns
        pass

    def _handle_endless_dungeon_begin(self, entry: ESOLogEntry):
        """Handle ENDLESS_DUNGEON_BEGIN events."""
        # For now, just log that we're processing endless dungeon begin events
        # In the future, this could track endless dungeon progress
        pass

    def _handle_endless_dungeon_stage_end(self, entry: ESOLogEntry):
        """Handle ENDLESS_DUNGEON_STAGE_END events."""
        # For now, just log that we're processing endless dungeon stage end events
        # In the future, this could track stage completion
        pass

    def _handle_endless_dungeon_buff_added(self, entry: ESOLogEntry):
        """Handle ENDLESS_DUNGEON_BUFF_ADDED events."""
        # For now, just log that we're processing endless dungeon buff added events
        # In the future, this could track buff management
        pass

    def _handle_endless_dungeon_buff_removed(self, entry: ESOLogEntry):
        """Handle ENDLESS_DUNGEON_BUFF_REMOVED events."""
        # For now, just log that we're processing endless dungeon buff removed events
        # In the future, this could track buff management
        pass


def find_session_start_offset(log_file: Path, end: int, lookback_bytes: int) -> Optional[int]:
    """Byte offset of the most recent BEGIN_LOG line before *end* in
    *log_file*, searching back at most *lookback_bytes*; None if none."""
    chunk_size = 1024 * 1024
    scanned = 0
    pos = end
    carry = b''
    with open(log_file, 'rb') as f:
        while pos > 0 and scanned < lookback_bytes:
            start = max(0, pos - chunk_size)
            f.seek(start)
            chunk = f.read(pos - start) + carry
            idx = chunk.rfind(b',BEGIN_LOG,')
            if idx != -1:
                line_start = chunk.rfind(b'\n', 0, idx) + 1
                return start + line_start
            carry = chunk[:64]
            scanned += pos - start
            pos = start
    return None


class LogSplitter:
    """Handles automatic splitting of encounter logs into individual encounter files.

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
    """

    # ESO writes CRLF line endings; split files keep them on every OS
    # (text mode alone would give LF on Linux)
    NEWLINE = '\r\n'
    LOCK_NAME = '.esolog-tail-split.lock'
    # Catch-up tolerance for a split written by an older version, which left
    # out the lines the parser rejected: 0.2% of the file, 64 KB at least
    CATCH_UP_SLACK = 65536
    CATCH_UP_SLACK_SHARE = 0.002

    def __init__(self, log_file: Path, diagnostic: bool = False, split_dir: Optional[Path] = None):
        self.log_file = log_file
        self.diagnostic = diagnostic
        self.split_dir = split_dir or log_file.parent  # Use custom dir or same as log file
        self.current_split_file = None
        self.current_split_path = None
        self.current_encounter_info = None
        self.split_files = []  # Track all created split files
        self.file_handle = None  # File handle for current split file
        
        # Zone tracking for combat-based naming
        self.pending_begin_log = None  # Store BEGIN_LOG entry until combat starts
        self.current_zone = None  # Track current zone as we go through the log
        self.current_difficulty = None  # Track current difficulty
        self.combat_started = False  # Track if combat has started
        self.temp_file_path = None  # Temporary file path before rename
        self.final_file_path = None  # Final file path after rename
        
        # Combat tracking for auto-cleanup
        self.combat_event_count = 0  # Count of combat events in current encounter

        # Deduplication: skip flag for encounters already on disk
        self.skip_current = False
        # Index of existing split files: prefix → set of file sizes (the
        # zipped ones are only known this way, see _scan_existing_splits)
        self.existing_splits = {}
        # The session's file on disk was continued rather than written
        # again (see the class docstring): never removed as a copy
        self.continued = False
        # While catching up to a continued file: bytes of it still to pass,
        # its last line, and the slack a split by an older version gets
        self._catch_up = None
        # Another instance of the app holds this folder's lock: write nothing
        self.disabled = False
        self._lock_path = None
        # The first failure to create or write the split file, until a line
        # is written again (issue #111): the monitor shows it in the window
        # (a full disk, a removed drive), where it was a diagnostic print
        self.write_error: Optional[str] = None
        self._batch_failed = False  # a write failed since the last flush

        # Ensure split directory exists
        self.split_dir.mkdir(parents=True, exist_ok=True)

        self._acquire_lock()

        # Scan existing splits for deduplication
        self._scan_existing_splits()

    # ------------------------------------------------------------- lock --

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        """Whether a process with *pid* is running (a stale lock's is not)."""
        if pid <= 0:
            return False
        if os.name == 'nt':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return False
                return code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _acquire_lock(self) -> None:
        """Take the folder's lock, or stand down when a live process has it."""
        self._lock_path = self.split_dir / self.LOCK_NAME
        try:
            holder = int(self._lock_path.read_text(encoding='utf-8').strip() or 0)
        except (OSError, ValueError):
            holder = 0
        if holder and holder != os.getpid() and self._pid_alive(holder):
            self.disabled = True
            self.lock_holder = holder
            return
        self.lock_holder = os.getpid()
        try:
            self._lock_path.write_text(str(os.getpid()), encoding='utf-8')
        except OSError:
            pass  # a read-only folder: split anyway, as before

    def release_lock(self) -> None:
        """Give the folder's lock up (the app is closing or the monitor is
        being rebuilt); a lock another process holds is left alone."""
        if self.disabled or not self._lock_path:
            return
        try:
            if int(self._lock_path.read_text(encoding='utf-8').strip() or 0) == os.getpid():
                self._lock_path.unlink()
        except (OSError, ValueError):
            pass
        
    @staticmethod
    def _strip_numeric_suffix(stem: str) -> str:
        """Strip a trailing ``-N`` numeric suffix from a filename stem."""
        return re.sub(r'-\d+$', '', stem)

    def _scan_existing_splits(self):
        """Scan split directory for existing files and build dedup index.

        A split zipped by the retention job (``<stem>.log.zip``, issue #86)
        counts as the split it holds, indexed by the log's own size: the
        zip's size would never match a split written again."""
        try:
            with os.scandir(self.split_dir) as it:
                for entry in it:
                    filename = entry.name
                    zipped = filename.endswith(split_retention.ZIP_SUFFIX)
                    if zipped:
                        stem = filename[:-len(split_retention.ZIP_SUFFIX)]
                    elif filename.endswith('.log') and not filename.endswith('-temp.log'):
                        stem = filename[:-len('.log')]
                    else:
                        continue
                    if not entry.is_file():
                        continue
                    prefix = self._strip_numeric_suffix(stem)
                    try:
                        size = (split_retention.zipped_log_size(Path(entry.path)) if zipped
                                else entry.stat().st_size)
                    except OSError:
                        continue
                    if size is None:
                        continue
                    if prefix not in self.existing_splits:
                        self.existing_splits[prefix] = set()
                    self.existing_splits[prefix].add(size)
        except OSError:
            pass

    def start_encounter(self, begin_log_entry, zone_name: str = "", difficulty: str = ""):
        """Start a new encounter split file."""
        # Close any existing split file
        self.end_encounter()
        self.skip_current = False
        if self.disabled:
            return  # another instance of the app splits this folder
        
        # Store BEGIN_LOG entry and initialize zone tracking
        self.pending_begin_log = begin_log_entry
        self.current_zone = zone_name if zone_name else ""
        self.current_difficulty = difficulty if difficulty else ""
        self.combat_started = False
        self.combat_event_count = 0  # Reset combat event counter
        
        # Create temporary file immediately
        self._create_temp_file()
        
        # If we already have zone info, rename immediately
        if zone_name:
            self._rename_to_final()
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: BEGIN_LOG detected with zone: {zone_name}{Style.RESET_ALL}")
        else:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: BEGIN_LOG detected, waiting for first zone{Style.RESET_ALL}")
    
    def _create_temp_file(self):
        """Create a temporary file immediately for writing."""
        if not self.pending_begin_log:
            return
            
        # Create temporary filename based on BEGIN_LOG timestamp
        timestamp = self.pending_begin_log.timestamp
        dt = datetime.fromtimestamp(timestamp / 1000)  # Convert from milliseconds
        
        # Format: YYMMDDHHMMSS-temp.log
        time_str = dt.strftime("%y%m%d%H%M%S")
        temp_filename = f"{time_str}-temp.log"
        self.temp_file_path = self.split_dir / temp_filename
        
        try:
            # Open file for writing (create new file)
            self.file_handle = open(self.temp_file_path, 'w', encoding='utf-8',
                                    newline=self.NEWLINE)
            self.current_split_file = self.temp_file_path
            self.current_split_path = self.temp_file_path
            self.current_encounter_info = {
                'path': self.temp_file_path,
                'start_time': timestamp,
                'zone_name': self.current_zone,
                'difficulty': self.current_difficulty
            }
            
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.GREEN}[{timestamp_str}] DIAGNOSTIC: Created temporary file: {self.temp_file_path}{Style.RESET_ALL}")
                
        except Exception as e:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to create temporary file {self.temp_file_path}: {e}{Style.RESET_ALL}")
            if self.write_error is None:
                self.write_error = f"could not create {self.temp_file_path}: {e}"
            self.current_split_file = None
            self.current_split_path = None
            self.current_encounter_info = None
            self.file_handle = None
            self.temp_file_path = None
    
    def _rename_to_final(self):
        """Rename the temporary file to the final name based on combat zone."""
        if not self.temp_file_path or not self.file_handle:
            return
            
        # Close the file handle before renaming
        try:
            self.file_handle.close()
            self.file_handle = None
        except Exception as e:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to close file before rename: {e}{Style.RESET_ALL}")
        
        # Create final filename based on BEGIN_LOG timestamp and combat zone
        timestamp = self.pending_begin_log.timestamp
        dt = datetime.fromtimestamp(timestamp / 1000)  # Convert from milliseconds
        
        # Format: YYMMDDHHMMSS-{Zone-Name with dashes}{-vet or blank}.log
        time_str = dt.strftime("%y%m%d%H%M%S")
        
        difficulty_suffix = "-vet" if self.current_difficulty.upper() == "VETERAN" else ""
        zone_suffix = self.current_zone.replace(" ", "-") if self.current_zone else "Unknown-Zone"
        
        final_filename = f"{time_str}-{zone_suffix}{difficulty_suffix}.log"
        self.final_file_path = self.split_dir / final_filename

        try:
            # Rename the file. Windows refuses a rename onto an existing
            # file; POSIX replaces it silently, which would clobber the
            # session's split, so the existing file is met the same way on
            # every platform
            if self.final_file_path.exists():
                raise FileExistsError(str(self.final_file_path))
            self.temp_file_path.rename(self.final_file_path)

            # Update tracking
            self.current_split_file = self.final_file_path
            self.current_split_path = self.final_file_path
            self.current_encounter_info['path'] = self.final_file_path
            self.split_files.append(self.final_file_path)
            
            # Reopen the file for continued writing
            self.file_handle = open(self.final_file_path, 'a', encoding='utf-8',
                                    newline=self.NEWLINE)
            
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.GREEN}[{timestamp_str}] DIAGNOSTIC: Renamed to final file: {self.final_file_path}{Style.RESET_ALL}")
                
        except Exception as e:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to rename file to {self.final_file_path}: {e}{Style.RESET_ALL}")
            
            # Try to handle rename conflict
            if self._handle_rename_conflict(self.temp_file_path, self.final_file_path):
                if self.skip_current:
                    # Same content detected — don't reopen existing file
                    self.file_handle = None
                else:
                    # Successfully handled conflict, update tracking
                    self.current_split_file = self.final_file_path
                    self.current_split_path = self.final_file_path
                    self.current_encounter_info['path'] = self.final_file_path
                    self.split_files.append(self.final_file_path)

                    # Reopen the file for continued writing
                    self.file_handle = open(self.final_file_path, 'a', encoding='utf-8',
                                            newline=self.NEWLINE)
            else:
                # Keep the temp file if conflict resolution fails
                self.current_split_file = self.temp_file_path
                self.current_split_path = self.temp_file_path
    
    def _handle_rename_conflict(self, temp_file_path, target_file_path):
        """Handle rename conflicts by comparing content and using suffixes if needed.
        
        Args:
            temp_file_path: Path to the temporary file
            target_file_path: Path to the target file
            
        Returns:
            bool: True if conflict was resolved successfully, False otherwise
        """
        try:
            # Check if target file exists
            if not target_file_path.exists():
                # No conflict, just rename
                temp_file_path.rename(target_file_path)
                return True

            # The same session when the file on disk begins with what the
            # temp file holds (the lines up to this BEGIN_COMBAT); see the
            # class docstring for why a whole-file hash could never say so
            temp_bytes = temp_file_path.read_bytes()
            with open(target_file_path, 'rb') as existing:
                head = existing.read(len(temp_bytes) + 65536)
            passed = self._same_session(temp_bytes, head)
            if passed:
                temp_file_path.unlink()
                self._continue_existing(target_file_path, passed)
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.YELLOW}[{timestamp_str}] DIAGNOSTIC: Same session on disk, continuing it: {target_file_path}{Style.RESET_ALL}")
                return True
            else:
                # Different content - find available suffix
                suffix = 1
                while True:
                    # Create suffixed filename
                    stem = target_file_path.stem
                    suffix_file_path = target_file_path.parent / f"{stem}-{suffix}{target_file_path.suffix}"
                    
                    if not suffix_file_path.exists():
                        # Found available name, rename temp file
                        temp_file_path.rename(suffix_file_path)
                        # Update final_file_path to the suffixed version
                        self.final_file_path = suffix_file_path
                        if self.diagnostic:
                            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Renamed to suffixed file: {suffix_file_path}{Style.RESET_ALL}")
                        return True
                    
                    suffix += 1
                    
        except Exception as e:
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to handle rename conflict: {e}{Style.RESET_ALL}")
            return False
    
    @staticmethod
    def _same_session(temp_bytes: bytes, head: bytes) -> int:
        """Whether a file beginning with *head* holds the session the temp
        file holds: its BEGIN_LOG line is the temp file's, and every whole
        line of its head, taken in order, is a line of the temp file (a
        split by an older version lacks the lines its parser rejected, so
        the temp file may hold lines the head does not, never the other way
        round). Returns the bytes of the head the temp file stands for, 0
        when it is another session."""
        temp_lines = temp_bytes.split(b'\n')
        if temp_lines and temp_lines[-1] == b'':
            temp_lines.pop()
        head_lines = head.split(b'\n')
        head_lines.pop()  # the last piece is cut off, or empty after a newline
        if not temp_lines or not head_lines or head_lines[0] != temp_lines[0]:
            return 0
        passed = 0
        j = 0
        for line in head_lines:
            k = j
            while k < len(temp_lines) and temp_lines[k] != line:
                k += 1
            if k == len(temp_lines):
                # Not among the temp file's remaining lines: the session
                # goes on past its preamble here (the temp file ends before
                # the BEGIN_COMBAT that named it), or this is another session
                return passed if b',BEGIN_COMBAT' in line else 0
            j = k + 1
            passed += len(line) + 1
        # The head ended inside the preamble: a file cut short before combat
        return passed

    def _continue_existing(self, target_file_path, passed: int) -> None:
        """Take the session's file on disk over: trim it to its last whole
        line, and arrange for the lines still to come to be skipped until
        they have passed the file's end (see write_log_line). *passed* is
        how much of it the temp file already stood for."""
        size = target_file_path.stat().st_size
        with open(target_file_path, 'rb') as existing:
            tail = existing.read()[-262144:] if size <= 262144 else self._tail(existing, size)
        if tail and not tail.endswith(b'\n'):
            # A crash mid-line: drop the partial line
            cut = tail.rfind(b'\n') + 1
            dropped = len(tail) - cut
            with open(target_file_path, 'r+b') as existing:
                existing.truncate(size - dropped)
            size -= dropped
            tail = tail[:cut]
        lines = tail.splitlines()
        last_line = lines[-1].decode('utf-8', errors='ignore') if lines else ''
        self._catch_up = {
            'remaining': size - passed,
            'slack': max(self.CATCH_UP_SLACK, int(size * self.CATCH_UP_SLACK_SHARE)),
            'last_line': last_line,
            'passed_last': False,
        }
        self.continued = True
        self.skip_current = False
        self.final_file_path = target_file_path

    @staticmethod
    def _tail(handle, size: int, length: int = 262144) -> bytes:
        handle.seek(size - length)
        return handle.read()

    def _catching_up(self, line: str) -> bool:
        """Whether *line* is one the continued file already holds. The
        count of bytes passes the file's end exactly for a split this
        version wrote; a split by an older version is short by the lines it
        left out, so within the slack the file's own last line marks the
        end, and past the slack the rest is appended regardless."""
        state = self._catch_up
        if state is None:
            return False
        if state['passed_last']:
            self._catch_up = None
            return False
        state['remaining'] -= len(line.encode('utf-8', errors='ignore')) + len(self.NEWLINE)
        if state['remaining'] > 0:
            return True  # still inside the file, whichever version wrote it
        # At or past the file's size: the file's last line is met here for a
        # split this version wrote (remaining 0), or a little further on for
        # an older one, whose count ran past because of the lines it lacks
        if line == state['last_line']:
            state['passed_last'] = True  # the next line is new
            return True
        if state['remaining'] <= -state['slack']:
            self._catch_up = None  # the last line never came: append from here
            return False
        return True

    def _is_copy_of_another(self, path) -> bool:
        """Whether *path* repeats another file of its stamp in the folder:
        the same size and the same bytes, or a zipped split of that size."""
        prefix = self._strip_numeric_suffix(path.stem)
        size = path.stat().st_size
        if size in self.existing_splits.get(prefix, ()):
            # A zipped split (its log size is only known from the index)
            for entry in os.scandir(self.split_dir):
                if (entry.name.endswith(split_retention.ZIP_SUFFIX)
                        and self._strip_numeric_suffix(entry.name[:-len(split_retention.ZIP_SUFFIX)]) == prefix
                        and split_retention.zipped_log_size(Path(entry.path)) == size):
                    return True
        for entry in os.scandir(self.split_dir):
            if not entry.name.endswith('.log') or entry.name.endswith('-temp.log'):
                continue
            other = Path(entry.path)
            if other == path or self._strip_numeric_suffix(other.stem) != prefix:
                continue
            try:
                if entry.stat().st_size != size:
                    continue
                with open(path, 'rb') as a, open(other, 'rb') as b:
                    while True:
                        chunk_a, chunk_b = a.read(1 << 20), b.read(1 << 20)
                        if chunk_a != chunk_b:
                            break
                        if not chunk_a:
                            return True
            except OSError:
                continue
        return False

    def write_log_line(self, line: str):
        """Write a log line to the current split file. Not flushed here: a
        flush per line made one OS write per log line (3.3 M for a 573 MB
        session, issue #109); the monitor calls flush() once per batch."""
        if self.skip_current or self.disabled:
            return
        if self._catch_up is not None and self._catching_up(line):
            return  # the continued file holds this line already
        if self.file_handle:
            try:
                self.file_handle.write(line + '\n')
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to write to split file: {e}{Style.RESET_ALL}")
                self._batch_failed = True
                if self.write_error is None:
                    self.write_error = f"could not write to {self.current_split_path}: {e}"

    def flush(self):
        """Push the lines written so far to the split file: the monitor's
        end of each batch of new lines, so a crash loses at most one poll's
        lines, which are still in the game's log for the split's catch-up
        (_continue_existing) to restore. A batch whose writes and flush all
        went through clears write_error (a full disk usually shows here,
        when the buffer reaches the disk)."""
        failed, self._batch_failed = self._batch_failed, False
        if self.file_handle:
            try:
                self.file_handle.flush()
                if not failed:
                    self.write_error = None
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to write to split file: {e}{Style.RESET_ALL}")
                if self.write_error is None:
                    self.write_error = f"could not write to {self.current_split_path}: {e}"

    def start_combat(self):
        """Mark that combat has started - rename file to current zone."""
        if not self.combat_started:
            self.combat_started = True
            if self.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Combat started in zone: {self.current_zone} ({self.current_difficulty}){Style.RESET_ALL}")
            
            # Rename the file to reflect the current zone when combat started
            self._rename_to_final()
    
    def increment_combat_events(self):
        """Increment the combat event counter for the current encounter."""
        self.combat_event_count += 1
    
    def handle_zone_change(self, zone_name: str, difficulty: str):
        """Handle a zone change - update current zone tracking."""
        # Check if this is the first zone we've encountered
        first_zone = not self.current_zone
        
        # Update current zone information
        self.current_zone = zone_name
        self.current_difficulty = difficulty
        
        if self.diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Zone changed to: {zone_name} ({difficulty}){Style.RESET_ALL}")
        
        # Don't rename here - wait for combat to start
        # The file will be renamed when combat begins
    
    def end_encounter(self):
        """End the current encounter and close the split file."""
        # Check if we should delete temp files with no combat or minimal combat
        should_delete_temp = False
        if self.temp_file_path and self.temp_file_path.exists():
            # Delete temp files with no combat or very few combat events (likely incomplete encounters)
            if self.combat_event_count == 0:
                should_delete_temp = True
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.YELLOW}[{timestamp_str}] DIAGNOSTIC: No combat events detected, will delete temp file: {self.temp_file_path}{Style.RESET_ALL}")
            elif self.combat_event_count < 5 and not self.combat_started:
                # Delete temp files with very few combat events that never had proper combat start
                should_delete_temp = True
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.YELLOW}[{timestamp_str}] DIAGNOSTIC: Minimal combat events ({self.combat_event_count}) and no combat start, will delete temp file: {self.temp_file_path}{Style.RESET_ALL}")
            elif self.temp_file_path.name.endswith('-temp.log') and not self.final_file_path:
                # Delete temp files that were never properly renamed (orphaned temp files)
                should_delete_temp = True
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.YELLOW}[{timestamp_str}] DIAGNOSTIC: Orphaned temp file never renamed, will delete: {self.temp_file_path}{Style.RESET_ALL}")
        
        if self.file_handle:
            try:
                self.file_handle.close()
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.YELLOW}[{timestamp_str}] DIAGNOSTIC: Closed split file: {self.current_split_path}{Style.RESET_ALL}")
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to close split file {self.current_split_path}: {e}{Style.RESET_ALL}")
        
        # Delete temp file if it should be cleaned up
        if should_delete_temp:
            try:
                self.temp_file_path.unlink()
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.GREEN}[{timestamp_str}] DIAGNOSTIC: Deleted temp file: {self.temp_file_path}{Style.RESET_ALL}")
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to delete temp file {self.temp_file_path}: {e}{Style.RESET_ALL}")
        
        # Dedup check: now that the file is complete, compare against the
        # folder as it is now (another file of the same stamp with the same
        # size and bytes, or a zipped split of that size); a continued file
        # is the session's own and is never the copy
        if (self.final_file_path and not should_delete_temp and not self.skip_current
                and not self.continued):
            try:
                if self.final_file_path.exists() and self._is_copy_of_another(self.final_file_path):
                    self.skip_current = True
                    try:
                        self.final_file_path.unlink()
                    except OSError:
                        pass
                    if self.diagnostic:
                        ts = time.strftime("%H:%M:%S", time.localtime())
                        _console(f"{Fore.YELLOW}[{ts}] DIAGNOSTIC: Removed duplicate split: {self.final_file_path.name}{Style.RESET_ALL}")
            except OSError:
                pass

        # Add newly created file to dedup index
        if self.final_file_path and not self.skip_current:
            try:
                if self.final_file_path.exists():
                    stem = self.final_file_path.stem
                    prefix = self._strip_numeric_suffix(stem)
                    size = self.final_file_path.stat().st_size
                    if prefix not in self.existing_splits:
                        self.existing_splits[prefix] = set()
                    self.existing_splits[prefix].add(size)
            except OSError:
                pass

        # Always clear encounter state, regardless of file handle status
        self.skip_current = False
        self.continued = False
        self._catch_up = None
        self.file_handle = None
        self.current_split_file = None
        self.current_split_path = None
        self.current_encounter_info = None
        self.pending_begin_log = None
        self.current_zone = None
        self.current_difficulty = None
        self.combat_started = False
        self.temp_file_path = None
        self.final_file_path = None
        self.combat_event_count = 0
    
    def close_for_waiting(self):
        """Close the current split file when waiting for new events to prevent data loss."""
        if self.file_handle:
            try:
                self.file_handle.close()
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Closed split file for waiting: {self.current_split_path}{Style.RESET_ALL}")
                self.file_handle = None
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to close split file for waiting: {e}{Style.RESET_ALL}")
    
    def reopen_for_append(self):
        """Reopen the current split file for appending when new events arrive."""
        if self.current_split_path and not self.file_handle:
            try:
                self.file_handle = open(self.current_split_path, 'a', encoding='utf-8',
                                        newline=self.NEWLINE)
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Reopened split file for append: {self.current_split_path}{Style.RESET_ALL}")
            except Exception as e:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Failed to reopen split file for append: {e}{Style.RESET_ALL}")
                self.file_handle = None

    def cleanup(self):
        """Close the current split and give the folder's lock up."""
        self.end_encounter()
        self.release_lock()


class LogFileMonitor:
    """Simple file polling monitor for log file changes."""

    def __init__(self, analyzer: ESOLogAnalyzer, log_file: Path, read_all_then_tail: bool = False, tail_and_split: bool = False, split_dir: Optional[Path] = None):
        self.analyzer = analyzer
        self.log_file = log_file
        self.last_position = 0
        self.read_all_then_tail = read_all_then_tail
        self.tail_and_split = tail_and_split
        self.has_read_all = False
        self.diagnostic = analyzer.diagnostic
        self.running = False
        self.last_entry_offset_ms = None  # latest line's relative ms, for freshness
        self._split_warning = None  # the split failure last reported

        # Initialize log splitter if needed
        self.log_splitter = LogSplitter(log_file, diagnostic=self.diagnostic, split_dir=split_dir) if tail_and_split else None
        if self.log_splitter is not None and self.log_splitter.disabled:
            # Another instance of the app holds the folder's lock: two
            # splitters would append one session from two sides
            self.analyzer._notify(
                'on_diagnostic',
                f"Split files are being written by another ESO Log Tail (process "
                f"{self.log_splitter.lock_holder}); this one writes none")

        # Initialize position based on mode
        if self.log_file.exists():
            if read_all_then_tail:
                # Start from the beginning to read everything first
                _console(f"{Fore.CYAN}Reading entire log file from the beginning...{Style.RESET_ALL}")
                self.last_position = 0
                self._process_entire_file()
                _console(f"{Fore.GREEN}Monitoring for new data. Ctrl-C to stop...{Style.RESET_ALL}\n")
            else:
                # Look back through recent log entries to find zone changes
                self._initialize_zone_history()
                self.last_position = self.log_file.stat().st_size
                # Attaching mid-file: replay the latest session so its
                # fights load into the UI, the roster is known, and a
                # missing split file for the session is created
                self._load_latest_session()
            # Initial freshness snapshot (content-derived; falls back to mtime)
            self._emit_initial_log_status()

    # Roster/metadata events swept from the current session when attaching
    # mid-file. Combat events are deliberately excluded so no old fights
    # replay; markers include the delimiting commas so they only match the
    # event-type field (checked within the line's leading bytes).
    PREAMBLE_EVENT_MARKERS = (
        b',BEGIN_LOG,', b',ZONE_CHANGED,', b',TRIAL_INIT,',
        b',UNIT_ADDED,', b',UNIT_CHANGED,', b',PLAYER_INFO,',
        b',ABILITY_INFO,',
    )
    # Cap the backward search for the session's BEGIN_LOG
    PREAMBLE_LOOKBACK_BYTES = 2 * 1024 * 1024 * 1024

    def _find_session_start_offset(self, end: int) -> Optional[int]:
        """Byte offset of the most recent BEGIN_LOG line before *end*."""
        return find_session_start_offset(self.log_file, end, self.PREAMBLE_LOOKBACK_BYTES)

    # A session replayed at attach above this size reports its progress
    REPLAY_PROGRESS_BYTES = 8 * 1024 * 1024

    def _session_split_exists(self, session_start: int) -> bool:
        """True when a split file for this session's stamp already exists."""
        if self.log_splitter is None:
            return False
        try:
            with open(self.log_file, 'rb') as f:
                f.seek(session_start)
                line = f.readline().decode('utf-8', errors='ignore')
            parts = line.split(',')
            if len(parts) < 3 or parts[1] != 'BEGIN_LOG':
                return False
            stamp = datetime.fromtimestamp(
                int(parts[2]) / 1000).strftime('%y%m%d%H%M%S')
            # A zipped split (issue #86) is the session's split too: missing
            # it here would write the session out again at every start
            split_dir = Path(self.log_splitter.split_dir)
            return (any(split_dir.glob(f"{stamp}*.log"))
                    or any(split_dir.glob(f"{stamp}*{split_retention.ZIP_SUFFIX}")))
        except (OSError, ValueError):
            return False

    def _load_latest_session(self):
        """Replay the log's most recent session up to the attach point.

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
        """
        try:
            end = self.last_position
            if end <= 0:
                return
            start = self._find_session_start_offset(end)
            if start is None:
                self._backfill_session_preamble()
                return
            # The session's split file, when it exists, is continued by the
            # splitter itself (LogSplitter._handle_rename_conflict), so the
            # replay runs through it like any other lines: a complete split
            # gains nothing, a truncated one its missing tail
            self.analyzer._notify(
                'on_diagnostic',
                f"Loading last session ({(end - start) // (1024 * 1024)} MB)…")
            self._process_range(start, end)
            self._report_split_status()
        except Exception as exc:
            _console(f"Latest-session load failed: {exc}")
            try:
                self._backfill_session_preamble()
            except Exception:
                pass

    def _process_range(self, start: int, end: int):
        """Stream lines in [start, end) through the normal processing path.
        A range over REPLAY_PROGRESS_BYTES reports its progress (the
        window's progress bar), about every 1%."""
        total = end - start
        report = total > self.REPLAY_PROGRESS_BYTES
        label = "Loading last session"
        step = max(1, total // 100)
        done = last = 0
        if report:
            self.analyzer._notify('on_parse_progress', label, 0, total)
        try:
            with open(self.log_file, 'rb') as f:
                f.seek(start)
                while f.tell() < end:
                    raw = f.readline()
                    if not raw:
                        break
                    done += len(raw)
                    if report and done - last >= step:
                        last = done
                        self.analyzer._notify('on_parse_progress', label, min(done, total), total)
                    line = raw.decode('utf-8', errors='ignore').strip()
                    if line:
                        self._process_one_line(line)
        finally:
            if self.log_splitter:
                self.log_splitter.flush()
            if report:
                self.analyzer._notify('on_parse_progress', label, total, total)

    def _backfill_session_preamble(self):
        """Process the current session's roster/metadata up to attach point.

        Best-effort: any failure leaves the monitor tailing normally, just
        without pre-attach roster knowledge (the pre-fix behavior).
        """
        try:
            end = self.last_position
            if end <= 0:
                return
            start = self._find_session_start_offset(end)
            aligned = start is not None  # found offsets are line starts
            if start is None:
                # Session began beyond the lookback cap: sweep what we can
                start = max(0, end - self.PREAMBLE_LOOKBACK_BYTES)
            processed = 0
            with open(self.log_file, 'rb') as f:
                f.seek(start)
                if start > 0 and not aligned:
                    f.readline()  # sync to a line boundary
                while f.tell() < end:
                    raw = f.readline()
                    if not raw:
                        break
                    head = raw[:40]
                    if not any(marker in head
                               for marker in self.PREAMBLE_EVENT_MARKERS):
                        continue
                    line = raw.decode('utf-8', errors='ignore').strip()
                    entry = self.analyzer.log_parser.parse_line(line)
                    if entry is not None:
                        self.analyzer.process_log_entry(entry)
                        processed += 1
            if processed and self.diagnostic:
                _console(f"{Fore.CYAN}Session preamble: learned roster from "
                         f"{processed} events{Style.RESET_ALL}")
        except Exception as exc:
            _console(f"Session preamble backfill failed: {exc}")

    def _emit_initial_log_status(self):
        """Emit a startup freshness snapshot derived from the file itself."""
        from log_freshness import derive_log_freshness, derive_session_epoch_ms
        try:
            status = derive_log_freshness(self.log_file)
        except Exception:
            return
        # Seed the session epoch when attaching mid-file (tail-only mode) so
        # per-batch freshness stays exact without re-scanning the file.
        if self.analyzer.log_start_unix_timestamp is None and status.source == 'exact':
            epoch_ms = derive_session_epoch_ms(self.log_file)
            if epoch_ms is not None:
                self.analyzer.log_start_unix_timestamp = epoch_ms // 1000
        self.analyzer._notify('on_log_status', status)

    def _initialize_zone_history(self):
        """Look back through recent log entries to find zone changes."""
        if not self.log_file.exists():
            return
            
        file_size = self.log_file.stat().st_size
        # Look back through the last 50KB of the file for zone changes
        lookback_size = min(50000, file_size)
        start_position = max(0, file_size - lookback_size)
        
        _console(f"{Fore.CYAN}Scanning recent log entries for zone changes...{Style.RESET_ALL}")
        
        entries = self.analyzer._process_log_file_from_position(self.log_file, start_position)
        zone_found = False
        latest_zone = None

        # Process entries in chronological order to find the most recent zone change
        for entry in entries:
            if entry.event_type == "ZONE_CHANGED" and len(entry.fields) >= 3:
                zone_id = entry.fields[0].strip('"')
                zone_name = entry.fields[1].strip('"')
                difficulty = entry.fields[2].strip('"')
                self.analyzer._add_zone_to_history(entry.timestamp, zone_name, zone_id, difficulty)
                latest_zone = (zone_name, zone_id, difficulty)  # zone_history's order
                if not zone_found:
                    _console(f"{Fore.GREEN}Found recent zone: {zone_name}{Style.RESET_ALL}")
                    zone_found = True

        if latest_zone is not None:
            # Seed current zone from the lookback and tell frontends
            (self.analyzer.current_zone, self.analyzer.current_zone_id,
             self.analyzer.current_difficulty) = latest_zone
            self.analyzer._notify('on_zone_changed', latest_zone[0], latest_zone[2])
        else:
            _console(f"{Fore.YELLOW}No recent zone changes found in log{Style.RESET_ALL}")

    def _find_catchup_start(self, file_size, max_fights=20):
        """Scan backward through the file for BEGIN_COMBAT markers.

        Returns a byte offset just before the *max_fights*-th BEGIN_COMBAT
        from the end so that catch-up only processes recent fights.
        Returns 0 if the file is small or doesn't contain enough fights.
        """
        CHUNK = 1_000_000  # 1 MB per read
        marker = b',BEGIN_COMBAT'
        found = 0
        offset = file_size

        with open(self.log_file, 'rb') as f:
            while offset > 0:
                read_start = max(0, offset - CHUNK)
                f.seek(read_start)
                data = f.read(offset - read_start)

                search_end = len(data)
                while True:
                    idx = data.rfind(marker, 0, search_end)
                    if idx == -1:
                        break
                    found += 1
                    if found >= max_fights:
                        # Back up to the start of this line
                        nl = data.rfind(b'\n', 0, idx)
                        if nl >= 0:
                            return read_start + nl + 1
                        return read_start
                    search_end = idx

                offset = read_start

        return 0  # not enough fights — read from beginning

    def _process_entire_file(self):
        """Process the log file, jumping ahead in large files.

        For files larger than 2 MB the method scans backward for
        BEGIN_COMBAT markers and only processes the last ~20 fights,
        which makes catch-up near-instant on multi-GB logs.
        """
        if not self.log_file.exists():
            return

        file_size = self.log_file.stat().st_size
        start_position = 0

        # For large files, jump ahead to only scan the last ~20 fights
        if file_size > 2_000_000:
            start_position = self._find_catchup_start(file_size, max_fights=20)
            if start_position > 0:
                mb_skipped = start_position / 1_000_000
                _console(f"{Fore.CYAN}Large log ({file_size / 1_000_000:.1f} MB) "
                      f"— skipping to last ~20 fights ({mb_skipped:.1f} MB ahead){Style.RESET_ALL}")

        if self.diagnostic:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: Processing {self.log_file.name} "
                  f"from position {start_position}{Style.RESET_ALL}")

        line_count = 0
        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            if start_position > 0:
                f.seek(start_position)
                f.readline()  # skip partial line at boundary

            while True:
                line = f.readline()
                if not line:
                    break

                line = line.strip()
                if line:
                    entry = self.analyzer.log_parser.parse_line(line)
                    if entry:
                        if self.log_splitter:
                            self._handle_log_splitting(entry, line)
                        self.analyzer.process_log_entry(entry)
                    line_count += 1

            self.last_position = f.tell()

        if self.diagnostic:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: Processed {line_count} lines "
                  f"from {self.log_file.name}, now tailing{Style.RESET_ALL}")

        # Close any open split files after processing
        if self.log_splitter:
            self.log_splitter.end_encounter()

        self.has_read_all = True

    def check_for_changes(self, cancel_check=None):
        """Check for file changes and process new lines.

        Args:
            cancel_check: Optional callable returning True to abort processing early
                (used to keep 'q' responsive during catch-up on large backlogs).
        """
        if not self.log_file.exists():
            return False

        current_size = self.log_file.stat().st_size
        if current_size > self.last_position:
            # Reopen split file for appending when new data arrives
            if self.log_splitter:
                self.log_splitter.reopen_for_append()

            if self.diagnostic:
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: File growth detected in {self.log_file.name} (size: {current_size}, pos: {self.last_position}){Style.RESET_ALL}")
            self._process_new_lines(cancel_check=cancel_check)
            return True
        else:
            # Close split file when waiting for new data
            if self.log_splitter:
                self.log_splitter.close_for_waiting()
            
            if self.diagnostic:
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.BLUE}[{timestamp}] DIAGNOSTIC: No changes in {self.log_file.name} (size: {current_size}, pos: {self.last_position}){Style.RESET_ALL}")
        return False

    def _process_new_lines(self, cancel_check=None):
        """Process new lines added to the log file.

        Args:
            cancel_check: Optional callable returning True to abort the processing
                loop early (polled every 500 lines to keep 'q' responsive during
                catch-up on large backlogs).
        """
        if not self.log_file.exists():
            return

        current_size = self.log_file.stat().st_size
        if current_size <= self.last_position:
            if self.diagnostic:
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.BLUE}[{timestamp}] DIAGNOSTIC: No new data in {self.log_file.name} (size: {current_size}, pos: {self.last_position}){Style.RESET_ALL}")
            return

        if self.diagnostic:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: Reading new data from {self.log_file.name} (size: {current_size}, pos: {self.last_position}){Style.RESET_ALL}")

        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(self.last_position)
            new_lines = f.readlines()
            new_end_position = f.tell()

        if self.diagnostic:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.GREEN}[{timestamp}] DIAGNOSTIC: Read {len(new_lines)} lines from {self.log_file.name}{Style.RESET_ALL}")

        CANCEL_POLL_INTERVAL = 500
        for idx, line in enumerate(new_lines):
            # Periodic cancel check during large catch-up batches
            if cancel_check is not None and idx % CANCEL_POLL_INTERVAL == 0 and idx > 0:
                if cancel_check():
                    # Advance last_position by the bytes consumed so far so resume
                    # doesn't re-process already-handled lines.
                    self.last_position += sum(len(l) for l in new_lines[:idx])
                    if self.log_splitter:
                        self.log_splitter.flush()
                    if self.diagnostic:
                        timestamp = time.strftime("%H:%M:%S", time.localtime())
                        _console(f"{Fore.YELLOW}[{timestamp}] DIAGNOSTIC: Line processing aborted at line {idx}/{len(new_lines)}{Style.RESET_ALL}")
                    return

            line = line.strip()
            if line:
                self._process_one_line(line)

        if self.log_splitter:
            self.log_splitter.flush()
        self.last_position = new_end_position
        if new_lines:
            self._emit_log_status(new_end_position)

    def _process_one_line(self, line: str):
        """Parse one log line and run it through splitter and analyzer."""
        entry = self.analyzer.log_parser.parse_line(line)
        offset_ms = parse_relative_ms(line)
        if offset_ms is not None:
            self.last_entry_offset_ms = offset_ms
        if entry:
            if self.log_splitter:
                self._handle_log_splitting(entry, line)
            self.analyzer.process_log_entry(entry)
        elif self.log_splitter:
            # A line the parser rejects (an END_CAST with a cancel reason,
            # an OBJECT unit) is still the session's: the split keeps it
            self.log_splitter.write_log_line(line)

    def _emit_log_status(self, size_bytes: int):
        """Notify listeners of the log's current freshness."""
        status = status_from_tracking(
            self.log_file, size_bytes,
            self.analyzer.log_start_unix_timestamp,
            self.last_entry_offset_ms,
        )
        self.analyzer._notify('on_log_status', status)
        self._report_split_status()

    def _report_split_status(self):
        """Tell listeners when split writing fails or works again (issue
        #111): once per change, as an 'on_warning' from source 'split'."""
        error = self.log_splitter.write_error if self.log_splitter is not None else None
        if error == self._split_warning:
            return
        self._split_warning = error
        self.analyzer._notify('on_warning', 'split',
                              f"Split file writing stopped: {error}" if error else None)

    def _handle_log_splitting(self, entry, line: str):
        """Handle log splitting logic based on log entry type."""
        if not self.log_splitter:
            return
            
        # Handle BEGIN_LOG - start new encounter
        if entry.event_type == "BEGIN_LOG":
            # Start encounter without zone info - will wait for first zone
            self.log_splitter.start_encounter(entry)
            # Write the BEGIN_LOG line
            self.log_splitter.write_log_line(line)
        
        # Handle ZONE_CHANGED - track current zone
        elif entry.event_type == "ZONE_CHANGED":
            # Extract zone name and difficulty from ZONE_CHANGED
            # Format: ZONE_CHANGED,zone_id,"Zone Name",difficulty
            if len(entry.fields) >= 3:
                zone_id = entry.fields[0].strip('"') if entry.fields[0] else ""
                zone_name = entry.fields[1].strip('"') if len(entry.fields) > 1 else ""
                difficulty = entry.fields[2].strip('"') if len(entry.fields) > 2 else ""
                
                # Update current zone tracking
                self.log_splitter.handle_zone_change(zone_name, difficulty)
                
                # Write the ZONE_CHANGED line
                self.log_splitter.write_log_line(line)
        
        # Handle BEGIN_COMBAT - rename file to current zone
        elif entry.event_type == "BEGIN_COMBAT":
            self.log_splitter.start_combat()
            # Write the BEGIN_COMBAT line
            self.log_splitter.write_log_line(line)
        
        # Handle COMBAT_EVENT - increment combat counter
        elif entry.event_type == "COMBAT_EVENT":
            self.log_splitter.increment_combat_events()
            # Write the COMBAT_EVENT line
            self.log_splitter.write_log_line(line)
        
        # Handle END_LOG - end current encounter
        elif entry.event_type == "END_LOG":
            # Always write END_LOG to split file if we have an active split file
            if self.log_splitter.file_handle:
                self.log_splitter.write_log_line(line)
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_LOG written to split file{Style.RESET_ALL}")
            else:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: END_LOG NOT written - no file handle{Style.RESET_ALL}")
            
            # End the encounter and close the split file
            if self.log_splitter.pending_begin_log or self.log_splitter.current_split_file:
                self.log_splitter.end_encounter()
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_LOG detected, closing split file{Style.RESET_ALL}")
            else:
                if self.diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: END_LOG detected but no active split file to close{Style.RESET_ALL}")
        
        # Write all other lines to current split file
        else:
            self.log_splitter.write_log_line(line)

def _find_eso_log_file_windows(diagnostic: bool = False) -> Optional[Path]:
    """Enhanced Windows-specific ESO log file detection with comprehensive search."""
    
    # Windows-specific search locations
    search_locations = [
        Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs",
        Path.home() / "OneDrive" / "Documents" / "Elder Scrolls Online" / "live" / "Logs",
    ]
    
    found_directories = []
    found_encounter_logs = []
    
    if diagnostic:
        timestamp_str = time.strftime("%H:%M:%S", time.localtime())
        _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Searching Windows locations for ESO log directories{Style.RESET_ALL}")
    
    # Check each directory
    for directory in search_locations:
        if directory.exists():
            found_directories.append(directory)
            encounter_log = directory / "Encounter.log"
            
            if diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Found directory: {directory}{Style.RESET_ALL}")
            
            # Check for Encounter.log in this directory
            if encounter_log.exists():
                try:
                    # Get file modification time
                    mod_time = encounter_log.stat().st_mtime
                    mod_datetime = datetime.fromtimestamp(mod_time)
                    mod_time_str = mod_datetime.strftime("%Y-%m-%d %H:%M:%S")
                    
                    found_encounter_logs.append({
                        'path': encounter_log,
                        'directory': directory,
                        'mod_time': mod_time,
                        'mod_time_str': mod_time_str
                    })
                    
                    _console(f"{Fore.GREEN}Encounter.log found: {encounter_log}{Style.RESET_ALL}")
                    _console(f"{Fore.GREEN}Last modified: {mod_time_str} (local time){Style.RESET_ALL}")
                    
                except OSError as e:
                    if diagnostic:
                        timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                        _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Error accessing {encounter_log}: {e}{Style.RESET_ALL}")
            else:
                if diagnostic:
                    timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                    _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: No Encounter.log in {directory}{Style.RESET_ALL}")
        else:
            if diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Directory not found: {directory}{Style.RESET_ALL}")
    
    # If no directories found, exit with summary
    if not found_directories:
        _console(f"{Fore.YELLOW}No ESO log directories found on Windows.{Style.RESET_ALL}")
        _console(f"{Fore.CYAN}Searched locations:{Style.RESET_ALL}")
        for location in search_locations:
            _console(f"{Fore.WHITE}  - {location}{Style.RESET_ALL}")
        _console(f"{Fore.CYAN}Please ensure ESO is installed and encounter logging is enabled.{Style.RESET_ALL}")
        return None
    
    # Print found directories
    _console(f"{Fore.GREEN}Found {len(found_directories)} ESO log directory(ies):{Style.RESET_ALL}")
    for directory in found_directories:
        _console(f"{Fore.WHITE}  - {directory}{Style.RESET_ALL}")
        
        # Find most recently updated file in directory
        try:
            most_recent_file = None
            most_recent_time = 0
            
            for file_path in directory.iterdir():
                if file_path.is_file():
                    try:
                        file_time = file_path.stat().st_mtime
                        if file_time > most_recent_time:
                            most_recent_time = file_time
                            most_recent_file = file_path
                    except OSError:
                        continue
            
            if most_recent_file:
                mod_datetime = datetime.fromtimestamp(most_recent_time)
                mod_time_str = mod_datetime.strftime("%Y-%m-%d %H:%M:%S")
                _console(f"{Fore.CYAN}    Most recent file: {most_recent_file.name} ({mod_time_str}){Style.RESET_ALL}")
            else:
                _console(f"{Fore.CYAN}    Directory is empty{Style.RESET_ALL}")
                
        except OSError as e:
            if diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: Error scanning {directory}: {e}{Style.RESET_ALL}")
    
    # If Encounter.log files found, pick the most recent one
    if found_encounter_logs:
        # Sort by modification time (most recent first)
        found_encounter_logs.sort(key=lambda x: x['mod_time'], reverse=True)
        
        most_recent_log = found_encounter_logs[0]
        
        if len(found_encounter_logs) > 1:
            _console(f"{Fore.GREEN}Selected most recently updated Encounter.log:{Style.RESET_ALL}")
            _console(f"{Fore.WHITE}  {most_recent_log['path']}{Style.RESET_ALL}")
            _console(f"{Fore.WHITE}  Last modified: {most_recent_log['mod_time_str']}{Style.RESET_ALL}")
        
        return most_recent_log['path']
    
    # If directories found but no Encounter.log files, pick the directory with most recent activity
    if found_directories:
        best_directory = None
        best_time = 0
        
        for directory in found_directories:
            try:
                # Check directory modification time
                dir_time = directory.stat().st_mtime
                
                # Also check for most recent file in directory
                most_recent_file_time = 0
                for file_path in directory.iterdir():
                    if file_path.is_file():
                        try:
                            file_time = file_path.stat().st_mtime
                            most_recent_file_time = max(most_recent_file_time, file_time)
                        except OSError:
                            continue
                
                # Use the more recent of directory time or most recent file time
                effective_time = max(dir_time, most_recent_file_time)
                
                if effective_time > best_time:
                    best_time = effective_time
                    best_directory = directory
                    
            except OSError:
                continue
        
        if best_directory:
            _console(f"{Fore.YELLOW}No Encounter.log files found, but will monitor:{Style.RESET_ALL}")
            _console(f"{Fore.WHITE}  {best_directory / 'Encounter.log'}{Style.RESET_ALL}")
            return best_directory / "Encounter.log"
    
    return None

def _find_eso_log_file(diagnostic: bool = False) -> Optional[Path]:
    """Try to find the ESO encounter log file in common locations with enhanced detection."""
    
    # Use Windows-specific detection for Windows
    if sys.platform == "win32":
        return _find_eso_log_file_windows(diagnostic)
    
    # Enhanced ESO log file locations with more comprehensive coverage for other platforms
    possible_paths = []
    
    if sys.platform == "darwin":
        # macOS - native and Wine installations
        possible_paths = [
            # Native macOS installations
            Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / "Documents" / "Elder Scrolls Online" / "Logs" / "Encounter.log",
            # Wine installations
            Path.home() / ".wine" / "drive_c" / "users" / "Public" / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / ".wine" / "drive_c" / "users" / os.getenv("USER", "user") / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            # Alternative Wine paths
            Path.home() / ".wine" / "drive_c" / "Program Files" / "Zenimax Online" / "The Elder Scrolls Online" / "game" / "client" / "Logs" / "Encounter.log",
        ]
    else:
        # Linux - Wine and native installations
        possible_paths = [
            # Wine installations (most common on Linux)
            Path.home() / ".wine" / "drive_c" / "users" / "Public" / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / ".wine" / "drive_c" / "users" / os.getenv("USER", "user") / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            # Alternative Wine paths
            Path.home() / ".wine" / "drive_c" / "Program Files" / "Zenimax Online" / "The Elder Scrolls Online" / "game" / "client" / "Logs" / "Encounter.log",
            Path.home() / ".wine" / "drive_c" / "Program Files (x86)" / "Zenimax Online" / "The Elder Scrolls Online" / "game" / "client" / "Logs" / "Encounter.log",
            # Native Linux installations (if any)
            Path.home() / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / "Documents" / "Elder Scrolls Online" / "Logs" / "Encounter.log",
            # Steam (Proton) paths: Steam Deck/SteamOS, native Steam, Flatpak Steam
            Path.home() / ".steam" / "steam" / "steamapps" / "compatdata" / "306130" / "pfx" / "drive_c" / "users" / "steamuser" / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / ".local" / "share" / "Steam" / "steamapps" / "compatdata" / "306130" / "pfx" / "drive_c" / "users" / "steamuser" / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
            Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam" / "steamapps" / "compatdata" / "306130" / "pfx" / "drive_c" / "users" / "steamuser" / "Documents" / "Elder Scrolls Online" / "live" / "Logs" / "Encounter.log",
        ]

    # Show diagnostic information if requested
    if diagnostic:
        timestamp_str = time.strftime("%H:%M:%S", time.localtime())
        _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Searching for Encounter.log in {len(possible_paths)} locations{Style.RESET_ALL}")
        for i, path in enumerate(possible_paths, 1):
            status = "✓ EXISTS" if path.exists() else "✗ not found"
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: {i:2d}. {path} - {status}{Style.RESET_ALL}")

    # Search for existing files
    found_paths = []
    for path in possible_paths:
        if path.exists():
            found_paths.append(path)
    
    # Return the first found path, or None if none found
    if found_paths:
        if diagnostic:
            timestamp_str = time.strftime("%H:%M:%S", time.localtime())
            _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: Found {len(found_paths)} log file(s), using: {found_paths[0]}{Style.RESET_ALL}")
        return found_paths[0]

    return None

def _handle_replay_log_splitting(log_splitter, entry, line: str):
    """Handle log splitting logic for replay mode."""
    # Handle BEGIN_LOG - start new encounter
    if entry.event_type == "BEGIN_LOG":
        # Start encounter without zone info - will wait for first zone
        log_splitter.start_encounter(entry)
        # Write the BEGIN_LOG line
        log_splitter.write_log_line(line)
    
    # Handle ZONE_CHANGED - track current zone
    elif entry.event_type == "ZONE_CHANGED":
        # Extract zone name and difficulty from ZONE_CHANGED
        # Format: ZONE_CHANGED,zone_id,"Zone Name",difficulty
        if len(entry.fields) >= 3:
            zone_id = entry.fields[0].strip('"') if entry.fields[0] else ""
            zone_name = entry.fields[1].strip('"') if len(entry.fields) > 1 else ""
            difficulty = entry.fields[2].strip('"') if len(entry.fields) > 2 else ""
            
            # Update current zone tracking
            log_splitter.handle_zone_change(zone_name, difficulty)
            
            # Write the ZONE_CHANGED line
            log_splitter.write_log_line(line)
    
    # Handle BEGIN_COMBAT - rename file to current zone
    elif entry.event_type == "BEGIN_COMBAT":
        log_splitter.start_combat()
        # Write the BEGIN_COMBAT line
        log_splitter.write_log_line(line)
    
    # Handle COMBAT_EVENT - increment combat counter
    elif entry.event_type == "COMBAT_EVENT":
        log_splitter.increment_combat_events()
        # Write the COMBAT_EVENT line
        log_splitter.write_log_line(line)
    
    # Handle END_LOG - end current encounter
    elif entry.event_type == "END_LOG":
        # Always write END_LOG to split file if we have an active split file
        if log_splitter.file_handle:
            log_splitter.write_log_line(line)
            if log_splitter.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_LOG written to split file{Style.RESET_ALL}")
        else:
            if log_splitter.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: END_LOG NOT written - no file handle{Style.RESET_ALL}")
        
        # End the encounter and close the split file
        if log_splitter.pending_begin_log or log_splitter.current_split_file:
            log_splitter.end_encounter()
            if log_splitter.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.CYAN}[{timestamp_str}] DIAGNOSTIC: END_LOG detected, closing split file{Style.RESET_ALL}")
        else:
            if log_splitter.diagnostic:
                timestamp_str = time.strftime("%H:%M:%S", time.localtime())
                _console(f"{Fore.RED}[{timestamp_str}] DIAGNOSTIC: END_LOG detected but no active split file to close{Style.RESET_ALL}")
    
    # Write all other lines to current split file
    else:
        log_splitter.write_log_line(line)

