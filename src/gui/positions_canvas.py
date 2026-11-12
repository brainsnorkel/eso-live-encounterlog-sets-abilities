"""
The positions canvas (issue #214): where everyone stood at one moment of a
fight, drawn on a plain 2D canvas, with the boss bars above it and the
scrub bar the moment is chosen on. The positions window (positions_window)
holds the fight and its re-read states (fight_reread) and hands these
widgets a Scene for each moment, held still or, while it plays (#232),
for each frame.

Design: A moment, drawn directly. Nothing moves by itself: the canvas is
repainted on a step, a selection, a resize, a theme or Hide names flip, a
new text size, or a frame of playback, which only the reader's Play
starts, and a full repaint is cheap. Measured offscreen for the study
(build/positions214/paint): 60 markers with rings, noses, bodies and
numbers in 2.2 to 3.4 ms at device pixel ratio 1 and 4.7 to 7.9 ms at
ratio 2; twelve players alone 1.3 to 2.0 ms. Over every second of six real
12-player boss fights (build/positions214/window/probe_piles_out.txt)
this canvas repainted in a median 1.9 to 4.2 ms, a step of the moment cost
0.5 to 1.6 ms and the whole window's repaint 5.7 to 11.3 ms. Played back
at 200% text and ratio 2, a frame of a 284 s Lord Falgravn kill painted
the canvas in a median 5.4 ms on a busy machine, as paused, and built its
glided scene in 0.66 ms (positions_window has the measures and the frame
rate). So there is no sprite or frame cache, no QGraphicsView and no timer
here; the canvas is opaque (it fills itself first), so a frame does not
paint the panes under it again.

Playback glides, a paused moment never does (glide_state, build_scene's
glide): while the window plays, a mark moves on a straight line between
two logged samples at most GLIDE_MS apart, from the last line that wrote
its place to the next state's first, in one map frame, both on their map;
only its place moves. Paused, every mark is where its last state put it.
The window's notes say why.

One box per map frame. The log's coordinates are fractions of the map the
last MAP_CHANGED line named, so places in two frames are never joined: each
frame gets its own box, fitted once to the 2nd to 98th percentile of the
players' and bosses' places in that frame over the whole range, padded by
12% of its longer side, with one scale for x and y and y down. The study
found the min-max box 1.2 to 2.6 times larger, empty for most of a fight.
The moment's frame is the frame of the selected unit's state, else the one
most drawn players are in. A unit whose last state is of another frame, or
far off its map (fight_reread.on_map), is not drawn: the line under the
canvas and the table say "not on this map". A drawn unit outside the
fitted box is pinned to the canvas's edge, with a small arrow towards where
it stands. There is no map art, scale or height (#148 stays parked).

Piles. A group stands close, and a marker's radius grows with the text
size (it must hold '12') while the canvas does not, so numbered players
whose markers overlap by over a quarter (closer than PILE_SHARE radii)
are drawn as one badge that lists them: each member's shape and number
with a short bar of its health, at their mean place, with a dashed line to
it when the badge had to move. The selected player is never piled. Over
six boss fights this gathered 2 to 61% of the players' seconds at 100%
text (Chimera's split the most) and 32 to 90% at 200%, where unpiled
numbers covered each other (the study's critique counted 18 to 82% piled
at 200% with a tighter rule). Badges and labels keep off the players,
bosses, notes and other badges where the canvas has room (_avoid), and
cover least where it has none; a boss's name is never hidden.

Meaning rides on shape, number, arc length and stroke, never on colour
alone, and every mark is in neutral ink. The role hexes are the very
hexes of health 'good', heal, health 'critical', damage and shield
(measured: light T #1565c0 is the recap's shield, D #c62828 its critical
health and damage), so a marker coloured by role would say 'DPS = critical
health'. A player with a row in the fight table is a role shape (circle
for damage, diamond for a healer, square for a tank) filled with the
pane's text ink, holding the row's number in the Base colour (16.1:1
light, 11.4:1 dark). The number font is the application font at 0.78,
bold, in a radius of scaled_px(8): '12' needs 5.9 to 6.5 px at 100% text
and 12.2 to 14.1 px at 200%, and the radius is 8 and 16 px there. Health
is the length of a ring arc clockwise from 12 o'clock, in the death
recap's four health steps, over a decorative 13% track: the steps' closest
pair under deuteranopia is CIEDE2000 2.2 (light), so the length carries the
value and the colour only repeats it. Shield is a thin outer arc in the
recap's shield colour, capped at a full turn of the maximum health. The
nose shows facing in text ink at 75% (7.1:1), the heading taken modulo 2π
with the facing vector (-sin h, -cos h), y down; it is facing, not travel
(the survey: players face their travel in under half their moving steps).

Gaps in the log are marked, never faded. With text ink at 45% a number
on the body reads 3.36:1 (light) and a 30% body 2.12:1, under the app's
4.5:1 and 3:1 floors, so: a unit whose last state is over STALE_MS old is
hollow with a dashed outline; over LOST_MS, hollow and dotted with its
number in muted ink (6.05:1 and 5.22:1); dead, it is hollow in muted ink
with a cross in the recap's damage red under its number, which stays in
full ink. Dead is health 0 (the rule the engine counts deaths by since
#221), and for a player also a death the fight counts, from its moment
until their health next rises (still_dead): the log can write a dead
player's health above 0. A regeneration tick written in the death's own
millisecond after the DIED line kept one player at 631 health for the 17 s
they lay dead, and a mechanic's DIED line carries the health before the
kill; over 1,585 deaths in 9 trial splits, 7 were not at 0 at their own
moment, the moment a death's Positions link opens at. Gaps over
0.5 s are 0.5 to 15.9% of a fight, by log (the study), hence the two
steps. A unit's age counts from the last line that wrote it (the
reader's seen), not from when its state began: the log writes a unit
standing still again and again unchanged (state_age has the measures),
and the table says 'last seen 6 s ago'. Adds keep their own
clock: an add's last line is not its death
(62% of an add's life lies in gaps over 1 s), so a hostile unit is drawn
while its last state is under FORGET_MS old, as a cross for DEAD_ADD_MS
after a state at health 0, then not at all.

The colours. Ink and muted are the fight pane's (fight_render._theme);
health, shield and damage the death recap's (death_render._THEMES), all
pinned by test_palette. New here, keyed {False: light, True: dark} and
measured on the windows11 Base (#ffffff, #2d2d2d): the hostile red of the
adds, 6.65:1 and 4.70:1, and the boss's, 10.30:1 and 6.03:1. The canvas
reads light or dark from its palette's background at paint, as the
timeline strip does, so a theme switch needs only a repaint.

The scrub bar is a QSlider so a screen reader meets a slider with a value
(whole seconds into the fight); Qt gives a QAbstractSlider subclass no
value text at all, and a value text of '1:50.0' would need an accessible
interface made in Python, which crashed at exit in the GUI survey, so the
moment in words is its description. It takes the focus with a mark of its
own: Qt's focus frame (PE_FrameFocusRect) draws a 6,000 px tint over a
100x60 rect in the Fusion style.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from typing import NamedTuple

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QSizePolicy, QSlider, QToolTip, QWidget

from fight_locator import BOSS, COMPANION, ENEMY, GROUP, OTHER, PET, PLAYER, SELF
from fight_reread import on_map
from gui.death_render import _THEMES as _RECAP_THEMES
from gui.fight_render import _theme as _pane_theme
from gui.name_mask import NO_MASK, mask_image, stand_in
from gui.text_size import scaled_px

# A player's kinds in the locator's unit table
PLAYER_KINDS = (SELF, GROUP, PLAYER)
# The kinds whose places the box of a frame is fitted to
FIT_KINDS = PLAYER_KINDS + (BOSS,)

# How a unit is drawn (UnitAt.mark)
MARK_PLAYER = "player"        # a row of the fight table: a numbered role shape
MARK_LOOSE = "loose"          # a player with no row (no build, not grouped): small hollow circle
MARK_BOSS = "boss"            # a hexagon with its health and its name
MARK_ADD = "add"              # a hostile unit: a small triangle pointing where it faces
MARK_PET = "pet"              # a player's pet: a small hollow dot
MARK_COMPANION = "companion"  # a small 'C'
MARK_OTHER = "other"          # a unit neither hostile nor a player's: a grey '+'
MARK_UNKNOWN = "unknown"      # a unit the log never announced: a grey '+'
# The marks the Show menu turns on and off, and which start on
SHOWN_BY_DEFAULT = {MARK_ADD: True, MARK_PET: False, MARK_COMPANION: False,
                    MARK_UNKNOWN: False, MARK_OTHER: False}

# Where a unit is at the moment (UnitAt.where)
DRAWN = "drawn"
OTHER_MAP = "other map"   # its last state is of another map frame
OFF_MAP = "off map"       # far off its map: another zone or instance
NOT_YET = "not yet"       # no state at or before the moment
GONE = "gone"             # an add (pet, ...) whose last state is too old to draw
LEFT = "left"             # past its window: left the zone, removed, or its id handed on
HIDDEN = "hidden"         # a kind the Show menu leaves out
# How it looks (UnitAt.look)
ALIVE, DEAD, STALE, LOST = "alive", "dead", "stale", "lost"

STALE_MS = 1_000       # no state for longer: dashed (the study's 1 s)
LOST_MS = 5_000        # longer still: dotted, the number muted (the study's 5 s)
FORGET_MS = 15_000     # an add, a pet or an unannounced unit is drawn this long after its last state
DEAD_ADD_MS = 2_000    # an add at health 0 is a cross this long, then gone
# The deaths noted on the canvas: this long before the moment to this long after
NOTES_BEFORE_MS = 4_000
NOTES_AFTER_MS = 3_000
NOTES_MAX = 5          # lines of notes at most; more are counted
# While the window plays the fight back (#232), a mark glides between two
# logged places at most this far apart (glide_state)
GLIDE_MS = 1_000
# The fit: these percentiles of the places, padded by this share of the longer side
FIT_LOW, FIT_HIGH, FIT_PAD = 0.02, 0.98, 0.12
MIN_SIDE = 0.01        # a box never narrower than this share of the map
CANVAS_LEAST = (320, 260)  # the canvas's floor in pixels; it does not grow with the text
BOSS_ROWS_MAX = 3      # the boss bars' lines at most (BossBars)

# Marker geometry at 100% text, in pixels (scaled_px)
RADIUS_PX = 8          # a player's body
RING_GAP_PX = 3.5      # the health ring's radius past the body
RING_WIDTH_PX = 2.5
SHIELD_GAP_PX = 6.5
SHIELD_WIDTH_PX = 1.5
NOSE_GAP_PX = 4.5
NOSE_LENGTH_PX = 5
NOSE_HALF_PX = 3.2
SELECT_GAP_PX = 9      # the selection ring's radius past the body
NUMBER_SCALE = 0.78    # the number's size against the application font
BOSS_SCALE = 1.55      # a boss's hexagon against a player's body
ADD_SCALE = 0.52
SMALL_SCALE = 0.42     # pets, '+' marks
LOOSE_SCALE = 0.6
# Players closer than this many radii, their markers overlapping by over a
# quarter, make a pile, drawn as one badge listing them, this many a row
PILE_SHARE = 1.5
PILE_PER_ROW = 6
TRACK_ALPHA = 0.13     # the health ring's track: decorative
NOSE_ALPHA = 0.75
GRID_ALPHA = 0.06      # the faint grid: decorative, a reference for movement, not a scale
GRID_STEPS = (0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5)

# New colours, keyed {False: light, True: dark}; measured in the module notes
HOSTILE_COLORS = {False: "#a8322d", True: "#ef6f6c"}
BOSS_COLORS = {False: "#7a1f1b", True: "#ff8a80"}


def is_dark(widget) -> bool:
    """Whether *widget* is drawn in the dark theme: its background's
    lightness, read at paint, as the timeline strip reads it."""
    return widget.palette().color(widget.backgroundRole()).lightness() < 128


def colors(dark: bool, base=None) -> dict:
    """The canvas's colours for a theme, as QColors: ink, muted, base (the
    surface; *base* when given, the palette's), health (four steps),
    shield, damage, hostile, boss, and the decorative track, nose and grid
    inks."""
    pane, recap = _pane_theme(dark), _RECAP_THEMES[bool(dark)]
    ink = QColor(pane["text"])

    def faded(alpha):
        color = QColor(ink)
        color.setAlphaF(alpha)
        return color
    return {"ink": ink, "muted": QColor(pane["muted"]),
            "base": QColor(base) if base is not None else QColor("#2d2d2d" if dark else "#ffffff"),
            "health": tuple(QColor(c) for c in recap["health"]),
            "shield": QColor(recap["shield"]), "damage": QColor(recap["damage"]),
            "hostile": QColor(HOSTILE_COLORS[bool(dark)]), "boss": QColor(BOSS_COLORS[bool(dark)]),
            "track": faded(TRACK_ALPHA), "nose": faded(NOSE_ALPHA), "grid": faded(GRID_ALPHA)}


def share_text(value: int, maximum: int) -> str:
    """A share as the window writes it: '42%', '<1%' for a sliver above 0
    (a boss held at 1 health of 17 million), '' with no maximum."""
    if maximum <= 0:
        return ""
    share = round(100 * max(0, value) / maximum)
    return "<1%" if value > 0 and share == 0 else f"{share}%"


def health_color(colours: dict, fraction: float) -> QColor:
    """The death recap's step for a share of health: over 75%, 50%, 25%,
    else the last."""
    good, hurt, low, critical = colours["health"]
    return (good if fraction > 0.75 else hurt if fraction > 0.5
            else low if fraction > 0.25 else critical)


# ------------------------------------------------------------ the moment --

class Roster(NamedTuple):
    """What the window reads of its fight entry for the canvas: each
    player row's number (1-based, companions skipped), role and name, by
    the row's unit id; and the deaths as (moment ms, unit id, name,
    ability, killer), by time."""
    numbers: dict
    roles: dict
    names: dict
    deaths: tuple


EMPTY_ROSTER = Roster({}, {}, {}, ())


def roster_of(entry) -> Roster:
    """The Roster of a fight entry. The moment of a death is the locator's
    start plus the recap's time into the fight (ms since BEGIN_LOG, the
    reader's clock). Never writes into the entry: the engine owns it."""
    numbers, roles, names = {}, {}, {}
    for p in getattr(entry, "players", None) or []:
        if p.get("companion"):
            continue
        unit_id = str(p.get("unit_id") or "")
        if not unit_id or unit_id in numbers:
            continue
        numbers[unit_id] = len(numbers) + 1
        roles[unit_id] = str(p.get("role") or "")
        names[unit_id] = str(p.get("name") or "")
    locator = getattr(entry, "locator", None)
    deaths = []
    if locator is not None:
        for recap in getattr(entry, "death_recaps", None) or []:
            deaths.append((locator.start_ms + int(recap.get("time_ms") or 0),
                           str(recap.get("unit_id") or ""), str(recap.get("name") or ""),
                           str(recap.get("ability") or ""), str(recap.get("killer") or "")))
    return Roster(numbers, roles, names, tuple(sorted(deaths, key=lambda d: d[0])))


class UnitAt(NamedTuple):
    """A unit at the moment. *key*: its selection key (unit_key_of);
    *unit_key*: FightUnit.key, or an unannounced unit's id; *mark*: how it
    is drawn; *number* and *role*: its fight-table row's; *name*: as the
    fight names it, unmasked; *state*: its last state at or before the
    moment (fight_reread.State) or None; *age*: that state's age in ms;
    *where* and *look*: see the constants; *seen*: whether it has a state
    anywhere in the range."""
    key: str
    unit_key: str
    mark: str
    number: int | None
    role: str
    name: str
    state: object
    age: int | None
    where: str
    look: str
    seen: bool = True
    until: int | None = None


class Note(NamedTuple):
    """A death near the moment: *offset_ms* from the moment, *number* of
    the player who died (or None), their *name* (unmasked), the *ability*
    and the *killer*."""
    offset_ms: int
    number: int | None
    name: str
    ability: str
    killer: str


class Scene(NamedTuple):
    """What the canvas draws for one moment *t* (ms since BEGIN_LOG):
    the map *frame* and its *frame_name*, the fitted *box* (x0, x1, y0,
    y1) or None, every *unit* (players in number order, players with no
    row, bosses, then the rest), the death *notes* and the *selected*
    key."""
    t: int
    frame: int
    frame_name: str
    box: tuple | None
    units: tuple
    notes: tuple
    selected: str | None


def unit_key_of(track) -> str:
    """A track's selection key: a player's or companion's key (the
    'unit_id' of their fight-table row), a monster's key and arrival (its
    unit id can name several units in turn), an unannounced unit's id
    after '?'."""
    unit = track.unit
    if unit is None:
        return "?" + str(track.ids[0])
    if unit.kind in PLAYER_KINDS or unit.kind == COMPANION:
        return unit.key
    return f"{unit.key}@{unit.since_ms}"


def _mark_of(track, numbers) -> str:
    unit = track.unit
    if unit is None:
        return MARK_UNKNOWN
    kind = unit.kind
    if kind in PLAYER_KINDS:
        return MARK_PLAYER if unit.key in numbers else MARK_LOOSE
    return {BOSS: MARK_BOSS, ENEMY: MARK_ADD, PET: MARK_PET, COMPANION: MARK_COMPANION,
            OTHER: MARK_OTHER}.get(kind, MARK_OTHER)


def state_age(state, t: int) -> int:
    """How long before *t* the unit was last known to be as *state* says:
    since the last line that wrote it (the reader's seen), 0 when one wrote
    it at or after *t*. Counted from when the state began, a unit standing
    still at full pools would age though the log keeps writing it: over
    seven boss fights of Kyne's Aegis and Sanity's Edge, 1.4 to 19% of the
    players' seconds in the fight had a state over STALE_MS old, and 25 to
    88% of those had a line within the second; in Sanity's Edge's three
    lead-ins 38 to 49% did, and every one had."""
    return max(0, t - min(state.seen, t))


def age_words(unit) -> str:
    """The gap in words: 'last seen 6 s ago' (state_age)."""
    return f"last seen {(unit.age or 0) // 1000} s ago"


def look_of(state, age) -> str:
    """ALIVE, DEAD (health 0), STALE or LOST by the state's age."""
    if state is None:
        return LOST
    if state.health <= 0 and state.health_max > 0:
        return DEAD
    if age > LOST_MS:
        return LOST
    if age > STALE_MS:
        return STALE
    return ALIVE


def still_dead(track, died_at: int, t: int) -> bool:
    """Whether a player the fight counts dead at *died_at* is still dead at
    *t*: no state from the death's own to the moment's has more health than
    the one before it. A revive raises the health; a corpse's stale figures
    repeat or fall, and its own healing tick, which writes magicka and
    stamina both at 0 of a pool (the engine's rule since #221,
    esolog_tail._corpse_pools), is no revive."""
    first, last = track.at(died_at), track.at(t)
    if last < 0:
        return False
    health, magicka, stamina = track.health, track.magicka, track.stamina
    magicka_max, stamina_max = track.magicka_max, track.stamina_max
    for k in range(max(first, 0) + 1, last + 1):
        if health[k] > health[k - 1] and not (magicka[k] == 0 < magicka_max[k]
                                               and stamina[k] == 0 < stamina_max[k]):
            return False
    return True


def fit_boxes(states) -> dict:
    """Frame index -> its box (x0, x1, y0, y1): the FIT_LOW to FIT_HIGH
    percentiles of the players' and bosses' places in that frame over the
    whole range, padded by FIT_PAD of the longer side (see the module)."""
    places: dict = {}
    for track in states.tracks:
        unit = track.unit
        if unit is None or unit.kind not in FIT_KINDS:
            continue
        for x, y, frame in zip(track.x, track.y, track.frame):
            if on_map(x, y):
                xs, ys = places.setdefault(frame, ([], []))
                xs.append(x)
                ys.append(y)
    return {frame: box_of(xs, ys) for frame, (xs, ys) in places.items()}


def box_of(xs, ys) -> tuple:
    """The fitted box of places (see fit_boxes)."""
    xs, ys = sorted(xs), sorted(ys)

    def share(values, q):
        return values[int(q * (len(values) - 1))]
    x0, x1 = share(xs, FIT_LOW), share(xs, FIT_HIGH)
    y0, y1 = share(ys, FIT_LOW), share(ys, FIT_HIGH)
    side = max(x1 - x0, y1 - y0, MIN_SIDE)
    pad = FIT_PAD * side
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half_w, half_h = max(x1 - x0, MIN_SIDE) / 2 + pad, max(y1 - y0, MIN_SIDE) / 2 + pad
    return (cx - half_w, cx + half_w, cy - half_h, cy + half_h)


def map_change_times(states) -> tuple:
    """The time each map frame after the first begins: its first state's,
    the earliest over every track (a track's frames only go up)."""
    times = []
    for frame in range(1, len(states.frames)):
        first = None
        for track in states.tracks:
            column = track.frame
            index = bisect_left(column, frame)
            if index < len(column) and column[index] == frame:
                at = track.t[index]
                first = at if first is None else min(first, at)
        if first is not None:
            times.append(first)
    return tuple(times)


def glide_state(track, state, t: int):
    """*state*, the track's last at or before *t*, placed where the unit
    is drawn at *t* while the window plays (see the module): on the
    straight line from the last line that wrote it (its seen) to the next
    state's first, when those two samples are GLIDE_MS or less apart, in
    one map frame and both on their map; else *state* itself, as paused.
    Only the place moves: the health, the pools and the heading stay the
    last sample's."""
    seen = state.seen
    if t <= seen:
        return state  # a line wrote it at or after the moment: it stood there
    index = track.at(t) + 1
    if index >= len(track):
        return state
    later = track.t[index]
    if later - seen > GLIDE_MS or track.frame[index] != state.frame:
        return state
    x, y = track.x[index], track.y[index]
    if not (on_map(state.x, state.y) and on_map(x, y)):
        return state
    share = (t - seen) / (later - seen)
    return state._replace(x=state.x + (x - state.x) * share, y=state.y + (y - state.y) * share)


def build_scene(states, roster: Roster, t: int, selected: str | None = None,
                shown: dict | None = None, boxes: dict | None = None,
                glide: bool = False) -> Scene:
    """The Scene of moment *t*: every unit with its last state, where it
    is and how it looks (see the module), the moment's frame and box, and
    the deaths near it. *shown*: the Show menu's marks on or off
    (SHOWN_BY_DEFAULT); *boxes*: fit_boxes(states), computed when None;
    *glide*: while the window plays, each place as glide_state gives it,
    never when paused."""
    shown = SHOWN_BY_DEFAULT if shown is None else shown
    boxes = fit_boxes(states) if boxes is None else boxes
    moment = states.moment(t)
    if glide:
        moment = [(track, glide_state(track, state, t), age) for track, state, age in moment]
    last = {id(track): (state, state_age(state, t)) for track, state, _age in moment}
    numbers = roster.numbers
    # Each player's latest death the fight counts, at or before the moment
    # (the roster's deaths are in time order)
    died = {unit_id: at for at, unit_id, *_rest in roster.deaths if at <= t}

    def player_look(track, state, age):
        """look_of, and DEAD from a counted death until a revive (see the
        module): the log can write a dead player's health above 0."""
        key = track.unit.key if track is not None else None
        if state is not None and key in died and still_dead(track, died[key], t):
            return DEAD
        return look_of(state, age)

    players, loose, bosses, rest = {}, [], [], []
    for track in states.tracks:
        mark = _mark_of(track, numbers)
        state, age = last.get(id(track), (None, None))
        unit = track.unit
        name = unit.name if unit is not None else ""
        item = (track, mark, state, age, name)
        if mark == MARK_PLAYER:
            players[unit.key] = item
        elif mark == MARK_LOOSE:
            loose.append(item)
        elif mark == MARK_BOSS:
            bosses.append(item)
        else:
            rest.append(item)

    ordered = []
    for unit_id, number in sorted(numbers.items(), key=lambda kv: kv[1]):
        track, _mark, state, age, name = players.get(unit_id, (None, MARK_PLAYER, None, None, ""))
        until = track.unit.until_ms if track is not None else None
        ordered.append(UnitAt(unit_id, unit_id, MARK_PLAYER, number, roster.roles.get(unit_id, ""),
                              roster.names.get(unit_id) or name, state, age, NOT_YET,
                              player_look(track, state, age), track is not None, until))
    for track, mark, state, age, name in loose + bosses + rest:
        unit = track.unit
        unit_key = unit.key if unit is not None else str(track.ids[0])
        ordered.append(UnitAt(unit_key_of(track), unit_key, mark, None, "", name, state, age,
                              NOT_YET,
                              player_look(track, state, age) if mark == MARK_LOOSE
                              else look_of(state, age), True,
                              unit.until_ms if unit is not None else None))

    frame = _frame_of([u for u in ordered if u.until is None or t <= u.until], selected)
    units = tuple(unit._replace(where=_where(unit, frame, shown, t)) for unit in ordered)
    box = boxes.get(frame)
    if box is None:
        drawn = [u.state for u in units if u.where == DRAWN]
        box = box_of([s.x for s in drawn], [s.y for s in drawn]) if drawn else None
    frames = getattr(states, "frames", ())
    frame_name = frames[frame].name if 0 <= frame < len(frames) else ""
    return Scene(t, frame, frame_name, box, units, notes_at(roster, t), selected)


def _frame_of(units, selected) -> int:
    """The moment's frame: the selected unit's, else the one most players
    with a place on their map are in (the latest such frame on a tie),
    else the bosses', else the latest state's."""
    for unit in units:
        if unit.key == selected and unit.state is not None:
            return unit.state.frame
    for marks in ((MARK_PLAYER, MARK_LOOSE), (MARK_BOSS,)):
        counts: dict = {}
        for unit in units:
            if unit.mark in marks and unit.state is not None and on_map(unit.state.x, unit.state.y):
                count, latest = counts.get(unit.state.frame, (0, 0))
                counts[unit.state.frame] = (count + 1, max(latest, unit.state.t))
        if counts:
            return max(counts, key=lambda frame: counts[frame])
    states = [unit.state for unit in units if unit.state is not None]
    return max(states, key=lambda s: s.t).frame if states else 0


def _where(unit: UnitAt, frame: int, shown: dict, t: int) -> str:
    state = unit.state
    if unit.mark in shown and not shown[unit.mark]:
        return HIDDEN
    if state is None:
        return NOT_YET
    if unit.until is not None and t > unit.until:
        return LEFT
    if unit.mark in (MARK_ADD, MARK_PET, MARK_UNKNOWN, MARK_OTHER) and (
            unit.age > FORGET_MS or (unit.look == DEAD and unit.age > DEAD_ADD_MS)):
        return GONE
    if state.frame != frame:
        return OTHER_MAP
    if not on_map(state.x, state.y):
        return OFF_MAP
    return DRAWN


def notes_at(roster: Roster, t: int) -> tuple:
    """The deaths from NOTES_BEFORE_MS before *t* to NOTES_AFTER_MS after
    it, oldest first."""
    return tuple(Note(at - t, roster.numbers.get(unit_id), name, ability, killer)
                 for at, unit_id, name, ability, killer in roster.deaths
                 if -NOTES_BEFORE_MS <= at - t <= NOTES_AFTER_MS)


def offset_text(offset_ms: int) -> str:
    """'-0.4 s', '+0.6 s'."""
    tenths = round(offset_ms / 100)
    return f"{'-' if tenths < 0 else '+'}{abs(tenths) / 10:.1f} s"


def note_text(note: Note, names=NO_MASK) -> str:
    """'8 died: Grievous Pulse (Lord Falgravn)': the player by number,
    else by name through the Hide names mask; the killer through it too,
    which passes every enemy and hides a player (a PvP log), as the death
    recap does."""
    who = str(note.number) if note.number is not None else (names.text(note.name) or "Someone")
    killer = names.text(note.killer)
    what = f"{note.ability} ({killer})" if note.ability and killer else note.ability or killer
    return f"{who} died: {what}" if what else f"{who} died"


# --------------------------------------------------------------- drawing --

def role_path(cx: float, cy: float, r: float, role: str) -> QPainterPath:
    """A player's body: a square for a tank, a diamond for a healer, a
    circle for anyone else (the shape carries the role, not the colour)."""
    path = QPainterPath()
    if role == "T":
        k = r * 0.9
        path.addRect(QRectF(cx - k, cy - k, 2 * k, 2 * k))
    elif role == "H":
        k = r * 1.25
        path.addPolygon(QPolygonF([QPointF(cx, cy - k), QPointF(cx + k, cy), QPointF(cx, cy + k),
                                   QPointF(cx - k, cy), QPointF(cx, cy - k)]))
    else:
        path.addEllipse(QPointF(cx, cy), r, r)
    return path


def hexagon_path(cx: float, cy: float, r: float) -> QPainterPath:
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
                               for a in (k * math.pi / 3 + math.pi / 6 for k in range(7))]))
    return path


def facing(heading: float) -> tuple[float, float]:
    """The unit vector a heading faces, y down: (-sin h, -cos h), h taken
    modulo 2π (the log writes -π to 2π)."""
    h = float(heading) % (2 * math.pi)
    return -math.sin(h), -math.cos(h)


def number_font(base: QFont) -> QFont:
    """The font of a marker's number: *base* at NUMBER_SCALE, bold."""
    font = QFont(base)
    font.setBold(True)
    if base.pointSizeF() > 0:
        font.setPointSizeF(base.pointSizeF() * NUMBER_SCALE)
    else:
        font.setPixelSize(max(6, round(base.pixelSize() * NUMBER_SCALE)))
    return font


def _pen(color, width: float, style=Qt.SolidLine) -> QPen:
    pen = QPen(color, width)
    pen.setStyle(style)
    pen.setCapStyle(Qt.FlatCap)
    pen.setJoinStyle(Qt.MiterJoin)
    return pen


def draw_ring(painter: QPainter, cx: float, cy: float, radius: float, width: float,
              fraction: float, color, track=None) -> None:
    """An arc of *fraction* of a turn clockwise from 12 o'clock, over a
    full *track* ring when one is given."""
    rect = QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
    painter.setBrush(Qt.NoBrush)
    if track is not None:
        painter.setPen(_pen(track, width))
        painter.drawEllipse(rect)
    fraction = max(0.0, min(1.0, fraction))
    if fraction > 0:
        painter.setPen(_pen(color, width))
        painter.drawArc(rect, 90 * 16, -round(fraction * 360 * 16))


def draw_nose(painter: QPainter, cx: float, cy: float, gap: float, heading: float,
              length: float, half: float, color) -> None:
    """A small triangle *gap* past the centre, pointing where the unit
    faces."""
    fx, fy = facing(heading)
    px, py = -fy, fx
    base = QPointF(cx + fx * gap, cy + fy * gap)
    tip = QPointF(cx + fx * (gap + length), cy + fy * (gap + length))
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(QPolygonF([QPointF(base.x() + px * half, base.y() + py * half), tip,
                                   QPointF(base.x() - px * half, base.y() - py * half)]))


def draw_cross(painter: QPainter, cx: float, cy: float, k: float, color, width: float) -> None:
    pen = _pen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(cx - k, cy - k), QPointF(cx + k, cy + k))
    painter.drawLine(QPointF(cx - k, cy + k), QPointF(cx + k, cy - k))


def _draw_number(painter: QPainter, cx: float, cy: float, r: float, text: str, color,
                 halo=None) -> None:
    box = QRectF(cx - r * 1.6, cy - r, 3.2 * r, 2 * r)
    if halo is not None:
        painter.setPen(halo)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            painter.drawText(box.translated(dx, dy), Qt.AlignCenter, text)
    painter.setPen(color)
    painter.drawText(box, Qt.AlignCenter, text)


def draw_player(painter: QPainter, colours: dict, cx: float, cy: float, r: float, role: str,
                number, look: str, health: float | None, shield: float, heading: float | None,
                font: QFont, selected: bool = False) -> None:
    """A numbered player marker (see the module): the role shape and its
    number, the health ring and shield arc, the nose, the gap marks, and
    the selection ring. *health* and *shield* are shares of the maximum
    health (None: not known)."""
    ink, muted, base = colours["ink"], colours["muted"], colours["base"]
    width = max(1.2, scaled_px(1.5))
    if look in (ALIVE, STALE) and health is not None:
        draw_ring(painter, cx, cy, r + scaled_px(RING_GAP_PX), scaled_px(RING_WIDTH_PX), health,
                  health_color(colours, health), colours["track"])
        if shield > 0:
            draw_ring(painter, cx, cy, r + scaled_px(SHIELD_GAP_PX), scaled_px(SHIELD_WIDTH_PX),
                      min(1.0, shield), colours["shield"])
    if look in (ALIVE, STALE) and heading is not None:
        draw_nose(painter, cx, cy, r + scaled_px(NOSE_GAP_PX), heading, scaled_px(NOSE_LENGTH_PX),
                  scaled_px(NOSE_HALF_PX), colours["nose"])
    if selected:
        painter.setPen(_pen(ink, 2.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), r + scaled_px(SELECT_GAP_PX), r + scaled_px(SELECT_GAP_PX))
    shape = role_path(cx, cy, r, role)
    painter.setFont(font)
    text = "" if number is None else str(number)
    if look == ALIVE:
        painter.setPen(_pen(ink, 1.0))
        painter.setBrush(ink)
        painter.drawPath(shape)
        _draw_number(painter, cx, cy, r, text, base)
    elif look == DEAD:
        painter.setPen(_pen(muted, width))
        painter.setBrush(base)
        painter.drawPath(shape)
        draw_cross(painter, cx, cy, r * 1.05, colours["damage"], max(1.4, r * 0.18))
        _draw_number(painter, cx, cy, r, text, ink, halo=base)
    elif look == STALE:
        painter.setPen(_pen(ink, width, Qt.DashLine))
        painter.setBrush(base)
        painter.drawPath(shape)
        _draw_number(painter, cx, cy, r, text, ink)
    else:  # LOST
        painter.setPen(_pen(muted, width, Qt.DotLine))
        painter.setBrush(base)
        painter.drawPath(shape)
        _draw_number(painter, cx, cy, r, text, muted)


def draw_boss(painter: QPainter, colours: dict, cx: float, cy: float, r: float, look: str,
              health: float | None, heading: float | None, selected: bool = False) -> None:
    """A boss: a hexagon in the boss colour with its health ring and nose;
    hollow and crossed at health 0, outlined dashed or dotted after a gap."""
    br = r * BOSS_SCALE
    color, base = colours["boss"], colours["base"]
    width = max(1.2, scaled_px(1.5))
    if look in (ALIVE, STALE) and health is not None:
        draw_ring(painter, cx, cy, br + scaled_px(4), scaled_px(3), health,
                  health_color(colours, health), colours["track"])
    if look in (ALIVE, STALE) and heading is not None:
        draw_nose(painter, cx, cy, br + scaled_px(6), heading, scaled_px(8), scaled_px(4.5),
                  colours["nose"])
    if selected:
        painter.setPen(_pen(colours["ink"], 2.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), br + scaled_px(SELECT_GAP_PX), br + scaled_px(SELECT_GAP_PX))
    shape = hexagon_path(cx, cy, br)
    if look == ALIVE:
        painter.setPen(_pen(color, 1.0))
        painter.setBrush(color)
    elif look == DEAD:
        painter.setPen(_pen(colours["muted"], width))
        painter.setBrush(base)
    else:
        painter.setPen(_pen(color, width, Qt.DashLine if look == STALE else Qt.DotLine))
        painter.setBrush(base)
    painter.drawPath(shape)
    if look == DEAD:
        draw_cross(painter, cx, cy, br * 0.8, colours["damage"], max(1.4, r * 0.18))


def draw_add(painter: QPainter, colours: dict, cx: float, cy: float, r: float, look: str,
             heading: float | None) -> None:
    """A hostile unit: a small triangle pointing where it faces, a cross
    at health 0, outlined dashed or dotted after a gap."""
    rr = r * ADD_SCALE
    color = colours["hostile"]
    if look == DEAD:
        draw_cross(painter, cx, cy, rr * 0.9, color, max(1.2, scaled_px(1.4)))
        return
    fx, fy = facing(heading or 0.0)
    px, py = -fy, fx
    triangle = QPolygonF([QPointF(cx + fx * rr * 1.5, cy + fy * rr * 1.5),
                          QPointF(cx - fx * rr + px * rr, cy - fy * rr + py * rr),
                          QPointF(cx - fx * rr - px * rr, cy - fy * rr - py * rr)])
    if look == ALIVE:
        painter.setPen(_pen(color, 1.0))
        painter.setBrush(color)
    else:
        painter.setPen(_pen(color, max(1.2, scaled_px(1.3)), Qt.DashLine if look == STALE else Qt.DotLine))
        painter.setBrush(colours["base"])
    painter.drawPolygon(triangle)


def draw_small(painter: QPainter, colours: dict, cx: float, cy: float, r: float, mark: str,
               font: QFont) -> None:
    """A pet (a small hollow dot), a companion (a 'C'), a player with no
    fight-table row (a small hollow circle in ink), or a unit neither
    hostile nor a player's, or never announced (a grey '+')."""
    width = max(1.2, scaled_px(1.4))
    painter.setBrush(Qt.NoBrush)
    if mark == MARK_PET:
        painter.setPen(_pen(colours["muted"], width))
        painter.drawEllipse(QPointF(cx, cy), r * SMALL_SCALE, r * SMALL_SCALE)
    elif mark == MARK_LOOSE:
        painter.setPen(_pen(colours["ink"], width))
        painter.drawEllipse(QPointF(cx, cy), r * LOOSE_SCALE, r * LOOSE_SCALE)
    elif mark == MARK_COMPANION:
        painter.setPen(_pen(colours["muted"], width))
        painter.drawEllipse(QPointF(cx, cy), r * 0.75, r * 0.75)
        painter.setFont(font)
        painter.setPen(colours["ink"])
        painter.drawText(QRectF(cx - r, cy - r, 2 * r, 2 * r), Qt.AlignCenter, "C")
    else:
        k = r * SMALL_SCALE * 1.1
        painter.setPen(_pen(colours["muted"], width))
        painter.drawLine(QPointF(cx - k, cy), QPointF(cx + k, cy))
        painter.drawLine(QPointF(cx, cy - k), QPointF(cx, cy + k))


def marker_icon(mark: str, role: str, side: int, dark: bool, dpr: float = 1.0,
                ink=None) -> QImage:
    """The table's picture of a unit: its role shape, hexagon or small
    circle, filled with the ink (the boss's colour for a boss), drawn by the
    canvas's own shapes, *side* pixels square at device pixel ratio *dpr*;
    with *ink* (a colour name), every shape in it, as on a selected row,
    drawn in the table's highlighted text. An image, cached for the run as
    the glyphs are: a QPixmap kept in a module would outlive the
    application."""
    ink = QColor(ink).name() if ink is not None else None
    key = (mark, role, side, bool(dark), round(dpr, 2), ink)
    cached = _icons.get(key)
    if cached is not None:
        return cached
    device = max(1, round(side * dpr))
    image = QImage(device, device, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    image.setDevicePixelRatio(dpr)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    colours = colors(dark)
    if ink is not None:
        colours["ink"] = colours["boss"] = QColor(ink)
    c = side / 2
    if mark == MARK_BOSS:
        r = side * 0.46 / BOSS_SCALE
        painter.setPen(_pen(colours["boss"], 1.0))
        painter.setBrush(colours["boss"])
        painter.drawPath(hexagon_path(c, c, r * BOSS_SCALE))
    elif mark == MARK_PLAYER:
        r = side * 0.36
        painter.setPen(_pen(colours["ink"], 1.0))
        painter.setBrush(colours["ink"])
        painter.drawPath(role_path(c, c, r, role))
    else:
        painter.setPen(_pen(colours["ink"], 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(c, c), side * 0.25, side * 0.25)
    painter.end()
    _icons[key] = image
    return image


_icons: dict = {}


# ------------------------------------------------------------- the canvas --

class Placed(NamedTuple):
    """A drawn unit on the canvas: the UnitAt, its centre, whether it was
    pinned to the edge (it stands outside the fitted box), and the radius
    a click finds it within."""
    unit: UnitAt
    point: QPointF
    pinned: bool
    hit: float


class Pile(NamedTuple):
    """Numbered players whose markers overlap by over a quarter (closer
    than PILE_SHARE radii), drawn as one badge that lists them, so no
    number hides another: *members* (Placed, in number order), the
    *centre* they stand round, the badge's *rect* and each member's
    *cells* centre in it."""
    members: tuple
    centre: QPointF
    rect: QRectF
    cells: tuple


# The order units are drawn in, last on top: the selected unit is drawn
# after all of them
_DRAW_ORDER = {MARK_UNKNOWN: 0, MARK_OTHER: 0, MARK_PET: 1, MARK_ADD: 2, MARK_COMPANION: 3,
               MARK_LOOSE: 4, MARK_BOSS: 5, MARK_PLAYER: 6}


class PositionsCanvas(QWidget):
    """The plain canvas of one moment (see the module): painted, never in
    the Tab chain; the table beside it carries the keyboard and the
    screen reader. A click on a marker asks for that unit (unit_clicked,
    its selection key)."""

    unit_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = None
        self._message = ""
        self._names = NO_MASK
        self.setFocusPolicy(Qt.NoFocus)
        # Every paint fills the whole canvas first, so the window, the
        # splitter and the pane under it are not painted again with it at
        # each frame of playback (see the module)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumSize(*CANVAS_LEAST)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAccessibleName("Positions")

    # ---- what it shows ----

    def set_scene(self, scene: Scene | None, names=None) -> None:
        self._scene = scene
        self._message = ""
        if names is not None:
            self._names = names
        self.update()

    def set_message(self, text: str) -> None:
        """Words in place of the moment ('Reading the fight's lines…')."""
        self._scene = None
        self._message = text
        self.update()

    def scene(self) -> Scene | None:
        return self._scene

    def message(self) -> str:
        return self._message

    # ---- the colours, read from the palette at paint ----

    def dark(self) -> bool:
        return is_dark(self)

    def colours(self) -> dict:
        return colors(self.dark(), self.palette().color(QPalette.Base))

    def ink(self) -> QColor:
        return self.colours()["ink"]

    def muted(self) -> QColor:
        return self.colours()["muted"]

    def hostile_color(self) -> QColor:
        return self.colours()["hostile"]

    def boss_color(self) -> QColor:
        return self.colours()["boss"]

    # ---- geometry ----

    def radius(self) -> float:
        return float(scaled_px(RADIUS_PX))

    def margin(self) -> float:
        """Room kept round the fitted box for a marker's ring, nose and
        selection ring."""
        return self.radius() + scaled_px(SELECT_GAP_PX) + 3

    def transform(self):
        """(scale, x origin, y origin) taking the scene's box to the
        widget, None when there is no box."""
        scene = self._scene
        if scene is None or scene.box is None:
            return None
        x0, x1, y0, y1 = scene.box
        width, height = max(1e-9, x1 - x0), max(1e-9, y1 - y0)
        margin = self.margin()
        room_w = max(1.0, self.width() - 2 * margin)
        room_h = max(1.0, self.height() - 2 * margin)
        scale = min(room_w / width, room_h / height)
        ox = margin + (room_w - width * scale) / 2 - x0 * scale
        oy = margin + (room_h - height * scale) / 2 - y0 * scale
        return scale, ox, oy

    def placed(self) -> list[Placed]:
        """The drawn units with their centres, in drawing order (the
        selected last)."""
        scene, at = self._scene, self.transform()
        if scene is None or at is None:
            return []
        scale, ox, oy = at
        margin = self.margin()
        inner = QRectF(margin, margin, max(1.0, self.width() - 2 * margin),
                       max(1.0, self.height() - 2 * margin))
        r = self.radius()
        hits = {MARK_PLAYER: r * 1.35, MARK_BOSS: r * BOSS_SCALE + 2, MARK_ADD: max(6.0, r * 0.8),
                MARK_LOOSE: max(6.0, r * 0.8)}
        out = []
        for unit in scene.units:
            if unit.where != DRAWN:
                continue
            x, y = ox + unit.state.x * scale, oy + unit.state.y * scale
            pinned = not inner.contains(QPointF(x, y))
            if pinned:
                x = min(max(x, inner.left()), inner.right())
                y = min(max(y, inner.top()), inner.bottom())
            out.append(Placed(unit, QPointF(x, y), pinned, hits.get(unit.mark, max(6.0, r * 0.6))))
        out.sort(key=lambda p: (p.unit.key == scene.selected, _DRAW_ORDER.get(p.unit.mark, 0),
                                p.unit.mark == MARK_PLAYER and p.unit.look != DEAD))
        return out

    def layout(self) -> tuple[list, list]:
        """(the units drawn on their own, the piles): numbered players
        other than the selected one, not pinned, closer than PILE_SHARE
        radii to another, gathered (with the players near those) into a
        badge at their mean place, kept inside the canvas and off the
        badges before it."""
        placed = self.placed()
        if not placed:
            return [], []
        r = self.radius()
        selected = self._scene.selected
        pileable = [item for item in placed if item.unit.mark == MARK_PLAYER and not item.pinned
                    and item.unit.key != selected]
        parent = list(range(len(pileable)))

        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i, a in enumerate(pileable):
            for j in range(i + 1, len(pileable)):
                b = pileable[j]
                if math.hypot(a.point.x() - b.point.x(), a.point.y() - b.point.y()) < PILE_SHARE * r:
                    parent[root(i)] = root(j)
        groups: dict = {}
        for i, item in enumerate(pileable):
            groups.setdefault(root(i), []).append(item)
        groups = [sorted(group, key=lambda m: m.unit.number) for group in groups.values()
                  if len(group) > 1]
        piled = {item.unit.key for group in groups for item in group}
        singles = [item for item in placed if item.unit.key not in piled]
        # A badge keeps off the players and bosses drawn on their own, and
        # off the badges before it, where the canvas has room
        piles = []
        taken = [self._extent(item, r) for item in singles if item.unit.mark in (MARK_PLAYER, MARK_BOSS)]
        taken += [box for box, _offset, _text in self.note_lines()]
        pad, gap = scaled_px(4), scaled_px(4)
        cell_w, cell_h = 2 * r + gap, 2 * r + scaled_px(8)
        for members in sorted(groups, key=lambda group: group[0].unit.number):
            cx = sum(m.point.x() for m in members) / len(members)
            cy = sum(m.point.y() for m in members) / len(members)
            per_row = min(len(members), PILE_PER_ROW)
            rows = math.ceil(len(members) / per_row)
            width, height = per_row * cell_w + 2 * pad, rows * cell_h + 2 * pad
            rect = self._avoid(QRectF(cx - width / 2, cy - height / 2, width, height), taken)
            taken.append(rect)
            cells = tuple(QPointF(rect.left() + pad + (k % per_row) * cell_w + cell_w / 2,
                                  rect.top() + pad + (k // per_row) * cell_h + r + 1)
                          for k in range(len(members)))
            piles.append(Pile(tuple(members), QPointF(cx, cy), rect, cells))
        return singles, piles

    def _keep_inside(self, rect: QRectF) -> None:
        rect.moveLeft(min(max(rect.left(), 2), max(2, self.width() - rect.width() - 2)))
        rect.moveTop(min(max(rect.top(), 2), max(2, self.height() - rect.height() - 2)))

    def _avoid(self, rect: QRectF, taken: list) -> QRectF:
        """*rect* inside the canvas, moved to the nearest of a few spots
        (beside each box it covers) where it covers nothing in *taken*;
        where none is free, the spot covering least."""
        rect = QRectF(rect)
        self._keep_inside(rect)

        def covered(box):
            return sum(box.intersected(other).width() * box.intersected(other).height()
                       for other in taken if box.intersects(other))
        if not covered(rect):
            return rect
        gap = scaled_px(3)
        spots = [rect]
        for other in taken:
            if not rect.intersects(other):
                continue
            for dx, dy in ((0, other.bottom() + gap - rect.top()), (0, other.top() - gap - rect.bottom()),
                           (other.right() + gap - rect.left(), 0), (other.left() - gap - rect.right(), 0)):
                spot = rect.translated(dx, dy)
                self._keep_inside(spot)
                spots.append(spot)
        centre = rect.center()
        return min(spots, key=lambda box: (covered(box), math.hypot(box.center().x() - centre.x(),
                                                                    box.center().y() - centre.y())))

    def piles(self) -> list:
        return self.layout()[1]

    def unit_at(self, pos) -> Placed | None:
        """The drawn unit a click at *pos* finds, as it is drawn: the
        selected unit (on top of all), a member of a pile (at its place in
        the badge), else the topmost unit whose mark holds the point."""
        point = QPointF(pos)
        singles, piles = self.layout()
        selected = self._scene.selected if self._scene is not None else None

        def hits(item, at):
            return math.hypot(at.x() - point.x(), at.y() - point.y()) <= item.hit
        for item in singles:
            if item.unit.key == selected and hits(item, item.point):
                return item
        for pile in reversed(piles):
            for member, cell in zip(pile.members, pile.cells):
                if hits(member, cell):
                    return member._replace(point=cell)
            if pile.rect.contains(point):
                return None
        for item in reversed(singles):
            if hits(item, item.point):
                return item
        return None

    def point_of(self, key: str) -> QPointF | None:
        """Where the unit *key* is drawn (in its pile's badge when piled),
        None when it is not drawn."""
        singles, piles = self.layout()
        for pile in piles:
            for member, cell in zip(pile.members, pile.cells):
                if member.unit.key == key:
                    return cell
        for item in singles:
            if item.unit.key == key:
                return item.point
        return None

    # ---- events ----

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            item = self.unit_at(event.position())
            if item is not None:
                self.unit_clicked.emit(item.unit.key)
                event.accept()
                return
        super().mousePressEvent(event)

    def event(self, event) -> bool:
        if event.type() == QEvent.ToolTip:
            item = self.unit_at(event.position() if hasattr(event, "position") else event.pos())
            if item is None:
                QToolTip.hideText()
                event.ignore()
            else:
                QToolTip.showText(event.globalPos(), self.tooltip_text(item.unit), self)
            return True
        return super().event(event)

    def tooltip_text(self, unit: UnitAt) -> str:
        """A marker's hover: who, then how they are."""
        name = self._names.text(unit.name) or "Unannounced unit"
        who = f"{unit.number} {name}" if unit.number is not None else name
        state = unit.state
        parts = [who]
        if state is not None and state.health_max > 0:
            parts.append(f"{share_text(state.health, state.health_max)} health")
        if unit.look == DEAD:
            parts.append("dead")
        elif unit.look in (STALE, LOST) and unit.age is not None:
            parts.append(age_words(unit))
        return " · ".join(parts)

    def changeEvent(self, event) -> None:
        if event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange):
            self.update()
        super().changeEvent(event)

    # ---- painting ----

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        colours = self.colours()
        painter.fillRect(self.rect(), colours["base"])
        if self._scene is None:
            self._paint_message(painter, colours)
            return
        at = self.transform()
        if at is not None:
            self._paint_grid(painter, colours, *at)
        # Under the units: a note may be covered, never a unit
        self._paint_notes(painter, colours)
        singles, piles = self.layout()
        r = self.radius()
        number = number_font(self.font())
        small = QFont(self.font())
        selected = self._scene.selected
        for item in singles:
            if item.unit.key != selected:
                self._paint_unit(painter, colours, item, r, number, small, False)
        for pile in piles:
            self._paint_pile(painter, colours, pile, r, number)
        # The labels keep off the markers and the badges where they can
        taken = [self._extent(item, r) for item in singles] + [pile.rect for pile in piles]
        taken += [box for box, _offset, _text in self.note_lines()]
        taken += self._paint_boss_names(painter, colours, singles, r, taken)
        for item in singles:
            if item.unit.key == selected:
                self._paint_unit(painter, colours, item, r, number, small, True)
                # A boss's name is beside it already (_paint_boss_names)
                if item.unit.mark != MARK_BOSS:
                    self._paint_label(painter, colours, item, r, taken)

    def message_layout(self) -> tuple[QRectF, Qt.AlignmentFlag]:
        """(the room, the flags) the message is drawn in: centred, or from
        the top when it is taller than the room, so its first line, which
        says what happened, stays while the end of a long list of places
        tried is cut."""
        pad = scaled_px(16)
        room = QRectF(self.rect()).adjusted(pad, pad, -pad, -pad)
        flags = Qt.AlignCenter | Qt.TextWordWrap
        need = QFontMetricsF(self.font()).boundingRect(room, int(flags), self._message)
        if need.height() > room.height():
            flags = Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap
        return room, flags

    def _paint_message(self, painter, colours) -> None:
        if not self._message:
            return
        painter.setPen(colours["ink"])
        painter.setFont(self.font())
        room, flags = self.message_layout()
        painter.drawText(room, flags, self._message)

    def _paint_grid(self, painter, colours, scale, ox, oy) -> None:
        if scale <= 0:
            return
        step = next((s for s in GRID_STEPS if s * scale >= scaled_px(56)), GRID_STEPS[-1])
        grid = colours["grid"]
        x = math.floor((-ox / scale) / step) * step
        while ox + x * scale <= self.width():
            painter.fillRect(QRectF(ox + x * scale, 0, 1, self.height()), grid)
            x += step
        y = math.floor((-oy / scale) / step) * step
        while oy + y * scale <= self.height():
            painter.fillRect(QRectF(0, oy + y * scale, self.width(), 1), grid)
            y += step

    def _paint_unit(self, painter, colours, item: Placed, r: float, number: QFont, small: QFont,
                    selected: bool) -> None:
        unit, point = item.unit, item.point
        state = unit.state
        cx, cy = point.x(), point.y()
        health = state.health / state.health_max if state.health_max > 0 else None
        heading = None if item.pinned else state.heading
        if unit.mark == MARK_PLAYER:
            shield = state.shield / state.health_max if state.health_max > 0 else 0.0
            draw_player(painter, colours, cx, cy, r, unit.role, unit.number, unit.look, health,
                        shield, heading, number, selected)
        elif unit.mark == MARK_BOSS:
            draw_boss(painter, colours, cx, cy, r, unit.look, health, heading, selected)
        elif unit.mark == MARK_ADD:
            draw_add(painter, colours, cx, cy, r, unit.look, state.heading)
        else:
            draw_small(painter, colours, cx, cy, r, unit.mark, number)
        if selected and unit.mark not in (MARK_PLAYER, MARK_BOSS):
            painter.setPen(_pen(colours["ink"], 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(point, r, r)
        if item.pinned:
            self._paint_pin(painter, colours, item, r)

    def _paint_pile(self, painter, colours, pile: Pile, r: float, number: QFont) -> None:
        """A pile's badge: each member's marker and number as the canvas
        draws them, with a short bar of its health under it, and a dashed
        line to where they stand when the badge was moved off it."""
        painter.setPen(_pen(colours["muted"], 1.0))
        painter.setBrush(colours["base"])
        painter.drawRoundedRect(pile.rect, scaled_px(5), scaled_px(5))
        if not pile.rect.contains(pile.centre):
            edge = QPointF(min(max(pile.centre.x(), pile.rect.left()), pile.rect.right()),
                           min(max(pile.centre.y(), pile.rect.top()), pile.rect.bottom()))
            painter.setPen(_pen(colours["muted"], 1.0, Qt.DashLine))
            painter.drawLine(pile.centre, edge)
            painter.setPen(Qt.NoPen)
            painter.setBrush(colours["muted"])
            painter.drawEllipse(pile.centre, 2.5, 2.5)
        bar_h = max(2, scaled_px(3))
        for member, cell in zip(pile.members, pile.cells):
            unit = member.unit
            draw_player(painter, colours, cell.x(), cell.y(), r, unit.role, unit.number, unit.look,
                        None, 0.0, None, number)
            state = unit.state
            bar = QRectF(cell.x() - r, cell.y() + r + scaled_px(2), 2 * r, bar_h)
            painter.fillRect(bar, colours["track"])
            if unit.look in (ALIVE, STALE) and state.health_max > 0 and state.health > 0:
                share = max(0.0, min(1.0, state.health / state.health_max))
                painter.fillRect(QRectF(bar.left(), bar.top(), bar.width() * share, bar_h),
                                 health_color(colours, share))

    def _paint_pin(self, painter, colours, item: Placed, r: float) -> None:
        """A small arrow beside a unit pinned to the edge, towards where it
        stands, outside the fitted box."""
        at = self.transform()
        if at is None:
            return
        scale, ox, oy = at
        true_x, true_y = ox + item.unit.state.x * scale, oy + item.unit.state.y * scale
        dx, dy = true_x - item.point.x(), true_y - item.point.y()
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return
        dx, dy = dx / length, dy / length
        heading = math.atan2(-dx, -dy)
        draw_nose(painter, item.point.x(), item.point.y(), r + scaled_px(2), heading,
                  scaled_px(6), scaled_px(4), colours["muted"])

    def _extent(self, item: Placed, r: float) -> QRectF:
        """The square a drawn unit's mark covers, its ring and nose
        included."""
        reach = {MARK_PLAYER: r + scaled_px(SHIELD_GAP_PX) + 2,
                 MARK_BOSS: r * BOSS_SCALE + scaled_px(8)}.get(item.unit.mark, r * 0.8)
        return QRectF(item.point.x() - reach, item.point.y() - reach, 2 * reach, 2 * reach)

    def _place(self, width: float, height: float, around: QRectF, taken: list,
               sides=("above", "below", "right", "left")) -> QRectF:
        """A label's box beside *around*: the first side where it covers
        nothing in *taken*, kept inside the canvas; else the first side
        moved off what it covers where it can (_avoid)."""
        gap = scaled_px(3)
        taken = [other for other in taken if other != around]
        boxes = []
        for side in sides:
            if side == "above":
                box = QRectF(around.center().x() - width / 2, around.top() - gap - height, width, height)
            elif side == "below":
                box = QRectF(around.center().x() - width / 2, around.bottom() + gap, width, height)
            elif side == "right":
                box = QRectF(around.right() + gap, around.center().y() - height / 2, width, height)
            else:
                box = QRectF(around.left() - gap - width, around.center().y() - height / 2, width, height)
            self._keep_inside(box)
            if not any(box.intersects(other) for other in taken):
                return box
            boxes.append(box)
        return self._avoid(boxes[0], taken)

    def _paint_boss_names(self, painter, colours, singles, r: float, taken: list) -> list:
        """Each drawn boss's name beside it, never hidden; the boxes used."""
        bold = QFont(self.font())
        bold.setBold(True)
        metrics = QFontMetricsF(bold)
        painter.setFont(bold)
        used = []
        for item in singles:
            if item.unit.mark != MARK_BOSS or not item.unit.name:
                continue
            text = item.unit.name
            box = self._place(metrics.horizontalAdvance(text) + scaled_px(8), metrics.height() + 2,
                              self._extent(item, r), taken + used)
            painter.setPen(Qt.NoPen)
            painter.setBrush(colours["base"])
            painter.drawRoundedRect(box, 3, 3)
            painter.setPen(colours["boss"])
            painter.drawText(box, Qt.AlignCenter, text)
            used.append(box)
        return used

    def _paint_label(self, painter, colours, item: Placed, r: float, taken=()) -> None:
        """The selected unit's name beside it: through the Hide names mask,
        a hidden name drawn as '@' and its pixelated stand-in (name_mask),
        as the pages draw it."""
        name = item.unit.name
        if item.unit.mark == MARK_UNKNOWN or not name:
            name = "Unannounced unit" if item.unit.mark == MARK_UNKNOWN else ""
        if not name:
            return
        bold = QFont(self.font())
        bold.setBold(True)
        metrics = QFontMetricsF(bold)
        before, hidden, after = label_parts(self._names, name)
        image = None
        if hidden:
            image = mask_image(stand_in(hidden), colours["ink"].name(),
                               max(3.0, bold.pointSizeF() if bold.pointSizeF() > 0 else 9.0),
                               True, bold, self.devicePixelRatioF())
        image_w = image.width() / image.devicePixelRatio() if image is not None else 0.0
        width = (metrics.horizontalAdvance(before) + image_w + metrics.horizontalAdvance(after)
                 + scaled_px(10))
        height = metrics.height() + 4
        reach = (r * BOSS_SCALE if item.unit.mark == MARK_BOSS else r) + scaled_px(SELECT_GAP_PX) + 2
        around = QRectF(item.point.x() - reach, item.point.y() - reach, 2 * reach, 2 * reach)
        box = self._place(width, height, around, list(taken), ("right", "left", "below", "above"))
        painter.setPen(_pen(colours["muted"], 1.0))
        painter.setBrush(colours["base"])
        painter.drawRoundedRect(box, 4, 4)
        painter.setFont(bold)
        painter.setPen(colours["ink"])
        x = box.left() + scaled_px(5)
        if before:
            painter.drawText(QRectF(x, box.top(), box.width(), height), Qt.AlignLeft | Qt.AlignVCenter,
                             before)
            x += metrics.horizontalAdvance(before)
        if image is not None:
            painter.drawImage(QPointF(x, box.top() + (height - image.height() / image.devicePixelRatio()) / 2),
                              image)
            x += image_w
        if after:
            painter.drawText(QRectF(x, box.top(), box.width(), height), Qt.AlignLeft | Qt.AlignVCenter,
                             after)

    def note_lines(self) -> list:
        """The notes' lines as drawn: (box, offset, text), top left."""
        notes = self._scene.notes if self._scene is not None else ()
        if not notes:
            return []
        metrics = QFontMetricsF(self.font())
        lines = [(offset_text(n.offset_ms), note_text(n, self._names)) for n in notes[:NOTES_MAX]]
        if len(notes) > NOTES_MAX:
            lines.append(("", f"and {len(notes) - NOTES_MAX} more"))
        offset_w = metrics.horizontalAdvance("+00.0 s") + scaled_px(8)
        height = metrics.height() + scaled_px(2)
        out, y = [], scaled_px(6)
        for offset, text in lines:
            width = min(self.width() - scaled_px(12),
                        scaled_px(5) + offset_w + metrics.horizontalAdvance(text) + scaled_px(8))
            out.append((QRectF(scaled_px(6), y, width, height), offset, text))
            y += height
        return out

    def _paint_notes(self, painter, colours) -> None:
        lines = self.note_lines()
        if not lines:
            return
        small = QFont(self.font())
        metrics = QFontMetricsF(small)
        painter.setFont(small)
        offset_w = metrics.horizontalAdvance("+00.0 s") + scaled_px(8)
        for box, offset, text in lines:
            y, height = box.top(), box.height()
            painter.setPen(Qt.NoPen)
            painter.setBrush(colours["base"])
            painter.drawRect(box)
            painter.setPen(colours["muted"])
            painter.drawText(QRectF(box.left() + scaled_px(5), y, offset_w, height),
                             Qt.AlignLeft | Qt.AlignVCenter, offset)
            painter.setPen(colours["ink"])
            painter.drawText(QRectF(box.left() + scaled_px(5) + offset_w, y,
                                    box.width() - offset_w - scaled_px(5), height),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             metrics.elidedText(text, Qt.ElideRight,
                                                box.width() - offset_w - scaled_px(8)))


def label_parts(names, name: str) -> tuple[str, str, str]:
    """(text before, the hidden part or '', text after) of *name* on the
    canvas: itself when the mask keeps it; else '@' as text, the hidden
    part, whose stand-in (name_mask.stand_in, made from it with its '@')
    is drawn pixelated, so the canvas and the pages show the same word,
    and a companion's "'s Companion" after it (NameMask.html's rule)."""
    if not names.hides(name):
        return name, "", ""
    split = getattr(names, "_split", None)
    hidden, suffix = split(name) if split is not None else (name, "")
    return ("@" if hidden.startswith("@") else ""), hidden, suffix


# ------------------------------------------------------------ boss bars --

class BossBars(QWidget):
    """Each boss's health at the moment, one line each: its name (never
    hidden), a bar in the death recap's health steps over a decorative
    track, and the share with the figures; 'not in the log yet' before
    its first state, 'left' once it has gone. A row is (name, health,
    health max, known): *known* True with a state at the moment, False
    before the boss's first, LEFT after its last unit left. Painted; the
    table and the canvas's description say the same in words.

    At most BOSS_ROWS_MAX lines, so a fight with many boss units still
    fits a 1280x720 screen at 200% text (each line is 40 px there, and
    the window's least height was 520 px plus one line a row: 5 and 6
    rows, as Dreadsail Reef's Reef Guardian and Cloudrest's shades have,
    took 720 and 760 px). Past it the living bosses come first and the
    last line counts the rest, which the table lists; the accessible
    description keeps them all."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list = []  # (name, health, health max, known)
        self.setAccessibleName("Boss health")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def set_bosses(self, rows, describe: bool = True) -> None:
        """Paint *rows*; with *describe* False (a frame of playback, see
        positions_window) the accessible description waits for the next
        call that describes. The layout is asked again only when the
        number of lines changes, which is all the size hint reads."""
        rows = list(rows)
        if rows != self._rows:
            lines = min(len(self._rows), BOSS_ROWS_MAX)
            self._rows = rows
            self.setVisible(bool(rows))
            if min(len(rows), BOSS_ROWS_MAX) != lines:
                self.updateGeometry()
            self.update()
        if describe:
            text = self.accessible_text()
            if text != self.accessibleDescription():
                self.setAccessibleDescription(text)

    def rows(self) -> list:
        return list(self._rows)

    def shown_rows(self) -> tuple[list, int]:
        """(the rows painted, how many more the last line counts): every
        row up to BOSS_ROWS_MAX; past it BOSS_ROWS_MAX - 1 rows, the
        living bosses first, in their order, then the rest."""
        rows = self._rows
        if len(rows) <= BOSS_ROWS_MAX:
            return list(rows), 0
        living = [row for row in rows if row[3] is True and row[2] > 0 and row[1] > 0]
        ordered = living + [row for row in rows if row not in living]
        return ordered[:BOSS_ROWS_MAX - 1], len(rows) - (BOSS_ROWS_MAX - 1)

    def accessible_text(self) -> str:
        return ". ".join(f"{name} {boss_health_text(health, maximum, known)}"
                         for name, health, maximum, known in self._rows)

    def _line(self) -> float:
        return QFontMetricsF(self.font()).height() + scaled_px(4)

    def sizeHint(self) -> QSize:
        lines = min(len(self._rows), BOSS_ROWS_MAX)
        return QSize(scaled_px(320), round(self._line() * lines) + scaled_px(2))

    def minimumSizeHint(self) -> QSize:
        return QSize(scaled_px(160), self.sizeHint().height())

    def changeEvent(self, event) -> None:
        if event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange):
            self.updateGeometry()
            self.update()
        super().changeEvent(event)

    def paintEvent(self, event) -> None:
        if not self._rows:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colours = colors(is_dark(self), self.palette().color(QPalette.Base))
        bold = QFont(self.font())
        bold.setBold(True)
        metrics, bold_metrics = QFontMetricsF(self.font()), QFontMetricsF(bold)
        line = self._line()
        rows, more = self.shown_rows()
        name_w = min(max(bold_metrics.horizontalAdvance(name) for name, *_ in rows),
                     self.width() * 0.4)
        bar_w = max(scaled_px(60), min(scaled_px(220), self.width() * 0.3))
        bar_h = max(4, scaled_px(8))
        for index, (name, health, maximum, known) in enumerate(rows):
            top = index * line
            painter.setFont(bold)
            painter.setPen(colours["ink"])
            painter.drawText(QRectF(0, top, name_w, line), Qt.AlignLeft | Qt.AlignVCenter,
                             bold_metrics.elidedText(name, Qt.ElideRight, name_w))
            x = name_w + scaled_px(8)
            bar = QRectF(x, top + (line - bar_h) / 2, bar_w, bar_h)
            painter.fillRect(bar, colours["track"])
            if known is True and maximum > 0 and health > 0:
                share = max(0.0, min(1.0, health / maximum))
                painter.fillRect(QRectF(bar.left(), bar.top(), bar.width() * share, bar.height()),
                                 health_color(colours, share))
            painter.setFont(self.font())
            painter.setPen(colours["ink"] if known is True else colours["muted"])
            text_x = bar.right() + scaled_px(8)
            text = boss_health_text(health, maximum, known)
            painter.drawText(QRectF(text_x, top, max(1.0, self.width() - text_x), line),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             metrics.elidedText(text, Qt.ElideRight, max(1.0, self.width() - text_x)))
        if more:
            painter.setFont(self.font())
            painter.setPen(colours["muted"])
            painter.drawText(QRectF(0, len(rows) * line, self.width(), line),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             metrics.elidedText(more_bosses_text(more), Qt.ElideRight, self.width()))


def more_bosses_text(count: int) -> str:
    """The boss bars' last line past BOSS_ROWS_MAX: 'and 3 more bosses (in
    the table)'."""
    return f"and {count} more boss{'' if count == 1 else 'es'} (in the table)"


def boss_health_text(health: int, maximum: int, known) -> str:
    """'80% (99,754,917 of 124,193,032)', 'dead', 'not in the log yet', or
    'left' (*known* LEFT: see BossBars)."""
    if known == LEFT:
        return "left"
    if not known:
        return "not in the log yet"
    if maximum <= 0:
        return ""
    if health <= 0:
        return "dead"
    return f"{share_text(health, maximum)} ({health:,} of {maximum:,})"


# ------------------------------------------------------------ scrub bar --

class ScrubBar(QSlider):
    """The fight from the lead-in to the tail, as a bar the moment is
    chosen on (see the module): the lead-in before BEGIN_COMBAT and the
    tail after END_COMBAT hatched, a cross per death, a dashed line at
    each map change, the moment as a line. A click or a drag asks for a
    moment; focused, Left and Right step a second (Shift: a tenth), Home
    and End go to the ends, PgUp and PgDn to the previous and next death.
    Its slider value is whole seconds into the fight, its description the
    moment in words."""

    moment_requested = Signal(int)  # ms since BEGIN_LOG
    step_requested = Signal(int)    # ms to move by
    death_requested = Signal(int)   # -1 the previous death, 1 the next

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._span = None  # (range start, fight start, fight end, range end), ms
        self._t = 0
        self._deaths: tuple = ()
        self._maps: tuple = ()
        self._dragging = False
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Moment")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # A value set from outside (a screen reader setting the slider, as
        # UIA's RangeValue does) asks for that moment; set_moment's own is
        # silent
        self.valueChanged.connect(self._value_set)

    def _value_set(self, value: int) -> None:
        if self._span is not None:
            self.moment_requested.emit(self._span[1] + int(value) * 1000)

    # ---- what it shows ----

    def set_fight(self, range_start: int, start: int, end: int, range_end: int,
                  deaths=(), maps=()) -> None:
        range_end = max(range_end, range_start + 1)
        self._span = (range_start, start, end, range_end)
        self._deaths = tuple(deaths)
        self._maps = tuple(maps)
        self.blockSignals(True)
        self.setRange(math.floor((range_start - start) / 1000), math.ceil((range_end - start) / 1000))
        self.blockSignals(False)
        self.update()

    def set_moment(self, t: int, text: str = "") -> None:
        self._t = int(t)
        if self._span is not None:
            # No valueChanged for the moment's own value; a screen reader
            # still hears the change, an accessibility event and no signal
            self.blockSignals(True)
            self.setValue(round((self._t - self._span[1]) / 1000))
            self.blockSignals(False)
        self.setAccessibleDescription(text)
        self.update()

    def move_to(self, t: int) -> None:
        """The moment's mark alone, for a frame of playback: the slider's
        value and the description, which a screen reader reads, wait for
        set_moment (positions_window's once a second)."""
        self._t = int(t)
        self.update()

    def moment(self) -> int:
        return self._t

    def span(self):
        return self._span

    def deaths(self) -> tuple:
        return self._deaths

    def map_changes(self) -> tuple:
        return self._maps

    # ---- geometry ----

    def _band(self) -> QRectF:
        side = scaled_px(10)
        return QRectF(side, scaled_px(5), max(1.0, self.width() - 2 * side), scaled_px(18))

    def x_of(self, t: int) -> float:
        band = self._band()
        if self._span is None:
            return band.left()
        start, _s, _e, end = self._span
        return band.left() + band.width() * (min(max(t, start), end) - start) / (end - start)

    def t_of(self, x: float) -> int:
        band = self._band()
        if self._span is None:
            return self._t
        start, _s, _e, end = self._span
        share = (x - band.left()) / band.width() if band.width() > 0 else 0.0
        return round(start + max(0.0, min(1.0, share)) * (end - start))

    def sizeHint(self) -> QSize:
        small = QFontMetricsF(self.font())
        return QSize(scaled_px(400), round(scaled_px(5) + scaled_px(18) + scaled_px(4)
                                           + small.height() + scaled_px(4)))

    def minimumSizeHint(self) -> QSize:
        return QSize(scaled_px(160), self.sizeHint().height())

    # ---- events ----

    def keyPressEvent(self, event) -> None:
        key, shift = event.key(), bool(event.modifiers() & Qt.ShiftModifier)
        plain = not (event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
        if plain and key in (Qt.Key_Left, Qt.Key_Right):
            step = 100 if shift else 1000
            self.step_requested.emit(-step if key == Qt.Key_Left else step)
        elif plain and key in (Qt.Key_Home, Qt.Key_End) and self._span is not None:
            self.moment_requested.emit(self._span[0] if key == Qt.Key_Home else self._span[3])
        elif plain and key in (Qt.Key_PageUp, Qt.Key_PageDown):
            self.death_requested.emit(-1 if key == Qt.Key_PageUp else 1)
        else:
            event.ignore()
            return
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._span is not None:
            self.setFocus(Qt.MouseFocusReason)
            self._dragging = True
            self.moment_requested.emit(self.t_of(event.position().x()))
            event.accept()
            return
        event.ignore()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.moment_requested.emit(self.t_of(event.position().x()))
            event.accept()
            return
        event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        event.accept()

    def wheelEvent(self, event) -> None:
        event.ignore()

    def changeEvent(self, event) -> None:
        if event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange):
            self.updateGeometry()
            self.update()
        super().changeEvent(event)

    # ---- painting ----

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colours = colors(is_dark(self), self.palette().color(QPalette.Base))
        band = self._band()
        painter.setPen(_pen(colours["muted"], 1.0))
        painter.setBrush(colours["base"])
        painter.drawRect(band)
        if self._span is None:
            return
        start, fight_start, fight_end, end = self._span
        hatch = QBrush(colours["muted"], Qt.BDiagPattern)
        for lo, hi in ((start, fight_start), (fight_end, end)):
            if hi > lo:
                painter.fillRect(QRectF(self.x_of(lo), band.top(), self.x_of(hi) - self.x_of(lo),
                                        band.height()), hatch)
        painter.setPen(_pen(colours["muted"], 1.0))
        for at in (fight_start, fight_end):
            if start < at < end:
                x = self.x_of(at)
                painter.drawLine(QPointF(x, band.top()), QPointF(x, band.bottom()))
        painter.setPen(_pen(colours["ink"], 1.0, Qt.DashLine))
        for at in self._maps:
            x = self.x_of(at)
            painter.drawLine(QPointF(x, band.top()), QPointF(x, band.bottom()))
        k = band.height() * 0.22
        for at in self._deaths:
            draw_cross(painter, self.x_of(at), band.center().y(), k, colours["damage"],
                       max(1.4, scaled_px(1.6)))
        self._paint_ticks(painter, colours, band, start, fight_start, end)
        x = self.x_of(self._t)
        painter.setPen(_pen(colours["ink"], 2.0))
        painter.drawLine(QPointF(x, band.top() - scaled_px(3)), QPointF(x, band.bottom() + scaled_px(3)))
        knob = scaled_px(4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(colours["ink"])
        painter.drawPolygon(QPolygonF([QPointF(x - knob, band.top() - scaled_px(4)),
                                       QPointF(x + knob, band.top() - scaled_px(4)),
                                       QPointF(x, band.top() + 1)]))
        if self.hasFocus():
            # The bar's own focus mark: Qt's focus frame tints the whole
            # widget in the Fusion style
            painter.setPen(_pen(colours["ink"], 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(band.adjusted(-3, -3, 3, 3), 3, 3)

    def _paint_ticks(self, painter, colours, band, start, fight_start, end) -> None:
        small = QFont(self.font())
        if small.pointSizeF() > 0:
            small.setPointSizeF(small.pointSizeF() * 0.85)
        metrics = QFontMetricsF(small)
        painter.setFont(small)
        label_w = metrics.horizontalAdvance("-00:00") + scaled_px(14)
        span = max(1, end - start)
        step = next((s for s in (5_000, 10_000, 15_000, 30_000, 60_000, 120_000, 300_000, 600_000)
                     if band.width() * s / span >= label_w), 600_000)
        first = math.ceil((start - fight_start) / step) * step
        painter.setPen(colours["muted"])
        at = first
        while fight_start + at <= end:
            x = self.x_of(fight_start + at)
            painter.drawLine(QPointF(x, band.bottom()), QPointF(x, band.bottom() + scaled_px(3)))
            seconds = abs(at) // 1000
            text = f"{'-' if at < 0 else ''}{seconds // 60}:{seconds % 60:02d}"
            painter.drawText(QRectF(x - label_w / 2, band.bottom() + scaled_px(3), label_w,
                                    metrics.height() + 2), Qt.AlignHCenter | Qt.AlignTop, text)
            at += step
