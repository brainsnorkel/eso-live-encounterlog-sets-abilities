"""
Instance art: a strip of a trial's or an arena's loading-screen painting on
its block's header in the fight list and above the Instance tab's heading.

Design: instance art in the window (issue #249). The request was for a
very faint backdrop of the instance's art behind the fight list, to give
the window some of the game's look. That was drawn in the real window, in
both themes, over real sessions (2026-11-21) and not built, for what the
pictures and the measurements showed:

- The list's own cues are faint. The Windows 11 style marks the selected
  fight with a fill 3.5 L* from the list's background in the light theme
  and 5.5 L* in the dark, and a 3 px bar; the block band (gui.fight_list)
  is 6.3 and 6.8 L* from it. A painting needs about 12% opacity to read as
  a picture at all, and at 12% its own lightness varies by 6 to 8 L* across
  the list (the 5th to 95th percentile, median of twelve paintings): more
  than the selection's fill, which it drowned. At 6% it read as a dirty
  panel. The text was never the problem: its contrast stayed above 13:1
  in the light theme and 7:1 in the dark at 20%.
- The list is a portrait slot and the paintings are landscapes: at the
  default window size it showed 35% of a painting's width, and nobody
  could have named the instance from that.
- A session holds several instances, so one backdrop sat behind the rows
  of the others; and most paintings are dark, which faded towards a white
  background is grey haze.

So the art has a slot of its own, at full colour, where no fight's text
is:

- A block's header row in the fight list. The row is header_height tall
  (44 px at the usual text size, against a row's 30 in the Windows 11
  style), its title where it always was, on the block's own ground (the
  band's colour or the list's); the art runs from ART_GAP px after the
  title to the list's right edge and fades in from that ground over the
  first ART_FADE of its width. With less than MIN_ART_WIDTH px for it the
  row keeps its height and shows none. A header can be clicked (it opens
  the Instance tab), and a picture on it says so better than the pointer
  alone did.
- The Instance tab: STRIP_HEIGHT px of the same painting across the page,
  above its heading, where a landscape has room and the page is about
  nothing else. It is painted under the page (FightView.set_art) in the
  room the page leaves for it (STRIP_SPACE), not put in the page as an
  image: an image as wide as the page made the page scroll sideways when
  its scroll bar came, and had to be made again at every width.

Both are cut from one bundled picture per instance, a band across the
whole painting seven times as wide as it is high
(scripts/extract_instance_art.py, data/art/instances/<zone id>.jpg), by
covering the slot: scaled until it fills the slot and cut evenly at the
two sides or at top and bottom (cover_source). The art is found by the
zone id the log gives (ZONE_CHANGED) and by nothing else. A zone with no
file has no art, so a trial the game adds, a dungeon, a house or the open
world shows the header it always had and no strip, with nothing reserved
for one: only trials and arenas have a file (the maintainer's choice).

Settings → Display → Instance art turns both off (display.instance_art,
on by default: an install with no such setting saved has the art, a new
one and one updated from a version before it alike), and so does a system
set to high contrast, where a picture behind a title's row is what the
setting asks to be spared; the window follows the system's setting while
it is open (MainWindow._follow_instance_art).
"""

import math
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainterPath,
)

from ability_icons import instance_art_dir

# A header row with art: this many lines of its font high, and never less
# than a row and HEADER_EXTRA px (44 px either way at the usual text size:
# the header's bold line is 16 px, a Windows 11 style row 30)
HEADER_LINES = 2.75
HEADER_EXTRA = 14
# Between the header's title and its art, px; the part of the art's width
# over which it fades in; the least width worth drawing
ART_GAP = 18
ART_FADE = 0.45
MIN_ART_WIDTH = 120
# The Instance tab's strip: its height, the gap under it, its corners
STRIP_HEIGHT = 120
STRIP_GAP = 6
STRIP_SPACE = STRIP_HEIGHT + STRIP_GAP
STRIP_RADIUS = 4
# Fitted pictures kept: a header or two per block on screen and the strip,
# at the sizes of a splitter being dragged; and the bytes they may hold
# together. The count alone let a window being resized with the Instance
# tab on screen keep 48 strips of its every width, about 100 MB at 1900 px
# and a pixel ratio of 1.5 (the review of PR #258); a cut and a scale take
# under a millisecond, so little is lost by keeping few
FITTED_KEPT = 48
FITTED_BYTES = 8 * 1024 * 1024

_setting = True  # Settings → Display → Instance art
_cache = None


def art_dir() -> Path:
    return instance_art_dir()


def set_enabled(on: bool) -> bool:
    """The Instance art setting; whether that changed it."""
    global _setting
    changed = _setting != bool(on)
    _setting = bool(on)
    return changed


def high_contrast() -> bool:
    """Whether the system asks for high contrast (Qt 6.10 and later tell;
    an older Qt is taken not to)."""
    try:
        preference = QGuiApplication.styleHints().accessibility().contrastPreference()
        return preference == Qt.ContrastPreference.HighContrast
    except (AttributeError, RuntimeError):
        return False


def enabled() -> bool:
    """Whether art is drawn at all: the setting on and no high contrast."""
    return _setting and not high_contrast()


def cover_source(size: QSize, width: float, height: float) -> QRectF:
    """The part of a picture of *size* that covers a slot *width* by
    *height*: as much of the picture as has the slot's shape, from its
    middle."""
    if size.isEmpty() or width <= 0 or height <= 0:
        return QRectF()
    scale = max(width / size.width(), height / size.height())
    part = QRectF(0, 0, min(size.width(), width / scale), min(size.height(), height / scale))
    part.moveCenter(QRectF(0, 0, size.width(), size.height()).center())
    return part


class ArtCache:
    """The bundled art, each picture read once, and the last few cut and
    scaled to a slot: at most FITTED_KEPT of them and FITTED_BYTES in all,
    the newest always. A zone with no picture is remembered too."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else art_dir()
        self._images: dict[str, QImage | None] = {}
        self._fitted: OrderedDict = OrderedDict()
        self._fitted_bytes = 0

    def image(self, zone_id) -> QImage | None:
        """The art of *zone_id* as bundled; None when there is none. Only a
        number names a file: the zone id is the log's."""
        key = str(zone_id or "")
        if not key.isdigit():
            return None
        if key not in self._images:
            path = self.root / f"{key}.jpg"
            image = QImage(str(path)) if path.is_file() else QImage()
            self._images[key] = None if image.isNull() else image
        return self._images[key]

    def fitted(self, zone_id, width: int, height: int, dpr: float = 1.0) -> QImage | None:
        """The art of *zone_id* covering a slot *width* by *height* px, at
        device pixel ratio *dpr*; None when there is none or no slot."""
        image = self.image(zone_id)
        if image is None or width <= 0 or height <= 0:
            return None
        key = (str(zone_id), int(width), int(height), round(dpr * 100))
        fitted = self._fitted.get(key)
        if fitted is None:
            part = cover_source(image.size(), width, height).toRect()
            fitted = image.copy(part).scaled(
                max(1, round(width * dpr)), max(1, round(height * dpr)),
                Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            fitted.setDevicePixelRatio(dpr)
            self._fitted[key] = fitted
            self._fitted_bytes += fitted.sizeInBytes()
            while len(self._fitted) > 1 and (len(self._fitted) > FITTED_KEPT
                                             or self._fitted_bytes > FITTED_BYTES):
                _oldest, dropped = self._fitted.popitem(last=False)
                self._fitted_bytes -= dropped.sizeInBytes()
        else:
            self._fitted.move_to_end(key)
        return fitted


def cache() -> ArtCache:
    global _cache
    if _cache is None:
        _cache = ArtCache()
    return _cache


def zone_with_art(zone_id) -> str:
    """*zone_id* as text when its art is to be drawn (enabled, and the zone
    has a picture), else ''."""
    zone = str(zone_id or "")
    return zone if enabled() and cache().image(zone) is not None else ""


def header_height(row_height: int, line_height: int) -> int:
    """A header row's height with art, from a plain row's and its font's
    line height (see the module)."""
    return max(row_height + HEADER_EXTRA, round(line_height * HEADER_LINES))


def paint_header_art(painter, zone: str, left: int, row: QRect, ground: QColor) -> bool:
    """The art of *zone* on a header row *row*, from *left* to the row's
    right edge, fading in from *ground*; False, and nothing drawn, when the
    room is under MIN_ART_WIDTH or the zone has no art."""
    width = row.right() + 1 - left
    if width < MIN_ART_WIDTH:
        return False
    fitted = cache().fitted(zone, width, row.height(), painter.device().devicePixelRatioF())
    if fitted is None:
        return False
    painter.drawImage(QPoint(left, row.top()), fitted)
    fade_width = math.ceil(width * ART_FADE)
    clear = QColor(ground)
    clear.setAlpha(0)
    fade = QLinearGradient(left, 0, left + fade_width, 0)
    fade.setColorAt(0.0, ground)
    fade.setColorAt(1.0, clear)
    painter.fillRect(QRect(left, row.top(), fade_width, row.height()), QBrush(fade))
    return True


def paint_strip(painter, zone: str, rect: QRect) -> bool:
    """The art of *zone* covering *rect*, its corners rounded: the Instance
    tab's strip. False when the zone has no art or *rect* no room."""
    fitted = cache().fitted(zone, rect.width(), rect.height(),
                            painter.device().devicePixelRatioF())
    if fitted is None:
        return False
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(rect), STRIP_RADIUS, STRIP_RADIUS)
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    painter.setClipPath(shape)
    painter.drawImage(rect.topLeft(), fitted)
    painter.restore()
    return True
