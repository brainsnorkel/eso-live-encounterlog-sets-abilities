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

    def test_two_tabs_with_their_alt_letters(self):
        """Fight and Deaths, named for a screen reader; Alt+E and Alt+F
        each land on their tab both times they are pressed."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        win = self._window(_entry_with_deaths())
        tabs = win.fight_tabs
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())], ["&Fight", "D&eaths"])
        self.assertEqual(tabs.accessibleName(), "Fight views")
        self.assertEqual(win.deaths_view.accessibleName(), "Deaths")
        self.assertTrue(tabs.tabBar().isVisible())
        for letter, page in ((Qt.Key_E, win.deaths_view), (Qt.Key_F, tabs.widget(0))):
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
        self.assertEqual(win.fight_tabs.currentIndex(), 0)
        win.fight_view.setFocus()
        _app.processEvents()
        self._key(win, Qt.Key_PageUp, Qt.ControlModifier)
        self.assertIs(win.fight_tabs.currentWidget(), win.deaths_view)

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
        """Typing in the search, the column narrowed past what the corner
        needs takes the field to its own row, and widened again back to
        the corner: the focus stays in it, and typing goes on there. A new
        text size moves it by the same step (FightViews.place_search);
        review of #205. The widths come from the bar and the field, so the
        test holds in any font."""
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        win = self._window(_entry_with_deaths())
        views, field = win.fight_views, win.search_field
        bar = win.fight_tabs.tabBar()
        total = sum(win._splitter.sizes())
        margins = views.parentWidget().layout().contentsMargins()

        def column(width):
            right = width + margins.left() + margins.right()
            win._splitter.setSizes([total - right, right])
            self._settle()
            self.assertEqual(views.width(), width)

        need = bar.sizeHint().width() + field.least_width()
        column(need + 40)
        self.assertTrue(views.in_corner())
        field.setFocus()
        QTest.keyClicks(field, "Sharp")
        column(need - 40)
        self.assertFalse(views.in_corner())
        self.assertIs(QApplication.focusWidget(), field)
        QTest.keyClicks(QApplication.focusWidget(), "fang")
        column(need + 40)
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
                              (Qt.Key_PageUp, Qt.ControlModifier), (Qt.Key_E, Qt.AltModifier)):
            self._key(win, key, modifier)
            self.assertEqual(win.fight_tabs.currentIndex(), 0, key)
            self.assertIsNot(QApplication.focusWidget(), win.search_field, key)
        win._on_fight_completed(_entry_with_deaths())
        self.assertTrue(win.fight_tabs.tabBar().isVisible())
        self.assertTrue(win.search_field.isVisible())


if __name__ == "__main__":
    unittest.main()
