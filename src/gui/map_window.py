"""
The map window (issue #148): a fight's maps of where the group stood, large,
opened from a thumbnail in the fight pane's header. One tab per map the
fight touched, in the order the group reached them, and a switch between
the fight's area (the crop the thumbnail shows, map_art.crop_square) and
the whole map. Under the map, its name, the time the group spent on it and,
for a map the app has no art for, the texture path, so it can be added
(scripts/extract_map_art.py). Modeless like the other windows; it keeps the
fight it was opened for, and the whole-map switch from one fight to the
next.

A picture is drawn again when the window is resized, once the size has
settled (RESIZE_SETTLE_MS); until then the last one is scaled to fit.
"""

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout, QWidget,
)

from gui.fight_map import WINDOW_CELLS, has_art, map_image
from gui.fight_render import NO_ART_NOTE, _fmt_duration, map_alt

WHOLE_MAP_LABEL = "Whole map"
RESIZE_SETTLE_MS = 120


class MapCanvas(QWidget):
    """One map's picture, as large as the widget allows, centred."""

    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self.record = record
        self.whole = False
        self._image = None
        self.setMinimumSize(240, 240)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(RESIZE_SETTLE_MS)
        self._settle.timeout.connect(self._redraw)
        self.setAccessibleName(map_alt(record))

    def sizeHint(self):
        return QSize(640, 640)

    def set_whole(self, whole: bool) -> None:
        if bool(whole) != self.whole:
            self.whole = bool(whole)
            self._redraw()

    def _edge(self) -> int:
        return max(1, min(self.width(), self.height()))

    def _redraw(self) -> None:
        self._image = map_image(self.record, self._edge(), self.devicePixelRatioF(),
                                whole=self.whole, cells=WINDOW_CELLS)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._image is None:
            self._redraw()
        else:
            self._settle.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(QPalette.Window))
        if self._image is None:
            self._redraw()
        edge = self._edge()
        target = QRectF((self.width() - edge) / 2, (self.height() - edge) / 2, edge, edge)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawImage(target, self._image)
        painter.end()


class MapDialog(QDialog):
    """The map window: a tab per map, the whole-map switch, and a line
    about the map shown."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fight map")
        self.resize(720, 800)
        self._entry = None
        layout = QVBoxLayout(self)
        self.header = QLabel("")
        self.header.setWordWrap(True)
        layout.addWidget(self.header)
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab)
        layout.addWidget(self.tabs, 1)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        self.note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.note)
        bottom = QHBoxLayout()
        self.whole = QCheckBox(WHOLE_MAP_LABEL)
        self.whole.toggled.connect(self._on_whole)
        bottom.addWidget(self.whole)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        bottom.addWidget(buttons)
        layout.addLayout(bottom)

    @property
    def entry(self):
        """The fight on display, None before the first."""
        return self._entry

    def canvases(self) -> list[MapCanvas]:
        return [self.tabs.widget(i) for i in range(self.tabs.count())]

    def show_maps(self, entry, place: int = 0) -> None:
        """Show the maps of the fight *entry*, at the one at *place* in its
        positions."""
        self._entry = entry
        name = entry.boss_name or entry.zone_name or "fight"
        self.setWindowTitle(f"Fight map – {name}")
        facts = [entry.boss_name or "", entry.zone_name or "", str(entry.timestamp or ""),
                 f"{_fmt_duration(entry.duration_s)} fight"]
        self.header.setText(" · ".join(f for f in facts if f))
        self.tabs.blockSignals(True)
        while self.tabs.count():
            canvas = self.tabs.widget(0)
            self.tabs.removeTab(0)
            canvas.deleteLater()
        maps = list(getattr(entry, "positions", None) or [])
        for n, record in enumerate(maps):
            canvas = MapCanvas(record)
            canvas.set_whole(self.whole.isChecked())
            label = str(record.get("name") or f"Map {n + 1}")
            if len(maps) > 1:
                label = f"{n + 1}. {label}"
            self.tabs.addTab(canvas, label)
        self.tabs.setTabBarAutoHide(len(maps) < 2)
        self.tabs.blockSignals(False)
        if maps:
            self.tabs.setCurrentIndex(min(max(place, 0), len(maps) - 1))
        self._on_tab(self.tabs.currentIndex())

    def _on_tab(self, index: int) -> None:
        if not 0 <= index < self.tabs.count():
            self.note.setText("No positions were logged in this fight.")
            return
        record = self.tabs.widget(index).record
        lines = [(f"{record.get('name') or 'Map'} · the group stood here for "
                  f"{_fmt_duration(float(record.get('seconds') or 0))}")]
        if not has_art(record):
            lines.append(NO_ART_NOTE.format(path=record.get("path", "")))
        self.note.setText("\n".join(lines))

    def _on_whole(self, whole: bool) -> None:
        for canvas in self.canvases():
            canvas.set_whole(whole)
