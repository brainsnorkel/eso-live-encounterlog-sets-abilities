#!/usr/bin/env python3
"""The positions window's trails (#246) and the reader's view (#241),
offscreen, over the engine's own fight: test_positions_window_gui's
session with the healer walking in the first map frame, as the log
writes a walk (one axis a step, 0.0005 of the map), then quiet for 1.2 s
and on a step (a dashed gap), then thrown across the room (a jump)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_gui import HAVE_QT, _ensure_app
from tests.unit.test_positions_window_gui import (
    DEATH,
    DPS,
    HEALER,
    MAP_AT,
    START,
    PositionsTestCase,
    effect,
    healer,
    merged,
    session,
    split_and_states,
)

_app = None
WALK_FROM, STEP_MS, STEPS = START + 600, 200, 10
WALK_END = WALK_FROM + STEP_MS * STEPS          # the last step of the walk
QUIET_STEP = WALK_END + 1200                     # 1.2 s quiet, then a step: dashed
JUMP_AT = QUIET_STEP + 200                       # thrown across the room: dotted
AFTER = JUMP_AT + 300                            # a moment after it all, in frame 0
assert AFTER < MAP_AT


def walk_place(k):
    """The healer's place at step *k*: one axis a step, as the log has it."""
    return f"{0.45 + 0.0005 * ((k + 1) // 2):.4f}", f"{0.55 + 0.0005 * (k // 2):.4f}"


def walking():
    """The session with the healer's walk (see the module)."""
    extra = [effect(WALK_FROM + STEP_MS * k, healer(*walk_place(k))) for k in range(STEPS + 1)]
    x, y = walk_place(STEPS)
    extra.append(effect(QUIET_STEP, healer(f"{float(x) + 0.0005:.4f}", y)))
    extra.append(effect(JUMP_AT, healer("0.3000", "0.7000")))
    return merged(session(), extra)


def mouse(widget, kind, pos, button=None, buttons=None):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    kinds = {"press": QEvent.MouseButtonPress, "move": QEvent.MouseMove,
             "release": QEvent.MouseButtonRelease, "double": QEvent.MouseButtonDblClick}
    pos = QPointF(pos)
    event = QMouseEvent(kinds[kind], pos, QPointF(widget.mapToGlobal(pos.toPoint())),
                        button if button is not None else Qt.LeftButton,
                        buttons if buttons is not None else Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, event)


def wheel(widget, pos, notches=1):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication
    pos = QPointF(pos)
    event = QWheelEvent(pos, QPointF(widget.mapToGlobal(pos.toPoint())), QPoint(0, 0),
                        QPoint(0, 120 * notches), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class ViewTestCase(PositionsTestCase):

    @classmethod
    def setUpClass(cls):
        global _app
        _app = _ensure_app()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.log, cls.path, cls.fights, cls.states = split_and_states(cls.root, walking())
        cls.entry = cls.fights[0]

    def _empty(self, canvas):
        """A point of the canvas with no mark at or near it."""
        from PySide6.QtCore import QPointF
        for fx in (0.3, 0.5, 0.7, 0.2, 0.8):
            for fy in (0.85, 0.7, 0.5, 0.3):
                point = QPointF(canvas.width() * fx, canvas.height() * fy)
                near = [QPointF(point.x() + dx, point.y() + dy) for dx in (-60, 0, 60) for dy in (-30, 0, 30)]
                if all(canvas.unit_at(p) is None for p in near):
                    return point
        self.fail("no empty point")

    def _styles(self, window, key):
        strokes = {unit.key: stroke for unit, stroke in window.canvas.trail_strokes()}
        return {style for style, _band in strokes[key].paths} if key in strokes else set()


# ------------------------------------------------------------------ trails --

class TestTrails(ViewTestCase):

    def test_on_by_default_the_selected_units_last_10_s(self):
        from gui import positions_trails as tr
        window = self._window(t=AFTER, unit=HEALER)
        self.assertEqual(window.trail(), (tr.TRAIL_DEFAULT, tr.WHOSE_SELECTED))
        self.assertEqual([u.key for u in window.canvas.trail_units()], [HEALER])
        # The walk solid, the quiet step dashed, the throw dotted
        self.assertEqual(self._styles(window, HEALER), {tr.SOLID, tr.DASHED, tr.DOTTED})
        self.assertTrue(window.canvas.accessibleDescription().endswith("Trail: 3's last 10 s."))
        self.assertIn("the selected unit's last 10 s", window.show_button.toolTip())

    def test_the_trail_ends_at_the_mark(self):
        window = self._window(t=AFTER, unit=HEALER)
        healer_unit = self._unit(window, HEALER)
        ends = [(e.x, e.y) for _unit, stroke in window.canvas.trail_strokes()
                for path in stroke.paths.values()
                for e in (path.elementAt(k) for k in range(path.elementCount()))]
        self.assertIn((healer_unit.state.x, healer_unit.state.y), ends)

    def test_the_walk_is_drawn_through_its_midpoints(self):
        """The log's stairs: no drawn point of the walk is a corner of the
        staircase but its first and last places."""
        from gui import positions_trails as tr
        window = self._window(t=WALK_END, unit=HEALER)
        points = set()
        for _unit, stroke in window.canvas.trail_strokes():
            for (style, _band), path in stroke.paths.items():
                self.assertEqual(style, tr.SOLID)
                points |= {(round(path.elementAt(k).x, 6), round(path.elementAt(k).y, 6))
                           for k in range(path.elementCount())}
        corners = {(round(float(x), 6), round(float(y), 6))
                   for x, y in (walk_place(k) for k in range(1, STEPS))}
        self.assertFalse(points & corners)
        self.assertGreater(len(points), STEPS // 2)

    def test_10_s_leaves_out_what_came_before(self):
        """At the fight's end the walk's start is over 10 s old: the 10 s
        trail leaves it out, 30 s and the whole fight draw it."""
        from gui import positions_trails as tr
        from tests.unit.test_positions_window_gui import END
        first = tuple(round(float(v), 6) for v in walk_place(0))

        def points(window):
            return {(round(path.elementAt(k).x, 6), round(path.elementAt(k).y, 6))
                    for _unit, stroke in window.canvas.trail_strokes()
                    for path in stroke.paths.values() for k in range(path.elementCount())}
        window = self._window(t=END, unit=HEALER)
        self.assertGreater(END - 10_000, WALK_FROM)
        ten = points(window)
        self.assertNotIn(first, ten)
        window.set_trail(length=30_000)
        self.assertIn(first, points(window))
        window.set_trail(length=tr.TRAIL_WHOLE)
        whole = points(window)
        self.assertIn(first, whole)
        self.assertTrue(ten < whole)

    def test_every_player_draws_the_numbered_players_the_selected_on_top(self):
        from gui import positions_trails as tr
        from gui.positions_canvas import DRAWN, MARK_PLAYER
        window = self._window(t=AFTER, unit=HEALER)
        window.set_trail(whose=tr.WHOSE_EVERY)
        keys = [u.key for u in window.canvas.trail_units()]
        drawn = [u.key for u in window.scene().units if u.mark == MARK_PLAYER and u.where == DRAWN]
        self.assertEqual(sorted(keys), sorted(drawn))
        self.assertEqual(keys[-1], HEALER)
        self.assertIn("Trails: every player's last 10 s, 3's strongest",
                      window.canvas.accessibleDescription())

    def test_off_draws_none_and_says_nothing(self):
        from gui import positions_trails as tr
        window = self._window(t=AFTER, unit=HEALER)
        window.set_trail(length=tr.TRAIL_OFF)
        self.assertEqual(window.canvas.trail_strokes(), [])
        self.assertNotIn("Trail", window.canvas.accessibleDescription())
        self.assertIn("(off)", window.show_button.toolTip())

    def test_no_unit_selected_no_trail_and_the_reader_is_told(self):
        window = self._window(t=AFTER, unit=None)
        self.assertEqual(window.canvas.trail_strokes(), [])
        self.assertTrue(window.canvas.accessibleDescription().endswith("No trail: no unit selected."))

    def test_the_reader_is_told_when_the_selected_unit_is_not_drawn(self):
        """The review's finding 4: the leaver, selected, left in the
        lead-in, so in the fight it is not drawn and has no trail, and the
        description says so rather than naming one."""
        from gui.positions_canvas import LEFT
        from tests.unit.test_positions_window_gui import LEAVER
        window = self._window(t=AFTER, unit=LEAVER)
        self.assertEqual(self._unit(window, LEAVER).where, LEFT)
        self.assertEqual(window.canvas.trail_strokes(), [])
        self.assertTrue(window.canvas.accessibleDescription().endswith(
            "No trail: the selected unit is not drawn."))

    def test_the_show_menu_picks_it(self):
        from gui import positions_trails as tr
        window = self._window(t=AFTER, unit=HEALER)
        thirty = next(a for a in window.show_menu.actions() if a.text() == "Last 30 s")
        every = next(a for a in window.show_menu.actions() if a.text() == "Every player")
        thirty.trigger()
        every.trigger()
        self.assertEqual(window.trail(), (30_000, tr.WHOSE_EVERY))
        self.assertTrue(thirty.isChecked() and every.isChecked())
        ten = next(a for a in window.show_menu.actions() if a.text() == "Last 10 s")
        self.assertFalse(ten.isChecked())  # one length at a time
        # Kept when the window is given another moment, as Show's choices
        window.open(self.entry, AFTER - 100, HEALER, dark=False)
        self.assertEqual(window.trail(), (30_000, tr.WHOSE_EVERY))

    def test_a_trail_is_only_of_the_moments_map(self):
        """At the damage dealer's death, in frame 1, its trail does not
        reach back into frame 0's places."""
        window = self._window(t=DEATH + 500, unit=DPS)
        for _unit, stroke in window.canvas.trail_strokes():
            for path in stroke.paths.values():
                for k in range(path.elementCount()):
                    self.assertLess(path.elementAt(k).x, 0.3)  # frame 0's were at 0.6


# ------------------------------------------------------------- the view --

class TestTheView(ViewTestCase):

    def test_the_wheel_zooms_at_the_pointer(self):
        window = self._window(t=AFTER, unit=HEALER)
        canvas = window.canvas
        at = canvas.rect().center()
        at.setX(at.x() + 40)
        scale, ox, oy = canvas.transform()
        mx, my = (at.x() - ox) / scale, (at.y() - oy) / scale
        wheel(canvas, at, 2)
        self.assertAlmostEqual(canvas.zoom(), 1.25 ** 2)
        scale, ox, oy = canvas.transform()
        self.assertAlmostEqual(ox + mx * scale, at.x(), places=6)
        self.assertAlmostEqual(oy + my * scale, at.y(), places=6)
        self.assertTrue(window.fit_button.isEnabled())
        self.assertIn("Zoomed in 1.6x", window.canvas.accessibleDescription())
        wheel(canvas, at, -2)
        self.assertAlmostEqual(canvas.zoom(), 1.0)

    def test_the_buttons_zoom_and_fit(self):
        from gui.positions_canvas import BUTTON_ZOOM, ZOOM_MAX
        window = self._window(t=AFTER, unit=HEALER)
        self.assertFalse(window.fit_button.isEnabled())
        window.zoom_in_button.click()
        self.assertAlmostEqual(window.canvas.zoom(), BUTTON_ZOOM)
        self.assertTrue(window.fit_button.isEnabled())
        window.fit_button.click()
        self.assertEqual((window.canvas.zoom(), window.canvas.shift()), (1.0, (0.0, 0.0)))
        self.assertFalse(window.fit_button.isEnabled())
        for _ in range(20):
            window.zoom_in()
        self.assertEqual(window.canvas.zoom(), ZOOM_MAX)
        self.assertFalse(window.zoom_in_button.isEnabled())

    def test_a_drag_on_no_mark_pans_and_a_click_on_a_mark_selects(self):
        from PySide6.QtCore import QPointF, Qt
        window = self._window(t=AFTER, unit=HEALER)
        canvas = window.canvas
        empty = self._empty(canvas)
        mouse(canvas, "press", empty)
        mouse(canvas, "move", empty + QPointF(2, 0))           # under the slop: no pan
        self.assertEqual(canvas.shift(), (0.0, 0.0))
        mouse(canvas, "move", empty + QPointF(-50, -20))
        mouse(canvas, "release", empty + QPointF(-50, -20), buttons=Qt.NoButton)
        scale = canvas.transform()[0]
        self.assertAlmostEqual(canvas.shift()[0], 50 / scale)
        self.assertAlmostEqual(canvas.shift()[1], 20 / scale)
        self.assertEqual(window.selected(), HEALER)             # a drag picks no one
        dps = canvas.point_of(DPS)
        shift = canvas.shift()
        mouse(canvas, "press", dps)
        mouse(canvas, "move", dps + QPointF(30, 0))             # a press on a mark never pans
        mouse(canvas, "release", dps, buttons=Qt.NoButton)
        self.assertEqual(window.selected(), DPS)
        self.assertEqual(canvas.shift(), shift)

    def test_a_double_click_on_no_mark_fits_again(self):
        window = self._window(t=AFTER, unit=HEALER)
        canvas = window.canvas
        window.zoom_in()
        mouse(canvas, "double", self._empty(canvas))
        self.assertTrue(canvas.view_is_fitted())

    def test_kept_while_stepping_and_fitted_again_on_another_map(self):
        window = self._window(t=AFTER, unit=HEALER)
        window.zoom_in()
        zoom = window.canvas.zoom()
        window._step(1000)
        self.assertEqual(window.canvas.zoom(), zoom)
        window.play()
        window._tick()
        window.pause()
        self.assertEqual(window.canvas.zoom(), zoom)
        window._selected = DPS                                  # in frame 1 at its death
        window._go_to(DEATH + 500)
        self.assertEqual(window.scene().frame, 1)
        self.assertTrue(window.canvas.view_is_fitted())

    def test_fitted_again_for_another_reading(self):
        from fight_reread import RereadEvent
        window = self._window(t=AFTER, unit=HEALER)
        window.zoom_in()
        window.reread_done(RereadEvent("loaded", self.entry.locator, self.states))
        self.assertTrue(window.canvas.view_is_fitted())

    def test_the_buttons_sit_in_the_canvass_corner_and_marks_keep_out_from_under_them(self):
        window = self._window(t=AFTER, unit=HEALER)
        canvas = window.canvas
        overlay = canvas.overlay_rect()
        self.assertIsNotNone(overlay)
        self.assertTrue(canvas.rect().contains(overlay.toRect()))
        self.assertGreater(overlay.left(), canvas.width() / 2)
        self.assertGreater(overlay.top(), canvas.height() * 3 / 4)
        for box, _offset, _text in canvas.note_lines():
            self.assertFalse(box.intersects(overlay))
        # A unit pinned at the bottom right corner is pinned above the buttons
        healer_unit = self._unit(window, HEALER)
        x0, x1, y0, y1 = canvas.view_box()
        w, h = x1 - x0, y1 - y0
        canvas._shift = (healer_unit.state.x - (x0 + x1) / 2 - w,   # the healer past the bottom right
                         healer_unit.state.y - (y0 + y1) / 2 - h)
        canvas.update()
        item = next(i for i in canvas.placed() if i.unit.key == HEALER)
        self.assertTrue(item.pinned)
        self.assertFalse(overlay.contains(item.point))
        self.assertLess(item.point.y(), overlay.top())

    def test_a_reset_in_the_middle_of_a_drag_ends_it(self):
        """The review's finding 2: a reset (a new map frame, new states,
        Fit) while dragging left the closed hand on."""
        from PySide6.QtCore import QPointF, Qt
        window = self._window(t=AFTER, unit=HEALER)
        canvas = window.canvas
        at = self._empty(canvas)
        mouse(canvas, "press", at)
        mouse(canvas, "move", at + QPointF(-40, 0))
        self.assertEqual(canvas.cursor().shape(), Qt.ClosedHandCursor)
        window.fit_view()
        self.assertEqual(canvas.cursor().shape(), Qt.ArrowCursor)
        mouse(canvas, "release", at + QPointF(-40, 0), buttons=Qt.NoButton)
        mouse(canvas, "move", at + QPointF(-80, 0))             # no button: nothing pans
        self.assertTrue(canvas.view_is_fitted())

    def test_a_unit_under_the_buttons_in_the_view_is_pinned_above_them(self):
        """The review's finding 3: a unit in the view but under the
        buttons could be neither seen nor clicked."""
        window = self._window(t=AFTER, unit=HEALER)
        canvas = window.canvas
        overlay = canvas.overlay_rect()
        scale, ox, oy = canvas.transform()
        healer_unit = self._unit(window, HEALER)
        # Shift the view so the healer's place is under the buttons and in
        # the drawn area (not past its edge, where it is pinned anyway)
        margin = canvas.margin()
        cx, cy = overlay.left() + 6, overlay.top() + 3
        self.assertLess(cy, canvas.height() - margin)
        self.assertLess(cx, canvas.width() - margin)
        hx, hy = ox + healer_unit.state.x * scale, oy + healer_unit.state.y * scale
        canvas._shift = (canvas._shift[0] + (hx - cx) / scale, canvas._shift[1] + (hy - cy) / scale)
        item = next(i for i in canvas.placed() if i.unit.key == HEALER)
        self.assertTrue(item.pinned)
        self.assertLess(item.point.y(), overlay.top())
        self.assertIs(canvas.unit_at(item.point).unit.key, HEALER)

    def test_notes_reaching_the_buttons_stop_short_of_them(self):
        """At 200% text on the shortest canvas, the deaths' notes (six
        lines at most) can run down to the buttons in the corner (in Segoe
        UI, 228 px against 212): a line that reaches them is cut short of
        them. A taller panel stands in for them here, as the tests' font
        is not Segoe UI."""
        from PySide6.QtWidgets import QFrame

        from gui.positions_canvas import CANVAS_LEAST, Note, PositionsCanvas
        window = self._window(t=AFTER, unit=HEALER)
        canvas = PositionsCanvas()
        self.addCleanup(canvas.deleteLater)
        canvas.resize(*CANVAS_LEAST)
        panel = QFrame()
        panel.setFixedSize(120, 200)
        canvas.set_overlay(panel)
        canvas.show()
        _ensure_app().processEvents()
        notes = tuple(Note(0, 1, "@dps", "A very long ability name indeed", "A long killer name")
                      for _ in range(8))
        canvas.set_scene(window.scene()._replace(notes=notes))
        overlay = canvas.overlay_rect()
        lines = canvas.note_lines()
        self.assertTrue(any(box.bottom() > overlay.top() for box, _o, _t in lines))
        for box, _offset, _text in lines:
            self.assertFalse(box.intersects(overlay))

    def test_fine_wheel_steps_come_back_to_the_fitted_view(self):
        """The review's finding 5: a high-resolution wheel's eighth notches
        there and back left the zoom a hair off 1."""
        window = self._window(t=AFTER, unit=HEALER)
        canvas = window.canvas
        at = canvas.rect().center()
        for _ in range(8):
            canvas.zoom_by(1.25 ** (15 / 120), at)
        for _ in range(8):
            canvas.zoom_by(1.25 ** (-15 / 120), at)
        self.assertEqual(canvas.zoom(), 1.0)
        self.assertNotIn("Zoomed", window.canvas.accessibleDescription())

    def test_a_fight_that_moves_is_followed(self):
        """Where the window's FollowView gives a box of the moment, the
        scene is drawn in it and the reader is told."""
        window = self._window(t=AFTER, unit=HEALER)

        class Follow:
            def follows(self, frame):
                return frame == 0

            def box_at(self, frame, t):
                return (0.4, 0.5, 0.5, 0.6) if frame == 0 else None
        window._follow = Follow()
        window._step(100)
        self.assertEqual(window.scene().box, (0.4, 0.5, 0.5, 0.6))
        self.assertTrue(window.follows())
        self.assertIn("View follows the group", window.canvas.accessibleDescription())
        window._selected = DPS
        window._go_to(DEATH + 500)                              # frame 1: held still
        self.assertNotEqual(window.scene().box, (0.4, 0.5, 0.5, 0.6))
        self.assertNotIn("follows", window.canvas.accessibleDescription())

    def test_the_fit_is_of_the_fight_not_its_lead_in(self):
        """The leaver stood at (0.3, 0.3) in the lead-in only: the fight's
        box leaves it out, though it is in the range read."""
        from gui.positions_canvas import fit_boxes
        x0, x1, y0, y1 = fit_boxes(self.states)[0]
        self.assertFalse(x0 <= 0.3 <= x1 and y0 <= 0.3 <= y1)


if __name__ == "__main__":
    unittest.main()
