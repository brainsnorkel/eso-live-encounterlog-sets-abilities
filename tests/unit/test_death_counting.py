#!/usr/bin/env python3
"""Death counting: player deaths come from DIED events, or KILLING_BLOW when
another player lands the blow (not DIED_XP)."""

import unittest

from esolog_tail import ESOLogAnalyzer, FightHistory

EPOCH = 1755729685851

_PLAYER_STATE = "22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"
_DEAD_PLAYER_STATE = "0/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"
_BOSS_STATE = "287485/287485,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"
_DEAD_BOSS_STATE = "0/287485,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _died(ts, killer_id, killer_state, dying_id, dying_state):
    return (f"{ts},COMBAT_EVENT,DIED,PHYSICAL,0,0,0,985157,12437,"
            f"{killer_id},{killer_state},{dying_id},{dying_state}")


def _died_self(ts, unit_id):
    return (f"{ts},COMBAT_EVENT,DIED,PHYSICAL,0,0,0,985157,12437,"
            f"{unit_id},{_DEAD_PLAYER_STATE},*")


def _died_xp(ts, killer_id, dying_id):
    return (f"{ts},COMBAT_EVENT,DIED_XP,PHYSICAL,0,32,0,985855,217348,"
            f"{killer_id},{_PLAYER_STATE},{dying_id},{_DEAD_BOSS_STATE}")


def _killing_blow(ts, killer_id, dying_id):
    return (f"{ts},COMBAT_EVENT,KILLING_BLOW,OBLIVION,0,0,0,5389015,59767,"
            f"{killer_id},{_PLAYER_STATE},{dying_id},{_DEAD_PLAYER_STATE}")


class TestDeathCounting(unittest.TestCase):

    def _run(self, lines):
        analyzer = ESOLogAnalyzer()
        analyzer.fight_history = FightHistory()
        base = [
            f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.11.1"',
            '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
            '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
            '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1708524619155578000,50,787,0,PLAYER_ALLY,T',
            '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
        ]
        for line in base + lines:
            entry = analyzer.log_parser.parse_line(line)
            if entry is not None:
                analyzer.process_log_entry(entry)
        return analyzer

    def test_player_death_via_died_event_counted(self):
        analyzer = self._run([
            '10000,BEGIN_COMBAT',
            _died(15000, 70, _BOSS_STATE, 1, _DEAD_PLAYER_STATE),
            '70000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)
        self.assertEqual(analyzer.zone_deaths, 1)

    def test_self_inflicted_death_star_target_counted(self):
        analyzer = self._run([
            '10000,BEGIN_COMBAT',
            _died_self(15000, 2),
            '70000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)

    def test_player_killed_by_a_player_arrives_as_killing_blow(self):
        """Friendly fire (and PvP) logs KILLING_BLOW and no DIED for the death."""
        analyzer = self._run([
            '10000,BEGIN_COMBAT',
            _killing_blow(15000, 2, 1),
            '70000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)
        self.assertEqual(analyzer.zone_deaths, 1)

    def test_pet_or_npc_death_not_counted(self):
        analyzer = self._run([
            '10000,BEGIN_COMBAT',
            _died(15000, 70, _BOSS_STATE, 55, _DEAD_PLAYER_STATE),  # unit 55: not a player
            '70000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 0)

    def test_enemy_died_xp_not_counted_as_player_death(self):
        analyzer = self._run([
            '10000,BEGIN_COMBAT',
            _died_xp(15000, 1, 70),
            '70000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 0)
        self.assertEqual(analyzer.zone_deaths, 0)

    def test_per_fight_reset_and_zone_accumulation(self):
        analyzer = self._run([
            '10000,BEGIN_COMBAT',
            _died(15000, 70, _BOSS_STATE, 1, _DEAD_PLAYER_STATE),
            _died(16000, 70, _BOSS_STATE, 2, _DEAD_PLAYER_STATE),
            '70000,END_COMBAT',
            '100000,BEGIN_COMBAT',
            _died(110000, 70, _BOSS_STATE, 1, _DEAD_PLAYER_STATE),
            '130000,END_COMBAT',
        ])
        fights = analyzer.fight_history.fights
        self.assertEqual([f.deaths for f in fights], [2, 1])
        self.assertEqual(analyzer.zone_deaths, 3)

    def test_zone_change_resets_counters(self):
        analyzer = self._run([
            '10000,BEGIN_COMBAT',
            _died(15000, 70, _BOSS_STATE, 1, _DEAD_PLAYER_STATE),
            '70000,END_COMBAT',
            '80000,ZONE_CHANGED,57,"Deshaan",NONE',
        ])
        self.assertEqual(analyzer.zone_deaths, 0)
        self.assertEqual(analyzer.fight_deaths, 0)


if __name__ == '__main__':
    unittest.main()
