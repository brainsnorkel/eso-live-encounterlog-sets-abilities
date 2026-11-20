"""
Trails and the following view of the positions canvas (issues #246 and
#241): a line through the places a unit has been, and, in a fight that
moves across its map, a view that follows the group. No widget here: the
canvas (positions_canvas) draws what this module works out, and the window
(positions_window) holds one TrailSet and one FollowView per fight read.

Design: whose trail, and how it looks. Decided for #246 from prototype
pictures drawn on the real window over a veteran Lucent Citadel split, a
UX review of them that had not seen the prototype's intent, and measures.
One unit's trail at a time, the selected one's, reads clearly in every
picture: twelve tangle on a short fight and make a hairball over a whole
one. So the trail is the selected unit's by default, last 10 s, on when
the window opens (a Deaths link selects the player who died, and the line
answers where they came from); Every player adds a thinner one for each
numbered player. Over 121 boss fights of nine trials a 10 s trail left the
marker's footprint (radius, ring and selection gap at the fitted scale) in
about 85% of player-seconds, 60 to 99% by fight, and a 30 s one in about
95%; 5 s drew next to nothing at four of five moments tried, so the
lengths are 10 s, 30 s and the whole fight so far.

Age is a taper, never a fade. Text ink reaches the canvas's 3:1 floor for
graphics only at 48% opacity on the light theme (39% on the dark), so a
trail fading from 55% to 5% left its oldest 86% under the floor, the "where
from" end among it, and trails crossing each other added up to black
bundles whatever their age. A trail is drawn opaque, in text ink for the
selected unit (16.1:1 light, 11.4:1 dark) and in the muted ink for Every
player's (6.05:1 and 5.22:1), widest at the mark and narrowing to its
oldest end in TAPER_BANDS steps of its length (the whole fight so far
tapers over its last TAPER_WHOLE_MS, older parts at the thinnest width).
Colour never says whose it is: the role hexes are the health, shield and
damage hexes (positions_canvas).

The log's stairs. The places are fractions of the map with four decimals,
but over six boss fights 61 to 70% of the logged moves changed one axis
only, in steps of 0.0005 of the map, for the logging player as much as
for anyone: drawn raw, a diagonal walk is a staircase (about 6.5 px a step
at Cavot Agnan's fit). A run of plain moves is drawn through the midpoints
of its consecutive places, its first and last places kept: the line strays
at most half a step from where the log put the unit, and the stairs become
the walk.

Gaps and jumps, never a break. A segment is solid when the unit's next
place came within GAP_DASHED_MS of the last line that wrote the one before
(the reader's seen: a unit standing still is written again and again);
dashed after that, dotted after GAP_DOTTED_MS, the canvas's own stale and
lost steps (STALE_MS, LOST_MS), so a trail and a mark say a gap the same
way, and both are straight lines, not the way they went. Over the 121
fights dashed stretches were under 2% of a trail's length in most, 16 to
24% in some Dreadsail Reef and Halls of Fabrication pulls, dotted up to
32% (a Spiral Descender pull). A jump is dotted too: a portal, a teleport
or a pull moved players 9 to 580 times the fight's 99th-percentile step
within a second (Lucent Citadel's portals, Shaper of Flesh, Kazpian,
Chimera, Z'Maja, Falgravn, Nahviintaas), while ordinary movement never
passed 7.4 times it, so a step over JUMP_FACTOR times the 99th percentile
of the players' steps in the fight is drawn dotted, straight from where
they were to where they appeared. A trail breaks only where the log gives
no line to draw: a new map frame (places of two maps are never joined) and
a place off the map (fight_reread.on_map). A dead unit lies still, so its
trail shrinks to its corpse as the moment moves on and grows again after a
revive; nothing is frozen. Playback's glide (positions_canvas.glide_state)
is left as #232 made it.

Drawing it fast enough to play. Drawn as one line per logged step, every
player's whole-fight trail took 490 to 870 ms to paint on Xoryn (712 s,
82,771 states), against playback's FRAME_MS of 33. So each unit's points
are worked out once per fight read (Trail, built on first use and kept),
cut into chunks of at most CHUNK_MS of one map frame, each with its paths
by style in map coordinates and its bounds; a paint takes the chunks that
overlap the trail's span and the view, adds each whole chunk's paths to
the path of its taper band, builds only the two part chunks at the ends
from their points, and strokes each band once with a cosmetic pen through
the view's transform. Measured as built, every frame of a fight at 5x
through the window's own draw and the canvas's paint, offscreen (the
frame's median, then its 99th percentile): on Xoryn (712 s, the view
following) at 100% text 6.1 ms (9.5) with no trail, 6.9 (10.1) with the
default, 9.9 (14.7) for every player's 30 s and 10.7 (16.3) for every
player's whole fight; at 200% text and device pixel ratio 2, 6.8 (11.4),
7.6 (12.5), 11.6 (24.1) and 15.7 (48.1); on Lord Falgravn (284 s, Kyne's
Aegis) there 5.2 (8.2), 5.6 (9.5), 10.1 (23.2) and 16.0 (37.7). So the
default costs under a millisecond, and only every player's whole fight at
200% on a ratio-2 screen passes playback's FRAME_MS of 33 in its slowest
frames, where a frame late only skips (positions_window). A FollowView is
built in 12 to 32 ms when a fight's states come.

The view that follows (#241). Over the same 121 fights the box fitted to
the whole fight is already tight in most: a box fitted round the moment
(the living players' and bosses' places in the FOLLOW_WINDOW_MS either
side) would zoom 1.0 to 1.3 times at the median. A few fights cross their
room and are drawn in a corner: Xoryn 9.3 times (5 to 26), Overfiend
Kazpian 3.7, Archcustodian 3.5, Shaper of Flesh 2.2 to 2.5, Kagouti
Fabricant 1.9 to 2.2, Yolnahkriin 1.7. Decided: in a map frame where the
moment's box is at least FOLLOW_GAIN times tighter at the median, the view
follows the group, its box eased over EASE_MS either side so it glides
rather than jumps; elsewhere the box holds still as before. Moving the
view is not motion of its own: it moves only as the moment does, which
only the reader moves (the guide's Motion note holds), and the faint grid
moves with it, so a pan is seen as one. A box round the moment is fitted
as the whole fight's is (positions_canvas.box_of) to the places sampled
once a second, so a lone unit far off is pinned to the edge, not followed.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from typing import NamedTuple

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

from fight_reread import on_map

# The trail's lengths (ms), as Show offers them
TRAIL_OFF = 0
TRAIL_WHOLE = -1           # the whole fight so far
TRAIL_LENGTHS = (TRAIL_OFF, 10_000, 30_000, TRAIL_WHOLE)
TRAIL_DEFAULT = 10_000
# Whose trails
WHOSE_SELECTED, WHOSE_EVERY = "selected", "every"

# A segment's look; BREAK: no segment into this point (a run starts there)
BREAK, SOLID, DASHED, DOTTED = -1, 0, 1, 2
# The canvas's STALE_MS and LOST_MS (test_positions_trails pins them equal)
GAP_DASHED_MS = 1_000
GAP_DOTTED_MS = 5_000
# A step this many times the fight's 99th-percentile step is a jump
JUMP_FACTOR = 8.0
# The log's own step (measured: 0.0005 of the map), the floor of the 99th
# percentile, so a fight where no one moved does not call every step a jump
STEP_FLOOR = 0.0005

TAPER_BANDS = 4            # the taper's widths, newest widest
TAPER_WHOLE_MS = 30_000    # the whole fight so far tapers over this, older parts thinnest
CHUNK_MS = 5_000           # a cached chunk's span at most

# The view that follows (see the module)
FOLLOW_WINDOW_MS = 10_000  # a moment's box: the places this long either side
FOLLOW_GAIN = 1.5          # follow where the moment's box is this much tighter at the median
EASE_MS = 5_000            # the boxes eased over this long either side
FOLLOW_LEAST = 3           # places a moment's box needs, else the whole fight's


# ------------------------------------------------------------------ trails --

class Chunk(NamedTuple):
    """Points *first* to *last* of a Trail (indices), all in one map
    frame, *t0* to *t1* their times; *paths*: style -> QPainterPath of
    the segments into points first+1 to last, in map coordinates;
    *bounds*: a QRectF round them."""
    first: int
    last: int
    t0: int
    t1: int
    frame: int
    paths: dict
    bounds: QRectF


class Trail:
    """One track's trail, worked out once: the drawn points (times, places,
    the style of the segment into each, map frames) after the midpoint
    smoothing, and their chunks (see the module)."""

    __slots__ = ("_chunk_t1", "chunks", "frame", "style", "t", "x", "y")

    def __init__(self, t, x, y, style, frame):
        self.t, self.x, self.y, self.style, self.frame = t, x, y, style, frame
        self.chunks = _chunks(self)
        self._chunk_t1 = [chunk.t1 for chunk in self.chunks]

    def __len__(self) -> int:
        return len(self.t)

    def chunks_over(self, t0: int, t1: int) -> list:
        """The chunks with a point in (t0, t1]."""
        i = bisect_left(self._chunk_t1, t0 + 1)
        out = []
        while i < len(self.chunks) and self.chunks[i].t0 <= t1:
            out.append(self.chunks[i])
            i += 1
        return out


def places_of(track, jump_step: float):
    """The track's logged places as (t, x, y, style, frame) lists: one
    point per change of place, each with the style of the segment into it
    (BREAK at a run's start), by the rules of the module."""
    ts, xs, ys, frames, seen = track.t, track.x, track.y, track.frame, track.seen
    out_t, out_x, out_y, out_s, out_f = [], [], [], [], []
    last = None  # (x, y, frame, seen)
    for i in range(len(ts)):
        x, y, frame = xs[i], ys[i], frames[i]
        if not on_map(x, y):
            last = None
            continue
        if last is not None and frame == last[2] and x == last[0] and y == last[1]:
            last = (x, y, frame, seen[i])  # still there, known till this line
            continue
        if last is None or frame != last[2]:
            style = BREAK
        else:
            gap = ts[i] - last[3]
            if math.hypot(x - last[0], y - last[1]) > jump_step or gap > GAP_DOTTED_MS:
                style = DOTTED
            elif gap > GAP_DASHED_MS:
                style = DASHED
            else:
                style = SOLID
        out_t.append(ts[i])
        out_x.append(x)
        out_y.append(y)
        out_s.append(style)
        out_f.append(frame)
        last = (x, y, frame, seen[i])
    return out_t, out_x, out_y, out_s, out_f


def smoothed(t, x, y, style, frame):
    """The points as drawn (see the module): a solid run P_a .. P_b drawn
    through P_a, the midpoints of its consecutive places and P_b; a dashed
    or dotted segment straight between its two places. A midpoint takes the
    later place's time, when the unit moved there."""
    out_t, out_x, out_y, out_s, out_f = [], [], [], [], []
    n = len(t)
    k = 0
    while k < n:
        out_t.append(t[k])
        out_x.append(x[k])
        out_y.append(y[k])
        out_s.append(style[k])
        out_f.append(frame[k])
        b = k
        while b + 1 < n and style[b + 1] == SOLID:
            b += 1
        for m in range(k, b):
            out_t.append(t[m + 1])
            out_x.append((x[m] + x[m + 1]) / 2)
            out_y.append((y[m] + y[m + 1]) / 2)
            out_s.append(SOLID)
            out_f.append(frame[m])
        if b > k:
            out_t.append(t[b])
            out_x.append(x[b])
            out_y.append(y[b])
            out_s.append(SOLID)
            out_f.append(frame[b])
        k = b + 1
    return out_t, out_x, out_y, out_s, out_f


def _chunks(trail) -> list:
    """The trail's segments cut into chunks: consecutive segments with no
    break between them (so of one map frame), spanning at most CHUNK_MS
    (a longer single segment is a chunk of its own), each with its paths
    by style and its bounds. A chunk starts at the last point of the one
    before when no break comes between."""
    out = []
    n = len(trail.t)
    tt, xs, ys, styles = trail.t, trail.x, trail.y, trail.style
    i = 0
    while i < n - 1:
        if styles[i + 1] == BREAK:
            i += 1
            continue
        first, t0 = i, tt[i]
        paths: dict = {}
        x_lo = x_hi = xs[i]
        y_lo = y_hi = ys[i]
        j = i + 1
        while j < n and styles[j] != BREAK and (j == i + 1 or tt[j] - t0 <= CHUNK_MS):
            path = paths.get(styles[j])
            if path is None:
                path = paths[styles[j]] = QPainterPath()
            here = path.currentPosition()
            if path.elementCount() == 0 or here.x() != xs[j - 1] or here.y() != ys[j - 1]:
                path.moveTo(xs[j - 1], ys[j - 1])
            path.lineTo(xs[j], ys[j])
            x_lo, x_hi = min(x_lo, xs[j]), max(x_hi, xs[j])
            y_lo, y_hi = min(y_lo, ys[j]), max(y_hi, ys[j])
            j += 1
        last = j - 1
        out.append(Chunk(first, last, t0, tt[last], trail.frame[first], paths,
                         QRectF(x_lo, y_lo, x_hi - x_lo, y_hi - y_lo)))
        i = last
    return out


def jump_step_of(states) -> float:
    """The step over which a move is a jump: JUMP_FACTOR times the 99th
    percentile of the players' moves within the fight that came within
    GAP_DASHED_MS of their last line, never under JUMP_FACTOR times
    STEP_FLOOR."""
    from fight_locator import GROUP, PLAYER, SELF
    steps = []
    start, end = states.start_ms, states.end_ms
    for track in states.tracks:
        unit = track.unit
        if unit is None or unit.kind not in (SELF, GROUP, PLAYER):
            continue
        ts, xs, ys, frames, seen = track.t, track.x, track.y, track.frame, track.seen
        for i in range(max(1, bisect_left(ts, start)), bisect_right(ts, end)):
            if frames[i] != frames[i - 1] or ts[i] - seen[i - 1] > GAP_DASHED_MS:
                continue
            if not (on_map(xs[i], ys[i]) and on_map(xs[i - 1], ys[i - 1])):
                continue
            step = math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1])
            if step > 0:
                steps.append(step)
    steps.sort()
    p99 = steps[int(0.99 * (len(steps) - 1))] if steps else STEP_FLOOR
    return JUMP_FACTOR * max(p99, STEP_FLOOR)


class TrailSet:
    """The trails of one fight read (FightStates), each built on first use
    and kept while the window holds the states."""

    def __init__(self, states):
        self.states = states
        self._jump = None
        self._trails: dict = {}

    @property
    def jump_step(self) -> float:
        if self._jump is None:
            self._jump = jump_step_of(self.states)
        return self._jump

    def trail(self, track) -> Trail:
        key = id(track)
        trail = self._trails.get(key)
        if trail is None:
            trail = self._trails[key] = Trail(*smoothed(*places_of(track, self.jump_step)))
        return trail


class Stroke(NamedTuple):
    """What to stroke for one trail at a moment: *paths*, (style, band)
    -> QPainterPath in map coordinates; band 0 is the oldest, thinnest."""
    paths: dict


def span_of(length: int, t: int, fight_start: int) -> tuple[int, int]:
    """(from, taper span) of a trail of *length* (TRAIL_LENGTHS) at the
    moment *t*: the whole fight so far starts at the fight's start (or the
    moment, in the lead-in) and tapers over TAPER_WHOLE_MS."""
    if length == TRAIL_WHOLE:
        return min(fight_start, t), TAPER_WHOLE_MS
    return t - length, length


def band_of(age: int, taper: int) -> int:
    """The taper band of a point *age* ms old: TAPER_BANDS - 1 newest,
    0 at the taper's end and beyond."""
    if taper <= 0:
        return TAPER_BANDS - 1
    share = age / taper
    return max(0, TAPER_BANDS - 1 - min(TAPER_BANDS - 1, int(share * TAPER_BANDS)))


def stroke(trail: Trail, t0: int, t: int, taper: int, frame: int, head=None,
           view: QRectF | None = None) -> Stroke:
    """The paths of *trail* from *t0* to the moment *t*, in *frame* only,
    ending at *head* (x, y), the mark's place, when given: whole chunks
    from the cache, the ends built from their points, chunks outside
    *view* (map coordinates) skipped. A segment counts from the time of
    its first point to that of its last; the one *t0* falls in starts at
    its share of the way, when it ends by *t*."""
    paths: dict = {}
    tt, xs, ys, styles = trail.t, trail.x, trail.y, trail.style

    def segment(style, band, a, b):
        path = paths.get((style, band))
        if path is None:
            path = paths[(style, band)] = QPainterPath()
        here = path.currentPosition()
        if path.elementCount() == 0 or here.x() != a[0] or here.y() != a[1]:
            path.moveTo(a[0], a[1])
        path.lineTo(b[0], b[1])

    for chunk in trail.chunks_over(t0, t):
        if chunk.frame != frame:
            continue
        if (chunk.t0 >= t0 and chunk.t1 <= t
                and band_of(t - chunk.t0, taper) == band_of(t - chunk.t1, taper)):
            # Whole and within one taper band: from the cache (a chunk
            # across a band's edge is built from its points, as the ends are)
            bounds = chunk.bounds
            if view is not None and not view.intersects(bounds.adjusted(-1e-9, -1e-9, 1e-9, 1e-9)):
                continue
            band = band_of(t - chunk.t1, taper)
            for style, path in chunk.paths.items():
                into = paths.get((style, band))
                if into is None:
                    paths[(style, band)] = QPainterPath(path)
                else:
                    into.addPath(path)
            continue
        for j in range(chunk.first + 1, chunk.last + 1):
            tj = tt[j]
            if tj <= t0 or tj > t:
                continue
            a = (xs[j - 1], ys[j - 1])
            if tt[j - 1] < t0 < tj:
                share = (t0 - tt[j - 1]) / (tj - tt[j - 1])
                a = (xs[j - 1] + (xs[j] - xs[j - 1]) * share, ys[j - 1] + (ys[j] - ys[j - 1]) * share)
            segment(styles[j], band_of(t - tj, taper), a, (xs[j], ys[j]))
    if head is not None:
        j = bisect_right(tt, t) - 1
        # No head where the unit has not moved within the span: it stood
        # (or lay) there throughout, and a stub to its place would say not
        if j >= 0 and trail.frame[j] == frame and tt[j] > t0:
            end = (xs[j], ys[j])
            if abs(head[0] - end[0]) > 1e-12 or abs(head[1] - end[1]) > 1e-12:
                # Gliding (while playing) along a jump: the head is drawn as
                # the jump is
                nxt = j + 1
                style = (styles[nxt] if nxt < len(tt) and styles[nxt] == DOTTED else SOLID)
                segment(style, TAPER_BANDS - 1, end, head)
    return Stroke(paths)


def width_of(band: int, widest: float, thinnest: float) -> float:
    """A taper band's width, *thinnest* at band 0 to *widest* at the newest."""
    if TAPER_BANDS <= 1:
        return widest
    return thinnest + (widest - thinnest) * band / (TAPER_BANDS - 1)


# ------------------------------------------------------ the following view --

class FollowView:
    """The boxes of a fight's moments in the map frames where the view
    follows the group (see the module): per frame, one box a second over
    the fight, eased; box_at gives the box of any moment, None where the
    frame's box holds still."""

    def __init__(self, states, boxes: dict, box_of, kinds):
        self._times: dict = {}   # frame -> sorted seconds (ms)
        self._boxes: dict = {}   # frame -> eased boxes, one per time
        self.gains: dict = {}    # frame -> the median gain measured
        start, end = states.start_ms, states.end_ms
        if end <= start:
            return
        seconds = list(range(start, end + 1, 1000))
        # One sample a second of each living player's and boss's place
        samples: dict = {}  # frame -> {second index: [(x, y)]}
        for track in states.tracks:
            unit = track.unit
            if unit is None or unit.kind not in kinds:
                continue
            # The columns once: each of a track's attributes is a new view
            ts, xs, ys, frames = track.t, track.x, track.y, track.frame
            seen, health, health_max = track.seen, track.health, track.health_max
            for k, s in enumerate(seconds):
                index = bisect_right(ts, s) - 1
                if index < 0 or s - seen[index] > GAP_DOTTED_MS:
                    continue
                if 0 < health_max[index] and health[index] <= 0:
                    continue
                x, y = xs[index], ys[index]
                if not on_map(x, y):
                    continue
                samples.setdefault(frames[index], {}).setdefault(k, []).append((x, y))
        reach = FOLLOW_WINDOW_MS // 1000
        for frame, by_second in samples.items():
            whole = boxes.get(frame)
            if whole is None:
                continue
            side = max(whole[1] - whole[0], whole[3] - whole[2])
            times, raw = [], []
            for k in sorted(by_second):
                xs, ys = [], []
                for kk in range(k - reach, k + reach + 1):
                    for x, y in by_second.get(kk, ()):
                        xs.append(x)
                        ys.append(y)
                if len(xs) < FOLLOW_LEAST:
                    continue
                times.append(seconds[k])
                raw.append(box_of(xs, ys))
            if not raw:
                continue
            gains = sorted(side / max(b[1] - b[0], b[3] - b[2]) for b in raw)
            gain = gains[len(gains) // 2]
            self.gains[frame] = gain
            if gain < FOLLOW_GAIN:
                continue
            self._times[frame] = times
            self._boxes[frame] = _eased(times, raw)

    def follows(self, frame: int) -> bool:
        return frame in self._boxes

    def box_at(self, frame: int, t: int):
        """The box of the moment *t* in *frame*, between the eased boxes
        of the seconds either side; None where the view holds still."""
        times = self._times.get(frame)
        if not times:
            return None
        boxes = self._boxes[frame]
        j = bisect_right(times, t)
        if j == 0:
            return boxes[0]
        if j >= len(times):
            return boxes[-1]
        a, b = times[j - 1], times[j]
        share = (t - a) / (b - a) if b > a else 0.0
        return tuple(p + (q - p) * share for p, q in zip(boxes[j - 1], boxes[j]))


def _eased(times, boxes) -> list:
    """Each box's edges averaged over the boxes within EASE_MS of it."""
    out = []
    lo = 0
    hi = 0
    n = len(times)
    for i, t in enumerate(times):
        while times[lo] < t - EASE_MS:
            lo += 1
        while hi < n and times[hi] <= t + EASE_MS:
            hi += 1
        window = boxes[lo:hi]
        out.append(tuple(sum(box[e] for box in window) / len(window) for e in range(4)))
    return out
