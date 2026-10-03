"""
Fight detail pane: a QTextBrowser that serves the bundled ability icons to the
rendered HTML (``icon:<stem>`` image URLs), shows an ability's name while an
icon is hovered, and opens ESO-Hub links in the system browser.

Links never navigate the document itself: every click is routed through
anchorClicked, and only http(s) targets are opened externally. A click on a
player's death-recap button is announced through death_recap_requested.
"""

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QCursor, QDesktopServices, QTextCursor, QTextDocument
from PySide6.QtWidgets import QTextBrowser, QToolTip

from gui.death_render import unit_from_href
from gui.icon_cache import IconCache

ICON_SCHEME = "icon"


class FightView(QTextBrowser):

    death_recap_requested = Signal(str)  # unit id of the player who died

    def __init__(self, parent=None, icons: Optional[IconCache] = None,
                 open_external: Optional[Callable[[QUrl], bool]] = None):
        super().__init__(parent)
        self.icons = icons if icons is not None else IconCache()
        self._open_external = open_external or QDesktopServices.openUrl
        self._tooltips: Dict[str, str] = {}
        self._anchor_names: Dict[str, str] = {}
        self.current_tooltip = ""  # text shown for the hovered anchor, "" when none
        # Never load a clicked link into the pane; anchorClicked still fires
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.highlighted.connect(self._on_highlighted)
        self.anchorClicked.connect(self._on_anchor_clicked)

    def set_tooltips(self, tooltips: Dict[str, str]) -> None:
        """Hover text per anchor href (as rendered by fight_render)."""
        self._tooltips = dict(tooltips or {})

    def set_anchor_names(self, names: Dict[str, str]) -> None:
        """Plain ability name per anchor href, so searches can match icons."""
        self._anchor_names = dict(names or {})

    def anchor_matches(self, text: str) -> List[QTextCursor]:
        """A cursor selecting each icon whose ability name contains *text*
        (case-insensitive), in document order.

        Only image anchors are considered: a slot rendered as text is found
        by QTextDocument.find like any other text, so it is not duplicated.
        """
        needle = (text or "").casefold()
        matches: List[QTextCursor] = []
        if not needle or not self._anchor_names:
            return matches
        document = self.document()
        block = document.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                fmt = fragment.charFormat()
                if fmt.isImageFormat() and fmt.isAnchor():
                    name = self._anchor_names.get(fmt.anchorHref(), "")
                    if needle in name.casefold():
                        cursor = QTextCursor(document)
                        cursor.setPosition(fragment.position())
                        cursor.setPosition(fragment.position() + fragment.length(),
                                           QTextCursor.KeepAnchor)
                        matches.append(cursor)
                it += 1
            block = block.next()
        return matches

    def loadResource(self, resource_type, name: QUrl):
        if resource_type == QTextDocument.ImageResource and name.scheme() == ICON_SCHEME:
            image = self.icons.image(name.path())
            if image is not None:
                return image
        return super().loadResource(resource_type, name)

    def _on_highlighted(self, url) -> None:
        key = url.toString() if isinstance(url, QUrl) else str(url)
        text = self._tooltips.get(key) if key else None
        self.current_tooltip = text or ""
        if text:
            QToolTip.showText(QCursor.pos(), text, self)
        else:
            QToolTip.hideText()

    def _on_anchor_clicked(self, url: QUrl) -> None:
        if url.scheme() in ("http", "https"):
            self._open_external(url)
            return
        unit_id = unit_from_href(url.toString())
        if unit_id is not None:
            self.death_recap_requested.emit(unit_id)
