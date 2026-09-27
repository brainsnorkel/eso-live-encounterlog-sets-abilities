#!/usr/bin/env python3
"""Integration test: startup sequencing (archive check before monitoring)."""

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app_config import AppConfig
from app_startup import run_startup_sequence
from engine_events import RecordingListener

EPOCH_MS = 1755729685851
BEGIN_LOG = f'5,BEGIN_LOG,{EPOCH_MS},15,"NA Megaserver","en","eso.live.11.1"'


class TestStartupSequence(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / 'Encounter.log'
        self.config = AppConfig(path=self.dir / 'config.json')
        self.config.set('log_path', str(self.log))
        self.recorder = RecordingListener()

    def tearDown(self):
        self.tmp.cleanup()

    def test_oversized_log_archived_before_monitoring(self):
        self.config.set('archive.size_threshold_mb', 0)  # any growth triggers
        self.log.write_text(BEGIN_LOG + '\n60000,END_COMBAT\n' + 'x' * 4096,
                            encoding='utf-8')

        result = run_startup_sequence(self.config, [self.recorder])

        # A verified archive exists
        self.assertIsNotNone(result.archive_path)
        with zipfile.ZipFile(result.archive_path) as zf:
            self.assertIsNone(zf.testzip())

        # Monitoring attached after the archive; original kept by default
        self.assertIsNotNone(result.monitor)
        self.assertTrue(self.log.exists())

        # Event ordering: archive completed before the first log status
        kinds = [e[0] for e in self.recorder.events]
        self.assertIn('archive_event', kinds)
        completed_idx = max(i for i, e in enumerate(self.recorder.events)
                            if e[0] == 'archive_event')
        status_idx = min(i for i, e in enumerate(self.recorder.events)
                         if e[0] == 'log_status')
        self.assertLess(completed_idx, status_idx)

    def test_below_threshold_starts_monitoring_without_archive(self):
        self.log.write_text(BEGIN_LOG + '\n60000,END_COMBAT\n', encoding='utf-8')
        result = run_startup_sequence(self.config, [self.recorder])
        self.assertIsNone(result.archive_path)
        self.assertIsNotNone(result.monitor)
        self.assertEqual(self.recorder.of_kind('archive_event'), [])
        # Freshness snapshot emitted at attach
        statuses = self.recorder.of_kind('log_status')
        self.assertTrue(statuses)
        self.assertEqual(statuses[-1][1].source, 'exact')

    def test_missing_log_yields_no_monitor(self):
        result = run_startup_sequence(self.config, [self.recorder])
        self.assertIsNone(result.monitor)
        self.assertIsNone(result.archive_path)
        self.assertEqual(result.log_path, self.log)


if __name__ == '__main__':
    unittest.main()
