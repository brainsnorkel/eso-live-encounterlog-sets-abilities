#!/usr/bin/env python3
"""Taunts in a fight: how long the boss was taunted, which abilities each
player taunted with, and the marks on their bars (no Qt needed).

The log's shape is from live logs of October 2026 (Sunspire, Dreadsail
Reef, Lucent Citadel): every TAUNTED combat event shares its cast tracking
id with the BEGIN_CAST of the skill that taunted, and the game keeps one
Taunt debuff (ability 38254) on the enemy that GAINED, UPDATED and FADED
lines bracket. Destructive Clench with an ice staff is cast and hits as
Frost Clench, a different id with the same icon as the slotted skill.
"""

import unittest

from engine_events import RecordingListener  # noqa: E402
from esolog_tail import (  # noqa: E402
    CAST_MEMORY, ESOLogAnalyzer, FightHistory, _covered_ms, mark_taunt_slots,
)
from gui.fight_render import render_plain_text  # noqa: E402

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
INNER_RAGE, CLENCH, FROST_CLENCH, HIT, TAUNT = '42056', '38984', '38989', '12345', '38254'


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _boss(health=BOSS_HEALTH, unit_id=70):
    return f"{unit_id},{health}/{BOSS_HEALTH},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _event(ts, result, hit, source, target, ability=HIT, cast=900):
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{hit},0,{cast},{ability},"
            f"{source},{target}")


def _hit(ts, player, damage=1000, boss_health_after=900000, cast=900, ability=HIT):
    return _event(ts, 'DAMAGE', damage, _player(player), _boss(boss_health_after),
                  ability=ability, cast=cast)


def _cast(ts, player, ability, cast):
    return f"{ts},BEGIN_CAST,0,F,{cast},{ability},{_player(player)},{_boss()}"


def _taunted(ts, player, cast, boss=70):
    return _event(ts, 'TAUNTED', 0, _player(player), _boss(unit_id=boss), ability=TAUNT,
                  cast=cast)


def _taunt_effect(ts, change, player, cast, boss=70):
    return f"{ts},EFFECT_CHANGED,{change},1,{cast},{TAUNT},{_player(player)},{_boss(unit_id=boss)}"


def _taunt(ts, player, ability, cast, boss=70):
    """A taunting cast: the cast, its hit, the TAUNTED event and the debuff."""
    return [_cast(ts, player, ability, cast),
            _hit(ts, player, cast=cast, ability=ability),
            _taunted(ts, player, cast, boss),
            _taunt_effect(ts, 'GAINED', player, cast, boss)]


def _builds(ts, *players):
    lines = []
    for unit in players:
        front = f"{INNER_RAGE},{CLENCH},{HIT}" if unit == 1 else HIT
        lines.append(f'{ts},PLAYER_INFO,{unit},[45549],[1],[],[{front}],[{HIT}]')
    return lines


def _base(boss_flag='T'):
    return [
        f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
        '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
        '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,1,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
        '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
        '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,2,7,"Third Wheel","@third",1003,50,1800,0,PLAYER_ALLY,T',
        f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},{boss_flag},0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F',
        f'2500,UNIT_ADDED,71,MONSTER,F,0,{BOSS_HEALTH},F,0,0,"Dreadsail Deckhand","",0,50,160,0,HOSTILE,F',
        f'2600,ABILITY_INFO,{HIT},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
        '2600,ABILITY_INFO,45549,"Grace","/esoui/art/icons/ability_armor_004.dds",T,T',
        f'2600,ABILITY_INFO,{INNER_RAGE},"Inner Rage","/esoui/art/icons/ability_undaunted_002_b.dds",F,F',
        f'2600,ABILITY_INFO,{CLENCH},"Destructive Clench","/esoui/art/icons/ability_destructionstaff_005_a.dds",F,F',
        f'2600,ABILITY_INFO,{FROST_CLENCH},"Frost Clench","/esoui/art/icons/ability_destructionstaff_005_a.dds",F,F',
        f'2600,ABILITY_INFO,{TAUNT},"Taunt","/esoui/art/icons/quest_shield_001.dds",F,F',
    ]


# A 50 s fight: the tank taunts with Inner Rage at 11 s (the taunt fades at
# 26 s), with Frost Clench at 30 s, and again with Inner Rage at 35 s while
# that taunt is up (the debuff is UPDATED, not restarted); it fades at 45 s.
# The boss is taunted for 30 of the 50 s.
FIGHT = [
    '10000,BEGIN_COMBAT',
    *_builds(10001, 1, 2, 3),
    _hit(10500, 2),
    *_taunt(11000, 1, INNER_RAGE, 901),
    _hit(20000, 2),
    _taunt_effect(26000, 'FADED', 1, 901),
    *_taunt(30000, 1, FROST_CLENCH, 902),
    _cast(35000, 1, INNER_RAGE, 903),
    _hit(35000, 1, cast=903, ability=INNER_RAGE),
    _taunted(35000, 1, 903),
    _taunt_effect(35000, 'UPDATED', 1, 903),
    _hit(40000, 3),
    _taunt_effect(45000, 'FADED', 1, 903),
    _hit(55000, 2),
    '60000,END_COMBAT',
]


def _fights(lines, base=None):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in (base if base is not None else _base()) + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer, analyzer.fight_history.fights


def _player_of(fight, name):
    return next(p for p in fight.players if p['name'] == name)


class TestTauntUptime(unittest.TestCase):

    def test_share_of_the_fight_the_boss_was_taunted(self):
        _analyzer, fights = _fights(FIGHT)
        self.assertEqual(len(fights), 1)
        self.assertEqual(fights[0].buff_summary, 'Taunt:60%')

    def test_a_taunt_still_up_when_the_fight_ends_counts_to_the_end(self):
        lines = [line for line in FIGHT if not line.startswith('45000,EFFECT_CHANGED,FADED')]
        _analyzer, fights = _fights(lines)
        # 11-26 s and 30 s to the end at 60 s
        self.assertEqual(fights[0].buff_summary, 'Taunt:90%')

    def test_a_boss_killed_before_the_fight_ends_is_measured_to_its_death(self):
        lines = FIGHT[:-2] + [
            _hit(50000, 2, boss_health_after=0),
            _event(50001, 'DIED_XP', 0, _player(2), _boss(0)),
            _hit(55000, 2),  # the deckhand still up: the fight goes on
            '60000,END_COMBAT',
        ]
        _analyzer, fights = _fights(lines)
        # 30 taunted of the boss's 40 s
        self.assertEqual(fights[0].buff_summary, 'Taunt:75%')

    def test_no_line_for_a_fight_without_a_boss(self):
        _analyzer, fights = _fights(FIGHT, base=_base(boss_flag='F'))
        self.assertEqual(fights[0].buff_summary, '')
        # The taunts themselves are still known
        self.assertEqual([t['name'] for t in _player_of(fights[0], '@brainsnorkel')['taunts']],
                         ['Inner Rage', 'Frost Clench'])

    def test_a_small_group_gets_the_line_only_when_someone_taunted(self):
        duo = [line for line in _base() if '"@third"' not in line]
        quiet = ['10000,BEGIN_COMBAT', *_builds(10001, 1, 2), _hit(11000, 2),
                 _hit(20000, 1), '30000,END_COMBAT']
        _analyzer, fights = _fights(quiet, base=duo)
        self.assertEqual(fights[0].buff_summary, '')
        taunting = ['10000,BEGIN_COMBAT', *_builds(10001, 1, 2), _hit(11000, 2),
                    *_taunt(15000, 1, INNER_RAGE, 901), '30000,END_COMBAT']
        _analyzer, fights = _fights(taunting, base=duo)
        self.assertEqual(fights[0].buff_summary, 'Taunt:75%')

    def test_a_boss_dead_since_the_last_fight_is_not_measured(self):
        # The boss dies in the first fight; the second, against the deckhand
        # only, carries the boss's unit over but did not fight it
        first = FIGHT[:-2] + [_hit(50000, 2, boss_health_after=0),
                              _event(50001, 'DIED_XP', 0, _player(2), _boss(0)),
                              '50100,END_COMBAT']
        deckhand = _boss(unit_id=71)
        second = ['70000,BEGIN_COMBAT', *_builds(70001, 1, 2, 3),
                  _event(71000, 'DAMAGE', 1000, _player(2), deckhand),
                  _event(80000, 'DAMAGE', 1000, _player(3), deckhand),
                  '90000,END_COMBAT']
        _analyzer, fights = _fights(first + second)
        self.assertEqual([f.buff_summary for f in fights], ['Taunt:75%', ''])


class TestWhoTauntedWithWhat(unittest.TestCase):

    def setUp(self):
        self.analyzer, fights = _fights(FIGHT)
        self.fight = fights[0]
        self.tank = _player_of(self.fight, '@brainsnorkel')

    def test_the_skill_is_named_through_its_cast_most_used_first(self):
        self.assertEqual(self.tank['taunts'], [
            {'id': INNER_RAGE, 'name': 'Inner Rage', 'icon': 'ability_undaunted_002_b',
             'count': 2},
            {'id': FROST_CLENCH, 'name': 'Frost Clench',
             'icon': 'ability_destructionstaff_005_a', 'count': 1},
        ])
        for name in ('@templar', '@third'):
            self.assertEqual(_player_of(self.fight, name)['taunts'], [])

    def test_bars_mark_the_slots_that_taunted(self):
        front = self.tank['front_bar_slots']
        self.assertEqual([slot['id'] for slot in front], [INNER_RAGE, CLENCH, HIT])
        # Inner Rage by id; Destructive Clench by the icon it shares with
        # Frost Clench, which is not slotted; the plain hit not at all
        self.assertEqual([slot.get('taunt') for slot in front], [True, True, None])
        self.assertEqual([slot.get('taunt') for slot in self.tank['back_bar_slots']], [None])
        for name in ('@templar', '@third'):
            p = _player_of(self.fight, name)
            self.assertFalse(any(slot.get('taunt') for slot in p['front_bar_slots']))

    def test_copied_text_lists_the_taunting_abilities(self):
        text = render_plain_text(self.fight)
        self.assertIn('      taunted with Inner Rage ×2, Frost Clench ×1\n', text)
        self.assertEqual(text.count('taunted with'), 1)
        self.assertIn('Taunt:60%', text)

    def test_cast_memory_stays_bounded(self):
        casts = [_cast(100000 + i, 2, HIT, 5000 + i) for i in range(CAST_MEMORY + 10)]
        _analyzer, _fights_ = _fights(FIGHT[:-1] + casts + ['200000,END_COMBAT'])
        self.assertLessEqual(len(_analyzer._cast_abilities), CAST_MEMORY)
        self.assertIn(str(5000 + CAST_MEMORY + 9), _analyzer._cast_abilities)


class TestHelpers(unittest.TestCase):

    def test_covered_ms_merges_overlaps_and_clips_to_the_window(self):
        self.assertEqual(_covered_ms([], 0, 100), 0)
        self.assertEqual(_covered_ms([(10, 20), (15, 30), (40, 50)], 0, 100), 30)
        self.assertEqual(_covered_ms([(0, 50), (90, 200)], 10, 100), 50)
        self.assertEqual(_covered_ms([(200, 300)], 0, 100), 0)
        self.assertEqual(_covered_ms([(0, 1000)], 100, 200), 100)

    def test_mark_taunt_slots(self):
        slots = [{'id': '1', 'icon': 'a'}, {'id': '2', 'icon': 'b'}, {'id': '3', 'icon': 'b'},
                 {'id': '4', 'icon': ''}]
        # By id for 1; by icon for the taunt logged as 9, which no slot has
        # but which shares icon 'b' with slots 2 and 3; 5 shares icon 'a'
        # but 1 is slotted, so the icon rule does not fire for it
        mark_taunt_slots(slots, [{'id': '1', 'icon': 'a', 'name': 'x', 'count': 1},
                                 {'id': '9', 'icon': 'b', 'name': 'y', 'count': 1}])
        self.assertEqual([slot.get('taunt') for slot in slots], [True, True, True, None])
        plain = [{'id': '4', 'icon': ''}]
        mark_taunt_slots(plain, [{'id': '9', 'icon': '', 'name': 'y', 'count': 1}])
        self.assertEqual(plain, [{'id': '4', 'icon': ''}])


if __name__ == '__main__':
    unittest.main()
