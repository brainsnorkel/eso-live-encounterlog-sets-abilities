#!/usr/bin/env python3
"""Saving settings while the engine is still replaying a log.

The engine thread runs its slots one after another, so the restart Save
asks for begins only once the replay in progress has finished, and that
replay keeps sending fights meanwhile. The window used to clear its
history the moment Save was pressed, so those fights refilled it and the
new analyzer's fights were listed under them (seen 2026-10-09: a session
listed twice, the first copy without timelines). The history is now
cleared when the engine says the restart has begun, and fights sent
before that are dropped.
"""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QDialog
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

from app_config import AppConfig
from fight_history import FightHistoryEntry


def _fight(boss, stamp):
    entry = FightHistoryEntry()
    entry.boss_name = boss
    entry.zone_name = "Sunspire"
    entry.timestamp = stamp
    entry.duration_s = 20.0
    entry.group_dps = 100000.0
    return entry


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestSaveDuringAReplay(unittest.TestCase):

    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.tmp = tempfile.TemporaryDirectory()
        self.config = AppConfig(path=Path(self.tmp.name) / "config.json")
        self.config.set("log_path", str(Path(self.tmp.name) / "Encounter.log"))
        from gui.main_window import MainWindow
        self.win = MainWindow(self.config)
        # Tests drive the window's slots directly on this thread
        self.win.worker_thread.quit()
        self.win.worker_thread.wait(3000)

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def _press_save(self):
        def accept():
            dialog = next((w for w in self.app.topLevelWidgets()
                           if isinstance(w, QDialog) and w.isVisible()
                           and hasattr(w, "buff_timeline")), None)
            if dialog is None:
                QTimer.singleShot(10, accept)
            else:
                dialog.accept()
        QTimer.singleShot(0, accept)
        self.win._open_settings()

    def _listed(self):
        return [self.win.history_list.item(i).text().split(" · ")[0]
                for i in range(self.win.history_list.count())]

    def test_fights_from_the_old_replay_are_dropped_and_the_new_ones_listed(self):
        win = self.win
        win._on_fight_completed(_fight("Alkosh's Roar", "2026-08-30 13:58:42"))
        win._on_fight_completed(_fight("Alkosh's Fate", "2026-08-30 13:59:03"))
        self.assertEqual(self._listed(), ["Alkosh's Roar", "Alkosh's Fate"])

        self._press_save()
        # The old analyzer is still replaying: its remaining fights arrive
        # before the engine reaches the restart, and are not listed
        stale = _fight("Lokkestiiz", "2026-08-30 14:03:20")
        win._on_fight_completed(stale)
        win._on_fight_updated(stale)
        self.assertEqual(self._listed(), ["Alkosh's Roar", "Alkosh's Fate"])

        # The engine begins the restart: the history is cleared here
        win._on_monitoring_restarting()
        self.assertEqual(self._listed(), [])
        self.assertEqual(win._fights, [])

        # The new analyzer's replay fills it
        win._on_fight_completed(_fight("Alkosh's Roar", "2026-08-30 13:58:42"))
        self.assertEqual(self._listed(), ["Alkosh's Roar"])

    def test_a_review_keeps_its_list_across_the_restart(self):
        win = self.win
        reviewed = [_fight("Yolnahkriin", "2026-08-30 14:10:31")]
        win._on_review_loaded("some.log", reviewed)
        self.assertEqual(self._listed(), ["Yolnahkriin"])
        self._press_save()
        win._on_monitoring_restarting()
        self.assertEqual(self._listed(), ["Yolnahkriin"])
        self.assertEqual(win._fights, [])


if __name__ == '__main__':
    unittest.main()
