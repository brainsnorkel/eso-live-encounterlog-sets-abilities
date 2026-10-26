#!/usr/bin/env python3
"""Dps time and the damage record (damage_stats): every dps figure divides
by the span of the hits it sums, first hit to last and a second at least,
as in Combat Metrics, not by the fight time; and each player's breakdown by
ability and by target for the damage window. The lines have the shape of
Chris's trial logs (see test_boss_dps).
"""

import unittest

from damage_stats import AbilityDamage, Window, dps, dps_time_s
from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
ADD_HEALTH = 50000
PET_HEALTH = 45478
JABS = 26792
WALL = 28549
BLASTBONES = 117691


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _monster(unit_id, health, max_health):
    return f"{unit_id},{health}/{max_health},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _boss(health=900000):
    return _monster(70, health, BOSS_HEALTH)


def _add(health=40000):
    return _monster(71, health, ADD_HEALTH)


def _pet(unit_id=90):
    return _monster(unit_id, PET_HEALTH, PET_HEALTH)


def _hit(ts, source, damage, target, result='DAMAGE', ability=JABS):
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{damage},0,900,{ability},"
            f"{source},{target}")


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,6,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,5,1,"Necro Friend","@necro",1002,50,2547,0,PLAYER_ALLY,T',
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F',
    f'2500,UNIT_ADDED,71,MONSTER,F,0,{ADD_HEALTH},F,0,0,"Lesser Sea Adder","",0,50,160,0,HOSTILE,F',
    # Player 1's pet, summoned before the pull
    f'3000,UNIT_ADDED,90,MONSTER,F,0,{PET_HEALTH},F,0,0,"Blighted Blastbones","",0,50,160,1,NPC_ALLY,F',
    f'2600,ABILITY_INFO,{JABS},"Biting Jabs","/esoui/art/icons/ability_templar_reckless_attacks.dds",F,F',
    f'2600,ABILITY_INFO,{WALL},"Wall of Elements","/esoui/art/icons/ability_destructionstaff_002a.dds",F,F',
    f'2600,ABILITY_INFO,{BLASTBONES},"Blighted Blastbones","/esoui/art/icons/ability_necromancer_002_b.dds",F,F',
    '10000,BEGIN_COMBAT',
    *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[{JABS}],[{JABS}]' for unit in (1, 2)],
]
FIGHT_END = ['70000,END_COMBAT']  # a sixty-second fight


def _fight(lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines + FIGHT_END:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer.fight_history.fights[0]


def _by_unit(fight):
    return {p['unit_id']: p for p in fight.players}


class TestDpsTime(unittest.TestCase):

    def test_dps_divides_by_the_span_of_the_hits(self):
        fight = _fight([
            _hit(20000, _player(1), 100000, _boss()),
            _hit(40000, _player(1), 100000, _boss(800000)),
        ])
        p1 = _by_unit(fight)['1']
        # 200,000 over the 20 s between the hits, not over the 60 s fight
        self.assertEqual(p1['dps'], 10000.0)
        self.assertEqual(p1['boss_dps'], 10000.0)
        self.assertEqual(fight.group_dps, 10000.0)
        self.assertEqual(fight.group_boss_dps, 10000.0)
        self.assertEqual(fight.dps_time_s, 20.0)
        self.assertEqual(fight.boss_dps_time_s, 20.0)
        # The fight time stays the fight time
        self.assertEqual(fight.duration_s, 60.0)

    def test_a_lone_hit_reads_as_its_value_per_second(self):
        fight = _fight([_hit(30000, _player(1), 5000, _boss())])
        self.assertEqual(_by_unit(fight)['1']['dps'], 5000.0)
        self.assertEqual(fight.group_dps, 5000.0)
        self.assertEqual(fight.dps_time_s, 0.0)  # the span; the figure uses the floor

    def test_each_player_has_their_own_dps_time(self):
        fight = _fight([
            _hit(20000, _player(1), 100000, _boss()),
            _hit(30000, _player(2), 50000, _boss(850000)),
            _hit(40000, _player(1), 100000, _boss(750000)),
        ])
        by_unit = _by_unit(fight)
        self.assertEqual(by_unit['1']['dps'], 10000.0)
        self.assertEqual(by_unit['2']['dps'], 50000.0)  # one hit
        self.assertEqual(fight.group_dps, 250000 / 20)
        self.assertEqual(by_unit['1']['dmg_pct'], 80.0)
        self.assertEqual(by_unit['2']['dmg_pct'], 20.0)
        self.assertEqual(by_unit['1']['boss_pct'], 80.0)
        self.assertEqual(by_unit['2']['boss_pct'], 20.0)

    def test_boss_dps_time_is_the_span_of_the_hits_on_the_bosses(self):
        fight = _fight([
            _hit(11000, _player(1), 10000, _add()),
            _hit(30000, _player(1), 100000, _boss()),
            _hit(40000, _player(1), 100000, _boss(800000)),
            _hit(60000, _player(1), 10000, _add(30000)),
        ])
        p1 = _by_unit(fight)['1']
        self.assertAlmostEqual(p1['dps'], 220000 / 49)
        self.assertEqual(p1['boss_dps'], 20000.0)
        self.assertEqual(p1['boss_pct'], 100.0)
        self.assertEqual(fight.boss_dps_time_s, 10.0)
        self.assertEqual(fight.group_boss_dps, 20000.0)

    def test_a_player_without_damage_has_an_empty_record(self):
        fight = _fight([_hit(20000, _player(1), 100000, _boss())])
        p2 = _by_unit(fight)['2']
        self.assertEqual((p2['dps'], p2['boss_dps'], p2['dmg_pct'], p2['boss_pct']), (0, 0, 0, 0))
        self.assertEqual(p2['damage']['total'], 0)
        self.assertEqual(p2['damage']['abilities'], [])
        self.assertEqual(p2['damage']['targets'], [])
        self.assertIsNone(p2['damage']['window']['first_ms'])


class TestDamageRecord(unittest.TestCase):

    def _record(self):
        fight = _fight([
            _hit(20000, _player(1), 1000, _boss()),
            _hit(21000, _player(1), 3000, _boss(), 'CRITICAL_DAMAGE'),
            _hit(22000, _player(1), 500, _add(), 'DOT_TICK', ability=WALL),
            _hit(23000, _player(1), 800, _boss(), 'BLOCKED_DAMAGE'),
            _hit(24000, _player(1), 700, _boss(), 'DAMAGE_SHIELDED'),
            _hit(25000, _pet(), 2000, _boss(), ability=BLASTBONES),
        ])
        return fight, _by_unit(fight)['1']['damage']

    def test_totals_and_windows(self):
        fight, damage = self._record()
        self.assertEqual((damage['total'], damage['boss']), (8000, 7500))
        self.assertEqual(damage['window'],
                         {'first_ms': 20000, 'last_ms': 25000, 'span_ms': 5000,
                          'first_s': 10.0, 'last_s': 15.0})
        self.assertEqual(damage['boss_window']['span_ms'], 5000)
        self.assertEqual(_by_unit(fight)['1']['dps'], 8000 / 5)

    def test_rows_by_ability_largest_first(self):
        _fight_, damage = self._record()
        rows = damage['abilities']
        self.assertEqual([(r['name'], r['pet'], r['damage']) for r in rows],
                         [('Biting Jabs', False, 5500), ('Blighted Blastbones', True, 2000),
                          ('Wall of Elements', False, 500)])
        jabs = rows[0]
        # Hits that landed: the normal, the critical and the blocked one; the
        # absorb is damage but not a hit (see damage_stats)
        self.assertEqual((jabs['hits'], jabs['crits'], jabs['blocked'], jabs['shielded'],
                          jabs['ticks'], jabs['max'], jabs['min']),
                         (3, 1, 1, 700, 0, 3000, 800))
        self.assertEqual((jabs['id'], jabs['icon']),
                         (str(JABS), 'ability_templar_reckless_attacks'))
        wall = rows[2]
        self.assertEqual((wall['hits'], wall['ticks'], wall['crits']), (1, 1, 0))

    def test_rows_for_the_bosses_alone(self):
        _fight_, damage = self._record()
        self.assertEqual([(r['name'], r['damage']) for r in damage['boss_abilities']],
                         [('Biting Jabs', 5500), ('Blighted Blastbones', 2000)])

    def test_targets_with_their_own_spans(self):
        _fight_, damage = self._record()
        targets = damage['targets']
        # The boss took four hits and one absorb (damage, not a hit)
        self.assertEqual([(t['name'], t['boss'], t['damage'], t['hits']) for t in targets],
                         [('Tideborn Taleria', True, 7500, 4), ('Lesser Sea Adder', False, 500, 1)])
        self.assertEqual((targets[0]['first_ms'], targets[0]['last_ms'], targets[0]['span_ms']),
                         (20000, 25000, 5000))
        self.assertEqual(targets[1]['span_ms'], 0)


class TestDamageStatsUnits(unittest.TestCase):

    def test_dps_time_has_a_floor_of_a_second(self):
        self.assertEqual(dps_time_s(0), 1.0)
        self.assertEqual(dps_time_s(400), 1.0)
        self.assertEqual(dps_time_s(2500), 2.5)
        self.assertEqual(dps(0, 5000), 0.0)
        self.assertEqual(dps(3000, 0), 3000.0)
        self.assertEqual(dps(3000, 500), 3000.0)
        self.assertEqual(dps(3000, 1500), 2000.0)
        self.assertEqual(dps(3000, 2000), 1500.0)

    def test_window_keeps_the_extremes_whatever_the_order(self):
        window = Window()
        self.assertEqual(window.span_ms, 0)
        for ts in (5000, 2000, 9000):
            window.note(ts)
        self.assertEqual((window.first_ms, window.last_ms, window.span_ms), (2000, 9000, 7000))
        self.assertEqual(window.as_dict(1000)['first_s'], 1.0)

    def test_ability_row_counts(self):
        row = AbilityDamage('1', False)
        row.note(100, 'DAMAGE')
        row.note(300, 'DOT_TICK_CRITICAL')
        row.note(50, 'DAMAGE_SHIELDED')
        self.assertEqual((row.damage, row.hits, row.crits, row.ticks, row.shielded,
                          row.max_hit, row.min_hit), (450, 2, 1, 1, 50, 300, 100))


def _cast_hit(ts, source, damage, target, cast, ability, result='DAMAGE', damage_type='PHYSICAL'):
    """A hit with its own cast id and damage type (the kinds of damage)."""
    return (f"{ts},COMBAT_EVENT,{result},{damage_type},1,{damage},0,{cast},{ability},"
            f"{source},{target}")


class TestKindsOfDamageDealt(unittest.TestCase):
    """The record's kinds (damage_kinds): area or single target by the cast
    and the bundled table of player skills, direct or over time, Martial or
    Magical, the types, and the shield absorbs outside the splits."""

    def test_kinds_by_cast_table_and_type(self):
        fight = _fight([
            # Impulse on the lone boss: area by the table (28800 is Area)
            _cast_hit(11000, _player(1), 10000, _boss(), 1, 28800, damage_type='FIRE'),
            # Crystal Fragments: single target by the table (46324 is Enemy)
            _cast_hit(12000, _player(1), 5000, _boss(), 2, 46324, damage_type='MAGIC'),
            # An ability the table lacks, one cast on the boss and then the
            # add: area by the cast, the first hit moved over
            _cast_hit(13000, _player(1), 3000, _boss(), 3, 555555),
            _cast_hit(13000, _player(1), 3000, _add(), 3, 555555),
            # A tick of an unknown ability on the boss alone: single
            _cast_hit(14000, _player(1), 2000, _boss(), 4, 666666, result='DOT_TICK',
                      damage_type='POISON'),
            # A shield absorb: damage, but outside the splits
            _cast_hit(15000, _player(1), 1000, _boss(), 5, 777777, result='DAMAGE_SHIELDED',
                      damage_type='GENERIC'),
        ])
        damage = _by_unit(fight)['1']['damage']
        self.assertEqual(damage['total'], 24000)
        kinds = damage['kinds']
        self.assertEqual(kinds['total'], 23000)
        self.assertEqual((kinds['direct'], kinds['dot']), (21000, 2000))
        self.assertEqual((kinds['area'], kinds['single']), (16000, 7000))
        self.assertEqual((kinds['martial'], kinds['magical'], kinds['oblivion'], kinds['other']),
                         (8000, 15000, 0, 0))
        self.assertEqual(kinds['types'],
                         {'fire': 10000, 'magic': 5000, 'physical': 6000, 'poison': 2000})
        self.assertEqual(kinds['rules'], {'table': 15000, 'cast': 6000, 'none': 2000})
        self.assertEqual(kinds['shielded'], 1000)
        rows = {row['id']: row for row in damage['abilities']}
        self.assertEqual((rows['28800']['area_damage'], rows['28800']['types']),
                         (10000, {'fire': 10000}))
        self.assertEqual((rows['555555']['area_damage'], rows['555555']['damage']), (6000, 6000))
        self.assertEqual((rows['666666']['tick_damage'], rows['666666']['area_damage']), (2000, 0))
        self.assertEqual(rows['46324']['area_damage'], 0)
        # The boss view's rows carry the same kinds
        boss_rows = {row['id']: row for row in damage['boss_abilities']}
        self.assertEqual(boss_rows['555555']['area_damage'], 3000)

    def test_a_record_without_kinds_still_snapshots(self):
        from damage_stats import PlayerDamage
        record = PlayerDamage()
        record.note(1000, 500, 'DAMAGE', '1', False, '70', True)
        snapshot = record.snapshot(lambda a: 'x', lambda a: '', lambda u: 'Boss')
        self.assertEqual(snapshot['kinds']['total'], 500)
        self.assertEqual(snapshot['kinds']['types'], {'untyped': 500})
        self.assertEqual(snapshot['kinds']['rules'], {'none': 500})


if __name__ == '__main__':
    unittest.main()
