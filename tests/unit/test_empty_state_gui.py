#!/usr/bin/env python3
"""The pane before the first fight (issue #191), offscreen: what the app is
doing, when Encounter.log was last archived, the Recent activity link with
the newest archives and splits under it, and a click on one of them running
Open log for review."""

import html
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

FIXTURE_LOG = Path(__file__).parent.parent / 'fixtures' / 'golden_fight.log'

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _file(path: Path, when: datetime, data: bytes = b"x" * 2048) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, (when.timestamp(), when.timestamp()))
    return path


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class EmptyStateTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / 'Encounter.log'
        self.splits = self.dir / 'splits'
        self.splits.mkdir()
        from app_config import AppConfig
        self.config = AppConfig(path=self.dir / 'config.json')
        self.config.set('log_path', str(self.log))
        self.config.set('split.dir', str(self.splits))
        self.config.set('update.check_enabled', False)

    def tearDown(self):
        self.tmp.cleanup()

    def _window(self):
        from gui.main_window import MainWindow
        win = MainWindow(self.config)
        # Stop the real worker thread; tests drive slots directly
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        return win

    def _archives(self):
        """Two archives beside the log: the newer made on 2 Nov."""
        older = _file(self.dir / 'Encounter-261027194400.zip', datetime(2026, 10, 27, 21, 14))
        newer = _file(self.dir / 'Encounter-261102204800.zip', datetime(2026, 11, 2, 21, 0))
        return older, newer

    def _split_files(self):
        """Three splits, one zipped, and a temp split still being written."""
        import split_retention
        plain = self.splits / '261102195454-Lucent-Citadel-vet.log'
        plain.write_bytes(FIXTURE_LOG.read_bytes())
        _file(self.splits / '261101150312-Grahtwood.log', datetime(2026, 11, 1, 16, 0))
        zipped_src = self.splits / '261031205111-Moon-Hunter-Keep.log'
        zipped_src.write_bytes(FIXTURE_LOG.read_bytes())
        split_retention.zip_split(zipped_src)
        _file(self.splits / '261102204837-temp.log', datetime(2026, 11, 2, 20, 48))
        return plain, self.splits / (zipped_src.name + '.zip')


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestEmptyPane(EmptyStateTestCase):

    def test_monitoring_names_the_newest_archive_and_offers_recent_activity(self):
        older, _newer = self._archives()
        self._split_files()
        self.log.write_text('', encoding='utf-8')
        win = self._window()
        try:
            win._on_monitoring_started(str(self.log))
            text = win._last_placeholder
            self.assertIn('Monitoring Encounter.log for encounters', text)
            self.assertIn('Encounter.log was last archived at 2 Nov 2026, 21:00 '
                          '(Encounter-261102204800.zip, 2 KB; its last entry 2 Nov 2026, 20:48).',
                          text)
            # The lists wait behind the link
            self.assertIn('Recent activity ▸', text)
            self.assertIn("href='esolog:activity/show'", text)
            self.assertNotIn(older.name, text)
            self.assertNotIn('Lucent Citadel', text)
            self.assertEqual(win._empty_reason, 'monitoring')
        finally:
            win.close()

    def test_recent_activity_opens_and_closes_in_place(self):
        older, newer = self._archives()
        plain, zipped = self._split_files()
        win = self._window()
        try:
            win._on_monitoring_started(str(self.log))
            win._on_activity_requested('show')
            text = win._last_placeholder
            self.assertIn('Recent activity ▾', text)
            self.assertIn("href='esolog:activity/hide'", text)
            self.assertIn('<b>Archives</b>', text)
            self.assertIn('<b>Split logs</b>', text)
            # Archives newest first, then the splits by session, newest first
            self.assertLess(text.index(newer.name), text.index(older.name))
            self.assertLess(text.index('Lucent Citadel · Veteran'), text.index('Grahtwood'))
            self.assertLess(text.index('Grahtwood'), text.index('Moon Hunter Keep'))
            self.assertIn('zipped', text)
            self.assertNotIn('temp', text)
            # Each file's link carries its place, and its hover the path
            from gui.activity_render import REVIEW_HREF, activity_paths
            paths = activity_paths(win._activity)
            self.assertEqual(paths[:2], [newer, older])
            self.assertEqual(paths[2], plain)
            self.assertEqual(paths[4], zipped)
            for index in range(len(paths)):
                self.assertIn(f"href='{REVIEW_HREF}{index}'", text)
            self.assertEqual(win.fight_view._tooltips[f'{REVIEW_HREF}2'],
                             f'Open {plain} for review')
            # The folders are named
            self.assertIn(str(self.splits), text)
            win._on_activity_requested('hide')
            text = win._last_placeholder
            self.assertIn('Recent activity ▸', text)
            self.assertNotIn('<b>Archives</b>', text)
            self.assertNotIn(older.name, text)
        finally:
            win.close()

    def test_a_click_on_a_file_requests_its_review(self):
        from PySide6.QtCore import QUrl

        from gui.activity_render import ACTIVITY_HREF, REVIEW_HREF
        _older, newer = self._archives()
        plain, zipped = self._split_files()
        win = self._window()
        try:
            # Only the request is under test: no review runs
            win.request_review.disconnect(win._start_review)
            requests = []
            win.request_review.connect(lambda p, m: requests.append((p, m)))
            win._on_monitoring_started(str(self.log))
            win.fight_view.anchorClicked.emit(QUrl(f'{ACTIVITY_HREF}show'))
            self.assertTrue(win._activity_open)
            win.fight_view.anchorClicked.emit(QUrl(f'{REVIEW_HREF}2'))
            win.fight_view.anchorClicked.emit(QUrl(f'{REVIEW_HREF}4'))
            win.fight_view.anchorClicked.emit(QUrl(f'{REVIEW_HREF}0'))
            win.fight_view.anchorClicked.emit(QUrl(f'{REVIEW_HREF}99'))  # nothing there
            # The zipped split and the archive open as their one log
            self.assertEqual(requests, [(str(plain), ''), (str(zipped), ''), (str(newer), '')])
            self.assertTrue(win.statusBar().currentMessage().startswith('Loading '))
            win.fight_view.anchorClicked.emit(QUrl(f'{ACTIVITY_HREF}hide'))
            self.assertFalse(win._activity_open)
            self.assertIn('Recent activity ▸', win._last_placeholder)
        finally:
            win.close()

    def test_waiting_with_delete_on_says_the_log_was_archived_and_removed(self):
        self._archives()
        self.config.set('archive.delete_original', True)
        win = self._window()
        try:
            win._on_waiting_for_log(r'C:\Users\R&D <x>\Encounter.log')
            text = win._last_placeholder
            self.assertIn('Encounter.log was archived at 2 Nov 2026, 21:00 '
                          '(Encounter-261102204800.zip, 2 KB; its last entry 2 Nov 2026, 20:48) '
                          'and removed, as Settings asks.', text)
            self.assertIn('Waiting for encounters.', text)
            self.assertNotIn('Waiting for Encounter.log…', text)
            self.assertNotIn('last archived at', text)  # said once
            # Where it is looked for and how to turn logging on, as before
            self.assertIn(r'<code>C:\Users\R&amp;D &lt;x&gt;\Encounter.log</code>', text)
            self.assertIn('Always Logging (from GitHub', text)
            self.assertIn('Easy Stalking (ESOUI or Minion)', text)
            self.assertIn('not both', text)
            self.assertIn('Recent activity ▸', text)
            self.assertEqual(win.freshness_label.text(), 'No log file')
        finally:
            win.close()

    def test_waiting_with_the_original_kept_waits_as_before(self):
        self._archives()
        win = self._window()
        try:
            win._on_waiting_for_log(str(self.log))
            text = win._last_placeholder
            self.assertIn('Waiting for Encounter.log…', text)
            self.assertIn('Encounter.log was last archived at 2 Nov 2026, 21:00', text)
            self.assertNotIn('and removed', text)
        finally:
            win.close()

    def test_nothing_archived_and_no_splits_shows_no_link(self):
        win = self._window()
        try:
            win._on_monitoring_started(str(self.log))
            text = win._last_placeholder
            self.assertIn('Monitoring Encounter.log for encounters', text)
            self.assertNotIn('archived', text)
            self.assertNotIn('Recent activity', text)
            win._on_waiting_for_log('')
            text = win._last_placeholder
            self.assertIn('Waiting for Encounter.log…', text)
            self.assertIn('known ESO log locations', text)
            self.assertNotIn('Recent activity', text)
        finally:
            win.close()

    def test_an_archive_just_made_goes_on_the_page(self):
        from engine_events import ArchiveEvent
        win = self._window()
        try:
            win._on_monitoring_started(str(self.log))
            self.assertNotIn('archived', win._last_placeholder)
            made = _file(self.dir / 'Encounter-261103090000.zip', datetime(2026, 11, 3, 9, 1))
            win._on_archive_event(ArchiveEvent(kind='completed', log_path=self.log,
                                               archive_path=made, done_bytes=1, total_bytes=1))
            text = win._last_placeholder
            self.assertIn('Encounter.log was last archived at 3 Nov 2026, 09:01', text)
            self.assertIn('Recent activity ▸', text)
        finally:
            win.close()

    def test_back_to_live_with_no_fights_names_the_archive(self):
        self._archives()
        win = self._window()
        try:
            win._exit_review()
            text = win._last_placeholder
            self.assertIn('Back to live monitoring. No fight has ended in this session yet.', text)
            self.assertIn('Encounter.log was last archived at 2 Nov 2026, 21:00', text)
            self.assertEqual(win._empty_reason, 'back')
        finally:
            win.close()

    def test_the_first_fight_replaces_the_page_and_closes_the_lists(self):
        import review_load
        from app_startup import build_analyzer
        self._archives()
        _shown, fights = review_load.replay_log(build_analyzer(self.config, []), FIXTURE_LOG)
        self.assertTrue(fights)
        win = self._window()
        try:
            win._on_monitoring_started(str(self.log))
            win._on_activity_requested('show')
            self.assertTrue(win._activity_open)
            win._on_fight_completed(fights[0])
            self.assertIs(win.history_list.current_entry(), fights[0])
            self.assertIsNone(win._empty_reason)
            self.assertFalse(win._activity_open)
            self.assertNotIn('Recent activity', win.fight_view.toPlainText())
            # An archive completing now leaves the fight on the pane
            from engine_events import ArchiveEvent
            made = _file(self.dir / 'Encounter-261103090000.zip', datetime(2026, 11, 3, 9, 1))
            win._on_archive_event(ArchiveEvent(kind='completed', log_path=self.log,
                                               archive_path=made, done_bytes=1, total_bytes=1))
            self.assertIs(win.history_list.current_entry(), fights[0])
            self.assertNotIn('archived', win.fight_view.toPlainText())
        finally:
            win.close()

    def test_the_review_dialog_still_asks_which_log_a_zip_holds(self):
        import zipfile
        from unittest import mock
        archive = self.dir / 'two.zip'
        with zipfile.ZipFile(archive, 'w') as zf:
            zf.writestr('a.log', 'x')
            zf.writestr('b.log', 'y')
        win = self._window()
        try:
            win.request_review.disconnect(win._start_review)
            requests = []
            win.request_review.connect(lambda p, m: requests.append((p, m)))
            with mock.patch('gui.main_window.QFileDialog.getOpenFileName',
                            return_value=(str(archive), '')), \
                    mock.patch('gui.main_window.QInputDialog.getItem',
                               return_value=('b.log', True)):
                win._open_review_dialog()
            self.assertEqual(requests, [(str(archive), 'b.log')])
        finally:
            win.close()


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestEmptyPageText(unittest.TestCase):
    """The page's text alone (gui.activity_render), with no window."""

    def test_links_are_told_apart_by_their_hrefs(self):
        from gui.activity_render import (
            ACTIVITY_HREF,
            REVIEW_HREF,
            activity_action_from_href,
            review_index_from_href,
        )
        self.assertEqual(activity_action_from_href(f'{ACTIVITY_HREF}show'), 'show')
        self.assertEqual(activity_action_from_href(f'{ACTIVITY_HREF}hide'), 'hide')
        self.assertIsNone(activity_action_from_href(f'{ACTIVITY_HREF}open'))
        self.assertIsNone(activity_action_from_href('esolog:build/12'))
        self.assertEqual(review_index_from_href(f'{REVIEW_HREF}7'), 7)
        self.assertIsNone(review_index_from_href(f'{REVIEW_HREF}seven'))
        self.assertIsNone(review_index_from_href(REVIEW_HREF))
        self.assertIsNone(review_index_from_href(''))

    def test_names_in_the_page_are_escaped(self):
        from gui.activity_render import empty_state_html
        from recent_activity import RecentActivity
        from split_retention import SplitFile
        split = SplitFile(path=Path('x/261101150312-R&D-<x>.log'), stamp='261101150312',
                          zone='R&D <x>', vet=False, zipped=False, size=10, reference=0.0)
        folder = Path('C:/a&b <c>')
        activity = RecentActivity(splits=[split], split_dir=folder)
        text = empty_state_html('monitoring', activity, dark=False, show_activity=True)
        self.assertIn('R&amp;D &lt;x&gt;', text)
        self.assertIn(f'<code>{html.escape(str(folder))}</code>', text)
        self.assertNotIn('<x>', text)
        self.assertNotIn('<c>', text)
