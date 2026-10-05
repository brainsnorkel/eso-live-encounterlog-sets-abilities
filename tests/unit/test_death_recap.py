#!/usr/bin/env python3
"""Death recaps: the last seconds of damage and healing before each player
death, as the engine hands them to frontends (FightHistoryEntry.death_recaps).

The log shapes exercised here were taken from live trial and arena logs: the
killing blow written after its DIED line, shields written before the hit they
absorbed, and the last player's death written after END_COMBAT.
"""

import unittest

from death_recap import (  # noqa: E402
    KILLING_BLOW_GRACE_MS, RECAP_WINDOW_MS, DeathRecapRecorder,
)
from engine_events import RecordingListener  # noqa: E402
from esolog_tail import LATE_DEATH_GRACE_MS, ESOLogAnalyzer, FightHistory  # noqa: E402

EPOCH = 1755729685851

BOSS = "70,287485/287485,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"
NO_UNIT = "0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000"


def _player(unit_id, health, max_health=20000):
    return (f"{unit_id},{health}/{max_health},26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _event(ts, result, hit, source, target=None, overflow=0, cast=900, ability=12437):
    """A COMBAT_EVENT line; *target* None writes the self-target '*'."""
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{hit},{overflow},{cast},{ability},"
            f"{source},{target if target is not None else '*'}")


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.11.1"',
    '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1708524619155578000,50,787,0,PLAYER_ALLY,T',
    '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
    '2600,ABILITY_INFO,12437,"Toppling Blow","/esoui/art/icons/death_recap_melee_basic.dds",F,T',
    '2600,ABILITY_INFO,40079,"Radiating Regeneration","/esoui/art/icons/ability_restorationstaff_002b.dds",F,F',
    '2600,ABILITY_INFO,555,"Bone Shield","/esoui/art/icons/ability_undaunted_005.dds",F,F',
    '2600,ABILITY_INFO,556,"Hardened Ward","/esoui/art/icons/ability_sorcerer_hardened_ward.dds",F,F',
]


def _run(lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    listener = RecordingListener()
    analyzer.add_listener(listener)
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer, listener


class TestRecapFromTheLog(unittest.TestCase):

    def test_chronology_of_the_last_five_seconds_with_the_killing_blow(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 1000, BOSS, _player(1, 19000)),        # older than 5 s
            _event(15500, 'DAMAGE', 3000, BOSS, _player(1, 17000)),
            _event(16000, 'HEAL', 0, _player(2, 20000), _player(1, 17000),
                   overflow=2000, ability=40079),                           # pure overheal
            _event(17000, 'HEAL', 2500, _player(2, 20000), _player(1, 19500), ability=40079),
            _event(18000, 'DODGED', 0, BOSS, _player(1, 19500)),
            _event(19000, 'BLOCKED_DAMAGE', 4500, BOSS, _player(1, 15000)),
            _event(19500, 'POWER_ENERGIZE', 200, _player(1, 15000)),        # not damage or healing
            _event(20000, 'DIED', 0, BOSS, _player(1, 0), cast=901),
            # The killing blow is logged after the DIED line
            _event(20001, 'DAMAGE', 15000, BOSS, _player(1, 0), overflow=3000, cast=901),
            '70000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.deaths, 1)
        self.assertEqual(len(fight.death_recaps), 1)
        recap = fight.death_recaps[0]
        self.assertEqual(recap['unit_id'], '1')
        self.assertEqual(recap['name'], '@brainsnorkel')
        self.assertEqual(recap['time_ms'], 10000)
        self.assertEqual(recap['killer'], 'Test Boss')
        self.assertEqual(recap['ability'], 'Toppling Blow')
        self.assertEqual(recap['icon'], 'death_recap_melee_basic')
        self.assertEqual(recap['max_health'], 20000)

        rows = recap['events']
        self.assertEqual([r['result'] for r in rows],
                         ['DAMAGE', 'HEAL', 'DODGED', 'BLOCKED_DAMAGE', 'DAMAGE'])
        self.assertEqual([r['kind'] for r in rows],
                         ['damage', 'heal', 'avoided', 'damage', 'damage'])
        self.assertEqual([r['offset_ms'] for r in rows], [-4500, -3000, -2000, -1000, 1])
        self.assertEqual([r['health'] for r in rows], [17000, 19500, 19500, 15000, 0])
        heal = rows[1]
        self.assertEqual((heal['source'], heal['ability'], heal['amount']),
                         ('@templar', 'Radiating Regeneration', 2500))
        self.assertEqual(heal['icon'], 'ability_restorationstaff_002b')
        blow = rows[-1]
        self.assertEqual((blow['source'], blow['ability']), ('Test Boss', 'Toppling Blow'))
        self.assertEqual((blow['amount'], blow['overflow'], blow['max_health']),
                         (15000, 3000, 20000))

    def test_shields_fold_into_the_hit_they_absorbed(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            # A shield nothing follows stays a row of its own
            _event(17000, 'DAMAGE_SHIELDED', 800, BOSS, _player(1, 20000), cast=950, ability=555),
            _event(19000, 'DAMAGE_SHIELDED', 5603, BOSS, _player(1, 20000), cast=900, ability=555),
            _event(19000, 'BLOCKED_DAMAGE', 2102, BOSS, _player(1, 17898), cast=900),
            # Two shields, then the death event, then the hit they soaked
            _event(20000, 'DAMAGE_SHIELDED', 3000, BOSS, _player(1, 17898), cast=901, ability=555),
            _event(20000, 'DAMAGE_SHIELDED', 2000, BOSS, _player(1, 17898), cast=901, ability=556),
            _event(20000, 'DIED', 0, BOSS, _player(1, 0), cast=901),
            _event(20001, 'DAMAGE', 17898, BOSS, _player(1, 0), overflow=1000, cast=901),
            '70000,END_COMBAT',
        ])
        rows = analyzer.fight_history.fights[0].death_recaps[0]['events']
        self.assertEqual([r['kind'] for r in rows], ['absorbed', 'damage', 'damage'])
        lone, blocked, blow = rows
        self.assertEqual((lone['ability'], lone['amount'], lone['source']),
                         ('Bone Shield', 800, 'Test Boss'))
        self.assertEqual((blocked['result'], blocked['amount'], blocked['absorbed'],
                          blocked['shields']),
                         ('BLOCKED_DAMAGE', 2102, 5603, ['Bone Shield']))
        self.assertEqual((blow['amount'], blow['absorbed'], blow['shields']),
                         (17898, 5000, ['Bone Shield', 'Hardened Ward']))

    def test_death_event_without_a_source_takes_the_killer_from_the_blow(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(19900, 'DAMAGE', 719, BOSS, _player(1, 0), overflow=1224),
            _event(20000, 'DIED', 0, NO_UNIT, _player(1, 0)),
            '70000,END_COMBAT',
        ])
        recap = analyzer.fight_history.fights[0].death_recaps[0]
        self.assertEqual(recap['killer'], 'Test Boss')
        self.assertEqual(recap['ability'], 'Toppling Blow')

    def test_recaps_belong_to_their_fight_and_player(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(14000, 'DAMAGE', 20000, BOSS, _player(1, 0)),
            _event(14000, 'DIED', 0, BOSS, _player(1, 0)),
            _event(16000, 'DAMAGE', 20000, BOSS, _player(2, 0)),
            _event(16000, 'DIED', 0, BOSS, _player(2, 0)),
            '70000,END_COMBAT',
            '100000,BEGIN_COMBAT',
            _event(101000, 'DAMAGE', 500, BOSS, _player(1, 19500)),
            _event(102000, 'DIED', 0, BOSS, _player(1, 0)),
            '130000,END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        self.assertEqual([(r['name'], r['time_ms']) for r in first.death_recaps],
                         [('@brainsnorkel', 4000), ('@templar', 6000)])
        self.assertEqual([len(r['events']) for r in first.death_recaps], [1, 1])
        self.assertEqual([(r['name'], r['time_ms']) for r in second.death_recaps],
                         [('@brainsnorkel', 2000)])
        self.assertEqual([r['amount'] for r in second.death_recaps[0]['events']], [500])
        self.assertEqual([f.deaths for f in (first, second)], [2, 1])

    def test_zone_change_forgets_earlier_events(self):
        """Unit ids are handed out afresh in a new zone."""
        analyzer, _ = _run([
            _event(9000, 'DAMAGE', 700, BOSS, _player(1, 19300)),
            '9500,ZONE_CHANGED,57,"Deshaan",NONE',
            '9600,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
            '10000,BEGIN_COMBAT',
            _event(11000, 'DIED', 0, NO_UNIT, _player(1, 0)),
            '70000,END_COMBAT',
        ])
        recap = analyzer.fight_history.fights[0].death_recaps[0]
        self.assertEqual(recap['events'], [])
        self.assertEqual(recap['killer'], '')


class TestKillingBlowDeaths(unittest.TestCase):
    """A player killed by a player is logged as KILLING_BLOW, with no DIED."""

    def test_killing_blow_on_a_player_is_a_death_with_a_recap(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(15000, 'KILLING_BLOW', 0, _player(2, 20000), _player(1, 0), cast=77),
            _event(15000, 'DAMAGE', 20000, _player(2, 20000), _player(1, 0), overflow=30000, cast=77),
            '70000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.deaths, 1)
        self.assertEqual(analyzer.zone_deaths, 1)
        recap = fight.death_recaps[0]
        self.assertEqual((recap['name'], recap['killer']), ('@brainsnorkel', '@templar'))
        self.assertEqual([(r['amount'], r['overflow']) for r in recap['events']], [(20000, 30000)])

    def test_self_inflicted_killing_blow(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(15000, 'KILLING_BLOW', 0, _player(2, 0)),
            _event(15000, 'DAMAGE', 20000, _player(2, 0), overflow=5000),
            '70000,END_COMBAT',
        ])
        recap = analyzer.fight_history.fights[0].death_recaps[0]
        self.assertEqual((recap['name'], recap['killer'], recap['max_health']),
                         ('@templar', '@templar', 20000))
        self.assertEqual([r['health'] for r in recap['events']], [0])

    def test_killing_blow_on_an_enemy_is_not_a_player_death(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(15000, 'KILLING_BLOW', 0, _player(1, 20000), BOSS),
            '70000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual((fight.deaths, fight.death_recaps), (0, []))


class TestDeathLoggedAfterEndCombat(unittest.TestCase):
    """The blow that kills the last player standing ends combat; that death
    is written after END_COMBAT and still belongs to the fight."""

    def test_late_death_joins_the_fight_that_just_ended(self):
        analyzer, listener = _run([
            '10000,BEGIN_COMBAT',
            _event(19900, 'DAMAGE', 719, BOSS, _player(1, 0), overflow=1224),
            '20000,END_COMBAT',
            _event(20085, 'DIED', 0, NO_UNIT, _player(1, 0)),
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.deaths, 1)
        self.assertEqual(len(fight.death_recaps), 1)
        recap = fight.death_recaps[0]
        self.assertEqual((recap['name'], recap['killer'], recap['time_ms']),
                         ('@brainsnorkel', 'Test Boss', 10085))
        self.assertEqual([r['offset_ms'] for r in recap['events']], [-185])
        # Frontends that already drew the fight are told it changed
        completed = listener.of_kind('fight_completed')
        updated = listener.of_kind('fight_updated')
        self.assertEqual(len(completed), 1)
        self.assertEqual(len(updated), 1)
        self.assertIs(updated[0][1], completed[0][1])

    def test_death_well_after_combat_is_not_part_of_the_fight(self):
        analyzer, listener = _run([
            '10000,BEGIN_COMBAT',
            '20000,END_COMBAT',
            _event(20000 + LATE_DEATH_GRACE_MS + 1, 'DIED', 0, NO_UNIT, _player(1, 0)),
            '100000,BEGIN_COMBAT',
            '130000,END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        self.assertEqual((first.deaths, first.death_recaps), (0, []))
        self.assertEqual((second.deaths, second.death_recaps), (0, []))
        self.assertEqual(listener.of_kind('fight_updated'), [])


class TestRecorder(unittest.TestCase):
    """DeathRecapRecorder on its own: the window and the killing-blow grace."""

    def setUp(self):
        self.recorder = DeathRecapRecorder(
            lambda unit_id: {'70': 'Boss'}.get(unit_id, ''),
            lambda ability_id: (f'Ability {ability_id}', ''))

    @staticmethod
    def _fields(result, hit, health, overflow=0, cast=900):
        line = _event(0, result, hit, BOSS, _player(1, health), overflow=overflow, cast=cast)
        return line.split(',')[2:]

    def test_window_keeps_only_the_last_five_seconds(self):
        for ts in range(0, 12000, 1000):
            self.recorder.record(ts, self._fields('DAMAGE', ts, 15000), '1')
        recap = self.recorder.note_death('1', 11500, self._fields('DIED', 0, 0))
        self.assertEqual([r['offset_ms'] for r in recap['events']],
                         [-4500, -3500, -2500, -1500, -500])
        self.assertEqual(recap['events'][0]['offset_ms'], 7000 - 11500)
        self.assertGreaterEqual(recap['events'][0]['offset_ms'], -RECAP_WINDOW_MS)

    def test_hits_after_the_grace_are_on_the_corpse(self):
        recap = self.recorder.note_death('1', 20000, self._fields('DIED', 0, 0))
        self.recorder.record(20000 + KILLING_BLOW_GRACE_MS,
                             self._fields('DAMAGE', 111, 0, overflow=5), '1')
        self.recorder.record(20000 + KILLING_BLOW_GRACE_MS + 1,
                             self._fields('DAMAGE', 222, 0), '1')
        self.recorder.record(20500, self._fields('DAMAGE', 333, 0), '1')
        self.assertEqual([r['amount'] for r in recap['events']], [111])

    def test_a_death_starts_the_next_window_from_scratch(self):
        self.recorder.record(19000, self._fields('DAMAGE', 100, 0), '1')
        self.recorder.note_death('1', 20000, self._fields('DIED', 0, 0))
        self.recorder.record(22000, self._fields('DAMAGE', 200, 0), '1')
        again = self.recorder.note_death('1', 23000, self._fields('DIED', 0, 0))
        self.assertEqual([r['amount'] for r in again['events']], [200])

    def test_reset_drops_everything(self):
        self.recorder.record(19000, self._fields('DAMAGE', 100, 15000), '1')
        self.recorder.reset()
        recap = self.recorder.note_death('1', 20000, self._fields('DIED', 0, 0))
        self.assertEqual(recap['events'], [])


if __name__ == '__main__':
    unittest.main()
