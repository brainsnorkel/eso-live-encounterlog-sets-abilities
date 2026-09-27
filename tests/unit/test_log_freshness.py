#!/usr/bin/env python3
"""Unit tests for log freshness derivation (log-freshness spec)."""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from log_freshness import (
    derive_log_freshness, derive_session_epoch_ms, parse_begin_log_epoch_ms,
    parse_relative_ms, status_from_tracking,
)

EPOCH_MS = 1755729685851  # 2025-08-21 (local) session epoch used in fixtures
BEGIN_LOG = f'5,BEGIN_LOG,{EPOCH_MS},15,"NA Megaserver","en","eso.live.11.1"'


class TestParsers(unittest.TestCase):

    def test_parse_relative_ms(self):
        self.assertEqual(parse_relative_ms('43016,COMBAT_EVENT,DAMAGE,...'), 43016)
        self.assertEqual(parse_relative_ms(BEGIN_LOG), 5)
        self.assertIsNone(parse_relative_ms('garbage line'))
        self.assertIsNone(parse_relative_ms(''))

    def test_parse_begin_log_epoch(self):
        self.assertEqual(parse_begin_log_epoch_ms(BEGIN_LOG), EPOCH_MS)
        self.assertIsNone(parse_begin_log_epoch_ms('5,ZONE_CHANGED,975,"X",VETERAN'))


class TestDeriveLogFreshness(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / 'Encounter.log'

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, *lines):
        self.log.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def test_missing_file(self):
        status = derive_log_freshness(self.log)
        self.assertEqual(status.source, 'none')
        self.assertIsNone(status.latest_entry_time)

    def test_exact_derivation(self):
        self._write(BEGIN_LOG,
                    '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
                    '3600000,END_COMBAT')
        status = derive_log_freshness(self.log)
        self.assertEqual(status.source, 'exact')
        expected = datetime.fromtimestamp((EPOCH_MS + 3600000) / 1000.0)
        self.assertEqual(status.latest_entry_time, expected)
        self.assertEqual(status.size_bytes, self.log.stat().st_size)

    def test_epoch_rollover_uses_most_recent_begin_log(self):
        second_epoch = EPOCH_MS + 86_400_000  # next day's session
        self._write(BEGIN_LOG,
                    '9000000,END_LOG',
                    f'5,BEGIN_LOG,{second_epoch},15,"NA Megaserver","en","eso.live.11.1"',
                    '60000,END_COMBAT')
        status = derive_log_freshness(self.log)
        self.assertEqual(status.source, 'exact')
        expected = datetime.fromtimestamp((second_epoch + 60000) / 1000.0)
        self.assertEqual(status.latest_entry_time, expected)

    def test_mid_file_attach_within_lookback(self):
        # BEGIN_LOG far from the tail but within the lookback cap
        filler = ['100,ABILITY_INFO,1,"X","/x.dds",F,F'] * 5000
        self._write(BEGIN_LOG, *filler, '7200000,END_COMBAT')
        status = derive_log_freshness(self.log)
        self.assertEqual(status.source, 'exact')
        expected = datetime.fromtimestamp((EPOCH_MS + 7200000) / 1000.0)
        self.assertEqual(status.latest_entry_time, expected)

    def test_no_begin_log_reachable_falls_back_to_mtime(self):
        # No BEGIN_LOG anywhere: approximate from mtime
        self._write('1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
                    '2000,END_COMBAT')
        status = derive_log_freshness(self.log)
        self.assertEqual(status.source, 'approximate')
        mtime = datetime.fromtimestamp(self.log.stat().st_mtime)
        self.assertEqual(status.latest_entry_time, mtime)

    def test_lookback_cap_respected(self):
        # BEGIN_LOG exists but beyond a tiny lookback cap
        filler = ['100,ABILITY_INFO,1,"X","/x.dds",F,F'] * 100
        self._write(BEGIN_LOG, *filler, '7200000,END_COMBAT')
        status = derive_log_freshness(self.log, lookback_bytes=64)
        self.assertEqual(status.source, 'approximate')

    def test_empty_file(self):
        self.log.write_text('', encoding='utf-8')
        status = derive_log_freshness(self.log)
        self.assertEqual(status.source, 'approximate')

    def test_unparseable_tail(self):
        self._write('not a log line at all')
        status = derive_log_freshness(self.log)
        self.assertEqual(status.source, 'approximate')

    def test_derive_session_epoch_ms(self):
        self._write(BEGIN_LOG, '1000,END_COMBAT')
        self.assertEqual(derive_session_epoch_ms(self.log), EPOCH_MS)
        self.assertIsNone(derive_session_epoch_ms(Path(self.tmp.name) / 'nope.log'))


class TestStatusFromTracking(unittest.TestCase):

    def test_exact_from_tracked_values(self):
        status = status_from_tracking(Path('x.log'), 123, EPOCH_MS // 1000, 3600000)
        self.assertEqual(status.source, 'exact')
        expected = datetime.fromtimestamp(EPOCH_MS // 1000 + 3600.0)
        self.assertEqual(status.latest_entry_time, expected)
        self.assertEqual(status.size_bytes, 123)

    def test_missing_tracking_falls_back_to_derivation(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / 'Encounter.log'
            log.write_text(BEGIN_LOG + '\n60000,END_COMBAT\n', encoding='utf-8')
            status = status_from_tracking(log, log.stat().st_size, None, None)
            self.assertEqual(status.source, 'exact')
            expected = datetime.fromtimestamp((EPOCH_MS + 60000) / 1000.0)
            self.assertEqual(status.latest_entry_time, expected)


class TestMonitorEmitsStatus(unittest.TestCase):
    """Freshness events flow through the monitor's tail loop (task 2.1)."""

    def test_tail_updates_emit_exact_status(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
        from esolog_tail import ESOLogAnalyzer, LogFileMonitor
        from engine_events import RecordingListener

        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / 'Encounter.log'
            log.write_text(BEGIN_LOG + '\n1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN\n',
                           encoding='utf-8')

            analyzer = ESOLogAnalyzer()
            recorder = RecordingListener()
            analyzer.add_listener(recorder)
            monitor = LogFileMonitor(analyzer, log, read_all_then_tail=True)

            # Initial snapshot from startup
            initial = recorder.of_kind('log_status')
            self.assertTrue(initial)
            self.assertEqual(initial[-1][1].source, 'exact')

            # New data arrives: emitted status advances with the new offset
            with open(log, 'a', encoding='utf-8') as f:
                f.write('120000,BEGIN_COMBAT\n')
            monitor._process_new_lines()
            statuses = recorder.of_kind('log_status')
            latest = statuses[-1][1]
            self.assertEqual(latest.source, 'exact')
            expected = datetime.fromtimestamp(EPOCH_MS // 1000 + 120.0)
            self.assertEqual(latest.latest_entry_time, expected)

            # Epoch rollover: a new BEGIN_LOG resets the session base
            second_epoch = EPOCH_MS + 86_400_000
            with open(log, 'a', encoding='utf-8') as f:
                f.write(f'5,BEGIN_LOG,{second_epoch},15,"NA","en","eso.live.11.1"\n')
                f.write('30000,BEGIN_COMBAT\n')
            monitor._process_new_lines()
            latest = recorder.of_kind('log_status')[-1][1]
            self.assertEqual(latest.source, 'exact')
            expected = datetime.fromtimestamp(second_epoch // 1000 + 30.0)
            self.assertEqual(latest.latest_entry_time, expected)


if __name__ == '__main__':
    unittest.main()
