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
        import re

        from gui.fight_render import render_html
        entry = _entry()
        for detailed in (True, False):
            html = render_html(entry, detailed=detailed)
            self.assertEqual(html.count('esolog:issues/'), 1, detailed)
            # The anchor holds the drawn (i) in the link colour, as tall as
            # the line and aligned to its top (issue #140)
            cue = re.search(r'<a href="esolog:issues/2" style="text-decoration:none">(.*?)</a>',
                            html).group(1)
            self.assertEqual(cue, '<img src="glyph:issues?color=166ad8&amp;px=16" '
                                  'alt="possible build issues" style="vertical-align:top">')
            # Right after the name, before the class text of that row
            row = html[html.index('esolog:build/2'):html.index('</tr>', html.index('esolog:build/2'))]
            self.assertIn('>@dualwield</a>&nbsp;<a href="esolog:issues/2"', row)
            self.assertLess(row.index('esolog:issues/2'), row.index('NB'))
        self.assertIn('glyph:issues?color=8ab4f8&amp;px=16',
                      render_html(entry, detailed=True, dark=True))
        # The glyph follows the pane's font size
        self.assertIn('glyph:issues?color=166ad8&amp;px=21',
                      render_html(entry, detailed=False, base_pt=12.0))

    def test_the_cue_follows_the_first_damage_star(self):
        from gui.fight_render import render_html
        entry = _entry()
        entry.first_damage_dealer = '2'
        html = render_html(entry, detailed=False)
        self.assertIn('>@dualwield</a> <b>*</b>&nbsp;<a href="esolog:issues/2"', html)

    def test_a_hidden_name_does_not_take_the_cue_in(self):
        from gui.fight_render import render_html
        from gui.name_mask import NameMask
        entry = _entry()
        html = render_html(entry, detailed=False, names=NameMask.for_entry(entry, True))
        row = html[html.index('esolog:build/2'):html.index('</tr>', html.index('esolog:build/2'))]
        self.assertNotIn('@dualwield', row)
        # The stand-in image, the name's anchor closed, then the cue
        self.assertLess(row.index('mask:'), row.index('</a>&nbsp;<a href="esolog:issues/2"'))

    def test_the_fight_list_popup_and_build_window_keep_the_text_mark(self):
        from gui.fight_render import ISSUES_CUE, ISSUES_LIST_CUE, issues_html
        self.assertEqual(ISSUES_CUE, ISSUES_LIST_CUE)
        p = next(p for p in _entry().players if p['unit_id'] == '2')
        self.assertEqual(issues_html(p).count(ISSUES_CUE), len(FINDINGS))

    def test_the_mark_leaves_the_rows_their_height(self):
        """A marked row is as tall as an unmarked one, at three text sizes:
        the image is no taller than the line and aligned to its top."""
        from PySide6.QtGui import QFont

        from gui.fight_render import render_html
        from gui.fight_view import FightView
        for pt in (9.0, 12.0, 18.0):
            heights = []
            for marked in (False, True):
                entry = _entry()
                if not marked:
                    for p in entry.players:
                        p['build_issues'] = []
                view = FightView()
                view.setFont(QFont(view.font().family(), pt))
                view.setHtml(render_html(entry, detailed=False, base_pt=pt))
                # Wide enough that no cell wraps even in the fallback font
                # CI draws with (no font directory: every glyph a wide box)
                view.document().setTextWidth(20000)
                # The whole page laid out, not only what a pane would show
                heights.append(view.document().documentLayout().documentSize().height())
                view.deleteLater()
            self.assertEqual(heights[0], heights[1], pt)

    def test_a_screen_reader_hears_what_the_mark_is(self):
        from gui.fight_render import render_html
        from gui.fight_view import FightView
        view = FightView()
        view.setHtml(render_html(_entry(), detailed=False))
        self.assertIn('@dualwield possible build issues', ' '.join(view.accessible_text().split()))
        view.deleteLater()

    def test_the_view_holds_the_mark_to_its_line(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QFont, QFontMetrics, QTextDocument

        from gui.fight_view import FightView
        view = FightView()
        view.setFont(QFont(view.font().family(), 9))
        line = QFontMetrics(view.font()).height()
        served = view.loadResource(QTextDocument.ImageResource,
                                   QUrl(f'glyph:issues?color=166ad8&px={line + 4}'))
        self.assertEqual(served.width(), line)
        served = view.loadResource(QTextDocument.ImageResource,
                                   QUrl(f'glyph:issues?color=166ad8&px={line - 2}'))
        self.assertEqual(served.width(), line - 2)
        # Only this glyph: the others keep the size asked for
        served = view.loadResource(QTextDocument.ImageResource,
                                   QUrl(f'glyph:graph?color=166ad8&px={line + 4}'))
        self.assertEqual(served.width(), line + 4)
        view.deleteLater()

    def test_the_mark_is_a_bold_ring_and_i_over_a_faint_halo(self):
        from gui.glyphs import glyph_image
        image = glyph_image('issues', '#166ad8', 16)
        self.assertEqual((image.width(), image.height()), (16, 16))

        def alpha(x, y):
            return image.pixelColor(x, y).alpha()

        # Across the middle: halo, ring, the clear inside, the ring again
        middle = [alpha(x, 8) for x in range(16)]
        self.assertTrue(0 < middle[1] < 80, middle)  # the halo: faint
        self.assertGreater(middle[3], 230, middle)  # the ring
        self.assertEqual(middle[5], 0, middle)  # inside the ring: clear
        self.assertGreater(middle[12], 230, middle)
        self.assertEqual(alpha(0, 0), 0)  # a clear corner
        # Down the i: a clear pixel, the dot, a clear pixel, the stem, a
        # clear pixel, so the two never run together at 100% scaling
        column = [alpha(7, y) for y in range(4, 12)]
        self.assertEqual([a > 200 for a in column],
                         [False, True, True, False, True, True, True, False], column)
        self.assertTrue(all(a < 5 for a, solid in zip(column, [0, 1, 1, 0, 1, 1, 1, 0])
                            if not solid), column)
        # Solid pixels are the link colour itself
        solid = {image.pixelColor(x, y).name() for x in range(16) for y in range(16)
                 if alpha(x, y) == 255}
        self.assertEqual(solid, {'#166ad8'})
        # On a scaled display: twice the pixels, the same logical size
        hidpi = glyph_image('issues', '#166ad8', 16, dpr=2.0)
        self.assertEqual((hidpi.width(), hidpi.devicePixelRatio()), (32, 2.0))

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
