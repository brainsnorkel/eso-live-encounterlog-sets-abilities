#!/usr/bin/env python3
"""The kinds of damage (damage_kinds): what a result and a damage type are
classed as, the cast index behind area or single target, the per-fight
tally of damage taken, the summary both windows draw, and the Warfare
star table. The figures come from the 87-log survey of 2026-10-27 and the
Dreadsail Reef death it describes."""

import json
import tempfile
import unittest
from pathlib import Path

from damage_kinds import (
    ESOHUB_CP,
    SIDE_LABELS,
    SPLITS,
    STARS,
    CastIndex,
    TakenTally,
    area_of,
    area_rule,
    classify,
    rows_have_kinds,
    stars_for,
    summary_of_rows,
    summary_of_taken,
    table_target,
    type_label,
)


class TestClassify(unittest.TestCase):

    def test_direct_dot_and_fall_by_result(self):
        for result in ('DAMAGE', 'CRITICAL_DAMAGE', 'BLOCKED_DAMAGE'):
            self.assertEqual(classify(result, 'FIRE')['time'], 'direct', result)
        for result in ('DOT_TICK', 'DOT_TICK_CRITICAL'):
            self.assertEqual(classify(result, 'FIRE')['time'], 'dot', result)
        fall = classify('FALL_DAMAGE', 'GENERIC')
        self.assertEqual((fall['time'], fall['school'], fall['type']), ('fall', 'other', 'fall'))
        self.assertEqual(classify('HEAL', 'GENERIC')['time'], '')

    def test_martial_magical_oblivion_and_the_rest_by_type(self):
        for damage_type in ('PHYSICAL', 'BLEED', 'POISON', 'DISEASE'):
            self.assertEqual(classify('DAMAGE', damage_type)['school'], 'martial', damage_type)
        for damage_type in ('MAGIC', 'FIRE', 'COLD', 'SHOCK'):
            self.assertEqual(classify('DAMAGE', damage_type)['school'], 'magical', damage_type)
        self.assertEqual(classify('DAMAGE', 'OBLIVION')['school'], 'oblivion')
        for damage_type in ('DROWN', 'GENERIC', 'NONE', 'EARTH', 'PLASMA', ''):
            self.assertEqual(classify('DAMAGE', damage_type)['school'], 'other', damage_type)

    def test_type_labels_use_the_games_words_and_the_logs_for_unknown_ones(self):
        self.assertEqual(type_label('COLD'), 'frost')
        self.assertEqual(type_label('DROWN'), 'drowning')
        self.assertEqual(type_label('GENERIC'), 'untyped')
        self.assertEqual(type_label('NONE'), 'untyped')
        self.assertEqual(type_label('EARTH'), 'earth')     # a type the tables do not list
        self.assertEqual(type_label('PLASMA'), 'plasma')   # a type no release has seen
        self.assertEqual(type_label(''), 'untyped')
        self.assertEqual(type_label('SHOCK', 'FALL_DAMAGE'), 'fall')


class TestCastIndex(unittest.TestCase):

    def test_one_cast_many_players_is_area_for_every_hit(self):
        index = CastIndex()
        self.assertEqual(index.note_hit('70', '4711', '95687', '1'), 1)
        for target in ('2', '3', '4'):
            index.note_hit('70', '4711', '95687', target)
        self.assertEqual(index.targets_of('70', '4711'), 4)
        # The first hit, classed now, reads the cast's whole count
        self.assertEqual(area_of(index, '70', '4711', '95687', False), (True, 'cast', 4))

    def test_one_cast_one_player_is_single(self):
        index = CastIndex()
        index.note_hit('70', '4712', '166191', '1')
        index.note_hit('70', '4713', '166191', '2')   # another cast, another player
        self.assertEqual(area_of(index, '70', '4712', '166191', False), (False, 'none', 1))

    def test_an_ability_that_hit_a_group_earlier_in_the_session_is_area_on_a_lone_hit(self):
        index = CastIndex()
        for target in ('1', '2', '3', '4', '5', '6', '7', '8'):
            index.note_hit('70', '100', '95687', target)
        index.new_fight()                                   # the next pull
        index.note_hit('71', '200', '95687', '1')
        self.assertEqual(index.targets_of('70', '100'), 0)  # the old cast is gone
        self.assertEqual(index.session_max('95687'), 8)
        self.assertEqual(area_of(index, '71', '200', '95687', False), (True, 'session', 1))
        index.reset()                                       # a new zone
        index.note_hit('5', '300', '95687', '1')
        self.assertEqual(area_of(index, '5', '300', '95687', False), (False, 'none', 1))

    def test_watch_fires_once_when_the_second_unit_lands(self):
        index = CastIndex()
        fired = []
        index.note_hit('70', '9', 'a', '1')
        index.watch('70', '9', lambda: fired.append('x'))
        index.note_hit('70', '9', 'a', '1')   # the same unit again: still one
        self.assertEqual(fired, [])
        index.note_hit('70', '9', 'a', '2')
        index.note_hit('70', '9', 'a', '3')
        self.assertEqual(fired, ['x'])

    def test_player_skills_fall_back_to_the_table_and_monsters_never_do(self):
        self.assertEqual(area_rule(1, 0, True, '28800', table='area'), (True, 'table'))
        self.assertEqual(area_rule(1, 0, True, '46324', table='single'), (False, 'table'))
        self.assertEqual(area_rule(1, 0, True, '118604', table=None), (False, 'none'))
        # A monster's ability with the same evidence never asks the table
        self.assertEqual(area_rule(1, 0, False, '28800', table='area'), (False, 'none'))
        # Evidence from casts beats the table either way
        self.assertEqual(area_rule(3, 0, True, '46324', table='single'), (True, 'cast'))

    def test_table_is_read_from_the_bundled_file_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ability_targets.json'
            path.write_text(json.dumps({'area': [28800, 28858], 'single': ['46324']}),
                            encoding='utf-8')
            self.assertEqual(table_target('28800', path=path), 'area')
            self.assertEqual(table_target(28858, path=path), 'area')
            self.assertEqual(table_target('46324', path=path), 'single')
            self.assertIsNone(table_target('1', path=path))
            self.assertIsNone(table_target('28800', path=Path(tmp) / 'missing.json'))


class TestTakenTally(unittest.TestCase):

    def test_the_dreadsail_death(self):
        """@Badz7, Dreadsail Reef 2026-09-02: 29,626 damage in the window,
        76% ticks of Ignite from a cast that hit others, all fire; 3,848
        absorbed, healed 2,419 against 45,236 overheal."""
        tally = TakenTally()
        index = CastIndex()
        index.note_hit('70', '1', '170159', '5')
        index.note_hit('70', '1', '170159', '6')  # the cast hit two players
        area, rule, _n = area_of(index, '70', '1', '170159', False)
        for _ in range(13):
            tally.note_damage(1000, 'DOT_TICK', 'FIRE', 1732, '170159', '70', area, rule, index, '1')
        tally.note_damage(2000, 'DAMAGE', 'FIRE', 7110, '166213', '71', False, 'none', index, '2')
        tally.note_other('DAMAGE_SHIELDED', 3848, 0)
        tally.note_other('HEAL', 2419, 20000)
        tally.note_other('HOT_TICK', 0, 25236)
        snapshot = tally.snapshot(lambda a: {'170159': 'Ignite', '166213': 'Destructive Ember'}[a],
                                  lambda a: '', lambda u: {'70': 'Reef Guardian', '71': 'Ember'}[u])
        self.assertEqual(snapshot['total'], 29626)
        self.assertEqual((snapshot['direct'], snapshot['dot']), (7110, 22516))
        self.assertEqual((snapshot['area'], snapshot['single']), (22516, 7110))
        self.assertEqual((snapshot['martial'], snapshot['magical']), (0, 29626))
        self.assertEqual(snapshot['types'], {'fire': 29626})
        self.assertEqual((snapshot['absorbed'], snapshot['healed'], snapshot['overheal']),
                         (3848, 2419, 45236))
        self.assertEqual((snapshot['heal_direct'], snapshot['heal_hot']), (2419, 0))
        self.assertEqual((snapshot['first_ms'], snapshot['last_ms']), (1000, 2000))
        top = snapshot['abilities']
        self.assertEqual([r['name'] for r in top], ['Ignite', 'Destructive Ember'])
        self.assertEqual((top[0]['damage'], top[0]['dot'], top[0]['area'], top[0]['source']),
                         (22516, 22516, 22516, 'Reef Guardian'))
        summary = summary_of_taken(snapshot)
        self.assertEqual(summary['pcts'], {'time': (24, 76), 'target': (76, 24), 'school': (0, 100)})
        self.assertEqual(summary['types'], [('fire', 29626)])
        self.assertEqual(summary['outside'], {})

    def test_a_cast_that_finds_its_second_target_later_moves_its_damage_to_area(self):
        tally = TakenTally()
        index = CastIndex()
        index.note_hit('70', '8', 'x', '1')
        area, rule, _n = area_of(index, '70', '8', 'x', False)
        tally.note_damage(0, 'DAMAGE', 'SHOCK', 5000, 'x', '70', area, rule, index, '8')
        self.assertEqual((tally.area, tally.single), (0, 5000))
        self.assertEqual(tally.rules, {'none': 5000})
        index.note_hit('70', '8', 'x', '2')   # the same cast lands on another player
        self.assertEqual((tally.area, tally.single), (5000, 0))
        self.assertEqual(dict(tally.rules), {'none': 0, 'cast': 5000})
        self.assertEqual((tally.abilities['x']['area'], tally.abilities['x']['single']), (5000, 0))

    def test_outside_the_schools_and_unknown_types_are_named_not_refused(self):
        tally = TakenTally()
        tally.note_damage(0, 'DAMAGE', 'OBLIVION', 9000, 'a', '70', False, 'none')
        tally.note_damage(0, 'DAMAGE', 'MAGIC', 9000, 'b', '70', False, 'none')
        tally.note_damage(0, 'FALL_DAMAGE', 'GENERIC', 15000, '10950', '1', False, 'none')
        tally.note_damage(0, 'DAMAGE', 'DROWN', 1000, 'c', '0', False, 'none')
        tally.note_damage(0, 'DAMAGE', 'EARTH', 6526, 'd', '70', False, 'none')
        tally.note_damage(0, 'DAMAGE', 'PLASMA', 1, 'e', '70', False, 'none')
        snapshot = tally.snapshot(lambda a: a, lambda a: '', lambda u: u)
        self.assertEqual(snapshot['total'], 9000 + 9000 + 15000 + 1000 + 6526 + 1)
        self.assertEqual((snapshot['martial'], snapshot['magical'], snapshot['oblivion']),
                         (0, 9000, 9000))
        self.assertEqual(snapshot['fall'], 15000)
        summary = summary_of_taken(snapshot)
        self.assertEqual(summary['outside'],
                         {'oblivion': 9000, 'fall': 15000, 'drowning': 1000, 'earth': 6526, 'plasma': 1})
        self.assertEqual(summary['pcts']['school'], (0, 100))

    def test_blocked_hits_count_as_direct_and_are_reported_as_got_through(self):
        tally = TakenTally()
        tally.note_damage(0, 'BLOCKED_DAMAGE', 'PHYSICAL', 4073, 'a', '70', False, 'none')
        tally.note_other('DODGED', 0, 0)
        tally.note_other('MISS', 0, 0)
        tally.note_other('HEAL_ABSORBED', 1328, 0)
        tally.note_overkill(6100)
        snapshot = tally.snapshot(lambda a: a, lambda a: '', lambda u: u)
        self.assertEqual((snapshot['direct'], snapshot['blocked_through']), (4073, 4073))
        self.assertEqual((snapshot['avoided'], snapshot['heal_absorbed'], snapshot['overkill']),
                         (2, 1328, 6100))


class TestSummaryOfRows(unittest.TestCase):

    @staticmethod
    def _row(kind, result, amount, damage_type='PHYSICAL', area=False, rule='none',
             health=1000, overflow=0, absorbed=0, ability='9'):
        return {'kind': kind, 'result': result, 'amount': amount, 'damage_type': damage_type,
                'area': area, 'area_rule': rule, 'health': health, 'overflow': overflow,
                'absorbed': absorbed, 'ability_id': ability, 'source': 'Boss'}

    def test_the_one_shot(self):
        rows = [self._row('damage', 'DAMAGE', 20372, health=0, overflow=6100)]
        summary = summary_of_rows(rows)
        self.assertEqual(summary['total'], 20372)
        self.assertEqual(summary['pcts'], {'time': (100, 0), 'target': (0, 100), 'school': (100, 0)})
        self.assertEqual(summary['types'], [('physical', 20372)])
        self.assertEqual(summary['overkill'], 6100)
        self.assertEqual(summary['healed'], 0)

    def test_heals_shields_and_the_recaps_own_overheal_sum(self):
        rows = [
            self._row('damage', 'BLOCKED_DAMAGE', 2102, absorbed=5603),
            self._row('absorbed', 'DAMAGE_SHIELDED', 800),
            self._row('heal', 'HOT_TICK', 2500, overflow=700),
            self._row('heal', 'HEAL', 1000, overflow=300),
            self._row('avoided', 'DODGED', 0),
            self._row('heal_absorbed', 'HEAL_ABSORBED', 1328),
        ]
        summary = summary_of_rows(rows)
        self.assertEqual((summary['blocked_through'], summary['absorbed'], summary['avoided']),
                         (2102, 6403, 1))
        self.assertEqual((summary['healed'], summary['heal_direct'], summary['heal_hot']),
                         (3500, 1000, 2500))
        self.assertEqual(summary['overheal'], 1000)   # the rows' overflow
        self.assertEqual(summary_of_rows(rows, overheal=45236)['overheal'], 45236)
        self.assertEqual(summary['heal_absorbed'], 1328)

    def test_rows_from_before_the_change_are_told_apart(self):
        old = [{'kind': 'damage', 'result': 'DAMAGE', 'amount': 5}]
        new = [self._row('damage', 'DAMAGE', 5)]
        self.assertFalse(rows_have_kinds(old))
        self.assertTrue(rows_have_kinds(new))
        self.assertTrue(rows_have_kinds([{'kind': 'heal', 'result': 'HEAL', 'amount': 5}]))


class TestStars(unittest.TestCase):

    def test_every_side_of_every_split_names_a_star_with_an_esohub_link(self):
        for scope in ('dealt', 'taken'):
            for left, right in SPLITS:
                for side in (left, right):
                    stars = stars_for(scope, side)
                    self.assertTrue(stars, (scope, side))
                    for star in stars:
                        self.assertTrue(star['url'].startswith(ESOHUB_CP), star)
                        self.assertTrue(star['text'].endswith('.'), star)
                    self.assertIn(side, SIDE_LABELS)
        for side in ('direct', 'dot', 'landed', 'overheal'):
            self.assertTrue(stars_for('heal', side), side)

    def test_preparation_joins_every_damage_taken_side_and_no_other(self):
        for _left, right in SPLITS:
            self.assertIn('Preparation', [s['name'] for s in stars_for('taken', right)])
        for scope in ('dealt', 'heal'):
            for side in ('direct', 'dot'):
                self.assertNotIn('Preparation', [s['name'] for s in stars_for(scope, side)])
        self.assertEqual(stars_for('taken', 'nothing'), [])
        self.assertNotIn(('taken', 'nothing'), STARS)

    def test_the_named_stars(self):
        names = {key: [s['name'] for s in stars] for key, stars in STARS.items()}
        self.assertEqual(names[('dealt', 'dot')], ['Thaumaturge'])
        self.assertEqual(names[('dealt', 'direct')], ['Master-at-Arms'])
        self.assertEqual(names[('taken', 'area')], ['Unassailable'])
        self.assertEqual(names[('taken', 'single')], ["Duelist's Rebuff"])
        self.assertEqual(names[('taken', 'martial')], ['Hardy'])
        self.assertEqual(names[('dealt', 'magical')], ['War Mage'])
        self.assertEqual(names[('heal', 'landed')], ['Blessed', 'Quick Recovery'])


if __name__ == '__main__':
    unittest.main()
