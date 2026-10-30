#!/usr/bin/env python3
"""Offscreen tests for the TimelineStrip widget."""

import os
import unittest

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


def _sample_timeline():
    return {
        "duration_ms": 60_000,
        "effects": {
            "Major Force": [
                {"start_ms": 10_000, "end_ms": 20_000,
                 "source": "@caster", "target": "@receiver"},
                {"start_ms": 15_000, "end_ms": 30_000,
                 "source": "@other", "target": "@receiver2"},
            ],
            "Major Vulnerability": [
                {"start_ms": 5_000, "end_ms": 60_000,
                 "source": "@caster", "target": "Test Boss"},
            ],
        },
    }


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestTimelineStrip(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        from gui.timeline_strip import TimelineStrip
        self.strip = TimelineStrip()
        self.strip.resize(600, 100)

    def tearDown(self):
        self.strip.deleteLater()

    def test_hidden_without_data(self):
        self.assertFalse(self.strip.isVisibleTo(self.strip.parentWidget()
                                                or self.strip))
        self.strip.set_timeline(None)
        self.assertEqual(self.strip._rows, [])
        self.strip.set_timeline({"duration_ms": 0, "effects": {}})
        self.assertEqual(self.strip._rows, [])

    def test_rows_only_for_active_effects(self):
        """Spec scenario: effect with no activity is omitted."""
        self.strip.set_timeline(_sample_timeline())
        self.assertEqual(self.strip._rows,
                         ["Major Force", "Major Vulnerability"])

    def test_compact_height_bound(self):
        """Spec: strip stays compact even with all six effects active."""
        timeline = _sample_timeline()
        for effect in ("Major Slayer", "Major Courage", "Major Berserk",
                       "Powerful Assault"):
            timeline["effects"][effect] = [
                {"start_ms": 0, "end_ms": 1_000, "source": "a", "target": "b"}]
        self.strip.set_timeline(timeline)
        self.assertEqual(len(self.strip._rows), 6)
        self.assertLessEqual(self.strip.sizeHint().height(), 100)

    def test_taunt_row_is_last_and_solid_with_one_receiver(self):
        timeline = _sample_timeline()
        timeline["effects"]["Taunt"] = [
            {"start_ms": 0, "end_ms": 45_000, "source": "@tank", "target": "Test Boss"}]
        self.strip.set_timeline(timeline)
        self.assertEqual(self.strip._rows[-1], "Taunt")
        self.assertEqual(self.strip._row_info["Taunt"], {"uptime_pct": 75, "sparse": False, "scope": "boss"})

    def test_uptime_percentages(self):
        from gui.timeline_strip import uptime_pct
        # Two overlapping intervals 10-20s and 15-30s = 20s union of 60s
        self.strip.set_timeline(_sample_timeline())
        self.assertEqual(self.strip._row_info["Major Force"]["uptime_pct"], 33)
        # Vulnerability covers 5-60s = 55/60
        self.assertEqual(
            self.strip._row_info["Major Vulnerability"]["uptime_pct"], 92)
        # Direct function checks
        self.assertEqual(uptime_pct([], 60_000), 0)
        self.assertEqual(uptime_pct(
            [{"start_ms": 0, "end_ms": 60_000}], 60_000), 100)

    def test_sparse_receivers_are_marked(self):
        timeline = _sample_timeline()
        # Force reaches 2 distinct receivers -> sparse, drawn hatched
        self.strip.set_timeline(timeline)
        self.assertTrue(self.strip._row_info["Major Force"]["sparse"])
        # Vulnerability is single-target by nature -> never sparse
        self.assertFalse(
            self.strip._row_info["Major Vulnerability"]["sparse"])
        # A buff reaching 3+ receivers renders solid
        timeline["effects"]["Major Courage"] = [
            {"start_ms": 0, "end_ms": 10_000, "source": "@h", "target": f"@p{i}"}
            for i in range(4)]
        self.strip.set_timeline(timeline)
        self.assertFalse(self.strip._row_info["Major Courage"]["sparse"])

    def test_merged_spans(self):
        from gui.timeline_strip import merged_spans
        self.assertEqual(merged_spans([]), [])
        self.assertEqual(merged_spans([{"start_ms": 20, "end_ms": 30}, {"start_ms": 0, "end_ms": 10}]),
                         [(0, 10), (20, 30)])
        # Abutting and overlapping spans are joined
        self.assertEqual(merged_spans([{"start_ms": 0, "end_ms": 10}, {"start_ms": 10, "end_ms": 20},
                                       {"start_ms": 15, "end_ms": 30}, {"start_ms": 40, "end_ms": 50}]),
                         [(0, 30), (40, 50)])

    def test_a_sparse_row_is_hatched_without_gaps(self):
        """Issue #45: a buff that reached one or two people is an unbroken,
        cross-hatched span, not the dotted line that read like a buff
        flickering at half uptime; a buff on the whole group is solid."""
        from PySide6.QtGui import QImage

        from gui.timeline_strip import ROW_HEIGHT
        timeline = _sample_timeline()
        timeline["effects"]["Major Courage"] = [
            {"start_ms": 10_000, "end_ms": 30_000, "source": "@h", "target": f"@p{i}"}
            for i in range(4)]
        self.strip.set_timeline(timeline)
        self.strip.resize(600, self.strip.sizeHint().height())
        self.strip.show()
        image = self.strip.grab().toImage().convertToFormat(QImage.Format_ARGB32)

        def coloured(effect, x):
            rect = self.strip._row_rect(self.strip._rows.index(effect))
            rgb = self.strip.row_color(effect).rgb()
            return sum(1 for y in range(int(rect.top()), int(rect.top()) + ROW_HEIGHT)
                       if image.pixel(x, y) == rgb)

        # Force (two receivers, up 10-30s as a union): every column of the
        # span carries the colour and none is solid; Courage (four
        # receivers, the same span) is solid; outside the span, nothing
        x_from = int(self.strip._x_for_ms(10_000)) + 1
        x_to = int(self.strip._x_for_ms(30_000)) - 1
        force = [coloured("Major Force", x) for x in range(x_from, x_to + 1)]
        self.assertTrue(all(1 <= n < ROW_HEIGHT for n in force), force)
        self.assertTrue(all(coloured("Major Courage", x) == ROW_HEIGHT
                            for x in range(x_from, x_to + 1)))
        self.assertEqual(coloured("Major Force", int(self.strip._x_for_ms(40_000))), 0)

    def test_abutting_and_overlapping_sparse_spans_hatch_as_one(self):
        """The union of a sparse row's intervals is painted, so two spans
        that meet or overlap look exactly like the one span they cover: no
        seam, and no darker patch where the translucent base would double."""
        from PySide6.QtGui import QImage

        def rendered(intervals):
            self.strip.set_timeline({"duration_ms": 60_000, "effects": {"Major Force": intervals}})
            self.strip.resize(600, self.strip.sizeHint().height())
            self.strip.show()
            return self.strip.grab().toImage().convertToFormat(QImage.Format_ARGB32)

        one = rendered([{"start_ms": 10_000, "end_ms": 30_000, "source": "@a", "target": "@r1"}])
        two = rendered([{"start_ms": 10_000, "end_ms": 20_000, "source": "@a", "target": "@r1"},
                        {"start_ms": 20_000, "end_ms": 30_000, "source": "@a", "target": "@r2"}])
        lapped = rendered([{"start_ms": 10_000, "end_ms": 25_000, "source": "@a", "target": "@r1"},
                           {"start_ms": 15_000, "end_ms": 30_000, "source": "@b", "target": "@r2"}])
        self.assertEqual(two, one)
        self.assertEqual(lapped, one)

    def test_paint_smoke(self):
        from PySide6.QtGui import QPixmap
        self.strip.set_timeline(_sample_timeline())
        self.strip.show()
        pixmap = QPixmap(self.strip.size())
        self.strip.render(pixmap)  # exercises paintEvent without a screen

    def test_hover_hit_testing_lists_overlapping_intervals(self):
        """Spec scenario: hovering a segment lists all overlapping intervals."""
        from PySide6.QtCore import QPoint
        self.strip.set_timeline(_sample_timeline())
        self.strip.show()
        row_rect = self.strip._row_rect(0)  # Major Force row
        # 18s into a 60s fight: both Force intervals are active
        x = self.strip._x_for_ms(18_000)
        pos = QPoint(int(x), int(row_rect.center().y()))
        found = self.strip._intervals_at(pos)
        self.assertIsNotNone(found)
        effect, ms, hits = found
        self.assertEqual(effect, "Major Force")
        self.assertEqual(len(hits), 2)
        sources = {h["source"] for h in hits}
        self.assertEqual(sources, {"@caster", "@other"})

    def test_hover_outside_intervals_finds_none(self):
        from PySide6.QtCore import QPoint
        self.strip.set_timeline(_sample_timeline())
        self.strip.show()
        row_rect = self.strip._row_rect(0)
        x = self.strip._x_for_ms(55_000)  # after both Force intervals
        found = self.strip._intervals_at(
            QPoint(int(x), int(row_rect.center().y())))
        effect, ms, hits = found
        self.assertEqual(hits, [])

    def test_the_armour_row_is_last_drawn_by_height_with_its_own_hover_and_summary(self):
        """Issue #55: the target's armour less the group's debuffs, by height."""
        from PySide6.QtCore import QEvent, QPoint
        from PySide6.QtGui import QHelpEvent
        from PySide6.QtWidgets import QToolTip
        from gui.timeline_strip import LABEL_WIDTH
        armour = {"name": "Armour", "estimate": 27300, "label": "Armour 27,300 · 15,000",
                  "scope": "boss", "stacks_max": 27300, "game_cap": 25000, "average_left": 15000,
                  "lowest_left": 0, "no_debuff_pct": 33, "target": "Balorgh",
                  "explain": "A solo dungeon's bosses have 27,300 armour.", "intervals": [
                      {"start_ms": 0, "end_ms": 20_000, "stacks": 27300, "debuff_pen": 0,
                       "debuffs": "", "target": "Balorgh", "source": ""},
                      {"start_ms": 20_000, "end_ms": 40_000, "stacks": 18378, "debuff_pen": 8922,
                       "debuffs": "Major Breach, Minor Breach", "target": "Balorgh", "source": ""},
                      {"start_ms": 40_000, "end_ms": 60_000, "stacks": 0, "debuff_pen": 30000,
                       "debuffs": "Major Breach, Crusher", "target": "Balorgh", "source": ""}]}
        tracked = [{"name": "OB", "kind": "uptime", "scope": "boss", "text": "OB:17%",
                    "uptime_pct": 16.7, "max_stacks": 0, "intervals": [
                        {"start_ms": 30_000, "end_ms": 40_000, "stacks": 1, "target": "Test Boss"}]}]
        self.strip.set_timeline(_sample_timeline(), tracked, armour)
        # Last of all, under the debuff rows, with the row's own colour
        self.assertEqual(self.strip._rows, ["Major Force", "Major Vulnerability", "OB", "Armour"])
        info = self.strip._row_info["Armour"]
        self.assertEqual((info["scope"], info["stacks_max"], info["zero_level"]), ("boss", 27300, True))
        self.assertEqual(self.strip.row_color("Armour"), self.strip.armour_color())
        self.strip.show()
        image = self.strip.grab().toImage()
        rect = self.strip._row_rect(3)
        color = self.strip.row_color("Armour").rgb()

        def filled(ms):
            x = int(self.strip._x_for_ms(ms))
            return sum(1 for y in range(int(rect.top()), int(rect.bottom()) + 1)
                       if image.pixel(x, y) == color)

        full, part, none = filled(10_000), filled(30_000), filled(50_000)
        self.assertEqual(full, int(rect.height()))
        self.assertTrue(2 <= part < full, (part, full))
        self.assertLessEqual(none, 1)  # no armour left: a hairline at most
        # Hover on the bar: the armour left at that moment and the debuffs
        pos = QPoint(int(self.strip._x_for_ms(30_000)), int(rect.center().y()))
        self.assertTrue(self.strip.event(QHelpEvent(QEvent.ToolTip, pos, self.strip.mapToGlobal(pos))))
        text = QToolTip.text()
        self.assertIn("18,378 of 27,300 left", text)
        self.assertIn("Major Breach, Minor Breach", text)
        self.assertIn("8,922 off", text)
        # Hover on the label: the whole label and where the estimate comes from
        pos = QPoint(int(LABEL_WIDTH / 2), int(rect.center().y()))
        self.assertTrue(self.strip.event(QHelpEvent(QEvent.ToolTip, pos, self.strip.mapToGlobal(pos))))
        text = QToolTip.text()
        self.assertIn("Armour 27,300 · 15,000", text)
        self.assertIn("solo dungeon's bosses", text)
        # The click summary is the row's own
        html = self.strip.summary_html("Armour")
        self.assertIn("15,000 armour left on average", html)
        self.assertIn("0 at the lowest", html)
        self.assertIn("33% of the fight", html)
        self.assertIn("Balorgh", html)
        # Without the series there is no row
        self.strip.set_timeline(_sample_timeline(), tracked, None)
        self.assertNotIn("Armour", self.strip._rows)
        self.strip.set_timeline(_sample_timeline(), tracked, dict(armour, intervals=[]))
        self.assertNotIn("Armour", self.strip._rows)

    def test_the_armour_row_is_blank_outside_its_window(self):
        """Issue #64: nothing is drawn before the first hit on the target,
        the hover there says so, and the summary names the window."""
        from PySide6.QtCore import QEvent, QPoint
        from PySide6.QtGui import QHelpEvent
        from PySide6.QtWidgets import QToolTip
        armour = {"name": "Armour", "estimate": 27300, "label": "Armour 27,300 · 9,189",
                  "scope": "boss", "stacks_max": 27300, "game_cap": 25000, "average_left": 9189,
                  "lowest_left": 0, "no_debuff_pct": 0, "target": "Balorgh",
                  "window": [[20_000, 30_000], [45_000, 55_000]], "window_ms": [20_000, 55_000],
                  "drawn_ms": 20_000, "fight_ms": 60_000, "weighted_left": 7300,
                  "explain": "A solo dungeon's bosses have 27,300 armour.", "intervals": [
                      {"start_ms": 20_000, "end_ms": 30_000, "stacks": 18378, "debuff_pen": 8922,
                       "debuffs": "Major Breach, Minor Breach", "target": "Balorgh", "source": ""},
                      {"start_ms": 45_000, "end_ms": 55_000, "stacks": 0, "debuff_pen": 30000,
                       "debuffs": "Major Breach, Crusher", "target": "Balorgh", "source": ""}]}
        self.strip.set_timeline(_sample_timeline(), [], armour)
        self.strip.show()
        info = self.strip._row_info["Armour"]
        image = self.strip.grab().toImage()
        rect = self.strip._row_rect(self.strip._rows.index("Armour"))
        color = self.strip.row_color("Armour").rgb()

        def filled(ms):
            x = int(self.strip._x_for_ms(ms))
            return sum(1 for y in range(int(rect.top()), int(rect.bottom()) + 1)
                       if image.pixel(x, y) == color)

        self.assertEqual((filled(10_000), filled(40_000), filled(58_000)), (0, 0, 0))
        self.assertGreater(filled(25_000), 1)

        # Hover on a blank: why there is nothing there
        def hover(ms):
            pos = QPoint(int(self.strip._x_for_ms(ms)), int(rect.center().y()))
            self.assertTrue(self.strip.event(QHelpEvent(QEvent.ToolTip, pos, self.strip.mapToGlobal(pos))))
            return QToolTip.text()

        self.assertIn("Balorgh not yet engaged", hover(10_000))
        self.assertIn("no hits on Balorgh for this stretch", hover(40_000))
        self.assertIn("after the last hit on Balorgh", hover(58_000))
        # The summary names the window and gives the damage-weighted figure
        html = self.strip.summary_html("Armour")
        self.assertIn("from 20s to 55s, 20s of the 1m fight", html)
        self.assertIn("0% of that time", html)
        self.assertIn("7,300 left", html)

    def test_the_pack_reading_is_paler_names_its_unit_and_has_its_own_figures(self):
        """Issue #66: the boss row's blank stretches carry the per-second
        reading on whatever the group hit, drawn paler; its hover names the
        unit and the summary gives the pack's figures beside the boss's."""
        from PySide6.QtCore import QEvent, QPoint
        from PySide6.QtGui import QHelpEvent
        from PySide6.QtWidgets import QToolTip
        armour = {"name": "Armour", "estimate": 27300, "label": "Armour 27,300 · 9,189",
                  "scope": "boss", "stacks_max": 27300, "game_cap": 25000, "average_left": 9189,
                  "lowest_left": 0, "no_debuff_pct": 0, "target": "Balorgh",
                  "window": [[45_000, 55_000]], "window_ms": [45_000, 55_000],
                  "drawn_ms": 10_000, "fight_ms": 60_000, "weighted_left": 7300,
                  "pack_only": False, "pack_units": 3, "pack_window": [[5_000, 30_000]],
                  "pack_window_ms": [5_000, 30_000], "pack_drawn_ms": 25_000,
                  "pack_average_left": 20_000, "pack_lowest_left": 15_000, "pack_no_debuff_pct": 40,
                  "pack_weighted_left": 19_000,
                  "explain": "A solo dungeon's bosses have 27,300 armour.", "intervals": [
                      {"start_ms": 5_000, "end_ms": 20_000, "stacks": 27300, "debuff_pen": 0,
                       "debuffs": "", "target": "Wyress Strigidae", "source": "", "pack": True,
                       "unit_armour": 18200},
                      {"start_ms": 20_000, "end_ms": 30_000, "stacks": 15000, "debuff_pen": 12300,
                       "debuffs": "Major Breach, Crusher", "target": "Hagraven", "source": "", "pack": True,
                       "unit_armour": 18200},
                      {"start_ms": 45_000, "end_ms": 55_000, "stacks": 0, "debuff_pen": 30000,
                       "debuffs": "Major Breach, Crusher", "target": "Balorgh", "source": ""}]}
        self.strip.set_timeline(_sample_timeline(), [], armour)
        self.strip.show()
        info = self.strip._row_info["Armour"]
        image = self.strip.grab().toImage()
        rect = self.strip._row_rect(self.strip._rows.index("Armour"))

        def column(ms):
            x = int(self.strip._x_for_ms(ms))
            return [image.pixel(x, y) for y in range(int(rect.top()), int(rect.bottom()) + 1)]

        boss = self.strip.row_color("Armour").rgb()
        # The pack stretch is drawn, in a colour that is not the boss bar's
        pack_pixels = [p for p in column(10_000) if p != image.pixel(int(self.strip._x_for_ms(40_000)), int(rect.top()))]
        self.assertGreater(len(pack_pixels), 1)
        self.assertNotIn(boss, pack_pixels)
        self.assertEqual(sum(1 for p in column(40_000) if p == boss), 0)

        def hover(ms):
            pos = QPoint(int(self.strip._x_for_ms(ms)), int(rect.center().y()))
            self.assertTrue(self.strip.event(QHelpEvent(QEvent.ToolTip, pos, self.strip.mapToGlobal(pos))))
            return QToolTip.text()

        text = hover(25_000)
        self.assertIn("15,000 of 27,300 left on Hagraven", text)
        self.assertIn("Major Breach, Crusher", text)
        self.assertIn("Read on the unit the group hit hardest that second", text)
        self.assertIn("its armour is 18,200, the row's scale the 27,300 of its target", text)
        # A blank stretch of a row with the pack reading: nothing was hit
        self.assertIn("the group hit nothing for this stretch", hover(40_000))
        html = self.strip.summary_html("Armour")
        self.assertIn("On Balorgh from 45s to 55s", html)
        self.assertIn("The paler 25s, read each second on whichever of 3 other units the group hit hardest: "
                      "20,000 left on average, 15,000 at the lowest; no armour debuff for 40% of that time. "
                      "Weighed by the damage dealt: 19,000 left", html)
        # A fight without a boss: the row is the pack reading
        trash = dict(armour, scope="mobs", pack_only=True, window=[[5_000, 30_000]],
                     window_ms=[5_000, 30_000], drawn_ms=25_000, average_left=20_000,
                     label="Armour 18,200 · 20,000", intervals=armour["intervals"][:2])
        self.strip.set_timeline(_sample_timeline(), [], trash)
        html = self.strip.summary_html("Armour")
        self.assertIn("Read each second on the unit the group hit hardest, 3 units in all, from 5s to 30s", html)
        self.assertNotIn("The paler", html)

    def test_help_event_shows_tooltip(self):
        """QHelpEvent path end-to-end (task 2.2)."""
        from PySide6.QtCore import QEvent, QPoint
        from PySide6.QtGui import QHelpEvent
        from PySide6.QtWidgets import QToolTip
        self.strip.set_timeline(_sample_timeline())
        self.strip.show()
        row_rect = self.strip._row_rect(1)  # Major Vulnerability row
        pos = QPoint(int(self.strip._x_for_ms(30_000)),
                     int(row_rect.center().y()))
        ev = QHelpEvent(QEvent.ToolTip, pos, self.strip.mapToGlobal(pos))
        handled = self.strip.event(ev)
        self.assertTrue(handled)
        text = QToolTip.text()
        self.assertIn("Major Vulnerability", text)
        self.assertIn("@caster", text)
        self.assertIn("Test Boss", text)
        self.assertIn("Click for who applied it", text)

    def test_a_click_on_a_row_opens_its_sources_and_targets(self):
        """Issue #19: a single click, label or bar, opens a transient popup."""
        from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
        from PySide6.QtTest import QTest
        from gui.timeline_strip import SummaryPopup
        self.strip.set_timeline(_sample_timeline())
        self.strip.show()
        y = int(self.strip._row_rect(0).center().y())  # Major Force
        self.assertEqual(self.strip._row_at(QPointF(10, y)), "Major Force")
        self.assertEqual(self.strip._row_at(QPointF(self.strip._x_for_ms(50_000), y)),
                         "Major Force")
        self.assertIsNone(self.strip._row_at(QPointF(10, self.strip.height() - 2)))
        QTest.mouseClick(self.strip, Qt.LeftButton, pos=QPoint(10, y))
        popups = self.strip.findChildren(SummaryPopup)
        self.assertEqual(len(popups), 1)
        popup = popups[0]
        self.assertTrue(popup.isVisible())
        self.assertTrue(popup.windowFlags() & Qt.Popup)
        text = popup.label.text()
        for name in ("Major Force", "@caster", "@other", "@receiver", "@receiver2"):
            self.assertIn(name, text)
        # Esc closes it, and it deletes itself
        QTest.keyClick(popup, Qt.Key_Escape)
        self.assertFalse(popup.isVisible())
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertEqual(self.strip.findChildren(SummaryPopup), [])

    def test_summary_text_for_a_sparse_row_and_a_stacking_rule(self):
        tracked = [{"name": "Crux", "kind": "stacks", "scope": "self", "text": "Crux:2.0/3",
                    "uptime_pct": 66.7, "max_stacks": 3, "intervals": [
                        {"start_ms": 0, "end_ms": 20_000, "stacks": 1, "target": "@me", "source": "@me"},
                        {"start_ms": 20_000, "end_ms": 40_000, "stacks": 3, "target": "@me"}]}]
        self.strip.set_timeline(_sample_timeline(), tracked)
        force = self.strip.summary_html("Major Force")
        self.assertIn("Hatched: reached only 2 receivers", force)
        self.assertIn("Up 33%", force)
        # Two casters on two receivers: the grid is shown
        self.assertIn("On \\ by", force)
        crux = self.strip.summary_html("Crux")
        self.assertIn("×3", crux)
        self.assertIn("unknown source", crux)  # a span saved without a caster
        self.assertNotIn("Hatched", crux)


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestStripIsAlwaysOn(unittest.TestCase):
    """Issue #25: the strip is the only view of the rules, with no switch."""

    def test_the_old_switch_is_dropped_from_a_config_either_way(self):
        import json
        import tempfile
        from pathlib import Path
        _ensure_app()
        from app_config import AppConfig
        from app_startup import build_analyzer
        from gui.settings_dialog import SettingsDialog
        for old in (False, True):
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / 'config.json'
                path.write_text(json.dumps({"experimental": {"buff_timeline": old}}), encoding="utf-8")
                config = AppConfig(path=path)
                self.assertIsNone(config.get('experimental.buff_timeline'))
                self.assertTrue(build_analyzer(config, []).track_buff_timeline)
                dialog = SettingsDialog(config)
                self.assertFalse(hasattr(dialog, 'buff_timeline'))  # no checkbox
                dialog.apply_to_config()
                config.save()
                self.assertNotIn('experimental', json.loads(path.read_text(encoding="utf-8")))
                dialog.deleteLater()

    def test_a_fight_without_a_recorded_timeline_still_draws_its_rules(self):
        from fight_history import FightHistoryEntry
        from gui.timeline_strip import TimelineStrip, strip_timeline
        entry = FightHistoryEntry()
        entry.duration_s = 60.0
        entry.tracked = [{"name": "Crux", "kind": "stacks", "scope": "self", "text": "Crux:1.0/1",
                          "uptime_pct": 50.0, "max_stacks": 1,
                          "intervals": [{"start_ms": 0, "end_ms": 30_000, "stacks": 1, "target": "@me"}]}]
        self.assertEqual(strip_timeline(entry), {"duration_ms": 60_000, "effects": {}})
        recorded = {"duration_ms": 60_000, "effects": {"Major Force": []}}
        entry.buff_timeline = recorded
        self.assertIs(strip_timeline(entry), recorded)
        entry.buff_timeline = None
        strip = TimelineStrip()
        strip.set_timeline(strip_timeline(entry), entry.tracked)
        self.assertEqual(strip._rows, ["Crux"])
        strip.deleteLater()


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestTrackedRows(unittest.TestCase):
    """Rows for the user's tracked effects (effect_rules), after the built-in ones."""

    def setUp(self):
        _ensure_app()
        from gui.timeline_strip import TimelineStrip
        self.strip = TimelineStrip()
        self.strip.resize(600, 100)

    def tearDown(self):
        self.strip.deleteLater()

    def test_tracked_effects_are_rows_after_the_built_in_ones(self):
        tracked = [
            {"name": "Crux", "kind": "stacks", "scope": "self", "text": "Crux:2.0/3",
             "uptime_pct": 75.0, "max_stacks": 3, "intervals": [
                 {"start_ms": 0, "end_ms": 20_000, "stacks": 1, "target": "@me"},
                 {"start_ms": 20_000, "end_ms": 40_000, "stacks": 3, "target": "@me"}]},
            {"name": "Never", "kind": "uptime", "scope": "group", "text": "Never:0%", "uptime_pct": 0.0,
             "max_stacks": 0, "intervals": []},
            {"name": "OB", "kind": "uptime", "scope": "boss", "text": "OB:17%", "uptime_pct": 16.7,
             "max_stacks": 0, "intervals": [
                 {"start_ms": 30_000, "end_ms": 40_000, "stacks": 1, "target": "Test Boss"}]},
        ]
        self.strip.set_timeline(_sample_timeline(), tracked)
        # A rule that never occurred has no row, as for a built-in effect;
        # the rules follow the built-in rows on their side
        self.assertEqual(self.strip._rows, ["Major Force", "Crux", "Major Vulnerability", "OB"])
        self.assertEqual(self.strip._row_info["Crux"]["label"], "Crux:2.0/3")
        self.assertEqual(self.strip._row_info["OB"]["uptime_pct"], 17)
        # Hover on a tracked row names the unit and the stacks
        found = self.strip._intervals_at(self.strip._row_rect(self.strip._rows.index("Crux")).center())
        self.assertEqual(found[0], "Crux")
        self.assertEqual([iv["stacks"] for iv in found[2]], [3])

    def test_buffs_above_debuffs_with_a_divider_between(self):
        """Issue #26: our side's effects first, the enemy's after, each in
        the order it came in, a divider only when both sides have rows."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from gui.timeline_strip import DIVIDER_GAP, SummaryPopup

        def rule(name, scope, units=None):
            item = {"name": name, "kind": "uptime", "scope": scope, "text": f"{name}:10%",
                    "uptime_pct": 10.0, "max_stacks": 0,
                    "intervals": [{"start_ms": 0, "end_ms": 6_000, "stacks": 1, "target": "x"}]}
            if units:
                item["units"] = units
            return item

        timeline = _sample_timeline()
        timeline["effects"]["Taunt"] = [{"start_ms": 0, "end_ms": 1_000, "source": "@t", "target": "B"}]
        tracked = [rule("Echoes", "group"), rule("OB", "boss"), rule("Crux", "self"),
                   rule("Alkosh", "boss", units="mobs"), rule("Pets", "pets"), rule("Hostile", "enemies")]
        self.strip.set_timeline(timeline, tracked)
        self.assertEqual(self.strip._rows, ["Major Force", "Echoes", "Crux", "Pets",
                                            "Major Vulnerability", "Taunt", "OB", "Alkosh", "Hostile"])
        self.assertEqual(self.strip._divider, 4)
        # The first debuff row sits a divider's height lower than a row would
        above, below = self.strip._row_rect(3), self.strip._row_rect(4)
        self.assertEqual(below.top() - above.top(), above.height() + 2 + DIVIDER_GAP)
        self.assertTrue(above.bottom() < self.strip._divider_y() < below.top())
        # A click on the first debuff row opens that row's summary
        self.strip.resize(600, self.strip.sizeHint().height())
        self.strip.show()
        QTest.mouseClick(self.strip, Qt.LeftButton, pos=below.center().toPoint())
        [popup] = self.strip.findChildren(SummaryPopup)
        self.assertIn("Major Vulnerability", popup.label.text())
        popup.close()
        self.strip.grab()  # paints the divider without error
        # One side alone: no divider, no gap
        self.strip.set_timeline({"duration_ms": 60_000, "effects": {}}, [rule("OB", "boss"), rule("Alkosh", "boss")])
        self.assertIsNone(self.strip._divider)
        self.assertIsNone(self.strip._divider_y())
        self.assertEqual(self.strip._row_rect(1).top() - self.strip._row_rect(0).top(),
                         self.strip._row_rect(0).height() + 2)

    def test_shown_items_get_rows_and_an_expected_absent_one_is_empty(self):
        """Issue #13: a shown item has a row, empty when its effect never
        came; an item not shown has none."""
        tracked = [
            {"name": "Lucent Echoes", "kind": "uptime", "scope": "group", "text": "Lucent Echoes:0%",
             "uptime_pct": 0.0, "max_stacks": 0, "seen": False, "expected": True, "shown": True,
             "intervals": []},
            {"name": "Alkosh", "kind": "uptime", "scope": "boss", "text": "Alkosh:0%",
             "uptime_pct": 0.0, "max_stacks": 0, "seen": False, "expected": False, "shown": False,
             "intervals": []},
        ]
        self.strip.set_timeline({"duration_ms": 60_000, "effects": {}}, tracked)
        self.assertEqual(self.strip._rows, ["Lucent Echoes"])
        self.assertEqual(self.strip._row_info["Lucent Echoes"]["label"], "Lucent Echoes:0%")
        self.assertIn("Not up in this fight", self.strip.summary_html("Lucent Echoes"))
        self.strip.show()
        self.strip.grab()  # an empty track paints

    def test_an_expected_row_at_zero_is_marked_missing_and_painted_red(self):
        """An expected rule whose effect never came is marked missing, so
        its label is painted red and bold; an expected rule that was up,
        and an unexpected one at 0% that is shown anyway, are not."""
        from PySide6.QtGui import QColor, QImage
        tracked = [
            {"name": "Lucent Echoes", "kind": "uptime", "scope": "group", "text": "Lucent Echoes:0%",
             "uptime_pct": 0.0, "max_stacks": 0, "seen": False, "expected": True, "shown": True,
             "intervals": []},
            {"name": "Major Courage", "kind": "uptime", "scope": "group", "text": "Major Courage:80%",
             "uptime_pct": 80.0, "max_stacks": 1, "seen": True, "expected": True, "shown": True,
             "intervals": [{"start_ms": 0, "end_ms": 48_000, "source": "@a", "target": "@b"}]},
            {"name": "Nearly", "kind": "uptime", "scope": "group", "text": "Nearly:0%",
             "uptime_pct": 0.4, "max_stacks": 1, "seen": True, "expected": True, "shown": True,
             "intervals": [{"start_ms": 0, "end_ms": 240, "source": "@a", "target": "@b"}]},
            {"name": "Alkosh", "kind": "uptime", "scope": "boss", "text": "Alkosh:0%",
             "uptime_pct": 0.0, "max_stacks": 0, "seen": False, "expected": False, "shown": True,
             "intervals": []},
        ]
        self.strip.set_timeline({"duration_ms": 60_000, "effects": {}}, tracked)
        self.assertTrue(self.strip._row_info["Lucent Echoes"]["missing"])
        self.assertTrue(self.strip._row_info["Nearly"]["missing"], "rounds to 0%")
        self.assertFalse(self.strip._row_info["Major Courage"]["missing"])
        self.assertFalse(self.strip._row_info["Alkosh"]["missing"], "not expected")
        # The label column of the missing row carries the red; the row that
        # was up does not
        self.strip.show()
        image = self.strip.grab().toImage().convertToFormat(QImage.Format_ARGB32)
        red = self.strip.missing_color()

        def has_red(row):
            rect = self.strip._row_rect(row)
            for y in range(int(rect.top()) - 1, int(rect.bottom()) + 2):
                for x in range(int(rect.left())):
                    if QColor(image.pixel(x, y)) == red:
                        return True
            return False

        rows = self.strip._rows
        self.assertTrue(has_red(rows.index("Lucent Echoes")))
        self.assertFalse(has_red(rows.index("Major Courage")))

    def test_missing_color_follows_the_palette(self):
        """Dark red on a light pane, a lighter red on a dark one."""
        from PySide6.QtGui import QColor

        from gui.timeline_strip import MISSING_COLORS
        palette = self.strip.palette()
        palette.setColor(self.strip.backgroundRole(), QColor("#ffffff"))
        self.strip.setPalette(palette)
        self.assertEqual(self.strip.missing_color(), MISSING_COLORS[False])
        palette.setColor(self.strip.backgroundRole(), QColor("#202020"))
        self.strip.setPalette(palette)
        self.assertEqual(self.strip.missing_color(), MISSING_COLORS[True])

    def test_a_dots_rule_is_drawn_against_five_with_zero_a_level(self):
        tracked = [{"name": "Zen", "kind": "dots", "scope": "boss", "text": "Zen:2.5/5",
                    "uptime_pct": 100.0, "max_stacks": 5, "shown": True, "intervals": [
                        {"start_ms": 0, "end_ms": 30_000, "stacks": 0, "target": "Boss", "source": "@a"},
                        {"start_ms": 30_000, "end_ms": 60_000, "stacks": 5, "target": "Boss", "source": "@a"}]}]
        self.strip.set_timeline({"duration_ms": 60_000, "effects": {}}, tracked)
        self.assertEqual(self.strip._row_info["Zen"]["stacks_max"], 5)
        self.strip.show()
        image = self.strip.grab().toImage()
        rect = self.strip._row_rect(0)
        color = self.strip.row_color("Zen").rgb()

        def filled(ms):
            x = int(self.strip._x_for_ms(ms))
            return sum(1 for y in range(int(rect.top()), int(rect.bottom()) + 1)
                       if image.pixel(x, y) == color)

        self.assertEqual(filled(45_000), int(rect.height()))
        self.assertLessEqual(filled(15_000), 1)  # zero DoTs: a hairline at most
        from PySide6.QtCore import QPoint
        found = self.strip._intervals_at(QPoint(int(self.strip._x_for_ms(15_000)), int(rect.center().y())))
        self.assertEqual([iv["stacks"] for iv in found[2]], [0])

    def test_a_stacking_rule_is_drawn_by_height(self):
        tracked = [{"name": "Crux", "kind": "stacks", "text": "Crux:2.0/3", "uptime_pct": 100.0,
                    "max_stacks": 3, "intervals": [
                        {"start_ms": 0, "end_ms": 30_000, "stacks": 1, "target": "@me"},
                        {"start_ms": 30_000, "end_ms": 60_000, "stacks": 3, "target": "@me"}]}]
        self.strip.set_timeline(_sample_timeline(), tracked)
        self.strip.show()
        image = self.strip.grab().toImage()
        rect = self.strip._row_rect(self.strip._rows.index("Crux"))
        color = self.strip.row_color("Crux").rgb()

        def filled_height(ms):
            x = int(self.strip._x_for_ms(ms))
            return sum(1 for y in range(int(rect.top()), int(rect.bottom()) + 1)
                       if image.pixel(x, y) == color)

        one, three = filled_height(15_000), filled_height(45_000)
        self.assertEqual(three, int(rect.height()))
        self.assertTrue(2 <= one <= three // 2, (one, three))

    def test_tracked_rows_alone_need_the_timeline_on(self):
        tracked = [{"name": "OB", "kind": "uptime", "text": "OB:17%", "uptime_pct": 16.7,
                    "max_stacks": 0, "intervals": [{"start_ms": 0, "end_ms": 10, "stacks": 1, "target": "x"}]}]
        self.strip.set_timeline(None, tracked)
        self.assertEqual(self.strip._rows, [])
        self.strip.set_timeline({"duration_ms": 60_000, "effects": {}}, tracked)
        self.assertEqual(self.strip._rows, ["OB"])

    def test_every_row_names_whose_effect_it_is(self):
        from gui.timeline_strip import LABEL_WIDTH, SCOPE_WIDTH
        tracked = [{"name": "Crux", "kind": "stacks", "scope": "self", "text": "Crux:2.0/3",
                    "uptime_pct": 75.0, "max_stacks": 3,
                    "intervals": [{"start_ms": 0, "end_ms": 20_000, "stacks": 1, "target": "@me"}]},
                   # A boss rule measured on the pack of a fight without a boss
                   {"name": "Alkosh", "kind": "uptime", "scope": "boss", "units": "mobs",
                    "text": "Alkosh:17% on 3 of 7 mobs", "uptime_pct": 16.7, "max_stacks": 0,
                    "intervals": [{"start_ms": 0, "end_ms": 10_000, "stacks": 1, "target": "Deckhand"}]}]
        self.strip.set_timeline(_sample_timeline(), tracked)
        scopes = {row: self.strip._row_info[row]["scope"] for row in self.strip._rows}
        self.assertEqual(scopes, {"Major Force": "group", "Major Vulnerability": "boss",
                                  "Crux": "self", "Alkosh": "mobs"})
        # The scope column sits between the label and the track
        self.assertEqual(self.strip._track_rect().left(), LABEL_WIDTH + SCOPE_WIDTH)
        self.strip.show()
        self.strip.grab()  # paints the scope words without error

    def test_a_label_that_does_not_fit_is_cut_and_shown_whole_on_hover(self):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QFontMetrics
        from gui.timeline_strip import LABEL_WIDTH, SCOPE_WIDTH
        text = "Off-Balance:11% on 2 of 11 mobs"
        tracked = [{"name": "Off-Balance", "kind": "uptime", "scope": "boss", "units": "mobs",
                    "text": text, "uptime_pct": 11.0, "max_stacks": 0,
                    "intervals": [{"start_ms": 0, "end_ms": 5_000, "stacks": 1, "target": "Reaver"}]}]
        self.strip.set_timeline(_sample_timeline(), tracked)
        row = self.strip._rows.index("Off-Balance")
        info = self.strip._row_info["Off-Balance"]
        metrics = QFontMetrics(self.strip._label_font())  # the font the labels are painted in
        painted = self.strip._painted_label("Off-Balance", info, metrics)
        self.assertTrue(painted.endswith("…") and len(painted) < len(text), painted)
        self.assertTrue(painted.startswith("Off-Bal"), painted)
        # Hovering the label, or the scope word beside it, gives the whole text
        y = self.strip._row_rect(row).center().y()
        self.assertEqual(self.strip._label_at(QPointF(LABEL_WIDTH / 2, y)), (text, "mobs"))
        self.assertEqual(self.strip._label_at(QPointF(LABEL_WIDTH + 5, y)), (text, "mobs"))
        self.assertIsNone(self.strip._label_at(QPointF(LABEL_WIDTH + SCOPE_WIDTH + 5, y)))
        # A built-in row is drawn short and hovers as its full name
        force = self.strip._row_info["Major Force"]
        self.assertEqual(self.strip._painted_label("Major Force", force, metrics), "M.Force 33%")
        self.assertEqual(self.strip._label_at(QPointF(LABEL_WIDTH / 2, self.strip._row_rect(0).center().y())),
                         ("Major Force 33%", "group"))


if __name__ == '__main__':
    unittest.main()
