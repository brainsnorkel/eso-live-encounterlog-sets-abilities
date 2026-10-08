#!/usr/bin/env python3
"""Group buff uptimes count a buff on whoever it lands on, not only on the
player who applied it (issue #11).

An EFFECT_CHANGED line carries two unit states of ten fields each. The
target's starts at field 14 and is "*" when the target is the source. The
engine used to take the target id from field 10, the source's shield value,
so a buff one player put on another was never seen.
"""

import unittest

from engine_events import RecordingListener
from esolog_tail import BUFF_ABILITY_IDS, ESOLogAnalyzer, FightHistory

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
COURAGE = BUFF_ABILITY_IDS['major_courage']
FORCE = BUFF_ABILITY_IDS['major_force']
DEBUFF = 12345


def _player(unit_id, health=20000, shield=0):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,{shield},0.2,0.5,5.5")


def _boss(health, unit_id=70):
    return f"{unit_id},{health}/{BOSS_HEALTH},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _effect(ts, change, ability, source, target=None):
    """An EFFECT_CHANGED line; *target* None writes the self-target '*'."""
    return (f"{ts},EFFECT_CHANGED,{change},1,900,{ability},{source},"
            f"{target if target is not None else '*'}")


def _hit(ts, player, damage, boss_health_after):
    return (f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{damage},0,900,{DEBUFF},"
            f"{_player(player)},{_boss(boss_health_after)}")


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,2,7,"Third Wheel","@third",1003,50,1800,0,PLAYER_ALLY,T',
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F',
    f'2600,ABILITY_INFO,{DEBUFF},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
]

# A twenty-second fight: player 1 deals a quarter of the damage, player 2
# the rest
FIGHT_START = [
    '10000,BEGIN_COMBAT',
    *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2, 3)],
]
FIGHT_END = [
    _hit(28000, 1, 100000, 900000),
    _hit(29000, 2, 300000, 600000),
    '30000,END_COMBAT',
]


def _run(lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer


class TestBuffOnAnotherPlayer(unittest.TestCase):

    def test_a_buff_cast_on_another_player_counts(self):
        # Player 1 gives player 2 Major Courage for half the fight
        analyzer = _run(FIGHT_START + [
            _effect(12000, 'GAINED', COURAGE, _player(1), _player(2)),
            _effect(22000, 'FADED', COURAGE, _player(1), _player(2)),
        ] + FIGHT_END)
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.buff_summary, 'MCourage:50%')
        # It is on player 2, not on the player who cast it
        enc = analyzer.current_encounter
        self.assertEqual(enc.player_buffs['2']['MCourage'], [(12000, 22000)])
        self.assertNotIn('MCourage', enc.player_buffs['1'])

    def test_a_buff_cast_before_the_pull_on_another_player_carries_in(self):
        analyzer = _run([
            _effect(5000, 'GAINED', COURAGE, _player(1), _player(2)),
        ] + FIGHT_START + FIGHT_END)
        self.assertEqual(analyzer.fight_history.fights[0].buff_summary, 'MCourage:100%')

    def test_uptime_is_the_time_the_buff_was_on_anyone(self):
        # Major Force on player 2 for 10-20 s and on player 3 for 15-25 s:
        # fifteen of the twenty seconds
        analyzer = _run(FIGHT_START + [
            _effect(10000, 'GAINED', FORCE, _player(1), _player(2)),
            _effect(15000, 'GAINED', FORCE, _player(1), _player(3)),
            _effect(20000, 'FADED', FORCE, _player(1), _player(2)),
            _effect(25000, 'FADED', FORCE, _player(1), _player(3)),
        ] + FIGHT_END)
        self.assertEqual(analyzer.fight_history.fights[0].buff_summary, 'MForce:75%')

    def test_the_sources_shield_is_not_read_as_the_target(self):
        # The source's shield value sits where the target id used to be read.
        # A shield of 3 must not put the buff on player 3
        analyzer = _run(FIGHT_START + [
            _effect(10000, 'GAINED', COURAGE, _player(1, shield=3), _player(2)),
        ] + FIGHT_END)
        enc = analyzer.current_encounter
        self.assertEqual(analyzer.fight_history.fights[0].buff_summary, 'MCourage:100%')
        self.assertIn('MCourage', enc.player_buffs['2'])
        self.assertNotIn('MCourage', enc.player_buffs['3'])


class TestOtherReadersOfTheTarget(unittest.TestCase):

    def test_a_debuff_on_the_boss_reads_the_boss_health_not_the_casters(self):
        analyzer = _run(FIGHT_START + [
            _effect(12000, 'GAINED', DEBUFF, _player(1), _boss(500000)),
        ] + FIGHT_END)
        boss = analyzer.current_encounter.enemies['70']
        self.assertEqual((boss.current_health, boss.max_health), (500000, BOSS_HEALTH))

    def test_an_enemys_own_effect_still_reads_its_health(self):
        analyzer = _run(FIGHT_START + [
            _effect(12000, 'GAINED', DEBUFF, _boss(250000)),
        ] + FIGHT_END)
        boss = analyzer.current_encounter.enemies['70']
        self.assertEqual((boss.current_health, boss.max_health), (250000, BOSS_HEALTH))

    def test_buffing_another_player_does_not_move_damage_between_them(self):
        analyzer = _run(FIGHT_START + [
            _effect(12000, 'GAINED', COURAGE, _player(1), _player(2)),
            _effect(12000, 'GAINED', COURAGE, _player(2), _player(1)),
        ] + FIGHT_END)
        fight = analyzer.fight_history.fights[0]
        dps = {p['unit_id']: p['dps'] for p in fight.players}
        self.assertEqual(dps, {'1': 5000.0, '2': 15000.0, '3': 0.0})
        enc = analyzer.current_encounter
        self.assertEqual(enc.find_player_by_unit_id('1').unit_id, '1')
        self.assertEqual(enc.find_player_by_unit_id('2').unit_id, '2')
        self.assertEqual(enc.pet_ownership, {})


if __name__ == '__main__':
    unittest.main()
