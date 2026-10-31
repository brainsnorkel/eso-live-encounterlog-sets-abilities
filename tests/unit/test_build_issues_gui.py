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
        from PySide6.QtGui import QFont, QFontMetrics

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
                # The line height, as the main window passes it
                view.setHtml(render_html(entry, detailed=False, base_pt=pt,
                                         line_px=QFontMetrics(view.font()).height()))
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

    def test_the_mark_is_as_tall_as_the_panes_line(self):
        from gui.fight_render import issues_glyph_px
        self.assertEqual(issues_glyph_px(9.0), 16)  # Segoe UI's line, estimated
        self.assertEqual(issues_glyph_px(9.0, line_px=14), 14)  # DejaVu Sans's
        self.assertEqual(issues_glyph_px(12.0, line_px=21), 21)
        self.assertEqual(issues_glyph_px(5.0, line_px=7), 10)  # the floor

    def test_the_window_sizes_the_mark_from_its_panes_font(self):
        from PySide6.QtGui import QFontMetrics
        win = self._window(_entry())
        try:
            line = QFontMetrics(win.fight_view.font()).height()
            sizes = set()
            block = win.fight_view.document().begin()
            while block.isValid():
                it = block.begin()
                while not it.atEnd():
                    fmt = it.fragment().charFormat()
                    if fmt.isImageFormat():
                        name = fmt.toImageFormat().name()
                        if name.startswith('glyph:issues'):
                            sizes.add(name.rsplit('px=', 1)[1])
                    it += 1
                block = block.next()
            self.assertEqual(sizes, {str(max(10, line))})
        finally:
            win.close()

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

    def test_the_i_stays_clear_of_the_ring_at_every_size_and_scaling(self):
        """Down the middle column: ring, a clear row, the dot, a clear row,
        the stem in whole pixels, a clear row, ring. At the smallest text
        size (80% of 9 pt, 12 px) and at fractional scalings, where a
        layout from the unrounded size blurred the stem (review of #142)."""
        from gui.glyphs import glyph_image
        for px, dpr in ((12, 1.0), (13, 1.0), (16, 1.0), (21, 1.0), (31, 1.0),
                        (15, 1.5), (16, 1.25), (16, 1.5), (13, 1.25), (16, 2.0), (12, 1.75)):
            image = glyph_image('issues', '#166ad8', px, dpr)
            size = image.width()
            column = [image.pixelColor(size // 2, y).alpha() for y in range(size)]
            marks = ''.join('#' if a == 255 else '+' if a > 200 else '.' if a < 128 else '-'
                            for a in column)
            label = f'{px}@{dpr}: {marks} {column}'
            runs = [run for run in marks.replace('-', '.').split('.') if run]
            self.assertEqual(len(runs), 4, label)  # ring, dot, stem, ring
            self.assertEqual(set(runs[2]), {'#'}, label)  # the stem: solid, not blurred
            # A clear row on each side of the dot and of the stem, inside the
            # ring's anti-aliased edge ('-')
            inside = marks[marks.index(runs[0]) + len(runs[0]):marks.rindex(runs[3])].strip('-')
            self.assertTrue(inside.startswith('.') and inside.endswith('.'), label)

    def test_at_the_smallest_mark_dot_and_stem_still_part(self):
        from gui.glyphs import issues_i_layout
        width, dot_top, dot, stem_top, stem = issues_i_layout(10, 2.1, 1.65)
        self.assertEqual(width, 2)
        self.assertGreaterEqual(stem_top, dot_top + dot + 1)  # a clear row between
        self.assertGreaterEqual(stem, 1)

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


def _clean_entry():
    entry = _entry()
    for p in entry.players:
        p['build_issues'] = []
    return entry


class TestFightListHoverText(unittest.TestCase):
    """What the fight list's (i) says on hover (issue #147)."""

    def test_each_flagged_player_with_class_text_and_finding_titles(self):
        from gui.fight_render import ISSUES_CUE, ISSUES_TITLE, fight_issues_tooltip
        text = fight_issues_tooltip(_entry())
        self.assertTrue(text.startswith(f'<b>{ISSUES_TITLE}</b>'), text)
        self.assertIn('<b>@dualwield · NB</b>', text)
        for finding in FINDINGS:
            self.assertIn(f"• {finding['title']}", text)
        # Only the flagged player
        self.assertNotIn('@brainsnorkel', text)
        self.assertIn(f"click a player's {ISSUES_CUE} for the rules", text)

    def test_players_in_the_panes_row_order_with_borrowed_lines(self):
        from gui.fight_render import fight_issues_tooltip
        entry = _entry()
        first = entry.players[0]
        first['build_issues'] = [{'title': 'Two <Poison> glyphs on the front bar'}]
        first['skill_lines'] = ['Herald of the Tome']
        text = fight_issues_tooltip(entry)
        self.assertLess(text.index('@brainsnorkel'), text.index('@dualwield'))
        self.assertIn('@brainsnorkel · Warden +Herald', text)
        self.assertIn('Two &lt;Poison&gt; glyphs', text)

    def test_hide_names_leaves_the_text_form_of_the_mask(self):
        from gui.fight_render import fight_issues_tooltip
        from gui.name_mask import BLOCK, NameMask
        entry = _entry()
        text = fight_issues_tooltip(entry, NameMask.for_entry(entry, True))
        self.assertNotIn('dualwield', text)
        self.assertIn(f"<b>@{BLOCK * len('dualwield')} · NB</b>", text)

    def test_nothing_for_a_fight_without_findings(self):
        from gui.fight_render import fight_issues_tooltip, issues_description
        self.assertEqual(fight_issues_tooltip(_clean_entry()), '')
        self.assertEqual(issues_description(_clean_entry()), '')

    def test_the_description_counts_players_and_names_nobody(self):
        from gui.fight_render import issues_description
        entry = _entry()
        self.assertEqual(issues_description(entry), 'Possible build issues: 1 player')
        entry.players[0]['build_issues'] = list(FINDINGS)
        self.assertEqual(issues_description(entry), 'Possible build issues: 2 players')


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestFightListHover(IssuesGuiTestCase):
    """The fight list's (i) shows the hover text, and only there (#147)."""

    def _list(self, width=520):
        from gui.fight_list import FightList
        lst = FightList()
        lst.resize(width, 200)
        lst.set_fights([_entry(), _clean_entry()])
        lst.show()
        _app.processEvents()
        self.addCleanup(lst.deleteLater)
        self.addCleanup(lst.close)
        return lst

    def _hover(self, lst, pos):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QHelpEvent
        event = QHelpEvent(QEvent.ToolTip, pos, lst.viewport().mapToGlobal(pos))
        QApplication.sendEvent(lst.viewport(), event)
        return lst.current_tooltip

    def _flagged_row(self, lst):
        return lst.row(lst.fight_item(0))

    def test_the_mark_is_found_where_the_list_paints_it(self):
        # Paint the row with and without the mark: the first column that
        # differs is where the mark's ink starts
        from gui.fight_render import ISSUES_LIST_CUE
        with_mark = self._list()
        without = self._list()
        row = self._flagged_row(with_mark)
        text = with_mark.item(row).text()
        without.item(row).setText(text[:text.index(ISSUES_LIST_CUE)])
        _app.processEvents()
        rect = with_mark.issues_mark_rect(row)
        self.assertIsNotNone(rect)
        a = with_mark.viewport().grab().toImage()
        b = without.viewport().grab().toImage()
        dpr = a.devicePixelRatio()
        first = next(x for x in range(a.width())
                     if any(a.pixel(x, y) != b.pixel(x, y)
                            for y in range(int(rect.top() * dpr), int(rect.bottom() * dpr))))
        self.assertGreaterEqual(first / dpr, rect.left() - 1)
        self.assertLessEqual(first / dpr, rect.right() + 1)

    def test_hovering_the_mark_shows_the_hovered_fights_players(self):
        lst = self._list()
        # The clean fight is the one on screen; the hover reads its own row
        lst.select_fight(1)
        rect = lst.issues_mark_rect(self._flagged_row(lst))
        text = self._hover(lst, rect.center())
        self.assertIn('@dualwield · NB', text)
        self.assertIn(FINDINGS[0]['title'], text)

    def test_the_slack_either_side_counts(self):
        from PySide6.QtCore import QPoint

        from gui.fight_list import MARK_SLACK
        lst = self._list()
        rect = lst.issues_mark_rect(self._flagged_row(lst))
        y = rect.center().y()
        self.assertTrue(self._hover(lst, QPoint(rect.left() - MARK_SLACK, y)))
        self.assertTrue(self._hover(lst, QPoint(rect.right() + MARK_SLACK, y)))
        self.assertEqual(self._hover(lst, QPoint(rect.right() + MARK_SLACK + 8, y)), '')

    def test_no_text_elsewhere_on_the_row_or_on_a_clean_fight(self):
        from PySide6.QtCore import QPoint
        lst = self._list()
        flagged = lst.visualItemRect(lst.fight_item(0))
        self.assertEqual(self._hover(lst, QPoint(flagged.left() + 2, flagged.center().y())), '')
        clean = lst.row(lst.fight_item(1))
        self.assertIsNone(lst.issues_mark_rect(clean))
        rect = lst.visualItemRect(lst.item(clean))
        self.assertEqual(self._hover(lst, rect.center()), '')
        # A header row neither
        self.assertIsNone(lst.issues_mark_rect(0))

    def test_hide_names_masks_the_hover_text(self):
        lst = self._list()
        lst.hide_names = True
        text = self._hover(lst, lst.issues_mark_rect(self._flagged_row(lst)).center())
        self.assertNotIn('dualwield', text)
        self.assertIn('· NB', text)

    def test_the_mark_follows_a_narrow_lists_sideways_scroll(self):
        lst = self._list(width=60)
        row = self._flagged_row(lst)
        before = lst.issues_mark_rect(row)
        bar = lst.horizontalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(bar.maximum())
        _app.processEvents()
        self.assertEqual(lst.issues_mark_rect(row).left(), before.left() - bar.value())

    def test_a_screen_reader_hears_the_mark_as_the_rows_description(self):
        from PySide6.QtCore import Qt
        lst = self._list()
        self.assertEqual(lst.fight_item(0).data(Qt.AccessibleDescriptionRole),
                         'Possible build issues: 1 player')
        self.assertEqual(lst.fight_item(1).data(Qt.AccessibleDescriptionRole), '')
        # A rewritten row is described anew
        entry = lst.entry_at(self._flagged_row(lst))
        for p in entry.players:
            p['build_issues'] = []
        lst.update_fight(entry)
        self.assertEqual(lst.fight_item(0).data(Qt.AccessibleDescriptionRole), '')

    def test_the_window_passes_its_hide_names_switch(self):
        win = self._window(_entry())
        try:
            self.assertFalse(win.history_list.hide_names)
            win.hide_names_action.setChecked(True)
            self.assertTrue(win.history_list.hide_names)
            win.hide_names_action.setChecked(False)
            self.assertFalse(win.history_list.hide_names)
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
