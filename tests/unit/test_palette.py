#!/usr/bin/env python3
"""The app's colours, pinned by measurement (issue #77): text at 4.5:1 or
more and bars and lines at 3:1 or more against the real backgrounds of
both themes (WCAG 2.2, 1.4.3 and 1.4.11), and the DPS graph's colour-blind
set kept apart for normal vision and the three dichromacies. A palette
change that fails here needs re-measuring, not a looser number."""

import os
import tempfile
import unittest
from pathlib import Path

from tests.unit.colour_measure import BACKGROUNDS, contrast, min_difference

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

_app = None
TEXT, NON_TEXT = 4.5, 3.0
DARK, LIGHT = True, False


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _hex(color) -> str:
    return color if isinstance(color, str) else color.name()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestTextContrast(unittest.TestCase):

    def assert_text(self, where, color, dark, backgrounds=None):
        for background in backgrounds or BACKGROUNDS[dark]:
            ratio = contrast(_hex(color), background)
            self.assertGreaterEqual(ratio, TEXT, f"{where} {_hex(color)} on {background}: {ratio:.2f}")

    def test_the_page_themes(self):
        from gui import death_render, fight_render
        for dark in (LIGHT, DARK):
            theme = fight_render._THEMES[dark]
            for key in ("text", "muted", "detail", "vet", "link", "taunt"):
                self.assert_text(f"fight {key}", theme[key], dark)
            for role, color in theme["roles"].items():
                self.assert_text(f"role {role}", color, dark)
            kinds = death_render._THEMES[dark]
            for key in ("text", "muted", "damage", "heal", "shield"):
                self.assert_text(f"death {key}", kinds[key], dark)
            for color in kinds["health"]:
                self.assert_text("health", color, dark)

    def test_text_on_its_own_fill(self):
        from gui import death_render
        for dark in (LIGHT, DARK):
            kinds = death_render._THEMES[dark]
            self.assert_text("death chip", kinds["chip_fg"], dark, [kinds["chip_bg"]])
            self.assert_text("kinds bar", kinds["bar_text"], dark,
                             [kinds["bar_left"], kinds["bar_right"], kinds["bar_empty"]])

    def test_gear_quality_and_status_colours(self):
        from gui import build_render, main_window
        for dark in (LIGHT, DARK):
            for quality, color in build_render._QUALITY_COLORS[dark].items():
                self.assert_text(f"quality {quality}", color, dark)
            for state, color in main_window._STATE_COLORS[dark].items():
                if color:
                    self.assert_text(f"status {state}", color, dark)

    def test_the_missing_label_on_the_strip(self):
        # Painted on the strip, which is drawn on the Window colour
        from gui.timeline_strip import MISSING_COLORS
        for dark in (LIGHT, DARK):
            self.assert_text("missing label", MISSING_COLORS[dark], dark, [BACKGROUNDS[dark][0]])

    def test_settings_helper_lines(self):
        from gui.fight_render import _theme
        for dark in (LIGHT, DARK):
            self.assert_text("settings muted", _theme(dark)["muted"], dark)
            self.assert_text("settings warning", _theme(dark)["vet"], dark)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestBarsAndLines(unittest.TestCase):

    def assert_non_text(self, where, color, background):
        ratio = contrast(_hex(color), background)
        self.assertGreaterEqual(ratio, NON_TEXT, f"{where} {_hex(color)} on {background}: {ratio:.2f}")

    def test_strip_bars_on_the_window_colour(self):
        from gui import timeline_strip as ts
        for dark, effects, tracked in ((LIGHT, ts.EFFECT_COLORS_LIGHT, ts.TRACKED_COLORS_LIGHT),
                                       (DARK, ts.EFFECT_COLORS, ts.TRACKED_COLORS)):
            window = BACKGROUNDS[dark][0]
            for effect, color in effects.items():
                self.assert_non_text(effect, color, window)
            for index, color in enumerate(tracked):
                self.assert_non_text(f"tracked {index}", color, window)
            self.assert_non_text("default row", ts.DEFAULT_ROW_COLORS[dark], window)
            self.assert_non_text("armour row", ts.ARMOUR_COLORS[dark], window)

    def test_both_sets_name_the_same_effects(self):
        from gui import timeline_strip as ts
        self.assertEqual(set(ts.EFFECT_COLORS), set(ts.EFFECT_COLORS_LIGHT))
        self.assertEqual(len(ts.TRACKED_COLORS), len(ts.TRACKED_COLORS_LIGHT))

    def test_colourblind_graph_lines_on_the_graph_surface(self):
        from gui.dps_graph import COLORBLIND_SERIES_COLORS
        for dark in (LIGHT, DARK):
            base = BACKGROUNDS[dark][1]  # the graph paints on Base
            for color in COLORBLIND_SERIES_COLORS[dark]:
                self.assert_non_text("graph line", color, base)

    def test_colourblind_graph_set_stays_apart(self):
        # Measured when the set was chosen: 9.8 at worst on light, 13.1 on
        # dark; the default set measures 5 and 2 for protanopes
        from gui.dps_graph import COLORBLIND_SERIES_COLORS
        floors = {LIGHT: 9.5, DARK: 13.0}
        for dark in (LIGHT, DARK):
            for deficiency in (None, "protan", "deutan", "tritan"):
                difference, pair = min_difference(COLORBLIND_SERIES_COLORS[dark], deficiency)
                self.assertGreaterEqual(difference, floors[dark],
                                        f"{'dark' if dark else 'light'} {deficiency}: {pair}")

    def test_no_two_of_the_first_28_lines_look_alike(self):
        from gui.dps_graph import series_color, series_style
        for dark in (LIGHT, DARK):
            looks = {(series_color(i, dark, True).name(), series_style(i, True)) for i in range(28)}
            self.assertEqual(len(looks), 28)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestThemesInTheWidgets(unittest.TestCase):

    def setUp(self):
        _ensure_app()

    def _palette(self, window_hex):
        from PySide6.QtGui import QColor, QPalette
        palette = QPalette()
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            palette.setColor(group, QPalette.Window, QColor(window_hex))
        return palette

    def test_the_strip_paints_the_set_of_its_theme(self):
        from gui import timeline_strip as ts
        strip = ts.TimelineStrip()
        self.addCleanup(strip.deleteLater)
        strip.set_timeline({"duration_ms": 10_000, "effects": {"Major Courage": [
            {"start_ms": 0, "end_ms": 5_000, "source": "@a", "target": "@b"}]}},
            [{"name": "Crux", "kind": "plain", "text": "Crux 50%", "uptime_pct": 50.0,
              "intervals": [{"start_ms": 0, "end_ms": 5_000, "target": "@me"}]}])
        strip.setPalette(self._palette("#f3f3f3"))
        self.assertEqual(strip.row_color("Major Courage"), ts.EFFECT_COLORS_LIGHT["Major Courage"])
        self.assertEqual(strip.row_color("Crux"), ts.TRACKED_COLORS_LIGHT[0])
        self.assertEqual(strip.row_color("Unknown"), ts.DEFAULT_ROW_COLORS[False])
        strip.setPalette(self._palette("#1e1e1e"))  # a live theme switch
        self.assertEqual(strip.row_color("Major Courage"), ts.EFFECT_COLORS["Major Courage"])
        self.assertEqual(strip.row_color("Crux"), ts.TRACKED_COLORS[0])

    def test_settings_helper_lines_follow_the_theme(self):
        from app_config import AppConfig
        from gui.fight_render import _theme
        from gui.settings_dialog import SettingsDialog
        with tempfile.TemporaryDirectory() as tmp:
            dialog = SettingsDialog(AppConfig(path=Path(tmp) / "config.json"))
            self.addCleanup(dialog.deleteLater)
            dark = dialog.palette().color(dialog.backgroundRole()).lightness() < 128
            self.assertIn(_theme(dark)["muted"], dialog._small_style("muted"))
            self.assertIn(_theme(dark)["vet"], dialog._small_style("warning"))


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestColourblindGraphOption(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _entry(self, players=10):
        # The graph tests' fight: players with unit ids 1..n in rank order
        from tests.unit.test_dps_graph import _entry
        return _entry(players)

    def test_off_by_default(self):
        from app_config import AppConfig
        self.assertFalse(AppConfig(path=self.root / "c.json").get("display.colorblind_graph"))

    def test_the_settings_box_writes_the_option(self):
        from app_config import AppConfig
        from gui.settings_dialog import SettingsDialog
        config = AppConfig(path=self.root / "c.json")
        dialog = SettingsDialog(config)
        self.addCleanup(dialog.deleteLater)
        self.assertFalse(dialog.colorblind_graph.isChecked())
        dialog.colorblind_graph.setChecked(True)
        dialog.apply_to_config()
        self.assertTrue(config.get("display.colorblind_graph"))

    def test_the_graph_switches_set_and_strokes(self):
        from PySide6.QtCore import Qt

        from gui.dps_graph import (
            COLORBLIND_SERIES_COLORS,
            DASH_CYCLE,
            SERIES_COLORS,
            DpsGraphPanel,
        )
        dialog = DpsGraphPanel()
        self.addCleanup(dialog.deleteLater)
        dialog.show_graph(self._entry(), False)
        curves = {c.key: c for c in dialog.graph._curves}
        self.assertEqual(curves["1"].color.name(), SERIES_COLORS[False][0])
        self.assertEqual({curves[str(n)].style for n in range(1, 9)}, {Qt.SolidLine})
        dialog.set_colorblind(True)  # redraws the fight on display
        curves = {c.key: c for c in dialog.graph._curves}
        self.assertEqual(curves["1"].color.name(), COLORBLIND_SERIES_COLORS[False][0])
        self.assertEqual([curves[str(n)].style for n in range(1, 5)], list(DASH_CYCLE))
        self.assertEqual(curves["8"].color.name(), COLORBLIND_SERIES_COLORS[False][0])  # 8th: hue 1 again,
        self.assertEqual(curves["8"].style, Qt.DashDotLine)                              # another stroke

    def test_the_main_window_passes_the_option(self):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / "config.json")
        config.set("log_path", str(self.root / "Encounter.log"))
        config.set("update.check_enabled", False)
        config.set("display.colorblind_graph", True)
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.addCleanup(win.close)
        win._on_fight_completed(self._entry(3))
        win.history_list.select_fight(0)
        win._show_graph()
        self.assertTrue(win.dps_panel.colorblind)


def _over(color: str, alpha: float, surface: str) -> str:
    """*color* at *alpha* composited over *surface*, as opaque hex (the
    contrast measure takes opaque colours only)."""
    fg = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    bg = [int(surface[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(alpha * f + (1 - alpha) * b):02x}" for f, b in zip(fg, bg))


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestPositionsWindowColours(unittest.TestCase):
    """The positions window (issue #214): every mark of its canvas, boss
    bars and scrub bar at 3:1 against the surface it is drawn on, every
    text at 4.5:1, numbers on their own fill; the health ring's 13% track
    and the 6% grid are decorative and left out."""

    def assert_ratio(self, where, color, surface, floor):
        ratio = contrast(_hex(color), surface)
        self.assertGreaterEqual(ratio, floor, f"{where} {_hex(color)} on {surface}: {ratio:.2f}")

    def test_the_canvas_marks_on_base(self):
        from gui import positions_canvas as pc
        for dark in (LIGHT, DARK):
            base = BACKGROUNDS[dark][1]  # the canvas fills Base
            colours = pc.colors(dark, base)
            for key in ("ink", "muted", "shield", "damage", "hostile", "boss"):
                self.assert_ratio(f"canvas {key}", colours[key], base, NON_TEXT)
            for color in colours["health"]:
                self.assert_ratio("health ring", color, base, NON_TEXT)
            # The nose: the ink at NOSE_ALPHA over Base
            self.assert_ratio("nose", _over(colours["ink"].name(), pc.NOSE_ALPHA, base), base,
                              NON_TEXT)

    def test_the_canvas_texts(self):
        from gui import positions_canvas as pc
        for dark in (LIGHT, DARK):
            base = BACKGROUNDS[dark][1]
            colours = pc.colors(dark, base)
            # A number in the Base colour on a player's inked body
            self.assert_ratio("number on its body", base, colours["ink"].name(), TEXT)
            # A dead or stale player's number in ink, a lost one's muted, on
            # the hollow body (Base); the boss's name; the notes and the
            # selected unit's label
            for key in ("ink", "muted", "boss"):
                self.assert_ratio(f"canvas text {key}", colours[key], base, TEXT)

    def test_the_boss_bars_and_the_scrub_bar(self):
        from gui import positions_canvas as pc
        for dark in (LIGHT, DARK):
            window, base = BACKGROUNDS[dark]
            colours = pc.colors(dark, base)
            # A boss bar's fill on its track (the ink at TRACK_ALPHA over the
            # window), its words in ink or muted on the window
            track = _over(colours["ink"].name(), pc.TRACK_ALPHA, window)
            for color in colours["health"]:
                self.assert_ratio("boss bar fill", color, track, NON_TEXT)
            for key in ("ink", "muted"):
                self.assert_ratio(f"boss bar text {key}", colours[key], window, TEXT)
            # The scrub bar: its band's edge and its focus mark on the
            # window; the hatch, the deaths' crosses, the map changes and
            # the moment's line on the band (Base)
            self.assert_ratio("band edge", colours["muted"], window, NON_TEXT)
            self.assert_ratio("focus mark", colours["ink"], window, NON_TEXT)
            for key in ("muted", "damage", "ink"):
                self.assert_ratio(f"band {key}", colours[key], base, NON_TEXT)
            # The ticks' labels
            self.assert_ratio("tick label", colours["muted"], window, TEXT)

    def test_the_table_icons(self):
        """The table's pictures of the units: the ink, the boss's colour,
        drawn on the table's Base."""
        _ensure_app()
        from gui import positions_canvas as pc
        for dark in (LIGHT, DARK):
            base = BACKGROUNDS[dark][1]
            for mark in (pc.MARK_PLAYER, pc.MARK_BOSS, pc.MARK_LOOSE):
                image = pc.marker_icon(mark, "T", 24, dark)
                middle = image.pixelColor(12, 12) if mark != pc.MARK_LOOSE else None
                if middle is not None:
                    self.assertEqual(middle.alpha(), 255)
                    self.assert_ratio(f"icon {mark}", middle.name(), base, NON_TEXT)

    def test_the_table_icons_on_a_selected_row(self):
        """A selected row's picture is drawn in the table's highlighted
        text (the review's finding 15): in the ink, the dark theme's light
        blue highlight (Windows 11's #4cc2ff) left it at 1.3:1. Against the
        highlight, in both of Windows 11's pairs."""
        _ensure_app()
        from gui import positions_canvas as pc
        for dark, highlight, text in ((DARK, "#4cc2ff", "#000000"), (LIGHT, "#0067c0", "#ffffff")):
            for mark in (pc.MARK_PLAYER, pc.MARK_BOSS):
                image = pc.marker_icon(mark, "T", 24, dark, ink=text)
                middle = image.pixelColor(12, 12)
                self.assertEqual(middle.alpha(), 255)
                self.assert_ratio(f"selected icon {mark}", middle.name(), highlight, NON_TEXT)

    def test_the_canvas_reads_its_theme_from_its_palette(self):
        _ensure_app()
        from PySide6.QtGui import QColor, QPalette

        from gui import positions_canvas as pc
        canvas = pc.PositionsCanvas()
        self.addCleanup(canvas.deleteLater)
        for window_hex, dark in (("#f3f3f3", False), ("#1e1e1e", True)):
            palette = QPalette()
            for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
                palette.setColor(group, QPalette.Window, QColor(window_hex))
            canvas.setPalette(palette)  # a live theme switch
            self.assertEqual(canvas.hostile_color().name(), pc.HOSTILE_COLORS[dark])
            self.assertEqual(canvas.boss_color().name(), pc.BOSS_COLORS[dark])
            self.assertEqual(canvas.ink().name(), _theme_text(dark))


def _theme_text(dark):
    from gui.fight_render import _theme
    return _theme(dark)["text"]


if __name__ == "__main__":
    unittest.main()
