#!/usr/bin/env python3
"""The fight's tabs (issue #196, PR 5), offscreen: the main window's right
column as Fight and Deaths tabs on the list's fight, the search in the tab
bar's corner. The tabs and their Alt letters, each pressed twice; Ctrl+PgDn
and Ctrl+PgUp from the list; the tab chosen kept as live fights come and
through a page with no fight; Deaths N in the header; a name on Deaths
opening that death in its fight; the search on the tab on screen, and
Ctrl+C on Deaths; the bar never narrower than its labels, and the search's
own row; nothing to switch while there is no fight."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_death_recap_gui import _entry_with_deaths
from tests.unit.test_gui import HAVE_QT, _ensure_app

_app = None


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class FightTabsTestCase(unittest.TestCase):

    def setUp(self):
        global _app
        _app = _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.windows = []

    def tearDown(self):
        from gui import text_size
        for win in self.windows:
            win.close()
        text_size.apply(text_size.DEFAULT_PCT)  # the application font is shared
        self.tmp.cleanup()

    def _window(self, *entries):
        """A main window shown and active (a shortcut needs an active
        window, which show() alone does not give offscreen), its worker
        stopped, with *entries* come in live: each is selected."""
        from PySide6.QtTest import QTest

        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / "config.json")
        config.set("log_path", str(self.root / "Encounter.log"))
        config.set("update.check_enabled", False)
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.windows.append(win)
        win.resize(1080, 720)
        win.show()
        win.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(win, 2000))
        _app.processEvents()
        for entry in entries:
            win._on_fight_completed(entry)
        return win

    def _key(self, win, key, modifier=None):
        """A key pressed where a user's lands: on the focused widget."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        QTest.keyClick(QApplication.focusWidget() or win, key, modifier or Qt.NoModifier)
        _app.processEvents()

    def _settle(self):
        """The layout requests a resize or a new font posts, run."""
        from PySide6.QtCore import QCoreApplication, QEvent
        for _ in range(4):
            QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
            _app.processEvents()


class TestTheTabs(FightTabsTestCase):

    def test_the_tabs_with_their_alt_letters(self):
        """Fight, Deaths and DPS graph, named for a screen reader; Alt+E,
        Alt+G and Alt+F each land on their tab both times they are
        pressed."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        win = self._window(_entry_with_deaths())
        tabs = win.fight_tabs
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],
                         ["&Fight", "D&eaths", "DPS &graph"])
        self.assertEqual(tabs.accessibleName(), "Fight views")
        self.assertEqual(win.deaths_view.accessibleName(), "Deaths")
        self.assertTrue(tabs.tabBar().isVisible())
        for letter, page in ((Qt.Key_E, win.deaths_view), (Qt.Key_G, win.dps_panel),
                             (Qt.Key_F, tabs.widget(0))):
            for press in (1, 2):
                QTest.keyClick(win, letter, Qt.AltModifier)
                self.assertIs(tabs.currentWidget(), page, press)

    def test_ctrl_page_keys_from_the_list_and_from_a_page(self):
        """Ctrl+PgDn and Ctrl+PgUp change the tab with the focus on the
        list, which keeps it, and on a page; round the end."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        win = self._window(_entry_with_deaths())
        win.history_list.setFocus()
        _app.processEvents()
        self._key(win, Qt.Key_PageDown, Qt.ControlModifier)
        self.assertIs(win.fight_tabs.currentWidget(), win.deaths_view)
        self.assertIs(QApplication.focusWidget(), win.history_list)
        self._key(win, Qt.Key_PageDown, Qt.ControlModifier)
        self.assertIs(win.fight_tabs.currentWidget(), win.dps_panel)
        self._key(win, Qt.Key_PageDown, Qt.ControlModifier)
        self.assertEqual(win.fight_tabs.currentIndex(), 0)
        win.fight_view.setFocus()
        _app.processEvents()
        self._key(win, Qt.Key_PageUp, Qt.ControlModifier)
        self.assertIs(win.fight_tabs.currentWidget(), win.dps_panel)

    def test_the_tab_chosen_stays_as_fights_come(self):
        """Deaths chosen stays on screen as a new live fight is selected,
        drawn for it; and through a page with no fight (a Settings replay),
        which shows the Fight tab, the bar hidden, until a fight is back."""
        win = self._window(_entry_with_deaths())
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        second = _entry_with_deaths()
        win._on_fight_completed(second)
        self.assertIs(win.history_list.current_entry(), second)
        self.assertIs(win.fight_tabs.currentWidget(), win.deaths_view)
        self.assertIs(win._deaths_entry, second)
        win._show_replaying()
        self.assertEqual(win.fight_tabs.currentIndex(), 0)
        self.assertFalse(win.fight_tabs.tabBar().isVisible())
        win._show_fight()
        self.assertTrue(win.fight_tabs.tabBar().isVisible())
        self.assertIs(win.fight_tabs.currentWidget(), win.deaths_view)
        self.assertIs(win._deaths_entry, second)

    def test_deaths_n_in_the_header_opens_the_deaths_tab(self):
        """With a death, the header's Deaths N is a link to the Deaths tab;
        with none, plain text."""
        from PySide6.QtCore import QUrl

        from gui.death_render import FIGHT_DEATHS_HREF
        win = self._window(_entry_with_deaths())
        self.assertIn("Deaths 3", win.fight_view.toPlainText())
        self.assertIn(FIGHT_DEATHS_HREF, win.fight_view.toHtml())
        win.fight_view.anchorClicked.emit(QUrl(FIGHT_DEATHS_HREF))
        self.assertIs(win.fight_tabs.currentWidget(), win.deaths_view)
        calm = _entry_with_deaths()
        calm.death_recaps = []
        calm.deaths = 0
        win.fight_tabs.setCurrentIndex(0)
        win._on_fight_completed(calm)
        self.assertIn("Deaths 0", win.fight_view.toPlainText())
        self.assertNotIn(FIGHT_DEATHS_HREF, win.fight_view.toHtml())

    def test_a_name_on_deaths_opens_that_death_in_its_fight(self):
        """A name on the Deaths tab opens the player window's Deaths tab at
        that death, in the fight the page shows; the window keeps it as
        the list moves on, and a name on the next fight's page opens that
        fight."""
        from PySide6.QtCore import QUrl

        from gui.death_render import recap_href
        from gui.player_window import DEATHS_TAB
        first = _entry_with_deaths()
        win = self._window(first)
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        win.deaths_view.anchorClicked.emit(QUrl(recap_href("1", 2)))
        window = win._player_window
        self.assertEqual((window.entry, window.unit_id, window.current_tab()),
                         (first, "1", DEATHS_TAB))
        second = _entry_with_deaths()
        win._on_fight_completed(second)
        self.assertIs(window.entry, first)
        win.deaths_view.anchorClicked.emit(QUrl(recap_href("77", 1)))
        self.assertEqual((window.entry, window.unit_id), (second, "77"))


class TestTheSearch(FightTabsTestCase):

    def _search(self, win, text, steps=0):
        """Search *text* on the tab on screen and press Enter *steps*
        times; the start of the match the cursor is then at."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        win.search_field.setText(text)
        for _ in range(steps):
            QTest.keyClick(win.search_field, Qt.Key_Return)
        _app.processEvents()
        return win._search_view().textCursor().position()

    def test_the_count_stops_at_999_plus(self):
        """The field keeps room for '999+ matches', the widest count it
        shows (review of #205)."""
        from gui.fight_tabs import WIDEST_COUNT, count_text
        self.assertEqual([count_text(n) for n in (0, 1, 2, 999, 1000, 12345)],
                         ["0 matches", "1 match", "2 matches", "999 matches",
                          "999+ matches", "999+ matches"])
        self.assertEqual(WIDEST_COUNT, "999+ matches")

    def test_the_search_goes_on_where_it_was_on_a_page_drawn_while_hidden(self):
        """Review of #205. On Deaths at the third match, the Fight tab
        shown and Hide names flipped, which draws the fight again: back on
        Deaths, the cursor is at the third match. On Fight at a later
        match, Deaths shown and a pen/crit Save made: back on Fight, still
        that match. With Deaths on screen a new fight comes: back on Fight,
        its first match."""
        win = self._window(_entry_with_deaths())
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        at = self._search(win, "Sharpfang", steps=2)
        starts = [match.selectionStart() for match in win._search_matches()]
        self.assertGreaterEqual(len(starts), 3)
        self.assertEqual(at, starts[2])
        win.fight_tabs.setCurrentIndex(0)
        win.hide_names_action.setChecked(True)
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        self.assertEqual(win.deaths_view.textCursor().position(),
                         [match.selectionStart() for match in win._search_matches()][2])

        win.fight_tabs.setCurrentIndex(0)
        at = self._search(win, "Sharpfang", steps=1)
        self.assertNotEqual(at, win._search_matches()[0].selectionStart())
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        win._apply_pen_crit_settings()
        win.fight_tabs.setCurrentIndex(0)
        self.assertEqual(win.fight_view.textCursor().position(), at)

        win.fight_tabs.setCurrentWidget(win.deaths_view)
        win._on_fight_completed(_entry_with_deaths())
        win.fight_tabs.setCurrentIndex(0)
        self.assertEqual(win.fight_view.textCursor().position(),
                         win._search_matches()[0].selectionStart())

    def test_a_pen_crit_save_keeps_the_search_on_deaths(self):
        """A pen/crit Save with Deaths on screen draws the fight again in
        place: the Deaths page's cursor stays at its match (review of
        #205)."""
        win = self._window(_entry_with_deaths())
        win.fight_tabs.setCurrentIndex(0)
        # The Fight page's cursor at its first match, the header's boss: read
        # against the Deaths page's matches, it is before them all
        self.assertEqual(self._search(win, "Sharpfang"), 0)
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        at = self._search(win, "Sharpfang", steps=1)
        self.assertGreater(at, 0)
        win._apply_pen_crit_settings()
        self.assertEqual(win.deaths_view.textCursor().position(), at)

    def test_the_search_keeps_the_focus_as_it_moves(self):
        """Typing in the search, a bigger text size takes the field from the
        tab bar's corner to its own row, and a smaller one back: the focus
        stays in it, and typing goes on there (review of #205). The column's
        width is measured to hold the corner at 100% and not at 200%, so the
        test holds in any font."""
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        win = self._window(_entry_with_deaths())
        views, field = win.fight_views, win.search_field
        bar = win.fight_tabs.tabBar()
        total = sum(win._splitter.sizes())
        margins = views.parentWidget().layout().contentsMargins()
        win.set_text_size(200)
        self._settle()
        need_200 = bar.sizeHint().width() + field.least_width()
        least_200 = views.minimumSizeHint().width()
        win.set_text_size(100)
        self._settle()
        width = max(bar.sizeHint().width() + field.least_width() + 20, least_200)
        if width >= need_200:
            self.skipTest("no column width holds the corner at 100% and not at 200% here")
        right = width + margins.left() + margins.right()
        win._splitter.setSizes([total - right, right])
        self._settle()
        self.assertTrue(views.in_corner())
        field.setFocus()
        QTest.keyClicks(field, "Sharp")
        win.set_text_size(200)
        self._settle()
        self.assertFalse(views.in_corner())
        self.assertIs(QApplication.focusWidget(), field)
        QTest.keyClicks(QApplication.focusWidget(), "fang")
        win.set_text_size(100)
        self._settle()
        self.assertTrue(views.in_corner())
        self.assertIs(QApplication.focusWidget(), field)
        self.assertEqual(field.text(), "Sharpfang")

    def test_the_search_works_on_the_tab_on_screen(self):
        """Ctrl+F on Deaths puts the cursor in the search, which counts the
        Deaths page's matches; on Fight, the Fight page's. Ctrl+C on Deaths
        copies the fight, as on Fight."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        from gui.fight_tabs import count_text
        win = self._window(_entry_with_deaths())
        win.history_list.setFocus()
        self._key(win, Qt.Key_C, Qt.ControlModifier)
        copied = QGuiApplication.clipboard().text()
        self.assertIn("Sharpfang", copied)
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        win.deaths_view.setFocus()
        _app.processEvents()
        self._key(win, Qt.Key_F, Qt.ControlModifier)
        self.assertIs(QApplication.focusWidget(), win.search_field)
        QTest.keyClicks(win.search_field, "passerby")
        on_deaths = win.deaths_view.toPlainText().lower().count("passerby")
        self.assertGreater(on_deaths, 0)
        self.assertEqual(win.search_count.text(), count_text(on_deaths))
        QTest.keyClick(win, Qt.Key_F, Qt.AltModifier)
        on_fight = win.fight_view.toPlainText().lower().count("passerby")
        self.assertEqual(win.search_count.text(), count_text(on_fight))
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        self.assertEqual(win.search_count.text(), count_text(on_deaths))
        QGuiApplication.clipboard().clear()
        win.deaths_view.setFocus()
        _app.processEvents()
        self._key(win, Qt.Key_C, Qt.ControlModifier)
        self.assertEqual(QGuiApplication.clipboard().text(), copied)

    def test_the_bar_keeps_its_labels_whole_beside_the_search(self):
        """With '128 matches' in the field, at 100% and 200% text, in a wide
        and a narrow right column: the tab bar is never narrower than its
        labels need. The search is in the corner while it has its least
        room there, and on a row of its own above the tabs at 200% in a
        narrow column; in the corner again at 100% in a wide one."""
        win = self._window(_entry_with_deaths())
        views, field = win.fight_views, win.search_field
        bar = win.fight_tabs.tabBar()
        field.set_count("128 matches")
        total = sum(win._splitter.sizes())
        seen = set()
        for pct in (100, 200):
            win.set_text_size(pct)
            for right in (total * 2 // 3, 520, 420):
                win._splitter.setSizes([total - right, right])
                self._settle()
                with self.subTest(pct=pct, right=right):
                    self.assertGreaterEqual(bar.width(), bar.sizeHint().width())
                    self.assertTrue(field.isVisible())
                    if views.in_corner():
                        self.assertGreaterEqual(field.width(), field.least_width())
                    seen.add(views.in_corner())
        self.assertEqual(seen, {True, False})  # both places were used
        win.set_text_size(100)
        win._splitter.setSizes([total // 3, total - total // 3])
        self._settle()
        self.assertTrue(views.in_corner())

    def test_typing_in_the_search_does_not_lay_the_tabs_out_again(self):
        """Each key typed in the search changes its count, not the field's
        text margin, so the tab widget is not laid out again, which
        repainted its pages, the buff timeline strip among them, at every
        key: 46 ms a key on a 22-minute fight, against 1.2 ms in v0.35.0
        (the fresh review of #205). The count appearing lays the field out
        once."""
        from PySide6.QtCore import QEvent, QObject
        from PySide6.QtTest import QTest

        class Layouts(QObject):
            def __init__(self):
                super().__init__()
                self.count = 0

            def eventFilter(self, _watched, event):
                if event.type() == QEvent.LayoutRequest:
                    self.count += 1
                return False

        win = self._window(_entry_with_deaths())
        layouts = Layouts()
        win.fight_tabs.installEventFilter(layouts)
        win.search_field.setFocus()
        QTest.keyClick(win.search_field, "S")
        _app.processEvents()
        self.assertTrue(win.search_count.text())
        layouts.count = 0
        for key in "harpfang":
            QTest.keyClick(win.search_field, key)
            _app.processEvents()
        self.assertEqual(layouts.count, 0)

    def test_ctrl_tab_with_no_fight_stays_on_the_fight_tab(self):
        """With no fight shown (a Settings replay's page), Ctrl+Tab and
        Ctrl+Shift+Tab from the page keep the Fight tab, and the Deaths page
        drawn before holds nothing: the tab widget's own keys showed the
        last fight's deaths there, its names unmasked under Hide names (the
        fresh review of #205)."""
        from PySide6.QtCore import Qt
        win = self._window(_entry_with_deaths())
        win.graph_action.trigger()  # the graph drawn, its legend naming the players
        self.assertGreater(win.dps_panel.legend.count(), 0)
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        self.assertIn("@passerby", win.deaths_view.toPlainText())
        win._on_monitoring_restarting()  # a Settings Save: the list cleared, the replay's page
        self.assertIsNone(win.history_list.current_entry())
        win.hide_names_action.setChecked(True)
        win.fight_view.setFocus()
        _app.processEvents()
        for key, modifier in ((Qt.Key_Tab, Qt.ControlModifier),
                              (Qt.Key_Backtab, Qt.ControlModifier | Qt.ShiftModifier)):
            self._key(win, key, modifier)
            self.assertEqual(win.fight_tabs.currentIndex(), 0, key)
        self.assertNotIn("@passerby", win.deaths_view.toPlainText())
        self.assertEqual(win.dps_panel.legend.count(), 0)  # the graph's names gone too

    def test_detail_view_leaves_the_deaths_page_and_its_search_alone(self):
        """Ctrl+D with Deaths on screen changes the Fight page only: the
        Deaths page's search stays at its match, and the Fight page's starts
        at its first match when it is shown (#206)."""
        win = self._window(_entry_with_deaths())
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        at = self._search(win, "Sharpfang", steps=2)
        win.detail_action.setChecked(False)
        self.assertEqual(win.deaths_view.textCursor().position(), at)
        win.fight_tabs.setCurrentIndex(0)
        self.assertEqual(win.fight_view.textCursor().position(),
                         win._search_matches()[0].selectionStart())

    def test_a_search_typed_on_one_tab_starts_at_the_others_first_match(self):
        """Fight at its third match, a new search typed on Deaths: back on
        Fight, the new search's first match (#206)."""
        win = self._window(_entry_with_deaths())
        self._search(win, "Sharpfang", steps=2)
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        self._search(win, "Slap")
        win.fight_tabs.setCurrentIndex(0)
        matches = win._search_matches()
        self.assertTrue(matches)
        self.assertEqual(win.fight_view.textCursor().position(), matches[0].selectionStart())

    def test_the_tab_link_comes_back_with_its_tab(self):
        """A link reached with Tab on the Fight page has Tab's focus again
        after Ctrl+PgDn and Ctrl+PgUp, as in the player window (#206)."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        win = self._window(_entry_with_deaths())
        view = win.fight_view
        view.setFocus()
        _app.processEvents()
        for _ in range(3):
            QTest.keyClick(view, Qt.Key_Tab)
        link = view._tab_link()
        self.assertIsNotNone(link)
        self._key(win, Qt.Key_PageDown, Qt.ControlModifier)
        self._key(win, Qt.Key_PageUp, Qt.ControlModifier)
        self.assertEqual(win.fight_tabs.currentIndex(), 0)
        self.assertEqual(view._tab_link(), link)

    def test_the_deaths_table_never_breaks_a_word_at_large_text(self):
        """At 200% text in the default window, each cell of the Deaths
        table's time, role, player and dead-for columns is one line: their
        fixed shares broke 'Time' and '1:03' in two (#206)."""
        import re
        win = self._window(_entry_with_deaths())
        win.set_text_size(200)
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        self._settle()
        short = re.compile(r"^(Time|Role|Dead for|\d+:\d\d|@\w+)$")
        checked = 0
        block = win.deaths_view.document().begin()
        while block.isValid():
            if short.match(block.text().strip()):
                self.assertEqual(block.layout().lineCount(), 1, block.text())
                checked += 1
            block = block.next()
        self.assertGreaterEqual(checked, 8)

    def test_the_headers_skull_is_read_as_the_deaths_tab(self):
        """The header's Deaths N ends in a glyph image whose alt text a
        screen reader is given, as the dps figure's is (#206)."""
        from gui.fight_render import DEATHS_GLYPH
        from gui.glyphs import glyph_image
        win = self._window(_entry_with_deaths())
        self.assertIn("Deaths 3 Deaths tab", win.fight_view.accessible_text())
        image = glyph_image(DEATHS_GLYPH, "#1a73e8", 13)
        self.assertIsNotNone(image)
        # Drawn, and in the colour asked for whatever font drew the skull
        # (DejaVu Sans's at 13 px is never wholly opaque, so half will do;
        # a colour emoji font's skull is grey and pink)
        from PySide6.QtGui import QColor
        want = QColor("#1a73e8")
        inked = [image.pixelColor(x, y) for x in range(13) for y in range(13)
                 if image.pixelColor(x, y).alpha() >= 128]
        self.assertTrue(inked)
        for colour in inked:
            self.assertLessEqual(max(abs(colour.red() - want.red()), abs(colour.green() - want.green()),
                                     abs(colour.blue() - want.blue())), 3, colour.name())

    def test_the_tabs_cost_the_windows_least_height_no_more_than_their_bar(self):
        """The window's least height with a fight shown is no more than its
        least with none (the bar hidden) and the bar's height, and the pane
        gives up height for it: a 1280x720 screen held the window at 200%
        text before the tabs and did not after (#206)."""
        from gui.main_window import PANE_LEAST_PX
        win = self._window()
        self._settle()
        bare = win.minimumSizeHint().height()
        win._on_fight_completed(_entry_with_deaths())
        self._settle()
        bar = win.fight_tabs.tabBar().sizeHint().height()
        self.assertTrue(win.fight_views.in_corner())
        self.assertLessEqual(win.minimumSizeHint().height(), bare + bar)
        self.assertEqual(win.fight_view.minimumHeight(), PANE_LEAST_PX)
        self.assertLess(PANE_LEAST_PX, win.fight_view.minimumSizeHint().height())

    def test_the_search_is_off_on_the_graph_and_ctrl_f_goes_to_fight(self):
        """The DPS graph has no text to search: on its tab the search field
        is off, its text kept, and Ctrl+F goes to the Fight tab and puts the
        cursor in the search (issue #196)."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        win = self._window(_entry_with_deaths())
        win.search_field.setText("Sharpfang")
        win.graph_action.trigger()
        self.assertIs(win.fight_tabs.currentWidget(), win.dps_panel)
        self.assertFalse(win.search_field.isEnabled())
        self.assertEqual(win.search_field.text(), "Sharpfang")
        self.assertEqual(win.search_count.text(), "")
        win.dps_panel.legend.setFocus()
        _app.processEvents()
        self._key(win, Qt.Key_F, Qt.ControlModifier)
        self.assertEqual(win.fight_tabs.currentIndex(), 0)
        self.assertTrue(win.search_field.isEnabled())
        self.assertIs(QApplication.focusWidget(), win.search_field)
        self.assertTrue(win.search_count.text())

    def test_a_new_window_gives_the_list_a_third_at_any_text_size(self):
        """A first run's window gives the fight list a third of its width at
        100% and 200% text, the graph tab notwithstanding: the splitter
        shared out the width by the pages' sizes, and the graph's took the
        list from 348 px of 1080 to 121 (issue #196)."""
        from app_config import AppConfig
        from gui.main_window import MainWindow
        widths = []
        for pct in (100, 200):
            config = AppConfig(path=self.root / f"config{pct}.json")
            config.set("log_path", str(self.root / "Encounter.log"))
            config.set("update.check_enabled", False)
            config.set("display.text_scale", pct)
            win = MainWindow(config)
            win.worker_thread.quit()
            win.worker_thread.wait(3000)
            self.windows.append(win)
            win.resize(1080, 720)
            win.show()
            win._on_fight_completed(_entry_with_deaths())
            self._settle()
            widths.append(win._splitter.sizes()[0])
        self.assertEqual(widths[0], widths[1])
        self.assertGreaterEqual(widths[0], sum(win._splitter.sizes()) // 3 - 2)

    def test_a_fight_back_on_the_graph_leaves_the_search_off_and_uncounted(self):
        """The graph chosen, a page with no fight counts its own matches;
        the next fight brings the graph back with the search off and no
        count, where the page's count stayed (review of #207)."""
        win = self._window(_entry_with_deaths())
        win.search_field.setText("Sharpfang")
        win.graph_action.trigger()
        win._show_replaying()
        win._show_fight()
        self.assertIs(win.fight_tabs.currentWidget(), win.dps_panel)
        self.assertFalse(win.search_field.isEnabled())
        self.assertEqual(win.search_count.text(), "")

    def test_with_no_fight_the_column_keeps_no_floor_for_the_hidden_bar(self):
        """With no fight the tab bar is hidden, and the column is no wider
        at least than its pages need; a fight brings the bar's floor back
        (review of #207)."""
        win = self._window()
        # Labels wider than any page, so the bar's floor is the one that binds
        win.fight_tabs.setTabText(0, "&Fight " + "x" * 120)
        win.fight_views.place_search()
        self._settle()
        bar = win.fight_tabs.tabBar().sizeHint().width()
        self.assertLess(win.fight_views.minimumSizeHint().width(), bar)
        win._on_fight_completed(_entry_with_deaths())
        self._settle()
        self.assertGreaterEqual(win.fight_views.minimumSizeHint().width(), bar)

    def test_with_no_fight_the_bar_and_the_search_hide_and_the_keys_do_nothing(self):
        """No fight: the Fight tab, the bar and the search hidden; Ctrl+F,
        Ctrl+PgDn, Ctrl+PgUp and Alt+E do nothing. A fight brings them back."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        win = self._window()
        self.assertFalse(win.fight_views.is_shown())
        self.assertFalse(win.fight_tabs.tabBar().isVisible())
        self.assertFalse(win.search_field.isVisible())
        win.history_list.setFocus()
        _app.processEvents()
        for key, modifier in ((Qt.Key_F, Qt.ControlModifier), (Qt.Key_PageDown, Qt.ControlModifier),
                              (Qt.Key_PageUp, Qt.ControlModifier), (Qt.Key_E, Qt.AltModifier),
                              (Qt.Key_G, Qt.AltModifier)):
            self._key(win, key, modifier)
            self.assertEqual(win.fight_tabs.currentIndex(), 0, key)
            self.assertIsNot(QApplication.focusWidget(), win.search_field, key)
        win._on_fight_completed(_entry_with_deaths())
        self.assertTrue(win.fight_tabs.tabBar().isVisible())
        self.assertTrue(win.search_field.isVisible())


if __name__ == "__main__":
    unittest.main()
