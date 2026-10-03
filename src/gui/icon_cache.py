"""
In-memory cache of bundled ability icons for the fight view.

Icons are PNG files under data/icons/abilities, one per game icon stem
(see scripts/extract_ability_icons.py). Each image is read from disk once
and kept as a QImage; a miss is remembered too, so an ability with no bundled
icon costs a single stat() per session and then renders as text.
"""

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtGui import QImage

from ability_icons import icons_dir


class IconCache:

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root is not None else icons_dir()
        self._images: Dict[str, Optional[QImage]] = {}

    def has(self, stem: str) -> bool:
        return self.image(stem) is not None

    def image(self, stem: str) -> Optional[QImage]:
        if not stem:
            return None
        if stem not in self._images:
            path = self.root / f"{stem}.png"
            image = QImage(str(path)) if path.is_file() else QImage()
            self._images[stem] = None if image.isNull() else image
        return self._images[stem]

    def __len__(self) -> int:
        return sum(1 for image in self._images.values() if image is not None)
