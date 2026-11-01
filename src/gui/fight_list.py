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

The (i) on a fight row (issue #147): hovering it shows who in that fight
has a possible build issue and what (fight_render.fight_issues_tooltip),
so a session's flagged fights can be read without selecting each one and
looking for the marks on the pane's rows. The row is plain text, so the
mark has no anchor of its own: viewportEvent takes the ToolTip event and
works out where the mark is drawn (issues_mark_rect), the way the style
lays the row out: the style's text rectangle, the margin every style keeps
inside it, then the width of the text before the mark. The text rectangle
matters: Windows 11's style starts it 6 px in, leaving room for its
selection bar, where Fusion and windowsvista start at the row's edge
(measured 2026-10-31 on all three and offscreen, the mark's first painted
column within a pixel of the computed one). The pointer gets MARK_SLACK
pixels either side, and the tooltip closes once it leaves that band. The
rest of a row shows no tooltip, as before. The text is built at hover
time from the hovered row's own fight, usually not the one on screen,
with the window's Hide names switch (hide_names), so it follows the switch
without a rebuild. A screen reader hears the mark as the
row's description (fight_render.issues_description), which names nobody.

Kill or wipe (issues #168 and #169, pull_outcome): a boss fight's row
carries its verdict after the boss ('Wipe 62%'), including what only the
fights after it can tell ('Cut', 'group went on'), which the engine puts
on the pull and sends the fight again for, so the row, the pane and the
copy always agree. A boss's pulls in a row get an inert run row under the
last of them ('Lord Falgravn: 13 pulls, best 48%, 9 wipes at 80 to
90%'), above the run's result row when it ended a trial; hovering it
adds the first death of each pull, the killers and the players longest
dead, names through the Hide names switch. Each new or updated fight
redoes its block's run rows (_refresh_runs) from the block's own rows,
so a run row moves down as the run grows and a refresh never walks the
whole list.
"""

from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyleOptionViewItem,
    QToolTip,
)

from gui.fight_render import (
    ISSUES_LIST_CUE,
    fight_issues_tooltip,
    issues_description,
    summary_line,
)
from gui.name_mask import NameMask
from pull_outcome import run_details, run_summary, runs
from trial_result import result_text

# Item data: the fight's FightHistoryEntry (None on a header or result
# row), the row's kind, the block's number, and on a run row the run
# (pull_outcome.runs)
ENTRY_ROLE = Qt.UserRole
KIND_ROLE = Qt.UserRole + 1
BLOCK_ROLE = Qt.UserRole + 2
RUN_ROLE = Qt.UserRole + 3

HEADER, FIGHT, RESULT, RUN = "header", "fight", "result", "run"

# How far a band's background is from the list's base colour, towards its
# text colour
BAND_MIX = 0.07

# Pixels either side of the (i) that still count as over it
MARK_SLACK = 3

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


def run_tooltip(run, hide_names: bool = False) -> str:
    """A run row's hover text: its summary and the details under it."""
    entries = [fight for pull in run for fight in pull]
    names = NameMask.for_entries(entries, hide_names)
    return "\n".join([run_summary(run)] + run_details(run, names))


def run_description(run) -> str:
    """What a screen reader hears for a run row: the summary, the first
    deaths and the killers, naming no player."""
    entries = [fight for pull in run for fight in pull]
    lines = [run_summary(run)] + run_details(run, NameMask.for_entries(entries, True))
    return ". ".join(line for line in lines if not line.startswith("Most time dead"))


def result_row_text(entry) -> str:
    """The result row's text, with a cue when the run's score banner was
    captured from the screen (issue #167)."""
    text = result_text(entry.trial_result)
    return f"{text} · banner" if getattr(entry, "banner_path", None) else text


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
        # Each block's fight rows and run rows, so a block's run rows are
        # redone without a pass over the whole list
        self._block_items: dict[int, list] = {}
        self._block_runs: dict[int, list] = {}
        self._batch = False  # set_fights: one refresh per block at the end
        # The window's Hide names switch, for the (i)'s hover text. A flag,
        # not the window's _names_for: a bound method kept here would tie
        # the window and the list in a reference cycle
        self.hide_names = False
        self.current_tooltip = ""  # the hover text last shown, for tests

    # ---- building ----

    def clear(self):
        super().clear()
        self._last_entry = None
        self._block = -1
        self._block_items = {}
        self._block_runs = {}

    def set_fights(self, fights):
        """Every row anew for *fights*; none is made current."""
        self.clear()
        self._batch = True
        try:
            for entry in fights:
                self.add_fight(entry)
        finally:
            self._batch = False
        for block in self._block_items:
            self._refresh_runs(block)

    def add_fight(self, entry) -> int:
        """Add *entry* under the last fight, with a header when it opens a
        block and its result row when it completed a run; its row."""
        if starts_block(self._last_entry, entry):
            self._block += 1
            self._add_row(HEADER, header_text(entry))
        self._last_entry = entry
        item = self._add_row(FIGHT, summary_line(entry, death_cue=True, issue_cue=True,
                                                 zone=False), entry)
        if getattr(entry, "trial_result", None):
            self._add_row(RESULT, result_row_text(entry))
        self._block_items.setdefault(self._block, []).append(item)
        if not self._batch:
            # A run row above it can move down under it
            self._refresh_runs(self._block)
        return self.row(item)

    def update_fight(self, entry):
        """Rewrite *entry*'s row (a late death, a fight the game cut in
        two) and add its result row when the run's result came after it
        was listed; its row, or None when the list does not hold it. The
        engine updates only its newest fight, so a result row never lands
        between two fights of a block."""
        row = self.row_of(entry)
        if row is None:
            return None
        block = self.item(row).data(BLOCK_ROLE)
        self.item(row).setText(summary_line(entry, death_cue=True, issue_cue=True, zone=False))
        self.item(row).setData(Qt.AccessibleDescriptionRole, issues_description(entry))
        result = getattr(entry, "trial_result", None)
        if result:
            # Under the fight, past a run row that may sit there
            below = row + 1
            while self.item(below) is not None and self.item(below).data(KIND_ROLE) == RUN:
                below += 1
            item = self.item(below)
            if item is not None and item.data(KIND_ROLE) == RESULT:
                item.setText(result_row_text(entry))
            else:
                self._add_row(RESULT, result_row_text(entry), at=below, block=block)
        self._refresh_runs(block)
        return self.row_of(entry)

    def _add_row(self, kind, text, entry=None, at=None, block=None):
        item = QListWidgetItem(text)
        item.setData(ENTRY_ROLE, entry)
        item.setData(KIND_ROLE, kind)
        item.setData(BLOCK_ROLE, self._block if block is None else block)
        if kind == FIGHT:
            item.setData(Qt.AccessibleDescriptionRole, issues_description(entry))
        else:
            item.setFlags(Qt.NoItemFlags)
        self._style(item)
        if at is None:
            self.addItem(item)
        else:
            self.insertItem(at, item)
        return item

    def _refresh_runs(self, block):
        """The block's run rows anew, each straight under its run's last
        fight (pull_outcome.runs). The words a fight row owes to later
        fights ('Cut', 'group went on') are on its pull, set by the engine,
        which sends the fight again when they change."""
        items = self._block_items.get(block) or []
        for item in self._block_runs.pop(block, []):
            row = self.row(item)
            if row >= 0:
                self.takeItem(row)
        by_entry = {id(item.data(ENTRY_ROLE)): item for item in items}
        made = []
        for run in runs([item.data(ENTRY_ROLE) for item in items]):
            if len(run) < 2:
                continue
            last = by_entry.get(id(run[-1][-1]))
            if last is None:
                continue
            item = self._add_row(RUN, run_summary(run), at=self.row(last) + 1, block=block)
            item.setData(RUN_ROLE, run)
            item.setData(Qt.AccessibleDescriptionRole, run_description(run))
            made.append(item)
        if made:
            self._block_runs[block] = made

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

    # ---- the (i)'s hover text ----

    def issues_mark_rect(self, row):
        """Where *row*'s (i) is drawn, in viewport coordinates; None on a
        row without one (see the module). A list narrower than its text
        scrolls sideways rather than cutting rows short, and the item's
        rectangle carries the scroll."""
        item = self.item(row) if row is not None and row >= 0 else None
        if item is None or item.data(KIND_ROLE) != FIGHT:
            return None
        text = item.text()
        at = text.find(ISSUES_LIST_CUE)
        if at < 0:
            return None
        option = QStyleOptionViewItem()
        self.initViewItemOption(option)
        option.rect = self.visualItemRect(item)
        self.itemDelegate().initStyleOption(option, self.indexFromItem(item))
        style = self.style()
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, option, self)
        margin = style.pixelMetric(QStyle.PM_FocusFrameHMargin, None, self) + 1
        left = text_rect.left() + margin + option.fontMetrics.horizontalAdvance(text[:at])
        return QRect(left, option.rect.top(),
                     option.fontMetrics.horizontalAdvance(ISSUES_LIST_CUE), option.rect.height())

    def viewportEvent(self, event):
        """The (i)'s hover text over a fight row's mark, nothing anywhere
        else: the rows carry no tooltip of their own (see the module)."""
        if event.type() != QEvent.ToolTip:
            return super().viewportEvent(event)
        pos = event.pos()
        item = self.itemAt(pos)
        row = self.row(item) if item is not None else -1
        mark = self.issues_mark_rect(row)
        band = mark.adjusted(-MARK_SLACK, 0, MARK_SLACK, 0) if mark is not None else None
        text = ""
        if band is not None and band.contains(pos):
            entry = self.entry_at(row)
            text = fight_issues_tooltip(entry, NameMask.for_entry(entry, self.hide_names))
        elif item is not None and item.data(KIND_ROLE) == RUN:
            # A run row: its summary, the first deaths, the killers and
            # who spent longest dead (pull_outcome)
            band = self.visualItemRect(item)
            text = run_tooltip(item.data(RUN_ROLE), self.hide_names)
        self.current_tooltip = text
        if text:
            QToolTip.showText(event.globalPos(), text, self.viewport(), band)
        else:
            QToolTip.hideText()
        return True

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
        elif item.data(KIND_ROLE) == RUN:
            font = QFont(self.font())
            font.setItalic(True)
            item.setFont(font)

    def restyle(self):
        for row in range(self.count()):
            self._style(self.item(row))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.PaletteChange, QEvent.FontChange):
            self.restyle()
