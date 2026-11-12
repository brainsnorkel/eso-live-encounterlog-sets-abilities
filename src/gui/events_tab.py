"""
The Events tab (issue #214): the fight selected in the list told as a
table of its notable events, one row per happening in time order (the rows
are event_rows'), with a line that sums it up, the categories to show and
the search of the fight's tabs filtering the rows. The main window's fifth
fight tab, after Deaths.

Design: the Events tab. A table, not a page of rich text like Deaths: a
QTableView over a model reads to a screen reader as rows and cells, the
arrow keys go from row to row, and Enter or a double-click on a death's row
opens that death's recap in the player window (recap_requested, the
(unit id, number) the Deaths tab's names carry). A row of several deaths
(Died x3) opens nothing: it names no one death.

What is shown. The five categories the study chose are on at first
(event_rows.DEFAULT_CATEGORIES: deaths, the bosses, the big hits, the
taunt swaps, the phases), and More holds the three that are off
(event_rows.MORE: a boss's casts at the player holding its taunt, its
auto-attacks, the hits of 30 to 49% of a player's health), which on a
145-second Kyne's Aegis boss fight add 51 rows to its 78. Show picks the
whole fight or its last 60 seconds, where a wipe's story ends. The
choices carry from one fight to the next, as the DPS graph's do, and not
from one run of the app to the next.

The search. The tab bar's search filters the rows to those whose cells
hold its text, case-insensitive, over what the cells show (a hidden name
is its blocks, so a hidden player is not found by name); the field counts
the rows, and Enter goes to the next of them. A table has no text cursor
to move to a match, and a row that matches is shown whole. A search typed
selects its first row, as the text pages put the cursor on the first
match; cleared, the row selected stays and comes into view among the
others.

Around a moment. Show's ± choices keep the rows within 10 or 30 seconds
of a moment: the row selected when the choice is made, named in the count
beside it. The moment stays as the reader picks other rows, so the window
does not slide under them, and from ±10 s to ±30 s; it belongs to its
fight, and another fight goes back to the whole. It is how the other views
open the tab (show_around): a double-click on the DPS graph, the buff
strip's pop-up and a death's Events link in the player window each send
their moment, where the study had a double-click on the strip too: a click
there already opens the pop-up, so the pop-up carries the link. The other
way, Ctrl+G or the link that ends the line under the table marks the row's
moment on the DPS graph (graph_requested), with what happened and no name,
so the mark needs no mask.

Keeping the reader's place. A new fight selects its first death, the
moment a wipe turns on, else its first row. The same fight drawn again (it
changed: a death logged after combat ended, the fight the game had cut in
two going on, Hide names, the text size, the theme) is drawn in place: the
row selected is found again by what it says, its time, what and ability,
not by its place, since rows can come before it, and the scroll is kept.
A category or Show changed keeps the row selected while it is shown, else
takes the first row from its time on.

Hide names. Cells are plain text, so a hidden name is '@' and a block per
character, as in hover text and the DPS graph's legend
(NameMask.text_in): in Who, which can name two players or say '3
players', and in Detail, which names who raised, interrupted or was aimed
at. A screen reader hears 'hidden name' (Qt.AccessibleTextRole), as in the
positions window's table.

Sizes. The rows are as tall as a line of text or an ability icon at the
text size in force (death_render.ICON_PX scaled): a QTableView keeps its
30 px rows at any text size (the positions window measured it). The
filter bar wraps its controls onto more lines as the column narrows (a
flow layout), so at 200% text the tab never sets the column's least width:
its controls take 1,185 px on one line at 200% in Segoe UI (666 at 100%),
where a 1080 px window gives the tabs 705. The Time and What columns are
as wide as the fight's widest cell, Ability and Who too up to a share of
the table, and Detail takes the rest: at 200% text in that column, Detail
had a quarter of the table while Ability and Who took their whole cells. A
cut cell is whole in its hover, and the row selected is whole on the line
under the table, as the study's design has it.

Design: one player's actions on the Events tab (issue #214). Who, first on
the bar, picks Everyone (the rows above) or one of the fight's player
rows (action_rows.players: tanks, healers, then damage dealers, each in
the table's order; companions' casts are not kept), and the table lists
that player's casts with the events that touched them (action_rows has
the rules). It lives here rather than on an eighth tab of the player
window, the maintainer's choice: that window has no search and would need
more than its width at 200% text. The table takes the mode's columns
(ACTION_COLUMNS: Time, Bar, LA, Action, Target, Length, Gap, Detail) and
is named Player actions for a screen reader; a column no row of the
player's fills is hidden (HIDEABLE), judged on all their rows rather than
the ones the filters leave, so columns do not come and go as boxes are
ticked.

The controls keep their meaning for one player. The casts are always
shown; Deaths, Boss, Big hits and Taunt swaps show or hide the player's
events of that kind; Phases is greyed out, its rows (the map, combat begun
again, the trial's end) being context rows (action_rows._context_rows),
which More's Context switch shows with the bosses' health and deaths. More's three kinds are everyone's and greyed
out for one player, and the player's switches (ACTION_SWITCHES: light
attacks as rows, swaps as rows, context) are greyed out for everyone; the
count on More is of the items on that apply. Context rows are italic in
the palette's placeholder colour, the fight around the player rather than
the player's own. Show, the search, the line under the table, Ctrl+G and
Enter on a death's row work on the player's rows as on everyone's. The
marks are words to a screen reader and on the line under the table ('after
a weapon swap', 'after a light attack'), whose two seconds are labelled
('lasted 1.6 s', '1.1 s after the skill before'), as they would read
alike there.

Who changed keeps the reader's moment: the other mode's rows from the
selected row's time on. The player picked carries to the next fight as
the DPS graph's legend ticks do, by legend_key (the handle, or an
anonymous player's zone and unit id): a fight without them shows everyone,
and the next fight with them picks them again. A jump from another view
keeps the mode, but a death's Events link for another player than the one
picked goes back to everyone, whose rows hold that death. The player
window's This player's actions button selects its fight in the list and
opens the tab on the player (show_player), at their first death, else
their first row.
"""

from collections import namedtuple
from html import escape

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QItemSelectionModel,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QFont,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPalette,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QMenu,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import action_rows
import event_rows
from event_rows import CATEGORIES, DEFAULT_CATEGORIES, MORE, clock
from gui.death_render import ICON_PX
from gui.dps_graph import legend_key
from gui.fight_render import link_color
from gui.icon_cache import IconCache
from gui.name_mask import NO_MASK
from gui.text_size import scaled_px

PAGE_NAME = "Events"
TABLE_NAME = "Fight events"
TABLE_HINT = "Enter or a double-click on a death's row opens that death's recap."
COLUMNS = ("Time", "What", "Ability", "Who", "Detail")
TIME_COL, WHAT_COL, ABILITY_COL, WHO_COL, DETAIL_COL = range(len(COLUMNS))
# One player's actions (Who a player): their own columns
ACTION_COLUMNS = ("Time", "Bar", "LA", "Action", "Target", "Length", "Gap", "Detail")
(A_TIME_COL, A_BAR_COL, A_LA_COL, A_ACTION_COL, A_TARGET_COL, A_LENGTH_COL, A_GAP_COL,
 A_DETAIL_COL) = range(len(ACTION_COLUMNS))
# The columns hidden when no row of the player's has anything in them
HIDEABLE = (A_BAR_COL, A_LA_COL, A_TARGET_COL, A_LENGTH_COL, A_GAP_COL)
WHO_LABEL = "Who"
EVERYONE = "Everyone"
WHO_TIP = "Everyone's events, or one player's casts with the events that touched them"
ACTIONS_TABLE_NAME = "Player actions"
# More's switches for one player's actions, and whether each is on at first
LIGHT_ROWS, SWAP_ROWS, CONTEXT_ROWS = "light", "swaps", "context"
ACTION_SWITCHES = ((LIGHT_ROWS, "Light attacks as rows", False),
                   (SWAP_ROWS, "Swaps as rows", False),
                   (CONTEXT_ROWS, "Context", True))
PHASES_OFF_TIP = "For one player, the phases are context rows: More, Context"
LA_TIP = "A light attack began 0.3 s or less before this skill"
SWAP_TIP = "A weapon swap came just before this cast"
SHOW_LABEL = "Show"
# Show's choices: the whole fight, its last stretch, or the seconds either
# side of a moment (the row selected when the choice is made, or the moment
# another view sent: show_around)
LAST, AROUND = "last", "around"
SHOW_CHOICES = (("Whole fight", None), ("Last 60 s", (LAST, 60000)),
                ("±10 s around a moment", (AROUND, 10000)),
                ("±30 s around a moment", (AROUND, 30000)))
AROUND_MS = 10000  # the window a jump from another view opens with
MORE_LABEL = "More"
MORE_TIP = "More kinds of events, off at first"
HIDDEN_NAME = "hidden name"  # what a reader hears for a name Hide names hides
RECAP_TIP = "Enter or double-click: this death's recap"
FULL_ROW_NAME = "Selected event"
GRAPH_HREF = "graph"
GRAPH_LINK = "On the DPS graph"
GRAPH_KEYS = "Ctrl+G"
SEARCHED = " · matching the search"  # the count's end while a search narrows the rows
OLD_FIGHT = "This fight was recorded before the app kept its events."
NO_EVENTS = "No events in this fight."
# The widest each column's cells make it, in average characters and as a
# share of the table, before they are cut (Detail takes the rest; What,
# a word or two, is never cut)
COLUMN_CAPS = {WHAT_COL: (14, 1.0), ABILITY_COL: (28, 0.22), WHO_COL: (26, 0.15)}
ACTION_CAPS = {A_BAR_COL: (8, 1.0), A_LA_COL: (3, 1.0), A_ACTION_COL: (28, 0.30),
               A_TARGET_COL: (22, 0.15), A_LENGTH_COL: (7, 1.0), A_GAP_COL: (7, 1.0)}
TIME_TEMPLATE = "99:99.9"
# The roles the model answers, as plain ints: a table asks for several of
# each cell at every paint (see gui.positions_window)
_DISPLAY, _ACCESSIBLE, _DECORATION, _ALIGNMENT, _TOOLTIP, _FONT, _FOREGROUND = (
    int(role.value) for role in (Qt.DisplayRole, Qt.AccessibleTextRole, Qt.DecorationRole,
                                 Qt.TextAlignmentRole, Qt.ToolTipRole, Qt.FontRole,
                                 Qt.ForegroundRole))
_RIGHT = int((Qt.AlignRight | Qt.AlignVCenter).value)
# The columns right-aligned in one player's actions: the times and seconds
_ACTION_RIGHT = frozenset({A_TIME_COL, A_LENGTH_COL, A_GAP_COL})
# The selected row's line: its text can be selected, its link followed by
# mouse or by Tab and Enter
_LINE_FLAGS = (Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
               | Qt.LinksAccessibleByKeyboard)
# How a row is chosen after the rows change (EventsPage._refill)
_FIRST_DEATH, _FIRST = "first death", "first"

# A row as the table shows it: the event_rows Row (or action_rows
# ActionRow), its cells' text (names through the mask), the text the search
# looks in, the cells a screen reader hears otherwise ({column: text}), the
# cells' own hover text ({column: text}), and the row whole for the line
# under the table
Shown = namedtuple("Shown", "row cells searched spoken tips line")


def row_key(row) -> tuple:
    """What a row is known by across a redraw: its time, what and ability."""
    return row.t, row.what, row.ability


def masked(row, names=NO_MASK) -> Shown:
    """*row* as the table shows it, its names through the mask *names*."""
    cells = (clock(row.t), row.what, row.ability, names.text_in(row.who),
             names.text_in(row.detail))
    who_spoken = names.text_in(row.who, HIDDEN_NAME)
    spoken = {WHO_COL: who_spoken} if who_spoken != cells[WHO_COL] else {}
    return Shown(row, cells, "\0".join(cells).casefold(), spoken, {},
                 " · ".join(cell for cell in cells if cell))


def masked_action(row, names=NO_MASK) -> Shown:
    """One player's action *row* (action_rows) as the table shows it, its
    names through the mask *names*; the line under the table says what the
    marks and the seconds are."""
    bar = row.bar
    cells = (clock(row.t), bar, row.la, row.action, names.text_in(row.target), row.length,
             row.gap, names.text_in(row.detail))
    spoken, tips = {}, {}
    swapped = bar.startswith(action_rows.SWAP_MARK)
    if swapped:
        slot = bar[len(action_rows.SWAP_MARK):]
        spoken[A_BAR_COL] = "after a weapon swap" + (f", {slot}" if slot else "")
        tips[A_BAR_COL] = SWAP_TIP + (f"; its skill is in {slot}" if slot else "")
    if row.la:
        spoken[A_LA_COL] = "after a light attack"
        tips[A_LA_COL] = LA_TIP
    for column, text in ((A_TARGET_COL, row.target), (A_DETAIL_COL, row.detail)):
        heard = names.text_in(text, HIDDEN_NAME)
        if heard != cells[column]:
            spoken[column] = heard
    parts = [cells[A_TIME_COL], spoken.get(A_BAR_COL, bar),
             spoken.get(A_LA_COL, ""), row.action,
             f"at {cells[A_TARGET_COL]}" if row.target else "",
             f"lasted {row.length}" if row.length else "",
             f"{row.gap} after the skill before" if row.gap else "", cells[A_DETAIL_COL]]
    return Shown(row, cells, "\0".join(cells).casefold(), spoken, tips,
                 " · ".join(part for part in parts if part))


def deaths_in(row) -> int:
    """How many deaths a deaths row tells: 'Died x3' three, a 'Back' none."""
    if row.category != "deaths" or not row.strong:
        return 0
    return max(1, len(row.who_keys))


def summary_text(rows, names=NO_MASK) -> str:
    """The line above the table: '62 events · 3 deaths · Lokkestiiz
    reached 25%' (or 'Lokkestiiz died at 4:31.2')."""
    if not rows:
        return NO_EVENTS
    deaths = sum(deaths_in(row) for row in rows)
    parts = [f"{len(rows)} event{'s' if len(rows) != 1 else ''}",
             f"{deaths} death{'s' if deaths != 1 else ''}" if deaths else "no deaths"]
    died = [row for row in rows if row.what == "Boss died"]
    marks = [row for row in rows if row.what == "Boss health"]
    if died:
        bosses = list(dict.fromkeys(row.who for row in died))
        if len(bosses) == 1:
            parts.append(f"{names.text_in(bosses[0])} died at {clock(died[-1].t)}")
        else:
            parts.append(f"{len(bosses)} bosses died, the last at {clock(died[-1].t)}")
    elif marks:
        lowest = min(marks, key=lambda row: (int(row.ability.rstrip("%") or 100), row.t))
        parts.append(f"{names.text_in(lowest.who)} reached {lowest.ability}")
    return " · ".join(parts)


class EventsModel(QAbstractTableModel):
    """The rows shown (Shown), in the columns of the mode: everyone's
    events (COLUMNS) or one player's actions (ACTION_COLUMNS). It holds no
    reference to the page."""

    def __init__(self, icons: IconCache, parent=None):
        super().__init__(parent)
        self._rows: list = []
        self._columns = COLUMNS
        self._icon_column = ABILITY_COL
        self._right = frozenset({TIME_COL})
        self._icons = icons
        self._icon_of: dict = {}  # icon stem -> QIcon, or None for none bundled
        self._bold = QFont()
        self._bold.setBold(True)
        self._italic = QFont()
        self._italic.setItalic(True)
        self._muted = None  # the context rows' colour (QColor)

    def set_rows(self, rows, actions: bool = False) -> None:
        """*rows* shown in everyone's columns, or one player's (*actions*)."""
        self.beginResetModel()
        self._rows = list(rows)
        if actions:
            self._columns, self._icon_column, self._right = (ACTION_COLUMNS, A_ACTION_COL,
                                                             _ACTION_RIGHT)
        else:
            self._columns, self._icon_column, self._right = COLUMNS, ABILITY_COL, {TIME_COL}
        self.endResetModel()

    def columns(self) -> tuple:
        return self._columns

    def set_bold(self, font: QFont) -> None:
        """The strong rows' font: the table's own, bold; the context rows'
        the same, italic."""
        self._bold = QFont(font)
        self._bold.setBold(True)
        self._italic = QFont(font)
        self._italic.setItalic(True)
        self._changed()

    def set_muted(self, color) -> None:
        """The context rows' text colour (the palette's placeholder text)."""
        self._muted = color
        self._changed()

    def _changed(self) -> None:
        if self._rows:
            self.dataChanged.emit(self.index(0, 0),
                                  self.index(len(self._rows) - 1, len(self._columns) - 1))

    def rows(self) -> list:
        return list(self._rows)

    def shown_at(self, row: int):
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def _icon(self, stem: str):
        if stem not in self._icon_of:
            image = self._icons.image(stem) if stem else None
            self._icon_of[stem] = QIcon(QPixmap.fromImage(image)) if image is not None else None
        return self._icon_of[stem]

    def rowCount(self, parent=None) -> int:
        return 0 if parent is not None and parent.isValid() else len(self._rows)

    def columnCount(self, parent=None) -> int:
        return 0 if parent is not None and parent.isValid() else len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if (orientation == Qt.Horizontal and role == Qt.DisplayRole
                and 0 <= section < len(self._columns)):
            return self._columns[section]
        return None

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable if index.isValid() else Qt.NoItemFlags

    def data(self, index, role=_DISPLAY):
        role = int(role.value) if hasattr(role, "value") else int(role)
        if role not in (_DISPLAY, _ACCESSIBLE, _DECORATION, _ALIGNMENT, _TOOLTIP, _FONT,
                        _FOREGROUND):
            return None
        row, column = index.row(), index.column()
        if not 0 <= row < len(self._rows) or not 0 <= column < len(self._columns):
            return None
        shown = self._rows[row]
        if role == _DISPLAY:
            return shown.cells[column]
        muted = getattr(shown.row, "muted", False)
        if role == _FONT:
            return self._bold if shown.row.strong else self._italic if muted else None
        if role == _FOREGROUND:
            return self._muted if muted else None
        if role == _DECORATION:
            return self._icon(shown.row.icon) if column == self._icon_column else None
        if role == _ALIGNMENT:
            return _RIGHT if column in self._right else None
        if role == _ACCESSIBLE:
            return shown.spoken.get(column)
        # The hover: a cut cell whole (or what a mark means), and what
        # Enter does on a death's row
        text = shown.tips.get(column) or (shown.cells[column] if column else "")
        if shown.row.death is not None:
            text = f"{text}\n{RECAP_TIP}" if text else RECAP_TIP
        return text or None


class _FlowLayout(QLayout):
    """Widgets left to right, onto a new line where the width runs out,
    each centred on its line: the filter bar (see the module notes)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list = []
        self._gaps = (6, 4)  # between items on a line, between lines

    def set_gaps(self, across: int, down: int) -> None:
        self._gaps = (across, down)
        self.invalidate()

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._lay_out(QRect(0, 0, width, 0), place=False)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._lay_out(rect, place=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            if not item.isEmpty():
                size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _lay_out(self, rect, place: bool) -> int:
        """The lines' height in all; with *place*, the items placed."""
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        across, down = self._gaps
        lines, line, width = [], [], 0
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            if line and width + across + hint.width() > area.width():
                lines.append(line)
                line, width = [], 0
            width += (across if line else 0) + hint.width()
            line.append((item, hint))
        if line:
            lines.append(line)
        y = area.y()
        for number, items in enumerate(lines):
            tall = max(hint.height() for _item, hint in items)
            x = area.x()
            for item, hint in items:
                if place:
                    item.setGeometry(QRect(QPoint(x, y + (tall - hint.height()) // 2), hint))
                x += hint.width() + across
            y += tall + (down if number < len(lines) - 1 else 0)
        return y - rect.y() + margins.bottom()


class EventsPage(QWidget):
    """The Events tab's page: the summary line, the filter bar and the
    table, for the fight the main window gives it (see the module notes)."""

    # A death's row chosen with Enter or a double-click: the player's unit
    # id and the death's number among theirs, as the Deaths tab's names
    recap_requested = Signal(str, int)
    # The row selected asked for on the DPS graph (Ctrl+G, or the link under
    # the table): its time in ms into the fight, and what it was
    graph_requested = Signal(int, str)

    def __init__(self, icons=None, parent=None):
        super().__init__(parent)
        self.setAccessibleName(PAGE_NAME)
        self._entry = None
        self._names = NO_MASK
        self._all: list = []  # every row of the fight, as shown (Shown)
        self._search = ""
        self._anchor_ms = None  # the moment Show's ± choices are around
        self._content_widths: dict = {}  # column -> its widest cell, measured for the rows
        self._who = None  # the player whose actions are shown (their key), None for everyone
        self._who_carried = None  # ... and what a next fight finds them by (legend_key)
        self._hidden: set = set()  # the columns no row of the player's fills

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        self.summary = QLabel("")
        self.summary.setTextFormat(Qt.PlainText)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self._bar = _FlowLayout()
        # Who: everyone's events, or one player's actions; the label and its
        # picker wrap together
        who = QWidget()
        who_layout = QHBoxLayout(who)
        who_layout.setContentsMargins(0, 0, 0, 0)
        who_label = QLabel(WHO_LABEL)
        who_layout.addWidget(who_label)
        self.who_picker = QComboBox()
        who_label.setBuddy(self.who_picker)
        self.who_picker.setAccessibleName(WHO_LABEL)
        self.who_picker.setToolTip(WHO_TIP)
        self.who_picker.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.who_picker.setMinimumContentsLength(16)
        self.who_picker.addItem(EVERYONE, None)
        self.who_picker.currentIndexChanged.connect(self._on_who)
        who_layout.addWidget(self.who_picker)
        self._bar.addWidget(who)
        self.category_boxes = {}
        for key, label in CATEGORIES:
            if key in DEFAULT_CATEGORIES:
                box = QCheckBox(label)
                box.setChecked(True)
                box.toggled.connect(self._on_filter)
                self.category_boxes[key] = box
                self._bar.addWidget(box)
        self.more_button = QToolButton()
        self.more_button.setText(MORE_LABEL)
        self.more_button.setAccessibleName(MORE_LABEL)
        self.more_button.setToolTip(MORE_TIP)
        self.more_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.more_button)
        self.more_actions = {}
        for key, label in CATEGORIES:
            if key in MORE:
                action = menu.addAction(label)
                action.setCheckable(True)
                action.toggled.connect(self._on_filter)
                self.more_actions[key] = action
        # One player's actions: their switches, under the categories
        menu.addSeparator()
        self.action_switches = {}
        for key, label, on in ACTION_SWITCHES:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(on)
            action.toggled.connect(self._on_switch)
            self.action_switches[key] = action
        self.more_button.setMenu(menu)
        self._bar.addWidget(self.more_button)
        # The Show label and its picker wrap together
        show = QWidget()
        show_layout = QHBoxLayout(show)
        show_layout.setContentsMargins(0, 0, 0, 0)
        show_label = QLabel(SHOW_LABEL)
        show_layout.addWidget(show_label)
        self.show_picker = QComboBox()
        show_label.setBuddy(self.show_picker)
        self.show_picker.setAccessibleName(SHOW_LABEL)
        for label, window in SHOW_CHOICES:
            self.show_picker.addItem(label, window)
        self.show_picker.currentIndexChanged.connect(self._on_filter)
        show_layout.addWidget(self.show_picker)
        self._bar.addWidget(show)
        self.count_label = QLabel("")
        self.count_label.setTextFormat(Qt.PlainText)
        self._bar.addWidget(self.count_label)
        layout.addLayout(self._bar)

        self.table = QTableView()
        self.model = EventsModel(icons if icons is not None else IconCache(), self)
        self.table.setModel(self.model)
        self.table.setAccessibleName(TABLE_NAME)
        self.table.setAccessibleDescription(TABLE_HINT)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setTabKeyNavigation(False)  # Tab leaves the table
        self.table.setSortingEnabled(False)  # time order, always
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        self.table.activated.connect(self._on_activated)
        layout.addWidget(self.table, 1)
        # The row selected in full, under the table: its cells are cut at a
        # large text size
        self.full_row = QLabel("")
        self.full_row.setTextFormat(Qt.RichText)
        self.full_row.setWordWrap(True)
        # Its link, the row's moment on the DPS graph, by mouse and by Tab,
        # once a row is selected (_show_full_row)
        self.full_row.setTextInteractionFlags(Qt.NoTextInteraction)
        self.full_row.setAccessibleName(FULL_ROW_NAME)
        self.full_row.linkActivated.connect(self._ask_graph)
        layout.addWidget(self.full_row)
        self.table.selectionModel().currentRowChanged.connect(self._show_full_row)
        QShortcut(QKeySequence(GRAPH_KEYS), self, self._ask_graph,
                  context=Qt.WidgetWithChildrenShortcut)
        self._fit_rows()
        self._fit_controls()

    # ---- what the main window asks ----

    @property
    def entry(self):
        """The fight on display, None before the first."""
        return self._entry

    @property
    def who(self):
        """The key of the player whose actions are shown, None for everyone."""
        return self._who

    def focus_chain(self) -> list:
        """The page's controls in Tab order, for the window's."""
        return [self.who_picker, *self.category_boxes.values(), self.more_button,
                self.show_picker, self.table, self.full_row]

    def show_fight(self, entry, names=None) -> None:
        """Show the fight *entry*, its names through the mask *names*: in
        place when it is the fight shown already, the row selected and the
        scroll kept; else anew, at its first death (see the module notes).
        Who stays on the player picked when they are in another fight
        (legend_key), else goes back to everyone."""
        same = entry is not None and entry is self._entry
        key = self._selected_key() if same else None
        scroll = self.table.verticalScrollBar().value() if same else None
        self._entry = entry
        self._names = names or NO_MASK
        self._fill_who(same)
        self._build_rows()
        if same:
            self._refill(key, scroll=scroll)
        else:
            # Another fight: a moment of the last one is none of this one's
            if self._around() is not None:
                self._set_show(0)
            self._anchor_ms = None
            self._refill(_FIRST_DEATH)
        # Measured again in place too: rows logged later, or Hide names,
        # can widen a column (the selection and the scroll stay)
        self._measure_columns()

    def clear(self) -> None:
        """Show no fight: the page with no fight keeps no names from the
        last. The player picked is kept for the next fight."""
        self._entry = None
        self._all = []
        self._anchor_ms = None
        self._who = None
        self._fill_who(False)
        self.summary.setText("")
        self._set_mode()
        self._refill(None)

    def show_player(self, unit_key: str) -> bool:
        """Who set to the player *unit_key* of the fight shown, their
        actions drawn from their first death, else their first row: where
        the player window's link sends the reader. Whether they are among
        the players Who lists."""
        index = self.who_picker.findData(str(unit_key))
        if self._entry is None or index < 0:
            return False
        if self._around() is not None:
            self._set_show(0)
            self._anchor_ms = None
        self._set_who(index, _FIRST_DEATH)
        return True

    def show_around(self, t_ms: int, window_ms: int = AROUND_MS, unit_key: str = "") -> bool:
        """Show the rows within *window_ms* of the moment *t_ms* (ms into
        the fight), the first row from that moment on selected: where a
        death's recap, the DPS graph or the buff strip sends the reader.
        With *unit_key*, the moment is that player's death: the Deaths box
        is ticked if it was not, and the row that tells the death is
        selected, which for players who died together is one row at the
        first death's time; Who goes back to everyone when another player
        is picked, whose actions hold no such row. Whether there was a
        fight to show it for."""
        index = next((n for n, (_label, data) in enumerate(SHOW_CHOICES)
                      if data == (AROUND, window_ms)), None)
        if index is None or self._entry is None:
            return False
        self._anchor_ms = int(t_ms)
        self._set_show(index)
        if unit_key and self._who is not None and str(unit_key) != self._who:
            self._set_who(0, None)
        select = (int(t_ms), None, None)
        if unit_key:
            box = self.category_boxes["deaths"]
            if not box.isChecked():
                box.blockSignals(True)
                box.setChecked(True)
                box.blockSignals(False)
            told = [shown.row for shown in self._all
                    if shown.row.category == "deaths" and shown.row.strong
                    and str(unit_key) in shown.row.who_keys and shown.row.t <= int(t_ms)]
            if told:
                select = row_key(told[-1])
        self._refill(select)
        return True

    def _set_show(self, index: int) -> None:
        """Show's choice set without its signal: the caller fills the rows."""
        self.show_picker.blockSignals(True)
        self.show_picker.setCurrentIndex(index)
        self.show_picker.blockSignals(False)

    def _around(self):
        """The window either side of the moment, when Show is one; else None."""
        data = self.show_picker.currentData()
        return data[1] if data and data[0] == AROUND else None

    # ---- who ----

    def _fill_who(self, same: bool) -> None:
        """Who's list for the fight shown: Everyone, then each player row
        (action_rows.players), names through the mask, while the fight's
        casts were kept. The player picked stays for the same fight; in
        another, the one found by what the last was picked by, else
        everyone."""
        entry = self._entry
        listed = action_rows.players(entry) if getattr(entry, "casts", None) is not None else []
        zone = str(getattr(entry, "zone_name", "") or "")
        if same:
            want = self._who
        else:
            want = next((str(p["unit_id"]) for p in listed
                         if self._who_carried is not None
                         and legend_key(p, zone) == self._who_carried), None)
        self.who_picker.blockSignals(True)
        self.who_picker.clear()
        self.who_picker.addItem(EVERYONE, None)
        for p in listed:
            role = str(p.get("role") or "")
            name = self._names.text(action_rows.player_name(p))
            self.who_picker.addItem(f"{role}  {name}" if role else name, str(p["unit_id"]))
        index = self.who_picker.findData(want) if want is not None else 0
        self.who_picker.setCurrentIndex(max(0, index))
        self.who_picker.blockSignals(False)
        self._who = self.who_picker.currentData()
        # The list shows whole rows, though the field may be narrower
        view = self.who_picker.view()
        view.setMinimumWidth(view.sizeHintForColumn(0) + 2 * view.frameWidth()
                             + view.verticalScrollBar().sizeHint().width())

    def _on_who(self, index: int) -> None:
        """Who chosen: the other mode's rows, from the moment of the row
        selected on (another mode's rows are other rows)."""
        key = self._selected_key()
        self._set_who(index, (key[0], None, None) if key is not None else _FIRST_DEATH,
                      chosen=True)

    def _set_who(self, index: int, select, chosen: bool = True) -> None:
        """Who set to its *index*, the rows built for it and *select*ed
        (see _refill); *chosen*: the reader's choice, which a next fight
        keeps."""
        if self.who_picker.currentIndex() != index:
            self.who_picker.blockSignals(True)
            self.who_picker.setCurrentIndex(index)
            self.who_picker.blockSignals(False)
        self._who = self.who_picker.currentData()
        if chosen:
            p = action_rows.player_row(self._entry, self._who) if self._who is not None else None
            self._who_carried = (legend_key(p, str(getattr(self._entry, "zone_name", "") or ""))
                                 if p is not None else None)
        self._build_rows()
        self._refill(select)
        self._measure_columns()

    def _build_rows(self) -> None:
        """Every row of the fight for Who (Shown), the summary above them
        and the controls of the mode."""
        entry = self._entry
        if entry is not None and self._who is not None:
            rows = action_rows.action_rows(
                entry, self._who, light_rows=self.action_switches[LIGHT_ROWS].isChecked(),
                swap_rows=self.action_switches[SWAP_ROWS].isChecked())
            self._all = [masked_action(row, self._names) for row in rows]
            self.summary.setText(action_rows.summary_text(entry, self._who, self._names))
        else:
            rows = event_rows.event_rows(entry) if entry is not None else []
            self._all = [masked(row, self._names) for row in rows]
            if entry is not None and getattr(entry, "events", None) is None:
                self.summary.setText(OLD_FIGHT)
            else:
                self.summary.setText(summary_text(rows, self._names) if entry is not None else "")
        self._set_mode()

    def _set_mode(self) -> None:
        """The table's name, the columns empty for every row of one player
        (HIDEABLE), and the controls that apply (_fit_controls)."""
        actions = self._who is not None
        self.table.setAccessibleName(ACTIONS_TABLE_NAME if actions else TABLE_NAME)
        self._hidden = ({column for column in HIDEABLE
                         if not any(shown.cells[column] for shown in self._all)}
                        if actions else set())
        self._fit_controls()

    def _fit_controls(self) -> None:
        """Everyone's More categories, or one player's switches, and the
        Phases box, whose rows are context rows for one player."""
        actions = self._who is not None
        for action in self.more_actions.values():
            action.setEnabled(not actions)
        for action in self.action_switches.values():
            action.setEnabled(actions)
        phases = self.category_boxes.get("phases")
        if phases is not None:
            phases.setEnabled(not actions)
            phases.setToolTip(PHASES_OFF_TIP if actions else "")

    def _on_switch(self, *_):
        """One of More's switches for one player: light attacks or swaps
        as rows build the rows again, the row selected kept by its moment;
        Context shows or hides its rows."""
        if self._who is None or self._entry is None:
            return
        key = self._selected_key()
        self._build_rows()
        self._refill(key)
        self._measure_columns()

    def set_search(self, text: str) -> int:
        """Filter the rows to those whose cells hold *text*
        (case-insensitive); a new search selects its first row, a cleared
        one keeps the row selected. The rows shown."""
        text = str(text or "")
        if text != self._search:
            key = self._selected_key()
            self._search = text
            self._refill(_FIRST if text else key)
        return self.model.rowCount()

    def select_next_match(self) -> None:
        """Enter in the search: the next row shown after the one selected,
        round to the first."""
        rows = self.model.rowCount()
        if not self._search or not rows:
            return
        current = self._selected_row()
        self._select(0 if current is None else (current + 1) % rows)

    def shown_rows(self) -> list:
        """The rows on the table, event_rows Rows (action_rows ActionRows
        for one player)."""
        return [shown.row for shown in self.model.rows()]

    def selected(self):
        """The row selected (an event_rows Row or ActionRow), or None."""
        row = self._selected_row()
        return self.model.shown_at(row).row if row is not None else None

    def categories(self) -> list:
        """The categories chosen, in the filter's order."""
        chosen = [key for key, box in self.category_boxes.items() if box.isChecked()]
        return chosen + [key for key, action in self.more_actions.items() if action.isChecked()]

    def hidden_columns(self) -> set:
        """The columns no row of the player picked fills, hidden."""
        return set(self._hidden)

    # ---- the rows ----

    def _filtered(self) -> list:
        if self._who is None:
            chosen = set(self.categories())
        else:
            # One player: every cast and stretch with no cast; the events
            # of the boxes ticked (not Phases); the context with its switch
            chosen = {key for key, box in self.category_boxes.items()
                      if box.isChecked() and key in action_rows.EVENT_CATEGORIES}
            chosen |= {action_rows.CASTS, action_rows.IDLE}
            if self.action_switches[CONTEXT_ROWS].isChecked():
                chosen.add(action_rows.CONTEXT)
        rows = [shown for shown in self._all if shown.row.category in chosen]
        data = self.show_picker.currentData()
        if data and self._entry is not None:
            kind, window = data
            if kind == LAST:
                end = round(float(getattr(self._entry, "duration_s", 0) or 0) * 1000)
                rows = [shown for shown in rows if shown.row.t >= end - window]
            elif self._anchor_ms is not None:
                low, high = self._anchor_ms - window, self._anchor_ms + window
                rows = [shown for shown in rows if low <= shown.row.t <= high]
        if self._search:
            needle = self._search.casefold()
            rows = [shown for shown in rows if needle in shown.searched]
        return rows

    def _refill(self, select, scroll=None) -> None:
        """The table filled again from the fight's rows and the filters,
        then a row selected: *select* is _FIRST_DEATH, _FIRST, a row's key
        (row_key; else the first row from its time on), or None; *scroll*,
        when given, put back, else the row selected brought into view."""
        shown = self._filtered()
        self.model.set_rows(shown, actions=self._who is not None)
        for column in range(self.model.columnCount()):
            self.table.setColumnHidden(column, column in self._hidden)
        # The scroll bars' range follows the rows only once the view lays
        # them out, which a reset leaves for later
        self.table.doItemsLayout()
        row = self._pick(shown, select)
        if row is not None:
            self._select(row, visible=scroll is None)
        if scroll is not None:
            self.table.verticalScrollBar().setValue(scroll)
        elif row is None:
            self.table.scrollToTop()
        self._update_count()
        # A model reset need not say that the current row changed
        self._show_full_row(self.model.index(row, 0) if row is not None else self.model.index(-1, 0))

    @staticmethod
    def _pick(shown: list, select):
        if not shown or select is None:
            return None
        if select == _FIRST:
            return 0
        if select == _FIRST_DEATH:
            return next((n for n, s in enumerate(shown)
                         if s.row.category == "deaths" and s.row.strong), 0)
        exact = next((n for n, s in enumerate(shown) if row_key(s.row) == select), None)
        if exact is not None:
            return exact
        return next((n for n, s in enumerate(shown) if s.row.t >= select[0]), len(shown) - 1)

    def _select(self, row: int, visible: bool = True) -> None:
        index = self.model.index(row, 0)
        self.table.selectionModel().setCurrentIndex(
            index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        if visible:
            self.table.scrollTo(index, QAbstractItemView.EnsureVisible)

    def _selected_row(self):
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _selected_key(self):
        row = self._selected_row()
        shown = self.model.shown_at(row) if row is not None else None
        return row_key(shown.row) if shown is not None else None

    def _update_count(self) -> None:
        total, shown = len(self._all), self.model.rowCount()
        if self._entry is None or not total:
            self.count_label.setText("")
        else:
            around = (f" · around {clock(self._anchor_ms)}"
                      if self._around() is not None and self._anchor_ms is not None else "")
            # A search narrows the rows too: said, so a table left short or
            # empty after a jump from another view explains itself
            searched = SEARCHED if self._search else ""
            self.count_label.setText(f"{shown} of {total} shown{around}{searched}")
        # The items on that apply: everyone's categories, or one player's
        # switches (Context, on at first, among them)
        items = self.action_switches if self._who is not None else self.more_actions
        on = sum(1 for action in items.values() if action.isChecked())
        label = f"{MORE_LABEL} ({on})" if on else MORE_LABEL
        self.more_button.setText(label)
        self.more_button.setAccessibleName(label)

    def _on_filter(self, *_):
        """A category or Show changed: the row selected kept while shown.
        Show turned to the seconds around a moment takes the row selected
        as the moment, and keeps the one it has from ±10 s to ±30 s."""
        key = self._selected_key()
        if self._around() is None:
            self._anchor_ms = None
        elif self._anchor_ms is None:
            self._anchor_ms = key[0] if key is not None else 0
        self._refill(key)

    def _show_full_row(self, current, _previous=None) -> None:
        """The row selected, every cell whole, under the table; and for a
        single death, what Enter does."""
        shown = self.model.shown_at(current.row()) if current.isValid() else None
        # A Tab stop only while it has a link to stop at
        self.full_row.setTextInteractionFlags(_LINE_FLAGS if shown is not None
                                              else Qt.NoTextInteraction)
        if shown is None:
            self.full_row.setText("")
            return
        text = escape(shown.line, quote=False)
        if shown.row.death is not None:
            text += f" — {escape(RECAP_TIP, quote=False)}"
        # In the app's link colour, as a death's Positions link is
        dark = self.palette().color(QPalette.Base).lightness() < 128
        text += (f' — <a href="{GRAPH_HREF}" style="text-decoration:none;'
                 f'color:{link_color(dark)}">{GRAPH_LINK}</a> ({GRAPH_KEYS})')
        self.full_row.setText(text)

    def _ask_graph(self, *_) -> None:
        """Ctrl+G or the link under the table: the row selected, as a
        moment on the DPS graph."""
        row = self.selected()
        if row is not None:
            label = row.what + (f" · {row.ability}" if row.ability else "")
            self.graph_requested.emit(int(row.t), label)

    def _on_activated(self, index) -> None:
        """Enter or a double-click: a single death's recap."""
        shown = self.model.shown_at(index.row())
        if shown is not None and shown.row.death is not None:
            unit_id, number = shown.row.death
            self.recap_requested.emit(str(unit_id), int(number))

    # ---- sizes ----

    def _fit_rows(self) -> None:
        """The icon, the rows' height and the bold font at the text size in
        force (see the module notes)."""
        metrics = QFontMetrics(self.font())
        icon = scaled_px(ICON_PX)
        self.table.setIconSize(QSize(icon, icon))
        row = max(metrics.height() + scaled_px(6), icon + scaled_px(4))
        header = self.table.verticalHeader()
        header.setMinimumSectionSize(min(header.minimumSectionSize(), row))
        header.setDefaultSectionSize(row)
        self.model.set_bold(self.font())
        self.model.set_muted(self.palette().color(QPalette.PlaceholderText))
        self._bar.set_gaps(scaled_px(10), scaled_px(4))

    def _caps(self) -> tuple[dict, int]:
        """The mode's column caps (COLUMN_CAPS, ACTION_CAPS) and the column
        with the icon."""
        if self._who is not None:
            return ACTION_CAPS, A_ACTION_COL
        return COLUMN_CAPS, ABILITY_COL

    def _measure_columns(self) -> None:
        """Each column's widest cell for the rows of the fight, then the
        widths (_apply_widths)."""
        metrics = QFontMetrics(self.font())
        header = self.table.horizontalHeader()
        pad = metrics.horizontalAdvance("M")
        self._content_widths = {TIME_COL: max(metrics.horizontalAdvance(TIME_TEMPLATE) + pad,
                                              header.sectionSizeHint(TIME_COL))}
        for column in self._caps()[0]:
            cells = self.table.sizeHintForColumn(column) if self.model.rowCount() else 0
            self._content_widths[column] = max(cells, header.sectionSizeHint(column))
        self._apply_widths()

    def _apply_widths(self) -> None:
        if not self._content_widths:
            return
        average = QFontMetrics(self.font()).averageCharWidth()
        room = self.table.viewport().width()
        caps, icon_column = self._caps()
        for column, width in self._content_widths.items():
            if column in caps:
                chars, share = caps[column]
                most = chars * average + (self.table.iconSize().width() if column == icon_column
                                          else 0)
                width = max(min(width, most, int(room * share)),
                            self.table.horizontalHeader().sectionSizeHint(column))
            self.table.setColumnWidth(column, width)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._apply_widths()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self.model.set_muted(self.palette().color(QPalette.PlaceholderText))
        if event.type() == QEvent.FontChange:
            self._fit_rows()
            self._measure_columns()
            # Taller rows move the row selected: it is kept in view, once the
            # table has laid its rows out at the new size (it takes the
            # font change after its page)
            QTimer.singleShot(0, self, self._keep_current_in_view)

    def _keep_current_in_view(self) -> None:
        current = self.table.currentIndex()
        if current.isValid():
            self.table.scrollTo(current, QAbstractItemView.EnsureVisible)
