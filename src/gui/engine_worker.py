"""
Engine worker: runs the analysis engine on a QThread and bridges
AnalyzerListener callbacks to Qt signals (queued to the UI thread).

Engine modules never import Qt; this adapter is the only crossing point.
"""

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from app_config import AppConfig
from app_startup import build_analyzer, resolve_log_path, run_startup_sequence
from engine_events import AnalyzerListener
from esolog_tail import LogFileMonitor
from fight_history import FightHistory
from log_archiver import LogArchiver

POLL_INTERVAL_MS = 1000
WAIT_FOR_LOG_INTERVAL_MS = 2000


class SignalListener(AnalyzerListener):
    """Forwards engine callbacks to the worker's Qt signals."""

    def __init__(self, worker: "EngineWorker"):
        self._worker = worker

    def on_fight_completed(self, entry):
        self._worker.fight_completed.emit(entry)

    def on_zone_changed(self, zone_name, difficulty):
        self._worker.zone_changed.emit(zone_name, difficulty)

    def on_log_status(self, status):
        self._worker.log_status.emit(status)

    def on_archive_event(self, event):
        self._worker.archive_event.emit(event)

    def on_diagnostic(self, message):
        self._worker.diagnostic.emit(message)


class EngineWorker(QObject):
    """Owns the engine objects; lives on a dedicated QThread.

    All slots run on the worker thread, so polling, manual archiving, review
    replays, and monitoring restarts are naturally serialized.
    """

    fight_completed = Signal(object)   # FightHistoryEntry
    zone_changed = Signal(str, str)
    log_status = Signal(object)        # LogStatus
    archive_event = Signal(object)     # ArchiveEvent
    diagnostic = Signal(str)
    waiting_for_log = Signal(str)      # expected path
    monitoring_started = Signal(str)   # log path
    review_loaded = Signal(str, list)  # path, [FightHistoryEntry]

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.listener = SignalListener(self)
        self.analyzer = None
        self.monitor = None
        self._log_path = None
        self._poll_timer = None
        self._wait_timer = None

    # ---- lifecycle ----

    @Slot()
    def stop(self):
        """Stop timers on the worker thread ahead of thread shutdown."""
        if self._poll_timer is not None:
            self._poll_timer.stop()
        if self._wait_timer is not None:
            self._wait_timer.stop()

    @Slot()
    def start(self):
        """App startup: archive check (startup-only), then monitoring."""
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._wait_timer = QTimer(self)
        self._wait_timer.setInterval(WAIT_FOR_LOG_INTERVAL_MS)
        self._wait_timer.timeout.connect(self._check_log_appeared)

        result = run_startup_sequence(self.config, [self.listener])
        self.analyzer = result.analyzer
        self.monitor = result.monitor
        self._log_path = result.log_path

        if self.monitor is not None:
            self.monitoring_started.emit(str(self._log_path))
            self._poll_timer.start()
        else:
            self._start_waiting()

    @Slot()
    def restart_monitoring(self):
        """Settings changed: rebuild analyzer/monitor. No archive check
        (auto-archive is startup-only by spec)."""
        self._teardown()
        self._log_path = resolve_log_path(self.config)
        self.analyzer = build_analyzer(self.config, [self.listener])
        if self._log_path is not None and self._log_path.exists():
            self._attach_monitor()
        else:
            self._start_waiting()

    def _teardown(self):
        if self._poll_timer:
            self._poll_timer.stop()
        if self._wait_timer:
            self._wait_timer.stop()
        self.monitor = None
        self.analyzer = None

    def _attach_monitor(self):
        split_enabled = bool(self.config.get("split.enabled", False))
        split_dir = self.config.get("split.dir")
        self.monitor = LogFileMonitor(
            self.analyzer, self._log_path,
            read_all_then_tail=False,
            tail_and_split=split_enabled,
            split_dir=Path(split_dir) if split_dir else None,
        )
        self.monitor.running = True
        self.monitoring_started.emit(str(self._log_path))
        self._poll_timer.start()

    def _start_waiting(self):
        expected = self._log_path or resolve_log_path(self.config)
        self.waiting_for_log.emit(str(expected) if expected else "")
        self._wait_timer.start()

    # ---- timers ----

    def _poll(self):
        if self.monitor is None:
            return
        try:
            if not self.monitor.log_file.exists():
                # Log vanished (rotated/deleted): fall back to waiting
                self._poll_timer.stop()
                self._start_waiting()
                return
            size = self.monitor.log_file.stat().st_size
            if size < self.monitor.last_position:
                # Truncated/replaced: start over from the beginning
                self.monitor.last_position = 0
            self.monitor._process_new_lines()
        except Exception as exc:
            self.diagnostic.emit(f"poll error: {exc}")

    def _check_log_appeared(self):
        self._log_path = resolve_log_path(self.config)
        if self._log_path is not None and self._log_path.exists():
            self._wait_timer.stop()
            if self.analyzer is None:
                self.analyzer = build_analyzer(self.config, [self.listener])
            self._attach_monitor()

    # ---- actions ----

    @Slot()
    def archive_now(self):
        """Manual archive: same guarded operation, no threshold check."""
        if self._log_path is None or not self._log_path.exists():
            self.diagnostic.emit("Archive now: no log file to archive")
            return
        polling = self._poll_timer is not None and self._poll_timer.isActive()
        if polling:
            self._poll_timer.stop()
        try:
            archiver = LogArchiver(self.config)
            archiver.add_listener(self.listener)
            archiver.archive(self._log_path)
        finally:
            if self.monitor is not None:
                if not self.monitor.log_file.exists():
                    # Original deleted after archive: wait for a fresh log
                    self._start_waiting()
                    return
                if polling:
                    self._poll_timer.start()

    @Slot(str)
    def open_review(self, path: str):
        """Replay an arbitrary log file and hand its fights to the UI."""
        review_path = Path(path)
        try:
            analyzer = build_analyzer(self.config, [])
            analyzer.save_reports = False
            analyzer.current_log_file = str(review_path)
            with open(review_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = analyzer.log_parser.parse_line(line)
                    if entry is not None:
                        analyzer.process_log_entry(entry)
            self.review_loaded.emit(str(review_path),
                                    list(analyzer.fight_history.fights))
        except Exception as exc:
            self.diagnostic.emit(f"Review failed for {review_path}: {exc}")
            self.review_loaded.emit(str(review_path), [])
