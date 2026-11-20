#!/usr/bin/env python3
"""One player's actions on the Events tab (issue #214, gui.events_tab with
action_rows), offscreen: the Who picker, the actions' columns and rows,
Everyone as before, More's switches, the category boxes for one player,
Hide names, the columns no row fills, Enter, Ctrl+G, Show and the search
in actions, the choice carried to the next fight, and the player window's
button to the player's actions."""

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_events_tab_gui import EventsTestCase, _fight
from tests.unit.test_gui import HAVE_QT


def _with_casts():
    """A fresh entry of test_action_rows' fight: test_fight_events' fight
    with each player's build and casts. @first writes the log."""
    from tests.unit.test_action_rows import _fight_with_casts
    return _fight_with_casts()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestWho(EventsTestCase):

    def _pick(self, page, key):
        page.who_picker.setCurrentIndex(page.who_picker.findData(key))

    def test_who_lists_everyone_then_each_player_by_role(self):
        from gui.events_tab import EVERYONE
        from tests.unit.test_action_rows import _cast, _entry, _row
        page = self._page(_with_casts())
        items = [page.who_picker.itemText(n) for n in range(page.who_picker.count())]
        self.assertEqual(items, [EVERYONE, "D  @first", "D  @second", "D  @third"])
        self.assertEqual(page.who_picker.accessibleName(), "Who")
        self.assertIsNone(page.who)
        self.assertIs(page.focus_chain()[0], page.who_picker)
        # Tanks, then healers, then the damage dealers, each in the rows' order
        entry = _entry({key: [_cast(1000, "46356")] for key in ("1", "2", "3", "4")},
                       rows=[_row("1", role="D"), _row("2", role="T"), _row("3", role="H"),
                             _row("4", local=False, role="T"),
                             dict(_row("5", local=False), companion=True)])
        page.show_fight(entry)
        self.assertEqual([page.who_picker.itemData(n) for n in range(page.who_picker.count())],
                         [None, "2", "4", "3", "1"])
        # A fight whose casts were not kept lists everyone alone
        old = _with_casts()
        old.casts = None
        page.show_fight(old)
        self.assertEqual(page.who_picker.count(), 1)

    def test_a_player_picked_shows_their_actions(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont

        from gui.events_tab import ACTION_COLUMNS, ACTIONS_TABLE_NAME
        page = self._page(_with_casts())
        self._pick(page, "1")
        self.assertEqual(page.who, "1")
        model = page.model
        self.assertEqual([model.headerData(c, Qt.Horizontal) for c in range(model.columnCount())],
                         list(ACTION_COLUMNS))
        self.assertEqual(page.summary.text(), "@first · D · Warden · 6 casts · no deaths")
        self.assertEqual(page.table.accessibleName(), ACTIONS_TABLE_NAME)
        rows = page.shown_rows()
        self.assertEqual(page.count_label.text(), f"{len(rows)} of {len(rows)} shown")
        pulse = next(n for n, row in enumerate(rows) if row.ability == "Force Pulse")
        self.assertEqual(self._cells(page, pulse),
                         ["0:00.4", "F2", "LA", "Force Pulse", "Lokkestiiz", "", "", ""])
        heavy = next(n for n, row in enumerate(rows) if row.what == "Heavy attack")
        self.assertEqual(self._cells(page, heavy)[5], "1.6 s")
        blockade = next(n for n, row in enumerate(rows) if row.ability == "Blockade of Frost")
        self.assertEqual(self._cells(page, blockade)[1:7], ["⇄B1", "", "Blockade of Frost", "",
                                                             "", "3.2 s"])
        self.assertIn("weapon swap", model.index(blockade, 1).data(Qt.ToolTipRole))
        self.assertEqual(model.index(blockade, 1).data(Qt.AccessibleTextRole),
                         "after a weapon swap, B1")
        self.assertEqual(model.index(pulse, 2).data(Qt.AccessibleTextRole), "after a light attack")
        # The events that touched them, and the context drawn muted
        whats = [row.action for row in rows]
        self.assertIn("Boss cast: Storm Fury", whats)
        self.assertIn("Hit: Toppling Blow", whats)
        self.assertIn("No cast for 7.4 s", whats)
        context = next(n for n, row in enumerate(rows) if row.muted)
        self.assertTrue(QFont(model.index(context, 3).data(Qt.FontRole)).italic())
        self.assertIsNotNone(model.index(context, 3).data(Qt.ForegroundRole))
        self.assertIsNone(model.index(pulse, 3).data(Qt.ForegroundRole))
        # Phases is a context row for one player: its box is off, More holds
        # the player's switches, Context on
        self.assertFalse(page.category_boxes["phases"].isEnabled())
        self.assertFalse(any(action.isEnabled() for action in page.more_actions.values()))
        self.assertTrue(all(action.isEnabled() for action in page.action_switches.values()))
        self.assertEqual(page.more_button.text(), "More (1)")

    def test_everyone_again_is_as_before(self):
        from PySide6.QtCore import Qt

        from gui.events_tab import COLUMNS, TABLE_NAME
        page = self._page(_with_casts())
        before = [self._cells(page, n) for n in range(page.model.rowCount())]
        summary, selected = page.summary.text(), page.selected()
        self._pick(page, "3")
        self.assertNotEqual(page.summary.text(), summary)
        page.who_picker.setCurrentIndex(0)
        self.assertIsNone(page.who)
        self.assertEqual([self._cells(page, n) for n in range(page.model.rowCount())], before)
        self.assertEqual([page.model.headerData(c, Qt.Horizontal) for c in range(5)],
                         list(COLUMNS))
        self.assertEqual((page.summary.text(), page.table.accessibleName()), (summary, TABLE_NAME))
        self.assertEqual(page.selected(), selected)
        self.assertTrue(page.category_boxes["phases"].isEnabled())
        self.assertEqual(page.hidden_columns(), set())
        self.assertFalse(any(page.table.isColumnHidden(c) for c in range(5)))

    def test_mores_switches(self):
        from gui.events_tab import A_LA_COL, CONTEXT_ROWS, LIGHT_ROWS, SWAP_ROWS
        page = self._page(_with_casts())
        self._pick(page, "1")
        page.action_switches[LIGHT_ROWS].setChecked(True)
        rows = page.shown_rows()
        self.assertIn("Light Attack (Lightning)", [row.ability for row in rows])
        self.assertFalse(any(row.la for row in rows))
        self.assertTrue(page.table.isColumnHidden(A_LA_COL))  # no mark left
        self.assertEqual(page.more_button.text(), "More (2)")
        page.action_switches[SWAP_ROWS].setChecked(True)
        self.assertIn("Swap Weapons", [row.ability for row in page.shown_rows()])
        self.assertFalse(any(row.bar.startswith("⇄") for row in page.shown_rows()))
        page.action_switches[CONTEXT_ROWS].setChecked(False)
        self.assertFalse(any(row.muted for row in page.shown_rows()))
        page.action_switches[LIGHT_ROWS].setChecked(False)
        rows = page.shown_rows()
        self.assertNotIn("Light Attack (Lightning)", [row.ability for row in rows])
        self.assertFalse(page.table.isColumnHidden(A_LA_COL))
        # Everyone: the switches do not apply
        page.who_picker.setCurrentIndex(0)
        self.assertFalse(any(action.isEnabled() for action in page.action_switches.values()))
        self.assertTrue(all(action.isEnabled() for action in page.more_actions.values()))
        self.assertEqual(page.more_button.text(), "More")

    def test_the_category_boxes_for_one_player(self):
        page = self._page(_with_casts())
        self._pick(page, "3")
        categories = {row.category for row in page.shown_rows()}
        self.assertTrue({"deaths", "taunts", "casts", "context"} <= categories)
        page.category_boxes["deaths"].setChecked(False)
        page.category_boxes["taunts"].setChecked(False)
        self.assertEqual({row.category for row in page.shown_rows()}, {"casts", "context"})
        self._pick(page, "1")
        page.category_boxes["boss"].setChecked(False)
        page.category_boxes["hits"].setChecked(False)
        self.assertEqual({row.category for row in page.shown_rows()}, {"casts", "context", "idle"})

    def test_hide_names(self):
        from PySide6.QtCore import Qt
        page = self._page(_with_casts(), hide=True)
        items = [page.who_picker.itemText(n) for n in range(page.who_picker.count())]
        self.assertEqual(items[1:], ["D  @first", "D  @▒▒▒▒▒▒", "D  @▒▒▒▒▒"])
        self._pick(page, "2")
        self.assertTrue(page.summary.text().startswith("@▒▒▒▒▒▒ · D"))
        cast = next(n for n, row in enumerate(page.shown_rows()) if row.category == "casts")
        self.assertEqual(self._cells(page, cast)[4], "@first")  # the logging player kept
        self._pick(page, "1")
        boss = next(n for n, row in enumerate(page.shown_rows()) if row.category == "boss")
        self.assertEqual(self._cells(page, boss)[7], "from Lokkestiiz · interrupted by @▒▒▒▒▒▒")
        self.assertEqual(page.model.index(boss, 7).data(Qt.AccessibleTextRole),
                         "from Lokkestiiz · interrupted by hidden name")
        self._select(page, boss)
        self.assertNotIn("@second", page.full_row.text())
        self.assertEqual(page.set_search("second"), 0)
        self.assertEqual(page.set_search("Storm"), 1)

    def test_the_columns_no_row_fills_are_hidden(self):
        from gui.events_tab import (
            A_BAR_COL,
            A_GAP_COL,
            A_LA_COL,
            A_LENGTH_COL,
            A_TARGET_COL,
        )
        page = self._page(_with_casts())
        self._pick(page, "2")
        self.assertEqual(page.hidden_columns(), {A_LA_COL, A_LENGTH_COL, A_GAP_COL})
        for column in (A_LA_COL, A_LENGTH_COL, A_GAP_COL):
            self.assertTrue(page.table.isColumnHidden(column))
        for column in (A_BAR_COL, A_TARGET_COL):
            self.assertFalse(page.table.isColumnHidden(column))
        self._pick(page, "1")
        self.assertEqual(page.hidden_columns(), set())

    def test_enter_ctrl_g_and_the_line_in_one_players_actions(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        page = self._page(_with_casts())
        recaps, marks = [], []
        page.recap_requested.connect(lambda unit, number: recaps.append((unit, number)))
        page.graph_requested.connect(lambda ms, label: marks.append((ms, label)))
        self.assertTrue(page.show_player("3"))
        self.assertEqual((page.who, page.selected().action), ("3", "Died: Toppling Blow"))
        self.assertTrue(page.full_row.text().startswith("0:10.0 · Died: Toppling Blow · from "
                                                        "Lokkestiiz"))
        page.table.setFocus()
        QTest.keyClick(page.table, Qt.Key_Return)
        QTest.keyClick(page.table, Qt.Key_G, Qt.ControlModifier)
        self.assertEqual(recaps, [("3", 1)])
        self.assertEqual(marks, [(10000, "Died · Toppling Blow")])
        self.assertFalse(page.show_player("9"))
        page.show_player("1")
        pulse = next(n for n, row in enumerate(page.shown_rows()) if row.ability == "Force Pulse")
        self._select(page, pulse)
        self.assertTrue(page.full_row.text().startswith(
            "0:00.4 · F2 · after a light attack · Force Pulse · at Lokkestiiz"))
        QTest.keyClick(page.table, Qt.Key_G, Qt.ControlModifier)
        self.assertEqual(marks[-1], (400, "Cast · Force Pulse"))

    def test_show_around_and_the_search_in_one_players_actions(self):
        page = self._page(_with_casts())
        page.show_player("1")
        page.show_around(3600)
        self.assertEqual(page.who, "1")
        self.assertTrue(all(-6400 <= row.t <= 13600 for row in page.shown_rows()))
        self.assertIn("around 0:03.6", page.count_label.text())
        self.assertEqual(page.selected().t, 3600)
        self.assertEqual(page.set_search("Crystal"), 1)
        page.set_search("")
        # A death's link for another player: everyone's rows, that death
        page.show_around(10000, unit_key="3")
        self.assertIsNone(page.who)
        self.assertEqual((page.selected().what, page.selected().t), ("Died", 10000))

    def test_who_changed_keeps_the_moment(self):
        """Picking a player goes on from the moment of the row selected:
        everyone opens at the first death (10 s), and @first, who did not
        die, opens at their first row from 10 s on, not at their first."""
        page = self._page(_with_casts())
        self.assertEqual(page.selected().t, 10000)
        self._pick(page, "1")
        later = [row.t for row in page.shown_rows() if row.t >= 10000]
        self.assertTrue(later)
        self.assertEqual(page.selected().t, later[0])

    def test_the_line_labels_the_seconds(self):
        """On the line under the table a cast's two seconds say which is
        which: how long it lasted, and how long after the skill before."""
        page = self._page(_with_casts())
        page.show_player("1")
        rows = page.shown_rows()
        self._select(page, next(n for n, row in enumerate(rows) if row.what == "Heavy attack"))
        self.assertIn("lasted 1.6 s", page.full_row.text())
        self._select(page, next(n for n, row in enumerate(rows)
                                if row.ability == "Blockade of Frost"))
        self.assertIn("3.2 s after the skill before", page.full_row.text())

    def test_a_cast_at_a_hidden_player(self):
        """A cast's target is a name like any other: hidden in its cell, on
        the line and in the search, read as 'hidden name'."""
        from action_rows import CASTS, action_rows
        from gui.events_tab import A_TARGET_COL, masked_action
        from gui.name_mask import NameMask
        from tests.unit.test_action_rows import _cast, _entry
        names = NameMask.for_entry(_with_casts(), True)
        entry = _entry({"1": [_cast(1000, "46356", ("@second", "2"))]}, duration_s=2.0)
        row, = [row for row in action_rows(entry, "1") if row.category == CASTS]
        shown = masked_action(row, names)
        self.assertEqual(shown.cells[A_TARGET_COL], "@▒▒▒▒▒▒")
        self.assertEqual(shown.spoken[A_TARGET_COL], "hidden name")
        self.assertNotIn("second", shown.line)
        self.assertNotIn("second", shown.searched)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestInTheWindow(EventsTestCase):

    def test_the_choice_carries_to_the_next_fight(self):
        """The player picked stays as fights come in while they are in
        them, by their handle (gui.dps_graph.legend_key); a fight without
        them shows everyone, and the next with them picks them again."""
        win = self._window(_with_casts())
        win.fight_tabs.setCurrentWidget(win.events_view)
        page = win.events_view
        page.who_picker.setCurrentIndex(page.who_picker.findData("2"))
        second = _with_casts()
        win._on_fight_completed(second)
        self.assertIs(page.entry, second)
        self.assertEqual(page.who, "2")
        self.assertTrue(page.summary.text().startswith("@second"))
        win._on_fight_completed(_fight())
        self.assertIsNone(page.who)
        win._on_fight_completed(_with_casts())
        self.assertEqual(page.who, "2")
        # Hide names redraws the same fight in place, the player kept
        win.hide_names_action.setChecked(True)
        self.assertEqual(page.who, "2")
        self.assertTrue(page.summary.text().startswith("@▒▒▒▒▒▒"))

    def test_the_player_windows_button_shows_their_actions(self):
        from gui.player_window import (
            ACTIONS_LABEL,
            BUILD_TAB,
            DEATHS_TAB,
            NO_ACTIONS_TIP,
        )
        first, second = _with_casts(), _with_casts()
        win = self._window(first, second)
        self.assertIs(win.history_list.current_entry(), second)
        win._open_player("2", BUILD_TAB, entry=first)
        window = win._player_window
        button = window.actions_button
        self.assertEqual(button.text(), ACTIONS_LABEL)
        self.assertTrue(button.isEnabled())
        button.click()
        self.assertIs(win.history_list.current_entry(), first)
        self.assertIs(win.fight_tabs.currentWidget(), win.events_view)
        self.assertIs(win.events_view.entry, first)
        self.assertEqual(win.events_view.who, "2")
        # The picker on another player: the button follows
        window.picker.setCurrentIndex(window.picker.findData("3"))
        button.click()
        self.assertEqual(win.events_view.who, "3")
        # A player the table does not list: nothing kept to show
        old = _fight()
        win._on_fight_completed(old)
        win._open_player("3", DEATHS_TAB, entry=old, death=1)
        self.assertFalse(button.isEnabled())
        self.assertEqual(button.toolTip(), NO_ACTIONS_TIP)

    def test_a_fight_gone_from_the_list(self):
        from gui.player_window import BUILD_TAB, NOT_LISTED_TIP
        first = _with_casts()
        win = self._window(first)
        gone = _with_casts()
        win._open_player("2", BUILD_TAB, entry=gone)
        self.assertFalse(win._player_window.actions_button.isEnabled())
        self.assertEqual(win._player_window.actions_button.toolTip(), NOT_LISTED_TIP)
        # Asked all the same (a signal from elsewhere): the list says so
        win._player_window.actions_requested.emit(gone, "2")
        self.assertIs(win.history_list.current_entry(), first)
        self.assertIsNone(win.events_view.who)
        win._player_window.actions_requested.emit(SimpleNamespace(casts=None), "2")


if __name__ == "__main__":
    unittest.main()
