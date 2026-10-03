#!/usr/bin/env python3
"""Ability icon helpers and the engine's per-slot bar data (no Qt needed)."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ability_icons import esohub_set_url, esohub_skill_url, icon_stem, slugify  # noqa: E402

FIXTURE_LOG = Path(__file__).parent.parent / 'fixtures' / 'golden_fight.log'


class TestIconStem(unittest.TestCase):

    def test_log_icon_path_becomes_lowercase_stem(self):
        self.assertEqual(icon_stem('/esoui/art/icons/ability_arcanist_002_b.dds'),
                         'ability_arcanist_002_b')
        self.assertEqual(icon_stem('\\esoui\\art\\icons\\Ability_Mage_065.DDS'),
                         'ability_mage_065')

    def test_non_icon_values_give_empty_stem(self):
        # Defensive: anything that is not a .dds path must fall back to text
        self.assertEqual(icon_stem(''), '')
        self.assertEqual(icon_stem('Magic Damage'), '')
        self.assertEqual(icon_stem(None), '')


class TestSlugsAndLinks(unittest.TestCase):

    def test_slugify_matches_esohub_style(self):
        self.assertEqual(slugify("Cephaliarch's Flail"), 'cephaliarchs-flail')
        self.assertEqual(slugify("Mages' Wrath"), 'mages-wrath')
        self.assertEqual(slugify('Coup De Grâce'), 'coup-de-grace')
        self.assertEqual(slugify('Spriggan\\’s Vigor'), 'spriggans-vigor')
        self.assertEqual(slugify('  Life amid Death '), 'life-amid-death')

    def test_skill_url_from_link_table(self):
        links = {'biting-jabs': '/en/skills/templar/aedric-spear/biting-jabs'}
        self.assertEqual(esohub_skill_url('Biting Jabs', links),
                         'https://eso-hub.com/en/skills/templar/aedric-spear/biting-jabs')
        self.assertIsNone(esohub_skill_url('Magical Banner', links))
        self.assertIsNone(esohub_skill_url('', links))

    def test_set_url_from_link_table(self):
        links = {'Deadly Strike': '/en/sets/deadly-strike'}
        self.assertEqual(esohub_set_url('Deadly Strike', links),
                         'https://eso-hub.com/en/sets/deadly-strike')
        self.assertEqual(esohub_set_url(' Deadly Strike ', links),
                         'https://eso-hub.com/en/sets/deadly-strike')
        self.assertIsNone(esohub_set_url('Set#999', links))
        self.assertIsNone(esohub_set_url('', links))


class TestBarSlotsFromEngine(unittest.TestCase):
    """PLAYER_INFO bars reach the fight entry with ids and icon stems."""

    def test_golden_fixture_players_carry_bar_slots(self):
        from esolog_tail import ESOLogAnalyzer
        from fight_history import FightHistory
        analyzer = ESOLogAnalyzer()
        analyzer.fight_history = FightHistory()
        analyzer.current_log_file = str(FIXTURE_LOG)
        for line in FIXTURE_LOG.read_text(encoding='utf-8').splitlines():
            if line.strip():
                entry = analyzer.log_parser.parse_line(line)
                if entry is not None:
                    analyzer.process_log_entry(entry)
        fights = analyzer.fight_history.fights
        self.assertTrue(fights)
        player = fights[0].players[0]
        slots = player['front_bar_slots']
        # Slots line up one-to-one with the existing name list
        self.assertEqual([s['name'] for s in slots], player['front_bar'])
        self.assertEqual([s['name'] for s in player['back_bar_slots']], player['back_bar'])
        flail = next(s for s in slots if s['name'] == "Cephaliarch's Flail")
        self.assertEqual(flail['id'], '183006')
        self.assertEqual(flail['icon'], 'ability_arcanist_002')
        # Every slot resolved an icon stem from its ABILITY_INFO line
        self.assertTrue(all(s['icon'].startswith('ability_') for s in slots))


if __name__ == '__main__':
    unittest.main()
