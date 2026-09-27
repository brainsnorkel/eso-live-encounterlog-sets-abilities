"""
Log freshness derivation: when was the newest entry written to an encounter log?

Every ESO encounter log line starts with a relative millisecond offset from the
session's BEGIN_LOG event, and each BEGIN_LOG carries a Unix epoch (ms):

    5,BEGIN_LOG,1755729685851,15,"NA Megaserver","en","eso.live.11.1"
    43016,COMBAT_EVENT,DAMAGE,...

latest entry time = most recent BEGIN_LOG epoch + last line's relative offset.

Derivation is exact when a BEGIN_LOG is reachable, and falls back to the file's
mtime (marked "approximate") otherwise. Logs can reach tens of GB, so the
backward BEGIN_LOG search is capped rather than unbounded.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from engine_events import LogStatus

# Read the file tail in slices of this size when searching backwards.
_CHUNK_SIZE = 1024 * 1024
# Give up the exact derivation after scanning this much of the file tail.
DEFAULT_LOOKBACK_BYTES = 64 * 1024 * 1024

_BEGIN_LOG_MARKER = b',BEGIN_LOG,'


def parse_relative_ms(line: str) -> Optional[int]:
    """Extract the leading relative-millisecond offset from a log line."""
    head = line.split(',', 1)[0].strip()
    if head.isdigit():
        return int(head)
    return None


def parse_begin_log_epoch_ms(line: str) -> Optional[int]:
    """Extract the Unix epoch (ms) from a BEGIN_LOG line."""
    parts = line.split(',')
    if len(parts) >= 3 and parts[1] == 'BEGIN_LOG' and parts[2].strip().isdigit():
        return int(parts[2])
    return None


def _last_complete_line(chunk: bytes, at_file_start: bool) -> Optional[str]:
    """Last non-empty complete line in a tail chunk.

    Unless the chunk starts at offset 0, its first line may be a partial
    read and is discarded.
    """
    lines = chunk.split(b'\n')
    if not at_file_start and len(lines) > 1:
        lines = lines[1:]
    for raw in reversed(lines):
        raw = raw.strip()
        if raw:
            try:
                return raw.decode('utf-8', errors='ignore')
            except Exception:
                return None
    return None


def _find_last_begin_log_epoch(f, file_size: int, lookback_bytes: int) -> Optional[int]:
    """Scan backwards (capped) for the most recent BEGIN_LOG epoch (ms)."""
    scanned = 0
    end = file_size
    carry = b''
    while end > 0 and scanned < lookback_bytes:
        step = min(_CHUNK_SIZE, lookback_bytes - scanned)
        start = max(0, end - step)
        f.seek(start)
        chunk = f.read(end - start) + carry
        idx = chunk.rfind(_BEGIN_LOG_MARKER)
        if idx != -1:
            line_start = chunk.rfind(b'\n', 0, idx) + 1
            line_end = chunk.find(b'\n', idx)
            if line_end == -1:
                line_end = len(chunk)
            line = chunk[line_start:line_end].decode('utf-8', errors='ignore')
            epoch = parse_begin_log_epoch_ms(line)
            if epoch is not None:
                return epoch
        # Keep a marker-sized tail of this chunk so a BEGIN_LOG split across
        # the chunk boundary is still found on the next iteration.
        carry = chunk[:len(_BEGIN_LOG_MARKER) + 32]
        scanned += end - start
        end = start
    return None


def derive_session_epoch_ms(log_path: Path,
                            lookback_bytes: int = DEFAULT_LOOKBACK_BYTES) -> Optional[int]:
    """Most recent BEGIN_LOG epoch (ms) reachable within the lookback cap."""
    log_path = Path(log_path)
    try:
        size = log_path.stat().st_size
        if size == 0:
            return None
        with open(log_path, 'rb') as f:
            return _find_last_begin_log_epoch(f, size, lookback_bytes)
    except OSError:
        return None


def derive_log_freshness(log_path: Path,
                         lookback_bytes: int = DEFAULT_LOOKBACK_BYTES) -> LogStatus:
    """Derive the latest-entry timestamp of an encounter log from its content.

    Returns a LogStatus with source "exact" (content-derived), "approximate"
    (file mtime; no BEGIN_LOG reachable within lookback_bytes or the tail was
    unparseable), or "none" (file missing/unreadable).
    """
    log_path = Path(log_path)
    try:
        stat = log_path.stat()
    except OSError:
        return LogStatus(log_path=log_path, source='none')

    size = stat.st_size
    mtime = datetime.fromtimestamp(stat.st_mtime)
    approximate = LogStatus(log_path=log_path, size_bytes=size,
                            latest_entry_time=mtime, source='approximate')
    if size == 0:
        return approximate

    try:
        with open(log_path, 'rb') as f:
            # Last complete line from the tail chunk
            tail_start = max(0, size - _CHUNK_SIZE)
            f.seek(tail_start)
            chunk = f.read(size - tail_start)
            last_line = _last_complete_line(chunk, at_file_start=(tail_start == 0))
            if last_line is None:
                return approximate
            offset_ms = parse_relative_ms(last_line)
            if offset_ms is None:
                return approximate

            epoch_ms = parse_begin_log_epoch_ms(last_line)
            if epoch_ms is None:
                epoch_ms = _find_last_begin_log_epoch(f, size, lookback_bytes)
            if epoch_ms is None:
                return approximate
    except OSError:
        return approximate

    latest = datetime.fromtimestamp(epoch_ms / 1000.0 + offset_ms / 1000.0)
    return LogStatus(log_path=log_path, size_bytes=size,
                     latest_entry_time=latest, source='exact')


def status_from_tracking(log_path: Path, size_bytes: int,
                         begin_log_epoch_s: Optional[int],
                         last_offset_ms: Optional[int]) -> LogStatus:
    """Build a LogStatus from values already tracked while tailing.

    begin_log_epoch_s is the analyzer's log_start_unix_timestamp (seconds).
    """
    if begin_log_epoch_s is None or last_offset_ms is None:
        return derive_log_freshness(log_path)
    latest = datetime.fromtimestamp(begin_log_epoch_s + last_offset_ms / 1000.0)
    return LogStatus(log_path=Path(log_path), size_bytes=size_bytes,
                     latest_entry_time=latest, source='exact')
