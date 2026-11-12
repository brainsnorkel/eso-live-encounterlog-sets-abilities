"""
The fight's tabs (issue #196): the main window's right column, under the
review banner, as tabs on the fight selected in the list, with the search
in the tab bar's corner.

Design: The fight tabs. The list's fight is shown on tabs: Fight, the buff
timeline strip and the fight pane as they were; Deaths, every death of the
fight on one page (fight_deaths_render); Events, the fight's notable
events as a table (events_tab, issue #214); the DPS graph (dps_graph); and
Instance, the instance the fight belongs to, its block of the list
(instance_render). The tabs show the fight the list has selected, so this
level cannot go stale, where the player window keeps the fight it was
opened for. The tab chosen stays when the fight
changes, new live fights included, and is not kept from one run of the app
to the next. The Alt letters are the labels' mnemonics; Ctrl+PgDn and
Ctrl+PgUp change the tab from anywhere in the window, the list included.

The search sits in the tab bar's corner, so the Fight page keeps its
height: a row of its own cost the pane 30 px. It searches the page on
screen, and its count follows that page. The count is drawn inside the
field, at its right end, before the clear button: beside the field, as it
was, it clipped the tab labels at 190-200% text (probed with the window's
own text). The field takes the width the bar leaves, at most about forty
characters (260 px at 100% in Segoe UI). When the bar leaves less than the
widest count ('999+ matches') and about six characters, at a large text
size in a narrow column or in a wide font (at 200% in Segoe UI the five
tabs' labels need 517 px of the 705 a 1080 px window gives the column,
leaving 188 where the field needs 267), the corner holds a Find button
instead (issue #214; the maintainer's decision: "the search field shrinks to a
button at large text, so no page loses 48 px"). The button, or Ctrl+F, shows the
field on a row of its own above the tabs while the search is in use; Esc
on the empty field, or leaving it empty, hides the row and gives the
button back, with the focus after Esc. A search with text keeps its row,
and its count, until it is cleared. When the field took that row whenever
the corner was short, every page lost the row's height for as long as the
window was narrow. The field is placed again as the column's width, the
text size or the tabs change, so the bar is never narrower than its labels
and the button together, and none hides behind Qt's scroll arrows; a
search in use, or the field with the focus, goes on on its row as the
corner shrinks.

With no fight to show (the page before the first fight, a Settings
replay), the Fight tab is on screen and the bar and the field (or the
button) are hidden together: hiding the bar alone left the field a control 0 px tall that took
the focus, and Ctrl+PgDn still switched the pages (probed on PySide6
6.12.0). The window's Ctrl+F, Ctrl+PgDn and Ctrl+PgUp do nothing then, and
the hidden bar's Alt letters do not fire, until a fight brings back the tab
chosen.
"""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStyle,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

TABS_NAME = "Fight views"
SEARCH_PLACEHOLDER = "Find (Ctrl+F)"
FIND_LABEL = "Find"
FIND_NAME = "Find (Ctrl+F)"  # the Find button's accessible name and hover text
SEARCH_NAME = "Search this tab"
SEARCH_HINTS = ("Enter goes to the next match and Esc clears the search; ability icons "
                "match by their names.")
MOST_COUNTED = 999  # a count past it reads '999+ matches'
WIDEST_COUNT = f"{MOST_COUNTED}+ matches"
LEAST_CHARS = 6  # the room the field keeps for the search's text beside the widest count
MOST_CHARS = 40  # the widest the field goes in the corner: 260 px at 100% in Segoe UI


def count_text(matches: int) -> str:
    """The search's count: '1 match', '12 matches', and '999+ matches'
    past that, the widest the field keeps room for."""
    if matches > MOST_COUNTED:
        return WIDEST_COUNT
    return f"{matches} match{'es' if matches != 1 else ''}"


class SearchField(QLineEdit):
    """The search field, with the search's count drawn inside it at its
    right end (see the module notes)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(SEARCH_PLACEHOLDER)
        self.setToolTip(SEARCH_HINTS)
        self.setAccessibleName(SEARCH_NAME)
        self.setAccessibleDescription(SEARCH_HINTS)
        self.setClearButtonEnabled(True)
        # The count, a label inside the field that clicks pass through, in
        # the placeholder's muted colour
        self.count_label = QLabel(self)
        self.count_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.count_label.setForegroundRole(QPalette.PlaceholderText)
        self.count_label.hide()
        self._hint_width = None  # the width the corner gives the field, when there

    def set_count(self, text: str) -> None:
        """Show the search's count, '' for none; a screen reader is given it
        before the hints."""
        self.count_label.setText(text)
        self.count_label.setVisible(bool(text))
        self.setAccessibleDescription(f"{text}. {SEARCH_HINTS}" if text else SEARCH_HINTS)
        self._lay_out_count()

    def least_width(self) -> int:
        """The narrowest the field goes in the corner: the widest count and
        about six characters, beside the clear button, inside the frame."""
        metrics = self.fontMetrics()
        style = self.style()
        # Qt's room for a side button: its icon, 6 px about it and a margin
        # (QLineEditPrivate::sideWidgetParameters)
        button = (style.pixelMetric(QStyle.PM_LineEditIconSize, None, self) + 6
                  + style.pixelMetric(QStyle.PM_LineEditIconMargin, None, self))
        frame = 2 * (style.pixelMetric(QStyle.PM_DefaultFrameWidth, None, self) + 2)
        return (metrics.horizontalAdvance(WIDEST_COUNT) + self._gap()
                + LEAST_CHARS * metrics.averageCharWidth() + button + frame)

    def most_width(self) -> int:
        """The widest the field goes in the corner."""
        return MOST_CHARS * self.fontMetrics().averageCharWidth()

    def set_hint_width(self, width) -> None:
        """The width the field asks for: the corner's share (a tab widget
        sizes its corner by the widget's hint), None for its own."""
        if width != self._hint_width:
            self._hint_width = width
            self.updateGeometry()

    def sizeHint(self):
        hint = super().sizeHint()
        if self._hint_width is not None:
            hint.setWidth(self._hint_width)
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        if self._hint_width is not None:
            hint.setWidth(min(hint.width(), self._hint_width))
        return hint

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)  # places the clear button
        self._lay_out_count()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange, QEvent.StyleChange):
            self._lay_out_count()

    def _gap(self) -> int:
        return max(2, self.fontMetrics().averageCharWidth() // 2)

    def _lay_out_count(self) -> None:
        """The count before the clear button, and the typed text kept clear
        of it by the field's right text margin: the widest count's while
        any count shows, set only when that changes. A new text margin lays
        the field out again, and in the tab bar's corner the tab widget
        with it, which repainted its pages, the buff timeline strip among
        them, at every key typed: 46 ms a key on a 22-minute fight, against
        1.2 ms before (the fresh review of PR #205)."""
        label = self.count_label
        gap = self._gap()
        margin = self.fontMetrics().horizontalAdvance(WIDEST_COUNT) + gap if label.text() else 0
        if self.textMargins().right() != margin:
            self.setTextMargins(0, 0, margin, 0)
        if not label.text():
            return
        label.adjustSize()
        # Qt's clear button, a tool button child at the field's right end
        button = self.findChild(QToolButton)
        right = (button.geometry().left() if button is not None and button.width() > 0
                 else self.contentsRect().right())
        label.move(max(0, right - gap - label.width()), (self.height() - label.height()) // 2)


class FightViews(QWidget):
    """The right column under the review banner: the search's own row,
    empty while the search is in the tab bar's corner and while the Find
    button there stands for it, then the tabs (see the module notes)."""

    # The search moved between the corner and its own row: the window sets
    # its Tab order again
    search_placed = Signal()
    # The Find button pressed: the window opens the search as Ctrl+F does
    find_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._row = QHBoxLayout()
        self._row.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._row)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setAccessibleName(TABS_NAME)
        # No Tab stop of its own: the bar, its focus proxy, is one, and the
        # tab widget's place in the focus chain, after its pages, sent Tab
        # from the page back to the bar, so the focus never left the tabs
        # for the fight list (probed on PySide6 6.12.0)
        self.tabs.setFocusProxy(None)
        self.tabs.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.tabs, 1)
        self.search_field = SearchField()
        self._row.addWidget(self.search_field)
        # The corner's stand-in for the field at a large text size
        self.find_button = QToolButton(self.tabs)
        self.find_button.setText(FIND_LABEL)
        self.find_button.setAccessibleName(FIND_NAME)
        self.find_button.setToolTip(FIND_NAME)
        self.find_button.hide()
        self.find_button.clicked.connect(self._on_find_clicked)
        # Esc clears the search; on the empty field on its own row, it hides
        # the row (escape_search)
        QShortcut(QKeySequence(Qt.Key_Escape), self.search_field, activated=self.escape_search,
                  context=Qt.WidgetShortcut)
        self.search_field.installEventFilter(self)
        # A search given text is in use: out on its row if the corner is short
        self.search_field.textChanged.connect(self._on_text_changed)
        self._shown = True
        self._bar_width = 0  # the bar's width when the column's least was last set
        # The corner too short for the field: the button there, and whether
        # the field is out on its own row (open_search)
        self._compact = False
        self._open = False
        self._placing = False  # the field being moved: its focus-out is no leaving
        # The tab widget's own Ctrl+Tab and Ctrl+Shift+Tab, from a page,
        # change the tab with the bar hidden too: without a fight, the first
        # tab is put back (the fresh review of PR #205)
        self.tabs.currentChanged.connect(self._keep_first_tab)

    def add_tab(self, page, label: str) -> int:
        """Add a tab, the search placed again for the bar's new width."""
        index = self.tabs.addTab(page, label)
        self.place_search()
        return index

    def is_shown(self) -> bool:
        """Whether the bar and the search are shown: there is a fight."""
        return self._shown

    def set_shown(self, shown: bool) -> None:
        """The bar and the search shown with a fight; without one, hidden
        together, the first tab on screen (see the module notes)."""
        if bool(shown) != self._shown:
            self.updateGeometry()  # the least width follows the bar (minimumSizeHint)
        self._shown = bool(shown)
        if not self._shown:
            self.tabs.setCurrentIndex(0)
            if not self.search_field.text():
                self._open = False  # an empty search out on its row is not in use
        self.tabs.tabBar().setVisible(self._shown)
        self.place_search()

    def _keep_first_tab(self, index: int) -> None:
        if not self._shown and index != 0:
            self.tabs.setCurrentIndex(0)

    def minimumSizeHint(self):
        """Never narrower than the tab bar's labels and the Find button
        need, as the player window's least width is its tab bar's: in a
        narrower column Qt scrolls the labels (three need 552 px at 200%
        text in the test runner's font)."""
        hint = super().minimumSizeHint()
        if self._shown:  # a hidden bar draws no labels to keep whole
            hint.setWidth(max(hint.width(), self.tabs.tabBar().sizeHint().width()
                              + self.find_button.sizeHint().width()))
        return hint

    def in_corner(self) -> bool:
        """Whether the field is in the tab bar's corner."""
        return self.tabs.cornerWidget(Qt.TopRightCorner) is self.search_field

    def is_compact(self) -> bool:
        """Whether the corner holds the Find button, too short for the field."""
        return self._compact

    def search_open(self) -> bool:
        """Whether the field is out on its own row, the corner too short."""
        return self._compact and self._open

    def place_search(self) -> None:
        """The search in the tab bar's corner, as wide as the bar leaves it
        up to its most, when that is at least its least; else the Find
        button there, and the field on its own row while it is in use (see
        the module notes)."""
        field = self.search_field
        bar = self.tabs.tabBar().sizeHint().width()
        if bar != self._bar_width:
            # The labels' width changed (a tab, a text size): so has the least
            self._bar_width = bar
            self.updateGeometry()
        room = self.width() - bar
        # A new parent takes the focus from the field: it is given back, so
        # typing goes on through a new text size or a resize
        had_focus = field is self.window().focusWidget()
        moved = False
        self._placing = True
        try:
            if room >= field.least_width():
                field.set_hint_width(min(room, field.most_width()))
                self._compact = self._open = False
                if not self.in_corner():
                    self._row.removeWidget(field)
                    # The button, the corner's widget before, is hidden by it
                    self.tabs.setCornerWidget(field, Qt.TopRightCorner)
                    moved = True
            else:
                field.set_hint_width(None)
                if not self._compact:
                    # A search in use goes on on its row; else the button
                    self._compact = True
                    self._open = had_focus or bool(field.text())
                if self.in_corner():
                    self.tabs.setCornerWidget(None, Qt.TopRightCorner)
                    self._row.addWidget(field)
                    moved = True
                if self.tabs.cornerWidget(Qt.TopRightCorner) is not self.find_button:
                    self.tabs.setCornerWidget(self.find_button, Qt.TopRightCorner)
                    moved = True
            # A new parent hides a widget; the field and the button show
            # with the bar
            self._show_parts()
            if moved:
                if had_focus and self._shown and field.isVisible():
                    field.setFocus()
                self.search_placed.emit()
        finally:
            self._placing = False

    def _show_parts(self) -> None:
        """The field in the corner, or on its row while it is out; the
        button while the corner holds it and the field is not out."""
        self.search_field.setVisible(self._shown and (not self._compact or self._open))
        self.find_button.setVisible(self._shown and self._compact and not self._open)

    def _on_find_clicked(self, *_) -> None:
        self.find_requested.emit()

    def _on_text_changed(self, text: str) -> None:
        if text:
            self.open_search()

    def open_search(self) -> None:
        """Ctrl+F or the Find button: with the button in the corner, the
        field out on its own row; the window then gives it the focus."""
        if self._compact and not self._open:
            self._open = True
            self._show_parts()

    def escape_search(self) -> None:
        """Esc in the field: the search cleared; on the empty field out on
        its row, the row hidden and the focus given to the button."""
        if self.search_field.text():
            self.search_field.clear()
        elif self.search_open():
            self._close_search(focus=True)

    def _close_search(self, focus: bool) -> None:
        self._open = False
        if focus and self._shown:
            self.find_button.show()
            self.find_button.setFocus(Qt.OtherFocusReason)
        self._show_parts()

    def eventFilter(self, watched, event) -> bool:
        """The empty field out on its row left for another control (not for
        another window or a popup): the row is hidden, the button back."""
        if (watched is self.search_field and event.type() == QEvent.FocusOut
                and not self._placing and self.search_open() and not self.search_field.text()
                and event.reason() not in (Qt.ActiveWindowFocusReason, Qt.PopupFocusReason)):
            self._close_search(focus=False)
        return False

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.place_search()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        # A new text size changes the labels' width and the field's least
        if event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange, QEvent.StyleChange):
            self.place_search()
