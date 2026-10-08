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

from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from ability_icons import icons_dir


def ringed(image: QImage, color: QColor) -> QImage:
    """A copy of *image* with a ring of *color* just inside its edge, about
    a twelfth of the icon wide (3 px on the bundled 40 px icons)."""
    framed = image.convertToFormat(QImage.Format_ARGB32)
    width = max(2, round(min(framed.width(), framed.height()) / 12))
    painter = QPainter(framed)
    pen = QPen(color)
    pen.setWidth(width)
    pen.setJoinStyle(Qt.MiterJoin)
    painter.setPen(pen)
    half = width / 2
    painter.drawRect(QRectF(half, half, framed.width() - width, framed.height() - width))
    painter.end()
    return framed


class IconCache:

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root is not None else icons_dir()
        self._images: Dict[str, Optional[QImage]] = {}
        self._ringed: Dict[Tuple[str, str], QImage] = {}

    def has(self, stem: str) -> bool:
        return self.image(stem) is not None

    def image(self, stem: str, ring: Optional[str] = None) -> Optional[QImage]:
        """The icon for *stem*, None when there is none; with *ring*, a color
        name QColor accepts ('#9575cd'), the icon ringed in that color."""
        if not stem:
            return None
        if stem not in self._images:
            path = self.root / f"{stem}.png"
            image = QImage(str(path)) if path.is_file() else QImage()
            self._images[stem] = None if image.isNull() else image
        image = self._images[stem]
        if image is None or not ring:
            return image
        key = (stem, ring)
        if key not in self._ringed:
            self._ringed[key] = ringed(image, QColor(ring))
        return self._ringed[key]

    def __len__(self) -> int:
        return sum(1 for image in self._images.values() if image is not None)
