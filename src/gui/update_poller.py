"""
The update poller: when the app asks GitHub for a newer release, and on
which thread.

Design: the check runs 3 s after the window is built and then every
``update.check_interval_min`` minutes (default 15), for as long as the
Settings box is ticked, so an app that runs through a raid night learns of
a release published after it started. Issue #56 (2026-10-26) asked for
this in place of the one check at startup and the pop-up it opened.

Each check is a conditional request: the ETag GitHub returned with the last
full reply goes back as If-None-Match, and an unchanged release is answered
304 with no body, which GitHub does not count against its limit of 60
unsigned requests an hour per address (update_check has the figures). A
rate-limit reply names a reset time, and no check runs until then.

The network call and the installer download run on a daemon Python thread,
not on the engine thread as they did until 0.14.2: there a wedged network
stalled fight updates for the 10-second timeout, and a download for its
whole length; once per run that was bearable, every 15 minutes it is not.
The thread calls update_check functions only, creates no Qt object and
holds no widget, and hands its result back through a signal carrying plain
data, which Qt queues to this object's thread, the UI thread (see
engine_worker.py and the 0.6.x settings crash for why a Qt object must
never be freed off the UI thread). One check or download runs at a time; a
tick during one is skipped. A result that arrives after stop() is dropped
(the generation counter), so a closing window never hears from a late
thread.

start() clears the ETag so its first request is a full one: Settings saved
with the check on also clears a skipped version, and a 304 would otherwise
hide the release that was skipped and is wanted again.
"""

import tempfile
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

import update_check

FIRST_CHECK_MS = 3000
DEFAULT_INTERVAL_MIN = 15
MAX_WAIT_S = 3600


class UpdatePoller(QObject):
    """Checks GitHub on a schedule and downloads the installer on request;
    lives on the UI thread, works on daemon threads."""

    update_available = Signal(object)   # update_check.UpdateInfo
    update_gone = Signal()              # the offer no longer stands
    download_progress = Signal(str, int, int)  # label, done, total (as parse_progress)
    update_ready = Signal(str)          # downloaded installer path
    update_failed = Signal(str)         # reason, for the status bar
    checked = Signal(str)               # the outcome of each check, for diagnostics

    # Thread -> UI thread hand-offs: queued, the payload plain data
    _checked = Signal(object)
    _progressed = Signal(object)
    _downloaded = Signal(object)

    def __init__(self, config, current_version: str, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_version = current_version
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._first = QTimer(self)
        self._first.setSingleShot(True)
        self._first.timeout.connect(self._tick)
        self._etag = None
        self._offered = None      # the version on offer, or None
        self._busy = False        # a check or download thread is running
        self._wait_until = 0.0    # no check before this time (rate limit)
        self._generation = 0      # bumped by start() and stop(); late results are dropped
        self._running = False
        self.last_outcome = ""
        self._checked.connect(self._on_checked, Qt.QueuedConnection)
        self._progressed.connect(self._on_progressed, Qt.QueuedConnection)
        self._downloaded.connect(self._on_downloaded, Qt.QueuedConnection)

    # ---- the schedule ----

    def interval_ms(self) -> int:
        try:
            minutes = int(self.config.get("update.check_interval_min",
                                          DEFAULT_INTERVAL_MIN))
        except (TypeError, ValueError):
            minutes = DEFAULT_INTERVAL_MIN
        return max(1, minutes) * 60 * 1000

    def start(self) -> None:
        """Begin, or begin again: a full check shortly, then one every interval."""
        self._generation += 1
        self._running = True
        self._busy = False
        self._etag = None
        self._wait_until = 0.0
        self._timer.start(self.interval_ms())
        self._first.start(FIRST_CHECK_MS)

    def stop(self) -> None:
        """End the schedule; a thread still running is ignored when it reports."""
        self._running = False
        self._generation += 1
        self._busy = False
        self._first.stop()
        self._timer.stop()
        self._offered = None

    def is_running(self) -> bool:
        return self._running

    def check_now(self) -> None:
        """A full check at once (no ETag), regardless of a rate-limit wait."""
        self._etag = None
        self._wait_until = 0.0
        self._tick()

    @Slot()
    def _tick(self):
        if not self._running or self._busy:
            return
        if time.time() < self._wait_until:
            return
        self._busy = True
        args = (self._generation, self.current_version,
                self.config.get("update.skip_version"), self._etag)
        threading.Thread(target=self._run_check, args=args,
                         name="esolog-update-check", daemon=True).start()

    def _run_check(self, generation, version, skip, etag):
        # The worker thread: update_check only, plain data out
        try:
            result = update_check.check_for_update(version, skip, etag)
        except Exception as exc:  # a thread must never die noisily
            result = update_check.CheckResult(error=str(exc))
        try:
            self._checked.emit((generation, result))
        except RuntimeError:
            pass  # the poller is gone

    @Slot(object)
    def _on_checked(self, payload):
        generation, result = payload
        if generation != self._generation:
            return
        self._busy = False
        if result.retry_at:
            self._wait_until = min(result.retry_at, time.time() + MAX_WAIT_S)
        if result.error:
            self._report(f"update check failed: {result.error}")
            return
        if result.not_modified:
            self._report("update check: not modified")
            return
        if result.etag:
            self._etag = result.etag
        info = result.info
        if info is not None:
            self._offered = info.version
            self._report(f"update check: {info.version} available")
            self.update_available.emit(info)
            return
        self._report("update check: up to date")
        if self._offered is not None:
            self._offered = None
            self.update_gone.emit()

    def _report(self, outcome: str) -> None:
        self.last_outcome = outcome
        self.checked.emit(outcome)

    # ---- the download ----

    def download(self, url: str, name: str) -> bool:
        """Fetch the installer to the temp folder on a thread; False while
        a check or download is still running."""
        if self._busy:
            return False
        self._busy = True
        dest = Path(tempfile.gettempdir()) / name
        label = f"Downloading {name}"
        self.download_progress.emit(label, 0, 0)
        threading.Thread(target=self._run_download,
                         args=(self._generation, url, dest, label),
                         name="esolog-update-download", daemon=True).start()
        return True

    def _run_download(self, generation, url, dest, label):
        def progress(done, total):
            try:
                self._progressed.emit((generation, label, done, total or 0))
            except RuntimeError:
                pass

        try:
            ok = update_check.download_file(url, dest, progress=progress)
        except Exception:
            ok = False
        try:
            self._downloaded.emit((generation, ok, str(dest), label))
        except RuntimeError:
            pass

    @Slot(object)
    def _on_progressed(self, payload):
        generation, label, done, total = payload
        if generation == self._generation:
            self.download_progress.emit(label, done, total)

    @Slot(object)
    def _on_downloaded(self, payload):
        generation, ok, path, label = payload
        if generation != self._generation:
            return
        self._busy = False
        self.download_progress.emit(label, 1, 1)  # hides the bar
        if ok:
            self.update_ready.emit(path)
        else:
            self.update_failed.emit("download failed; try again later or "
                                    "download from the releases page")
