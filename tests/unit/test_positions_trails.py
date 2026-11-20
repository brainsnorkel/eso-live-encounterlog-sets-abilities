#!/usr/bin/env python3
"""The positions canvas's trails and following view (issues #246 and
#241), apart from any widget: a track's places as a trail (gaps, jumps,
breaks, the midpoint smoothing), its cached chunks against a plain
segment-by-segment reference, the taper, and the boxes of a fight that
moves."""

import math
import os
import random
import unittest
from bisect import bisect_right
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_gui import HAVE_QT

if HAVE_QT:
    from gui import positions_trails as tr


class FakeTrack:
    """A track as fight_reread gives one: columns as lists, at(t)."""

    def __init__(self, rows, kind="group", key="1"):
        # rows: (t, x, y, frame, seen[, health, health_max])
        self.t = [r[0] for r in rows]
        self.x = [r[1] for r in rows]
        self.y = [r[2] for r in rows]
        self.frame = [r[3] for r in rows]
        self.seen = [r[4] for r in rows]
        self.health = [r[5] if len(r) > 5 else 100 for r in rows]
        self.health_max = [r[6] if len(r) > 6 else 100 for r in rows]
        self.unit = SimpleNamespace(kind=kind, key=key, since_ms=0)
        self.ids = (key,)

    def __len__(self):
        return len(self.t)

    def at(self, t_ms):
        return bisect_right(self.t, t_ms) - 1


def walk(points, start=0, every=300, frame=0):
    """Rows of a unit written at each of *points* *every* ms apart, each
    seen when written."""
    return [(start + k * every, x, y, frame, start + k * every) for k, (x, y) in enumerate(points)]


def segments_of(path):
    """A QPainterPath's line segments as ((x0, y0), (x1, y1)), rounded."""
    out = []
    here = None
    for k in range(path.elementCount()):
        e = path.elementAt(k)
        point = (round(e.x, 9), round(e.y, 9))
        if e.isMoveTo():
            here = point
        else:
            out.append((here, point))
            here = point
    return out


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestPlaces(unittest.TestCase):

    def test_the_gap_steps_are_the_canvass_stale_and_lost(self):
        from gui.positions_canvas import LOST_MS, STALE_MS
        self.assertEqual((tr.GAP_DASHED_MS, tr.GAP_DOTTED_MS), (STALE_MS, LOST_MS))

    def test_a_place_written_again_is_one_point_seen_till_its_last_line(self):
        """The log writes a unit standing still again and again: one point,
        and the gap to the next place counts from the last line, so a move
        4.5 s after arriving but 0.5 s after the last line is solid."""
        track = FakeTrack([(0, 0.5, 0.5, 0, 0), (2000, 0.5, 0.5, 0, 2000),
                           (4000, 0.5, 0.5, 0, 4000), (4500, 0.51, 0.5, 0, 4500)])
        t, x, _y, style, _f = tr.places_of(track, 1.0)
        self.assertEqual(t, [0, 4500])
        self.assertEqual(x, [0.5, 0.51])
        self.assertEqual(style, [tr.BREAK, tr.SOLID])

    def test_gaps_dash_then_dot_and_never_break(self):
        track = FakeTrack([(0, 0.50, 0.5, 0, 0), (900, 0.51, 0.5, 0, 900),        # 0.9 s: solid
                           (2400, 0.52, 0.5, 0, 2400),                              # 1.5 s: dashed
                           (8400, 0.53, 0.5, 0, 8400),                              # 6 s: dotted
                           (8401, 0.54, 0.5, 0, 8401)])
        _t, _x, _y, style, _f = tr.places_of(track, 1.0)
        self.assertEqual(style, [tr.BREAK, tr.SOLID, tr.DASHED, tr.DOTTED, tr.SOLID])
        track = FakeTrack([(0, 0.50, 0.5, 0, 0), (1000, 0.51, 0.5, 0, 1000),       # exactly 1 s: solid
                           (6000, 0.52, 0.5, 0, 6000)])                            # exactly 5 s: dashed
        self.assertEqual(tr.places_of(track, 1.0)[3], [tr.BREAK, tr.SOLID, tr.DASHED])

    def test_a_jump_is_dotted_however_quick(self):
        track = FakeTrack([(0, 0.50, 0.5, 0, 0), (100, 0.501, 0.5, 0, 100),
                           (200, 0.70, 0.5, 0, 200), (300, 0.701, 0.5, 0, 300)])
        style = tr.places_of(track, 0.05)[3]
        self.assertEqual(style, [tr.BREAK, tr.SOLID, tr.DOTTED, tr.SOLID])
        # At the threshold itself it is a step, not a jump
        track = FakeTrack([(0, 0.5, 0.5, 0, 0), (100, 0.55, 0.5, 0, 100)])
        self.assertEqual(tr.places_of(track, 0.05 + 1e-12)[3], [tr.BREAK, tr.SOLID])

    def test_a_new_frame_and_a_place_off_the_map_break_it(self):
        track = FakeTrack([(0, 0.5, 0.5, 0, 0), (100, 0.51, 0.5, 0, 100),
                           (200, 0.2, 0.2, 1, 200),              # another map: a break
                           (300, -270.0, 15.5, 1, 300),          # far off the map: dropped
                           (400, 0.21, 0.2, 1, 400)])            # back: a break
        t, _x, _y, style, frame = tr.places_of(track, 1.0)
        self.assertEqual(t, [0, 100, 200, 400])
        self.assertEqual(style, [tr.BREAK, tr.SOLID, tr.BREAK, tr.BREAK])
        self.assertEqual(frame, [0, 0, 1, 1])


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestSmoothing(unittest.TestCase):

    def test_a_staircase_is_drawn_through_its_midpoints(self):
        """The log's one-axis steps: the line passes through each pair's
        midpoint, the run's first and last places kept, each midpoint at
        the later place's time."""
        stairs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (2.0, 1.0), (2.0, 2.0)]
        track = FakeTrack(walk(stairs))
        t, x, y, style, _f = tr.smoothed(*tr.places_of(track, 99.0))
        self.assertEqual(list(zip(x, y)), [(0.0, 0.0), (0.5, 0.0), (1.0, 0.5), (1.5, 1.0),
                                           (2.0, 1.5), (2.0, 2.0)])
        self.assertEqual(t, [0, 300, 600, 900, 1200, 1200])
        self.assertEqual(style, [tr.BREAK] + [tr.SOLID] * 5)
        # Never more than half a step from a logged place
        for px, py in zip(x, y):
            self.assertLessEqual(min(math.hypot(px - a, py - b) for a, b in stairs), 0.5 + 1e-12)

    def test_a_gap_or_a_jump_runs_straight_between_logged_places(self):
        rows = walk([(0.0, 0.0), (1.0, 0.0)]) + [(5000, 1.0, 1.0, 0, 5000), (5300, 2.0, 1.0, 0, 5300)]
        _t, x, y, style, _f = tr.smoothed(*tr.places_of(FakeTrack(rows), 99.0))
        self.assertEqual(list(zip(x, y, style)),
                         [(0.0, 0.0, tr.BREAK), (0.5, 0.0, tr.SOLID), (1.0, 0.0, tr.SOLID),
                          (1.0, 1.0, tr.DASHED), (1.5, 1.0, tr.SOLID), (2.0, 1.0, tr.SOLID)])

    def test_a_lone_point_stays_as_it_is(self):
        t, x, y, style, _f = tr.smoothed([5], [0.1], [0.2], [tr.BREAK], [0])
        self.assertEqual((t, x, y, style), ([5], [0.1], [0.2], [tr.BREAK]))


def random_trail(seed, n=400):
    """A trail of a random walk with gaps, jumps and frame changes."""
    rng = random.Random(seed)
    rows, t, x, y, frame = [], 0, 0.5, 0.5, 0
    for _ in range(n):
        t += rng.choice((100, 200, 300, 300, 300, 1500, 6000))
        roll = rng.random()
        if roll < 0.02:
            frame += 1
        elif roll < 0.05:
            x, y = rng.random(), rng.random()   # a jump
        else:
            x += rng.choice((-0.0005, 0, 0.0005))
            y += rng.choice((-0.0005, 0, 0.0005))
        rows.append((t, x, y, frame, t + rng.choice((0, 0, 50, 400))))
    track = FakeTrack(rows)
    return tr.Trail(*tr.smoothed(*tr.places_of(track, 0.01)))


def reference(trail, t0, t, frame):
    """The segments drawn from *t0* to *t* in *frame*, one at a time, the
    one *t0* falls in cut at its share: (style, a, b)."""
    out = []
    for j in range(1, len(trail)):
        if trail.style[j] == tr.BREAK or trail.frame[j] != frame:
            continue
        tj = trail.t[j]
        if tj <= t0 or tj > t:
            continue
        a = (trail.x[j - 1], trail.y[j - 1])
        if trail.t[j - 1] < t0 < tj:
            share = (t0 - trail.t[j - 1]) / (tj - trail.t[j - 1])
            a = (a[0] + (trail.x[j] - a[0]) * share, a[1] + (trail.y[j] - a[1]) * share)
        a, b = (round(a[0], 9), round(a[1], 9)), (round(trail.x[j], 9), round(trail.y[j], 9))
        # A unit stepping back and forth gives two equal midpoints in a
        # row; Qt adds no element for a line to where the path is
        if a != b:
            out.append((trail.style[j], a, b))
    return sorted(out)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestChunksAndStrokes(unittest.TestCase):

    def test_chunks_cover_every_segment_once(self):
        for seed in range(5):
            trail = random_trail(seed)
            covered = []
            for chunk in trail.chunks:
                self.assertLessEqual(chunk.first, chunk.last)
                self.assertTrue(chunk.last - chunk.first == 1
                                or trail.t[chunk.last] - trail.t[chunk.first] <= tr.CHUNK_MS)
                for j in range(chunk.first + 1, chunk.last + 1):
                    self.assertNotEqual(trail.style[j], tr.BREAK)
                    self.assertEqual(trail.frame[j], chunk.frame)
                    covered.append(j)
            expected = [j for j in range(1, len(trail)) if trail.style[j] != tr.BREAK]
            self.assertEqual(covered, expected)

    def test_a_stroke_draws_exactly_the_segments_of_its_span(self):
        """Whole chunks from the cache and the ends from their points draw
        the same segments as a plain loop over them, at any span."""
        rng = random.Random(7)
        for seed in range(6):
            trail = random_trail(seed)
            end = trail.t[-1]
            for _ in range(25):
                t = rng.randint(0, end + 1000)
                t0 = t - rng.choice((10_000, 30_000, 10 ** 9))
                for frame in set(trail.frame):
                    stroke = tr.stroke(trail, t0, t, 10_000, frame)
                    drawn = sorted((style, a, b) for (style, _band), path in stroke.paths.items()
                                   for a, b in segments_of(path))
                    self.assertEqual(drawn, reference(trail, t0, t, frame), (seed, t0, t, frame))

    def test_a_span_starting_on_a_point_leaves_out_the_segment_ending_there(self):
        trail = random_trail(3)
        for j in range(5, len(trail), 37):
            t0 = trail.t[j]
            t = t0 + 10_000
            for frame in set(trail.frame):
                stroke = tr.stroke(trail, t0, t, 10_000, frame)
                drawn = sorted((style, a, b) for (style, _band), path in stroke.paths.items()
                               for a, b in segments_of(path))
                self.assertEqual(drawn, reference(trail, t0, t, frame))

    def test_the_head_runs_to_the_mark_and_a_glide_over_a_jump_is_dotted(self):
        rows = walk([(0.0, 0.0), (0.001, 0.0), (0.5, 0.5)], every=300)
        trail = tr.Trail(*tr.smoothed(*tr.places_of(FakeTrack(rows), 0.01)))
        # Paused at 400 ms the mark is at its logged place: the line ends there
        stroke = tr.stroke(trail, -10_000, 400, 10_000, 0, head=(0.001, 0.0))
        last = max((b for path in stroke.paths.values() for _a, b in segments_of(path)),
                   key=lambda p: p[0])
        self.assertEqual(last, (0.001, 0.0))
        # Playing, glided halfway across the jump: the head is dotted
        stroke = tr.stroke(trail, -10_000, 450, 10_000, 0, head=(0.25, 0.25))
        self.assertIn((tr.DOTTED, tr.TAPER_BANDS - 1), stroke.paths)

    def test_no_stub_where_the_unit_stood_through_the_span(self):
        """The review's finding 1: a run, then 15 s standing (written every
        300 ms): 10 s later nothing is drawn, though the last drawn point
        is the run's last midpoint, half a step short of where it stands."""
        rows = walk([(0.5 + 0.004 * k, 0.5) for k in range(10)], every=300)
        stand = rows[-1]
        rows += [(stand[0] + 300 * k, stand[1], stand[2], 0, stand[0] + 300 * k) for k in range(1, 51)]
        # Then on, so the standing place is inside the run and the last
        # point drawn before the moment is a midpoint half a step short
        rows.append((stand[0] + 15_300, stand[1] + 0.004, stand[2], 0, stand[0] + 15_300))
        track = FakeTrack(rows)
        trail = tr.Trail(*tr.smoothed(*tr.places_of(track, 1.0)))
        t = stand[0] + 15_000
        stroke = tr.stroke(trail, t - 10_000, t, 10_000, 0, head=(stand[1], stand[2]))
        self.assertEqual(stroke.paths, {})
        # Within the span the run is drawn, to the mark
        stroke = tr.stroke(trail, t - 20_000, t, 20_000, 0, head=(stand[1], stand[2]))
        self.assertTrue(stroke.paths)

    def test_chunks_outside_the_view_are_left_out(self):
        from PySide6.QtCore import QRectF
        rows = walk([(0.1 + 0.001 * k, 0.1) for k in range(200)], every=300)
        trail = tr.Trail(*tr.smoothed(*tr.places_of(FakeTrack(rows), 1.0)))
        whole = tr.stroke(trail, -1, 10 ** 9, 10_000, 0)
        part = tr.stroke(trail, -1, 10 ** 9, 10_000, 0, view=QRectF(0.1, 0.0, 0.05, 0.2))
        count = sum(len(segments_of(p)) for p in whole.paths.values())
        kept = sum(len(segments_of(p)) for p in part.paths.values())
        self.assertGreater(kept, 0)
        self.assertLess(kept, count / 2)

    def test_the_taper_narrows_to_the_oldest(self):
        self.assertEqual(tr.band_of(0, 10_000), tr.TAPER_BANDS - 1)
        self.assertEqual(tr.band_of(9_999, 10_000), 0)
        self.assertEqual(tr.band_of(60_000, 10_000), 0)
        self.assertEqual([tr.band_of(age, 10_000) for age in (0, 2_500, 5_000, 7_500)], [3, 2, 1, 0])
        self.assertEqual(tr.width_of(tr.TAPER_BANDS - 1, 2.5, 1.0), 2.5)
        self.assertEqual(tr.width_of(0, 2.5, 1.0), 1.0)
        self.assertEqual(tr.span_of(10_000, 50_000, 20_000), (40_000, 10_000))
        self.assertEqual(tr.span_of(tr.TRAIL_WHOLE, 50_000, 20_000), (20_000, tr.TAPER_WHOLE_MS))
        # In the lead-in, the whole fight so far starts at the moment
        self.assertEqual(tr.span_of(tr.TRAIL_WHOLE, 15_000, 20_000)[0], 15_000)


def states_of(tracks, start, end, frames=1):
    return SimpleNamespace(tracks=tracks, start_ms=start, end_ms=end, frames=[None] * frames)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestJumpStep(unittest.TestCase):

    def test_eight_times_the_players_99th_percentile_step(self):
        rows = walk([(0.5 + 0.001 * k, 0.5) for k in range(300)], every=200)
        boss = FakeTrack(walk([(0.1 * k, 0.5) for k in range(300)], every=200), kind="boss", key="70")
        step = tr.jump_step_of(states_of([FakeTrack(rows), boss], 0, 10 ** 9))
        self.assertAlmostEqual(step, tr.JUMP_FACTOR * 0.001, places=9)  # the boss's steps not counted

    def test_never_under_eight_log_steps(self):
        still = FakeTrack(walk([(0.5, 0.5)] * 50))
        self.assertAlmostEqual(tr.jump_step_of(states_of([still], 0, 10 ** 9)),
                               tr.JUMP_FACTOR * tr.STEP_FLOOR)
        # Steps under the log's own (a shuffle) do not lower it
        shuffle = FakeTrack(walk([(0.5 + 0.0001 * (k % 2), 0.5) for k in range(50)]))
        self.assertAlmostEqual(tr.jump_step_of(states_of([shuffle], 0, 10 ** 9)),
                               tr.JUMP_FACTOR * tr.STEP_FLOOR)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestFollowView(unittest.TestCase):

    def _follow(self, tracks, start=0, end=120_000):
        from gui.positions_canvas import FIT_KINDS, box_of, fit_boxes
        states = states_of(tracks, start, end)
        return tr.FollowView(states, fit_boxes(states), box_of, FIT_KINDS)

    def test_a_group_that_crosses_its_room_is_followed(self):
        """Four players walking together from x 0.1 to 0.9 over two
        minutes: the moment's box is far tighter than the fight's."""
        tracks = [FakeTrack(walk([(0.1 + 0.8 * k / 120 + 0.002 * p, 0.5 + 0.002 * p) for k in range(121)],
                                 every=1000), key=str(p)) for p in range(4)]
        follow = self._follow(tracks)
        self.assertTrue(follow.follows(0))
        self.assertGreater(follow.gains[0], tr.FOLLOW_GAIN)
        early, late = follow.box_at(0, 10_000), follow.box_at(0, 110_000)
        self.assertLess(early[1], late[0])           # the box has moved on with the group
        middle = follow.box_at(0, 60_500)            # between two seconds' boxes
        a, b = follow.box_at(0, 60_000), follow.box_at(0, 61_000)
        for k in range(4):
            self.assertAlmostEqual(middle[k], (a[k] + b[k]) / 2)

    def test_a_group_that_stands_is_not(self):
        tracks = [FakeTrack(walk([(0.5 + 0.01 * (k % 3), 0.5 + 0.002 * p) for k in range(121)],
                                 every=1000), key=str(p)) for p in range(4)]
        follow = self._follow(tracks)
        self.assertFalse(follow.follows(0))
        self.assertIsNone(follow.box_at(0, 60_000))

    def test_the_dead_and_the_long_unseen_are_not_followed(self):
        """A dead player lying far off, written every second, and one last
        seen long ago, each apart, do not hold the box open."""
        group = [FakeTrack(walk([(0.1 + 0.8 * k / 120, 0.5 + 0.002 * p) for k in range(121)],
                                every=1000), key=str(p)) for p in range(3)]
        dead = FakeTrack([(k * 1000, 0.95, 0.95, 0, k * 1000, 0, 100) for k in range(121)], key="9")
        unseen = FakeTrack([(0, 0.95, 0.95, 0, 0)], key="8")
        for other in (dead, unseen):
            box = self._follow(group + [other]).box_at(0, 60_000)
            self.assertLess(box[3], 0.9, other.unit.key)

    def test_the_fit_starts_at_the_pull_not_the_run_in(self):
        """A player running in during the lead-in from (0.1, 0.1): the box
        of the fight is fitted from where they stood at the pull."""
        from gui.positions_canvas import fit_boxes
        run_in = [(k * 1000, 0.1 + 0.04 * k, 0.1 + 0.04 * k, 0, k * 1000) for k in range(10)]
        fight = [(10_000 + k * 1000, 0.5 + 0.001 * (k % 3), 0.5, 0, 10_000 + k * 1000) for k in range(60)]
        mates = [FakeTrack(walk([(0.5 + 0.002 * p, 0.51)] * 70, every=1000), key=str(p)) for p in range(2, 5)]
        box = fit_boxes(states_of([FakeTrack(run_in + fight)] + mates, 10_000, 70_000))[0]
        self.assertGreater(box[0], 0.3)
        self.assertGreater(box[2], 0.3)

    def test_the_box_eases_between_its_seconds(self):
        times = [0, 1000, 2000, 3000, 20_000]
        boxes = [(0, 1, 0, 1), (1, 2, 1, 2), (2, 3, 2, 3), (3, 4, 3, 4), (9, 10, 9, 10)]
        eased = tr._eased(times, boxes)
        self.assertEqual(eased[0], (1.5, 2.5, 1.5, 2.5))          # 0 to 3 s averaged
        self.assertEqual(eased[3], (1.5, 2.5, 1.5, 2.5))          # 3 s: back to 0 s too
        self.assertEqual(eased[-1], (9.0, 10.0, 9.0, 10.0))       # alone within 5 s


if __name__ == "__main__":
    unittest.main()
