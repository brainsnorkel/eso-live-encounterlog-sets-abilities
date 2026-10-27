#!/usr/bin/env python3
"""GUI tests (offscreen): worker signal bridge, views, freshness, archive.

Runs headless via QT_QPA_PLATFORM=offscreen; skipped if PySide6 is missing.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
        # No request to GitHub from a test; the poller has tests of its own
        self.config.set('update.check_enabled', False)

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

    def test_the_uptime_line_is_only_in_the_plain_copy(self):
        """Issue #25: the strip shows the rules in the pane; the copy keeps
        the text line, timeline or not."""
        from fight_history import FightHistoryEntry
        from gui.fight_render import render_html, render_plain_text
        entry = FightHistoryEntry()
        entry.zone_name = 'Coral Aerie'
        entry.buff_summary = 'MCourage:87% Mslayer:48%'
        for timeline in (None, {'duration_ms': 60_000, 'effects': {
                'Major Courage': [{'start_ms': 0, 'end_ms': 1000, 'source': 'a', 'target': 'b'}]}}):
            entry.buff_timeline = timeline
            for detailed in (False, True):
                self.assertNotIn('MCourage:87%', render_html(entry, detailed=detailed))
            self.assertIn('MCourage:87%', render_plain_text(entry))


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

    # ---- the Update button (issue #56: a button and an ⓘ, never a dialog) ----

    @staticmethod
    def _update_info(version='9.9.9'):
        from update_check import UpdateInfo
        return UpdateInfo(
            version=version, tag=f'v{version}',
            installer_url=f'https://example.invalid/{version}/setup.exe',
            installer_name=f'esolog-tail-windows-setup-{version}.exe',
            notes="## What's Changed\n* A fix (#1) by @someone in "
                  "https://example.invalid/pull/1\n",
            page_url=f'https://example.invalid/releases/v{version}',
            published='2026-10-26T00:23:57Z')

    @staticmethod
    def _no_dialogs():
        """Patch QMessageBox so any dialog in the update path fails the test."""
        from unittest.mock import MagicMock, patch
        box = MagicMock(side_effect=AssertionError('a dialog in the update path'))
        for name in ('question', 'information', 'warning', 'critical', 'about'):
            getattr(box, name).side_effect = AssertionError('a dialog in the update path')
        return patch('gui.main_window.QMessageBox', box)

    def test_update_offer_shows_button_title_and_hover(self):
        from unittest.mock import patch

        from version import __version__
        win = self._window()
        try:
            plain = f'ESO Log Tail v{__version__}'
            self.assertFalse(win.update_action.isVisible())
            self.assertFalse(win.update_info_action.isVisible())
            self.assertEqual(win.windowTitle(), plain)
            with patch('gui.main_window.HAS_INSTALLER', True), self._no_dialogs():
                win._on_update_available(self._update_info())
            self.assertTrue(win.update_action.isVisible())
            self.assertTrue(win.update_info_action.isVisible())
            self.assertEqual(win.update_button.text(), 'Update to 9.9.9')
            self.assertTrue(win.update_button.isEnabled())
            self.assertIn(f'you have {__version__}', win.update_button.toolTip())
            self.assertIn('install', win.update_button.toolTip())
            self.assertIn('26 October 2026', win.update_info_button.toolTip())
            self.assertEqual(win.windowTitle(), f'{plain} · 9.9.9 available')
            # A still newer release replaces the offer; Linux wording
            with patch('gui.main_window.HAS_INSTALLER', False):
                win._on_update_available(self._update_info('9.9.10'))
            self.assertEqual(win.update_button.text(), 'Get 9.9.10')
            self.assertIn('release page', win.update_button.toolTip())
            self.assertEqual(win.windowTitle(), f'{plain} · 9.9.10 available')
            # Gone: both hidden, the title plain again
            win._on_update_gone()
            self.assertFalse(win.update_action.isVisible())
            self.assertFalse(win.update_info_action.isVisible())
            self.assertEqual(win.windowTitle(), plain)
        finally:
            win.close()

    def test_update_click_downloads_then_installs(self):
        from unittest.mock import patch
        win = self._window()
        try:
            info = self._update_info()
            with patch('gui.main_window.HAS_INSTALLER', True), self._no_dialogs():
                win._on_update_available(info)
                with patch.object(win.update_poller, 'download',
                                  return_value=True) as download:
                    win.update_button.click()
                download.assert_called_once_with(info.installer_url, info.installer_name)
                self.assertEqual(win.update_button.text(), 'Downloading 9.9.9…')
                self.assertFalse(win.update_button.isEnabled())
                # The installer lands: it is started and the app closes
                with patch('subprocess.Popen') as popen, \
                     patch.object(win, 'close') as close:
                    win._on_update_ready('C:/tmp/esolog-tail-windows-setup-9.9.9.exe')
                self.assertEqual(popen.call_args[0][0],
                                 ['C:/tmp/esolog-tail-windows-setup-9.9.9.exe'])
                close.assert_called_once()
                # A failed start reverts the button and says why
                with patch('subprocess.Popen', side_effect=OSError('denied')), \
                     patch.object(win, 'close') as close:
                    win._on_update_ready('x.exe')
                close.assert_not_called()
                self.assertEqual(win.update_button.text(), 'Update to 9.9.9')
                self.assertTrue(win.update_button.isEnabled())
                self.assertIn('could not start', win.statusBar().currentMessage())
                # A failed download likewise
                win.update_button.setText('Downloading 9.9.9…')
                win.update_button.setEnabled(False)
                win._on_update_failed('download failed; try again later')
                self.assertEqual(win.update_button.text(), 'Update to 9.9.9')
                self.assertTrue(win.update_button.isEnabled())
                self.assertIn('download failed', win.statusBar().currentMessage())
                # The poller busy with a check: the click says so, no download
                with patch.object(win.update_poller, 'download', return_value=False):
                    win.update_button.click()
                self.assertEqual(win.update_button.text(), 'Update to 9.9.9')
                self.assertIn('try again', win.statusBar().currentMessage())
        finally:
            win.close()

    def test_update_on_linux_opens_the_release_page(self):
        from unittest.mock import patch
        win = self._window()
        try:
            info = self._update_info()
            with patch('gui.main_window.HAS_INSTALLER', False), \
                 patch('gui.main_window.QDesktopServices') as services, \
                 patch.object(win.update_poller, 'download') as download:
                win._on_update_available(info)
                win.update_button.click()
            download.assert_not_called()
            services.openUrl.assert_called_once()
            self.assertEqual(services.openUrl.call_args[0][0].toString(), info.page_url)
            self.assertEqual(win.update_button.text(), 'Get 9.9.9')
            self.assertTrue(win.update_button.isEnabled())
        finally:
            win.close()

    def test_update_notes_popup_and_skip(self):
        from unittest.mock import patch

        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from app_config import AppConfig
        from gui.update_popup import SKIP_HREF, UpdateNotesPopup
        from version import __version__

        def popups():
            return [w for w in _app.topLevelWidgets() if isinstance(w, UpdateNotesPopup)]

        win = self._window()
        try:
            with patch('gui.main_window.HAS_INSTALLER', True):
                win._on_update_available(self._update_info())
            win._show_update_notes()
            _app.processEvents()
            popup = popups()[0]
            self.assertIn('9.9.9', popup.heading.text())
            self.assertIn('26 October 2026', popup.heading.text())
            self.assertIn(__version__, popup.heading.text())
            self.assertIn('A fix', popup.notes.toPlainText())
            self.assertIn('https://example.invalid/pull/1', popup.notes.toHtml())
            self.assertTrue(popup.notes.openExternalLinks())
            self.assertIn('Release page', popup.links.text())
            self.assertIn('https://example.invalid/releases/v9.9.9', popup.links.text())
            self.assertIn('/blob/v9.9.9/CHANGELOG.md', popup.links.text())
            self.assertIn(SKIP_HREF, popup.links.text())
            # Esc closes it (and it deletes itself)
            QTest.keyClick(popup, Qt.Key_Escape)
            _app.processEvents()
            self.assertEqual(popups(), [])
            # The skip link persists the version and withdraws the offer
            win._show_update_notes()
            _app.processEvents()
            popups()[0]._on_link(SKIP_HREF)
            _app.processEvents()
            self.assertEqual(popups(), [])
            self.assertEqual(AppConfig(path=self.config.path).get('update.skip_version'),
                             '9.9.9')
            self.assertFalse(win.update_action.isVisible())
            self.assertEqual(win.windowTitle(), f'ESO Log Tail v{__version__}')
        finally:
            win.close()

    def test_update_settings_start_and_stop_the_poller(self):
        from unittest.mock import patch

        from version import __version__
        win = self._window()
        try:
            self.assertFalse(win.update_poller.is_running())  # the test config
            with patch('gui.main_window.HAS_INSTALLER', True):
                win._on_update_available(self._update_info())
            self.config.set('update.check_enabled', False)
            win._apply_update_settings()
            self.assertFalse(win.update_poller.is_running())
            self.assertFalse(win.update_action.isVisible())
            self.assertEqual(win.windowTitle(), f'ESO Log Tail v{__version__}')
            self.config.set('update.check_enabled', True)
            win._apply_update_settings()
            self.assertTrue(win.update_poller.is_running())
            win.update_poller.stop()  # before its first check reaches GitHub
        finally:
            win.close()

    def test_update_info_button_follows_the_theme(self):
        from gui.fight_render import link_color
        win = self._window()
        try:
            self.assertIn(link_color(win._dark), win.update_info_button.styleSheet())
            win._dark = not win._dark
            win._style_update_buttons()
            self.assertIn(link_color(win._dark), win.update_info_button.styleSheet())
        finally:
            win.close()

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


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestZippedReview(GuiTestCase):
    """Issue #86: a zipped split or an archive reviews like the log it holds."""

    def _review(self, path, member=''):
        worker = self._worker()
        loaded, progress = {}, []
        worker.review_loaded.connect(lambda p, f: loaded.update(path=p, fights=f))
        worker.parse_progress.connect(lambda *a: progress.append(a))
        worker.open_review(str(path), member)
        _app.processEvents()
        return loaded, progress

    def _fight_key(self, fights):
        return [(f.zone_name, round(f.group_dps, 1), [p.get('name') for p in f.players])
                for f in fights]

    def test_zipped_split_lists_the_same_fights(self):
        import split_retention
        split = self.dir / '250820201000-Coral-Aerie-vet.log'
        split.write_bytes(FIXTURE_LOG.read_bytes())
        split_retention.zip_split(split)
        zipped = self.dir / (split.name + '.zip')
        plain, _ = self._review(FIXTURE_LOG)
        loaded, progress = self._review(zipped)
        self.assertEqual(loaded['path'], str(zipped))
        self.assertTrue(loaded['fights'])
        self.assertEqual(self._fight_key(loaded['fights']), self._fight_key(plain['fights']))
        # Progress counts the log's bytes, not the zip's
        self.assertEqual(progress[0][2], FIXTURE_LOG.stat().st_size)

    def test_archive_with_several_logs_opens_the_chosen_one(self):
        import zipfile
        archive = self.dir / 'Encounter-250820.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('empty.log', BEGIN_LOG + '\n')
            zf.write(FIXTURE_LOG, 'Encounter.log')
        loaded, _ = self._review(archive, 'Encounter.log')
        self.assertTrue(loaded['fights'])
        self.assertTrue(loaded['path'].endswith('› Encounter.log'))
        # Without a choice it is refused, not guessed
        loaded, _ = self._review(archive)
        self.assertEqual(loaded['fights'], [])

    def test_review_dialog_passes_the_member_and_filters_zips(self):
        import zipfile
        from unittest import mock

        from gui.main_window import MainWindow
        archive = self.dir / 'two.zip'
        with zipfile.ZipFile(archive, 'w') as zf:
            zf.writestr('a.log', 'x')
            zf.writestr('b.log', 'y')
        win = MainWindow(self.config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        try:
            requests = []  # the ended worker is already cut off (_hand_back)
            win.request_review.connect(lambda p, m: requests.append((p, m)))
            with mock.patch('gui.main_window.QFileDialog.getOpenFileName',
                            return_value=(str(archive), '')) as chooser, \
                    mock.patch('gui.main_window.QInputDialog.getItem',
                               return_value=('b.log', True)):
                win._open_review_dialog()
            self.assertIn('*.zip', chooser.call_args[0][3])
            self.assertEqual(requests, [(str(archive), 'b.log')])
        finally:
            win.close()


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestRetentionSettings(GuiTestCase):
    """Issue #86: the zip setting, its preview and its status messages."""

    def test_preview_counts_what_a_run_would_zip_and_saves(self):
        import time

        from gui.settings_dialog import SettingsDialog
        splits = self.dir / 'splits'
        splits.mkdir()
        old = time.time() - 10 * 7 * 86400
        for name in ('251001200000-Sunspire-vet.log', '251002200000-Cloudrest-vet.log'):
            path = splits / name
            path.write_bytes(b'x' * 2048)
            os.utime(path, (old, old))
        (splits / '261020200000-Rockgrove-vet.log').write_bytes(b'x')  # young
        self.config.set('split.dir', str(splits))
        dialog = SettingsDialog(self.config)
        try:
            self.assertEqual(dialog.retention_preview.text(), '')  # off
            dialog.zip_enabled.setChecked(True)
            self.assertIn('Would zip 2 split logs (4 KB)', dialog.retention_preview.text())
            dialog.zip_weeks.setValue(52)
            self.assertIn('Would zip 0 split logs', dialog.retention_preview.text())
            dialog.zip_weeks.setValue(6)
            dialog.apply_to_config()
            self.assertTrue(self.config.get('split.zip_enabled'))
            self.assertEqual(self.config.get('split.zip_after_weeks'), 6)
        finally:
            dialog.deleteLater()

    def test_run_events_reach_the_status_bar(self):
        import split_retention
        from gui.main_window import MainWindow
        win = MainWindow(self.config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        try:
            win._on_retention_event(split_retention.RetentionEvent('started', total=3))
            self.assertIn('Zipping 3 old split logs', win.statusBar().currentMessage())
            win._on_retention_event(split_retention.RetentionEvent(
                'completed', total=3, zipped=2, saved=3 * 1024 ** 3,
                skipped=['a.log: the log changed while it was zipped']))
            message = win.statusBar().currentMessage()
            self.assertIn('Zipped 2 split logs, 3.0 GB saved', message)
            self.assertIn('1 left as they were', message)
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
