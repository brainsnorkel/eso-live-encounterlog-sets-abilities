"""
Fight history across sessions (issue #170, no Qt): every boss fight's
figures in a JSON Lines file beside the config, read back so a pull is set
against the group's own earlier kills of the boss, and a player against
their own.

Design: the fight history (fight_history.FightHistory) lives for a
session, and the split logs the app writes are never read again, so a kill
had nothing to be read against. The index keeps one line per boss fight
(a fight with a pull, pull_outcome), kill or not, written by the GUI when
the engine sends the fight and again when it sends it updated. Nothing is
parsed for it: the line is the entry's own figures. Builds are not kept.

- **Where**: ``fights.jsonl`` beside the config (the AppConfig folder,
  ``%LOCALAPPDATA%\\esolog-tail`` on Windows, ``~/.config/esolog-tail`` on
  Linux), never in the split folder, so split retention never deletes it.
  Plain JSON Lines, one object per line, handles in clear as in the logs.
- **Key**: the fight's start in Unix seconds (pull['start_s'], the
  session's BEGIN_LOG time plus the fight's own offset), so the live
  fight, its replay at the next start and a backfill of its split file all
  write the same key. A line is only appended when it differs from the one
  already held under its key, and readers take the last line per key: an
  update appends, a restart's replay of the session appends nothing.
- **A bad line**: a line that does not parse (a crash halfway through a
  write, a hand edit) is skipped and counted; the rest of the file reads.
  A file another program holds open (a sync client) keeps its lines
  queued and retries at the next write, never raising.
- **Backfill**: the split folder's logs (and the logs in its zips), newest
  first, through the engine itself (review_load.replay_log), on the
  review thread with its cancel and progress, so every figure is the
  app's own. Byte-identical copies, zipped or not, are skipped by a hash
  of their first 256 KB and their size. A session's re-splits that the
  old splitter cut short (issue #85) are read too, shortest first, so
  where two hold one fight the longest log's line is the one kept: in the
  maintainer's folder 20 such logs in 10 sessions. The live log's newest
  session is left out: the splitter may still be writing its split (the
  temp name lasts only until the zone is known), and the window indexes
  that session itself as it replays and follows it. Each log done is noted in
  ``fights-backfill.json`` beside the index, by its own name (which a zip
  of it keeps) and with its copy mark, once its lines are written, so a
  cancelled backfill carries on where it stopped. The
  maintainer's 378 unique split logs (35 GB) replay at the engine's 10
  MB/s on one thread.

Comparisons (the issue's measurements: 179 bosses killed, 23 in 10 or
more sessions; Lord Falgravn's kills 265k to 953k; a standing Sunspire
group shares 10 handles between sessions while Kyne's Aegis and Lucent
Citadel pugs share one, and 8 or more named players in three fights in
four):

- **The pull** in the fight pane: the group's boss dps (all damage in a
  fight with no boss figure) against the earlier kills of the same boss
  at the same difficulty in the same zone, always, and against a narrower
  set when one holds enough: kills with ROSTER_MIN or more of tonight's
  named players on the same game version when SET_MIN or more remain, else
  those kills on any version when SET_MIN or more remain. The line names
  the set it used. Only kills before this fight count, so a fight read
  later is set against its own past.
- **A player** in their name's hover: their boss dps in their last
  PLAYER_LAST kills of the boss in the index, with you (the logging
  player) or as you.
- **A boss's pulls in a row** (gui.fight_list's run row): the best earlier
  kill of the boss with ROSTER_MIN or more of the run's named players.

Anonymous players (no handle in the log) are kept without one and never
matched. The game version is the session's own (BEGIN_LOG), so a patch
narrows the set by itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import zipfile
import zlib
from collections.abc import Callable
from pathlib import Path
from statistics import median

INDEX_NAME = "fights.jsonl"
BACKFILL_NAME = "fights-backfill.json"
FORMAT = 1
# Named players shared with tonight's fight for "this roster"
ROSTER_MIN = 8
# Kills a narrower set needs before it is said
SET_MIN = 3
# Kills in a player's hover
PLAYER_LAST = 3
# Bytes hashed, with the size, to tell a byte-identical copy of a split log
HEAD_BYTES = 262144
# Fields that do not make a line different: the app version (the first
# start after an update replays the session with a new one)
_NOT_COMPARED = frozenset({"app"})

_COUNT_WORDS = {1: "kill", 2: "two kills", 3: "three kills"}


def index_path(config_path) -> Path:
    """The index beside the config file."""
    return Path(config_path).parent / INDEX_NAME


def line_key(start_s) -> str:
    """A fight's key: its start in Unix seconds, to the millisecond."""
    return f"{float(start_s):.3f}"


def short_version(version) -> str:
    """'12.1' from 'eso.live.12.1'; the text itself when it is not one."""
    return str(version or "").removeprefix("eso.live.")


def fmt_dps(value) -> str:
    """'441.2k', '1.10M', '950': the fight pane's own dps format (that of
    gui.fight_render's _fmt_dps), so the history line and the header
    beside it read alike."""
    value = float(value or 0)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return f"{value:.0f}"


# ------------------------------------------------------------ the line --

def fight_line(entry, app_version: str = "") -> dict | None:
    """The index line for a fight entry; None for a fight without a pull
    or without the log's start time (no key)."""
    pull = getattr(entry, "pull", None)
    if not pull or pull.get("start_s") is None:
        return None
    time_dead = getattr(entry, "time_dead", None) or {}
    rows = []
    for p in getattr(entry, "players", None) or []:
        if p.get("companion"):
            continue
        name = str(p.get("name") or "")
        rows.append({
            "handle": name if name.startswith("@") else "",
            "role": str(p.get("role") or ""),
            "class": str(p.get("class_abbr") or ""),
            "boss_dps": round(float(p.get("boss_dps") or 0)),
            "dps": round(float(p.get("dps") or 0)),
            "dead_ms": int(time_dead.get(str(p.get("unit_id", "")), 0) or 0),
        })
    handles, local = set(), ""
    for p in getattr(entry, "player_names", None) or []:
        name = str(p.get("name") or "")
        if name.startswith("@"):
            handles.add(name)
            if p.get("is_local"):
                local = name
    health = pull.get("health_left")
    return {
        "v": FORMAT,
        "key": line_key(pull["start_s"]),
        "start_s": round(float(pull["start_s"]), 3),
        "end_s": round(float(pull["end_s"]), 3) if pull.get("end_s") is not None else None,
        "app": str(app_version or ""),
        "game": str(getattr(entry, "game_version", "") or ""),
        "zone_id": str(getattr(entry, "zone_id", "") or ""),
        "zone": str(getattr(entry, "zone_name", "") or ""),
        "difficulty": str(getattr(entry, "difficulty", "") or ""),
        "boss": str(pull.get("boss") or ""),
        "bosses": list(pull.get("bosses") or []),
        "outcome": str(pull.get("outcome") or ""),
        "health_left": round(float(health), 2) if health is not None else None,
        "duration_s": round(float(getattr(entry, "duration_s", 0) or 0), 1),
        "dps_time_s": round(float(getattr(entry, "dps_time_s", 0) or 0), 1),
        "group_dps": round(float(getattr(entry, "group_dps", 0) or 0)),
        "group_boss_dps": round(float(getattr(entry, "group_boss_dps", 0) or 0)),
        "deaths": int(getattr(entry, "deaths", 0) or 0),
        "players": int(pull.get("players") or 0),
        # A pull the game cut in two (pull_outcome): the later fight's
        # figures cover only its tail, so it is never compared
        "continues": bool(pull.get("continues")),
        "cut": bool(pull.get("cut")),
        "handles": sorted(handles),
        "local": local,
        "rows": rows,
    }


def _metric(line: dict) -> float:
    """What a fight is compared by: the group's boss dps, all damage in a
    fight without a boss figure."""
    return float(line.get("group_boss_dps") or line.get("group_dps") or 0)


# ----------------------------------------------------------- the index --

class FightIndex:
    """The index file and the lines read from it: key -> the last line
    under that key. Every method takes the lock: the backfill adds from
    the review thread while the window reads and adds on its own."""

    def __init__(self, path):
        self.path = Path(path)
        self.lines: dict[str, dict] = {}
        self.skipped = 0  # lines that did not parse
        self._pending: list[str] = []
        self._by_boss: dict[tuple, list[str]] = {}
        self._done: tuple[set[str], set[str]] | None = None
        self._lock = threading.RLock()

    @property
    def backfill_path(self) -> Path:
        return self.path.with_name(BACKFILL_NAME)

    def load(self) -> int:
        """Read the file; the number of fights held. A missing file is an
        empty index, a line that does not parse is skipped."""
        with self._lock:
            self.lines.clear()
            self._by_boss.clear()
            self.skipped = 0
            try:
                with open(self.path, encoding="utf-8") as fh:
                    for raw in fh:
                        raw = raw.strip()
                        if not raw:
                            continue
                        try:
                            line = json.loads(raw)
                        except ValueError:
                            self.skipped += 1
                            continue
                        if isinstance(line, dict) and line.get("key"):
                            self._hold(line)
                        else:
                            self.skipped += 1
            except OSError:
                pass
            return len(self.lines)

    def _hold(self, line: dict) -> None:
        key = line["key"]
        old = self.lines.get(key)
        if old is not None:
            boss_key = _boss_key(old)
            keys = self._by_boss.get(boss_key)
            if keys and key in keys:
                keys.remove(key)
        self.lines[key] = line
        self._by_boss.setdefault(_boss_key(line), []).append(key)

    def add(self, line: dict | None, flush: bool = True) -> bool:
        """Hold *line* and queue it for the file when it differs from the
        one under its key; whether it did."""
        if not line or not line.get("key"):
            return False
        with self._lock:
            if _same(self.lines.get(line["key"]), line):
                return False
            try:
                text = json.dumps(line, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                return False  # a value JSON cannot hold: the fight is not kept
            self._hold(line)
            self._pending.append(text)
            if flush:
                self.flush()
            return True

    def flush(self) -> bool:
        """Append the queued lines; on a file another program holds, keep
        them for the next try. Whether the queue is empty after."""
        with self._lock:
            if not self._pending:
                return True
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
                    fh.write("\n".join(self._pending) + "\n")
            except OSError:
                return False
            self._pending.clear()
            return True

    def pending(self) -> int:
        with self._lock:
            return len(self._pending)

    # ---- the backfill's notes ----

    def backfill_notes(self) -> tuple[set[str], set[str]]:
        """(the split logs a backfill has read, the copy marks of those
        read: fight_index._copy_hash), from fights-backfill.json."""
        with self._lock:
            if self._done is None:
                try:
                    data = json.loads(self.backfill_path.read_text(encoding="utf-8"))
                    self._done = ({str(name) for name in data.get("done", [])},
                                  {str(mark) for mark in data.get("copies", [])})
                except (OSError, ValueError, AttributeError):
                    self._done = (set(), set())
            return set(self._done[0]), set(self._done[1])

    def done_names(self) -> set[str]:
        """The split logs a backfill has read already."""
        return self.backfill_notes()[0]

    def mark_done(self, name: str, copy_mark: str | None = None) -> None:
        """Note *name* read (and its copy mark, so a copy of it is passed
        over in a later build too)."""
        with self._lock:
            done, copies = self.backfill_notes()
            done.add(str(name))
            if copy_mark:
                copies.add(str(copy_mark))
            self._done = (done, copies)
            try:
                tmp = self.backfill_path.with_suffix(".json.tmp")
                tmp.write_text(json.dumps({"done": sorted(done), "copies": sorted(copies)},
                                          ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self.backfill_path)
            except OSError:
                pass  # a later run reads the log again; its lines are held already

    # ---- queries ----

    def kills(self, zone_id: str, difficulty: str, boss: str, before_s: float | None) -> list[dict]:
        """The kills of *boss* at *difficulty* in the zone, before
        *before_s* (Unix seconds; None for every one), oldest first. A
        kill that carried on a pull the game cut in two is left out: its
        figures are the tail's (34 such fights in 2,362 pulls)."""
        with self._lock:
            keys = list(self._by_boss.get((str(zone_id), str(difficulty), str(boss)), ()))
            found = [self.lines[k] for k in keys if k in self.lines]
        found = [line for line in found if line.get("outcome") == "kill"
                 and not line.get("continues")
                 and (before_s is None or float(line.get("start_s") or 0) < before_s)]
        found.sort(key=lambda line: float(line.get("start_s") or 0))
        return found

    def __len__(self) -> int:
        with self._lock:
            return len(self.lines)

    def sessions(self) -> int:
        """Distinct days of play in the index (a cheap 'sessions' figure)."""
        with self._lock:
            return len({int(float(line.get("start_s") or 0) // 86400) for line in self.lines.values()})


def _same(old: dict | None, new: dict) -> bool:
    """Whether two lines hold the same fight figures (_NOT_COMPARED aside)."""
    if old is None:
        return False
    keys = (set(old) | set(new)) - _NOT_COMPARED
    return all(old.get(key) == new.get(key) for key in keys)


def _boss_key(line: dict) -> tuple:
    return (str(line.get("zone_id") or ""), str(line.get("difficulty") or ""),
            str(line.get("boss") or ""))


# --------------------------------------------------------- comparisons --

def _roster(entry) -> set[str]:
    return {str(p.get("name") or "") for p in (getattr(entry, "player_names", None) or [])
            if str(p.get("name") or "").startswith("@")}


def earlier_kills(index: FightIndex | None, entry) -> list[dict]:
    """The index's kills of the fight's boss at its difficulty in its zone,
    before it, oldest first; read once per render and handed to
    comparison and player_history."""
    pull = getattr(entry, "pull", None)
    if index is None or not pull or pull.get("start_s") is None:
        return []
    return index.kills(getattr(entry, "zone_id", ""), getattr(entry, "difficulty", ""),
                       pull.get("boss") or "", float(pull["start_s"]))


def comparison(index: FightIndex | None, entry, kills: list[dict] | None = None) -> dict | None:
    """The pull against the earlier kills of its boss (see the module):
    {'boss', 'all': [figures], 'narrow': [figures], 'label', 'every',
    'this'}; None when the index holds no earlier kill of it. *kills*:
    earlier_kills, when the caller has it already."""
    kills = earlier_kills(index, entry) if kills is None else kills
    if not kills:
        return None
    roster = _roster(entry)
    with_roster = [line for line in kills if len(roster & set(line.get("handles") or [])) >= ROSTER_MIN]
    version = str(getattr(entry, "game_version", "") or "")
    on_version = [line for line in with_roster if version and line.get("game") == version]
    narrow, label = [], ""
    if len(on_version) >= SET_MIN:
        narrow, label = on_version, f"with {ROSTER_MIN}+ of this roster on {short_version(version)}"
    elif len(with_roster) >= SET_MIN:
        narrow, label = with_roster, f"with {ROSTER_MIN}+ of this roster"
    every = bool(narrow) and len(narrow) == len(kills)
    if every:
        narrow = []  # the same set as every kill: said once, with its label
    this = float(getattr(entry, "group_boss_dps", 0) or getattr(entry, "group_dps", 0) or 0)
    return {"boss": getattr(entry, "pull", {}).get("boss") or "",
            "all": [_metric(line) for line in kills],
            "narrow": [_metric(line) for line in narrow],
            "label": label if (narrow or every) else "",
            "every": every,
            "this": this}


def comparison_text(found: dict | None) -> str:
    """'Your Lord Falgravn kills: median 441.2k over 28, best 953.4k; with
    8+ of this roster on 12.1: median 470.6k over 10. This pull: 512.3k'."""
    if not found or not found["all"]:
        return ""
    figures = found["all"]
    # Every earlier kill was with this roster: the set is said once, named
    every = f", all {found['label']}" if found.get("every") else ""
    if len(figures) == 1:
        text = f"Your earlier {found['boss']} kill: {fmt_dps(figures[0])}"
    else:
        text = (f"Your {found['boss']} kills{every}: median {fmt_dps(median(figures))} over "
                f"{len(figures)}, best {fmt_dps(max(figures))}")
    if found["narrow"]:
        text += (f"; {found['label']}: median {fmt_dps(median(found['narrow']))} over "
                 f"{len(found['narrow'])}")
    if found["this"]:
        text += f". This pull: {fmt_dps(found['this'])}"
    return text


def player_history(index: FightIndex | None, entry, handle: str,
                   kills: list[dict] | None = None) -> list[float]:
    """A named player's boss dps in their last PLAYER_LAST earlier kills of
    the fight's boss in the index, most recent first. *kills*:
    earlier_kills, when the caller has it already."""
    if not str(handle or "").startswith("@"):
        return []
    kills = earlier_kills(index, entry) if kills is None else kills
    values = []
    for line in reversed(kills):
        for row in line.get("rows") or []:
            if row.get("handle") == handle:
                values.append(float(row.get("boss_dps") or row.get("dps") or 0))
                break
        if len(values) >= PLAYER_LAST:
            break
    return values


def player_history_text(entry, handle: str, values: list[float], names=None) -> str:
    """'@x on Lord Falgravn: 92.4k, 101.2k, 88.0k in their last three
    kills with you'; 'in your last ...' for the logging player; '' for none.
    *names*: the Hide names mask."""
    if not values:
        return ""
    pull = getattr(entry, "pull", None) or {}
    local = any(p.get("is_local") and p.get("name") == handle
                for p in (getattr(entry, "player_names", None) or []))
    count = _COUNT_WORDS.get(len(values), f"{len(values)} kills")
    tail = f"in your last {count}" if local else f"in their last {count} with you"
    who = names.text(handle) if names is not None else handle
    return f"{who} on {pull.get('boss') or 'this boss'}: {', '.join(fmt_dps(v) for v in values)} {tail}"


def run_best_kill(index: FightIndex | None, run) -> float | None:
    """For a boss's pulls in a row (pull_outcome.runs): the best earlier
    kill of the boss with ROSTER_MIN or more of the run's named players,
    before its first pull; None when there is none."""
    if index is None or not run:
        return None
    first, last = run[0][0], run[-1][-1]
    pull = getattr(first, "pull", None)
    if not pull or pull.get("start_s") is None:
        return None
    roster = _roster(last)
    kills = index.kills(getattr(first, "zone_id", ""), getattr(first, "difficulty", ""),
                        pull.get("boss") or "", float(pull["start_s"]))
    figures = [_metric(line) for line in kills
               if len(roster & set(line.get("handles") or [])) >= ROSTER_MIN]
    return max(figures) if figures else None


# ------------------------------------------------------------ backfill --

_SPLIT_NAME = re.compile(r"^\d{12}-.+\.(log|zip)$", re.IGNORECASE)


def is_split_name(name: str) -> bool:
    """A file the splitter wrote, '<yymmddhhmmss>-<Zone>[-vet].log', or
    split retention's zip of one ('<that>.log.zip'); never the live
    session's '<yymmddhhmmss>-temp.log' the splitter is still writing, nor
    Encounter.log or an archive, which a blank split folder (the log's
    own) holds too."""
    name = str(name)
    return bool(_SPLIT_NAME.match(name)) and not name.lower().endswith("-temp.log")


def split_logs(folder) -> list[tuple[Path, str | None]]:
    """The split folder's logs, newest first by name (the splitter names
    them by their start): each split .log, and each log in a split's .zip.
    A zip that will not open is left out."""
    from log_open import is_zip, log_members
    folder = Path(folder)
    found = []
    try:
        names = sorted((name for name in os.listdir(folder) if is_split_name(name)), reverse=True)
    except OSError:
        return []
    for name in names:
        path = folder / name
        if name.lower().endswith(".log") and path.is_file():
            found.append((path, None))
        elif name.lower().endswith(".zip") and path.is_file() and is_zip(path):
            try:
                found.extend((path, member) for member in log_members(path))
            except (OSError, ValueError, zipfile.BadZipFile):
                continue
    return found


def source_name(path: Path, member: str | None) -> str:
    """A log's name in the backfill's notes: the split's own file name,
    which split retention's zip keeps as its member's, so a log read and
    later zipped is not read again."""
    return Path(member).name if member else Path(path).name


def _copy_hash(path: Path, member: str | None, size: int) -> str | None:
    """A byte-identical copy's mark: the first HEAD_BYTES and the size (a
    split cut short shares its head with the full one, not its size). A
    zip member's is its log's, so a copy zipped by split retention under
    its own name is still known; None when the head will not read."""
    try:
        if member:
            with zipfile.ZipFile(path) as zf, zf.open(member) as fh:
                head = fh.read(HEAD_BYTES)
        else:
            with open(path, "rb") as fh:
                head = fh.read(HEAD_BYTES)
    except (OSError, EOFError, ValueError, RuntimeError, NotImplementedError,
            zipfile.BadZipFile, zlib.error):
        return None
    return f"{hashlib.sha1(head).hexdigest()}:{size}"


def backfill(folder, index: FightIndex, make_analyzer: Callable[[], object],
             app_version: str = "",
             progress: Callable[[str, int, int], None] | None = None,
             cancel: threading.Event | None = None,
             live_stamp: str | None = None) -> dict:
    """Read the split logs the index has not read yet through the engine
    (see the module): {'logs': read, 'skipped': copies skipped, 'failed':
    logs that would not read, 'fights': lines added, 'left': logs still
    to read}. A log that fails (a zip member that will not decompress, a
    file moved away mid-read, an engine error) is counted and passed over,
    not noted done, so the next build tries it again and the rest are
    read. A log, or a copy passed over, is noted done only once the lines
    it stands for are on disk. *live_stamp*: the live log's newest session
    (split_retention.latest_session_stamp), whose split the splitter may
    still be writing under its final name; it is left to the window, which
    indexes that session as it replays and follows it, and is neither read
    nor noted. Raises review_load.ReviewCancelled on *cancel*."""
    import review_load
    from log_open import log_size
    done, copies = index.backfill_notes()
    live = f"{live_stamp}-" if live_stamp else None
    todo = [(path, member) for path, member in split_logs(folder)
            if source_name(path, member) not in done
            and not (live and path.name.startswith(live))]
    sizes = []
    for path, member in todo:
        try:
            sizes.append(log_size(path, member))
        except (OSError, ValueError, zipfile.BadZipFile):
            sizes.append(0)
    # Newest session first, and one session's logs shortest first: the old
    # splitter's re-splits of a session cut short (issue #85) share its
    # start and hold its fights up to their end, and where two hold one
    # fight with different figures (the shorter one's last fights, read
    # without what came after), the longest log's line, read last, is kept
    order = sorted(range(len(todo)), reverse=True,
                   key=lambda i: (todo[i][0].name[:12], -sizes[i]))
    todo = [todo[i] for i in order]
    sizes = [sizes[i] for i in order]
    total = sum(sizes) or 1
    result = {"logs": 0, "skipped": 0, "failed": 0, "fights": 0, "left": len(todo)}
    # Read or passed over, the lines they stand for not on disk yet
    unwritten: list[tuple[str, str | None]] = []

    def note_written():
        if index.flush():
            for done_name, done_mark in unwritten:
                index.mark_done(done_name, done_mark)
            unwritten.clear()

    offset = 0
    try:
        for number, ((path, member), size) in enumerate(zip(todo, sizes), start=1):
            # Between logs too: a replay checks only every megabyte or so
            if cancel is not None and cancel.is_set():
                raise review_load.ReviewCancelled()
            name = source_name(path, member)
            mark = _copy_hash(path, member, size)
            if mark is not None and mark in copies:
                result["skipped"] += 1
                unwritten.append((name, None))  # noted with the log it copies
                offset += size
                result["left"] -= 1
                continue
            label = f"Fight history: log {number} of {len(todo)}, {path.name}"

            def step(_label, done_bytes, _total, base=offset, label=label):
                if progress:
                    progress(label, min(base + done_bytes, total), total)

            try:
                analyzer = make_analyzer()
                _shown, fights = review_load.replay_log(analyzer, path, member, -1, step, cancel)
            except review_load.ReviewCancelled:
                raise
            except Exception:  # one bad log must not stop the rest
                result["failed"] += 1
                result["left"] -= 1
                offset += size
                continue
            for entry in fights:
                if index.add(fight_line(entry, app_version), flush=False):
                    result["fights"] += 1
            if mark is not None:
                copies.add(mark)
            unwritten.append((name, mark))
            note_written()
            result["logs"] += 1
            result["left"] -= 1
            offset += size
    finally:
        note_written()  # a cancel keeps what was read and written
    return result
