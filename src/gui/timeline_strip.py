"""
EXPERIMENTAL compact buff/debuff timeline strip (buff-timeline spec).

One thin colored row per tracked effect across the fight duration, with the
effect's uptime % in its label, whose effect it is beside it (group, self,
pets, boss, enemies, or mobs for a boss rule measured on the pack of a
fight without a boss), time tick marks, and hover tooltips naming caster
and receiver. A label wider than its column is cut with an ellipsis, and
hovering any label shows it whole. A group buff that only ever reached one or two
receivers renders dotted rather than solid (Major Vulnerability and Taunt
are exempt: they target the boss, so a single receiver is their normal
case).

Deliberately tiny: it must never crowd the fight summary. Hidden entirely
when the displayed fight carries no timeline data.
"""

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

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

# Effects whose normal case is a single receiver (never rendered dotted)
SINGLE_TARGET_EFFECTS = {"Major Vulnerability", "Taunt"}

# The user's tracked effects (effect_rules) get rows after the built-in
# ones, coloured in turn from this list; a stacking rule's bar is drawn with
# a height that follows the stack count over the fight's peak
TRACKED_COLORS = [QColor("#f06292"), QColor("#4dd0e1"), QColor("#aed581"),
                  QColor("#a1887f"), QColor("#90a4ae"), QColor("#ffb74d")]

# A group buff reaching at most this many distinct receivers renders dotted
SPARSE_RECEIVER_LIMIT = 2

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


def uptime_pct(intervals, duration_ms: int) -> int:
    """Union coverage of intervals as a whole percentage of the fight."""
    if duration_ms <= 0 or not intervals:
        return 0
    spans = sorted((iv["start_ms"], iv["end_ms"]) for iv in intervals)
    covered = 0
    cur_start, cur_end = spans[0]
    for start, end in spans[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            covered += cur_end - cur_start
            cur_start, cur_end = start, end
    covered += cur_end - cur_start
    return min(100, round(100 * covered / duration_ms))


class TimelineStrip(QWidget):
    """Paints the per-fight effect timeline; hover shows attribution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timeline = None
        self._rows = []       # ordered effect names present in the timeline
        self._row_info = {}   # effect -> {'uptime_pct': int, 'dotted': bool}
        self._tracked = {}    # tracked effect name -> its FightHistoryEntry.tracked item
        self.setVisible(False)

    # ---- data ----

    def set_timeline(self, timeline, tracked=None) -> None:
        """timeline: {'duration_ms', 'effects': {...}} or None to hide.
        tracked: the fight's tracked effects (FightHistoryEntry.tracked),
        rows after the built-in ones; a rule that never occurred has none."""
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
                    "dotted": (effect not in SINGLE_TARGET_EFFECTS
                               and len(receivers) <= SPARSE_RECEIVER_LIMIT),
                    "scope": BUILTIN_SCOPES.get(effect, "group"),
                }
            for index, item in enumerate(tracked or []):
                name = item.get("name")
                if not name or not item.get("intervals") or name in self._row_info:
                    continue
                self._tracked[name] = item
                self._rows.append(name)
                self._row_info[name] = {
                    "uptime_pct": int(round(item.get("uptime_pct", 0))),
                    "dotted": False,
                    "label": item.get("text", name),
                    # What the rule measured this fight: its scope, or the
                    # pack's mobs for a boss rule in a fight without a boss
                    "scope": item.get("units") or item.get("scope", ""),
                    "color": TRACKED_COLORS[index % len(TRACKED_COLORS)],
                    "stacks_max": (item.get("max_stacks") or 0) if item.get("kind") == "stacks" else 0,
                }
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
        return (MARGIN + len(self._rows) * (ROW_HEIGHT + ROW_GAP)
                + AXIS_HEIGHT + MARGIN)

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
                      len(self._rows) * (ROW_HEIGHT + ROW_GAP))

    def _row_rect(self, row: int) -> QRectF:
        track = self._track_rect()
        return QRectF(track.left(), MARGIN + row * (ROW_HEIGHT + ROW_GAP),
                      track.width(), ROW_HEIGHT)

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

        painter.setFont(self._label_font())

        duration = self._timeline["duration_ms"]

        for row, effect in enumerate(self._rows):
            rect = self._row_rect(row)
            info = self._row_info.get(effect, {})
            # Label with uptime % (a tracked rule shows its uptime-line text),
            # cut with an ellipsis when it does not fit; hovering it shows
            # the whole label (see _label_at)
            painter.setPen(dim)
            painter.drawText(QRectF(MARGIN, rect.top() - 1,
                                    LABEL_WIDTH - 2 * MARGIN, rect.height() + 2),
                             Qt.AlignRight | Qt.AlignVCenter,
                             self._painted_label(effect, info, painter.fontMetrics()))
            # Whose effect this row is
            painter.drawText(QRectF(LABEL_WIDTH + 2, rect.top() - 1,
                                    SCOPE_WIDTH - 4, rect.height() + 2),
                             Qt.AlignLeft | Qt.AlignVCenter, info.get("scope", ""))
            # Track background
            painter.fillRect(rect, track_bg)
            # Fill segments (dotted when the buff reached <=2 receivers; a
            # stacking rule's bar as high as its count over the peak)
            color = info.get("color") or EFFECT_COLORS.get(effect, QColor("#9e9e9e"))
            dotted = info.get("dotted", False)
            stacks_max = info.get("stacks_max", 0)
            for interval in self._intervals(effect):
                x0 = self._x_for_ms(interval["start_ms"])
                x1 = self._x_for_ms(interval["end_ms"])
                if stacks_max:
                    level = max(1, min(stacks_max, int(interval.get("stacks") or 1)))
                    height = max(2.0, rect.height() * level / stacks_max)
                    painter.fillRect(QRectF(x0, rect.bottom() - height,
                                            max(1.0, x1 - x0), height), color)
                elif dotted:
                    pen = QPen(color, max(2.0, ROW_HEIGHT - 4.0),
                               Qt.DotLine, Qt.FlatCap)
                    painter.setPen(pen)
                    mid_y = rect.center().y()
                    painter.drawLine(int(x0), int(mid_y),
                                     int(max(x0 + 1, x1)), int(mid_y))
                else:
                    painter.fillRect(QRectF(x0, rect.top(),
                                            max(1.0, x1 - x0), rect.height()),
                                     color)

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
                QToolTip.showText(ev.globalPos(),
                                  f"<b>{label}</b> ({scope})" if scope else f"<b>{label}</b>",
                                  self)
                return True
            found = self._intervals_at(pos)
            if found:
                effect, ms, hits = found
                if hits:
                    info = self._row_info.get(effect, {})
                    lines = [f"<b>{effect}</b> ({info.get('scope', '')}) @ {_fmt_tick(ms)}"
                             f" &nbsp;·&nbsp; uptime {info.get('uptime_pct', 0)}%"]
                    for iv in hits:
                        who = (f"{iv['source']} → {iv['target']}" if iv.get("source")
                               else f"on {iv.get('target', '')}")
                        stacks = f" &nbsp; ×{iv['stacks']}" if iv.get("stacks") and effect in self._tracked else ""
                        lines.append(
                            f"{_fmt_tick(iv['start_ms'])}–{_fmt_tick(iv['end_ms'])}"
                            f" &nbsp; {who}{stacks}")
                    QToolTip.showText(ev.globalPos(), "<br>".join(lines), self)
                    return True
            QToolTip.hideText()
            return True
        return super().event(ev)
