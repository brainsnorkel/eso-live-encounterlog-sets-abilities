"""
In-memory cache of bundled ability icons for the fight view.

Icons are PNG files under data/icons/abilities, one per game icon stem
(see scripts/extract_ability_icons.py). Each image is read from disk once
and kept as a QImage; a miss is remembered too, so an ability with no bundled
icon costs a single stat() per session and then renders as text. An icon can
also be had with a colored ring drawn inside its edge (the fight view marks
the abilities a player taunted with that way); each ring color is drawn once
per icon.
"""

import math
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from ability_icons import icons_dir


PULSE_STEPS = 8  # ring images per colour over one glow cycle (see FightView)


def ringed(image: QImage, color: QColor, phase: float = 0.0) -> QImage:
    """A copy of *image* with a ring of *color* just inside its edge: about
    an eighth of the icon wide (5 px on the bundled 40 px icons), a dark
    hairline outside it so it reads on any icon art, and a light hairline
    inside. *phase*, 0 to 1 around one glow cycle, brightens the ring from
    the colour itself (0) to a paler, lighter tone (0.5) and back, which the
    fight view steps through to make a taunt mark pulse (issue #12)."""
    framed = image.convertToFormat(QImage.Format_ARGB32)
    edge = min(framed.width(), framed.height())
    width = max(3, round(edge / 8))
    glow = 0.5 * (1 - math.cos(2 * math.pi * phase))  # 0 at phase 0, 1 at 0.5
    ring = QColor(color).lighter(100 + round(55 * glow))
    painter = QPainter(framed)
    painter.setRenderHint(QPainter.Antialiasing, False)
    # The coloured ring, starting one pixel in
    pen = QPen(ring)
    pen.setWidth(width)
    pen.setJoinStyle(Qt.MiterJoin)
    painter.setPen(pen)
    half = width / 2
    painter.drawRect(QRectF(1 + half, 1 + half, framed.width() - 2 - width, framed.height() - 2 - width))
    # Dark hairline on the very edge, light hairline on the ring's inner side
    for inset, line in ((0, QColor(0, 0, 0, 170)),
                        (1 + width, QColor(255, 255, 255, 120 + round(100 * glow)))):
        pen = QPen(line)
        pen.setWidth(1)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.drawRect(QRectF(inset + 0.5, inset + 0.5,
                                framed.width() - 2 * inset - 1, framed.height() - 2 * inset - 1))
    painter.end()
    return framed


class IconCache:

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root is not None else icons_dir()
        self._images: Dict[str, Optional[QImage]] = {}
        self._ringed: Dict[Tuple[str, str, int], QImage] = {}

    def has(self, stem: str) -> bool:
        return self.image(stem) is not None

    def image(self, stem: str, ring: Optional[str] = None,
              phase: float = 0.0) -> Optional[QImage]:
        """The icon for *stem*, None when there is none; with *ring*, a color
        name QColor accepts ('#9575cd'), the icon ringed in that color, at
        *phase* of the glow cycle (quantised to PULSE_STEPS images)."""
        if not stem:
            return None
        if stem not in self._images:
            path = self.root / f"{stem}.png"
            image = QImage(str(path)) if path.is_file() else QImage()
            self._images[stem] = None if image.isNull() else image
        image = self._images[stem]
        if image is None or not ring:
            return image
        step = round(phase * PULSE_STEPS) % PULSE_STEPS
        key = (stem, ring, step)
        if key not in self._ringed:
            self._ringed[key] = ringed(image, QColor(ring), step / PULSE_STEPS)
        return self._ringed[key]

    def __len__(self) -> int:
        return sum(1 for image in self._images.values() if image is not None)
