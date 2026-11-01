"""
Engine worker: runs the analysis engine on a QThread and bridges
AnalyzerListener callbacks to Qt signals (queued to the UI thread).

Engine modules never import Qt; this adapter is the only crossing point.

Design: the worker is a Python-created QObject, so it is freed on the UI
thread and never by Python's garbage collector, which frees whatever is
garbage on whichever thread happens to be allocating. As the worker's thread
finishes, QThread.finished calls leave_thread on that thread (a direct
connection): the timers stop and the worker moves itself to the UI thread,
since only the thread an object lives in may move it. The window then
deletes it there (MainWindow._discard_worker). The listener holds the worker
weakly, so a worker nobody holds is freed at once.

Until issue #18 the window tried to pull the worker over from the UI thread
after the thread had ended. Qt refuses that ("Cannot move to target thread",
printed at every close), so the deletion went to a thread that would never
run it. The listener also held the worker in a reference cycle, so only the
garbage collector could free it. In the test suite, where every GUI test
leaves windows and workers behind, a collection was seen running on an
engine thread; one that found GUI objects there would free them off the UI
thread, which is how Settings crashed in 0.6.x.
"""

import weakref
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
    """Forwards engine callbacks to the worker's Qt signals. It holds the
    worker weakly: the worker holds it, and a cycle would leave the worker
    to the garbage collector (see the module's design note)."""

    def __init__(self, worker: "EngineWorker"):
        self._worker = weakref.ref(worker)

    def _emit(self, signal: str, *args):
        worker = self._worker()
        if worker is not None:
            getattr(worker, signal).emit(*args)

    def on_fight_completed(self, entry):
        self._emit("fight_completed", entry)

    def on_fight_updated(self, entry):
        self._emit("fight_updated", entry)

    def on_zone_changed(self, zone_name, difficulty):
        self._emit("zone_changed", zone_name, difficulty)

    def on_log_status(self, status):
        self._emit("log_status", status)

    def on_archive_event(self, event):
        self._emit("archive_event", event)

    def on_diagnostic(self, message):
        self._emit("diagnostic", message)

    def on_parse_progress(self, label, done, total):
        self._emit("parse_progress", label, done, total)

    def on_warning(self, source, message):
        self._emit("warning", source, message)

    def on_trial_result(self, result):
        self._emit("trial_result", result)


class EngineWorker(QObject):
    """Owns the engine objects; lives on a dedicated QThread.

    All slots run on the worker thread, so polling, manual archiving and
    monitoring restarts are naturally serialized. A review has a thread of
    its own (gui/review_runner.py), so the poll never waits for one.
    """

    fight_completed = Signal(object)   # FightHistoryEntry
    fight_updated = Signal(object)     # FightHistoryEntry already delivered
    zone_changed = Signal(str, str)
    log_status = Signal(object)        # LogStatus
    archive_event = Signal(object)     # ArchiveEvent
    diagnostic = Signal(str)
    # A lasting problem by source ('split', 'poll'): message, or None once
    # it has cleared (issue #111)
    warning = Signal(str, object)
    trial_result = Signal(object)      # END_TRIAL's result dict, as the line is read (issue #167)
    waiting_for_log = Signal(str)      # expected path
    monitoring_started = Signal(str)   # log path
    # A requested restart has begun: fights sent before this came from the
    # analyzer being replaced (queued signals arrive in emission order)
    monitoring_restarting = Signal()
    # Catch-up progress: (label, done_bytes, total_bytes).
    # total == 0 -> indeterminate busy; done >= total > 0 -> finished (hide).
    parse_progress = Signal(str, int, int)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.listener = SignalListener(self)
        self.analyzer = None
        self.monitor = None
        self._log_path = None
        self._poll_timer = None
        self._wait_timer = None
        self._poll_failures = 0  # polls in a row that raised

    # ---- lifecycle ----

    @Slot()
    def stop(self):
        """Stop timers on the worker thread ahead of thread shutdown."""
        if self._poll_timer is not None:
            self._poll_timer.stop()
        if self._wait_timer is not None:
            self._wait_timer.stop()

    def leave_thread(self, home):
        """Hand the worker to the *home* thread as its own thread finishes.
        Runs on the worker's thread, from QThread.finished: only the thread
        an object lives in may move it. The timers stop first, so none starts
        again on the UI thread."""
        try:
            self.stop()
            self.moveToThread(home)
        except RuntimeError:
            pass  # already deleted

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
        # The update check is the window's (gui/update_poller.py): it ran
        # here until 0.14.2, where a wedged network stalled the log polling

    @Slot()
    def restart_monitoring(self):
        """Settings changed: rebuild analyzer/monitor. No archive check
        (auto-archive is startup-only by spec)."""
        # Slots on this thread run one after another, so this is emitted
        # only once any replay the old analyzer was in the middle of is done
        self.monitoring_restarting.emit()
        try:
            self._teardown()
            self._log_path = resolve_log_path(self.config)
            self.analyzer = build_analyzer(self.config, [self.listener])
            if self._log_path is not None and self._log_path.exists():
                self._attach_monitor()
            else:
                self._start_waiting()
        except Exception as exc:
            # A failed restart must degrade to waiting, never escape into Qt
            self.diagnostic.emit(f"Monitoring restart failed: {exc}")
            try:
                self._start_waiting()
            except Exception:
                pass

    def _teardown(self):
        if self._poll_timer:
            self._poll_timer.stop()
        if self._wait_timer:
            self._wait_timer.stop()
        # Close the session's split and give the folder's lock up, so the
        # monitor built next (a Settings save) continues the split rather
        # than finding the folder held by this same process
        monitor = self.monitor
        if monitor is not None and getattr(monitor, "log_splitter", None) is not None:
            try:
                monitor.log_splitter.cleanup()
            except Exception:
                pass
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

    # Backlogs above this show a busy indicator while catching up
    CATCHUP_BUSY_BYTES = 8 * 1024 * 1024
    _CATCHUP_LABEL = "Catching up on new log data…"
    # Polls in a row that raise before the window shows a lasting warning
    POLL_FAILURES_WARN = 3

    def _poll(self):
        if self.monitor is None:
            return
        busy = False
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
            if size - self.monitor.last_position > self.CATCHUP_BUSY_BYTES:
                busy = True
                self.parse_progress.emit(self._CATCHUP_LABEL, 0, 0)
            self.monitor._process_new_lines()
            if self._poll_failures >= self.POLL_FAILURES_WARN:
                self.warning.emit("poll", None)
            self._poll_failures = 0
        except Exception as exc:
            self.diagnostic.emit(f"poll error: {exc}")
            # One failure is a status line; failing poll after poll (out of
            # memory, a line the engine cannot take) is a lasting warning
            self._poll_failures += 1
            if self._poll_failures == self.POLL_FAILURES_WARN:
                self.warning.emit("poll", f"Reading the log keeps failing: {exc}")
        finally:
            if busy:
                self.parse_progress.emit(self._CATCHUP_LABEL, 1, 1)  # hide

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
                elif polling:
                    self._poll_timer.start()
