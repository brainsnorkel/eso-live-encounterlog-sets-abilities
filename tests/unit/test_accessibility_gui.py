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
        from gui.dps_graph import DpsGraphDialog
        from tests.unit.test_dps_graph import _entry
        dialog = DpsGraphDialog()
        self.addCleanup(dialog.deleteLater)
        dialog.show_graph(_entry(3), False)
        from PySide6.QtGui import QAccessible
        iface = QAccessible.queryAccessibleInterface(dialog.graph)
        self.assertEqual(iface.text(QAccessible.Name), "DPS over time")
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
        for widget, name in ((win.history_list, "Fights"), (win.search_field, "Search in fight"),
                             (win.fight_view, "Fight"), (win.timeline_strip, "Buff timeline")):
            self.assertEqual(QAccessible.queryAccessibleInterface(widget).text(QAccessible.Name),
                             name)

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


if __name__ == "__main__":
    unittest.main()
