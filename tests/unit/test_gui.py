#!/usr/bin/env python3
"""GUI tests (offscreen): worker signal bridge, views, freshness, archive.

Runs headless via QT_QPA_PLATFORM=offscreen; skipped if PySide6 is missing.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

FIXTURE_LOG = Path(__file__).parent.parent / 'fixtures' / 'golden_fight.log'
GOLDEN_JSON = Path(__file__).parent.parent / 'fixtures' / 'golden_fight_expected.json'

EPOCH_MS = 1755729685851
BEGIN_LOG = f'5,BEGIN_LOG,{EPOCH_MS},15,"NA Megaserver","en","eso.live.11.1"'

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


class TestEngineIsQtFree(unittest.TestCase):
    """Engine modules must not import Qt (gui-application spec)."""

    def test_no_qt_imports_in_engine_modules(self):
        src = Path(__file__).parent.parent.parent / 'src'
        offenders = []
        for py in src.glob('*.py'):
            if py.name == 'esolog_gui.py':
                continue  # GUI entry point, not an engine module
            text = py.read_text(encoding='utf-8', errors='ignore')
            if 'PySide6' in text or 'PyQt' in text:
                offenders.append(py.name)
        self.assertEqual(offenders, [])

    def test_no_terminal_libs_in_engine_modules(self):
        src = Path(__file__).parent.parent.parent / 'src'
        offenders = []
        for py in src.rglob('*.py'):
            text = py.read_text(encoding='utf-8', errors='ignore')
            for banned in ('import curses', 'import click', 'from colorama'):
                if banned in text:
                    offenders.append(f'{py.name}: {banned}')
        self.assertEqual(offenders, [])


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class GuiTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / 'Encounter.log'
        from app_config import AppConfig
        self.config = AppConfig(path=self.dir / 'config.json')
        self.config.set('log_path', str(self.log))

    def tearDown(self):
        self.tmp.cleanup()

    def _worker(self):
        from gui.engine_worker import EngineWorker
        # Driven synchronously on this thread: we call start()/_poll() directly
        return EngineWorker(self.config)


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestWorkerSignalBridge(GuiTestCase):
    """Task 4.2: engine events surface as Qt signals."""

    def test_fight_events_arrive_via_signals(self):
        self.log.write_text(BEGIN_LOG + '\n', encoding='utf-8')
        worker = self._worker()
        received = {'fights': [], 'statuses': [], 'zones': []}
        worker.fight_completed.connect(lambda e: received['fights'].append(e))
        worker.log_status.connect(lambda s: received['statuses'].append(s))
        worker.zone_changed.connect(lambda z, d: received['zones'].append((z, d)))
        worker.start()

        # Append a complete fight and poll
        fixture_lines = FIXTURE_LOG.read_text(encoding='utf-8').splitlines()
        with open(self.log, 'a', encoding='utf-8') as f:
            for line in fixture_lines[1:]:  # skip duplicate BEGIN_LOG
                f.write(line + '\n')
        worker._poll()
        _app.processEvents()

        self.assertEqual(len(received['fights']), 2)
        self.assertTrue(received['statuses'])
        self.assertEqual(received['statuses'][-1].source, 'exact')
        self.assertIn(('Coral Aerie', 'VETERAN'), received['zones'])

    def test_waiting_state_when_log_missing(self):
        worker = self._worker()
        waits = []
        worker.waiting_for_log.connect(lambda p: waits.append(p))
        worker.start()
        _app.processEvents()
        self.assertTrue(waits)
        self.assertIn('Encounter.log', waits[0])


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestReviewMatchesGolden(GuiTestCase):
    """Task 4.3: review replay shows the same fights as the golden data."""

    def test_review_fixture_matches_golden(self):
        worker = self._worker()
        loaded = {}
        worker.review_loaded.connect(lambda p, f: loaded.update(path=p, fights=f))
        worker.open_review(str(FIXTURE_LOG))
        _app.processEvents()

        golden = json.loads(GOLDEN_JSON.read_text(encoding='utf-8'))
        fights = loaded['fights']
        self.assertEqual(len(fights), len(golden['fights']))
        for got, want in zip(fights, golden['fights']):
            self.assertEqual(got.zone_name, want['zone_name'])
            self.assertEqual(got.is_vet, want['is_vet'])
            self.assertEqual(round(got.group_dps, 1), want['group_dps'])
            self.assertEqual([p.get('name') for p in got.players],
                             [p['name'] for p in want['players']])

    def test_render_functions(self):
        from gui.fight_render import render_html, render_plain_text, summary_line
        worker = self._worker()
        loaded = {}
        worker.review_loaded.connect(lambda p, f: loaded.update(fights=f))
        worker.open_review(str(FIXTURE_LOG))
        _app.processEvents()
        entry = loaded['fights'][0]
        line = summary_line(entry)
        self.assertIn('Coral Aerie', line)
        # Order: boss, duration, gdps, zone, timestamp; no em dashes
        self.assertTrue(line.startswith('Test Boss · '))
        self.assertNotIn('—', line)
        self.assertLess(line.index('gdps'), line.index('Coral Aerie'))
        self.assertLess(line.index('Coral Aerie'), line.index('2025'))
        # First-damage dealer gets a star in both renderings
        html_marked = render_html(entry, detailed=False)
        # (the name itself is a link to the player's build window)
        self.assertIn('@brainsnorkel</a> <b>*</b>', html_marked)
        self.assertIn('first damage', html_marked)
        self.assertIn('@brainsnorkel *', render_plain_text(entry))
        html_out = render_html(entry, detailed=True)
        self.assertIn('@brainsnorkel', html_out)
        self.assertIn('Tide-Born Wildstalker', html_out)
        # Lists must be joined for display, never rendered as Python reprs
        self.assertNotIn("['", html_out)
        self.assertNotIn('["', html_out)
        # Detail view lists ALL equipment: misc pieces below 5 pieces included
        import html as html_mod
        player1 = entry.players[0]
        for count, set_name in player1.get('all_sets', []):
            self.assertIn(html_mod.escape(f'{count}x {set_name}'), html_out)
        misc = [s for s in player1.get('all_sets', []) if s[0] < 5]
        self.assertTrue(misc, 'fixture should include sub-5pc pieces')
        text_out = render_plain_text(entry)
        self.assertIn('@brainsnorkel', text_out)
        self.assertNotIn("['", text_out)

    def test_buff_summary_text_suppressed_when_timeline_present(self):
        from fight_history import FightHistoryEntry
        from gui.fight_render import render_html
        entry = FightHistoryEntry()
        entry.zone_name = 'Coral Aerie'
        entry.buff_summary = 'MCourage:87% Mslayer:48%'
        # No timeline: text uptimes shown as fallback
        self.assertIn('MCourage:87%', render_html(entry, detailed=False))
        # Timeline present: the graph replaces the text line
        entry.buff_timeline = {'duration_ms': 60_000, 'effects': {
            'Major Courage': [{'start_ms': 0, 'end_ms': 1000,
                               'source': 'a', 'target': 'b'}]}}
        self.assertNotIn('MCourage:87%', render_html(entry, detailed=False))


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestMainWindowStates(GuiTestCase):
    """Tasks 4.5/4.6/4.7: status bar states, settings persistence, waiting."""

    def _window(self):
        from gui.main_window import MainWindow
        win = MainWindow(self.config)
        # Stop the real worker thread; tests drive slots directly
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        return win

    def test_freshness_states(self):
        from datetime import datetime, timedelta
        from engine_events import LogStatus
        from gui.main_window import state_style
        win = self._window()
        try:
            cases = [
                (timedelta(seconds=40), 'live'),
                (timedelta(minutes=10), 'idle'),
                (timedelta(minutes=45), 'stale'),
            ]
            for age, state in cases:
                status = LogStatus(log_path=self.log, size_bytes=1,
                                   latest_entry_time=datetime.now() - age,
                                   source='exact')
                win._on_log_status(status)
                text = win.freshness_label.text()
                self.assertIn('Last entry:', text)
                self.assertIn('ago', text)
                self.assertEqual(win.freshness_label.styleSheet(),
                                 state_style(state, win._dark))
            # Live/stale/none must actually color the label for this theme
            self.assertTrue(state_style('live', win._dark))
            self.assertTrue(state_style('stale', win._dark))
            # No log
            win._last_status = None
            win._refresh_freshness_label()
            self.assertEqual(win.freshness_label.text(), 'No log file')
            self.assertEqual(win.freshness_label.styleSheet(),
                             state_style('none', win._dark))
        finally:
            win.close()

    def test_age_text_formats(self):
        from gui.main_window import _age_text
        self.assertEqual(_age_text(40), '40s')
        self.assertEqual(_age_text(3 * 60), '3m')
        self.assertEqual(_age_text(45 * 60), '45m')
        self.assertEqual(_age_text(2 * 3600 + 300), '2h 5m')

    def test_settings_dialog_round_trip(self):
        from gui.settings_dialog import SettingsDialog
        win = self._window()
        try:
            dialog = SettingsDialog(self.config, win)
            dialog.threshold.setValue(2048)
            dialog.delete_original.setChecked(True)
            dialog.split_enabled.setChecked(True)
            dialog.apply_to_config()
            self.config.save()

            from app_config import AppConfig
            reloaded = AppConfig(path=self.config.path)
            self.assertEqual(reloaded.get('archive.size_threshold_mb'), 2048)
            self.assertTrue(reloaded.get('archive.delete_original'))
            self.assertTrue(reloaded.get('split.enabled'))
        finally:
            win.close()

    def test_sizing_guide_visible_in_settings(self):
        """log-archiving spec: sizing guide beside the threshold field."""
        from PySide6.QtWidgets import QLabel
        from gui.settings_dialog import SIZE_GUIDE, SettingsDialog
        win = self._window()
        try:
            dialog = SettingsDialog(self.config, win)
            self.assertIn('veteran trial', SIZE_GUIDE)
            labels = [w.text() for w in dialog.findChildren(QLabel)]
            self.assertTrue(any(SIZE_GUIDE in text for text in labels),
                            'sizing guide label missing from settings dialog')
        finally:
            win.close()

    def test_live_theme_switch_rerenders_with_dark_colors(self):
        """System dark-mode switches mid-session must re-render content."""
        from datetime import datetime, timedelta
        from PySide6.QtGui import QColor, QPalette
        from engine_events import LogStatus
        from gui.fight_render import muted_color
        from gui.main_window import state_style
        win = self._window()
        try:
            self.assertFalse(win._dark)  # offscreen default palette is light
            win._show_placeholder('theme test')
            win._on_log_status(LogStatus(
                log_path=self.log, size_bytes=1,
                latest_entry_time=datetime.now() - timedelta(minutes=45),
                source='exact'))

            palette = QPalette()
            for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
                palette.setColor(group, QPalette.Window, QColor('#1e1e1e'))
                palette.setColor(group, QPalette.WindowText, QColor('#eeeeee'))
            win.setPalette(palette)
            win._on_theme_maybe_changed()

            self.assertTrue(win._dark)
            # Placeholder re-rendered with the dark-theme muted color
            self.assertIn(muted_color(True), win.fight_view.toHtml())
            # Freshness state color switched to the dark-theme variant
            self.assertEqual(win.freshness_label.styleSheet(),
                             state_style('stale', True))
            # Flipping back re-renders light again
            win.setPalette(QPalette())
            win._on_theme_maybe_changed()
            self.assertFalse(win._dark)
            self.assertIn(muted_color(False), win.fight_view.toHtml())
        finally:
            win.close()

    def test_in_fight_search_highlights_all_matches(self):
        """Typing in the search field highlights every occurrence."""
        win = self._window()
        try:
            worker = self._worker()
            loaded = {}
            worker.review_loaded.connect(lambda p, f: loaded.update(fights=f))
            worker.open_review(str(FIXTURE_LOG))
            _app.processEvents()
            for entry in loaded['fights']:
                win._on_fight_completed(entry)
            win.history_list.setCurrentRow(0)

            # Substring, case-insensitive: "wild" hits "Tide-Born Wildstalker"
            win.search_field.setText('wild')
            hits = len(win.fight_view.extraSelections())
            self.assertGreaterEqual(hits, 1)
            self.assertIn(str(hits), win.search_count.text())
            win.search_field.setText('WILD')
            self.assertEqual(len(win.fight_view.extraSelections()), hits)

            # Switching fights re-applies the search to the new content
            win.history_list.setCurrentRow(1)
            self.assertGreaterEqual(len(win.fight_view.extraSelections()), 1)

            # Highlighted ranges actually cover the search text
            selection = win.fight_view.extraSelections()[0]
            self.assertEqual(selection.cursor.selectedText().lower(), 'wild')

            # No match
            win.search_field.setText('zzzznothing')
            self.assertEqual(len(win.fight_view.extraSelections()), 0)
            self.assertIn('0 matches', win.search_count.text())

            # Clearing removes highlights and the counter
            win.search_field.clear()
            self.assertEqual(len(win.fight_view.extraSelections()), 0)
            self.assertEqual(win.search_count.text(), '')
        finally:
            win.close()

    def test_search_enter_cycles_matches(self):
        win = self._window()
        try:
            worker = self._worker()
            loaded = {}
            worker.review_loaded.connect(lambda p, f: loaded.update(fights=f))
            worker.open_review(str(FIXTURE_LOG))
            _app.processEvents()
            win._on_fight_completed(loaded['fights'][0])
            win.history_list.setCurrentRow(0)
            win.search_field.setText('a')  # plenty of matches
            matches = win._search_matches()
            self.assertGreater(len(matches), 2)
            first_pos = win.fight_view.textCursor().position()
            win._goto_next_match()
            second_pos = win.fight_view.textCursor().position()
            self.assertGreater(second_pos, first_pos)
            # Wraps around eventually
            for _ in range(len(matches)):
                win._goto_next_match()
            self.assertLessEqual(win.fight_view.textCursor().position(),
                                 matches[-1].selectionStart())
        finally:
            win.close()

    def test_archive_events_drive_progress_bar(self):
        from engine_events import ArchiveEvent
        win = self._window()
        try:
            win._on_archive_event(ArchiveEvent(kind='started', total_bytes=100))
            self.assertTrue(win.progress_bar.isVisibleTo(win))
            win._on_archive_event(ArchiveEvent(kind='progress', done_bytes=50,
                                               total_bytes=100))
            self.assertEqual(win.progress_bar.value(), 500)
            win._on_archive_event(ArchiveEvent(kind='completed',
                                               archive_path=Path('x.zip'),
                                               done_bytes=100, total_bytes=100))
            self.assertFalse(win.progress_bar.isVisibleTo(win))
        finally:
            win.close()

    def test_parse_progress_drives_progress_bar(self):
        win = self._window()
        try:
            # Determinate parsing progress
            win._on_parse_progress('Parsing x.log', 0, 1000)
            self.assertTrue(win.progress_bar.isVisibleTo(win))
            win._on_parse_progress('Parsing x.log', 500, 1000)
            self.assertEqual(win.progress_bar.value(), 500)
            self.assertIn('50%', win.statusBar().currentMessage())
            # Completion hides the bar and clears only the parsing label
            win._on_parse_progress('Parsing x.log', 1000, 1000)
            self.assertFalse(win.progress_bar.isVisibleTo(win))
            self.assertEqual(win.statusBar().currentMessage(), '')
            # A later completion message survives the hide event
            win.statusBar().showMessage('Loaded 10 fights from x.log', 8000)
            win._on_parse_progress('Parsing x.log', 1000, 1000)
            self.assertEqual(win.statusBar().currentMessage(),
                             'Loaded 10 fights from x.log')
            # Indeterminate busy (catch-up)
            win._on_parse_progress('Catching up…', 0, 0)
            self.assertTrue(win.progress_bar.isVisibleTo(win))
            self.assertEqual(win.progress_bar.maximum(), 0)  # marquee mode
            win._on_parse_progress('Catching up…', 1, 1)
            self.assertFalse(win.progress_bar.isVisibleTo(win))
        finally:
            win.close()

    def test_update_flow(self):
        """Update prompt wiring: skip persists; update triggers download."""
        from unittest.mock import patch
        from update_check import UpdateInfo
        win = self._window()
        try:
            info = UpdateInfo(version='9.9.9', tag='v9.9.9',
                              installer_url='https://example.invalid/s.exe',
                              installer_name='esolog-tail-windows-setup-9.9.9.exe',
                              notes='', page_url='')
            # Skip: persisted to config
            with patch.object(win, '_prompt_update', return_value='skip'):
                win._on_update_available(info)
            from app_config import AppConfig
            self.assertEqual(AppConfig(path=self.config.path)
                             .get('update.skip_version'), '9.9.9')
            # Update (Windows: there is an installer): emits the download request
            requested = []
            win.request_update_download.connect(
                lambda url, name: requested.append((url, name)))
            with patch.object(win, '_prompt_update', return_value='update'), \
                 patch('gui.main_window.HAS_INSTALLER', True):
                win._on_update_available(info)
            self.assertEqual(requested,
                             [(info.installer_url, info.installer_name)])
            # Later: nothing persisted or requested
            requested.clear()
            self.config.set('update.skip_version', None)
            with patch.object(win, '_prompt_update', return_value='later'):
                win._on_update_available(info)
            self.assertEqual(requested, [])
            self.assertIsNone(self.config.get('update.skip_version'))
        finally:
            win.close()

    def test_update_without_installer_opens_release_page(self):
        """Linux has no installer: 'update' opens the release page instead."""
        from unittest.mock import patch
        from update_check import UpdateInfo
        win = self._window()
        try:
            info = UpdateInfo(
                version='9.9.9', tag='v9.9.9',
                installer_url='https://example.invalid/l.tar.gz',
                installer_name='esolog-tail-linux-x86_64-9.9.9.tar.gz',
                notes='', page_url='https://example.invalid/releases/v9.9.9')
            requested = []
            win.request_update_download.connect(
                lambda url, name: requested.append((url, name)))
            with patch.object(win, '_prompt_update', return_value='update'), \
                 patch('gui.main_window.HAS_INSTALLER', False), \
                 patch('gui.main_window.QDesktopServices') as services:
                win._on_update_available(info)
            self.assertEqual(requested, [])
            services.openUrl.assert_called_once()
            self.assertEqual(services.openUrl.call_args[0][0].toString(),
                             info.page_url)
        finally:
            win.close()

    def test_worker_update_check_emits_signal(self):
        from unittest.mock import patch
        from update_check import UpdateInfo
        import gui.engine_worker  # noqa: F401  (module for patch target)
        worker = self._worker()
        seen = []
        worker.update_available.connect(lambda i: seen.append(i))
        info = UpdateInfo(version='9.9.9', tag='v9.9.9', installer_url='u',
                          installer_name='n', notes='', page_url='')
        with patch('update_check.check_for_update', return_value=info):
            worker.check_for_update()
        _app.processEvents()
        self.assertEqual([i.version for i in seen], ['9.9.9'])

    def test_worker_download_update_emits_ready(self):
        import tempfile
        worker = self._worker()
        ready, failed = [], []
        worker.update_ready.connect(lambda p: ready.append(p))
        worker.update_failed.connect(lambda r: failed.append(r))
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / 'setup.exe'
            src.write_bytes(b'installer-bytes')
            worker.download_update(src.as_uri(), 'esolog-test-setup.exe')
            _app.processEvents()
        self.assertEqual(failed, [])
        self.assertEqual(len(ready), 1)
        downloaded = Path(ready[0])
        self.assertEqual(downloaded.read_bytes(), b'installer-bytes')
        downloaded.unlink()

    def test_review_emits_parse_progress(self):
        worker = self._worker()
        events = []
        worker.parse_progress.connect(lambda l, d, t: events.append((l, d, t)))
        loaded = {}
        worker.review_loaded.connect(lambda p, f: loaded.update(fights=f))
        worker.open_review(str(FIXTURE_LOG))
        _app.processEvents()
        self.assertTrue(loaded['fights'])
        self.assertGreaterEqual(len(events), 2)
        first_label, first_done, first_total = events[0]
        self.assertIn('golden_fight.log', first_label)
        self.assertEqual(first_done, 0)
        self.assertEqual(first_total, FIXTURE_LOG.stat().st_size)
        last_label, last_done, last_total = events[-1]
        self.assertGreaterEqual(last_done, last_total)  # hide event


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestArchiveNowEndToEnd(GuiTestCase):
    """Task 4.6: Archive now performs a real guarded archive."""

    def test_archive_now_creates_zip(self):
        self.log.write_text(BEGIN_LOG + '\n60000,END_COMBAT\n', encoding='utf-8')
        worker = self._worker()
        events = []
        worker.archive_event.connect(lambda e: events.append(e))
        worker.start()
        worker.archive_now()
        _app.processEvents()

        kinds = [e.kind for e in events]
        self.assertIn('completed', kinds)
        zips = list(self.dir.glob('Encounter-*.zip'))
        self.assertEqual(len(zips), 1)
        self.assertTrue(self.log.exists())  # default keep


if __name__ == '__main__':
    unittest.main()
