#!/usr/bin/env python3
"""What a screen reader is given, and Reduce motion (issue #77), offscreen:
a page's images read out as their alt text in place of U+FFFC, through
Qt's own accessibility interface; the timeline strip and the DPS graph,
both painted, described in words; the main window's parts named; and the
taunt ring's pulse stopped at rest while Reduce motion is on."""

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
OBJECT = "￼"  # what Qt gives a screen reader for an image


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _described(widget) -> str:
    """The description as Qt's accessibility layer reports it."""
    from PySide6.QtGui import QAccessible
    return QAccessible.queryAccessibleInterface(widget).text(QAccessible.Description)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class AccessibilityTestCase(unittest.TestCase):

    def setUp(self):
        from gui.fight_view import set_reduce_motion
        _ensure_app()
        set_reduce_motion(False)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        from PySide6.QtGui import QColor, QImage
        image = QImage(40, 40, QImage.Format_ARGB32)
        image.fill(QColor("red"))
        self.assertTrue(image.save(str(self.root / "ability_test_001.png")))

    def tearDown(self):
        from gui.fight_view import set_reduce_motion
        set_reduce_motion(False)
        self.tmp.cleanup()

    def _view(self):
        from gui.fight_view import FightView
        from gui.icon_cache import IconCache
        view = FightView(icons=IconCache(self.root))
        self.addCleanup(view.close)
        return view


class TestThePage(AccessibilityTestCase):

    def _fight(self, hide=False):
        from gui.fight_render import render_html
        from gui.name_mask import NameMask
        from tests.unit.test_fight_view import _entry_with_bars
        entry = _entry_with_bars()
        entry.players.append(dict(entry.players[0], name="@friend", unit_id="2", is_local=False))
        entry.players[0]["is_local"] = True
        entry.group_dps = 2000.0  # the header's graph glyph comes with a group figure
        view = self._view()
        view.setHtml(render_html(entry, True, icons=view.icons, base_pt=9.0,
                                 names=NameMask.for_entry(entry, hide)))
        return view

    def test_an_ability_icon_reads_as_its_name(self):
        view = self._fight()
        text = _described(view)
        self.assertIn("Biting Jabs", text)
        self.assertNotIn(OBJECT, text)
        # Qt's own text still has the placeholder: the description is the fix
        self.assertIn(OBJECT, view.toPlainText())

    def test_the_glyphs_say_what_they_open(self):
        text = _described(self._fight())
        for words in ("DPS graph", "damage breakdown", "damage taken"):
            self.assertIn(words, text)

    def test_a_hidden_name_reads_as_hidden(self):
        text = _described(self._fight(hide=True))
        self.assertIn("hidden name", text)
        self.assertNotIn("@friend", text)
        self.assertIn("@tester", text)  # the player writing the log stays

    def test_the_description_follows_the_page(self):
        view = self._fight()
        view.setHtml("<p>No fight</p>")
        self.assertEqual(_described(view), "No fight")

    def test_an_icon_beside_its_name_is_not_read_twice(self):
        from gui.damage_render import _icon_html
        from gui.icon_cache import IconCache
        view = self._view()
        icon = _icon_html("ability_test_001", IconCache(self.root))
        view.setHtml(f"<table><tr><td>{icon}</td><td>Biting Jabs</td></tr></table>")
        self.assertEqual(_described(view).count("Biting Jabs"), 1)


class TestPaintedWidgets(AccessibilityTestCase):

    def test_the_strip_reads_its_rows(self):
        from gui.timeline_strip import TimelineStrip
        strip = TimelineStrip()
        self.addCleanup(strip.deleteLater)
        strip.set_timeline({"duration_ms": 10_000, "effects": {"Major Force": [
            {"start_ms": 0, "end_ms": 5_000, "source": "@a", "target": "@b"}]}},
            [{"name": "Lucent Echoes", "kind": "plain", "text": "Lucent Echoes:0%",
              "uptime_pct": 0, "expected": True, "shown": True, "scope": "group", "intervals": []}])
        from PySide6.QtGui import QAccessible
        iface = QAccessible.queryAccessibleInterface(strip)
        self.assertEqual(iface.text(QAccessible.Name), "Buff timeline")
        lines = _described(strip).split("\n")
        self.assertEqual(lines[0], "Major Force 50% group")
        self.assertEqual(lines[1], "Lucent Echoes:0% group, expected but not up")

    def test_the_graph_reads_its_lines(self):
        from gui.dps_graph import DpsGraphPanel
        from tests.unit.test_dps_graph import _entry
        dialog = DpsGraphPanel()
        self.addCleanup(dialog.deleteLater)
        dialog.show_graph(_entry(3), False)
        from PySide6.QtGui import QAccessible
        iface = QAccessible.queryAccessibleInterface(dialog.graph)
        self.assertEqual(iface.text(QAccessible.Name), "DPS over time")
        # The legend and the curve picker are named too (issue #196). Qt on
        # Linux names a combo box by its current item whatever its name, the
        # Show label reaching a reader as its buddy, so the picker's own name
        # is checked here
        self.assertEqual(QAccessible.queryAccessibleInterface(dialog.legend).text(QAccessible.Name),
                         "Lines drawn")
        self.assertEqual(dialog.mode.accessibleName(), "Show")
        text = _described(dialog.graph)
        names = [c.name for c in dialog.graph.curves]
        self.assertTrue(names)
        for name in names:
            self.assertIn(name, text)
        self.assertIn("at the end", text)


class TestMainWindow(AccessibilityTestCase):

    def _window(self, reduce_motion=False):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / "config.json")
        config.set("log_path", str(self.root / "Encounter.log"))
        config.set("update.check_enabled", False)
        config.set("display.reduce_motion", reduce_motion)
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.addCleanup(win.close)
        return win

    def test_the_parts_are_named(self):
        from PySide6.QtGui import QAccessible
        win = self._window()
        for widget, name in ((win.history_list, "Fights"), (win.search_field, "Search this tab"),
                             (win.fight_tabs, "Fight views"), (win.fight_view, "Fight"),
                             (win.deaths_view, "Deaths"), (win.timeline_strip, "Buff timeline"),
                             (win.events_view.table, "Fight events"),
                             (win.events_view.more_button, "More"),
                             (win.fight_views.find_button, "Find (Ctrl+F)")):
            self.assertEqual(QAccessible.queryAccessibleInterface(widget).text(QAccessible.Name),
                             name)
        # Linux names a combo box by its current item, so its own name here
        self.assertEqual(win.events_view.show_picker.accessibleName(), "Show")

    def test_reduce_motion_is_read_at_start(self):
        from gui.fight_view import reduce_motion
        self._window(reduce_motion=True)
        self.assertTrue(reduce_motion())
        self._window(reduce_motion=False)
        self.assertFalse(reduce_motion())


class TestReduceMotion(AccessibilityTestCase):

    def _ringed(self):
        from PySide6.QtGui import QImage, QPainter
        view = self._view()
        view.resize(300, 100)
        view.show()
        view.setHtml('<p><img src="icon:ability_test_001?ring=7b1fa2" width="40" height="40"></p>')
        out = QImage(300, 100, QImage.Format_ARGB32)
        painter = QPainter(out)
        view.document().drawContents(painter)  # lays the page out, loading the icon
        painter.end()
        return view

    def _ring_pixel(self, view):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QImage, QTextDocument
        url = QUrl("icon:ability_test_001?ring=7b1fa2")
        return QImage(view.document().resource(QTextDocument.ImageResource, url)).pixelColor(1, 1).name()

    def test_turning_it_on_stops_a_pulse_at_rest(self):
        from gui.fight_view import set_reduce_motion
        view = self._ringed()
        self.assertTrue(view._pulse.isActive())
        view._pulse_step()
        view._pulse_step()
        self.assertNotEqual(self._ring_pixel(view), "#7b1fa2")  # mid-glow
        set_reduce_motion(True)
        self.assertFalse(view._pulse.isActive())
        self.assertEqual(view._pulse_phase, 0)
        self.assertEqual(self._ring_pixel(view), "#7b1fa2")  # the plain ring

    def test_no_pulse_starts_while_it_is_on(self):
        from gui.fight_view import set_reduce_motion
        set_reduce_motion(True)
        view = self._ringed()
        self.assertEqual(len(view._ring_urls), 1)  # the ring is still drawn
        self.assertFalse(view._pulse.isActive())
        self.assertEqual(self._ring_pixel(view), "#7b1fa2")

    def test_the_settings_box_writes_it(self):
        from app_config import AppConfig
        from gui.settings_dialog import SettingsDialog
        config = AppConfig(path=self.root / "c.json")
        self.assertFalse(config.get("display.reduce_motion"))
        dialog = SettingsDialog(config)
        self.addCleanup(dialog.deleteLater)
        self.assertFalse(dialog.reduce_motion.isChecked())
        dialog.reduce_motion.setChecked(True)
        dialog.apply_to_config()
        self.assertTrue(config.get("display.reduce_motion"))


class TestPositionsWindow(AccessibilityTestCase):
    """The positions window (issue #214): its painted canvas is named and
    describes the moment in numbers, never names; the table beside it is
    the reader's surface, a real table whose hidden names read 'hidden
    name'; the scrub bar is a slider with the moment in words; no
    animation runs, so Reduce motion has nothing to stop."""

    def _window(self, hide=False):
        from fight_reread import RereadEvent
        from gui.name_mask import NameMask
        from gui.positions_window import PositionsWindow
        from tests.unit.test_positions_window_gui import (
            DEATH,
            DPS,
            session,
            split_and_states,
        )
        _log, _path, fights, states = split_and_states(self.root, session())
        entry = fights[0]
        window = PositionsWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        window.open(entry, DEATH, DPS, dark=False, names=NameMask.for_entry(entry, hide))
        window.reread_done(RereadEvent("loaded", entry.locator, states))
        return window

    def test_the_canvas_reads_the_moment_in_numbers(self):
        from PySide6.QtGui import QAccessible
        window = self._window(hide=True)
        iface = QAccessible.queryAccessibleInterface(window.canvas)
        self.assertEqual(iface.text(QAccessible.Name), "Positions")
        text = _described(window.canvas)
        self.assertEqual(text, "0:06.0 into the fight. Test Boss 95%. 3 players, 2 alive.")
        self.assertNotIn("@", text)

    def test_the_table_is_a_table_and_a_hidden_name_reads_as_hidden(self):
        from PySide6.QtGui import QAccessible
        window = self._window(hide=True)
        iface = QAccessible.queryAccessibleInterface(window.table)
        self.assertEqual(iface.role(), QAccessible.Table)
        self.assertEqual(iface.text(QAccessible.Name), "Players and bosses")
        names = [iface.child(i).text(QAccessible.Name) for i in range(iface.childCount())]
        self.assertIn("hidden name", names)
        self.assertIn("@tester", names)  # the player writing the log
        self.assertFalse(any("▒" in name for name in names))
        # The table carries the canvas's description, for a reader on it
        self.assertEqual(_described(window.table), _described(window.canvas))

    def test_the_scrub_bar_is_a_slider_and_the_boss_bars_are_read(self):
        from PySide6.QtGui import QAccessible
        window = self._window()
        iface = QAccessible.queryAccessibleInterface(window.scrub)
        self.assertEqual(iface.role(), QAccessible.Slider)
        self.assertEqual(iface.text(QAccessible.Name), "Moment")
        self.assertEqual(_described(window.scrub), "0:06.0 into the fight, of 12s")
        bars = QAccessible.queryAccessibleInterface(window.boss_bars)
        self.assertEqual(bars.text(QAccessible.Name), "Boss health")
        self.assertEqual(_described(window.boss_bars), "Test Boss 95% (950,000 of 1,000,000)")

    def test_nothing_moves_by_itself(self):
        from PySide6.QtCore import QTimer
        window = self._window()
        timers = window.findChildren(QTimer)
        # Its one timer is the single-shot redraw of a burst of updates
        self.assertEqual(len(timers), 1)
        self.assertTrue(timers[0].isSingleShot())
        self.assertEqual(timers[0].interval(), 0)
        self.assertFalse(timers[0].isActive())


if __name__ == "__main__":
    unittest.main()
