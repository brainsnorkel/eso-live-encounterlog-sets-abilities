"""
DPS over time: a line chart of the group's and each player's dps across a
fight, drawn the way Combat Metrics' graph tab draws it (see damage_stats
for the two curves: the centred moving average over a window of seconds,
Combat Metrics' default 5 s, and the running figure, the live dps as it
stood at each second).

The data is the fight entry's group series (FightHistoryEntry.damage_series)
and each player's (the 'series' and 'boss_series' of their 'damage' dict),
damage summed per second of the fight. The window offers the window length
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
order (an eight-slot palette validated for colour-vision deficiency on both
the light and the dark surface), text in the pane's own text colours and
never in a series colour, and the end value of each line labelled when a
panel shows four or fewer.
"""

import math
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QToolTip, QVBoxLayout, QWidget,
)

from damage_stats import running_dps, smoothed_dps
from gui.fight_render import _fmt_dps, _fmt_duration, _join
from gui.name_mask import NO_MASK
from gui.text_size import scaled_px
from gui.timeline_strip import _fmt_tick, _tick_step_ms

# The categorical palette, light and dark steps of the same eight hues
SERIES_COLORS = {
    False: ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"),
    True: ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"),
}
MAX_HUES = len(SERIES_COLORS[False])
GROUP = "Group"
GROUP_PANEL, PLAYER_PANEL = 0, 1
PANEL_TITLES = {GROUP_PANEL: "Group", PLAYER_PANEL: "Players"}
# (label, window in seconds; 0 is the running figure)
MODES = (("Average over 1 s", 1), ("Average over 5 s", 5), ("Average over 10 s", 10),
         ("Average over 30 s", 30), ("Running figure, the live dps", 0))
DEFAULT_MODE = 1  # Combat Metrics' five-second window
BOSS_ONLY_LABEL = "Boss targets only"
NO_DAMAGE = "No damage in this fight"
LINE_WIDTH = 2.0
GROUP_LINE_WIDTH = 3.0
MARKER_RADIUS = 4.0
DIRECT_LABEL_MAX = 4  # lines labelled with their end value, per panel
# Pixel sizes at 100% text, each grown with a larger text size (gui.text_size)
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 60, 70, 10, 28
PANEL_GAP = 22
GROUP_PANEL_SHARE = 0.36  # of the plot height, when both panels show
LEGEND_WIDTH = 230


def series_color(index: int, dark: bool) -> QColor:
    """The hue of the player ranked *index* (0-based) in the fight."""
    return QColor(SERIES_COLORS[dark][index % MAX_HUES])


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
    __slots__ = ('key', 'name', 'color', 'points', 'width', 'dashed', 'panel')

    def __init__(self, key: str, name: str, color: Optional[QColor],
                 points: List[Tuple[float, float]], width: float = LINE_WIDTH,
                 dashed: bool = False, panel: int = PLAYER_PANEL):
        self.key = key
        self.name = name
        self.color = color
        self.points = points
        self.width = width
        self.dashed = dashed
        self.panel = panel

    def value_at(self, t: float) -> Optional[float]:
        """The curve's dps at second *t*: the nearest point within a
        second, None before its first point or after its last."""
        if not self.points or t < self.points[0][0] - 0.5 or t > self.points[-1][0] + 0.5:
            return None
        nearest = min(self.points, key=lambda p: abs(p[0] - t))
        return nearest[1]


class DpsGraph(QWidget):
    """The chart itself; the dialog around it builds the curves."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(360, 240)
        self._curves: List[Curve] = []
        self._panels: List[int] = []  # the panels with a curve, top first
        self._duration_s = 0.0
        self._y_top: Dict[int, float] = {}
        self._y_step: Dict[int, float] = {}
        self.hover_second: Optional[int] = None

    # ---- data ----

    def set_curves(self, curves: List[Curve], duration_s: float) -> None:
        self._curves = [c for c in curves if c.points]
        self._duration_s = max(float(duration_s or 0), 0.0)
        self._panels = sorted({c.panel for c in self._curves})
        self._y_top, self._y_step = {}, {}
        for panel in self._panels:
            peak = max((y for c in self._curves if c.panel == panel for _x, y in c.points),
                       default=0.0)
            step = _nice_step(peak)
            self._y_step[panel] = step
            self._y_top[panel] = max(step, math.ceil(peak / step) * step)
        self.hover_second = None
        self.update()

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
        step_ms = _tick_step_ms(int(self._duration_s * 1000))
        ms = 0
        while ms <= self._duration_s * 1000:
            x = self._x_for(ms / 1000.0)
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.setPen(dim)
            painter.drawText(QRectF(x - 30, plot.bottom() + 4, 60, metrics.height()),
                             Qt.AlignHCenter | Qt.AlignTop, _fmt_tick(ms))
            ms += step_ms

        for panel in self._panels:
            self._paint_panel(painter, panel, text, surface, dim, grid, metrics)

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
            pen = QPen(curve.color or text, curve.width,
                       Qt.DashLine if curve.dashed else Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
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

    def leaveEvent(self, event):
        if self.hover_second is not None:
            self.hover_second = None
            self.update()
        QToolTip.hideText()
        super().leaveEvent(event)


def _line_icon(color: QColor, dashed: bool) -> QIcon:
    """A short stroke of the series colour, the legend's key."""
    pixmap = QPixmap(28, 12)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QPen(color, 3, Qt.DashLine if dashed else Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(3, 6), QPointF(25, 6))
    painter.end()
    return QIcon(pixmap)


def _curve_points(series, window: dict, mode_window: int, duration_s: float):
    if mode_window:
        return smoothed_dps(series or [], mode_window, duration_s)
    window = window or {}
    return running_dps(series or [], window.get("first_s"), window.get("last_s"), duration_s)


class DpsGraphDialog(QDialog):
    """The graph window: the chart, a legend of checkboxes, the mode and
    the boss switch. Modeless like the other windows; it keeps the fight it
    was opened for, and its mode and legend choices from one fight to the
    next within a session."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DPS over time")
        self.resize(1040, 640)
        self._shown = None  # (entry, dark) on display
        self._checked: Dict[str, bool] = {}  # legend choices by key, kept across fights
        self._players: List[Tuple[str, str, int]] = []  # (unit id, name, rank)

        layout = QVBoxLayout(self)
        self.header = QLabel("")
        self.header.setWordWrap(True)
        layout.addWidget(self.header)
        middle = QHBoxLayout()
        self.graph = DpsGraph()
        middle.addWidget(self.graph, 1)
        self.legend = QListWidget()
        self.legend.setFixedWidth(scaled_px(LEGEND_WIDTH))
        self.legend.itemChanged.connect(self._on_legend_changed)
        middle.addWidget(self.legend)
        layout.addLayout(middle, 1)
        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Show"))
        self.mode = QComboBox()
        for label, window in MODES:
            self.mode.addItem(label, window)
        self.mode.setCurrentIndex(DEFAULT_MODE)
        self.mode.currentIndexChanged.connect(self._rerender)
        bottom.addWidget(self.mode)
        self.boss_only = QCheckBox(BOSS_ONLY_LABEL)
        self.boss_only.toggled.connect(self._rerender)
        bottom.addWidget(self.boss_only)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        bottom.addWidget(buttons)
        layout.addLayout(bottom)

    # ---- showing a fight ----

    @property
    def entry(self):
        """The fight on display, None before the first."""
        return self._shown[0] if self._shown is not None else None

    def show_graph(self, entry, dark: bool, names=None) -> None:
        """Show the fight *entry*: the group's line and every player's.
        *names* is the Hide names mask (gui.name_mask) for the legend and
        the hover."""
        self._shown = (entry, dark, names)
        name = entry.boss_name or entry.zone_name or "fight"
        self.setWindowTitle(f"DPS over time – {name}")
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
        group = QListWidgetItem(_line_icon(text_color, False), self._legend_label(
            GROUP, entry.group_boss_dps, entry.group_dps, boss_fight))
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
            item = QListWidgetItem(_line_icon(series_color(rank, dark), rank >= MAX_HUES),
                                   self._legend_label(name, p.get("boss_dps"), p.get("dps"),
                                                      boss_fight))
            item.setData(Qt.UserRole, unit_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            default = rank < MAX_HUES
            item.setCheckState(Qt.Checked if self._checked.get(unit_id, default) else Qt.Unchecked)
            self.legend.addItem(item)
        self.legend.blockSignals(False)

    @staticmethod
    def _legend_label(name: str, boss_dps, dps, boss_fight: bool) -> str:
        figure = _fmt_dps(float(dps or 0))
        if boss_fight:
            figure = f"{_fmt_dps(float(boss_dps or 0))} / {figure}"
        return f"{name}   {figure}"

    def _on_legend_changed(self, item) -> None:
        self._checked[str(item.data(Qt.UserRole))] = item.checkState() == Qt.Checked
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
        duration = float(entry.duration_s or 0)
        mode_window = int(self.mode.currentData() or 0)
        boss = self.boss_only.isChecked()
        checked = set(self.checked_keys())
        curves: List[Curve] = []
        series = getattr(entry, "damage_series", None) or {}
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
            curves.append(Curve(unit_id, name, series_color(rank, dark), points,
                                LINE_WIDTH, rank >= MAX_HUES, PLAYER_PANEL))
        self.graph.set_curves(curves, duration)

    def changeEvent(self, event):
        # A new text size: the legend's names are wider, so is its column
        if event.type() == QEvent.FontChange:
            self.legend.setFixedWidth(scaled_px(LEGEND_WIDTH))
        super().changeEvent(event)

    def refresh(self, dark: bool, names=None) -> None:
        """Re-render for a theme switch (the series colours follow it) or
        a flip of the Hide names switch (*names*, the new mask; None keeps
        the one shown)."""
        if self._shown is not None and self.isVisible():
            entry, _dark, shown = self._shown
            self.show_graph(entry, dark, names=shown if names is None else names)
