"""
EXPERIMENTAL compact buff/debuff timeline strip (buff-timeline spec).

One thin colored row per tracked effect across the fight duration, with time
tick marks and hover tooltips naming caster and receiver. Deliberately tiny:
it must never crowd the fight summary. Hidden entirely when the displayed
fight carries no timeline data (experiment off, or nothing tracked).
"""

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QToolTip, QWidget

EFFECT_ORDER = ["Major Slayer", "Major Force", "Major Courage",
                "Major Berserk", "Major Vulnerability"]

EFFECT_COLORS = {
    "Major Slayer": QColor("#e57373"),
    "Major Force": QColor("#64b5f6"),
    "Major Courage": QColor("#ffd54f"),
    "Major Berserk": QColor("#ba68c8"),
    "Major Vulnerability": QColor("#4db6ac"),
}

ROW_HEIGHT = 10
ROW_GAP = 2
AXIS_HEIGHT = 14
LABEL_WIDTH = 92
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


class TimelineStrip(QWidget):
    """Paints the per-fight effect timeline; hover shows attribution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timeline = None
        self._rows = []  # ordered effect names present in the timeline
        self.setVisible(False)

    # ---- data ----

    def set_timeline(self, timeline) -> None:
        """timeline: {'duration_ms', 'effects': {...}} or None to hide."""
        valid = bool(timeline and timeline.get("effects")
                     and timeline.get("duration_ms", 0) > 0)
        self._timeline = timeline if valid else None
        self._rows = ([e for e in EFFECT_ORDER if e in timeline["effects"]]
                      if valid else [])
        self.setVisible(bool(self._rows))
        self.updateGeometry()
        self.update()

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
        return QRectF(LABEL_WIDTH, MARGIN,
                      max(1, self.width() - LABEL_WIDTH - MARGIN),
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

        small = QFont(self.font())
        small.setPointSizeF(max(6.5, self.font().pointSizeF() - 2))
        painter.setFont(small)

        duration = self._timeline["duration_ms"]
        effects = self._timeline["effects"]

        for row, effect in enumerate(self._rows):
            rect = self._row_rect(row)
            # Label
            painter.setPen(dim)
            painter.drawText(QRectF(MARGIN, rect.top() - 1,
                                    LABEL_WIDTH - 2 * MARGIN, rect.height() + 2),
                             Qt.AlignRight | Qt.AlignVCenter,
                             effect.replace("Major ", "M."))
            # Track background
            painter.fillRect(rect, track_bg)
            # Fill segments
            color = EFFECT_COLORS.get(effect, QColor("#9e9e9e"))
            for interval in effects[effect]:
                x0 = self._x_for_ms(interval["start_ms"])
                x1 = self._x_for_ms(interval["end_ms"])
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

        # Experimental marking, unobtrusive
        painter.setPen(dim)
        painter.drawText(QRectF(track.right() - 90, 0, 90, MARGIN + ROW_HEIGHT),
                         Qt.AlignRight | Qt.AlignTop, "experimental")
        painter.end()

    # ---- hover attribution ----

    def _intervals_at(self, pos):
        """(effect, [intervals active at pos's time]) or None."""
        if not self._timeline:
            return None
        for row, effect in enumerate(self._rows):
            if self._row_rect(row).adjusted(0, -1, 0, 1).contains(pos):
                ms = self._ms_for_x(pos.x())
                if ms is None:
                    return None
                hits = [iv for iv in self._timeline["effects"][effect]
                        if iv["start_ms"] <= ms <= iv["end_ms"]]
                return effect, ms, hits
        return None

    def event(self, ev):
        if ev.type() == QEvent.ToolTip:
            found = self._intervals_at(ev.position() if hasattr(ev, "position")
                                       else ev.pos())
            if found:
                effect, ms, hits = found
                if hits:
                    lines = [f"<b>{effect}</b> @ {_fmt_tick(ms)}"]
                    for iv in hits:
                        lines.append(
                            f"{_fmt_tick(iv['start_ms'])}–{_fmt_tick(iv['end_ms'])}"
                            f" &nbsp; {iv['source']} → {iv['target']}")
                    QToolTip.showText(ev.globalPos(), "<br>".join(lines), self)
                    return True
            QToolTip.hideText()
            return True
        return super().event(ev)
