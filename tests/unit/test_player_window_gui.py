#!/usr/bin/env python3
"""The player window (issue #196, PR 4), offscreen: one window with a tab
for each pane link in place of the build, damage, damage taken and death
recap windows. Which tab each link opens; the seven tabs and their Alt
letters, each pressed twice; Ctrl+PgDn, Ctrl+Up and the player picker;
tabs that do not apply; Boss targets only; Show in list; the fight
changing in place and a Settings replay; a pen/crit save; the size; the
focus; the teardown; the names a screen reader is given."""

import os
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from build_session import fights

from tests.unit.test_damage_window_gui import _entry as _damage_entry
from tests.unit.test_death_recap_gui import _entry_with_deaths
from tests.unit.test_gui import HAVE_QT, _ensure_app
from tests.unit.test_taken_window_gui import _entry as _taken_entry

_app = None


def _wait_for(condition, ms=1000):
    """Run the event loop until *condition()* holds or *ms* have passed;
    whether it holds (PySide6's QTest has no qWaitFor)."""
    import time

    from PySide6.QtTest import QTest
    deadline = time.monotonic() + ms / 1000
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
    return bool(condition())


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class PlayerWindowTestCase(unittest.TestCase):

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

    def _window(self, *entries, show=False):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / "config.json")
        config.set("log_path", str(self.root / "Encounter.log"))
        config.set("update.check_enabled", False)
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.windows.append(win)
        if show:
            win.resize(1080, 720)
            win.show()
        # The worker's queued startup signals, before the fights
        _app.processEvents()
        for entry in entries:
            win._on_fight_completed(entry)
        if entries:
            win.history_list.select_fight(0)
        return win

    def _click(self, win, href):
        from PySide6.QtCore import QUrl
        win.fight_view.anchorClicked.emit(QUrl(href))
        return win._player_window

    def _active(self, window):
        from PySide6.QtTest import QTest
        window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(window, 2000))


class TestOneWindowForEveryLink(PlayerWindowTestCase):

    def test_each_pane_link_opens_its_tab(self):
        """The name and the lone mastery's '?' open Build, the dps figure
        Damage done, the token Pen and crit, the shield Damage taken, the
        skull and the Also died chip Deaths: one window, which each link
        reuses."""
        from gui.player_window import (
            BUILD_TAB,
            DAMAGE_TAB,
            DEATHS_TAB,
            PEN_CRIT_TAB,
            TAKEN_TAB,
        )
        win = self._window(_entry_with_deaths())
        first = None
        for href, tab, unit in (("esolog:build/1", BUILD_TAB, "1"),
                                ("esolog:mastery/2", BUILD_TAB, "2"),
                                ("esolog:damage/1", DAMAGE_TAB, "1"),
                                ("esolog:pencrit/2", PEN_CRIT_TAB, "2"),
                                ("esolog:taken/1", TAKEN_TAB, "1"),
                                ("esolog:deaths/1", DEATHS_TAB, "1"),
                                ("esolog:deaths/77", DEATHS_TAB, "77")):
            window = self._click(win, href)
            first = first or window
            self.assertIs(window, first, href)
            self.assertTrue(window.isVisible(), href)
            self.assertEqual((window.current_tab(), window.unit_id), (tab, unit), href)

    def test_the_seven_tabs_in_order_with_their_titles(self):
        from gui.player_window import TAB_KEYS
        win = self._window(fights()[0])
        window = self._click(win, "esolog:build/1")
        labels = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        self.assertEqual(labels, ["&Build", "&Damage done", "&Pen and crit", "&Resources",
                                  "Damage &taken", "&Healing received", "D&eaths"])
        titles = []
        for index in range(len(TAB_KEYS)):
            window.tabs.setCurrentIndex(index)
            titles.append(window.windowTitle())
        self.assertEqual(titles, ["Build – @brainsnorkel (Pïque)", "Damage – @brainsnorkel",
                                  "Pen and crit – @brainsnorkel", "Resources – @brainsnorkel",
                                  "Damage taken – @brainsnorkel", "Healing received – @brainsnorkel",
                                  "Death recap – @brainsnorkel"])

    def test_the_header_names_the_fight_and_the_player(self):
        from gui.player_window import fight_line
        entry = _damage_entry()
        win = self._window(entry)
        window = self._click(win, "esolog:damage/1")
        self.assertEqual(window.fight_label.text(),
                         "Sharpfang · Moonlit Cove VET · 1:40 · 16:54:04")
        self.assertEqual(window.fight_label.text(), fight_line(entry))
        self.assertEqual(window.picker.currentText(), "D  @tester  Templar")


class TestKeys(PlayerWindowTestCase):
    """On a window of its own: offscreen, a second top-level window beside
    the main one never becomes the application's active window, so the
    window's keys would never reach it."""

    def _alone(self, entry, tab, unit="1"):
        from gui.player_window import PlayerWindow
        window = PlayerWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        window.open(entry, unit, tab, dark=False)
        self._active(window)
        return window

    def test_each_alt_letter_twice(self):
        """The tab labels' mnemonics, never shortcuts too: each pressed
        twice lands on its tab both times (a key bound twice in a window
        works every other press). Alt+O ticks Boss targets only on Damage
        done, twice."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from gui.player_window import BUILD_TAB, TAB_KEYS
        window = self._alone(_damage_entry(), BUILD_TAB)
        for letter, tab in zip("BDPRTHE", TAB_KEYS):
            for press in (1, 2):
                QTest.keyClick(window, getattr(Qt, f"Key_{letter}"), Qt.AltModifier)
                self.assertEqual(window.current_tab(), tab, (letter, press))
        QTest.keyClick(window, Qt.Key_D, Qt.AltModifier)
        self.assertTrue(window.boss_only.isVisible())
        # A check box's mnemonic clicks it as a short animation
        QTest.keyClick(window, Qt.Key_O, Qt.AltModifier)
        self.assertTrue(_wait_for(window.boss_only.isChecked))
        QTest.keyClick(window, Qt.Key_O, Qt.AltModifier)
        self.assertTrue(_wait_for(lambda: not window.boss_only.isChecked()))

    def test_ctrl_page_keys_and_the_player_keys(self):
        """Ctrl+PgDn and Ctrl+PgUp change the tab from the page, round the
        end; Ctrl+Down and Ctrl+Up, and the buttons beside the picker, the
        player, keeping the tab, the buttons off at the ends."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from gui.player_window import BUILD_TAB, DAMAGE_TAB, DEATHS_TAB
        window = self._alone(fights()[0], BUILD_TAB)
        QTest.keyClick(window.view(BUILD_TAB), Qt.Key_PageDown, Qt.ControlModifier)
        self.assertEqual(window.current_tab(), DAMAGE_TAB)
        QTest.keyClick(window.view(DAMAGE_TAB), Qt.Key_PageUp, Qt.ControlModifier)
        QTest.keyClick(window.view(BUILD_TAB), Qt.Key_PageUp, Qt.ControlModifier)
        self.assertEqual(window.current_tab(), DEATHS_TAB)
        QTest.keyClick(window.view(DEATHS_TAB), Qt.Key_PageDown, Qt.ControlModifier)
        self.assertEqual(window.current_tab(), BUILD_TAB)

        self.assertFalse(window.previous_player.isEnabled())
        QTest.keyClick(window.view(BUILD_TAB), Qt.Key_Down, Qt.ControlModifier)
        self.assertEqual((window.unit_id, window.current_tab()), ("2", BUILD_TAB))
        self.assertEqual(window.windowTitle(), "Build – @dualwield (Stabby)")
        window.next_player.click()
        self.assertEqual(window.unit_id, "3")
        self.assertFalse(window.next_player.isEnabled())
        QTest.keyClick(window.view(BUILD_TAB), Qt.Key_Up, Qt.ControlModifier)
        self.assertEqual(window.unit_id, "2")

    def test_opening_puts_the_focus_in_the_page(self):
        """Opened, the window's focus is in the page; a tab changed from the
        picker takes it into the new page, since PgDn there would change
        the player; Esc hides the window, Enter does not."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        from gui.player_window import DAMAGE_TAB, TAKEN_TAB
        window = self._alone(fights()[0], DAMAGE_TAB)
        self.assertIs(QApplication.focusWidget(), window.view(DAMAGE_TAB))
        window.picker.setFocus()
        QTest.keyClick(window, Qt.Key_T, Qt.AltModifier)
        self.assertEqual(window.current_tab(), TAKEN_TAB)
        self.assertIs(QApplication.focusWidget(), window.view(TAKEN_TAB))
        QTest.keyClick(window.view(TAKEN_TAB), Qt.Key_Return)
        self.assertTrue(window.isVisible())
        QTest.keyClick(window.view(TAKEN_TAB), Qt.Key_Escape)
        self.assertFalse(window.isVisible())

    def test_a_link_from_the_main_window_puts_the_focus_in_the_page(self):
        """Opened from the pane, the main window still active: the player
        window's own focus is in the opened tab's page, for when it is
        brought up."""
        from gui.player_window import DAMAGE_TAB, TAKEN_TAB
        win = self._window(fights()[0], show=True)
        window = self._click(win, "esolog:damage/1")
        self.assertIs(window.focusWidget(), window.view(DAMAGE_TAB))
        window = self._click(win, "esolog:taken/1")
        self.assertIs(window.focusWidget(), window.view(TAKEN_TAB))


class TestWhatTheTabsShow(PlayerWindowTestCase):

    def test_the_picker_lists_the_rows_then_the_also_died(self):
        """The fight's rows in the pane's order, each with its deaths, then
        the players the table does not list who died: no build of theirs
        reached the log, so each tab but Deaths says so."""
        from gui.build_render import NO_BUILD
        from gui.player_window import BUILD_TAB, DEATHS_TAB
        win = self._window(_entry_with_deaths())
        window = self._click(win, "esolog:deaths/1")
        rows = [window.picker.itemText(i) for i in range(window.picker.count())]
        self.assertEqual(rows, ["D  @tester  ☠ ×2", "D  @friend", "@passerby  ☠  · also died"])
        window.picker.setCurrentIndex(2)
        self.assertEqual(window.unit_id, "77")
        self.assertIn("Death 1 of 1", window.view(DEATHS_TAB).toPlainText())
        window.tabs.setCurrentIndex(window.tabs.indexOf(window.view(BUILD_TAB)))
        self.assertIn(NO_BUILD, window.view(BUILD_TAB).toPlainText())

    def test_tabs_that_do_not_apply_say_so(self):
        """A survivor's Deaths tab says they did not die; a companion's tabs
        past Damage done that none are logged for it, and its Deaths tab how
        often it died. No tab is disabled (Qt moves off a disabled current
        tab)."""
        from gui.player_window import (
            DEATHS_TAB,
            HEALING_TAB,
            NO_COMPANION_DATA,
            PEN_CRIT_TAB,
            RESOURCES_TAB,
            TAB_KEYS,
            TAKEN_TAB,
        )
        entry = _taken_entry()
        entry.players[2]["deaths"] = 2
        win = self._window(entry)
        window = self._click(win, "esolog:deaths/2")
        self.assertEqual(window.view(DEATHS_TAB).toPlainText().strip(),
                         "@friend did not die in this fight.")
        window = self._click(win, "esolog:build/3")
        for tab in (PEN_CRIT_TAB, RESOURCES_TAB, TAKEN_TAB, HEALING_TAB):
            window.tabs.setCurrentIndex(TAB_KEYS.index(tab))
            self.assertEqual(window.view(tab).toPlainText().strip(), NO_COMPANION_DATA, tab)
        window.tabs.setCurrentIndex(TAB_KEYS.index(DEATHS_TAB))
        self.assertIn("died 2 times; the log keeps no recap of a companion's deaths",
                      window.view(DEATHS_TAB).toPlainText())
        self.assertTrue(all(window.tabs.isTabEnabled(i) for i in range(window.tabs.count())))

    def test_boss_targets_only_on_damage_done_with_boss_damage(self):
        """The switch shows on Damage done for a player with damage to the
        bosses, narrowing the page to them; with none it is hidden and
        cleared; on the other tabs it is hidden, not cleared."""
        from gui.player_window import BUILD_TAB, DAMAGE_TAB, TAB_KEYS
        win = self._window(_damage_entry())
        window = self._click(win, "esolog:damage/1")
        self.assertTrue(window.boss_only.isVisibleTo(window))
        window.boss_only.setChecked(True)
        self.assertIn("damage to the bosses", window.view(DAMAGE_TAB).toPlainText())
        window.tabs.setCurrentIndex(TAB_KEYS.index(BUILD_TAB))
        self.assertFalse(window.boss_only.isVisibleTo(window))
        self.assertTrue(window.boss_only.isChecked())
        self._click(win, "esolog:damage/2")
        self.assertFalse(window.boss_only.isVisibleTo(window))
        self.assertFalse(window.boss_only.isChecked())

    def test_the_pages_links_are_the_windows_tabs(self):
        """A page's link to another of the player's pages switches the tab:
        the healing received line, the Damage dealt heading's link and the
        Deaths tab's last line."""
        from PySide6.QtCore import QUrl

        from gui.player_window import DAMAGE_TAB, DEATHS_TAB, HEALING_TAB, TAKEN_TAB
        win = self._window(_taken_entry())
        window = self._click(win, "esolog:taken/1")
        window.view(TAKEN_TAB).anchorClicked.emit(QUrl("esolog:healing/1"))
        self.assertEqual(window.current_tab(), HEALING_TAB)
        window.view(HEALING_TAB).anchorClicked.emit(QUrl("esolog:damage/1"))
        self.assertEqual(window.current_tab(), DAMAGE_TAB)
        window.view(DAMAGE_TAB).anchorClicked.emit(QUrl("esolog:taken/1"))
        self.assertEqual(window.current_tab(), TAKEN_TAB)
        window.view(TAKEN_TAB).anchorClicked.emit(QUrl("esolog:deaths/1"))
        self.assertEqual(window.current_tab(), DEATHS_TAB)


class TestTheWindowsFight(PlayerWindowTestCase):

    def test_show_in_list_selects_the_fight(self):
        """Show in list selects the window's fight in the list, which has
        moved on, and brings the main window up; off, with its reason, while
        a review has the list, and on again at Back to live."""
        from gui.player_window import NOT_LISTED_TIP
        first, later = fights()[0], fights()[0]
        later.boss_name = "Another Boss"
        win = self._window(first, show=True)
        window = self._click(win, "esolog:build/1")
        win._on_fight_completed(later)
        self.assertIs(win.history_list.current_entry(), later)
        self.assertTrue(window.show_in_list.isEnabled())
        window.show_in_list.click()
        self.assertIs(win.history_list.current_entry(), first)
        win._on_review_loaded("old.log", [fights()[0]])
        self.assertFalse(window.show_in_list.isEnabled())
        self.assertEqual(window.show_in_list.toolTip(), NOT_LISTED_TIP)
        win._exit_review()
        self.assertTrue(window.show_in_list.isEnabled())

    def test_an_update_in_place_draws_the_tab_on_screen_once(self):
        """Three updates to the window's fight in one pass (mark_context and
        the backfill send one per earlier fight) draw the tab on screen
        once, on the event loop's next turn; another tab is drawn when it
        is shown."""
        from gui.player_window import BUILD_TAB, DAMAGE_TAB, TAB_KEYS
        entry = fights()[0]
        win = self._window(entry, show=True)
        window = self._click(win, "esolog:build/1")
        with mock.patch.object(window, "_render", wraps=window._render) as render:
            for _ in range(3):
                win._on_fight_updated(entry)
            self.assertEqual(render.call_count, 0)
            _app.processEvents()
            self.assertEqual([call.args for call in render.call_args_list], [(BUILD_TAB,)])
            window.tabs.setCurrentIndex(TAB_KEYS.index(DAMAGE_TAB))
            self.assertEqual(render.call_args_list[-1].args, (DAMAGE_TAB,))
            # Shown again with nothing new, a page is not drawn again
            count = render.call_count
            window.tabs.setCurrentIndex(TAB_KEYS.index(BUILD_TAB))
            self.assertEqual(render.call_count, count)

    def _replay(self, win, replayed):
        """A Settings replay as the engine's queued signals bring it."""
        win._restart_pending = True
        win._on_monitoring_restarting()
        for entry in replayed:
            win._on_fight_completed(entry)
        win._on_monitoring_started(str(self.root / "Encounter.log"))

    def test_a_settings_replay_puts_the_window_on_the_replayed_fight(self):
        """The window's fight read again, with the same key and the same
        player under its unit id: the window goes on to the new entry, at
        its tab (MainWindow._rebind_player_window)."""
        from gui.player_window import DAMAGE_TAB
        win = self._window(fights()[0])
        window = self._click(win, "esolog:damage/1")
        replayed = fights()[0]
        self._replay(win, [replayed])
        self.assertIs(window.entry, replayed)
        self.assertEqual(window.current_tab(), DAMAGE_TAB)
        self.assertFalse(window.replayed_label.isVisibleTo(window))
        self.assertTrue(window.show_in_list.isEnabled())

    def test_a_replay_without_the_fight_keeps_it_and_says_so(self):
        from gui.player_window import REPLAYED_NOTE
        entry = fights()[0]
        win = self._window(entry)
        window = self._click(win, "esolog:build/1")
        other = fights()[0]
        other.timestamp = "2026-01-01 00:00:00"
        self._replay(win, [other])
        self.assertIs(window.entry, entry)
        self.assertTrue(window.replayed_label.isVisibleTo(window))
        self.assertEqual(window.replayed_label.text(), REPLAYED_NOTE)
        self.assertFalse(window.show_in_list.isEnabled())
        # A link opens a listed fight again, without the note
        self._click(win, "esolog:build/1")
        self.assertFalse(window.replayed_label.isVisibleTo(window))

    def test_a_pen_crit_save_redraws_the_pages(self):
        """Settings saved with new pen/crit options redraw the pane and the
        player window's page at once (decision 10), where they waited for
        the next build window."""
        from gui.player_window import PEN_CRIT_TAB
        win = self._window(fights()[0], show=True)
        window = self._click(win, "esolog:pencrit/1")
        before = window.view(PEN_CRIT_TAB).toPlainText()
        pane = win.fight_view.toPlainText()

        class Settings:
            Accepted = 1

            def __init__(self, config, *_args, **_kwargs):
                self.config = config

            def exec(self):
                return self.Accepted

            def apply_to_config(self):
                self.config.set("pen_crit", {"cp_piercing": False, "cp_fighting_finesse": False,
                                             "crit_cap": 125, "armour_cap": 18200})

            def deleteLater(self):
                pass
        with mock.patch("gui.main_window.SettingsDialog", Settings):
            win._open_settings()
        self.assertNotEqual(window.view(PEN_CRIT_TAB).toPlainText(), before)
        self.assertIsNotNone(pane)


class TestSizeAndTeardown(PlayerWindowTestCase):

    def test_the_size_its_least_width_and_its_place_saved(self):
        """900x840, no more than nine tenths of the screen; never narrower
        than its tab bar, at 100% and 200% text; its geometry saved with
        the main window's and put back at the next start."""
        from gui import text_size
        win = self._window(fights()[0])
        window = self._click(win, "esolog:build/1")
        area = window.screen().availableGeometry()
        self.assertLessEqual(window.width(), max(int(area.width() * 0.9), window.minimumWidth()))
        self.assertLessEqual(window.height(), int(area.height() * 0.9))
        for pct in (100, 200):
            win.set_text_size(pct)
            _app.processEvents()
            margins = window.layout().contentsMargins()
            needed = window.tabs.tabBar().sizeHint().width() + margins.left() + margins.right()
            self.assertGreaterEqual(window.minimumWidth(), min(needed, int(area.width() * 0.9)), pct)
        text_size.apply(100)
        window.resize(700, 600)
        window.move(40, 50)
        win._save_window_layout()
        saved = win.config.get("window.player_geometry")
        self.assertTrue(saved)
        again = self._window(fights()[0])
        reopened = self._click(again, "esolog:build/1")
        self.assertEqual(reopened.size().width(), window.size().width())

    def test_a_window_alone_is_freed_when_deleted(self):
        """The window holds no reference to the main window nor a lambda on
        a child: deleted, it is freed at once, with no collector run
        (conftest keeps it off)."""
        from PySide6.QtCore import QCoreApplication, QEvent

        from gui.player_window import BUILD_TAB, PlayerWindow
        window = PlayerWindow()
        window.open(fights()[0], "1", BUILD_TAB, dark=False)
        freed = weakref.ref(window)
        window.deleteLater()
        del window
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertIsNone(freed())


class TestAccessibleNames(PlayerWindowTestCase):

    def test_the_pages_are_named_and_begin_with_the_fight(self):
        from gui.player_window import BUILD_TAB, TABS, fight_line
        entry = fights()[0]
        win = self._window(entry)
        window = self._click(win, "esolog:build/1")
        names = [window.view(key).accessibleName() for key, _label, _title in TABS]
        self.assertEqual(names, ["Build", "Damage done", "Pen and crit", "Resources",
                                 "Damage taken", "Healing received", "Death recap"])
        self.assertEqual(window.picker.accessibleDescription(), fight_line(entry))
        self.assertTrue(window.view(BUILD_TAB).accessibleDescription().startswith(
            fight_line(entry) + "\n"))
        self.assertEqual((window.previous_player.accessibleName(),
                          window.next_player.accessibleName()),
                         ("Previous player", "Next player"))


if __name__ == "__main__":
    unittest.main()
