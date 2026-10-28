#!/usr/bin/env python3
"""The (i) of possible build issues in the GUI (offscreen Qt): the cue on
the fight pane, its hover text, the click, the popup, and the list repeated
in the build window (issue #16)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from build_session import fights

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

_app = None
ALKOSH_URL = 'https://eso-hub.com/en/sets/roar-of-alkosh'
DRAIN_URL = 'https://eso-hub.com/en/skills/weapon/destruction-staff/elemental-drain'
FINDINGS = [
    {'rule': 'nirnhoned-off-hand', 'title': 'Nirnhoned on the off-hand Dagger (front bar)',
     'detail': 'Nirnhoned raises the damage of the weapon it is on <6%>', 'set': '', 'skill': ''},
    {'rule': 'set-never-fired', 'title': 'Roar of Alkosh never fired in 2 fights of a minute or more',
     'detail': "Roar of Alkosh's five-piece bonus fires when the wearer activates a synergy",
     'set': 'Roar of Alkosh', 'skill': ''},
    {'rule': 'elemental-drain', 'title': 'Elemental Drain slotted (back bar)',
     'detail': 'Elemental Drain applies Major Breach and Minor Magickasteal.',
     'set': '', 'skill': 'Elemental Drain'},
]


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _set_links(name):
    return ALKOSH_URL if name == 'Roar of Alkosh' else None


def _links(name):
    return DRAIN_URL if name == 'Elemental Drain' else None


def _entry():
    """The shared session's fight, with findings on @dualwield (unit 2) alone."""
    entry = fights()[0]
    for p in entry.players:
        p['build_issues'] = list(FINDINGS) if p['unit_id'] == '2' else []
    return entry


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class IssuesGuiTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _window(self, entry):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / 'config.json')
        config.set('log_path', str(self.root / 'Encounter.log'))
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        win._on_fight_completed(entry)
        win.history_list.select_fight(0)
        return win

    def _popups(self):
        from gui.build_issues_popup import BuildIssuesPopup
        return [w for w in _app.topLevelWidgets() if isinstance(w, BuildIssuesPopup)]


class TestCue(IssuesGuiTestCase):

    def test_only_a_player_with_findings_carries_the_cue_in_both_views(self):
        from gui.fight_render import ISSUES_CUE, render_html
        entry = _entry()
        for detailed in (True, False):
            html = render_html(entry, detailed=detailed)
            self.assertEqual(html.count('esolog:issues/'), 1, detailed)
            self.assertIn('href="esolog:issues/2" style="text-decoration:none;color:#166ad8">'
                          f'{ISSUES_CUE}</a>', html)
            # After the class text of that row, before the next row
            row = html[html.index('@dualwield'):html.index('</tr>', html.index('@dualwield'))]
            self.assertIn('esolog:issues/2', row)
        self.assertIn(f'color:#8ab4f8">{ISSUES_CUE}</a>', render_html(entry, detailed=True, dark=True))
        # The same mark as the fight list's
        from gui.fight_render import ISSUES_LIST_CUE
        self.assertEqual(ISSUES_CUE, ISSUES_LIST_CUE)

    def test_no_findings_no_cue(self):
        from gui.fight_render import render_html
        entry = _entry()
        for p in entry.players:
            p['build_issues'] = []
        self.assertNotIn('esolog:issues/', render_html(entry, detailed=True))
        del entry.players[0]['build_issues']  # an entry from an older engine
        self.assertNotIn('esolog:issues/', render_html(entry, detailed=False))

    def test_hover_text_lists_the_titles(self):
        from gui.fight_render import issues_tooltips
        tips = issues_tooltips(_entry())
        self.assertEqual(set(tips), {'esolog:issues/2'})
        tip = tips['esolog:issues/2']
        self.assertIn('<b>Possible build issues</b>', tip)
        for finding in FINDINGS:
            self.assertIn(finding['title'].replace("'", '&#x27;'), tip)
        self.assertIn('Click for the rules', tip)
        # The window's hover map carries it
        win = self._window(_entry())
        try:
            self.assertIn('esolog:issues/2', win.fight_view._tooltips)
        finally:
            win.close()

    def test_issues_html_has_each_finding_its_rule_and_the_links(self):
        from gui.fight_render import issues_html
        p = next(p for p in _entry().players if p['unit_id'] == '2')
        html = issues_html(p, dark=False, set_links=_set_links, links=_links)
        self.assertIn('Possible build issues', html)
        for finding in FINDINGS:
            self.assertIn(f"<b>{finding['title']}</b>".replace("'", '&#x27;'), html)
            self.assertIn(finding['detail'].replace('<', '&lt;').replace('>', '&gt;')
                          .replace("'", '&#x27;'), html)
        self.assertIn(f'<a href="{ALKOSH_URL}"', html)
        self.assertIn('Roar of Alkosh on ESO-Hub', html)
        self.assertIn(f'<a href="{DRAIN_URL}"', html)
        self.assertEqual(html.count('on ESO-Hub'), 2)
        # Without the maps, no links; without findings, nothing
        self.assertNotIn('ESO-Hub', issues_html(p))
        self.assertEqual(issues_html({'build_issues': []}), '')
        self.assertEqual(issues_html(None), '')

    def test_click_is_announced(self):
        from PySide6.QtCore import QUrl

        from gui.fight_view import FightView
        view = FightView()
        asked, builds = [], []
        view.issues_requested.connect(asked.append)
        view.build_requested.connect(builds.append)
        view.anchorClicked.emit(QUrl('esolog:issues/2'))
        view.anchorClicked.emit(QUrl('esolog:build/2'))
        self.assertEqual((asked, builds), (['2'], ['2']))


class TestPopup(IssuesGuiTestCase):

    def test_the_window_opens_the_popup_for_the_clicked_player(self):
        from gui.fight_render import ISSUES_TITLE
        win = self._window(_entry())
        try:
            win.fight_view.issues_requested.emit('2')
            _app.processEvents()
            popups = self._popups()
            self.assertEqual(len(popups), 1)
            popup = popups[0]
            self.assertTrue(popup.isVisible())
            text = popup.label.text()
            self.assertIn(ISSUES_TITLE, text)
            for finding in FINDINGS:
                self.assertIn(finding['title'].replace("'", '&#x27;'), text)
            # Esc closes it, and Qt deletes it
            from PySide6.QtCore import Qt
            from PySide6.QtTest import QTest
            QTest.keyClick(popup, Qt.Key_Escape)
            _app.processEvents()
            self.assertEqual(self._popups(), [])
        finally:
            win.close()

    def test_no_popup_for_a_player_without_findings_or_unknown(self):
        win = self._window(_entry())
        try:
            win.fight_view.issues_requested.emit('1')
            win.fight_view.issues_requested.emit('99')
            _app.processEvents()
            self.assertEqual(self._popups(), [])
        finally:
            win.close()

    def test_popup_stays_on_screen(self):
        from PySide6.QtCore import QPoint

        from gui.build_issues_popup import BuildIssuesPopup
        popup = BuildIssuesPopup('<b>x</b><br>' + 'a long rule sentence ' * 30)
        try:
            area = _app.primaryScreen().availableGeometry()
            popup.show_at(QPoint(area.right() - 5, area.bottom() - 5))
            self.assertTrue(popup.isVisible())
            self.assertLessEqual(popup.geometry().right(), area.right())
            self.assertLessEqual(popup.geometry().bottom(), area.bottom())
            self.assertTrue(popup.label.wordWrap())
            self.assertTrue(popup.label.openExternalLinks())
        finally:
            popup.close()


class TestBuildWindow(IssuesGuiTestCase):

    def test_the_build_window_repeats_the_findings(self):
        from gui.build_render import render_build_html
        from gui.fight_render import ISSUES_TITLE
        entry = _entry()
        html = render_build_html(entry, '2', set_links=_set_links, links=_links)
        self.assertIn(ISSUES_TITLE, html)
        self.assertIn('Roar of Alkosh on ESO-Hub', html)
        # Under the header, before the bars
        self.assertLess(html.index(ISSUES_TITLE), html.index('>Front<'))
        self.assertNotIn(ISSUES_TITLE, render_build_html(entry, '1'))

    def test_the_dialog_shows_them(self):
        from gui.fight_render import ISSUES_TITLE
        win = self._window(_entry())
        try:
            win._show_build('2')
            self.assertIn(ISSUES_TITLE, win._build_dialog.view.toPlainText())
            win._show_build('1')
            self.assertNotIn(ISSUES_TITLE, win._build_dialog.view.toPlainText())
        finally:
            win.close()


class TestHistoryListCue(IssuesGuiTestCase):
    """The fight list marks a fight with a flagged player with a circled i,
    after the skull of a fight with a death; the copied text has neither."""

    def test_summary_line_marks_a_fight_with_a_flagged_player(self):
        from gui.fight_render import (
            DEATH_CUE,
            ISSUES_LIST_CUE,
            render_plain_text,
            summary_line,
        )
        entry = _entry()
        self.assertEqual(DEATH_CUE, '☠')
        self.assertEqual(ISSUES_LIST_CUE, 'ⓘ')
        line = summary_line(entry, death_cue=True, issue_cue=True)
        self.assertTrue(line.startswith(f'Test Boss {ISSUES_LIST_CUE} · '), line)
        self.assertNotIn(DEATH_CUE, line)
        # A death too: skull first, then the i
        entry.deaths = 1
        self.assertTrue(summary_line(entry, death_cue=True, issue_cue=True)
                        .startswith(f'Test Boss {DEATH_CUE} {ISSUES_LIST_CUE} · '))
        # Neither cue in the copied text, nor without the flags
        self.assertNotIn(ISSUES_LIST_CUE, summary_line(entry))
        self.assertNotIn(ISSUES_LIST_CUE, render_plain_text(entry))
        self.assertNotIn(ISSUES_LIST_CUE, summary_line(entry, death_cue=True))
        # No flagged player, no mark
        for p in entry.players:
            p['build_issues'] = []
        self.assertNotIn(ISSUES_LIST_CUE, summary_line(entry, death_cue=True, issue_cue=True))

    def test_the_window_list_carries_it(self):
        from gui.fight_render import ISSUES_LIST_CUE
        win = self._window(_entry())
        try:
            self.assertIn(ISSUES_LIST_CUE, win.history_list.fight_item(0).text())
            clean = _entry()
            for p in clean.players:
                p['build_issues'] = []
            win._on_fight_completed(clean)
            self.assertNotIn(ISSUES_LIST_CUE, win.history_list.fight_item(1).text())
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
