#!/usr/bin/env python3
"""The app-wide text size (issue #77, gui.text_size), offscreen: the steps
and their limits, Ctrl+=, Ctrl++, Ctrl+- and Ctrl+0 from the main window
and from a pop-up, the saved setting read at the next start, Settings'
slider, a Ctrl+wheel zoom giving way to the setting, and what is drawn in
pixels growing with it (icons in the pages, the strip's rows and label
column, the graph's legend) while 100% draws exactly what it did."""

import json
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


def _slot(n):
    return {"id": str(n), "name": f"Skill {n}", "icon": "ability_1handed_001"}  # bundled


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
        "front_bar": [f"Skill {n}" for n in range(1, 7)],
        "back_bar": [f"Skill {n}" for n in range(1, 7)],
        "front_bar_slots": [_slot(n) for n in range(1, 7)],
        "back_bar_slots": [_slot(n) for n in range(1, 7)]}]
    entry.buff_timeline = {"duration_ms": 100_000, "effects": {"Major Force": [
        {"start_ms": 10_000, "end_ms": 20_000, "source": "@me", "target": "@me"}]}}
    return entry


class TestSteps(unittest.TestCase):
    """The arithmetic, without a window."""

    def tearDown(self):
        from gui import text_size
        text_size._pct = text_size.DEFAULT_PCT

    def test_clamp(self):
        from gui.text_size import clamp
        self.assertEqual([clamp(v) for v in (50, 80, 125.4, 200, 300, None, "x", "150")],
                         [80, 80, 125, 200, 200, 100, 100, 150])

    def test_step_stops_at_the_ends_and_zero_resets(self):
        from gui.text_size import step
        self.assertEqual(step(100, 1), 110)
        self.assertEqual(step(100, -1), 90)
        self.assertEqual(step(200, 1), 200)
        self.assertEqual(step(80, -1), 80)
        self.assertEqual(step(170, 0), 100)

    def test_pixels_grow_above_100_and_never_shrink(self):
        from gui import text_size
        for pct, expected in ((100, 22), (80, 22), (150, 33), (200, 44)):
            text_size._pct = pct
            self.assertEqual(text_size.scaled_px(22), expected, pct)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TextSizeTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.windows = []

    def tearDown(self):
        from gui import text_size
        for win in self.windows:
            win.close()
        # The application font is shared by every test after this one
        text_size.apply(text_size.DEFAULT_PCT)
        self.tmp.cleanup()

    def _window(self, pct=None, show=True):
        from PySide6.QtTest import QTest

        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / "config.json")
        config.set("log_path", str(self.root / "Encounter.log"))
        config.set("update.check_enabled", False)
        if pct is not None:
            config.set("display.text_scale", pct)
        config.save()
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.windows.append(win)
        if show:
            win.show()
            win.activateWindow()
            self.assertTrue(QTest.qWaitForWindowActive(win, 2000))
        win._on_fight_completed(_entry())
        win.history_list.setCurrentRow(0)
        return win

    def _press(self, target, key_text):
        from PySide6.QtGui import QKeySequence
        from PySide6.QtTest import QTest
        combo = QKeySequence(key_text)[0]
        QTest.keyClick(target, combo.key(), combo.keyboardModifiers())
        _app.processEvents()

    def _saved(self):
        return json.loads((self.root / "config.json").read_text())["display"]["text_scale"]

    def _base_pt(self):
        from gui import text_size
        return text_size._base_font.pointSizeF()


class TestShortcuts(TextSizeTestCase):

    def test_starts_at_100_with_the_system_font(self):
        win = self._window()
        self.assertAlmostEqual(QApplication.font().pointSizeF(), self._base_pt())
        self.assertAlmostEqual(win.fight_view.font().pointSizeF(), self._base_pt())

    def test_ctrl_equals_and_ctrl_plus_go_up_and_are_saved(self):
        win = self._window()
        self._press(win.history_list, "Ctrl+=")
        self.assertEqual(self._saved(), 110)
        self._press(win.history_list, "Ctrl++")
        self.assertEqual(self._saved(), 120)
        self.assertAlmostEqual(win.fight_view.font().pointSizeF(), self._base_pt() * 1.2)
        self.assertIn("Text size 120%", win.statusBar().currentMessage())

    def test_ctrl_minus_and_ctrl_zero(self):
        win = self._window(130)
        self._press(win.history_list, "Ctrl+-")
        self.assertEqual(self._saved(), 120)
        self._press(win.history_list, "Ctrl+0")
        self.assertEqual(self._saved(), 100)
        self.assertAlmostEqual(QApplication.font().pointSizeF(), self._base_pt())

    def test_it_stops_at_200_and_80(self):
        win = self._window()
        for _ in range(15):
            self._press(win.history_list, "Ctrl+=")
        self.assertEqual(self._saved(), 200)
        for _ in range(15):
            self._press(win.history_list, "Ctrl+-")
        self.assertEqual(self._saved(), 80)

    def test_up_and_back_returns_to_the_same_size(self):
        win = self._window()
        before = win.fight_view.toHtml()
        for _ in range(7):
            self._press(win.history_list, "Ctrl+=")
        self.assertNotEqual(win.fight_view.toHtml(), before)
        for _ in range(7):
            self._press(win.history_list, "Ctrl+-")
        self.assertAlmostEqual(QApplication.font().pointSizeF(), self._base_pt())
        self.assertEqual(win.fight_view.toHtml(), before)

    def test_the_saved_size_is_used_at_the_next_start(self):
        win = self._window(150)
        self.assertAlmostEqual(QApplication.font().pointSizeF(), self._base_pt() * 1.5)
        self.assertAlmostEqual(win.history_list.font().pointSizeF(), self._base_pt() * 1.5)

    def test_the_keys_work_from_a_popup_window(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtTest import QTest
        win = self._window()
        win.fight_view.anchorClicked.emit(QUrl("esolog:build/1"))
        build = win._build_dialog
        build.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(build, 2000))
        html = build.view.toHtml()
        self._press(build, "Ctrl+=")
        self.assertEqual(self._saved(), 110)
        self.assertAlmostEqual(build.view.font().pointSizeF(), self._base_pt() * 1.1)
        self.assertNotEqual(build.view.toHtml(), html)  # re-rendered at the new size

    def test_a_wheel_zoom_gives_way_to_the_setting(self):
        win = self._window()
        win.fight_view.zoomIn(4)
        self.assertGreater(win.fight_view.font().pointSizeF(), self._base_pt())
        self._press(win.history_list, "Ctrl+0")
        self.assertAlmostEqual(win.fight_view.font().pointSizeF(), self._base_pt())
        self._press(win.history_list, "Ctrl+=")
        self.assertAlmostEqual(win.fight_view.font().pointSizeF(), self._base_pt() * 1.1)


class TestPixels(TextSizeTestCase):

    def test_icons_in_the_pane_grow(self):
        win = self._window()
        self.assertIn('width="22"', win.fight_view.toHtml())
        win.set_text_size(150)
        self.assertIn('width="33"', win.fight_view.toHtml())
        self.assertNotIn('width="22"', win.fight_view.toHtml())

    def test_icons_never_shrink(self):
        win = self._window()
        win.set_text_size(80)
        self.assertIn('width="22"', win.fight_view.toHtml())

    def test_the_strip_grows_with_the_text(self):
        from gui.timeline_strip import LABEL_WIDTH, ROW_HEIGHT, SCOPE_WIDTH
        win = self._window()
        strip = win.timeline_strip
        self.assertEqual(strip._row_rect(0).height(), ROW_HEIGHT)
        self.assertEqual(strip._track_rect().left(), LABEL_WIDTH + SCOPE_WIDTH)
        height = strip.sizeHint().height()
        win.set_text_size(150)
        self.assertEqual(strip._row_rect(0).height(), 15)
        self.assertEqual(strip._track_rect().left(), 180 + 69)
        self.assertGreater(strip.sizeHint().height(), height)
        # the label font follows the application font, in proportion
        self.assertAlmostEqual(strip._label_font().pointSizeF(), (self._base_pt() - 2) * 1.5)

    def test_the_graph_legend_widens(self):
        from gui.dps_graph import LEGEND_WIDTH
        win = self._window()
        win._show_graph()
        graph = win._graph_dialog
        self.assertEqual(graph.legend.width(), LEGEND_WIDTH)
        win.set_text_size(150)
        self.assertEqual(graph.legend.maximumWidth(), 345)
        graph.close()

    def test_the_bundled_icons_are_64_px(self):
        from PySide6.QtGui import QImage

        from ability_icons import icons_dir
        paths = sorted(icons_dir().glob("ability_*.png"))[:20]
        self.assertTrue(paths)
        for path in paths:
            image = QImage(str(path))
            self.assertEqual((image.width(), image.height()), (64, 64), path.name)


class TestSettings(TextSizeTestCase):

    def _dialog(self, pct=None):
        from app_config import AppConfig
        from gui.settings_dialog import SettingsDialog
        config = AppConfig(path=self.root / "config.json")
        if pct is not None:
            config.set("display.text_scale", pct)
        dialog = SettingsDialog(config)
        self.addCleanup(dialog.deleteLater)
        return config, dialog

    def test_the_slider_shows_and_writes_the_size(self):
        config, dialog = self._dialog(140)
        self.assertEqual(dialog.text_size.value(), 140)
        self.assertEqual(dialog.text_size_label.text(), "140%")
        dialog.text_size.setValue(170)
        self.assertEqual(dialog.text_size_label.text(), "170%")
        dialog.apply_to_config()
        self.assertEqual(config.get("display.text_scale"), 170)

    def test_the_slider_snaps_to_a_step(self):
        _, dialog = self._dialog()
        dialog.text_size.setValue(127)
        self.assertEqual(dialog.text_size.value(), 130)
        self.assertEqual(dialog.text_size_label.text(), "130%")

    def test_a_bad_saved_value_shows_as_100(self):
        _, dialog = self._dialog("big")
        self.assertEqual(dialog.text_size.value(), 100)

    def test_helper_lines_are_in_points_and_follow_the_size(self):
        from gui import text_size
        _, dialog = self._dialog()
        self.assertNotIn("px", dialog._small_style("muted"))
        small = text_size.small_pt()
        text_size.apply(150)
        self.assertAlmostEqual(text_size.small_pt(), round(small * 1.5, 2), places=1)

    def test_saving_settings_applies_the_size(self):
        from unittest import mock

        from gui.settings_dialog import SettingsDialog
        win = self._window()

        def save_with_130(dialog):
            dialog.text_size.setValue(130)
            return SettingsDialog.Accepted

        # Settings opened and saved with the slider moved, without the
        # modal loop
        with mock.patch.object(SettingsDialog, "exec", save_with_130):
            win._open_settings()
        self.assertAlmostEqual(QApplication.font().pointSizeF(), self._base_pt() * 1.3)
        self.assertEqual(self._saved(), 130)
        self.assertIn('width="29"', win.fight_view.toHtml())


if __name__ == "__main__":
    unittest.main()
