"""
The fight list: the session's fights in blocks, one per instance.

Design (issue #129): the fights fought one after another in the same
instance form a block. A header row above it names the zone and its
difficulty, so the fight rows leave the zone out; when the block ended a
trial or an arena, an inert row under its last fight gives the run's
result (trial_result: vitality, score, time); and the blocks lie on
alternate backgrounds, a faint band and none, so neighbours stand apart.

A new block starts at a fight in another zone or at another difficulty
than the fight before, or at the first fight after a completed run, even
in the same zone. A wipe and a walk back in through the same door keep the
block: the zone and difficulty are the same and no run was completed. The
zone is told by its id (a solo dungeon shares its name with the group
dungeon, pen_crit.zone_kind) and by its name only when the entry has none.

Header and result rows are not enabled, so a click or a key never makes
one current: the arrow keys step from fight to fight over them, and Home,
End and the page keys go on to the nearest fight (moveCursor). Their text
takes the list's own text colour, which a disabled row would otherwise
grey out. The list therefore maps rows to fights itself (entry_at,
row_of) and offers the fight-index calls the window and tests use
(select_fight, fight_item, current_fight_index).

The band is the list's base colour moved BAND_MIX of the way towards its
text colour, so it follows the theme and keeps the text's contrast; it is
worked out again, with the header's bold font, whenever the palette or the
font changes (a theme switch, a new text size).
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPalette
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from gui.fight_render import summary_line
from trial_result import result_text

# Item data: the fight's FightHistoryEntry (None on a header or result
# row), the row's kind and the block's number
ENTRY_ROLE = Qt.UserRole
KIND_ROLE = Qt.UserRole + 1
BLOCK_ROLE = Qt.UserRole + 2

HEADER, FIGHT, RESULT = "header", "fight", "result"

# How far a band's background is from the list's base colour, towards its
# text colour
BAND_MIX = 0.07

_DIFFICULTY_NAMES = {"VETERAN": "Veteran", "NORMAL": "Normal"}


def _difficulty(entry) -> str:
    difficulty = str(getattr(entry, "difficulty", "") or "").upper()
    if not difficulty and getattr(entry, "is_vet", False):
        difficulty = "VETERAN"
    return difficulty


def block_key(entry) -> tuple:
    """What fights of one block share: the zone and its difficulty."""
    zone = str(getattr(entry, "zone_id", "") or "") or str(entry.zone_name or "")
    return zone, _difficulty(entry)


def starts_block(previous, entry) -> bool:
    """Whether *entry* opens a block after *previous* (None: the first)."""
    return (previous is None or block_key(previous) != block_key(entry)
            or bool(getattr(previous, "trial_result", None)))


def header_text(entry) -> str:
    """'Sunspire · Veteran'; the name alone for a zone without one."""
    zone = entry.zone_name or "Unknown"
    difficulty = _DIFFICULTY_NAMES.get(_difficulty(entry))
    return f"{zone} · {difficulty}" if difficulty else zone


def band_color(base: QColor, text: QColor) -> QColor:
    """*base* moved BAND_MIX of the way towards *text*."""
    def mix(a, b):
        return round(a + (b - a) * BAND_MIX)
    return QColor(mix(base.red(), text.red()), mix(base.green(), text.green()),
                  mix(base.blue(), text.blue()))


class FightList(QListWidget):
    """The history list: header, fight and result rows (see the module)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Fights")
        self._last_entry = None  # the newest fight, for the next one's block
        self._block = -1

    # ---- building ----

    def clear(self):
        super().clear()
        self._last_entry = None
        self._block = -1

    def set_fights(self, fights):
        """Every row anew for *fights*; none is made current."""
        self.clear()
        for entry in fights:
            self.add_fight(entry)

    def add_fight(self, entry) -> int:
        """Add *entry* under the last fight, with a header when it opens a
        block and its result row when it completed a run; its row."""
        if starts_block(self._last_entry, entry):
            self._block += 1
            self._add_row(HEADER, header_text(entry))
        self._last_entry = entry
        row = self.count()
        self._add_row(FIGHT, summary_line(entry, death_cue=True, issue_cue=True, zone=False),
                      entry)
        if getattr(entry, "trial_result", None):
            self._add_row(RESULT, result_text(entry.trial_result))
        return row

    def update_fight(self, entry):
        """Rewrite *entry*'s row (a late death, a fight the game cut in
        two) and add its result row when the run's result came after it
        was listed; its row, or None when the list does not hold it. The
        engine updates only its newest fight, so a result row never lands
        between two fights of a block."""
        row = self.row_of(entry)
        if row is None:
            return None
        self.item(row).setText(summary_line(entry, death_cue=True, issue_cue=True, zone=False))
        result = getattr(entry, "trial_result", None)
        if result:
            below = self.item(row + 1)
            if below is not None and below.data(KIND_ROLE) == RESULT:
                below.setText(result_text(result))
            else:
                self._add_row(RESULT, result_text(result), at=row + 1,
                              block=self.item(row).data(BLOCK_ROLE))
        return row

    def _add_row(self, kind, text, entry=None, at=None, block=None):
        item = QListWidgetItem(text)
        item.setData(ENTRY_ROLE, entry)
        item.setData(KIND_ROLE, kind)
        item.setData(BLOCK_ROLE, self._block if block is None else block)
        if kind != FIGHT:
            item.setFlags(Qt.NoItemFlags)
        self._style(item)
        if at is None:
            self.addItem(item)
        else:
            self.insertItem(at, item)

    # ---- looking up ----

    def entry_at(self, row):
        """The fight on *row*; None for a header or result row, or none."""
        item = self.item(row) if row is not None and row >= 0 else None
        return item.data(ENTRY_ROLE) if item is not None else None

    def current_entry(self):
        return self.entry_at(self.currentRow())

    def row_of(self, entry):
        """*entry*'s row, looked for from the end; None when not listed."""
        for row in range(self.count() - 1, -1, -1):
            if self.item(row).data(ENTRY_ROLE) is entry:
                return row
        return None

    def _fight_rows(self) -> list:
        return [row for row in range(self.count())
                if self.item(row).data(KIND_ROLE) == FIGHT]

    def fight_count(self) -> int:
        return len(self._fight_rows())

    def fight_item(self, index):
        """The row item of the *index*-th fight (0 first), or None."""
        rows = self._fight_rows()
        return self.item(rows[index]) if -len(rows) <= index < len(rows) else None

    def select_fight(self, index):
        """Make the *index*-th fight (0 first, -1 last) current."""
        rows = self._fight_rows()
        if -len(rows) <= index < len(rows):
            self.setCurrentRow(rows[index])

    def select_entry(self, entry):
        row = self.row_of(entry)
        if row is not None:
            self.setCurrentRow(row)

    def current_fight_index(self) -> int:
        """The current fight's place among the fights, -1 for none."""
        rows = self._fight_rows()
        row = self.currentRow()
        return rows.index(row) if row in rows else -1

    # ---- keys ----

    def moveCursor(self, action, modifiers):
        """Qt's own move, then on to the nearest fight when it lands on a
        header or result row: the arrows skip them already, Home, End and
        the page keys do not. A key that moves up looks up first."""
        index = super().moveCursor(action, modifiers)
        if not index.isValid() or index.flags() & Qt.ItemIsEnabled:
            return index
        up = action in (QAbstractItemView.MoveUp, QAbstractItemView.MovePrevious,
                        QAbstractItemView.MovePageUp, QAbstractItemView.MoveHome)
        row = index.row()
        for step in ((-1, 1) if up else (1, -1)):
            near = row + step
            while 0 <= near < self.count():
                if self.item(near).data(KIND_ROLE) == FIGHT:
                    return self.model().index(near, 0)
                near += step
        return self.currentIndex()

    # ---- look ----

    def _style(self, item):
        palette = self.palette()
        if item.data(BLOCK_ROLE) % 2:
            item.setBackground(QBrush(band_color(palette.color(QPalette.Base),
                                                 palette.color(QPalette.Text))))
        else:
            item.setBackground(QBrush())
        if item.data(KIND_ROLE) != FIGHT:
            # Not greyed out as a disabled row would be
            item.setForeground(QBrush(palette.color(QPalette.Text)))
        if item.data(KIND_ROLE) == HEADER:
            font = QFont(self.font())
            font.setBold(True)
            item.setFont(font)

    def restyle(self):
        for row in range(self.count()):
            self._style(self.item(row))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.PaletteChange, QEvent.FontChange):
            self.restyle()
