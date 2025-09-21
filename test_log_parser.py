#!/usr/bin/env python3
"""
Unit tests for ESO Log Parser
Tests all log entry types using real example data from the encounter log.
"""

import unittest
from eso_log_parser import ESOLogParser, ESOLogEntry


class TestESOLogParser(unittest.TestCase):
    """Test suite for ESO log parser using real example data."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = ESOLogParser()
        
        # Real example data from the encounter log
        self.sample_lines = {
            'begin_log': '5,BEGIN_LOG,1755729685851,15,"NA Megaserver","en","eso.live.11.1"',
            'zone_changed': '5,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
            'unit_added_player': '5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
            'unit_added_anon': '5,UNIT_ADDED,30,PLAYER,F,2,0,F,6,1,"","",0,50,787,0,PLAYER_ALLY,F',
            'ability_info': '2928,ABILITY_INFO,84734,"Witchfest Food: Max HM, Reg M","/esoui/art/icons/ability_mage_065.dds",T,T',
            'map_changed': '2928,MAP_CHANGED,2110,"Brackish Cove","summerset/CoralAerie_Beach_001"',
            'begin_cast': '2928,BEGIN_CAST,0,F,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000',
            'end_cast': '2928,END_CAST,COMPLETED,4021667,84734',
            'effect_info': '2928,EFFECT_INFO,84734,BUFF,NONE,NEVER',
            'effect_changed_gained': '2928,EFFECT_CHANGED,GAINED,1,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,*',
            'effect_changed_faded': '2928,EFFECT_CHANGED,FADED,1,4021288,89971,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,*',
            'effect_changed_updated': '2928,EFFECT_CHANGED,UPDATED,1,4021667,84731,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,*',
            'player_info': '40604,PLAYER_INFO,1,[142210,142079,84731,220015,58955,147226,150054,240281,193447,45549,45557,45559,45561,45562,29738,45565,45564,45572,45048,45038,45053,45060,45602,45601,45603,40393,45596,39248,55676,55386,35965,45274,117970,45276,39255,45573,86190,86194,86196,184858,184847,184873,184887,13975,227121,183049,34741,217699,227120,227030,217705,227082,227600,227122,45514,99875,45513,45509],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],[[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,MAGICKA,T,16,LEGENDARY],[NECK,194512,T,16,JEWELRY_INFUSED,LEGENDARY,694,INCREASE_SPELL_DAMAGE,T,16,LEGENDARY],[CHEST,215597,T,16,ARMOR_DIVINES,LEGENDARY,809,MAGICKA,T,16,LEGENDARY],[SHOULDERS,174468,T,16,ARMOR_DIVINES,LEGENDARY,591,MAGICKA,T,16,LEGENDARY],[MAIN_HAND,173599,T,16,WEAPON_CHARGED,LEGENDARY,587,FIERY_WEAPON,T,16,LEGENDARY],[OFF_HAND,173599,T,16,WEAPON_CHARGED,LEGENDARY,587,POISONED_WEAPON,T,16,LEGENDARY],[WAIST,215603,T,16,ARMOR_DIVINES,LEGENDARY,809,MAGICKA,T,16,LEGENDARY],[LEGS,215601,T,16,ARMOR_DIVINES,LEGENDARY,809,MAGICKA,T,16,LEGENDARY],[FEET,215598,T,16,ARMOR_DIVINES,LEGENDARY,809,MAGICKA,T,16,LEGENDARY],[RING1,175047,T,16,JEWELRY_BLOODTHIRSTY,LEGENDARY,591,INCREASE_SPELL_DAMAGE,T,16,LEGENDARY],[RING2,175047,T,16,JEWELRY_BLOODTHIRSTY,LEGENDARY,591,INCREASE_SPELL_DAMAGE,T,16,LEGENDARY],[HAND,215599,T,16,ARMOR_DIVINES,LEGENDARY,809,MAGICKA,T,16,LEGENDARY],[BACKUP_MAIN,166199,T,16,WEAPON_INFUSED,LEGENDARY,526,BERSERKER,T,16,LEGENDARY]],[183006,183122,38901,25267,217699,113105],[39028,86169,86156,185842,217699,86113]'
        }

    def test_basic_log_entry_parsing(self):
        """Test basic log entry parsing."""
        # Test BEGIN_LOG
        entry = self.parser.parse_line(self.sample_lines['begin_log'])
        self.assertIsNotNone(entry)
        self.assertEqual(entry.timestamp, 5)
        self.assertEqual(entry.event_type, "BEGIN_LOG")
        
        # Test ZONE_CHANGED
        entry = self.parser.parse_line(self.sample_lines['zone_changed'])
        self.assertIsNotNone(entry)
        self.assertEqual(entry.timestamp, 5)
        self.assertEqual(entry.event_type, "ZONE_CHANGED")
        
        # Test MAP_CHANGED
        entry = self.parser.parse_line(self.sample_lines['map_changed'])
        self.assertIsNotNone(entry)
        self.assertEqual(entry.timestamp, 2928)
        self.assertEqual(entry.event_type, "MAP_CHANGED")

    def test_unit_added_parsing(self):
        """Test UNIT_ADDED entry parsing."""
        # Test player with handle
        entry = self.parser.parse_line(self.sample_lines['unit_added_player'])
        parsed = self.parser.parse_unit_added(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.timestamp, 5)
        self.assertEqual(parsed.unit_id, "1")
        self.assertEqual(parsed.unit_type, "PLAYER")
        self.assertEqual(parsed.name, "Beam Hal")
        self.assertEqual(parsed.handle, "@brainsnorkel")
        self.assertEqual(parsed.level, 50)
        self.assertEqual(parsed.alliance, 3084)
        
        # Test anonymous player
        entry = self.parser.parse_line(self.sample_lines['unit_added_anon'])
        parsed = self.parser.parse_unit_added(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.timestamp, 5)
        self.assertEqual(parsed.unit_id, "30")
        self.assertEqual(parsed.unit_type, "PLAYER")
        self.assertEqual(parsed.name, "")
        self.assertEqual(parsed.handle, "")
        self.assertEqual(parsed.level, 50)
        self.assertEqual(parsed.alliance, 787)

    def test_ability_info_parsing(self):
        """Test ABILITY_INFO entry parsing."""
        entry = self.parser.parse_line(self.sample_lines['ability_info'])
        parsed = self.parser.parse_ability_info(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.timestamp, 2928)
        self.assertEqual(parsed.ability_id, "84734")
        self.assertEqual(parsed.ability_name, "Witchfest Food: Max HM, Reg M")
        self.assertEqual(parsed.icon_path, "/esoui/art/icons/ability_mage_065.dds")
        self.assertEqual(parsed.flags, ["T", "T"])
        
        # Test that ability was cached
        self.assertEqual(self.parser.get_ability_name("84734"), "Witchfest Food: Max HM, Reg M")

    def test_begin_cast_parsing(self):
        """Test BEGIN_CAST entry parsing."""
        entry = self.parser.parse_line(self.sample_lines['begin_cast'])
        parsed = self.parser.parse_begin_cast(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.timestamp, 2928)
        self.assertEqual(parsed.unknown1, "0")
        self.assertEqual(parsed.unknown2, "F")
        self.assertEqual(parsed.caster_unit_id, "4021667")
        self.assertEqual(parsed.ability_id, "84734")
        self.assertEqual(parsed.target_unit_id, "1")
        self.assertGreater(len(parsed.stats), 10)  # Should have many stat fields

    def test_effect_changed_parsing(self):
        """Test EFFECT_CHANGED entry parsing."""
        # Test GAINED effect
        entry = self.parser.parse_line(self.sample_lines['effect_changed_gained'])
        parsed = self.parser.parse_effect_changed(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.timestamp, 2928)
        self.assertEqual(parsed.effect_type, "GAINED")
        self.assertEqual(parsed.target_unit_id, "1")
        self.assertEqual(parsed.source_unit_id, "4021667")
        self.assertEqual(parsed.ability_id, "84734")
        self.assertEqual(parsed.stacks, "1")
        self.assertGreater(len(parsed.target_stats), 5)
        
        # Test FADED effect
        entry = self.parser.parse_line(self.sample_lines['effect_changed_faded'])
        parsed = self.parser.parse_effect_changed(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.effect_type, "FADED")
        self.assertEqual(parsed.target_unit_id, "1")
        self.assertEqual(parsed.source_unit_id, "4021288")
        
        # Test UPDATED effect
        entry = self.parser.parse_line(self.sample_lines['effect_changed_updated'])
        parsed = self.parser.parse_effect_changed(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.effect_type, "UPDATED")

    def test_player_info_parsing(self):
        """Test PLAYER_INFO entry parsing - the most complex one."""
        entry = self.parser.parse_line(self.sample_lines['player_info'])
        parsed = self.parser.parse_player_info(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.timestamp, 40604)
        self.assertEqual(parsed.unit_id, "1")
        
        # Test ability IDs parsing
        self.assertGreater(len(parsed.ability_ids), 50)  # Should have many abilities
        self.assertEqual(parsed.ability_ids[0], "142210")
        self.assertEqual(parsed.ability_ids[1], "142079")
        self.assertEqual(parsed.ability_ids[2], "84731")
        
        # Test ability levels parsing
        self.assertEqual(len(parsed.ability_levels), len(parsed.ability_ids))
        self.assertEqual(parsed.ability_levels[0], "1")
        
        # Test gear data parsing - ESO logs have 13 gear slots
        self.assertEqual(len(parsed.gear_data), 13)  # Should have exactly 13 gear slots
        
        # Find the HEAD gear item (could be in any position)
        head_gear = None
        for gear_item in parsed.gear_data:
            if gear_item[0] == "HEAD":
                head_gear = gear_item
                break
        self.assertIsNotNone(head_gear)
        self.assertEqual(head_gear[1], "95044")
        
        # Verify we have the expected ESO gear slots
        expected_slots = {'HEAD', 'SHOULDERS', 'HAND', 'LEGS', 'CHEST', 'WAIST', 'FEET', 
                         'NECK', 'RING1', 'RING2', 'MAIN_HAND', 'OFF_HAND', 'BACKUP_MAIN'}
        actual_slots = {gear_item[0] for gear_item in parsed.gear_data}
        self.assertEqual(actual_slots, expected_slots)
        
        # Test champion points
        self.assertGreater(len(parsed.champion_points), 0)
        self.assertEqual(parsed.champion_points[0], "183006")
        
        # Test additional data
        self.assertGreater(len(parsed.additional_data), 0)

    def test_equipped_abilities_extraction(self):
        """Test extraction of equipped abilities from PLAYER_INFO."""
        # First, add some abilities to the cache
        self.parser.ability_cache["84731"] = "Witchmother's Potent Brew"
        self.parser.ability_cache["220015"] = "Lucent Echoes"
        self.parser.ability_cache["142210"] = "Some Ability"
        
        # Parse PLAYER_INFO
        entry = self.parser.parse_line(self.sample_lines['player_info'])
        parsed = self.parser.parse_player_info(entry)
        
        # Get equipped abilities
        equipped_abilities = self.parser.get_equipped_abilities(parsed)
        
        # Should contain the abilities we cached
        self.assertIn("Witchmother's Potent Brew", equipped_abilities)
        self.assertIn("Lucent Echoes", equipped_abilities)
        self.assertIn("Some Ability", equipped_abilities)

    def test_invalid_entries(self):
        """Test handling of invalid entries."""
        # Test empty line
        entry = self.parser.parse_line("")
        self.assertIsNone(entry)
        
        # Test malformed line
        entry = self.parser.parse_line("invalid")
        self.assertIsNone(entry)
        
        # Test incomplete UNIT_ADDED
        entry = self.parser.parse_line("5,UNIT_ADDED,1")
        parsed = self.parser.parse_unit_added(entry)
        self.assertIsNone(parsed)
        
        # Test incomplete ABILITY_INFO
        entry = self.parser.parse_line("2928,ABILITY_INFO")
        parsed = self.parser.parse_ability_info(entry)
        self.assertIsNone(parsed)

    def test_edge_cases(self):
        """Test edge cases and special characters."""
        # Test quoted fields with commas
        line = '2928,ABILITY_INFO,84734,"Ability with, comma in name","/path/to/icon.dds",T,T'
        entry = self.parser.parse_line(line)
        parsed = self.parser.parse_ability_info(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.ability_name, "Ability with, comma in name")
        
        # Test empty strings in UNIT_ADDED
        line = '5,UNIT_ADDED,30,PLAYER,F,2,0,F,6,1,"","",0,50,787,0,PLAYER_ALLY,F'
        entry = self.parser.parse_line(line)
        parsed = self.parser.parse_unit_added(entry)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.name, "")
        self.assertEqual(parsed.handle, "")


if __name__ == '__main__':
    unittest.main()
