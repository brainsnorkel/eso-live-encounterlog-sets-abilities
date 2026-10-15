#!/usr/bin/env python3
"""Class Mastery passives on a fight's players: from the PLAYER_INFO list,
or from a mastery's effect firing with the player as its source
(eso_sets.mastery_of_effect), kept for the rest of the session."""

import unittest

from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory

EPOCH = 1700000000000
ABILITY = 12345
UNBOUND_POTENTIAL = 263411        # the effect Unbound Potential fires (never in the list)
AN_EYE_FOR_EXPLOITATION = 263604  # a mastery passive that is in the list
HEMORRHAGE = 45060                # an Assassination passive, not a mastery


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _monster(unit_id, health, max_health):
    return f"{unit_id},{health}/{max_health},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _hit(ts, source, damage, target):
    return (f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{damage},0,900,{ABILITY},"
            f"{_player(source)},{_monster(target, 50000, 50000)}")


def _gained(ts, ability_id, source):
    return f"{ts},EFFECT_CHANGED,GAINED,1,777,{ability_id},{_player(source)},*"


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,4,"Arcanist","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,3,1,"Blade","@nightblade",1002,50,2547,0,PLAYER_ALLY,T',
    '2500,UNIT_ADDED,70,MONSTER,F,0,50000,F,0,0,"Lesser Sea Adder","",0,50,160,0,HOSTILE,F',
    f'2600,ABILITY_INFO,{ABILITY},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    f'2600,ABILITY_INFO,{UNBOUND_POTENTIAL},"Unbound Potential","/esoui/art/icons/passive_arcanist_04.dds",F,F',
]


def _fight(start, effects_in_fight, second_player_list):
    return [
        f'{start},BEGIN_COMBAT',
        f'{start + 1},PLAYER_INFO,1,[{HEMORRHAGE}],[1],[],[{ABILITY}],[{ABILITY}]',
        f'{start + 1},PLAYER_INFO,2,[{second_player_list}],[1],[],[{ABILITY}],[{ABILITY}]',
        _hit(start + 1000, 1, 5000, 70),
        _hit(start + 1000, 2, 5000, 70),
        *effects_in_fight,
        f'{start + 20000},END_COMBAT',
    ]


def _run(lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer, analyzer.fight_history.fights


def _masteries(fight, unit_id):
    return next(p['masteries'] for p in fight.players if p['unit_id'] == str(unit_id))


class TestClassMastery(unittest.TestCase):

    def test_listed_and_fired_masteries(self):
        _analyzer, fights = _run(_fight(10000, [_gained(12000, UNBOUND_POTENTIAL, 1)],
                                        f'{HEMORRHAGE},{AN_EYE_FOR_EXPLOITATION}'))
        self.assertEqual(len(fights), 1)
        # Player 1's list has no mastery; Unbound Potential fired from them
        self.assertEqual(_masteries(fights[0], 1), ['Unbound Potential'])
        # Player 2's mastery is in the list, and nothing fired
        self.assertEqual(_masteries(fights[0], 2), ['An Eye for Exploitation'])

    def test_a_mastery_seen_once_stays_for_the_session(self):
        _analyzer, fights = _run(
            _fight(10000, [_gained(12000, UNBOUND_POTENTIAL, 1)], HEMORRHAGE)
            + _fight(40000, [], HEMORRHAGE))
        self.assertEqual(len(fights), 2)
        self.assertEqual(_masteries(fights[1], 1), ['Unbound Potential'])
        self.assertEqual(_masteries(fights[1], 2), [])

    def test_only_a_player_source_counts_and_only_once(self):
        monster_fires = f'12000,EFFECT_CHANGED,GAINED,1,777,{UNBOUND_POTENTIAL},{_monster(70, 50000, 50000)},*'
        _analyzer, fights = _run(_fight(10000, [
            monster_fires,
            _gained(13000, UNBOUND_POTENTIAL, 2), _gained(14000, UNBOUND_POTENTIAL, 2),
            _gained(15000, HEMORRHAGE, 2),  # a line passive, not a mastery
        ], HEMORRHAGE))
        self.assertEqual(_masteries(fights[0], 1), [])
        self.assertEqual(_masteries(fights[0], 2), ['Unbound Potential'])

    def test_session_cache_carries_a_fired_mastery(self):
        analyzer, _fights = _run(_fight(10000, [_gained(12000, UNBOUND_POTENTIAL, 1)], HEMORRHAGE))
        session = analyzer.player_sessions['@brainsnorkel+Arcanist']
        self.assertEqual(session['masteries'], ['Unbound Potential'])
        restored = analyzer._get_player_from_session('9', 'Arcanist', '@brainsnorkel')
        self.assertEqual(restored.masteries_seen, ['Unbound Potential'])
        self.assertEqual(restored.masteries(), ['Unbound Potential'])


if __name__ == '__main__':
    unittest.main()
