#!/usr/bin/env python3
"""Playing a fight back in the positions window (issue #232), offscreen:
Play and Pause, Space, the speeds, the marks gliding while playing, the
paused window exactly as before, the end of the fight, the table and the
descriptions once a second, and what pauses playback.

The fight is the positions window tests' session (test_positions_window_gui)
with a few more lines: the damage dealer written again unchanged at
GLIDE_FROM, then moved at GLIDE_TO, half a second later, and again at
JUMP_TO, a second and a half after that; the tank written at its place
half a second before it stands far off the map (FAR_AT), and 0.4 s before
the map changes (MAP_AT). The wall clock is a FakeClock the tests move by
hand, and each frame is the window's _tick, so nothing sleeps."""

import copy
import os
import unittest
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_gui import HAVE_QT, _ensure_app
from tests.unit.test_positions_window_gui import (
    BOSS,
    DEATH,
    DPS,
    END,
    FAR_AT,
    MAP_AT,
    START,
    TANK,
    PositionsTestCase,
    dps,
    effect,
    merged,
    session,
    split_and_states,
    state,
    tank,
)

_app = None
GLIDE_FROM = START + 1300   # the damage dealer written again at (0.6, 0.5)
GLIDE_TO = START + 1800     # then at (0.7, 0.5), its heading 0.5
JUMP_TO = START + 3300      # then at (0.7, 0.6), 1.5 s later
DPS_HEADING = 1.5708        # its heading until GLIDE_TO


def moving():
    """The session (see the module) with the moves."""
    def moved(x, y):
        return state(DPS, hp="18000/18000", x=x, y=y, heading="0.5000")
    return merged(session(), [
        effect(GLIDE_FROM, dps("0.6000", "0.5000")),
        effect(GLIDE_TO, moved("0.7000", "0.5000")),
        effect(JUMP_TO, moved("0.7000", "0.6000")),
        effect(FAR_AT - 500, tank("0.4000", "0.5000")),
        effect(MAP_AT - 300, tank("0.4000", "0.5000")),
    ])


class FakeClock:
    """The wall clock playback reads (PositionsWindow._wall_ms), in ms,
    moved by hand."""

    def __init__(self, now: float = 0.0):
        self.now = float(now)

    def __call__(self) -> float:
        return self.now


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class PlaybackTestCase(PositionsTestCase):

    @classmethod
    def setUpClass(cls):
        global _app
        super().setUpClass()
        _app = _ensure_app()
        cls.log, cls.path, cls.fights, cls.states = split_and_states(cls.root, moving(),
                                                                      "moving.log")
        cls.entry = cls.fights[0]

    def setUp(self):
        global _app
        super().setUp()
        _app = _ensure_app()

    def _clocked(self, t=START, unit=DPS, **kwargs):
        """A window at moment *t*, paused, on a FakeClock."""
        window = self._window(t=t, unit=unit, **kwargs)
        clock = FakeClock()
        window._wall_ms = clock
        return window, clock

    def _frame(self, window, clock, ms):
        """*ms* of wall time, then a frame; whether it updated what a
        reader reads."""
        clock.now += ms
        return window._tick()

    def _place(self, window, key):
        state = self._unit(window, key).state
        return round(state.x, 4), round(state.y, 4)


# ----------------------------------------------------------- the session --

class TestTheSession(PlaybackTestCase):

    def test_the_engine_made_the_moves(self):
        track = self.states.track_of(DPS, START + 2000)
        times = list(track.t)
        self.assertIn(GLIDE_TO, times)
        self.assertIn(JUMP_TO, times)
        index = track.at(GLIDE_FROM)
        self.assertEqual(track.seen[index], GLIDE_FROM)  # written again, unchanged
        self.assertEqual(track.at(GLIDE_TO), index + 1)
        first = self.entry.players[0]
        self.assertEqual((first["unit_id"], first["role"]), (DPS, "D"))


# ---------------------------------------------------------- play and pause --

class TestPlayAndPause(PlaybackTestCase):

    def test_the_button_plays_and_pauses(self):
        from PySide6.QtCore import Qt

        from gui.positions_window import FRAME_MS, PAUSE_TEXT, PLAY_TEXT
        window, _clock = self._clocked()
        button = window.play_button
        self.assertFalse(window.is_playing())
        self.assertEqual((button.text(), button.accessibleName()), (PLAY_TEXT, "Play"))
        button.click()
        self.assertTrue(window.is_playing())
        self.assertEqual((button.text(), button.accessibleName()), (PAUSE_TEXT, "Pause"))
        timer = window._play_timer
        self.assertTrue(timer.isActive())
        self.assertEqual((timer.interval(), timer.timerType()), (FRAME_MS, Qt.PreciseTimer))
        button.click()
        self.assertFalse(window.is_playing())
        self.assertFalse(timer.isActive())
        self.assertEqual(button.accessibleName(), "Play")

    def test_space_in_the_table_or_on_the_bar_plays_and_pauses(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        window, _clock = self._clocked()
        self._active(window)
        window.table.setFocus()
        QTest.keyClick(window.table, Qt.Key_Space)
        self.assertTrue(window.is_playing())
        QTest.keyClick(window.table, Qt.Key_Space)
        self.assertFalse(window.is_playing())
        window.scrub.setFocus()
        QTest.keyClick(window.scrub, Qt.Key_Space)
        self.assertTrue(window.is_playing())
        QTest.keyClick(window.scrub, Qt.Key_Space)
        self.assertFalse(window.is_playing())
        # Ctrl+Space is not Space
        QTest.keyClick(window.table, Qt.Key_Space, Qt.ControlModifier)
        self.assertFalse(window.is_playing())

    def test_space_held_down_toggles_once(self):
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent
        window, _clock = self._clocked()
        self._active(window)
        window.table.setFocus()
        for repeat in (False, True):  # a second toggle would pause it
            _app.sendEvent(window.table, QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier,
                                                   " ", repeat))
        self.assertTrue(window.is_playing())

    def test_space_on_a_button_is_the_buttons_own(self):
        """Space on a focused '+1 s' steps a second, as it did; on the
        play button it plays once, not twice."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        window, _clock = self._clocked()
        self._active(window)
        window.forward.setFocus()
        QTest.keyClick(window.forward, Qt.Key_Space)
        self.assertEqual(window.moment(), START + 1000)
        self.assertFalse(window.is_playing())
        window.play_button.setFocus()
        QTest.keyClick(window.play_button, Qt.Key_Space)
        self.assertTrue(window.is_playing())

    def test_nothing_plays_while_the_fight_is_read(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from fight_reread import RereadEvent
        window = self._window(t=START, load=False)
        self.assertFalse(window.play_button.isEnabled())
        window.play()
        self.assertFalse(window.is_playing())
        self._active(window)
        window.table.setFocus()
        QTest.keyClick(window.table, Qt.Key_Space)
        self.assertFalse(window.is_playing())
        window.reread_done(RereadEvent("loaded", self.entry.locator, self.states))
        self.assertTrue(window.play_button.isEnabled())
        self.assertFalse(window.is_playing())  # the states never start it

    def test_only_play_starts_it(self):
        """Motion (#232): opening, the states coming, a speed, a refresh,
        an update of the fight and the Show menu never start playback."""
        from gui.name_mask import NameMask
        window, _clock = self._clocked()
        window.set_speed(4)
        window.faster()
        window.refresh(True, names=NameMask.for_entry(self.entry, True))
        window.entry_updated(self.entry, False, None)
        window.set_shown("pet", True)
        _app.processEvents()
        self.assertFalse(window.is_playing())
        self.assertFalse(window._play_timer.isActive())

    def test_the_real_timer_runs_the_moment(self):
        """Without the fake clock: the precise timer's frames move the
        moment by the wall clock."""
        from PySide6.QtTest import QTest
        window = self._window(t=START)
        window.play()
        QTest.qWait(200)
        moved = window.moment() - START
        window.pause()
        self.assertGreater(moved, 50)
        self.assertLess(moved, 2000)


# ----------------------------------------------------------------- speeds --

class TestSpeeds(PlaybackTestCase):

    def test_each_speed_moves_by_the_wall_time_times_the_speed(self):
        from gui.positions_window import SPEEDS
        self.assertEqual(SPEEDS, (1, 2, 3, 4, 5))
        window, clock = self._clocked()
        for speed in SPEEDS:
            window._go_to(START)
            window.set_speed(speed)
            window.play()
            self._frame(window, clock, 300)
            self._frame(window, clock, 100)
            self.assertEqual(window.moment(), START + 400 * speed, speed)
            self.assertEqual(window.scene().t, START + 400 * speed)
            window.pause()

    def test_a_slow_frame_does_not_slow_the_fight(self):
        window, clock = self._clocked()
        window.set_speed(2)
        window.play()
        self._frame(window, clock, 700)  # one frame, 700 ms late
        self.assertEqual(window.moment(), START + 1400)

    def test_a_new_speed_goes_on_from_the_moment_reached(self):
        window, clock = self._clocked()
        window.play()
        clock.now += 500                 # no frame in between
        window.set_speed(3)
        self._frame(window, clock, 500)
        self.assertEqual(window.moment(), START + 500 + 1500)

    def test_the_picker_and_the_keys(self):
        window, _clock = self._clocked()
        self._active(window)
        window.table.setFocus()
        self.assertEqual([window.speed_box.itemText(i) for i in range(window.speed_box.count())],
                         ["1x", "2x", "3x", "4x", "5x"])
        window.speed_box.setCurrentIndex(2)
        self.assertEqual(window.speed(), 3)
        self._press(window, "Ctrl+.")
        self.assertEqual((window.speed(), window.speed_box.currentText()), (4, "4x"))
        for _ in range(3):
            self._press(window, "Ctrl+.")
        self.assertEqual(window.speed(), 5)
        for _ in range(6):
            self._press(window, "Ctrl+,")
        self.assertEqual((window.speed(), window.speed_box.currentText()), (1, "1x"))
        self.assertFalse(window.is_playing())


# ---------------------------------------------------------------- gliding --

class TestGliding(PlaybackTestCase):

    def _playing_at(self, window, clock, t):
        """Playing, at moment *t*: from a second before."""
        window._go_to(t - 1000)
        window.play()
        self._frame(window, clock, 1000)
        self.assertEqual(window.moment(), t)

    def test_a_mark_glides_between_samples_half_a_second_apart_while_playing(self):
        window, clock = self._clocked()
        middle = (GLIDE_FROM + GLIDE_TO) // 2
        window._go_to(middle)
        self.assertEqual(self._place(window, DPS), (0.6, 0.5))  # paused: the last sample
        self._playing_at(window, clock, middle)
        self.assertEqual(self._place(window, DPS), (0.65, 0.5))
        point = window.canvas.point_of(DPS)
        self._frame(window, clock, 100)
        self.assertEqual(self._place(window, DPS), (0.67, 0.5))
        self.assertGreater(window.canvas.point_of(DPS).x(), point.x())  # drawn further on
        # The heading stays the last sample's
        self.assertAlmostEqual(self._unit(window, DPS).state.heading, DPS_HEADING, places=3)
        window.pause()
        self.assertEqual(self._place(window, DPS), (0.6, 0.5))

    def test_it_glides_from_the_last_line_that_wrote_the_place(self):
        """Written again unchanged at GLIDE_FROM: it stood there until
        then, and glides only after."""
        window, clock = self._clocked()
        self._playing_at(window, clock, GLIDE_FROM - 100)
        self.assertEqual(self._place(window, DPS), (0.6, 0.5))

    def test_no_glide_between_samples_over_a_second_apart(self):
        window, clock = self._clocked()
        self._playing_at(window, clock, (GLIDE_TO + JUMP_TO) // 2)
        self.assertEqual(self._place(window, DPS), (0.7, 0.5))

    def test_no_glide_into_another_map_or_off_the_map(self):
        window, clock = self._clocked(unit=TANK)
        self._playing_at(window, clock, MAP_AT - 100)
        self.assertEqual(self._place(window, TANK), (0.4, 0.5))
        window.pause()
        self._playing_at(window, clock, FAR_AT - 250)
        self.assertEqual(self._place(window, TANK), (0.4, 0.5))

    def test_glide_state_alone(self):
        from gui.positions_canvas import GLIDE_MS, glide_state
        self.assertEqual(GLIDE_MS, 1000)
        track = self.states.track_of(DPS, GLIDE_FROM)
        last = track.row(track.at(GLIDE_FROM))
        self.assertIs(glide_state(track, last, GLIDE_FROM), last)
        moved = glide_state(track, last, GLIDE_FROM + 100)
        self.assertAlmostEqual(moved.x, 0.62, places=4)
        self.assertEqual(moved._replace(x=last.x, y=last.y), last)  # only the place moves

    def test_paused_is_exactly_as_before(self):
        """Played to a moment and paused, the window shows what it shows
        opened there and never played: the places, the looks, the table,
        the descriptions, the bars, the lines, the canvas's pixels."""
        from PySide6.QtCore import Qt
        middle = (GLIDE_FROM + GLIDE_TO) // 2
        played, clock = self._clocked(t=middle - 1500)
        played.play()
        for ms in (200, 300, 1000):  # one frame updates what a reader reads
            self._frame(played, clock, ms)
        self.assertEqual(played.moment(), middle)
        still = self._window(t=middle)
        self.assertNotEqual(played.scene(), still.scene())  # glided
        played.pause()
        self.assertEqual(played.scene(), still.scene())
        roles = (Qt.DisplayRole, Qt.AccessibleTextRole, Qt.ToolTipRole, Qt.TextAlignmentRole)
        for model in (played.model, still.model):
            self.assertEqual(model.rowCount(), still.model.rowCount())
        for row in range(still.model.rowCount()):
            for column in range(still.model.columnCount()):
                for role in roles:
                    self.assertEqual(played.model.data(played.model.index(row, column), role),
                                     still.model.data(still.model.index(row, column), role))
        for get in (lambda w: w.canvas.accessibleDescription(),
                    lambda w: w.table.accessibleDescription(),
                    lambda w: w.boss_bars.rows(), lambda w: w.boss_bars.accessibleDescription(),
                    lambda w: w.elsewhere_label.text(), lambda w: w.fight_label.text(),
                    lambda w: w.clock.text(), lambda w: w.scrub.value(),
                    lambda w: w.scrub.moment(), lambda w: w.scrub.accessibleDescription(),
                    lambda w: [b.isEnabled() for b in (w.previous_death, w.back, w.forward,
                                                       w.next_death)],
                    lambda w: w.table.selectionModel().selectedRows()[0].row(),
                    lambda w: [(p.unit.key, p.point.x(), p.point.y()) for p in w.canvas.placed()]):
            self.assertEqual(get(played), get(still))
        self.assertEqual(played.canvas.grab().toImage(), still.canvas.grab().toImage())


# ---------------------------------------------------------------- the end --

class TestTheEnd(PlaybackTestCase):

    def test_it_stops_at_the_fights_end_and_plays_again_from_its_start(self):
        window, clock = self._clocked(t=END - 300)
        window.play()
        self._frame(window, clock, 200)
        self.assertTrue(window.is_playing())
        self._frame(window, clock, 200)
        self.assertEqual(window.moment(), END)
        self.assertFalse(window.is_playing())
        self.assertFalse(window._play_timer.isActive())
        self.assertEqual(window.play_button.accessibleName(), "Play")
        window.play()
        self.assertEqual(window.moment(), START)
        self.assertTrue(window.is_playing())
        # From the tail after the end, too
        window._go_to(END + 500)
        window.play()
        self.assertEqual(window.moment(), START)

    def test_a_death_does_not_stop_it(self):
        window, clock = self._clocked(t=DEATH - 200)
        window.play()
        self._frame(window, clock, 400)
        self.assertTrue(window.is_playing())
        self.assertEqual(window.moment(), DEATH + 200)


# -------------------------------------------- what a reader reads, and when --

class TestOnceASecond(PlaybackTestCase):

    def test_the_table_and_the_descriptions_follow_once_a_second(self):
        from gui.positions_window import DESCRIBE_MS
        self.assertEqual(DESCRIBE_MS, 1000)
        window, clock = self._clocked()
        changes = []
        window.model.dataChanged.connect(lambda *_args: changes.append("data"))
        window.model.modelReset.connect(lambda: changes.append("reset"))
        first = window.canvas.accessibleDescription()
        header, bosses = window.fight_label.text(), window.boss_bars.accessibleDescription()
        scrub = (window.scrub.value(), window.scrub.accessibleDescription())
        self.assertEqual(bosses, "Test Boss not in the log yet")
        window.play()
        changes.clear()
        self.assertFalse(self._frame(window, clock, 300))
        # The picture, the clock, the bar's mark and the boss bars' paint moved...
        self.assertEqual(window.scene().t, START + 300)
        self.assertEqual(window.clock.text(), "0:00.3")
        self.assertEqual(window.scrub.moment(), START + 300)
        self.assertEqual(window.boss_bars.rows(), [("Test Boss", 970_000, 1_000_000, True)])
        # ...and nothing a reader reads
        self.assertEqual(changes, [])
        self.assertEqual(window.canvas.accessibleDescription(), first)
        self.assertEqual(window.table.accessibleDescription(), first)
        self.assertEqual(window.fight_label.text(), header)
        self.assertEqual(window.boss_bars.accessibleDescription(), bosses)
        self.assertEqual((window.scrub.value(), window.scrub.accessibleDescription()), scrub)
        self.assertTrue(self._frame(window, clock, 700))
        self.assertTrue(changes)
        self.assertTrue(window.canvas.accessibleDescription().startswith(
            "0:01.0 into the fight. Test Boss 97%."))
        self.assertEqual(window.table.accessibleDescription(), window.canvas.accessibleDescription())
        self.assertEqual(window.boss_bars.accessibleDescription(),
                         "Test Boss 97% (970,000 of 1,000,000)")
        self.assertIn("0:01.0 of", window.fight_label.text())
        self.assertEqual(window.scrub.value(), 1)
        changes.clear()
        self.assertFalse(self._frame(window, clock, 200))
        self.assertEqual(changes, [])
        window.pause()
        self.assertTrue(changes)
        self.assertTrue(window.canvas.accessibleDescription().startswith("0:01.2 into the fight."))

    def test_a_frame_paints_the_picture_alone_and_asks_no_layout(self):
        """The canvas paints all of itself, so the panes under it are not
        painted again; the clock's new text and the boss's new health ask
        the window for no layout (measured: one every fifth frame)."""
        from PySide6.QtCore import QEvent, QObject

        class Count(QObject):
            def __init__(self):
                super().__init__()
                self.seen = []

            def eventFilter(self, obj, event):
                if event.type() in (QEvent.Paint, QEvent.LayoutRequest):
                    self.seen.append((obj, event.type()))
                return False
        window, clock = self._clocked()
        count = Count()
        under = (window.splitter, window.canvas.parentWidget())
        for part in (window, window.canvas, *under):
            part.installEventFilter(count)
        window.play()
        _app.processEvents()
        count.seen.clear()
        for _ in range(6):  # the boss's health changes at START + 100 to 300
            self.assertFalse(self._frame(window, clock, 100))
            _app.processEvents()
        kinds = {(obj, kind) for obj, kind in count.seen}
        self.assertIn((window.canvas, QEvent.Paint), kinds)
        for part in under:
            self.assertNotIn((part, QEvent.Paint), kinds)
        self.assertNotIn((window, QEvent.LayoutRequest), kinds)
        for part in (window, window.canvas, *under):
            part.removeEventFilter(count)

    def test_a_frame_leaves_the_table_where_the_reader_scrolled_it(self):
        window, clock = self._clocked()
        window.table.setFixedHeight(80)
        _app.processEvents()
        bar = window.table.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(bar.maximum())
        window.play()
        self._frame(window, clock, 400)
        self._frame(window, clock, 700)  # what a reader reads
        self.assertEqual(bar.value(), bar.maximum())
        self.assertEqual(window.selected(), DPS)


# ------------------------------------------------- what pauses, what not --

class TestWhatPauses(PlaybackTestCase):

    def _playing(self, t=START + 2000, unit=DPS):
        window, clock = self._clocked(t=t, unit=unit)
        window.play()
        self._frame(window, clock, 500)
        return window, clock

    def test_a_step_pauses_there(self):
        window, _clock = self._playing()
        window.back.click()
        self.assertFalse(window.is_playing())
        self.assertEqual(window.moment(), START + 1500)
        window, _clock = self._playing()
        self._active(window)
        window.table.setFocus()
        self._press(window, "Ctrl+Right")
        self.assertFalse(window.is_playing())
        self.assertEqual(window.moment(), START + 3500)

    def test_a_scrub_pauses_there(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        window, _clock = self._playing()
        bar = window.scrub
        QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier,
                         QPoint(round(bar.x_of(DEATH)), int(bar._band().center().y())))
        self.assertFalse(window.is_playing())
        self.assertLess(abs(window.moment() - DEATH), 200)
        window, _clock = self._playing()
        self._active(window)
        bar = window.scrub
        bar.setFocus()
        QTest.keyClick(bar, Qt.Key_Right)
        self.assertFalse(window.is_playing())
        self.assertEqual(window.moment(), START + 3500)

    def test_a_death_pauses_there(self):
        window, _clock = self._playing()
        window.next_death.click()
        self.assertFalse(window.is_playing())
        self.assertEqual((window.moment(), window.selected()), (DEATH, DPS))

    def test_a_selection_a_speed_or_the_show_menu_play_on(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        window, clock = self._playing()
        window.table.setCurrentIndex(window.model.index(window.model.row_of(TANK), 0))
        self.assertEqual(window.selected(), TANK)
        point = window.canvas.point_of(f"{BOSS}@1200")
        QTest.mouseClick(window.canvas, Qt.LeftButton, Qt.NoModifier, point.toPoint())
        self.assertEqual(window.selected(), f"{BOSS}@1200")
        window.set_speed(2)
        window.set_shown("pet", True)
        self.assertTrue(window.is_playing())
        self._frame(window, clock, 100)
        self.assertEqual(window.moment(), START + 2700)

    def test_the_play_button_keeps_its_width(self):
        """The wider of its words sets its width, so Pause never moves
        the speed picker and the bar."""
        window, _clock = self._clocked()
        before = (window.speed_box.x(), window.scrub.x())
        window.play()
        _app.processEvents()
        self.assertEqual((window.speed_box.x(), window.scrub.x()), before)


# --------------------------------------------- the timer goes with the fight --

class TestTheTimerStops(PlaybackTestCase):

    def _playing(self):
        window, clock = self._clocked(t=START + 2000)
        window.play()
        return window, clock

    def test_closing_stops_it(self):
        window, _clock = self._playing()
        window.close()
        self.assertFalse(window.is_playing())
        self.assertFalse(window._play_timer.isActive())

    def test_esc_stops_it(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        window, _clock = self._playing()
        self._active(window)
        QTest.keyClick(window.table, Qt.Key_Escape)
        self.assertFalse(window.isVisible())
        self.assertFalse(window._play_timer.isActive())

    def test_minimised_it_pauses_keeping_the_fight(self):
        from PySide6.QtGui import QHideEvent

        class Spontaneous(QHideEvent):
            def spontaneous(self):
                return True
        window, clock = self._clocked(t=GLIDE_FROM)
        window.play()
        self._frame(window, clock, 250)
        self.assertEqual(self._place(window, DPS), (0.65, 0.5))
        window.hideEvent(Spontaneous())
        self.assertFalse(window.is_playing())
        self.assertIs(window.states(), self.states)
        self.assertEqual(self._place(window, DPS), (0.6, 0.5))  # paused: no glide

    def test_another_fight_stops_it(self):
        window, _clock = self._playing()
        other = copy.copy(self.entry)
        window.open(other, DEATH, DPS, dark=False, names=None)
        self.assertFalse(window.is_playing())
        self.assertFalse(window._play_timer.isActive())
        self.assertEqual(window.moment(), DEATH)

    def test_new_states_or_a_new_locator_stop_it(self):
        from fight_reread import RereadEvent
        window, _clock = self._playing()
        window.reread_done(RereadEvent("loaded", self.entry.locator, self.states))
        self.assertFalse(window.is_playing())
        entry = copy.copy(self.entry)
        window, _clock = self._clocked(entry=entry)
        window.play()
        entry.locator = entry.locator._replace(end_ms=entry.locator.end_ms + 5000)
        window.entry_updated(entry, False, None)
        _app.processEvents()
        self.assertIsNone(window.states())
        self.assertFalse(window.is_playing())
        self.assertFalse(window._play_timer.isActive())

    def test_a_rebind_stops_it(self):
        window, _clock = self._playing()
        replayed = copy.copy(self.entry)
        replayed.locator = self.entry.locator._replace()
        window.rebind(replayed, None)
        self.assertFalse(window.is_playing())

    def test_a_window_playing_is_freed_when_deleted(self):
        from PySide6.QtCore import QCoreApplication, QEvent

        from fight_reread import RereadEvent
        from gui.positions_window import PositionsWindow
        window = PositionsWindow()
        window._wall_ms = FakeClock()
        window.open(self.entry, START, DPS, dark=False, names=None)
        window.reread_done(RereadEvent("loaded", self.entry.locator, self.states))
        window.play()
        window._tick()
        _app.processEvents()
        freed = weakref.ref(window)
        window.deleteLater()
        del window
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertIsNone(freed())


# ------------------------------------------------- named, reachable, fits --

class TestTheControls(PlaybackTestCase):

    def test_they_are_named_and_reached_by_tab_only(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeySequence, QShortcut
        window = self._window()
        self.assertEqual((window.play_button.accessibleName(), window.speed_box.accessibleName()),
                         ("Play", "Speed"))
        self.assertEqual(window.speed_box.focusPolicy(), Qt.TabFocus)
        self.assertEqual(window.play_button.focusPolicy(), Qt.TabFocus)
        keys = {shortcut.key().toString() for shortcut in window.findChildren(QShortcut)}
        self.assertTrue({QKeySequence("Ctrl+,").toString(), QKeySequence("Ctrl+.").toString()}
                        <= keys)
        self.assertNotIn(QKeySequence("Space").toString(), keys)  # a button keeps its own

    def test_they_fit_1280_by_720_at_200_percent(self):
        from PySide6.QtCore import QPoint, QRect

        from gui import text_size
        budget = (1280, 720 - 40 - 32)
        text_size.apply(200)
        window = self._window(size=budget)
        window.play()
        self.assertLessEqual(window.minimumSizeHint().width(), budget[0])
        for part in (window.play_button, window.speed_box, window.scrub, window.clock):
            place = QRect(part.mapTo(window, QPoint(0, 0)), part.size())
            self.assertTrue(window.rect().contains(place), part.accessibleName())
        clock = window.clock
        self.assertGreaterEqual(clock.width(), clock.fontMetrics().horizontalAdvance("-00:00.0"))
        window.pause()


class TestTheGuide(unittest.TestCase):

    def test_the_positions_section_and_accessibility_say_how_it_plays(self):
        from pathlib import Path

        from gui.positions_canvas import GLIDE_MS
        text = (Path(__file__).resolve().parents[2] / "docs" / "user-guide.md").read_text(
            encoding="utf-8")
        start = text.index("\n## Positions\n")
        section = text[start:text.find("\n## ", start + 5)]
        for words in ("**Play**", "1x to 5x", "Space", f"at most {GLIDE_MS // 1000} second apart",
                      "never moves a mark off the place the log last gave it",
                      "stops at the fight's end"):
            self.assertIn(words, section)
        access = text[text.index("\n## Accessibility\n"):]
        self.assertIn("only when you press **Play**", access)


if __name__ == "__main__":
    unittest.main()
