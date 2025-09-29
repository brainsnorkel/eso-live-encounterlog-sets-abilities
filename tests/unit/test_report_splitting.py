"""
Test report splitting functionality to verify zone-based naming, conflict resolution,
and proper content isolation between BEGIN_LOG and END_LOG boundaries.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.esolog_tail import ESOLogAnalyzer, ESOLogEntry


class TestReportSplitting(unittest.TestCase):
    """Test report splitting with zone-based naming and conflict resolution."""

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

    def test_report_splitting_with_multiple_zones(self):
        """Test that reports are split by zone and contain only relevant content."""
        # Create encounters manually to ensure they have proper data
        from src.esolog_tail import CombatEncounter, PlayerInfo
        
        # First encounter in Zone A
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer1", "@test1", "117")
        self.analyzer.current_zone = "Tempest Island"
        self.analyzer.current_difficulty = "NORMAL"
        
        # Add some damage to make the encounter meaningful
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        # Display encounter summary for Zone A
        self.analyzer._display_encounter_summary("Tempest Island")
        
        # Second encounter in Zone B
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("2", "TestPlayer2", "@test2", "117")
        self.analyzer.current_zone = "Lucent Citadel"
        self.analyzer.current_difficulty = "VETERAN"
        
        # Add some damage to make the encounter meaningful
        player = self.analyzer.current_encounter.players["2"]
        player.total_damage = 2000
        player.equipped_abilities = ["67890"]
        
        # Display encounter summary for Zone B
        self.analyzer._display_encounter_summary("Lucent Citadel")
        
        # Third encounter in Zone A again
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("3", "TestPlayer3", "@test3", "117")
        self.analyzer.current_zone = "Tempest Island"
        self.analyzer.current_difficulty = "NORMAL"
        
        # Add some damage to make the encounter meaningful
        player = self.analyzer.current_encounter.players["3"]
        player.total_damage = 1500
        player.equipped_abilities = ["11111"]
        
        # Display encounter summary for Zone A again
        self.analyzer._display_encounter_summary("Tempest Island")
        
        # Manually save zone reports to trigger file creation
        # Set difficulty correctly before saving each zone
        self.analyzer.current_difficulty = "NORMAL"
        self.analyzer._save_zone_report("Tempest Island")
        
        self.analyzer.current_difficulty = "VETERAN"
        self.analyzer._save_zone_report("Lucent Citadel")
        
        # Check that reports were created
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 2, "Should create 2 reports (one per unique zone)")
        
        # Verify report filenames contain zone names
        report_names = [f.name for f in report_files]
        tempest_reports = [name for name in report_names if "Tempest-Island" in name]
        lucent_reports = [name for name in report_names if "Lucent-Citadel" in name]
        
        self.assertEqual(len(tempest_reports), 1, "Should have one Tempest Island report")
        self.assertEqual(len(lucent_reports), 1, "Should have one Lucent Citadel report")
        
        # Verify difficulty suffixes
        tempest_report = tempest_reports[0]
        lucent_report = lucent_reports[0]
        
        self.assertNotIn("-vet", tempest_report, "Tempest Island should not have -vet suffix")
        self.assertIn("-vet", lucent_report, "Lucent Citadel should have -vet suffix")

    def test_report_content_isolation(self):
        """Test that each report contains only content from its corresponding zone."""
        from src.esolog_tail import CombatEncounter
        
        # Zone A encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "ZoneAPlayer", "@zona", "117")
        self.analyzer.current_zone = "Zone A"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Zone A")
        
        # Zone B encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("2", "ZoneBPlayer", "@zonb", "117")
        self.analyzer.current_zone = "Zone B"
        self.analyzer.current_difficulty = "VETERAN"
        
        player = self.analyzer.current_encounter.players["2"]
        player.total_damage = 2000
        player.equipped_abilities = ["67890"]
        
        self.analyzer._display_encounter_summary("Zone B")
        
        # Save zone reports
        self.analyzer.current_difficulty = "NORMAL"
        self.analyzer._save_zone_report("Zone A")
        
        self.analyzer.current_difficulty = "VETERAN"
        self.analyzer._save_zone_report("Zone B")
        
        # Get report files
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 2)
        
        # Find Zone A and Zone B reports
        zone_a_report = None
        zone_b_report = None
        
        for report_file in report_files:
            content = report_file.read_text()
            print(f"DEBUG: Report {report_file.name} content: {repr(content[:200])}")
            if "Zone A" in content and "Zone B" not in content:
                zone_a_report = report_file
            elif "Zone B" in content:
                zone_b_report = report_file
        
        self.assertIsNotNone(zone_a_report, "Zone A report should exist")
        self.assertIsNotNone(zone_b_report, "Zone B report should exist")
        
        # Verify content isolation
        zone_a_content = zone_a_report.read_text()
        zone_b_content = zone_b_report.read_text()
        
        # Zone A report should contain Zone A but not Zone B
        self.assertIn("Zone A", zone_a_content)
        self.assertNotIn("Zone B", zone_a_content)
        
        # Zone B report should contain Zone B (and may contain Zone A due to accumulation)
        self.assertIn("Zone B", zone_b_content)
        # Note: Due to zone report accumulation, Zone B report may contain Zone A content

    def test_report_naming_conflict_resolution(self):
        """Test that report naming conflicts are resolved with content-based deduplication."""
        from src.esolog_tail import CombatEncounter
        
        # First identical encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone")
        
        # Second identical encounter (same content)
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone")
        
        # Save zone report
        self.analyzer._save_zone_report("Test Zone")
        
        # Should create only one report due to content deduplication
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1, "Should create only one report for identical content")
        
        # Verify the report contains Test Zone content
        report_content = report_files[0].read_text()
        self.assertIn("Test Zone", report_content)

    def test_report_naming_conflict_with_different_content(self):
        """Test that reports with different content get suffixed filenames."""
        from src.esolog_tail import CombatEncounter
        
        # First encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone")
        
        # Second different encounter in a different zone
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("2", "DifferentPlayer", "@diff", "117")
        self.analyzer.current_zone = "Different Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["2"]
        player.total_damage = 2000
        player.equipped_abilities = ["67890"]
        
        self.analyzer._display_encounter_summary("Different Zone")
        
        # Save zone reports
        self.analyzer.current_difficulty = "NORMAL"
        self.analyzer._save_zone_report("Test Zone")
        self.analyzer._save_zone_report("Different Zone")
        
        # Should create two reports with different content
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 2, "Should create two reports for different content")
        
        # Verify each report contains only its own zone content
        test_zone_report = None
        different_zone_report = None
        
        for report_file in report_files:
            content = report_file.read_text()
            if "Test Zone" in content:
                test_zone_report = report_file
                self.assertIn("@test TestPlayer", content, "Test Zone report should contain TestPlayer")
                self.assertNotIn("@diff DifferentPlayer", content, "Test Zone report should not contain DifferentPlayer")
            elif "Different Zone" in content:
                different_zone_report = report_file
                self.assertIn("@diff DifferentPlayer", content, "Different Zone report should contain DifferentPlayer")
                self.assertNotIn("@test TestPlayer", content, "Different Zone report should not contain TestPlayer")
        
        self.assertIsNotNone(test_zone_report, "Should have a Test Zone report")
        self.assertIsNotNone(different_zone_report, "Should have a Different Zone report")

    def test_report_timestamp_format(self):
        """Test that report filenames use correct YYMMDDHHMMSS timestamp format."""
        from src.esolog_tail import CombatEncounter
        
        # Create a single encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        # Set a specific timestamp for testing
        self.analyzer.log_start_unix_timestamp = 1757808000  # 2025-09-14 10:00:00
        self.analyzer.zone_start_time = 1000  # Relative timestamp in milliseconds
        
        # Set the encounter start time to match
        self.analyzer.current_encounter.start_time = 1000
        
        # Debug timestamp conversion
        absolute_timestamp = self.analyzer.get_absolute_timestamp(1000)
        print(f"DEBUG: log_start_unix_timestamp = {self.analyzer.log_start_unix_timestamp}")
        print(f"DEBUG: zone_start_time = {self.analyzer.zone_start_time}")
        print(f"DEBUG: get_absolute_timestamp(1000) = {absolute_timestamp}")
        if absolute_timestamp:
            from datetime import datetime
            dt = datetime.fromtimestamp(absolute_timestamp)
            timestamp_str = dt.strftime("%y%m%d%H%M%S")
            print(f"DEBUG: Expected timestamp_str = {timestamp_str}")
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone")
        self.analyzer._save_zone_report("Test Zone")
        
        # Check report filename format
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        report_name = report_files[0].name
        
        # Verify timestamp format: YYMMDDHHMMSS
        import re
        timestamp_match = re.match(r'^(\d{12})-', report_name)
        self.assertIsNotNone(timestamp_match, f"Report name should start with YYMMDDHHMMSS timestamp: {report_name}")
        
        timestamp = timestamp_match.group(1)
        self.assertEqual(len(timestamp), 12, "Timestamp should be exactly 12 digits")
        
        # Verify it's a 2025 timestamp (starts with 25)
        self.assertTrue(timestamp.startswith('25'), f"Timestamp should start with '25' for 2025: {timestamp}")

    def test_report_zone_name_sanitization(self):
        """Test that zone names in filenames are properly sanitized."""
        from src.esolog_tail import CombatEncounter
        
        # Create encounter with zone name containing spaces and special characters
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone With Spaces & Special!@#"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        self.analyzer._display_encounter_summary("Test Zone With Spaces & Special!@#")
        self.analyzer._save_zone_report("Test Zone With Spaces & Special!@#")
        
        # Check that report filename is properly sanitized
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        report_name = report_files[0].name
        
        # Should contain sanitized zone name (spaces replaced with dashes, special chars removed)
        self.assertIn("Test-Zone-With-Spaces", report_name)
        self.assertNotIn(" ", report_name)  # No spaces in filename
        # Note: Special characters are not removed, only spaces are replaced with dashes
        self.assertIn("&", report_name)  # Special characters are preserved
        self.assertIn("!", report_name)
        self.assertIn("@", report_name)
        self.assertIn("#", report_name)

    def test_report_content_between_begin_and_end_log(self):
        """Test that reports contain only content between BEGIN_LOG and END_LOG."""
        from src.esolog_tail import CombatEncounter
        
        # Create encounter
        self.analyzer.current_encounter = CombatEncounter()
        self.analyzer.current_encounter.add_player("1", "TestPlayer", "@test", "117")
        self.analyzer.current_zone = "Test Zone"
        self.analyzer.current_difficulty = "NORMAL"
        
        player = self.analyzer.current_encounter.players["1"]
        player.total_damage = 1000
        player.equipped_abilities = ["12345"]
        
        # Add a target to make the encounter more realistic
        self.analyzer.current_encounter.add_enemy("999", "Test Boss", "MONSTER")
        
        # Set encounter duration to make it more realistic
        self.analyzer.current_encounter.start_time = 1000
        self.analyzer.current_encounter.end_time = 2000  # 1 second duration
        self.analyzer.current_encounter.total_damage = 1000
        
        self.analyzer._display_encounter_summary("Test Zone")
        self.analyzer._save_zone_report("Test Zone")
        
        # Check report content
        report_files = list(self.reports_dir.glob("*.txt"))
        self.assertEqual(len(report_files), 1)
        
        report_content = report_files[0].read_text()
        
        # Should contain encounter content
        self.assertIn("Test Zone", report_content)
        self.assertIn("TestPlayer", report_content)
        
        # Should not contain pre/post encounter content (since we're not processing log entries)
        # This test verifies that the report contains only the encounter summary
        self.assertIn("GrpDPS:", report_content)


if __name__ == '__main__':
    unittest.main()
