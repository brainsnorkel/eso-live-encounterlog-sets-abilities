#!/usr/bin/env python3
"""One pull the game cuts in two: END_COMBAT, then BEGIN_COMBAT a moment
later, in the middle of a fight. The engine carries on with the same fight
when an enemy the group was hitting is still alive, and brings the entry it
already sent to frontends up to date.

The shape is from a live trial log (Tideborn Taleria, 2026-10-05): the
logging player dies, accepts a resurrection, and the game writes END_COMBAT
and, 36 ms later, BEGIN_COMBAT and every group member's PLAYER_INFO again,
with the boss at half health throughout.
"""

import unittest

from engine_events import RecordingListener  # noqa: E402
from esolog_tail import (  # noqa: E402
    BUFF_ABILITY_IDS, COMBAT_RESUME_MS, ENGAGED_ENEMY_MS, ESOLogAnalyzer, FightHistory,
)

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
NO_UNIT = "0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000"
COURAGE = BUFF_ABILITY_IDS['major_courage']
FORCE = BUFF_ABILITY_IDS['major_force']


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _boss(health, unit_id=70):
    return f"{unit_id},{health}/{BOSS_HEALTH},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _event(ts, result, hit, source, target=None, ability=12345):
    """A COMBAT_EVENT line; *target* None writes the self-target '*'."""
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{hit},0,900,{ability},"
            f"{source},{target if target is not None else '*'}")


def _hit(ts, player, damage, boss_health_after, result='DAMAGE', boss=70):
    """Player *player* hits the boss, leaving it at *boss_health_after*."""
    return _event(ts, result, damage, _player(player), _boss(boss_health_after, boss))


def _died(ts, player):
    return _event(ts, 'DIED', 0, NO_UNIT, _player(player, 0))


def _builds(ts, *players):
    """The PLAYER_INFO lines the game writes after each BEGIN_COMBAT."""
    return [f'{ts},PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in players]


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,2,7,"Third Wheel","@third",1003,50,1800,0,PLAYER_ALLY,T',
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F',
    f'2500,UNIT_ADDED,71,MONSTER,F,0,{BOSS_HEALTH},F,0,0,"Dreadsail Deckhand","",0,50,160,0,HOSTILE,F',
    '2600,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    '2600,ABILITY_INFO,45549,"Grace","/esoui/art/icons/ability_armor_004.dds",T,T',
]

# Player 1 dies and is resurrected; the game ends combat and starts it again
# 36 ms later, a hit landing in between
FIRST_PART = [
    '10000,BEGIN_COMBAT',
    *_builds(10001, 1, 2, 3),
    _hit(11000, 2, 100000, 900000),
    _died(20100, 1),
    _hit(29000, 2, 300000, 600000),
    _event(30000, 'SOUL_GEM_RESURRECTION_ACCEPTED', 0, _player(2), _player(1, 0), ability=0),
    '30031,END_COMBAT',
]
SECOND_PART = [
    _hit(30050, 2, 50000, 550000),
    '30067,BEGIN_COMBAT',
    *_builds(30067, 1, 2, 3),
    _hit(40000, 1, 100000, 450000),
    _hit(50000, 2, 450000, 0),
    _event(50001, 'DIED_XP', 0, _player(2), _boss(0)),
    '50100,END_COMBAT',
]


class Engine:
    """An analyzer fed in steps, so a fight can be looked at between its parts."""

    def __init__(self, timeline=False):
        self.analyzer = ESOLogAnalyzer()
        self.analyzer.fight_history = FightHistory()
        self.analyzer.track_buff_timeline = timeline
        self.listener = RecordingListener()
        self.analyzer.add_listener(self.listener)
        self.feed(BASE)

    def feed(self, lines):
        for line in lines:
            entry = self.analyzer.log_parser.parse_line(line)
            if entry is not None:
                self.analyzer.process_log_entry(entry)
        return self

    @property
    def fights(self):
        return self.analyzer.fight_history.fights

    def events(self):
        """The fight events sent to frontends, in order: (kind, entry)."""
        return [event for event in self.listener.events
                if event[0] in ('fight_completed', 'fight_updated')]


def _fights(*lines):
    return Engine().feed(lines).fights


class TestFightCutInTwo(unittest.TestCase):

    def test_it_is_one_fight(self):
        engine = Engine().feed(FIRST_PART + SECOND_PART)
        self.assertEqual(len(engine.fights), 1)
        fight = engine.fights[0]
        self.assertEqual(fight.boss_name, 'Tideborn Taleria')
        # From the first BEGIN_COMBAT to the last END_COMBAT
        self.assertAlmostEqual(fight.duration_s, 40.1)
        # Every hit counts, the one between the two lines included
        self.assertAlmostEqual(fight.group_dps, 1000000 / 40.1)
        dps = {p['name']: p['dps'] for p in fight.players}
        self.assertAlmostEqual(dps['@brainsnorkel'], 100000 / 40.1)
        self.assertAlmostEqual(dps['@templar'], 900000 / 40.1)
        self.assertEqual(fight.deaths, 1)

    def test_first_part_shows_until_the_fight_really_ends(self):
        engine = Engine().feed(FIRST_PART)
        self.assertEqual(len(engine.fights), 1)
        fight = engine.fights[0]
        started = fight.timestamp
        self.assertAlmostEqual(fight.duration_s, 20.031)
        self.assertAlmostEqual(fight.group_dps, 400000 / 20.031)
        self.assertEqual([kind for kind, _entry in engine.events()], ['fight_completed'])

        engine.feed(SECOND_PART)
        # The entry frontends already hold is the one brought up to date
        self.assertEqual(len(engine.fights), 1)
        self.assertIs(engine.fights[0], fight)
        self.assertAlmostEqual(fight.duration_s, 40.1)
        self.assertEqual(fight.timestamp, started)
        events = engine.events()
        self.assertEqual([kind for kind, _entry in events], ['fight_completed', 'fight_updated'])
        self.assertIs(events[1][1], fight)

    def test_deaths_of_both_parts_are_counted_once_each(self):
        engine = Engine().feed(FIRST_PART + [
            _died(30050, 2),                      # between the two lines
            '30067,BEGIN_COMBAT',
            *_builds(30067, 1, 2, 3),
            _hit(40000, 3, 100000, 500000),
            _died(45000, 1),
            '50100,END_COMBAT',
        ])
        self.assertEqual(len(engine.fights), 1)
        fight = engine.fights[0]
        self.assertEqual(fight.deaths, 3)
        # Times run from the start of the fight, not of its second part
        self.assertEqual([(r['name'], r['time_ms']) for r in fight.death_recaps],
                         [('@brainsnorkel', 10100), ('@templar', 20050),
                          ('@brainsnorkel', 35000)])

    def test_fight_cut_twice(self):
        engine = Engine().feed(FIRST_PART + [
            '30067,BEGIN_COMBAT',
            _hit(40000, 1, 100000, 500000),
            '45000,END_COMBAT',
            '45080,BEGIN_COMBAT',
            _hit(50000, 2, 500000, 0),
            '50100,END_COMBAT',
        ])
        self.assertEqual(len(engine.fights), 1)
        self.assertAlmostEqual(engine.fights[0].duration_s, 40.1)
        self.assertAlmostEqual(engine.fights[0].group_dps, 1000000 / 40.1)
        self.assertEqual([kind for kind, _entry in engine.events()],
                         ['fight_completed', 'fight_updated', 'fight_updated'])

    def test_damage_over_time_keeps_an_enemy_engaged(self):
        fights = _fights('10000,BEGIN_COMBAT',
                         _hit(19000, 2, 5000, 600000, result='DOT_TICK'),
                         '20000,END_COMBAT',
                         '20100,BEGIN_COMBAT',
                         _hit(25000, 2, 100000, 500000),
                         '30000,END_COMBAT')
        self.assertEqual(len(fights), 1)
        self.assertAlmostEqual(fights[0].duration_s, 20.0)

    def test_the_next_fight_is_a_fight_of_its_own(self):
        engine = Engine().feed(FIRST_PART + SECOND_PART + [
            '90000,BEGIN_COMBAT',
            *_builds(90001, 1, 2, 3),
            _hit(91000, 1, 70000, 930000, boss=71),
            '100000,END_COMBAT',
        ])
        first, second = engine.fights
        self.assertAlmostEqual(first.duration_s, 40.1)
        self.assertEqual((second.boss_name, second.deaths), ('Dreadsail Deckhand', 0))
        self.assertAlmostEqual(second.duration_s, 10.0)
        self.assertAlmostEqual(second.group_dps, 7000.0)
        self.assertEqual([kind for kind, _entry in engine.events()],
                         ['fight_completed', 'fight_updated', 'fight_completed'])


class TestSeparateFightsStaySeparate(unittest.TestCase):

    def _two_pulls(self, gap_ms):
        return _fights('10000,BEGIN_COMBAT',
                       _hit(19000, 2, 100000, 900000),
                       '20000,END_COMBAT',
                       f'{20000 + gap_ms},BEGIN_COMBAT',
                       _hit(25000, 2, 100000, 800000),
                       '30000,END_COMBAT')

    def test_begin_combat_must_follow_closely(self):
        self.assertEqual(len(self._two_pulls(COMBAT_RESUME_MS)), 1)
        apart = self._two_pulls(COMBAT_RESUME_MS + 1)
        self.assertEqual(len(apart), 2)
        self.assertAlmostEqual(apart[0].duration_s, 10.0)
        self.assertAlmostEqual(apart[1].duration_s, 30.0 - 20.0 - (COMBAT_RESUME_MS + 1) / 1000)

    def test_next_pack_pulled_as_the_last_enemy_dies(self):
        for label, kill in (
                ('the last hit leaves no health', [_hit(19000, 2, 900000, 0)]),
                ('its death is logged', [_hit(19000, 2, 899999, 1),
                                         _event(19001, 'DIED_XP', 0, _player(2), _boss(0))])):
            with self.subTest(label):
                fights = _fights('10000,BEGIN_COMBAT',
                                 _hit(11000, 2, 100000, 900000),
                                 *kill,
                                 '20000,END_COMBAT',
                                 '20100,BEGIN_COMBAT',
                                 _hit(25000, 2, 100000, 900000, boss=71),
                                 '30000,END_COMBAT')
                self.assertEqual([f.boss_name for f in fights],
                                 ['Tideborn Taleria', 'Dreadsail Deckhand'])

    def test_damage_reaching_the_next_pack_between_the_two_lines(self):
        """Common on trash: the pack dies, combat ends, and the group's
        damage is already landing on the next pack as combat begins again."""
        fights = _fights('10000,BEGIN_COMBAT',
                         _hit(19000, 2, 900000, 0),
                         '20000,END_COMBAT',
                         _hit(20050, 2, 100000, 900000, boss=71),
                         '20100,BEGIN_COMBAT',
                         _hit(25000, 2, 100000, 800000, boss=71),
                         '30000,END_COMBAT')
        self.assertEqual([f.boss_name for f in fights],
                         ['Tideborn Taleria', 'Dreadsail Deckhand'])

    def test_last_enemy_dying_between_the_two_lines(self):
        fights = _fights('10000,BEGIN_COMBAT',
                         _hit(19000, 2, 899999, 1),
                         '20000,END_COMBAT',
                         _event(20050, 'DIED_XP', 0, _player(2), _boss(0)),
                         '20100,BEGIN_COMBAT',
                         _hit(25000, 2, 100000, 900000, boss=71),
                         '30000,END_COMBAT')
        self.assertEqual(len(fights), 2)

    def test_enemy_removed_without_a_death_line(self):
        """A summoned add leaves the log with UNIT_REMOVED when its summoner
        dies; it is not an enemy still being fought."""
        fights = _fights('10000,BEGIN_COMBAT',
                         _hit(19000, 2, 100000, 900000),
                         '19500,UNIT_REMOVED,70',
                         '20000,END_COMBAT',
                         '20100,BEGIN_COMBAT',
                         _hit(25000, 2, 100000, 900000, boss=71),
                         '30000,END_COMBAT')
        self.assertEqual([f.boss_name for f in fights],
                         ['Tideborn Taleria', 'Dreadsail Deckhand'])

    def test_enemy_left_alone_for_a_while_does_not_join_two_fights(self):
        ended = 11000 + ENGAGED_ENEMY_MS + 1
        fights = _fights('10000,BEGIN_COMBAT',
                         _hit(11000, 2, 100000, 900000),
                         f'{ended},END_COMBAT',
                         f'{ended + 100},BEGIN_COMBAT',
                         _hit(ended + 5000, 2, 100000, 800000),
                         f'{ended + 9000},END_COMBAT')
        self.assertEqual(len(fights), 2)

    def test_fight_without_a_hit_on_an_enemy(self):
        fights = _fights('10000,BEGIN_COMBAT',
                         _event(15000, 'DAMAGE', 3000, _boss(BOSS_HEALTH), _player(1, 17000)),
                         '20000,END_COMBAT',
                         '20100,BEGIN_COMBAT',
                         '30000,END_COMBAT')
        self.assertEqual(len(fights), 2)

    def test_zone_change_ends_the_carrying_on(self):
        engine = Engine().feed(FIRST_PART + [
            '30067,BEGIN_COMBAT',
            _hit(31000, 1, 100000, 500000),
            # The group leaves mid-fight; a new fight follows in the next zone
            '40000,ZONE_CHANGED,1263,"Rockgrove",VETERAN',
            '41000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
            f'41000,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Oaxiltso","",0,50,160,0,HOSTILE,F',
            '50000,BEGIN_COMBAT',
            *_builds(50001, 1),
            _hit(51000, 1, 80000, 920000),
            '60000,END_COMBAT',
        ])
        first, second = engine.fights
        # The first fight keeps what was sent for it; the new one is not
        # written over it
        self.assertEqual((first.boss_name, first.zone_name), ('Tideborn Taleria', 'Dreadsail Reef'))
        self.assertAlmostEqual(first.duration_s, 20.031)
        self.assertEqual((second.boss_name, second.zone_name), ('Oaxiltso', 'Rockgrove'))
        self.assertAlmostEqual(second.duration_s, 10.0)
        self.assertEqual([kind for kind, _entry in engine.events()],
                         ['fight_completed', 'fight_completed'])


class TestBuffsAcrossTheCut(unittest.TestCase):

    def test_group_buff_uptime_covers_the_whole_fight(self):
        engine = Engine()
        engine.feed([
            # Up from before the pull to its end
            f'5000,EFFECT_CHANGED,GAINED,1,900,{COURAGE},{_player(1)},*',
            *FIRST_PART[:3],
            # Ten seconds, all of them in the first part
            f'12000,EFFECT_CHANGED,GAINED,1,901,{FORCE},{_player(2)},*',
            f'22000,EFFECT_CHANGED,FADED,1,901,{FORCE},{_player(2)},*',
            *FIRST_PART[3:],
        ])
        # A group fighting a boss gets its taunt uptime too, here none
        self.assertEqual(engine.fights[0].buff_summary, 'MCourage:100% MForce:50% Taunt:0%')
        engine.feed(SECOND_PART)
        self.assertEqual(engine.fights[0].buff_summary, 'MCourage:100% MForce:25% Taunt:0%')

    def test_timeline_keeps_the_first_part(self):
        force = ('{ts},EFFECT_CHANGED,{change},1,111,61747,' + _player(1) + ',' + _player(2))
        engine = Engine(timeline=True).feed([
            *FIRST_PART[:3],
            force.format(ts=15000, change='GAINED'),
            force.format(ts=25000, change='FADED'),
            *FIRST_PART[3:],
            *SECOND_PART,
        ])
        timeline = engine.fights[0].buff_timeline
        self.assertEqual(timeline['duration_ms'], 40100)
        self.assertEqual(timeline['effects']['Major Force'],
                         [{'start_ms': 5000, 'end_ms': 15000,
                           'source': '@brainsnorkel', 'target': '@templar'}])


if __name__ == '__main__':
    unittest.main()
