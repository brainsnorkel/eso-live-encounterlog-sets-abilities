#!/usr/bin/env python3
"""
Unit tests for new log entry types
Tests HEALTH_REGEN and endless dungeon events using real example data.
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from eso_log_structures import (
    ESOLogStructureParser,
    HealthRegenEntry,
    EndlessDungeonBeginEntry,
    EndlessDungeonStageEndEntry,
    EndlessDungeonBuffAddedEntry,
    EndlessDungeonBuffRemovedEntry,
    EventType
)


class TestNewLogEntryTypes(unittest.TestCase):
    """Test suite for new log entry types using real example data."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = ESOLogStructureParser()
        
        # Real example data from the encounter log
        self.sample_lines = {
            'health_regen': '252431,HEALTH_REGEN,898,72,19576/19576,14844/15729,32560/33221,500/500,1000/1000,0,0.6681,0.9093,5.7946',
            'endless_dungeon_begin': '11147,ENDLESS_DUNGEON_BEGIN,1,1758511859000,T',
            'endless_dungeon_stage_end': '53960,ENDLESS_DUNGEON_STAGE_END,1,1758511859000',
            'endless_dungeon_buff_added': '66452,ENDLESS_DUNGEON_BUFF_ADDED,1,200018',
            'endless_dungeon_buff_removed': '146276,ENDLESS_DUNGEON_BUFF_REMOVED,1,200020',
        }

    def test_health_regen_entry_parsing(self):
        """Test HEALTH_REGEN entry parsing."""
        line = self.sample_lines['health_regen']
        
        # Test direct parsing
        entry = HealthRegenEntry.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.line_number, 252431)
        self.assertEqual(entry.effective_regen, 898)
        self.assertEqual(entry.unit_id, 72)
        self.assertEqual(entry.health_current, 19576)
        self.assertEqual(entry.health_max, 19576)
        self.assertEqual(entry.magicka_current, 14844)
        self.assertEqual(entry.magicka_max, 15729)
        self.assertEqual(entry.stamina_current, 32560)
        self.assertEqual(entry.stamina_max, 33221)
        self.assertEqual(entry.ultimate_current, 500)
        self.assertEqual(entry.ultimate_max, 500)
        self.assertEqual(entry.werewolf_current, 1000)
        self.assertEqual(entry.werewolf_max, 1000)
        self.assertEqual(entry.shield, 0)
        self.assertEqual(entry.map_normalized_x, 0.6681)
        self.assertEqual(entry.map_normalized_y, 0.9093)
        self.assertEqual(entry.heading_radians, 5.7946)
        
        # Test structured parser
        structured_entry = self.parser.parse_line(line)
        self.assertIsNotNone(structured_entry)
        self.assertIsInstance(structured_entry, HealthRegenEntry)
        self.assertEqual(structured_entry.line_number, 252431)

    def test_endless_dungeon_begin_entry_parsing(self):
        """Test ENDLESS_DUNGEON_BEGIN entry parsing."""
        line = self.sample_lines['endless_dungeon_begin']
        
        # Test direct parsing
        entry = EndlessDungeonBeginEntry.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.line_number, 11147)
        self.assertEqual(entry.dungeon_id, 1)
        self.assertEqual(entry.start_time_ms, 1758511859000)
        self.assertEqual(entry.unknown_boolean, True)
        
        # Test structured parser
        structured_entry = self.parser.parse_line(line)
        self.assertIsNotNone(structured_entry)
        self.assertIsInstance(structured_entry, EndlessDungeonBeginEntry)
        self.assertEqual(structured_entry.line_number, 11147)

    def test_endless_dungeon_stage_end_entry_parsing(self):
        """Test ENDLESS_DUNGEON_STAGE_END entry parsing."""
        line = self.sample_lines['endless_dungeon_stage_end']
        
        # Test direct parsing
        entry = EndlessDungeonStageEndEntry.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.line_number, 53960)
        self.assertEqual(entry.dungeon_id, 1)
        self.assertEqual(entry.dungeon_begin_start_time_ms, 1758511859000)
        
        # Test structured parser
        structured_entry = self.parser.parse_line(line)
        self.assertIsNotNone(structured_entry)
        self.assertIsInstance(structured_entry, EndlessDungeonStageEndEntry)
        self.assertEqual(structured_entry.line_number, 53960)

    def test_endless_dungeon_buff_added_entry_parsing(self):
        """Test ENDLESS_DUNGEON_BUFF_ADDED entry parsing."""
        line = self.sample_lines['endless_dungeon_buff_added']
        
        # Test direct parsing
        entry = EndlessDungeonBuffAddedEntry.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.line_number, 66452)
        self.assertEqual(entry.dungeon_id, 1)
        self.assertEqual(entry.ability_id, 200018)
        
        # Test structured parser
        structured_entry = self.parser.parse_line(line)
        self.assertIsNotNone(structured_entry)
        self.assertIsInstance(structured_entry, EndlessDungeonBuffAddedEntry)
        self.assertEqual(structured_entry.line_number, 66452)

    def test_endless_dungeon_buff_removed_entry_parsing(self):
        """Test ENDLESS_DUNGEON_BUFF_REMOVED entry parsing."""
        line = self.sample_lines['endless_dungeon_buff_removed']
        
        # Test direct parsing
        entry = EndlessDungeonBuffRemovedEntry.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.line_number, 146276)
        self.assertEqual(entry.dungeon_id, 1)
        self.assertEqual(entry.ability_id, 200020)
        
        # Test structured parser
        structured_entry = self.parser.parse_line(line)
        self.assertIsNotNone(structured_entry)
        self.assertIsInstance(structured_entry, EndlessDungeonBuffRemovedEntry)
        self.assertEqual(structured_entry.line_number, 146276)

    def test_event_type_enum_values(self):
        """Test that EventType enum contains the new event types."""
        self.assertEqual(EventType.HEALTH_REGEN.value, "HEALTH_REGEN")
        self.assertEqual(EventType.ENDLESS_DUNGEON_BEGIN.value, "ENDLESS_DUNGEON_BEGIN")
        self.assertEqual(EventType.ENDLESS_DUNGEON_STAGE_END.value, "ENDLESS_DUNGEON_STAGE_END")
        self.assertEqual(EventType.ENDLESS_DUNGEON_BUFF_ADDED.value, "ENDLESS_DUNGEON_BUFF_ADDED")
        self.assertEqual(EventType.ENDLESS_DUNGEON_BUFF_REMOVED.value, "ENDLESS_DUNGEON_BUFF_REMOVED")

    def test_parser_dictionary_includes_new_types(self):
        """Test that the parser dictionary includes the new event types."""
        parsers = self.parser.PARSERS
        self.assertIn(EventType.HEALTH_REGEN, parsers)
        self.assertIn(EventType.ENDLESS_DUNGEON_BEGIN, parsers)
        self.assertIn(EventType.ENDLESS_DUNGEON_STAGE_END, parsers)
        self.assertIn(EventType.ENDLESS_DUNGEON_BUFF_ADDED, parsers)
        self.assertIn(EventType.ENDLESS_DUNGEON_BUFF_REMOVED, parsers)

    def test_invalid_line_handling(self):
        """Test that invalid lines return None."""
        invalid_lines = [
            "invalid,line",
            "123,UNKNOWN_EVENT,data",
            "123,HEALTH_REGEN",  # Too few fields
            "123,ENDLESS_DUNGEON_BEGIN",  # Too few fields
        ]
        
        for line in invalid_lines:
            result = self.parser.parse_line(line)
            self.assertIsNone(result, f"Expected None for invalid line: {line}")

    def test_health_regen_edge_cases(self):
        """Test HEALTH_REGEN parsing with edge cases."""
        # Test with different health/magicka/stamina values
        line = "123456,HEALTH_REGEN,0,1,0/1000,0/2000,0/3000,0/500,0/1000,0,0.0,0.0,0.0"
        entry = HealthRegenEntry.parse(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.effective_regen, 0)
        self.assertEqual(entry.health_current, 0)
        self.assertEqual(entry.health_max, 1000)
        self.assertEqual(entry.magicka_current, 0)
        self.assertEqual(entry.magicka_max, 2000)

    def test_endless_dungeon_boolean_handling(self):
        """Test ENDLESS_DUNGEON_BEGIN boolean field handling."""
        # Test with False
        line_false = "11147,ENDLESS_DUNGEON_BEGIN,1,1758511859000,F"
        entry_false = EndlessDungeonBeginEntry.parse(line_false)
        self.assertIsNotNone(entry_false)
        self.assertEqual(entry_false.unknown_boolean, False)
        
        # Test with True
        line_true = "11147,ENDLESS_DUNGEON_BEGIN,1,1758511859000,T"
        entry_true = EndlessDungeonBeginEntry.parse(line_true)
        self.assertIsNotNone(entry_true)
        self.assertEqual(entry_true.unknown_boolean, True)

    def test_structured_parser_event_type_detection(self):
        """Test that structured parser correctly detects new event types."""
        test_cases = [
            ("HEALTH_REGEN", self.sample_lines['health_regen']),
            ("ENDLESS_DUNGEON_BEGIN", self.sample_lines['endless_dungeon_begin']),
            ("ENDLESS_DUNGEON_STAGE_END", self.sample_lines['endless_dungeon_stage_end']),
            ("ENDLESS_DUNGEON_BUFF_ADDED", self.sample_lines['endless_dungeon_buff_added']),
            ("ENDLESS_DUNGEON_BUFF_REMOVED", self.sample_lines['endless_dungeon_buff_removed']),
        ]
        
        for expected_type, line in test_cases:
            entry = self.parser.parse_line(line)
            self.assertIsNotNone(entry, f"Failed to parse {expected_type}")
            # Check that the entry has the expected attributes
            self.assertTrue(hasattr(entry, 'line_number'), f"{expected_type} entry missing line_number")

    def test_multiple_health_regen_entries(self):
        """Test parsing multiple HEALTH_REGEN entries with different values."""
        lines = [
            "252431,HEALTH_REGEN,898,72,19576/19576,14844/15729,32560/33221,500/500,1000/1000,0,0.6681,0.9093,5.7946",
            "309502,HEALTH_REGEN,2273,77,38183/39960,14506/17152,16524/16524,241/500,1000/1000,14709,93.8287,299.3488,0.9687",
            "311504,HEALTH_REGEN,2069,77,39960/39960,16816/17152,16524/16524,241/500,1000/1000,14709,93.8137,299.3377,0.9329",
        ]
        
        for line in lines:
            entry = self.parser.parse_line(line)
            self.assertIsNotNone(entry)
            self.assertIsInstance(entry, HealthRegenEntry)
            # Verify basic structure
            self.assertGreater(entry.line_number, 0)
            self.assertGreaterEqual(entry.effective_regen, 0)
            self.assertGreater(entry.unit_id, 0)


if __name__ == '__main__':
    unittest.main()
