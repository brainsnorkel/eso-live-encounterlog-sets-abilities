"""
Test file naming conflict resolution for split logs and reports.
"""
import os
import tempfile
import hashlib
import unittest
from unittest.mock import patch, MagicMock

from pathlib import Path
from src.esolog_tail import LogSplitter, ESOLogAnalyzer


class TestFileNamingConflicts(unittest.TestCase):
    """Test file naming conflict resolution."""

    def setUp(self):
        """Set up test environment."""
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        # Create a dummy log file for LogSplitter
        dummy_log = os.path.join(self.temp_dir, "dummy.log")
        with open(dummy_log, 'w') as f:
            f.write("dummy")
        self.splitter = LogSplitter(Path(dummy_log), split_dir=Path(self.temp_dir))
        self.analyzer = ESOLogAnalyzer(save_reports=True, reports_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_file(self, filename, content="test content"):
        """Create a test file with specified content."""
        filepath = os.path.join(self.temp_dir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        return filepath

    def _get_file_hash(self, filepath):
        """Get MD5 hash of file content."""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def test_split_log_same_content_deletes_temp(self):
        """Test that temp file is deleted when target exists with same content."""
        # Create existing target file
        target_file = self._create_test_file("250914094523-Lucent-Citadel-vet.log", "encounter data")
        target_hash = self._get_file_hash(target_file)
        
        # Create temp file with same content
        temp_file = self._create_test_file("250914094523-Lucent-Citadel-vet-temp.log", "encounter data")
        temp_hash = self._get_file_hash(temp_file)
        
        # Verify hashes match
        self.assertEqual(target_hash, temp_hash)
        
        # Mock the rename operation to simulate conflict
        with patch('os.rename', side_effect=FileExistsError("File exists")):
            with patch('os.path.exists', return_value=True):
                result = self.splitter._handle_rename_conflict(Path(temp_file), Path(target_file))
        
        # Should return True (success) and temp file should be deleted
        self.assertTrue(result)
        self.assertFalse(os.path.exists(temp_file))
        self.assertTrue(os.path.exists(target_file))

    def test_split_log_different_content_uses_suffix(self):
        """Test that different content uses suffix numbering."""
        # Create existing target file
        target_file = self._create_test_file("250914094523-Lucent-Citadel-vet.log", "old encounter data")
        
        # Create temp file with different content
        temp_file = self._create_test_file("250914094523-Lucent-Citadel-vet-temp.log", "new encounter data")
        
        # Mock the rename operation to simulate conflict
        with patch('os.rename', side_effect=FileExistsError("File exists")):
            with patch('os.path.exists', return_value=True):
                result = self.splitter._handle_rename_conflict(Path(temp_file), Path(target_file))
        
        # Should return True (success) and create suffixed file
        self.assertTrue(result)
        self.assertFalse(os.path.exists(temp_file))
        
        # Check that suffixed file was created
        suffixed_file = os.path.join(self.temp_dir, "250914094523-Lucent-Citadel-vet-1.log")
        self.assertTrue(os.path.exists(suffixed_file))
        
        # Verify content is correct
        with open(suffixed_file, 'r') as f:
            content = f.read()
        self.assertEqual(content, "new encounter data")

    def test_split_log_multiple_conflicts_increments_suffix(self):
        """Test that multiple conflicts increment suffix correctly."""
        # Create existing files
        self._create_test_file("250914094523-Lucent-Citadel-vet.log", "old data")
        self._create_test_file("250914094523-Lucent-Citadel-vet-1.log", "older data")
        self._create_test_file("250914094523-Lucent-Citadel-vet-2.log", "oldest data")
        
        # Create temp file with new content
        temp_file = self._create_test_file("250914094523-Lucent-Citadel-vet-temp.log", "newest data")
        
        # Mock the rename operation to simulate conflicts
        def mock_rename(src, dst):
            if os.path.exists(dst):
                raise FileExistsError("File exists")
            os.rename(src, dst)
        
        with patch('os.rename', side_effect=mock_rename):
            with patch('os.path.exists', return_value=True):
                result = self.splitter._handle_rename_conflict(Path(temp_file), Path(temp_file.replace('-temp', '')))
        
        # Should return True and create -3 suffix
        self.assertTrue(result)
        self.assertFalse(os.path.exists(temp_file))
        
        suffixed_file = os.path.join(self.temp_dir, "250914094523-Lucent-Citadel-vet-3.log")
        self.assertTrue(os.path.exists(suffixed_file))

    def test_report_same_content_deletes_temp(self):
        """Test that report temp file is deleted when target exists with same content."""
        # Create existing target file
        target_file = self._create_test_file("250914094523-Lucent-Citadel-vet.txt", "report data")
        
        # Create temp file with same content
        temp_file = self._create_test_file("250914094523-Lucent-Citadel-vet-temp.txt", "report data")
        
        # Mock the rename operation to simulate conflict
        with patch('os.rename', side_effect=FileExistsError("File exists")):
            with patch('os.path.exists', return_value=True):
                result = self.analyzer._handle_rename_conflict(Path(temp_file), Path(target_file))
        
        # Should return True (success) and temp file should be deleted
        self.assertTrue(result)
        self.assertFalse(os.path.exists(temp_file))
        self.assertTrue(os.path.exists(target_file))

    def test_report_different_content_uses_suffix(self):
        """Test that report with different content uses suffix numbering."""
        # Create existing target file
        target_file = self._create_test_file("250914094523-Lucent-Citadel-vet.txt", "old report data")
        
        # Create temp file with different content
        temp_file = self._create_test_file("250914094523-Lucent-Citadel-vet-temp.txt", "new report data")
        
        # Mock the rename operation to simulate conflict
        with patch('os.rename', side_effect=FileExistsError("File exists")):
            with patch('os.path.exists', return_value=True):
                result = self.analyzer._handle_rename_conflict(Path(temp_file), Path(target_file))
        
        # Should return True (success) and create suffixed file
        self.assertTrue(result)
        self.assertFalse(os.path.exists(temp_file))
        
        # Check that suffixed file was created
        suffixed_file = os.path.join(self.temp_dir, "250914094523-Lucent-Citadel-vet-1.txt")
        self.assertTrue(os.path.exists(suffixed_file))
        
        # Verify content is correct
        with open(suffixed_file, 'r') as f:
            content = f.read()
        self.assertEqual(content, "new report data")

    def test_temp_file_overwrite_allowed(self):
        """Test that temp files can be overwritten without conflict."""
        # Create existing temp file
        existing_temp = self._create_test_file("250914094523-Lucent-Citadel-vet-temp.log", "old temp data")
        
        # Create new temp file (should overwrite)
        new_temp = self._create_test_file("250914094523-Lucent-Citadel-vet-temp.log", "new temp data")
        
        # Should succeed without conflict
        self.assertTrue(os.path.exists(new_temp))
        
        # Verify content is updated
        with open(new_temp, 'r') as f:
            content = f.read()
        self.assertEqual(content, "new temp data")


if __name__ == '__main__':
    unittest.main()
