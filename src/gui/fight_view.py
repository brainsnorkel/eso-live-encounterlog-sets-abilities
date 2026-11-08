"""
Fight detail pane: a QTextBrowser that serves the bundled ability icons to the
rendered HTML (``icon:<stem>`` image URLs), shows an ability's name while an
icon is hovered, and opens ESO-Hub links in the system browser.

Links never navigate the document itself: every click is routed through
anchorClicked, and only http(s) targets are opened externally. A click on a
player's death-recap button is announced through death_recap_requested, a
click on a player's name, or on the '?' after a lone Class Mastery,
through build_requested, a click on their dps
figure through damage_requested, a click on the header's group dps figure
through graph_requested, a click on a player's build-issues (i) through
issues_requested, a click on a player's pen/crit token through
pen_crit_requested.

A player's name and dps figure look like plain text (the dps figures carry
a small glyph that says they can be clicked, see gui.glyphs; the names do
not), so the pane shows they can be clicked while the pointer is over them:
the text is underlined in the link color (see _show_hover_cue). The glyphs
are images the page asks for by URL, served by loadResource like the icons,
and so are the pixelated stand-ins the Hide names switch puts in place of
other players' names (``mask:`` URLs, see gui.name_mask).

Design: a screen reader reads a QTextBrowser's text, where every image is
U+FFFC; Qt keeps an image's alt attribute but never reads it out. So the
view gives its accessible description the page's text with each image
replaced by its alt text (an ability icon on a bar says the ability, a
glyph what it opens, a hidden name 'hidden name'; an icon beside its own
name has alt="" and says nothing), rebuilt whenever the page changes
(issue #77). The taunt ring's pulse stops, at its plain phase, while
Reduce motion is on (set_reduce_motion).
"""

import weakref

from contextlib import contextmanager
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QRect, Qt, QTimer, QUrl, QUrlQuery, Signal
from PySide6.QtGui import (
    QColor, QCursor, QDesktopServices, QPalette, QTextCharFormat, QTextCursor,
    QTextDocument, QTextFormat,
)
from PySide6.QtWidgets import QTextBrowser, QTextEdit, QToolTip

from gui.activity_render import activity_action_from_href, review_index_from_href
from gui.death_render import FIGHT_DEATHS_HREF, RECAP_HREF, recap_from_href, unit_from_href
from gui.fight_render import (
    BANNER_HREF, BUILD_HREF, DAMAGE_HREF, GLYPH_SCHEME, GRAPH_HREF, MASTERY_HREF, build_unit_from_href,
    damage_unit_from_href, healing_unit_from_href, issues_unit_from_href, mastery_unit_from_href,
    pen_crit_unit_from_href, taken_unit_from_href,
)
from gui.glyphs import glyph_image
from gui.icon_cache import PULSE_STEPS, IconCache
from gui.instance_render import INSTANCE_COPY_HREF, PLAYER_HREF, fight_from_href, player_from_href
from gui.name_mask import MASK_SCHEME, mask_image, mask_request

ICON_SCHEME = "icon"
_RING_QUERY = "ring"  # icon:<stem>?ring=<rrggbb> asks for the icon ringed in that color
PULSE_INTERVAL_MS = 150  # a glow cycle is PULSE_STEPS of these: about a breath
HOLD_MS = 500  # how long a place put back is held while Qt lays the page out (see __init__)
_ALT_PROPERTY = getattr(QTextFormat.Property, "ImageAltText", 0x5002)  # an <img>'s alt
_reduce_motion = False  # Settings → Display → Reduce motion
_views = weakref.WeakSet()  # every live view, for set_reduce_motion


def set_reduce_motion(on: bool) -> None:
    """Reduce motion on or off for every view: on, a pulsing taunt ring
    stops at its plain phase and no new pulse starts."""
    global _reduce_motion
    _reduce_motion = bool(on)
    if _reduce_motion:
        for view in list(_views):
            view._still()


def reduce_motion() -> bool:
    return _reduce_motion


def _query_color(url: QUrl, key: str) -> str | None:
    """'#rrggbb' when the URL's query gives *key* as six hex digits, else None."""
    value = QUrlQuery(url).queryItemValue(key)
    if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value):
        return f"#{value}"
    return None


def _ring_color(url: QUrl) -> Optional[str]:
    """'#rrggbb' when an icon URL asks for a ring (the fight render marks
    the abilities a player taunted with that way), else None."""
    return _query_color(url, _RING_QUERY)


def _glyph(url: QUrl, dpr: float):
    """The link glyph a glyph:<kind>?color=rrggbb&px=<n> URL asks for (see
    gui.glyphs), drawn at device pixel ratio *dpr*; None for a bad URL."""
    color = _query_color(url, "color")
    try:
        px = int(QUrlQuery(url).queryItemValue("px") or 0)
    except ValueError:
        return None
    if color is None or px <= 0:
        return None
    return glyph_image(url.path(), color, px, dpr)


class FightView(QTextBrowser):

    death_recap_requested = Signal(str)  # unit id of the player who died
    build_requested = Signal(str)  # unit id of the player whose name was clicked
    damage_requested = Signal(str)  # unit id of the player whose dps figure was clicked
    graph_requested = Signal()  # the header's group dps figure was clicked
    fight_deaths_requested = Signal()  # the header's Deaths N: the fight's Deaths tab (issue #196)
    issues_requested = Signal(str)  # unit id of the player whose (i) was clicked
    pen_crit_requested = Signal(str)  # unit id of the player whose pen/crit token was clicked
    taken_requested = Signal(str)  # unit id of the player whose damage-taken shield was clicked
    # unit id of the player whose healing received line was clicked, on their
    # damage taken page (issue #196)
    healing_requested = Signal(str)
    # unit id and number from 1 of one death, in a list of a fight's deaths
    # (issue #196)
    recap_requested = Signal(str, int)
    banner_requested = Signal(str)  # 'open', 'save' or 'copy': the run's score banner (issue #167)
    # The empty pane's links (gui.activity_render, issue #191): 'show' or
    # 'hide' the recent activity; a file's place in it to open for review
    activity_requested = Signal(str)
    review_requested = Signal(int)
    # The Instance page's links (gui.instance_render, issue #196): a pull,
    # by its place in the list the page was drawn from; a player, by the
    # place of the fight to open them on and their unit id there; Copy this
    # instance
    fight_requested = Signal(int)
    player_requested = Signal(int, str)
    instance_copy_requested = Signal()

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
        # Design: Steps after the page is laid out. restore_scroll and
        # open_at_anchor put the page where it should be now, and again in a
        # step on the next pass of the event loop. Qt lays a page out in
        # parts, the first in setHtml and the rest on its timer ticks after
        # that step, and until it is done the bar's range is an estimate
        # from the part laid out, short of the page's or past it. A scroll
        # put back stops at the estimate, so a build window redrawn at or
        # near its end landed up to 92 px short of where it was (97 of 940
        # redraws of real build pages, issue #196). So the place is held for
        # HOLD_MS: each change of the bar's range puts the page there again,
        # until it gets there, and the reader moving the page, with the
        # wheel, a key, the bar, Tab or the in-fight search, ends the hold at
        # once, so the page is never taken back from under them
        # (release_place). The step runs on a single-shot timer the
        # view owns, connected to the view's own method: deleted with the
        # view, the timer never fires at a dead one, and the connection
        # keeps nothing alive. The forms used before,
        # QTimer.singleShot(0, ...) with a bound method (restore_scroll) or
        # with a lambda holding the window (the build window's anchor
        # scroll), raised "Internal C++ object already deleted" when the
        # view was deleted first, and kept the view's Python wrapper, and the
        # lambda the window's too, alive until then;
        # QTimer.singleShot(0, view, method) does not raise but keeps the
        # method, and so the wrapper, alive (all probed on PySide6 6.12.0). A
        # new page drops the step and the hold of the one it replaces. A
        # redraw of the page while the step is to run or the place is held,
        # a second fight update in the same pass say, puts the page where
        # they were to put it, not where its bar is meanwhile (keeping_place).
        self._kept_scroll = 0
        self._kept_anchor = ""
        self._kept_link_top: int | None = None  # where keep_link_at put the Tab link
        self._own_step = False  # keeping_place's Tab step, not the reader's (_focus_link)
        self._key_link: tuple[int, int] | None = None  # what Tab's step selected (_tab_link)
        self._after_layout = QTimer(self)
        self._after_layout.setSingleShot(True)
        self._after_layout.setInterval(0)
        self._after_layout.timeout.connect(self._apply_after_layout)
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.setInterval(HOLD_MS)
        self.verticalScrollBar().rangeChanged.connect(self._on_range_changed)
        self.verticalScrollBar().actionTriggered.connect(self._on_reader_scrolled)
        # The link Enter is activating, on the screen, while its signal is
        # handled (see keyPressEvent)
        self._key_link_rect: QRect | None = None
        # The link Tab had the focus on when the focus last left the page,
        # which Qt drops (see focusOutEvent)
        self._left_link = None
        _views.add(self)
        # What a screen reader is given in place of the images (see above),
        # after a lead line of the window's (set_accessible_lead)
        self._accessible_lead = ""
        self.textChanged.connect(self._update_accessible_text)
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
        # A scroll still to be put back belongs to the page being replaced,
        # and so do the link Tab reached (keeping_place gives it back) and
        # a link to give back (give_link_back)
        self._after_layout.stop()
        self._hold.stop()
        self._key_link = None
        self._left_link = None
        super().setHtml(text)

    def _apply_selections(self) -> None:
        self.setExtraSelections(self._search_selections + self._hover_selections)

    def restore_scroll(self, value: int) -> None:
        """Put the vertical scroll back at *value* after a setHtml that
        redrew the page the reader was looking at (a flip of the Hide names
        switch, a theme change, its fight changing in place): now, in the
        step after layout, and at each change of the bar's range while the
        place is held (see __init__)."""
        self._kept_anchor = ""
        self._kept_link_top = None
        self._kept_scroll = int(value)
        self.verticalScrollBar().setValue(self._kept_scroll)
        self._after_layout.start()
        self._hold.start()

    def open_at_anchor(self, name: str) -> None:
        """Scroll the page just set to the anchor *name* (an <a name> before
        a heading, build_render.PEN_CRIT_ANCHOR say): now, in the step after
        layout, and at each change of the bar's range while the place is
        held (see __init__)."""
        self._kept_anchor = str(name)
        self._kept_link_top = None
        self.scrollToAnchor(self._kept_anchor)
        self._after_layout.start()
        self._hold.start()

    def release_place(self) -> None:
        """The reader has moved the page: the scroll or anchor kept for the
        last redraw is put back no more (see __init__). The wheel, a key or
        the bar end it here on their own (_on_reader_scrolled); Tab
        (focusNextPrevChild) and the in-fight search (MainWindow) move the
        page in ways the bar does not report, so they call this too (issue
        #199). Their move otherwise lasted only until a second redraw
        within HOLD_MS, which took the page back to the place still held."""
        self._after_layout.stop()
        self._hold.stop()

    def focusNextPrevChild(self, forward: bool) -> bool:
        # The reader's Tab or Shift+Tab, to the next link: their place from
        # now on. keeping_place's own step to the link it gives the focus
        # back to is not the reader's (_focus_link)
        if not self._own_step:
            self.release_place()
        moved = super().focusNextPrevChild(forward)
        # The link the step reached, or none when it left the page
        cursor = self.textCursor()
        self._key_link = ((cursor.selectionStart(), cursor.selectionEnd())
                          if cursor.hasSelection() else None)
        return moved

    def mousePressEvent(self, event) -> None:
        # A click is not Tab: the link it selects is no link Tab reached
        # (_tab_link)
        self._key_link = None
        super().mousePressEvent(event)

    def link_top(self) -> int | None:
        """Where the link the reader reached with Tab is on the screen: the
        top of its line, in the viewport's coordinates. None when no link
        has Tab's focus, or the reader has it out of view."""
        if self._tab_link() is None:
            return None
        rect = self.cursorRect(self._selection_start())
        if rect.bottom() < 0 or rect.top() >= self.viewport().height():
            return None
        return rect.top()

    def keep_link_at(self, top: int) -> None:
        """Scroll the page so the link that has Tab's focus is at *top* on
        the screen (a viewport y), the whole of its line in view, and hold
        it there while Qt lays the page out (restore_scroll); nothing when
        no link has Tab's focus. See keeping_place."""
        if self._tab_link() is None:
            return
        rect = self.cursorRect(self._selection_start())
        top = max(0, min(int(top), self.viewport().height() - rect.height()))
        # The cursor rectangle is in the viewport, the bar's value the
        # viewport's offset into the page
        self.restore_scroll(max(0, rect.top() + self.verticalScrollBar().value() - top))
        self._kept_link_top = top

    def _selection_start(self) -> QTextCursor:
        """A cursor at the start of the text cursor's selection."""
        start = QTextCursor(self.textCursor())
        start.setPosition(start.selectionStart())
        return start

    @contextmanager
    def keeping_place(self):
        """Redraw the page the reader is looking at inside the with block,
        and put it back where it was: at the bar's position, or, while the
        step after the last drawing is still to run or its place is held,
        where they were to put it (its scroll or its anchor), since the bar
        is not there yet (see __init__). The with block is given where the
        text cursor was, for the in-fight search to find its place among its
        matches before the page is drawn again (MainWindow._search_place).

        A link the reader had reached with Tab has Tab's focus again, known
        by its href and its place among the page's links with that href (an
        ESO-Hub set link is on every player who wears the set, and a
        player's own links move when the fight ranks them anew), or none
        when the page no longer has it. Selecting it with setTextCursor
        would paint it as selected text, in the palette's highlight, where
        Tab draws a dotted frame round it; so Tab's own step is taken, which
        frames it: from the link before it, selected as Tab selects it, or,
        for the page's first link, from no selection, where Tab starts at
        the page's start. Never from a selection of the character before
        it: QTextCursor widens a selection that crosses into a table over
        the whole table, and a bar's first ability begins a table's first
        cell (the build card's in the pane, its bar's own in the build
        window), so Tab's search went on from the table's end, to the next
        link after it. The step is QTextBrowser.focusNextPrevChild, which
        moves the focus on to the next widget when its search finds no
        link, as it did then with none after the table. It cannot now: the
        step is taken only for a link the page has, with the links reachable
        from the keyboard, and from where that link is the next one the
        search finds, since _links reads the page's links as the search does
        (issue #196).

        A link the reader could see stays where they saw it on the screen
        (keep_link_at), and the page moves under it: a fight ranking its
        player anew moves the link down the page, and Hide names moves it
        too. Kept by the bar's position, the link was often scrolled out of
        sight, its focus frame with it, and Enter opened a link the reader
        could not see (issue #199). A new text size moves it before the page
        is redrawn, so MainWindow.set_text_size notes it first. A link the
        reader has scrolled out of view leaves the page at their scroll, as
        does a page with no link reached."""
        held = self._after_layout.isActive() or self._hold.isActive()
        if held:
            anchor, scroll = self._kept_anchor, self._kept_scroll
        else:
            anchor, scroll = "", self.verticalScrollBar().value()
        link = self._tab_link()
        if link is None:
            top = None
        elif held and self._kept_link_top is not None:
            top = self._kept_link_top  # the bar is not there yet
        else:
            top = self.link_top()
        yield self.textCursor().position()
        if link is not None:
            self._focus_link(*link)
        # After the link, which Tab's step scrolls into view
        if top is not None and self._tab_link() is not None:
            self.keep_link_at(top)
        elif anchor:
            self.open_at_anchor(anchor)
        else:
            self.restore_scroll(scroll)

    def _apply_after_layout(self) -> None:
        """Put the page at its kept scroll or anchor; once it is there, the
        bar's range having grown to let it, the hold ends (see __init__)."""
        bar = self.verticalScrollBar()
        if self._kept_anchor:
            self.scrollToAnchor(self._kept_anchor)
            # Hidden, the view only notes the anchor for its showEvent
            there = self.isVisible() and bar.value() < bar.maximum()
        else:
            bar.setValue(self._kept_scroll)
            there = bar.value() == self._kept_scroll
        if there:
            self._hold.stop()

    def _on_range_changed(self, _minimum, _maximum) -> None:
        # Qt has laid more of the page out (see __init__)
        if self._hold.isActive():
            self._apply_after_layout()

    def _on_reader_scrolled(self, _action) -> None:
        # The wheel, a key or the bar itself: the reader's place from now on
        self.release_place()

    def _links(self):
        """(href, start, end) of each link on the page, in document order,
        read as Tab's search reads them (QWidgetTextControl's
        findNextPrevAnchor), so the two agree on the links Tab reaches: a
        link starts at a fragment, text or image, that is an anchor with an
        href, and runs on, within its paragraph, over the fragments that are
        anchors to that href."""
        block = self.document().begin()
        while block.isValid():
            run = None  # [href, start, end] of the link being read
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                fmt = fragment.charFormat()
                end = fragment.position() + fragment.length()
                if run is not None and fmt.isAnchor() and fmt.anchorHref() == run[0]:
                    run[2] = end
                else:
                    if run is not None:
                        yield tuple(run)
                    # Tab's search starts a link at an anchor that has an
                    # href, even an empty one; an <a name> alone has none
                    run = ([fmt.anchorHref(), fragment.position(), end]
                           if fmt.isAnchor() and fmt.hasProperty(QTextFormat.AnchorHref) else None)
                it += 1
            if run is not None:
                yield tuple(run)
            block = block.next()

    def _tab_link(self):
        """The link Tab has the focus on, as (href, its place among the
        page's links with that href); None when no link is selected, or a
        click selected it.

        Qt selects a link clicked with the mouse as Tab selects one, framed
        the same way, and the selection stays when the window the click
        opens takes the focus. Taken for a link the reader reached with Tab,
        a clicked name was kept where it was on the screen when the fight
        ranked its players anew, and the pane scrolled down the page after
        it, 815 px in the review's probe, where v0.34.1 stayed at the top
        (issue #202). So only the selection Tab's own step made counts
        (focusNextPrevChild), the reader's Tab and Shift+Tab or
        keeping_place's, until a click or a new page."""
        cursor = self.textCursor()
        if not (cursor.hasSelection()
                and self.textInteractionFlags() & Qt.LinksAccessibleByKeyboard):
            return None
        place = (cursor.selectionStart(), cursor.selectionEnd())
        if place != self._key_link:
            return None
        seen = {}  # the links so far to each href
        for href, start, end in self._links():
            if (start, end) == place:
                return href, seen.get(href, 0)
            seen[href] = seen.get(href, 0) + 1
        return None

    def _focus_link(self, href: str, n: int) -> None:
        """Give Tab's focus to the page's link *n* (from 0) of those to
        *href*, as Tab gives it: Tab's step taken from the link before it,
        selected over its run as Tab selects it, or, for the page's first
        link, from no selection, where Tab starts at the page's start (see
        keeping_place); nothing when the page has fewer."""
        links = list(self._links())
        places = [i for i, (link, _start, _end) in enumerate(links) if link == href]
        if n >= len(places):
            return
        before = QTextCursor(self.document())
        if places[n]:
            _link, start, end = links[places[n] - 1]
            before.setPosition(start)
            before.setPosition(end, QTextCursor.KeepAnchor)
        self.setTextCursor(before)
        self._own_step = True
        try:
            self.focusNextPrevChild(True)
        finally:
            self._own_step = False

    def focusOutEvent(self, event) -> None:
        """Qt drops the link Tab has the focus on when the focus leaves the
        page, unless it leaves for another window or a popup; so it does as
        a tab widget hides the page. The link is kept here first, for the
        page's window to give back when the tab is shown again
        (give_link_back, issue #196)."""
        if event.reason() not in (Qt.ActiveWindowFocusReason, Qt.PopupFocusReason):
            self._left_link = self._tab_link()
        super().focusOutEvent(event)

    def give_link_back(self) -> None:
        """Give Tab's focus back to the link it had when the focus last left
        the page, the page staying where it is, which Tab's step would
        scroll to the link; nothing when there was none, when the page has
        a selection again, or when it was drawn anew since (setHtml). A
        redraw that keeps the page's place (keeping_place) keeps the link."""
        link, self._left_link = self._left_link, None
        if link is None or self.textCursor().hasSelection():
            return
        bar = self.verticalScrollBar()
        scroll = bar.value()
        self._focus_link(*link)
        bar.setValue(scroll)

    def keyPressEvent(self, event) -> None:
        """Enter on a link the reader moved to with Tab activates it inside
        this call: Qt emits anchorClicked from the key press. While that is
        handled, keyboard_link_rect says where the link is, so what it opens
        can open beside it rather than at the pointer, which may be anywhere
        (issue #196)."""
        cursor = self.textCursor()
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and cursor.hasSelection():
            # The cursor at the link's start: its left edge, its line. The
            # one at its end is on the next line when the link ends a
            # wrapped line
            start = QTextCursor(cursor)
            start.setPosition(cursor.selectionStart())
            rect = self.cursorRect(start)
            self._key_link_rect = QRect(self.viewport().mapToGlobal(rect.topLeft()), rect.size())
        try:
            super().keyPressEvent(event)
        finally:
            self._key_link_rect = None

    def keyboard_link_rect(self) -> QRect | None:
        """Where the link Enter is activating starts, as a rectangle on the
        screen (the text cursor's there: the link's left edge, the height of
        its line), while the link's signal is handled; None when a click
        activated it."""
        return self._key_link_rect

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
        # Not the space that joins a dps figure to its glyph (fight_render
        # puts an &nbsp; between them so they wrap together)
        while end > start + 1 and document.characterAt(end - 1).isspace():
            end -= 1
        cursor = QTextCursor(document)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        return cursor

    def _show_hover_cue(self, href: str) -> None:
        """Design: the hover cue. Underline the hovered player name or dps
        figure in the link color; any other target, or none, clears the cue.

        A name or dps figure keeps the look of plain text in the page (the
        figures carry a glyph beside them, see gui.glyphs; the names do not,
        since twelve underlined or blue names would be clutter). Qt rich text
        has no hover styling, and changing the document's own character
        format on hover would enter the undo stack, relayout the page and
        invalidate the cursors the in-fight search holds. So the cue is an
        extra selection: a format painted over a text range without touching
        the document. The search's highlights are extra selections too, and
        setting one list replaces the other, so the view owns both lists and
        applies their union. The selection covers the anchor's text and stops
        at its glyph, which is an image fragment of the same anchor; the
        glyph still triggers the cue and the tooltip, since the pointer on it
        is the pointer on the anchor.
        """
        selections = []
        if href.startswith((BUILD_HREF, DAMAGE_HREF, GRAPH_HREF, MASTERY_HREF, RECAP_HREF,
                            FIGHT_DEATHS_HREF, PLAYER_HREF)):
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
                    if not self._pulse.isActive() and not _reduce_motion:
                        self._pulse.start()
                return image
        if resource_type == QTextDocument.ImageResource and name.scheme() == GLYPH_SCHEME:
            image = _glyph(name, self.devicePixelRatioF())
            if image is not None:
                return image
        if resource_type == QTextDocument.ImageResource and name.scheme() == MASK_SCHEME:
            # A hidden player name: the pixelated stand-in (gui.name_mask)
            # in this view's font family and at its device pixel ratio
            request = mask_request(name)
            if request is not None:
                image = mask_image(*request, self.font(), self.devicePixelRatioF())
                if image is not None:
                    return image
        return super().loadResource(resource_type, name)

    def set_accessible_lead(self, text: str) -> None:
        """A line a screen reader hears before the page (accessible_text):
        the fight, on the player window's pages, whose header names it
        outside the page (issue #196)."""
        self._accessible_lead = str(text or "")
        self._update_accessible_text()

    def accessible_text(self) -> str:
        """The page as a screen reader should hear it: its text, each
        image replaced by its alt text, one line per paragraph or cell,
        after the lead line when there is one (set_accessible_lead)."""
        lines = [self._accessible_lead] if self._accessible_lead else []
        block = self.document().begin()
        while block.isValid():
            pieces = []
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                fmt = fragment.charFormat()
                if fmt.isImageFormat():
                    alt = fmt.property(_ALT_PROPERTY)
                    if alt:
                        pieces.append(f" {alt} ")
                else:
                    pieces.append(fragment.text().replace("\ufffc", ""))
                it += 1
            line = " ".join("".join(pieces).split())
            if line:
                lines.append(line)
            block = block.next()
        return "\n".join(lines)

    def _update_accessible_text(self) -> None:
        self.setAccessibleDescription(self.accessible_text())

    def _still(self) -> None:
        """Stop the pulse with every ringed icon at its plain phase."""
        self._pulse.stop()
        if self._pulse_phase:
            self._pulse_phase = 0
            document = self.document()
            for url in self._ring_urls.values():
                image = self.icons.image(url.path(), ring=_ring_color(url), phase=0.0)
                if image is not None:
                    document.addResource(QTextDocument.ImageResource, url, image)
            self.viewport().update()

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
        if url.toString().startswith(BANNER_HREF):
            self.banner_requested.emit(url.toString()[len(BANNER_HREF):])
            return
        action = activity_action_from_href(url.toString())
        if action is not None:
            self.activity_requested.emit(action)
            return
        index = review_index_from_href(url.toString())
        if index is not None:
            self.review_requested.emit(index)
            return
        index = fight_from_href(url.toString())
        if index is not None:
            self.fight_requested.emit(index)
            return
        player = player_from_href(url.toString())
        if player is not None:
            self.player_requested.emit(*player)
            return
        if url.toString() == INSTANCE_COPY_HREF:
            self.instance_copy_requested.emit()
            return
        unit_id = build_unit_from_href(url.toString())
        if unit_id is None:
            unit_id = mastery_unit_from_href(url.toString())
        if unit_id is not None:
            self.build_requested.emit(unit_id)
            return
        unit_id = damage_unit_from_href(url.toString())
        if unit_id is not None:
            self.damage_requested.emit(unit_id)
            return
        if url.toString() == GRAPH_HREF:
            self.graph_requested.emit()
            return
        if url.toString() == FIGHT_DEATHS_HREF:
            self.fight_deaths_requested.emit()
            return
        unit_id = issues_unit_from_href(url.toString())
        if unit_id is not None:
            self.issues_requested.emit(unit_id)
            return
        unit_id = pen_crit_unit_from_href(url.toString())
        if unit_id is not None:
            self.pen_crit_requested.emit(unit_id)
            return
        unit_id = taken_unit_from_href(url.toString())
        if unit_id is not None:
            self.taken_requested.emit(unit_id)
            return
        unit_id = healing_unit_from_href(url.toString())
        if unit_id is not None:
            self.healing_requested.emit(unit_id)
            return
        death = recap_from_href(url.toString())
        if death is not None:
            self.recap_requested.emit(*death)
            return
        unit_id = unit_from_href(url.toString())
        if unit_id is not None:
            self.death_recap_requested.emit(unit_id)
