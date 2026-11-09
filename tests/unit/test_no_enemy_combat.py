#!/usr/bin/env python3
"""Combat with no enemy in it is not a fight: the game also enters combat
when the group hits a neutral unit or a neutral trap hits the group, and
such combat is held back at END_COMBAT unless a player dies in it or just
after (ESOLogAnalyzer._note_enemy_met).

The shapes are from the real logs: Vateshran Hollows' Brimstone Orbs
(monster 99123, NPC_NEUTRAL), hit for 0 by weapon enchants, area damage
and heavy attacks (2026-11-01); the Aetherian Archive's Shock Trap (monster
56034, NPC_NEUTRAL) hitting the group; and a Sunspire combat with no combat
event at all.
"""

import unittest

from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory

EPOCH = 1793499204071
BOSS_HEALTH = 1000000


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _unit(unit_id, health, maximum):
    return f"{unit_id},{health}/{maximum},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _boss(health=BOSS_HEALTH):
    return _unit(70, health, BOSS_HEALTH)


ORB = _unit(80, 1, 1)
TRAP = _unit(81, 0, 0)
METEOR = _unit(82, 14608, 14608)  # a hostile hazard named as its ability


def _event(ts, result, hit, source, target=None, ability=12345):
    """A COMBAT_EVENT line; *target* None writes the self-target '*'."""
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{hit},0,900,{ability},"
            f"{source},{target if target is not None else '*'}")


def _cast(ts, source, target, ability=12345):
    """A BEGIN_CAST line, written with its own time (the parser stamps 0)."""
    return f"{ts},BEGIN_CAST,0,F,901,{ability},{source},{target}"


def _died(ts, killer, player):
    return _event(ts, 'DIED', 0, killer, _player(player, 0))


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1227,"Vateshran Hollows",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,4,"Ok Beamer","@brainsnorkel",1001,50,3239,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},F,0,0,"Brimstone Warden","",0,50,160,0,HOSTILE,F',
    '2500,UNIT_ADDED,80,MONSTER,F,0,99123,F,0,0,"Brimstone Orb","",0,50,160,0,NPC_NEUTRAL,F',
    '2500,UNIT_ADDED,81,MONSTER,F,0,56034,F,0,0,"Storm","",0,50,160,0,NPC_NEUTRAL,F',
    '2500,UNIT_ADDED,82,MONSTER,F,0,122686,F,0,0,"Molten Destruction","",0,50,160,0,HOSTILE,F',
    '2600,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    '2600,ABILITY_INFO,219233,"Molten Destruction","/esoui/art/icons/ability_mage_065.dds",T,T',
    '2600,ABILITY_INFO,45549,"Grace","/esoui/art/icons/ability_armor_004.dds",T,T',
]


def _builds(ts, *players):
    """The PLAYER_INFO lines the game writes after each BEGIN_COMBAT."""
    return [f'{ts},PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in players]


def _orb_combat(begin):
    """The group breaks an orb: a heavy attack and its enchant for 0, a DoT
    tick; combat from *begin* for 8 s."""
    return [
        f'{begin},BEGIN_COMBAT',
        *_builds(begin + 1, 1, 2),
        _event(begin, 'DAMAGE', 0, _player(1), ORB, ability=17169),
        _event(begin, 'CRITICAL_DAMAGE', 0, _player(1), ORB, ability=17895),
        _event(begin + 2000, 'DOT_TICK', 0, _player(1), ORB, ability=62912),
        _event(begin + 3000, 'TARGET_DEAD', 0, _player(1), ORB),
        f'{begin + 8000},END_COMBAT',
    ]


ORB_COMBAT = _orb_combat(10000)


def _real_fight(begin, end, hit_at=None):
    hit_at = hit_at if hit_at is not None else begin + 1000
    return [f'{begin},BEGIN_COMBAT',
            *_builds(begin + 1, 1, 2),
            _event(hit_at, 'DAMAGE', 50000, _player(2), _boss(900000)),
            f'{end},END_COMBAT']


class Engine:

    def __init__(self):
        self.analyzer = ESOLogAnalyzer()
        self.analyzer.fight_history = FightHistory()
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
        return [event[0] for event in self.listener.events
                if event[0] in ('fight_completed', 'fight_updated')]


def _fights(*lines):
    return Engine().feed(lines).fights


class TestNotListed(unittest.TestCase):

    def test_breaking_an_orb(self):
        engine = Engine().feed(ORB_COMBAT)
        self.assertEqual(engine.fights, [])
        self.assertEqual(engine.events(), [])

    def test_a_neutral_trap_hitting_the_group(self):
        self.assertEqual(_fights('10000,BEGIN_COMBAT',
                                 _event(10500, 'DAMAGE', 7912, TRAP, _player(1, 12088)),
                                 _event(12500, 'DAMAGE', 4000, TRAP, _player(2, 16000)),
                                 '16000,END_COMBAT'), [])

    def test_combat_with_no_combat_event(self):
        self.assertEqual(_fights('10000,BEGIN_COMBAT', *_builds(10001, 1, 2),
                                 '40000,END_COMBAT'), [])

    def test_the_fights_around_it_are_kept(self):
        engine = Engine().feed(_real_fight(4000, 8000) + ORB_COMBAT + _real_fight(30000, 40000))
        self.assertEqual([f.duration_s for f in engine.fights], [4.0, 10.0])
        self.assertEqual(engine.events(), ['fight_completed', 'fight_completed'])

    def test_a_fight_right_after_is_a_fight_of_its_own(self):
        """Combat begins again a moment after the held combat ends: nothing
        is carried on (see COMBAT_RESUME_MS)."""
        fights = _fights(*ORB_COMBAT, *_real_fight(18100, 28000, hit_at=19000))
        self.assertEqual(len(fights), 1)
        self.assertAlmostEqual(fights[0].duration_s, 9.9)
        self.assertEqual(fights[0].boss_name, 'Brimstone Warden')

    def test_an_enemy_hit_before_the_last_fight_ended(self):
        """A hit before the previous END_COMBAT is that fight's, not the
        next combat's moments before its line (beyond COMBAT_RESUME_MS, so
        not the fight carrying on)."""
        fights = _fights(*_real_fight(4000, 9500, hit_at=9000), *_orb_combat(11000))
        self.assertEqual(len(fights), 1)
        self.assertAlmostEqual(fights[0].duration_s, 5.5)

    def test_a_death_long_after_it_ended(self):
        fights = _fights(*ORB_COMBAT, _died(25000, TRAP, 1))
        self.assertEqual(fights, [])

    def test_a_hazard_falling_on_a_player(self):
        """The Infinite Archive's Molten Destruction: a hostile unit named as
        its ability casts at the player, and nothing else happens."""
        self.assertEqual(_fights(_cast(9975, METEOR, _player(1), ability=219233),
                                 '10000,BEGIN_COMBAT',
                                 _event(11500, 'DAMAGE', 0, METEOR, _player(1), ability=219233),
                                 '16000,END_COMBAT'), [])

    def test_a_dead_enemys_lingering_damage(self):
        self.assertEqual(_fights('10000,BEGIN_COMBAT',
                                 _event(10500, 'DAMAGE', 900, _boss(0), _player(1, 19100)),
                                 '16000,END_COMBAT'), [])

    def test_an_enemys_damage_over_time_from_before(self):
        self.assertEqual(_fights('10000,BEGIN_COMBAT',
                                 _event(10500, 'DOT_TICK', 900, _boss(), _player(1, 19100)),
                                 '16000,END_COMBAT'), [])

    def test_a_cast_at_a_dead_enemy(self):
        self.assertEqual(_fights('10000,BEGIN_COMBAT', _cast(11000, _player(1), _boss(0)),
                                 '16000,END_COMBAT'), [])

    def test_swinging_at_a_corpse(self):
        self.assertEqual(_fights('10000,BEGIN_COMBAT',
                                 _event(11000, 'TARGET_DEAD', 0, _player(1), _boss(0)),
                                 _event(11500, 'DOT_TICK', 0, _player(1), _boss(0)),
                                 '16000,END_COMBAT'), [])

    def test_a_hazard_hitting_a_shielded_player(self):
        """A shield absorb names the shield; the line after it names the
        attack, the hazard's own ability."""
        self.assertEqual(_fights('10000,BEGIN_COMBAT',
                                 _event(11500, 'DAMAGE_SHIELDED', 3000, METEOR, _player(1),
                                        ability=99999),
                                 _event(11500, 'DAMAGE', 0, METEOR, _player(1), ability=219233),
                                 '16000,END_COMBAT'), [])

    def test_an_enemys_line_that_is_no_act(self):
        """The opener's monster acts are damage, misses and crowd control;
        any other line is no meeting."""
        self.assertEqual(_fights('10000,BEGIN_COMBAT',
                                 _event(11000, 'POWER_DRAIN', 300, _boss(), _player(1)),
                                 '16000,END_COMBAT'), [])

    def test_the_zones_first_combat_keeps_the_ten_seconds(self):
        """The zone's first encounter is reused from the zone's start, so it
        saw a hit 57 s before its line: too long ago to meet."""
        self.assertEqual(_fights(_event(3000, 'DAMAGE', 0, _player(2), _boss()),
                                 *_orb_combat(60000)), [])


class TestListed(unittest.TestCase):

    def test_a_monster_hitting_the_group(self):
        fights = _fights('10000,BEGIN_COMBAT',
                         _event(11000, 'DAMAGE', 3000, _boss(), _player(1, 17000)),
                         '16000,END_COMBAT')
        self.assertEqual(len(fights), 1)
        self.assertEqual(fights[0].group_dps, 0)

    def test_a_hit_on_an_enemy_for_nothing(self):
        """Any result or value counts: a boss immune to the hit is still met."""
        fights = _fights('10000,BEGIN_COMBAT',
                         _event(11000, 'IMMUNE', 0, _player(1), _boss()),
                         '16000,END_COMBAT')
        self.assertEqual(len(fights), 1)

    def test_a_cast_at_an_enemy(self):
        fights = _fights('10000,BEGIN_COMBAT', _cast(11000, _player(1), _boss()),
                         '16000,END_COMBAT')
        self.assertEqual(len(fights), 1)

    def test_the_group_hitting_a_hazard(self):
        """A hazard's own acts are a mechanic, but the group's hits on it,
        a hostile unit, are damage like any other."""
        fights = _fights('10000,BEGIN_COMBAT',
                         _event(11000, 'DAMAGE', 5000, _player(1), _unit(82, 9608, 14608)),
                         '16000,END_COMBAT')
        self.assertEqual(len(fights), 1)
        self.assertEqual(fights[0].group_dps, 5000)

    def test_the_killing_blow_on_an_enemy(self):
        """The hit that kills reads 0 health on its line and still counts."""
        fights = _fights('10000,BEGIN_COMBAT',
                         _event(11000, 'DAMAGE', 1000, _player(1), _boss(0)),
                         '16000,END_COMBAT')
        self.assertEqual(len(fights), 1)

    def test_an_enemy_casting_at_the_group(self):
        fights = _fights('10000,BEGIN_COMBAT', _cast(11000, _boss(), _player(2)),
                         '16000,END_COMBAT')
        self.assertEqual(len(fights), 1)

    def test_an_enemy_hit_just_before_the_line(self):
        """The group's first hits often land before BEGIN_COMBAT."""
        fights = _fights(_event(8000, 'DAMAGE', 50000, _player(2), _boss(950000)),
                         *ORB_COMBAT)
        self.assertEqual(len(fights), 1)

    def test_an_enemy_hit_long_before_the_line(self):
        fights = _fights(*_real_fight(4000, 8000),
                         _event(8500, 'DAMAGE', 50000, _player(2), _boss(850000)),
                         *_orb_combat(19000))
        # The real fight only: the hit between the two was 10.5 s before the line
        self.assertEqual(len(fights), 1)
        self.assertAlmostEqual(fights[0].duration_s, 4.0)

    def test_a_death_in_it(self):
        fights = _fights('10000,BEGIN_COMBAT',
                         _event(10500, 'DAMAGE', 20000, TRAP, _player(1, 0)),
                         _died(10501, TRAP, 1),
                         '11000,END_COMBAT')
        self.assertEqual(len(fights), 1)
        self.assertEqual(fights[0].deaths, 1)
        self.assertEqual([r['time_ms'] for r in fights[0].death_recaps], [501])

    def test_a_death_just_after_it_ended(self):
        """The blow that kills the last player standing ends combat, and the
        death is written after END_COMBAT (see LATE_DEATH_GRACE_MS)."""
        engine = Engine().feed([
            '10000,BEGIN_COMBAT',
            *_builds(10001, 1, 2),
            _event(15000, 'DAMAGE', 20000, TRAP, _player(1, 0)),
            '15010,END_COMBAT',
            _died(15095, TRAP, 1),
        ])
        self.assertEqual(len(engine.fights), 1)
        fight = engine.fights[0]
        # The fight as it ended, though the death line came after END_COMBAT
        self.assertAlmostEqual(fight.duration_s, 5.01)
        self.assertEqual(fight.deaths, 1)
        self.assertEqual([(r['name'], r['time_ms']) for r in fight.death_recaps],
                         [('@brainsnorkel', 5095)])
        self.assertEqual(engine.events(), ['fight_completed', 'fight_updated'])
        # Nothing of it is carried into the next fight
        engine.feed(_real_fight(30000, 40000))
        self.assertEqual([f.deaths for f in engine.fights], [1, 0])


END_TRIAL = 'END_TRIAL,12,600000,T,100000,30000'


class TestTrialResult(unittest.TestCase):
    """END_TRIAL in or after a held combat: the run was won in the last
    fight listed."""

    def test_in_a_held_combat(self):
        engine = Engine().feed([*_real_fight(4000, 9000), '11000,BEGIN_COMBAT',
                                f'17000,{END_TRIAL}', '18000,END_COMBAT'])
        self.assertEqual(len(engine.fights), 1)
        self.assertEqual(engine.fights[0].trial_result['score'], 100000)
        self.assertEqual(engine.events(), ['fight_completed', 'fight_updated'])

    def test_just_after_a_held_combat(self):
        engine = Engine().feed([*_real_fight(4000, 9000), '11000,BEGIN_COMBAT',
                                '12000,END_COMBAT', f'13000,{END_TRIAL}'])
        self.assertEqual(len(engine.fights), 1)
        self.assertEqual(engine.fights[0].trial_result['score'], 100000)

    def test_with_no_fight_listed_the_held_combat_carries_it(self):
        engine = Engine().feed(['11000,BEGIN_COMBAT', f'17000,{END_TRIAL}', '18000,END_COMBAT'])
        self.assertEqual(len(engine.fights), 1)
        self.assertEqual(engine.fights[0].trial_result['score'], 100000)


if __name__ == '__main__':
    unittest.main()
