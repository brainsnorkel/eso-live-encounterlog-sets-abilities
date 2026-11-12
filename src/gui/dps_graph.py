"""
DPS over time: a line chart of the group's and each player's dps across a
fight, drawn the way Combat Metrics' graph tab draws it (see damage_stats
for the two curves: the centred moving average over a window of seconds,
Combat Metrics' default 5 s, and the running figure, the live dps as it
stood at each second).

The data is the fight entry's group series (FightHistoryEntry.damage_series)
and each player's (the 'series' and 'boss_series' of their 'damage' dict),
damage summed per second of the fight. The tab offers the window length
(1, 5, 10 or 30 s) or the running figure, the boss units alone in a fight
with a boss, and a legend of checkboxes for the group and every player. The
first eight players (in the fight's ranking) are on to begin with and the
rest off, because eight is as many hues as can be told apart; a player past
the eighth reuses a hue with a dashed line. A player's hue is their rank in
the fight, so hiding others never repaints them.

Two panels, one scale each: the group's figure is as many times a player's
as there are players, so on one scale the players' lines lie flat along
the floor, and a second axis on the same plot is the classic way to mislead.
The group's line gets the upper panel and the players the lower, sharing
the time axis, the crosshair and the tooltip. Drawing otherwise: hairline
solid gridlines a step off the surface, 2 px lines with round joins, the
group's heavier in the pane's text colour, the categorical hues in a fixed
order (eight hues with a light and a dark step; Settings' colour-blind
option swaps in seven measured to stay apart for the dichromacies, with a
cycle of four strokes), text in the pane's own text colours and
never in a series colour, and the end value of each line labelled when a
panel shows four or fewer.

Design: The graph as a fight tab (issue #196). The graph is the main
window's DPS graph tab, beside Fight and Deaths, on the fight the list has
selected, where it was a window that kept the fight it was opened for. The
toolbar's DPS graph and the header's group dps figure open the tab. A tab
widget is as wide as its widest page: the chart's 360 px floor beside a
legend fixed at its 230 px (scaled with the text) widened the column to 729
px at 150% text and 844 px at 200%, cutting the fight list from 347 px to
231 px on every tab (probed). So the legend takes what the chart's floor
leaves, from its 230 px down to 100 px (scaled), each name elided there
and whole in its hover. The legend is named Lines drawn, and the Show
label is the mode's buddy, for a screen reader. The legend's ticks are
kept by the player's handle where there is one, a companion by its name,
which is its owner's handle and Companion (gui.fight_render), and an
anonymous player by the zone and the unit id: the game keeps a player's
unit id through an instance's pulls and gives it to another player in the
next zone, so ticks kept by the id alone went to whoever had it there, and
dropped at every pull they followed the anonymous players no further than
the fight. The mode carries across fights, and the boss switch between
boss fights; a fight without boss damage hides and clears it. The chart's
time axis takes a wider step than the timeline strip's for a long fight
when its labels would run together: the chart is narrower in the tab than
it was in the window.

The group fighting on after the fight's END_COMBAT counts in the fight
(waiting_hits, issue #162): the chart then runs to the group's last hit,
a dashed line where the fight ended, so that damage keeps its own seconds
instead of piling into the fight's last.

A moment can be marked on the chart (issue #214): an Events row asked for
with Ctrl+G is a line down both panels in the palette's highlight, with
its time and what happened at the plot's top, on the side that has room.
The chart and the Events tab count time alike, from the fight's start, so
the mark needs no conversion. It stays through the same fight drawn again
and goes with the fight. A double-click on the chart asks for the events
around the second under it (moment_requested); the keyboard's way to a
moment is the Events tab itself, whose rows the arrow keys walk. The mark
is in the chart's description for a screen reader, after its lines.
"""

import math
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QEvent, QItemSelectionModel, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem,
    QSizePolicy, QStyle, QStyledItemDelegate, QStyleOptionComboBox, QToolTip, QVBoxLayout,
    QWidget,
)

from damage_stats import running_dps, smoothed_dps
from event_rows import clock
from gui.fight_render import _fmt_dps, _fmt_duration, _join
from gui.name_mask import NO_MASK
from gui.text_size import scaled_px
from gui.timeline_strip import _fmt_tick, _tick_step_ms

# The time axis's steps past the timeline strip's, in milliseconds, tried
# in turn until the labels fit (axis_step_ms)
AXIS_STEPS_MS = (10_000, 15_000, 30_000, 60_000, 120_000, 300_000, 600_000, 900_000, 1_800_000)

# The categorical palette, light and dark steps of the same eight hues
SERIES_COLORS = {
    False: ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"),
    True: ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"),
}
MAX_HUES = len(SERIES_COLORS[False])
# The colour-blind set, a Settings option (issue #77, off by default): Paul
# Tol's 'bright' seven, each lightened or darkened only until it stands 3:1
# or more against the graph's surface, then tuned so the closest pair stays
# as far apart as it can for normal vision and the three dichromacies
# (CIEDE2000 after the Machado 2009 simulation: 9.8 at worst on light,
# 13.1 on dark, where the default set measures 5 and 2). Each line also
# takes the next of four strokes, so no two of the first 28 players share
# both colour and stroke, and shape tells lines apart where hue cannot
COLORBLIND_SERIES_COLORS = {
    False: ("#4477aa", "#179fcd", "#1d742b", "#a4952d", "#ed5d6f", "#aa3377", "#939393"),
    True: ("#6896c3", "#6fcfef", "#228833", "#ccbb44", "#f07887", "#c7448f", "#bbbbbb"),
}
DASH_CYCLE = (Qt.SolidLine, Qt.DashLine, Qt.DotLine, Qt.DashDotLine)
GROUP = "Group"
GROUP_PANEL, PLAYER_PANEL = 0, 1
PANEL_TITLES = {GROUP_PANEL: "Group", PLAYER_PANEL: "Players"}
# (label, window in seconds; 0 is the running figure)
MODES = (("Average over 1 s", 1), ("Average over 5 s", 5), ("Average over 10 s", 10),
         ("Average over 30 s", 30), ("Running figure, the live dps", 0))
DEFAULT_MODE = 1  # Combat Metrics' five-second window
BOSS_ONLY_LABEL = "Boss targets only"
NO_DAMAGE = "No damage in this fight"
FIGHT_ENDED = "fight ended"  # the dashed line, when the group fought on after it
LINE_WIDTH = 2.0
GROUP_LINE_WIDTH = 3.0
MARKER_RADIUS = 4.0
DIRECT_LABEL_MAX = 4  # lines labelled with their end value, per panel
# Pixel sizes at 100% text, each grown with a larger text size (gui.text_size)
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 60, 70, 10, 28
PANEL_GAP = 22
GROUP_PANEL_SHARE = 0.36  # of the plot height, when both panels show
LEGEND_WIDTH = 230  # the legend's widest, at 100% text
LEGEND_LEAST = 100  # its narrowest, beside the chart's floor (see the module notes)
LEGEND_NAME = "Lines drawn"
SHOW_LABEL = "Show"
MODE_LEAST_CHARS = 10  # the mode's least width, in characters


def series_color(index: int, dark: bool, colorblind: bool = False) -> QColor:
    """The hue of the player ranked *index* (0-based) in the fight, from
    the colour-blind set when *colorblind*."""
    colors = (COLORBLIND_SERIES_COLORS if colorblind else SERIES_COLORS)[dark]
    return QColor(colors[index % len(colors)])


def series_style(index: int, colorblind: bool = False):
    """The stroke of the player ranked *index*: solid for the first eight
    and dashed after them, or the colour-blind set's cycle of four."""
    if colorblind:
        return DASH_CYCLE[index % len(DASH_CYCLE)]
    return Qt.DashLine if index >= MAX_HUES else Qt.SolidLine


def axis_step_ms(duration_ms: int, plot_px: float, metrics) -> int:
    """The time axis's step for a fight *duration_ms* long on a plot
    *plot_px* wide: the timeline strip's for that length, or a wider one
    until the widest label, two characters apart, fits between two ticks
    (see the module notes). *metrics*: the font's QFontMetrics."""
    step = _tick_step_ms(duration_ms)
    if duration_ms <= 0 or plot_px <= 0:
        return step
    gap = 2 * metrics.averageCharWidth()
    for candidate in [step] + [s for s in AXIS_STEPS_MS if s > step]:
        widest = max(metrics.horizontalAdvance(_fmt_tick(ms))
                     for ms in range(0, duration_ms + 1, candidate))
        if plot_px * candidate / duration_ms >= widest + gap:
            return candidate
    return AXIS_STEPS_MS[-1]


def _nice_step(span: float) -> float:
    """A tick step of 1, 2 or 5 times a power of ten giving about four ticks."""
    if span <= 0:
        return 1.0
    rough = span / 4.0
    magnitude = 10 ** math.floor(math.log10(rough))
    for factor in (1, 2, 5, 10):
        if factor * magnitude >= rough:
            return factor * magnitude
    return 10 * magnitude


class Curve:
    """One line: a key (unit id, or GROUP), its legend name, colour (None
    for the pane's text colour), (x seconds, dps) points, style, and the
    panel it is drawn in."""
    __slots__ = ('key', 'name', 'color', 'points', 'width', 'style', 'panel')

    def __init__(self, key: str, name: str, color: Optional[QColor],
                 points: List[Tuple[float, float]], width: float = LINE_WIDTH,
                 style=Qt.SolidLine, panel: int = PLAYER_PANEL):
        self.key = key
        self.name = name
        self.color = color
        self.points = points
        self.width = width
        self.style = style
        self.panel = panel

    @property
    def dashed(self) -> bool:
        return self.style != Qt.SolidLine

    def value_at(self, t: float) -> Optional[float]:
        """The curve's dps at second *t*: the nearest point within a
        second, None before its first point or after its last."""
        if not self.points or t < self.points[0][0] - 0.5 or t > self.points[-1][0] + 0.5:
            return None
        nearest = min(self.points, key=lambda p: abs(p[0] - t))
        return nearest[1]


class DpsGraph(QWidget):
    """The chart itself; the panel around it builds the curves."""

    # A double-click on the chart: the moment under it, in ms into the fight
    moment_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(360, 240)
        self._curves: List[Curve] = []
        self._panels: List[int] = []  # the panels with a curve, top first
        self._duration_s = 0.0
        self._fight_end_s: Optional[float] = None
        self._y_top: Dict[int, float] = {}
        self._y_step: Dict[int, float] = {}
        self.hover_second: Optional[int] = None
        # A moment another view sent (the Events tab's row, issue #214): its
        # second into the fight and what happened then, None for none
        self._cursor_s: float | None = None
        self._cursor_label = ""
        self._lines_described = ""

    # ---- data ----

    def set_curves(self, curves: List[Curve], duration_s: float,
                   fight_end_s: Optional[float] = None) -> None:
        """The *curves* over *duration_s*, the chart's length; *fight_end_s*,
        the fight's end when it comes before that (the group fought on), is
        marked."""
        self._curves = [c for c in curves if c.points]
        self._duration_s = max(float(duration_s or 0), 0.0)
        self._fight_end_s = (float(fight_end_s) if fight_end_s is not None
                             and 0 < fight_end_s < self._duration_s else None)
        self._panels = sorted({c.panel for c in self._curves})
        self._y_top, self._y_step = {}, {}
        for panel in self._panels:
            peak = max((y for c in self._curves if c.panel == panel for _x, y in c.points),
                       default=0.0)
            step = _nice_step(peak)
            self._y_step[panel] = step
            self._y_top[panel] = max(step, math.ceil(peak / step) * step)
        self.hover_second = None
        # What a screen reader hears for the painted chart (issue #77): the
        # lines drawn, each with its dps at the end of the fight
        description = "; ".join(
            f"{c.name} {_fmt_dps(c.points[-1][1])} at the end" for c in self._curves)
        if self._fight_end_s is not None:
            description += (f"; the fight ended at {_fmt_duration(self._fight_end_s)}, "
                            f"the group fought on to {_fmt_duration(self._duration_s)}")
        self._lines_described = description
        self._describe()
        self.update()

    def set_cursor(self, second: float | None, label: str = "") -> None:
        """Mark the moment *second* into the fight with a line down the
        chart and *label* beside it (issue #214: an Events row asked for on
        the graph); None takes the mark away."""
        self._cursor_s = float(second) if second is not None else None
        self._cursor_label = str(label or "") if second is not None else ""
        self._describe()
        self.update()

    @property
    def cursor(self) -> tuple | None:
        """(second, label) of the moment marked, None for none."""
        return (self._cursor_s, self._cursor_label) if self._cursor_s is not None else None

    def cursor_text(self) -> str:
        """'1:50.6 Died · Bile Spray' for the moment marked, '' for none."""
        if self._cursor_s is None:
            return ""
        return f"{clock(round(self._cursor_s * 1000))} {self._cursor_label}".rstrip()

    def _describe(self) -> None:
        """What a screen reader hears: the lines, then the moment marked."""
        marked = self.cursor_text()
        self.setAccessibleDescription(
            self._lines_described + (f"; marked: {marked}" if marked and self._curves else ""))

    @property
    def curves(self) -> List[Curve]:
        return list(self._curves)

    @property
    def panels(self) -> List[int]:
        return list(self._panels)

    def sizeHint(self):
        return QSize(760, 460)

    # ---- geometry ----

    def _plot_rect(self) -> QRectF:
        """The whole plotting area, every panel and the gaps between."""
        return QRectF(scaled_px(MARGIN_LEFT), scaled_px(MARGIN_TOP),
                      max(1.0, self.width() - scaled_px(MARGIN_LEFT) - scaled_px(MARGIN_RIGHT)),
                      max(1.0, self.height() - scaled_px(MARGIN_TOP) - scaled_px(MARGIN_BOTTOM)))

    def _panel_rect(self, panel: int) -> QRectF:
        plot = self._plot_rect()
        if len(self._panels) < 2:
            return plot
        group_height = (plot.height() - PANEL_GAP) * GROUP_PANEL_SHARE
        if panel == self._panels[0]:
            return QRectF(plot.left(), plot.top(), plot.width(), group_height)
        return QRectF(plot.left(), plot.top() + group_height + PANEL_GAP, plot.width(),
                      plot.height() - group_height - PANEL_GAP)

    def _x_for(self, t: float) -> float:
        plot = self._plot_rect()
        if self._duration_s <= 0:
            return plot.left()
        return plot.left() + plot.width() * min(max(t, 0.0), self._duration_s) / self._duration_s

    def _y_for(self, value: float, panel: int) -> float:
        rect = self._panel_rect(panel)
        top = self._y_top.get(panel, 1.0)
        return rect.bottom() - rect.height() * min(max(value, 0.0), top) / top

    def second_at(self, x: float) -> Optional[int]:
        """The fight second under horizontal position *x*, None outside."""
        plot = self._plot_rect()
        if self._duration_s <= 0 or plot.width() <= 0:
            return None
        frac = (x - plot.left()) / plot.width()
        if frac < 0 or frac > 1:
            return None
        return int(round(frac * self._duration_s))

    # ---- painting ----

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = self.palette()
        text = palette.color(QPalette.Text)
        surface = palette.color(QPalette.Base)
        dim = QColor(text)
        dim.setAlphaF(0.6)
        grid = QColor(text)
        grid.setAlphaF(0.12)
        painter.fillRect(self.rect(), surface)
        if not self._curves or self._duration_s <= 0:
            painter.setPen(dim)
            painter.drawText(self.rect(), Qt.AlignCenter, NO_DAMAGE)
            painter.end()
            return

        metrics = painter.fontMetrics()
        plot = self._plot_rect()
        # Time ticks: hairlines down the whole plot, labels under its foot
        step_ms = axis_step_ms(int(self._duration_s * 1000), plot.width(), metrics)
        ms = 0
        while ms <= self._duration_s * 1000:
            x = self._x_for(ms / 1000.0)
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.setPen(dim)
            painter.drawText(QRectF(x - 30, plot.bottom() + 4, 60, metrics.height()),
                             Qt.AlignHCenter | Qt.AlignTop, _fmt_tick(ms))
            ms += step_ms
        # The fight's end, when the group fought on after it
        if self._fight_end_s is not None:
            x = self._x_for(self._fight_end_s)
            painter.setPen(QPen(dim, 1, Qt.DashLine))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.setPen(dim)
            painter.drawText(QRectF(x + 4, plot.top(), plot.right() - x - 4, metrics.height()),
                             Qt.AlignLeft | Qt.AlignTop, FIGHT_ENDED)

        for panel in self._panels:
            self._paint_panel(painter, panel, text, surface, dim, grid, metrics)

        # The moment another view sent: a line down every panel in the
        # palette's highlight, its time and what happened at the plot's
        # top, on the side with room for it
        if self._cursor_s is not None:
            # A moment off the chart (a death logged after its end, a hit
            # before the pull) is marked at that edge, its own time said
            x = self._x_for(self._cursor_s)
            accent = palette.color(QPalette.Highlight)
            painter.setPen(QPen(accent, 2))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            label = self.cursor_text()
            width = metrics.horizontalAdvance(label) + 8
            left = x + 5 if x + 5 + width <= plot.right() else max(plot.left(), x - 5 - width)
            box = QRectF(left, plot.top() + 1, width, metrics.height() + 2)
            painter.fillRect(box, surface)
            painter.setPen(text)
            painter.drawText(box, Qt.AlignCenter, label)

        # Crosshair down every panel at the hovered second
        if self.hover_second is not None:
            x = self._x_for(float(self.hover_second))
            painter.setPen(QPen(dim, 1))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            for curve in self._curves:
                value = curve.value_at(float(self.hover_second))
                if value is None:
                    continue
                center = QPointF(x, self._y_for(value, curve.panel))
                painter.setPen(QPen(surface, 2))
                painter.setBrush(curve.color or text)
                painter.drawEllipse(center, MARKER_RADIUS, MARKER_RADIUS)
            painter.setBrush(Qt.NoBrush)
        painter.end()

    def _paint_panel(self, painter, panel, text, surface, dim, grid, metrics) -> None:
        rect = self._panel_rect(panel)
        curves = [c for c in self._curves if c.panel == panel]
        # Gridlines and the dps ticks, recessive
        value = 0.0
        top, step = self._y_top[panel], self._y_step[panel]
        while value <= top + 1e-9:
            y = self._y_for(value, panel)
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(dim)
            painter.drawText(QRectF(0, y - metrics.height() / 2,
                                    scaled_px(MARGIN_LEFT) - 8, metrics.height()),
                             Qt.AlignRight | Qt.AlignVCenter, _fmt_dps(value))
            value += step
        painter.setPen(QPen(dim, 1))
        painter.drawLine(QPointF(rect.left(), rect.bottom()), QPointF(rect.right(), rect.bottom()))
        if len(self._panels) > 1:
            painter.setPen(dim)
            painter.drawText(QRectF(rect.left() + 6, rect.top() + 2, 120, metrics.height()),
                             Qt.AlignLeft | Qt.AlignTop, PANEL_TITLES.get(panel, ""))

        # The lines
        painter.save()
        painter.setClipRect(rect.adjusted(-2, -2, 2, 2))
        for curve in curves:
            pen = QPen(curve.color or text, curve.width, curve.style, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            for i, (t, y) in enumerate(curve.points):
                point = QPointF(self._x_for(t), self._y_for(y, panel))
                if i == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            painter.drawPath(path)
        painter.restore()

        # End values, when few enough lines to label without a tangle
        if len(curves) <= DIRECT_LABEL_MAX:
            labels = sorted(((self._y_for(c.points[-1][1], panel), c) for c in curves),
                            key=lambda item: item[0])
            placed: List[float] = []
            for y, curve in labels:
                for other in placed:  # push a label clear of the one above it
                    if abs(y - other) < metrics.height():
                        y = other + metrics.height()
                placed.append(y)
                painter.setPen(QPen(curve.color or text, curve.width, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(QPointF(rect.right() + 4, y), QPointF(rect.right() + 14, y))
                painter.setPen(text)
                painter.drawText(QRectF(rect.right() + 18, y - metrics.height() / 2,
                                        scaled_px(MARGIN_RIGHT) - 20, metrics.height()),
                                 Qt.AlignLeft | Qt.AlignVCenter, _fmt_dps(curve.points[-1][1]))

    # ---- hover ----

    def tooltip_html(self, second: int) -> str:
        """Every visible series' dps at *second*, keyed by a stroke of its
        colour, the value first in bold."""
        text = self.palette().color(QPalette.Text).name()
        rows = []
        for curve in self._curves:
            value = curve.value_at(float(second))
            if value is None:
                continue
            color = (curve.color or QColor(text)).name()
            rows.append(f"<span style='color:{color}'>&#9644;</span> "
                        f"<b>{_fmt_dps(value)}</b> {curve.name}")
        if not rows:
            return ""
        return f"<b>{_fmt_tick(second * 1000)}</b><br>" + "<br>".join(rows)

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        second = self.second_at(pos.x())
        if second != self.hover_second:
            self.hover_second = second
            self.update()
        if second is None:
            QToolTip.hideText()
        else:
            QToolTip.showText(event.globalPosition().toPoint() if hasattr(event, "globalPosition")
                              else event.globalPos(), self.tooltip_html(second), self)
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        """A double-click on the chart: that moment's events (issue #214)."""
        pos = event.position() if hasattr(event, "position") else event.pos()
        second = self.second_at(pos.x())
        if event.button() == Qt.LeftButton and second is not None and self._curves:
            self.moment_requested.emit(int(second) * 1000)
            return
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event):
        if self.hover_second is not None:
            self.hover_second = None
            self.update()
        QToolTip.hideText()
        super().leaveEvent(event)


def _line_icon(color: QColor, style=Qt.SolidLine) -> QIcon:
    """A short stroke of the series colour and stroke, the legend's key."""
    pixmap = QPixmap(28, 12)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QPen(color, 3, style, Qt.RoundCap))
    painter.drawLine(QPointF(3, 6), QPointF(25, 6))
    painter.end()
    return QIcon(pixmap)


def _curve_points(series, window: dict, mode_window: int, duration_s: float):
    if mode_window:
        return smoothed_dps(series or [], mode_window, duration_s)
    window = window or {}
    return running_dps(series or [], window.get("first_s"), window.get("last_s"), duration_s)


class _Legend(QListWidget):
    """The legend, asking for its widest at the text size in force: a
    list view's own width hint is 256 px at any text size, so from 125%
    text the legend never grew past it and its rows lost their figures
    (the fresh review of PR #207)."""

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(scaled_px(LEGEND_WIDTH))
        return hint


class _ModePicker(QComboBox):
    """The curve picker, as wide as its longest item, on a row of its own,
    and never narrower than about ten characters: held to those ten it cut
    its own items, the default among them at 200% text (the fresh review
    of PR #207)."""

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        least = self.style().sizeFromContents(
            QStyle.CT_ComboBox, option,
            QSize(MODE_LEAST_CHARS * self.fontMetrics().averageCharWidth(), hint.height()), self)
        hint.setWidth(min(hint.width(), least.width()))
        return hint


class _LegendRows(QStyledItemDelegate):
    """The legend's rows no wider than the legend, so a long one is cut
    short with an ellipsis, whole in its hover, where a list view gives
    each row its text's width and scrolls sideways."""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setWidth(min(size.width(), self.parent().viewport().width()))
        return size


def legend_key(p: dict, zone: str = "") -> str:
    """The key a player's legend tick is kept by: their handle, or a
    companion's name, which is its owner's handle and Companion; else the
    *zone* and the unit id, the game keeping a player's id through an
    instance's pulls (see the module notes)."""
    name = _join(p.get("name", ""))
    if name.startswith("@"):
        return name
    return f"{zone}/{p.get('unit_id', '')}"


class DpsGraphPanel(QWidget):
    """The DPS graph tab: the chart, a legend of checkboxes, the mode and
    the boss switch, for the fight the main window gives it; the mode and
    the legend's ticks carry from one fight to the next within a session
    (see the module notes)."""

    # A double-click on the chart: the moment under it, in ms into the fight
    moment_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shown = None  # (entry, dark, names) on display
        # The colour-blind series set and strokes (Settings → Display)
        self.colorblind = False
        self._checked: Dict[str, bool] = {}  # legend choices by key, kept across fights
        self._players: List[Tuple[str, str, int]] = []  # (unit id, name, rank)
        self._keys: Dict[str, str] = {}  # unit id -> its legend key, for the fight shown
        self._zone = None  # the zone of the fights the anonymous players' ticks are for

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        self.header = QLabel("")
        self.header.setWordWrap(True)
        layout.addWidget(self.header)
        middle = QHBoxLayout()
        self.graph = DpsGraph()
        self.graph.setAccessibleName("DPS over time")
        self.graph.moment_requested.connect(self.moment_requested)
        middle.addWidget(self.graph, 1)
        self.legend = _Legend()
        self.legend.setAccessibleName(LEGEND_NAME)
        self.legend.setTextElideMode(Qt.ElideRight)
        self.legend.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.legend.setResizeMode(QListView.Adjust)  # rows laid out again as it narrows
        self.legend.setItemDelegate(_LegendRows(self.legend))
        self.legend.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._size_legend()
        self.legend.itemChanged.connect(self._on_legend_changed)
        middle.addWidget(self.legend)
        layout.addLayout(middle, 1)
        # The mode and the boss switch on rows of their own, so the chart's
        # floor and the legend's narrowest set the tab's least width, not a
        # row of both controls (wider than those at 200% text)
        bottom = QHBoxLayout()
        show = QLabel(SHOW_LABEL)
        bottom.addWidget(show)
        self.mode = _ModePicker()
        show.setBuddy(self.mode)
        # Named Show for a screen reader: Qt on Windows names a combo box by
        # its buddy, and on Linux by its current item, the label reaching a
        # reader there as the buddy relation
        self.mode.setAccessibleName(SHOW_LABEL)
        for label, window in MODES:
            self.mode.addItem(label, window)
        self.mode.setCurrentIndex(DEFAULT_MODE)
        self.mode.currentIndexChanged.connect(self._rerender)
        bottom.addWidget(self.mode)
        bottom.addStretch(1)
        layout.addLayout(bottom)
        self.boss_only = QCheckBox(BOSS_ONLY_LABEL)
        self.boss_only.toggled.connect(self._rerender)
        layout.addWidget(self.boss_only)

    def sizeHint(self):
        """No wider than the tab needs: the chart's floor and the legend's
        narrowest. A tab widget asks for its widest page's width, and the
        chart's 760 px took the window's first split from the fight list
        (121 px of 1080, against 348 px before the tab)."""
        hint = super().sizeHint()
        hint.setWidth(self.minimumSizeHint().width())
        return hint

    def minimumSizeHint(self):
        """The chart's floor and the legend's narrowest, with the tab on
        screen; nothing while it is hidden. A tab widget is at least as
        large as its largest page, hidden ones too, and the graph's floor
        held the window at 556 px on every tab, against 286 before the tab
        (the fresh review of PR #207; Chris chose this): showing the graph
        in a narrower window widens it to fit."""
        hint = super().minimumSizeHint()
        if not self.isVisible():
            hint.setWidth(0)
            hint.setHeight(0)
        return hint

    def showEvent(self, event):
        super().showEvent(event)
        self.updateGeometry()  # the floor counts again (minimumSizeHint)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.updateGeometry()

    def _size_legend(self) -> None:
        """The legend's widest and narrowest at the text size in force
        (see the module notes)."""
        self.legend.setMinimumWidth(scaled_px(LEGEND_LEAST))
        self.legend.setMaximumWidth(scaled_px(LEGEND_WIDTH))

    # ---- showing a fight ----

    @property
    def entry(self):
        """The fight on display, None before the first."""
        return self._shown[0] if self._shown is not None else None

    def set_cursor_ms(self, ms, label: str = "") -> None:
        """Mark the moment *ms* into the fight on the chart, with *label*
        (DpsGraph.set_cursor); None takes the mark away. It stays until
        another fight is shown."""
        self.graph.set_cursor(ms / 1000.0 if ms is not None else None, label)

    def show_graph(self, entry, dark: bool, names=None) -> None:
        """Show the fight *entry*: the group's line and every player's.
        *names* is the Hide names mask (gui.name_mask) for the legend and
        the hover."""
        zone = str(getattr(entry, "zone_name", "") or "")
        if zone != self._zone:
            # An anonymous player's tick is their instance's: in the next
            # zone the game gives the unit id to another player (legend_key)
            self._checked = {key: on for key, on in self._checked.items()
                             if key == GROUP or key.startswith("@")}
            self._zone = zone
        if entry is not self.entry:
            self.graph.set_cursor(None)  # a moment of the last fight
        self._shown = (entry, dark, names)
        facts = [entry.boss_name or "", entry.zone_name or "",
                 str(entry.timestamp or ""), f"{_fmt_duration(entry.duration_s)} fight"]
        dps_time = float(getattr(entry, "dps_time_s", 0) or 0)
        if dps_time:
            facts.append(f"{_fmt_duration(max(dps_time, 1.0))} dps time")
        self.header.setText(" · ".join(f for f in facts if f))
        series = getattr(entry, "damage_series", None) or {}
        has_boss = bool(series.get("boss")) or any(
            (p.get("damage") or {}).get("boss_series") for p in entry.players
            if isinstance(p.get("damage"), dict))
        if not has_boss and self.boss_only.isChecked():
            self.boss_only.blockSignals(True)
            self.boss_only.setChecked(False)
            self.boss_only.blockSignals(False)
        self.boss_only.setVisible(has_boss)
        self._fill_legend(entry, dark, names or NO_MASK)
        self._rerender()

    def _fill_legend(self, entry, dark: bool, names) -> None:
        self.legend.blockSignals(True)
        self.legend.clear()
        text_color = self.palette().color(QPalette.Text)
        boss_fight = float(getattr(entry, "group_boss_dps", 0) or 0) > 0
        self._players = []
        self._keys = {}
        group = QListWidgetItem(_line_icon(text_color), self._legend_label(
            GROUP, entry.group_boss_dps, entry.group_dps, boss_fight))
        group.setToolTip(group.text())
        group.setData(Qt.UserRole, GROUP)
        group.setFlags(group.flags() | Qt.ItemIsUserCheckable)
        group.setCheckState(Qt.Checked if self._checked.get(GROUP, True) else Qt.Unchecked)
        self.legend.addItem(group)
        for rank, p in enumerate(entry.players):
            unit_id = str(p.get("unit_id", ""))
            # The name as the legend and the hover show it: through the
            # Hide names mask, so a hidden player reads as blocks there too
            name = names.text(_join(p.get("name", ""))) or unit_id
            self._players.append((unit_id, name, rank))
            self._keys[unit_id] = legend_key(p, self._zone)
            item = QListWidgetItem(_line_icon(series_color(rank, dark, self.colorblind),
                                              series_style(rank, self.colorblind)),
                                   self._legend_label(name, p.get("boss_dps"), p.get("dps"),
                                                      boss_fight))
            # Elided in a narrow legend, whole in the hover
            item.setToolTip(item.text())
            item.setData(Qt.UserRole, unit_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            default = rank < MAX_HUES
            ticked = self._checked.get(self._keys[unit_id], default)
            item.setCheckState(Qt.Checked if ticked else Qt.Unchecked)
            self.legend.addItem(item)
        self.legend.blockSignals(False)

    @staticmethod
    def _legend_label(name: str, boss_dps, dps, boss_fight: bool) -> str:
        figure = _fmt_dps(float(dps or 0))
        if boss_fight:
            figure = f"{_fmt_dps(float(boss_dps or 0))} / {figure}"
        return f"{name}   {figure}"

    def _on_legend_changed(self, item) -> None:
        unit_id = str(item.data(Qt.UserRole))
        key = self._keys.get(unit_id, unit_id)
        ticked = item.checkState() == Qt.Checked
        self._checked[key] = ticked
        # A player with two rows (gone and back in the fight, a unit id
        # each) shares one key: the other row follows the tick
        self.legend.blockSignals(True)
        for row in range(self.legend.count()):
            other = self.legend.item(row)
            if other is not item and self._keys.get(str(other.data(Qt.UserRole))) == key:
                other.setCheckState(Qt.Checked if ticked else Qt.Unchecked)
        self.legend.blockSignals(False)
        self._rerender()

    def checked_keys(self) -> List[str]:
        """The legend's ticked entries, GROUP and unit ids, in legend order."""
        keys = []
        for row in range(self.legend.count()):
            item = self.legend.item(row)
            if item.checkState() == Qt.Checked:
                keys.append(str(item.data(Qt.UserRole)))
        return keys

    def _rerender(self) -> None:
        if self._shown is None:
            return
        entry, dark, _names = self._shown
        fight_s = float(entry.duration_s or 0)
        mode_window = int(self.mode.currentData() or 0)
        boss = self.boss_only.isChecked()
        checked = set(self.checked_keys())
        curves: List[Curve] = []
        series = getattr(entry, "damage_series", None) or {}
        # The group's last hit after the fight's end (the group fought on):
        # the chart runs to it
        duration = max(fight_s, float((series.get("window") or {}).get("last_s") or 0))
        if GROUP in checked and series:
            points = _curve_points(series.get("boss" if boss else "all"),
                                   series.get("boss_window" if boss else "window"),
                                   mode_window, duration)
            curves.append(Curve(GROUP, GROUP, None, points, GROUP_LINE_WIDTH, panel=GROUP_PANEL))
        by_unit = {str(p.get("unit_id", "")): p for p in entry.players}
        for unit_id, name, rank in self._players:
            if unit_id not in checked:
                continue
            damage = by_unit.get(unit_id, {}).get("damage")
            if not isinstance(damage, dict):
                continue
            points = _curve_points(damage.get("boss_series" if boss else "series"),
                                   damage.get("boss_window" if boss else "window"),
                                   mode_window, duration)
            curves.append(Curve(unit_id, name, series_color(rank, dark, self.colorblind), points,
                                LINE_WIDTH, series_style(rank, self.colorblind), PLAYER_PANEL))
        self.graph.set_curves(curves, duration, fight_end_s=fight_s)

    def changeEvent(self, event):
        # A new text size: the legend's names are wider, so is its column
        if event.type() == QEvent.FontChange:
            self._size_legend()
        super().changeEvent(event)

    def draw(self, entry, dark: bool, names=None) -> None:
        """Show the fight *entry*: in place, the legend keeping its place,
        when it is the fight shown already (changed, a theme switch, Hide
        names); else anew."""
        if self._shown is not None and entry is self._shown[0]:
            with self._keeping_legend_place():
                self.show_graph(entry, dark, names=names)
        else:
            self.show_graph(entry, dark, names=names)

    def clear(self) -> None:
        """Show no fight: the page with no fight (the main window's), whose
        tab is hidden, keeps no names from the last."""
        self._shown = None
        self.header.setText("")
        self.legend.blockSignals(True)
        self.legend.clear()
        self.legend.blockSignals(False)
        self._players = []
        self._keys = {}
        self.graph.set_cursor(None)
        self.graph.set_curves([], 0.0)

    def set_colorblind(self, on: bool, redraw: bool = True) -> None:
        """Switch the series set; with *redraw*, a graph on display is
        redrawn with it, the legend keeping its place (the main window
        draws a hidden tab when it is next shown instead)."""
        if bool(on) == self.colorblind:
            return
        self.colorblind = bool(on)
        if redraw and self._shown is not None:
            entry, dark, names = self._shown
            with self._keeping_legend_place():
                self.show_graph(entry, dark, names=names)

    @contextmanager
    def _keeping_legend_place(self):
        """Fill the legend anew inside the with block and put the reader's
        place in it back, as the other pages keep theirs (issue #196): the
        current line, known by its key, is current again, and selected only
        if it was (the legend makes GROUP current, unselected, when it takes
        the focus); the scroll is put back, and when the fight has ranked
        the line's player anew onto a row out of view at that scroll, the
        row is scrolled into view, if the reader could see the line: one
        they had scrolled away from leaves the legend where they put it.
        scrollToItem's EnsureVisible scrolls only for a row out of view, so
        a line moved a row or two, still in view, leaves the legend where
        the reader had it."""
        current = self.legend.currentItem()
        key = current.data(Qt.UserRole) if current is not None else None
        selected = current is not None and current.isSelected()
        seen = current is not None and self.legend.visualItemRect(current).intersects(
            self.legend.viewport().rect())
        row = self.legend.currentRow()
        scroll = self.legend.verticalScrollBar().value()
        yield
        moved = None  # the line, when the redraw put it on another row
        if key is not None:
            for new_row in range(self.legend.count()):
                item = self.legend.item(new_row)
                if item.data(Qt.UserRole) == key:
                    self.legend.setCurrentRow(new_row, QItemSelectionModel.ClearAndSelect
                                              if selected else QItemSelectionModel.NoUpdate)
                    if new_row != row:
                        moved = item
                    break
        self.legend.doItemsLayout()  # the new rows' scroll range, before setting it
        self.legend.verticalScrollBar().setValue(scroll)
        if moved is not None and seen:
            self.legend.scrollToItem(moved)
