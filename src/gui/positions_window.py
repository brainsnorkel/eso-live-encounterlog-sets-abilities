"""
The positions window (issue #214): one fight paused at a moment, where
everyone stood, with their health, opened from a death (and later from an
event) of the fight.

Design: One window, re-used, beside the main window, as the player window
is (a QDialog child of it, never deleted before it, hidden by Esc): it
keeps the fight it was opened for while the list moves on, and it has
room the main window's tabs do not. Its parts, top to bottom: the fight
and the moment ('Lord Falgravn · Kyne's Aegis VET · Kill · 1:50.0 of
5:16'), Show in list; each boss's health at the moment; the canvas
(positions_canvas) beside a table of the same units in a splitter, the
line under the canvas naming who is not drawn ('Not on this map: 6, 11');
the controls (previous death, a second back, the moment's clock, a second
on, next death, Show); and the scrub bar. Decided for #214: paused
moments only (no playback, no animation, no casts yet), players, bosses
and adds drawn, pets, companions, unannounced and other units each one
toggle away in Show.

What it draws comes from two places. The fight entry gives the numbers,
the roles and the deaths: a player's number is the place of their row in
the fight table (companion rows skipped), worked out afresh each time the
fight changes in place, since the engine can re-rank the rows; a death's
moment is the locator's start plus the recap's time into the fight, in
the log's own clock (ms since BEGIN_LOG). The states come from re-reading
the fight from disk (fight_reread), which the main window runs on its own
thread and hands in through reread_done; the window never reads a file or
starts a thread. It holds the states while shown: a 12-player boss
fight's are a median 609 KB and 2.2 MB at most (fight_reread), dropped on
hide (Esc gives a dialog no close event, only a hide) and read again at
the next open, 95 ms at the median.

Which states it takes. It asks for its fight's locator (wanted_locator)
and drops any answer for another: a request the runner superseded still
reports, as 'cancelled', with its old locator. Only a fight the game cut
in two that then went on replaces its entry's locator (every other change
in place leaves the same object: test_fight_locator), and then the window
shows "Reading the fight's lines…" until the new states come. It follows
the new locator when its coalesced redraw runs, the event loop's next
turn, so the main window may compare entry.locator with wanted_locator
before or after it calls entry_updated; and an answer for the entry's new
locator that comes before that turn is taken too. After a Settings
replay rebuilt the entry it keeps the states when the new locator equals
theirs, as a replay of the same log makes it.

The bosses. The game removes some bosses and adds them again, each time
as a new unit with a track of its own: Z'Maja between her phases (three
units in one 5:10 Cloudrest pull), Cloudrest's shades, Halls of
Fabrication's Hunter-Killers at a reset. The canvas draws only the units
present, but the boss bars, the description and the line under the canvas
read every unit, and gave one boss three healths at once ('Z'Maja 56%.
Z'Maja 30%. Z'Maja not in the log yet.', the 56% of a unit that had left a
minute before). They take the bosses from boss_rows: by name, the units
present; else the one that left last, as 'left'; 'not in the log yet'
only while no unit of the name has come. The table keeps every unit, each
with its State.

The table is the reader's surface and the keyboard's. A painted canvas
is a blank to a screen reader (its accessible name, 'Positions', and a
one-line description of the moment in numbers are all it has), while a
QTableView over a model reads as a real table, rows and cells, and a
hidden name cell reads 'hidden name' through Qt.AccessibleTextRole rather
than '@' and shade blocks (measured: build/positions214/paint). Its rows
are the numbered players in number order, then players with no row (no
build in the log, not grouped), then the bosses; a click on a marker
selects its row and a row selects its marker, Enter or a double-click on a
player opens the player window (player_requested). Its rows grow with the
text size: a QTableView keeps 30 px rows at 100%, 150% and 200% text
while the line grows to 16, 24 and 32 px, but sized to their contents
with no word wrap they are 20, 28 and 36 px (probed). They are sized once
for each text size and each new set of rows, not at each step: sized to
contents, the header asked every cell for its size whenever the moment
changed, 936 calls a step and 12 ms of it (profiled over Lord Falgravn's
331 seconds); a step now costs 0.5 to 1.6 ms (positions_canvas has the
measures).

Keys. A window shortcut on a bare key takes it from a focused table (all
21 keys probed), so the window binds modified keys only: Ctrl+Left and
Ctrl+Right step a second, with Shift a tenth; Ctrl+PgUp and Ctrl+PgDn go
to the previous and next death; Ctrl+Up and Ctrl+Down to the previous and
next unit, as they change the player in the player window; Ctrl+C copies
the moment in words, names through the mask. Ctrl+H and the text size
keys are the main window's, application-wide, and never bound here: a
second binding makes both ambiguous and neither fires (probed on Ctrl+0).
The bare keys belong to the focused scrub bar: Left and Right, Shift, Home
and End, PgUp and PgDn. The buttons are QToolButtons: a QPushButton in a
dialog takes Enter even with the focus elsewhere (probed). Tab goes from
the scrub bar to the table to the buttons.

Hide names. The main window hands the window the mask of its fight
(NameMask.for_entry, from the entry's player_names). The window extends it
with the players of the locator's unit table, keeping the logging
player's names and hiding every other player's name and character name:
a player who left during the 10 s lead-in is in that table, read before
the roster drops them, but not in player_names. Bosses, adds and pets are
never hidden. On the canvas a hidden name is drawn as '@' and its
pixelated stand-in, as the pages draw it.

It holds no reference to the main window and stores no lambda on a child;
its only timer is its own single-shot 0 ms redraw, which draws a burst of
updates to the fight once.
"""

from __future__ import annotations

import re
from itertools import pairwise

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QItemSelectionModel,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QPalette,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QSizePolicy,
    QSplitter,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from companions import ANON
from fight_locator import LEAD_MS, SELF, TAIL_MS
from gui import text_size
from gui.fight_render import ROLE_NAMES
from gui.name_mask import NO_MASK, NameMask
from gui.positions_canvas import (
    DEAD,
    EMPTY_ROSTER,
    LEFT,
    LOST,
    MARK_ADD,
    MARK_BOSS,
    MARK_COMPANION,
    MARK_LOOSE,
    MARK_OTHER,
    MARK_PET,
    MARK_PLAYER,
    MARK_UNKNOWN,
    NOT_YET,
    OFF_MAP,
    OTHER_MAP,
    PLAYER_KINDS,
    SHOWN_BY_DEFAULT,
    STALE,
    BossBars,
    PositionsCanvas,
    ScrubBar,
    age_words,
    build_scene,
    fit_boxes,
    is_dark,
    map_change_times,
    marker_icon,
    roster_of,
    share_text,
    unit_key_of,
)
from gui.text_size import scaled_px
from pull_outcome import clock, outcome_text

TITLE = "Positions"
READING = "Reading the fight's lines…"
MISSING = "This fight's lines are no longer on disk"
FAILED = "This fight's lines could not be read"
NO_LOCATOR = "Where this fight's lines are in its log is not known, so its positions cannot be shown."
REPLAYED_NOTE = ("From before Settings replayed the session: this fight is not in the "
                 "replay, so it is shown as it was.")
SHOW_IN_LIST_LABEL = "Show in list"
SHOW_IN_LIST_TIP = "Select this fight in the fight list"
NOT_LISTED_TIP = "This fight is not in the list now"
HIDDEN_NAME = "hidden name"  # what a reader hears for a name Hide names hides
DEFAULT_SIZE = (1120, 760)
# The Show menu: the marks it turns on and off, in its order, with their
# words
SHOW_ITEMS = ((MARK_ADD, "Adds"), (MARK_PET, "Pets"), (MARK_COMPANION, "Companions"),
              (MARK_UNKNOWN, "Unannounced units"), (MARK_OTHER, "Other units"))
SHOW_TIPS = {MARK_ADD: "Hostile units other than the bosses",
             MARK_PET: "Players' pets",
             MARK_COMPANION: "Companions",
             MARK_UNKNOWN: "Units the log never announced: anchors, hazards, objects",
             MARK_OTHER: "Units neither hostile nor a player's: NPCs, invisible targets"}

# The table's columns
# The table's columns: who, their health and their state first, where a
# narrow table still shows them (the number's picture shows the role's
# shape; the Role column says it in words)
COLUMNS = ("#", "Name", "Health", "State", "Role", "Shield", "Ult", "Magicka", "Stamina")
(NUMBER_COL, NAME_COL, HEALTH_COL, STATE_COL, ROLE_COL, SHIELD_COL, ULT_COL, MAGICKA_COL,
 STAMINA_COL) = range(len(COLUMNS))
POOL_COLUMNS = (MAGICKA_COL, STAMINA_COL)
# Above this share of the system font the table goes compact: no magicka
# and stamina columns, the health as a share alone. Measured offscreen
# with Segoe UI 9 (build/positions214/window/probe_table_widths_out.txt):
# all nine columns take 573 px at 100% text and 877 at 150%; compact at
# 200%, seven take 891, the number, name, health and state 623 of the 687
# the table first gets in a 1280x648 window (a 1280x720 screen less a
# taskbar and a title bar), the canvas keeping 565x348
POOLS_UP_TO = 1.5
# The table's first share of the window, at most
TABLE_SHARE = 0.55
# The widest text each column is sized for, so stepping the moment never
# moves the columns
TEMPLATES = {NUMBER_COL: "99", ROLE_COL: "Healer", HEALTH_COL: "100% 99,999",
             SHIELD_COL: "99,999", MAGICKA_COL: "99,999", STAMINA_COL: "99,999", ULT_COL: "500",
             STATE_COL: "dead, not on this map"}
COMPACT_HEALTH = "100%"  # the health column's widest text, compact
_NUMERIC = (NUMBER_COL, HEALTH_COL, SHIELD_COL, MAGICKA_COL, STAMINA_COL, ULT_COL)
# The roles the model answers, as plain ints: a table asks for several of
# each cell at every paint, and comparing PySide6's enums cost 10 us a
# call (profiled: 3.1 of 4.3 s over a fight's 331 steps)
_DISPLAY, _ACCESSIBLE, _DECORATION, _ALIGNMENT, _TOOLTIP = (
    int(role.value) for role in (Qt.DisplayRole, Qt.AccessibleTextRole, Qt.DecorationRole,
                                 Qt.TextAlignmentRole, Qt.ToolTipRole))
_RIGHT = int((Qt.AlignRight | Qt.AlignVCenter).value)
_TABLE_MARKS = (MARK_PLAYER, MARK_LOOSE, MARK_BOSS)


# ------------------------------------------------------------- the words --

def fight_clock(ms_into: int) -> str:
    """A moment in the fight, to the tenth: '1:50.0', '-0:03.0' in the
    lead-in."""
    tenths = round(abs(int(ms_into)) / 100)
    minutes, rest = divmod(tenths, 600)
    return f"{'-' if ms_into < 0 and tenths else ''}{minutes}:{rest // 10:02d}.{rest % 10}"


def moment_words(t: int, start: int, end: int) -> str:
    """'1:50.0 into the fight', '3.0 s before the fight began', or '5:16.4
    into the fight, after its end'."""
    if t < start:
        return f"{(start - t) / 1000:.1f} s before the fight began"
    words = f"{fight_clock(t - start)} into the fight"
    return f"{words}, after its end" if t > end else words


def header_line(entry, t: int | None = None) -> str:
    """'Lord Falgravn · Kyne's Aegis VET · Kill · 1:50.0 of 5:16 ·
    2026-10-15 19:30:07': the fight, the moment *t* (ms into it) of its
    length, and its start, dated for a fight from an older log."""
    boss = str(getattr(entry, "boss_name", "") or "")
    zone = str(getattr(entry, "zone_name", "") or "")
    if zone and getattr(entry, "is_vet", False):
        zone += " VET"
    length = clock(getattr(entry, "duration_s", 0))
    moment = f"{fight_clock(t)} of {length}" if t is not None else length
    parts = (boss, zone, outcome_text(getattr(entry, "pull", None), boss), moment,
             str(getattr(entry, "timestamp", "") or ""))
    return " · ".join(part for part in parts if part)


# A path's folders: from a drive, a UNC share or a root, folder by folder
# (spaces and apostrophes allowed, as in 'Home PC' and "Kim O'Neil"),
# never past a ';', ':' or a double quote; a folder ends in a slash, so a
# quote closing a file name is never taken
_FOLDERS = re.compile(r"(?:[A-Za-z]:[\\/]+|\\\\|(?<![\w.])/)(?:[^\\/\r\n;:\"]*[\\/]+)*")


def _counted(names: list) -> list:
    """*names* in first-seen order, a repeated one once with its count
    ('Reef Guardian ×2'): a boss the game splits into copies would
    otherwise wrap the line under the canvas past the 200% budget."""
    counts: dict = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    return [name if n == 1 else f"{name} ×{n}" for name, n in counts.items()]


def file_names_only(text: str) -> str:
    """*text* with every path cut to its file name: folders name the
    Windows user, and the window shows no path."""
    return _FOLDERS.sub("", str(text or ""))


def window_mask(names, locator) -> NameMask:
    """The window's own Hide names mask (see the module): *names*, the
    main window's for the fight, with the locator's players added, the
    logging player's names kept and every other player's hidden."""
    names = names or NO_MASK
    if not names.active or locator is None:
        return names
    keep = set(getattr(names, "_keep", ()))
    hidden = set(getattr(names, "_hidden", ()))
    for unit in locator.units:
        if unit.kind not in PLAYER_KINDS:
            continue
        both = {str(unit.name or ""), str(unit.character or "")} - {"", ANON}
        if unit.kind == SELF:
            keep |= both
        else:
            hidden |= both
    return NameMask(True, keep, hidden - keep)


def health_text(state, compact: bool = False) -> str:
    """'42% 8,664'; a boss's millions short, '80% 99.8M'; '42%' alone
    when *compact*; '' when not known."""
    if state is None or state.health_max <= 0:
        return ""
    share = share_text(state.health, state.health_max)
    if state.health <= 0 or compact:
        return share
    if state.health < 100_000:
        value = f"{state.health:,}"
    else:
        millions = state.health / 1_000_000
        value = f"{millions:.2f}M" if millions < 10 else f"{millions:.1f}M"
    return f"{share} {value}"


def state_text(unit) -> str:
    """The State cell: 'alive', 'dead', 'last seen 12 s ago'
    (positions_canvas.age_words), 'not on this map' ('dead, not on this
    map'), 'left' or 'not in the log yet'."""
    if unit.where == NOT_YET or unit.state is None:
        return "not in the log yet"
    if unit.where == LEFT:
        return "left"
    if unit.where in (OTHER_MAP, OFF_MAP):
        return "dead, not on this map" if unit.look == DEAD else "not on this map"
    if unit.look == DEAD:
        return "dead"
    if unit.look in (STALE, LOST):
        return age_words(unit)
    return "alive"


def cell_text(unit, column: int, names=NO_MASK, compact: bool = False) -> str:
    """A table cell's text (names through the Hide names mask; *compact*:
    the health as a share alone)."""
    state = unit.state
    if column == NUMBER_COL:
        return "" if unit.number is None else str(unit.number)
    if column == ROLE_COL:
        return "Boss" if unit.mark == MARK_BOSS else ROLE_NAMES.get(unit.role, "")
    if column == NAME_COL:
        return names.text(unit.name) if unit.mark != MARK_BOSS else unit.name
    if column == HEALTH_COL:
        return health_text(state, compact)
    if column == STATE_COL:
        return state_text(unit)
    if state is None:
        return ""
    if column == SHIELD_COL:
        return f"{state.shield:,}" if state.shield > 0 else ""
    if column == MAGICKA_COL:
        return f"{state.magicka:,}" if state.magicka_max > 0 else ""
    if column == STAMINA_COL:
        return f"{state.stamina:,}" if state.stamina_max > 0 else ""
    if column == ULT_COL:
        return str(state.ultimate) if unit.mark != MARK_BOSS else ""
    return ""


def compact() -> bool:
    """Whether the table is compact at the text size in force
    (POOLS_UP_TO)."""
    return text_size.scale() > POOLS_UP_TO


def boss_rows(units) -> list:
    """The bosses of the moment as the boss bars, the description, Ctrl+C
    and the line under the canvas give them (see the module): by name, in
    the order the units come, every unit of a name with a state that has
    not left, so two of one name present together both stay; if none, the
    one that left last, which reads 'left'; a unit with no state, 'not in
    the log yet', only when no unit of its name has one."""
    groups: dict = {}
    for unit in units:
        if unit.mark == MARK_BOSS:
            groups.setdefault(unit.name, []).append(unit)
    rows = []
    for same in groups.values():
        here = [unit for unit in same if unit.state is not None and unit.where != LEFT]
        gone = [unit for unit in same if unit.state is not None]
        if here:
            rows += here
        else:
            rows.append(max(gone, key=lambda unit: unit.state.t) if gone else same[0])
    return rows


def boss_bar(unit) -> tuple:
    """A boss of boss_rows as a row of the boss bars (BossBars)."""
    if unit.state is None:
        return (unit.name, 0, 0, False)
    if unit.where == LEFT:
        return (unit.name, 0, 0, LEFT)
    return (unit.name, unit.state.health, unit.state.health_max, True)


def moment_summary(scene, start: int, end: int) -> str:
    """The moment in one line, in numbers, never names: '1:50.0 into the
    fight. Lord Falgravn 80%. 12 players, 11 alive. Lowest: 8 at 42%.'; in
    the lead-in, '12 players, 3 alive, 9 not in the log yet'."""
    parts = [moment_words(scene.t, start, end)]
    for unit in boss_rows(scene.units):
        state = unit.state
        if state is None:
            parts.append(f"{unit.name} not in the log yet")
        elif unit.where == LEFT:
            parts.append(f"{unit.name} left")
        elif state.health_max > 0:
            parts.append(f"{unit.name} dead" if unit.look == DEAD else
                         f"{unit.name} {share_text(state.health, state.health_max)}")
    players = [unit for unit in scene.units if unit.mark == MARK_PLAYER]
    if players:
        known = [unit for unit in players if unit.state is not None]
        alive = [unit for unit in known if unit.look != DEAD]
        words = f"{len(players)} players, {len(alive)} alive"
        if len(known) < len(players):
            words += f", {len(players) - len(known)} not in the log yet"
        parts.append(words)
        hurt = [unit for unit in alive if 0 < unit.state.health_max
                and unit.state.health < unit.state.health_max]
        if hurt:
            low = min(hurt, key=lambda u: (u.state.health / u.state.health_max, u.number))
            parts.append(f"Lowest: {low.number} at "
                         f"{share_text(low.state.health, low.state.health_max)}")
    return ". ".join(parts) + "."


# ------------------------------------------------------------- the table --

class PositionsTable(QAbstractTableModel):
    """The units of the moment as rows (see the module): the canvas's
    twin for the keyboard and the screen reader. It holds no reference to
    the window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._units: list = []
        self._names = NO_MASK
        self._dark = False
        self._icon = (12, 1.0)  # side, device pixel ratio
        self._ink = None        # the selected row's ink: the table's highlighted text
        # The pictures, kept here and not in the module, so no pixmap
        # outlives the application
        self._icons: dict = {}

    def set_units(self, units, names=None, dark: bool = False, icon_side: int = 12,
                  dpr: float = 1.0, selected_ink: str | None = None) -> bool:
        """Show *units* (UnitAt); in place when the rows are the same units,
        else anew. *selected_ink*: the colour a selected row's picture is
        drawn in. Whether the rows changed."""
        units = list(units)
        names = names or NO_MASK
        if (dark, (icon_side, dpr), selected_ink) != (self._dark, self._icon, self._ink):
            self._icons.clear()
        same = [u.key for u in units] == [u.key for u in self._units]
        if same:
            self._units, self._names, self._dark = units, names, dark
            self._icon, self._ink = (icon_side, dpr), selected_ink
            if units:
                self.dataChanged.emit(self.index(0, 0), self.index(len(units) - 1, len(COLUMNS) - 1))
            return False
        self.beginResetModel()
        self._units, self._names, self._dark = units, names, dark
        self._icon, self._ink = (icon_side, dpr), selected_ink
        self.endResetModel()
        return True

    def icon_of(self, unit) -> QIcon:
        """A unit's picture: in the ink, and on a selected row in the
        highlighted text, whose contrast with the highlight the style
        keeps (the ink on the dark theme's light blue was 1.3:1)."""
        side, dpr = self._icon
        key = (unit.mark, unit.role)
        icon = self._icons.get(key)
        if icon is None:
            icon = QIcon()
            icon.addPixmap(QPixmap.fromImage(marker_icon(unit.mark, unit.role, side, self._dark,
                                                         dpr)), QIcon.Normal)
            if self._ink is not None:
                icon.addPixmap(QPixmap.fromImage(marker_icon(unit.mark, unit.role, side,
                                                             self._dark, dpr, self._ink)),
                               QIcon.Selected)
            self._icons[key] = icon
        return icon

    def units(self) -> list:
        return list(self._units)

    def unit_at(self, row: int):
        return self._units[row] if 0 <= row < len(self._units) else None

    def row_of(self, key) -> int | None:
        for row, unit in enumerate(self._units):
            if unit.key == key:
                return row
        return None

    def rowCount(self, parent=None) -> int:
        return 0 if parent is not None and parent.isValid() else len(self._units)

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
        if role not in (_DISPLAY, _ACCESSIBLE, _DECORATION, _ALIGNMENT, _TOOLTIP):
            return None
        row, column = index.row(), index.column()
        if not 0 <= row < len(self._units):
            return None
        unit = self._units[row]
        if role == _DISPLAY:
            return cell_text(unit, column, self._names, compact())
        if role == _ACCESSIBLE:
            if column == NAME_COL and unit.mark != MARK_BOSS and self._names.hides(unit.name):
                return HIDDEN_NAME
            return None
        if role == _DECORATION:
            return self.icon_of(unit) if column == NUMBER_COL else None
        if role == _ALIGNMENT:
            return _RIGHT if column in _NUMERIC else None
        return cell_text(unit, column, self._names) if column == NAME_COL else None


# ------------------------------------------------------------ the window --

class _WrapLabel(QLabel):
    """A word-wrapped label whose least size is the height of its lines at
    its width, so the window's least size counts every line it shows: a
    QLabel's own least size is one line, and squeezed below the lines, the
    canvas, which keeps its floor, was drawn under the line beneath it (19
    px at the least size at 100% text, 115 px at 200%). Its least size
    hint, not a minimum height: QLabel's height for a width grows to the
    widget's minimum, so a minimum set once never lets the label shrink."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines_height = 0

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        if self.text():
            hint.setHeight(max(hint.height(), self.heightForWidth(self.width())))
        return hint

    def _fit(self) -> None:
        """Have the layout ask again when the lines' height changed."""
        height = self.heightForWidth(self.width()) if self.text() else 0
        if height != self._lines_height:
            self._lines_height = height
            self.updateGeometry()

    def setText(self, text: str) -> None:
        super().setText(text)
        self._fit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange):
            self._fit()


class PositionsWindow(QDialog):
    """See the module notes."""

    # The fight the window shows, which its Show in list button asks the
    # main window to select
    show_in_list_requested = Signal(object)
    # The fight and a player's key (their fight-table row's 'unit_id'):
    # open the player window on them
    player_requested = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self._entry = None
        self._wanted = None        # the locator whose states the window shows or waits for
        self._states = None        # its FightStates, while shown
        self._boxes: dict = {}
        self._maps: tuple = ()
        self._message = ""
        self._dark = False
        self._given = NO_MASK      # the main window's mask for the fight
        self._names = NO_MASK      # that mask with the locator's players (window_mask)
        self._roster = EMPTY_ROSTER
        self._t = 0
        self._selected = None
        self._shown = dict(SHOWN_BY_DEFAULT)
        self._scene = None
        self._syncing = False
        self._split_done = False

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.fight_label = _WrapLabel()
        self.fight_label.setWordWrap(True)
        self.fight_label.setTextFormat(Qt.PlainText)
        self.fight_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.show_in_list = QToolButton()
        self.show_in_list.setText(SHOW_IN_LIST_LABEL)
        self.show_in_list.setAutoRaise(True)
        self.show_in_list.setFocusPolicy(Qt.StrongFocus)
        self.show_in_list.clicked.connect(self._on_show_in_list)
        header.addWidget(self.fight_label, 1)
        header.addWidget(self.show_in_list, 0, Qt.AlignTop)
        layout.addLayout(header)
        self.replayed_label = QLabel(REPLAYED_NOTE)
        self.replayed_label.setWordWrap(True)
        self.replayed_label.setVisible(False)
        layout.addWidget(self.replayed_label)
        self.boss_bars = BossBars()
        self.boss_bars.setVisible(False)
        layout.addWidget(self.boss_bars)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = PositionsCanvas()
        self.canvas.unit_clicked.connect(self._on_canvas_clicked)
        self.elsewhere_label = _WrapLabel()
        self.elsewhere_label.setWordWrap(True)
        self.elsewhere_label.setTextFormat(Qt.PlainText)
        self.elsewhere_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        left_layout.addWidget(self.canvas, 1)
        left_layout.addWidget(self.elsewhere_label)
        self.table = QTableView()
        self.model = PositionsTable(self)
        self.table.setModel(self.model)
        self.table.setAccessibleName("Players and bosses")
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setTabKeyNavigation(False)  # Tab leaves the table for the buttons
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.verticalHeader().setVisible(False)
        # Rows sized to their contents once per new text size or new rows
        # (_fit_table), not at every step: sized to contents, the header
        # asked every cell for its size at each change of the moment
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        # The selection, not the current row: a table given the focus with
        # no current row makes its first row current, unselected, and the
        # window's return to the front picked player 1 by itself
        self.table.selectionModel().selectionChanged.connect(self._on_row_changed)
        self.table.activated.connect(self._on_activated)
        self.splitter.addWidget(left)
        self.splitter.addWidget(self.table)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter, 1)

        controls = QHBoxLayout()
        self.previous_death = self._button("◀ Death", "Previous death",
                                           "Previous death (Ctrl+PgUp)", self._previous_death)
        self.back = self._button("−1 s", "Back one second",
                                 "Back a second (Ctrl+Left); with Shift a tenth", self._back)
        self.clock = QLabel()
        self.clock.setAccessibleName("Moment")
        self.clock.setTextFormat(Qt.PlainText)
        self.forward = self._button("+1 s", "On one second",
                                    "On a second (Ctrl+Right); with Shift a tenth", self._forward)
        self.next_death = self._button("Death ▶", "Next death", "Next death (Ctrl+PgDn)",
                                       self._next_death)
        self.show_button = QToolButton()
        self.show_button.setText("Show")
        self.show_button.setAccessibleName("Show")
        self.show_button.setToolTip("Which units the canvas draws")
        self.show_button.setPopupMode(QToolButton.InstantPopup)
        self.show_button.setFocusPolicy(Qt.TabFocus)
        self.show_menu = QMenu(self)
        self._show_actions = {}
        for mark, words in SHOW_ITEMS:
            action = self.show_menu.addAction(words)
            action.setCheckable(True)
            action.setChecked(SHOWN_BY_DEFAULT[mark])
            action.setToolTip(SHOW_TIPS[mark])
            action.toggled.connect(self._on_shown)
            self._show_actions[mark] = action
        self.show_button.setMenu(self.show_menu)
        for widget in (self.previous_death, self.back):
            controls.addWidget(widget)
        controls.addWidget(self.clock)
        for widget in (self.forward, self.next_death):
            controls.addWidget(widget)
        controls.addStretch(1)
        controls.addWidget(self.show_button)
        layout.addLayout(controls)
        self.scrub = ScrubBar()
        self.scrub.moment_requested.connect(self._go_to)
        self.scrub.step_requested.connect(self._step)
        self.scrub.death_requested.connect(self._death_step)
        layout.addWidget(self.scrub)

        # Modified keys only (see the module); never Ctrl+H nor the text
        # size keys, which are the main window's, application-wide
        for keys, slot in (("Ctrl+Left", self._back_second), ("Ctrl+Right", self._forward_second),
                           ("Ctrl+Shift+Left", self._back_tenth),
                           ("Ctrl+Shift+Right", self._forward_tenth),
                           ("Ctrl+PgUp", self._previous_death), ("Ctrl+PgDown", self._next_death),
                           ("Ctrl+Up", self._previous_unit), ("Ctrl+Down", self._next_unit)):
            QShortcut(QKeySequence(keys), self, slot)
        QShortcut(QKeySequence(QKeySequence.Copy), self, self._copy_moment)

        # A burst of updates to the fight draws once, on the event loop's
        # next turn, on a timer the window owns
        self._redraw = QTimer(self)
        self._redraw.setSingleShot(True)
        self._redraw.setInterval(0)
        self._redraw.timeout.connect(self._redraw_now)

        QWidget.setTabOrder(self.scrub, self.table)
        order = (self.table, self.previous_death, self.back, self.forward, self.next_death,
                 self.show_button, self.show_in_list)
        for first, second in pairwise(order):
            QWidget.setTabOrder(first, second)
        self._fit_table()
        self.resize(*self._default_size())

    def _button(self, text: str, name: str, tip: str, slot) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setAccessibleName(name)
        button.setToolTip(tip)
        button.setFocusPolicy(Qt.TabFocus)
        button.clicked.connect(slot)
        return button

    # ---- the contract with the main window ----

    @property
    def entry(self):
        """The fight the window shows, None before the first open."""
        return self._entry

    @property
    def wanted_locator(self):
        """The locator whose states the window shows or waits for; None
        while hidden."""
        return self._wanted

    def has_states_for(self, locator) -> bool:
        """Whether the window holds that locator's states already."""
        return locator is not None and self._states is not None and self._states.locator == locator

    def views(self) -> list:
        """The window's FightView pages, for a new text size: none."""
        return []

    def open(self, entry, t_ms: int, unit_key: str | None, dark: bool, names=None,
             listed: bool = True) -> None:
        """Show the fight *entry* at moment *t_ms* (ms since its session's
        BEGIN_LOG, the locator's clock) with *unit_key* selected (a
        player's fight-table 'unit_id'), and bring the window up with the
        focus in the table. Without the states of its locator it says it
        is reading them until reread_done brings them."""
        self._dark = bool(dark)
        self._given = names or NO_MASK
        self._entry = entry
        locator = getattr(entry, "locator", None)
        self._wanted = locator
        if locator is None:
            self._drop_states(NO_LOCATOR)
        elif not self.has_states_for(locator):
            self._drop_states(READING)
        self._bind()
        self._t = int(t_ms)
        self._selected = str(unit_key) if unit_key else None
        self.replayed_label.setVisible(False)
        self.set_listed(listed)
        self._draw()
        self.show()
        self.raise_()
        self.activateWindow()
        self._first_split()
        self.table.setFocus()

    def reread_done(self, event) -> None:
        """A read the main window ran (fight_reread.RereadEvent): taken
        when it is for the locator the window wants, else dropped; a read
        cancelled says nothing."""
        locator = event.locator
        # Besides the wanted locator, the entry's new one, answered before
        # the redraw that would want it (see the module)
        if locator is not self._wanted and not (
                self._wanted is not None and self._entry is not None and self.isVisible()
                and locator is getattr(self._entry, "locator", None)):
            return
        if event.kind == "cancelled":
            return
        self._wanted = locator
        if event.kind == "loaded" and event.states is not None:
            self._take_states(event.states)
        elif event.kind == "missing":
            self._drop_states(_with_reason(MISSING, event.error))
        else:
            self._drop_states(_with_reason(FAILED, event.error))
        self._bind()
        self._draw()

    def refresh(self, dark: bool, names=None) -> None:
        """Draw again for a theme switch, a flip of Hide names (*names*,
        the new mask; None keeps the one shown) or a new text size."""
        self._dark = bool(dark)
        if names is not None:
            self._given = names
        self._bind()
        if self._entry is not None and self.isVisible():
            self._draw()
            self._fit_table()  # a hidden name's blocks are wider than its letters
            # Once more on the event loop's next turn: a theme switch calls
            # this in the middle of Qt's palette change, before the table
            # has the new palette its pictures' ink is read from
            self._redraw.start()

    def entry_updated(self, entry, dark: bool, names=None) -> None:
        """The fight *entry* changed in place: when it is the window's, it
        is drawn again on the event loop's next turn, once for a burst,
        at the same moment with the same unit selected; its numbers,
        roles and deaths may have changed, and its locator, when the game
        cut it in two and it went on."""
        if entry is not self._entry:
            return
        self._dark = bool(dark)
        if names is not None:
            self._given = names
        if self.isVisible():
            self._redraw.start()

    def rebind(self, entry, names=None) -> None:
        """A Settings replay rebuilt the window's fight as *entry*: the
        window shows it, keeping the states it holds when the new locator
        equals theirs."""
        self._entry = entry
        if names is not None:
            self._given = names
        if self._wanted is not None:
            self._wanted = getattr(entry, "locator", None)
        self._bind()
        self.replayed_label.setVisible(False)
        if self.isVisible():
            self._draw()

    def mark_replayed(self) -> None:
        """A Settings replay did not bring the fight back: the window keeps
        it as it was, and says so."""
        self.replayed_label.setVisible(self._entry is not None)

    def set_listed(self, listed: bool) -> None:
        """Whether the window's fight is in the fight list, for Show in
        list."""
        self.show_in_list.setEnabled(bool(listed))
        self.show_in_list.setToolTip(SHOW_IN_LIST_TIP if listed else NOT_LISTED_TIP)

    # ---- what it holds, for the tests and the main window ----

    def states(self):
        return self._states

    def moment(self) -> int:
        return self._t

    def selected(self) -> str | None:
        return self._selected

    def scene(self):
        return self._scene

    def message(self) -> str:
        return self._message

    def names(self):
        return self._names

    def shown(self) -> dict:
        return dict(self._shown)

    def set_shown(self, mark: str, on: bool) -> None:
        """Turn a mark of the Show menu on or off."""
        self._show_actions[mark].setChecked(bool(on))

    # ---- binding and drawing ----

    def _take_states(self, states) -> None:
        self._states = states
        self._boxes = fit_boxes(states)
        self._maps = map_change_times(states)
        self._message = ""

    def _drop_states(self, message: str) -> None:
        self._states = None
        self._boxes = {}
        self._maps = ()
        self._message = message

    def _bind(self) -> None:
        """The roster and the mask from the entry as it is now."""
        entry = self._entry
        self._roster = roster_of(entry) if entry is not None else EMPTY_ROSTER
        locator = getattr(entry, "locator", None)
        if locator is None and self._states is not None:
            locator = self._states.locator
        self._names = window_mask(self._given, locator)

    def _redraw_now(self) -> None:
        if self._entry is None or not self.isVisible():
            return
        locator = getattr(self._entry, "locator", None)
        if locator is not self._wanted:
            self._wanted = locator
            if not self.has_states_for(locator):
                self._drop_states(READING if locator is not None else NO_LOCATOR)
        self._bind()
        self._draw()

    def _span(self):
        """(range start, fight start, fight end, range end), ms since
        BEGIN_LOG: the states' first line, else LEAD_MS before the
        fight, to TAIL_MS after it; None with no locator."""
        states = self._states
        locator = states.locator if states is not None else getattr(self._entry, "locator", None)
        if locator is None:
            return None
        first = locator.start_ms - LEAD_MS
        if states is not None and states.range_start_ms is not None:
            first = min(states.range_start_ms, locator.start_ms)
        return first, locator.start_ms, locator.end_ms, locator.end_ms + TAIL_MS

    def _draw(self, sync_table: bool = True) -> None:
        """Everything for the moment: the header, the canvas, the table,
        the boss bars, the line under the canvas, the scrub bar, the
        buttons."""
        entry = self._entry
        if entry is None:
            return
        span = self._span()
        if span is not None:
            self._t = max(span[0], min(span[3], self._t))
        start, end = (span[1], span[2]) if span is not None else (self._t, self._t)
        self.fight_label.setText(header_line(entry, self._t - start if span is not None else None))
        title = str(getattr(entry, "boss_name", "") or getattr(entry, "zone_name", "") or "")
        self.setWindowTitle(f"{TITLE} – {title}" if title else TITLE)
        self.clock.setText(fight_clock(self._t - start) if span is not None else "")
        if self._states is None:
            self._scene = None
            self.canvas.set_message(self._message)
            self._fill_table([])
            self.boss_bars.set_bosses([])
            self.elsewhere_label.setText("")
            summary = self._message
        else:
            self._resolve_selected()
            self._scene = build_scene(self._states, self._roster, self._t, self._selected,
                                      self._shown, self._boxes)
            self.canvas.set_scene(self._scene, self._names)
            self._fill_table([u for u in self._scene.units if u.mark in _TABLE_MARKS])
            self.boss_bars.set_bosses([boss_bar(unit) for unit in boss_rows(self._scene.units)])
            self.elsewhere_label.setText(self._elsewhere_text())
            summary = moment_summary(self._scene, start, end)
        self.canvas.setAccessibleDescription(summary)
        self.table.setAccessibleDescription(summary)
        if sync_table:
            self._sync_table()
        self._fill_scrub(span)
        self._fill_buttons()

    def _resolve_selected(self) -> None:
        """A key from open() that names no player: the unit of that key
        with a state at the moment, or the last to arrive."""
        key = self._selected
        if key is None or self._states is None:
            return
        tracks = self._states.tracks
        if key in self._roster.numbers or any(unit_key_of(track) == key for track in tracks):
            return
        matches = [track for track in tracks if track.unit is not None and track.unit.key == key]
        if matches:
            present = [track for track in matches if track.at(self._t) >= 0]
            self._selected = unit_key_of((present or matches)[-1])

    def _fill_table(self, units) -> None:
        side = max(10, scaled_px(12))
        # The icons' ink from the table's own palette, as the canvas reads
        # its colours; a selected row's in its highlighted text
        changed = self.model.set_units(units, self._names, is_dark(self.table), side,
                                       self.devicePixelRatioF(),
                                       self.table.palette().color(QPalette.HighlightedText).name())
        if self.table.iconSize() != QSize(side, side):
            self.table.setIconSize(QSize(side, side))
            changed = True
        if changed:
            self._fit_table()

    def _sync_table(self) -> None:
        """Select the selected unit's row, or none."""
        row = self.model.row_of(self._selected)
        selection = self.table.selectionModel()
        self._syncing = True
        try:
            if row is None:
                selection.clear()
            else:
                index = self.model.index(row, 0)
                if self.table.currentIndex().row() != row or not selection.isRowSelected(row):
                    selection.setCurrentIndex(index, QItemSelectionModel.ClearAndSelect
                                              | QItemSelectionModel.Rows)
                self.table.scrollTo(index)
        finally:
            self._syncing = False

    def _elsewhere_text(self) -> str:
        """'Map: Floor (2 of 3) · Not on this map: 6, 11 · Not in the log
        yet: 12': the map the canvas shows, then who it does not draw,
        players by number (the table names them), bosses by name, as
        boss_rows gives them: a boss that left is not named, and one is
        not in the log yet only while no unit of its name is. Under the
        canvas, where it covers no unit."""
        away, not_yet = [], []
        players = [(str(unit.number), unit) for unit in self._scene.units
                   if unit.mark == MARK_PLAYER]
        bosses = [(unit.name, unit) for unit in boss_rows(self._scene.units)]
        for who, unit in players + bosses:
            if unit.where in (OTHER_MAP, OFF_MAP):
                away.append(who)
            elif unit.where == NOT_YET:
                not_yet.append(who)
        parts = []
        frames = len(self._states.frames) if self._states is not None else 0
        if self._scene.frame_name:
            parts.append(f"Map: {self._scene.frame_name}"
                         + (f" ({self._scene.frame + 1} of {frames})" if frames > 1 else ""))
        if away:
            parts.append("Not on this map: " + ", ".join(_counted(away)))
        if not_yet:
            parts.append("Not in the log yet: " + ", ".join(_counted(not_yet)))
        return " · ".join(parts)

    def _fill_scrub(self, span) -> None:
        if span is None:
            self.scrub.set_fight(0, 0, 0, 1)
            self.scrub.set_moment(0, "")
            return
        deaths = [death[0] for death in self._roster.deaths]
        self.scrub.set_fight(*span, deaths=deaths, maps=self._maps)
        length = clock(getattr(self._entry, "duration_s", 0))
        self.scrub.set_moment(self._t, f"{moment_words(self._t, span[1], span[2])}, of {length}")

    def _fill_buttons(self) -> None:
        self.previous_death.setEnabled(self._death_index(-1) is not None)
        self.next_death.setEnabled(self._death_index(1) is not None)
        span = self._span()
        self.back.setEnabled(span is not None and self._t > span[0])
        self.forward.setEnabled(span is not None and self._t < span[3])

    def _first_split(self) -> None:
        """The splitter's first share: the table as wide as its columns,
        up to TABLE_SHARE of the window; the reader's share kept after."""
        if self._split_done:
            return
        self._split_done = True
        self.layout().activate()
        total = max(1, self.splitter.width())
        table = min(self._table_width(), int(total * TABLE_SHARE))
        self.splitter.setSizes([total - table, table])

    def _table_width(self) -> int:
        header = self.table.horizontalHeader()
        width = sum(header.sectionSize(column) for column in range(len(COLUMNS))
                    if not self.table.isColumnHidden(column))
        return width + 2 * self.table.frameWidth() + self.table.verticalScrollBar().sizeHint().width()

    def _fit_table(self) -> None:
        """Every column as wide as its widest text at the text size in
        force, the moment's or its template's (TEMPLATES); magicka and
        stamina left out above POOLS_UP_TO."""
        small = compact()
        for column in POOL_COLUMNS:
            self.table.setColumnHidden(column, small)
        self.table.resizeColumnsToContents()
        # The rows as high as their text and picture need (a QTableView
        # keeps 30 px rows at every text size: see the module)
        header = self.table.verticalHeader()
        row = max(self.table.sizeHintForRow(0) if self.model.rowCount() else 0,
                  self.table.fontMetrics().height() + 4, self.table.iconSize().height() + 4)
        header.setMinimumSectionSize(min(header.minimumSectionSize(), row))
        header.setDefaultSectionSize(row)
        metrics = QFontMetrics(self.table.font())
        pad = metrics.horizontalAdvance("M") + scaled_px(4)
        for column, template in TEMPLATES.items():
            if column == HEALTH_COL and small:
                template = COMPACT_HEALTH
            least = metrics.horizontalAdvance(template) + pad
            if column == NUMBER_COL:
                least += self.table.iconSize().width() + scaled_px(4)
            if self.table.columnWidth(column) < least:
                self.table.setColumnWidth(column, least)

    # ---- moving ----

    def _go_to(self, t: int) -> None:
        self._t = int(t)
        self._draw()

    def _step(self, ms: int) -> None:
        self._go_to(self._t + int(ms))

    def _shift_held(self) -> bool:
        return bool(QGuiApplication.keyboardModifiers() & Qt.ShiftModifier)

    def _back(self) -> None:
        self._step(-100 if self._shift_held() else -1000)

    def _forward(self) -> None:
        self._step(100 if self._shift_held() else 1000)

    def _back_second(self) -> None:
        self._step(-1000)

    def _forward_second(self) -> None:
        self._step(1000)

    def _back_tenth(self) -> None:
        self._step(-100)

    def _forward_tenth(self) -> None:
        self._step(100)

    def _death_index(self, direction: int) -> int | None:
        """The death a step of *direction* goes to: from the death on
        screen (the moment's, its player selected) the one before or
        after it, deaths at one moment in turn; else the nearest before
        or after the moment. Each death is taken at the moment it is
        shown at: one counted past the range's end (a death read from
        health 0 settled at the next fight) is shown at the end, and is
        still on screen there, not a death to go to again."""
        span = self._span()
        moments = [death[0] if span is None else max(span[0], min(span[3], death[0]))
                   for death in self._roster.deaths]
        here = next((i for i, (at, death) in enumerate(zip(moments, self._roster.deaths))
                     if at == self._t and death[1] == self._selected), None)
        if here is not None:
            index = here + (1 if direction > 0 else -1)
            return index if 0 <= index < len(moments) else None
        if direction > 0:
            return next((i for i, at in enumerate(moments) if at > self._t), None)
        return next((i for i in range(len(moments) - 1, -1, -1) if moments[i] < self._t), None)

    def _death_step(self, direction: int) -> None:
        index = self._death_index(direction)
        if index is None:
            return
        t, unit_id = self._roster.deaths[index][:2]
        self._t = t
        self._selected = unit_id
        self._draw()

    def _previous_death(self) -> None:
        self._death_step(-1)

    def _next_death(self) -> None:
        self._death_step(1)

    # ---- selecting ----

    def _on_canvas_clicked(self, key: str) -> None:
        self._selected = key
        self._draw()

    def _on_row_changed(self, _selected, _deselected) -> None:
        """A row the reader selected: its unit. A row made current without
        being selected (the table's focus-in does that) is no choice."""
        if self._syncing:
            return
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        unit = self.model.unit_at(rows[0].row())
        if unit is None or unit.key == self._selected:
            return
        self._selected = unit.key
        self._draw(sync_table=False)

    def _step_unit(self, step: int) -> None:
        rows = self.model.rowCount()
        if not rows:
            return
        row = self.model.row_of(self._selected)
        row = 0 if row is None else max(0, min(rows - 1, row + step))
        self.table.setCurrentIndex(self.model.index(row, 0))

    def _previous_unit(self) -> None:
        self._step_unit(-1)

    def _next_unit(self) -> None:
        self._step_unit(1)

    def _on_activated(self, index) -> None:
        """Enter or a double-click on a player's row: their player window.
        A player with no fight-table row has one only when they died (the
        player window lists them as 'also died')."""
        unit = self.model.unit_at(index.row())
        if unit is None or self._entry is None:
            return
        died = {death[1] for death in self._roster.deaths}
        if unit.mark == MARK_PLAYER or (unit.mark == MARK_LOOSE and unit.unit_key in died):
            self.player_requested.emit(self._entry, unit.unit_key)

    def _on_shown(self, _checked: bool) -> None:
        self._shown = {mark: action.isChecked() for mark, action in self._show_actions.items()}
        if self._entry is not None:
            self._draw()

    def _on_show_in_list(self) -> None:
        if self._entry is not None:
            self.show_in_list_requested.emit(self._entry)

    # ---- copying ----

    def moment_text(self) -> str:
        """The moment in words, as Ctrl+C copies it: the fight line, the
        moment's summary and the table's rows, tab-separated, names
        through the Hide names mask."""
        if self._entry is None:
            return ""
        lines = [self.fight_label.text()]
        if self._scene is None:
            lines.append(self._message)
            return "\n".join(line for line in lines if line)
        lines.append(self.canvas.accessibleDescription())
        lines.append("\t".join(COLUMNS))
        for unit in self.model.units():
            lines.append("\t".join(cell_text(unit, column, self._names)
                                   for column in range(len(COLUMNS))))
        return "\n".join(lines)

    def _copy_moment(self) -> None:
        text = self.moment_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    # ---- size, fonts and hiding ----

    def _default_size(self):
        """DEFAULT_SIZE, no more than nine tenths of the screen."""
        width, height = DEFAULT_SIZE
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            width = min(width, int(area.width() * 0.9))
            height = min(height, int(area.height() * 0.9))
        return width, height

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange):
            side = max(10, scaled_px(12))
            self.table.setIconSize(QSize(side, side))
            self._fit_table()
            if self._entry is not None and self.isVisible():
                self._draw()

    def hideEvent(self, event) -> None:
        """Hidden by Esc, the title bar's x or the main window (no close
        event comes): the states and the locator wanted are dropped, the
        fight kept. A window the system minimised keeps them."""
        super().hideEvent(event)
        if event.spontaneous():
            return
        self._redraw.stop()
        self._wanted = None
        self._drop_states("")
        self._scene = None
        self.canvas.set_message("")
        self.model.set_units([])
        self.boss_bars.set_bosses([])


def _with_reason(lead: str, error: str) -> str:
    """*lead*, then the reader's reasons with file names only."""
    reason = file_names_only(error).strip()
    return f"{lead}:\n{reason}" if reason else f"{lead}."
