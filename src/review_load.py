"""
Replaying a log for review (issue #107): the engine side of "Open log for
review…", with no Qt in it, so it runs on a thread of its own while live
monitoring keeps its poll.

A large log is first outlined: one pass over the line heads that finds each
session's start (``BEGIN_LOG``) and counts its fights (``BEGIN_COMBAT``),
so the window can offer the whole log or only its most recent sessions.
The cut is always at a session start. Starting in the middle of a session
was measured and rejected: the roster lines alone do not carry what the
engine learns from the rest of the session (who owns which companion and
pet), and on a Dreadsail Reef split every one of the last 18 fights came
out different. A replay from a ``BEGIN_LOG`` matched a replay of the whole
file in 75 of 75 fights (once champion points followed the log).

Lines before the first session read are skipped unparsed, so a cut log
costs a pass over its head plus the engine's time for the rest. The engine
runs at about 10 MB/s on the maintainer's machine, which the time estimate
uses.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from log_open import open_log_text

# A log above this size is outlined and the reader asked first
LARGE_REVIEW_BYTES = 1 << 30
# The recent sessions offered hold at least this many fights
RECENT_FIGHTS = 50
# The engine's replay speed for the time estimate
REVIEW_BYTES_PER_SECOND = 10 << 20
# Progress is reported at most this often (and at least every MB)
PROGRESS_STEPS = 200


class ReviewCancelled(Exception):
    """The reader cancelled the review."""


@dataclass
class Outline:
    """Where a log's sessions start (in characters read, which for these
    logs is about bytes) and how many fights each holds."""
    total: int
    starts: list[int] = field(default_factory=list)
    fights: list[int] = field(default_factory=list)
    # The log opens mid-session: its first session has no BEGIN_LOG line
    headless: bool = False

    def begin_log(self, session: int) -> int:
        """The BEGIN_LOG line (counted from 0) that starts *session*, or -1
        for the whole log, for replay_log."""
        if session <= 0:
            return -1
        return session - 1 if self.headless else session

    def recent(self, fights: int | None = None) -> int:
        """The index of the first session of the fewest most recent
        sessions that hold at least *fights* (RECENT_FIGHTS) fights (0: the
        whole log)."""
        if fights is None:
            fights = RECENT_FIGHTS
        held = 0
        for index in range(len(self.starts) - 1, -1, -1):
            held += self.fights[index]
            if held >= fights:
                return index
        return 0

    def size_from(self, session: int) -> int:
        """Characters from the start of *session* to the end."""
        if not self.starts or session <= 0:
            return self.total
        return self.total - self.starts[session]

    def fights_from(self, session: int) -> int:
        return sum(self.fights[max(session, 0):])


def estimate_seconds(size: int) -> float:
    return size / REVIEW_BYTES_PER_SECOND


def _check(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise ReviewCancelled()


def outline(path: Path, member: str | None = None,
            cancel: threading.Event | None = None) -> Outline:
    """One pass over the line heads: session starts and fights per session."""
    with open_log_text(path, member) as (f, total, _shown):
        result = Outline(total=total)
        done = 0
        for n, line in enumerate(f):
            head = line[:40]
            if ',BEGIN_LOG,' in head:
                result.starts.append(done)
                result.fights.append(0)
            elif ',BEGIN_COMBAT' in head:
                if not result.fights:  # a log that opens mid-session
                    result.starts.append(0)
                    result.fights.append(0)
                    result.headless = True
                result.fights[-1] += 1
            done += len(line)
            if n % 100_000 == 0:
                _check(cancel)
        result.total = max(total, done)
        return result


def replay_log(analyzer, path: Path, member: str | None = None,
               from_begin_log: int = -1,
               progress: Callable[[str, int, int], None] | None = None,
               cancel: threading.Event | None = None) -> tuple[str, list]:
    """Run the log through *analyzer* from its *from_begin_log*-th BEGIN_LOG
    line, counted from 0 (-1: the whole log; Outline.begin_log gives it for
    a session); (name to show, completed fights). Raises ReviewCancelled
    when *cancel* is set."""
    skip_until = from_begin_log + 1  # BEGIN_LOG lines to have met
    met = 0
    analyzer.current_log_file = str(path)
    with open_log_text(path, member) as (f, total, shown):
        label = f"Parsing {Path(shown).name if member is None else shown}"
        step = max(1024 * 1024, total // PROGRESS_STEPS)
        done = last_emit = 0
        if progress:
            progress(label, 0, total)
        for line in f:
            # Char length approximates byte length for these logs;
            # progress is clamped to total either way
            done += len(line)
            if done - last_emit >= step:
                last_emit = done
                _check(cancel)
                if progress:
                    progress(label, min(done, total), total)
            if met < skip_until:
                if ',BEGIN_LOG,' not in line[:40]:
                    continue
                met += 1
                if met < skip_until:
                    continue
            line = line.strip()
            if not line:
                continue
            entry = analyzer.log_parser.parse_line(line)
            if entry is not None:
                analyzer.process_log_entry(entry)
    return shown, list(analyzer.fight_history.fights)
