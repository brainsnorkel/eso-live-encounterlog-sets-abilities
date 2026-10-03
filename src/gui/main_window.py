"""
Main window: live fight view, session fight history, review mode,
settings, manual archive, and the freshness status bar.
"""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction, QColor, QGuiApplication, QKeySequence, QShortcut, QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)

from ability_icons import esohub_set_url, esohub_skill_url
from app_config import AppConfig
from gui.death_recap_dialog import DeathRecapDialog
from gui.death_render import death_tooltips
from gui.engine_worker import EngineWorker
from gui.fight_render import (
    anchor_names, anchor_tooltips, muted_color, render_html, render_plain_text,
    summary_line,
)
from gui.fight_view import FightView
from gui.settings_dialog import SettingsDialog
from gui.timeline_strip import TimelineStrip
from version import __version__

# Freshness state thresholds (log-freshness spec)
LIVE_SECONDS = 2 * 60
IDLE_SECONDS = 30 * 60

# State colors per theme: dark backgrounds need lighter accents and vice versa
_STATE_COLORS = {
    True: {"live": "#81c784", "idle": None, "stale": "#ffb74d", "none": "#e57373"},
    False: {"live": "#2e7d32", "idle": None, "stale": "#b25a00", "none": "#c62828"},
}


def state_style(state: str, dark: bool) -> str:
    color = _STATE_COLORS[bool(dark)].get(state)
    return f"color: {color};" if color else ""


class MainWindow(QMainWindow):

    request_archive = Signal()
    request_restart = Signal()
    request_review = Signal(str)
    request_update_download = Signal(str, str)  # url, asset name

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"ESO Log Tail v{__version__}")
        self.resize(1080, 720)

        self._fights = []          # live session FightHistoryEntry list
        self._review_fights = None  # list when in review mode, else None
        self._review_path = None
        self._detailed = True
        self._last_status = None
        self._follow_live = True
        self._last_placeholder = ""
        self._death_dialog = None  # created on the first death-recap click
        # Theme-aware text colors: pick per the actual window background
        self._dark = self.palette().color(self.backgroundRole()).lightness() < 128

        self._build_ui()
        self._build_worker()

        # Follow live theme switches (e.g. Windows auto dark mode after
        # sunset): rendered HTML embeds theme colors, so it must re-render
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(
                lambda *_: self._on_theme_maybe_changed())
        except AttributeError:
            pass  # older Qt: changeEvent still covers palette changes

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
        self.timeline_strip.update()
        if self._death_dialog is not None:
            self._death_dialog.refresh(dark)
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
        self.worker.review_loaded.connect(self._on_review_loaded)
        self.worker.parse_progress.connect(self._on_parse_progress)
        self.worker.update_available.connect(self._on_update_available)
        self.worker.update_ready.connect(self._on_update_ready)
        self.worker.update_failed.connect(self._on_update_failed)

        self.request_archive.connect(self.worker.archive_now)
        self.request_restart.connect(self.worker.restart_monitoring)
        self.request_review.connect(self.worker.open_review)
        self.request_update_download.connect(self.worker.download_update)

        self.worker_thread.started.connect(self.worker.start)
        # Canonical Qt worker teardown: delete the worker (and its timers)
        # once its thread's event loop has finished, not at interpreter exit
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.start()

    def closeEvent(self, event):
        self._ticker.stop()
        # Stop worker timers on their own thread, then end the loop and wait.
        # Destroying a QThread that is still running is a native crash, so
        # block as long as it takes rather than proceed with it running.
        # (If the thread already finished, the worker has been deferred-
        # deleted via finished->deleteLater and must not be touched.)
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
        self._fights.append(entry)
        if self._review_fights is None:
            item = QListWidgetItem(summary_line(entry, death_cue=True))
            self.history_list.addItem(item)
            if self._follow_live:
                self.history_list.setCurrentRow(self.history_list.count() - 1)

    @Slot(object)
    def _on_fight_updated(self, entry):
        """A delivered fight gained a death (logged just after combat ended):
        its history line gets the death cue, and the pane is redrawn if it is
        the fight on screen."""
        fights = self._current_fights()
        # Late deaths belong to the newest fight, so look from the end
        row = next((i for i in range(len(fights) - 1, -1, -1)
                    if fights[i] is entry), -1)
        item = self.history_list.item(row) if row >= 0 else None
        if item is None:
            return
        item.setText(summary_line(entry, death_cue=True))
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

    def _prompt_update(self, info) -> str:
        """Ask about an available update: 'update' | 'later' | 'skip'."""
        box = QMessageBox(self)
        box.setWindowTitle("Update available")
        box.setIcon(QMessageBox.Information)
        box.setText(f"ESO Log Tail {info.version} is available "
                    f"(you have {__version__}).")
        notes = (info.notes or "").strip()
        if notes:
            box.setDetailedText(notes)
        update_btn = box.addButton("Update now", QMessageBox.AcceptRole)
        box.addButton("Later", QMessageBox.RejectRole)
        skip_btn = box.addButton("Skip this version", QMessageBox.DestructiveRole)
        box.setDefaultButton(update_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is update_btn:
            return "update"
        if clicked is skip_btn:
            return "skip"
        return "later"

    @Slot(object)
    def _on_update_available(self, info):
        choice = self._prompt_update(info)
        if choice == "update":
            self.statusBar().showMessage(
                f"Downloading update {info.version}…")
            self.request_update_download.emit(info.installer_url,
                                              info.installer_name)
        elif choice == "skip":
            self.config.set("update.skip_version", info.version)
            self.config.save()

    @Slot(str)
    def _on_update_ready(self, installer_path):
        reply = QMessageBox.question(
            self, "Install update",
            "The update has downloaded. Install it now?\n\n"
            "ESO Log Tail will close and the installer will take over; "
            "your settings are kept and monitoring resumes when it "
            "relaunches.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply != QMessageBox.Yes:
            self.statusBar().showMessage(
                f"Update downloaded to {installer_path} — run it when ready",
                15000)
            return
        import subprocess
        try:
            subprocess.Popen([installer_path], close_fds=True)
        except OSError as exc:
            QMessageBox.warning(self, "Update",
                                f"Could not start the installer:\n{exc}")
            return
        self.close()

    @Slot(str)
    def _on_update_failed(self, reason):
        self.statusBar().showMessage(f"Update {reason}", 15000)

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
                QListWidgetItem(summary_line(entry, death_cue=True)))
        if fights:
            self.history_list.setCurrentRow(len(fights) - 1)

    def _show_fight(self, row):
        fights = self._current_fights()
        if row < 0 or row >= len(fights):
            return
        self._follow_live = (self._review_fights is None
                             and row == len(fights) - 1)
        entry = fights[row]
        self.timeline_strip.set_timeline(getattr(entry, 'buff_timeline', None))
        # Ability icons replace names in the detail view; the hover text, the
        # ESO-Hub link and the searchable name of each icon come from the
        # same per-slot data. Death-recap buttons show in both views
        tooltips = death_tooltips(entry)
        if self._detailed:
            tooltips.update(anchor_tooltips(
                entry, links=esohub_skill_url, set_links=esohub_set_url))
            self.fight_view.set_anchor_names(anchor_names(entry, links=esohub_skill_url))
        else:
            self.fight_view.set_anchor_names({})
        self.fight_view.set_tooltips(tooltips)
        self.fight_view.setHtml(render_html(entry, self._detailed, dark=self._dark,
                                            icons=self.fight_view.icons,
                                            links=esohub_skill_url,
                                            set_links=esohub_set_url,
                                            base_pt=self.fight_view.font().pointSizeF()))
        self._apply_search()

    def _show_death_recap(self, unit_id):
        """A player's death-recap button was clicked in the fight on screen."""
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if row < 0 or row >= len(fights):
            return
        if self._death_dialog is None:
            self._death_dialog = DeathRecapDialog(self, icons=self.fight_view.icons)
        self._death_dialog.show_recap(fights[row], unit_id, self._dark)
        self._death_dialog.show()
        self._death_dialog.raise_()
        self._death_dialog.activateWindow()

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
        self.fight_view.setExtraSelections(selections)
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

    def _copy_current(self):
        fights = self._current_fights()
        row = self.history_list.currentRow()
        if 0 <= row < len(fights):
            QGuiApplication.clipboard().setText(render_plain_text(fights[row]))
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
            self._fights.clear()
            if self._review_fights is None:
                self.history_list.clear()
            self.statusBar().showMessage("Settings saved — restarting monitoring", 5000)
            self.request_restart.emit()

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
