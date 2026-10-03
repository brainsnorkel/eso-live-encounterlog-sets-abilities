#!/usr/bin/env python3
"""Skill-line detection: exact ability names only, at most three lines."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from eso_sets import ESOSubclassAnalyzer  # noqa: E402


class TestSubclassDetection(unittest.TestCase):

    def setUp(self):
        self.analyzer = ESOSubclassAnalyzer()

    def test_substrings_do_not_match(self):
        # A real pure-Nightblade bar from a live log: "Carve" (Two Handed) used
        # to count as an Arcanist Fatecarver and add a fourth line
        nightblade = {'Surprise Attack', "Killer's Blade", 'Merciless Resolve',
                      'Shadowy Disguise', 'Debilitate', 'Incapacitating Strike',
                      'Stampede', 'Barbed Trap', 'Carve', 'Siphoning Attacks',
                      'Dark Shade', 'Shooting Star'}
        self.assertEqual(self.analyzer.analyze_subclass(nightblade)['skill_lines'],
                         ['Assassination', 'Shadow', 'Siphoning'])
        # "Swarming Scion" (Vampire) is not the Warden "Swarm"
        vampire = {'Swallow Soul', 'Twisting Path', 'Siphoning Attacks', 'Swarming Scion'}
        self.assertNotIn('Animal Companions',
                         self.analyzer.analyze_subclass(vampire)['skill_lines'])
        self.assertFalse(self.analyzer._ability_matches('Fatecarver', 'Carve'))
        self.assertTrue(self.analyzer._ability_matches('fatecarver', 'Fatecarver '))

    def test_at_most_three_best_supported_lines_in_table_order(self):
        mixed = {'Flame Lash', 'Molten Whip', 'Burning Embers',          # Ardent Flame x3
                 'Fatecarver', 'Runeblades',                              # Herald x2
                 'Radiant Glory',                                         # Dawn's Wrath x1
                 'Soul Harvest', 'Impale', 'Concealed Weapon', 'Mark Target'}  # Assassination x4
        lines = self.analyzer.analyze_subclass(mixed)['skill_lines']
        self.assertEqual(lines, ['Ardent Flame', 'Assassination', 'Herald of the Tome'])

    def test_empty_and_unknown(self):
        self.assertEqual(self.analyzer.analyze_subclass(set())['skill_lines'], [])
        self.assertEqual(self.analyzer.analyze_subclass({'Light Attack (Bow)'})['skill_lines'], [])


if __name__ == '__main__':
    unittest.main()
