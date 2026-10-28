#!/usr/bin/env python3
"""Tests for the update poller (offscreen): the schedule, the thread
hand-off to the UI thread, each outcome of a check, and the download."""

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

import update_check
from update_check import CheckResult, UpdateInfo

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _info(version='9.9.9'):
    return UpdateInfo(version=version, tag=f'v{version}', installer_url='u',
                      installer_name='n', notes='', page_url='',
                      published='2026-10-26T00:23:57Z')


def _pump(until, timeout=5.0):
    """Run the event loop until *until()* holds or *timeout* passes."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        _app.processEvents()
        if until():
            return True
        time.sleep(0.01)
    return until()


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestUpdatePoller(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        from app_config import AppConfig
        self.config = AppConfig(path=Path(self.tmp.name) / 'config.json')
        from gui.update_poller import UpdatePoller
        self.poller = UpdatePoller(self.config, '0.14.2')
        self.available, self.threads, self.outcomes = [], [], []
        self.gone, self.ready, self.failed, self.progress = [], [], [], []
        self.poller.update_available.connect(
            lambda i: (self.available.append(i),
                       self.threads.append(QThread.currentThread())))
        self.poller.update_gone.connect(lambda: self.gone.append(True))
        self.poller.checked.connect(self.outcomes.append)
        self.poller.update_ready.connect(self.ready.append)
        self.poller.update_failed.connect(self.failed.append)
        self.poller.download_progress.connect(
            lambda label, done, total: self.progress.append((label, done, total)))

    def tearDown(self):
        self.poller.stop()
        self.poller.deleteLater()
        _app.processEvents()
        self.tmp.cleanup()

    def _check(self, result):
        """One check with check_for_update returning *result*; the mock."""
        seen = len(self.outcomes)
        with patch.object(update_check, 'check_for_update',
                          return_value=result) as fn:
            if not self.poller.is_running():
                self.poller.start()
            self.poller.check_now()
            self.assertTrue(_pump(lambda: len(self.outcomes) > seen),
                            'the check never reported')
        return fn

    def test_interval_follows_config(self):
        self.assertEqual(self.poller.interval_ms(), 15 * 60 * 1000)
        self.config.set('update.check_interval_min', 7)
        self.assertEqual(self.poller.interval_ms(), 7 * 60 * 1000)
        self.config.set('update.check_interval_min', 'junk')
        self.assertEqual(self.poller.interval_ms(), 15 * 60 * 1000)

    def test_available_arrives_on_the_ui_thread(self):
        fn = self._check(CheckResult(info=_info(), etag='"abc"'))
        fn.assert_called_once_with('0.14.2', None, None, channel='stable')
        self.assertEqual([i.version for i in self.available], ['9.9.9'])
        self.assertIs(self.threads[0], _app.thread())
        self.assertEqual(self.outcomes[-1], 'update check: 9.9.9 available')

    def test_not_modified_changes_nothing_and_sends_the_etag(self):
        self._check(CheckResult(info=_info(), etag='"abc"'))
        fn = self._check_tick(CheckResult(not_modified=True))
        fn.assert_called_once_with('0.14.2', None, '"abc"', channel='stable')
        self.assertEqual(len(self.available), 1)
        self.assertEqual(self.gone, [])
        self.assertEqual(self.outcomes[-1], 'update check: not modified')

    def _check_tick(self, result):
        """A scheduled tick (the ETag kept), unlike check_now()."""
        seen = len(self.outcomes)
        with patch.object(update_check, 'check_for_update',
                          return_value=result) as fn:
            self.poller._tick()
            self.assertTrue(_pump(lambda: len(self.outcomes) > seen))
        return fn

    def test_a_newer_release_is_offered_again(self):
        self._check(CheckResult(info=_info('9.9.9')))
        self._check_tick(CheckResult(info=_info('9.9.10')))
        self.assertEqual([i.version for i in self.available], ['9.9.9', '9.9.10'])

    def test_nothing_newer_after_an_offer_is_gone(self):
        self._check(CheckResult(info=_info()))
        self._check_tick(CheckResult())
        self.assertEqual(self.gone, [True])
        # And only once: a further up-to-date check says nothing new
        self._check_tick(CheckResult())
        self.assertEqual(self.gone, [True])

    def test_skipped_version_is_passed_to_the_check(self):
        self.config.set('update.skip_version', '9.9.9')
        fn = self._check(CheckResult())
        fn.assert_called_once_with('0.14.2', '9.9.9', None, channel='stable')

    def test_the_configured_channel_is_passed_to_the_check(self):
        self.config.set('update.channel', 'beta')
        fn = self._check(CheckResult())
        fn.assert_called_once_with('0.14.2', None, None, channel='beta')
        self.config.set('update.channel', 'junk')
        fn = self._check(CheckResult())
        fn.assert_called_once_with('0.14.2', None, None, channel='stable')

    def test_an_etag_is_never_sent_to_the_other_channel(self):
        # The channels ask different endpoints (issue #134)
        self._check(CheckResult(etag='"stable-1"'))
        self.config.set('update.channel', 'beta')
        fn = self._check_tick(CheckResult(etag='"beta-1"'))
        fn.assert_called_once_with('0.14.2', None, None, channel='beta')
        fn = self._check_tick(CheckResult(not_modified=True))
        fn.assert_called_once_with('0.14.2', None, '"beta-1"', channel='beta')

    def test_leaving_beta_withdraws_an_offer_stable_does_not_make(self):
        self.config.set('update.channel', 'beta')
        self._check(CheckResult(info=_info('0.15.0')))
        self.config.set('update.channel', 'stable')
        self.poller.start()   # what a Settings save does
        self._check(CheckResult())
        self.assertEqual(self.gone, [True])

    def test_rate_limit_wait_skips_the_next_tick(self):
        self._check(CheckResult(error='rate limited (403)',
                                retry_at=time.time() + 600))
        with patch.object(update_check, 'check_for_update',
                          return_value=CheckResult(info=_info())) as fn:
            self.poller._tick()
            _pump(lambda: False, timeout=0.3)
        fn.assert_not_called()
        self.assertEqual(self.available, [])
        # check_now() is the user's own request and ignores the wait
        self._check(CheckResult(info=_info()))
        self.assertEqual(len(self.available), 1)

    def test_a_failure_reports_and_changes_nothing(self):
        self._check(CheckResult(error='timed out'))
        self.assertEqual(self.available, [])
        self.assertEqual(self.gone, [])
        self.assertIn('timed out', self.poller.last_outcome)

    def test_stop_drops_a_late_result(self):
        gate = threading.Event()

        def slow(*_args, **_kwargs):
            gate.wait(5)
            return CheckResult(info=_info())

        with patch.object(update_check, 'check_for_update', side_effect=slow):
            self.poller.start()
            self.poller.check_now()
            self.poller.stop()
            gate.set()
            _pump(lambda: False, timeout=0.5)
        self.assertEqual(self.available, [])
        self.assertEqual(self.outcomes, [])

    def test_download_reports_progress_and_ready(self):
        src = Path(self.tmp.name) / 'setup.exe'
        src.write_bytes(b'installer-bytes')
        self.assertTrue(self.poller.download(src.as_uri(), 'esolog-test-setup.exe'))
        self.assertTrue(_pump(lambda: self.ready or self.failed))
        self.assertEqual(self.failed, [])
        self.assertTrue(self.ready[0].endswith('esolog-test-setup.exe'))
        self.assertEqual(Path(self.ready[0]).read_bytes(), b'installer-bytes')
        self.assertEqual(self.progress[0], ('Downloading esolog-test-setup.exe', 0, 0))
        self.assertEqual(self.progress[-1], ('Downloading esolog-test-setup.exe', 1, 1))
        Path(self.ready[0]).unlink()

    def test_download_failure_reports(self):
        missing = (Path(self.tmp.name) / 'missing.exe').as_uri()
        self.assertTrue(self.poller.download(missing, 'esolog-test-missing.exe'))
        self.assertTrue(_pump(lambda: self.ready or self.failed))
        self.assertEqual(self.ready, [])
        self.assertIn('download failed', self.failed[0])

    def test_download_refused_while_busy(self):
        gate = threading.Event()

        def slow(*_args, **_kwargs):
            gate.wait(5)
            return CheckResult()

        with patch.object(update_check, 'check_for_update', side_effect=slow):
            self.poller.start()
            self.poller.check_now()
            self.assertFalse(self.poller.download('file:///x', 'x.exe'))
            gate.set()
            _pump(lambda: self.outcomes)


if __name__ == '__main__':
    unittest.main()
