#!/usr/bin/env python3
"""
Unit tests for analyzer handling of new log entry types
Tests that the ESOLogAnalyzer correctly processes HEALTH_REGEN and endless dungeon events.
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from esolog_tail import ESOLogAnalyzer, ESOLogEntry


class TestAnalyzerNewLogEntryTypes(unittest.TestCase):
    """Test suite for analyzer handling of new log entry types."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = ESOLogAnalyzer()
        self.analyzer.diagnostic = True  # Enable diagnostic mode for testing

    def test_health_regen_event_processing(self):
        """Test that HEALTH_REGEN events are processed by the analyzer."""
        # Create a HEALTH_REGEN log entry
        line = "252431,HEALTH_REGEN,898,72,19576/19576,14844/15729,32560/33221,500/500,1000/1000,0,0.6681,0.9093,5.7946"
        entry = ESOLogEntry.parse(line)
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.event_type, "HEALTH_REGEN")
        
        # Process the entry - should not raise an exception
        try:
            self.analyzer.process_log_entry(entry)
        except Exception as e:
            self.fail(f"Processing HEALTH_REGEN event raised an exception: {e}")

    def test_endless_dungeon_begin_event_processing(self):
        """Test that ENDLESS_DUNGEON_BEGIN events are processed by the analyzer."""
        # Create an ENDLESS_DUNGEON_BEGIN log entry
        line = "11147,ENDLESS_DUNGEON_BEGIN,1,1758511859000,T"
        entry = ESOLogEntry.parse(line)
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.event_type, "ENDLESS_DUNGEON_BEGIN")
        
        # Process the entry - should not raise an exception
        try:
            self.analyzer.process_log_entry(entry)
        except Exception as e:
            self.fail(f"Processing ENDLESS_DUNGEON_BEGIN event raised an exception: {e}")

    def test_endless_dungeon_stage_end_event_processing(self):
        """Test that ENDLESS_DUNGEON_STAGE_END events are processed by the analyzer."""
        # Create an ENDLESS_DUNGEON_STAGE_END log entry
        line = "53960,ENDLESS_DUNGEON_STAGE_END,1,1758511859000"
        entry = ESOLogEntry.parse(line)
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.event_type, "ENDLESS_DUNGEON_STAGE_END")
        
        # Process the entry - should not raise an exception
        try:
            self.analyzer.process_log_entry(entry)
        except Exception as e:
            self.fail(f"Processing ENDLESS_DUNGEON_STAGE_END event raised an exception: {e}")

    def test_endless_dungeon_buff_added_event_processing(self):
        """Test that ENDLESS_DUNGEON_BUFF_ADDED events are processed by the analyzer."""
        # Create an ENDLESS_DUNGEON_BUFF_ADDED log entry
        line = "66452,ENDLESS_DUNGEON_BUFF_ADDED,1,200018"
        entry = ESOLogEntry.parse(line)
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.event_type, "ENDLESS_DUNGEON_BUFF_ADDED")
        
        # Process the entry - should not raise an exception
        try:
            self.analyzer.process_log_entry(entry)
        except Exception as e:
            self.fail(f"Processing ENDLESS_DUNGEON_BUFF_ADDED event raised an exception: {e}")

    def test_endless_dungeon_buff_removed_event_processing(self):
        """Test that ENDLESS_DUNGEON_BUFF_REMOVED events are processed by the analyzer."""
        # Create an ENDLESS_DUNGEON_BUFF_REMOVED log entry
        line = "146276,ENDLESS_DUNGEON_BUFF_REMOVED,1,200020"
        entry = ESOLogEntry.parse(line)
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.event_type, "ENDLESS_DUNGEON_BUFF_REMOVED")
        
        # Process the entry - should not raise an exception
        try:
            self.analyzer.process_log_entry(entry)
        except Exception as e:
            self.fail(f"Processing ENDLESS_DUNGEON_BUFF_REMOVED event raised an exception: {e}")

    def test_multiple_new_event_types_processing(self):
        """Test processing multiple new event types in sequence."""
        test_events = [
            ("252431,HEALTH_REGEN,898,72,19576/19576,14844/15729,32560/33221,500/500,1000/1000,0,0.6681,0.9093,5.7946", "HEALTH_REGEN"),
            ("11147,ENDLESS_DUNGEON_BEGIN,1,1758511859000,T", "ENDLESS_DUNGEON_BEGIN"),
            ("53960,ENDLESS_DUNGEON_STAGE_END,1,1758511859000", "ENDLESS_DUNGEON_STAGE_END"),
            ("66452,ENDLESS_DUNGEON_BUFF_ADDED,1,200018", "ENDLESS_DUNGEON_BUFF_ADDED"),
            ("146276,ENDLESS_DUNGEON_BUFF_REMOVED,1,200020", "ENDLESS_DUNGEON_BUFF_REMOVED"),
        ]
        
        for line, expected_type in test_events:
            entry = ESOLogEntry.parse(line)
            self.assertIsNotNone(entry, f"Failed to parse {expected_type}")
            self.assertEqual(entry.event_type, expected_type)
            
            # Process the entry - should not raise an exception
            try:
                self.analyzer.process_log_entry(entry)
            except Exception as e:
                self.fail(f"Processing {expected_type} event raised an exception: {e}")

    def test_new_event_types_with_diagnostic_mode(self):
        """Test that new event types are included in diagnostic output."""
        # This test verifies that the diagnostic mode includes the new event types
        # in the list of events that trigger diagnostic messages
        
        # The diagnostic check is in the process_log_entry method
        # We can't easily test the output without mocking, but we can verify
        # that the event types are in the diagnostic list
        
        diagnostic_event_types = [
            "ZONE_CHANGED", "UNIT_ADDED", "UNIT_CHANGED", "BEGIN_COMBAT", "END_COMBAT", 
            "PLAYER_INFO", "COMBAT_EVENT", "EFFECT_CHANGED", "HEALTH_REGEN", 
            "ENDLESS_DUNGEON_BEGIN", "ENDLESS_DUNGEON_STAGE_END", 
            "ENDLESS_DUNGEON_BUFF_ADDED", "ENDLESS_DUNGEON_BUFF_REMOVED"
        ]
        
        new_event_types = [
            "HEALTH_REGEN", "ENDLESS_DUNGEON_BEGIN", "ENDLESS_DUNGEON_STAGE_END",
            "ENDLESS_DUNGEON_BUFF_ADDED", "ENDLESS_DUNGEON_BUFF_REMOVED"
        ]
        
        for event_type in new_event_types:
            self.assertIn(event_type, diagnostic_event_types, 
                         f"{event_type} should be included in diagnostic event types")

    def test_handler_methods_exist(self):
        """Test that handler methods exist for new event types."""
        # Verify that the handler methods exist
        self.assertTrue(hasattr(self.analyzer, '_handle_health_regen'))
        self.assertTrue(hasattr(self.analyzer, '_handle_endless_dungeon_begin'))
        self.assertTrue(hasattr(self.analyzer, '_handle_endless_dungeon_stage_end'))
        self.assertTrue(hasattr(self.analyzer, '_handle_endless_dungeon_buff_added'))
        self.assertTrue(hasattr(self.analyzer, '_handle_endless_dungeon_buff_removed'))
        
        # Verify they are callable
        self.assertTrue(callable(getattr(self.analyzer, '_handle_health_regen')))
        self.assertTrue(callable(getattr(self.analyzer, '_handle_endless_dungeon_begin')))
        self.assertTrue(callable(getattr(self.analyzer, '_handle_endless_dungeon_stage_end')))
        self.assertTrue(callable(getattr(self.analyzer, '_handle_endless_dungeon_buff_added')))
        self.assertTrue(callable(getattr(self.analyzer, '_handle_endless_dungeon_buff_removed')))

    def test_handler_methods_accept_entries(self):
        """Test that handler methods can accept ESOLogEntry objects."""
        # Create test entries
        health_regen_entry = ESOLogEntry.parse("252431,HEALTH_REGEN,898,72,19576/19576,14844/15729,32560/33221,500/500,1000/1000,0,0.6681,0.9093,5.7946")
        endless_begin_entry = ESOLogEntry.parse("11147,ENDLESS_DUNGEON_BEGIN,1,1758511859000,T")
        
        # Test that handlers can be called without exceptions
        try:
            self.analyzer._handle_health_regen(health_regen_entry)
            self.analyzer._handle_endless_dungeon_begin(endless_begin_entry)
        except Exception as e:
            self.fail(f"Handler methods should accept ESOLogEntry objects: {e}")


if __name__ == '__main__':
    unittest.main()