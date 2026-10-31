#!/usr/bin/env python3
"""Kill or wipe and time dead from the engine (issues #168 and #169): a
synthetic log of three players and a boss, through the analyzer."""

import unittest

from esolog_tail import ESOLogAnalyzer, FightHistory

EPOCH = 1755729685851
BOSS_MAX = 287485

_PLAYER = "22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"
_DEAD = "0/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _boss(health):
    return f"{health}/{BOSS_MAX},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _hit(ts, player, boss_health, hit=1000):
    return (f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,0,{hit},0,{ts},12437,"
            f"{player},{_PLAYER},70,{_boss(boss_health)}")


def _died(ts, player, boss_health=BOSS_MAX // 2):
    """The boss killed *player*; the line carries the boss's state too."""
    return (f"{ts},COMBAT_EVENT,DIED,PHYSICAL,0,0,0,985157,12437,"
            f"70,{_boss(boss_health)},{player},{_DEAD}")


def _healed(ts, player):
    return (f"{ts},COMBAT_EVENT,HEAL,MAGIC,0,500,0,{ts},22250,"
            f"1,{_PLAYER},{player},{_PLAYER}")


def _boss_died(ts):
    return (f"{ts},COMBAT_EVENT,DIED_XP,PHYSICAL,0,32,0,985855,217348,"
            f"1,{_PLAYER},70,{_boss(0)}")


class TestPullFromTheEngine(unittest.TestCase):

    def _run(self, lines):
        analyzer = ESOLogAnalyzer()
        analyzer.fight_history = FightHistory()
        base = [
            f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
            '1000,ZONE_CHANGED,1196,"Kyne\'s Aegis",VETERAN',
            '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@me",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
            '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1708524619155578000,50,787,0,PLAYER_ALLY,T',
            '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,4,1,"Warden Friend","@warden",1708524619155578001,50,900,0,PLAYER_ALLY,T',
            '2500,UNIT_ADDED,70,MONSTER,F,0,105634,T,0,0,"Lord Falgravn","",0,50,160,0,HOSTILE,F',
        ]
        for line in base + lines:
            entry = analyzer.log_parser.parse_line(line)
            if entry is not None:
                analyzer.process_log_entry(entry)
        return analyzer.fight_history.fights

    def test_the_boss_dying_is_a_kill(self):
        fights = self._run([
            '10000,BEGIN_COMBAT', _hit(11000, 1, BOSS_MAX // 2), _died(12000, 2),
            _boss_died(15000), '16000,END_COMBAT'])
        pull = fights[0].pull
        self.assertEqual(pull["outcome"], "kill")
        self.assertEqual(pull["boss"], "Lord Falgravn")
        self.assertEqual(pull["players"], 3)

    def test_two_of_three_dead_at_the_end_is_a_wipe(self):
        fights = self._run([
            '10000,BEGIN_COMBAT', _hit(11000, 1, BOSS_MAX // 2), _died(12000, 2),
            _died(13000, 3), '20000,END_COMBAT'])
        pull = fights[0].pull
        self.assertEqual(pull["outcome"], "wipe")
        self.assertAlmostEqual(pull["health_left"], 50.0, places=1)
        self.assertEqual(sorted(fights[0].time_dead), ["2", "3"])
        self.assertEqual(fights[0].time_dead["2"], 8000)

    def test_a_player_revived_is_not_dead_at_the_end(self):
        fights = self._run([
            '10000,BEGIN_COMBAT', _hit(11000, 1, BOSS_MAX // 2), _died(12000, 2),
            _died(12100, 3), _healed(15000, 2), _healed(15000, 3), '20000,END_COMBAT'])
        pull = fights[0].pull
        self.assertEqual(pull["outcome"], "left")
        self.assertEqual(pull["dead_at_end"], [])
        self.assertEqual(fights[0].time_dead, {"2": 3000, "3": 2900})

    def test_the_writer_down_at_the_end_is_lost_sight(self):
        fights = self._run([
            '10000,BEGIN_COMBAT', _hit(11000, 1, BOSS_MAX // 2), _died(12000, 1),
            '20000,END_COMBAT'])
        self.assertEqual(fights[0].pull["outcome"], "unseen")

    def test_a_boss_under_two_percent_with_the_group_standing_is_a_kill(self):
        fights = self._run([
            '10000,BEGIN_COMBAT', _hit(11000, 1, BOSS_MAX // 100), '20000,END_COMBAT'])
        self.assertEqual(fights[0].pull["outcome"], "kill")

    def test_a_fight_without_a_boss_has_no_pull(self):
        fights = self._run(['10000,BEGIN_COMBAT', _died(12000, 2), '20000,END_COMBAT'])
        self.assertIsNone(fights[0].pull)
        self.assertEqual(fights[0].time_dead, {"2": 8000})

    def test_a_fight_starting_where_the_last_stopped_carries_it_on(self):
        fights = self._run([
            '10000,BEGIN_COMBAT', _hit(11000, 1, int(BOSS_MAX * 0.60)),
            _died(12000, 1, int(BOSS_MAX * 0.60)), '20000,END_COMBAT', _healed(25000, 1),
            '30000,BEGIN_COMBAT', _hit(31000, 1, int(BOSS_MAX * 0.59)),
            _hit(40000, 1, int(BOSS_MAX * 0.40)), '50000,END_COMBAT'])
        self.assertEqual(len(fights), 2)
        self.assertFalse(fights[0].pull["continues"])
        self.assertTrue(fights[1].pull["continues"])

    def test_a_death_just_after_the_end_turns_the_verdict(self):
        fights = self._run([
            '10000,BEGIN_COMBAT', _hit(11000, 1, BOSS_MAX // 2), _died(12000, 2),
            '20000,END_COMBAT', _died(20050, 3)])
        pull = fights[0].pull
        self.assertEqual(pull["outcome"], "wipe")
        self.assertEqual(pull["dead_at_end"], ["2", "3"])


if __name__ == "__main__":
    unittest.main()
