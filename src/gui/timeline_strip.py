"""
Compact buff/debuff timeline strip (buff-timeline spec): the only view of
the tracked effects in the fight pane since issue #25, the text uptime line
surviving only in the plain-text copy.

One thin colored row per tracked effect across the fight duration, with the
effect's uptime % in its label, whose effect it is beside it (group, self,
pets, boss, enemies, or mobs for a boss rule measured on the pack of a
fight without a boss), time tick marks, and hover tooltips naming caster
and receiver. A label wider than its column is cut with an ellipsis, and
hovering any label shows it whole. A group buff that only ever reached one or two
receivers is drawn cross-hatched rather than solid (Major Vulnerability and
Taunt are exempt: they target the boss, so a single receiver is their
normal case); paint_sparse_span says why a hatch, and not the dotted line
it replaced.

A single click on a row, label or bar, opens a pop-up summing the row up
over the whole fight: who applied the effect and who had it (issue #19,
effect_summary). It is a transient popup, closed by a click elsewhere or
Esc, and deletes itself on close: Qt owns it through its parent, and it
holds nothing of the strip, so the garbage collector never frees it off
the UI thread.

Buffs come first and debuffs after, with a divider between (issue #26).

A row a rule expects in this group size whose effect never came (issue
#13) reads 0% with its label in dark red and bold, so the gap is seen at a
glance (Chris's request, 2026-10-24); the dark theme gets a lighter red,
since dark red vanishes on a dark pane. The hover text says why the row
is there.

The last row, "Armour" (issue #55, pen_crit.armour_row), is not an effect
but an estimate: the target's armour (18,200 in an instance, 9,100
overland, 27,300 on a solo dungeon's boss) less the group's armour debuffs
on it, second by second, drawn by height like Touch of Z'en's row so the
bar drops as Breach, Crusher and Alkosh land and climbs back as they fall
off; the label carries the estimate and the time-averaged remainder. The
row's intervals carry the debuffs' names and sum for the hover, and its
click summary is its own (the sources-and-receivers popup makes no sense
for it). When the estimate is above the game's 25,000 cap on an enemy's
armour (a solo dungeon's boss) a dashed line marks the cap: armour above
it changes nothing until the debuffs bring it under.

Deliberately tiny: it must never crowd the fight summary. A fight in which
none of the built-in effects was up has no recorded timeline; its tracked
rows are still drawn over the fight's duration (main_window passes it).
Hidden entirely when nothing was up at all.
"""

import math
from html import escape

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QToolTip, QVBoxLayout, QWidget

from effect_rules import DOTS_CAP
from effect_summary import matrix, summarise

EFFECT_ORDER = ["Major Slayer", "Major Force", "Major Courage",
                "Major Berserk", "Powerful Assault", "Major Vulnerability",
                "Taunt"]

EFFECT_COLORS = {
    "Major Slayer": QColor("#e57373"),
    "Major Force": QColor("#64b5f6"),
    "Major Courage": QColor("#ffd54f"),
    "Major Berserk": QColor("#ba68c8"),
    "Powerful Assault": QColor("#ff8a65"),
    "Major Vulnerability": QColor("#4db6ac"),
    "Taunt": QColor("#9575cd"),
}

EFFECT_SHORT = {
    "Major Slayer": "M.Slayer",
    "Major Force": "M.Force",
    "Major Courage": "M.Courage",
    "Major Berserk": "M.Berserk",
    "Powerful Assault": "PA",
    "Major Vulnerability": "M.Vuln",
    "Taunt": "Taunt",
}

# Effects whose normal case is a single receiver (never hatched)
SINGLE_TARGET_EFFECTS = {"Major Vulnerability", "Taunt"}

# The user's tracked effects (effect_rules) get rows after the built-in
# ones, coloured in turn from this list; a stacking rule's bar is drawn with
# a height that follows the stack count over the fight's peak
TRACKED_COLORS = [QColor("#f06292"), QColor("#4dd0e1"), QColor("#aed581"),
                  QColor("#a1887f"), QColor("#90a4ae"), QColor("#ffb74d")]
# The label of an expected row that never came: dark red on a light pane, a
# lighter red on a dark one (keyed by whether the pane is dark)
MISSING_COLORS = {False: QColor("#b71c1c"), True: QColor("#ef5350")}
# The Armour row's bar: a blue-grey of its own, so the rules keep theirs
ARMOUR_COLORS = {False: QColor("#546e7a"), True: QColor("#b0bec5")}

# A group buff reaching at most this many distinct receivers is drawn
# cross-hatched (paint_sparse_span)
SPARSE_RECEIVER_LIMIT = 2
# The hatched fill: the effect's colour at this opacity over the whole
# span, under diagonal lines of the full colour both ways, one every this
# many pixels along the row (never more than the row's height, so that no
# column of the span is without a line)
SPARSE_BASE_ALPHA = 0.35
SPARSE_HATCH_STEP = 8

ROW_HEIGHT = 10
ROW_GAP = 2
AXIS_HEIGHT = 14
LABEL_WIDTH = 120
# A column between the label and the track naming whose effect the row is:
# group, self, pets, boss or enemies (effect_rules scopes); the built-in
# rows are group buffs except the two that sit on the boss
SCOPE_WIDTH = 46
BUILTIN_SCOPES = {"Major Vulnerability": "boss", "Taunt": "boss"}
MARGIN = 4

# Buffs above, debuffs below (issue #26): a row is a debuff when its scope
# word is one of these, the effects on hostile units; anything else, a row
# without a scope word included, is a buff. Each side keeps the order the
# rows come in, built-in rows first, then the rules in Settings order, and
# a divider this many pixels high parts the two when both have rows
DEBUFF_SCOPES = {"boss", "enemies", "mobs"}
DIVIDER_GAP = 5

# The pop-up lists at most this many casters or receivers, then "+N more"
# (a pack's mobs can run to dozens); a caster x receiver grid is added when
# both sides are this small
SUMMARY_LIST_LIMIT = 12
MATRIX_MAX_SOURCES = 4
MATRIX_MAX_TARGETS = 12
CLICK_HINT = "<br><i>Click for who applied it and who had it</i>"


def _tick_step_ms(duration_ms: int) -> int:
    if duration_ms <= 2 * 60_000:
        return 10_000
    if duration_ms <= 10 * 60_000:
        return 30_000
    return 60_000


def _fmt_tick(ms: int) -> str:
    total = ms // 1000
    if total % 60 == 0 and total >= 60:
        return f"{total // 60}m"
    if total >= 60:
        return f"{total // 60}m{total % 60:02d}"
    return f"{total}s"


def strip_timeline(entry):
    """The timeline to draw for a fight entry: its recorded one, or, for a
    fight in which none of the built-in effects was up (none was recorded),
    an empty one over the fight's length, so its tracked rows still show."""
    timeline = getattr(entry, "buff_timeline", None)
    if timeline:
        return timeline
    return {"duration_ms": int((getattr(entry, "duration_s", 0) or 0) * 1000), "effects": {}}


def merged_spans(intervals):
    """The union of intervals: sorted (start_ms, end_ms) pairs that neither
    overlap nor touch, abutting and overlapping ones joined."""
    merged = []
    for start, end in sorted((iv["start_ms"], iv["end_ms"]) for iv in intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def uptime_pct(intervals, duration_ms: int) -> int:
    """Union coverage of intervals as a whole percentage of the fight."""
    if duration_ms <= 0 or not intervals:
        return 0
    covered = sum(end - start for start, end in merged_spans(intervals))
    return min(100, round(100 * covered / duration_ms))


def paint_sparse_span(painter, rect: QRectF, color: QColor, grid_left: float) -> None:
    """Paint one span of a group buff that reached only one or two receivers
    (issue #45): the effect's colour at SPARSE_BASE_ALPHA over the row's
    full height, under a cross-hatch of the full colour, so the span is
    unbroken along the time axis and textured across it.

    Up to 0.13.1 such a span was a dotted line down the row's middle, and a
    row of dots is exactly what a solid bar looks like when the effect
    comes and goes every few seconds: at a glance, up the whole time on
    one person read as up half the time on everyone, and the two call for
    different fixes (whom the buff reaches against how long it lasts). A
    fill with no gaps keeps up reading as up; the hatch says not the whole
    group. The lines are drawn here rather than with one of Qt's pattern
    brushes so that their spacing suits a ten-pixel row (a step no larger
    than the row's height puts a line through every column) and so that
    they fall on a grid anchored at the track's left edge, the same
    wherever a span starts. The caller paints the union of the row's
    intervals, one call per merged span, so overlapping receivers do not
    double the translucent base and abutting spans show no seam.
    """
    base = QColor(color)
    base.setAlphaF(SPARSE_BASE_ALPHA)
    painter.fillRect(rect, base)
    painter.save()
    painter.setClipRect(rect)
    painter.setPen(QPen(color, 1))
    height = rect.height()
    step = min(SPARSE_HATCH_STEP, height)
    x = grid_left + math.floor((rect.left() - height - grid_left) / step) * step
    while x < rect.right():
        painter.drawLine(QPointF(x, rect.bottom()), QPointF(x + height, rect.top()))
        painter.drawLine(QPointF(x, rect.top()), QPointF(x + height, rect.bottom()))
        x += step
    painter.restore()


class TimelineStrip(QWidget):
    """Paints the per-fight effect timeline; hover shows attribution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timeline = None
        self._rows = []       # ordered effect names present in the timeline
        self._row_info = {}   # effect -> {'uptime_pct': int, 'sparse': bool}
        self._tracked = {}    # tracked effect name -> its FightHistoryEntry.tracked item
        self._divider = None  # index of the first debuff row below buff rows, or None
        self.setVisible(False)
        self.setCursor(Qt.PointingHandCursor)

    # ---- data ----

    def set_timeline(self, timeline, tracked=None, armour=None) -> None:
        """timeline: {'duration_ms', 'effects': {...}} or None to hide.
        tracked: the fight's tracked effects (FightHistoryEntry.tracked),
        rows after the built-in ones; a rule that never occurred has none.
        armour: the Armour row (pen_crit.armour_row), last of all, or None."""
        valid = bool(timeline and timeline.get("duration_ms", 0) > 0
                     and (timeline.get("effects") or tracked))
        self._timeline = timeline if valid else None
        self._tracked = {}
        self._rows = ([e for e in EFFECT_ORDER if e in (timeline.get("effects") or {})]
                      if valid else [])
        self._row_info = {}
        if valid:
            duration = timeline["duration_ms"]
            for effect in self._rows:
                intervals = timeline["effects"][effect]
                receivers = {iv.get("target") for iv in intervals}
                self._row_info[effect] = {
                    "uptime_pct": uptime_pct(intervals, duration),
                    "sparse": (effect not in SINGLE_TARGET_EFFECTS
                               and len(receivers) <= SPARSE_RECEIVER_LIMIT),
                    "scope": BUILTIN_SCOPES.get(effect, "group"),
                }
            for index, item in enumerate(tracked or []):
                name = item.get("name")
                # A shown item (seen, or expected in this group size, issue
                # #13) has a row, an empty one when nothing was up; an item
                # from before the flag has one when it has intervals
                shown = item.get("shown")
                if shown is None:
                    shown = bool(item.get("intervals"))
                if not name or not shown or name in self._row_info:
                    continue
                self._tracked[name] = item
                self._rows.append(name)
                pct = round(item.get("uptime_pct", 0))
                self._row_info[name] = {
                    "uptime_pct": pct,
                    # Expected in this group size and never up: the label is
                    # painted in red, bold
                    "missing": bool(item.get("expected")) and pct == 0,
                    "sparse": False,
                    "label": item.get("text", name),
                    # What the rule measured this fight: its scope, or the
                    # pack's mobs for a boss rule in a fight without a boss
                    "scope": item.get("units") or item.get("scope", ""),
                    "color": TRACKED_COLORS[index % len(TRACKED_COLORS)],
                    # A stacking rule's bar is as high as its count over the
                    # peak; a dots rule's over Z'en's five, where 0 is a level
                    "stacks_max": (DOTS_CAP if item.get("kind") == "dots"
                                   else (item.get("max_stacks") or 0) if item.get("kind") == "stacks"
                                   else 0),
                    "zero_level": item.get("kind") == "dots",
                }
        buffs = [r for r in self._rows if self._row_info[r].get("scope") not in DEBUFF_SCOPES]
        debuffs = [r for r in self._rows if self._row_info[r].get("scope") in DEBUFF_SCOPES]
        # The Armour row, last of all: the target's armour less the group's
        # debuffs, by height against the estimate (issue #55)
        if valid and armour and armour.get("intervals") and armour.get("stacks_max"):
            name = str(armour.get("name") or "Armour")
            if name not in self._row_info:
                self._tracked[name] = armour
                self._row_info[name] = {
                    "uptime_pct": 100,
                    "sparse": False,
                    "label": armour.get("label", name),
                    "scope": armour.get("scope", "boss"),
                    "color": self.armour_color(),
                    "stacks_max": int(armour["stacks_max"]),
                    "zero_level": True,
                    "armour": armour,
                }
                debuffs.append(name)
        self._rows = buffs + debuffs
        self._divider = len(buffs) if buffs and debuffs else None
        self.setVisible(bool(self._rows))
        self.updateGeometry()
        self.update()

    def _intervals(self, effect):
        """The intervals of a row, built-in or tracked."""
        if effect in self._tracked:
            return self._tracked[effect]["intervals"]
        return self._timeline["effects"][effect]

    # ---- geometry ----

    def _strip_height(self) -> int:
        if not self._rows:
            return 0
        return MARGIN + self._rows_height() + AXIS_HEIGHT + MARGIN

    def _rows_height(self) -> int:
        """The rows' height, the divider between buffs and debuffs included."""
        return (len(self._rows) * (ROW_HEIGHT + ROW_GAP)
                + (DIVIDER_GAP if self._divider is not None else 0))

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(400, self._strip_height())

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(200, self._strip_height())

    def _track_rect(self) -> QRectF:
        left = LABEL_WIDTH + SCOPE_WIDTH
        return QRectF(left, MARGIN,
                      max(1, self.width() - left - MARGIN),
                      self._rows_height())

    def _row_rect(self, row: int) -> QRectF:
        track = self._track_rect()
        below = DIVIDER_GAP if self._divider is not None and row >= self._divider else 0
        return QRectF(track.left(), MARGIN + row * (ROW_HEIGHT + ROW_GAP) + below,
                      track.width(), ROW_HEIGHT)

    def _divider_y(self):
        """The y of the line between the buff and the debuff rows, or None."""
        if self._divider is None:
            return None
        above = self._row_rect(self._divider - 1).bottom()
        return (above + self._row_rect(self._divider).top()) / 2

    def _x_for_ms(self, ms: int) -> float:
        track = self._track_rect()
        duration = self._timeline["duration_ms"]
        return track.left() + track.width() * min(max(ms, 0), duration) / duration

    def _ms_for_x(self, x: float):
        track = self._track_rect()
        if track.width() <= 0 or not self._timeline:
            return None
        frac = (x - track.left()) / track.width()
        if frac < 0 or frac > 1:
            return None
        return int(frac * self._timeline["duration_ms"])

    # ---- painting ----

    def paintEvent(self, event):
        if not self._timeline or not self._rows:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        palette = self.palette()
        text_color = palette.color(self.foregroundRole())
        dim = QColor(text_color)
        dim.setAlphaF(0.55)
        track_bg = QColor(text_color)
        track_bg.setAlphaF(0.08)

        label_font = self._label_font()
        painter.setFont(label_font)
        missing_font = QFont(label_font)
        missing_font.setBold(True)
        missing_color = self.missing_color()

        duration = self._timeline["duration_ms"]
        track_left = self._track_rect().left()

        for row, effect in enumerate(self._rows):
            rect = self._row_rect(row)
            info = self._row_info.get(effect, {})
            # Label with uptime % (a tracked rule shows its uptime-line text),
            # cut with an ellipsis when it does not fit; hovering it shows
            # the whole label (see _label_at). An expected row that never
            # came is red and bold, so the gap is seen at a glance
            if info.get("missing"):
                painter.setPen(missing_color)
                painter.setFont(missing_font)
            else:
                painter.setPen(dim)
                painter.setFont(label_font)
            painter.drawText(QRectF(MARGIN, rect.top() - 1,
                                    LABEL_WIDTH - 2 * MARGIN, rect.height() + 2),
                             Qt.AlignRight | Qt.AlignVCenter,
                             self._painted_label(effect, info, painter.fontMetrics()))
            painter.setPen(dim)
            painter.setFont(label_font)
            # Whose effect this row is
            painter.drawText(QRectF(LABEL_WIDTH + 2, rect.top() - 1,
                                    SCOPE_WIDTH - 4, rect.height() + 2),
                             Qt.AlignLeft | Qt.AlignVCenter, info.get("scope", ""))
            # Track background
            painter.fillRect(rect, track_bg)
            # Fill segments: the union of the spans, cross-hatched, when the
            # buff reached <=2 receivers (paint_sparse_span); otherwise each
            # interval, a stacking rule's bar as high as its count over the
            # peak
            color = info.get("color") or EFFECT_COLORS.get(effect, QColor("#9e9e9e"))
            stacks_max = info.get("stacks_max", 0)
            if info.get("sparse"):
                for start_ms, end_ms in merged_spans(self._intervals(effect)):
                    x0, x1 = self._x_for_ms(start_ms), self._x_for_ms(end_ms)
                    paint_sparse_span(painter,
                                      QRectF(x0, rect.top(), max(1.0, x1 - x0), rect.height()),
                                      color, track_left)
            else:
                for interval in self._intervals(effect):
                    x0 = self._x_for_ms(interval["start_ms"])
                    x1 = self._x_for_ms(interval["end_ms"])
                    if stacks_max:
                        if info.get("zero_level"):
                            level = max(0, min(stacks_max, int(interval.get("stacks") or 0)))
                        else:
                            level = max(1, min(stacks_max, int(interval.get("stacks") or 1)))
                        height = max(1.0 if level == 0 else 2.0, rect.height() * level / stacks_max)
                        painter.fillRect(QRectF(x0, rect.bottom() - height,
                                                max(1.0, x1 - x0), height), color)
                    else:
                        painter.fillRect(QRectF(x0, rect.top(),
                                                max(1.0, x1 - x0), rect.height()),
                                         color)
            # The game's cap on an enemy's armour, when the estimate is
            # above it: a dashed line across the Armour row at that level
            game_cap = (info.get("armour") or {}).get("game_cap")
            if game_cap and stacks_max and game_cap < stacks_max:
                y = rect.bottom() - rect.height() * game_cap / stacks_max
                painter.setPen(QPen(dim, 1, Qt.DashLine))
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                painter.setPen(dim)

        # The line between the buffs above and the debuffs below
        divider_y = self._divider_y()
        if divider_y is not None:
            painter.setPen(QPen(dim, 1))
            painter.drawLine(int(MARGIN), int(divider_y),
                             int(self._track_rect().right()), int(divider_y))

        # Axis with tick marks
        track = self._track_rect()
        axis_y = track.bottom() + 2
        painter.setPen(dim)
        painter.drawLine(int(track.left()), int(axis_y),
                         int(track.right()), int(axis_y))
        step = _tick_step_ms(duration)
        ms = 0
        while ms <= duration:
            x = self._x_for_ms(ms)
            painter.drawLine(int(x), int(axis_y), int(x), int(axis_y + 3))
            painter.drawText(QRectF(x - 24, axis_y + 2, 48, AXIS_HEIGHT - 2),
                             Qt.AlignHCenter | Qt.AlignTop, _fmt_tick(ms))
            ms += step

        painter.end()

    # ---- labels ----

    def missing_color(self) -> QColor:
        """The red an expected-but-absent row's label is painted in: dark
        red, or a lighter red when the pane's background is dark."""
        dark = self.palette().color(self.backgroundRole()).lightness() < 128
        return MISSING_COLORS[dark]

    def armour_color(self) -> QColor:
        """The Armour row's blue-grey, lighter on a dark pane."""
        dark = self.palette().color(self.backgroundRole()).lightness() < 128
        return ARMOUR_COLORS[dark]

    def _label_font(self) -> QFont:
        """The small font the labels, scope words and ticks are painted in."""
        small = QFont(self.font())
        small.setPointSizeF(max(6.5, self.font().pointSizeF() - 2))
        return small

    def _full_label(self, effect: str, info: dict) -> str:
        """A row's whole label: a rule's uptime-line text, or the built-in
        effect's full name with its uptime."""
        return info.get("label") or f"{effect} {info.get('uptime_pct', 0)}%"

    def _painted_label(self, effect: str, info: dict, metrics) -> str:
        """The label as drawn: the built-in effects by their short names,
        and anything wider than the label column cut with an ellipsis."""
        label = info.get("label") or (f"{EFFECT_SHORT.get(effect, effect)} "
                                      f"{info.get('uptime_pct', 0)}%")
        return metrics.elidedText(label, Qt.ElideRight, int(LABEL_WIDTH - 2 * MARGIN))

    def _label_at(self, pos):
        """(whole label, scope word) of the row whose label or scope word
        is under *pos*, or None."""
        for row, effect in enumerate(self._rows):
            rect = self._row_rect(row)
            band = QRectF(0, rect.top() - 1, LABEL_WIDTH + SCOPE_WIDTH, rect.height() + 2)
            if band.contains(pos):
                info = self._row_info.get(effect, {})
                return self._full_label(effect, info), info.get("scope", "")
        return None

    def _row_at(self, pos):
        """The effect of the row under *pos*, label, scope word or bar, or None."""
        for row, effect in enumerate(self._rows):
            rect = self._row_rect(row)
            if QRectF(0, rect.top() - 1, rect.right() + 1, rect.height() + 2).contains(pos):
                return effect
        return None

    # ---- click: the row's sources and targets ----

    def summary_html(self, effect: str) -> str:
        """The pop-up's text for a row: a header, the casters, the
        receivers, and a caster x receiver grid when both are few."""
        info = self._row_info.get(effect, {})
        if info.get("armour"):
            return self._armour_summary(effect, info)
        intervals = self._intervals(effect)
        duration = self._timeline["duration_ms"]
        stacks = bool(info.get("stacks_max"))
        summary = summarise(intervals, duration, stacks=stacks)
        scope = info.get("scope", "")
        head = [f"<b>{escape(self._full_label(effect, info))}</b>"
                + (f" ({escape(scope)})" if scope else ""),
                f"Up {summary['uptime_pct']}% of {_fmt_tick(duration)} on any unit"]
        if info.get("sparse"):
            receivers = len(summary["targets"])
            head.append(f"<i>Hatched: reached only {receivers} "
                        f"receiver{'s' if receivers != 1 else ''}</i>")
        if not intervals:
            # An expected rule whose effect never came (issue #13)
            head.append("<i>Not up in this fight; shown because the rule is "
                        "expected in a group this size</i>")
            return "<br>".join(head)

        def table(title, columns, lines, cells):
            rows = [f"<tr><th align=left>{escape(title)}</th>"
                    + "".join(f"<th align=right>&nbsp;{c}</th>" for c in columns) + "</tr>"]
            for line in lines[:SUMMARY_LIST_LIMIT]:
                rows.append(f"<tr><td>{escape(line['name'])}</td>"
                            + "".join(f"<td align=right>&nbsp;{v}</td>" for v in cells(line))
                            + "</tr>")
            if len(lines) > SUMMARY_LIST_LIMIT:
                rows.append(f"<tr><td><i>+{len(lines) - SUMMARY_LIST_LIMIT} more</i></td></tr>")
            return "<table cellspacing=0 cellpadding=1>" + "".join(rows) + "</table>"

        sections = [table("Applied by", ["uptime", "alone", "spans"], summary["sources"],
                          lambda l: [f"{l['uptime_pct']}%", f"{l['sole_pct']}%", l["spans"]])]
        if stacks:
            sections.append(table("On", ["uptime", "peak", "at peak", "spans"], summary["targets"],
                                  lambda l: [f"{l['uptime_pct']}%", f"×{l['max_stacks']}",
                                             f"{l['at_max_pct']}%", l["spans"]]))
        else:
            sections.append(table("On", ["uptime", "spans"], summary["targets"],
                                  lambda l: [f"{l['uptime_pct']}%", l["spans"]]))
        grid = matrix(intervals, duration)
        if (grid and len(grid) <= MATRIX_MAX_SOURCES
                and len(summary["targets"]) <= MATRIX_MAX_TARGETS):
            sources = [line["name"] for line in summary["sources"]]
            rows = ["<tr><th align=left>On \\ by</th>"
                    + "".join(f"<th align=right>&nbsp;{escape(s)}</th>" for s in sources) + "</tr>"]
            for line in summary["targets"]:
                target = line["name"]
                rows.append(f"<tr><td>{escape(target)}</td>" + "".join(
                    f"<td align=right>&nbsp;{grid[s][target]}%</td>" if target in grid[s]
                    else "<td align=right>&nbsp;–</td>" for s in sources) + "</tr>")
            sections.append("<table cellspacing=0 cellpadding=1>" + "".join(rows) + "</table>")
        return "<br>".join(head) + "".join(
            f"<p style='margin-top:6px'>{section}</p>" for section in sections)

    def _armour_summary(self, effect: str, info: dict) -> str:
        """The Armour row's pop-up: the estimate and its reason, the armour
        left on average and at the lowest, and how much of the fight had no
        armour debuff at all."""
        armour = info["armour"]
        duration = self._timeline["duration_ms"]
        scope = info.get("scope", "")
        head = (f"<b>{escape(self._full_label(effect, info), quote=False)}</b>"
                + (f" ({escape(scope)})" if scope else ""))
        figures = (f"On {escape(str(armour.get('target') or ''), quote=False)} over "
                   f"{_fmt_tick(duration)}: {int(armour.get('average_left', 0)):,} armour left "
                   f"on average, {int(armour.get('lowest_left', 0)):,} at the lowest; no armour "
                   f"debuff on it for {int(armour.get('no_debuff_pct', 0))}% of the fight")
        explain = f"<i>{escape(str(armour.get('explain') or ''), quote=False)}</i>"
        return "<br>".join((head, figures, explain))

    def show_summary(self, effect: str, global_pos) -> "SummaryPopup":
        """Open the pop-up for *effect*'s row at *global_pos*."""
        QToolTip.hideText()
        popup = SummaryPopup(self.summary_html(effect), self)
        popup.adjustSize()
        popup.move(global_pos)
        popup.show()
        return popup

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._timeline:
            effect = self._row_at(ev.position())
            if effect:
                self.show_summary(effect, ev.globalPosition().toPoint())
                return
        super().mouseReleaseEvent(ev)

    # ---- hover attribution ----

    def _intervals_at(self, pos):
        """(effect, ms, [intervals active at pos's time]) or None."""
        if not self._timeline:
            return None
        for row, effect in enumerate(self._rows):
            if self._row_rect(row).adjusted(0, -1, 0, 1).contains(pos):
                ms = self._ms_for_x(pos.x())
                if ms is None:
                    return None
                hits = [iv for iv in self._intervals(effect)
                        if iv["start_ms"] <= ms <= iv["end_ms"]]
                return effect, ms, hits
        return None

    def event(self, ev):
        if ev.type() == QEvent.ToolTip:
            pos = ev.position() if hasattr(ev, "position") else ev.pos()
            # A row's label, whole, with whose effect it is
            labelled = self._label_at(pos)
            if labelled:
                label, scope = labelled
                text = f"<b>{label}</b> ({scope})" if scope else f"<b>{label}</b>"
                # The Armour row's label says where its estimate comes from
                armour = self._row_info.get(self._row_at(pos) or "", {}).get("armour")
                if armour and armour.get("explain"):
                    text += f"<br>{escape(str(armour['explain']), quote=False)}"
                QToolTip.showText(ev.globalPos(), text + CLICK_HINT, self)
                return True
            found = self._intervals_at(pos)
            if found:
                effect, ms, hits = found
                info = self._row_info.get(effect, {})
                if hits and info.get("armour"):
                    # The armour left at that moment and the debuffs behind it
                    estimate = int(info["armour"].get("estimate") or info.get("stacks_max") or 0)
                    iv = hits[-1]
                    debuffs = str(iv.get("debuffs") or "") or "no armour debuff"
                    taken = int(iv.get("debuff_pen") or 0)
                    lines = [(f"<b>{effect}</b> ({info.get('scope', '')}) @ {_fmt_tick(ms)}"
                              f" &nbsp;·&nbsp; {int(iv.get('stacks') or 0):,} of {estimate:,} left"),
                             escape(debuffs, quote=False)
                             + (f" &nbsp;·&nbsp; {taken:,} off" if taken else "")]
                    QToolTip.showText(ev.globalPos(), "<br>".join(lines) + CLICK_HINT, self)
                    return True
                if hits:
                    lines = [f"<b>{effect}</b> ({info.get('scope', '')}) @ {_fmt_tick(ms)}"
                             f" &nbsp;·&nbsp; uptime {info.get('uptime_pct', 0)}%"]
                    for iv in hits:
                        who = (f"{iv['source']} → {iv['target']}" if iv.get("source")
                               else f"on {iv.get('target', '')}")
                        counted = iv.get("stacks") or (info.get("zero_level") and "stacks" in iv)
                        stacks = f" &nbsp; ×{iv['stacks']}" if counted and effect in self._tracked else ""
                        lines.append(
                            f"{_fmt_tick(iv['start_ms'])}–{_fmt_tick(iv['end_ms'])}"
                            f" &nbsp; {who}{stacks}")
                    QToolTip.showText(ev.globalPos(), "<br>".join(lines) + CLICK_HINT, self)
                    return True
            QToolTip.hideText()
            return True
        return super().event(ev)


class SummaryPopup(QFrame):
    """A row's sources and targets: a transient popup that closes on a click
    elsewhere or Esc and deletes itself when closed. It keeps no reference
    to the strip; Qt owns it through its parent."""

    def __init__(self, html: str, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.label = QLabel(html)
        self.label.setTextFormat(Qt.RichText)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.label)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(ev)
