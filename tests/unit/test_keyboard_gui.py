#!/usr/bin/env python3
"""The main window from the keyboard, offscreen (issue #77): Tab moves the
focus between the fight list, the search field and the fight pane, as it
does in any Windows app, and Ctrl+D toggles Detail view from wherever the
focus is. Tab used to be Detail view's shortcut, which kept a keyboard user
on the fight list."""

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

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _entry():
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = "Sharpfang"
    entry.zone_name = "Moonlit Cove"
    entry.timestamp = "2026-10-28 20:00:00"
    entry.duration_s = 100.0
    entry.dps_time_s = 92.0
    entry.group_dps = 3000.0
    entry.players = [{
        "role": "D", "name": "@me", "character": "My Char", "is_local": True,
        "class_abbr": "NB", "class_name": "Nightblade", "dps": 1000.0, "boss_dps": 0.0,
        "dmg_pct": 100.0, "boss_pct": 0.0, "h": 20000, "m": 30000, "s": 15000,
        "unit_id": "1", "sets": [], "all_sets": [], "skill_lines": [], "class_lines": [],
        "front_bar": [], "back_bar": [], "front_bar_slots": [], "back_bar_slots": []}]
    return entry


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestKeyboard(unittest.TestCase):

    def setUp(self):
        from PySide6.QtTest import QTest

        from app_config import AppConfig
        from gui.main_window import MainWindow
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        config = AppConfig(path=root / "config.json")
        config.set("log_path", str(root / "Encounter.log"))
        config.set("update.check_enabled", False)
        self.win = MainWindow(config)
        self.win.worker_thread.quit()
        self.win.worker_thread.wait(3000)
        # A shortcut needs an active window, which show() alone does not
        # give offscreen
        self.win.show()
        self.win.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(self.win, 2000))
        self.win._on_fight_completed(_entry())
        self.win.history_list.setCurrentRow(0)

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def _key(self, key, modifier=None):
        """Press a key where a user's key would land: on the focused widget."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        target = QApplication.focusWidget() or self.win
        QTest.keyClick(target, key, modifier or Qt.NoModifier)
        _app.processEvents()

    def _focus(self, widget):
        widget.setFocus()
        _app.processEvents()
        self.assertIs(QApplication.focusWidget(), widget)

    def test_tab_moves_the_focus_and_leaves_detail_view_alone(self):
        from PySide6.QtCore import Qt
        self._focus(self.win.history_list)
        self._key(Qt.Key_Tab)
        self.assertIsNot(QApplication.focusWidget(), self.win.history_list)
        self.assertTrue(self.win.detail_action.isChecked())

    def test_tab_reaches_the_search_field_and_the_fight_pane(self):
        from PySide6.QtCore import Qt
        self._focus(self.win.history_list)
        reached = set()
        for _ in range(20):
            self._key(Qt.Key_Tab)
            reached.add(QApplication.focusWidget())
        self.assertIn(self.win.search_field, reached)
        self.assertIn(self.win.fight_view, reached)
        self.assertIn(self.win.history_list, reached)  # and comes round again
        self.assertTrue(self.win.detail_action.isChecked())

    def test_shift_tab_goes_back(self):
        from PySide6.QtCore import Qt
        self._focus(self.win.history_list)
        self._key(Qt.Key_Tab)
        after_one = QApplication.focusWidget()
        self._key(Qt.Key_Backtab, Qt.ShiftModifier)
        self.assertIs(QApplication.focusWidget(), self.win.history_list)
        self.assertIsNot(after_one, self.win.history_list)

    def test_ctrl_d_toggles_detail_view_from_each_part_of_the_window(self):
        from PySide6.QtCore import Qt
        for widget in (self.win.history_list, self.win.fight_view, self.win.search_field):
            with self.subTest(widget=type(widget).__name__):
                self._focus(widget)
                self._key(Qt.Key_D, Qt.ControlModifier)
                self.assertFalse(self.win.detail_action.isChecked())
                self._key(Qt.Key_D, Qt.ControlModifier)
                self.assertTrue(self.win.detail_action.isChecked())
                self.assertIs(QApplication.focusWidget(), widget)

    def test_ctrl_d_in_the_search_field_leaves_the_text_alone(self):
        from PySide6.QtCore import Qt
        self.win.search_field.setText("jabs")
        self._focus(self.win.search_field)
        self.win.search_field.setCursorPosition(0)
        self._key(Qt.Key_D, Qt.ControlModifier)
        self.assertEqual(self.win.search_field.text(), "jabs")
        self.assertFalse(self.win.detail_action.isChecked())

    def test_the_toolbar_names_the_key(self):
        self.assertEqual(self.win.detail_action.shortcut().toString(), "Ctrl+D")
        self.assertIn("Ctrl+D", self.win.detail_action.toolTip())

    def test_the_arrows_pick_a_fight(self):
        # What the guide's Keyboard table says, with a second fight listed
        from PySide6.QtCore import Qt
        second = _entry()
        second.boss_name = "Ozezan"
        self.win._on_fight_completed(second)
        self._focus(self.win.history_list)
        row = self.win.history_list.currentRow()
        self._key(Qt.Key_Down if row == 0 else Qt.Key_Up)
        self.assertNotEqual(self.win.history_list.currentRow(), row)
        shown = self.win.fight_view.toPlainText()
        self._key(Qt.Key_Up if row == 0 else Qt.Key_Down)
        self.assertEqual(self.win.history_list.currentRow(), row)
        self.assertNotEqual(self.win.fight_view.toPlainText(), shown)

    def test_ctrl_wheel_zooms_the_fight_pane(self):
        # The guide's table promises it; it is Qt's own for a read-only
        # text browser. The event goes to the viewport, not the widget
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent
        view = self.win.fight_view
        before = view.font().pointSizeF()
        pos = QPointF(view.viewport().rect().center())
        event = QWheelEvent(pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())),
                            QPoint(0, 0), QPoint(0, 120), Qt.NoButton,
                            Qt.ControlModifier, Qt.NoScrollPhase, False)
        QApplication.sendEvent(view.viewport(), event)
        self.assertGreater(view.font().pointSizeF(), before)

    def test_detail_view_still_changes_the_pane(self):
        from PySide6.QtCore import Qt
        self._focus(self.win.history_list)
        detailed = self.win.fight_view.toHtml()
        self._key(Qt.Key_D, Qt.ControlModifier)
        self.assertNotEqual(self.win.fight_view.toHtml(), detailed)
        self._key(Qt.Key_D, Qt.ControlModifier)
        self.assertEqual(self.win.fight_view.toHtml(), detailed)


if __name__ == "__main__":
    unittest.main()
