#!/usr/bin/env python3
"""Death recaps: the last seconds of damage and healing before each player
death, as the engine hands them to frontends (FightHistoryEntry.death_recaps).

The log shapes exercised here were taken from live trial and arena logs: the
killing blow written after its DIED line, shields written before the hit they
absorbed, and the last player's death written after END_COMBAT.
"""

import unittest

from death_recap import (  # noqa: E402
    KILLING_BLOW_GRACE_MS, DeathRecapRecorder,
)
from engine_events import RecordingListener  # noqa: E402
from esolog_tail import LATE_DEATH_GRACE_MS, ESOLogAnalyzer, FightHistory  # noqa: E402

EPOCH = 1755729685851
# The window these fixtures were written for (the default of issue #95; it
# is 3 seconds since #133, which test_death_recap_window covers)
FIVE_S_MS = 5000

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
    analyzer.death_recap_recorder.window_ms = FIVE_S_MS
    listener = RecordingListener()
    analyzer.add_listener(listener)
    _feed(analyzer, BASE + lines)
    return analyzer, listener


def _feed(analyzer, lines):
    for line in lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)


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


def _press(ts, unit, ability, track, health=19000):
    """A BEGIN_CAST by the player *unit* on its own track."""
    return f"{ts},BEGIN_CAST,0,F,{track},{ability},{_player(unit, health)},*"


class TestCastsInTheRecap(unittest.TestCase):
    """Issue #214: the dying player's own casts in the recap's window."""

    def test_the_players_casts_in_the_window(self):
        light, meridias_favor = 18350, 117119
        analyzer, _ = _run([
            '2600,ABILITY_INFO,18350,"Light Attack (Lightning)","/esoui/art/icons/x.dds",F,T',
            '10000,BEGIN_COMBAT',
            _press(13000, 1, 40079, 1),                    # older than the 5 s window
            _press(16000, 1, light, 2),
            _press(17500, 1, 40079, 3),
            _press(18000, 2, 40079, 4),                    # another player's
            # A proc written again on its track after END_CAST (casts.py)
            _press(18200, 1, meridias_favor, 5), f"18200,END_CAST,COMPLETED,5,{meridias_favor}",
            _press(19200, 1, meridias_favor, 5), f"19200,END_CAST,COMPLETED,5,{meridias_favor}",
            _event(20000, 'DIED', 0, BOSS, _player(1, 0), cast=901),
            _event(20001, 'DAMAGE', 15000, BOSS, _player(1, 0), overflow=3000, cast=901),
            '70000,END_COMBAT',
        ])
        recap = analyzer.fight_history.fights[0].death_recaps[0]
        self.assertEqual(recap['casts'], [
            {'offset_ms': -4000, 'ability_id': '18350', 'ability': 'Light Attack (Lightning)',
             'icon': 'x', 'kind': 'light'},
            {'offset_ms': -2500, 'ability_id': '40079', 'ability': 'Radiating Regeneration',
             'icon': 'ability_restorationstaff_002b', 'kind': ''},
        ])
        # The hits and heals are as before
        self.assertEqual([r['result'] for r in recap['events']], ['DAMAGE'])


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
            _event(15000, 'DAMAGE', 719, BOSS, _player(1, 19281)),
            '20000,END_COMBAT',
            _event(20000 + LATE_DEATH_GRACE_MS + 1, 'DIED', 0, NO_UNIT, _player(1, 0)),
            '100000,BEGIN_COMBAT',
            _event(110000, 'DAMAGE', 719, BOSS, _player(2, 19281)),
            '130000,END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        self.assertEqual((first.deaths, first.death_recaps), (0, []))
        self.assertEqual((second.deaths, second.death_recaps), (0, []))
        self.assertEqual(listener.of_kind('fight_updated'), [])


def _fall(ts, target):
    """A fall into lava or off the map, as the log writes it (issue #184):
    no source, ability or cast, the dying unit as the target."""
    return f"{ts},COMBAT_EVENT,KILLED_BY_SUBZONE,GENERIC,0,0,0,0,0,{NO_UNIT},{target}"


class TestFallDeaths(unittest.TestCase):
    """A fall is one KILLED_BY_SUBZONE line, with no DIED (issue #184)."""

    def test_a_fall_in_a_fight_is_a_death_to_a_fall_or_lava(self):
        from death_recap import FALL_CAUSE, FALL_DEATH
        from pull_outcome import first_death_text
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            # A hit of ability 0, as the fall's own id: still not the killer
            _event(16000, 'DAMAGE', 3000, BOSS, _player(1, 17000), ability=0),
            _fall(17000, _player(1, 0)),
            '17026,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.deaths, 1)
        self.assertEqual(analyzer.zone_deaths, 1)
        recap = fight.death_recaps[0]
        self.assertEqual((recap['name'], recap['time_ms'], recap['max_health']),
                         ('@brainsnorkel', 7000, 20000))
        self.assertEqual((recap['killer'], recap['ability'], recap['ability_id'],
                          recap['icon'], recap['cause']),
                         ('', FALL_DEATH, '0', '', FALL_CAUSE))
        # The boss's hit stays in the window and is not taken for the killer
        self.assertEqual([(r['source'], r['amount']) for r in recap['events']],
                         [('Test Boss', 3000)])
        self.assertIn('1', fight.time_dead)
        self.assertEqual(first_death_text(fight),
                         f'First death: @brainsnorkel to {FALL_DEATH} at 0:07 · 1 death')

    def test_any_other_death_has_no_cause(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(15000, 'DIED', 0, BOSS, _player(1, 0)),
            '70000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].death_recaps[0]['cause'], '')

    def test_a_fall_just_after_end_combat_joins_the_fight(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(15000, 'DAMAGE', 719, BOSS, _player(1, 19281)),
            '20000,END_COMBAT',
            _fall(20026, _player(1, 0)),
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)

    def test_a_fall_outside_a_fight_belongs_to_no_fight(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(15000, 'DAMAGE', 719, BOSS, _player(1, 19281)),
            '20000,END_COMBAT',
            _fall(50000, _player(1, 0)),
            '100000,BEGIN_COMBAT',
            _event(110000, 'DAMAGE', 719, BOSS, _player(2, 19281)),
            '130000,END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        self.assertEqual((first.deaths, first.death_recaps), (0, []))
        self.assertEqual((second.deaths, second.death_recaps), (0, []))

    def test_a_fall_before_the_pull_then_seen_alive_leaves_no_time_dead(self):
        """The 17 falls outside a fight in the logs: the player's own lines
        (a regeneration tick) show them up again before the next pull."""
        analyzer, _ = _run([
            _fall(5000, _player(1, 0)),
            _event(15000, 'POWER_ENERGIZE', 200, _player(1, 20000)),
            '30000,BEGIN_COMBAT',
            _event(35000, 'DAMAGE', 3000, BOSS, _player(1, 17000)),
            '60000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual((fight.deaths, fight.death_recaps), (0, []))
        self.assertEqual(fight.time_dead, {})

    def test_an_enemys_fall_is_not_its_death(self):
        """None is in the logs, and one would read as the group's kill."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 500, _player(1, 20000), BOSS),
            _fall(15000, BOSS),
            '70000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual((fight.deaths, fight.death_recaps), (0, []))
        self.assertIsNone(analyzer.current_encounter.enemies['70'].died_at)


class TestRecorder(unittest.TestCase):
    """DeathRecapRecorder on its own: the window and the killing-blow grace."""

    def setUp(self):
        self.recorder = DeathRecapRecorder(
            lambda unit_id: {'70': 'Boss'}.get(unit_id, ''),
            lambda ability_id: (f'Ability {ability_id}', ''), window_ms=FIVE_S_MS)

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
        self.assertGreaterEqual(recap['events'][0]['offset_ms'], -FIVE_S_MS)

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


def _typed(ts, result, damage_type, hit, source, target=None, overflow=0, cast=900,
           ability=12437):
    """A COMBAT_EVENT line with its damage type (see damage_kinds)."""
    return (f"{ts},COMBAT_EVENT,{result},{damage_type},1,{hit},{overflow},{cast},{ability},"
            f"{source},{target if target is not None else '*'}")


PLAYER_INFO = [f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12437],[12437]' for unit in (1, 2)]


def _taken(analyzer, fight_index, unit_id):
    fight = analyzer.fight_history.fights[fight_index]
    return next(p for p in fight.players if p['unit_id'] == unit_id)['taken']


class TestKindsInTheRecap(unittest.TestCase):
    """Each row's damage type and area rule, the recap's overheal sum, and
    the player's whole-fight tally of damage taken (damage_kinds)."""

    def test_rows_carry_their_kinds_and_the_fight_is_tallied(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT', *PLAYER_INFO,
            # One cast of the boss lands on both players: area
            _typed(15000, 'DAMAGE', 'SHOCK', 3000, BOSS, _player(1, 17000), cast=901),
            _typed(15000, 'DAMAGE', 'SHOCK', 3000, BOSS, _player(2, 17000), cast=901),
            _typed(17000, 'DOT_TICK', 'FIRE', 1000, BOSS, _player(1, 16000), cast=902, ability=777),
            # A pure overheal (no row, but counted) and a HoT that landed
            _typed(18000, 'HEAL', 'GENERIC', 0, _player(2, 20000), _player(1, 16000),
                   overflow=5000, cast=903, ability=40079),
            _typed(18500, 'HOT_TICK', 'GENERIC', 500, _player(2, 20000), _player(1, 16500),
                   overflow=200, cast=904, ability=40079),
            _typed(19000, 'DAMAGE_SHIELDED', 'GENERIC', 800, BOSS, _player(1, 16500),
                   cast=905, ability=555),
            _typed(20000, 'DIED', 'COLD', 0, BOSS, _player(1, 0), cast=906),
            _typed(20001, 'DAMAGE', 'COLD', 16500, BOSS, _player(1, 0), overflow=2000, cast=906),
            # The killing cast lands on the other player too, within the grace
            _typed(20050, 'DAMAGE', 'COLD', 16500, BOSS, _player(2, 500), cast=906),
            '70000,END_COMBAT',
        ])
        recap = analyzer.fight_history.fights[0].death_recaps[0]
        rows = recap['events']
        self.assertEqual([r['result'] for r in rows],
                         ['DAMAGE', 'DOT_TICK', 'HOT_TICK', 'DAMAGE_SHIELDED', 'DAMAGE'])
        self.assertEqual([r['damage_type'] for r in rows],
                         ['SHOCK', 'FIRE', 'GENERIC', 'GENERIC', 'COLD'])
        self.assertEqual([(r['area'], r['area_rule'], r['targets_hit']) for r in rows],
                         [(True, 'cast', 2), (False, 'none', 1), (False, '', 0),
                          (False, '', 0), (True, 'cast', 2)])
        self.assertEqual(recap['overheal'], 5200)
        self.assertEqual((rows[2]['amount'], rows[2]['overflow']), (500, 200))

        taken = _taken(analyzer, 0, '1')
        self.assertEqual(taken['total'], 20500)
        self.assertEqual((taken['direct'], taken['dot'], taken['fall']), (19500, 1000, 0))
        # The killing blow was counted single until its cast struck player 2
        self.assertEqual((taken['area'], taken['single']), (19500, 1000))
        self.assertEqual((taken['martial'], taken['magical'], taken['oblivion']), (0, 20500, 0))
        self.assertEqual(taken['types'], {'shock': 3000, 'fire': 1000, 'frost': 16500})
        # The blow's ability had struck both players on cast 901, so the
        # tally classed it by the session as it landed; the row, classed
        # again once cast 906 struck player 2, reads the cast
        self.assertEqual(taken['rules'], {'cast': 3000, 'session': 16500, 'none': 1000})
        self.assertEqual((taken['absorbed'], taken['healed'], taken['heal_hot'],
                          taken['heal_direct'], taken['overheal'], taken['overkill']),
                         (800, 500, 500, 0, 5200, 2000))
        self.assertEqual((taken['first_ms'], taken['last_ms']), (15000, 20001))
        self.assertEqual([(a['name'], a['damage'], a['area'], a['source']) for a in taken['abilities']],
                         [('Toppling Blow', 19500, 19500, 'Test Boss'),
                          ('Ability 777', 1000, 0, 'Test Boss')])
        self.assertEqual(taken['abilities'][1]['types'], {'fire': 1000})
        other = _taken(analyzer, 0, '2')
        self.assertEqual((other['total'], other['area'], other['overkill']), (19500, 19500, 0))

    def test_a_late_hit_of_the_same_cast_reclasses_the_row_when_the_fight_ends(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT', *PLAYER_INFO,
            _typed(19000, 'DAMAGE', 'SHOCK', 5000, BOSS, _player(1, 15000), cast=950),
            _typed(20000, 'DIED', 'PHYSICAL', 0, BOSS, _player(1, 0), cast=951, ability=778),
            _typed(20001, 'DAMAGE', 'PHYSICAL', 15000, BOSS, _player(1, 0), overflow=100,
                   cast=951, ability=778),
            # Five seconds on, the same ground effect reaches the other player
            _typed(25000, 'DAMAGE', 'SHOCK', 5000, BOSS, _player(2, 15000), cast=950),
            '70000,END_COMBAT',
        ])
        rows = analyzer.fight_history.fights[0].death_recaps[0]['events']
        self.assertEqual([(r['area'], r['area_rule'], r['targets_hit']) for r in rows],
                         [(True, 'cast', 2), (False, 'none', 1)])
        taken = _taken(analyzer, 0, '1')
        self.assertEqual((taken['area'], taken['single']), (5000, 15000))

    def test_a_repeat_pull_reads_the_ability_as_area_from_the_session(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT', *PLAYER_INFO,
            _typed(15000, 'DAMAGE', 'FIRE', 4000, BOSS, _player(1, 16000), cast=960, ability=888),
            _typed(15000, 'DAMAGE', 'FIRE', 4000, BOSS, _player(2, 16000), cast=960, ability=888),
            '30000,END_COMBAT',
            '100000,BEGIN_COMBAT', *PLAYER_INFO,
            _typed(105000, 'DAMAGE', 'FIRE', 4000, BOSS, _player(1, 16000), cast=970, ability=888),
            _typed(106000, 'DIED', 'FIRE', 0, BOSS, _player(1, 0), cast=971),
            _typed(106001, 'DAMAGE', 'FIRE', 16000, BOSS, _player(1, 0), overflow=10, cast=971),
            '130000,END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        rows = second.death_recaps[0]['events']
        self.assertEqual([(r['area'], r['area_rule'], r['targets_hit']) for r in rows],
                         [(True, 'session', 1), (False, 'none', 1)])
        # Each fight's tally is its own
        self.assertEqual(_taken(analyzer, 0, '1')['total'], 4000)
        self.assertEqual(_taken(analyzer, 1, '1')['total'], 20000)
        self.assertEqual(_taken(analyzer, 1, '1')['rules'], {'session': 4000, 'none': 16000})

    def test_a_players_own_skill_falls_back_to_the_bundled_table(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT', *PLAYER_INFO,
            _typed(17000, 'DAMAGE', 'MAGIC', 2000, _player(2, 20000), _player(1, 18000),
                   cast=980, ability=28800),     # Impulse: Area in the table
            _typed(18000, 'DAMAGE', 'MAGIC', 2000, _player(2, 20000), _player(1, 16000),
                   cast=981, ability=46324),     # Crystal Fragments: Enemy
            _typed(19000, 'DAMAGE', 'MAGIC', 2000, _player(2, 20000), _player(1, 14000),
                   cast=982, ability=999999),    # a player ability the table lacks
            _typed(19500, 'DAMAGE', 'MAGIC', 2000, BOSS, _player(1, 12000),
                   cast=983, ability=28800),     # a monster never asks the table
            _typed(20000, 'DIED', 'MAGIC', 0, BOSS, _player(1, 0), cast=984),
            _typed(20001, 'DAMAGE', 'MAGIC', 12000, BOSS, _player(1, 0), cast=984),
            '70000,END_COMBAT',
        ])
        rows = analyzer.fight_history.fights[0].death_recaps[0]['events']
        self.assertEqual([(r['area'], r['area_rule']) for r in rows],
                         [(True, 'table'), (False, 'table'), (False, 'none'),
                          (False, 'none'), (False, 'none')])
        self.assertEqual(_taken(analyzer, 0, '1')['rules'], {'table': 4000, 'none': 16000})


# Any line a second on, which lets a wait at 0 health run out (the boss on
# itself: no player's state on it)
def _tick(ts):
    return _event(ts, 'DAMAGE', 300, BOSS)


def _effect(ts, source, target=None, ability=40079):
    """An EFFECT_CHANGED line; *target* None writes the self-target '*'."""
    return (f"{ts},EFFECT_CHANGED,GAINED,1,950,{ability},{source},"
            f"{target if target is not None else '*'}")


def _cast(ts, source, target=None, ability=12437):
    """A BEGIN_CAST line (instant, not channelled)."""
    return f"{ts},BEGIN_CAST,0,F,960,{ability},{source},{target if target is not None else '*'}"


def _regen(ts, regen, unit):
    """A HEALTH_REGEN line: the regeneration, then the unit's state."""
    return f"{ts},HEALTH_REGEN,{regen},{unit}"


class TestDeathsWithNoDeathLine(unittest.TestCase):
    """About one death in thirteen has no DIED, KILLING_BLOW or KILLED_BY_SUBZONE:
    the player's state reads 0 and stays there (issue #221)."""

    def test_a_player_at_zero_for_a_second_with_no_death_line_died(self):
        from death_recap import HEALTH_CAUSE
        from pull_outcome import first_death_text
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(15000, 'DAMAGE', 3000, BOSS, _player(1, 17000)),
            # The blow: a hit of 0 with the overkill in the overflow, and no
            # death line after it
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=17000, cast=901),
            _event(16400, 'DAMAGE', 500, BOSS, _player(1, 0), cast=902),     # on the corpse
            _tick(17200),
            # Resurrected: the state shows health again
            _event(25000, 'HEAL', 4000, _player(2, 20000), _player(1, 4000), ability=40079),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual((fight.deaths, analyzer.zone_deaths), (1, 1))
        recap = fight.death_recaps[0]
        self.assertEqual((recap['unit_id'], recap['name'], recap['time_ms']),
                         ('1', '@brainsnorkel', 6000))
        self.assertEqual((recap['killer'], recap['ability'], recap['cause'], recap['max_health']),
                         ('Test Boss', 'Toppling Blow', HEALTH_CAUSE, 20000))
        # The window up to the blow; the hit on the corpse is left out, as a
        # death line's later hits are
        self.assertEqual([(r['offset_ms'], r['amount'], r['overflow']) for r in recap['events']],
                         [(-1000, 3000, 0), (0, 0, 17000)])
        # Dead from the first 0 until the state showed health
        self.assertEqual(fight.time_dead.get('1'), 9000)
        self.assertEqual(first_death_text(fight),
                         'First death: @brainsnorkel to Toppling Blow (Test Boss) at 0:06 · 1 death')

    def test_a_blip_at_zero_is_no_death(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500),
            _event(16300, 'HEAL', 3000, _player(2, 20000), _player(1, 3000), ability=40079),
            _tick(18000),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual((fight.deaths, fight.death_recaps, fight.time_dead), (0, [], {}))

    def test_a_death_line_after_the_zero_names_the_death_once(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500, cast=901),
            _event(16002, 'DIED', 0, BOSS, _player(1, 0), cast=901),
            _tick(18000),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.deaths, 1)
        self.assertEqual([r['cause'] for r in fight.death_recaps], [''])

    def test_a_death_line_after_the_hold_is_the_same_death(self):
        from death_recap import HEALTH_CAUSE
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500, cast=901),
            _tick(17100),                                              # counted here
            _event(17500, 'DIED', 0, BOSS, _player(1, 0), cast=901),   # the same death
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual((fight.deaths, analyzer.zone_deaths), (1, 1))
        self.assertEqual([r['cause'] for r in fight.death_recaps], [HEALTH_CAUSE])

    def test_a_second_death_after_a_revive_still_counts(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500, cast=901),
            _tick(17100),
            _event(25000, 'HEAL', 4000, _player(2, 20000), _player(1, 4000), ability=40079),
            _event(28000, 'DIED', 0, BOSS, _player(1, 0), cast=905),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 2)

    def test_a_corpse_at_zero_after_its_death_line_is_no_second_death(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DIED', 0, BOSS, _player(1, 0), cast=901),
            _event(16001, 'DAMAGE', 20000, BOSS, _player(1, 0), overflow=10, cast=901),
            _event(18000, 'DAMAGE', 500, BOSS, _player(1, 0), cast=902),
            _tick(20000),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)

    def test_the_recaps_stay_in_time_order(self):
        """A death read from 0 health is counted a second late, after a
        death line that came while it waited."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500, cast=901),
            _event(16500, 'DIED', 0, BOSS, _player(2, 0), cast=903),
            _tick(17100),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual([(r['unit_id'], r['time_ms']) for r in fight.death_recaps],
                         [('1', 6000), ('2', 6500)])

    def test_at_zero_as_combat_ends_joins_the_fight_after_the_grace(self):
        """No death line in the late-death grace either: the death joins the
        fight that ended, as a death logged just after it would."""
        from death_recap import HEALTH_CAUSE
        analyzer, listener = _run([
            '10000,BEGIN_COMBAT',
            _event(19900, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=1224),
            '20000,END_COMBAT',
            _tick(21000),
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.deaths, 1)
        recap = fight.death_recaps[0]
        self.assertEqual((recap['time_ms'], recap['cause']), (9900, HEALTH_CAUSE))
        self.assertEqual(len(listener.of_kind('fight_updated')), 1)
        # Dead from the first 0 to the fight's end
        self.assertEqual(fight.time_dead.get('1'), 100)

    def test_at_zero_as_combat_ends_then_up_again_is_no_death(self):
        analyzer, listener = _run([
            '10000,BEGIN_COMBAT',
            _event(19900, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=10),
            '20000,END_COMBAT',
            _event(20300, 'HEAL', 3000, _player(2, 20000), _player(1, 3000), ability=40079),
            _tick(21500),
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 0)
        self.assertEqual(listener.of_kind('fight_updated'), [])

    def test_at_zero_as_combat_ends_and_nothing_after_until_the_next_pull(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(19900, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=10),
            '20000,END_COMBAT',
            '90000,BEGIN_COMBAT',
            _event(95000, 'DAMAGE', 719, BOSS, _player(2, 19281)),
            '99000,END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        self.assertEqual((first.deaths, second.deaths), (1, 0))

    def test_a_death_first_seen_on_an_effect_line(self):
        """Nearly a third of these deaths show the first 0 on an effect's or
        a cast's line; with no hit within 3 s the killer is unknown."""
        from death_recap import HEALTH_CAUSE, NO_HIT_DEATH
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 3000, BOSS, _player(1, 17000)),    # 4 s before
            _effect(16000, BOSS, _player(1, 0)),
            _effect(16500, _player(1, 0)),
            _tick(17200),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.deaths, 1)
        recap = fight.death_recaps[0]
        self.assertEqual((recap['time_ms'], recap['cause'], recap['ability'], recap['killer']),
                         (6000, HEALTH_CAUSE, NO_HIT_DEATH, ''))

    def test_a_hit_within_three_seconds_names_the_killer(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(14500, 'DAMAGE', 15000, BOSS, _player(1, 5000)),
            _effect(16000, BOSS, _player(1, 0)),
            _tick(17200),
            '30000,END_COMBAT',
        ])
        recap = analyzer.fight_history.fights[0].death_recaps[0]
        self.assertEqual((recap['killer'], recap['ability']), ('Test Boss', 'Toppling Blow'))

    def test_the_blow_just_after_an_effect_line_names_the_killer(self):
        """The 0 first shows on an effect's line and the killing blow comes
        1 ms later: the blow names the death, not 'an unknown cause'."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _effect(16000, BOSS, _player(1, 0)),
            _event(16001, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=8000, cast=901),
            _tick(17200),
            '30000,END_COMBAT',
        ])
        recap = analyzer.fight_history.fights[0].death_recaps[0]
        self.assertEqual((recap['time_ms'], recap['killer'], recap['ability']),
                         (6000, 'Test Boss', 'Toppling Blow'))

    def test_a_death_first_seen_on_a_cast_line_takes_the_lines_time(self):
        """The parser stamps BEGIN_CAST with 0: the line's own time counts."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _cast(16000, BOSS, _player(1, 0)),
            _tick(17200),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual([r['time_ms'] for r in fight.death_recaps], [6000])

    def test_a_corpse_tick_is_no_revive(self):
        """A dead player's regeneration tick writes health equal to its own
        regeneration, and later lines repeat that stale value."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500, cast=901),
            _regen(16001, 894, _player(1, 894)),
            _event(16500, 'DAMAGE', 0, BOSS, _player(1, 894)),
            _tick(17200),
            _event(19000, 'DAMAGE', 0, BOSS, _player(1, 894)),
            _event(25000, 'HEAL', 4000, _player(2, 20000), _player(1, 4000), ability=40079),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(fight.deaths, 1)
        # Dead until the resurrection, not until the stale value came back
        self.assertEqual(fight.time_dead.get('1'), 9000)

    def test_a_corpse_tick_after_a_death_line_is_no_revive(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DIED', 0, BOSS, _player(1, 0), cast=901),
            _regen(16001, 894, _player(1, 894)),
            _event(19000, 'DAMAGE', 0, BOSS, _player(1, 894)),
            _event(25000, 'HEAL', 4000, _player(2, 20000), _player(1, 4000), ability=40079),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual((fight.deaths, fight.time_dead.get('1')), (1, 9000))

    def test_a_corpse_from_before_the_pull_is_no_death(self):
        analyzer, _ = _run([
            _event(5000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=10),
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 0, BOSS, _player(1, 0)),
            _tick(14000),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 0)

    def test_a_death_line_well_after_one_read_from_zero_is_a_new_death(self):
        """Past ZERO_LINE_SAME_MS a death line is a death of its own, the
        player's revive not having been seen."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500, cast=901),
            _tick(17100),
            _event(23000, 'DIED', 0, BOSS, _player(1, 0), cast=905),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 2)

    def test_a_revive_seen_only_on_an_effect_ends_the_follow(self):
        """Time dead's revive reads only combat events; the follow at 0
        health ends on any line, so the next death is still read."""
        from death_recap import HEALTH_CAUSE
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DIED', 0, BOSS, _player(1, 0), cast=901),
            _effect(25000, _player(2, 20000), _player(1, 6000)),
            _event(28000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=900, cast=906),
            _tick(29200),
            '30000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual([r['cause'] for r in fight.death_recaps], ['', HEALTH_CAUSE])

    def test_a_corpse_with_no_magicka_or_stamina_is_no_revive(self):
        """The dead player's own healing tick writes health on the corpse,
        magicka and stamina both at 0."""
        corpse = "1,400/20000,0/26657,0/13021,500/500,1000/1000,0,0.2,0.5,5.5"
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500),
            _event(16300, 'HOT_TICK', 400, _player(2, 20000), corpse, ability=40079),
            _tick(17200),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)

    def test_no_wait_starts_on_a_resurrection_line(self):
        """The accept line shows the corpse being raised at 0: a death not
        seen before it is not dated there."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 500, BOSS, _player(2, 19500)),    # the group met the boss
            _event(16000, 'SOUL_GEM_RESURRECTION_ACCEPTED', 0, _player(2, 20000), _player(1, 0)),
            _tick(17200),
            _event(18500, 'HEAL', 4000, _player(2, 20000), _player(1, 4000), ability=40079),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 0)

    def test_a_player_outside_the_group_is_not_watched(self):
        analyzer, _ = _run([
            ('2100,UNIT_ADDED,3,PLAYER,F,3,0,F,6,1,"Passer By","@passer",'
             '1708524619155578001,50,787,0,PLAYER_ALLY,F'),
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(3, 0), overflow=500),
            _tick(17200),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 0)

    def test_the_tome_hold_polymorph_is_no_death(self):
        """The Infinite Archive's minigame form has no stamina pool; it is
        knocked to 0 and restored when the minigame ends."""
        form = "1,0/4501,0/0,0/0,0/0,0/0,0,0.2,0.5,5.5"
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, form, overflow=500),
            _tick(17200),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 0)

    def test_the_hold_cuts_no_row_from_the_recap(self):
        """The recap is built a second late: the corpse's heals meanwhile
        must not push the window's oldest hit out of the history."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(11500, 'DAMAGE', 1000, BOSS, _player(1, 19000)),     # 4.5 s before
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500),
            _event(16600, 'HOT_TICK', 0, _player(2, 20000), _player(1, 0), ability=40079),
            _tick(17200),
            '30000,END_COMBAT',
        ])
        rows = analyzer.fight_history.fights[0].death_recaps[0]['events']
        self.assertEqual([r['offset_ms'] for r in rows], [-4500, 0])

    def test_a_death_with_no_hit_keeps_the_players_max_health(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 500, BOSS, _player(2, 19500)),
            _effect(16000, BOSS, _player(1, 0)),
            _tick(17200),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].death_recaps[0]['max_health'], 20000)

    def test_a_first_zero_in_the_late_grace_joins_the_fight_that_ended(self):
        """As a death line just after END_COMBAT does."""
        analyzer, listener = _run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 500, _player(1, 20000), BOSS),
            '20000,END_COMBAT',
            _event(20300, 'DAMAGE', 0, BOSS, _player(2, 0), overflow=500),
            _tick(21500),
        ])
        fight = analyzer.fight_history.fights[0]
        self.assertEqual([(r['unit_id'], r['time_ms']) for r in fight.death_recaps], [('2', 10300)])
        self.assertEqual(len(listener.of_kind('fight_updated')), 1)

    def test_the_late_path_replaces_the_recap_list(self):
        """A frontend may be reading the entry's list: a late death gives
        the entry a new one."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 500, _player(1, 20000), BOSS),
            _event(19900, 'DAMAGE', 0, BOSS, _player(2, 0), overflow=500),
            '20000,END_COMBAT',
        ])
        fight = analyzer.fight_history.fights[0]
        sent = fight.death_recaps
        _feed(analyzer, [_tick(21000)])
        self.assertIsNot(fight.death_recaps, sent)
        self.assertEqual((len(sent), len(fight.death_recaps)), (0, 1))

    def test_a_death_while_the_group_fights_on_joins_the_fight_it_carries_on(self):
        """The logging player dies, combat ends for the log, the group
        fights on and the fight carries on: a death between the lines with
        no death line is the fight's, as one with a line is (#162)."""
        boss = "72,{h}/287485,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"
        lines = [('2100,UNIT_ADDED,3,PLAYER,F,3,0,F,6,1,"Third Friend","@third",'
                  '1708524619155578002,50,787,0,PLAYER_ALLY,T'),
                 '2600,UNIT_ADDED,72,MONSTER,F,0,105636,T,0,0,"Big Boss","",0,50,160,0,HOSTILE,F',
                 '10000,BEGIN_COMBAT']
        health = 280000
        hits = []
        for ts in list(range(11000, 29000, 1000)) + list(range(30000, 60000, 1000)):
            hits.append(_event(ts, 'DAMAGE', 1000, _player(3, 20000), boss.format(h=health)))
            health -= 1000
        hits += [
            _event(20000, 'DIED', 0, BOSS, _player(1, 0)),
            _event(31000, 'DAMAGE', 0, BOSS, _player(2, 0), overflow=7000),
            _event(40200, 'HEAL', 5000, _player(3, 20000), _player(1, 5000), ability=40079),
        ]
        hits.sort(key=lambda line: int(line.split(',')[0]))
        lines += [h for h in hits if int(h.split(',')[0]) < 29000] + ['29000,END_COMBAT']
        lines += [h for h in hits if 29000 < int(h.split(',')[0]) < 40500] + ['40500,BEGIN_COMBAT']
        lines += [h for h in hits if int(h.split(',')[0]) > 40500] + ['60000,END_COMBAT']
        analyzer, _ = _run(lines)
        fight, = analyzer.fight_history.fights
        self.assertEqual(sorted(r['unit_id'] for r in fight.death_recaps), ['1', '2'])
        self.assertEqual((fight.time_dead.get('2'), fight.pull['dead_at_end']), (29000, ['2']))

    def test_a_new_fight_inside_the_hold_leaves_the_death_in_the_fight_that_ended(self):
        add = "71,{h}/5000,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"
        analyzer, _ = _run([
            '2600,UNIT_ADDED,71,MONSTER,F,0,105635,F,0,0,"Test Add","",0,50,160,0,HOSTILE,F',
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 2000, _player(1, 20000), add.format(h=3000)),
            _event(19500, 'DAMAGE', 0, BOSS, _player(2, 0), overflow=500),
            _event(19600, 'DIED_XP', 0, _player(1, 20000), add.format(h=0)),
            '19800,END_COMBAT',
            '20200,BEGIN_COMBAT',
            _event(20300, 'DAMAGE', 500, BOSS, _player(1, 19500)),
            _event(26000, 'DAMAGE', 500, BOSS, _player(1, 19000)),
            '40000,END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        self.assertEqual((first.deaths, second.deaths), (1, 0))

    def test_a_player_back_on_a_new_unit_id_can_die_again(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(15000, 'DIED', 0, BOSS, _player(2, 0)),
            '20000,UNIT_REMOVED,2',
            ('30000,UNIT_ADDED,12,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",'
             '1708524619155578000,50,787,0,PLAYER_ALLY,T'),
            _event(31000, 'HEAL', 4000, _player(1, 20000), _player(12, 20000), ability=40079),
            _event(40000, 'DAMAGE', 0, BOSS, _player(12, 0), overflow=900),
            _tick(41200),
            '50000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 2)

    def test_back_on_a_new_unit_id_with_no_removal_can_die_again(self):
        """No UNIT_REMOVED for the old unit: the player's health on the new
        one, read from a combat line, still ends the old follow."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(15000, 'DIED', 0, BOSS, _player(2, 0)),
            ('30000,UNIT_ADDED,12,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",'
             '1708524619155578000,50,787,0,PLAYER_ALLY,T'),
            _event(31000, 'HEAL', 4000, _player(1, 20000), _player(12, 20000), ability=40079),
            _event(40000, 'DAMAGE', 0, BOSS, _player(12, 0), overflow=900),
            _tick(41200),
            '50000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 2)

    def test_strangers_are_not_followed(self):
        """A player outside the group: their death line counts as before,
        with no follow and no corpse value kept."""
        analyzer, _ = _run([
            ('2100,UNIT_ADDED,3,PLAYER,F,3,0,F,6,1,"Passer By","@passer",'
             '1708524619155578001,50,787,0,PLAYER_ALLY,F'),
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 500, BOSS, _player(2, 19500)),
            _event(16000, 'DIED', 0, BOSS, _player(3, 0)),
            _regen(16001, 894, _player(3, 894)),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)
        self.assertEqual((analyzer._at_zero, analyzer._corpse_health), ({}, {}))

    def test_a_corpse_with_no_pools_after_a_death_line_is_no_revive(self):
        corpse = "1,400/20000,0/26657,0/13021,500/500,1000/1000,0,0.2,0.5,5.5"
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DIED', 0, BOSS, _player(1, 0), cast=901),
            _event(18000, 'HOT_TICK', 400, _player(2, 20000), corpse, ability=40079),
            _event(25000, 'HEAL', 4000, _player(2, 20000), _player(1, 4000), ability=40079),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].time_dead.get('1'), 9000)

    def test_no_wait_starts_on_a_release_effect(self):
        """Recently Revived and the like show the corpse at 0."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 500, BOSS, _player(2, 19500)),
            _effect(16000, _player(1, 0), ability=14646),
            _tick(17200),
            _event(18500, 'HEAL', 4000, _player(2, 20000), _player(1, 4000), ability=40079),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 0)

    def test_regeneration_ticks_start_and_end_a_wait(self):
        died, lived = (_run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 500, BOSS, _player(2, 19500)),
            *lines,
            _tick(17200),
            '30000,END_COMBAT',
        ])[0].fight_history.fights[0].deaths for lines in (
            [_regen(16000, 0, _player(1, 0))],
            [_event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=10),
             _regen(16300, 500, _player(1, 3000))],
        ))
        self.assertEqual((died, lived), (1, 0))

    def test_health_just_after_a_late_death_line_is_the_dying_lines_own(self):
        """The revive guard counts from the death line, as time dead's
        does, so the corpse's next 0 is no second death."""
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500, cast=901),
            _tick(17100),
            _event(18000, 'DIED', 0, BOSS, _player(1, 0), cast=901),
            _event(18500, 'HEAL', 300, _player(2, 20000), _player(1, 300), ability=40079),
            _event(19000, 'DAMAGE', 0, BOSS, _player(1, 0)),
            _tick(20500),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)

    def test_a_zone_change_counts_a_wait_that_lasted_the_hold(self):
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(12000, 'DAMAGE', 500, BOSS, _player(2, 19500)),
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500),
            '16500,END_COMBAT',
            '17500,ZONE_CHANGED,1302,"Somewhere Else",NORMAL',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)

    def test_a_placeholder_state_says_nothing(self):
        """The log's 1/1 placeholder for a unit it has no state for does not
        end a wait at 0 health."""
        placeholder = "1,1/1,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000"
        analyzer, _ = _run([
            '10000,BEGIN_COMBAT',
            _event(16000, 'DAMAGE', 0, BOSS, _player(1, 0), overflow=500),
            _event(16300, 'DAMAGE', 0, BOSS, placeholder),
            _tick(17100),
            '30000,END_COMBAT',
        ])
        self.assertEqual(analyzer.fight_history.fights[0].deaths, 1)


if __name__ == '__main__':
    unittest.main()
