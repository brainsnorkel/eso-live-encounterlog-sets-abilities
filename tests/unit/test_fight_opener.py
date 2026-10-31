#!/usr/bin/env python3
"""Who opened the fight, and with what (issue #159, fight_opener).

The engine tests feed log lines through the analyzer, in the shape of the
real ones the survey read: a group member's hit or taunt a few ms before
the logging player's BEGIN_COMBAT, a TAUNTED sharing its cast id with the
skill's hit, a shield absorb followed by its attack in the same
millisecond, a hostile's BEGIN_CAST naming the player it goes for, a dead
monster's leftover hits. The line tests build entries by hand.
"""

import unittest

from esolog_tail import ESOLogAnalyzer, FightHistory
from fight_history import FightHistoryEntry
from fight_opener import (
    ARENA_ZONES,
    OPENER_WINDOW_MS,
    TIME_SHOWN_MS,
    PlayerName,
    opener_parts,
    seconds_text,
    time_text,
)

EPOCH = 1759600000000
BOSS_ID, MOB_ID = 1000001, 1000002
KNOT_ID = 122316  # a scripted mechanic (fight_opener.SCRIPTED_MONSTERS)
LOOK_AT = 121308  # a scripted cast (fight_opener.SCRIPTED_ABILITIES)
LA, INNER_RAGE, TAUNT, GOADING = 100, 200, 38254, 210
CONCUSSION, SUSCEPTIBILITY, SUNDERED = 300, 301, 302
CALTROPS, CALTROPS_TICK = 400, 401
SHOCK, WICKED_BONDS, BARRIER, SWIPE = 500, 501, 600, 700
ABILITIES = {
    LA: "Light Attack (Ice)", INNER_RAGE: "Inner Rage", TAUNT: "Taunt", GOADING: "Goading Throw",
    CONCUSSION: "Concussion", SUSCEPTIBILITY: "Elemental Susceptibility", SUNDERED: "Sundered",
    CALTROPS: "Razor Caltrops", CALTROPS_TICK: "Razor Caltrops", SHOCK: "Shock",
    WICKED_BONDS: "Wicked Bonds", BARRIER: "Scorching Barrier", SWIPE: "Crushing Swipe",
}


def _units(ts):
    """Three players (1 writes the log) and two hostiles: Reef Guardian, a
    boss, and Sail Ripper."""
    return [
        f'{ts},UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
        f'{ts},UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
        f'{ts},UNIT_ADDED,3,PLAYER,F,3,0,F,1,7,"Tank Friend","@tank",1003,50,1800,0,PLAYER_ALLY,T',
        f'{ts},UNIT_ADDED,70,MONSTER,F,0,{BOSS_ID},T,0,0,"Reef Guardian","",0,50,160,0,HOSTILE,F',
        f'{ts},UNIT_ADDED,71,MONSTER,F,0,{MOB_ID},F,0,0,"Sail Ripper","",0,50,160,0,HOSTILE,F',
    ]


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    *_units(2000),
    *[f'2600,ABILITY_INFO,{ability_id},"{name}","/esoui/art/icons/x.dds",F,F'
      for ability_id, name in ABILITIES.items()],
]


def _p(unit_id, health=20000):
    return f"{unit_id},{health}/20000,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _m(unit_id, health=1000000, max_health=1000000):
    return f"{unit_id},{health}/{max_health},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _pet(unit_id):
    return f"{unit_id},45478/45478,0/0,0/0,0/0,0/0,0,0.3,0.4,1.0"


def _ev(ts, result, value, cast, ability, source, target="*"):
    return f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{value},0,{cast},{ability},{source},{target}"


def _hit(ts, player, cast=0, ability=LA, value=1000, target=70, result="DAMAGE"):
    return _ev(ts, result, value, cast, ability, _p(player), _m(target))


def _taunt(ts, player, cast, target=70):
    return _ev(ts, "TAUNTED", 0, cast, TAUNT, _p(player), _m(target))


def _cast(ts, cast, ability, source, target="*"):
    return f"{ts},BEGIN_CAST,0,F,{cast},{ability},{source},{target}"


def _player_cast(ts, player, cast, ability, target=70, target_health=1000000):
    return _cast(ts, cast, ability, _p(player), _m(target, target_health))


def _monster_cast(ts, monster, cast, ability, player, monster_health=1000000):
    return _cast(ts, cast, ability, _m(monster, monster_health), _p(player))


def _monster_hit(ts, monster, player, result="DAMAGE", ability=SHOCK, cast=0, value=500):
    return _ev(ts, result, value, cast, ability, _m(monster), _p(player))


def _died(ts, monster):
    return _ev(ts, "DIED_XP", 0, 0, 0, _p(1), _m(monster, 0))


def _monster_added(ts, unit_id, name, monster_id=MOB_ID, owner=0, reaction="HOSTILE"):
    return (f'{ts},UNIT_ADDED,{unit_id},MONSTER,F,0,{monster_id},F,0,0,"{name}","",'
            f'0,50,160,{owner},{reaction},F')


def _unit_changed(ts, unit_id, name, owner, reaction):
    return f'{ts},UNIT_CHANGED,{unit_id},0,0,"{name}","",0,50,160,{owner},{reaction},F'


def _fights(*lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.track_buff_timeline = False
    for line in BASE + list(lines):
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer.fight_history.fights


def _fight(*lines):
    return _fights(*lines)[-1]


def _in_fight(*acts, pre=(), start=10000, end=20000):
    """One fight: *pre* before its BEGIN_COMBAT, *acts* during it."""
    return _fight(*pre, f"{start},BEGIN_COMBAT", *acts, f"{end},END_COMBAT")


class TestTheMemoryBeforeTheLine(unittest.TestCase):
    """BEGIN_COMBAT is the logging player's line: a group member's hit
    often lands a moment before it."""

    def test_a_hit_14_ms_before_the_line_opens_a_zones_first_fight(self):
        opener = _in_fight(_hit(10100, 1, result="DOT_TICK"), pre=[_hit(9986, 2)]).opener
        self.assertEqual((opener["name"], opener["kind"], opener["time_ms"]), ("@templar", "hit", -14))
        self.assertEqual((opener["target"], opener["ability"]), ("Reef Guardian", "Light Attack (Ice)"))

    def test_and_any_later_fight(self):
        fights = _fights("3000,BEGIN_COMBAT", _hit(3500, 1), "4000,END_COMBAT",
                         _hit(9986, 2), "10000,BEGIN_COMBAT", _hit(10100, 1), "20000,END_COMBAT")
        self.assertEqual(len(fights), 2)
        self.assertEqual((fights[1].opener["name"], fights[1].opener["time_ms"]), ("@templar", -14))

    def test_the_memory_holds_ten_seconds(self):
        dropped = _in_fight(_hit(15500, 3), pre=[_hit(4000, 2, target=71)], start=15000, end=25000)
        self.assertEqual(dropped.opener["name"], "@tank")
        kept = _in_fight(_hit(15500, 3), pre=[_hit(7000, 2, target=71)], start=15000, end=25000)
        self.assertEqual((kept.opener["name"], kept.opener["time_ms"], kept.opener["edge"]),
                         ("@templar", -8000, False))
        self.assertEqual(OPENER_WINDOW_MS, 10000)

    def test_nothing_before_the_last_end_combat_counts(self):
        fights = _fights("3000,BEGIN_COMBAT", _hit(7900, 2), "8000,END_COMBAT",
                         "10000,BEGIN_COMBAT", _hit(10500, 3), "20000,END_COMBAT")
        self.assertEqual([f.opener["name"] for f in fights], ["@templar", "@tank"])

    def test_a_zone_change_clears_the_memory(self):
        fight = _fight(_hit(9000, 2), '9500,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
                       *_units(9600), "10000,BEGIN_COMBAT", _hit(10500, 3), "20000,END_COMBAT")
        self.assertEqual(fight.opener["name"], "@tank")

    def test_end_combats_millisecond(self):
        """Before the END_COMBAT line it is the fight's; after it, the next
        fight's memory, at its edge (200 ms after the line that began it)."""
        fights = _fights("10000,BEGIN_COMBAT", _hit(20000, 2), "20000,END_COMBAT", _hit(20000, 3),
                         "25000,BEGIN_COMBAT", "30000,END_COMBAT")
        self.assertEqual((fights[0].opener["name"], fights[0].opener["time_ms"]), ("@templar", 10000))
        second = fights[1].opener
        self.assertEqual((second["name"], second["time_ms"], second["edge"]), ("@tank", -5000, True))

    def test_an_empty_fight_has_neither_record(self):
        fight = _in_fight()
        self.assertIsNone(fight.opener)
        self.assertIsNone(fight.monster_first)

    def test_the_lines_millisecond_goes_to_the_new_fight_when_the_last_never_ended(self):
        """A BEGIN_COMBAT with no END_COMBAT before it (never in the 9,571 of
        the survey): the last fight closes, and the acts written in the new
        line's millisecond, before it, open the new one."""
        fights = _fights("3000,BEGIN_COMBAT", _player_cast(9900, 3, 6001, INNER_RAGE),
                         _hit(10000, 3, 6001, INNER_RAGE), _taunt(10000, 3, 6001),
                         "10000,BEGIN_COMBAT", "20000,END_COMBAT")
        opener = fights[-1].opener
        self.assertEqual((opener["kind"], opener["name"], opener["time_ms"]), ("taunt", "@tank", 0))


class TestTaunts(unittest.TestCase):
    CAST = (_player_cast(9900, 3, 6001, INNER_RAGE),)

    def test_a_hit_and_its_taunted_in_the_lines_millisecond_are_one_taunt(self):
        for order in (
                [_hit(10000, 3, 6001, INNER_RAGE), _taunt(10000, 3, 6001), "10000,BEGIN_COMBAT"],
                [_hit(10000, 3, 6001, INNER_RAGE), "10000,BEGIN_COMBAT", _taunt(10000, 3, 6001)],
                ["10000,BEGIN_COMBAT", _hit(10000, 3, 6001, INNER_RAGE), _taunt(10000, 3, 6001)]):
            opener = _fight(*self.CAST, *order, "20000,END_COMBAT").opener
            self.assertEqual((opener["kind"], opener["name"], opener["time_ms"], opener["ability"]),
                             ("taunt", "@tank", 0, "Inner Rage"), order)

    def test_a_taunted_a_millisecond_after_its_hit(self):
        opener = _in_fight(_hit(10500, 3, 6001, INNER_RAGE), _taunt(10501, 3, 6001), _hit(11000, 1),
                           pre=self.CAST).opener
        self.assertEqual((opener["kind"], opener["target"]), ("taunt", "Reef Guardian"))

    def test_not_six_ms_later_nor_another_players(self):
        late = _in_fight(_hit(10500, 3, 6001, INNER_RAGE), _taunt(10506, 3, 6001), pre=self.CAST)
        self.assertEqual(late.opener["kind"], "hit")
        other = _in_fight(_hit(10500, 3, 6001, INNER_RAGE), _taunt(10500, 2, 6002), pre=self.CAST)
        self.assertEqual((other.opener["kind"], other.opener["name"]), ("hit", "@tank"))

    def test_a_taunt_whose_hit_did_no_damage_opens_by_itself(self):
        opener = _in_fight(_hit(10500, 1), pre=[
            _player_cast(9000, 3, 7001, GOADING), _hit(9500, 3, 7001, GOADING, value=0),
            _taunt(9500, 3, 7001)]).opener
        self.assertEqual((opener["kind"], opener["name"], opener["ability"], opener["time_ms"]),
                         ("taunt", "@tank", "Goading Throw", -500))

    def test_a_taunt_the_log_ties_to_no_cast_is_named_by_nothing(self):
        opener = _in_fight(_taunt(10500, 3, 7101)).opener
        self.assertEqual((opener["kind"], opener["ability"]), ("taunt", ""))

    def test_a_taunt_on_a_unit_that_is_not_hostile_never_opens(self):
        fight = _in_fight(_taunt(10200, 3, 7201, target=73), _hit(10500, 1),
                          pre=[_monster_added(3000, 73, "Ghost", reaction="FRIENDLY")])
        self.assertEqual(fight.opener["name"], "@brainsnorkel")


class TestNaming(unittest.TestCase):

    def test_cast_id_0_names_the_hit_alone(self):
        opener = _in_fight(_hit(10500, 1, cast=0)).opener
        self.assertEqual((opener["ability"], opener["skill"]), ("Light Attack (Ice)", ""))

    def test_a_hit_under_another_skill_keeps_both(self):
        opener = _in_fight(_player_cast(10400, 1, 8001, SUSCEPTIBILITY),
                           _hit(10500, 1, 8001, CONCUSSION)).opener
        self.assertEqual((opener["ability"], opener["skill"]),
                         ("Concussion", "Elemental Susceptibility"))

    def test_a_tick_under_its_casts_name_has_no_from(self):
        """Another id than its cast's, the same name: compared by name."""
        opener = _in_fight(_player_cast(10400, 2, 8101, CALTROPS),
                           _hit(10900, 2, 8101, CALTROPS_TICK, result="DOT_TICK")).opener
        self.assertEqual((opener["ability"], opener["skill"]), ("Razor Caltrops", ""))

    def test_a_skill_known_only_from_a_hit_is_not_used(self):
        fights = _fights("3000,BEGIN_COMBAT", _hit(3500, 1, 8201, CONCUSSION), "4000,END_COMBAT",
                         "10000,BEGIN_COMBAT", _hit(10500, 1, 8201, SUNDERED), "20000,END_COMBAT")
        self.assertEqual((fights[1].opener["ability"], fights[1].opener["skill"]), ("Sundered", ""))


class TestShieldAbsorbs(unittest.TestCase):
    """A DAMAGE_SHIELDED line names the enemy's shield; the attack follows
    with the same cast id, source, target and millisecond."""

    def test_named_by_its_attack_whatever_that_carries(self):
        for rest in (0, 1200):
            opener = _in_fight(
                _player_cast(10400, 1, 9001, SUSCEPTIBILITY, target=71),
                _ev(10500, "DAMAGE_SHIELDED", 3000, 9001, WICKED_BONDS, _p(1), _m(71)),
                _ev(10500, "DAMAGE", rest, 9001, CONCUSSION, _p(1), _m(71))).opener
            self.assertEqual((opener["ability"], opener["skill"], opener["target"]),
                             ("Concussion", "Elemental Susceptibility", "Sail Ripper"), rest)

    def test_unpaired_by_its_cast_or_nothing_never_by_the_shield(self):
        opener = _in_fight(_player_cast(10400, 1, 9101, SUSCEPTIBILITY, target=71),
                           _ev(10500, "DAMAGE_SHIELDED", 3000, 9101, WICKED_BONDS, _p(1), _m(71))).opener
        self.assertEqual((opener["ability"], opener["skill"]), ("Elemental Susceptibility", ""))
        bare = _in_fight(_ev(10500, "DAMAGE_SHIELDED", 3000, 9201, WICKED_BONDS, _p(1), _m(71)))
        self.assertEqual(bare.opener["ability"], "")


class TestWhoIsCredited(unittest.TestCase):

    def test_a_pet_credits_its_owner_and_is_named(self):
        opener = _in_fight(_ev(10500, "DAMAGE", 2000, 0, SWIPE, _pet(90), _m(70)), pre=[
            _monster_added(3000, 90, "Wild Guardian", owner=2, reaction="NPC_ALLY")]).opener
        self.assertEqual((opener["via"], opener["unit_id"], opener["owner_id"], opener["name"],
                          opener["pet"], opener["ability"]),
                         ("pet", "2", "2", "@templar", "Wild Guardian", "Crushing Swipe"))

    def test_a_unit_nobody_owns_never_counts(self):
        fight = _in_fight(_ev(10200, "DAMAGE", 2000, 0, SWIPE, _pet(91), _m(70)), _hit(10500, 1),
                          pre=[_monster_added(3000, 91, "Stray", reaction="FRIENDLY")])
        self.assertEqual(fight.opener["name"], "@brainsnorkel")

    def test_a_friendly_unit_counts_once_it_turns_hostile(self):
        fight = _in_fight(_hit(10200, 2, target=73), _unit_changed(10300, 73, "Ghost", 0, "HOSTILE"),
                          _hit(10400, 3, target=73),
                          pre=[_monster_added(3000, 73, "Ghost", reaction="FRIENDLY")])
        self.assertEqual((fight.opener["name"], fight.opener["time_ms"]), ("@tank", 400))


class TestTheMemorysEdge(unittest.TestCase):
    """Where nobody can be called first: just after the line that began
    the memory, or in the 10 s window's oldest second."""

    def test_in_the_windows_oldest_second(self):
        opener = _in_fight(_hit(20500, 1), pre=[_hit(10500, 3)], start=20000, end=30000).opener
        self.assertEqual((opener["time_ms"], opener["edge"]), (-9500, True))

    def test_not_four_seconds_before_the_line_and_six_after_end_combat(self):
        fights = _fights("3000,BEGIN_COMBAT", _hit(3500, 1), "4000,END_COMBAT",
                         _hit(10000, 3), "14000,BEGIN_COMBAT", "20000,END_COMBAT")
        self.assertEqual((fights[1].opener["time_ms"], fights[1].opener["edge"]), (-4000, False))


class TestDeadEnemies(unittest.TestCase):
    """Rule 5: what was aimed at, or came from, an enemy that died before
    the line belonged to the last pack."""

    def test_a_hit_on_an_enemy_dead_before_the_line_is_dropped(self):
        fight = _in_fight(_hit(10500, 3), pre=[_hit(9000, 2, target=71), _died(9500, 71)])
        self.assertEqual(fight.opener["name"], "@tank")

    def test_so_is_a_monsters_act_whose_source_died(self):
        fight = _in_fight(_hit(10500, 3), pre=[_monster_cast(9000, 71, 9301, SHOCK, 2), _died(9500, 71)])
        self.assertIsNone(fight.monster_first)


class TestMonsterFirst(unittest.TestCase):

    def test_a_hostiles_cast_at_a_player_before_any_hit(self):
        fight = _in_fight(_monster_cast(10200, 71, 9401, SHOCK, 2), _hit(10500, 3))
        monster, opener = fight.monster_first, fight.opener
        self.assertEqual((monster["name"], monster["action"], monster["target_kind"],
                          monster["target_name"], monster["time_ms"], monster["in_flight"]),
                         ("Sail Ripper", "Shock", "player", "@templar", 200, None))
        self.assertEqual((opener["name"], opener["time_ms"], opener["edge"]), ("@tank", 500, False))

    def test_the_margin_is_100_ms(self):
        self.assertIsNone(_in_fight(_monster_cast(10450, 71, 9402, SHOCK, 2), _hit(10500, 3)).monster_first)
        self.assertIsNotNone(_in_fight(_monster_cast(10400, 71, 9403, SHOCK, 2),
                                       _hit(10500, 3)).monster_first)

    def test_before_the_line_its_time_is_negative(self):
        fight = _in_fight(_hit(10500, 3), pre=[_monster_cast(9800, 71, 9404, SHOCK, 2)])
        self.assertEqual(fight.monster_first["time_ms"], -200)

    def test_nobody_answered(self):
        fight = _in_fight(_monster_hit(10200, 71, 3, result="SNARED"))
        self.assertIsNone(fight.opener)
        self.assertEqual(fight.monster_first["action"], "Shock")

    def test_a_monster_going_for_a_pet(self):
        monster = _in_fight(_cast(10200, 9501, SHOCK, _m(71), _pet(90)), _hit(10500, 3), pre=[
            _monster_added(3000, 90, "Wild Guardian", owner=2, reaction="NPC_ALLY")]).monster_first
        self.assertEqual((monster["target_kind"], monster["target_name"], monster["target_pet"]),
                         ("pet", "@templar", "Wild Guardian"))


class TestNoiseIsNeverTheMonstersOpening(unittest.TestCase):

    def _first(self, *acts, pre=()):
        return _in_fight(*acts, _hit(15000, 3), pre=pre).monster_first

    def test_a_dead_monster_a_hazard_a_tick_and_a_listed_mechanic(self):
        self.assertIsNone(self._first(_monster_cast(10200, 71, 9601, SHOCK, 2, monster_health=0)))
        self.assertIsNone(self._first(_monster_hit(10200, 72, 2, ability=BARRIER),
                                      pre=[_monster_added(3000, 72, "Scorching Barrier")]))
        self.assertIsNone(self._first(_monster_hit(10200, 71, 2, result="DOT_TICK")))
        self.assertIsNone(self._first(_monster_cast(10200, 74, 9602, SHOCK, 2),
                                      pre=[_monster_added(3000, 74, "Arcane Knot", KNOT_ID)]))
        self.assertIsNone(self._first(_monster_cast(10200, 71, 9603, LOOK_AT, 2)))

    def test_a_cast_at_three_players_at_once_but_not_two(self):
        fan = [_monster_cast(10200, 71, 9700 + p, SHOCK, p) for p in (1, 2, 3)]
        self.assertIsNone(self._first(*fan))
        self.assertIsNotNone(self._first(*fan[:2]))

    def test_a_released_pet_a_self_cast_and_results_that_are_no_act(self):
        released = [_monster_added(3000, 90, "Wild Guardian", owner=2, reaction="NPC_ALLY"),
                    _unit_changed(9000, 90, "Wild Guardian", 0, "HOSTILE")]
        self.assertIsNone(self._first(_monster_hit(10200, 90, 1), pre=released))
        self.assertIsNone(self._first(_cast(10200, 9801, SHOCK, _m(71))))
        for result in ("DIED", "ABILITY_ON_COOLDOWN"):
            self.assertIsNone(self._first(_monster_hit(10200, 71, 2, result=result)), result)

    def test_nor_is_a_released_pet_the_enemy_a_player_hit(self):
        released = [_monster_added(3000, 90, "Blighted Blastbones", owner=2, reaction="NPC_ALLY"),
                    _unit_changed(9000, 90, "Blighted Blastbones", 0, "HOSTILE")]
        fight = _in_fight(_hit(10200, 3, target=90), _hit(10500, 1), pre=released)
        self.assertEqual((fight.opener["name"], fight.opener["target"]), ("@brainsnorkel", "Reef Guardian"))


class TestACastAlreadyInFlight(unittest.TestCase):

    def test_a_players_cast_begun_before_the_monster_acted(self):
        for pre, acts in (
                ([], [_player_cast(10100, 1, 9901, INNER_RAGE), _monster_cast(10300, 71, 9902, SHOCK, 2)]),
                ([_player_cast(9500, 1, 9901, INNER_RAGE), _monster_cast(9800, 71, 9902, SHOCK, 2)], [])):
            fight = _in_fight(*acts, _hit(10900, 1, 9901, INNER_RAGE), pre=pre)
            flight = fight.monster_first["in_flight"]
            self.assertEqual((flight["name"], flight["skill"], flight["via"]),
                             ("@brainsnorkel", "Inner Rage", "player"))

    def test_not_one_at_a_dead_monster(self):
        fight = _in_fight(_player_cast(10100, 1, 9903, INNER_RAGE, target=71, target_health=0),
                          _monster_cast(10300, 70, 9904, SHOCK, 2), _hit(10900, 1))
        self.assertIsNone(fight.monster_first["in_flight"])


# -- the line --------------------------------------------------------------------

def _row(unit_id, name, role="D", cls="NB", is_local=False, character=""):
    return {"unit_id": unit_id, "name": name, "role": role, "class_abbr": cls,
            "is_local": is_local, "character": character or name, "dps": 1000.0, "boss_dps": 0.0,
            "dmg_pct": 30.0, "boss_pct": 0.0, "h": 20000, "m": 30000, "s": 15000, "sets": [],
            "all_sets": [], "skill_lines": [], "class_lines": [], "front_bar": [], "back_bar": [],
            "front_bar_slots": [], "back_bar_slots": []}


ROWS = [_row("1", "@brainsnorkel", "D", "Arcanist", True, "Coworker"),
        _row("2", "@templar", "H", "Templar", character="Templar Friend"),
        _row("3", "@tank", "T", "DK", character="Tank Friend"),
        _row("5", "anon", "T", "DK"), _row("6", "anon", "D", "NB")]


def _entry(opener=None, monster=None, zone="Dreadsail Reef", rows=ROWS):
    entry = FightHistoryEntry()
    entry.zone_name = zone
    entry.boss_name = "Reef Guardian"
    entry.timestamp = "2026-09-02 22:24:05"
    entry.duration_s = 60.0
    entry.players = rows
    entry.player_names = [{"name": r["name"], "character": r["character"],
                           "is_local": r["is_local"]} for r in rows]
    entry.opener, entry.monster_first = opener, monster
    return entry


def _opener(name="@tank", owner="3", kind="hit", ability="Light Attack (Ice)", skill="",
            target="Sail Ripper", time_ms=0, edge=False, via="player", pet="", unit_id=None):
    return {"kind": kind, "unit_id": unit_id or owner, "via": via, "owner_id": owner, "name": name,
            "pet": pet, "ability": ability, "ability_id": "1", "skill": skill,
            "skill_id": "2" if skill else "", "target": target, "target_id": "71",
            "time_ms": time_ms, "edge": edge}


def _monster(name="Reclaimer", action="Shock", target_name="@templar", target_id="2",
             target_kind="player", target_pet="", time_ms=2000, edge=False, in_flight=None):
    return {"unit_id": "71", "name": name, "action": action, "action_id": "500",
            "target_kind": target_kind, "target_id": target_id, "target_row": target_id,
            "target_name": target_name, "target_pet": target_pet, "in_flight": in_flight,
            "time_ms": time_ms, "edge": edge}


def _lines(entry, names=None):
    from gui.fight_render import opener_text
    from gui.name_mask import NO_MASK
    return opener_text(opener_parts(entry), names or NO_MASK)


class TestTheLine(unittest.TestCase):
    """One line per case of the issue's table."""

    def test_a_player_hit_or_taunted_first(self):
        self.assertEqual(_lines(_entry(_opener())), ["@tank hit Sail Ripper first: Light Attack (Ice)"])
        self.assertEqual(_lines(_entry(_opener(kind="taunt", ability="Inner Rage", target="Reef Guardian"))),
                         ["@tank taunted Reef Guardian first: Inner Rage"])

    def test_the_skill_when_its_name_differs(self):
        self.assertEqual(
            _lines(_entry(_opener(ability="Concussion", skill="Elemental Susceptibility",
                                  target="Bow Breaker"))),
            ["@tank hit Bow Breaker first: Concussion, from Elemental Susceptibility"])

    def test_a_pet_and_a_companion_are_named_from_their_owner(self):
        pet = _opener(name="@templar", owner="2", via="pet", pet="Wild Guardian",
                      ability="Crushing Swipe", target="Darkcaster Skirmisher")
        self.assertEqual(_lines(_entry(pet)),
                         ["@templar's Wild Guardian hit Darkcaster Skirmisher first: Crushing Swipe"])
        companion = _opener(name="@brainsnorkel", owner="1", via="companion", unit_id="c1-106616",
                            ability="Light Attack", target="Dreadhorn Scrapper")
        self.assertEqual(_lines(_entry(companion)),
                         ["@brainsnorkel's Companion hit Dreadhorn Scrapper first: Light Attack"])

    def test_a_pet_whose_name_carries_a_handle(self):
        """A unit the engine does not know as a companion, named by the game
        "@handle's Companion", reads as its owner's Companion; any other pet
        name goes through the mask like a player's."""
        named = _opener(name="@templar", owner="2", via="pet", pet="@templar's Companion")
        self.assertEqual(_lines(_entry(named)), ["@templar's Companion hit Sail Ripper first: Light Attack (Ice)"])
        parts = opener_parts(_entry(_opener(name="@templar", owner="2", via="pet", pet="Wild Guardian")))
        self.assertIn(PlayerName("Wild Guardian"), parts[0])

    def test_a_monster_first_opening_is_two_lines(self):
        entry = _entry(_opener(name="@brainsnorkel", owner="1", ability="Burning",
                               target="Tazkad the Packmaster", time_ms=201),
                       _monster("Murkwater Durzog", "Rend", "@brainsnorkel", "1", time_ms=38))
        self.assertEqual(_lines(entry), [
            "Murkwater Durzog went for @brainsnorkel first (Rend), before any hit or taunt",
            "@brainsnorkel hit Tazkad the Packmaster first: Burning"])

    def test_times(self):
        before = _entry(_opener(target="Draugr Feral-Fiend", time_ms=-857),
                        _monster("Draugr Thrall", "Pound", "@tank", "3", time_ms=-2874))
        self.assertEqual(_lines(before), [
            ("Draugr Thrall went for @tank first (Pound), before any hit or taunt, "
             "2.9 s before the fight's start"),
            "@tank hit Draugr Feral-Fiend first: Light Attack (Ice), 2.0 s later"])
        slow = _entry(_opener(name="@dps", owner="1", ability="Light Attack (Dual Wield)",
                              target="Reducer", time_ms=7879), _monster(time_ms=2034))
        self.assertEqual(_lines(slow), [
            "Reclaimer went for @templar first (Shock), before any hit or taunt, 2.0 s into the fight",
            "@dps hit Reducer first: Light Attack (Dual Wield), 5.8 s later"])

    def test_the_time_rule_starts_at_1050_ms_and_never_says_into_an_arena_fight(self):
        self.assertEqual(TIME_SHOWN_MS, 1050)
        self.assertEqual(_lines(_entry(_opener(time_ms=1049))),
                         ["@tank hit Sail Ripper first: Light Attack (Ice)"])
        self.assertEqual(_lines(_entry(_opener(time_ms=1050))),
                         ["@tank hit Sail Ripper first: Light Attack (Ice), 1.1 s into the fight"])
        self.assertEqual(_lines(_entry(_opener(time_ms=-1050))),
                         ["@tank hit Sail Ripper first: Light Attack (Ice), 1.1 s before the fight's start"])
        self.assertIn("Infinite Archive", ARENA_ZONES)
        self.assertEqual(_lines(_entry(_opener(time_ms=2400), zone="Infinite Archive")),
                         ["@tank hit Sail Ripper first: Light Attack (Ice)"])
        self.assertEqual(_lines(_entry(_opener(time_ms=-2400), zone="Infinite Archive")),
                         ["@tank hit Sail Ripper first: Light Attack (Ice), 2.4 s before the fight's start"])
        # By zone id, whatever the client's language calls it
        german = _entry(_opener(time_ms=2400), zone="Unendliches Archiv")
        german.zone_id = "1436"
        self.assertEqual(_lines(german), ["@tank hit Sail Ripper first: Light Attack (Ice)"])

    def test_seconds_round_half_up(self):
        self.assertEqual([seconds_text(ms) for ms in (1050, 1149, 1150, -2874, 5845)],
                         ["1.1", "1.1", "1.2", "2.9", "5.8"])
        self.assertEqual(time_text(0, False), "")

    def test_a_cast_already_on_its_way(self):
        flight = {"via": "player", "unit_id": "3", "owner_id": "3", "name": "@tank", "pet": "",
                  "skill": "Inner Rage", "skill_id": "200"}
        entry = _entry(_opener(kind="taunt", ability="Inner Rage", target="Dreadsail Keelcutter",
                               time_ms=1398),
                       _monster("Harpy Windcaller", "Talon", "@tank", "3", time_ms=1065, in_flight=flight))
        self.assertEqual(_lines(entry), [
            ("Harpy Windcaller went for @tank (Talon), with @tank's Inner Rage already on its way, "
             "1.1 s into the fight"),
            "@tank taunted Dreadsail Keelcutter first: Inner Rage"])

    def test_a_monster_going_for_a_pet_in_an_arena(self):
        entry = _entry(None, _monster("Dremora Conduit", "Shock", "@brainsnorkel", "1", "pet",
                                      "Wild Guardian", time_ms=3120), zone="Infinite Archive")
        self.assertEqual(_lines(entry), [
            "Dremora Conduit went for @brainsnorkel's Wild Guardian first (Shock), before any hit or taunt"])
        # A target unit named with a handle reads as its owner's Companion
        handle = _entry(None, _monster("Dremora Conduit", "Shock", "@templar", "2", "pet",
                                       "@templar's Companion", time_ms=300))
        self.assertEqual(_lines(handle), [
            "Dremora Conduit went for @templar's Companion first (Shock), before any hit or taunt"])

    def test_nobody_answered(self):
        self.assertEqual(_lines(_entry(None, _monster("Strangler", "Spit", "@tank", "3", time_ms=2006))),
                         ["Strangler went for @tank first (Spit), before any hit or taunt, 2.0 s into the fight"])

    def test_at_the_memorys_edge_nobody_is_first(self):
        edge = _entry(_opener(kind="taunt", ability="Goading Throw", target="Yokeda Kai",
                              time_ms=-4377, edge=True))
        self.assertEqual(_lines(edge), ["@tank was already fighting Yokeda Kai (Goading Throw) when the fight began"])
        monster = _entry(_opener(time_ms=-4377), _monster("Yokeda Kai", "Flare", "@tank", "3",
                                                          time_ms=-4377 - 200, edge=True))
        self.assertEqual(_lines(monster), ["Yokeda Kai was already fighting @tank (Flare) when the fight began"])

    def test_a_name_that_picks_out_no_row_gets_its_role_and_class(self):
        anon = _opener(name="anon", owner="5", kind="taunt", ability="Goading Throw", target="Reef Guardian")
        self.assertEqual(_lines(_entry(anon)), ["anon (T, DK) taunted Reef Guardian first: Goading Throw"])
        # A player without a row gets none
        self.assertEqual(_lines(_entry(_opener(name="anon", owner="9"))),
                         ["anon hit Sail Ripper first: Light Attack (Ice)"])

    def test_an_entry_without_the_records_has_no_line(self):
        self.assertEqual(opener_parts(_entry()), [])
        self.assertEqual(opener_parts(object()), [])
        parts = opener_parts(_entry(_opener()))
        self.assertIsInstance(parts[0][0], PlayerName)


class TestThePane(unittest.TestCase):

    def test_under_the_table_before_also_died_muted_with_no_links(self):
        from gui.fight_render import render_html, render_plain_text
        entry = _entry(_opener(time_ms=11))
        entry.death_recaps = [{"unit_id": "77", "name": "@passerby", "time_ms": 1000, "killer": "x",
                               "ability": "y", "ability_id": "9", "icon": "", "max_health": 1, "events": []}]
        entry.deaths = 1
        for detailed in (False, True):
            html = render_html(entry, detailed=detailed)
            line = html.index("@tank hit Sail Ripper first: Light Attack (Ice)")
            self.assertLess(html.index("</table>"), line)
            self.assertLess(line, html.index("Also died"))
            paragraph = html[html.rindex("<p", 0, line):html.index("</p>", line)]
            self.assertNotIn("<a ", paragraph)
            self.assertNotIn("font-size", paragraph)
            self.assertNotIn("<b>*</b>", html)
        text = render_plain_text(entry)
        self.assertTrue(text.endswith("\n@tank hit Sail Ripper first: Light Attack (Ice)"))

    def test_two_lines_are_one_paragraph(self):
        from gui.fight_render import render_html
        entry = _entry(_opener(), _monster())
        html = render_html(entry, detailed=False)
        self.assertIn("before any hit or taunt, 2.0 s into the fight<br>@tank hit", html)


class TestHideNames(unittest.TestCase):
    """Every player's name in the line goes through the mask; a hidden one
    is followed by its row's role and class."""

    def _mask(self, entry):
        from gui.name_mask import NameMask
        return NameMask.for_entry(entry, True)

    def test_another_players_handle_is_hidden_and_the_logging_players_kept(self):
        entry = _entry(_opener(name="@templar", owner="2", ability="Inner Rage", kind="taunt",
                               target="Reef Guardian"))
        self.assertEqual(_lines(entry, self._mask(entry)),
                         ["@▒▒▒▒▒▒▒ (H, Templar) taunted Reef Guardian first: Inner Rage"])
        own = _entry(_opener(name="@brainsnorkel", owner="1"))
        self.assertEqual(_lines(own, self._mask(own)),
                         ["@brainsnorkel hit Sail Ripper first: Light Attack (Ice)"])

    def test_a_companion_is_named_from_its_hidden_owner(self):
        entry = _entry(_opener(name="@templar", owner="2", via="companion", unit_id="c2-106616",
                               target="Reef Guardian"),
                       _monster(target_name="@templar", target_id="2", target_kind="companion"))
        lines = _lines(entry, self._mask(entry))
        self.assertTrue(all("@templar" not in line and line.count("Companion") == 1 for line in lines), lines)
        self.assertEqual(lines[1], "@▒▒▒▒▒▒▒ (H, Templar)'s Companion hit Reef Guardian first: Light Attack (Ice)")
        plain = _lines(entry)
        self.assertEqual(plain[1].count("@templar"), 1)
        anon = _entry(_opener(name="anon", owner="5", via="companion", unit_id="c5-106616"))
        self.assertEqual(_lines(anon, self._mask(anon)),
                         ["anon (T, DK)'s Companion hit Sail Ripper first: Light Attack (Ice)"])

    def test_a_hidden_player_without_a_handle_and_the_pane(self):
        from gui.fight_render import render_html, render_plain_text
        rows = ROWS + [_row("8", "Nameless One", "H", "Necro")]
        entry = _entry(_opener(name="Nameless One", owner="8"), rows=rows)
        mask = self._mask(entry)
        self.assertEqual(_lines(entry, mask), ["▒" * len("Nameless One")
                                               + " (H, Necro) hit Sail Ripper first: Light Attack (Ice)"])
        html = render_html(entry, detailed=False, names=mask)
        self.assertNotIn("Nameless One hit", html)
        self.assertIn("(H, Necro) hit Sail Ripper first", html)
        self.assertIn("mask:", html[html.index("(H, Necro) hit") - 300:html.index("(H, Necro) hit")])
        self.assertNotIn("Nameless One", render_plain_text(entry, names=mask).splitlines()[-1])


if __name__ == "__main__":
    unittest.main()
