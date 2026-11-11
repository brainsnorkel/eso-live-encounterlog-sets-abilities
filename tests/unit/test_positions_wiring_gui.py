#!/usr/bin/env python3
"""The positions window's wiring (issue #214), offscreen: the links to it
and what the main window does for it. A Positions link on each row of the
Deaths tab, in each death's heading in the player window, and in the fight
header (the first death, else the start), each opening the one window at
its moment with its unit selected; the read through the real runner and
the bridge, from a split the test writes, with the places worked out from
the folders set; a fight cut in two read again, and no other update; a
Settings replay re-binding the window; the window's own links back; the
review's file; closing the main window; no link for a fight without a
locator; the hrefs; the Deaths tab's links taking no room at 150% and 200%
text; a theme switch.

The window itself is gui.positions_window's. Until that module is there,
the tests run against a small stand-in that keeps the contract the main
window is written to (MainWindow.show_moment); when it is there, every
test runs against it too (TestWiringWithTheWindow). Either way the class is
wrapped to note what it was asked."""

import json
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_death_recap_gui import _death, _entry_with_deaths, _player
from tests.unit.test_gui import HAVE_QT, _ensure_app

_app = None

ROOT = Path(__file__).resolve().parents[2]
READING = "Reading the fight's lines..."
NOT_ON_DISK = "This fight's lines are no longer on disk"


def _pump(until, timeout=10.0):
    """Run the event loop until *until()* holds or *timeout* seconds pass;
    whether it holds."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        _app.processEvents()
        if until():
            return True
        time.sleep(0.005)
    _app.processEvents()
    return bool(until())


def _stand_in():
    """A window that keeps the contract (see the module notes)."""
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QDialog

    class StandInPositionsWindow(QDialog):
        show_in_list_requested = Signal(object)
        player_requested = Signal(object, str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._entry = self._wanted = self._states = None
            self.note = ""
            self.listed = True
            self.replayed = False

        @property
        def entry(self):
            return self._entry

        @property
        def wanted_locator(self):
            return self._wanted

        def has_states_for(self, locator):
            return self._states is not None and self._states.locator == locator

        def open(self, entry, t_ms, unit_key, dark, names, listed=True):
            self._entry, self._wanted = entry, entry.locator
            if not self.has_states_for(entry.locator):
                self._states, self.note = None, READING
            self.set_listed(listed)
            self.replayed = False
            self.show()
            self.raise_()

        def reread_done(self, event):
            if event.locator is not self._wanted or event.kind == "cancelled":
                return
            if event.kind == "loaded":
                self._states, self.note = event.states, ""
            elif event.kind == "missing":
                self.note = f"{NOT_ON_DISK} {event.error}"
            else:
                self.note = event.error

        def refresh(self, dark, names=None):
            pass

        def entry_updated(self, entry, dark, names):
            if entry is self._entry and entry.locator is not self._wanted:
                self._wanted = entry.locator
                if not self.has_states_for(entry.locator):
                    self._states, self.note = None, READING

        def rebind(self, entry, names):
            self._entry = entry
            if not self.has_states_for(entry.locator):
                self._states, self._wanted = None, entry.locator
            self.replayed = False

        def mark_replayed(self):
            self.replayed = True

        def set_listed(self, listed):
            self.listed = bool(listed)

        def views(self):
            return []

    return StandInPositionsWindow


def _the_window():
    """gui.positions_window's class, None while the module is not there."""
    try:
        from gui.positions_window import PositionsWindow
    except ImportError:
        return None
    return PositionsWindow


def _recording(base):
    """*base* noting each call the main window makes on it."""

    class Recording(base):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.opened = []    # (entry, moment, unit key)
            self.masks = []     # the Hide names mask of each open
            self.answers = []   # (kind, locator) of each read's answer
            self.rebound = []
            self.marked = 0

        def open(self, entry, t_ms, unit_key, dark, names, listed=True):
            self.opened.append((entry, t_ms, unit_key))
            self.masks.append(names)
            return super().open(entry, t_ms, unit_key, dark, names, listed)

        def reread_done(self, event):
            self.answers.append((event.kind, event.locator))
            return super().reread_done(event)

        def rebind(self, entry, names):
            self.rebound.append(entry)
            return super().rebind(entry, names)

        def mark_replayed(self):
            self.marked += 1
            return super().mark_replayed()

    return Recording


def _decorated(entry):
    """The engine's fight with what the standard session's lines do not
    give it: player rows keyed as the locator's units are, and two deaths,
    @björk's first though the engine holds it second."""
    entry.players = [dict(_player("1", "@tëster"), is_local=True), _player("2", "@björk"),
                     _player("3", "@lǐ")]
    entry.player_names = [{"name": "@tëster", "is_local": True}, {"name": "@björk"},
                          {"name": "@lǐ"}]
    entry.death_recaps = [_death("1", "@tëster", 7000, "Test Boss", "Slam", []),
                          _death("2", "@björk", 5000, "Test Boss", "Slam", [])]
    entry.deaths = 2
    return entry


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class WiringTestCase(unittest.TestCase):
    """Main windows on a tmp config whose split, archive and log folders
    the test fills; the window class installed as gui.positions_window."""

    REAL = False

    def setUp(self):
        global _app
        _app = _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.splits = self.root / "splits"
        self.archives = self.root / "archives"
        self.splits.mkdir()
        self.archives.mkdir()
        self.windows = []
        base = _the_window() if self.REAL else _stand_in()
        if base is None:
            self.skipTest("gui.positions_window is not there yet")
        module = types.ModuleType("gui.positions_window")
        module.PositionsWindow = _recording(base)
        patcher = mock.patch.dict(sys.modules, {"gui.positions_window": module})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        from gui import text_size
        for win in self.windows:
            win.close()
        text_size.apply(text_size.DEFAULT_PCT)  # the application font is shared
        self.tmp.cleanup()

    def _split(self):
        """The standard session written as its split, named by its stamp
        as the splitter names it: the path."""
        import split_retention
        from tests.unit.test_fight_reread import EPOCH, Log, standard
        name = f"{split_retention.session_stamp(EPOCH)}-Kynes-Aegis-vet.log"
        return Log().add(standard()).save(self.splits / name)

    def _fight(self, path=None):
        """The fight of the split, as the engine builds it, decorated."""
        from tests.unit.test_fight_reread import replay
        fights = replay(path or self._split())
        self.assertEqual(len(fights), 1)
        self.assertIsNotNone(fights[0].locator)
        return _decorated(fights[0])

    def _window(self, *entries, pct=None):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.root / "config.json")
        config.set("log_path", str(self.root / "Encounter.log"))
        config.set("split.dir", str(self.splits))
        config.set("archive.dir", str(self.archives))
        config.set("update.check_enabled", False)
        if pct is not None:
            config.set("display.text_scale", pct)
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        self.windows.append(win)
        win.resize(1080, 720)
        win.show()
        _app.processEvents()  # the worker's queued startup signals
        for entry in entries:
            win._on_fight_completed(entry)
        if entries:
            win.history_list.select_entry(entries[0])
        return win

    def _asked(self, win):
        """Every request the window's runner gets, (locator, places), each
        still made."""
        asked = []
        request = win._reread.request

        def recording(locator, places, notify):
            asked.append((locator, list(places)))
            request(locator, places, notify)
        win._reread.request = recording
        return asked

    def _loaded(self, window, locator):
        return _pump(lambda: ("loaded", locator) in [(kind, at) for kind, at in window.answers
                                                     if at is locator])

    def _links(self, view):
        from gui.death_render import POSITIONS_HREF
        return [href for href, _start, _end in view._links() if href.startswith(POSITIONS_HREF)]

    def _deaths_page(self, win):
        win.fight_tabs.setCurrentWidget(win.deaths_view)
        _app.processEvents()
        return win.deaths_view

    def _replay(self, win, replayed):
        """A Settings replay as the engine's queued signals bring it."""
        win._restart_pending = True
        win._on_monitoring_restarting()
        for entry in replayed:
            win._on_fight_completed(entry)
        win._on_monitoring_started(str(self.root / "Encounter.log"))


class WiringTests:
    """The tests, run on the stand-in and on the window (see below)."""

    # ---- the links ----

    def test_a_deaths_row_opens_the_window_at_that_death(self):
        """Each row's time on the Deaths tab links to Positions, in the deaths'
        time order: the window at that moment of the fight the page was
        drawn for (the locator's clock), the player who died selected. One
        window, which the next fight's link reuses."""
        from PySide6.QtCore import QUrl

        from gui.death_render import positions_href
        entry = self._fight()
        win = self._window(entry)
        view = self._deaths_page(win)
        links = self._links(view)
        self.assertEqual(links, [positions_href("2", 5000), positions_href("1", 7000)])
        self.assertIn("Positions at 0:05", view._tooltips[links[0]])
        view.anchorClicked.emit(QUrl(links[1]))
        window = win._positions_window
        self.assertEqual(window.opened, [(entry, entry.locator.start_ms + 7000, "1")])
        self.assertIs(window.entry, entry)
        self.assertTrue(window.isVisible())
        second = self._fight()
        win._on_fight_completed(second)
        self.assertIs(window.entry, entry)
        self.assertIs(win._deaths_entry, second)
        win.deaths_view.anchorClicked.emit(QUrl(self._links(win.deaths_view)[0]))
        self.assertIs(win._positions_window, window)
        self.assertEqual(window.opened[-1], (second, second.locator.start_ms + 5000, "2"))

    def test_a_recap_headings_link_opens_it_from_the_player_window(self):
        """Each death's heading on the player window's Deaths tab ends in
        Positions, which the player window hands on with its fight: the
        window at that death, the player selected."""
        from PySide6.QtCore import QUrl

        from gui.death_render import death_href, positions_href
        from gui.player_window import DEATHS_TAB
        entry = self._fight()
        win = self._window(entry)
        win.fight_view.anchorClicked.emit(QUrl(death_href("2")))
        page = win._player_window.view(DEATHS_TAB)
        self.assertEqual(self._links(page), [positions_href("2", 5000)])
        self.assertIn("Death 1 of 1 · 0:05 into the fight · 18,678 max health · Positions",
                      page.toPlainText())
        self.assertIn("Positions at 0:05", page._tooltips[positions_href("2", 5000)])
        later = self._fight()
        win._on_fight_completed(later)  # the list moves on; the player window keeps its fight
        page.anchorClicked.emit(QUrl(positions_href("2", 5000)))
        self.assertEqual(win._positions_window.opened, [(entry, entry.locator.start_ms + 5000, "2")])

    def test_the_header_opens_at_the_first_death_or_the_start(self):
        """The fight header's Positions, after Deaths N: the first death by
        time, that player selected; with no death, the fight's start and
        nobody selected. Its hover says which."""
        from PySide6.QtCore import QUrl

        from gui.death_render import FIGHT_POSITIONS_HREF
        entry = self._fight()
        win = self._window(entry)
        self.assertIn("Deaths 2 Deaths tab · Positions", win.fight_view.accessible_text())
        self.assertIn("at the first death, 0:05 into the fight",
                      win.fight_view._tooltips[FIGHT_POSITIONS_HREF])
        win.fight_view.anchorClicked.emit(QUrl(FIGHT_POSITIONS_HREF))
        window = win._positions_window
        self.assertEqual(window.opened[-1], (entry, entry.locator.start_ms + 5000, "2"))
        calm = self._fight()
        calm.death_recaps, calm.deaths = [], 0
        win._on_fight_completed(calm)
        self.assertIs(win.history_list.current_entry(), calm)
        self.assertIn("as the fight began", win.fight_view._tooltips[FIGHT_POSITIONS_HREF])
        win.fight_view.anchorClicked.emit(QUrl(FIGHT_POSITIONS_HREF))
        self.assertEqual(window.opened[-1], (calm, calm.locator.start_ms, None))

    def test_no_link_for_a_fight_without_a_locator(self):
        """A fight with no locator, or one whose session is not known, has
        no Positions link on the pane, the Deaths tab or the recap, and
        opens nothing."""
        from PySide6.QtCore import QUrl

        from gui.death_render import death_href
        from gui.player_window import DEATHS_TAB
        bare = _entry_with_deaths()
        unknown = self._fight()
        unknown.locator = unknown.locator._replace(session_epoch_ms=None)
        for entry in (bare, unknown):
            win = self._window(entry)
            for view in (win.fight_view, self._deaths_page(win)):
                self.assertNotIn("esolog:positions", view.toHtml())
                self.assertNotIn("Positions", view.toPlainText())
            win.fight_view.anchorClicked.emit(QUrl(death_href(entry.death_recaps[0]["unit_id"])))
            self.assertNotIn("esolog:positions", win._player_window.view(DEATHS_TAB).toHtml())
            win.show_moment(entry, 0, "1")
            self.assertIsNone(win._positions_window)

    # ---- the read ----

    def test_the_read_goes_through_the_runner_and_the_bridge(self):
        """The link asks the runner for the fight, by its locator, from the
        places the folders set give: the session's split by its stamp, the
        live log, and the archives made since the session began (one stamped
        in its very second among them), never an older one, plain files
        before zips. The answer comes back on this thread through the
        bridge, and the window holds the states; a second link to the
        fight reads nothing."""
        import split_retention
        from tests.unit.test_fight_reread import EPOCH
        split = self._split()
        older = self.archives / f"Encounter-{split_retention.session_stamp(EPOCH - 3_600_000)}.zip"
        same = self.archives / f"Encounter-{split_retention.session_stamp(EPOCH)}-1.zip"
        newer = self.archives / f"Encounter-{split_retention.session_stamp(EPOCH + 3_600_000)}.zip"
        for path in (older, same, newer):
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("Encounter.log", b"")
        entry = self._fight(split)
        win = self._window(entry)
        asked = self._asked(win)
        win.show_moment(entry, entry.locator.start_ms + 5000, "2")
        window = win._positions_window
        self.assertEqual(len(asked), 1)
        locator, places = asked[0]
        self.assertIs(locator, entry.locator)
        self.assertEqual([(place.kind, place.path.name) for place in places][:2],
                         [("split", split.name), ("live", "Encounter.log")])
        self.assertEqual(sorted(place.path.name for place in places[2:]),
                         sorted([same.name, newer.name]))
        self.assertTrue(all(place.kind == "archive" for place in places[2:]))
        self.assertIs(window.wanted_locator, entry.locator)
        self.assertTrue(self._loaded(window, entry.locator))
        self.assertTrue(window.has_states_for(entry.locator))
        self.assertIsNone(win._reread_pending)
        win.show_moment(entry, entry.locator.start_ms, None)
        self.assertEqual(len(asked), 1)

    def test_a_second_link_while_the_fight_is_read_asks_for_nothing(self):
        """A link to the fight being read waits for that read; a link to
        another fight supersedes it, and the window drops the first one's
        answer."""
        entry, other = self._fight(), self._fight()
        win = self._window(entry, other)
        asked = self._asked(win)
        win.show_moment(entry, entry.locator.start_ms, None)
        win.show_moment(entry, entry.locator.start_ms + 5000, "2")
        self.assertEqual(len(asked), 1)
        win.show_moment(other, other.locator.start_ms, None)
        self.assertEqual([locator for locator, _places in asked], [entry.locator, other.locator])
        window = win._positions_window
        self.assertTrue(self._loaded(window, other.locator))
        self.assertTrue(window.has_states_for(other.locator))
        self.assertIs(window.entry, other)

    def test_the_reviewed_file_comes_first_while_a_window_holds_its_fight(self):
        """A reviewed fight is read from the file the review read, by the
        path and member the review's event gave, not the label shown. After
        Back to live, and after a second review, that file still comes
        first while a window holds the fight: it may be in none of the
        folders the app looks in (a log someone sent), where the window
        said the lines were no longer on disk (the review's finding 07).
        Once no window holds the fight, the file is forgotten."""
        split = self._split()
        entry = self._fight(split)
        win = self._window()
        win._on_review_loaded(f"{split} › its log", [entry], source=(str(split), ""))
        win.history_list.select_entry(entry)
        asked = self._asked(win)
        win.show_moment(entry, entry.locator.start_ms, None)
        place = asked[0][1][0]
        self.assertEqual((place.kind, place.path, place.member), ("review", split, None))
        self.assertTrue(self._loaded(win._positions_window, entry.locator))
        win._exit_review()
        self.assertIsNone(win._review_source)
        first = win._reread_places(entry)[0]
        self.assertEqual((first.kind, first.path), ("review", split))
        sent = self.root / "sent.log"
        sent.write_bytes(split.read_bytes())
        second = self._fight(sent)
        win._on_review_loaded(str(sent), [second], source=(str(sent), ""))
        self.assertEqual(win._reread_places(entry)[0].path, split)
        self.assertEqual(win._reread_places(second)[0].path, sent)
        win.show_moment(second, second.locator.start_ms, None)  # the window lets it go
        self.assertNotIn("review", [place.kind for place in win._reread_places(entry)])

    def test_a_reviewed_fight_in_the_player_window_is_read_after_back_to_live(self):
        """The review's finding 07 as the reviewer met it: the player
        window keeps a reviewed fight after Back to live, and its recap's
        Positions reads the reviewed file, wherever it is."""
        from PySide6.QtCore import QUrl

        from gui.death_render import death_href, positions_href
        from gui.player_window import DEATHS_TAB
        sent = self.root / "sent.log"
        sent.write_bytes(self._split().read_bytes())
        entry = self._fight(sent)
        win = self._window()
        win._on_review_loaded(str(sent), [entry], source=(str(sent), ""))
        win.history_list.select_entry(entry)
        win.fight_view.anchorClicked.emit(QUrl(death_href("2")))
        win._exit_review()
        asked = self._asked(win)
        page = win._player_window.view(DEATHS_TAB)
        page.anchorClicked.emit(QUrl(positions_href("2", 5000)))
        self.assertEqual([(place.kind, place.path) for place in asked[0][1]][:1],
                         [("review", sent)])
        self.assertTrue(self._loaded(win._positions_window, entry.locator))

    def test_a_link_before_the_log_is_known_is_read_once_it_is(self):
        """With the log auto-detected (no log, split or archive folder
        set), a Positions link clicked while the fights replayed at attach
        are listed, before monitoring_started names the log, finds no
        place, and the window hears 'missing'; monitoring_started asks
        again, and the split beside the log gives the lines (the review's
        finding 08)."""
        split = self._split()
        entry = self._fight(split)
        win = self._window(entry)
        for key in ("log_path", "split.dir", "archive.dir"):
            win.config.set(key, "")
        win._log_path, win._empty_expected = None, ""
        asked = self._asked(win)
        win.show_moment(entry, entry.locator.start_ms, None)
        window = win._positions_window
        self.assertEqual(asked[0][1], [])
        self.assertTrue(_pump(lambda: any(kind == "missing" for kind, _at in window.answers)))
        self.assertFalse(window.has_states_for(entry.locator))
        win._on_monitoring_started(str(self.splits / "Encounter.log"))
        self.assertEqual(len(asked), 2)
        self.assertTrue(self._loaded(window, entry.locator))
        self.assertTrue(window.has_states_for(entry.locator))

    def test_missing_lines_are_said_without_a_path(self):
        """With the split gone and nothing else holding the session, the
        window hears 'missing', with the files tried by name only; an
        update that leaves the locator as it was does not try again."""
        split = self._split()
        entry = self._fight(split)
        split.unlink()
        win = self._window(entry)
        asked = self._asked(win)
        win.show_moment(entry, entry.locator.start_ms, None)
        window = win._positions_window
        self.assertTrue(_pump(lambda: any(at is entry.locator and kind == "missing"
                                          for kind, at in window.answers)))
        self.assertFalse(window.has_states_for(entry.locator))
        if not self.REAL:
            self.assertTrue(window.note.startswith(NOT_ON_DISK))
            self.assertNotIn(str(self.root), window.note)
        win._on_fight_updated(entry)
        _app.processEvents()
        self.assertEqual(len(asked), 1)

    def test_a_replay_reads_again_a_fight_it_could_not_read(self):
        """A window with no states for its fight (its split was gone)
        re-bound by a Settings replay asks for a read of the copy's
        locator, and takes it, the split being back."""
        split = self._split()
        entry = self._fight(split)
        data = split.read_bytes()
        split.unlink()
        win = self._window(entry)
        asked = self._asked(win)
        win.show_moment(entry, entry.locator.start_ms, None)
        window = win._positions_window
        self.assertTrue(_pump(lambda: any(kind == "missing" for kind, _at in window.answers)))
        split.write_bytes(data)
        replayed = self._fight(split)
        self._replay(win, [replayed])
        self.assertIs(window.entry, replayed)
        self.assertEqual([locator for locator, _places in asked], [entry.locator, replayed.locator])
        self.assertIs(asked[-1][0], replayed.locator)
        self.assertTrue(self._loaded(window, replayed.locator))
        self.assertTrue(window.has_states_for(replayed.locator))

    # ---- updates in place ----

    def test_a_fight_cut_in_two_is_read_again_and_no_other_update_is(self):
        """A late death and a banner leave the same locator, and read
        nothing: the window redraws from its entry. A fight the game cut in
        two that went on has a new locator: read again, once, and the
        window takes the new states. A hidden window is asked for nothing,
        and its next link reads what it lacks."""
        entry = self._fight()
        win = self._window(entry)
        asked = self._asked(win)
        win.show_moment(entry, entry.locator.start_ms, None)
        window = win._positions_window
        self.assertTrue(self._loaded(window, entry.locator))
        late = _death("3", "@lǐ", 9500, "Test Boss", "Slam", [])
        entry.death_recaps = entry.death_recaps + [late]
        entry.deaths = 3
        win._on_fight_updated(entry)
        win._on_fight_updated(entry)
        _app.processEvents()
        self.assertEqual(len(asked), 1)
        self.assertTrue(window.has_states_for(entry.locator))
        resumed = entry.locator._replace(end_ms=entry.locator.end_ms + 500)
        entry.locator = resumed
        win._on_fight_updated(entry)
        _app.processEvents()
        self.assertEqual([locator for locator, _places in asked], [asked[0][0], resumed])
        self.assertTrue(_pump(lambda: any(at is resumed and kind != "cancelled"
                                          for kind, at in window.answers)))
        self.assertIs(window.wanted_locator, resumed)
        window.hide()
        entry.locator = resumed._replace(end_ms=resumed.end_ms + 500)
        win._on_fight_updated(entry)
        self.assertEqual(len(asked), 2)
        win.show_moment(entry, entry.locator.start_ms, None)
        self.assertEqual(asked[-1][0], entry.locator)

    # ---- a Settings replay ----

    def test_a_settings_replay_rebinds_the_window(self):
        """The window's fight read again by a Settings replay: the window
        goes on to the replayed copy, keeping the states it read, since the
        same log gives the same locator; nothing is read again."""
        split = self._split()
        entry = self._fight(split)
        win = self._window(entry)
        asked = self._asked(win)
        win.show_moment(entry, entry.locator.start_ms + 5000, "2")
        window = win._positions_window
        self.assertTrue(self._loaded(window, entry.locator))
        replayed = self._fight(split)
        self.assertEqual(replayed.locator, entry.locator)
        self.assertIsNot(replayed.locator, entry.locator)
        self._replay(win, [replayed])
        self.assertEqual(window.rebound, [replayed])
        self.assertIs(window.entry, replayed)
        self.assertTrue(window.has_states_for(replayed.locator))
        self.assertEqual(len(asked), 1)
        self.assertEqual(window.marked, 0)

    def test_a_replay_without_the_fight_keeps_it_and_says_so(self):
        entry = self._fight()
        win = self._window(entry)
        win.show_moment(entry, entry.locator.start_ms, None)
        window = win._positions_window
        other = self._fight()
        other.timestamp = "2026-01-01 00:00:00"
        self._replay(win, [other])
        self.assertEqual((window.marked, window.rebound), (1, []))
        self.assertIs(window.entry, entry)
        if not self.REAL:
            self.assertFalse(window.listed)

    def test_a_link_clicked_during_a_replay_is_kept_when_it_ends(self):
        """A link the reader clicks while a Settings replay runs puts the
        window on that fight; the replay's end leaves it there."""
        first, second = self._fight(), self._fight()
        second.timestamp = "2026-09-22 00:20:00"
        win = self._window(first)
        win.show_moment(first, first.locator.start_ms, None)
        window = win._positions_window
        win._restart_pending = True
        win._on_monitoring_restarting()
        copies = [self._fight(), second]
        for each in copies:
            win._on_fight_completed(each)
        win.show_moment(second, second.locator.start_ms, None)
        win._on_monitoring_started(str(self.root / "Encounter.log"))
        self.assertIs(window.entry, second)
        self.assertEqual((window.rebound, window.marked), ([], 0))

    # ---- the window's own links, its place, the main window closing ----

    def test_the_windows_links_back(self):
        """Show in list selects the window's fight; a unit's player link
        opens the player window on that row at Build, a player with no row
        who died at Deaths, and nothing for an enemy, with a word why."""
        from gui.player_window import BUILD_TAB, DEATHS_TAB
        entry, later = self._fight(), self._fight()
        win = self._window(entry, later)
        win.show_moment(entry, entry.locator.start_ms, None)
        window = win._positions_window
        win.history_list.select_entry(later)
        window.show_in_list_requested.emit(entry)
        self.assertIs(win.history_list.current_entry(), entry)
        window.player_requested.emit(entry, "2")
        player = win._player_window
        self.assertEqual((player.entry, player.unit_id, player.current_tab()),
                         (entry, "2", BUILD_TAB))
        entry.death_recaps = entry.death_recaps + [_death("9", "@gone", 8000, "Test Boss",
                                                          "Slam", [])]
        window.player_requested.emit(entry, "9")
        self.assertEqual((player.unit_id, player.current_tab()), ("9", DEATHS_TAB))
        window.player_requested.emit(entry, "70")
        self.assertEqual(player.unit_id, "9")
        self.assertIn("no player window", win.statusBar().currentMessage())

    def test_its_place_is_saved_and_put_back(self):
        entry = self._fight()
        win = self._window(entry)
        win.show_moment(entry, entry.locator.start_ms, None)
        window = win._positions_window
        window.resize(640, 500)
        win._save_window_layout()
        self.assertTrue(win.config.get("window.positions_geometry"))
        again = self._window(entry)
        again.show_moment(entry, entry.locator.start_ms, None)
        self.assertEqual(again._positions_window.size().width(), window.size().width())

    def test_closing_the_main_window_closes_the_runner(self):
        """The runner closed, its thread ended, its bridge cut off; a link
        or an update after it asks for nothing."""
        from fight_reread import RereadEvent
        entry = self._fight()
        win = self._window(entry)
        win.show_moment(entry, entry.locator.start_ms, None)
        window = win._positions_window
        self.assertTrue(self._loaded(window, entry.locator))
        thread = win._reread._thread
        self.assertTrue(thread.is_alive())
        win.close()
        self.assertFalse(thread.is_alive())
        with self.assertRaises(RuntimeError):
            win._reread.request(entry.locator, [], lambda event: None)
        heard = len(window.answers)
        win._reread_bridge.event.emit(RereadEvent("missing", entry.locator, error="late"))
        _app.processEvents()
        self.assertEqual(len(window.answers), heard)
        entry.locator = entry.locator._replace(end_ms=entry.locator.end_ms + 500)
        win.show_moment(entry, entry.locator.start_ms, None)
        win._on_fight_updated(entry)

    def test_a_notify_after_the_bridge_is_gone_raises_nothing(self):
        """Emitting on a bridge whose C++ side is gone raises RuntimeError
        even while the weak reference holds the wrapper: notify swallows
        it, so the runner's thread goes on."""
        import shiboken6

        from fight_reread import RereadEvent
        entry = self._fight()
        win = self._window(entry)
        notify = win._reread_notify()
        shiboken6.delete(win._reread_bridge)
        notify(RereadEvent("cancelled", entry.locator))

    # ---- Hide names ----

    def test_hide_names_shows_no_name_or_path_in_the_new_parts(self):
        """The Positions links and their hover name no player and no path;
        the window is given the fight's Hide names mask."""
        from PySide6.QtCore import QUrl

        from gui.death_render import FIGHT_POSITIONS_HREF
        entry = self._fight()
        win = self._window(entry)
        win.hide_names_action.setChecked(True)
        view = self._deaths_page(win)
        tips = [view._tooltips[href] for href in self._links(view)]
        tips.append(win.fight_view._tooltips[FIGHT_POSITIONS_HREF])
        for tip in tips:
            self.assertNotIn("@", tip)
            self.assertNotIn(str(self.root), tip)
        view.anchorClicked.emit(QUrl(self._links(view)[0]))
        mask = win._positions_window.masks[-1]
        self.assertTrue(mask.hides("@björk"))
        self.assertFalse(mask.hides("@tëster"))


class TestWiringWithAStandIn(WiringTests, WiringTestCase):
    REAL = False


class TestWiringWithTheWindow(WiringTests, WiringTestCase):
    """The same against gui.positions_window, once it is there."""
    REAL = True


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestTheHrefs(unittest.TestCase):

    def setUp(self):
        global _app
        _app = _ensure_app()

    def test_a_moment_and_the_fight_parse(self):
        from gui.death_render import (
            FIGHT_POSITIONS_HREF,
            POSITIONS_HREF,
            positions_from_href,
            positions_href,
            recap_from_href,
            recap_href,
        )
        for unit, ms in (("2", 5000), ("c12-9244", 0), ("", -1500), ("41", 10_800_000)):
            self.assertEqual(positions_from_href(positions_href(unit, ms)), (unit, ms))
        self.assertEqual(positions_href(None, 7), f"{POSITIONS_HREF}/7")
        for bad in (FIGHT_POSITIONS_HREF, f"{POSITIONS_HREF}2", f"{POSITIONS_HREF}2/x",
                    f"{POSITIONS_HREF}2/1.5", f"{POSITIONS_HREF}2/--3", "", recap_href("2", 1)):
            self.assertIsNone(positions_from_href(bad), bad)
        self.assertIsNone(recap_from_href(positions_href("2", 1)))

    def test_a_click_on_each_asks_for_its_moment(self):
        from PySide6.QtCore import QUrl

        from gui.death_render import FIGHT_POSITIONS_HREF, positions_href, recap_href
        from gui.fight_view import FightView
        view = FightView()
        asked = []
        view.positions_requested.connect(lambda unit, ms: asked.append(("moment", unit, ms)))
        view.fight_positions_requested.connect(lambda: asked.append(("fight",)))
        view.recap_requested.connect(lambda unit, n: asked.append(("recap", unit, n)))
        try:
            for href in (positions_href("2", 5000), positions_href("c12-9244", 0),
                         positions_href("", -500), FIGHT_POSITIONS_HREF,
                         "esolog:positions/2/x", recap_href("2", 1)):
                view.anchorClicked.emit(QUrl(href))
            self.assertEqual(asked, [("moment", "2", 5000), ("moment", "c12-9244", 0),
                                     ("moment", "", -500), ("fight",), ("recap", "2", 1)])
        finally:
            view.deleteLater()


def _four_deaths():
    """A fight with four deaths as the review measured the Deaths tab on
    (its finding 19): a 22-character handle, 'Lieutenant Njordal' and
    'Lord Falgravn' as killers, a fall, and '1:32 to the end'; no
    locator."""
    from fight_history import FightHistoryEntry
    handle = "@Synthetic_Tester_0042"
    entry = FightHistoryEntry()
    entry.boss_name, entry.zone_name, entry.duration_s = "Lord Falgravn", "Kyne's Aegis", 310.0
    entry.players = [{"role": "D", "name": handle, "class_abbr": "NB", "unit_id": "1"},
                     {"role": "H", "name": "@friend", "class_abbr": "TPL", "unit_id": "2"},
                     {"role": "T", "name": "anon", "class_abbr": "DK", "unit_id": "3"}]
    entry.player_names = [{"name": handle}, {"name": "@friend"}, {"name": "anon"}]

    def death(uid, name, t, killer, ability):
        return {"unit_id": uid, "name": name, "time_ms": t, "killer": killer,
                "ability": ability, "ability_id": "9", "icon": "", "cause": "",
                "max_health": 18678, "events": []}
    entry.death_recaps = [death("1", handle, 54000, "Lord Falgravn", "Grievous Pulse"),
                          death("2", "@friend", 60500, "Lieutenant Njordal", "Frenzied Cleave"),
                          death("3", "anon", 61000, "Lord Falgravn", "Grievous Pulse"),
                          death("1", handle, 195000, "", "a fall or lava")]
    entry.deaths = 4
    entry.time_dead = {"1": 51000, "2": 12000, "3": 59000}
    entry.pull = {"boss": "Lord Falgravn", "bosses": ["Lord Falgravn"], "outcome": "wipe",
                  "dead_at_end": ["1", "3"], "continues": False}
    return entry


def _a_locator():
    """A locator whose session is known, for the Positions links."""
    from fight_locator import FightLocator
    return FightLocator(session_stamp="", session_epoch_ms=1, session_offset=0, zone_offset=0,
                        begin_offset=0, end_offset=0, start_ms=0, end_ms=310000,
                        map_at_lead=None, units=())


def _deaths_table_layout(win, app):
    """The Deaths tab's table as laid out: each Player, Killed by and From
    cell's (lines, width), by row and column, the page's height and its
    sideways scroll, and how many Positions links it has."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QTextCursor
    for _ in range(5):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
        app.processEvents()
    view = win.deaths_view
    document = view.document()
    cursor = QTextCursor(document)
    table = None
    while table is None and not cursor.atEnd():
        table = cursor.currentTable()
        cursor.movePosition(QTextCursor.NextBlock)
    layout = document.documentLayout()
    cells = {}
    for row in range(1, table.rows()):
        for column in (2, 4, 5):  # Player, Killed by (after its icon), From
            block = table.cellAt(row, column).firstCursorPosition().block()
            cells[f"{row},{column}"] = [block.layout().lineCount(),
                                        round(layout.blockBoundingRect(block).width())]
    return {"cells": cells, "height": round(document.size().height()),
            "scroll": view.horizontalScrollBar().maximum(),
            "links": view.toHtml().count("esolog:positions/")}


# The Deaths tab at 150% and 200% text in a 1366x768 main window, in the
# app's own font, without the Positions links and with them: printed as
# JSON (_deaths_table_layout). The config goes in the folder the test gives
_SIZE_SCRIPT = r"""
import json, sys
from pathlib import Path
root, tmp, pct = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
sys.path[:0] = [str(root), str(root / "src")]
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
app = QApplication([])
app.setFont(QFont("Segoe UI", 9))
from app_config import AppConfig
from gui.main_window import MainWindow
from tests.unit.test_positions_wiring_gui import _a_locator, _deaths_table_layout, _four_deaths

config = AppConfig(path=tmp / "config.json")
config.set("log_path", str(tmp / "Encounter.log"))
config.set("update.check_enabled", False)
config.set("display.text_scale", pct)
win = MainWindow(config)
win.worker_thread.quit()
win.worker_thread.wait(3000)
win.resize(1366, 768)
win.show()
entry = _four_deaths()
win._on_fight_completed(entry)
win.history_list.select_entry(entry)
win.fight_tabs.setCurrentWidget(win.deaths_view)
sizes = {}
for side, locator in (("before", None), ("after", _a_locator())):
    entry.locator = locator
    win._draw_deaths(entry)
    sizes[side] = _deaths_table_layout(win, app)
sizes["page"] = win.deaths_view.viewport().width()
print(json.dumps(sizes))
win.close()
"""


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestTheDeathsTabAtLargeText(WiringTestCase):
    """The Deaths tab's Positions links take no room (the review's finding
    19): at 150% and 200% text in a 1366x768 main window, From, Killed by,
    Player and the page's height are as they are without them. A column of
    its own took the room of From's and Player's 22% shares: at 200% in
    1366x768 'Lieutenant Njordal' went from 2-3 lines to 13."""

    def _sizes(self, pct):
        win = self._window(_four_deaths(), pct=pct)
        win.resize(1366, 768)
        self._deaths_page(win)
        entry = win._deaths_entry
        sizes = {}
        for side, locator in (("before", None), ("after", _a_locator())):
            entry.locator = locator
            win._draw_deaths(entry)
            sizes[side] = _deaths_table_layout(win, _app)
        return sizes

    def test_the_links_take_no_room_from_the_cells_in_the_runners_font(self):
        for pct in (150, 200):
            with self.subTest(pct=pct):
                sizes = self._sizes(pct)
                self.assertEqual((sizes["before"]["links"], sizes["after"]["links"]), (0, 4))
                for key in ("cells", "height", "scroll"):
                    self.assertEqual(sizes["after"][key], sizes["before"][key], key)

    @unittest.skipUnless(sys.platform == "win32" and Path("C:/Windows/Fonts/segoeui.ttf").exists(),
                         "the app's own font is measured on Windows")
    def test_the_links_take_no_room_from_the_cells_in_segoe_ui(self):
        """In Segoe UI 9 pt (in a process of its own, as the font folder is
        read when Qt starts); its config in a folder this test removes."""
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_FONTDIR="C:/Windows/Fonts")
        for pct in (150, 200):
            with self.subTest(pct=pct), tempfile.TemporaryDirectory() as tmp:
                done = subprocess.run(
                    [sys.executable, "-X", "utf8", "-c", _SIZE_SCRIPT, str(ROOT), tmp, str(pct)],
                    env=env, capture_output=True, text=True, timeout=180, check=False)
                self.assertEqual(done.returncode, 0, done.stderr[-2000:])
                sizes = json.loads(done.stdout.strip().splitlines()[-1])
                self.assertEqual((sizes["before"]["links"], sizes["after"]["links"]), (0, 4))
                for key in ("cells", "height", "scroll"):
                    self.assertEqual(sizes["after"][key], sizes["before"][key], (key, sizes))
                self.assertEqual(sizes["after"]["scroll"], 0)


def _theme_palette():
    """The dark palette of Qt's Windows 11 style, set by hand as
    scripts/capture_screenshots.py does (offscreen ignores the scheme)."""
    from PySide6.QtGui import QColor, QPalette
    palette = QPalette()
    for role, value in ((QPalette.Window, "#1e1e1e"), (QPalette.Base, "#2d2d2d"),
                        (QPalette.AlternateBase, "#353535"), (QPalette.Button, "#2d2d2d"),
                        (QPalette.WindowText, "#ffffff"), (QPalette.Text, "#ffffff"),
                        (QPalette.ButtonText, "#ffffff"), (QPalette.Highlight, "#4cc2ff"),
                        (QPalette.HighlightedText, "#000000")):
        palette.setColor(role, QColor(value))
    return palette


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestATheme(WiringTestCase):
    """The real window beside the real main window through a theme
    switch."""

    REAL = True

    def test_a_theme_switch_draws_the_tables_pictures_in_the_new_ink(self):
        """The review's finding 14: the main window refreshes its windows
        in the middle of Qt's palette change, before the positions window's
        table has the new palette its pictures' ink is read from; the
        window draws once more after it, so the pictures take the new
        theme's ink both ways."""
        from PySide6.QtCore import Qt

        from gui.positions_canvas import colors, is_dark
        from tests.unit.test_positions_window_gui import _icon_image
        entry = self._fight()
        win = self._window(entry)
        win.show_moment(entry, entry.locator.start_ms + 5000, "2")
        window = win._positions_window
        self.assertTrue(self._loaded(window, entry.locator))
        light = _app.palette()
        self.addCleanup(_app.setPalette, light)
        def ink():
            # Row 0's number cell (gui.positions_window is the harness's
            # module here, which holds the class alone)
            image = _icon_image(window.model.data(window.model.index(0, 0), Qt.DecorationRole))
            return image.pixelColor(image.width() // 2, image.height() // 2).name()
        for dark in (True, False):
            _app.setPalette(_theme_palette() if dark else light)
            # The palette's change comes on the event loop's next turn, and
            # the window's own redraw on the one after
            _pump(lambda dark=dark: ink() == colors(dark)["ink"].name(), timeout=1.0)
            self.assertEqual(is_dark(window.table), dark)
            self.assertEqual(ink(), colors(dark)["ink"].name(), dark)



@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestTheReadWaitedFor(WiringTestCase):
    """The review of PR #224: the read asked for is cleared only by an
    answer, and an earlier review's fights are kept one by one."""

    def test_a_cancelled_read_leaves_the_newer_read_of_the_fight_waited_for(self):
        """Fight A, then B, then A again: A's first read answers
        'cancelled' while its second runs, and must not clear it."""
        from fight_reread import RereadEvent
        entry = self._fight()
        win = self._window(entry)
        win._reread_pending = entry.locator
        win._on_reread_event(RereadEvent("cancelled", entry.locator))
        self.assertIs(win._reread_pending, entry.locator)
        win._on_reread_event(RereadEvent("missing", entry.locator, error="gone"))
        self.assertIsNone(win._reread_pending)

    def test_only_the_held_fight_of_an_earlier_review_is_kept(self):
        split = self._split()
        entry, extra = self._fight(split), self._fight(split)
        win = self._window()
        win._on_review_loaded(str(split), [entry, extra], source=(str(split), ""))
        win.history_list.select_entry(entry)
        win.show_moment(entry, entry.locator.start_ms, None)
        win._exit_review()
        self.assertEqual([fight for fight, _source in win._past_reviews], [entry])
        self.assertEqual(win._reread_places(entry)[0].kind, "review")

if __name__ == "__main__":
    unittest.main()
