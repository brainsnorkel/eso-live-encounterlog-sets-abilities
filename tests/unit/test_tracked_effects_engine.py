#!/usr/bin/env python3
"""Tracked effects through the whole engine (issue #10): rules measured on
the units the log describes, and shown on the uptime line."""

import unittest

from effect_rules import DEFAULT_RULES, EffectTracker, parse_rules
from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
MOB_HEALTH = 50000
ABILITY = 12345
OB_A, OB_B, CRUX, COURAGE, TAUNT = "45902", "62988", "184220", "109966", "38254"


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _unit(unit_id, health=BOSS_HEALTH):
    return f"{unit_id},{health}/{health},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _effect(ts, change, ability, source, target=None, stacks=1):
    return (f"{ts},EFFECT_CHANGED,{change},{stacks},900,{ability},{source},"
            f"{target if target is not None else '*'}")


def _hit(ts, player, damage, boss_health_after):
    return (f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{damage},0,900,{ABILITY},"
            f"{_player(player)},{_unit(70, BOSS_HEALTH)}")


def _hit_unit(ts, player, unit, health=MOB_HEALTH):
    return (f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,900,{ABILITY},"
            f"{_player(player)},{_unit(unit, health)}")


def _died(ts, unit, health=MOB_HEALTH):
    """The unit's death: DIED_XP with the dying unit as the target state."""
    return (f"{ts},COMBAT_EVENT,DIED_XP,PHYSICAL,0,0,0,900,{ABILITY},"
            f"{_player(1)},{unit},0/{health},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3")


def _mob(ts, unit, name, boss="F", health=MOB_HEALTH):
    return f'{ts},UNIT_ADDED,{unit},MONSTER,F,0,{health},{boss},0,0,"{name}","",0,50,160,0,HOSTILE,F'


def _builds(ts, *players):
    return [f'{ts},PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in players]


# Player 1 writes the log (isLocalPlayer T); 70 is a boss, 71 a mob, 90 a pet
BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F',
    '2500,UNIT_ADDED,71,MONSTER,F,0,50000,F,0,0,"Dreadsail Deckhand","",0,50,160,0,HOSTILE,F',
    '2500,UNIT_ADDED,90,MONSTER,F,0,45478,F,0,0,"Blighted Blastbones","",0,50,160,1,NPC_ALLY,F',
    f'2600,ABILITY_INFO,{ABILITY},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
]
FIGHT_START = [
    '10000,BEGIN_COMBAT',
    *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2)],
]
FIGHT_END = [_hit(29000, 1, 100000, 900000), '30000,END_COMBAT']  # a 20 s fight

RULES = """\
OB = 45902 62988 on boss
Crux = 184220 on self stacks
Courage on pets = 109966 on pets
Everyone = 109966 on group
"""


def _run(lines, rules=RULES):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    parsed, errors = parse_rules(rules)
    assert not errors, errors
    analyzer.effect_tracker = EffectTracker(parsed)
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer


def _items(fight):
    return {item["name"]: item for item in fight.tracked}


class TestTrackedEffectsInTheEngine(unittest.TestCase):

    def test_off_balance_on_the_boss_is_the_union_of_its_ids(self):
        analyzer = _run(FIGHT_START + [
            _effect(12000, 'GAINED', OB_A, _player(1), _unit(70)),
            _effect(14000, 'GAINED', OB_B, _player(2), _unit(70)),
            _effect(16000, 'FADED', OB_A, _player(1), _unit(70)),
            _effect(18000, 'FADED', OB_B, _player(2), _unit(70)),
            # The same on a mob does not count for a boss rule
            _effect(20000, 'GAINED', OB_A, _player(1), _unit(71, 50000)),
        ] + FIGHT_END)
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(_items(fight)["OB"]["uptime_pct"], 30.0)
        self.assertIn("OB:30%", fight.buff_summary)

    def test_crux_stacks_on_the_player_who_writes_the_log(self):
        analyzer = _run(FIGHT_START + [
            _effect(10000, 'GAINED', CRUX, _player(1), stacks=1),
            _effect(15000, 'UPDATED', CRUX, _player(1), stacks=2),
            _effect(20000, 'UPDATED', CRUX, _player(1), stacks=3),
            _effect(25000, 'FADED', CRUX, _player(1), stacks=0),
            # Player 2's Crux is not "self"
            _effect(10000, 'GAINED', CRUX, _player(2), stacks=3),
        ] + FIGHT_END)
        fight = analyzer.fight_history.fights[0]
        crux = _items(fight)["Crux"]
        self.assertEqual((crux["avg_stacks"], crux["max_stacks"], crux["uptime_pct"]), (2.0, 3, 75.0))
        self.assertTrue(fight.buff_summary.endswith("Crux:2.0/3 Courage on pets:0% Everyone:0%"),
                        fight.buff_summary)

    def test_a_buff_on_a_pet_counts_for_pets_and_a_player_for_group(self):
        analyzer = _run(FIGHT_START + [
            _effect(10000, 'GAINED', COURAGE, _player(1), _unit(90, 45478)),
            _effect(20000, 'FADED', COURAGE, _player(1), _unit(90, 45478)),
            _effect(10000, 'GAINED', COURAGE, _player(1), _player(2)),
            _effect(15000, 'FADED', COURAGE, _player(1), _player(2)),
        ] + FIGHT_END)
        items = _items(analyzer.fight_history.fights[0])
        self.assertEqual(items["Courage on pets"]["uptime_pct"], 50.0)
        self.assertEqual(items["Everyone"]["uptime_pct"], 25.0)

    def test_an_effect_from_before_the_pull_counts_from_the_start(self):
        analyzer = _run([
            _effect(5000, 'GAINED', OB_A, _player(1), _unit(70)),
        ] + FIGHT_START + [
            _effect(15000, 'FADED', OB_A, _player(1), _unit(70)),
        ] + FIGHT_END)
        self.assertEqual(_items(analyzer.fight_history.fights[0])["OB"]["uptime_pct"], 25.0)

    def test_two_players_still_get_the_tracked_items(self):
        # Fewer than three players: no built-in group buffs, but the rules
        analyzer = _run(FIGHT_START + FIGHT_END)
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.buff_summary, "OB:0% Crux:0 Courage on pets:0% Everyone:0%")

    def test_no_rules_means_nothing_tracked(self):
        analyzer = _run(FIGHT_START + [
            _effect(12000, 'GAINED', OB_A, _player(1), _unit(70)),
        ] + FIGHT_END, rules="")
        fight = analyzer.fight_history.fights[0]
        self.assertEqual((fight.tracked, fight.buff_summary), ([], ""))

    def test_the_default_rules_are_the_whole_uptime_line(self):
        # The group buffs and the taunt are rules like the rest: a group of
        # two gets them too, and one never seen reads 0%
        analyzer = _run(FIGHT_START + [
            _effect(10000, 'GAINED', COURAGE, _player(1), _player(2)),
            _effect(20000, 'FADED', COURAGE, _player(1), _player(2)),
            _effect(10000, 'GAINED', TAUNT, _player(1), _unit(70)),
            _effect(22000, 'FADED', TAUNT, _player(1), _unit(70)),
        ] + FIGHT_END, rules=DEFAULT_RULES)
        self.assertEqual(
            analyzer.fight_history.fights[0].buff_summary,
            "Major Courage:50% Major Force:0% Major Slayer:0% Powerful Assault:0% "
            "Lucent Echoes:0% Pearlescent Ward:0% Taunt:60% Off-Balance:0% Touch of Z'en:0 "
            "Crux:0 Morag Tong:0% Minor Brittle:0% Major Brittle:0% Alkosh:0%")


class TestFightsWithoutABoss(unittest.TestCase):
    """A trash pack: a boss rule measures the mobs the group fought and says
    how many it reached; a mob's death ends the effects on it."""

    def test_a_boss_rule_measures_the_pack_and_counts_the_mobs(self):
        # Two deckhands hit and no boss: Off-Balance on one for 6 s, on the
        # other for 2 s inside that
        analyzer = _run(FIGHT_START + [
            _mob(10500, 72, "Dreadsail Sailor"),
            _hit_unit(11000, 1, 71), _hit_unit(11000, 2, 72),
            _effect(12000, 'GAINED', OB_A, _player(1), _unit(71, MOB_HEALTH)),
            _effect(14000, 'GAINED', OB_A, _player(2), _unit(72, MOB_HEALTH)),
            _effect(16000, 'FADED', OB_A, _player(2), _unit(72, MOB_HEALTH)),
            _effect(18000, 'FADED', OB_A, _player(1), _unit(71, MOB_HEALTH)),
            '30000,END_COMBAT',
        ])
        items = _items(analyzer.fight_history.fights[0])
        self.assertEqual((items["OB"]["text"], items["OB"]["units"]), ("OB:30% on 2 of 2 mobs", "mobs"))
        self.assertEqual((items["OB"]["mobs_reached"], items["OB"]["mobs"]), (2, 2))
        self.assertEqual(sorted(iv["target"] for iv in items["OB"]["intervals"]),
                         ["Dreadsail Deckhand", "Dreadsail Sailor"])
        # A group rule is unchanged by the fight having no boss
        self.assertEqual(items["Everyone"]["text"], "Everyone:0%")

    def test_a_dead_mobs_effect_ends_at_its_death_and_stays_out_of_the_next_pull(self):
        analyzer = _run(FIGHT_START + [
            _mob(10500, 72, "Dreadsail Sailor"),
            _hit_unit(11000, 1, 71),
            _effect(12000, 'GAINED', OB_A, _player(1), _unit(71, MOB_HEALTH)),
            _died(16000, 71),  # and no FADED line for its Off-Balance
            '30000,END_COMBAT',
            # The next pull in the zone, against the sailor
            '40000,BEGIN_COMBAT', *_builds(40001, 1, 2),
            _hit_unit(41000, 1, 72),
            '50000,END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        self.assertEqual(_items(first)["OB"]["text"], "OB:20% on 1 of 1 mobs")
        # Reached nothing: no count after the 0, though the pack is known
        self.assertEqual((_items(second)["OB"]["text"], _items(second)["OB"]["mobs"]), ("OB:0%", 1))

    def test_each_averages_the_bosses(self):
        analyzer = _run(FIGHT_START + [
            _mob(10500, 72, "Second Boss", boss="T", health=BOSS_HEALTH),
            _hit_unit(11000, 2, 72, BOSS_HEALTH),
            _effect(10000, 'GAINED', TAUNT, _player(1), _unit(70)),  # 70 taunted throughout
        ] + FIGHT_END, rules="Taunt = 38254 on boss each\nAny boss = 38254 on boss\n")
        items = _items(analyzer.fight_history.fights[0])
        self.assertEqual(items["Taunt"]["text"], "Taunt:50%")
        self.assertEqual(items["Any boss"]["text"], "Any boss:100%")


if __name__ == '__main__':
    unittest.main()
