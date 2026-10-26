#!/usr/bin/env python3
"""Units that carry the game's boss flag without being the fight's boss
(issue #67, boss_units): the Defense Prisms and Baron Rize of Xoryn's
gauntlet, the Sea Adders of Yandir's fight. Read once on UNIT_ADDED, so the
boss dps time, the boss shares, the boss-scoped rules, the penetration
targets and the Armour row all leave them out. Lines have the shape of
Chris's trial logs (see test_boss_dps, test_tracked_effects_engine).
"""

import unittest

from boss_units import BOSS_FLAG_ADDS, is_fight_boss
from effect_rules import EffectTracker, parse_rules
from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory

EPOCH = 1759600000000
ABILITY = 12345
TAUNT, BREACH = "38254", "61743"
PRISM, BARON, XORYN, ADDER, YANDIR = "121566", "122557", "121170", "96308", "94771"


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _unit(unit_id, health):
    return f"{unit_id},{health}/{health},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _hit(ts, player, damage, unit, health):
    return (f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{damage},0,900,{ABILITY},"
            f"{_player(player)},{_unit(unit, health)}")


def _effect(ts, change, ability, player, unit, health):
    """*player* applies *ability* to *unit*: the line carries both unit states."""
    return (f"{ts},EFFECT_CHANGED,{change},1,900,{ability},{_player(player)},"
            f"{_unit(unit, health)}")


def _mob(ts, unit, monster_id, name, boss, health):
    # Field four after the unit id is the game's monster id, field five its
    # boss flag
    return (f'{ts},UNIT_ADDED,{unit},MONSTER,F,0,{monster_id},{boss},0,0,"{name}","",'
            f'0,50,160,0,HOSTILE,F')


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1478,"Lucent Citadel",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    f'2600,ABILITY_INFO,{ABILITY},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
]
FIGHT_START = [
    '10000,BEGIN_COMBAT',
    *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2)],
]
RULES = "Taunt = 38254 on boss each\nBreach = 61743 on boss\n"


def _run(lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    parsed, errors = parse_rules(RULES)
    assert not errors, errors
    analyzer.effect_tracker = EffectTracker(parsed)
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer


class TestTheList(unittest.TestCase):

    def test_a_flagged_unit_is_a_boss_unless_listed(self):
        self.assertTrue(is_fight_boss(True, XORYN))
        self.assertTrue(is_fight_boss(True, 121170))
        self.assertFalse(is_fight_boss(False, XORYN))
        for monster_id in BOSS_FLAG_ADDS:
            self.assertFalse(is_fight_boss(True, monster_id))
        self.assertFalse(is_fight_boss(True, int(PRISM)))
        # A flagged unit with no monster id to read stays what the flag says
        self.assertTrue(is_fight_boss(True, None))

    def test_the_list_names_the_prisms_the_baron_and_the_adders(self):
        self.assertEqual({BOSS_FLAG_ADDS[m] for m in ("121566", "122810", "122811", "122812")},
                         {"Defense Prism"})
        self.assertEqual(BOSS_FLAG_ADDS[BARON], "Baron Rize")
        self.assertEqual(BOSS_FLAG_ADDS[ADDER], "Sea Adder")


class TestXorynsGauntlet(unittest.TestCase):
    """The Prisms and the Baron, hit first, are adds; Xoryn, added late,
    is the fight's one boss."""

    def setUp(self):
        self.analyzer = _run([
            _mob(9000, 80, PRISM, "Defense Prism", "T", 2910773),
            _mob(9000, 81, BARON, "Baron Rize", "T", 13971720),
        ] + FIGHT_START + [
            _effect(10500, "GAINED", TAUNT, 2, 80, 2910773),  # the Prism is taunted
            _hit(11000, 1, 100000, 80, 2910773),
            _hit(12000, 2, 100000, 80, 2910773),
            _hit(20000, 1, 300000, 81, 13971720),
            _hit(22000, 2, 100000, 81, 13971720),
            _mob(40000, 82, XORYN, "Xoryn", "T", 69858576),
            _effect(41000, "GAINED", TAUNT, 2, 82, 69858576),  # Xoryn is taunted
            _effect(41000, "GAINED", BREACH, 1, 82, 69858576),
            _hit(41000, 1, 500000, 82, 69858576),
            _hit(45000, 2, 500000, 82, 69858576),
            _hit(51000, 1, 200000, 82, 69858576),
            '52000,END_COMBAT',
        ])
        self.fight = self.analyzer.fight_history.fights[0]

    def test_the_units_kinds(self):
        enc = self.analyzer.current_encounter
        self.assertEqual([(enc.enemies[u].boss_flag, enc.enemies[u].is_boss, enc.enemies[u].monster_id)
                          for u in ("80", "81", "82")],
                         [(True, False, PRISM), (True, False, BARON), (True, True, XORYN)])
        units = enc.fight_units()
        self.assertEqual((units["80"][0], units["81"][0], units["82"][0]), ("enemy", "enemy", "boss"))
        self.assertEqual(self.analyzer._unit_kind("80"), "enemy")
        self.assertEqual(self.analyzer._unit_kind("82"), "boss")

    def test_boss_dps_time_and_shares_are_xoryns_alone(self):
        fight = self.fight
        # The group's hits span 40 s, its hits on Xoryn 10 s
        self.assertAlmostEqual(fight.dps_time_s, 40.0)
        self.assertAlmostEqual(fight.boss_dps_time_s, 10.0)
        self.assertAlmostEqual(fight.group_dps, 1800000 / 40)
        self.assertAlmostEqual(fight.group_boss_dps, 1200000 / 10)
        by_unit = {p["unit_id"]: p for p in fight.players}
        # Player 1: 700,000 of the 1,200,000 on Xoryn, over their own 10 s
        self.assertAlmostEqual(by_unit["1"]["boss_pct"], 700000 / 1200000 * 100)
        self.assertAlmostEqual(by_unit["1"]["boss_dps"], 700000 / 10)
        self.assertAlmostEqual(by_unit["2"]["boss_pct"], 500000 / 1200000 * 100)
        self.assertAlmostEqual(by_unit["2"]["boss_dps"], 500000.0)  # one hit: a second
        self.assertEqual(by_unit["1"]["damage"]["boss"], 700000)
        targets = {t["unit_id"]: t["boss"] for t in by_unit["1"]["damage"]["targets"]}
        self.assertEqual(targets, {"80": False, "81": False, "82": True})
        self.assertEqual(fight.boss_name, "Xoryn")

    def test_boss_rules_and_penetration_measure_xoryn_alone(self):
        items = {item["name"]: item for item in self.fight.tracked}
        # The taunt's ``each``: Xoryn from 41 s to the end (11 s of the 12 s
        # he was there), the taunted Prism not counted
        self.assertEqual(items["Taunt"]["units"], "boss")
        self.assertEqual({iv["target"] for iv in items["Taunt"]["intervals"]}, {"Xoryn"})
        self.assertAlmostEqual(items["Taunt"]["uptime_pct"], 100.0 * 11 / 12, places=0)
        self.assertEqual({iv["target"] for iv in items["Breach"]["intervals"]}, {"Xoryn"})
        pen = self.fight.pen_crit
        self.assertEqual((pen["on"], pen["targets"]), ("boss", 1))
        self.assertEqual(pen["damage"], 1200000)  # the histograms weigh Xoryn's seconds alone
        self.assertEqual(pen["armour"]["target"], "Xoryn")
        self.assertTrue(pen["armour"]["boss"])
        # Hits at 41, 45 and 51 s: the gaps of four and five seconds are bridged
        self.assertEqual(pen["armour"]["window"], [[31000, 42000]])


class TestAWipeBeforeXoryn(unittest.TestCase):

    def test_a_fight_on_the_prisms_and_the_baron_has_no_boss(self):
        analyzer = _run([
            _mob(9000, 80, PRISM, "Defense Prism", "T", 2910773),
            _mob(9000, 81, BARON, "Baron Rize", "T", 13971720),
        ] + FIGHT_START + [
            _hit(11000, 1, 100000, 80, 2910773),
            _hit(20000, 1, 300000, 81, 13971720),
            _hit(22000, 2, 100000, 81, 13971720),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.group_boss_dps, 0)
        self.assertEqual(fight.boss_dps_time_s, 0)
        self.assertEqual(fight.boss_name, "Baron Rize")  # the most damaged hostile
        # Boss rules fall back to the pack, as in any fight without a boss
        items = {item["name"]: item for item in fight.tracked}
        self.assertEqual(items["Taunt"]["units"], "mobs")
        self.assertEqual(fight.pen_crit["on"], "enemies")


class TestYandirsAdders(unittest.TestCase):

    def test_sea_adders_are_not_yandirs_boss_damage(self):
        analyzer = _run([
            _mob(9000, 70, YANDIR, "Yandir the Butcher", "T", 58215500),
            _mob(9000, 71, ADDER, "Sea Adder", "T", 4657240),
        ] + FIGHT_START + [
            _effect(10500, "GAINED", TAUNT, 2, 70, 58215500),
            _hit(11000, 1, 900000, 70, 58215500),
            _hit(12000, 2, 100000, 71, 4657240),  # the adder
            _hit(13000, 1, 100000, 70, 58215500),
            '20000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertAlmostEqual(fight.group_boss_dps, 1000000 / 2)
        by_unit = {p["unit_id"]: p for p in fight.players}
        self.assertAlmostEqual(by_unit["1"]["boss_pct"], 100.0)
        self.assertAlmostEqual(by_unit["2"]["boss_pct"], 0.0)
        items = {item["name"]: item for item in fight.tracked}
        # ``each`` over Yandir alone: taunted from 10.5 s to the end of 10 s
        self.assertAlmostEqual(items["Taunt"]["uptime_pct"], 95.0)
        self.assertEqual({iv["target"] for iv in items["Taunt"]["intervals"]}, {"Yandir the Butcher"})


if __name__ == '__main__':
    unittest.main()
