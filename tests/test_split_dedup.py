"""Tests for split file deduplication."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from esolog_tail import LogSplitter


def test_scan_existing_splits_indexes_files():
    """_scan_existing_splits correctly indexes existing split files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        split_dir = Path(tmpdir)
        # Create some fake split files
        (split_dir / "260112192756-Maw-of-Lorkhaj-vet.log").write_text("x" * 100)
        (split_dir / "260112192756-Maw-of-Lorkhaj-vet-1.log").write_text("y" * 200)
        (split_dir / "260113192924-Kynes-Aegis-vet.log").write_text("z" * 150)
        # Temp files should be ignored
        (split_dir / "260114000000-temp.log").write_text("temp")

        # Create a minimal log file for LogSplitter
        log_file = split_dir / "test.log"
        log_file.write_text("")

        splitter = LogSplitter(log_file, split_dir=split_dir)

        assert "260112192756-Maw-of-Lorkhaj-vet" in splitter.existing_splits
        assert 100 in splitter.existing_splits["260112192756-Maw-of-Lorkhaj-vet"]
        assert 200 in splitter.existing_splits["260112192756-Maw-of-Lorkhaj-vet"]
        assert "260113192924-Kynes-Aegis-vet" in splitter.existing_splits
        assert 150 in splitter.existing_splits["260113192924-Kynes-Aegis-vet"]


def test_scan_empty_directory():
    """_scan_existing_splits handles empty split directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        split_dir = Path(tmpdir) / "splits"
        split_dir.mkdir()
        log_file = Path(tmpdir) / "test.log"
        log_file.write_text("")

        splitter = LogSplitter(log_file, split_dir=split_dir)
        assert splitter.existing_splits == {}


def test_skip_current_starts_false():
    """skip_current flag starts as False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        split_dir = Path(tmpdir)
        log_file = split_dir / "test.log"
        log_file.write_text("")

        splitter = LogSplitter(log_file, split_dir=split_dir)
        assert splitter.skip_current is False


def test_write_log_line_skipped_when_skip_current():
    """write_log_line does nothing when skip_current is True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        split_dir = Path(tmpdir)
        log_file = split_dir / "test.log"
        log_file.write_text("")
        test_file = split_dir / "output.log"

        splitter = LogSplitter(log_file, split_dir=split_dir)
        splitter.file_handle = open(test_file, 'w')
        splitter.skip_current = True
        splitter.write_log_line("should not be written")
        splitter.file_handle.close()

        assert test_file.read_text() == ""
