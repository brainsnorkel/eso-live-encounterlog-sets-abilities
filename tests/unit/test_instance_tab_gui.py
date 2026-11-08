#!/usr/bin/env python3
"""The Instance tab (issue #196, PR 7), offscreen: a click on a header, run
or result row of the fight list opens the tab on that row's instance, the
current row staying a fight; a drag or another button opens nothing; the
rows' hand, hover line and description; the pull and player links, and
one whose fight has left the list; Copy this instance; the banner links on
the instance's result with another fight on screen; the page kept in place
as pulls come in and fights change, and drawn anew for another instance;
the search and Hide names on the page."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_gui import HAVE_QT, _ensure_app
from tests.unit.test_pull_outcome_gui import _entry, _pull

_app = None

RESULT = {'trial_id': 13, 'name': "Kyne's Aegis", 'is_vet': True, 'duration_ms': 1351407,
          'score': 153117, 'vitality': 30, 'vitality_max': 36}

# The rows of _session's list
HEADER, YANDIR, WIPE, WIPE_2, KILL, RUN, RESULT_ROW, OTHER_HEADER, OTHER = range(9)


def _session():
    """Two instances: Kyne's Aegis, Yandir killed and then Lord Falgravn
    wiped on twice and killed, which completes the trial; and a fight in
    Sunspire. A third player was in Yandir's fight alone."""
    yandir = _entry("Yandir the Butcher", _pull("kill", 0.0, "Yandir the Butcher", 0.0, 80.0))
    yandir.players.append(dict(yandir.players[1], name='@late', unit_id='3', role='T'))
    yandir.player_names.append({'name': '@late', 'character': 'Late', 'is_local': False})
    wipes = [_entry("Lord Falgravn", _pull("wipe", health, start_s=200.0 + i * 200,
                                           end_s=300.0 + i * 200))
             for i, health in enumerate((84.0, 62.0))]
    kill = _entry("Lord Falgravn", _pull("kill", 0.0, start_s=700.0, end_s=880.0))
    kill.trial_result = dict(RESULT)
    other = _entry("Sunspire Guard")
    other.zone_name = "Sunspire"
    other.zone_id = "1121"
    return [yandir, *wipes, kill, other]


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class InstanceTabTestCase(unittest.TestCase):

    def setUp(self):
        global _app
        _app = _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.windows = []

    def tearDown(self):
        from gui import text_size
        for win in self.windows:
            if win._player_window is not None:
                win._player_window.close()
            win.close()
        text_size.apply(text_size.DEFAULT_PCT)  # the application font is shared
        self.tmp.cleanup()

    def _window(self, *entries, page_height=None):
        """A main window shown, its worker stopped, with *entries* come in
        live: each is selected. *page_height* caps the Instance page's
        height, so a short page scrolls: the Linux runner does not shrink a
        shown window."""
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
        if page_height is not None:
            win.instance_view.setMaximumHeight(page_height)
        win.show()
        _app.processEvents()
        for entry in entries:
            win._on_fight_completed(entry)
        self._settle()
        return win

    def _settle(self):
        """The layout requests and the page's steps after layout, run."""
        from PySide6.QtCore import QCoreApplication, QEvent
        for _ in range(4):
            QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
            _app.processEvents()

    def _scroll_to_end(self, bar):
        """The reader scrolls the page to its end with the bar's own action,
        which ends a place held for a redraw, as the wheel does."""
        from PySide6.QtWidgets import QAbstractSlider
        bar.triggerAction(QAbstractSlider.SliderToMaximum)

    def _rect(self, win, row):
        return win.history_list.visualItemRect(win.history_list.item(row))

    def _click(self, win, row, button=None):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        QTest.mouseClick(win.history_list.viewport(), button or Qt.LeftButton, Qt.NoModifier,
                         self._rect(win, row).center())
        self._settle()

    def _move(self, win, row, buttons=None):
        """The pointer moved over *row*, sent to the list's viewport as the
        platform sends it: QTest.mouseMove sends no event offscreen."""
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QApplication
        viewport = win.history_list.viewport()
        pos = self._rect(win, row).center()
        held = buttons or Qt.NoButton
        QApplication.sendEvent(viewport, QMouseEvent(QEvent.MouseMove, pos, viewport.mapToGlobal(pos),
                                                     Qt.NoButton, held, Qt.NoModifier))

    def _links(self, win):
        """The hrefs of the Instance page's links, in page order."""
        return [href for href, _start, _end in win.instance_view._links()]

    def _activate(self, win, href):
        """A link on the Instance page clicked."""
        from PySide6.QtCore import QUrl
        win.instance_view.anchorClicked.emit(QUrl(href))
        self._settle()

    def _anchors(self, view):
        """The names of the page's <a name> anchors."""
        names = []
        block = view.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                names.extend(it.fragment().charFormat().anchorNames())
                it += 1
            block = block.next()
        return names


class TestRowsOpenTheInstance(InstanceTabTestCase):

    def test_a_header_row_opens_its_instance_at_the_top(self):
        """From another instance's fight, the block's last fight is
        selected and the tab opens at its top; with a fight of the block on
        screen, that fight stays. The current row is a fight both times."""
        fights = _session()
        win = self._window(*fights, page_height=150)
        lst = win.history_list
        self.assertIs(lst.current_entry(), fights[-1])
        self._click(win, HEADER)
        self.assertIs(win.fight_tabs.currentWidget(), win.instance_view)
        self.assertIs(lst.current_entry(), fights[3])
        self.assertEqual(lst.currentRow(), KILL)
        self.assertIn("Kyne's Aegis", win.instance_view.toPlainText())
        bar = win.instance_view.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)  # the page scrolls, so the top is a place
        self._scroll_to_end(bar)
        lst.select_entry(fights[1])
        self._settle()
        self.assertEqual(bar.value(), bar.maximum())  # the same instance, kept in place
        self._click(win, HEADER)
        self.assertIs(lst.current_entry(), fights[1])
        self.assertEqual(bar.value(), 0)

    def test_a_run_row_opens_at_its_boss(self):
        """A run row selects the run's last pull from outside the run, keeps
        a pull of the run on screen, and opens the tab at the boss's
        anchor, which the page has."""
        from gui.instance_render import run_anchor
        fights = _session()
        win = self._window(*fights)
        lst = win.history_list
        self._click(win, RUN)
        self.assertIs(lst.current_entry(), fights[3])
        self.assertIs(win.fight_tabs.currentWidget(), win.instance_view)
        # Lord Falgravn's is the instance's second run, after Yandir's
        self.assertEqual(win.instance_view._kept_anchor, run_anchor(2))
        self.assertIn(run_anchor(2), self._anchors(win.instance_view))
        lst.select_entry(fights[1])
        self._click(win, RUN)
        self.assertIs(lst.current_entry(), fights[1])
        lst.select_entry(fights[0])
        self._click(win, RUN)
        self.assertIs(lst.current_entry(), fights[3])
        self.assertEqual(lst.currentRow(), KILL)

    def test_a_result_row_opens_its_instance(self):
        fights = _session()
        win = self._window(*fights)
        self._click(win, RESULT_ROW)
        self.assertIs(win.history_list.current_entry(), fights[3])
        self.assertIs(win.fight_tabs.currentWidget(), win.instance_view)
        # Another instance's header opens that one
        self._click(win, OTHER_HEADER)
        self.assertIs(win.history_list.current_entry(), fights[-1])
        self.assertIn("Sunspire", win.instance_view.toPlainText())
        self.assertNotIn("Falgravn", win.instance_view.toPlainText())

    def test_a_drag_or_another_button_opens_nothing(self):
        """A right or middle click on a header, a drag from one inert row to
        another, and a press on a fight released on a header open nothing;
        a left click still does (the list tells the click itself: Qt does
        not promise itemClicked on an inert row)."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        win = self._window(*_session())
        lst = win.history_list
        opened = []
        lst.instance_requested.connect(opened.append)
        self._click(win, HEADER, Qt.RightButton)
        self._click(win, HEADER, Qt.MiddleButton)
        viewport = lst.viewport()
        for start, end in ((HEADER, OTHER_HEADER), (OTHER, OTHER_HEADER)):
            QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, self._rect(win, start).center())
            self._move(win, end, Qt.LeftButton)
            QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, self._rect(win, end).center())
            self._settle()
        self.assertEqual(opened, [])
        self.assertEqual(win.fight_tabs.currentIndex(), 0)
        self.assertIsNotNone(lst.current_entry())
        self._click(win, HEADER)
        self.assertEqual(opened, [HEADER])

    def test_a_double_click_opens_the_instance_once(self):
        """Qt makes a double-click's second press of it on an inert row:
        it opens nothing more (the review of PR #208)."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        win = self._window(*_session())
        opened = []
        win.history_list.instance_requested.connect(opened.append)
        viewport, pos = win.history_list.viewport(), self._rect(win, HEADER).center()
        # What the platform sends: a click, then the double-click and its
        # release (QTest.mouseDClick sends the double-click alone)
        QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, pos)
        QTest.mouseDClick(viewport, Qt.LeftButton, Qt.NoModifier, pos)
        QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, pos)
        self._settle()
        self.assertEqual(opened, [HEADER])

    def test_a_double_click_on_a_header_selects_nothing_under_it(self):
        """The first click selects the instance's last fight and scrolls the
        list; the double-click's second press, on whatever fight came under
        the pointer, selected it (the fresh review of PR #208)."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from tests.unit.test_pull_outcome_gui import _entry
        trash = [_entry(f"Half-Giant Raider {i}") for i in range(30)]
        other = _entry("Sunspire Guard")
        other.zone_name, other.zone_id = "Sunspire", "1121"
        win = self._window(*trash, other)
        lst = win.history_list
        lst.setMaximumHeight(6 * self._rect(win, 0).height() + 2 * lst.frameWidth())
        self._settle()
        lst.scrollToTop()
        self._settle()
        opened = []
        lst.instance_requested.connect(opened.append)
        viewport, pos = lst.viewport(), self._rect(win, HEADER).center()
        QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, pos)
        self._settle()
        self.assertIs(lst.current_entry(), trash[-1])
        self.assertGreater(lst.verticalScrollBar().value(), 0)  # a fight is under the pointer
        self.assertIsNot(lst.itemAt(pos).data(Qt.UserRole), None)
        QTest.mouseDClick(viewport, Qt.LeftButton, Qt.NoModifier, pos)
        QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, pos)
        self._settle()
        self.assertIs(lst.current_entry(), trash[-1])
        self.assertEqual(opened, [HEADER])

    def test_filling_the_list_checks_the_hand_once(self):
        """Rows added in a batch check the hand once, after the batch: once
        per row, each look-up laid the whole list out again, and a 915-fight
        review took 15.7 s to list against 0.14 (the fresh review of PR
        #208)."""
        from gui.fight_list import FightList
        lst = FightList()
        self.addCleanup(lst.deleteLater)
        lst.resize(300, 200)
        lst.show()
        checks = []
        lst._set_hand = checks.append
        lst.set_fights(_session() * 20)
        _app.processEvents()
        self.assertEqual(len(checks), 1)

    def test_the_hand_follows_rows_that_move_under_the_pointer(self):
        """The list scrolled under a pointer that did not move: the hand
        goes with the inert row (the review of PR #208)."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QCursor

        from gui.fight_list import FightList
        lst = FightList()
        self.addCleanup(lst.deleteLater)
        lst.set_fights(_session())
        row_height = lst.visualItemRect(lst.item(0)).height()
        lst.resize(300, 3 * row_height + 2 * lst.frameWidth())
        lst.show()
        _app.processEvents()
        bar = lst.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        QCursor.setPos(lst.viewport().mapToGlobal(lst.visualItemRect(lst.item(HEADER)).center()))
        lst._recheck_hand()
        self.assertEqual(lst.viewport().cursor().shape(), Qt.PointingHandCursor)
        bar.setValue(1)  # Yandir's row under the pointer now
        _app.processEvents()
        self.assertNotEqual(lst.viewport().cursor().shape(), Qt.PointingHandCursor)

    def test_the_rows_show_a_click_opens_the_instance(self):
        """The pointing hand over a header, run or result row, none over a
        fight; the hover line on each, after a run row's own text; and the
        description a screen reader hears, after a run row's own."""
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QHelpEvent
        from PySide6.QtWidgets import QApplication

        from gui.fight_list import (
            INSTANCE_CUE,
            INSTANCE_DESCRIPTION,
            RUN_ROLE,
            run_description,
            run_tooltip,
        )
        win = self._window(*_session())
        lst = win.history_list
        viewport = lst.viewport()

        def hover(row):
            pos = self._rect(win, row).center()
            QApplication.sendEvent(viewport, QHelpEvent(QEvent.ToolTip, pos, viewport.mapToGlobal(pos)))
            return lst.current_tooltip

        for row in (HEADER, RUN, RESULT_ROW, OTHER_HEADER, YANDIR, HEADER):
            self._move(win, row)
            hand = viewport.cursor().shape() == Qt.PointingHandCursor
            self.assertEqual(hand, row != YANDIR, row)
        for row in (HEADER, RESULT_ROW, OTHER_HEADER):
            self.assertEqual(hover(row), INSTANCE_CUE)
            self.assertEqual(lst.item(row).data(Qt.AccessibleDescriptionRole), INSTANCE_DESCRIPTION)
        run = lst.item(RUN).data(RUN_ROLE)
        self.assertEqual(hover(RUN), f"{run_tooltip(run)}\n{INSTANCE_CUE}")
        self.assertEqual(lst.item(RUN).data(Qt.AccessibleDescriptionRole),
                         f"{run_description(run)}. {INSTANCE_DESCRIPTION}")
        self.assertEqual(hover(YANDIR), "")

    def test_alt_i_opens_the_instance_of_the_fight_on_screen(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        fights = _session()
        win = self._window(*fights)
        win.history_list.select_entry(fights[1])
        win.activateWindow()
        QTest.qWaitForWindowActive(win, 2000)
        QTest.keyClick(win, Qt.Key_I, Qt.AltModifier)
        self._settle()
        self.assertIs(win.fight_tabs.currentWidget(), win.instance_view)
        self.assertIs(win.history_list.current_entry(), fights[1])
        self.assertIn("Kyne's Aegis", win.instance_view.toPlainText())


class TestLinks(InstanceTabTestCase):

    def test_a_pull_opens_that_fight_on_the_fight_tab(self):
        """Lord Falgravn's three pulls are links to their fights by their
        place in the list; Yandir's one pull has none. A pull clicked is
        selected, on the Fight tab."""
        from gui.instance_render import fight_from_href
        fights = _session()
        win = self._window(*fights)
        self._click(win, HEADER)
        pulls = [fight_from_href(href) for href in self._links(win)]
        self.assertEqual(sorted({index for index in pulls if index is not None}), [1, 2, 3])
        href = next(href for href in self._links(win) if fight_from_href(href) == 1)
        self._activate(win, href)
        self.assertEqual(win.fight_tabs.currentIndex(), 0)
        self.assertIs(win.history_list.current_entry(), fights[1])

    def test_a_name_opens_the_player_window_on_build(self):
        """A player in the fight on screen opens on it; one who was not,
        on their last fight of the instance."""
        from gui.instance_render import player_from_href
        from gui.player_window import BUILD_TAB
        fights = _session()
        win = self._window(*fights)
        self._click(win, HEADER)
        players = {unit: (index, href) for href in self._links(win)
                   for index, unit in [player_from_href(href) or (None, None)] if unit}
        self.assertEqual(players['2'][0], 3)  # @other, in the fight on screen
        self.assertEqual(players['3'][0], 0)  # @late, in Yandir's alone
        self._activate(win, players['3'][1])
        window = win._player_window
        self.assertIsNotNone(window)
        self.assertIs(window.entry, fights[0])
        self.assertEqual(window.unit_id, '3')
        self.assertEqual(window.current_tab(), BUILD_TAB)
        self.assertIs(win.history_list.current_entry(), fights[3])  # the list stays

    def test_a_player_who_only_died_opens_on_deaths(self):
        """A player who died in a pull with no row of their own (the pane's
        Also died) opens on the Deaths tab of that fight, where Build would
        be empty (the review of PR #208)."""
        from gui.instance_render import player_from_href
        from gui.player_window import DEATHS_TAB
        from tests.unit.test_pull_outcome_gui import _recap
        fights = _session()
        fights[2].death_recaps = [_recap('9', '@ghost', 20_000)]
        fights[2].deaths = 1
        win = self._window(*fights)
        self._click(win, HEADER)
        href = next(href for href in self._links(win)
                    if (player_from_href(href) or (None, None))[1] == '9')
        self.assertEqual(player_from_href(href)[0], 2)
        self._activate(win, href)
        window = win._player_window
        self.assertIs(window.entry, fights[2])
        self.assertEqual(window.unit_id, '9')
        self.assertEqual(window.current_tab(), DEATHS_TAB)

    def test_a_link_whose_fight_left_the_list_says_so(self):
        from gui.instance_render import fight_from_href
        win = self._window(*_session())
        self._click(win, HEADER)
        href = next(href for href in self._links(win) if fight_from_href(href) is not None)
        win.history_list.clear()
        self._activate(win, href)
        self.assertEqual(win.statusBar().currentMessage(), "That fight is not in the list now")
        self.assertIsNone(win.history_list.current_entry())

    def test_copy_this_instance_copies_its_recap(self):
        """The instance as Copy session writes it, names through Hide
        names: a player dead on a wipe is named in its Most time dead."""
        from PySide6.QtGui import QGuiApplication

        from gui.instance_render import INSTANCE_COPY_HREF
        from gui.name_mask import NameMask
        from session_recap import recap_text
        from tests.unit.test_pull_outcome_gui import _recap
        fights = _session()
        fights[1].death_recaps = [_recap('2', '@other', 30_000)]
        fights[1].deaths = 1
        fights[1].time_dead = {'2': 40_000}
        block = fights[:4]
        win = self._window(*fights)
        self._click(win, HEADER)
        self.assertIn(INSTANCE_COPY_HREF, self._links(win))
        self._activate(win, INSTANCE_COPY_HREF)
        self.assertEqual(QGuiApplication.clipboard().text(),
                         recap_text(block, NameMask.for_entries(block, False)))
        self.assertIn("@other", QGuiApplication.clipboard().text())
        self.assertTrue(win.statusBar().currentMessage().startswith(
            "Instance recap copied to clipboard, "))
        win.hide_names_action.setChecked(True)
        self._settle()
        self._activate(win, INSTANCE_COPY_HREF)
        text = QGuiApplication.clipboard().text()
        self.assertEqual(text, recap_text(block, NameMask.for_entries(block, True)))
        self.assertNotIn("@other", text)

    def test_the_banner_links_act_on_the_instances_result(self):
        """With another fight of the instance on screen, the page's banner
        links act on the fight that carries the result; the result strip's
        act on the fight on screen, which has none."""
        from PySide6.QtGui import QColor, QGuiApplication, QImage

        from gui.fight_render import BANNER_HREF
        png = self.root / "banner.png"
        image = QImage(8, 4, QImage.Format_RGB32)
        image.fill(QColor("#2e7d32"))
        image.save(str(png))
        fights = _session()
        fights[3].banner_path = png
        win = self._window(*fights)
        win.history_list.select_entry(fights[1])
        win.fight_tabs.setCurrentWidget(win.instance_view)
        self._settle()
        self.assertIn(f"{BANNER_HREF}copy", self._links(win))
        QGuiApplication.clipboard().clear()
        self._activate(win, f"{BANNER_HREF}copy")
        self.assertEqual(win.statusBar().currentMessage(), "Score banner copied")
        self.assertEqual(QGuiApplication.clipboard().image().size(), image.size())
        win._show_banner("copy")
        self.assertEqual(win.statusBar().currentMessage(), "The score banner file is gone")


class TestRedraws(InstanceTabTestCase):

    def test_live_pulls_keep_the_page_where_it_was(self):
        """A pull joining the instance on screen redraws the page in place,
        whether it is selected (following the live log) or another fight is
        on screen."""
        fights = _session()
        win = self._window(*fights[:2], page_height=150)
        win.fight_tabs.setCurrentWidget(win.instance_view)
        self._settle()
        bar = win.instance_view.verticalScrollBar()
        self._scroll_to_end(bar)
        kept = bar.value()
        self.assertGreater(kept, 0)  # the page scrolls, so its place is one to keep
        win._on_fight_completed(fights[2])  # followed: selected
        self._settle()
        self.assertIs(win.history_list.current_entry(), fights[2])
        self.assertIs(win._instance_block[-1], fights[2])
        self.assertEqual(bar.value(), kept)
        win.history_list.select_entry(fights[0])  # following stops
        self._settle()
        self.assertEqual(bar.value(), kept)
        win._on_fight_completed(fights[3])
        self._settle()
        self.assertIs(win.history_list.current_entry(), fights[0])
        self.assertIs(win._instance_block[-1], fights[3])
        self.assertEqual(bar.value(), kept)

    def test_a_fight_of_the_instance_changing_redraws_the_page(self):
        """Another fight of the instance updated in place (a late death)
        redraws the page while it is on screen, in place; while another tab
        is on screen it is drawn when the tab is shown again."""
        from tests.unit.test_pull_outcome_gui import _recap
        fights = _session()
        win = self._window(*fights[:4], page_height=150)
        win.history_list.select_entry(fights[1])
        win.fight_tabs.setCurrentWidget(win.instance_view)
        self._settle()
        bar = win.instance_view.verticalScrollBar()
        self._scroll_to_end(bar)
        kept = bar.value()
        self.assertGreater(kept, 0)
        before = win.instance_view.toPlainText()
        fights[3].death_recaps = [_recap('2', '@other', 30_000)]
        fights[3].deaths = 1
        win._on_fight_updated(fights[3])
        self._settle()
        self.assertNotEqual(win.instance_view.toPlainText(), before)
        self.assertEqual(bar.value(), kept)
        win.fight_tabs.setCurrentIndex(0)
        fights[2].death_recaps = [_recap('1', '@me', 20_000)]
        fights[2].deaths = 1
        win._on_fight_updated(fights[2])
        self.assertTrue(win._instance_dirty)
        changed = win.instance_view.toPlainText()
        win.fight_tabs.setCurrentWidget(win.instance_view)
        self._settle()
        self.assertNotEqual(win.instance_view.toPlainText(), changed)

    def test_another_instance_is_drawn_anew_at_the_top(self):
        fights = _session()
        win = self._window(*fights, page_height=150)
        self._click(win, HEADER)
        bar = win.instance_view.verticalScrollBar()
        self._scroll_to_end(bar)
        self.assertGreater(bar.value(), 0)
        win.history_list.select_entry(fights[-1])
        self._settle()
        self.assertIn("Sunspire", win.instance_view.toPlainText())
        self.assertEqual(bar.value(), 0)

    def test_the_search_and_hide_names_on_the_page(self):
        """The search works on the Instance page while it is on screen, and
        Hide names redraws it masked."""
        fights = _session()
        win = self._window(*fights)
        self._click(win, HEADER)
        win.search_field.setText("Falgravn")
        self.assertIs(win._search_view(), win.instance_view)
        self.assertTrue(win.instance_view.extraSelections())
        self.assertTrue(win.search_count.text())
        self.assertIn("@other", win.instance_view.toPlainText())
        win.hide_names_action.setChecked(True)
        self._settle()
        self.assertNotIn("@other", win.instance_view.toPlainText())
        self.assertIn("@me", win.instance_view.toPlainText())

    def test_no_fight_clears_the_page(self):
        win = self._window(*_session())
        self._click(win, HEADER)
        self.assertTrue(win.instance_view.toPlainText())
        win._show_replaying()
        self.assertEqual(win.instance_view.toPlainText(), "")
        self.assertEqual(win._instance_links, {})
        self.assertEqual(win.fight_tabs.currentIndex(), 0)


if __name__ == "__main__":
    unittest.main()
