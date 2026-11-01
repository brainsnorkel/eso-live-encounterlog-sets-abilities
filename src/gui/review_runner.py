"""
A review on a thread of its own (issue #107). Until 0.21 a review ran on
the engine thread, whose poll timer then waited for it: a month-sized log
took 8.6 minutes with no live fights shown. Now the engine polls on while a
review replays through an analyzer of its own.

The thread holds no Qt object. It reports through *notify*, which the
window turns into a signal on an object living on the UI thread (as split
retention does), so nothing Qt is created or freed here; the analyzer and
its fights are plain Python. The settings are a snapshot taken when the
review starts, since Settings may change them meanwhile.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import fight_index
import review_load
from app_startup import build_analyzer
from version import __version__


@dataclass
class ReviewEvent:
    """kind: 'progress' (label, done, total), 'outlined' (outline),
    'loaded' (shown, fights), 'indexed' (label: the backfill's summary, a
    fight_index.backfill result as done, the fights added, and total, the
    logs still to read), 'cancelled', 'failed' (reason)."""
    kind: str
    path: str
    member: str = ""
    label: str = ""
    done: int = 0
    total: int = 0
    outline: review_load.Outline | None = None
    shown: str = ""
    fights: list | None = None
    reason: str = ""


class ReviewRunner:
    """One review at a time: an outline pass, or a replay."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def cancel(self) -> None:
        self._cancel.set()

    def wait(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def outline(self, path: str, member: str,
                notify: Callable[[ReviewEvent], None]) -> bool:
        def work(cancel):
            result = review_load.outline(Path(path), member or None, cancel)
            notify(ReviewEvent("outlined", path, member, outline=result))
        return self._start(path, member, work, notify)

    def replay(self, config, path: str, member: str, from_begin_log: int,
               notify: Callable[[ReviewEvent], None]) -> bool:
        snapshot = config.snapshot()

        def progress(label, done, total):
            notify(ReviewEvent("progress", path, member, label=label, done=done, total=total))

        def work(cancel):
            analyzer = build_analyzer(snapshot, [])
            shown, fights = review_load.replay_log(
                analyzer, Path(path), member or None, from_begin_log, progress, cancel)
            notify(ReviewEvent("loaded", path, member, shown=shown, fights=fights))
        return self._start(path, member, work, notify)

    def backfill(self, config, folder: str, index,
                 notify: Callable[[ReviewEvent], None]) -> bool:
        """Read the split folder's logs into the fight history's index
        (fight_index.backfill) on this thread, each through an analyzer
        built from a snapshot of the settings, as a review is."""
        snapshot = config.snapshot()

        def progress(label, done, total):
            notify(ReviewEvent("progress", folder, label=label, done=done, total=total))

        def work(cancel):
            result = fight_index.backfill(folder, index, lambda: build_analyzer(snapshot, []),
                                          __version__, progress, cancel)
            notify(ReviewEvent(
                "indexed", folder,
                label=(f"Fight history: {result['fights']} fights from {result['logs']} "
                       f"split log{'s' if result['logs'] != 1 else ''}"
                       + (f", {result['skipped']} copies skipped" if result["skipped"] else "")
                       + (f", {result['failed']} that would not read (tried again next "
                          f"build)" if result["failed"] else "")),
                done=result["fights"], total=result["left"]))
        return self._start(folder, "", work, notify)

    def _start(self, path, member, work, notify) -> bool:
        if self.running:
            return False
        self._cancel = threading.Event()
        cancel = self._cancel

        def run():
            try:
                work(cancel)
            except review_load.ReviewCancelled:
                notify(ReviewEvent("cancelled", path, member))
            except Exception as exc:  # a review must never take the app down
                notify(ReviewEvent("failed", path, member, reason=f"{type(exc).__name__}: {exc}"))

        self._thread = threading.Thread(target=run, name="review", daemon=True)
        self._thread.start()
        return True
