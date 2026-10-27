"""
Main window: live fight view, session fight history, review mode,
settings, manual archive, and the freshness status bar.
"""

import base64
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (
    QAction, QColor, QDesktopServices, QGuiApplication, QKeySequence, QPalette,
    QCursor, QShortcut, QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QProgressBar, QSizePolicy, QSplitter,
    QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from ability_icons import esohub_ability_url, esohub_script_url, esohub_set_url
from app_config import AppConfig
from gui.build_dialog import BuildDialog
from gui.build_issues_popup import BuildIssuesPopup
from gui.build_render import PEN_CRIT_ANCHOR, player_for
from gui.damage_dialog import DamageDialog
from gui.death_recap_dialog import DeathRecapDialog
from gui.death_render import death_tooltips
from gui.dps_graph import DpsGraphDialog
from gui.engine_worker import EngineWorker
from gui.fight_render import (
    ISSUES_CUE, anchor_names, anchor_tooltips, build_tooltips, damage_tooltips, issues_html,
    issues_tooltips, link_color, misfortunes_tooltips, muted_color, pen_crit_tooltips, render_html,
    render_plain_text, summary_line,
)
from gui.fight_view import FightView
from gui.name_mask import NameMask
from gui.settings_dialog import SettingsDialog
from gui.timeline_strip import TimelineStrip, strip_timeline
from gui.update_poller import UpdatePoller
from gui.update_popup import UpdateNotesPopup
from pen_crit import armour_row
from update_check import format_release_date
from version import __version__

# Freshness state thresholds (log-freshness spec)
LIVE_SECONDS = 2 * 60
IDLE_SECONDS = 30 * 60

# State colors per theme: dark backgrounds need lighter accents and vice versa
_STATE_COLORS = {
    True: {"live": "#81c784", "idle": None, "stale": "#ffb74d", "none": "#e57373"},
    False: {"live": "#2e7d32", "idle": None, "stale": "#b25a00", "none": "#c62828"},
}


# Windows updates through its installer; other platforms have none, so an
# update there is a download from the release page
HAS_INSTALLER = sys.platform == "win32"


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
    request_review = Signal(str)

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
        self._graph_dialog = None  # created on the first DPS graph request
        # Theme-aware text colors: pick per the actual window background
        self._dark = self.palette().color(self.backgroundRole()).lightness() < 128
        # The Hide names switch (issue #72, gui.name_mask): every player
        # name but the logging player's hidden, for screenshots and
        # sharing. One state behind the toolbar button, Ctrl+H and the
        # Settings box, saved whenever it flips
        self._hide_names = bool(config.get("privacy.hide_names", False))

        self._build_ui()
        self._build_update_poller()
        self._build_worker()  # last: the engine thread starts here

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
        self._style_update_buttons()
        self.timeline_strip.update()
        if self._death_dialog is not None:
            self._death_dialog.refresh(dark)
        if self._build_dialog is not None:
            self._build_dialog.refresh(dark)
        if self._damage_dialog is not None:
            self._damage_dialog.refresh(dark)
        if self._graph_dialog is not None:
            self._graph_dialog.refresh(dark)
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if 0 <= row < len(fights):
            self._show_fight(row)
        elif self._last_placeholder:
            self._show_placeholder(self._last_placeholder)

    # ---- UI construction ----

    def _build_ui(self):
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        self.detail_action = QAction("Detail view", self)
        self.detail_action.setCheckable(True)
        self.detail_action.setChecked(True)
        self.detail_action.setShortcut(QKeySequence(Qt.Key_Tab))
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
        self.history_list = QListWidget()
        self.history_list.currentRowChanged.connect(self._show_fight)
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
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self._apply_search)
        self.search_field.returnPressed.connect(self._goto_next_match)
        self.search_count = QLabel("")
        search_row.addWidget(self.search_field, 1)
        search_row.addWidget(self.search_count)
        right_layout.addLayout(search_row)

        # Serves bundled ability icons, hover names, and ESO-Hub link clicks
        self.fight_view = FightView()
        self.fight_view.death_recap_requested.connect(self._show_death_recap)
        self.fight_view.build_requested.connect(self._show_build)
        self.fight_view.damage_requested.connect(self._show_damage)
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
        # Shared work-progress bar (archiving, review parsing, catch-up);
        # the worker thread serializes these, so one bar can't be contended
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(220)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)

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
        self.worker.waiting_for_log.connect(self._on_waiting_for_log)
        self.worker.monitoring_started.connect(self._on_monitoring_started)
        self.worker.monitoring_restarting.connect(self._on_monitoring_restarting)
        self.worker.review_loaded.connect(self._on_review_loaded)
        self.worker.parse_progress.connect(self._on_parse_progress)

        requests = ((self.request_archive, self.worker.archive_now),
                    (self.request_restart, self.worker.restart_monitoring),
                    (self.request_review, self.worker.open_review))
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

    @Slot(object)
    def _on_fight_completed(self, entry):
        if self._restart_pending:
            return  # from the analyzer Settings is replacing
        self._fights.append(entry)
        if self._review_fights is None:
            item = QListWidgetItem(summary_line(entry, death_cue=True, issue_cue=True))
            self.history_list.addItem(item)
            if self._follow_live:
                self.history_list.setCurrentRow(self.history_list.count() - 1)

    @Slot(object)
    def _on_fight_updated(self, entry):
        """A delivered fight changed: it gained a death (logged just after
        combat ended), or the game had cut it in two and it has now really
        ended. Its history line is rewritten, and the pane is redrawn if it
        is the fight on screen."""
        if self._restart_pending:
            return
        fights = self._current_fights()
        # Both happen to the newest fight, so look from the end
        row = next((i for i in range(len(fights) - 1, -1, -1)
                    if fights[i] is entry), -1)
        item = self.history_list.item(row) if row >= 0 else None
        if item is None:
            return
        item.setText(summary_line(entry, death_cue=True, issue_cue=True))
        if row == self.history_list.currentRow():
            self._show_fight(row)

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

    @Slot(str)
    def _on_waiting_for_log(self, expected):
        self._last_status = None
        self._refresh_freshness_label()
        where = expected or "known ESO log locations"
        self._show_placeholder(
            f"Waiting for Encounter.log…<br><br>"
            f"Expected at:<br><code>{where}</code><br><br>"
            f"Enable encounter logging in ESO (/encounterlog) or install the "
            f"Easy Stalking addon. Monitoring starts automatically when the "
            f"file appears.")

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

    def _apply_update_settings(self):
        """Settings saved: the check on starts a full check now and the
        schedule; off stops both and withdraws the offer."""
        if bool(self.config.get("update.check_enabled", True)):
            self.update_poller.start()
        else:
            self.update_poller.stop()
            self._on_update_gone()

    def _apply_title(self):
        title = f"ESO Log Tail v{__version__}"
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
        as it lands (one click, the maintainer's choice of 2026-10-26);
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
        """The installer has landed: hand over to it and close. The click on
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
        self.history_list.clear()
        for entry in fights:
            self.history_list.addItem(
                QListWidgetItem(summary_line(entry, death_cue=True, issue_cue=True)))
        if fights:
            self.history_list.setCurrentRow(len(fights) - 1)

    def _show_fight(self, row):
        fights = self._current_fights()
        if row < 0 or row >= len(fights):
            return
        self._follow_live = (self._review_fights is None
                             and row == len(fights) - 1)
        entry = fights[row]
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
        tooltips.update(build_tooltips(entry, names))
        tooltips.update(damage_tooltips(entry, names))
        tooltips.update(issues_tooltips(entry))
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
                                            names=names))
        self._apply_search()

    def _show_pen_crit(self, unit_id):
        """A player's pen/crit token was clicked: their build window, open
        at its Penetration and Critical damage sections."""
        self._show_build(unit_id, scroll_to=PEN_CRIT_ANCHOR)

    def _show_death_recap(self, unit_id):
        """A player's death-recap button was clicked in the fight on screen."""
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if row < 0 or row >= len(fights):
            return
        if self._death_dialog is None:
            self._death_dialog = DeathRecapDialog(self, icons=self.fight_view.icons)
        self._death_dialog.show_recap(fights[row], unit_id, self._dark,
                                      names=self._names_for(fights[row]))
        self._death_dialog.show()
        self._death_dialog.raise_()
        self._death_dialog.activateWindow()

    def _show_build(self, unit_id, scroll_to=None):
        """A player's name was clicked in the fight on screen (*scroll_to*:
        the anchor the window opens at, for the pen/crit token)."""
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if row < 0 or row >= len(fights):
            return
        if self._build_dialog is None:
            self._build_dialog = BuildDialog(self, icons=self.fight_view.icons)
        # The Settings' assumed Champion Point rows and cap, read at render
        # time so a change applies to the next build window without a restart
        self._build_dialog.show_build(fights[row], unit_id, self._dark,
                                      pen_crit_options=self.config.get("pen_crit") or {},
                                      scroll_to=scroll_to, names=self._names_for(fights[row]))
        self._build_dialog.show()
        self._build_dialog.raise_()
        self._build_dialog.activateWindow()

    def _show_damage(self, unit_id):
        """A player's dps figure was clicked in the fight on screen."""
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if row < 0 or row >= len(fights):
            return
        if self._damage_dialog is None:
            self._damage_dialog = DamageDialog(self, icons=self.fight_view.icons)
        self._damage_dialog.show_damage(fights[row], unit_id, self._dark,
                                        names=self._names_for(fights[row]))
        self._damage_dialog.show()
        self._damage_dialog.raise_()
        self._damage_dialog.activateWindow()

    def _show_issues(self, unit_id):
        """A player's (i) was clicked in the fight on screen: their possible
        build issues, each with its rule, in a popup at the pointer. The
        popup owns itself (Qt.Popup, deleted on close), so nothing here
        keeps a reference to it."""
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if row < 0 or row >= len(fights):
            return
        text = issues_html(player_for(fights[row], unit_id), self._dark,
                           set_links=esohub_set_url, links=esohub_ability_url)
        if text:
            BuildIssuesPopup(text, self).show_at(QCursor.pos())

    def _show_graph(self):
        """The toolbar's DPS graph, or the header's group dps figure, was
        clicked: the dps over time graph of the fight on screen."""
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if row < 0 or row >= len(fights):
            return
        if self._graph_dialog is None:
            self._graph_dialog = DpsGraphDialog(self)
        self._graph_dialog.show_graph(fights[row], self._dark,
                                      names=self._names_for(fights[row]))
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
        self._show_fight(self.history_list.currentRow())

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
        self.config.set("privacy.hide_names", self._hide_names)
        self.config.save()
        self._refresh_names()

    def _refresh_names(self):
        """Redraw everything that shows a player name with the current
        mask: the pane and the strip through _show_fight, and each open
        window with a mask for the fight it holds, which may not be the
        one on screen."""
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if 0 <= row < len(fights):
            # Redrawn in place: the reader is looking at this page, about
            # to take the picture, so it stays where it was scrolled to
            scroll = self.fight_view.verticalScrollBar().value()
            self._show_fight(row)
            self.fight_view.restore_scroll(scroll)
        for dialog in (self._death_dialog, self._build_dialog,
                       self._damage_dialog, self._graph_dialog):
            if dialog is not None and dialog.isVisible() and dialog.entry is not None:
                dialog.refresh(self._dark, names=self._names_for(dialog.entry))

    def _apply_privacy_settings(self):
        """Settings saved: the action follows the box (its toggled signal
        redraws when the state changed)."""
        self.hide_names_action.setChecked(bool(self.config.get("privacy.hide_names", False)))

    def _copy_current(self):
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if 0 <= row < len(fights):
            QGuiApplication.clipboard().setText(render_plain_text(
                fights[row], pen_crit_options=self.config.get("pen_crit") or {},
                names=self._names_for(fights[row])))
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
        show_about(self, __version__)

    def _open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == SettingsDialog.Accepted:
            dialog.apply_to_config()
            self.config.save()
            self._apply_update_settings()
            self._apply_privacy_settings()
            self.statusBar().showMessage("Settings saved — restarting monitoring", 5000)
            # The history is cleared when the engine reaches the restart
            # (see _on_monitoring_restarting); until then its fights are
            # the old analyzer's and are dropped
            self._restart_pending = True
            self.request_restart.emit()
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
            "Log files (*.log);;All files (*)")
        if path:
            self.statusBar().showMessage(f"Loading {path}…")
            self.request_review.emit(path)

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
