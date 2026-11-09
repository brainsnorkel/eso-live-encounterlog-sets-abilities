#!/usr/bin/env python3
"""A trial's result (issue #129): END_TRIAL read into vitality, score and
time, and given to the fight it ended, inside the fight or just after it.

The figures are from real runs: Sunspire on 2026-10-21 (35/36), a
Dragonstar Arena run on 2026-10-22, and the Blackrose Prison runs whose
END_TRIAL comes about 4 seconds after the last END_COMBAT.
"""

import unittest

from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory
from trial_result import (
    TRIAL_NAMES,
    VITALITY_MAX,
    duration_text,
    from_end_trial,
    result_text,
    trial_name,
)

SUNSPIRE = ['12', '1351407', 'T', '253117', '35000']
DRAGONSTAR = ['4', '3754390', 'T', '33475', '14000']
# The two solo arenas Chris cleared on 2026-11-01 (issue #183)
VATESHRAN = ['14', '1805625', 'T', '262915', '14000']
MAELSTROM = ['6', '2649500', 'T', '557196', '11000']


class TestFromEndTrial(unittest.TestCase):

    def test_a_veteran_trial(self):
        result = from_end_trial(SUNSPIRE, 'Sunspire', 'VETERAN')
        self.assertEqual(result, {
            'trial_id': 12, 'name': 'Sunspire', 'is_vet': True, 'duration_ms': 1351407,
            'score': 253117, 'vitality': 35, 'vitality_max': 36})
        self.assertEqual(result_text(result), '✓ Sunspire vet · Vitality 35/36 · 253,117 · 22:31')

    def test_an_arena_has_its_own_maximum(self):
        result = from_end_trial(DRAGONSTAR, 'Dragonstar Arena', 'VETERAN')
        self.assertEqual(result['vitality_max'], 24)
        self.assertEqual(result_text(result),
                         '✓ Dragonstar Arena vet · Vitality 14/24 · 33,475 · 1:02:34')
        self.assertEqual(result_text(from_end_trial(VATESHRAN, 'Vateshran Hollows', 'VETERAN')),
                         '✓ Vateshran Hollows vet · Vitality 14/15 · 262,915 · 30:06')
        self.assertEqual(result_text(from_end_trial(MAELSTROM, 'Maelstrom Arena', 'VETERAN')),
                         '✓ Maelstrom Arena vet · Vitality 11/15 · 557,196 · 44:10')

    def test_the_maximum_by_id(self):
        expected = {4: 24, 6: 15, 11: 24, 14: 15, 3: 36, 12: 36, 19: 36}
        for trial_id, maximum in expected.items():
            fields = [str(trial_id), '1000', 'T', '1', '0']
            self.assertEqual(from_end_trial(fields, None, 'VETERAN')['vitality_max'], maximum, trial_id)
        # Every named raid has one; an id the client does not name has none
        self.assertEqual(set(VITALITY_MAX), set(TRIAL_NAMES))
        self.assertIsNone(from_end_trial(['99', '1000', 'T', '1', '0'], None, 'VETERAN')['vitality_max'])

    def test_a_normal_trial_has_none_either(self):
        # Never seen in the logs, so not claimed
        result = from_end_trial(SUNSPIRE, 'Sunspire', 'NORMAL')
        self.assertFalse(result['is_vet'])
        self.assertIsNone(result['vitality_max'])
        self.assertEqual(result_text(result), '✓ Sunspire · Vitality 35 · 253,117 · 22:31')

    def test_no_vitality_left(self):
        result = from_end_trial(['13', '1724594', 'T', '195145', '0'], "Kyne's Aegis", 'VETERAN')
        self.assertIn('Vitality 0/36', result_text(result))

    def test_no_result_for_a_run_that_did_not_succeed(self):
        self.assertIsNone(from_end_trial(['12', '1351407', 'F', '0', '0'], 'Sunspire', 'VETERAN'))
        self.assertIsNone(from_end_trial(['12', '1351407', 'False', '0', '0'], 'Sunspire',
                                         'VETERAN'))

    def test_the_parsers_true(self):
        # The engine's parser hands success on as 'True'
        result = from_end_trial(['12', '1351407', 'True', '253117', '35000'], 'Sunspire', 'VETERAN')
        self.assertEqual(result['vitality'], 35)

    def test_no_result_from_a_line_it_cannot_read(self):
        self.assertIsNone(from_end_trial(['12', '1351407', 'T'], 'Sunspire', 'VETERAN'))
        self.assertIsNone(from_end_trial(['12', 'x', 'T', '1', '2'], 'Sunspire', 'VETERAN'))

    def test_the_name_is_the_zone_then_the_id(self):
        self.assertEqual(from_end_trial(SUNSPIRE, None, 'VETERAN')['name'], 'Sunspire')
        self.assertEqual(trial_name(99), 'Trial 99')
        # The ids as the logs write them, not the old table's guesses
        self.assertEqual((TRIAL_NAMES[12], TRIAL_NAMES[16], TRIAL_NAMES[2]),
                         ('Sunspire', 'Dreadsail Reef', 'Aetherian Archive'))
        # and as the client's table 111863941 names the ones never logged
        self.assertEqual((trial_name(3), trial_name(6), trial_name(14)),
                         ('Sanctum Ophidia', 'Maelstrom Arena', 'Vateshran Hollows'))
        self.assertEqual(from_end_trial(MAELSTROM, None, 'VETERAN')['name'], 'Maelstrom Arena')

    def test_the_timer_rounds_as_the_banner_does(self):
        # The two banners seen: 1,351,407 ms showed 22:31, 2,649,500 showed 44:10
        self.assertEqual(duration_text(1351407), '22:31')
        self.assertEqual(duration_text(2649500), '44:10')
        self.assertEqual(duration_text(1805625), '30:06')
        self.assertEqual(duration_text(2649499), '44:09')
        self.assertEqual(duration_text(59999), '1:00')
        self.assertEqual(duration_text(3599500), '1:00:00')
        self.assertEqual(duration_text(-5), '0:00')


EPOCH = 1792579000000
NO_UNIT = "0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000"


def _player(unit_id):
    return f"{unit_id},20000/20000,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _boss(health):
    return f"70,{health}/1000000,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _hit(ts, health_after):
    return f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,100000,0,900,12345,{_player(1)},{_boss(health_after)}"


def _kill(ts):
    return f"{ts},COMBAT_EVENT,DIED_XP,PHYSICAL,0,0,0,0,12345,{_player(1)},{_boss(0)}"


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1121,"Sunspire",VETERAN',
    # The instance's last run was completed before this session: not one
    # of this session's results
    '1005,TRIAL_INIT,12,F,T,0,1775625,F,0',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2500,UNIT_ADDED,70,MONSTER,F,0,1000000,T,0,0,"Nahviintaas","",0,50,160,0,HOSTILE,F',
    '2600,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    '3000,BEGIN_TRIAL,12,1792579003000',
    '10000,BEGIN_COMBAT',
    _hit(11000, 900000),
    '20000,END_COMBAT',
    '30000,BEGIN_COMBAT',
    _hit(31000, 500000),
    _kill(39000),
]


class Engine:

    def __init__(self, lines):
        self.analyzer = ESOLogAnalyzer()
        self.analyzer.fight_history = FightHistory()
        self.listener = RecordingListener()
        self.analyzer.add_listener(self.listener)
        for line in lines:
            entry = self.analyzer.log_parser.parse_line(line)
            if entry is not None:
                self.analyzer.process_log_entry(entry)

    @property
    def fights(self):
        return self.analyzer.fight_history.fights

    def events(self):
        return [kind for kind, *_ in self.listener.events
                if kind in ('fight_completed', 'fight_updated')]


class TestTheFightThatEndedTheRun(unittest.TestCase):

    def test_inside_the_final_fight(self):
        engine = Engine(BASE + ['39033,END_TRIAL,12,1351407,T,253117,35000', '40000,END_COMBAT'])
        first, final = engine.fights
        self.assertIsNone(first.trial_result)
        self.assertEqual(final.trial_result['vitality'], 35)
        self.assertEqual(final.trial_result['name'], 'Sunspire')
        self.assertEqual(engine.events(), ['fight_completed', 'fight_completed'])

    def test_after_the_final_fight_was_sent(self):
        # Blackrose Prison's: about 4 seconds after END_COMBAT, with combat
        # events between, which mark the sent fight's encounter in combat
        engine = Engine(BASE + ['40000,END_COMBAT', _hit(41000, 400000),
                                '44000,END_TRIAL,12,1351407,T,253117,35000'])
        self.assertTrue(engine.analyzer.current_encounter.in_combat)
        final = engine.fights[-1]
        self.assertEqual(final.trial_result['score'], 253117)
        self.assertEqual(engine.events(), ['fight_completed', 'fight_completed', 'fight_updated'])
        self.assertIs(engine.listener.events[-1][1], final)

    def test_a_late_result_stays_when_the_fight_carries_on(self):
        # The game cuts the fight in two just after END_TRIAL: the entry is
        # built again from the encounter, which holds the result too
        engine = Engine(BASE[:-1] + [
            '35000,END_COMBAT', '35010,END_TRIAL,12,1351407,T,253117,35000',
            _hit(35020, 400000), '35030,BEGIN_COMBAT', _kill(39000), '40000,END_COMBAT'])
        self.assertEqual(len(engine.fights), 2)
        self.assertEqual(engine.fights[-1].trial_result['vitality'], 35)

    def test_no_result_without_end_trial(self):
        engine = Engine(BASE + ['40000,END_COMBAT'])
        self.assertEqual([fight.trial_result for fight in engine.fights], [None, None])

    def test_the_fight_knows_its_zone_and_difficulty(self):
        fight = Engine(BASE + ['40000,END_COMBAT']).fights[-1]
        self.assertEqual((fight.zone_id, fight.difficulty, fight.is_vet), ('1121', 'VETERAN', True))


if __name__ == '__main__':
    unittest.main()
