"""
The player window (issue #196): one player's fight on seven tabs, in place
of the build, damage, damage taken and death recap windows.

Design: One window for a player. Each player link on the fight pane opens
this one window at the tab for that link: the name and the lone mastery's
'?' at Build, the dps figure at Damage done, the 'p:... cd:...' token at
Pen and crit, the shield at Damage taken, the skull and the Also died chip
at Deaths. Four windows to place became one, and the build page, which no
window fitted (2,352 px at the median), became pages that mostly do.

    Build · Damage done · Pen and crit · Resources · Damage taken ·
    Healing received · Deaths

Each tab is a FightView drawing one part of the four pages (build_render,
damage_render, taken_render and death_render, each with header=False), under
two header rows the window draws itself: the previous player button, the
player picker, the next player button and Boss targets only (shown on Damage
done); then the fight line and Show in list. The order is the build window's
(#143: gear, then what the player did with it, the cap sections and
Resources), then the damage taken side. The kinds of damage dealt moved from
the build page to Damage done, beside the damage they sort, and the death
recap's closing block of the whole fight's damage taken became a link to
the Damage taken tab, which has all of it (decision 4, reversing that part
of #95). The damage taken page is two tabs, its healing received line a link
to the second (decision 1).

The window keeps the fight it was opened for, as the four windows did
(#143): a pane link binds the pane's fight and the player and names the tab,
and the tabs, the picker and the links in the pages work on that pair,
never on the list. The fight changing in place (entry_updated) redraws the
page on screen, each other page when it is next shown, each keeping its
scroll; a burst of updates (mark_context and the mastery backfill send one
per earlier fight) draws once, on the event loop's next turn. A Settings
replay builds new entries: MainWindow puts the window on the replayed copy
of its fight, found by its key and checked by the player's handle, and
leaves it on the old one, saying so, when there is none.

Tabs that do not apply stay enabled and say so in a line (Qt moves off a
disabled current tab). The Alt letters are the tab labels' mnemonics and
never shortcuts too: a key bound twice in one window works every other
press (probed on PySide6 6.12.0). Ctrl+PgDn and Ctrl+PgUp change the tab
from anywhere in the window, Ctrl+Down and Ctrl+Up the player, keeping the
tab. Opening puts the focus in the page; an Alt letter or Ctrl+PgDn from the
header rows moves it into the new page, since Qt leaves it in the picker,
where PgDn changes the player. A link reached with Tab has Tab's focus
again when its tab is shown again, as it kept it between the four windows:
Qt drops it as the tab widget hides the page (FightView.give_link_back).
The window has no Close or default button, so Enter never closes it; Esc
and the title bar's x hide it.

It holds no reference to MainWindow: it asks for its fight to be shown in
the list by a signal, and its pages' links are its own tab switches, but
for a death's Positions link (issue #214), the one way out of it, which it
hands on by a signal too, with its fight: the positions window is the main
window's. It stores no lambda on a child.
"""

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
)

from ability_icons import esohub_ability_url, esohub_script_url, esohub_set_url
from gui.build_render import (
    BUILD_PART,
    NO_BUILD,
    PEN_CRIT_PART,
    RESOURCES_PART,
    build_title,
    player_for,
    render_build_html,
)
from gui.damage_render import damage_title, render_damage_html
from gui.death_render import (
    SKULL,
    death_anchor,
    death_events_tooltips,
    death_positions_tooltips,
    deaths_by_unit,
    kind_tooltips,
    render_death_recap_html,
)
from gui.fight_render import _join, _theme, anchor_tooltips
from gui.fight_view import FightView
from gui.name_mask import NO_MASK
from gui.taken_render import HEALING_PART, TAKEN_PART, render_taken_html, taken_title
from pull_outcome import clock, outcome_text

BUILD_TAB = "build"
DAMAGE_TAB = "damage"
PEN_CRIT_TAB = "pen_crit"
RESOURCES_TAB = "resources"
TAKEN_TAB = "taken"
HEALING_TAB = "healing"
DEATHS_TAB = "deaths"
# The tabs in order: key, label (its & marks the Alt letter), and the name
# the window's title begins with on that tab
TABS = (
    (BUILD_TAB, "&Build", "Build"),
    (DAMAGE_TAB, "&Damage done", "Damage"),
    (PEN_CRIT_TAB, "&Pen and crit", "Pen and crit"),
    (RESOURCES_TAB, "&Resources", "Resources"),
    (TAKEN_TAB, "Damage &taken", "Damage taken"),
    (HEALING_TAB, "&Healing received", "Healing received"),
    (DEATHS_TAB, "D&eaths", "Death recap"),
)
TAB_KEYS = tuple(key for key, _label, _title in TABS)
BOSS_ONLY_LABEL = "Boss targets &only"
SHOW_IN_LIST_LABEL = "Show in list"
SHOW_IN_LIST_TIP = "Select this fight in the fight list"
NOT_LISTED_TIP = "This fight is not in the list now"
REPLAYED_NOTE = ("From before Settings replayed the session: this fight is not in the "
                 "replay, so it is shown as it was.")
NO_COMPANION_DATA = "None logged for companions."
DID_NOT_DIE = "{name} did not die in this fight."
COMPANION_DIED = ("{name} died {count}; the log keeps no recap of a companion's deaths.")
ALSO_DIED_MARK = "also died"
DEFAULT_SIZE = (900, 840)  # an 868 x 730 page at 100% text (issue #196)
PICKER_CHARS = 28  # the picker's width in characters; its list shows whole rows


def fight_line(entry) -> str:
    """The fight the window shows, in one line: 'Lord Falgravn · Kyne's
    Aegis VET · Wipe 86% · 1:30 · 2026-10-15 19:30:07'. Its start has the
    date, as the windows' headers had, for a fight from an older log under
    review."""
    boss = str(getattr(entry, "boss_name", "") or "")
    zone = str(getattr(entry, "zone_name", "") or "")
    if zone and getattr(entry, "is_vet", False):
        zone += " VET"
    parts = (boss, zone, outcome_text(getattr(entry, "pull", None), boss),
             clock(getattr(entry, "duration_s", 0)),
             str(getattr(entry, "timestamp", "") or ""))
    return " · ".join(part for part in parts if part)


def _death_mark(count: int) -> str:
    return f"{SKULL} ×{count}" if count > 1 else SKULL if count else ""


def player_rows(entry, names=None):
    """(unit id, picker text) for each player of the fight: the pane's rows
    in its order ('D  @handle  Arcanist  ☠ ×2'), a companion under its
    owner as the pane has it, then the players the table does not list who
    died ('Also died'). Names through the Hide names mask."""
    names = names or NO_MASK
    deaths = deaths_by_unit(entry)
    rows = []
    listed = set()
    for p in getattr(entry, "players", None) or []:
        unit_id = str(p.get("unit_id") or "")
        if not unit_id:
            continue
        listed.add(unit_id)
        count = int(p.get("deaths") or 0) if p.get("companion") else len(deaths.get(unit_id, []))
        cells = (str(p.get("role") or ""), names.text(_join(p.get("name", ""))),
                 "" if p.get("companion") else str(p.get("class_name") or ""), _death_mark(count))
        rows.append((unit_id, "  ".join(cell for cell in cells if cell)))
    for unit_id, recaps in deaths.items():
        if unit_id not in listed:
            name = names.text(str(recaps[0].get("name") or "")) or "unknown"
            rows.append((unit_id, f"{name}  {_death_mark(len(recaps))}  · {ALSO_DIED_MARK}"))
    return rows


def _player_name(entry, unit_id, names) -> str:
    """The player's name as the window's title and lines show it."""
    p = player_for(entry, unit_id)
    if p is not None:
        return names.text(_join(p.get("name", "")))
    recaps = deaths_by_unit(entry).get(str(unit_id), [])
    return names.text(str(recaps[0].get("name") or "")) if recaps else ""


class PlayerWindow(QDialog):
    """See the module notes."""

    # The fight the window shows, which its Show in list button asks the
    # main window to select
    show_in_list_requested = Signal(object)
    # A death's Positions link on the Deaths tab (issue #214), which the
    # main window opens the positions window at: the fight, the key of the
    # unit to select ('' for none) and ms into the fight
    positions_requested = Signal(object, str, int)
    # A death's Events link: the window's fight and the moment, for the
    # main window's Events tab (issue #214)
    events_requested = Signal(object, int)

    def __init__(self, parent=None, icons=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Build")
        self._config = config
        self._entry = None
        self._unit_id = ""
        self._dark = False
        self._names = NO_MASK
        self._dirty = set(TAB_KEYS)  # the pages to draw again before they show
        self._drawn = {}  # tab -> (entry, unit id) its page was last drawn for
        self._death = None  # the death the Deaths tab opens at, from 1

        layout = QVBoxLayout(self)
        # First header row: the player
        players = QHBoxLayout()
        self.previous_player = QToolButton()
        self.previous_player.setText("◀")
        self.previous_player.setAccessibleName("Previous player")
        self.previous_player.setToolTip("Previous player (Ctrl+Up)")
        self.previous_player.clicked.connect(self._previous_player)
        self.picker = QComboBox()
        self.picker.setAccessibleName("Player")
        self.picker.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.picker.setMinimumContentsLength(PICKER_CHARS)
        self.picker.currentIndexChanged.connect(self._on_player_picked)
        self.next_player = QToolButton()
        self.next_player.setText("▶")
        self.next_player.setAccessibleName("Next player")
        self.next_player.setToolTip("Next player (Ctrl+Down)")
        self.next_player.clicked.connect(self._next_player)
        self.boss_only = QCheckBox(BOSS_ONLY_LABEL)
        self.boss_only.toggled.connect(self._on_boss_only)
        players.addWidget(self.previous_player)
        players.addWidget(self.picker)
        players.addWidget(self.next_player)
        players.addStretch(1)
        players.addWidget(self.boss_only)
        layout.addLayout(players)
        # Second: the fight, full width, wrapped (unwrapped it set a 1,094 px
        # minimum at 200% text), and the button that selects it in the list
        fight = QHBoxLayout()
        self.fight_label = QLabel()
        self.fight_label.setWordWrap(True)
        self.fight_label.setTextFormat(Qt.PlainText)
        self.fight_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.show_in_list = QToolButton()
        self.show_in_list.setText(SHOW_IN_LIST_LABEL)
        self.show_in_list.setAutoRaise(True)
        self.show_in_list.setFocusPolicy(Qt.StrongFocus)  # in the Tab chain
        self.show_in_list.clicked.connect(self._on_show_in_list)
        fight.addWidget(self.fight_label, 1)
        fight.addWidget(self.show_in_list, 0, Qt.AlignTop)
        layout.addLayout(fight)
        self.replayed_label = QLabel(REPLAYED_NOTE)
        self.replayed_label.setWordWrap(True)
        self.replayed_label.setVisible(False)
        layout.addWidget(self.replayed_label)

        self.tabs = QTabWidget()
        self._views = {}
        for key, label, title in TABS:
            view = FightView(icons=icons)
            view.setAccessibleName(title if key != DAMAGE_TAB else "Damage done")
            # The pages' links between them are tab switches; the rest open
            # on ESO-Hub (FightView)
            view.build_requested.connect(self._to_build)
            view.damage_requested.connect(self._to_damage)
            view.pen_crit_requested.connect(self._to_pen_crit)
            view.taken_requested.connect(self._to_taken)
            view.healing_requested.connect(self._to_healing)
            view.death_recap_requested.connect(self._to_deaths)
            view.recap_requested.connect(self._to_death)
            # A moment of the fight leaves the window: the main window has
            # the positions window (issue #214)
            view.positions_requested.connect(self._to_positions)
            view.events_requested.connect(self._to_events)
            self._views[key] = view
            self.tabs.addTab(view, label)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, 1)

        # Ctrl+PgDn and Ctrl+PgUp from anywhere in the window, Ctrl+Down and
        # Ctrl+Up for the player (decided keys; not the labels' Alt letters)
        for keys, slot in (("Ctrl+PgDown", self._next_tab), ("Ctrl+PgUp", self._previous_tab),
                           ("Ctrl+Down", self._next_player), ("Ctrl+Up", self._previous_player)):
            QShortcut(QKeySequence(keys), self, slot)

        # A burst of updates to the fight draws once, on the next turn of the
        # event loop, on a timer the window owns (see fight_view's steps)
        self._redraw = QTimer(self)
        self._redraw.setSingleShot(True)
        self._redraw.setInterval(0)
        self._redraw.timeout.connect(self._redraw_current)

        self._fit_width()
        self.resize(*self._default_size())

    # ---- what the window shows ----

    @property
    def entry(self):
        """The fight the window shows, None before the first link."""
        return self._entry

    @property
    def unit_id(self) -> str:
        return self._unit_id

    def current_tab(self) -> str:
        return TAB_KEYS[self.tabs.currentIndex()]

    def view(self, tab: str) -> FightView:
        """The page of tab *tab*."""
        return self._views[tab]

    def views(self):
        """The window's pages, which take a new text size
        (MainWindow.set_text_size)."""
        return list(self._views.values())

    def open(self, entry, unit_id, tab: str, dark: bool, names=None, death=None,
             listed: bool = True) -> None:
        """Show the player *unit_id* of the fight *entry* at the tab *tab*,
        at the death *death* (from 1) on the Deaths tab, and bring the
        window up with the focus in the page. *listed*: whether the fight is
        in the fight list, for Show in list."""
        self._dark = dark
        self._names = names or NO_MASK
        self._bind(entry, str(unit_id))
        self._death = death
        self.replayed_label.setVisible(False)
        self.set_listed(listed)
        index = TAB_KEYS.index(tab)
        if self.tabs.currentIndex() == index:
            self._draw(tab)
        else:
            self.tabs.setCurrentIndex(index)  # draws it (_on_tab_changed)
        self.show()
        self.raise_()
        self.activateWindow()
        self._views[tab].setFocus()

    def refresh(self, dark: bool, names=None) -> None:
        """Draw the pages again for a theme switch (the HTML embeds theme
        colours), a flip of Hide names (*names*, the new mask; None keeps the
        one shown) or a new text size: the page on screen now, each keeping
        its place, the others when they are next shown. Nothing while the
        window is hidden, until it is shown."""
        self._dark = dark
        if names is not None:
            self._names = names
        self._dirty = set(TAB_KEYS)
        # A hidden window is left alone: the next link to it fills it anew
        if self._entry is not None and self.isVisible():
            self._fill_header()
            self._draw(self.current_tab())

    def entry_updated(self, entry, dark: bool, names=None) -> None:
        """The fight *entry* changed in place (MainWindow._fight_changed):
        when it is the window's, its pages are drawn again, the one on
        screen on the event loop's next turn, once for a burst, keeping its
        place; with *names*, the Hide names mask made afresh for it."""
        if entry is not self._entry:
            return
        self._dark = dark
        if names is not None:
            self._names = names
        self._dirty = set(TAB_KEYS)
        if self.isVisible():
            self._redraw.start()

    def rebind(self, entry, names=None) -> None:
        """A Settings replay built *entry*, the window's fight read again:
        the window shows it, at the same player and tab, each page keeping
        its place (MainWindow._end_replay)."""
        self._entry = entry
        if names is not None:
            self._names = names
        self._drawn = {tab: (entry, unit) for tab, (_old, unit) in self._drawn.items()}
        self.replayed_label.setVisible(False)
        self._dirty = set(TAB_KEYS)
        self._fill_header()
        if self.isVisible():
            self._draw(self.current_tab())

    def mark_replayed(self) -> None:
        """A Settings replay did not bring the window's fight back: it keeps
        the fight as it was, and says so."""
        self.replayed_label.setVisible(self._entry is not None)

    def set_listed(self, listed: bool) -> None:
        """Whether the window's fight is in the fight list, for Show in
        list."""
        self.show_in_list.setEnabled(bool(listed))
        self.show_in_list.setToolTip(SHOW_IN_LIST_TIP if listed else NOT_LISTED_TIP)

    def redraw_pages(self) -> None:
        """The pen/crit settings changed (decision 10): every page drawn
        again, as for a theme switch."""
        self.refresh(self._dark)

    # ---- binding ----

    def _bind(self, entry, unit_id: str) -> None:
        self._entry = entry
        self._unit_id = unit_id
        self._dirty = set(TAB_KEYS)
        self._fill_header()

    def _fill_header(self) -> None:
        """The picker, its buttons, the fight line and the title, for the
        fight and the player bound."""
        entry = self._entry
        rows = player_rows(entry, self._names)
        self.picker.blockSignals(True)
        self.picker.clear()
        for unit_id, text in rows:
            self.picker.addItem(text, unit_id)
        index = self.picker.findData(self._unit_id)
        if index < 0 and rows:
            index = 0
            self._unit_id = rows[0][0]
        self.picker.setCurrentIndex(index)
        self.picker.blockSignals(False)
        # The list shows whole rows, though the field itself is cut at
        # PICKER_CHARS
        view = self.picker.view()
        view.setMinimumWidth(view.sizeHintForColumn(0) + 2 * view.frameWidth()
                             + view.verticalScrollBar().sizeHint().width())
        # A button going off with the focus on it hands the focus to the
        # picker beside it: Qt would move it on along the Tab chain, from ▶
        # past the picker to Show in list
        for button, on in ((self.previous_player, index > 0),
                           (self.next_player, 0 <= index < len(rows) - 1)):
            if not on and self.focusWidget() is button:
                self.picker.setFocus()
            button.setEnabled(on)
        line = fight_line(entry)
        self.fight_label.setText(line)
        self.picker.setAccessibleDescription(line)
        for view in self._views.values():
            view.set_accessible_lead(line)
        self._fill_boss_only()
        self._fill_title()

    def _fill_boss_only(self) -> None:
        """Boss targets only shows on Damage done, for a player with damage
        to the bosses; with none it is cleared too (the damage window's
        rule)."""
        p = player_for(self._entry, self._unit_id) or {}
        damage = p.get("damage") if isinstance(p.get("damage"), dict) else {}
        has_boss = bool(damage and damage.get("boss"))
        if not has_boss and self.boss_only.isChecked():
            self.boss_only.blockSignals(True)
            self.boss_only.setChecked(False)
            self.boss_only.blockSignals(False)
        self.boss_only.setVisible(has_boss and self.current_tab() == DAMAGE_TAB)

    def _fill_title(self) -> None:
        """The title for the tab on screen, the build window's and the
        others' as they were: 'Build – @x (Character)', 'Damage – @x', ...
        'Death recap – @x'."""
        tab = self.current_tab()
        entry, unit_id, names = self._entry, self._unit_id, self._names
        # Those three name the table's row; a player it does not list (Also
        # died) is named as the other tabs name them
        listed = player_for(entry, unit_id) is not None
        if listed and tab == BUILD_TAB:
            title = build_title(entry, unit_id, names)
        elif listed and tab == DAMAGE_TAB:
            title = damage_title(entry, unit_id, names)
        elif listed and tab == TAKEN_TAB:
            title = taken_title(entry, unit_id, names)
        else:
            prefix = {key: title for key, _label, title in TABS}[tab]
            name = _player_name(entry, unit_id, names)
            title = f"{prefix} – {name}" if name else prefix
        self.setWindowTitle(title)

    # ---- drawing ----

    def _draw(self, tab: str) -> None:
        """Draw the page of *tab* for the fight and player bound: in place,
        keeping its scroll, when it last showed the same pair; else from its
        top, the Deaths page at the death asked for."""
        if self._entry is None:
            return
        view = self._views[tab]
        same = self._drawn.get(tab) == (self._entry, self._unit_id)
        if same:
            with view.keeping_place():
                self._render(tab)
        else:
            self._render(tab)
        if tab == DEATHS_TAB and self._death:
            view.open_at_anchor(death_anchor(self._death))
            self._death = None
        self._drawn[tab] = (self._entry, self._unit_id)
        self._dirty.discard(tab)

    def _redraw_current(self) -> None:
        if self.isVisible():
            # The header follows the fight as the page does: the fight
            # line's outcome and length, and the picker's players and deaths
            self._fill_header()
            self._draw(self.current_tab())

    def _render(self, tab: str) -> None:
        view = self._views[tab]
        view.set_link_hover_color(_theme(self._dark)["link"])
        tooltips, page = self._page(tab, view)
        view.set_tooltips(tooltips)
        view.setHtml(page)

    def _page(self, tab: str, view: FightView):
        """(hover text, HTML) of the page of *tab*."""
        entry, unit_id, names, dark = self._entry, self._unit_id, self._names, self._dark
        base_pt = view.font().pointSizeF()
        text_color = view.palette().color(QPalette.Text).name()
        muted = _theme(dark)["muted"]
        p = player_for(entry, unit_id)
        if tab == DEATHS_TAB:
            # The star links, and each death heading's Positions link
            tooltips = kind_tooltips()
            tooltips.update(death_positions_tooltips(entry))
            tooltips.update(death_events_tooltips(entry))
            return tooltips, self._deaths_page(p, view, base_pt, text_color, muted)
        if p is None:
            # A player the table does not list (Also died): no build reached
            # the log
            return {}, f"<p style='color:{muted}'>{NO_BUILD}</p>"
        if p.get("companion") and tab in (PEN_CRIT_TAB, RESOURCES_TAB, TAKEN_TAB, HEALING_TAB):
            return {}, f"<p style='color:{muted}'>{NO_COMPANION_DATA}</p>"
        if tab in (BUILD_TAB, PEN_CRIT_TAB, RESOURCES_TAB):
            # The pages' anchors use the fight view's targets, so its hover
            # text serves; the kinds bars' star links carry the Warfare stars
            tooltips = anchor_tooltips(entry, links=esohub_ability_url, set_links=esohub_set_url,
                                       script_links=esohub_script_url)
            tooltips.update(kind_tooltips())
            part = {BUILD_TAB: BUILD_PART, PEN_CRIT_TAB: PEN_CRIT_PART,
                    RESOURCES_TAB: RESOURCES_PART}[tab]
            # The Settings' assumed Champion Point rows and cap, the
            # config's own, read at each drawing (decision 10)
            options = (self._config.get("pen_crit") if self._config is not None else None) or {}
            return tooltips, render_build_html(
                entry, unit_id, dark=dark, icons=view.icons, links=esohub_ability_url,
                set_links=esohub_set_url, script_links=esohub_script_url, base_pt=base_pt,
                text_color=text_color, pen_crit_options=options, names=names,
                header=False, part=part)
        if tab == DAMAGE_TAB:
            return kind_tooltips(), render_damage_html(
                entry, unit_id, boss_only=self.boss_only.isChecked(), dark=dark,
                icons=view.icons, base_pt=base_pt, names=names, text_color=text_color,
                header=False, dealt_kinds=True)
        return kind_tooltips(), render_taken_html(
            entry, unit_id, dark=dark, icons=view.icons, base_pt=base_pt, names=names,
            text_color=text_color, header=False,
            part=TAKEN_PART if tab == TAKEN_TAB else HEALING_PART)

    def _deaths_page(self, p, view, base_pt: float, text_color: str, muted: str) -> str:
        entry, unit_id, names = self._entry, self._unit_id, self._names
        name = _player_name(entry, unit_id, names)
        if p is not None and p.get("companion"):
            count = int(p.get("deaths") or 0)
            if count:
                times = "once" if count == 1 else f"{count} times"
                line = COMPANION_DIED.format(name=name, count=times)
            else:
                line = DID_NOT_DIE.format(name=name)
            return f"<p style='color:{muted}'>{line}</p>"
        if not deaths_by_unit(entry).get(str(unit_id)):
            return f"<p style='color:{muted}'>{DID_NOT_DIE.format(name=name)}</p>"
        return render_death_recap_html(
            entry, unit_id, dark=self._dark, icons=view.icons, base_pt=base_pt, names=names,
            text_color=text_color, header=False, fight_block=False)

    # ---- tabs and players ----

    def _on_tab_changed(self, index: int) -> None:
        tab = TAB_KEYS[index]
        if self._entry is not None:
            same = self._drawn.get(tab) == (self._entry, self._unit_id)
            if same:
                # Qt dropped the link Tab had the focus on as the page was
                # hidden: it has it again, before a redraw, which keeps it
                self._views[tab].give_link_back()
            if tab in self._dirty or not same:
                self._draw(tab)
        self._fill_boss_only()
        self._fill_title()
        # The window's focus goes into the new page, unless the reader is on
        # the tab bar, moving along it: Qt leaves it where it was, in the
        # picker say, where PgDn would change the player, or on the page
        # just hidden
        if self.focusWidget() is not self.tabs.tabBar():
            self._views[tab].setFocus()

    def _go(self, tab: str, unit_id=None) -> None:
        """A link in a page: tab *tab*, for *unit_id* when it names another
        player of the fight."""
        if unit_id is not None and str(unit_id) != self._unit_id:
            self._switch_player(str(unit_id))
        index = TAB_KEYS.index(tab)
        if self.tabs.currentIndex() == index:
            self._draw(tab)
        else:
            self.tabs.setCurrentIndex(index)
        self._views[tab].setFocus()

    def _to_build(self, unit_id):
        self._go(BUILD_TAB, unit_id)

    def _to_damage(self, unit_id):
        self._go(DAMAGE_TAB, unit_id)

    def _to_pen_crit(self, unit_id):
        self._go(PEN_CRIT_TAB, unit_id)

    def _to_taken(self, unit_id):
        self._go(TAKEN_TAB, unit_id)

    def _to_healing(self, unit_id):
        self._go(HEALING_TAB, unit_id)

    def _to_deaths(self, unit_id):
        self._go(DEATHS_TAB, unit_id)

    def _to_death(self, unit_id, number):
        self._death = number
        if str(unit_id) == self._unit_id:
            self._drawn.pop(DEATHS_TAB, None)  # open at the death, not at its place
        self._go(DEATHS_TAB, unit_id)

    def _to_positions(self, unit_key, ms):
        """A death's Positions link: the main window opens the positions
        window at that moment of the window's fight (issue #214)."""
        if self._entry is not None:
            self.positions_requested.emit(self._entry, str(unit_key), int(ms))

    def _to_events(self, ms):
        """A death's Events link: the main window shows the Events tab
        around that moment of the window's fight (issue #214)."""
        if self._entry is not None:
            self.events_requested.emit(self._entry, int(ms))

    def _switch_player(self, unit_id: str) -> None:
        self._unit_id = unit_id
        self._dirty = set(TAB_KEYS)
        self._fill_header()

    def _on_player_picked(self, index: int) -> None:
        unit_id = self.picker.itemData(index)
        if index < 0 or unit_id is None or str(unit_id) == self._unit_id:
            return
        self._switch_player(str(unit_id))
        self._draw(self.current_tab())

    def _step_player(self, step: int) -> None:
        index = self.picker.currentIndex() + step
        if 0 <= index < self.picker.count():
            self.picker.setCurrentIndex(index)  # draws it (_on_player_picked)

    def _previous_player(self):
        self._step_player(-1)

    def _next_player(self):
        self._step_player(1)

    def _step_tab(self, step: int) -> None:
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % self.tabs.count())

    def _next_tab(self):
        self._step_tab(1)

    def _previous_tab(self):
        self._step_tab(-1)

    def _on_boss_only(self, _checked: bool) -> None:
        if self._entry is not None and self.current_tab() == DAMAGE_TAB:
            self._render(DAMAGE_TAB)
            self._drawn[DAMAGE_TAB] = (self._entry, self._unit_id)
        else:
            self._dirty.add(DAMAGE_TAB)

    def _on_show_in_list(self) -> None:
        if self._entry is not None:
            self.show_in_list_requested.emit(self._entry)

    # ---- size ----

    def _default_size(self):
        """900x840, no more than nine tenths of the screen; wider when the
        tab bar needs it (1,035 px at 200% text)."""
        width = max(DEFAULT_SIZE[0], self.minimumWidth())
        height = DEFAULT_SIZE[1]
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            width = min(width, int(area.width() * 0.9))
            height = min(height, int(area.height() * 0.9))
        return width, height

    def _fit_width(self) -> None:
        """The narrowest the window goes: the tab bar's width at the text
        size in force, plus the margins, so no tab hides behind Qt's scroll
        arrows (605, 793 and 1,035 px at 100, 150 and 200%), unless that is
        wider than nine tenths of the screen."""
        margins = self.layout().contentsMargins()
        width = self.tabs.tabBar().sizeHint().width() + margins.left() + margins.right()
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            width = min(width, int(screen.availableGeometry().width() * 0.9))
        self.setMinimumWidth(width)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.ApplicationFontChange):
            self._fit_width()
