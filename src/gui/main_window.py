"""
Main window: live fight view, session fight history, review mode,
settings, manual archive, and the freshness status bar.
"""

import base64
import sys
import weakref
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QByteArray, QCoreApplication, QEvent, QObject, QProcess, Qt, QThread, QTimer, QUrl, Signal, Slot,
)
from PySide6.QtGui import (
    QAction, QColor, QDesktopServices, QFont, QFontMetrics, QGuiApplication, QKeySequence, QPalette,
    QCursor, QShortcut, QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import (
    QFileDialog, QInputDialog, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QSizePolicy, QSplitter,
    QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

import fight_index
import fight_reread
from ability_icons import esohub_ability_url, esohub_script_url, esohub_set_url
from app_config import AppConfig
from app_startup import engine_settings
from data_staleness import status_text, status_tooltip
from fight_blocks import difficulty_of, fight_key
from fight_index import (
    FightIndex,
    comparison,
    comparison_text,
    earlier_kills,
    fight_line,
    index_path,
    player_history,
    player_history_text,
)
from gui import text_size
from gui.activity_render import (
    OPEN_AT_FIRST, activity_paths, activity_tooltips, empty_state_html, status_text as empty_status_text,
)
from gui.build_issues_popup import BuildIssuesPopup
from gui.build_render import player_for
from gui.death_render import (
    death_tooltips, deaths_by_unit, fight_moment, fight_positions_tooltips, positions_known,
)
from gui.dps_graph import DpsGraphPanel
from gui.engine_worker import EngineWorker
from gui.events_tab import EventsPage
from gui.fight_deaths_render import fight_deaths_tooltips, render_fight_deaths_html
from gui.fight_list import FightList
from gui.fight_render import (
    EARLIER_LABEL, ISSUES_CUE, REVIEWED_LABEL, SPLIT_FOLDER_NOTE, SPLIT_LABEL, SPLIT_MISSING_NOTE,
    SPLIT_UNKNOWN_NOTE, SPLITS_OFF_NOTE,
    anchor_names, anchor_tooltips, build_tooltips, damage_tooltips, issues_html,
    set_tooltips,
    issues_tooltips, link_color, mastery_tooltips, misfortunes_tooltips, muted_color, pen_crit_tooltips,
    render_html,
    render_plain_text, split_tooltips, taken_tooltips,
)
from gui.fight_tabs import FightViews, count_text
from gui.fight_view import FightView, set_reduce_motion
from gui.instance_render import instance_tooltips, render_instance_html, run_anchor
from gui.name_mask import NameMask
from gui.player_window import (
    BUILD_TAB, DAMAGE_TAB, DEATHS_TAB, PEN_CRIT_TAB, TAKEN_TAB, PlayerWindow,
)
from gui.review_runner import ReviewRunner
from gui.settings_dialog import SettingsDialog
from gui.timeline_strip import TimelineStrip, given_by_caster, strip_timeline
from gui.update_poller import UpdatePoller
from gui.update_popup import UpdateNotesPopup
from log_open import is_zip, log_members, log_size
from pen_crit import armour_row
from pull_outcome import runs
import recent_activity
from recycle_bin import TRASH_NAME
from session_splits import earlier_split, splits_for
import review_load
from session_recap import DISCORD_LIMIT, recap_text
import split_retention
from update_check import CHANNEL_CHOICES, format_release_date, normalize_channel
from version import __version__

# The fight pane's least height, in pixels (see _build_ui, #206)
PANE_LEAST_PX = 48

# Freshness state thresholds (log-freshness spec)
LIVE_SECONDS = 2 * 60
IDLE_SECONDS = 30 * 60

# State colors per theme: dark backgrounds need lighter accents and vice versa
_STATE_COLORS = {
    True: {"live": "#81c784", "idle": None, "stale": "#ffb74d", "none": "#e57373"},
    False: {"live": "#2e7d32", "idle": None, "stale": "#aa5600", "none": "#c62828"},
}


# Windows updates through its installer; other platforms have none, so an
# update there is a download from the release page
HAS_INSTALLER = sys.platform == "win32"

# Split log retention: the first run waits for startup's replay, then daily
RETENTION_FIRST_DELAY_MS = 30 * 1000
RETENTION_INTERVAL_MS = 24 * 60 * 60 * 1000

# How long closing the window waits for a fight re-read's thread to end
# (see closeEvent): an idle runner closes in 0.4 to 1.4 ms (probed)
REREAD_CLOSE_S = 1.0


class _RetentionBridge(QObject):
    """Carries a retention run's events from its thread to this one."""
    event = Signal(object)  # split_retention.RetentionEvent


class _ReviewBridge(QObject):
    """Carries a review's events from its thread to this one."""
    event = Signal(object)  # gui.review_runner.ReviewEvent


class _RereadBridge(QObject):
    """Carries a fight re-read's events from its thread, 'fight-reread',
    to this one (issue #214)."""
    event = Signal(object)  # fight_reread.RereadEvent


def _duration_text(seconds: float) -> str:
    """'about 40 seconds', 'about 9 minutes' for a review's time estimate."""
    if seconds < 90:
        return f"about {max(10, round(seconds / 10) * 10)} seconds"
    return f"about {round(seconds / 60)} minutes"


def state_style(state: str, dark: bool) -> str:
    color = _STATE_COLORS[bool(dark)].get(state)
    return f"color: {color};" if color else ""


def _encode_state(state: QByteArray) -> str:
    """Qt state blob -> JSON-safe text for the config file."""
    return base64.b64encode(bytes(state)).decode("ascii")


def reveal_file(path: Path) -> None:
    """Show *path* in its folder: on Windows, Explorer with the file
    selected, since a split folder holds hundreds of files (issue #194),
    started detached, so nothing is left to wait for; elsewhere the
    folder."""
    if sys.platform == "win32":
        explorer = QProcess()
        explorer.setProgram("explorer")
        # One argument as Explorer reads it, the path quoted inside it
        explorer.setNativeArguments(f'/select,"{path}"')
        explorer.startDetached()
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def _decode_state(text) -> "QByteArray | None":
    """Inverse of _encode_state; None for a missing or unreadable value."""
    if not isinstance(text, str) or not text:
        return None
    try:
        return QByteArray(base64.b64decode(text, validate=True))
    except (ValueError, TypeError):
        return None


def _hand_back(worker: EngineWorker, home: QThread, requests) -> None:
    """Called on the worker's thread as it finishes: cut the window's
    (signal, slot) *requests* to the worker, so an ended engine takes no more
    work, and move the worker to *home*, the UI thread (see
    gui/engine_worker.py). Disconnecting is safe from any thread."""
    for signal, slot in requests:
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError):
            pass  # not connected, or already gone
    worker.leave_thread(home)


class MainWindow(QMainWindow):

    request_archive = Signal()
    request_restart = Signal()
    request_review = Signal(str, str)  # path, log in a zip ("" = its only one)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._update = None  # the UpdateInfo on offer (the toolbar button), or None
        self._apply_title()
        self.resize(1080, 720)

        self._fights = []          # live session FightHistoryEntry list
        self._review_fights = None  # list when in review mode, else None
        self._review_path = None
        # The reviewed file and its zip member ('' for its only one) as the
        # review read them, where _review_path is the label shown, for the
        # positions window to read a reviewed fight from (issue #214); and
        # (fight, source) for each fight of an earlier review a window still
        # holds (_keep_review_source)
        self._review_source = None
        self._past_reviews = []
        self._detailed = True
        self._last_status = None
        self._follow_live = True
        self._restart_pending = False  # Save pressed, engine not yet restarted
        # A Settings replay under way (issue #196): following live is held
        # off, and the fight to select again as the replay brings it back
        # is known by its key (fight_blocks.fight_key), None for the newest
        # once the replay is in (_on_monitoring_restarting)
        self._replaying = False
        self._replay_key = None
        self._last_placeholder = ""
        # The pane before the first fight (gui.activity_render, issue #191):
        # why it is empty ('monitoring', 'waiting' or 'back'; None once a
        # fight is on it), where the log was looked for, the recent
        # archives and splits the page links to, whether their lists are
        # open (the reader's choice, kept for the session), and the archive
        # whose completion deleted the log this session, which alone lets
        # the page say the missing log was archived
        self._empty_reason = None
        self._empty_expected = ""
        self._activity = None
        self._activity_open = OPEN_AT_FIRST
        self._archive_that_deleted_log = None
        # The engine waits for a log that is not there (waiting_for_log)
        # until it monitors one (monitoring_started) or restarts, which may
        # find it: Back to live with no fight listed then waits too
        # (_exit_review), and the bar keeps its explanation under a review
        # or a fight (_refresh_freshness_label)
        self._log_missing = False
        # The player window, created at the first player link (issue #196),
        # and the positions window, at the first Positions link (issue
        # #214); and for each window on a live fight as a Settings replay
        # begins, by the attribute that holds it, what finds its fight again
        # (_on_monitoring_restarting, _rebind_windows)
        self._player_window = None
        self._positions_window = None
        self._replay_keys = {}
        # The DPS graph tab's page is to be drawn before it is next shown
        self._graph_dirty = True
        # The fight's tabs (gui.fight_tabs, issue #196): the tab chosen, which
        # stays as the fights change, and the fight the Deaths page shows,
        # with whether it is to be drawn again before it is next shown
        self._chosen_tab = 0
        self._deaths_entry = None
        self._deaths_dirty = True
        # The fight the Events page shows (gui.events_tab, issue #214), and
        # whether it is to be drawn again before it is next shown
        self._events_entry = None
        self._events_dirty = True
        # The fight the Fight page shows, and for a page drawn while another
        # tab is on screen, where its search goes on when it is shown: from
        # its place among the matches for the same fight drawn again, None
        # for a new fight's first match (_note_search_place)
        self._fight_entry = None
        self._search_places = {}
        # The search's text when it last ran on each page: a search typed on
        # one tab starts at the other's first match when that is shown
        self._searched = {}
        # The Instance tab's page (gui.instance_render): the block of the
        # list it was drawn for, its fights by the place in the list its
        # links carry, and whether it is to be drawn again before it is next
        # shown
        self._instance_block = []
        self._instance_links = {}
        self._instance_dirty = True
        # The split logs listed on the Fight page's result strip and on the
        # Instance page, as each was drawn: their links carry a place in
        # these lists, never a path (issue #194)
        self._fight_split_files = []
        self._instance_split_files = []
        # Theme-aware text colors: pick per the actual window background
        self._dark = self.palette().color(self.backgroundRole()).lightness() < 128
        # The Hide names switch (issue #72, gui.name_mask): every player
        # name but the logging player's hidden, for screenshots and
        # sharing. One state behind the toolbar button, Ctrl+H and the
        # Settings box, saved whenever it flips
        self._hide_names = bool(config.get("privacy.hide_names", False))
        # The text size, before any widget is made, so all of them start at it
        text_size.apply(config.get(text_size.CONFIG_KEY, text_size.DEFAULT_PCT))
        set_reduce_motion(bool(config.get("display.reduce_motion", False)))
        # The fight history across sessions (fight_index, issue #170): read
        # once here, beside the config, and written as fights come
        self.fight_index = FightIndex(index_path(config.path))
        self.fight_index.load()

        self._build_ui()
        self.history_list.history_index = self.fight_index
        self._build_update_poller()
        self._build_retention()
        self._build_review()
        self._build_reread()
        self._build_worker()  # last: the engine thread starts here
        # The once-only hint about building the fight history, shown after
        # 'Monitoring …' (_on_monitoring_started), which would replace it
        self._backfill_hint_due = True

        # Follow live theme switches (e.g. Windows auto dark mode after
        # sunset): rendered HTML embeds theme colors, so it must re-render.
        # A bound method, not a lambda: Qt drops the connection when the
        # window is destroyed, where a lambda would keep the window alive
        # from the application's style hints and later call into it dead
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_color_scheme_changed)
        except AttributeError:
            pass  # older Qt: changeEvent still covers palette changes

    def _on_color_scheme_changed(self, *_):
        self._on_theme_maybe_changed()

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.PaletteChange, QEvent.ThemeChange,
                            QEvent.ApplicationPaletteChange):
            self._on_theme_maybe_changed()
        super().changeEvent(event)

    def _on_theme_maybe_changed(self):
        dark = self.palette().color(self.backgroundRole()).lightness() < 128
        if dark == self._dark:
            return
        self._dark = dark
        # Re-render everything that bakes theme colors into its output
        self._refresh_freshness_label()
        self._refresh_warning_label()
        self._refresh_data_label()
        self._style_update_buttons()
        self.timeline_strip.update()
        for window in self._windows():
            window.refresh(dark)
        if self.history_list.current_entry() is not None:
            # Where the reader had it, as the windows keep theirs
            self._redraw_fight()
        elif self._empty_reason is not None:
            self._show_empty_state(self._empty_reason)  # its links take the theme's colour
        elif self._last_placeholder:
            self._show_placeholder(self._last_placeholder)

    # ---- UI construction ----

    def _build_ui(self):
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        self.detail_action = QAction("Detail view", self)
        self.detail_action.setCheckable(True)
        self.detail_action.setChecked(True)
        # Not Tab, which this once was: Tab has to move the focus, or a
        # keyboard user never leaves the fight list (#77)
        self.detail_action.setShortcut(QKeySequence("Ctrl+D"))
        self.detail_action.setToolTip(
            "Show each player's ability bars as icons, or one line per player (Ctrl+D)")
        self.detail_action.toggled.connect(self._toggle_detail)
        toolbar.addAction(self.detail_action)

        copy_action = QAction("Copy fight", self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_current)
        toolbar.addAction(copy_action)

        # The whole list as a recap for Discord (session_recap, issue #171)
        self.copy_session_action = QAction("Copy session", self)
        self.copy_session_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.copy_session_action.setToolTip(
            "Copy every fight in the list as a short recap: each boss's pulls, the kills, "
            "what ended the pulls (Ctrl+Shift+C)")
        self.copy_session_action.triggered.connect(self._copy_session)
        toolbar.addAction(self.copy_session_action)

        self.graph_action = QAction("DPS graph", self)
        self.graph_action.triggered.connect(self._show_graph)
        toolbar.addAction(self.graph_action)

        self.hide_names_action = QAction("Hide names", self)
        self.hide_names_action.setCheckable(True)
        self.hide_names_action.setChecked(self._hide_names)
        self.hide_names_action.setShortcut(QKeySequence("Ctrl+H"))
        # From any of the app's windows, not only this one: the key is for
        # the moment before a screenshot of a build or a recap too
        self.hide_names_action.setShortcutContext(Qt.ApplicationShortcut)
        self.hide_names_action.setToolTip(
            "Hide other players' handles and character names, for screenshots and "
            "sharing; the player writing the log stays visible (Ctrl+H)")
        self.hide_names_action.toggled.connect(self._toggle_hide_names)
        toolbar.addAction(self.hide_names_action)

        # Text size (issue #77): Ctrl+= or Ctrl++ bigger, Ctrl+- smaller,
        # Ctrl+0 back to 100%, from any of the app's windows, saved at once
        for label, keys, direction in (("Bigger text", ("Ctrl+=", "Ctrl++"), 1),
                                       ("Smaller text", ("Ctrl+-",), -1),
                                       ("Normal text size", ("Ctrl+0",), 0)):
            action = QAction(label, self)
            action.setShortcuts([QKeySequence(key) for key in keys])
            action.setShortcutContext(Qt.ApplicationShortcut)
            action.triggered.connect(lambda _=False, d=direction: self._step_text_size(d))
            self.addAction(action)

        toolbar.addSeparator()

        review_action = QAction("Open log for review…", self)
        review_action.triggered.connect(self._open_review_dialog)
        toolbar.addAction(review_action)

        self.back_to_live_action = QAction("Back to live", self)
        self.back_to_live_action.triggered.connect(self._exit_review)
        self.back_to_live_action.setVisible(False)
        toolbar.addAction(self.back_to_live_action)

        toolbar.addSeparator()

        archive_action = QAction("Archive now", self)
        archive_action.triggered.connect(self._confirm_archive)
        toolbar.addAction(archive_action)

        settings_action = QAction("Settings…", self)
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

        about_action = QAction("About…", self)
        about_action.triggered.connect(self._show_about)
        toolbar.addAction(about_action)

        # The Update button and its ⓘ at the right end, shown only while a
        # newer release is on offer (issue #56: a button, never a pop-up).
        # Toolbar widgets are shown and hidden through their actions: the
        # toolbar's layout shows a widget again that was hidden directly
        stretch = QWidget()
        stretch.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(stretch)
        self.update_button = QToolButton()
        self.update_button.setAutoRaise(True)
        self.update_button.clicked.connect(self._on_update_clicked)
        self.update_action = toolbar.addWidget(self.update_button)
        self.update_action.setVisible(False)
        self.update_info_button = QToolButton()
        self.update_info_button.setAutoRaise(True)
        self.update_info_button.setText(ISSUES_CUE)
        self.update_info_button.clicked.connect(self._show_update_notes)
        self.update_info_action = toolbar.addWidget(self.update_info_button)
        self.update_info_action.setVisible(False)
        self._style_update_buttons()

        splitter = QSplitter(Qt.Horizontal)
        # The fights in blocks by instance, with each completed run's result
        # (gui.fight_list, issue #129)
        self.history_list = FightList()
        self.history_list.currentRowChanged.connect(self._show_fight)
        # A header, run or result row: the Instance tab on its instance
        self.history_list.instance_requested.connect(self._open_instance_from_list)
        # The (i)'s hover text hides names as the rest of the window does
        self.history_list.hide_names = self._hide_names
        splitter.addWidget(self.history_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 6, 6, 6)
        self.banner = QLabel("")
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        self.banner.setStyleSheet(
            "background: #37474f; color: #eceff1; padding: 6px; border-radius: 4px;")
        right_layout.addWidget(self.banner)
        # The fight's tabs, and the search in the tab bar's corner or on a
        # row of its own (gui.fight_tabs, issue #196)
        self.fight_views = FightViews()
        self.fight_tabs = self.fight_views.tabs
        fight_page = QWidget()
        fight_layout = QVBoxLayout(fight_page)
        fight_layout.setContentsMargins(0, 0, 0, 0)
        # EXPERIMENTAL buff timeline strip: sits between the header area and
        # the summary text; hidden whenever the fight has no timeline data
        self.timeline_strip = TimelineStrip()
        fight_layout.addWidget(self.timeline_strip)

        # The search: highlights every match on the tab on screen, the count
        # drawn inside the field
        self.search_field = self.fight_views.search_field
        self.search_field.textChanged.connect(self._apply_search)
        self.search_field.returnPressed.connect(self._goto_next_match)
        self.search_count = self.search_field.count_label

        # Serves bundled ability icons, hover names, and ESO-Hub link clicks
        self.fight_view = FightView()
        self.fight_view.setAccessibleName("Fight")
        # The tab bar costs the window's least height its own (25 px at 100%
        # text, 39 at 200%), which kept the window from fitting a 1280x720
        # screen at 200% (#206): the pane's least height is Qt's 70 px less
        # that, a line or two of the page when the window is at its least
        self.fight_view.setMinimumHeight(PANE_LEAST_PX)
        self.fight_view.death_recap_requested.connect(self._show_death_recap)
        self.fight_view.build_requested.connect(self._show_build)
        self.fight_view.damage_requested.connect(self._show_damage)
        self.fight_view.taken_requested.connect(self._show_taken)
        self.fight_view.graph_requested.connect(self._show_graph)
        self.fight_view.issues_requested.connect(self._show_issues)
        self.fight_view.pen_crit_requested.connect(self._show_pen_crit)
        self.fight_view.banner_requested.connect(self._show_banner)
        self.fight_view.split_requested.connect(self._fight_split)
        self.fight_view.fight_deaths_requested.connect(self._show_fight_deaths)
        # The header's Positions: the positions window (issue #214)
        self.fight_view.fight_positions_requested.connect(self._show_fight_positions)
        # The empty pane's Recent activity link and the files under it
        self.fight_view.activity_requested.connect(self._on_activity_requested)
        self.fight_view.review_requested.connect(self._on_review_requested)
        # The trial score banner captured from the screen (gui.banner_burst,
        # issue #167): the burst running, the runs already tried this
        # session, the files captured this session by run (the fight that
        # carries a result arrives after the burst started), and the log
        # the engine monitors, whose folder holds the banners by default
        self._banner_burst = None
        self._banner_done = set()
        self._banner_files = {}
        self._log_path = None
        fight_layout.addWidget(self.fight_view, 1)
        self.fight_views.add_tab(fight_page, "&Fight")
        # Every death of the fight on one page (gui.fight_deaths_render); a
        # name opens that death in the player window, its Positions where
        # everyone stood then (issue #214)
        self.deaths_view = FightView(icons=self.fight_view.icons)
        self.deaths_view.setAccessibleName("Deaths")
        self.deaths_view.recap_requested.connect(self._show_fight_death)
        self.deaths_view.positions_requested.connect(self._show_deaths_positions)
        self.fight_views.add_tab(self.deaths_view, "D&eaths")
        # The fight's notable events as a table (gui.events_tab, issue
        # #214): a death's row opens that death in the player window
        self.events_view = EventsPage(icons=self.fight_view.icons)
        self.events_view.recap_requested.connect(self._show_event_death)
        self.fight_views.add_tab(self.events_view, "E&vents")
        # The dps over time graph (gui.dps_graph), a tab where it was a window
        self.dps_panel = DpsGraphPanel()
        self.dps_panel.setAccessibleName("DPS graph")
        self.dps_panel.set_colorblind(bool(self.config.get("display.colorblind_graph", False)))
        self.fight_views.add_tab(self.dps_panel, "DPS &graph")
        # The instance the fight belongs to, its block of the list
        # (gui.instance_render): a pull opens that fight, a name that player
        self.instance_view = FightView(icons=self.fight_view.icons)
        self.instance_view.setAccessibleName("Instance")
        self.instance_view.fight_requested.connect(self._open_instance_fight)
        self.instance_view.player_requested.connect(self._open_instance_player)
        self.instance_view.instance_copy_requested.connect(self._copy_instance)
        self.instance_view.banner_requested.connect(self._instance_banner)
        self.instance_view.split_requested.connect(self._instance_split)
        self.fight_views.add_tab(self.instance_view, "&Instance")
        self.fight_tabs.currentChanged.connect(self._on_fight_tab_changed)
        self.fight_views.search_placed.connect(self._set_tab_order)
        # The Find button the tab bar's corner holds at a large text size
        self.fight_views.find_requested.connect(self._find)
        right_layout.addWidget(self.fight_views, 1)

        # Esc in the search field is the field's own (gui.fight_tabs)
        find = QAction("Find", self)
        find.setShortcut(QKeySequence.Find)
        find.triggered.connect(self._find)
        self.addAction(find)
        # The fight's tabs from anywhere in the window, the list too: the tab
        # widget's own keys work only with the focus inside it
        QShortcut(QKeySequence("Ctrl+PgDown"), self, self._next_fight_tab)
        QShortcut(QKeySequence("Ctrl+PgUp"), self, self._previous_fight_tab)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)
        self._splitter = splitter
        self._set_tab_order()

        # Status bar: freshness (left), zone (middle), archive progress (right)
        self.freshness_label = QLabel("No log file")
        self.statusBar().addWidget(self.freshness_label)
        self.zone_label = QLabel("")
        self.statusBar().addWidget(self.zone_label)
        # Lasting problems (issue #111): split writing stopped, the log
        # failing to read poll after poll. Permanent, so a status message
        # never hides it; it goes when its source says the problem cleared
        self._warnings = {}
        # The game version against the bundled data's, and what the log
        # named that the data does not know (issue #173): a label of its
        # own, beside the warnings, shown only when there is something to say
        self._data_check = None
        self.data_label = QLabel("")
        self.data_label.setVisible(False)
        self.statusBar().addPermanentWidget(self.data_label)
        self.warning_label = QLabel("")
        self.warning_label.setVisible(False)
        self.statusBar().addPermanentWidget(self.warning_label)
        # Shared work-progress bar (archiving, review parsing, catch-up). A
        # review runs on its own thread, so its progress can meet a live
        # catch-up's here; the next review update shows it again
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(220)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.review_cancel_button = QToolButton()
        self.review_cancel_button.setText("Cancel review")
        self.review_cancel_button.setAutoRaise(True)
        self.review_cancel_button.setVisible(False)
        self.statusBar().addPermanentWidget(self.review_cancel_button)

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._refresh_freshness_label)
        self._ticker.start()

        self._show_placeholder("Starting…")
        self._restore_window_layout()

    # ---- window placement ----

    def _restore_window_layout(self):
        """Put the window and the history/fight split back where they were
        when the app was last closed. Qt's restoreGeometry() keeps a window
        that was on a monitor which is no longer attached on a visible
        screen, so a stale value is safe to apply."""
        geometry = _decode_state(self.config.get("window.geometry"))
        if geometry is not None:
            self.restoreGeometry(geometry)
        splitter = _decode_state(self.config.get("window.splitter"))
        if splitter is not None:
            self._splitter.restoreState(splitter)
        else:
            # A first run: the fight list a third of the window, as it had
            # before the fight's tabs. The splitter shares out width it was
            # never given by the pages' sizes, and the DPS graph tab's took
            # the list from 348 px of 1080 down to 226 (issue #196)
            third = self.width() // 3
            self._splitter.setSizes([third, self.width() - third])

    def _save_window_layout(self):
        self.config.set("window.geometry", _encode_state(self.saveGeometry()))
        self.config.set("window.splitter", _encode_state(self._splitter.saveState()))
        # The player window's and the positions window's too, here: a
        # dialog gets no close event when the app quits (issue #196)
        if self._player_window is not None:
            self.config.set("window.player_geometry",
                            _encode_state(self._player_window.saveGeometry()))
        if self._positions_window is not None:
            self.config.set("window.positions_geometry",
                            _encode_state(self._positions_window.saveGeometry()))
        self.config.save()

    def _build_worker(self):
        self.worker_thread = QThread(self)
        self.worker = EngineWorker(self.config)
        self.worker.moveToThread(self.worker_thread)

        self.worker.fight_completed.connect(self._on_fight_completed)
        self.worker.fight_updated.connect(self._on_fight_updated)
        self.worker.zone_changed.connect(self._on_zone_changed)
        self.worker.log_status.connect(self._on_log_status)
        self.worker.archive_event.connect(self._on_archive_event)
        self.worker.diagnostic.connect(self._on_diagnostic)
        self.worker.warning.connect(self._on_warning)
        self.worker.data_check.connect(self._on_data_check)
        self.worker.waiting_for_log.connect(self._on_waiting_for_log)
        self.worker.monitoring_started.connect(self._on_monitoring_started)
        self.worker.monitoring_restarting.connect(self._on_monitoring_restarting)
        self.worker.parse_progress.connect(self._on_parse_progress)
        self.worker.trial_result.connect(self._on_trial_result)

        requests = ((self.request_archive, self.worker.archive_now),
                    (self.request_restart, self.worker.restart_monitoring))
        for signal, slot in requests:
            signal.connect(slot)

        self.worker_thread.started.connect(self.worker.start)
        # Teardown (see gui/engine_worker.py): as its thread finishes, still
        # on that thread, the worker is cut off from the window's requests
        # (an ended engine takes no more work) and moves itself to this, the
        # UI thread, since only its own thread may move it; then
        # _discard_worker deletes it here
        home = self.thread()
        worker = self.worker
        self.worker_thread.finished.connect(lambda: _hand_back(worker, home, requests),
                                            Qt.DirectConnection)
        self.worker_thread.finished.connect(self._discard_worker)
        self.worker_thread.start()

    def _build_retention(self):
        """Split log retention (split_retention, issues #86 and #87): a run shortly
        after startup, so the session replay goes first, then once a day.
        Runs have a thread of their own and report through a QObject that
        lives here; the thread holds it weakly, so it is never the one to
        free it (see gui/engine_worker.py on freeing Qt objects)."""
        self._retention = split_retention.RetentionRunner()
        self._retention_bridge = _RetentionBridge(self)
        self._retention_bridge.event.connect(self._on_retention_event)
        self._retention_first = QTimer(self)
        self._retention_first.setSingleShot(True)
        self._retention_first.setInterval(RETENTION_FIRST_DELAY_MS)
        self._retention_first.timeout.connect(self._start_retention)
        self._retention_first.start()
        self._retention_daily = QTimer(self)
        self._retention_daily.setInterval(RETENTION_INTERVAL_MS)
        self._retention_daily.timeout.connect(self._start_retention)
        self._retention_daily.start()

    def _start_retention(self):
        try:
            settings = split_retention.settings_from_config(self.config)
        except Exception as exc:
            self.statusBar().showMessage(f"Split log retention skipped: {exc}", 15000)
            return
        bridge = weakref.ref(self._retention_bridge)

        def notify(event):
            target = bridge()
            if target is not None:
                target.event.emit(event)

        self._retention.start(settings, notify)

    @Slot(object)
    def _on_retention_event(self, event):
        if event.kind == "started":
            noun = "log" if event.total == 1 else "logs"
            self.statusBar().showMessage(f"Tidying {event.total} old split {noun}…")
        elif event.kind == "progress":
            doing = f"Moving to the {TRASH_NAME}" if event.action == "delete" else "Zipping"
            self.statusBar().showMessage(
                f"Old split logs, {event.done + 1} of {event.total}: {doing} {event.name}")
        elif event.kind == "completed":
            parts = []
            if event.deleted:
                noun = "log" if event.deleted == 1 else "logs"
                parts.append(f"Moved {event.deleted} split {noun} "
                             f"({split_retention.format_bytes(event.freed)}) to the {TRASH_NAME}")
            if event.zipped:
                noun = "log" if event.zipped == 1 else "logs"
                parts.append(f"Zipped {event.zipped} split {noun}, "
                             f"{split_retention.format_bytes(event.saved)} saved")
            text = "; ".join(parts) or "No split logs changed"
            if event.skipped:
                text += f"; {len(event.skipped)} left as they were: {event.skipped[0]}"
            self.statusBar().showMessage(text, 30000)
        elif event.kind == "failed":
            self.statusBar().showMessage(f"Tidying split logs failed: {event.reason}", 30000)

    # ---- review (gui/review_runner.py, issue #107) ----

    def _build_review(self):
        """Reviews run on a thread of their own and report through a QObject
        that lives here; the thread holds it weakly, so it is never the one
        to free it (see gui/engine_worker.py on freeing Qt objects)."""
        self._review = ReviewRunner()
        self._backfilling = False  # the review thread is reading the split logs
        self._review_bridge = _ReviewBridge(self)
        self._review_bridge.event.connect(self._on_review_event)
        self.review_cancel_button.clicked.connect(self._review.cancel)
        self.request_review.connect(self._start_review)

    def _review_notify(self):
        bridge = weakref.ref(self._review_bridge)

        def notify(event):
            target = bridge()
            if target is not None:
                target.event.emit(event)
        return notify

    # ---- re-reading a fight for the positions window (fight_reread, #214) ----

    def _build_reread(self):
        """A fight's lines are read again on a thread of their own,
        'fight-reread' (fight_reread.RereadRunner), never the review's,
        which a review keeps busy for minutes. The thread holds no Qt
        object: it reports through a QObject that lives here, a child of
        this window rather than of the positions window, so it lives as long
        as this window and the thread's weak hold on it is enough (see
        gui/engine_worker.py on freeing Qt objects). The read last asked
        for and not yet answered is kept (_reread_pending), so a second
        link to the same fight while it is read asks for nothing."""
        self._reread = fight_reread.RereadRunner()
        self._reread_bridge = _RereadBridge(self)
        self._reread_bridge.event.connect(self._on_reread_event)
        self._reread_pending = None
        self._reread_closed = False

    def _reread_notify(self):
        """The runner's notify: called on 'fight-reread', it emits on the
        bridge, which Qt queues to this thread. The bridge is held weakly,
        and an emit on a bridge whose C++ side has gone (the window being
        deleted) raises RuntimeError even while the weak reference still
        holds the wrapper (probed): it is caught, as an exception out of
        notify would otherwise end the runner's thread for every later read
        in a runner that did not catch it."""
        bridge = weakref.ref(self._reread_bridge)

        def notify(event):
            target = bridge()
            if target is None:
                return
            try:
                target.event.emit(event)
            except RuntimeError:
                pass  # the window is going: no one waits for the read
        return notify

    @Slot(object)
    def _on_reread_event(self, event):
        """A read's answer, on this thread: to the positions window, which
        keeps only the one for the locator it waits for (a read superseded
        by a newer request answers 'cancelled' with its old locator). Only
        an answer clears the read asked for: a 'cancelled' read was
        superseded by a newer request, perhaps for the same fight, which
        is the one waited for now. Locators are matched by identity, as the
        window takes its answers: a Settings replay's equal copy is read
        once more rather than left waiting for an answer it would drop."""
        if event.kind != "cancelled" and event.locator is self._reread_pending:
            self._reread_pending = None
        window = self._positions_window
        if window is not None:
            window.reread_done(event)

    def _set_review_busy(self, busy: bool):
        self.review_cancel_button.setVisible(busy)
        if not busy:
            self.progress_bar.setVisible(False)

    @Slot(str, str)
    def _start_review(self, path, member=""):
        """A log above review_load.LARGE_REVIEW_BYTES is outlined first and
        the reader asked whether to read all of it; a smaller one replays
        at once."""
        if self._review.running:
            self.statusBar().showMessage("A review is still loading: cancel it first", 8000)
            return
        try:
            size = log_size(Path(path), member or None)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Review", f"Could not read {path}: {exc}")
            return
        self._set_review_busy(True)
        if size > review_load.LARGE_REVIEW_BYTES:
            self._on_parse_progress(f"Looking through {Path(path).name}", 0, 0)
            self._review.outline(path, member, self._review_notify())
        else:
            self._review.replay(self.config, path, member, -1, self._review_notify())

    @Slot(object)
    def _on_review_event(self, event):
        if event.kind == "progress":
            self._on_parse_progress(event.label, event.done, event.total)
            return
        self._set_review_busy(False)
        if event.kind == "outlined":
            self._ask_review_range(event)
        elif event.kind == "loaded":
            # The file and member as read, not the label shown, which for a
            # zip of several logs is no path
            self._on_review_loaded(event.shown, event.fights, source=(event.path, event.member))
        elif event.kind == "indexed":
            # The fight history grew: the run rows and the pane read it
            self.statusBar().showMessage(event.label, 15000)
            self.history_list.refresh_all_runs()
            if self.history_list.current_entry() is not None:
                self._redraw_fight()  # each page where the reader had it
        elif event.kind == "cancelled" and self._backfilling:
            self.statusBar().showMessage(
                "Fight history paused: Build from split logs in Settings carries on "
                "where it stopped", 15000)
            self.history_list.refresh_all_runs()
        elif event.kind == "cancelled":
            self.statusBar().showMessage(f"Review of {Path(event.path).name} cancelled", 8000)
        elif event.kind == "failed":
            self.statusBar().clearMessage()
            what = "build the fight history from" if self._backfilling else "review"
            QMessageBox.warning(self, "Review",
                                f"Could not {what} {event.path}:\n{event.reason}")
        self._backfilling = False

    # ---- the fight history's backfill (fight_index, issue #170) ----

    def _split_folder(self, log=None):
        """The split folder: the one set, else the log's own (the
        splitter's rule, as split retention reads it). *log*: the log, when
        the caller already knows it (_known_log), else resolved here."""
        try:
            return split_retention.split_folder(
                self.config.get("split.dir") or "",
                log if log is not None else
                split_retention.resolve_log(self.config.get("log_path") or ""))
        except OSError:
            return None

    def history_status(self) -> str:
        """Settings' line on the fight history: what it holds and where."""
        count = len(self.fight_index)
        held = (f"{count} boss fight{'s' if count != 1 else ''} on "
                f"{self.fight_index.sessions()} day{'s' if self.fight_index.sessions() != 1 else ''}"
                if count else "No boss fights yet")
        return f"{held}, in {self.fight_index.path}"

    def start_backfill(self, folder=None) -> tuple[bool, str]:
        """Read the split logs into the fight history on the review thread
        (gui.review_runner.ReviewRunner.backfill); the status bar shows the
        progress and its Cancel button stops it. *folder*: the split folder
        to read (Settings passes the one in its fields, saved or not), else
        the saved one. (whether it started, what to tell the reader)."""
        folder = Path(folder) if folder else self._split_folder()
        if folder is None or not folder.is_dir():
            return False, "There is no split folder to read: set one under Per-encounter split files."
        if self._review.running:
            return False, "A review is still loading: cancel it first, then build again."
        self._backfilling = True
        self._set_review_busy(True)
        self._on_parse_progress("Fight history: looking through the split logs", 0, 0)
        if not self._review.backfill(self.config, str(folder), self.fight_index,
                                     self._review_notify()):
            self._backfilling = False
            self._set_review_busy(False)
            return False, "A review is still loading: cancel it first, then build again."
        return True, f"Building from {folder}: see the status bar."

    def _offer_backfill(self):
        """Once, while the fight history is empty and the split folder holds
        logs: a line in the status bar saying where to build it (no
        pop-up). Settings notes that it was offered."""
        if len(self.fight_index) or self.config.get("history.backfill_offered", False):
            return
        folder = self._split_folder()
        if folder is None:
            return
        try:
            logs = sum(1 for path in folder.iterdir() if fight_index.is_split_name(path.name))
        except OSError:
            return
        if not logs:
            return
        self.statusBar().showMessage(
            f"Your fight history is empty: Settings, Fight history, Build from split logs "
            f"reads your {logs} split log{'s' if logs != 1 else ''}", 60000)
        self.config.set("history.backfill_offered", True)
        try:
            self.config.save()
        except OSError:
            pass

    def _ask_review_range(self, event):
        """The whole log, or its most recent sessions holding at least
        review_load.RECENT_FIGHTS fights (a cut is always at a session
        start: see review_load)."""
        # No fight counts here: the outline counts BEGIN_COMBAT lines, and
        # the engine merges or drops some (62 counted, 47 listed, on a
        # month's log), so sessions, size and time are what it states
        outline = event.outline
        name = Path(event.path).name
        sessions = len(outline.starts)
        recent = outline.recent()
        box = QMessageBox(self)
        box.setWindowTitle("Review")
        box.setIcon(QMessageBox.Information)
        box.setText(f"{name} is {split_retention.format_bytes(outline.total)}, "
                    f"{sessions} session{'s' if sessions != 1 else ''} of play.")
        box.setInformativeText(
            f"Reading all of it takes {_duration_text(review_load.estimate_seconds(outline.total))}. "
            f"Live monitoring carries on meanwhile.")
        whole = box.addButton("Whole log", QMessageBox.AcceptRole)
        recent_button = None
        if recent > 0:
            count = sessions - recent
            size = outline.size_from(recent)
            recent_button = box.addButton(
                f"Last {count} session{'s' if count != 1 else ''}, "
                f"{split_retention.format_bytes(size)} "
                f"({_duration_text(review_load.estimate_seconds(size))})",
                QMessageBox.AcceptRole)
            box.setDefaultButton(recent_button)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()
        if clicked is whole:
            choice = -1
        elif recent_button is not None and clicked is recent_button:
            choice = outline.begin_log(recent)
        else:
            self.statusBar().clearMessage()
            return
        self._set_review_busy(True)
        self._review.replay(self.config, event.path, event.member, choice, self._review_notify())

    @Slot()
    def _discard_worker(self):
        """Delete the worker on the UI thread, where leave_thread put it."""
        try:
            self.worker.deleteLater()
        except RuntimeError:
            pass  # already gone

    def closeEvent(self, event):
        self._ticker.stop()
        if self._banner_burst is not None:
            self._banner_burst.cancel()  # its recognition thread ends with the window
            self._banner_burst = None
        self.update_poller.stop()  # a thread still checking is ignored
        self._retention_first.stop()
        self._retention_daily.stop()
        self._retention.stop()  # a zip in progress stops within one chunk
        # A review stops within a megabyte of the log; its last event may
        # already be queued, so the bridge is cut off from this window,
        # which is being deleted
        self._review.cancel()
        self._review.wait(5)
        try:
            self._review_bridge.event.disconnect(self._on_review_event)
        except (RuntimeError, TypeError):
            pass
        # A fight being read again for the positions window: the runner
        # closed and its thread given a moment to end. A read stops within
        # a chunk, but the search for a session's start in a large plain log
        # does not look at the cancel, and the thread is a daemon, so the
        # wait is short; its answer, queued or to come, is cut off here as
        # the review's is, and no request is made after this
        self._reread_closed = True
        self._reread.close(REREAD_CLOSE_S)
        try:
            self._reread_bridge.event.disconnect(self._on_reread_event)
        except (RuntimeError, TypeError):
            pass
        self._save_window_layout()
        # Lines a held file kept queued get one more try (fight_index)
        self.fight_index.flush()
        # Stop worker timers on their own thread, then end the loop and wait.
        # Destroying a QThread that is still running is a native crash, so
        # block as long as it takes rather than proceed with it running.
        # (If the thread already finished, the worker has been handed to the
        # UI thread and deleted there, and must not be touched.)
        if self.worker_thread.isRunning():
            from PySide6.QtCore import QMetaObject
            try:
                QMetaObject.invokeMethod(self.worker, "stop", Qt.QueuedConnection)
            except RuntimeError:
                pass
            self.worker_thread.quit()
            if not self.worker_thread.wait(10000):
                self.worker_thread.wait()
        super().closeEvent(event)

    # ---- engine events (UI thread) ----

    def _index_fight(self, entry):
        """A live boss fight into the fight history (fight_index): its line
        is appended when it differs from the one held under its key, so a
        restart's replay of the session adds nothing."""
        self.fight_index.add(fight_line(entry, __version__))

    @Slot(object)
    def _on_fight_completed(self, entry):
        if self._restart_pending:
            return  # from the analyzer Settings is replacing
        self._index_fight(entry)
        self._fights.append(entry)
        self._attach_banner(entry)
        if self._review_fights is None:
            row = self.history_list.add_fight(entry)
            if self._replaying:
                # Only the fight that was on screen is selected again, and
                # only while the reader has picked none
                if self.history_list.current_entry() is None:
                    if fight_key(entry, self._fights[:-1]) == self._replay_key:
                        self.history_list.setCurrentRow(row)
                    elif self._empty_reason is not None:
                        # The replay's fights are coming, which no empty page
                        # says (the log missing at the restart has appeared,
                        # after waiting_for_log): its line takes the place
                        self._show_replaying()
            elif self._follow_live:
                self.history_list.setCurrentRow(row)
            if self.history_list.current_entry() is not entry:
                self._instance_changed(entry)  # a pull joining the instance on screen

    @Slot(object)
    def _on_fight_updated(self, entry):
        """A delivered fight changed: it gained a death (logged just after
        combat ended), the game had cut it in two and it has now really
        ended, or the run's result came just after it (trial_result). Its
        history line is rewritten, the pane redrawn if it is the fight on
        screen, and the open windows on it redrawn (_fight_changed)."""
        if self._restart_pending:
            return
        self._attach_banner(entry)
        self._index_fight(entry)
        self._fight_changed(entry)

    # The attributes holding the windows beside this one, each made at its
    # first use
    _WINDOW_SLOTS = ("_player_window", "_positions_window")

    def _windows(self):
        """The windows opened so far beside this one (each is made at its
        first use): the player window and the positions window (issue
        #214), the DPS graph being a fight tab now. The one list a theme
        switch, a flip of Hide names, a new text size, a fight changing in
        place and a Settings replay go through (issue #196)."""
        return [window for window in (getattr(self, slot) for slot in self._WINDOW_SLOTS)
                if window is not None]

    def _fight_changed(self, entry):
        """A delivered fight changed in place (a fight update from the
        engine, a score banner attached): its history line is rewritten, the
        pane redrawn if the fight is on screen, and every open window on that
        fight redrawn, each keeping its place, the windows with the Hide
        names mask made afresh from the fight, since a fight the game cut in
        two can bring players its first part did not have (issue #196). A
        hidden window, or one on another fight, is left alone: opening it
        draws the fight anew.

        A window tells its fight by identity (window.entry is entry), with
        no key of time, zone or boss, because the engine never sends a
        changed fight as a new object: it changes the one the frontends
        already hold. A late death replaces that entry's deaths and recaps,
        a fight the game cut in two has every slot of the finished entry
        copied onto it, the run's result (trial_result, its pull marked won)
        is written into it when END_TRIAL follows the fight, a mastery found
        later in the session and a later pull's reading of its outcome are
        written into it, and the banner is attached to it here. The engine
        writes on its own thread and then sends fight_updated, and the
        windows read the entry without a lock, as the pane and the run rows
        do: safe while each write replaces a value, a slot or a key the
        entry was built with. So the GUI writes nothing into an entry, a
        pull, a player row or a recap (banner_path aside), and orders with
        sorted() and new dicts, never .sort() or an added key: CPython
        empties a list while it sorts it, so an engine write built from that
        list meanwhile would lose its items.

        The positions window (issue #214) draws the fight's states, read
        again from disk by its locator, and is asked for a new read only
        when the update brought a new locator: a fight the game cut in two
        that went on is the one update that replaces it (the finished
        entry's slots copied onto the delivered one, its end later). A late
        death, a fought-on rebuild, a mastery found later, END_TRIAL and a
        banner leave the same locator object, and the window redraws its
        numbers, roles and death marks from the entry it holds: reading
        again on every update would have read 158 times in 172 for nothing
        (the replay design's engineering critique, R9). The window waits
        for the read it asked for and drops the answers to earlier ones; a
        hidden window is asked for nothing, and its next link reads what it
        lacks."""
        row = self.history_list.update_fight(entry)
        if row is not None and row == self.history_list.currentRow():
            # Where the reader had it, as the windows keep theirs
            self._redraw_fight()
        elif row is not None:
            self._instance_changed(entry)  # another fight of the instance on screen
        names = self._names_for(entry)
        # Taken before the windows hear of the update, which moves the
        # positions window on to the fight's new locator
        positions = self._positions_window
        moved = (positions is not None and positions.entry is entry
                 and getattr(entry, "locator", None) is not positions.wanted_locator)
        for window in self._windows():
            window.entry_updated(entry, self._dark, names)
        if moved and self._positions_read_wanted(entry):
            self._request_reread(entry)

    @Slot(str, str)
    def _on_zone_changed(self, zone, difficulty):
        vet = " (VETERAN)" if difficulty.upper() == "VETERAN" else ""
        self.zone_label.setText(f"  Zone: {zone}{vet}")

    @Slot(object)
    def _on_log_status(self, status):
        self._last_status = status
        self._refresh_freshness_label()

    @Slot(object)
    def _on_archive_event(self, event):
        if event.kind == "started":
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 1000)
            self.progress_bar.setValue(0)
            self.statusBar().showMessage("Archiving Encounter.log…")
        elif event.kind == "progress":
            if event.total_bytes:
                self.progress_bar.setValue(
                    int(1000 * event.done_bytes / event.total_bytes))
        elif event.kind == "completed":
            self.progress_bar.setVisible(False)
            deleted = " — original deleted" if event.original_deleted else ""
            self.statusBar().showMessage(
                f"Archived to {self._shown_path(event.archive_path)}{deleted}", 15000)
            if event.original_deleted and event.archive_path:
                self._archive_that_deleted_log = Path(event.archive_path)
            # The pane names the newest archive while no fight is on it
            if self._empty_reason is not None:
                self._show_empty_state(self._empty_reason)
        elif event.kind in ("skipped", "failed"):
            self.progress_bar.setVisible(False)
            self.statusBar().showMessage(f"Archive {event.kind}: {event.reason}", 15000)

    @Slot(str, int, int)
    def _on_parse_progress(self, label, done, total):
        """Progress for review parsing and live catch-up work.

        total == 0 -> indeterminate busy marquee; done >= total > 0 -> done.
        """
        if total > 0 and done >= total:
            self.progress_bar.setVisible(False)
            # Only clear our own label: a completion message (e.g. "Loaded
            # N fights") may already have replaced it
            if label and self.statusBar().currentMessage().startswith(label):
                self.statusBar().clearMessage()
            return
        self.progress_bar.setVisible(True)
        if total <= 0:
            self.progress_bar.setRange(0, 0)  # busy animation
        else:
            self.progress_bar.setRange(0, 1000)
            self.progress_bar.setValue(int(1000 * done / total))
        if label:
            pct = f"  {100 * done // total}%" if total > 0 else ""
            self.statusBar().showMessage(f"{label}{pct}")

    @Slot(str)
    def _on_diagnostic(self, message):
        # Low-priority: transient status message only
        self.statusBar().showMessage(message, 4000)

    @Slot(str, object)
    def _on_warning(self, source, message):
        """A lasting problem from *source*, or its end (message None)."""
        if message:
            self._warnings[source] = message
        else:
            self._warnings.pop(source, None)
        self._refresh_warning_label()

    def _refresh_warning_label(self):
        text = "; ".join(self._warnings.values())
        # The label is kept short; the hover has the whole text
        self.warning_label.setText(f"⚠ {text[:90]}…" if len(text) > 90 else f"⚠ {text}")
        self.warning_label.setToolTip(text)
        self.warning_label.setStyleSheet(state_style("none", self._dark))
        self.warning_label.setVisible(bool(text))

    @Slot(object)
    def _on_data_check(self, check):
        """The live session's game data check (data_staleness, issue #173)."""
        self._data_check = check
        self._refresh_data_label()

    def _refresh_data_label(self):
        """One line, amber like a stale log, with the ids and names in its
        hover; hidden when the data is current."""
        text = status_text(self._data_check)
        tooltip = status_tooltip(self._data_check)
        self.data_label.setText(text)
        self.data_label.setToolTip(tooltip)
        self.data_label.setAccessibleName(text)
        self.data_label.setAccessibleDescription(tooltip)
        self.data_label.setStyleSheet(state_style("stale", self._dark))
        self.data_label.setVisible(bool(text))

    @Slot(str)
    def _on_waiting_for_log(self, expected):
        self._log_missing = True
        self._last_status = None
        # No log: the pane says where it was looked for and, when the app
        # archived and removed it, that it did (gui.activity_render)
        self._empty_expected = expected or ""
        if self._review_fights is None and self.history_list.current_entry() is None:
            self._show_empty_state("waiting")  # and the bar with it
        else:
            # Never over a fight the reader is on, live or under review
            # (issue #199): the waiting page took the place of a fight read
            # as the log went away, and stayed when it came back, since
            # monitoring_started draws no page while fights are listed. The
            # bar alone says it, from the folders listed again: the page
            # last listed came before the archive that may just have deleted
            # the log
            self._scan_activity()
            self._refresh_freshness_label()

    @Slot()
    def _on_monitoring_restarting(self):
        """The engine has begun the restart Settings asked for. Everything
        it sent before this belonged to the analyzer being replaced, so the
        history is cleared now rather than when Save was pressed: a replay
        still running at that moment went on filling a list cleared too
        early, and its fights showed above the new analyzer's.

        The replay comes back to the fight the reader was on (issue #196):
        the clear used to leave a reader of an older fight with nothing
        selected, under a page whose links all returned early for want of a
        current fight. The new analyzer builds new entries, so the fight is
        known again by its key (fight_blocks.fight_key), kept here, and the
        pane says the session is being replayed in place of the stale page.
        Following the live log is held off until monitoring_started, which
        the engine sends after the replayed fights: the fight with that key
        is selected as it arrives, unless the reader has picked one (the
        emptied list picks none itself when it takes the focus,
        FightList.focusInEvent, and End goes to the newest so far,
        FightList.moveCursor), and no other fight is. Without the hold,
        _show_fight would start following once the fight came back as the
        newest so far, and every later fight of the replay would be
        selected in turn. A restart that finds no log waits for it
        (waiting_for_log), and the hold lasts until the monitoring_started
        sent once the log appears and is read; the first fight read from it
        puts the replay's line back in place of the waiting page. At
        monitoring_started (_end_replay) the fight on screen stays, the one
        that came back or the reader's pick; with none the newest is
        selected, the list having followed the live log or the fight not
        having come back. The replay reads only the log's latest logging
        session (LogFileMonitor._load_latest_session), so a fight of an
        earlier session the app tailed is gone, as is every fight when the
        log is another or was replaced since. Following is then
        _show_fight's rule again for the fight selected: the newest
        follows, an older fight does not.

        A review keeps its list and its selection, and the hold starts
        under it all the same, with no fight to come back to: Back to live
        during the replay lists the fights so far, none selected, under the
        replay's line, and the newest is selected once the replay is in
        (_exit_review). Without the hold, Back to live followed the live
        log and selected each fight of the replay in turn. While the engine
        waits for a log the restart did not find (_log_missing, cleared
        here and set again by waiting_for_log), Back to live with no fight
        listed draws the waiting page instead: nothing is replayed until
        the log appears.

        The windows' fights are known again by their keys too
        (_rebind_windows puts each window on the replayed copy): the player
        window's with the player's handle, which the copy must give again
        under the same unit id; the positions window's by the key alone,
        its units being the fight's (issue #214). A replay of the same log
        gives the same locator, so that window keeps the states it read,
        and the rows, numbers and roles it draws come from the new entry
        (companion accrual, say, changes the rows). A window on a reviewed
        fight, which no replay builds again, keeps it."""
        self._restart_pending = False
        self._log_missing = False  # the restart may find it
        for slot in self._WINDOW_SLOTS:
            window = getattr(self, slot)
            if window is not None and any(fight is window.entry for fight in self._fights):
                self._replay_keys[slot] = (self._listed_key(window.entry),
                                           self._replay_check(window))
            elif not self._replaying:
                self._replay_keys.pop(slot, None)
        if self._review_fights is None:
            entry = self.history_list.current_entry()
            # During a replay this one cuts short, following is held off,
            # so the fight on screen is the one to come back to, and with
            # none the fight that replay was bringing back still is
            if entry is not None and (self._replaying or not self._follow_live):
                self._replay_key = self._listed_key(entry)
            elif not self._replaying:
                self._replay_key = None
            self.history_list.clear()
            self._show_replaying()
        elif not self._replaying:
            self._replay_key = None  # no live fight on screen to come back to
        self._replaying = True
        self._fights.clear()
        self._update_windows_listed()
        # The new analyzer checks its session's data afresh
        self._on_data_check(None)

    def _listed_key(self, entry):
        """*entry*'s fight_key among the live fights listed before it."""
        earlier = next((self._fights[:index] for index, fight in enumerate(self._fights)
                        if fight is entry), [])
        return fight_key(entry, earlier)

    def _show_replaying(self):
        """The pane while a Settings replay brings the fights back, in place
        of the page before it (see _on_monitoring_restarting)."""
        self._empty_reason = None  # the replay's line ends the empty page
        self._show_placeholder("Replaying the session with the new settings…")

    def _end_replay(self):
        """The replay's fights are all in: the hold on following live ends
        with the fight on screen kept, the one that came back or the
        reader's pick, or else the newest selected (see
        _on_monitoring_restarting). With another Save's restart still to
        come, the hold stays for its replay."""
        if not self._replaying or self._restart_pending:
            return
        self._replaying = False
        self._rebind_windows()
        if self._review_fights is not None:
            return  # Back to live goes to the newest
        if self.history_list.current_entry() is None:
            self.history_list.select_fight(-1)
        entry = self.history_list.current_entry()
        # _show_fight's rule, last applied while fights were still coming
        self._follow_live = entry is None or entry is self._fights[-1]

    def _replay_check(self, window):
        """What the replayed copy of *window*'s fight must give again, past
        its key: the player window's player, by the handle under its unit
        id; nothing for the positions window."""
        if window is self._player_window:
            return window.unit_id, _player_handle(window.entry, window.unit_id)
        return None

    def _rebind_windows(self):
        """The replay is in: each window kept by its fight's key goes on to
        the replayed copy of its fight, the first one with that key, when it
        passes the window's check (_replay_check; a replay of the same log
        keeps the player's handle); with none, the window keeps its fight as
        it was before the Save, and says so (see
        _on_monitoring_restarting). The positions window re-bound is read
        again only when it holds no states for the copy's locator, which a
        replay of the same log gives again."""
        keys, self._replay_keys = self._replay_keys, {}
        for slot, (wanted, check) in keys.items():
            window = getattr(self, slot)
            if window is None:
                continue
            found = None
            for index, entry in enumerate(self._fights):
                if fight_key(entry, self._fights[:index]) == wanted:
                    if check is None or _player_handle(entry, check[0]) == check[1]:
                        found = entry
                    break
            if found is None:
                window.mark_replayed()
                continue
            window.rebind(found, names=self._names_for(found))
            if window is self._positions_window and self._positions_read_wanted(found):
                self._request_reread(found)
        self._update_windows_listed()

    @Slot(str)
    def _on_monitoring_started(self, path):
        self._log_path = path
        self._log_missing = False
        # The fights replayed at attach came before the log was known: the
        # banners saved beside it are found now (banner_capture, #167)
        for entry in self._fights:
            if getattr(entry, "trial_result", None) and not getattr(entry, "banner_path", None):
                self._attach_banner(entry)
                if getattr(entry, "banner_path", None):
                    self._fight_changed(entry)
        self.statusBar().showMessage(f"Monitoring {self._shown_path(path)}", 8000)
        self._end_replay()
        # A Positions link clicked while the fights replayed at attach were
        # listed, before the log was known, found no place to read: ask
        # again now there is one (issue #214)
        window = self._positions_window
        if window is not None and self._positions_read_wanted(window.entry):
            self._request_reread(window.entry)
        # Never over a review's fight, which stays on the pane
        if not self._fights and self._review_fights is None:
            self._show_empty_state("monitoring")
        # After 'Monitoring …', which would replace it (fight_index)
        if self._backfill_hint_due:
            self._backfill_hint_due = False
            self._offer_backfill()

    @Slot(str, list)
    def _on_review_loaded(self, path, fights, source=None):
        """A review's fights in the list. *path*: the label the file is
        shown by; *source*: (the file, its zip member or '') as the review
        read it, which the positions window reads a reviewed fight from
        again (issue #214), None when not known."""
        self.statusBar().clearMessage()  # replaces the persistent "Loading…"
        if not fights:
            QMessageBox.information(self, "Review",
                                    f"No completed fights found in\n{path}")
            return
        self._keep_review_source()
        self._review_fights = fights
        self._review_path = path
        self._review_source = source
        self.statusBar().showMessage(
            f"Loaded {len(fights)} fight{'s' if len(fights) != 1 else ''} "
            f"from {self._shown_path(path)}", 8000)
        self.banner.setText(self._review_banner_text())
        self.banner.setVisible(True)
        self.back_to_live_action.setVisible(True)
        self._reload_list(fights)

    # ---- updates ----

    def _build_update_poller(self):
        """The schedule and the threads behind the Update button (see
        gui/update_poller.py), started when Settings has the check on. No
        dialog anywhere in this path: a release found shows as the button,
        the ⓘ and the title; a failure as a status-bar message."""
        self.update_poller = UpdatePoller(self.config, __version__, self)
        self.update_poller.update_available.connect(self._on_update_available)
        self.update_poller.update_gone.connect(self._on_update_gone)
        self.update_poller.download_progress.connect(self._on_parse_progress)
        self.update_poller.update_ready.connect(self._on_update_ready)
        self.update_poller.update_failed.connect(self._on_update_failed)
        if bool(self.config.get("update.check_enabled", True)):
            self.update_poller.start()

    def _update_settings_key(self):
        """What the update checks depend on: on or off, the channel, and the
        skipped version (a save with checks on clears it)."""
        return (bool(self.config.get("update.check_enabled", True)),
                normalize_channel(self.config.get("update.channel")),
                self.config.get("update.skip_version"))

    def _apply_update_settings(self, before=None):
        """Settings saved: the check on starts a full check now and the
        schedule (on the channel saved, which the title names); off stops
        both and withdraws the offer. *before* is _update_settings_key()
        from before the save: when nothing about updates changed the
        schedule runs on, keeping its ETag and any rate-limit wait (a
        restart costs a full reply, about 80 KB on Beta, per save)."""
        if before is not None and before == self._update_settings_key():
            return
        if bool(self.config.get("update.check_enabled", True)):
            self.update_poller.start()
        else:
            self.update_poller.stop()
            self._on_update_gone()
        self._apply_title()

    def _update_channel(self):
        """The channel checks run on, or None while checks are off."""
        if not bool(self.config.get("update.check_enabled", True)):
            return None
        return normalize_channel(self.config.get("update.channel"))

    def _apply_title(self):
        """The version, " · beta" on the Beta channel (the maintainer's
        choice of 2026-10-29, issue #134, so a screenshot shows it), and
        the release on offer."""
        title = f"ESO Log Tail v{__version__}"
        if self._update_channel() == "beta":
            title += " · beta"
        if self._update is not None:
            title += f" · {self._update.version} available"
        self.setWindowTitle(title)

    def _style_update_buttons(self):
        self.update_info_button.setStyleSheet(
            f"QToolButton {{ color: {link_color(self._dark)}; font-weight: bold; }}")

    def _update_button_label(self) -> str:
        version = self._update.version
        return f"Update to {version}" if HAS_INSTALLER else f"Get {version}"

    @Slot(object)
    def _on_update_available(self, info):
        """A newer release: the button, the ⓘ and the title say so.
        Nothing is downloaded until the button is clicked."""
        self._update = info
        self.update_button.setText(self._update_button_label())
        self.update_button.setEnabled(True)
        if HAS_INSTALLER:
            hint = ("Click to download and install it now: the app closes for "
                    "the installer and comes back when it is done. Nothing "
                    "happens until you click.")
        else:
            hint = "Click to open the release page and download it."
        self.update_button.setToolTip(
            f"ESO Log Tail {info.version} is available (you have {__version__}). {hint}")
        released = format_release_date(info.published)
        when = f", released {released}" if released else ""
        self.update_info_button.setToolTip(f"Release notes for {info.version}{when}")
        self.update_action.setVisible(True)
        self.update_info_action.setVisible(True)
        self._apply_title()

    @Slot()
    def _on_update_gone(self):
        """No newer release any more (withdrawn, skipped, or the check
        turned off): the button, the ⓘ and the title suffix go."""
        self._update = None
        self.update_action.setVisible(False)
        self.update_info_action.setVisible(False)
        self._apply_title()

    def _on_update_clicked(self):
        """The button: on Windows the download, and the installer as soon
        once downloaded (one click, the maintainer's choice of 2026-10-26);
        elsewhere the release page."""
        info = self._update
        if info is None:
            return
        if not HAS_INSTALLER:
            QDesktopServices.openUrl(QUrl(info.page_url))
            return
        if not self.update_poller.download(info.installer_url, info.installer_name):
            self.statusBar().showMessage(
                "Update check in progress; try again in a moment", 5000)
            return
        self.update_button.setText(f"Downloading {info.version}…")
        self.update_button.setEnabled(False)

    @Slot(str)
    def _on_update_ready(self, installer_path):
        """The installer has downloaded: hand over to it and close. The click on
        the button was the consent; settings are kept and the installer
        relaunches the app."""
        import subprocess
        try:
            subprocess.Popen([installer_path], close_fds=True)
        except OSError as exc:
            self._on_update_failed(f"could not start the installer: {exc}")
            return
        self.close()

    @Slot(str)
    def _on_update_failed(self, reason):
        if self._update is not None:
            self.update_button.setText(self._update_button_label())
            self.update_button.setEnabled(True)
        self.statusBar().showMessage(f"Update {reason}", 15000)

    def _show_update_notes(self):
        """The ⓘ: the release notes in a popup at the pointer; its skip
        link withdraws the offer for this version. The popup owns itself
        (Qt.Popup, deleted on close)."""
        if self._update is None:
            return
        popup = UpdateNotesPopup(self._update, __version__, self._dark, self)
        popup.skip_requested.connect(self._skip_update)
        popup.show_at(QCursor.pos())

    def _skip_update(self):
        if self._update is None:
            return
        self.config.set("update.skip_version", self._update.version)
        self.config.save()
        self._on_update_gone()

    # ---- freshness ----

    def _refresh_freshness_label(self):
        status = self._last_status
        if status is None or status.latest_entry_time is None:
            # While the app's own archive explains the missing log, the bar
            # says so in the plain colour rather than "No log file" in red,
            # which would contradict the pane (gui.activity_render), and it
            # goes on saying so under a review or a fight while the engine
            # waits for the log
            reason = "waiting" if self._log_missing else self._empty_reason
            explained = empty_status_text(reason, self._activity, self._archive_that_deleted_log)
            self.freshness_label.setText(explained or "No log file")
            self.freshness_label.setStyleSheet(state_style("idle" if explained else "none", self._dark))
            return
        age = (datetime.now() - status.latest_entry_time).total_seconds()
        state = ("live" if age < LIVE_SECONDS
                 else "idle" if age < IDLE_SECONDS else "stale")
        approx = "~" if status.source == "approximate" else ""
        stamp = status.latest_entry_time.strftime("%Y-%m-%d %H:%M:%S")
        self.freshness_label.setText(
            f"Last entry: {approx}{stamp} ({_age_text(age)} ago)")
        self.freshness_label.setStyleSheet(state_style(state, self._dark))

    # ---- history / detail views ----

    def _current_fights(self):
        return self._review_fights if self._review_fights is not None else self._fights

    def _reload_list(self, fights):
        self.history_list.set_fights(fights)
        self.history_list.select_fight(-1)
        self._update_windows_listed()

    def _show_fight(self, *_, search_from=None, others=True):
        """The current fight on the fight's tabs (the list's
        currentRowChanged passes the row, which a header row never is).
        *search_from*, for the page redrawn in place, is where the reader
        had the text cursor among the search's matches on the tab on screen
        (_search_place): the search goes on from there (_apply_search).
        *others* False leaves the other tabs' pages as they are, for a
        change to the Fight page alone (Detail view).

        The Fight page, the strip and the pane, is always drawn, as the
        issue's design has it: one path for the pane, which the list's
        selection, Hide names, the theme, the text size, Detail view and
        the pen/crit settings all draw through, and a fight changes in place
        only a few times (a late death, its banner, a mastery found later).
        Then the tab on screen, if it is another, in place when it shows
        this fight already (the Instance page: this fight's instance, the
        search going on from its place; the Events page: its row selected
        and its scroll kept, gui.events_tab); the other tabs are marked, and
        drawn when they are next shown, the search going on where it was on
        a page drawn while hidden (_on_fight_tab_changed, gui.fight_tabs,
        issue #196)."""
        entry = self.history_list.current_entry()
        if entry is None:
            return
        self._empty_reason = None  # a fight on the pane ends the empty page
        if not self.fight_views.is_shown():
            # A fight again: the tab bar, the search and the tab chosen come
            # back, the tab drawn below
            self.fight_tabs.blockSignals(True)
            self.fight_views.set_shown(True)
            self.fight_tabs.setCurrentIndex(self._chosen_tab)
            self.fight_tabs.blockSignals(False)
        fights = self._current_fights()
        self._follow_live = (self._review_fights is None
                             and bool(fights) and entry is fights[-1])
        # The Settings' assumed Champion Point rows and cap, read at render
        # time (pen_crit): the row tokens, their hover text and the strip's
        # Armour row follow them
        pen_crit_options = self.config.get("pen_crit") or {}
        # The Hide names mask for this fight: the identity unless the
        # switch is on (gui.name_mask)
        names = self._names_for(entry)
        self.timeline_strip.set_timeline(
            strip_timeline(entry), getattr(entry, 'tracked', None),
            armour_row(getattr(entry, 'pen_crit', None), pen_crit_options), names=names,
            # The sets' own buff ids each player had up (set_text, issue #79)
            given=given_by_caster(entry.players))
        # Ability icons replace names in the detail view; the hover text, the
        # ESO-Hub link and the searchable name of each icon come from the
        # same per-slot data. Death-recap buttons and the build link on each
        # player's name show in both views
        tooltips = death_tooltips(entry, names)
        # Each named player's last kills of the boss, and the pull against
        # the earlier kills (fight_index, issue #170)
        kills = earlier_kills(self.fight_index, entry)  # once for the whole page
        histories = {}
        for p in entry.players:
            handle = str(p.get("name") or "")
            if handle.startswith("@") and not p.get("companion"):
                histories[str(p.get("unit_id", ""))] = player_history_text(
                    entry, handle, player_history(self.fight_index, entry, handle, kills), names)
        history = comparison_text(comparison(self.fight_index, entry, kills))
        tooltips.update(build_tooltips(entry, names, histories))
        tooltips.update(damage_tooltips(entry, names))
        tooltips.update(taken_tooltips(entry, names))
        tooltips.update(issues_tooltips(entry))
        tooltips.update(mastery_tooltips(entry))
        tooltips.update(pen_crit_tooltips(entry, pen_crit_options))
        tooltips.update(misfortunes_tooltips(entry))
        # The header's Positions, where it opens (issue #214)
        tooltips.update(fight_positions_tooltips(entry))
        # The split logs of the run this fight completed, every session of
        # it, on its result strip (issue #194)
        split_files = (self._split_files(self.history_list.block_of(entry) or [entry])
                       if getattr(entry, "trial_result", None) else [])
        self._fight_split_files = split_files
        tooltips.update(split_tooltips(split_files))
        if self._detailed:
            tooltips.update(anchor_tooltips(
                entry, links=esohub_ability_url, set_links=esohub_set_url,
                script_links=esohub_script_url))
            self.fight_view.set_anchor_names(anchor_names(entry, links=esohub_ability_url))
        else:
            self.fight_view.set_anchor_names({})
        self.fight_view.set_tooltips(tooltips)
        # A hovered name is underlined in the theme's link color; unhovered
        # it keeps the pane's own text color
        self.fight_view.set_link_hover_color(link_color(self._dark))
        text_color = self.fight_view.palette().color(QPalette.Text).name()
        if self.fight_tabs.currentIndex() == 0:
            self._search_places.pop(self.fight_view, None)  # the page is the search's now
        else:
            self._note_search_place(self.fight_view, entry is self._fight_entry)
        self._fight_entry = entry
        self.fight_view.setHtml(render_html(entry, self._detailed, dark=self._dark,
                                            icons=self.fight_view.icons,
                                            links=esohub_ability_url,
                                            set_links=esohub_set_url,
                                            base_pt=self.fight_view.font().pointSizeF(),
                                            script_links=esohub_script_url,
                                            text_color=text_color,
                                            pen_crit_options=pen_crit_options,
                                            names=names,
                                            line_px=QFontMetrics(self.fight_view.font()).height(),
                                            history=history, split_files=split_files,
                                            hide_paths=self._hide_names))
        if self._search_off_on_graph():
            # The graph on screen: no search there
            if others:
                self._draw_graph(entry)
                self._deaths_dirty = self._instance_dirty = self._events_dirty = True
            return
        if others:
            self._graph_dirty = True
        page = self.fight_tabs.currentWidget()
        if page is self.events_view:
            # The Events page, in place for the same fight, its row and its
            # scroll kept; the search filters its rows (gui.events_tab)
            if others:
                self._deaths_dirty = self._instance_dirty = True
                self._draw_events(entry)
                self._apply_search()
            return
        if page in (self.deaths_view, self.instance_view):
            if not others:
                return
            # The other pages are drawn when they are next shown
            self._events_dirty = True
            if page is self.deaths_view:
                self._instance_dirty = True
            else:
                self._deaths_dirty = True
            if self._page_state(page, entry)[1]:
                if search_from is None:
                    # Another fight of the instance on screen: the search
                    # goes on from its place, as the page keeps its own
                    search_from = self._search_place(page.textCursor().position())
                self._draw_in_place(page, entry, search_from)
            else:
                self._draw_page(page, entry)
                self._apply_search(search_from=search_from)
            return
        self._deaths_dirty = self._instance_dirty = self._events_dirty = True
        self._apply_search(search_from=search_from)

    def _open_player(self, unit_id, tab, entry=None, death=None):
        """A player link on the fight pane: the player window on the player
        *unit_id* of the fight on screen (or *entry*), at the tab *tab*, at
        the death *death* (from 1) on the Deaths tab (issue #196). The window
        keeps that fight while the list moves on (#143)."""
        if entry is None:
            entry = self.history_list.current_entry()
        if entry is None:
            return
        # A link clicked while a Settings replay runs is where the window
        # goes: the replay's end does not take it back to the fight it
        # showed before the Save (_rebind_windows)
        self._replay_keys.pop("_player_window", None)
        if self._player_window is None:
            self._player_window = PlayerWindow(self, icons=self.fight_view.icons,
                                               config=self.config)
            geometry = _decode_state(self.config.get("window.player_geometry"))
            if geometry is not None:
                self._player_window.restoreGeometry(geometry)
            self._player_window.show_in_list_requested.connect(self._show_in_list)
            # A death's Positions link on its Deaths tab (issue #214)
            self._player_window.positions_requested.connect(self._show_player_positions)
        self._player_window.open(entry, unit_id, tab, self._dark, names=self._names_for(entry),
                                 death=death, listed=self.history_list.row_of(entry) is not None)

    def _show_pen_crit(self, unit_id):
        """A player's pen/crit token was clicked: the Pen and crit tab."""
        self._open_player(unit_id, PEN_CRIT_TAB)

    def _show_death_recap(self, unit_id):
        """A player's death-recap chip was clicked: the Deaths tab."""
        self._open_player(unit_id, DEATHS_TAB)

    def _show_build(self, unit_id):
        """A player's name, or the '?' after a lone mastery: the Build tab."""
        self._open_player(unit_id, BUILD_TAB)

    def _show_damage(self, unit_id):
        """A player's dps figure was clicked: the Damage done tab."""
        self._open_player(unit_id, DAMAGE_TAB)

    def _show_taken(self, unit_id, entry=None):
        """A player's damage-taken shield was clicked: the Damage taken tab,
        the whole fight's damage taken (taken_render, issue #98)."""
        self._open_player(unit_id, TAKEN_TAB, entry)

    def _show_in_list(self, entry):
        """A window's Show in list (the player window's, the positions
        window's): its fight selected in the list, and this window brought
        up; the window, which this one owns, stays above it."""
        if self.history_list.row_of(entry) is None:
            self.statusBar().showMessage("That fight is not in the list now", 5000)
            return
        self.history_list.select_entry(entry)
        self.raise_()
        self.activateWindow()

    def _update_windows_listed(self):
        """Each window's Show in list follows the list as it is replaced: a
        review, Back to live, a Settings replay."""
        for window in self._windows():
            if window.entry is not None:
                window.set_listed(self.history_list.row_of(window.entry) is not None)

    def _show_issues(self, unit_id):
        """A player's (i) was clicked in the fight on screen: their possible
        build issues, each with its rule, in a popup at the pointer; under
        the (i) when Enter opened it from the keyboard, since the pointer
        may be anywhere then (issue #196). The popup owns itself (Qt.Popup,
        deleted on close), so nothing here keeps a reference to it."""
        entry = self.history_list.current_entry()
        if entry is None:
            return
        text = issues_html(player_for(entry, unit_id), self._dark,
                           set_links=esohub_set_url, links=esohub_ability_url)
        if text:
            popup = BuildIssuesPopup(text, self, tooltips=set_tooltips(
                player_for(entry, unit_id), esohub_set_url))
            link = self.fight_view.keyboard_link_rect()
            if link is not None:
                popup.show_under(link)
            else:
                popup.show_at(QCursor.pos())

    def _show_graph(self):
        """The toolbar's DPS graph, or the header's group dps figure, was
        clicked: the DPS graph tab, on the fight on screen (issue #196)."""
        if self.fight_views.is_shown():
            self.fight_tabs.setCurrentWidget(self.dps_panel)

    def _show_placeholder(self, html_text):
        self._last_placeholder = html_text
        # No fight: the Fight tab, the tab bar and the search hidden with it
        # (gui.fight_tabs); the next fight's Deaths page is drawn anew
        self.fight_views.set_shown(False)
        self._deaths_entry = None
        self._deaths_dirty = True
        self._events_entry = None
        self._events_dirty = True
        self.events_view.clear()
        self.dps_panel.clear()
        self._graph_dirty = True
        self._fight_entry = None
        self._search_places.clear()
        self._instance_block = []
        self._instance_links = {}
        self._instance_dirty = True
        self._fight_split_files = []
        self._instance_split_files = []
        # Nor is the last fight's deaths or instance kept on the hidden
        # pages, their names as they were drawn, Hide names or not
        for view in (self.deaths_view, self.instance_view):
            view.set_tooltips({})
            view.setHtml("")
        self.timeline_strip.set_timeline(None)
        self.fight_view.setHtml(
            f"<div style='color:{muted_color(self._dark)};padding:16px'>"
            f"{html_text}</div>")
        self._apply_search()

    # ---- the pane before the first fight (gui.activity_render, issue #191) ----

    def _known_log(self, search: bool = True):
        """The log the folders are taken from, without a search: the one
        Settings names, else the one the engine monitors or waits for
        (_log_path, _empty_expected: a log the app has just archived and
        deleted is not on disk, and auto-detection then finds nothing on
        Linux and walks the whole Logs folder on Windows), else, on a
        first run, the auto-detected one; None when there is none. With
        *search* False, None rather than the auto-detection, for a link's
        click (_reread_places)."""
        for candidate in (self.config.get("log_path"), self._log_path, self._empty_expected):
            if candidate:
                return Path(candidate)
        return split_retention.resolve_log("") if search else None

    def _archive_folder(self, log=None):
        """The archive folder: the one set, else the log's own (the
        archiver's rule, log_archiver.LogArchiver._archive_target)."""
        try:
            return recent_activity.archive_folder(
                self.config.get("archive.dir") or "",
                log if log is not None else self._known_log())
        except OSError:
            return None

    def _scan_activity(self):
        """The newest archives and splits, listed again from the folders
        of the log known now (_known_log)."""
        log = self._known_log()
        self._activity = recent_activity.scan(self._archive_folder(log), self._split_folder(log))

    def _show_empty_state(self, reason):
        """The pane while the fight list is empty: what the app is doing,
        when Encounter.log was last archived, and the Recent activity link
        with the newest archives and splits under it (gui.activity_render).
        The two folders are listed again at each redraw, so an archive just
        made is on the page; a listing is all it costs (the log is resolved
        once, _known_log, and never by a search of the Logs folder)."""
        self._empty_reason = reason
        self._scan_activity()
        self.fight_view.set_anchor_names({})
        self.fight_view.set_tooltips(activity_tooltips(self._activity))
        self.fight_view.set_link_hover_color(link_color(self._dark))
        self._show_placeholder(empty_state_html(
            reason, self._activity, dark=self._dark,
            text_color=self.fight_view.palette().color(QPalette.Text).name(),
            deleted_archive=self._archive_that_deleted_log,
            expected=self._empty_expected, show_activity=self._activity_open))
        self._refresh_freshness_label()  # the bar's text follows the page

    @Slot(str)
    def _on_activity_requested(self, action):
        """The Recent activity link: its lists open or close, in place."""
        if self._empty_reason is None:
            return
        self._activity_open = action == "show"
        self._show_empty_state(self._empty_reason)

    @Slot(int)
    def _on_review_requested(self, index):
        """A file under Recent activity: Open log for review on it."""
        paths = activity_paths(self._activity)
        if 0 <= index < len(paths):
            self._request_review_of(str(paths[index]))

    # ---- in-fight search ----

    def _search_matches(self, view=None):
        """QTextCursor for every match of the search text on the page
        *view*, the tab on screen's by default: each text occurrence, plus
        each ability icon whose name contains the text (the name is hover
        text, not document text). Document order."""
        text = self.search_field.text()
        matches = []
        view = view or self._search_view()
        if text and view is not self.events_view:  # the Events page filters its rows instead
            document = view.document()
            cursor = QTextCursor(document)
            while True:
                cursor = document.find(text, cursor)  # case-insensitive
                if cursor.isNull():
                    break
                matches.append(QTextCursor(cursor))
            matches.extend(view.anchor_matches(text))
            matches.sort(key=lambda c: c.selectionStart())
        return matches

    def _apply_search(self, *_, search_from=None, keep_cursor=False):
        """Highlight the search's matches on the tab on screen and count
        them (the field's textChanged passes the text). The text cursor goes
        to the first match, where Enter goes on from (_goto_next_match);
        with *keep_cursor*, for a page shown again as it was left (a tab
        change), it stays where it was.

        For the page redrawn in place, *search_from* is where the reader
        had the cursor among the matches (_search_place). The cursor goes to
        the start of the match with that number; from between two matches
        (a click leaves it so), to the start of the one before, or the
        page's start before the first, so the next Enter reaches the match
        it would have reached; with fewer matches now, to the last. By
        number, not by offset: the text before the match can change length,
        as a fight the game cut in two goes from 'Wipe 54%' to 'Cut 54%'
        above every match, and the cursor kept by its offset went on to the
        next match. An update that ranks the players anew moves the matches
        with their rows: the number keeps the search's place among the
        matches, not the occurrence, as the pane's scroll is kept by
        position (issue #196).

        On the Events page, a table, the search filters the rows to those
        that hold its text and counts them (gui.events_tab): a new search
        selects its first row, and the same search, after a redraw or a
        tab change, leaves the row selected where it was."""
        view = self._search_view()
        self._searched[view] = self.search_field.text()
        if view is self.events_view:
            text = self.search_field.text()
            rows = view.set_search(text)
            self.search_field.set_count(count_text(rows) if text else "")
            return
        matches = self._search_matches()
        highlight = QTextCharFormat()
        # Amber with black text reads on both light and dark themes
        highlight.setBackground(QColor("#ffd54f"))
        highlight.setForeground(QColor("#000000"))
        selections = []
        for cursor in matches:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = highlight
            selections.append(selection)
        # The page applies these together with its hover cue
        view.set_search_selections(selections)
        self.search_field.set_count(count_text(len(selections)) if self.search_field.text() else "")
        if selections and not keep_cursor:
            starts = [selection.cursor.selectionStart() for selection in selections]
            start = starts[0]
            if search_from is not None:
                before, on_match = search_from
                index = before if on_match else before - 1  # the match the cursor goes to
                start = starts[min(index, len(starts) - 1)] if index >= 0 else 0
            else:
                # A search typed, or a new page: the page is the search's to
                # move, not a redraw's to put back (FightView.release_place)
                view.release_place()
            first = QTextCursor(view.document())
            first.setPosition(start)
            view.setTextCursor(first)
            view.ensureCursorVisible()

    def _search_place(self, position, view=None):
        """Where the text cursor, at *position*, is among the search's
        matches on the page *view* (the tab on screen's by default), read
        before the page is drawn again for _apply_search to put it back: the
        number of matches that start before it, and whether one starts at
        it."""
        starts = [match.selectionStart() for match in self._search_matches(view)]
        return sum(1 for start in starts if start < position), position in starts

    def _goto_next_match(self):
        """Enter in the search field cycles through matches; on the Events
        page, through the rows the search left."""
        if self._search_view() is self.events_view:
            self.events_view.select_next_match()
            return
        matches = self._search_matches()
        if not matches:
            return
        view = self._search_view()
        position = view.textCursor().position()
        target = next((m for m in matches if m.selectionStart() > position),
                      matches[0])  # wrap around
        cursor = QTextCursor(target)
        cursor.setPosition(target.selectionStart())
        view.release_place()  # the reader's move, not undone by a redraw
        view.setTextCursor(cursor)
        view.ensureCursorVisible()

    # ---- the fight's tabs (gui.fight_tabs, issue #196) ----

    def _set_tab_order(self):
        """The Tab order: the list, the tab bar, the search (or the Find
        button standing for it), the page; set again when the search moves
        between the bar's corner and its own row, which gives it another
        parent. The Events page's controls in its own order (gui.events_tab)."""
        bar = self.fight_tabs.tabBar()
        QWidget.setTabOrder(self.history_list, bar)
        QWidget.setTabOrder(bar, self.fight_views.find_button)
        QWidget.setTabOrder(self.fight_views.find_button, self.search_field)
        QWidget.setTabOrder(self.search_field, self.fight_view)
        QWidget.setTabOrder(self.fight_view, self.deaths_view)
        previous = self.deaths_view
        for control in self.events_view.focus_chain():
            QWidget.setTabOrder(previous, control)
            previous = control
        QWidget.setTabOrder(previous, self.instance_view)

    def _search_view(self):
        """The page the search works on: the tab on screen's."""
        page = self.fight_tabs.currentWidget()
        if page in (self.deaths_view, self.events_view, self.instance_view):
            return page
        return self.fight_view

    def _find(self):
        """Ctrl+F, or the Find button the bar's corner holds at a large text
        size: the search, for the tab on screen, the Fight tab first from
        the graph, which has no text to search, the field out on its own row
        if the corner holds the button; nothing while no fight is shown, the
        field hidden with the tab bar."""
        if self.fight_views.is_shown():
            if self.fight_tabs.currentWidget() is self.dps_panel:
                self.fight_tabs.setCurrentIndex(0)
            self.fight_views.open_search()
            self.search_field.setFocus()
            self.search_field.selectAll()

    def _step_fight_tab(self, step: int):
        if self.fight_views.is_shown():
            tabs = self.fight_tabs
            tabs.setCurrentIndex((tabs.currentIndex() + step) % tabs.count())

    def _next_fight_tab(self):
        self._step_fight_tab(1)

    def _previous_fight_tab(self):
        self._step_fight_tab(-1)

    def _on_fight_tab_changed(self, index):
        """A tab chosen, which stays as the fights change: its page is
        drawn if it was marked, in place when it shows the fight already,
        and the search goes to it. On a page shown as it was left the text
        cursor stays where it was, and the link reached with Tab has Tab's
        focus again, which Qt drops as the tab widget hides the page (the
        player window gives it back too); a page drawn again while hidden
        goes on from its place (_note_search_place). A search typed while
        the page was hidden, or a new fight, starts at its first match
        (#206)."""
        if not self.fight_views.is_shown():
            return  # no fight: the Fight tab, put there by set_shown
        self._chosen_tab = index
        entry = self.history_list.current_entry()
        if self._search_off_on_graph():
            for view in (self.fight_view, self.deaths_view, self.instance_view):
                view.set_search_selections([])
            if entry is not None and (self._graph_dirty or entry is not self.dps_panel.entry):
                self._draw_graph(entry)
            return
        searched = self._search_view()
        if searched is self.events_view:
            # A table: drawn if marked, in place for the same fight, and
            # filtered by the search, its row kept for the same search
            for view in (self.fight_view, self.deaths_view, self.instance_view):
                view.set_search_selections([])
            if entry is not None and self._page_state(searched, entry)[0]:
                self._draw_page(searched, entry)
            self._apply_search()
            return
        # The page left keeps no matches; the one on screen has the search's
        for view in (self.fight_view, self.deaths_view, self.instance_view):
            if view is not searched:
                view.set_search_selections([])
        same_search = self._searched.get(searched, "") == self.search_field.text()
        stale, same = (self._page_state(searched, entry)
                       if searched is not self.fight_view and entry is not None else (False, False))
        if stale:
            if same:
                # Drawn again in place, its Tab link kept by the redraw, the
                # search going on from its place, read before the link moves
                # the cursor
                place = (self._search_place(searched.textCursor().position())
                         if same_search else None)
                searched.give_link_back()
                self._draw_in_place(searched, entry, place)
            else:
                self._draw_page(searched, entry)
                self._apply_search()  # a new fight or instance: its first match
            return
        noted = self._search_places.pop(searched, None)
        if noted is None:
            if same_search:
                searched.give_link_back()
                self._apply_search(keep_cursor=True)  # as it was left
            else:
                self._apply_search()  # a search typed meanwhile: its first match
            return
        text, place = noted
        if place is None or text != self.search_field.text():
            self._apply_search()  # a new fight, or a new search: its first match
        else:
            with searched.keeping_place():
                self._apply_search(search_from=place)

    def _note_search_place(self, view, same: bool):
        """The page *view* is drawn while another tab is on screen: when
        it is next shown, the search goes on from its place among the
        matches if it shows the same fight (*same*), taken before the first
        such drawing, while its cursor is where the reader left it; or
        from the first match of a new fight, or of a search typed since it
        last ran there. Kept with the search's text, which the place is
        for."""
        text = self.search_field.text()
        if not same or self._searched.get(view, "") != text:
            self._search_places[view] = (text, None)
        elif view not in self._search_places:
            self._search_places[view] = (text, self._search_place(view.textCursor().position(), view))

    def _draw_deaths(self, entry):
        """Every death of *entry* on the Deaths page
        (gui.fight_deaths_render)."""
        view = self.deaths_view
        names = self._names_for(entry)
        view.set_link_hover_color(link_color(self._dark))
        view.set_tooltips(fight_deaths_tooltips(entry, names))
        view.setHtml(render_fight_deaths_html(
            entry, dark=self._dark, icons=view.icons, base_pt=view.font().pointSizeF(),
            names=names, text_color=view.palette().color(QPalette.Text).name()))
        self._deaths_entry = entry
        self._deaths_dirty = False

    def _page_state(self, view, entry):
        """For the Deaths, Events or Instance page *view*: whether it is to
        be drawn for *entry* before it is shown, and whether it shows what
        it would show already (the same fight, the same instance), so is
        drawn in place."""
        if view is self.deaths_view:
            same = entry is self._deaths_entry
            return self._deaths_dirty or not same, same
        if view is self.events_view:
            same = entry is self._events_entry
            return self._events_dirty or not same, same
        same = self._same_instance(entry)
        return self._instance_dirty or not same, same

    def _draw_page(self, view, entry):
        """The Deaths, Events or Instance page *view* drawn for *entry*;
        the Events page in place by itself for the fight it shows."""
        if view is self.deaths_view:
            self._draw_deaths(entry)
        elif view is self.events_view:
            self._draw_events(entry)
        else:
            self._draw_instance(entry)

    def _draw_events(self, entry):
        """The notable events of *entry* on the Events page
        (gui.events_tab): in place, the row selected and the scroll kept,
        when it shows that fight already."""
        self.events_view.show_fight(entry, self._names_for(entry))
        self._events_entry = entry
        self._events_dirty = False

    def _draw_in_place(self, view, entry, search_from=None):
        """The Deaths or Instance page *view* drawn again for *entry* where
        the reader had it (FightView.keeping_place), the search going on
        from its place among the matches (*search_from*, _search_place); or,
        with None, a search typed while the page was hidden, from its first
        match, found after the page is put back, which would otherwise take
        the page from it. The one way a page is drawn in place: a fight, a
        tab chosen, a pull or a change in the instance on screen."""
        with view.keeping_place():
            self._draw_page(view, entry)
            if search_from is not None:
                self._apply_search(search_from=search_from)
        if search_from is None:
            self._apply_search()

    def _same_instance(self, entry) -> bool:
        """Whether *entry* is in the instance the Instance page shows: the
        block of the list that the same fight opens."""
        block = self.history_list.block_of(entry)
        return bool(block) and bool(self._instance_block) and block[0] is self._instance_block[0]

    def _draw_instance(self, entry):
        """The instance of *entry*, its block of the list, on the Instance
        page (gui.instance_render). The block is taken anew at each
        drawing, and the page's links carry the places in the list of the
        fights they open, kept here with those fights, so a link whose
        fight is no longer listed says so (_instance_fight)."""
        view = self.instance_view
        fights = self._current_fights()
        block = self.history_list.block_of(entry) or [entry]
        places = {id(fight): index for index, fight in enumerate(fights)}

        def index_of(fight):
            return places.get(id(fight))

        names = NameMask.for_entries(block, self._hide_names)
        # The live list's first instance may have begun before the log's
        # latest logging session, the one the app reads at its start
        opens_list = self._review_fights is None and bool(fights) and block[0] is fights[0]
        split_files = self._split_files(block)
        tips = instance_tooltips(block, index_of, shown=entry, names=names)
        tips.update(split_tooltips(split_files))
        view.set_link_hover_color(link_color(self._dark))
        view.set_tooltips(tips)
        view.setHtml(render_instance_html(
            block, index_of, shown=entry, dark=self._dark, icons=view.icons,
            base_pt=view.font().pointSizeF(), names=names,
            text_color=view.palette().color(QPalette.Text).name(),
            opens_list=opens_list, fight_index=self.fight_index, split_files=split_files,
            hide_paths=self._hide_names))
        self._instance_split_files = split_files
        self._instance_block = block
        self._instance_links = {places[id(fight)]: fight for fight in block if id(fight) in places}
        self._instance_dirty = False

    def _instance_changed(self, entry):
        """*entry* changed in place, or came in, with another fight on
        screen: if it is in the instance the Instance page shows, the page
        is drawn again in place while it is on screen, the search going on
        from its place, and else when it is next shown."""
        shown = self.history_list.current_entry()
        if shown is None or not self._same_instance(entry):
            return
        view = self.instance_view
        if self.fight_tabs.currentWidget() is not view:
            self._instance_dirty = True
            return
        self._draw_in_place(view, shown, self._search_place(view.textCursor().position()))

    def _open_instance_from_list(self, row):
        """A click on a header, run or result row of the list: the Instance
        tab on that row's instance (FightList.instance_of), the fight on
        screen kept when it is in it, at the page's top, or at the boss of
        a run row."""
        target = self.history_list.instance_of(row, self.history_list.current_entry())
        if target is None:
            return
        entry, run = target
        if entry is not self.history_list.current_entry():
            self.history_list.select_entry(entry)
        if not self.fight_views.is_shown():
            return
        self.fight_tabs.setCurrentWidget(self.instance_view)
        view = self.instance_view
        number = self._run_number(run) if run is not None else None
        if number is None:
            view.restore_scroll(0)
        else:
            view.open_at_anchor(run_anchor(number))

    def _run_number(self, run):
        """*run*'s number from 1 among the runs of the instance on the
        Instance page, as the page's anchors count them; None when the
        page does not have it."""
        first = run[0][0]
        for number, each in enumerate(runs(self._instance_block), 1):
            if each[0][0] is first:
                return number
        return None

    def _instance_fight(self, index):
        """The fight a link on the Instance page names by its place in the
        list the page was drawn from; None, the status bar saying so, when
        it is no longer listed."""
        entry = self._instance_links.get(index)
        if entry is None or self.history_list.row_of(entry) is None:
            self.statusBar().showMessage("That fight is not in the list now", 5000)
            return None
        return entry

    def _open_instance_fight(self, index):
        """A pull on the Instance page: that fight, on the Fight tab."""
        entry = self._instance_fight(index)
        if entry is not None:
            self.fight_tabs.setCurrentIndex(0)
            self.history_list.select_entry(entry)

    def _open_instance_player(self, index, unit_id):
        """A name on the Instance page: the player window on the fight the
        link names (gui.instance_render), on Build; on Deaths for a player
        with no row in it, who only died there, as the pane's Also died
        opens them."""
        entry = self._instance_fight(index)
        if entry is not None:
            tab = BUILD_TAB if player_for(entry, unit_id) is not None else DEATHS_TAB
            self._open_player(unit_id, tab, entry=entry)

    def _copy_instance(self):
        """Copy this instance, on the Instance page: its fights as a recap,
        as Copy session writes each instance (session_recap)."""
        block = self._instance_block
        if not block or self.history_list.row_of(block[0]) is None:
            self.statusBar().showMessage("That instance is not in the list now", 5000)
            return
        self._copy_recap(block, "Instance")

    def _split_files(self, fights) -> list:
        """The split logs behind *fights* (an instance's, or the run a fight
        with a result completed), as gui.fight_render.split_lines_html
        lists them: a (label, path or None, note) for each logging session
        of theirs, in order (session_splits, issue #194), the whole
        session's file first. The files are looked for whatever the setting
        says now, so splits written before split logs went off are still
        offered; with none found and split logs off, one line says where to
        turn them on. A split folder that cannot be read says so, where its
        sessions would read as missing. Under a review, the reviewed
        file.

        A list that begins inside a run, as after the app's start or a
        Settings replay, which read the log's latest session alone, holds
        only the run's later fights: the split of the session before, of the
        same instance by its name, comes first, as the earlier split
        (session_splits.earlier_split). The folder is found from the log
        known (_known_log), never by a search for the log, which listed the
        Logs folders at each drawing (the fresh review of PR #210)."""
        if self._review_fights is not None:
            return [(REVIEWED_LABEL, Path(self._review_path), "")] if self._review_path else []
        folder = self._split_folder(self._known_log())
        readable = folder is not None and folder.is_dir()
        sessions = splits_for((getattr(fight, "session_stamp", "") for fight in fights),
                              folder if readable else None)
        earlier = None
        if readable and fights and self._fights and fights[0] is self._fights[0]:
            first = fights[0]
            earlier = earlier_split(getattr(first, "session_stamp", ""), first.zone_name,
                                    difficulty_of(first) == "VETERAN", folder)
        if (not self.config.get("split.enabled", False) and earlier is None
                and not any(s.best for s in sessions)):
            return [(SPLIT_LABEL, None, SPLITS_OFF_NOTE)]
        files = [(EARLIER_LABEL, earlier.path, "")] if earlier is not None else []
        for session in sessions:
            if session.best is not None:
                files.append((SPLIT_LABEL, session.best.path, ""))
            elif not session.known:
                files.append((SPLIT_LABEL, None, SPLIT_UNKNOWN_NOTE))
            elif not readable:
                files.append((SPLIT_LABEL, None, SPLIT_FOLDER_NOTE))
            else:
                began = datetime.strptime(session.stamp, "%y%m%d%H%M%S")  # noqa: DTZ007
                files.append((SPLIT_LABEL, None,
                              SPLIT_MISSING_NOTE.format(time=f"{began:%Y-%m-%d %H:%M}")))
        return files

    @Slot(int, str)
    def _fight_split(self, place, action):
        """A split log's link on the Fight page's result strip."""
        self._split_action(self._fight_split_files, place, action)

    @Slot(int, str)
    def _instance_split(self, place, action):
        """A split log's link on the Instance page."""
        self._split_action(self._instance_split_files, place, action)

    def _split_action(self, files, place, action):
        """Open the folder of the *place*-th split log of *files* with the
        file selected, or copy its full path, Hide names or not: it is for
        a file dialog, not a post (issue #194)."""
        path = files[place][1] if 0 <= place < len(files) else None
        if path is None or not Path(path).is_file():
            self.statusBar().showMessage("That log is not there now", 5000)
            return
        if action == "copy":
            QGuiApplication.clipboard().setText(str(path))
            self.statusBar().showMessage("Log's path copied", 4000)
        else:
            reveal_file(Path(path))

    @Slot(str)
    def _instance_banner(self, action):
        """The Instance page's banner links: the banner of the instance's
        result, whichever of its fights is on screen."""
        result = next((fight for fight in reversed(self._instance_block)
                       if getattr(fight, "trial_result", None)), None)
        self._banner_action(result, action)

    def _search_off_on_graph(self) -> bool:
        """The search off, its text kept and its count blank, with the DPS
        graph on screen, which has no text to search; on with a page of
        text. Whether the graph is on screen. Both ways a tab comes on
        screen set it: a tab chosen, and a fight bringing the chosen tab
        back after a page with no fight, which counted that page's
        matches."""
        on_graph = self.fight_tabs.currentWidget() is self.dps_panel
        self.search_field.setEnabled(not on_graph)
        if on_graph:
            self.search_field.set_count("")
        return on_graph

    def _draw_graph(self, entry):
        """The DPS graph tab on *entry*: in place, the legend keeping its
        place, when it shows that fight already (gui.dps_graph)."""
        self.dps_panel.draw(entry, self._dark, names=self._names_for(entry))
        self._graph_dirty = False

    def _show_fight_deaths(self):
        """The fight header's Deaths N: the Deaths tab."""
        if self.fight_views.is_shown():
            self.fight_tabs.setCurrentWidget(self.deaths_view)

    def _show_fight_death(self, unit_id, number):
        """A name on the Deaths tab: that death on the player window's
        Deaths tab, in the fight the page was drawn for."""
        if self._deaths_entry is not None:
            self._open_player(unit_id, DEATHS_TAB, entry=self._deaths_entry, death=number)

    @Slot(str, int)
    def _show_event_death(self, unit_id, number):
        """Enter or a double-click on a death's row of the Events tab: that
        death on the player window's Deaths tab, in the fight the page was
        drawn for."""
        if self._events_entry is not None:
            self._open_player(unit_id, DEATHS_TAB, entry=self._events_entry, death=number)

    # ---- the positions window (issue #214) ----

    def show_moment(self, entry, t_ms, unit_key=None):
        """The positions window on the fight *entry* at the moment *t_ms*
        (ms since its session's BEGIN_LOG, the locator's own clock), the
        unit *unit_key* selected (a player's or companion's row 'unit_id',
        which is its FightUnit.key; None for none). The one way in for
        every link to it: a row of the Deaths tab, a death's heading in the
        player window, the fight header's Positions, and the fight's events
        to come. A fight with no locator, or one whose session is not known
        (death_render.positions_known), has no such link and opens nothing.

        Design: the positions window and the bytes. One window, made at
        the first link and kept, like the player window, which draws what
        it is given; this window finds where the fight's lines are and has
        them read. The places are worked out here, on the UI thread, at a
        link whose fight the window holds no states for (_reread_places): a
        listing of the split and archive folders, 0.4 to 1.0 ms over a
        428-file split folder. The read runs on 'fight-reread' (0.1 s for a
        median boss fight, 0.4 s for a long one, 0.6 s from a zip) and its
        answer comes back by the bridge (_build_reread). The window shows
        words, not a busy bar, while it waits: nothing in the app moves by
        itself under Reduce motion. A link to the fight being read asks for
        nothing more, and a link to another fight supersedes the read,
        whose answer the window then drops."""
        if not positions_known(entry):
            return
        window = self._positions()
        if window is None:
            return
        # A link clicked while a Settings replay runs is where the window
        # goes: the replay's end does not take it back (_rebind_windows)
        self._replay_keys.pop("_positions_window", None)
        locator = entry.locator
        if not window.has_states_for(locator) and locator is not self._reread_pending:
            self._request_reread(entry)
        window.open(entry, int(t_ms), None if unit_key is None else str(unit_key), self._dark,
                    self._names_for(entry), listed=self.history_list.row_of(entry) is not None)
        # The window may have let go of an earlier review's last fight
        self._prune_past_reviews()

    def _positions(self):
        """The positions window (gui.positions_window), made at the first
        link and kept, its place put back from the last run; None, the
        status bar saying so, when it cannot be made. Imported here, at its
        first use, as this window does not need it to open."""
        if self._positions_window is None:
            try:
                from gui.positions_window import PositionsWindow
            except ImportError:
                self.statusBar().showMessage("The positions window could not be opened", 8000)
                return None
            window = PositionsWindow(self)
            geometry = _decode_state(self.config.get("window.positions_geometry"))
            if geometry is not None:
                window.restoreGeometry(geometry)
            window.show_in_list_requested.connect(self._show_in_list)
            window.player_requested.connect(self._open_positions_player)
            self._positions_window = window
        return self._positions_window

    def _positions_read_wanted(self, entry) -> bool:
        """Whether the positions window, shown on *entry*, lacks the states
        of the fight's locator with no read asked for them: after an update
        that brought a new locator (_fight_changed), and after a Settings
        replay re-bound it (_rebind_windows). A hidden window is asked for
        nothing: its next link reads what it lacks (show_moment)."""
        window = self._positions_window
        return (window is not None and window.entry is entry and window.isVisible()
                and positions_known(entry) and entry.locator is not self._reread_pending
                and not window.has_states_for(entry.locator))

    def _held_entries(self) -> list:
        """The fights a window holds: the player window's, the positions
        window's and the Deaths tab's."""
        held = [self._deaths_entry]
        for window in (self._player_window, self._positions_window):
            held.append(getattr(window, "entry", None) if window is not None else None)
        return [entry for entry in held if entry is not None]

    def _prune_past_reviews(self) -> None:
        """Forget each earlier review's fight no window holds any more."""
        held = self._held_entries()
        self._past_reviews = [(fight, source) for fight, source in self._past_reviews
                              if any(fight is entry for entry in held)]

    def _keep_review_source(self) -> None:
        """Before Back to live or another review replaces the review on
        screen: keep its file for each of its fights a window holds, so a
        Positions link there still reads that file (_reread_places), which
        may be outside the split and archive folders (a log someone sent,
        a zip of several logs). Only those fights are kept, not the
        review's whole list, which would stay in memory with them."""
        if self._review_source is not None and self._review_fights:
            self._past_reviews += [(entry, self._review_source) for entry in self._held_entries()
                                   if any(entry is fight for fight in self._review_fights)]
        self._prune_past_reviews()

    def _reread_places(self, entry) -> list:
        """Where the fight *entry*'s lines may be, in the order they are
        tried (fight_reread.places_for): the reviewed file and its zip
        member when *entry* is one of the review's fights, or of an earlier
        review's while a window holds it (_keep_review_source); the
        session's splits by its stamp in the split folder, when it can be
        read; the live log; and the archives made since the session began,
        an archive's name being stamped with its last line's time to the
        second. The folders are those of the log known, never searched for
        (_known_log)."""
        locator = entry.locator
        reviewed = member = None
        if (self._review_source is not None
                and any(fight is entry for fight in self._review_fights or ())):
            reviewed, member = self._review_source
        else:
            for fight, source in self._past_reviews:
                if fight is entry:
                    reviewed, member = source
                    break
        self._prune_past_reviews()
        log = self._known_log(search=False)
        split_dir = split_retention.split_folder(self.config.get("split.dir") or "", log)
        if split_dir is not None and not split_dir.is_dir():
            split_dir = None
        try:
            # Local time, as the archiver stamps its names (log_archiver)
            began = datetime.fromtimestamp(  # noqa: DTZ006
                locator.session_epoch_ms / 1000).replace(microsecond=0)
        except (OverflowError, OSError, ValueError):
            began = None
        archives = []
        if began is not None:
            folder = recent_activity.archive_folder(self.config.get("archive.dir") or "", log)
            archives = [archive.path for archive in recent_activity.scan_archives(folder)
                        if archive.last_entry is not None and archive.last_entry >= began]
        return fight_reread.places_for(locator, reviewed=reviewed, member=member or None,
                                       split_dir=split_dir, live_log=self._log_path or log,
                                       archives=archives)

    def _request_reread(self, entry) -> None:
        """Have the fight *entry* read again by its locator, on the
        runner's thread; a read running or waiting is superseded. Nothing
        once this window is closing."""
        if self._reread_closed:
            return
        locator = entry.locator
        try:
            self._reread.request(locator, self._reread_places(entry), self._reread_notify())
        except RuntimeError:
            return  # the runner is closed
        self._reread_pending = locator

    @Slot(str, int)
    def _show_deaths_positions(self, unit_key, ms):
        """A death's Positions on the Deaths tab: the positions window at
        that moment (*ms* into the fight) of the fight the page was drawn
        for, the player who died selected."""
        entry = self._deaths_entry
        if positions_known(entry):
            self.show_moment(entry, entry.locator.start_ms + ms, unit_key or None)

    @Slot()
    def _show_fight_positions(self):
        """The fight header's Positions: the positions window on the fight
        on screen, at its first death with that player selected, else as
        it began (death_render.fight_moment)."""
        entry = self.history_list.current_entry()
        if positions_known(entry):
            ms, unit_key = fight_moment(entry)
            self.show_moment(entry, entry.locator.start_ms + ms, unit_key)

    @Slot(object, str, int)
    def _show_player_positions(self, entry, unit_key, ms):
        """A death's Positions in the player window's recap: the positions
        window at that moment of the player window's fight."""
        if positions_known(entry):
            self.show_moment(entry, entry.locator.start_ms + ms, unit_key or None)

    @Slot(object, str)
    def _open_positions_player(self, entry, unit_key):
        """The positions window's player: the player window on that unit's
        row of the window's fight, at Build; at Deaths for a player the
        fight's table does not list who died, as Also died opens them. A
        unit with neither (an enemy, a pet, a player with no build logged
        who did not die) has no page there, and the status bar says so: the
        player window would show another player in its place."""
        unit_key = str(unit_key)
        if player_for(entry, unit_key) is not None:
            tab = BUILD_TAB
        elif deaths_by_unit(entry).get(unit_key):
            tab = DEATHS_TAB
        else:
            self.statusBar().showMessage("There is no player window for that one", 5000)
            return
        self._open_player(unit_key, tab, entry=entry)

    def _redraw_fight(self):
        """The fight on screen drawn again in place (it changed, a theme
        switch, Hide names, a new text size): each page where the reader
        had it, the search going on from its place among the matches of the
        tab on screen (_search_place); the Events page keeps its row
        itself."""
        view = self._search_view()
        place = (self._search_place(view.textCursor().position())
                 if view is not self.events_view else None)
        with self.fight_view.keeping_place():
            self._show_fight(search_from=place)

    def _toggle_detail(self, checked):
        self._detailed = checked
        if self.fight_tabs.currentIndex() != 0:
            # Detail view changes the Fight page alone: the page on screen
            # is left as it is, its search where it was, and the Fight
            # page's search starts at its first match when it is next
            # shown, as on a page drawn anew (#206)
            self._search_places[self.fight_view] = (self.search_field.text(), None)
            self._show_fight(others=False)
        else:
            self._show_fight()

    # ---- hidden names ----

    def _names_for(self, entry) -> NameMask:
        """The Hide names mask for *entry*: the identity while the switch
        is off; with it on, every player but the logging one hidden."""
        return NameMask.for_entry(entry, self._hide_names)

    def _toggle_hide_names(self, checked):
        """The toolbar button or Ctrl+H: the state is saved at once (the
        button shows it, so the next start holds no surprise) and the
        fight on screen and every open window are redrawn with it."""
        self._hide_names = bool(checked)
        self.history_list.hide_names = self._hide_names
        self.config.set("privacy.hide_names", self._hide_names)
        self.config.save()
        self._refresh_names()

    def _shown_path(self, path) -> str:
        """*path* as the window shows it: under Hide names its name alone,
        since its folder names the Windows user (issue #194)."""
        return Path(path).name if self._hide_names else str(path)

    def _review_banner_text(self) -> str:
        """The review banner's line, the file as _shown_path shows it."""
        return (f"Reviewing {self._shown_path(self._review_path or '')} — live monitoring "
                f"continues in the background")

    def _refresh_names(self):
        """Redraw everything that shows a player name with the current
        mask: the pane and the strip through _show_fight, and each open
        window with a mask for the fight it holds, which may not be the
        one on screen; and the review banner, which names a folder."""
        if self._review_path:
            self.banner.setText(self._review_banner_text())
        if self.history_list.current_entry() is not None:
            # Redrawn in place: the reader is looking at this page, about
            # to take the picture, so it stays where it was scrolled to
            self._redraw_fight()
        # A window hidden or never filled draws nothing (its refresh)
        for window in self._windows():
            window.refresh(self._dark, names=self._names_for(window.entry))

    # ---- text size ----

    def _step_text_size(self, direction: int):
        """Ctrl+= / Ctrl+- / Ctrl+0: one step bigger, smaller, or 100%."""
        self.set_text_size(text_size.step(text_size.percent(), direction))

    def set_text_size(self, pct):
        """Apply and save the app-wide text size, then redraw every page.
        A view zoomed with Ctrl + mouse wheel drops its own size and takes
        the new one, so the setting is what the user sees everywhere."""
        views = ([self.fight_view, self.deaths_view, self.instance_view]
                 + [view for window in self._windows() for view in window.views()])
        # Where each page's link reached with Tab is on the screen, before
        # the new size moves it: the redraw cannot see it once the font has
        # changed, so it is put back there afterwards (FightView.keeping_place)
        tops = [(view, view.link_top()) for view in views]
        applied = text_size.apply(pct)
        self.config.set(text_size.CONFIG_KEY, applied)
        self.config.save()
        for view in views:
            view.setFont(QFont())  # inherit the application font again
        # The pane and every open window are rendered from their view's
        # font, as for a flip of Hide names
        self._refresh_names()
        # The windows are laid out at the new size before the links go
        # back: the toolbar, the strip, the search row and the status bar
        # grow, and the pane loses that height, so a link kept where it was
        # in the pane as it was would end below its foot, where Tab leaves
        # the links it scrolls to. A layout's request posts its parent's, so
        # it takes a few passes.
        for _ in range(3):
            QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
        for view, top in tops:
            if top is not None and view.isVisible():
                view.keep_link_at(top)
        self.statusBar().showMessage(f"Text size {applied}%", 3000)

    def _apply_pen_crit_settings(self):
        """Settings saved new pen/crit options (the assumed Champion Point
        rows and the cap): the pane's tokens and the player window's pages
        take them at once, each keeping its place (decision 10, issue #196),
        where they waited for the next build window."""
        if self.history_list.current_entry() is not None:
            self._redraw_fight()
        if self._player_window is not None:
            self._player_window.redraw_pages()

    def _apply_privacy_settings(self):
        """Settings saved: the action follows the box (its toggled signal
        redraws when the state changed)."""
        self.hide_names_action.setChecked(bool(self.config.get("privacy.hide_names", False)))

    def _copy_current(self):
        entry = self.history_list.current_entry()
        if entry is not None:
            QGuiApplication.clipboard().setText(render_plain_text(
                entry, pen_crit_options=self.config.get("pen_crit") or {},
                names=self._names_for(entry)))
            self.statusBar().showMessage("Fight summary copied to clipboard", 3000)

    def _copy_session(self):
        """Copy session: every fight of the list, live or under review, as
        a recap (session_recap), names through the Hide names switch; the
        status bar says how long it is against a Discord message."""
        fights = self._current_fights()
        if not fights:
            self.statusBar().showMessage("No fights to copy", 3000)
            return
        self._copy_recap(fights, "Session")

    def _copy_recap(self, fights, what):
        """*fights* on the clipboard as a recap (session_recap), names
        through the Hide names switch; the status bar says how long it is
        against a Discord message."""
        text = recap_text(fights, NameMask.for_entries(fights, self._hide_names))
        QGuiApplication.clipboard().setText(text)
        note = f"{what} recap copied to clipboard, {len(text):,} characters"
        if len(text) > DISCORD_LIMIT:
            note += f": a Discord message takes {DISCORD_LIMIT:,}, so paste it in parts"
        self.statusBar().showMessage(note, 6000)

    # ---- actions ----

    def _confirm_archive(self):
        reply = QMessageBox.question(
            self, "Archive now",
            "Create a dated zip archive of the active Encounter.log now?\n\n"
            "The archive is skipped if ESO currently has the log open.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            self.request_archive.emit()

    def _show_about(self):
        """Version, project link, and credits (ESO-Hub links, ZeniMax icons)."""
        from gui.about import show_about
        channel = self._update_channel()
        if channel is None:
            updates = "Updates: not checked (turned off in Settings)"
        else:
            name, offers = {key: (name, offers)
                            for key, name, offers in CHANNEL_CHOICES}[channel]
            updates = f"Update channel: {name} ({offers})"
        show_about(self, __version__, updates)

    # ---- the trial score banner (banner_capture, issue #167) ----

    def _banner_folder(self):
        """Where the banners go: the Settings folder, else Banners beside
        the monitored log. The log is the one the engine reported, or the
        one the config resolves to: the session replayed at attach delivers
        its fights before monitoring_started is sent, and their banners
        must be found then."""
        configured = self.config.get("banner.dir")
        if configured:
            return Path(configured)
        log = self._log_path
        if not log:
            from app_startup import resolve_log_path
            log = resolve_log_path(self.config)
        return Path(log).parent / "Banners" if log else None

    @Slot(object)
    def _on_trial_result(self, result):
        """END_TRIAL, as the engine reads it: start the burst now, with
        the fight to attach the banner to still to come (END_COMBAT trails
        the line by up to 6 s and the banner is up for ten). Only for a
        live result, with the capture on, one burst at a time, one try per
        run, never during a review."""
        from banner_capture import BannerTarget, existing_banner
        if self._restart_pending or self._review_fights is not None:
            return
        target = BannerTarget.from_result(result)
        if target is None or target.key in self._banner_done:
            return
        folder = self._banner_folder()
        if existing_banner(folder, target) is not None:
            return  # found when the fight arrives
        if (sys.platform != "win32" or not self.config.get("banner.enabled", False)
                or folder is None or self._banner_burst is not None or not target.is_live()):
            return
        from gui.banner_burst import BannerBurst
        self._banner_done.add(target.key)
        # What the burst saw goes to banner.log, beside the settings and crash.log
        burst = BannerBurst(target, folder, self, log_path=Path(self.config.path).parent / "banner.log")
        burst.finished.connect(self._on_banner_finished)
        self._banner_burst = burst
        self.statusBar().showMessage("Capturing the score banner…", 4000)
        burst.start()

    def _attach_banner(self, entry):
        """A fight carrying a run's result: give it the banner captured
        this session, or the one already saved for the run (the history is
        rebuilt from the log at every start), or hand it to the burst still
        running for it, which attaches it when it reports."""
        from banner_capture import BannerTarget, existing_banner
        if getattr(entry, "banner_path", None):
            return
        target = BannerTarget.from_entry(entry)
        if target is None:
            return
        path = self._banner_files.get(target.key)
        if path is None:
            path = existing_banner(self._banner_folder(), target)
        if path is not None:
            entry.banner_path = path
            return
        burst = self._banner_burst
        if burst is not None and burst.target.key == target.key:
            burst.entry = entry

    @Slot(object, str)
    def _on_banner_finished(self, path, message):
        burst = self._banner_burst
        self._banner_burst = None
        self.statusBar().showMessage(message, 8000)
        if path is None or burst is None:
            return
        self._banner_files[burst.target.key] = path
        entry = burst.entry
        if entry is None:
            return  # the fight is still to come: _attach_banner finds the file
        entry.banner_path = path
        self._fight_changed(entry)

    @Slot(str)
    def _show_banner(self, action):
        """The result strip's banner links, on the fight on screen."""
        self._banner_action(self.history_list.current_entry(), action)

    def _banner_action(self, entry, action):
        """A banner link on *entry*, the fight that carries a run's result:
        open the PNG, save a copy elsewhere, or put the image on the
        clipboard. The Instance page's links act on its result's fight,
        which need not be the fight on screen (issue #196)."""
        import shutil
        path = getattr(entry, "banner_path", None) if entry is not None else None
        if not path or not Path(path).is_file():
            self.statusBar().showMessage("The score banner file is gone", 5000)
            return
        path = Path(path)
        if action == "save":
            target, _ = QFileDialog.getSaveFileName(
                self, "Save the score banner as", str(Path.home() / path.name), "PNG image (*.png)")
            if target:
                try:
                    shutil.copyfile(path, target)
                    self.statusBar().showMessage(f"Saved {self._shown_path(target)}", 5000)
                except OSError as exc:
                    self.statusBar().showMessage(f"Could not save the banner: {exc}", 8000)
        elif action == "copy":
            from PySide6.QtGui import QImage
            image = QImage(str(path))
            if image.isNull():
                self.statusBar().showMessage("The score banner could not be read", 5000)
                return
            QGuiApplication.clipboard().setImage(image)
            self.statusBar().showMessage("Score banner copied", 4000)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_settings(self):
        dialog = SettingsDialog(self.config, self, history_status=self.history_status(),
                                on_build_history=self.start_backfill)
        updates_before = self._update_settings_key()
        engine_before = engine_settings(self.config)
        pen_crit_before = repr(self.config.get("pen_crit") or {})
        if dialog.exec() == SettingsDialog.Accepted:
            dialog.apply_to_config()
            self.config.save()
            self._apply_update_settings(updates_before)
            self._apply_privacy_settings()
            if repr(self.config.get("pen_crit") or {}) != pen_crit_before:
                self._apply_pen_crit_settings()
            set_reduce_motion(bool(self.config.get("display.reduce_motion", False)))
            # The graph on screen redraws with the new colours; a hidden one
            # is drawn when it is next shown
            on_graph = self.fight_tabs.currentWidget() is self.dps_panel
            self.dps_panel.set_colorblind(bool(self.config.get("display.colorblind_graph", False)),
                                          redraw=on_graph)
            if not on_graph:
                self._graph_dirty = True
            if self.config.get(text_size.CONFIG_KEY) != text_size.percent():
                self.set_text_size(self.config.get(text_size.CONFIG_KEY))
            if engine_settings(self.config) != engine_before:
                self.statusBar().showMessage("Settings saved — restarting monitoring", 5000)
                # The history is cleared when the engine reaches the restart
                # (see _on_monitoring_restarting); until then its fights are
                # the old analyzer's and are dropped
                self._restart_pending = True
                self.request_restart.emit()
            else:
                # Nothing the engine reads changed (issue #187): no replay,
                # the fights listed stay, and _restart_pending stays False
                # (set, it would drop every fight until the next restart)
                self.statusBar().showMessage("Settings saved", 5000)
            self._start_retention()  # new retention settings act now
        # Design: Qt objects are freed on the UI thread. Delete the closed
        # dialog here, on the UI thread, rather than leave
        # it to Python's garbage collector, which frees whatever is garbage
        # on whichever thread is allocating at the time. That was the engine
        # thread replaying the log after the restart, and freeing the
        # dialog's Qt objects there aborted the app (settings crash, 0.6.7)
        dialog.deleteLater()

    def _open_review_dialog(self):
        start_dir = str(Path(self.config.get("split.dir")
                             or self.config.get("log_path") or Path.home()).parent)
        path, _ = QFileDialog.getOpenFileName(
            self, "Open encounter log for review", start_dir,
            "Encounter logs (*.log *.zip);;All files (*)")
        if path:
            self._request_review_of(path)

    def _request_review_of(self, path):
        """Open log for review on *path*, from the toolbar's dialog or a
        file under the empty pane's Recent activity: a zip's one log, or
        the one chosen when it holds several, then the request to the
        review thread (_start_review)."""
        member = ""
        if is_zip(Path(path)):
            # A zipped split or an archive: its one log, or the one chosen
            try:
                members = log_members(Path(path))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Review", f"Could not read {path}: {exc}")
                return
            if not members:
                QMessageBox.information(self, "Review",
                                        f"{Path(path).name} holds no encounter log.")
                return
            if len(members) > 1:
                member, ok = QInputDialog.getItem(
                    self, "Review", f"{Path(path).name} holds {len(members)} logs. Open:",
                    members, 0, False)
                if not ok:
                    return
        self.statusBar().showMessage(f"Loading {self._shown_path(path)}…")
        self.request_review.emit(path, member)

    def _exit_review(self):
        # A reviewed fight still in a window is read from the reviewed file
        # while a window holds it (_keep_review_source, _reread_places)
        self._keep_review_source()
        self._review_fights = None
        self._review_path = None
        self._review_source = None
        self.banner.setVisible(False)
        self.back_to_live_action.setVisible(False)
        if self._replaying:
            # During a Settings replay: the fights so far listed, none
            # selected, and the newest once the replay is in (_end_replay),
            # rather than each one drawn as it comes
            self._replay_key = None
            self.history_list.set_fights(self._fights)
            self._update_windows_listed()
            if self._log_missing and not self._fights:
                # The restart found no log, so nothing is being replayed:
                # the log's first fight, once it appears, puts the replay's
                # line up (_on_fight_completed)
                self._show_empty_state("waiting")
            else:
                self._show_replaying()
            return
        self._reload_list(self._fights)
        self._follow_live = True
        if not self._fights:
            # 'back' would say a log is monitored
            self._show_empty_state("waiting" if self._log_missing else "back")


def _player_handle(entry, unit_id) -> str:
    """The name the player *unit_id* has in the fight *entry*, a row's or,
    for a player the table does not list, their death recap's: what a
    Settings replay is checked by (MainWindow._rebind_windows)."""
    p = player_for(entry, unit_id)
    if p is not None:
        return str(p.get("name") or "")
    recaps = deaths_by_unit(entry).get(str(unit_id), [])
    return str(recaps[0].get("name") or "") if recaps else ""


def _age_text(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d"
