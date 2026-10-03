"""
Engine event interface: the contract between the analysis engine and frontends.

The engine (ESOLogAnalyzer / LogFileMonitor / LogSplitter / LogArchiver) emits
typed events through AnalyzerListener callbacks. Frontends (the GUI) and tests
register listeners; engine modules never import GUI toolkits.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class LogStatus:
    """Snapshot of the monitored log file's freshness.

    latest_entry_time is derived from log content (most recent BEGIN_LOG epoch
    plus the latest line's relative millisecond offset) when source == "exact";
    from the file's mtime when source == "approximate"; and is None when
    source == "none" (no log file).
    """
    log_path: Optional[Path] = None
    size_bytes: int = 0
    latest_entry_time: Optional[datetime] = None
    source: str = "none"  # "exact" | "approximate" | "none"


@dataclass
class ArchiveEvent:
    """Progress/outcome of a log archive operation.

    kind:
        "skipped"   - archive not attempted (reason set, e.g. file in use)
        "started"   - archive began (total_bytes set)
        "progress"  - chunk written (done_bytes/total_bytes set)
        "completed" - archive verified (archive_path set, original_deleted set)
        "failed"    - archive failed and was cleaned up (reason set)
    """
    kind: str
    log_path: Optional[Path] = None
    archive_path: Optional[Path] = None
    done_bytes: int = 0
    total_bytes: int = 0
    reason: str = ""
    original_deleted: bool = False


class AnalyzerListener:
    """Base listener: subclass and override the callbacks you need.

    All callbacks are invoked synchronously on the engine's thread; frontends
    are responsible for marshalling to their UI thread.
    """

    def on_fight_completed(self, entry) -> None:  # entry: FightHistoryEntry
        """A combat encounter finished and produced a fight summary."""

    def on_fight_updated(self, entry) -> None:  # entry: FightHistoryEntry
        """An already-completed fight's summary changed in place (a player
        death that the log wrote just after the fight ended)."""

    def on_zone_changed(self, zone_name: str, difficulty: str) -> None:
        """The player entered a new zone."""

    def on_log_status(self, status: LogStatus) -> None:
        """The monitored log's freshness/size changed."""

    def on_archive_event(self, event: ArchiveEvent) -> None:
        """An archive operation was skipped, progressed, or finished."""

    def on_diagnostic(self, message: str) -> None:
        """Informational/diagnostic message (previously terminal output)."""


class ListenerMixin:
    """Mixin providing listener registration and safe fan-out notification."""

    def __init__(self):
        self.listeners: List[AnalyzerListener] = []

    def add_listener(self, listener: AnalyzerListener) -> None:
        if listener not in self.listeners:
            self.listeners.append(listener)

    def remove_listener(self, listener: AnalyzerListener) -> None:
        if listener in self.listeners:
            self.listeners.remove(listener)

    def _notify(self, callback_name: str, *args) -> None:
        for listener in list(self.listeners):
            try:
                getattr(listener, callback_name)(*args)
            except Exception:
                # A misbehaving frontend must never break analysis.
                pass


class RecordingListener(AnalyzerListener):
    """Test helper: records every callback invocation in order."""

    def __init__(self):
        self.events = []

    def on_fight_completed(self, entry) -> None:
        self.events.append(("fight_completed", entry))

    def on_fight_updated(self, entry) -> None:
        self.events.append(("fight_updated", entry))

    def on_zone_changed(self, zone_name: str, difficulty: str) -> None:
        self.events.append(("zone_changed", zone_name, difficulty))

    def on_log_status(self, status: LogStatus) -> None:
        self.events.append(("log_status", status))

    def on_archive_event(self, event: ArchiveEvent) -> None:
        self.events.append(("archive_event", event))

    def on_diagnostic(self, message: str) -> None:
        self.events.append(("diagnostic", message))

    def of_kind(self, kind: str):
        return [e for e in self.events if e[0] == kind]
