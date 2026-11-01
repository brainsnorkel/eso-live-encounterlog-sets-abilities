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
from death_recap import recap_window_s
from effect_rules import DEFAULT_RULES, EffectTracker, parse_rules
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


def engine_settings(config: AppConfig) -> tuple:
    """The settings the engine reads when it is built (build_analyzer) or
    attached (run_startup_sequence, engine_worker._attach_monitor), as it
    reads them. The main window takes this before and after Settings
    writes the config and replays the session only when it changed; every
    other setting applies at once, at the next build window, at the next
    retention run or at the next start (issue #187). The values are read
    with the engine's own defaults, so a config never saved (every key
    unset) compares equal to the same settings saved once: a blank path
    and an absent one are both None, absent rules are the default text, an
    absent window is the default. The rules are compared as build_analyzer
    parses them (Rule is a frozen dataclass, so the tuple compares by
    value): a comment, a blank line or the line endings of a hand-edited
    config.json (the editor writes LF) change nothing the engine reads and
    replay nothing."""
    return (config.get("log_path") or None,
            bool(config.get("split.enabled", False)),
            config.get("split.dir") or None,
            tuple(parse_rules(config.get("tracking.rules", DEFAULT_RULES) or "")[0]),
            bool(config.get("companions.accrue_to_owner", False)),
            recap_window_s(config.get("death_recap.window_s")))


def build_analyzer(config: AppConfig,
                   listeners: List[AnalyzerListener]) -> ESOLogAnalyzer:
    analyzer = ESOLogAnalyzer()
    # The user's tracked effects; a line that will not parse is skipped
    # here and reported in Settings
    rules, _errors = parse_rules(config.get("tracking.rules", DEFAULT_RULES) or "")
    analyzer.effect_tracker = EffectTracker(rules)
    # A companion's damage and healing on its owner's row too (companions.py);
    # Settings restarts the engine on save, so the change replays the session
    analyzer.companion_accrual = bool(config.get("companions.accrue_to_owner", False))
    # The seconds of damage and healing a death recap keeps (death_recap,
    # issue #95): read here, so the replay a save makes rebuilds the fights
    # already listed with the new window
    analyzer.death_recap_recorder.window_ms = (
        recap_window_s(config.get("death_recap.window_s")) * 1000)
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
