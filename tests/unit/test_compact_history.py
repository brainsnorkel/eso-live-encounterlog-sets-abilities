"""Fight entries hold their bulk compactly (issue #110) and read as before:
a damage series is a Series of [t, damage] pairs, an effect span an
Interval read as its dict, and identical gear rows one shared list."""

import unittest

from damage_stats import Series, compact_series, per_second, series_of
from effect_rules import Interval
from tests.fixtures.build_session import SESSION, fights


class TestSeries(unittest.TestCase):

    def test_reads_as_the_list_form(self):
        plain = series_of({12: 500, 10: 200, 11: 0}, 10000)
        s = compact_series(plain)
        self.assertIsInstance(s, Series)
        self.assertEqual(s, plain)
        self.assertEqual(list(s), plain)
        self.assertEqual(len(s), 3)
        self.assertEqual(s[0], [0.0, 200])
        self.assertEqual(s[-1], [2.0, 500])
        self.assertEqual(s[1:], plain[1:])
        self.assertEqual([d for _t, d in s], [200, 0, 500])
        self.assertEqual(per_second(s, 3.0), per_second(plain, 3.0))
        self.assertEqual(repr(s), repr(plain))

    def test_empty_is_falsy(self):
        self.assertFalse(compact_series([]))
        self.assertEqual(compact_series([]), [])

    def test_damage_that_is_not_whole_keeps_the_list(self):
        plain = [[0.0, 1.5]]
        self.assertIs(compact_series(plain), plain)


class TestInterval(unittest.TestCase):

    def test_reads_as_its_dict(self):
        iv = Interval(0, 24136, 1, '@a', '@b')
        as_dict = {'start_ms': 0, 'end_ms': 24136, 'stacks': 1, 'target': '@a', 'source': '@b'}
        self.assertEqual(iv, as_dict)
        self.assertEqual(iv['end_ms'], 24136)
        self.assertEqual(iv.get('stacks'), 1)
        self.assertEqual(iv.get('nothing', 7), 7)
        self.assertEqual(dict(iv.items()), as_dict)
        self.assertEqual(sorted(iv), sorted(as_dict))
        with self.assertRaises(KeyError):
            iv['nothing']

    def test_without_stacks_has_no_stacks_key(self):
        iv = Interval(5, 9, target='@t', source='@s')
        self.assertEqual(iv, {'start_ms': 5, 'end_ms': 9, 'target': '@t', 'source': '@s'})
        self.assertNotIn('stacks', iv)
        self.assertIsNone(iv.get('stacks'))
        with self.assertRaises(KeyError):
            iv['stacks']


class TestSharedGear(unittest.TestCase):

    def test_the_same_gear_is_one_list_across_fights(self):
        later = [line.replace('9990,BEGIN_COMBAT', '80000,BEGIN_COMBAT')
                 for line in SESSION if not line.startswith(('1000,', '2000,', '2500,'))]
        later = [line if not line.split(',')[0].isdigit() else
                 str(int(line.split(',')[0]) + 70000) + line[len(line.split(',')[0]):]
                 for line in later]
        first, second = fights(SESSION + later)
        gear = {p['name']: p['gear'] for p in first.players}
        shared = 0
        for p in second.players:
            if gear.get(p['name']):
                self.assertIs(p['gear'], gear[p['name']])
                shared += 1
        self.assertGreaterEqual(shared, 2)  # both geared players of the fixture


if __name__ == '__main__':
    unittest.main()
