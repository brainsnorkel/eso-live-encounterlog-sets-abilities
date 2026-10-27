"""
Design: Link glyphs. The fight pane has three kinds of link that are not
ESO-Hub pages: a player's name opens their build window, their dps figure
their damage window, and the header's group dps figure the dps over time
graph. All three are drawn as plain text in the pane's own colours, by
choice: twelve underlined or blue names in a trial fight would be clutter,
and the name is the row's identity. The cost is that nothing says they can
be clicked until the pointer is on them (the hover cue, see
FightView._show_hover_cue), and the two dps figures suffered most: the
group figure sits in the muted stats line where nothing else is clickable,
and the damage window has no other way in at all (issue #34).

So the two figures carry a small glyph inside their anchor, drawn here with
QPainter rather than shipped as a file: after the group figure, a short
polyline in the graph's own line style (about 2 px, round joins) in the
theme's link colour, the one coloured mark in that grey line; after each
player's figure, three bars, longest on top, in the muted colour, since
there are up to twelve of them. Being inside the anchor, a glyph is part
of the click target and of the hover: the view underlines the text beside
it and shows the same tooltip. The glyph follows the pane's font size and
is drawn at the view's device pixel ratio, so it stays crisp on a scaled
display (Qt lays out an image that carries a device pixel ratio at its
logical size). Names stay plain, with their hover cue.

The page asks for a glyph by URL, ``glyph:<kind>?color=rrggbb&px=<n>``
(fight_render.glyph_html), which FightView.loadResource answers from here:
one image per kind, colour, size and ratio, kept for the session.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

from gui.fight_render import BREAKDOWN_GLYPH, GRAPH_GLYPH, TAKEN_GLYPH

KINDS = (GRAPH_GLYPH, BREAKDOWN_GLYPH, TAKEN_GLYPH)

_images: dict[tuple[str, str, int, float], QImage] = {}


def glyph_image(kind: str, color: str, px: int, dpr: float = 1.0) -> QImage | None:
    """The *kind* glyph, *px* logical pixels square, in *color* (a name
    QColor accepts, '#1a73e8'), drawn at device pixel ratio *dpr*; None
    for a kind that does not exist, a size that is not one, or a colour
    that is not one."""
    paint = QColor(color)
    if kind not in KINDS or int(px) <= 0 or not paint.isValid():
        return None
    dpr = max(1.0, float(dpr))
    key = (kind, paint.name(), int(px), dpr)
    if key not in _images:
        _images[key] = _draw(kind, paint, int(px), dpr)
    return _images[key]


def _draw(kind: str, color: QColor, px: int, dpr: float) -> QImage:
    size = max(1, round(px * dpr))
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    image.setDevicePixelRatio(dpr)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    if kind == GRAPH_GLYPH:
        # A stretch of a dps line: two peaks and a trough, the graph's own
        # weight and round joins (see dps_graph)
        painter.setPen(QPen(color, max(1.5, px / 7.0), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        points = [(1.0, px * 0.80), (px * 0.30, px * 0.28), (px * 0.52, px * 0.64),
                  (px * 0.74, px * 0.16), (px - 1.0, px * 0.50)]
        path = QPainterPath(QPointF(*points[0]))
        for x, y in points[1:]:
            path.lineTo(QPointF(x, y))
        painter.drawPath(path)
    elif kind == TAKEN_GLYPH:
        # A shield, for the damage taken window (issue #98): a flat top,
        # straight sides to the middle, then curving to a point at the
        # bottom; an outline only, in the link colour, so it reads as a
        # cue beside the (i) and not as a filled mark like the death chip
        painter.setPen(QPen(color, max(1.5, px / 8.0), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        left, right = px * 0.16, px * 0.84
        top, waist, bottom = px * 0.12, px * 0.50, px * 0.92
        path = QPainterPath(QPointF(left, top))
        path.lineTo(QPointF(right, top))
        path.lineTo(QPointF(right, waist))
        path.quadTo(QPointF(right, px * 0.78), QPointF(px / 2.0, bottom))
        path.quadTo(QPointF(left, px * 0.78), QPointF(left, waist))
        path.closeSubpath()
        painter.drawPath(path)
    else:
        # A breakdown: three bars, the longest on top, as the damage
        # window ranks abilities
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        bar = max(2.0, px / 5.0)
        gap = (px - 3 * bar) / 4.0
        for i, share in enumerate((1.0, 0.62, 0.38)):
            painter.drawRoundedRect(
                QRectF(1.0, gap + i * (bar + gap), (px - 2.0) * share, bar), 1.0, 1.0)
    painter.end()
    return image
