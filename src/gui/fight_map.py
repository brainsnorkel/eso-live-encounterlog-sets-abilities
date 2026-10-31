"""
The fight's map pictures (issue #148): the game's map art, cropped to where
the fight was (map_art.crop_square) or whole, with the heat of where the
group stood drawn over it and the hottest area outlined. The fight pane's
header asks for them as ``map:<n>?px=<edge>`` images (gui.fight_view), and
the map window (gui.map_window) draws them at its own size.

Design: the heat's colours. The ramp is one hue, blue, from a light,
mostly clear tint where the group spent little time to a dark, nearly
solid one where it spent the most, so the amount reads as lightness, which
every kind of colour vision sees (issue #77), and blue keeps apart from the
map art's tans and browns for the red-green dichromacies as well as for
normal vision. The hottest area's outline is a dark line on a white one,
which shows on the light art and on the dark heat alike. The pictures do
not change with the theme: the frame is a mid grey that stands on both.

A map the app has no art for (overland, or content newer than the
bundle) is drawn as a plain grid at every twentieth of the map, in the
crop's place, with the heat on it; the hover and the window name the
texture path, so the map can be added (scripts/extract_map_art.py).
"""

from collections import OrderedDict

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from map_art import FLOOR, art_path, contour_segments, crop_square, heat_grid, points

THUMB_CELLS = 64  # the heat grid of a header thumbnail
WINDOW_CELLS = 128  # ... and of the map window's picture
GRID_STEP = 0.05  # the plain grid's spacing, as a share of the map
LIGHT = (198, 219, 239)  # the ramp's light end: little time here
DARK = (8, 48, 107)  # its dark end: the most time
ALPHA_LOW, ALPHA_HIGH = 0.35, 0.9
FRAME = QColor(128, 128, 128)
PLAIN_BACKGROUND = QColor(226, 222, 212)
PLAIN_LINES = QColor(160, 156, 146)
OUTLINE_HALO = QColor(255, 255, 255, 230)
OUTLINE = QColor(*DARK)
_CACHE_SIZE = 24

_art_cache: "OrderedDict[str, QImage]" = OrderedDict()
_heat_cache: "OrderedDict[tuple, tuple]" = OrderedDict()
_image_cache: "OrderedDict[tuple, tuple]" = OrderedDict()


def _remember(cache: OrderedDict, key, value) -> None:
    cache[key] = value
    while len(cache) > _CACHE_SIZE:
        cache.popitem(last=False)


def _recall(cache: OrderedDict, key, record):
    """A cached value made from *record*, None when there is none (a key
    holds the record's id, so the value keeps the record to be sure)."""
    hit = cache.get(key)
    if hit is None or hit[0] is not record:
        return None
    cache.move_to_end(key)
    return hit[1]


def has_art(record: dict) -> bool:
    return art_path(record.get("path", "")) is not None


def _art(path: str):
    """The bundled art of the map at texture *path*, None without one."""
    image = _art_cache.get(path)
    if image is None:
        file = art_path(path)
        if file is None:
            return None
        image = QImage(str(file))
        if image.isNull():
            return None
        _art_cache[path] = image
        while len(_art_cache) > 8:
            _art_cache.popitem(last=False)
    else:
        _art_cache.move_to_end(path)
    return image


def heat_color(value: float) -> QColor:
    """The ramp's colour for a cell at *value* of the hottest (0 to 1)."""
    t = max(0.0, min(1.0, value)) ** 0.7
    r, g, b = (round(lo + (hi - lo) * t) for lo, hi in zip(LIGHT, DARK))
    color = QColor(r, g, b)
    color.setAlphaF(ALPHA_LOW + (ALPHA_HIGH - ALPHA_LOW) * t)
    return color


def _heat_image(grid) -> QImage:
    cells = len(grid)
    image = QImage(cells, cells, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    for j, row in enumerate(grid):
        for i, value in enumerate(row):
            if value >= FLOOR:
                image.setPixelColor(i, j, heat_color(value))
    return image


def _plain_grid(painter: QPainter, target: QRectF, crop) -> None:
    """The stand-in for missing art: lines at every GRID_STEP of the map."""
    x0, y0, side = crop
    painter.fillRect(target, PLAIN_BACKGROUND)
    painter.setPen(QPen(PLAIN_LINES, 1))
    step = GRID_STEP
    k = int(x0 / step) + 1
    while k * step < x0 + side:
        x = target.left() + (k * step - x0) / side * target.width()
        painter.drawLine(QLineF(x, target.top(), x, target.bottom()))
        k += 1
    k = int(y0 / step) + 1
    while k * step < y0 + side:
        y = target.top() + (k * step - y0) / side * target.height()
        painter.drawLine(QLineF(target.left(), y, target.right(), y))
        k += 1


def heat_layer(record: dict, whole: bool = False, cells: int = THUMB_CELLS):
    """(crop, heat image, outline segments) of a map of a fight: the crop
    (left, top, side) as fractions of the map, the heat as a *cells*-square
    image, and the outline in cell units; the heat None when there are no
    samples. Cached, since it does not depend on the picture's size."""
    key = (id(record), len(record.get("xy") or ()), bool(whole), int(cells))
    layer = _recall(_heat_cache, key, record)
    if layer is None:
        pts = points(record.get("xy") or ())
        crop = (0.0, 0.0, 1.0) if whole else crop_square(pts)
        heat, segments = None, []
        if pts:
            grid = heat_grid(pts, crop, cells)
            heat, segments = _heat_image(grid), contour_segments(grid)
        layer = (crop, heat, segments)
        _remember(_heat_cache, key, (record, layer))
    return layer


def map_image(record: dict, edge_px: int, dpr: float = 1.0, whole: bool = False,
              cells: int = THUMB_CELLS) -> QImage:
    """The picture of one map of a fight (a FightHistoryEntry.positions
    dict), *edge_px* logical pixels square at device pixel ratio *dpr*: the
    fight's crop, or the whole map when *whole*. Cached."""
    key = (id(record), len(record.get("xy") or ()), int(edge_px), round(float(dpr), 2),
           bool(whole), int(cells))
    cached = _recall(_image_cache, key, record)
    if cached is not None:
        return cached
    crop, heat, segments = heat_layer(record, whole, cells)
    size = max(1, round(edge_px * dpr))
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    target = QRectF(0, 0, size, size)
    art = _art(record.get("path", ""))
    if art is not None:
        x0, y0, side = crop
        source = QRectF(x0 * art.width(), y0 * art.height(), side * art.width(), side * art.height())
        painter.drawImage(target, art, source)
    else:
        _plain_grid(painter, target, crop)
    if heat is not None:
        painter.drawImage(target, heat)
        scale = size / cells
        lines = [QLineF(a[0] * scale, a[1] * scale, b[0] * scale, b[1] * scale)
                 for a, b in segments]
        if lines:
            painter.setPen(QPen(OUTLINE_HALO, 2.5 * dpr, Qt.SolidLine, Qt.RoundCap))
            painter.drawLines(lines)
            painter.setPen(QPen(OUTLINE, 1.2 * dpr, Qt.SolidLine, Qt.RoundCap))
            painter.drawLines(lines)
    painter.setPen(QPen(FRAME, max(1.0, dpr)))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(target.adjusted(0.5, 0.5, -0.5, -0.5))
    painter.end()
    image.setDevicePixelRatio(dpr)
    _remember(_image_cache, key, (record, image))
    return image
