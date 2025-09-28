"""
Comprehensive tests for timestamp format in report filenames to ensure correct YYMMDDHHMMSS prefix.
"""
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
import time

from src.esolog_tail import ESOLogAnalyzer, CombatEncounter


class TestTimestampFormat(unittest.TestCase):
    """Test timestamp format generation for report filenames."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.reports_dir = Path(self.temp_dir) / "reports"
        self.reports_dir.mkdir()
        
        # Create analyzer with report saving enabled
        self.analyzer = ESOLogAnalyzer(
            save_reports=True,
            reports_dir=self.reports_dir,
            diagnostic=True
        )

    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_timestamp_conversion_logic(self):
        """Test the timestamp conversion logic directly."""
        # Set up test data
        self.analyzer.log_start_unix_timestamp = 1757808000  # 2025-09-14 10:00:00
        self.analyzer.zone_start_time = 1000  # 1 second in milliseconds
        
        # Test the conversion method directly
        absolute_timestamp = self.analyzer.get_absolute_timestamp(1000)
        self.assertIsNotNone(absolute_timestamp, "get_absolute_timestamp should return a value")
        self.assertEqual(absolute_timestamp, 1757808001.0, "Should convert correctly")
        
        # Test datetime conversion
        dt = datetime.fromtimestamp(absolute_timestamp)
        timestamp_str = dt.strftime("%y%m%d%H%M%S")
        expected_timestamp = "250914100001"
        self.assertEqual(timestamp_str, expected_timestamp, f"Expected {expected_timestamp}, got {timestamp_str}")

    def test_zone_start_time_not_set(self):
        """Test behavior when zone_start_time is not set."""
        # Don't set zone_start_time
        self.analyzer.log_start_unix_timestamp = 1757808000
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone")
        self.analyzer._save_zone_report("Test Zone")
        
        # Check that report was created with current time timestamp
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        report_name = report_files[0].name
        timestamp_match = report_name.split('-')[0]
        
        # Should be current time (2025 format)
        self.assertTrue(timestamp_match.startswith('25'), f"Should start with '25' for 2025: {timestamp_match}")

    def test_zone_start_time_set_correctly(self):
        """Test behavior when zone_start_time is set correctly."""
        # Set up test data
        self.analyzer.log_start_unix_timestamp = 1757808000  # 2025-09-14 10:00:00
        self.analyzer.zone_start_time = 1000  # 1 second in milliseconds
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        # Debug the state before saving
        self.analyzer._display_encounter_summary("Test Zone")
        self.analyzer._save_zone_report("Test Zone")
        
        # Check that report was created with correct timestamp
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        report_name = report_files[0].name
        timestamp_match = report_name.split('-')[0]
        
        # Should be the calculated timestamp
        expected_timestamp = "250914100001"
        self.assertEqual(timestamp_match, expected_timestamp, f"Expected {expected_timestamp}, got {timestamp_match}")

    def test_log_start_unix_timestamp_not_set(self):
        """Test behavior when log_start_unix_timestamp is not set."""
        # Don't set log_start_unix_timestamp
        self.analyzer.zone_start_time = 1000
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone")
        self.analyzer._save_zone_report("Test Zone")
        
        # Check that report was created with current time timestamp
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        report_name = report_files[0].name
        timestamp_match = report_name.split('-')[0]
        
        # Should be current time (2025 format)
        self.assertTrue(timestamp_match.startswith('25'), f"Should start with '25' for 2025: {timestamp_match}")

    def test_timestamp_conversion_failure(self):
        """Test behavior when timestamp conversion fails."""
        # Set up test data that will cause conversion to fail
        self.analyzer.log_start_unix_timestamp = None  # This will cause get_absolute_timestamp to return None
        self.analyzer.zone_start_time = 1000
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone")
        self.analyzer._save_zone_report("Test Zone")
        
        # Check that report was created with current time timestamp
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        report_name = report_files[0].name
        timestamp_match = report_name.split('-')[0]
        
        # Should be current time (2025 format)
        self.assertTrue(timestamp_match.startswith('25'), f"Should start with '25' for 2025: {timestamp_match}")

    def test_multiple_timestamps_consistency(self):
        """Test that multiple reports use consistent timestamp logic."""
        # Set up test data
        self.analyzer.log_start_unix_timestamp = 1757808000  # 2025-09-14 10:00:00
        self.analyzer.zone_start_time = 1000  # 1 second in milliseconds
        
        # Create multiple encounters in different zones
        zones = ["Zone A", "Zone B", "Zone C"]
        
        for i, zone in enumerate(zones):
            self.analyzer.current_encounter = CombatEncounter()
            self.analyzer.current_encounter.add_player(f"{i+1}", f"Player{i+1}", f"@player{i+1}", "117")
            self.analyzer.current_zone = zone
            self.analyzer.current_difficulty = "NORMAL"
            
            player = self.analyzer.current_encounter.players[f"{i+1}"]
            player.total_damage = 1000
            player.equipped_abilities = ["12345"]
            
            self.analyzer._display_encounter_summary(zone)
            self.analyzer._save_zone_report(zone)
        
        # Check that all reports use the same timestamp
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 3)
        
        timestamps = []
        for report_file in report_files:
            timestamp_match = report_file.name.split('-')[0]
            timestamps.append(timestamp_match)
        
        # All timestamps should be the same
        expected_timestamp = "250914100001"
        for timestamp in timestamps:
            self.assertEqual(timestamp, expected_timestamp, f"Expected {expected_timestamp}, got {timestamp}")

    def test_edge_case_zero_timestamp(self):
        """Test behavior with zero timestamp."""
        # Set up test data with zero timestamp
        self.analyzer.log_start_unix_timestamp = 1757808000  # 2025-09-14 10:00:00
        self.analyzer.zone_start_time = 0  # Zero timestamp
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone")
        self.analyzer._save_zone_report("Test Zone")
        
        # Check that report was created with correct timestamp (should be log_start_unix_timestamp)
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        report_name = report_files[0].name
        timestamp_match = report_name.split('-')[0]
        
        # Should be the log start timestamp (2025-09-14 10:00:00)
        expected_timestamp = "250914100000"
        self.assertEqual(timestamp_match, expected_timestamp, f"Expected {expected_timestamp}, got {timestamp_match}")

    def test_negative_timestamp(self):
        """Test behavior with negative timestamp."""
        # Set up test data with negative timestamp
        self.analyzer.log_start_unix_timestamp = 1757808000  # 2025-09-14 10:00:00
        self.analyzer.zone_start_time = -1000  # Negative timestamp
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone")
        self.analyzer._save_zone_report("Test Zone")
        
        # Check that report was created with current time timestamp (fallback)
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        report_name = report_files[0].name
        timestamp_match = report_name.split('-')[0]
        
        # Should be current time (2025 format) due to negative timestamp
        self.assertTrue(timestamp_match.startswith('25'), f"Should start with '25' for 2025: {timestamp_match}")


if __name__ == '__main__':
    unittest.main()
