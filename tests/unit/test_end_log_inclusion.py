"""
Test that END_LOG entries are included in split log files.
"""
import tempfile
import unittest
from pathlib import Path

from src.esolog_tail import LogSplitter, ESOLogEntry


class TestEndLogInclusion(unittest.TestCase):
    """Test that END_LOG entries are included in split files."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        # Create a dummy log file for LogSplitter
        dummy_log = Path(self.temp_dir) / "dummy.log"
        dummy_log.write_text("dummy")
        self.splitter = LogSplitter(dummy_log, split_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_log_included_in_split_file(self):
        """Test that END_LOG entry is included in the split file."""
        # Create a BEGIN_LOG entry
        begin_log_line = "1000,BEGIN_LOG,1757808000000"
        begin_entry = ESOLogEntry.parse(begin_log_line)
        
        # Create an END_LOG entry
        end_log_line = "2000,END_LOG"
        end_entry = ESOLogEntry.parse(end_log_line)
        
        # Start encounter
        self.splitter.start_encounter(begin_entry, "Test Zone", "NORMAL")
        
        # Write BEGIN_LOG line
        self.splitter.write_log_line(begin_log_line)
        
        # Write some combat events
        self.splitter.write_log_line("1500,BEGIN_COMBAT")
        self.splitter.write_log_line("1600,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000")
        self.splitter.write_log_line("1700,END_COMBAT")
        
        # Write END_LOG line and end encounter
        self.splitter.write_log_line(end_log_line)
        self.splitter.end_encounter()
        
        # Check that split file was created (exclude dummy.log)
        split_files = [f for f in Path(self.temp_dir).glob("*.log") if f.name != "dummy.log"]
        self.assertEqual(len(split_files), 1)
        
        split_file = split_files[0]
        
        # Read the split file content
        content = split_file.read_text()
        lines = content.strip().split('\n')
        
        # Verify all expected lines are present
        self.assertIn(begin_log_line, lines)
        self.assertIn("1500,BEGIN_COMBAT", lines)
        self.assertIn("1600,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000", lines)
        self.assertIn("1700,END_COMBAT", lines)
        self.assertIn(end_log_line, lines)  # This is the key assertion
        
        # Verify the END_LOG is the last line
        self.assertEqual(lines[-1], end_log_line)

    def test_end_log_included_with_zone_info(self):
        """Test that END_LOG entry is included when zone info is available."""
        # Create entries
        begin_log_line = "1000,BEGIN_LOG,1757808000000"
        zone_change_line = "1100,ZONE_CHANGED,131,\"Tempest Island\",NORMAL"
        end_log_line = "2000,END_LOG"
        
        # Start encounter
        begin_entry = ESOLogEntry.parse(begin_log_line)
        self.splitter.start_encounter(begin_entry, "Tempest Island", "NORMAL")
        
        # Write all lines
        self.splitter.write_log_line(begin_log_line)
        self.splitter.write_log_line(zone_change_line)
        self.splitter.write_log_line("1500,BEGIN_COMBAT")
        self.splitter.write_log_line("1600,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000")
        self.splitter.write_log_line("1700,END_COMBAT")
        self.splitter.write_log_line(end_log_line)
        self.splitter.end_encounter()
        
        # Check split file (exclude dummy.log)
        split_files = [f for f in Path(self.temp_dir).glob("*.log") if f.name != "dummy.log"]
        self.assertEqual(len(split_files), 1)
        
        content = split_files[0].read_text()
        lines = content.strip().split('\n')
        
        # Verify END_LOG is included and is the last line
        self.assertIn(end_log_line, lines)
        self.assertEqual(lines[-1], end_log_line)

    def test_split_log_structure_requirements(self):
        """Test that split logs must start with BEGIN_LOG and end with END_LOG."""
        # Create a complete encounter sequence
        begin_log_line = "1000,BEGIN_LOG,1757808000000"
        zone_change_line = "1100,ZONE_CHANGED,131,\"Tempest Island\",NORMAL"
        combat_start_line = "1200,BEGIN_COMBAT"
        combat_event_line = "1300,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,4021668,12346,2,24000/24000,31000/31000,27000/27000,500/500,1000/1000,0,0.2696,0.5942,5.5492,70,134704/136704,0/0,0/0,0/0,0/0,0,0.4081,0.5662,0.0256"
        combat_end_line = "1400,END_COMBAT"
        end_log_line = "1500,END_LOG"
        
        # Start encounter
        begin_entry = ESOLogEntry.parse(begin_log_line)
        self.splitter.start_encounter(begin_entry, "Tempest Island", "NORMAL")
        
        # Write all lines in sequence
        self.splitter.write_log_line(begin_log_line)
        self.splitter.write_log_line(zone_change_line)
        self.splitter.write_log_line(combat_start_line)
        self.splitter.write_log_line(combat_event_line)
        self.splitter.write_log_line(combat_end_line)
        self.splitter.write_log_line(end_log_line)
        self.splitter.end_encounter()
        
        # Check split file was created
        split_files = [f for f in Path(self.temp_dir).glob("*.log") if f.name != "dummy.log"]
        self.assertEqual(len(split_files), 1)
        
        split_file = split_files[0]
        content = split_file.read_text()
        lines = content.strip().split('\n')
        
        # Verify the split log structure requirements
        self.assertGreater(len(lines), 0, "Split log should not be empty")
        
        # Must start with BEGIN_LOG
        first_line = lines[0]
        self.assertTrue(",BEGIN_LOG," in first_line, 
                       f"Split log must start with BEGIN_LOG, but first line is: {first_line}")
        
        # Must end with END_LOG
        last_line = lines[-1]
        self.assertTrue(last_line.endswith(",END_LOG"), 
                       f"Split log must end with END_LOG, but last line is: {last_line}")
        
        # Verify all expected lines are present
        self.assertIn(begin_log_line, lines)
        self.assertIn(zone_change_line, lines)
        self.assertIn(combat_start_line, lines)
        self.assertIn(combat_event_line, lines)
        self.assertIn(combat_end_line, lines)
        self.assertIn(end_log_line, lines)
        
        # Verify the exact first and last lines
        self.assertEqual(lines[0], begin_log_line)
        self.assertEqual(lines[-1], end_log_line)

    def test_split_log_without_combat_still_has_begin_and_end(self):
        """Test that split logs without combat still start with BEGIN_LOG and end with END_LOG."""
        # Create a minimal encounter without combat
        begin_log_line = "1000,BEGIN_LOG,1757808000000"
        zone_change_line = "1100,ZONE_CHANGED,131,\"Tempest Island\",NORMAL"
        end_log_line = "1200,END_LOG"
        
        # Start encounter
        begin_entry = ESOLogEntry.parse(begin_log_line)
        self.splitter.start_encounter(begin_entry, "Tempest Island", "NORMAL")
        
        # Write lines (no combat events)
        self.splitter.write_log_line(begin_log_line)
        self.splitter.write_log_line(zone_change_line)
        self.splitter.write_log_line(end_log_line)
        self.splitter.end_encounter()
        
        # Check split file was created
        split_files = [f for f in Path(self.temp_dir).glob("*.log") if f.name != "dummy.log"]
        self.assertEqual(len(split_files), 1)
        
        split_file = split_files[0]
        content = split_file.read_text()
        lines = content.strip().split('\n')
        
        # Verify structure requirements even without combat
        self.assertGreater(len(lines), 0, "Split log should not be empty")
        self.assertTrue(",BEGIN_LOG," in lines[0], 
                       f"Split log must start with BEGIN_LOG, but first line is: {lines[0]}")
        self.assertTrue(lines[-1].endswith(",END_LOG"), 
                       f"Split log must end with END_LOG, but last line is: {lines[-1]}")
        
        # Verify exact first and last lines
        self.assertEqual(lines[0], begin_log_line)
        self.assertEqual(lines[-1], end_log_line)


if __name__ == '__main__':
    unittest.main()
