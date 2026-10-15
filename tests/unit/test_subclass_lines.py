#!/usr/bin/env python3
"""Skill-line detection: exact ability names only, at most three lines."""

import unittest

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


# Rows of data/skills/class_passives.json, as the game ids are
PASSIVES = {
    '36641': {'class': 'Nightblade', 'line': 'Assassination', 'name': 'Hemorrhage', 'rank': 1},
    '45060': {'class': 'Nightblade', 'line': 'Assassination', 'name': 'Hemorrhage', 'rank': 2},
    '45048': {'class': 'Nightblade', 'line': 'Assassination', 'name': 'Executioner', 'rank': 2},
    '45071': {'class': 'Nightblade', 'line': 'Shadow', 'name': 'Shadow Barrier', 'rank': 2},
    '45155': {'class': 'Nightblade', 'line': 'Siphoning', 'name': 'Soul Siphoner', 'rank': 2},
    '86194': {'class': 'Warden', 'line': "Winter's Embrace", 'name': 'Icy Aura', 'rank': 2},
    '86066': {'class': 'Warden', 'line': 'Animal Companions', 'name': 'Flourish', 'rank': 1},
    '184887': {'class': 'Arcanist', 'line': 'Herald of the Tome', 'name': 'Splintered Secrets', 'rank': 2},
    '45011': {'class': 'Dragonknight', 'line': 'Ardent Flame', 'name': 'Combustion', 'rank': 2},
    '263604': {'class': 'Nightblade', 'line': 'Class Mastery', 'name': 'An Eye for Exploitation', 'rank': 1},
    '263605': {'class': 'Nightblade', 'line': 'Class Mastery', 'name': 'Above and Beyond', 'rank': 1},
}


class TestSkillLinesFromPassives(unittest.TestCase):
    """The lines a player's PLAYER_INFO passives name, the slotted abilities
    filling in (eso_sets.skill_lines_of)."""

    def test_passives_name_the_lines_by_id_in_table_order(self):
        from eso_sets import lines_from_passives, skill_lines_of
        # A Nightblade who swapped Siphoning for Herald of the Tome, with
        # mundus, food and a mastery in the same list
        effects = ['13975', '45060', '45048', '45071', '184887', '263604', '263605']
        found, masteries = lines_from_passives(effects, PASSIVES)
        self.assertEqual(found, {'Assassination': 2, 'Shadow': 1, 'Herald of the Tome': 1})
        self.assertEqual(masteries, ['An Eye for Exploitation', 'Above and Beyond'])
        self.assertEqual(skill_lines_of(effects, set(), PASSIVES),
                         ['Assassination', 'Shadow', 'Herald of the Tome'])
        # Rank 1 of a passive names the line as rank 2 does
        self.assertEqual(skill_lines_of(['36641'], set(), PASSIVES), ['Assassination'])
        # Ids come as strings or ints
        self.assertEqual(skill_lines_of([45060, 86194], set(), PASSIVES),
                         ['Assassination', "Winter's Embrace"])

    def test_same_named_effects_do_not_count(self):
        from eso_sets import skill_lines_of
        # 42030 is the Combustion resource return a Dragonknight gives the
        # group: not in the table, so not an Ardent Flame passive
        self.assertEqual(skill_lines_of(['42030', '45071'], set(), PASSIVES), ['Shadow'])
        self.assertEqual(skill_lines_of(['45011', '45071'], set(), PASSIVES),
                         ['Ardent Flame', 'Shadow'])

    def test_slotted_abilities_fill_in_for_unlearned_passives(self):
        from eso_sets import skill_lines_of
        # A mid-level Nightblade with no Siphoning passive yet but Siphoning
        # Attacks slotted: the slotted line fills the third place
        bars = {'Surprise Attack', 'Shadowy Disguise', 'Siphoning Attacks', 'Carve'}
        self.assertEqual(skill_lines_of(['45060', '45071'], bars, PASSIVES),
                         ['Assassination', 'Shadow', 'Siphoning'])
        # Three lines of passives leave no room: the bars add nothing
        self.assertEqual(skill_lines_of(['45060', '45071', '45155'], {'Fatecarver'}, PASSIVES),
                         ['Assassination', 'Shadow', 'Siphoning'])
        # No passives at all (an empty table, an old log): the bars alone
        self.assertEqual(skill_lines_of([], bars, PASSIVES), ['Assassination', 'Shadow', 'Siphoning'])
        self.assertEqual(skill_lines_of(['45060'], bars, {}), ['Assassination', 'Shadow', 'Siphoning'])
        self.assertEqual(skill_lines_of([], set(), PASSIVES), [])

    def test_a_fourth_line_of_passives_loses_to_the_slotted_lines(self):
        from eso_sets import skill_lines_of
        effects = ['45060', '45048', '45071', '45155', '86194']   # four lines
        # Winter's Embrace is slotted and Siphoning is not: Siphoning goes
        self.assertEqual(skill_lines_of(effects, {'Surprise Attack', 'Polar Wind'}, PASSIVES),
                         ['Assassination', 'Shadow', "Winter's Embrace"])
        # Nothing slotted: the line with the fewest passives goes
        self.assertEqual(skill_lines_of(effects + ['86066'], set(), PASSIVES),
                         ['Assassination', 'Shadow', 'Siphoning'])

    def test_bundled_table_covers_every_class(self):
        from eso_sets import MASTERY_LINE, class_passive_table
        table = class_passive_table()
        self.assertEqual(len(table), 203)
        classes = {entry['class'] for entry in table.values()}
        self.assertEqual(len(classes), 7)
        for class_name in classes:
            lines = {entry['line'] for entry in table.values()
                     if entry['class'] == class_name and entry['line'] != MASTERY_LINE}
            self.assertEqual(len(lines), 3, class_name)
            self.assertTrue(lines <= set(ESOSubclassAnalyzer.SKILL_LINE_ABILITIES), lines)
        self.assertEqual(table['45060']['line'], 'Assassination')
        self.assertEqual(table['29424']['rank'], 1)
        self.assertNotIn('42030', table)

    def test_mastery_effects_name_their_mastery(self):
        from eso_sets import mastery_effect_table, mastery_of_effect
        # A small table: the effect Unbound Potential fires, and the passive itself
        table = {'263411': 'Unbound Potential', '263604': 'An Eye for Exploitation'}
        self.assertEqual(mastery_of_effect('263411', table), 'Unbound Potential')
        self.assertEqual(mastery_of_effect(263604, table), 'An Eye for Exploitation')
        self.assertEqual(mastery_of_effect('45060', table), '')
        # The bundled one: 60 effects plus the 35 passives, no monster ability
        bundled = mastery_effect_table()
        self.assertEqual(len(bundled), 95)
        self.assertEqual(bundled['263411'], 'Unbound Potential')      # proc effect
        self.assertEqual(bundled['263604'], 'An Eye for Exploitation')  # the passive
        self.assertEqual(bundled['268274'], 'Calculated Defense')     # group effect
        self.assertNotIn('107994', bundled)                           # Pound of Flesh, a monster's
        self.assertEqual(mastery_of_effect('263369'), 'Abyssal Emergence')


if __name__ == '__main__':
    unittest.main()
