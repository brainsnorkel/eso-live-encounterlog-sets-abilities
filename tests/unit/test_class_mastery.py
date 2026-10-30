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
            _gained(13000, UNBOUND_POTENTIAL, 1), _gained(14000, UNBOUND_POTENTIAL, 1),
            _gained(15000, HEMORRHAGE, 1),  # a line passive, not a mastery
            _gained(16000, UNBOUND_POTENTIAL, 2),  # a Nightblade: not an Arcanist mastery's holder
        ], HEMORRHAGE))
        self.assertEqual(_masteries(fights[0], 1), ['Unbound Potential'])
        self.assertEqual(_masteries(fights[0], 2), [])

    def test_buff_named_signature_effects_need_the_right_class(self):
        # 263306 is the Major Berserk a Dragonknight's Lead from the Front
        # gives the group; 263825 the Major Brittle of a Warden's Tundra's Maw
        base = [
            '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,1,4,"Knight","@dk",1003,50,3225,0,PLAYER_ALLY,T',
            '2000,UNIT_ADDED,4,PLAYER,F,4,0,F,4,4,"Warden","@warden",1004,50,3225,0,PLAYER_ALLY,T',
            '2600,ABILITY_INFO,263306,"Major Berserk","/esoui/art/icons/ability_mage_065.dds",F,F',
            '2600,ABILITY_INFO,263825,"Major Brittle","/esoui/art/icons/ability_mage_065.dds",F,F',
        ]
        fight = _fight(10000, [
            # The Dragonknight gives player 1 Major Berserk; a Nightblade (2)
            # sourcing the same id is not a Dragonknight
            f'12000,EFFECT_CHANGED,GAINED,1,777,263306,{_player(3)},{_player(1)}',
            f'12000,EFFECT_CHANGED,GAINED,1,778,263306,{_player(2)},{_player(1)}',
            f'13000,EFFECT_CHANGED,GAINED,1,779,263825,{_player(4)},{_monster(70, 50000, 50000)}',
        ], HEMORRHAGE)
        fight[1:1] = [
            f'10001,PLAYER_INFO,3,[{HEMORRHAGE}],[1],[],[{ABILITY}],[{ABILITY}]',
            f'10001,PLAYER_INFO,4,[{HEMORRHAGE}],[1],[],[{ABILITY}],[{ABILITY}]',
            _hit(11000, 3, 5000, 70), _hit(11000, 4, 5000, 70),
        ]
        _analyzer, fights = _run(base + fight)
        self.assertEqual(_masteries(fights[0], 3), ['Lead from the Front'])
        self.assertEqual(_masteries(fights[0], 4), ["Tundra's Maw"])
        self.assertEqual(_masteries(fights[0], 2), [])
        self.assertEqual(_masteries(fights[0], 1), [])

    def test_resource_masteries_from_the_gain_their_holder_gives(self):
        # Conservation of Energy fires no effect, only the Magicka gain to
        # the Sorcerer (263877); Share the Spoils only the Ultimate the
        # Nightblade (2) gives the group (263689): its holder is the source
        def energize(ts, ability_id, source, target, power_type=1):
            return (f'{ts},COMBAT_EVENT,POWER_ENERGIZE,GENERIC,{power_type},1500,0,900,{ability_id},'
                    f'{_player(source)},{target}')
        base = ['2000,UNIT_ADDED,3,PLAYER,F,3,0,F,2,4,"Sorc","@sorc",1003,50,3225,0,PLAYER_ALLY,T']
        fight = _fight(10000, [
            energize(12000, 263877, 3, '*'),
            energize(12500, 263689, 2, _player(1), power_type=8),
            # The same gain from a monster names no one
            f'13000,COMBAT_EVENT,POWER_ENERGIZE,GENERIC,1,1500,0,900,263877,'
            f'{_monster(70, 50000, 50000)},{_player(1)}',
        ], HEMORRHAGE)
        fight[1:1] = [f'10001,PLAYER_INFO,3,[{HEMORRHAGE}],[1],[],[{ABILITY}],[{ABILITY}]',
                      _hit(11000, 3, 5000, 70)]
        _analyzer, fights = _run(base + fight)
        self.assertEqual(_masteries(fights[0], 3), ['Conservation of Energy'])
        self.assertEqual(_masteries(fights[0], 2), ['Share the Spoils'])
        self.assertEqual(_masteries(fights[0], 1), [])

    def test_a_resource_gain_needs_the_masterys_class(self):
        # A Warden sourcing Conservation of Energy's gain is not a Sorcerer;
        # a Nightblade's Nocturnal Inspiration (263613) and a Templar's Hold
        # the Line Ultimate (263621) name their own masteries
        def energize(ts, ability_id, source):
            return (f'{ts},COMBAT_EVENT,POWER_ENERGIZE,GENERIC,8,1,0,900,{ability_id},'
                    f'{_player(source)},*')
        base = [
            '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,6,4,"Templar","@templar",1003,50,3225,0,PLAYER_ALLY,T',
            '2000,UNIT_ADDED,4,PLAYER,F,4,0,F,4,4,"Warden","@warden",1004,50,3225,0,PLAYER_ALLY,T',
        ]
        fight = _fight(10000, [
            energize(12000, 263877, 4),
            energize(12000, 263613, 2),
            energize(12000, 263621, 3),
        ], HEMORRHAGE)
        fight[1:1] = [
            f'10001,PLAYER_INFO,3,[{HEMORRHAGE}],[1],[],[{ABILITY}],[{ABILITY}]',
            f'10001,PLAYER_INFO,4,[{HEMORRHAGE}],[1],[],[{ABILITY}],[{ABILITY}]',
            _hit(11000, 3, 5000, 70), _hit(11000, 4, 5000, 70),
        ]
        _analyzer, fights = _run(base + fight)
        self.assertEqual(_masteries(fights[0], 4), [])
        self.assertEqual(_masteries(fights[0], 2), ['Nocturnal Inspiration'])
        self.assertEqual(_masteries(fights[0], 3), ['Devout Guardian'])

    def test_devout_guardian_from_its_hold_the_line_shield(self):
        # 263619, Hold the Line: the shield a Templar gains on themselves.
        # A Warden sourcing the id is not a Templar, and another player's
        # hit the shield absorbed names no one
        base = [
            '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,6,4,"Templar","@templar",1003,50,3225,0,PLAYER_ALLY,T',
            '2000,UNIT_ADDED,4,PLAYER,F,4,0,F,4,4,"Warden","@warden",1004,50,3225,0,PLAYER_ALLY,T',
        ]
        fight = _fight(10000, [
            _gained(12000, 263619, 3),
            _gained(12000, 263619, 4),
            f'12500,COMBAT_EVENT,DAMAGE_SHIELDED,GENERIC,0,900,0,901,263619,{_player(1)},{_player(3)}',
        ], HEMORRHAGE)
        fight[1:1] = [
            f'10001,PLAYER_INFO,3,[{HEMORRHAGE}],[1],[],[{ABILITY}],[{ABILITY}]',
            f'10001,PLAYER_INFO,4,[{HEMORRHAGE}],[1],[],[{ABILITY}],[{ABILITY}]',
            _hit(11000, 3, 5000, 70), _hit(11000, 4, 5000, 70),
        ]
        _analyzer, fights = _run(base + fight)
        self.assertEqual(_masteries(fights[0], 3), ['Devout Guardian'])
        self.assertEqual(_masteries(fights[0], 4), [])
        self.assertEqual(_masteries(fights[0], 1), [])

    def test_session_cache_carries_a_fired_mastery(self):
        analyzer, _fights = _run(_fight(10000, [_gained(12000, UNBOUND_POTENTIAL, 1)], HEMORRHAGE))
        session = analyzer.player_sessions['@brainsnorkel+Arcanist']
        self.assertEqual(session['masteries'], ['Unbound Potential'])
        restored = analyzer._get_player_from_session('9', 'Arcanist', '@brainsnorkel')
        self.assertEqual(restored.masteries_seen, ['Unbound Potential'])
        self.assertEqual(restored.masteries(), ['Unbound Potential'])


if __name__ == '__main__':
    unittest.main()
