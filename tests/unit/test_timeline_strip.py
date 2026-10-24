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
        self.assertEqual(self.strip._row_info["Taunt"], {"uptime_pct": 75, "dotted": False, "scope": "boss"})

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

    def test_dotted_for_sparse_receivers(self):
        timeline = _sample_timeline()
        # Force reaches 2 distinct receivers -> dotted
        self.strip.set_timeline(timeline)
        self.assertTrue(self.strip._row_info["Major Force"]["dotted"])
        # Vulnerability is single-target by nature -> never dotted
        self.assertFalse(
            self.strip._row_info["Major Vulnerability"]["dotted"])
        # A buff reaching 3+ receivers renders solid
        timeline["effects"]["Major Courage"] = [
            {"start_ms": 0, "end_ms": 10_000, "source": "@h", "target": f"@p{i}"}
            for i in range(4)]
        self.strip.set_timeline(timeline)
        self.assertFalse(self.strip._row_info["Major Courage"]["dotted"])

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

    def test_summary_text_for_a_dotted_row_and_a_stacking_rule(self):
        tracked = [{"name": "Crux", "kind": "stacks", "scope": "self", "text": "Crux:2.0/3",
                    "uptime_pct": 66.7, "max_stacks": 3, "intervals": [
                        {"start_ms": 0, "end_ms": 20_000, "stacks": 1, "target": "@me", "source": "@me"},
                        {"start_ms": 20_000, "end_ms": 40_000, "stacks": 3, "target": "@me"}]}]
        self.strip.set_timeline(_sample_timeline(), tracked)
        force = self.strip.summary_html("Major Force")
        self.assertIn("Dotted: reached only 2 receivers", force)
        self.assertIn("Up 33%", force)
        # Two casters on two receivers: the grid is shown
        self.assertIn("On \\ by", force)
        crux = self.strip.summary_html("Crux")
        self.assertIn("×3", crux)
        self.assertIn("unknown source", crux)  # a span saved without a caster
        self.assertNotIn("Dotted", crux)


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

    def test_a_stacking_rule_is_drawn_by_height(self):
        from gui.timeline_strip import TRACKED_COLORS
        tracked = [{"name": "Crux", "kind": "stacks", "text": "Crux:2.0/3", "uptime_pct": 100.0,
                    "max_stacks": 3, "intervals": [
                        {"start_ms": 0, "end_ms": 30_000, "stacks": 1, "target": "@me"},
                        {"start_ms": 30_000, "end_ms": 60_000, "stacks": 3, "target": "@me"}]}]
        self.strip.set_timeline(_sample_timeline(), tracked)
        self.strip.show()
        image = self.strip.grab().toImage()
        rect = self.strip._row_rect(self.strip._rows.index("Crux"))
        color = TRACKED_COLORS[0].rgb()

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
