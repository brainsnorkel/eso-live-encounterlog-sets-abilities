#!/usr/bin/env python3
"""
Unit tests for log splitting functionality.
"""

import unittest
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fixtures'))

from esolog_tail import LogSplitter, ESOLogEntry
from sample_data import SAMPLE_LOG_LINES


class TestLogSplitter(unittest.TestCase):
    """Test LogSplitter functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = Path(self.temp_dir) / "Encounter.log"
        self.split_dir = Path(self.temp_dir) / "splits"
        
        # Create a mock log file
        self.log_file.touch()
        
        self.splitter = LogSplitter(self.log_file, diagnostic=False, split_dir=self.split_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up any open files
        if hasattr(self.splitter, 'file_handle') and self.splitter.file_handle:
            self.splitter.file_handle.close()
        
        # Remove temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test LogSplitter initialization."""
        self.assertEqual(self.splitter.log_file, self.log_file)
        self.assertEqual(self.splitter.split_dir, self.split_dir)
        self.assertIsNone(self.splitter.current_split_file)
        self.assertIsNone(self.splitter.current_split_path)
        self.assertFalse(self.splitter.combat_started)
        self.assertEqual(self.splitter.split_files, [])
        
        # Verify split directory was created
        self.assertTrue(self.split_dir.exists())
        self.assertTrue(self.split_dir.is_dir())
    
    def test_start_encounter_with_zone(self):
        """Test starting an encounter with zone information."""
        # Create a mock BEGIN_LOG entry with proper timestamp
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        
        # Start encounter with zone info
        self.splitter.start_encounter(begin_log_entry, "Coral Aerie", "VETERAN")
        
        # Verify encounter state
        self.assertEqual(self.splitter.pending_begin_log, begin_log_entry)
        self.assertEqual(self.splitter.current_zone, "Coral Aerie")
        self.assertEqual(self.splitter.current_difficulty, "VETERAN")
        self.assertIsNotNone(self.splitter.current_split_path)
        self.assertIsNotNone(self.splitter.file_handle)
        
        # Verify file was created and named correctly (should be renamed immediately when zone is provided)
        self.assertTrue(self.splitter.current_split_path.exists())
        self.assertIn("Coral-Aerie", str(self.splitter.current_split_path))
        self.assertIn("-vet", str(self.splitter.current_split_path))
    
    def test_start_encounter_without_zone(self):
        """Test starting an encounter without zone information."""
        # Create a mock BEGIN_LOG entry
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        
        # Start encounter without zone info
        self.splitter.start_encounter(begin_log_entry)
        
        # Verify encounter state
        self.assertEqual(self.splitter.pending_begin_log, begin_log_entry)
        self.assertEqual(self.splitter.current_zone, "")
        self.assertEqual(self.splitter.current_difficulty, "")
        self.assertIsNotNone(self.splitter.temp_file_path)
        
        # Should have temp file and current_split_path points to it
        self.assertTrue(self.splitter.temp_file_path.exists())
        self.assertIsNotNone(self.splitter.current_split_path)
        self.assertIn("-temp.log", str(self.splitter.current_split_path))
    
    def test_handle_zone_change(self):
        """Test handling zone changes."""
        # Start encounter without zone
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        self.splitter.start_encounter(begin_log_entry)
        
        # Handle zone change
        self.splitter.handle_zone_change("Spindleclutch II", "NORMAL")
        
        # Verify zone was updated
        self.assertEqual(self.splitter.current_zone, "Spindleclutch II")
        self.assertEqual(self.splitter.current_difficulty, "NORMAL")
        
        # File should still be temp file until combat starts
        self.assertIsNotNone(self.splitter.current_split_path)
        self.assertIn("-temp.log", str(self.splitter.current_split_path))
        
        # Start combat to trigger rename
        self.splitter.start_combat()
        
        # Now should be renamed to final file
        self.assertIn("Spindleclutch-II", str(self.splitter.current_split_path))
        self.assertNotIn("-vet", str(self.splitter.current_split_path))  # Normal difficulty
    
    def test_start_combat(self):
        """Test starting combat."""
        # Start encounter
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        self.splitter.start_encounter(begin_log_entry, "Coral Aerie", "VETERAN")
        
        # Start combat
        self.splitter.start_combat()
        
        # Verify combat started
        self.assertTrue(self.splitter.combat_started)
    
    def test_write_log_line(self):
        """Test writing log lines to split file."""
        # Start encounter
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        self.splitter.start_encounter(begin_log_entry, "Test Zone", "NORMAL")
        
        # Write some log lines
        test_lines = [
            '1000,BEGIN_LOG,1755729685851,15,"NA Megaserver","en","eso.live.11.1"',
            '1001,ZONE_CHANGED,1301,"Test Zone",NORMAL',
            '1002,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Test Player","@test",123,50,3084,0,PLAYER_ALLY,T'
        ]
        
        for line in test_lines:
            self.splitter.write_log_line(line)
        
        # Get the file path before closing
        file_path = self.splitter.current_split_path
        
        # Close file and verify content
        self.splitter.end_encounter()
        
        # Read back the file content
        with open(file_path, 'r') as f:
            content = f.read()
        
        for line in test_lines:
            self.assertIn(line, content)
    
    def test_end_encounter(self):
        """Test ending an encounter."""
        # Start encounter
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        self.splitter.start_encounter(begin_log_entry, "Test Zone", "NORMAL")
        
        # Write some content
        self.splitter.write_log_line("test line")
        
        # End encounter
        self.splitter.end_encounter()
        
        # Verify cleanup - current_split_file and current_split_path should be None after end_encounter
        self.assertIsNone(self.splitter.current_split_file)
        self.assertIsNone(self.splitter.current_split_path)
        self.assertIsNone(self.splitter.file_handle)
        self.assertIsNone(self.splitter.pending_begin_log)
        self.assertFalse(self.splitter.combat_started)
        
        # Verify file was added to split_files list
        self.assertEqual(len(self.splitter.split_files), 1)
    
    def test_file_naming_conventions(self):
        """Test file naming conventions for different scenarios."""
        # Test with timestamp and zone - use actual timestamp from BEGIN_LOG
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        
        # Test veteran zone
        self.splitter.start_encounter(begin_log_entry, "Coral Aerie", "VETERAN")
        self.assertIn("Coral-Aerie-vet", str(self.splitter.current_split_path))
        self.splitter.end_encounter()
        
        # Test normal zone with spaces
        self.splitter.start_encounter(begin_log_entry, "Spindleclutch II", "NORMAL")
        self.assertIn("Spindleclutch-II", str(self.splitter.current_split_path))
        self.assertNotIn("-vet", str(self.splitter.current_split_path))
        self.splitter.end_encounter()
        
        # Test zone with special characters
        self.splitter.start_encounter(begin_log_entry, "Tempest Island", "NORMAL")
        self.assertIn("Tempest-Island", str(self.splitter.current_split_path))
        self.splitter.end_encounter()
    
    def test_multiple_encounters(self):
        """Test handling multiple encounters."""
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        
        # First encounter
        self.splitter.start_encounter(begin_log_entry, "Zone 1", "NORMAL")
        self.splitter.write_log_line("encounter 1 line")
        self.splitter.end_encounter()
        
        # Second encounter
        self.splitter.start_encounter(begin_log_entry, "Zone 2", "VETERAN")
        self.splitter.write_log_line("encounter 2 line")
        self.splitter.end_encounter()
        
        # Verify both files were created
        self.assertEqual(len(self.splitter.split_files), 2)
        
        # Verify both files exist and have correct content
        for i, split_file in enumerate(self.splitter.split_files, 1):
            self.assertTrue(split_file.exists())
            with open(split_file, 'r') as f:
                content = f.read()
            self.assertIn(f"encounter {i} line", content)
    
    def test_close_for_waiting_and_reopen(self):
        """Test closing file for waiting and reopening."""
        # Start encounter
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        self.splitter.start_encounter(begin_log_entry, "Test Zone", "NORMAL")
        
        # Write initial content
        self.splitter.write_log_line("initial line")
        
        # Get file path before closing
        file_path = self.splitter.current_split_path
        
        # Close for waiting
        self.splitter.close_for_waiting()
        self.assertIsNone(self.splitter.file_handle)
        
        # Reopen for append
        self.splitter.reopen_for_append()
        self.assertIsNotNone(self.splitter.file_handle)
        
        # Write more content
        self.splitter.write_log_line("appended line")
        
        # End encounter and verify both lines are present
        self.splitter.end_encounter()
        
        # Read the file content
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Both lines should be present
        self.assertIn("initial line", content)
        self.assertIn("appended line", content)
    
    def test_cleanup(self):
        """Test cleanup functionality."""
        # Start encounter
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        self.splitter.start_encounter(begin_log_entry, "Test Zone", "NORMAL")
        
        # Write content
        self.splitter.write_log_line("test line")
        
        # Cleanup
        self.splitter.cleanup()
        
        # Verify cleanup - cleanup calls end_encounter which should clear these
        self.assertIsNone(self.splitter.current_split_file)
        self.assertIsNone(self.splitter.current_split_path)
        self.assertIsNone(self.splitter.file_handle)
    
    def test_custom_split_directory(self):
        """Test using custom split directory."""
        custom_dir = Path(self.temp_dir) / "custom_splits"
        
        splitter = LogSplitter(self.log_file, diagnostic=False, split_dir=custom_dir)
        
        # Verify custom directory was created
        self.assertTrue(custom_dir.exists())
        self.assertEqual(splitter.split_dir, custom_dir)
        
        # Clean up
        if hasattr(splitter, 'file_handle') and splitter.file_handle:
            splitter.file_handle.close()
    
    def test_zone_name_sanitization(self):
        """Test that zone names are properly sanitized for file names."""
        begin_log_entry = ESOLogEntry(1755729685851, "BEGIN_LOG", ["1755729685851", "15", "NA Megaserver", "en", "eso.live.11.1"])
        
        # Test various zone name formats
        test_cases = [
            ("Coral Aerie", "Coral-Aerie"),
            ("Spindleclutch II", "Spindleclutch-II"),
            ("Tempest Island", "Tempest-Island"),
            ("Wayrest Sewers I", "Wayrest-Sewers-I"),
            ("City of Ash II", "City-of-Ash-II")
        ]
        
        for zone_name, expected in test_cases:
            self.splitter.start_encounter(begin_log_entry, zone_name, "NORMAL")
            self.assertIn(expected, str(self.splitter.current_split_path))
            self.splitter.end_encounter()


if __name__ == '__main__':
    unittest.main()
