"""
The split files behind an instance (issue #194): for each logging session
a block of the fight list holds (fight_blocks), the files in the split
folder that hold it, for the Instance tab's links and the result strip's,
so a run can be handed to a log tool without a search through a folder of
hundreds of splits. No Qt.

By the session's stamp. The engine keeps on each fight the stamp its
session's split is named by (FightHistoryEntry.session_stamp): the
session's BEGIN_LOG time to the second, ``YYMMDDHHMMSS`` in local time,
from the one function the splitter names its files with
(split_retention.session_stamp). It is set as the fight is built, before
the fight is sent, and carried onto a fight the game cut in two with its
other slots. So a fight finds its file by name. A guess from the fights'
own clock times could pick a neighbouring session, since a session starts
before its first fight and can run on into the next instance. The zone in
the file's name is never compared: the splitter names a session after the
zone of its first fight, and of 633 fights replayed from 34 of Chris's
splits (2026-11-09), 39 were in another zone than their file's name, all
in two files (Lucent Citadel fights in a ``…-Maw-of-Lorkhaj-vet`` split,
The Cauldron in a ``…-Volenfell-vet`` one).

Per stamp, in order. A block can span several sessions (a new BEGIN_LOG
mid-run: a relog, a crash, the log turned off and on; by issue #196's
survey 36 of the 366 blocks in that folder span 2 to 5 splits), and one
session can hold several blocks (two dungeons in one sitting). So
splits_for takes the stamps of a block's fights, one per fight, and gives
one SessionSplits per stamp, in the order the fights first carry it.

Several files for one session. A session has one split now: the ``-N``
files are copies the splitter wrote before 0.19.0 (issue #85), and since
then a file gets a suffix only when the file of its name begins with
another session's lines (a second session in the same second). In that
folder 10 sessions still have more than one file, 32 files of which 30
are suffixed, once the byte-identical copies went to the Recycle Bin, and
each of the 22 smaller ones is a byte prefix of its session's largest: a
copy cut short when an earlier run stopped mid-session. In 2 of the 10
the largest is a ``-N`` file, so the plain name would offer a cut copy.
The files therefore come largest first, a zipped split (issue #86) by the
size of the log inside it; at equal sizes the plain log before a zip, the
split folder before its keep folder, and the plain name before ``-1``
before ``-2``. SessionSplits.best is the first, and the rest stay listed.
The fight history's backfill reads such a session the same way round,
its longest log last (fight_index).

Where. The split folder's own files (split_retention.scan_splits: the
splitter's names only, plain or zipped, never ``-temp.log``) and those of
its keep folder, where split retention never zips or deletes, so a split
moved there to keep it is still found. No other subfolder is entered.

Missing or not known. A stamp no file carries is missing: splitting was
off for that session or wrote to another folder, or the file was moved,
deleted, or sent to the Recycle Bin by split retention. A fight with no
stamp ('') is from a session whose BEGIN_LOG the engine never saw (the app
attached to a session that began beyond its 2 GB lookback, or a reviewed
log opens mid-session): it is not known, and nothing is looked for.

The clock. The stamp is local wall-clock time, by this machine's time zone
with that zone's rules for the instant, so daylight saving shifts
nothing: in Chris's folder each of the 408 splits holds one session, its
BEGIN_LOG the first line, and the stamp worked out from that line is the
file's own in all 408, 250 at UTC+10 and 158 at UTC+11. A split written
under another time zone (the machine's was changed, or the folder came
from another machine) carries a name this machine would not give the same
BEGIN_LOG, so its session shows as missing. The hour repeated as daylight
saving ends gives two instants one stamp, so two sessions begun an hour
apart in it would each be offered both files; no session in that folder
began before 7 a.m. A session that runs past midnight keeps the day it
began; none in that folder did (the latest ended at 23:46).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from split_retention import KEEP_FOLDER, SplitFile, scan_splits, zipped_log_size

# The copy number the splitter added to a name already taken (issue #85)
_COPY = re.compile(r"-(\d+)\.log(?:\.zip)?$")
_STAMP = "%y%m%d%H%M%S"
# How long before a list's first session an earlier split of its instance
# is looked for: a relog's new session comes minutes later (a Sunspire
# run, 2026-08-30: 31 minutes), and a trial runs an hour or two
EARLIER_WITHIN_S = 3 * 3600


@dataclass(frozen=True)
class SessionSplits:
    """The split files of one session of a block: *stamp* is '' when the
    fights' session is not known, and *files* is () when no file holds it,
    else every file that does, the whole session first."""
    stamp: str
    files: tuple[SplitFile, ...] = ()

    @property
    def known(self) -> bool:
        """The fights carry their session's stamp."""
        return bool(self.stamp)

    @property
    def missing(self) -> bool:
        """The session is known, but no file in the folder holds it."""
        return bool(self.stamp) and not self.files

    @property
    def best(self) -> SplitFile | None:
        """The file to offer: the largest, the whole session."""
        return self.files[0] if self.files else None


def splits_for(stamps: Iterable[str], split_dir: Path | str | None) -> list[SessionSplits]:
    """One SessionSplits for each stamp of *stamps* (the session_stamp of a
    block's fights, in fight order), in the order first met, with the files
    in *split_dir* and its keep folder that hold that session; '' (no stamp)
    is an entry of its own in its place. With *split_dir* None every known
    session is missing."""
    order = list(dict.fromkeys(str(stamp or "") for stamp in stamps))
    wanted = {stamp for stamp in order if stamp}
    found: dict[str, list[tuple[int, SplitFile]]] = {}
    if split_dir is not None and wanted:
        folder = Path(split_dir)
        for place, where in enumerate((folder, folder / KEEP_FOLDER)):
            for split in scan_splits(where, wanted):
                found.setdefault(split.stamp, []).append((place, split))
    return [SessionSplits(stamp, _whole_first(found.get(stamp, []))) for stamp in order]


def earlier_split(stamp: str, zone: str, vet: bool, split_dir: Path | str | None) -> SplitFile | None:
    """The whole split of the session just before *stamp* in *split_dir*
    and its keep folder, when its name gives the same zone and difficulty
    and it began within EARLIER_WITHIN_S before *stamp*; else None.

    For a fight list that begins inside a run. The app reads the log's
    latest logging session alone, at its start and at a Settings replay,
    so a run begun in an earlier session (a relog, a crash) lists only its
    later fights, and its split links only the later session's: of the 408
    splits in the maintainer's folder, 31 begin inside a trial already in
    progress (the fresh review of PR #210). The session before is the one
    to offer when its file's name says the same instance. The splitter
    names a file after its session's first fight's zone, so an earlier
    session that began elsewhere is not offered, nor one hours older."""
    if not stamp or split_dir is None:
        return None
    try:
        began = datetime.strptime(stamp, _STAMP)  # noqa: DTZ007
    except ValueError:
        return None
    folder = Path(split_dir)
    earlier = [(place, split) for place, where in enumerate((folder, folder / KEEP_FOLDER))
               for split in scan_splits(where) if split.stamp < stamp]
    if not earlier:
        return None
    last = max(split.stamp for _place, split in earlier)
    if (began - datetime.strptime(last, _STAMP)).total_seconds() > EARLIER_WITHIN_S:  # noqa: DTZ007
        return None
    best = _whole_first([(place, split) for place, split in earlier if split.stamp == last])[0]
    if best.vet != bool(vet) or _zone_key(best.zone) != _zone_key(zone):
        return None
    return best


def _zone_key(zone) -> str:
    # The splitter writes a zone's spaces as dashes, and parse_split_name
    # reads every dash back as a space
    return str(zone or "").replace("-", " ").casefold()


def _whole_first(files: list[tuple[int, SplitFile]]) -> tuple[SplitFile, ...]:
    """A session's files, the one holding the most of it first (see the
    module); a lone file as it is, its zip not opened."""
    if len(files) < 2:
        return tuple(split for _place, split in files)

    def rank(item):
        place, split = item
        size = zipped_log_size(split.path) if split.zipped else split.size
        copy = _COPY.search(split.path.name)
        # A zip that does not open goes last
        return (-(size if size is not None else -1), split.zipped, place,
                int(copy.group(1)) if copy else 0, split.path.name)

    return tuple(split for _place, split in sorted(files, key=rank))
