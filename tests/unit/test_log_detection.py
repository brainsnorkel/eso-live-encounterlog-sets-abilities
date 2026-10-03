#!/usr/bin/env python3
"""Encounter.log auto-detection on Linux (Wine and Steam Proton prefixes)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import esolog_tail

_LOGS = Path('Documents') / 'Elder Scrolls Online' / 'live' / 'Logs'
_PROTON_USER = (Path('steamapps') / 'compatdata' / '306130' / 'pfx'
                / 'drive_c' / 'users' / 'steamuser')

# Where a Linux install keeps the log, relative to the home directory
_LINUX_LOCATIONS = {
    'steam symlink': Path('.steam') / 'steam' / _PROTON_USER / _LOGS,
    'native steam': Path('.local') / 'share' / 'Steam' / _PROTON_USER / _LOGS,
    'flatpak steam': (Path('.var') / 'app' / 'com.valvesoftware.Steam'
                      / '.local' / 'share' / 'Steam' / _PROTON_USER / _LOGS),
    'wine prefix': Path('.wine') / 'drive_c' / 'users' / 'Public' / _LOGS,
}


class TestLinuxLogDetection(unittest.TestCase):

    def _detect(self, home: Path):
        with patch.object(esolog_tail.sys, 'platform', 'linux'), \
             patch.object(esolog_tail.Path, 'home', return_value=home):
            return esolog_tail._find_eso_log_file()

    def test_known_locations_are_found(self):
        for label, location in _LINUX_LOCATIONS.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as td:
                log = Path(td) / location / 'Encounter.log'
                log.parent.mkdir(parents=True)
                log.write_text('', encoding='utf-8')
                self.assertEqual(self._detect(Path(td)), log)

    def test_no_log_anywhere_is_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(self._detect(Path(td)))


if __name__ == '__main__':
    unittest.main()
