#!/usr/bin/env python3
"""The per-fight tally of damage taken, the other way round (issue #98): by
the unit that did it and by the unit that healed, every result line
counted, the largest hit per row, and the snapshot the damage taken window
reads. The figures are a cut-down Nahviintaas pull from the 2026-10-27
survey: the boss, two Alkosh's Will adds, a fall, two healers and a pet."""

import unittest

from damage_kinds import CastIndex, TakenTally, summary_of_rows

ABILITIES = {'snap': 'Snap', 'bleed': 'Bleed', 'fall': 'Falling',
             'rr': 'Radiating Regeneration', 'vigor': 'Echoing Vigor',
             'matriarch': 'Twilight Matriarch', 'x': 'Fire Storm'}
UNITS = {'70': 'Nahviintaas', '71': "Alkosh's Will", '72': "Alkosh's Will",
         '1': '@tank', '2': '@healer', '0': 'unknown', '90': 'unit 90'}


def _snapshot(tally, top=None):
    return tally.snapshot(ABILITIES.__getitem__, lambda a: '', UNITS.__getitem__, top=top)


def _pull():
    """@tank's fight: Snap twice from the boss (one blocked), a Bleed tick
    from each of two adds, a fall; two Radiating Regeneration ticks from
    @healer (one all overheal), an Echoing Vigor of their own, a Matriarch
    heal from @healer's pet; a shield absorb and a dodge."""
    tally = TakenTally()
    index = CastIndex()
    tally.note_damage(1000, 'DAMAGE', 'PHYSICAL', 12000, 'snap', '70', False, 'none',
                      index, 'c1', source_boss=True)
    tally.note_damage(2000, 'BLOCKED_DAMAGE', 'PHYSICAL', 8000, 'snap', '70', False, 'none',
                      index, 'c2', source_boss=True)
    tally.note_damage(3000, 'DOT_TICK', 'BLEED', 1000, 'bleed', '71', False, 'none', index, 'c3')
    tally.note_damage(3500, 'DOT_TICK', 'BLEED', 1500, 'bleed', '72', False, 'none', index, 'c4')
    tally.note_damage(4000, 'FALL_DAMAGE', 'NONE', 500, 'fall', '0', False, 'none', index, '0')
    tally.note_other('HOT_TICK', 2000, 500, source_id='2', ability_id='rr')
    tally.note_other('HOT_TICK', 0, 3000, source_id='2', ability_id='rr')
    tally.note_other('HEAL', 4000, 1000, source_id='1', ability_id='vigor', self_source=True)
    tally.note_other('CRITICAL_HEAL', 1500, 0, source_id='90', ability_id='matriarch', pet_owner='2')
    tally.note_other('DAMAGE_SHIELDED', 3000, 0)
    tally.note_other('DODGED', 0, 0)
    return tally


class TestResultsAndMax(unittest.TestCase):

    def test_every_result_line_is_counted(self):
        snapshot = _snapshot(_pull())
        self.assertEqual(snapshot['results'], {
            'DAMAGE': 1, 'BLOCKED_DAMAGE': 1, 'DOT_TICK': 2, 'FALL_DAMAGE': 1, 'HOT_TICK': 2,
            'HEAL': 1, 'CRITICAL_HEAL': 1, 'DAMAGE_SHIELDED': 1, 'DODGED': 1})
        # The totals the recap already drew are what they were
        self.assertEqual((snapshot['total'], snapshot['blocked_through'], snapshot['absorbed'],
                          snapshot['avoided']), (23000, 8000, 3000, 1))
        self.assertEqual((snapshot['healed'], snapshot['overheal'], snapshot['heal_hot'],
                          snapshot['heal_direct']), (7500, 4500, 2000, 5500))

    def test_every_ability_row_with_its_largest_hit_unless_a_top_is_asked(self):
        snapshot = _snapshot(_pull())
        rows = snapshot['abilities']
        self.assertEqual([(r['name'], r['damage'], r['hits'], r['max']) for r in rows],
                         [('Snap', 20000, 2, 12000), ('Bleed', 2500, 2, 1500), ('Falling', 500, 1, 500)])
        self.assertEqual(snapshot['ability_count'], 3)
        # The recap's fight block asks for its top few, as before
        top = _snapshot(_pull(), top=1)
        self.assertEqual([r['name'] for r in top['abilities']], ['Snap'])
        self.assertEqual(top['ability_count'], 3)


class TestBySource(unittest.TestCase):

    def test_bosses_first_adds_of_one_name_as_one_row_and_the_unnamed_unit(self):
        sources = _snapshot(_pull())['sources']
        self.assertEqual([(s['name'], s['boss'], s['units'], s['damage'], s['hits'], s['max'])
                          for s in sources],
                         [('Nahviintaas', True, 1, 20000, 2, 12000),
                          ("Alkosh's Will", False, 2, 2500, 2, 1500),
                          ('', False, 1, 500, 1, 500)])
        self.assertEqual([s['unnamed'] for s in sources], [False, False, True])
        boss = sources[0]['abilities']
        self.assertEqual([(r['id'], r['name'], r['damage'], r['hits'], r['max'], r['direct'],
                           r['dot'], r['single'], r['types']) for r in boss],
                         [('snap', 'Snap', 20000, 2, 12000, 20000, 0, 20000, {'physical': 20000})])
        adds = sources[1]['abilities']
        self.assertEqual([(r['name'], r['damage'], r['dot'], r['types']) for r in adds],
                         [('Bleed', 2500, 2500, {'bleed': 2500})])
        self.assertEqual([(r['name'], r['fall']) for r in sources[2]['abilities']], [('Falling', 500)])

    def test_a_boss_flag_seen_later_marks_the_source(self):
        tally = TakenTally()
        tally.note_damage(0, 'DAMAGE', 'FIRE', 100, 'x', '70', True, 'cast')
        tally.note_damage(0, 'DAMAGE', 'FIRE', 100, 'x', '70', True, 'cast', source_boss=True)
        self.assertTrue(_snapshot(tally)['sources'][0]['boss'])

    def test_sources_sort_by_damage_within_bosses_and_the_rest(self):
        tally = TakenTally()
        tally.note_damage(0, 'DAMAGE', 'FIRE', 100, 'x', '71', True, 'cast')
        tally.note_damage(0, 'DAMAGE', 'FIRE', 900, 'x', '72', True, 'cast')  # same name as 71
        tally.note_damage(0, 'DAMAGE', 'FIRE', 50, 'x', '70', True, 'cast', source_boss=True)
        tally.note_damage(0, 'DAMAGE', 'FIRE', 10, 'x', '90', True, 'cast')
        names = [(s['name'], s['boss'], s['damage']) for s in _snapshot(tally)['sources']]
        self.assertEqual(names, [('Nahviintaas', True, 50), ("Alkosh's Will", False, 1000),
                                 ('unit 90', False, 10)])

    def test_a_cast_that_finds_its_second_target_later_moves_the_sources_row_too(self):
        tally = TakenTally()
        index = CastIndex()
        index.note_hit('70', '8', 'x', '1')
        tally.note_damage(0, 'DAMAGE', 'SHOCK', 5000, 'x', '70', False, 'none', index, '8',
                          source_boss=True)
        row = tally.sources['70']['abilities']['x']
        self.assertEqual((row['area'], row['single']), (0, 5000))
        index.note_hit('70', '8', 'x', '2')   # the same cast lands on another player
        self.assertEqual((row['area'], row['single']), (5000, 0))
        self.assertEqual((tally.area, tally.single), (5000, 0))
        snapshot = _snapshot(tally)
        self.assertEqual((snapshot['sources'][0]['abilities'][0]['area'],
                          snapshot['abilities'][0]['area']), (5000, 5000))


class TestByHealer(unittest.TestCase):

    def test_healers_by_landed_with_own_and_pet_rows_and_their_abilities(self):
        healers = _snapshot(_pull())['healers']
        self.assertEqual([(h['name'], h['self'], h['pet'], h['landed'], h['overheal'], h['hits'],
                           h['direct'], h['hot']) for h in healers],
                         [('@tank', True, False, 4000, 1000, 1, 4000, 0),
                          ('@healer', False, False, 2000, 3500, 2, 0, 2000),
                          ('@healer', False, True, 1500, 0, 1, 1500, 0)])
        rr = healers[1]['abilities']
        self.assertEqual([(r['id'], r['name'], r['landed'], r['overheal'], r['hits'], r['hot'])
                          for r in rr],
                         [('rr', 'Radiating Regeneration', 2000, 3500, 2, 2000)])
        self.assertEqual([r['name'] for r in healers[2]['abilities']], ['Twilight Matriarch'])
        self.assertFalse(any(h['unnamed'] for h in healers))

    def test_a_heal_from_no_unit_is_the_unnamed_row(self):
        tally = TakenTally()
        tally.note_other('HEAL', 100, 0, source_id='0', ability_id='vigor')
        healer = _snapshot(tally)['healers'][0]
        self.assertEqual((healer['name'], healer['unnamed'], healer['landed']), ('', True, 100))

    def test_a_heal_without_a_source_counts_in_the_totals_alone(self):
        """summary_of_rows builds a tally from recap rows, which name no
        unit id: the old three-argument call still works and keeps no
        healer rows."""
        tally = TakenTally()
        tally.note_other('HEAL', 2419, 20000)
        tally.note_other('HOT_TICK', 0, 25236)
        self.assertEqual((tally.healed, tally.overheal), (2419, 45236))
        snapshot = _snapshot(tally)
        self.assertEqual((snapshot['healers'], snapshot['sources']), ([], []))
        self.assertEqual(snapshot['results'], {'HEAL': 1, 'HOT_TICK': 1})
        rows = [{'kind': 'heal', 'result': 'HEAL', 'amount': 2419, 'overflow': 20000},
                {'kind': 'heal', 'result': 'HOT_TICK', 'amount': 0, 'overflow': 25236}]
        summary = summary_of_rows(rows)
        self.assertEqual((summary['healed'], summary['overheal']), (2419, 45236))


if __name__ == '__main__':
    unittest.main()
