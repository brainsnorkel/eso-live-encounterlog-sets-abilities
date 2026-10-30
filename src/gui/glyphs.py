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

The (i) of possible build issues is drawn here too (issue #140). It was the
font's ⓘ in the link colour after the class text, where it drifted right
with the text's length, thin and among muted words, and was easy to miss;
the first-damage * after the name was the mark people saw. It now sits on
the name, after the *, bold with a faint halo of its own colour. Qt rich
text has no text-shadow, filter or opacity, so the glow cannot come from
the page: the glyph is a ring about the size of the font's ⓘ (11.5 px of
11 at 9 pt), half again as heavy, over a radial gradient that is clear
inside the ring, about two fifths opaque at its outer edge and nothing at
the image's edge; the clear inside keeps the i at the link colour's full
contrast (issue #77). The image is as tall as the text line, so the halo
has 2 to 3 px around the ring, and aligned to the line's top: Qt centres
a middle-aligned image on half the x-height above the baseline, which
pushed a line-tall image 2 px under the line and made each marked row
taller. The page estimates the line from its point size, and the view
holds the image to its own font's line height (FightView, _glyph) for a
font whose line is shorter. At 100% scaling the ring's inside is 8 px
tall, and a dot and stem placed freely ran together into a bar touching
the ring, so the i is laid out in whole device pixels: a 2 px dot, a clear
pixel, a 3 px stem, and a clear pixel above and below. No
pulse: a still mark, so Reduce motion has nothing to stop. The fight
list's ⓘ is list text, which cannot be bold or glow without a delegate,
and the popup is a label that cannot serve these images; the build window
shows the popup's list, so all three keep the font's ⓘ.

The page asks for a glyph by URL, ``glyph:<kind>?color=rrggbb&px=<n>``
(fight_render.glyph_html), which FightView.loadResource answers from here:
one image per kind, colour, size and ratio, kept for the session.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QRadialGradient

from gui.fight_render import BREAKDOWN_GLYPH, GRAPH_GLYPH, ISSUES_GLYPH, TAKEN_GLYPH

KINDS = (GRAPH_GLYPH, BREAKDOWN_GLYPH, TAKEN_GLYPH, ISSUES_GLYPH)

# The build-issues mark: its ring's outer edge as a share of the image's
# edge (11.5 px of 16 at 9 pt, about the font's own ⓘ), and the halo's
# opacity just outside the ring, fading to nothing at the image's edge
ISSUES_RING = 0.36
ISSUES_HALO_ALPHA = 0.38

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
    elif kind == ISSUES_GLYPH:
        _draw_issues(painter, color, px, dpr)
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


def _draw_issues(painter: QPainter, color: QColor, px: int, dpr: float) -> None:
    """The build-issues (i): a ring and an i, both heavier than the font's
    ⓘ, over a halo of the same colour that fades out from the ring to the
    image's edge. The ring's inside stays clear, so the i keeps the full
    contrast of the link colour on the pane."""
    centre = px / 2.0
    stroke = max(1.5, px / 10.0)
    outer = px * ISSUES_RING
    ring = outer - stroke / 2.0
    # The halo: clear inside the ring, strongest at its outer edge, then a
    # soft fall to nothing (a third of the way out it is under half)
    halo = QRadialGradient(QPointF(centre, centre), centre)
    glow = QColor(color)
    for at, alpha in ((0.0, 0.0), ((ring - stroke / 2.0) / centre, 0.0),
                      (outer / centre, ISSUES_HALO_ALPHA),
                      ((outer + (centre - outer) * 0.35) / centre, ISSUES_HALO_ALPHA * 0.45),
                      (1.0, 0.0)):
        glow.setAlphaF(alpha)
        halo.setColorAt(min(1.0, at), glow)
    painter.setPen(Qt.NoPen)
    painter.setBrush(halo)
    painter.drawEllipse(QPointF(centre, centre), centre, centre)
    # The ring
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(color, stroke))
    painter.drawEllipse(QPointF(centre, centre), ring, ring)
    # The i: a dot over a stem, laid out in whole device pixels so it stays
    # crisp at 100% scaling, where the ring's inside is only 8 px tall and
    # a dot and stem placed freely run together into one bar. The stem's
    # width has the parity of the image's, so it sits on the ring's centre
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    edge = px * dpr
    middle = edge / 2.0
    inner = (ring - stroke / 2.0) * dpr
    raw = stroke * 1.1 * dpr
    width = max(1, round(raw))
    if abs(edge - round(edge)) < 1e-6 and (width - round(edge)) % 2:
        width = max(1, width + (1 if raw > width else -1))
    left = middle - width / 2.0
    dot_top = round(middle - inner * 0.75)
    stem_top = dot_top + width + max(1, round(inner * 0.2))
    stem_bottom = max(stem_top + width, round(middle + inner * 0.78))
    painter.drawRoundedRect(QRectF(left / dpr, dot_top / dpr, width / dpr, width / dpr),
                            width * 0.35 / dpr, width * 0.35 / dpr)
    painter.drawRect(QRectF(left / dpr, stem_top / dpr, width / dpr,
                            (stem_bottom - stem_top) / dpr))
