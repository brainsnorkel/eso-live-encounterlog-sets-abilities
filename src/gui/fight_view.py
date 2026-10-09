"""
Fight detail pane: a QTextBrowser that serves the bundled ability icons to the
rendered HTML (``icon:<stem>`` image URLs), shows an ability's name while an
icon is hovered, and opens ESO-Hub links in the system browser.

Links never navigate the document itself: every click is routed through
anchorClicked, and only http(s) targets are opened externally. A click on a
player's death-recap button is announced through death_recap_requested, a
click on a player's name through build_requested.

A player's name looks like plain text, so the pane shows it can be clicked
while the pointer is over it: the name is underlined in the link color. Qt
rich text has no hover styling, so this is an extra selection, which restyles
text at paint time without touching the document. The in-fight search's
highlights are extra selections too, and setting one list replaces the
other; the pane therefore holds both and applies them together.
"""

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QTimer, QUrl, QUrlQuery, Signal
from PySide6.QtGui import (
    QColor, QCursor, QDesktopServices, QPalette, QTextCharFormat, QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import QTextBrowser, QTextEdit, QToolTip

from gui.death_render import unit_from_href
from gui.fight_render import BUILD_HREF, build_unit_from_href
from gui.icon_cache import PULSE_STEPS, IconCache

ICON_SCHEME = "icon"
_RING_QUERY = "ring"  # icon:<stem>?ring=<rrggbb> asks for the icon ringed in that color
PULSE_INTERVAL_MS = 150  # a glow cycle is PULSE_STEPS of these: about a breath


def _ring_color(url: QUrl) -> Optional[str]:
    """'#rrggbb' when an icon URL asks for a ring (the fight render marks
    the abilities a player taunted with that way), else None."""
    value = QUrlQuery(url).queryItemValue(_RING_QUERY)
    if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value):
        return f"#{value}"
    return None


class FightView(QTextBrowser):

    death_recap_requested = Signal(str)  # unit id of the player who died
    build_requested = Signal(str)  # unit id of the player whose name was clicked

    def __init__(self, parent=None, icons: Optional[IconCache] = None,
                 open_external: Optional[Callable[[QUrl], bool]] = None):
        super().__init__(parent)
        self.icons = icons if icons is not None else IconCache()
        self._open_external = open_external or QDesktopServices.openUrl
        self._tooltips: Dict[str, str] = {}
        self._anchor_names: Dict[str, str] = {}
        self.current_tooltip = ""  # text shown for the hovered anchor, "" when none
        self.hovered_build_link = ""  # href of the name carrying the hover cue
        self._search_selections: List[QTextEdit.ExtraSelection] = []
        self._hover_selections: List[QTextEdit.ExtraSelection] = []
        self._link_hover_color: Optional[QColor] = None
        # Taunt marks pulse: the ringed icons on the page are redrawn at the
        # next glow phase on a timer (see _pulse_step)
        self._ring_urls: Dict[str, QUrl] = {}
        self._pulse_phase = 0
        self._pulse = QTimer(self)
        self._pulse.setInterval(PULSE_INTERVAL_MS)
        self._pulse.timeout.connect(self._pulse_step)
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

    def set_link_hover_color(self, color) -> None:
        """Color of a hovered player name (the theme's link color); the
        palette's link color when never set."""
        self._link_hover_color = QColor(color) if color else None

    def set_search_selections(self, selections) -> None:
        """The in-fight search's highlights. They are applied together with
        the hover cue: use this rather than setExtraSelections."""
        self._search_selections = list(selections or [])
        self._apply_selections()

    def setHtml(self, text: str) -> None:
        # Selections point into the document being replaced
        self._search_selections = []
        self._hover_selections = []
        self.hovered_build_link = ""
        self.setExtraSelections([])
        # The new page asks for its ringed icons afresh (loadResource)
        self._ring_urls = {}
        self._pulse_phase = 0
        self._pulse.stop()
        super().setHtml(text)

    def _apply_selections(self) -> None:
        self.setExtraSelections(self._search_selections + self._hover_selections)

    def _text_anchor_cursor(self, href: str) -> Optional[QTextCursor]:
        """A cursor selecting the text of the anchor that leads to *href*
        (its first run in the document), None when there is none."""
        document = self.document()
        start = end = None
        block = document.begin()
        while block.isValid() and start is None:
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                fmt = fragment.charFormat()
                if (fmt.isAnchor() and not fmt.isImageFormat()
                        and fmt.anchorHref() == href):
                    if start is None:
                        start = fragment.position()
                    end = fragment.position() + fragment.length()
                elif start is not None:
                    break  # past the anchor's text
                it += 1
            block = block.next()
        if start is None:
            return None
        cursor = QTextCursor(document)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        return cursor

    def _show_hover_cue(self, href: str) -> None:
        """Underline the hovered player name in the link color; any other
        target, or none, clears the cue."""
        selections = []
        if href.startswith(BUILD_HREF):
            cursor = self._text_anchor_cursor(href)
            if cursor is not None:
                cue = QTextCharFormat()
                cue.setFontUnderline(True)
                cue.setForeground(self._link_hover_color
                                  or self.palette().color(QPalette.Link))
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format = cue
                selections.append(selection)
        self.hovered_build_link = href if selections else ""
        if selections or self._hover_selections:
            self._hover_selections = selections
            self._apply_selections()

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
            ring = _ring_color(name)
            image = self.icons.image(name.path(), ring=ring)
            if image is not None:
                if ring:
                    self._ring_urls[name.toString()] = QUrl(name)
                    if not self._pulse.isActive():
                        self._pulse.start()
                return image
        return super().loadResource(resource_type, name)

    def _pulse_step(self) -> None:
        """Design: Taunt marks pulse. A QTextBrowser page cannot animate, but
        the document asks for an image's resource each time it paints, and
        one set with addResource is taken before loadResource is asked. So
        every ringed icon the page has loaded is redrawn at the next phase
        of the glow (IconCache keeps PULSE_STEPS images per ring colour) and
        the viewport repainted: a few small images and a repaint every
        PULSE_INTERVAL_MS, no layout, so the page never moves. The timer
        runs only while the page holds a ringed icon and the view is shown.
        """
        if not self._ring_urls:
            self._pulse.stop()
            return
        if not self.isVisible():
            return
        self._pulse_phase = (self._pulse_phase + 1) % PULSE_STEPS
        document = self.document()
        for url in self._ring_urls.values():
            image = self.icons.image(url.path(), ring=_ring_color(url),
                                     phase=self._pulse_phase / PULSE_STEPS)
            if image is not None:
                document.addResource(QTextDocument.ImageResource, url, image)
        self.viewport().update()

    def _on_highlighted(self, url) -> None:
        key = url.toString() if isinstance(url, QUrl) else str(url)
        text = self._tooltips.get(key) if key else None
        self.current_tooltip = text or ""
        if text:
            QToolTip.showText(QCursor.pos(), text, self)
        else:
            QToolTip.hideText()
        self._show_hover_cue(key)

    def _on_anchor_clicked(self, url: QUrl) -> None:
        if url.scheme() in ("http", "https"):
            self._open_external(url)
            return
        unit_id = build_unit_from_href(url.toString())
        if unit_id is not None:
            self.build_requested.emit(unit_id)
            return
        unit_id = unit_from_href(url.toString())
        if unit_id is not None:
            self.death_recap_requested.emit(unit_id)
