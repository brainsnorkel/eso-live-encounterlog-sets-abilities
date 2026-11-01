#!/usr/bin/env python3
"""The fight history in the window (issue #170), offscreen: the pull's
line under the header, a player's last kills in their name's hover, the
run row's best kill with this roster, the window writing the index beside
its config, and Settings' Build from split logs."""

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

ROSTER = [f"@p{i}" for i in range(12)]


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _entry(start_s, outcome="kill", boss_dps=450_000.0, roster=ROSTER):
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = "Lord Falgravn"
    entry.zone_name = "Kyne's Aegis"
    entry.zone_id = "1196"
    entry.difficulty = "VETERAN"
    entry.is_vet = True
    entry.game_version = "eso.live.12.1"
    entry.timestamp = "2026-10-31 21:39:00"
    entry.duration_s = 180.0
    entry.group_dps = boss_dps * 1.2
    entry.group_boss_dps = boss_dps
    entry.pull = {"boss": "Lord Falgravn", "bosses": ["Lord Falgravn"], "outcome": outcome,
                  "health_left": 0.0 if outcome == "kill" else 62.0, "players": len(roster),
                  "start_s": start_s, "end_s": start_s + 180.0, "continues": False,
                  "cut": False, "went_on": False}
    entry.player_names = [{"name": h, "character": h[1:], "is_local": h == "@p0"} for h in roster]
    entry.players = [
        {"role": "D", "name": h, "class_abbr": "NB", "dps": boss_dps / 10, "boss_dps": boss_dps / 12,
         "dmg_pct": 8.0, "h": 20000, "m": 30000, "s": 15000, "unit_id": str(i), "sets": [],
         "all_sets": [], "skill_lines": [], "class_lines": [], "front_bar": [], "back_bar": [],
         "front_bar_slots": [], "back_bar_slots": [], "is_local": h == "@p0"}
        for i, h in enumerate(roster)]
    return entry


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestPaneAndList(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        import fight_index as fi
        self.tmp = tempfile.TemporaryDirectory()
        self.index = fi.FightIndex(Path(self.tmp.name) / fi.INDEX_NAME)
        for start, dps in ((100.0, 400_000), (200.0, 480_000), (250.0, 460_000)):
            self.index.add(fi.fight_line(_entry(start, boss_dps=dps)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_line_under_the_header(self):
        import fight_index as fi
        from gui.fight_render import render_html
        entry = _entry(300.0, boss_dps=512_000)
        line = fi.comparison_text(fi.comparison(self.index, entry))
        page = render_html(entry, detailed=False, history=line)
        # Every earlier kill had this roster on this version: the set is
        # said once, named
        self.assertIn("Your Lord Falgravn kills, all with 8+ of this roster on 12.1: median 460.0k "
                      "over 3, best 480.0k. This pull: 512.0k", page)
        self.assertLess(page.index("Deaths"), page.index("Your Lord Falgravn kills"))
        self.assertNotIn("Your Lord Falgravn", render_html(entry, detailed=False))

    def test_a_players_last_kills_in_the_name_hover(self):
        import fight_index as fi
        from gui.fight_render import build_href, build_tooltips
        from gui.name_mask import NameMask
        entry = _entry(300.0)
        names = NameMask.for_entry(entry, True)
        text = fi.player_history_text(entry, "@p3", fi.player_history(self.index, entry, "@p3"),
                                      names)
        tips = build_tooltips(entry, names, {"3": text})
        self.assertIn("in their last three kills with you", tips[build_href("3")])
        self.assertNotIn("@p3", tips[build_href("3")])

    def test_the_run_row_names_the_best_kill_with_this_roster(self):
        from gui.fight_list import KIND_ROLE, RUN, FightList
        view = FightList()
        view.history_index = self.index
        view.add_fight(_entry(300.0, outcome="wipe"))
        view.add_fight(_entry(400.0, outcome="wipe"))
        runs = [view.item(r).text() for r in range(view.count())
                if view.item(r).data(KIND_ROLE) == RUN]
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0].endswith(", best kill with this roster 480.0k"))
        view.deleteLater()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestWindow(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        from app_config import AppConfig
        from gui.main_window import MainWindow
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        config = AppConfig(path=root / "config.json")
        config.set("log_path", str(root / "Encounter.log"))
        config.set("update.check_enabled", False)
        config.set("split.dir", str(root / "splits"))
        self.root = root
        self.win = MainWindow(config)
        self.win.worker_thread.quit()
        self.win.worker_thread.wait(3000)

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()
        self.tmp.cleanup()

    def test_live_fights_go_to_the_index_beside_the_config(self):
        import fight_index as fi
        self.win._on_fight_completed(_entry(100.0, boss_dps=400_000))
        self.win._on_fight_completed(_entry(200.0, boss_dps=480_000))
        path = self.root / fi.INDEX_NAME
        lines = [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([line["key"] for line in lines], ["100.000", "200.000"])
        # The same fight again (a restart's replay) adds nothing
        self.win._on_fight_updated(self.win._fights[-1])
        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)
        # The newest fight on screen is read against the one before it
        self.assertIn("Your earlier Lord Falgravn kill: 400.0k. This pull: 480.0k",
                      self.win.fight_view.toHtml())

    def test_settings_offers_the_build_from_split_logs(self):
        from gui.settings_dialog import SettingsDialog
        started = []
        dialog = SettingsDialog(self.win.config, self.win, history_status=self.win.history_status(),
                                on_build_history=lambda folder: (started.append(folder) or True, "Building"))
        self.assertIn("No boss fights yet", dialog.history_status.text())
        dialog.build_history_button.click()
        self.assertEqual(len(started), 1)
        self.assertEqual(dialog.history_status.text(), "Building")
        self.assertFalse(dialog.build_history_button.isEnabled())
        dialog.deleteLater()

    def test_no_split_folder_no_build(self):
        started, message = self.win.start_backfill()  # the folder does not exist
        self.assertFalse(started)
        self.assertIn("no split folder", message)

    def test_a_build_from_split_logs_on_the_review_thread(self):
        import time

        from tests.unit.test_fight_index import _log
        splits = self.root / "splits"
        splits.mkdir()
        (splits / "260101200000-Kyne's-Aegis-vet.log").write_text(_log(0), encoding="utf-8")
        (splits / "260102200000-Kyne's-Aegis-vet.log").write_text(_log(86_400_000),
                                                                   encoding="utf-8")
        started, message = self.win.start_backfill()
        self.assertTrue(started, message)
        self.assertFalse(self.win.review_cancel_button.isHidden())  # Cancel stops it
        self.assertEqual(self.win.start_backfill()[0], False)  # one at a time
        self.win._review.wait(30)
        deadline = time.monotonic() + 10
        while self.win._backfilling and time.monotonic() < deadline:
            QApplication.processEvents()  # the review thread's events
        self.assertFalse(self.win._backfilling)
        self.assertEqual(len(self.win.fight_index), 2)
        self.assertEqual(self.win.statusBar().currentMessage(),
                         "Fight history: 2 fights from 2 split logs")
        self.assertTrue(self.win.history_status().startswith("2 boss fights on 2 days"))
        self.assertTrue(self.win.review_cancel_button.isHidden())


if __name__ == "__main__":
    unittest.main()
