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

Since issue #187 a save restarts the engine only when a setting it reads
changed (app_startup.engine_settings), so the saves here change one; a
save that changes nothing the engine reads keeps the list and drops
nothing.

Since issue #196 the replay comes back to the fight the reader was on:
the new analyzer's entry for it, known by its key (fight_blocks.fight_key),
is selected as it arrives, and the newest at monitoring_started when the
list was following the live log or the fight is gone. The tests drive the
window's slots in the order the engine's queued signals arrive: Save, the
old analyzer's last fights, monitoring_restarting, the replayed fights,
then monitoring_started.
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

REPLAYING = "Replaying the session with the new settings…"

# The logging player's row, whose name links to the build window
PLAYER = {
    "role": "D", "name": "@me", "class_abbr": "NB", "dps": 1000.0, "dmg_pct": 100.0,
    "h": 20000, "m": 30000, "s": 15000, "unit_id": "1", "sets": [], "all_sets": [],
    "skill_lines": [], "class_lines": [], "front_bar": [], "back_bar": [],
    "front_bar_slots": [], "back_bar_slots": []}

# One session's fights, as (boss, start)
SESSION = (("Lokkestiiz", "2026-08-30 13:58:42"),
           ("Yolnahkriin", "2026-08-30 14:10:31"),
           ("Nahviintaas", "2026-08-30 14:24:05"))


def _fight(boss, stamp):
    entry = FightHistoryEntry()
    entry.boss_name = boss
    entry.zone_name = "Sunspire"
    entry.timestamp = stamp
    entry.duration_s = 20.0
    entry.group_dps = 100000.0
    return entry


def _played(boss, stamp):
    """A fight with the logging player's row and the zone's id."""
    entry = _fight(boss, stamp)
    entry.zone_id = "1121"
    entry.players = [dict(PLAYER)]
    return entry


def _session(fights=SESSION):
    """The session's fights as one reading of the log builds them: each
    reading makes new entries."""
    return [_played(boss, stamp) for boss, stamp in fights]


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class _WindowTestCase(unittest.TestCase):

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
        # The engine's first signals (no log: waiting_for_log) come first,
        # as in the app, not inside the Settings dialog's event loop
        self.app.processEvents()

    def tearDown(self):
        self.win.close()
        self.tmp.cleanup()

    def _press_save(self, engine_setting=True):
        def accept():
            dialog = next((w for w in self.app.topLevelWidgets()
                           if isinstance(w, QDialog) and w.isVisible()
                           and hasattr(w, "rules_edit")), None)
            if dialog is None:
                QTimer.singleShot(10, accept)
            else:
                if engine_setting:
                    # one the engine reads: the save restarts it
                    dialog.companion_accrual.setChecked(
                        not dialog.companion_accrual.isChecked())
                else:
                    dialog.reduce_motion.setChecked(not dialog.reduce_motion.isChecked())
                dialog.accept()
        QTimer.singleShot(0, accept)
        self.win._open_settings()

    def _listed(self):
        return [self.win.history_list.fight_item(i).text().split(" · ")[0]
                for i in range(self.win.history_list.fight_count())]


class TestSaveDuringAReplay(_WindowTestCase):

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

    def test_a_save_that_changes_nothing_the_engine_reads_keeps_the_list(self):
        win = self.win
        win._on_fight_completed(_fight("Alkosh's Roar", "2026-08-30 13:58:42"))
        self._press_save(engine_setting=False)
        self.assertFalse(win._restart_pending)
        self.assertEqual(win.statusBar().currentMessage(), "Settings saved")
        self.assertTrue(win.config.get("display.reduce_motion"))
        # No restart is coming: the next fight is listed, nothing is dropped
        win._on_fight_completed(_fight("Alkosh's Fate", "2026-08-30 13:59:03"))
        self.assertEqual(self._listed(), ["Alkosh's Roar", "Alkosh's Fate"])

    def test_a_review_keeps_its_list_across_the_restart(self):
        win = self.win
        reviewed = [_fight("Yolnahkriin", "2026-08-30 14:10:31")]
        win._on_review_loaded("some.log", reviewed)
        self.assertEqual(self._listed(), ["Yolnahkriin"])
        self._press_save()
        win._on_monitoring_restarting()
        self.assertEqual(self._listed(), ["Yolnahkriin"])
        self.assertEqual(win._fights, [])


class TestTheReplayComesBackToTheFight(_WindowTestCase):
    """Issue #196: after a Settings replay with an older fight selected,
    nothing was selected and every pane link returned early."""

    def _live(self, select=None):
        """The session listed live, and the fight at *select* picked by the
        reader (None: the newest stays on screen, following the log)."""
        fights = _session()
        for entry in fights:
            self.win._on_fight_completed(entry)
        if select is not None:
            self.win.history_list.select_entry(fights[select])
        return fights

    def _restart(self):
        """Save, the old analyzer's last fight (dropped) and the engine's
        monitoring_restarting."""
        self._press_save()
        stale = _played("Lokkestiiz", "2026-08-30 14:40:00")
        self.win._on_fight_completed(stale)
        self.win._on_fight_updated(stale)
        self.win._on_monitoring_restarting()

    def _started(self):
        self.win._on_monitoring_started(str(Path(self.tmp.name) / "Encounter.log"))

    def _current(self):
        return self.win.history_list.current_entry()

    def test_an_older_fight_is_selected_again_and_its_links_work(self):
        from PySide6.QtCore import QUrl
        win = self.win
        self._live(select=1)
        self.assertFalse(win._follow_live)
        self._restart()
        replayed = _session()
        for entry in replayed:
            win._on_fight_completed(entry)
        self._started()

        self.assertEqual(self._listed(), ["Lokkestiiz", "Yolnahkriin", "Nahviintaas"])
        # The same fight, by its key: the new analyzer's entry for it
        self.assertIs(self._current(), replayed[1])
        self.assertTrue(win.fight_view.toPlainText().startswith("Yolnahkriin"))
        # A pane link opens on it
        win.fight_view.anchorClicked.emit(QUrl("esolog:build/1"))
        self.assertIsNotNone(win._build_dialog)
        self.assertIs(win._build_dialog.entry, replayed[1])
        self.assertEqual(win._build_dialog.windowTitle(), "Build – @me")
        # An older fight does not follow the live log: the next one is
        # listed, not selected
        later = _played("Lokkestiiz", "2026-08-30 14:52:17")
        win._on_fight_completed(later)
        self.assertEqual(win.history_list.fight_count(), 4)
        self.assertIs(self._current(), replayed[1])

    def test_the_newest_comes_back_and_the_live_log_is_followed(self):
        win = self.win
        self._live()
        self.assertTrue(win._follow_live)
        self._restart()
        replayed = _session()
        for entry in replayed:
            win._on_fight_completed(entry)
            # Held off: the selection does not run through the replay
            self.assertIsNone(self._current())
        self._started()
        self.assertIs(self._current(), replayed[-1])
        self.assertTrue(win._follow_live)
        later = _played("Lokkestiiz", "2026-08-30 14:52:17")
        win._on_fight_completed(later)
        self.assertIs(self._current(), later)

    def test_the_newest_when_the_fight_is_not_in_the_replay(self):
        win = self.win
        self._live(select=0)
        self._restart()
        # Another log: none of its fights started when the one on screen did
        other = _session((("Lokkestiiz", "2026-09-02 20:11:09"),
                          ("Yolnahkriin", "2026-09-02 20:24:40")))
        for entry in other:
            win._on_fight_completed(entry)
        self.assertIsNone(self._current())
        self._started()
        self.assertIs(self._current(), other[-1])
        self.assertTrue(win._follow_live)
        later = _played("Nahviintaas", "2026-09-02 20:37:12")
        win._on_fight_completed(later)
        self.assertIs(self._current(), later)

    def test_a_fight_the_reader_picks_during_the_replay_stays(self):
        win = self.win
        self._live()  # following the live log: the newest would come back
        self._restart()
        replayed = _session()
        win._on_fight_completed(replayed[0])
        win.history_list.select_entry(replayed[0])
        for entry in replayed[1:]:
            win._on_fight_completed(entry)
        self._started()
        self.assertIs(self._current(), replayed[0])
        # An older fight: the next one is not followed
        self.assertFalse(win._follow_live)
        win._on_fight_completed(_played("Lokkestiiz", "2026-08-30 14:52:17"))
        self.assertIs(self._current(), replayed[0])

    def test_the_fight_coming_back_does_not_take_the_readers_pick(self):
        win = self.win
        self._live(select=1)
        self._restart()
        replayed = _session()
        win._on_fight_completed(replayed[0])
        win.history_list.select_entry(replayed[0])
        win._on_fight_completed(replayed[1])  # the fight that was on screen
        self.assertIs(self._current(), replayed[0])
        win._on_fight_completed(replayed[2])
        self._started()
        self.assertIs(self._current(), replayed[0])

    def test_the_pane_says_the_session_is_being_replayed(self):
        win = self.win
        self._live(select=1)
        self._press_save()
        # Until the engine restarts, the page stands, its fight current
        self.assertIn("esolog:build/1", win.fight_view.toHtml())
        win._on_monitoring_restarting()
        # The stale page and its links are gone
        self.assertEqual(win.fight_view.toPlainText(), REPLAYING)
        self.assertNotIn("esolog:", win.fight_view.toHtml())
        replayed = _session()
        win._on_fight_completed(replayed[0])
        self.assertEqual(win.fight_view.toPlainText(), REPLAYING)
        # Until the fight comes back
        win._on_fight_completed(replayed[1])
        self.assertTrue(win.fight_view.toPlainText().startswith("Yolnahkriin"))

    def test_a_log_missing_at_the_restart_is_the_replay_once_it_appears(self):
        # The restart found no log (waiting_for_log); once it appears the
        # engine reads it and sends monitoring_started, with no
        # monitoring_restarting of its own (engine_worker._check_log_appeared)
        win = self.win
        self._live(select=1)
        self._restart()
        win._on_waiting_for_log(str(Path(self.tmp.name) / "Encounter.log"))
        self.assertTrue(win.fight_view.toPlainText().startswith("Waiting for Encounter.log"))
        replayed = _session()
        win._on_fight_completed(replayed[0])
        # Its fights are the replay: the waiting page gives way to its line
        self.assertEqual(win.fight_view.toPlainText(), REPLAYING)
        self.assertIsNone(self._current())
        for entry in replayed[1:]:
            win._on_fight_completed(entry)
        self.assertIs(self._current(), replayed[1])
        self._started()
        self.assertIs(self._current(), replayed[1])
        self.assertFalse(win._follow_live)

    def test_the_list_taking_the_focus_during_the_replay_picks_no_fight(self):
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QFocusEvent
        win = self.win
        self._live(select=1)
        self._restart()
        replayed = _session()
        win._on_fight_completed(replayed[0])
        # Alt+Tab back to the app, the list focused: an emptied list would
        # make its first fight current (FightList.clear)
        self.app.sendEvent(win.history_list,
                           QFocusEvent(QEvent.FocusIn, Qt.ActiveWindowFocusReason))
        self.assertIsNone(self._current())
        win._on_fight_completed(replayed[1])
        self.assertIs(self._current(), replayed[1])

    def test_a_fight_given_its_key_by_an_update_is_found_at_the_end(self):
        win = self.win
        self._live(select=1)
        self._restart()
        replayed = _session()
        # The game cut the fight in two: its first half came with an add
        # as its boss, and the whole fight, sent again, with Yolnahkriin
        replayed[1].boss_name = "Grim Warden"
        win._on_fight_completed(replayed[0])
        win._on_fight_completed(replayed[1])
        self.assertIsNone(self._current())
        replayed[1].boss_name = "Yolnahkriin"
        win._on_fight_updated(replayed[1])
        win._on_fight_completed(replayed[2])
        self._started()
        self.assertIs(self._current(), replayed[1])
        self.assertFalse(win._follow_live)

    def test_a_review_opened_during_the_replay_keeps_its_fight(self):
        win = self.win
        self._live(select=1)
        self._restart()
        replayed = _session()
        win._on_fight_completed(replayed[0])
        reviewed = [_played("Ozezan the Inferno", "2026-09-05 20:22:57")]
        win._on_review_loaded("some.log", reviewed)
        for entry in replayed[1:]:
            win._on_fight_completed(entry)
        self._started()
        self.assertEqual(self._listed(), ["Ozezan the Inferno"])
        self.assertIs(self._current(), reviewed[0])
        # Back to live: the newest, following the log
        win._exit_review()
        self.assertIs(self._current(), replayed[-1])
        self.assertTrue(win._follow_live)

    def test_a_review_through_a_replay_that_brings_no_fight(self):
        win = self.win
        self._live(select=1)
        self._restart()
        reviewed = [_played("Ozezan the Inferno", "2026-09-05 20:22:57")]
        win._on_review_loaded("some.log", reviewed)
        self._started()  # the log holds no fight now
        self.assertIs(self._current(), reviewed[0])
        win._exit_review()
        self.assertIsNone(self._current())
        self.assertEqual(win._empty_reason, "back")
        later = _played("Lokkestiiz", "2026-08-30 14:52:17")
        win._on_fight_completed(later)
        self.assertIs(self._current(), later)

    def test_with_no_fight_the_replay_line_gives_way_to_the_empty_page(self):
        win = self.win
        self.assertEqual(win._empty_reason, "waiting")
        self._press_save()
        win._on_monitoring_restarting()
        self.assertEqual(win.fight_view.toPlainText(), REPLAYING)
        self.assertIsNone(win._empty_reason)
        self._started()
        self.assertEqual(win._empty_reason, "monitoring")
        self.assertTrue(win.fight_view.toPlainText().startswith("Monitoring Encounter.log."))
        # The first fight is followed
        first = _played("Lokkestiiz", "2026-08-30 14:52:17")
        win._on_fight_completed(first)
        self.assertIs(self._current(), first)

    def test_back_to_live_during_the_replay_follows_the_log(self):
        win = self.win
        self._live(select=1)
        self._restart()
        replayed = _session()
        win._on_fight_completed(replayed[0])
        win._on_review_loaded("some.log", [_played("Ozezan the Inferno", "2026-09-05 20:22:57")])
        win._exit_review()
        self.assertIs(self._current(), replayed[0])
        for entry in replayed[1:]:
            win._on_fight_completed(entry)
            self.assertIs(self._current(), entry)
        self._started()
        self.assertIs(self._current(), replayed[-1])
        self.assertTrue(win._follow_live)

    def test_a_second_save_during_the_replay_keeps_the_fight(self):
        win = self.win
        self._live(select=1)
        self._restart()
        first = _session()
        win._on_fight_completed(first[0])  # not yet the fight on screen
        # Saved again before that replay is done: the rest of it is
        # dropped, and its monitoring_started comes before the restart
        self._press_save()
        for entry in first[1:]:
            win._on_fight_completed(entry)
        self._started()
        self.assertIsNone(self._current())
        win._on_monitoring_restarting()
        second = _session()
        for entry in second:
            win._on_fight_completed(entry)
        self.assertIs(self._current(), second[1])
        self._started()
        self.assertIs(self._current(), second[1])
        self.assertFalse(win._follow_live)


if __name__ == '__main__':
    unittest.main()
