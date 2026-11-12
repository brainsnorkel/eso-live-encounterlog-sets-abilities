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
"""

from collections import namedtuple

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
from PySide6.QtGui import QFont, QFontMetrics, QIcon, QPixmap
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

import event_rows
from event_rows import CATEGORIES, DEFAULT_CATEGORIES, MORE, clock
from gui.death_render import ICON_PX
from gui.icon_cache import IconCache
from gui.name_mask import NO_MASK
from gui.text_size import scaled_px

PAGE_NAME = "Events"
TABLE_NAME = "Fight events"
TABLE_HINT = "Enter or a double-click on a death's row opens that death's recap."
COLUMNS = ("Time", "What", "Ability", "Who", "Detail")
TIME_COL, WHAT_COL, ABILITY_COL, WHO_COL, DETAIL_COL = range(len(COLUMNS))
SHOW_LABEL = "Show"
SHOW_CHOICES = (("Whole fight", None), ("Last 60 s", 60000))
MORE_LABEL = "More"
MORE_TIP = "More kinds of events, off at first"
HIDDEN_NAME = "hidden name"  # what a reader hears for a name Hide names hides
RECAP_TIP = "Enter or double-click: this death's recap"
FULL_ROW_NAME = "Selected event"
OLD_FIGHT = "This fight was recorded before the app kept its events."
NO_EVENTS = "No events in this fight."
# The widest each column's cells make it, in average characters and as a
# share of the table, before they are cut (Detail takes the rest; What,
# a word or two, is never cut)
COLUMN_CAPS = {WHAT_COL: (14, 1.0), ABILITY_COL: (28, 0.22), WHO_COL: (26, 0.15)}
TIME_TEMPLATE = "99:99.9"
# The roles the model answers, as plain ints: a table asks for several of
# each cell at every paint (see gui.positions_window)
_DISPLAY, _ACCESSIBLE, _DECORATION, _ALIGNMENT, _TOOLTIP, _FONT = (
    int(role.value) for role in (Qt.DisplayRole, Qt.AccessibleTextRole, Qt.DecorationRole,
                                 Qt.TextAlignmentRole, Qt.ToolTipRole, Qt.FontRole))
_RIGHT = int((Qt.AlignRight | Qt.AlignVCenter).value)
# How a row is chosen after the rows change (EventsPage._refill)
_FIRST_DEATH, _FIRST = "first death", "first"

# A row as the table shows it: the event_rows Row, its five cells' text
# (names through the mask), the text the search looks in, and Who as a
# screen reader hears it
Shown = namedtuple("Shown", "row cells searched who_spoken")


def row_key(row) -> tuple:
    """What a row is known by across a redraw: its time, what and ability."""
    return row.t, row.what, row.ability


def masked(row, names=NO_MASK) -> Shown:
    """*row* as the table shows it, its names through the mask *names*."""
    cells = (clock(row.t), row.what, row.ability, names.text_in(row.who),
             names.text_in(row.detail))
    return Shown(row, cells, "\0".join(cells).casefold(), names.text_in(row.who, HIDDEN_NAME))


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
    """The rows shown (Shown), five columns. It holds no reference to the
    page."""

    def __init__(self, icons: IconCache, parent=None):
        super().__init__(parent)
        self._rows: list = []
        self._icons = icons
        self._icon_of: dict = {}  # icon stem -> QIcon, or None for none bundled
        self._bold = QFont()
        self._bold.setBold(True)

    def set_rows(self, rows) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def set_bold(self, font: QFont) -> None:
        """The strong rows' font: the table's own, bold."""
        self._bold = QFont(font)
        self._bold.setBold(True)
        if self._rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, DETAIL_COL))

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
        return 0 if parent is not None and parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and 0 <= section < len(COLUMNS):
            return COLUMNS[section]
        return None

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable if index.isValid() else Qt.NoItemFlags

    def data(self, index, role=_DISPLAY):
        role = int(role.value) if hasattr(role, "value") else int(role)
        if role not in (_DISPLAY, _ACCESSIBLE, _DECORATION, _ALIGNMENT, _TOOLTIP, _FONT):
            return None
        row, column = index.row(), index.column()
        if not 0 <= row < len(self._rows):
            return None
        shown = self._rows[row]
        if role == _DISPLAY:
            return shown.cells[column]
        if role == _FONT:
            return self._bold if shown.row.strong else None
        if role == _DECORATION:
            return self._icon(shown.row.icon) if column == ABILITY_COL else None
        if role == _ALIGNMENT:
            return _RIGHT if column == TIME_COL else None
        if role == _ACCESSIBLE:
            if column == WHO_COL and shown.who_spoken != shown.cells[WHO_COL]:
                return shown.who_spoken
            return None
        # The hover: a cut cell whole, and what Enter does on a death's row
        text = shown.cells[column] if column != TIME_COL else ""
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

    def __init__(self, icons=None, parent=None):
        super().__init__(parent)
        self.setAccessibleName(PAGE_NAME)
        self._entry = None
        self._names = NO_MASK
        self._all: list = []  # every row of the fight, as shown (Shown)
        self._search = ""
        self._content_widths: dict = {}  # column -> its widest cell, measured for the rows

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        self.summary = QLabel("")
        self.summary.setTextFormat(Qt.PlainText)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self._bar = _FlowLayout()
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
        self.full_row.setTextFormat(Qt.PlainText)
        self.full_row.setWordWrap(True)
        self.full_row.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.full_row.setAccessibleName(FULL_ROW_NAME)
        layout.addWidget(self.full_row)
        self.table.selectionModel().currentRowChanged.connect(self._show_full_row)
        self._fit_rows()

    # ---- what the main window asks ----

    @property
    def entry(self):
        """The fight on display, None before the first."""
        return self._entry

    def focus_chain(self) -> list:
        """The page's controls in Tab order, for the window's."""
        return [*self.category_boxes.values(), self.more_button, self.show_picker, self.table]

    def show_fight(self, entry, names=None) -> None:
        """Show the fight *entry*, its names through the mask *names*: in
        place when it is the fight shown already, the row selected and the
        scroll kept; else anew, at its first death (see the module notes)."""
        same = entry is not None and entry is self._entry
        key = self._selected_key() if same else None
        scroll = self.table.verticalScrollBar().value() if same else None
        self._entry = entry
        self._names = names or NO_MASK
        rows = event_rows.event_rows(entry) if entry is not None else []
        self._all = [masked(row, self._names) for row in rows]
        if entry is not None and getattr(entry, "events", None) is None:
            self.summary.setText(OLD_FIGHT)
        else:
            self.summary.setText(summary_text(rows, self._names) if entry is not None else "")
        if same:
            self._refill(key, scroll=scroll)
        else:
            self._refill(_FIRST_DEATH)
            self._measure_columns()

    def clear(self) -> None:
        """Show no fight: the page with no fight keeps no names from the last."""
        self._entry = None
        self._all = []
        self.summary.setText("")
        self._refill(None)

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
        """The rows on the table, event_rows Rows."""
        return [shown.row for shown in self.model.rows()]

    def selected(self):
        """The row selected (an event_rows Row), or None."""
        row = self._selected_row()
        return self.model.shown_at(row).row if row is not None else None

    def categories(self) -> list:
        """The categories chosen, in the filter's order."""
        chosen = [key for key, box in self.category_boxes.items() if box.isChecked()]
        return chosen + [key for key, action in self.more_actions.items() if action.isChecked()]

    # ---- the rows ----

    def _filtered(self) -> list:
        chosen = set(self.categories())
        rows = [shown for shown in self._all if shown.row.category in chosen]
        window = self.show_picker.currentData()
        if window and self._entry is not None:
            end = round(float(getattr(self._entry, "duration_s", 0) or 0) * 1000)
            rows = [shown for shown in rows if shown.row.t >= end - window]
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
        self.model.set_rows(shown)
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
            self.count_label.setText(f"{shown} of {total} shown")
        on = sum(1 for action in self.more_actions.values() if action.isChecked())
        label = f"{MORE_LABEL} ({on})" if on else MORE_LABEL
        self.more_button.setText(label)
        self.more_button.setAccessibleName(label)

    def _on_filter(self, *_):
        """A category or Show changed: the row selected kept while shown."""
        self._refill(self._selected_key())

    def _show_full_row(self, current, _previous=None) -> None:
        """The row selected, every cell whole, under the table; and for a
        single death, what Enter does."""
        shown = self.model.shown_at(current.row()) if current.isValid() else None
        if shown is None:
            self.full_row.setText("")
            return
        text = " · ".join(cell for cell in shown.cells if cell)
        if shown.row.death is not None:
            text += f" — {RECAP_TIP}"
        self.full_row.setText(text)

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
        self._bar.set_gaps(scaled_px(10), scaled_px(4))

    def _measure_columns(self) -> None:
        """Each column's widest cell for the rows of the fight, then the
        widths (_apply_widths)."""
        metrics = QFontMetrics(self.font())
        header = self.table.horizontalHeader()
        pad = metrics.horizontalAdvance("M")
        self._content_widths = {TIME_COL: max(metrics.horizontalAdvance(TIME_TEMPLATE) + pad,
                                              header.sectionSizeHint(TIME_COL))}
        for column in COLUMN_CAPS:
            cells = self.table.sizeHintForColumn(column) if self.model.rowCount() else 0
            self._content_widths[column] = max(cells, header.sectionSizeHint(column))
        self._apply_widths()

    def _apply_widths(self) -> None:
        if not self._content_widths:
            return
        average = QFontMetrics(self.font()).averageCharWidth()
        room = self.table.viewport().width()
        for column, width in self._content_widths.items():
            if column in COLUMN_CAPS:
                chars, share = COLUMN_CAPS[column]
                most = chars * average + (self.table.iconSize().width() if column == ABILITY_COL
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
