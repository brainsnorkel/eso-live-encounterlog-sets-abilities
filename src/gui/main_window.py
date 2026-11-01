"""
Main window: live fight view, session fight history, review mode,
settings, manual archive, and the freshness status bar.
"""

import base64
import html
import sys
import weakref
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (
    QAction, QColor, QDesktopServices, QFont, QFontMetrics, QGuiApplication, QKeySequence, QPalette,
    QCursor, QShortcut, QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QSizePolicy, QSplitter,
    QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

import fight_index
from ability_icons import esohub_ability_url, esohub_script_url, esohub_set_url
from app_config import AppConfig
from fight_index import (
    FightIndex,
    comparison,
    comparison_text,
    fight_line,
    index_path,
    player_history,
    player_history_text,
)
from gui import text_size
from gui.build_dialog import BuildDialog
from gui.build_issues_popup import BuildIssuesPopup
from gui.build_render import PEN_CRIT_ANCHOR, player_for
from gui.damage_dialog import DamageDialog
from gui.death_recap_dialog import DeathRecapDialog
from gui.death_render import death_tooltips
from gui.dps_graph import DpsGraphDialog
from gui.engine_worker import EngineWorker
from gui.fight_list import FightList
from gui.fight_render import (
    ISSUES_CUE, anchor_names, anchor_tooltips, build_tooltips, damage_tooltips, issues_html,
    issues_tooltips, link_color, mastery_tooltips, misfortunes_tooltips, muted_color, pen_crit_tooltips,
    render_html,
    render_plain_text, taken_tooltips,
)
from gui.fight_view import FightView, set_reduce_motion
from gui.name_mask import NameMask
from gui.review_runner import ReviewRunner
from gui.settings_dialog import SettingsDialog
from gui.taken_dialog import TakenDialog
from gui.timeline_strip import TimelineStrip, strip_timeline
from gui.update_poller import UpdatePoller
from gui.update_popup import UpdateNotesPopup
from log_open import is_zip, log_members, log_size
from pen_crit import armour_row
from recycle_bin import TRASH_NAME
import review_load
import split_retention
from update_check import CHANNEL_CHOICES, format_release_date, normalize_channel
from version import __version__

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


class _RetentionBridge(QObject):
    """Carries a retention run's events from its thread to this one."""
    event = Signal(object)  # split_retention.RetentionEvent


class _ReviewBridge(QObject):
    """Carries a review's events from its thread to this one."""
    event = Signal(object)  # gui.review_runner.ReviewEvent


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
        self._detailed = True
        self._last_status = None
        self._follow_live = True
        self._restart_pending = False  # Save pressed, engine not yet restarted
        self._last_placeholder = ""
        self._death_dialog = None  # created on the first death-recap click
        self._build_dialog = None  # created on the first click on a player's name
        self._damage_dialog = None  # created on the first click on a player's dps
        self._taken_dialog = None  # created on the first click on a player's shield
        self._graph_dialog = None  # created on the first DPS graph request
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
        self._build_worker()  # last: the engine thread starts here
        self._offer_backfill()

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
        self._style_update_buttons()
        self.timeline_strip.update()
        if self._death_dialog is not None:
            self._death_dialog.refresh(dark)
        if self._build_dialog is not None:
            self._build_dialog.refresh(dark)
        if self._damage_dialog is not None:
            self._damage_dialog.refresh(dark)
        if self._taken_dialog is not None:
            self._taken_dialog.refresh(dark)
        if self._graph_dialog is not None:
            self._graph_dialog.refresh(dark)
        if self.history_list.current_entry() is not None:
            self._show_fight()
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
        # EXPERIMENTAL buff timeline strip: sits between the header area and
        # the summary text; hidden whenever the fight has no timeline data
        self.timeline_strip = TimelineStrip()
        right_layout.addWidget(self.timeline_strip)

        # In-fight text search: highlights every match in the detail pane
        search_row = QHBoxLayout()
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText(
            "Search in fight… (Ctrl+F, Enter jumps to next match; "
            "ability icons match by name)")
        self.search_field.setAccessibleName("Search in fight")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self._apply_search)
        self.search_field.returnPressed.connect(self._goto_next_match)
        self.search_count = QLabel("")
        search_row.addWidget(self.search_field, 1)
        search_row.addWidget(self.search_count)
        right_layout.addLayout(search_row)

        # Serves bundled ability icons, hover names, and ESO-Hub link clicks
        self.fight_view = FightView()
        self.fight_view.setAccessibleName("Fight")
        self.fight_view.death_recap_requested.connect(self._show_death_recap)
        self.fight_view.build_requested.connect(self._show_build)
        self.fight_view.damage_requested.connect(self._show_damage)
        self.fight_view.taken_requested.connect(self._show_taken)
        self.fight_view.graph_requested.connect(self._show_graph)
        self.fight_view.issues_requested.connect(self._show_issues)
        self.fight_view.pen_crit_requested.connect(self._show_pen_crit)
        right_layout.addWidget(self.fight_view, 1)

        focus_search = QAction("Find in fight", self)
        focus_search.setShortcut(QKeySequence.Find)
        focus_search.triggered.connect(
            lambda: (self.search_field.setFocus(), self.search_field.selectAll()))
        self.addAction(focus_search)
        QShortcut(QKeySequence(Qt.Key_Escape), self.search_field,
                  activated=self.search_field.clear,
                  context=Qt.WidgetShortcut)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)
        self._splitter = splitter

        # Status bar: freshness (left), zone (middle), archive progress (right)
        self.freshness_label = QLabel("No log file")
        self.statusBar().addWidget(self.freshness_label)
        self.zone_label = QLabel("")
        self.statusBar().addWidget(self.zone_label)
        # Lasting problems (issue #111): split writing stopped, the log
        # failing to read poll after poll. Permanent, so a status message
        # never hides it; it goes when its source says the problem cleared
        self._warnings = {}
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

    def _save_window_layout(self):
        self.config.set("window.geometry", _encode_state(self.saveGeometry()))
        self.config.set("window.splitter", _encode_state(self._splitter.saveState()))
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
        self.worker.waiting_for_log.connect(self._on_waiting_for_log)
        self.worker.monitoring_started.connect(self._on_monitoring_started)
        self.worker.monitoring_restarting.connect(self._on_monitoring_restarting)
        self.worker.parse_progress.connect(self._on_parse_progress)

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
            self._on_review_loaded(event.shown, event.fights)
        elif event.kind == "indexed":
            # The fight history grew: the run rows and the pane read it
            self.statusBar().showMessage(event.label, 15000)
            self.history_list.refresh_all_runs()
            if self.history_list.current_entry() is not None:
                self._show_fight()
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

    def _split_folder(self):
        """The split folder: the one set, else the log's own (the
        splitter's rule, as split retention reads it)."""
        try:
            return split_retention.split_folder(
                self.config.get("split.dir") or "",
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

    def start_backfill(self) -> bool:
        """Read the split logs into the fight history on the review thread
        (gui.review_runner.ReviewRunner.backfill); the status bar shows the
        progress and its Cancel button stops it. Whether it started."""
        folder = self._split_folder()
        if folder is None or not folder.is_dir():
            self.statusBar().showMessage("Fight history: no split folder is set in Settings", 10000)
            return False
        if self._review.running:
            self.statusBar().showMessage("A review is still loading: cancel it first", 8000)
            return False
        self._backfilling = True
        self._set_review_busy(True)
        self._on_parse_progress("Fight history: looking through the split logs", 0, 0)
        return self._review.backfill(self.config, str(folder), self.fight_index,
                                     self._review_notify())

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
        self._save_window_layout()
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
        if self._review_fights is None:
            row = self.history_list.add_fight(entry)
            if self._follow_live:
                self.history_list.setCurrentRow(row)

    @Slot(object)
    def _on_fight_updated(self, entry):
        """A delivered fight changed: it gained a death (logged just after
        combat ended), the game had cut it in two and it has now really
        ended, or the run's result came just after it (trial_result). Its
        history line is rewritten, and the pane is redrawn if it is the
        fight on screen."""
        if self._restart_pending:
            return
        self._index_fight(entry)
        row = self.history_list.update_fight(entry)
        if row is not None and row == self.history_list.currentRow():
            self._show_fight()

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
                f"Archived to {event.archive_path}{deleted}", 15000)
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

    @Slot(str)
    def _on_waiting_for_log(self, expected):
        self._last_status = None
        self._refresh_freshness_label()
        where = html.escape(expected or "known ESO log locations")
        self._show_placeholder(
            f"Waiting for Encounter.log…<br><br>"
            f"Expected at:<br><code>{where}</code><br><br>"
            f"Enable encounter logging in ESO (/encounterlog), or install an "
            f"addon that turns it on for you, one or the other but not both: "
            f"Always Logging (from GitHub, github.com/brainsnorkel/AlwaysLogging) "
            f"or Easy Stalking (ESOUI or Minion). "
            f"Monitoring starts automatically when the file appears.")

    @Slot()
    def _on_monitoring_restarting(self):
        """The engine has begun the restart Settings asked for. Everything
        it sent before this belonged to the analyzer being replaced, so the
        history is cleared now rather than when Save was pressed: a replay
        still running at that moment went on filling a list cleared too
        early, and its fights showed above the new analyzer's."""
        self._restart_pending = False
        self._fights.clear()
        if self._review_fights is None:
            self.history_list.clear()

    @Slot(str)
    def _on_monitoring_started(self, path):
        self.statusBar().showMessage(f"Monitoring {path}", 8000)
        if not self._fights:
            self._show_placeholder(
                "Monitoring for encounters… fight summaries appear here "
                "as combat ends.")

    @Slot(str, list)
    def _on_review_loaded(self, path, fights):
        self.statusBar().clearMessage()  # replaces the persistent "Loading…"
        if not fights:
            QMessageBox.information(self, "Review",
                                    f"No completed fights found in\n{path}")
            return
        self._review_fights = fights
        self._review_path = path
        self.statusBar().showMessage(
            f"Loaded {len(fights)} fight{'s' if len(fights) != 1 else ''} "
            f"from {path}", 8000)
        self.banner.setText(f"Reviewing {path} — live monitoring continues in "
                            f"the background")
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
            self.freshness_label.setText("No log file")
            self.freshness_label.setStyleSheet(state_style("none", self._dark))
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

    def _show_fight(self, *_):
        """The current fight in the pane and the strip (the list's
        currentRowChanged passes the row, which a header row never is)."""
        entry = self.history_list.current_entry()
        if entry is None:
            return
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
            armour_row(getattr(entry, 'pen_crit', None), pen_crit_options), names=names)
        # Ability icons replace names in the detail view; the hover text, the
        # ESO-Hub link and the searchable name of each icon come from the
        # same per-slot data. Death-recap buttons and the build link on each
        # player's name show in both views
        tooltips = death_tooltips(entry, names)
        # Each named player's last kills of the boss, and the pull against
        # the earlier kills (fight_index, issue #170)
        histories = {}
        for p in entry.players:
            handle = str(p.get("name") or "")
            if handle.startswith("@") and not p.get("companion"):
                histories[str(p.get("unit_id", ""))] = player_history_text(
                    entry, handle, player_history(self.fight_index, entry, handle), names)
        history = comparison_text(comparison(self.fight_index, entry))
        tooltips.update(build_tooltips(entry, names, histories))
        tooltips.update(damage_tooltips(entry, names))
        tooltips.update(taken_tooltips(entry, names))
        tooltips.update(issues_tooltips(entry))
        tooltips.update(mastery_tooltips(entry))
        tooltips.update(pen_crit_tooltips(entry, pen_crit_options))
        tooltips.update(misfortunes_tooltips(entry))
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
                                            history=history))
        self._apply_search()

    def _show_pen_crit(self, unit_id):
        """A player's pen/crit token was clicked: their build window, open
        at its Penetration and Critical damage sections."""
        self._show_build(unit_id, scroll_to=PEN_CRIT_ANCHOR)

    def _show_death_recap(self, unit_id):
        """A player's death-recap button was clicked in the fight on screen."""
        entry = self.history_list.current_entry()
        if entry is None:
            return
        if self._death_dialog is None:
            self._death_dialog = DeathRecapDialog(self, icons=self.fight_view.icons)
            # The fight block's link to the damage taken window (issue #98),
            # for the fight the recap shows (issue #143)
            self._death_dialog.view.taken_requested.connect(
                lambda unit_id: self._show_taken(unit_id, self._death_dialog.entry))
        self._death_dialog.show_recap(entry, unit_id, self._dark,
                                      names=self._names_for(entry))
        self._death_dialog.show()
        self._death_dialog.raise_()
        self._death_dialog.activateWindow()

    def _show_build(self, unit_id, scroll_to=None):
        """A player's name was clicked in the fight on screen (*scroll_to*:
        the anchor the window opens at, for the pen/crit token)."""
        entry = self.history_list.current_entry()
        if entry is None:
            return
        if self._build_dialog is None:
            self._build_dialog = BuildDialog(self, icons=self.fight_view.icons)
            # The Damage dealt heading's link to the damage taken window
            # (issue #98), for the fight the build window shows (issue #143)
            self._build_dialog.view.taken_requested.connect(
                lambda unit_id: self._show_taken(unit_id, self._build_dialog.entry))
        # The Settings' assumed Champion Point rows and cap, read at render
        # time so a change applies to the next build window without a restart
        self._build_dialog.show_build(entry, unit_id, self._dark,
                                      pen_crit_options=self.config.get("pen_crit") or {},
                                      scroll_to=scroll_to, names=self._names_for(entry))
        self._build_dialog.show()
        self._build_dialog.raise_()
        self._build_dialog.activateWindow()

    def _show_damage(self, unit_id):
        """A player's dps figure was clicked in the fight on screen."""
        entry = self.history_list.current_entry()
        if entry is None:
            return
        if self._damage_dialog is None:
            self._damage_dialog = DamageDialog(self, icons=self.fight_view.icons)
        self._damage_dialog.show_damage(entry, unit_id, self._dark,
                                        names=self._names_for(entry))
        self._damage_dialog.show()
        self._damage_dialog.raise_()
        self._damage_dialog.activateWindow()

    def _show_taken(self, unit_id, entry=None):
        """A player's damage-taken shield was clicked in the fight on screen,
        or the link to it in their build or death recap window: the whole
        fight's damage taken and healing received (taken_render, issue #98).
        The shield opens the fight on screen; a window's link passes the
        fight that window shows (*entry*), which stays the fight it was
        opened for while the list moves on to each new pull as the app
        follows the live log (issue #143)."""
        if entry is None:
            entry = self.history_list.current_entry()
        if entry is None:
            return
        if self._taken_dialog is None:
            self._taken_dialog = TakenDialog(self, icons=self.fight_view.icons)
        self._taken_dialog.show_taken(entry, unit_id, self._dark,
                                      names=self._names_for(entry))
        self._taken_dialog.show()
        self._taken_dialog.raise_()
        self._taken_dialog.activateWindow()

    def _show_issues(self, unit_id):
        """A player's (i) was clicked in the fight on screen: their possible
        build issues, each with its rule, in a popup at the pointer. The
        popup owns itself (Qt.Popup, deleted on close), so nothing here
        keeps a reference to it."""
        entry = self.history_list.current_entry()
        if entry is None:
            return
        text = issues_html(player_for(entry, unit_id), self._dark,
                           set_links=esohub_set_url, links=esohub_ability_url)
        if text:
            BuildIssuesPopup(text, self).show_at(QCursor.pos())

    def _show_graph(self):
        """The toolbar's DPS graph, or the header's group dps figure, was
        clicked: the dps over time graph of the fight on screen."""
        entry = self.history_list.current_entry()
        if entry is None:
            return
        if self._graph_dialog is None:
            self._graph_dialog = DpsGraphDialog(self)
        self._graph_dialog.set_colorblind(bool(self.config.get("display.colorblind_graph", False)))
        self._graph_dialog.show_graph(entry, self._dark,
                                      names=self._names_for(entry))
        self._graph_dialog.show()
        self._graph_dialog.raise_()
        self._graph_dialog.activateWindow()

    def _show_placeholder(self, html_text):
        self._last_placeholder = html_text
        self.timeline_strip.set_timeline(None)
        self.fight_view.setHtml(
            f"<div style='color:{muted_color(self._dark)};padding:16px'>"
            f"{html_text}</div>")
        self._apply_search()

    # ---- in-fight search ----

    def _search_matches(self):
        """QTextCursor for every match of the search text in the pane: each
        text occurrence, plus each ability icon whose name contains the text
        (the name is hover text, not document text). Document order."""
        text = self.search_field.text()
        matches = []
        if text:
            document = self.fight_view.document()
            cursor = QTextCursor(document)
            while True:
                cursor = document.find(text, cursor)  # case-insensitive
                if cursor.isNull():
                    break
                matches.append(QTextCursor(cursor))
            matches.extend(self.fight_view.anchor_matches(text))
            matches.sort(key=lambda c: c.selectionStart())
        return matches

    def _apply_search(self):
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
        # The pane applies these together with its hover cue
        self.fight_view.set_search_selections(selections)
        if self.search_field.text():
            n = len(selections)
            self.search_count.setText(f"{n} match{'es' if n != 1 else ''}")
        else:
            self.search_count.setText("")
        if selections:
            first = QTextCursor(selections[0].cursor)
            first.setPosition(first.selectionStart())
            self.fight_view.setTextCursor(first)
            self.fight_view.ensureCursorVisible()

    def _goto_next_match(self):
        """Enter in the search field cycles through matches."""
        matches = self._search_matches()
        if not matches:
            return
        position = self.fight_view.textCursor().position()
        target = next((m for m in matches if m.selectionStart() > position),
                      matches[0])  # wrap around
        cursor = QTextCursor(target)
        cursor.setPosition(target.selectionStart())
        self.fight_view.setTextCursor(cursor)
        self.fight_view.ensureCursorVisible()

    def _toggle_detail(self, checked):
        self._detailed = checked
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

    def _refresh_names(self):
        """Redraw everything that shows a player name with the current
        mask: the pane and the strip through _show_fight, and each open
        window with a mask for the fight it holds, which may not be the
        one on screen."""
        if self.history_list.current_entry() is not None:
            # Redrawn in place: the reader is looking at this page, about
            # to take the picture, so it stays where it was scrolled to
            scroll = self.fight_view.verticalScrollBar().value()
            self._show_fight()
            self.fight_view.restore_scroll(scroll)
        for dialog in (self._death_dialog, self._build_dialog,
                       self._damage_dialog, self._taken_dialog, self._graph_dialog):
            if dialog is not None and dialog.isVisible() and dialog.entry is not None:
                dialog.refresh(self._dark, names=self._names_for(dialog.entry))

    # ---- text size ----

    def _step_text_size(self, direction: int):
        """Ctrl+= / Ctrl+- / Ctrl+0: one step bigger, smaller, or 100%."""
        self.set_text_size(text_size.step(text_size.percent(), direction))

    def set_text_size(self, pct):
        """Apply and save the app-wide text size, then redraw every page.
        A view zoomed with Ctrl + mouse wheel drops its own size and takes
        the new one, so the setting is what the user sees everywhere."""
        applied = text_size.apply(pct)
        self.config.set(text_size.CONFIG_KEY, applied)
        self.config.save()
        for view in [self.fight_view] + [dialog.view for dialog in (
                self._death_dialog, self._build_dialog, self._damage_dialog,
                self._taken_dialog) if dialog is not None]:
            view.setFont(QFont())  # inherit the application font again
        # The pane and every open window are rendered from their view's
        # font, as for a flip of Hide names
        self._refresh_names()
        self.statusBar().showMessage(f"Text size {applied}%", 3000)

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

    def _open_settings(self):
        dialog = SettingsDialog(self.config, self, history_status=self.history_status(),
                                on_build_history=self.start_backfill)
        updates_before = self._update_settings_key()
        if dialog.exec() == SettingsDialog.Accepted:
            dialog.apply_to_config()
            self.config.save()
            self._apply_update_settings(updates_before)
            self._apply_privacy_settings()
            set_reduce_motion(bool(self.config.get("display.reduce_motion", False)))
            if self._graph_dialog is not None:
                self._graph_dialog.set_colorblind(
                    bool(self.config.get("display.colorblind_graph", False)))
            if self.config.get(text_size.CONFIG_KEY) != text_size.percent():
                self.set_text_size(self.config.get(text_size.CONFIG_KEY))
            self.statusBar().showMessage("Settings saved — restarting monitoring", 5000)
            # The history is cleared when the engine reaches the restart
            # (see _on_monitoring_restarting); until then its fights are
            # the old analyzer's and are dropped
            self._restart_pending = True
            self.request_restart.emit()
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
        if not path:
            return
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
        self.statusBar().showMessage(f"Loading {path}…")
        self.request_review.emit(path, member)

    def _exit_review(self):
        self._review_fights = None
        self._review_path = None
        self.banner.setVisible(False)
        self.back_to_live_action.setVisible(False)
        self._reload_list(self._fights)
        self._follow_live = True
        if not self._fights:
            self._show_placeholder("Back to live monitoring.")


def _age_text(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d"
