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

The instance (issue #196): a click on a header, run or result row opens
the window's Instance tab on that row's block (instance_requested,
instance_of), a run row's at that boss. The rows stay inert, so the
current row is always a fight and every caller of current_entry() still
gets one. Qt 6.12 sends itemClicked for an inert row, but does not
promise to, so the list tells the click itself: the row the left button
went down on, and its release on that same row (mouseReleaseEvent); a
drag to another row, or another button, opens nothing, nor does the
double-click a click on an inert row begins: Qt makes it a second press,
which opened the instance again, or, the first click having selected a
fight and scrolled the list, selected whatever fight came under the
pointer. The rows show they can be clicked with the pointing hand, set
again as rows move under a pointer that does not (a scroll, a fight
coming in), once the rows have moved, and
the hover line INSTANCE_CUE, which a run row's hover text ends with; a
screen reader hears INSTANCE_DESCRIPTION as their description, after a
run row's own.
"""

from PySide6.QtCore import QEvent, QModelIndex, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyleOptionViewItem,
    QToolTip,
)

from fight_blocks import header_text, starts_block
from fight_index import fmt_dps, run_best_kill
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

# A header, run or result row's hover line, and what a screen reader hears
# for it: a click on one opens the Instance tab (issue #196)
INSTANCE_CUE = "Click for the instance (Alt+I)"
INSTANCE_DESCRIPTION = "Alt+I opens the instance"

def run_text(run, index=None) -> str:
    """A run row's line: the run's summary, and the best earlier kill of
    the boss with this roster from the fight history when there is one
    (fight_index.run_best_kill, issue #170)."""
    text = run_summary(run)
    best = run_best_kill(index, run)
    if best:
        text += f", best kill with this roster {fmt_dps(best)}"
    return text


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

    # A click on a header, run or result row: its row, whose instance the
    # window shows (instance_of, issue #196)
    instance_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Fights")
        # The inert row a button last went down on, for the left button's
        # release; and whether the pointer shows the hand over one (see the
        # module), for which the viewport follows the pointer with no button
        # down
        self._pressed = None
        self._hand = False
        # Whether the last click opened an instance: a double-click it
        # begins is the same gesture (mouseDoubleClickEvent)
        self._opened = False
        self.viewport().setMouseTracking(True)
        # The hand is set again once rows have moved under a pointer that did
        # not, after the batch, on a timer the list owns: once per row added,
        # the look-up laid the whole list out again, and filling the list
        # took the square of its length, 15.7 s for a 915-fight review
        # against 0.14 (the fresh review of PR #208)
        self._hand_check = QTimer(self)
        self._hand_check.setSingleShot(True)
        self._hand_check.setInterval(0)
        self._hand_check.timeout.connect(self._recheck_hand)
        self.verticalScrollBar().valueChanged.connect(self._check_hand_later)
        self.model().rowsInserted.connect(self._check_hand_later)
        self.model().rowsRemoved.connect(self._check_hand_later)
        self._last_entry = None  # the newest fight, for the next one's block
        self._block = -1
        # Each block's fight rows and run rows, so a block's run rows are
        # redone without a pass over the whole list
        self._block_items: dict[int, list] = {}
        self._block_runs: dict[int, list] = {}
        self._batch = False  # set_fights: one refresh per block at the end
        # The fight history (fight_index.FightIndex, issue #170) the run
        # rows read their best earlier kill from: plain Python, no Qt, and
        # no reference back to the window; None without one
        self.history_index = None
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
            item.setData(Qt.AccessibleDescriptionRole, INSTANCE_DESCRIPTION)
        self._style(item)
        if at is None:
            self.addItem(item)
        else:
            self.insertItem(at, item)
        return item

    def refresh_all_runs(self):
        """Every block's run rows anew (after the fight history grew)."""
        for block in list(self._block_items):
            self._refresh_runs(block)

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
            item = self._add_row(RUN, run_text(run, self.history_index), at=self.row(last) + 1,
                                 block=block)
            item.setData(RUN_ROLE, run)
            item.setData(Qt.AccessibleDescriptionRole,
                         f"{run_description(run)}. {INSTANCE_DESCRIPTION}")
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

    def block_of(self, entry) -> list:
        """The fights of *entry*'s block, in order; [] when it is not
        listed."""
        row = self.row_of(entry)
        if row is None:
            return []
        items = self._block_items.get(self.item(row).data(BLOCK_ROLE)) or []
        return [item.data(ENTRY_ROLE) for item in items]

    def instance_of(self, row, shown=None):
        """What a click on the header, run or result row *row* opens on the
        Instance tab (issue #196), as (the fight to select, the run to open
        the page at); the run is None for the page's top, and the whole is
        None for a fight row or no row. The fight on screen, *shown*, stays
        when it is in the row's block, or for a run row in its run; else it
        is the block's last fight, which a result row's fight is (a block
        ends at a completed run), or the run's last pull."""
        item = self.item(row) if row is not None and row >= 0 else None
        if item is None or item.data(KIND_ROLE) == FIGHT:
            return None
        if item.data(KIND_ROLE) == RUN:
            run = item.data(RUN_ROLE)
            fights = [fight for pull in run for fight in pull]
            return (shown if any(fight is shown for fight in fights) else fights[-1]), run
        fights = [each.data(ENTRY_ROLE)
                  for each in self._block_items.get(item.data(BLOCK_ROLE)) or []]
        if not fights:
            return None
        return (shown if any(fight is shown for fight in fights) else fights[-1]), None

    # ---- keys ----

    def moveCursor(self, action, modifiers):
        """Qt's own move, then on to the nearest fight when it lands on a
        header or result row: the arrows skip them already, Home, End and
        the page keys do not. A key that moves up looks up first.

        With no fight current, as through a Settings replay until its
        fights are in (MainWindow._on_monitoring_restarting), Qt starts
        every key at the first fight, and End took a reader following the
        live log to the oldest. End, the page keys and the keys that move
        up go to the newest instead; Home, Down and Next keep the first."""
        if not self.currentIndex().isValid() and action in (
                QAbstractItemView.MoveEnd, QAbstractItemView.MovePageDown,
                QAbstractItemView.MoveUp, QAbstractItemView.MovePrevious,
                QAbstractItemView.MovePageUp):
            rows = self._fight_rows()
            if rows:
                return self.model().index(rows[-1], 0)
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

    # ---- the instance (issue #196) ----

    def _inert_at(self, pos):
        """The header, run or result row at *pos* in the viewport, or None."""
        item = self.itemAt(pos)
        return item if item is not None and item.data(KIND_ROLE) != FIGHT else None

    def mousePressEvent(self, event):
        # The inert row the button went down on, for its release: a click of
        # its own, which no double-click follows yet
        self._pressed = self._inert_at(event.position().toPoint())
        self._opened = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """The left button let go over the inert row it went down on: that
        row's instance (see the module)."""
        pressed, self._pressed = self._pressed, None
        super().mouseReleaseEvent(event)
        if (pressed is not None and event.button() == Qt.LeftButton
                and self._inert_at(event.position().toPoint()) is pressed):
            self._opened = True
            self.instance_requested.emit(self.row(pressed))

    def mouseDoubleClickEvent(self, event):
        # The double-click a click on an inert row began is that click's
        # (see the module): it opens nothing more and selects nothing
        if self._opened or self._inert_at(event.position().toPoint()) is not None:
            self._pressed = None
            self._opened = False
            return
        super().mouseDoubleClickEvent(event)

    def _set_hand(self, pos):
        """The pointing hand while the pointer, at *pos* in the viewport, is
        over an inert row, which a click opens."""
        hand = self._inert_at(pos) is not None
        if hand != self._hand:
            self._hand = hand
            if hand:
                self.viewport().setCursor(Qt.PointingHandCursor)
            else:
                self.viewport().unsetCursor()

    def mouseMoveEvent(self, event):
        self._set_hand(event.position().toPoint())
        super().mouseMoveEvent(event)

    def _check_hand_later(self, *_):
        self._hand_check.start()

    def _recheck_hand(self):
        # The rows moved under a pointer that did not
        self._set_hand(self.viewport().mapFromGlobal(QCursor.pos()))

    def focusInEvent(self, event):
        """Taking the focus never makes a fight current. Qt makes the first
        row current when a list with none takes the focus, unless a current
        index was set since its model was last reset (the view's private
        currentIndexSet, probed on PySide6 6.12), so none is set first,
        whatever emptied or reset the list. Otherwise an Alt+Tab back
        during a Settings replay would pick the oldest fight for the reader
        (MainWindow._on_monitoring_restarting, issue #196)."""
        if not self.currentIndex().isValid():
            self.setCurrentIndex(QModelIndex())
        super().focusInEvent(event)

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
        """The (i)'s hover text over a fight row's mark, a run row's over
        the row, and INSTANCE_CUE over a header or result row; nothing
        anywhere else: the rows carry no tooltip of their own (see the
        module)."""
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
            # who spent longest dead (pull_outcome), and what a click opens
            band = self.visualItemRect(item)
            text = f"{run_tooltip(item.data(RUN_ROLE), self.hide_names)}\n{INSTANCE_CUE}"
        elif item is not None and item.data(KIND_ROLE) != FIGHT:
            band = self.visualItemRect(item)  # a header or result row
            text = INSTANCE_CUE
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
