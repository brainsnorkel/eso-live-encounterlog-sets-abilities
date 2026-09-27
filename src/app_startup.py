"""
Engine-level application startup sequencing (no Qt):

    load config -> resolve log path -> startup archive check -> attach monitor

The GUI drives this from its worker thread; tests drive it directly.
The archive check runs before monitoring so the exclusive-access guard can
never collide with our own tail handle, and monitoring starts on whichever
file remains (the original, or a fresh one if it was archived and deleted).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app_config import AppConfig
from engine_events import AnalyzerListener
from esolog_tail import ESOLogAnalyzer, LogFileMonitor, _find_eso_log_file
from fight_history import FightHistory
from log_archiver import LogArchiver


@dataclass
class StartupResult:
    log_path: Optional[Path]
    analyzer: ESOLogAnalyzer
    monitor: Optional[LogFileMonitor]
    archive_path: Optional[Path]


def resolve_log_path(config: AppConfig) -> Optional[Path]:
    """Configured log path, or auto-detection across known ESO locations."""
    configured = config.get("log_path")
    if configured:
        return Path(configured)
    return _find_eso_log_file()


def build_analyzer(config: AppConfig,
                   listeners: List[AnalyzerListener]) -> ESOLogAnalyzer:
    reports_enabled = bool(config.get("reports.enabled", False))
    reports_dir = config.get("reports.dir")
    analyzer = ESOLogAnalyzer(
        save_reports=reports_enabled,
        reports_dir=Path(reports_dir) if reports_dir else None,
    )
    analyzer.track_buff_timeline = bool(
        config.get("experimental.buff_timeline", False))
    analyzer.fight_history = FightHistory()
    for listener in listeners:
        analyzer.add_listener(listener)
    return analyzer


def run_startup_sequence(config: AppConfig,
                         listeners: List[AnalyzerListener],
                         attach_monitor: bool = True) -> StartupResult:
    log_path = resolve_log_path(config)

    # Startup-only auto-archive, before any monitoring handle exists
    archive_path = None
    if log_path is not None and log_path.exists():
        archiver = LogArchiver(config)
        for listener in listeners:
            archiver.add_listener(listener)
        archive_path = archiver.auto_archive_if_needed(log_path)

    analyzer = build_analyzer(config, listeners)

    monitor = None
    if attach_monitor and log_path is not None and log_path.exists():
        split_enabled = bool(config.get("split.enabled", False))
        split_dir = config.get("split.dir")
        monitor = LogFileMonitor(
            analyzer, log_path,
            read_all_then_tail=False,
            tail_and_split=split_enabled,
            split_dir=Path(split_dir) if split_dir else None,
        )
        monitor.running = True

    return StartupResult(log_path=log_path, analyzer=analyzer,
                         monitor=monitor, archive_path=archive_path)
