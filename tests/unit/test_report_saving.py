#!/usr/bin/env python3
"""
Unit tests for report saving functionality.
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

from esolog_tail import ESOLogAnalyzer, CombatEncounter, PlayerInfo
from sample_data import SAMPLE_LOG_LINES


class TestReportSaving(unittest.TestCase):
    """Test report saving functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.reports_dir = Path(self.temp_dir) / "reports"
        self.log_file = Path(self.temp_dir) / "Encounter.log"
        
        # Create a mock log file
        self.log_file.touch()
        
        # Create analyzer with report saving enabled
        self.analyzer = ESOLogAnalyzer(
            save_reports=True,
            reports_dir=self.reports_dir,
            diagnostic=False
        )
        self.analyzer.current_log_file = str(self.log_file)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization_with_reports(self):
        """Test analyzer initialization with report saving enabled."""
        self.assertTrue(self.analyzer.save_reports)
        self.assertEqual(self.analyzer.reports_dir, self.reports_dir)
        self.assertEqual(self.analyzer.report_buffer, [])
    
    def test_initialization_without_reports(self):
        """Test analyzer initialization without report saving."""
        analyzer = ESOLogAnalyzer(save_reports=False)
        self.assertFalse(analyzer.save_reports)
        self.assertIsNone(analyzer.reports_dir)
    
    def test_print_and_buffer(self):
        """Test _print_and_buffer method."""
        # Test with report saving enabled
        test_message = "Test report message"
        self.analyzer._print_and_buffer(test_message)
        
        # Verify message was added to buffer
        self.assertIn(test_message, self.analyzer.report_buffer)
    
    def test_save_report_to_file_basic(self):
        """Test basic report saving functionality."""
        # Create a mock encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Add some content to report buffer
        self.analyzer.report_buffer = [
            "=== ESO Encounter Report ===",
            "Player: TestPlayer (@test)",
            "Class: Arcanist",
            "Damage: 1,000"
        ]
        
        # Save report
        self.analyzer._save_report_to_file()
        
        # Verify reports directory was created
        self.assertTrue(self.reports_dir.exists())
        
        # Find the report file
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        # Verify file content
        with open(report_files[0], 'r') as f:
            content = f.read()
        
        for line in self.analyzer.report_buffer:
            self.assertIn(line, content)
    
    def test_save_report_with_zone_info(self):
        """Test report saving with zone information."""
        # Set zone information
        self.analyzer.current_zone = "Coral Aerie"
        self.analyzer.current_difficulty = "VETERAN"
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Add content to buffer
        self.analyzer.report_buffer = ["Test report content"]
        
        # Save report
        self.analyzer._save_report_to_file()
        
        # Find report file
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        # Verify file name includes zone and difficulty
        report_file = report_files[0]
        self.assertIn("Coral-Aerie", report_file.name)
        self.assertIn("-vet-report.txt", report_file.name)
    
    def test_save_report_without_zone_info(self):
        """Test report saving without zone information."""
        # No zone information set
        self.analyzer.current_zone = None
        self.analyzer.current_difficulty = None
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Add content to buffer
        self.analyzer.report_buffer = ["Test report content"]
        
        # Save report
        self.analyzer._save_report_to_file()
        
        # Find report file
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        # Verify file name uses Unknown-Zone
        report_file = report_files[0]
        self.assertIn("Unknown-Zone", report_file.name)
        self.assertIn("-report.txt", report_file.name)
    
    def test_save_report_empty_buffer(self):
        """Test saving report with empty buffer."""
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Empty buffer
        self.analyzer.report_buffer = []
        
        # Save report (should not create file)
        self.analyzer._save_report_to_file()
        
        # Verify no report file was created
        if self.reports_dir.exists():
            report_files = list(self.reports_dir.glob("*.txt"))
            self.assertEqual(len(report_files), 0)
    
    def test_save_report_no_encounter(self):
        """Test saving report without current encounter."""
        # No current encounter
        self.analyzer.current_encounter = None
        
        # Add content to buffer
        self.analyzer.report_buffer = ["Test content"]
        
        # Save report (should not create file)
        self.analyzer._save_report_to_file()
        
        # Verify no report file was created
        if self.reports_dir.exists():
            report_files = list(self.reports_dir.glob("*.txt"))
            self.assertEqual(len(report_files), 0)
    
    def test_save_report_default_directory(self):
        """Test report saving with default directory (same as log file)."""
        # Create analyzer without reports_dir
        analyzer = ESOLogAnalyzer(save_reports=True)
        analyzer.current_log_file = str(self.log_file)
        
        # Create encounter
        analyzer.current_encounter = CombatEncounter()
        analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Add content to buffer
        analyzer.report_buffer = ["Test report content"]
        
        # Mock timestamp
        with patch('time.localtime') as mock_time:
            mock_time.return_value = time.struct_time((2025, 1, 15, 14, 30, 22, 2, 15, 0))
            
            # Save report
            analyzer._save_report_to_file()
        
        # Verify report was saved in log file directory
        log_dir = self.log_file.parent
        report_files = list(log_dir.glob("*-report.txt"))
        self.assertEqual(len(report_files), 1)
    
    def test_save_report_directory_creation(self):
        """Test automatic directory creation for reports."""
        # Use a non-existent directory
        new_reports_dir = Path(self.temp_dir) / "new_reports"
        
        analyzer = ESOLogAnalyzer(save_reports=True, reports_dir=new_reports_dir)
        analyzer.current_log_file = str(self.log_file)
        
        # Create encounter
        analyzer.current_encounter = CombatEncounter()
        analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Add content to buffer
        analyzer.report_buffer = ["Test report content"]
        
        # Save report
        analyzer._save_report_to_file()
        
        # Verify directory was created
        self.assertTrue(new_reports_dir.exists())
        self.assertTrue(new_reports_dir.is_dir())
        
        # Verify report file was created
        report_files = list(new_reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
    
    def test_save_report_permission_error(self):
        """Test report saving with permission error."""
        # Create a directory that we can't write to (simulate permission error)
        read_only_dir = Path(self.temp_dir) / "read_only"
        read_only_dir.mkdir()
        
        # Make directory read-only (Unix-like systems)
        if hasattr(os, 'chmod'):
            os.chmod(read_only_dir, 0o444)
        
        analyzer = ESOLogAnalyzer(save_reports=True, reports_dir=read_only_dir)
        analyzer.current_log_file = str(self.log_file)
        
        # Create encounter
        analyzer.current_encounter = CombatEncounter()
        analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Add content to buffer
        analyzer.report_buffer = ["Test report content"]
        
        # This should exit with sys.exit(1) for permission errors
        with self.assertRaises(SystemExit):
            analyzer._save_report_to_file()
        
        # Restore permissions for cleanup
        if hasattr(os, 'chmod'):
            os.chmod(read_only_dir, 0o755)
    
    def test_multiple_reports(self):
        """Test saving multiple reports to zone collection."""
        # Create multiple encounters and add to zone collection
        for i in range(3):
            # Create new encounter
            self.analyzer.current_encounter = CombatEncounter()
            self.analyzer.current_encounter.add_player("1", f"Player{i}", f"@player{i}", "117")
            
            # Set different start times to ensure unique filenames
            self.analyzer.current_encounter.start_time = 1755729685851 + (i * 1000)
            
            # Set current zone for zone-based reporting
            self.analyzer.current_zone = "Test Zone"
            
            # Add content to buffer
            self.analyzer.report_buffer = [f"Report {i} content"]
            
            # Add to zone collection (new behavior)
            self.analyzer._add_report_to_zone()
        
        # Save zone report
        self.analyzer._save_zone_report("Test Zone")
        
        # Verify single zone report file was created
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        # Verify file contains all reports
        with open(report_files[0], 'r') as f:
            content = f.read()
        self.assertIn("Report 0 content", content)
        self.assertIn("Report 1 content", content)
        self.assertIn("Report 2 content", content)
    
    def test_report_filename_timestamp_format(self):
        """Test that report filenames have YYMMDDHHMMSS prefix format."""
        # Create encounter with players
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Set zone information
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "VETERAN"
        
        # Set a specific start time to test timestamp conversion
        # Use a 2025 timestamp: 2025-09-14 10:00:00
        self.analyzer.current_encounter.start_time = 0  # Relative timestamp in ms (start of log)
        
        # Mock the log_start_unix_timestamp for consistent testing
        # 2025-09-14 10:00:00 = 1757808000 seconds since epoch
        self.analyzer.log_start_unix_timestamp = 1757808000  # Unix timestamp in seconds
        
        # Add content to buffer
        self.analyzer.report_buffer = ["Test report content"]
        
        # Add to zone collection and save
        self.analyzer._add_report_to_zone()
        
        # Manually set zone_start_time to test the conversion
        self.analyzer.zone_start_time = 0  # Relative timestamp in ms
        
        self.analyzer._save_zone_report("Test Zone")
        
        # Verify report file was created
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        # Verify filename has YYMMDDHHMMSS prefix
        report_file = report_files[0]
        filename = report_file.name
        
        # Extract timestamp part (first 12 characters before the first dash)
        timestamp_part = filename.split('-')[0]
        
        # Verify timestamp format: YYMMDDHHMMSS (12 digits)
        self.assertEqual(len(timestamp_part), 12)
        self.assertTrue(timestamp_part.isdigit())
        
        # Verify the timestamp represents a reasonable date (not 1970)
        # The timestamp should be from 2025 (25xxxxxx) based on our test data
        self.assertTrue(timestamp_part.startswith('25'))
        
        # Verify the rest of the filename format
        self.assertIn("Test-Zone-vet-report.txt", filename)
        
        # Verify the full filename format: YYMMDDHHMMSS-Zone-Name-difficulty-report.txt
        expected_pattern = r'^\d{12}-Test-Zone-vet-report\.txt$'
        import re
        self.assertTrue(re.match(expected_pattern, filename), 
                       f"Filename '{filename}' does not match expected pattern")
    
    def test_report_file_naming_edge_cases(self):
        """Test report file naming with edge cases."""
        # Test various zone names and difficulties
        test_cases = [
            ("Coral Aerie", "VETERAN", "Coral-Aerie-vet"),
            ("Spindleclutch II", "NORMAL", "Spindleclutch-II"),
            ("Tempest Island", "NORMAL", "Tempest-Island"),
            ("", "VETERAN", "Unknown-Zone-vet"),
            (None, "NORMAL", "Unknown-Zone")
        ]
        
        for zone, difficulty, expected_name in test_cases:
            # Set zone information
            self.analyzer.current_zone = zone
            self.analyzer.current_difficulty = difficulty
            
            # Create encounter
            self.analyzer.current_encounter = CombatEncounter()
            self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
            
            # Add content to buffer
            self.analyzer.report_buffer = ["Test content"]
            
            # Mock timestamp
            with patch('time.localtime') as mock_time:
                mock_time.return_value = time.struct_time((2025, 1, 15, 14, 30, 22, 2, 15, 0))
                
                # Save report
                self.analyzer._save_report_to_file()
            
            # Find the report file
            report_files = list(self.reports_dir.glob("*.txt"))
            self.assertGreater(len(report_files), 0)
            
            # Check the most recent file
            latest_file = max(report_files, key=lambda f: f.stat().st_mtime)
            self.assertIn(expected_name, latest_file.name)
    
    def test_report_buffer_clearing(self):
        """Test that report buffer is properly managed."""
        # Add content to buffer
        self.analyzer.report_buffer = ["Line 1", "Line 2", "Line 3"]
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Save report
        self.analyzer._save_report_to_file()
        
        # Buffer should be cleared after saving (this is the actual behavior)
        self.assertEqual(len(self.analyzer.report_buffer), 0)
    
    def test_display_encounter_summary_with_reports(self):
        """Test that _display_encounter_summary triggers report saving."""
        # Create encounter with players
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        
        # Add equipped abilities so player appears in report
        player = self.analyzer.current_encounter.players["1"]
        player.equipped_abilities = ["12345", "67890"]
        
        # Set current zone for zone-based reporting
        self.analyzer.current_zone = "Test Zone"
        
        # Display encounter summary (should trigger report saving)
        self.analyzer._display_encounter_summary("Test Zone")
        
        # Verify report was added to zone collection (not saved as individual file)
        self.assertIn("Test Zone", self.analyzer.zone_reports)
        self.assertGreater(len(self.analyzer.zone_reports["Test Zone"]), 0)
        
        # Manually trigger zone report saving to test the save functionality
        self.analyzer._save_zone_report("Test Zone")
        
        # Verify report was saved
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        # Verify report content
        with open(report_files[0], 'r') as f:
            content = f.read()
        
        # Should contain encounter summary information
        self.assertIn("TestPlayer", content)
        self.assertIn("@test", content)


if __name__ == '__main__':
    unittest.main()
