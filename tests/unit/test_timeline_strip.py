#!/usr/bin/env python3
"""Offscreen tests for the experimental TimelineStrip widget."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

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


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestSettingsToggle(unittest.TestCase):
    """Task 3.1: experimental checkbox round-trips through AppConfig."""

    def test_round_trip(self):
        import tempfile
        from pathlib import Path
        _ensure_app()
        from app_config import AppConfig
        from gui.settings_dialog import SettingsDialog
        with tempfile.TemporaryDirectory() as td:
            config = AppConfig(path=Path(td) / 'config.json')
            self.assertFalse(config.get('experimental.buff_timeline'))

            dialog = SettingsDialog(config)
            self.assertFalse(dialog.buff_timeline.isChecked())  # default off
            dialog.buff_timeline.setChecked(True)
            dialog.apply_to_config()
            config.save()

            reloaded = AppConfig(path=config.path)
            self.assertTrue(reloaded.get('experimental.buff_timeline'))
            dialog.deleteLater()


if __name__ == '__main__':
    unittest.main()
