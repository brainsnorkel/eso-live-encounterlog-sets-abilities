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
