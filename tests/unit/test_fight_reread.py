"""Re-reading one fight from disk by its locator (fight_reread, issue #214).

Each session is written as bytes with an explicit newline and run through
the real engine (review_load.replay_log, a fresh ESOLogAnalyzer and
FightHistory), so every locator here is the engine's own; only the stale
offsets and the missing session are built by hand from one. Player names
carry multibyte letters (é, ö, a CJK name), so a character count is never a
byte offset. Expected places and times come from the bytes written, never
from numbers typed in.
"""

import io
import shutil
import threading
import time
import weakref
import zipfile
from array import array
from pathlib import Path

import pytest

import fight_reread as fr
import review_load
import split_retention
from esolog_tail import ESOLogAnalyzer
from fight_history import FightHistory
from fight_locator import LEAD_MS, TAIL_MS, MapFrame

EPOCH = 1_790_000_000_000
HOUR = 3_600_000
BOSS_HP = 1_000_000
START, END = 20_000, 30_000
PLACEHOLDER = "1/1,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000"


def st(unit, hp="30000/30000", x="0.5000", y="0.5000", mag="20000/25000", shield=0):
    """A unit's ten state fields as the log writes them."""
    return f"{unit},{hp},{mag},15000/20000,100/500,0/1000,{shield},{x},{y},1.5708"


def foe(unit, hp, x="0.6000"):
    return f"{unit},{hp}/{BOSS_HP},0/0,0/0,0/0,0/0,0,{x},0.4000,2.3000"


def effect(t, state, target="*"):
    return f"{t},EFFECT_CHANGED,GAINED,1,{t},61744,{state},{target}"


def hit(t, source, target, result="DAMAGE"):
    return f"{t},COMBAT_EVENT,{result},FIRE,1,5000,0,{t},39012,{source},{target}"


def player(t, unit, name, handle, character, local="F", seat=None):
    return (f'{t},UNIT_ADDED,{unit},PLAYER,{local},{seat or unit},0,F,117,7,"{name}",'
            f'"{handle}",{character},50,3000,0,PLAYER_ALLY,T')


def monster(t, unit, name, boss="F", monster_id="5555"):
    return (f'{t},UNIT_ADDED,{unit},MONSTER,F,0,{monster_id},{boss},0,0,"{name}","",0,50,160,0,'
            'HOSTILE,F')


def opening(epoch=EPOCH, zone_at=1000):
    return [
        f'5,BEGIN_LOG,{epoch},15,"NA Megaserver","en","eso.live.12.1"',
        f'{zone_at},ZONE_CHANGED,1196,"Kyne\'s Aegis",VETERAN',
        f'{zone_at + 29},MAP_CHANGED,1805,"Kyne\'s Aegis","skyrim/KynesAegisMap001"',
        player(zone_at + 100, 1, "Éowyn Fëanor", "@tëster", 1001, local="T"),
        player(zone_at + 100, 2, "Björk Öst", "@björk", 1002),
        player(zone_at + 100, 3, "李小龍", "@lǐ", 1003),
        monster(zone_at + 200, 70, "Test Boss", boss="T", monster_id="105634"),
        monster(zone_at + 300, 80, "First Add"),
        monster(zone_at + 300, 81, "Third Add"),
        monster(zone_at + 300, 82, "Fifth Add"),
    ]


def standard(epoch=EPOCH):
    """A session: its zone and units, a line before the lead-in, the
    lead-in, a fight with every case the reader tells apart, the tail and
    lines after it."""
    return opening(epoch) + [
        effect(5000, st(1, x="0.1000")),                       # before the lead-in
        effect(START - 9000, st(1, x="0.2000")),               # the lead-in
        f"{START - 3000},BEGIN_CAST,0,F,7001,39012,{st(2)},*",
        f"{START},BEGIN_COMBAT",
        hit(START + 10, st(2), foe(70, 995000)),
        hit(START + 10, st(2), foe(70, 990000)),               # same ms: the last wins
        f"{START + 500},BEGIN_CAST,1000,T,7003,16420,{st(1, x='0.3000')},{foe(70, 990000)}",
        effect(START + 600, st(1, x="0.3000")),                # equal to the one before
        effect(START + 1000, foe(80, 5000, x="0.1500")),       # the first unit 80
        effect(START + 1500, foe(81, 3000, x="0.2500")),       # the first unit 81
        effect(START + 1800, foe(82, 200, x="0.9000")),
        f"{START + 2000},UNIT_REMOVED,80",
        f"{START + 2000},UNIT_REMOVED,82",
        hit(START + 2500, st(0, hp="0/0", x="0.0000", y="0.0000"), st(1, x="0.3200")),
        effect(START + 2600, foe(82, 100, x="0.9100")),        # after its UNIT_REMOVED
        effect(START + 3000, st(2, x="0.3300"), f"3,{PLACEHOLDER}"),
        monster(START + 4000, 80, "Second Add", monster_id="6666"),  # id 80 handed on
        monster(START + 4200, 81, "Fourth Add", monster_id="7777"),  # 81, never removed
        effect(START + 4200, foe(81, 9000, x="0.8000")),
        effect(START + 4500, foe(80, 7000, x="0.7000")),
        effect(START + 4900, st(2, x="0.2500")),
        effect(START + 5000, st(1, x="0.4000")),
        f'{START + 5000},MAP_CHANGED,1806,"Floor","skyrim/KynesAegisFloor01"',
        effect(START + 5000, st(1, x="0.6000")),
        effect(START + 5000, st(2, x="0.2500")),               # the same state, a new map
        effect(START + 6000, st(2, x="-270.1234", y="15.5000")),  # far off the map
        effect(START + 6100, st(3, x="0.3800")),
        effect(START + 6200, st(3, x="0.4000")),
        effect(START + 6200, st(3, x="0.3800")),               # back to the one before
        f"{START + 6500},UNIT_REMOVED,3",
        player(START + 7000, 33, "李小龍", "@lǐ", 1003, seat=4),  # back on a new id
        effect(START + 7500, st(33, x="0.3900")),
        effect(START + 8000, st(99, hp="0/0", x="0.7000")),    # never announced
        f"{START + 8500},HEALTH_REGEN,500,{st(1, hp='29000/30000', x='0.6100')}",
        hit(START + 9000, st(2), foe(70, 0)),
        hit(START + 9001, st(2), foe(70, 0), result="DIED_XP"),
        f"{END},END_COMBAT",
        f"{END},BEGIN_CAST,0,F,7013,28541,{st(1, x='0.3400')},*",  # END_COMBAT's ms
        effect(END + 800, st(1, x="0.3500")),                   # the tail
        effect(END + TAIL_MS + 500, st(1, x="0.9000")),         # past the tail
        effect(END + 9000, st(1, x="0.9500")),
    ]


class Log:
    """Lines written as bytes with one newline, each line's offset kept."""

    def __init__(self, newline=b"\r\n"):
        self.newline = newline
        self.data = bytearray()
        self.lines = []  # (offset, text)

    def add(self, lines):
        for text in lines:
            self.lines.append((len(self.data), text))
            self.data += text.encode("utf-8") + self.newline
        return self

    def offset_of(self, text, after=0):
        return next(at for at, line in self.lines if at >= after and line == text)

    def time_of_first(self, t_ms, after=0):
        """The time of the first line at or after *after* whose time is
        *t_ms* or later."""
        return next(int(line.split(",", 1)[0]) for at, line in self.lines
                    if at >= after and int(line.split(",", 1)[0]) >= t_ms)

    def save(self, path):
        Path(path).write_bytes(bytes(self.data))
        return Path(path)


def replay(path):
    """The engine's fights of the log at *path*, with their locators."""
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    _shown, fights = review_load.replay_log(analyzer, Path(path))
    return fights


def split_of(tmp_path, lines, name="split.log", newline=b"\r\n"):
    log = Log(newline).add(lines)
    path = log.save(tmp_path / name)
    return log, path, replay(path)


def read(locator, path, kind="split", hint=None, cancel=None):
    return fr.read_fight(locator, [fr.Place(Path(path), kind, None, hint)], cancel)


def xs(track):
    return [round(x, 4) for x in track.x]


def columns(states):
    return {name: [bytes(getattr(track, name)) for track in states.tracks]
            for name, _code in fr.STATE_COLUMNS}


def same(a, b):
    """Two reads hold the same tracks, units, states and frames."""
    assert [t.ids for t in a.tracks] == [t.ids for t in b.tracks]
    assert [t.unit for t in a.tracks] == [t.unit for t in b.tracks]
    assert columns(a) == columns(b)
    assert a.frames == b.frames
    assert (a.range_start_ms, a.tail_seen) == (b.range_start_ms, b.tail_seen)


def lead_of_many_lines(epoch=EPOCH):
    """standard() with ten more states in its lead-in, so that reading it
    back crosses a chunk's edge at every chunk size used here."""
    lines = standard(epoch)
    at = lines.index(effect(START - 9000, st(1, x="0.2000"))) + 1
    more = [effect(START - 8500 + 500 * k, st(2, x=f"0.{60 + k}00")) for k in range(10)]
    return lines[:at] + more + lines[at:]


def cancelled_casts(t, count, step=25):
    """Lines the parser rejects (a cancelled cast) from *t* on: bytes that a
    split since 0.19.0 keeps and the reader passes over."""
    return [f"{t + step * k},END_CAST,PLAYER_CANCELLED,{7_000_000 + k},269230"
            for k in range(count)]


class Looks:
    """A cancel that is set from its *n*-th look on."""

    def __init__(self, n):
        self.n, self.looks = n, 0

    def is_set(self):
        self.looks += 1
        return self.looks >= self.n


class Reads:
    """The bytes fight_reread reads from plain files: its open, wrapped to
    count them."""

    def __init__(self, monkeypatch):
        self.bytes = 0
        reads = self

        class Counted(io.BufferedReader):
            def read(self, size=-1):
                data = super().read(size)
                reads.bytes += len(data)
                return data

            def readline(self, size=-1):
                data = super().readline(size)
                reads.bytes += len(data)
                return data

        monkeypatch.setattr(fr, "open", lambda path, mode="rb": Counted(io.FileIO(path)),
                            raising=False)


def finishes(call, timeout=30):
    """*call*'s result, called on a thread of its own, which must return
    within *timeout* seconds (one that does not is left running, a daemon)."""
    got = []

    def run():
        try:
            got.append((True, call()))
        except BaseException as exc:  # noqa: BLE001 - raised again on the test's thread
            got.append((False, exc))

    thread = threading.Thread(target=run, name="test-read", daemon=True)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), f"still reading after {timeout} s"
    ((ok, value),) = got
    if not ok:
        raise value
    return value


@pytest.fixture
def fight(tmp_path):
    """(log, split path, locator, states) of the standard session."""
    log, path, fights = split_of(tmp_path, standard())
    assert len(fights) == 1
    locator = fights[0].locator
    return log, path, locator, read(locator, path, hint=0)


# ---------------------------------------------------------------- bytes --

def test_reads_by_offset_from_a_split(fight):
    log, _path, locator, states = fight
    assert locator.begin_offset == log.offset_of(f"{START},BEGIN_COMBAT")
    assert states.found_by == "offset" and states.tail_seen
    assert (states.start_ms, states.end_ms) == (START, END)
    assert states.skipped == 0


def test_the_lead_in_starts_by_time(fight):
    log, _path, _locator, states = fight
    assert states.range_start_ms == log.time_of_first(START - LEAD_MS)
    one = states.track_of("1")
    assert xs(one)[0] == 0.2          # the lead-in's state; the one before is not read
    assert one.t[0] == START - 9000


def test_the_lead_in_stops_at_the_zone_line(tmp_path):
    lines = [f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
             '10,ZONE_CHANGED,1,"Somewhere",NONE',
             player(20, 1, "Éowyn Fëanor", "@tëster", 1001, local="T"),
             effect(900, st(1, x="0.1111"))]                    # the zone before
    zone_line = '1000,ZONE_CHANGED,1196,"Kyne\'s Aegis",VETERAN'
    lines += [zone_line, player(1100, 1, "Éowyn Fëanor", "@tëster", 1001, local="T"),
              monster(1200, 70, "Test Boss", boss="T"), effect(3000, st(1, x="0.2222")),
              "6000,BEGIN_COMBAT", hit(6010, st(1), foe(70, 900000)), "9000,END_COMBAT"]
    log, path, fights = split_of(tmp_path, lines)
    locator = fights[-1].locator
    assert locator.zone_offset == log.offset_of(zone_line)
    by_offset = read(locator, path)
    assert by_offset.range_start_ms == 1000 and by_offset.frames == (fr.UNKNOWN_MAP,)
    assert xs(by_offset.track_of("1"))[0] == 0.2222
    # Found by time, or from a zip's member, which streams from the
    # session's start, the zone line in the lead-in drops what came before
    spoiled = locator._replace(begin_offset=locator.begin_offset + 5, zone_offset=None)
    by_scan = read(spoiled, path)
    assert by_scan.found_by == "scan"
    same(by_scan, by_offset)
    copy = Path(shutil.copy(path, tmp_path / "261015191452-Somewhere.log"))
    split_retention.zip_split(copy)
    from_zip = read(locator, Path(f"{copy}.zip"), hint=0)
    assert from_zip.found_by == "offset"
    same(from_zip, by_offset)


def test_the_tail_ends_one_second_after_end_combat(fight):
    _log, _path, _locator, states = fight
    one = states.track_of("1")
    assert 0.34 in xs(one) and 0.35 in xs(one)    # END_COMBAT's ms and the tail
    assert 0.9 not in xs(one) and max(one.t) <= END + TAIL_MS


def test_the_tail_stops_at_the_next_begin_combat(tmp_path):
    lines = standard()[:-3] + [
        effect(END + 200, st(1, x="0.8100")),
        monster(END + 300, 71, "Next Add"),
        f"{END + 500},BEGIN_COMBAT",
        effect(END + 600, st(1, x="0.8200")),
        hit(END + 700, st(2), foe(71, 4000)),
        f"{END + 9000},END_COMBAT"]
    _log, path, fights = split_of(tmp_path, lines)
    assert len(fights) == 2
    first = read(fights[0].locator, path)
    assert first.tail_seen
    assert 0.81 in xs(first.track_of("1")) and 0.82 not in xs(first.track_of("1"))
    # The next fight's lead-in reaches back over the first
    second = read(fights[1].locator, path)
    assert 0.81 in xs(second.track_of("1")) and 0.82 in xs(second.track_of("1"))


def test_a_fight_cut_in_two_is_read_whole(tmp_path):
    """The game ended combat and began it again 40 ms later with the boss
    alive: one fight, read through its first END_COMBAT and its second
    BEGIN_COMBAT to the tail after its last END_COMBAT."""
    lines = opening() + [
        effect(START - 9000, st(1, x="0.2000")),
        f"{START},BEGIN_COMBAT",
        hit(START + 10, st(2), foe(70, 995000)),
        hit(START + 4000, st(2), foe(70, 900000)),
        f"{START + 4500},END_COMBAT",                     # the game's cut
        hit(START + 4520, st(2), foe(70, 890000)),        # between the two lines
        f"{START + 4540},BEGIN_COMBAT",
        effect(START + 6000, st(1, x="0.7000")),
        hit(START + 9000, st(2), foe(70, 0)),
        f"{END},END_COMBAT",
        effect(END + 800, st(1, x="0.3500")),             # the tail
        effect(END + TAIL_MS + 500, st(1, x="0.9000"))]   # past it
    _log, path, fights = split_of(tmp_path, lines)
    assert len(fights) == 1
    locator = fights[0].locator
    assert (locator.start_ms, locator.end_ms) == (START, END)
    states = read(locator, path)
    assert states.found_by == "offset" and states.tail_seen
    assert list(states.track_of("70").health) == [995000, 900000, 890000, 0]
    assert xs(states.track_of("1")) == [0.2, 0.7, 0.35]


NEXT = EPOCH + HOUR
# What follows the line at END_COMBAT's ms; each stop line is followed at
# once by states of the same unit ids (or by the file's end), so that a
# reader that does not stop at that one kind of line reads them
TAIL_STOPS = {
    "zone": [f'{END + 50},ZONE_CHANGED,1000,"Elsewhere",NONE',
             effect(END + 300, st(1, x="0.8800")), effect(END + 400, foe(70, 5))],
    "end_log, a session after": [f"{END + 50},END_LOG", *standard(NEXT)],
    "end_log, the file's end": [f"{END + 50},END_LOG"],
    "begin_log": [f'5,BEGIN_LOG,{NEXT},15,"NA Megaserver","en","eso.live.12.1"',
                  effect(300, st(1, x="0.8800"))],
}


@pytest.mark.parametrize("case", list(TAIL_STOPS))
def test_a_zone_or_session_line_in_the_tail_ends_the_read(tmp_path, case):
    """Unit ids start over at a ZONE_CHANGED, and a new session's times at
    0: the read stops at the line, which counts as the tail's end."""
    path = Log().add(standard()[:-3] + TAIL_STOPS[case]).save(tmp_path / "Encounter.log")
    locator = next(f.locator for f in replay(path) if f.locator.session_epoch_ms == EPOCH)
    states = read(locator, path, "live", locator.session_offset)
    assert states.tail_seen
    one = states.track_of("1")
    assert 0.88 not in xs(one) and list(one.t) == sorted(one.t)
    assert max(one.t) <= END + TAIL_MS
    boss = states.track_of("70")
    assert boss.health[len(boss) - 1] == 0


def test_an_lf_only_log_reads_the_same(tmp_path, fight):
    _log, _path, crlf_locator, crlf = fight
    lf_log, lf_path, fights = split_of(tmp_path, standard(), "lf.log", newline=b"\n")
    locator = fights[0].locator
    assert locator.begin_offset == lf_log.offset_of(f"{START},BEGIN_COMBAT")
    assert locator.begin_offset < crlf_locator.begin_offset
    states = read(locator, lf_path)
    assert states.found_by == "offset"
    same(states, crlf)


def test_a_zipped_split_reads_the_same(tmp_path, fight):
    _log, path, locator, plain = fight
    copy = shutil.copy(path, tmp_path / "261015191452-Kyne's-Aegis-vet.log")
    assert split_retention.zip_split(Path(copy)).kind == "zipped"
    zipped = Path(str(copy) + ".zip")
    by_offset = read(locator, zipped, hint=0)
    assert by_offset.found_by == "offset"
    same(by_offset, plain)
    spoiled = locator._replace(begin_offset=locator.begin_offset + 3,
                               zone_offset=locator.zone_offset + 3)
    by_scan = read(spoiled, zipped, hint=0)
    assert by_scan.found_by == "scan"
    same(by_scan, plain)


def test_a_live_log_of_three_sessions(tmp_path, fight):
    _log, _path, _split_locator, from_split = fight
    log = Log().add(standard(EPOCH - HOUR)).add(standard(EPOCH)).add(standard(EPOCH + HOUR))
    live = log.save(tmp_path / "Encounter.log")
    fights = replay(live)
    locator = next(f.locator for f in fights if f.locator.session_epoch_ms == EPOCH)
    base = log.offset_of(standard(EPOCH)[0])
    assert locator.session_offset == base > 0
    # No hint, a wrong one (another session's start, the middle of a line),
    # the right one: the session is found by its own token
    for hint in (None, 0, 3, base):
        states = read(locator, live, "live", hint)
        assert states.found_by == "offset"
        same(states, from_split)
    # The same bytes archived: a zip's member streams, and a wrong hint
    # sends the reader back to the member's start
    archive = tmp_path / "Encounter-2026-11-11.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(live, "Encounter.log")
    for hint in (None, 3, base):
        states = read(locator, archive, "archive", hint)
        assert states.found_by == "offset" and states.source.endswith("Encounter-2026-11-11.zip")
        same(states, from_split)


def test_spoiled_offsets_fall_back_to_a_scan(fight):
    _log, path, locator, by_offset = fight
    for shift in (-7, 7):
        spoiled = locator._replace(begin_offset=locator.begin_offset + shift,
                                   zone_offset=locator.zone_offset + shift)
        states = read(spoiled, path, hint=0)
        assert states.found_by == "scan"
        same(states, by_offset)


def test_a_fight_with_no_begin_combat_is_found_by_time(tmp_path):
    lines = opening() + [effect(12000, st(1, x="0.2000")),
                         hit(20010, st(2), foe(70, 995000)),
                         hit(25010, st(2), foe(70, 990000)),
                         f"{END},END_COMBAT"]
    log, path, fights = split_of(tmp_path, lines)
    locator = fights[0].locator
    assert locator.begin_offset is None
    states = read(locator, path)
    assert states.found_by == "scan"
    assert states.range_start_ms == log.time_of_first(locator.start_ms - LEAD_MS)
    assert xs(states.track_of("1")) == [0.2]


def test_not_on_disk_says_why_for_each_place(tmp_path, fight):
    _log, path, locator, _states = fight
    other = Log().add(opening(EPOCH + 1)).save(tmp_path / "other.log")
    missing = tmp_path / "gone.log"
    moved = locator._replace(start_ms=START + 1)  # a BEGIN_COMBAT that is not there
    places = [fr.Place(missing, "live"), fr.Place(other, "review"), fr.Place(path, "split", None, 0)]
    with pytest.raises(fr.NotOnDisk) as caught:
        fr.read_fight(moved, places)
    assert [why for _place, why in caught.value.reasons] == [
        "no such file", fr.NOT_HERE, f"{fr.STALE}; {fr.NO_FIGHT}"]
    assert "gone.log" in str(caught.value) and "other.log" in str(caught.value)
    with pytest.raises(fr.NotOnDisk) as unknown:
        fr.read_fight(locator._replace(session_epoch_ms=None), places)
    assert {why for _place, why in unknown.value.reasons} == {fr.NOT_KNOWN}


def test_cancel(fight, monkeypatch):
    _log, path, locator, _states = fight
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(fr.Cancelled):
        read(locator, path, cancel=cancel)

    class LateCancel:
        """Set once the read has passed a few chunks."""
        calls = 0

        def is_set(self):
            self.calls += 1
            return self.calls > 4

    monkeypatch.setattr(fr, "CHUNK", 256)
    late = LateCancel()
    with pytest.raises(fr.Cancelled):
        read(locator, path, cancel=late)
    assert late.calls == 5


@pytest.mark.parametrize("where", ["the search back", "the session's end", "the lead-in"])
def test_a_cancel_is_seen_within_a_few_chunks(tmp_path, monkeypatch, fight, where):
    """A cancel set while the reader searches a plain file is seen a chunk
    later, not once it has read the whole stretch: the search back through
    a live log that does not hold the session (from a wrong hint), the
    session read to its end before a fight with no BEGIN_COMBAT line is
    found by time, and a lead-in read back from BEGIN_COMBAT."""
    _log, _split, locator, _states = fight
    if where == "the search back":
        log = Log().add(standard(EPOCH - HOUR)).add(standard(EPOCH + HOUR))
        path, hint, chunk = log.save(tmp_path / "Encounter.log"), 3, "SCAN_CHUNK"
        stretch = len(log.data)
    elif where == "the session's end":
        lines = opening() + [effect(12000, st(1, x="0.2000")),
                             hit(20010, st(2), foe(70, 995000)),
                             f"{END},END_COMBAT"] + cancelled_casts(END + 5000, 300)
        log, path, fights = split_of(tmp_path, lines)
        (locator,) = [f.locator for f in fights]
        assert locator.begin_offset is None
        hint, chunk = 0, "SCAN_CHUNK"
        stretch = len(log.data) - log.offset_of(f"{END},END_COMBAT")
    else:
        lines = standard()
        at = lines.index(f"{START},BEGIN_COMBAT") - 1   # before the cast at START - 3000
        log, path, fights = split_of(tmp_path, lines[:at] + cancelled_casts(START - 8900, 300, 15)
                                     + lines[at:])
        (locator,) = [f.locator for f in fights]
        hint, chunk = 0, "BACK_CHUNK"
        stretch = locator.begin_offset - log.offset_of(cancelled_casts(START - 8900, 1)[0])
    monkeypatch.setattr(fr, chunk, 256)
    assert stretch > 20 * 256
    reads = Reads(monkeypatch)
    with pytest.raises(fr.Cancelled):
        fr.read_fight(locator, [fr.Place(path, "live" if hint == 3 else "split", None, hint)],
                      Looks(3))
    # Set after a chunk or two of the stretch, seen at the next
    assert 0 < reads.bytes <= 4 * 256


# Above the longest line of the logs read here, so every line crosses or
# meets a chunk's edge somewhere: (CHUNK, BACK_CHUNK, SCAN_CHUNK)
ABOVE_THE_LONGEST = [(14, 26, 30), (3, 41, 7)]


@pytest.mark.parametrize("above", ABOVE_THE_LONGEST)
def test_reads_across_chunk_edges_are_the_same(tmp_path, monkeypatch, above):
    """Chunks a little longer than the longest line: the carry across
    CHUNK, a lead-in read back over several BACK_CHUNKs, the search for
    the session's token and the skips by time over SCAN_CHUNKs give the
    same states as one chunk does, in a split by offset and by time, its
    zip both ways, and a live log and its archive with no hint."""
    log, path, fights = split_of(tmp_path, lead_of_many_lines())
    locator = fights[0].locator
    spoiled = locator._replace(begin_offset=locator.begin_offset + 7,
                               zone_offset=locator.zone_offset + 7)
    copy = Path(shutil.copy(path, tmp_path / "261015191452-Kyne's-Aegis-vet.log"))
    split_retention.zip_split(copy)
    zipped = Path(f"{copy}.zip")
    live_log = (Log().add(lead_of_many_lines(EPOCH - HOUR)).add(lead_of_many_lines())
                .add(lead_of_many_lines(EPOCH + HOUR)))
    live = live_log.save(tmp_path / "Encounter.log")
    in_live = next(f.locator for f in replay(live) if f.locator.session_epoch_ms == EPOCH)
    assert in_live.session_offset > 0
    archive = tmp_path / "Encounter-2026-11-11.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(live, "Encounter.log")
    reads = {"by offset": (lambda: read(locator, path, hint=0), "offset"),
             "by time": (lambda: read(spoiled, path, hint=0), "scan"),
             "zip by offset": (lambda: read(locator, zipped, hint=0), "offset"),
             "zip by time": (lambda: read(spoiled, zipped, hint=0), "scan"),
             "live, no hint": (lambda: read(in_live, live, "live"), "offset"),
             "archive, no hint": (lambda: read(in_live, archive, "archive"), "offset")}
    whole = {}
    for case, (get, found_by) in reads.items():
        whole[case] = get()
        assert whole[case].found_by == found_by, case
    lead = log.offset_of(effect(START - 9000, st(1, x="0.2000")))
    longest = max(len(line) + 1 for line in bytes(live_log.data).split(b"\n"))
    for name, more in zip(("CHUNK", "BACK_CHUNK", "SCAN_CHUNK"), above, strict=True):
        monkeypatch.setattr(fr, name, longest + more)
    assert locator.begin_offset - lead > 2 * fr.BACK_CHUNK   # the lead-in is several chunks
    for case, (get, found_by) in reads.items():
        states = get()
        assert states.found_by == found_by, case
        same(states, whole[case])


def test_a_scan_window_edge_inside_the_sessions_token(tmp_path, monkeypatch):
    """The session's token ``,BEGIN_LOG,<unix ms>,`` across a SCAN_CHUNK
    edge: searched back from a live log's end, and forward through an
    archive's member, it is found all the same."""
    log = Log().add(standard(EPOCH - HOUR)).add(standard(EPOCH)).add(standard(EPOCH + HOUR))
    live = log.save(tmp_path / "Encounter.log")
    locator = next(f.locator for f in replay(live) if f.locator.session_epoch_ms == EPOCH)
    archive = tmp_path / "Encounter-2026-11-11.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(live, "Encounter.log")
    whole = read(locator, live, "live")
    data, token = bytes(log.data), b",BEGIN_LOG,%d," % EPOCH
    # Back from the end, the first window begins 5 bytes into the token
    monkeypatch.setattr(fr, "SCAN_CHUNK", len(data) - data.rfind(token) - 5)
    back = read(locator, live, "live")
    assert back.found_by == "offset"
    same(back, whole)
    # Forward from the member's start, the first chunk ends 5 bytes into it
    monkeypatch.setattr(fr, "SCAN_CHUNK", data.find(token) + 5)
    forward = read(locator, archive, "archive")
    assert forward.found_by == "offset"
    same(forward, whole)


@pytest.mark.parametrize("back", [64, 16])
def test_a_lead_in_line_longer_than_the_chunk(fight, monkeypatch, back):
    """A line before the BEGIN_COMBAT line is longer than the chunk read
    back: the walk reads further back instead of standing still."""
    log, path, locator, by_default = fight
    lead = log.offset_of(effect(START - 9000, st(1, x="0.2000")))
    lines = bytes(log.data[lead:locator.begin_offset]).split(b"\n")
    assert min(len(line) for line in lines if line) > back
    monkeypatch.setattr(fr, "BACK_CHUNK", back)
    states = finishes(lambda: read(locator, path, hint=0))
    assert states.found_by == "offset"
    assert states.range_start_ms == log.time_of_first(START - LEAD_MS)
    same(states, by_default)


# ---------------------------------------------------------------- lines --

def test_self_targets_unit_zero_and_placeholders(fight):
    _log, _path, _locator, states = fight
    assert states.track_of("0") is None and states.track_of("*") is None
    assert all(track.unit is not None or track.ids in (("82",), ("99",))
               for track in states.tracks)
    # The line's source is read; its target, player 3's placeholder, is not
    assert START + 3000 in list(states.track_of("2").t)
    three = states.track_of("3")
    assert START + 3000 not in list(three.t) and 1 not in list(three.health_max)


def test_one_state_per_millisecond_the_last_wins(fight):
    _log, _path, _locator, states = fight
    boss = states.track_of("70")
    assert list(boss.t).count(START + 10) == 1
    assert boss.health[list(boss.t).index(START + 10)] == 990000
    # A state equal to the one before is dropped, and so is one its own
    # millisecond brought back to the one before
    one = states.track_of("1")
    assert START + 600 not in list(one.t) and START + 500 in list(one.t)
    three = states.track_of("3")
    assert START + 6100 in list(three.t) and START + 6200 not in list(three.t)
    # The same state on a new map is a state of its own
    two = states.track_of("2")
    assert [(two.t[i], two.frame[i]) for i in range(len(two)) if round(two.x[i], 4) == 0.25] == [
        (START + 4900, 0), (START + 5000, 1)]


def test_far_places_are_kept_and_told(fight):
    _log, _path, _locator, states = fight
    two = states.track_of("2")
    far = [i for i in range(len(two)) if two.x[i] < -100]
    assert len(far) == 1 and not fr.on_map(two.x[far[0]], two.y[far[0]])
    assert fr.on_map(two.x[0], two.y[0])


def test_frames_switch_at_the_map_line_in_file_order(fight):
    _log, _path, locator, states = fight
    assert states.frames == (locator.map_at_lead,
                             MapFrame("1806", "Floor", "skyrim/KynesAegisFloor01"))
    assert locator.map_at_lead.map_id == "1805"
    one = states.track_of("1")
    rows = [(one.t[i], one.frame[i], round(one.x[i], 4)) for i in range(len(one))]
    assert (START + 5000, 0, 0.4) in rows and (START + 5000, 1, 0.6) in rows
    assert rows[-1][1] == 1


def test_a_reused_unit_id_is_told_apart_by_the_windows(fight):
    _log, _path, locator, states = fight
    rows = [unit for unit in locator.units if unit.key == "80"]
    assert len(rows) == 2
    first = states.track_of("80", START + 1000)
    second = states.track_of("80", START + 4500)
    assert first is not second
    assert first.unit.until_ms == START + 2000 and second.unit.since_ms == START + 4000
    assert xs(first) == [0.15] and xs(second) == [0.7]
    assert states.track_of("80") is second    # with no time, the latest arrival
    # Unit 81 was handed on with no UNIT_REMOVED: both windows hold the
    # millisecond it changed hands, and the latest arrival has it
    old, new = states.track_of("81", START + 1500), states.track_of("81", START + 4200)
    assert old is not new and new.unit.since_ms == START + 4200 == old.unit.until_ms
    assert xs(old) == [0.25] and xs(new) == [0.8]


def test_a_state_outside_its_rows_windows_is_an_unknown_units(fight):
    _log, _path, _locator, states = fight
    row = states.track_of("82", START + 1800)
    assert row.unit.key == "82" and row.unit.until_ms == START + 2000 and xs(row) == [0.9]
    stray = states.track_of("82", START + 2600)
    assert stray.unit is None and stray.ids == ("82",) and xs(stray) == [0.91]


def test_a_players_two_ids_are_one_track(fight):
    _log, _path, _locator, states = fight
    three = states.track_of("3")
    assert three is states.track_of("33") and three.ids == ("3", "33")
    assert xs(three)[-2:] == [0.38, 0.39]
    assert three.unit.name and three.unit.character == "李小龍"


def test_unknown_units_get_a_track_of_their_own(fight):
    _log, _path, _locator, states = fight
    unknown = states.track_of("99")
    assert unknown.unit is None and unknown.ids == ("99",) and len(unknown) == 1
    assert states.tracks[-1] is unknown


def test_columns_are_read_only(fight):
    _log, _path, _locator, states = fight
    one = states.track_of("1")
    with pytest.raises(TypeError):
        one.x[0] = 0.0
    with pytest.raises(TypeError):
        one.t[0] = 0
    assert one.x.readonly and isinstance(states.tracks, tuple)
    assert states.nbytes() == states.state_count * sum(array(code).itemsize
                                                       for _name, code in fr.STATE_COLUMNS)


def test_moment(fight):
    _log, _path, _locator, states = fight
    seen = {tuple(track.ids): (state, age) for track, state, age in states.moment(START + 8700)}
    state, age = seen[("1",)]
    assert (state.t, age, state.health) == (START + 8500, 200, 29000)
    assert seen[("99",)][1] == 700
    assert all(age >= 0 for _state, age in seen.values())
    assert states.moment(0) == []


def test_effect_and_cast_targets_are_read(tmp_path):
    """The target of an EFFECT_CHANGED and of a BEGIN_CAST is a state, as a
    COMBAT_EVENT's is: on real splits about 30% of the states in fights."""
    lines = opening() + [
        f"{START},BEGIN_COMBAT",
        effect(START + 1000, st(1, x="0.3000"), foe(70, 990000, x="0.1100")),
        (f"{START + 2000},BEGIN_CAST,0,F,7002,16420,{st(1, x='0.3000')},"
         f"{foe(70, 980000, x='0.2200')}"),
        hit(START + 3000, st(2), foe(70, 970000, x="0.3300")),
        f"{END},END_COMBAT"]
    _log, path, fights = split_of(tmp_path, lines)
    boss = read(fights[0].locator, path).track_of("70")
    assert [(boss.t[i], round(boss.x[i], 4), boss.health[i]) for i in range(len(boss))] == [
        (START + 1000, 0.11, 990000), (START + 2000, 0.22, 980000), (START + 3000, 0.33, 970000)]


def test_a_states_every_field(tmp_path):
    """Every field of a state lands in its own column (every value here a
    different number): a HEALTH_REGEN's unit, and a COMBAT_EVENT's target.
    Place and heading are float32 columns, compared as float32."""
    regen = f"{START + 8500},HEALTH_REGEN,500,{st(1, hp='29000/30000', x='0.6100')}"
    shielded = (f"{START + 8500},HEALTH_REGEN,500,"
                f"{st(1, hp='29000/30000', x='0.6100', mag='21000/26000', shield=4321)}")
    lines = [shielded if line == regen else line for line in standard()]
    assert shielded in lines
    _log, path, fights = split_of(tmp_path, lines)
    states = read(fights[0].locator, path)

    def f32(value):
        return array("f", [value])[0]

    one = states.track_of("1")
    got = one.row(one.at(START + 8500))
    assert got._replace(seen=0) == fr.State(
        START + 8500, f32(0.61), f32(0.5), f32(1.5708), 29000, 30000,
        21000, 26000, 15000, 20000, 100, 4321, 1, 0)
    assert got.seen >= got.t
    boss = states.track_of("70")
    got = boss.row(boss.at(START + 10))
    assert got._replace(seen=0) == fr.State(
        START + 10, f32(0.6), f32(0.4), f32(2.3), 990000, BOSS_HP, 0, 0, 0, 0, 0, 0, 0, 0)
    assert got.seen >= got.t


def test_a_state_written_again_is_seen_later(tmp_path):
    """A unit standing still is written again unchanged: it keeps one
    state, whose seen is the last line that wrote it, so a moment's age
    counts from that line, not from when the state began. A state that
    flips and flips back within one millisecond is the one before, seen
    later."""
    lines = opening() + [
        f"{START},BEGIN_COMBAT",
        effect(START + 1000, st(1, x="0.3000")),
        effect(START + 1500, st(1, x="0.3000")),   # the same state again
        effect(START + 2500, st(1, x="0.3000")),   # and again
        effect(START + 4000, st(1, x="0.4000")),   # moved...
        effect(START + 4000, st(1, x="0.3000")),   # ...and back in the same ms
        effect(START + 6000, st(1, x="0.5000")),
        hit(START + 7000, st(2), foe(70, 970000)),  # a fight meets an enemy (#182)
        f"{END},END_COMBAT"]
    _log, path, fights = split_of(tmp_path, lines)
    states = read(fights[0].locator, path)
    one = states.track_of("1")
    mine = [(one.t[i], round(one.x[i], 4), one.seen[i])
            for i in range(len(one)) if one.t[i] >= START]
    assert mine == [(START + 1000, 0.3, START + 4000), (START + 6000, 0.5, START + 6000)]
    ages = {tuple(track.ids): age for track, _state, age in states.moment(START + 3000)}
    assert ages[("1",)] == 0              # written again at 4000, the same state
    ages = {tuple(track.ids): age for track, _state, age in states.moment(START + 5000)}
    assert ages[("1",)] == 1000           # last written at 4000


def test_a_live_log_cut_mid_line_in_the_tail(tmp_path, fight):
    log, _path, locator, _states = fight
    # Cut just before the line's ',*': what is there would parse as a state
    line = effect(END + 800, st(1, x="0.3500"))
    tail_line = log.offset_of(line)
    live = tmp_path / "Encounter.log"
    live.write_bytes(bytes(log.data[:tail_line + len(line.encode()) - 2]))
    states = read(locator, live, "live", locator.session_offset)
    assert states.found_by == "offset" and not states.tail_seen
    assert states.skipped == 0
    one = xs(states.track_of("1"))
    assert 0.34 in one and 0.35 not in one


def test_places_plain_files_first(tmp_path, fight):
    _log, path, locator, _states = fight
    folder = tmp_path / "splits"
    folder.mkdir()
    name = f"{locator.session_stamp}-Kyne's-Aegis-vet"
    split = Path(shutil.copy(path, folder / f"{name}.log"))
    copy = Path(shutil.copy(path, folder / f"{name}-1.log"))
    split_retention.zip_split(copy)
    live = Path(shutil.copy(path, tmp_path / "Encounter.log"))
    archive = Path(shutil.copy(folder / f"{name}-1.log.zip", tmp_path / "Encounter-1.zip"))
    places = fr.places_for(locator, reviewed=split, split_dir=folder, live_log=live,
                           archives=[archive])
    assert [(place.kind, place.path.name, place.hint) for place in places] == [
        ("review", split.name, locator.session_offset), ("live", live.name, 0),
        ("split", f"{name}-1.log.zip", 0), ("archive", archive.name, 0)]
    assert fr.read_fight(locator, places[2:]).found_by == "offset"


def test_places_try_a_live_log_that_is_only_a_guess_after_the_zips(tmp_path, fight):
    """The reviewed file and the session's splits hold the session, zipped
    or not; a live log is only a guess unless the session's BEGIN_LOG is at
    the engine's hint or its first line, and searching a guess back costs
    a read of the whole file. So one of another session is tried after the
    zips, before the archives, and one that holds the session at its hint
    is still tried first."""
    _log, path, locator, from_split = fight
    folder = tmp_path / "splits"
    folder.mkdir()
    name = f"{locator.session_stamp}-Kyne's-Aegis-vet"
    reviewed = Path(shutil.copy(path, tmp_path / f"{name}.log"))
    split_retention.zip_split(reviewed)
    reviewed = Path(f"{reviewed}.zip")
    split_retention.zip_split(Path(shutil.copy(path, folder / f"{name}.log")))
    other = Log().add(standard(EPOCH + HOUR)).save(tmp_path / "Encounter.log")
    archive = Path(shutil.copy(reviewed, tmp_path / "Encounter-1.zip"))
    places = fr.places_for(locator, reviewed=reviewed, split_dir=folder, live_log=other,
                           archives=[archive])
    assert [(place.kind, place.path.name) for place in places] == [
        ("review", reviewed.name), ("split", f"{name}.log.zip"), ("live", other.name),
        ("archive", archive.name)]
    states = fr.read_fight(locator, places)
    assert states.found_by == "offset" and states.source.endswith(reviewed.name)
    same(states, from_split)
    # The live log of which the session is the second: at the hint, first
    log = Log().add(standard(EPOCH - HOUR)).add(standard())
    live = log.save(tmp_path / "Encounter-live.log")
    in_live = next(f.locator for f in replay(live) if f.locator.session_epoch_ms == EPOCH)
    assert in_live.session_offset == log.offset_of(standard()[0]) > 0
    places = fr.places_for(in_live, reviewed=reviewed, live_log=live)
    assert [(place.kind, place.path.name) for place in places] == [
        ("live", live.name), ("review", reviewed.name)]
    states = fr.read_fight(in_live, places)
    assert states.found_by == "offset" and states.source == str(live)
    same(states, from_split)


# --------------------------------------------------------------- thread --

def test_the_runner_reads_on_its_own_thread(fight):
    _log, path, locator, _states = fight
    runner = fr.RereadRunner()
    got = []

    def notify(event):
        got.append((event.kind, event.locator is locator, threading.current_thread().name,
                    event.states.found_by if event.states else event.error))

    runner.request(locator, [fr.Place(path, "split", None, 0)], notify)
    assert runner.wait(10)
    runner.request(locator, [fr.Place(path.with_name("gone.log"), "split")], notify)
    assert runner.wait(10)
    runner.close(5)
    assert got == [("loaded", True, "fight-reread", "offset"),
                   ("missing", True, "fight-reread", "split gone.log: no such file")]


def test_a_request_cancels_the_read_running(fight, monkeypatch):
    _log, path, locator, _states = fight
    started = threading.Event()
    real = fr.read_fight

    def slow(loc, places, cancel=None):
        if loc is first:
            started.set()
            deadline = time.monotonic() + 5
            while not cancel.is_set() and time.monotonic() < deadline:
                time.sleep(0.005)
            # Cancelled only when it was: a runner that never cancels the
            # read running reports this read 'failed', however long it waits
            if not cancel.is_set():
                raise RuntimeError("the read running was never cancelled")
            raise fr.Cancelled()
        return real(loc, places, cancel)

    monkeypatch.setattr(fr, "read_fight", slow)
    first, second = locator, locator._replace()
    runner = fr.RereadRunner()
    got = []
    threads = set()

    def notify(event):
        got.append((event.kind, event.locator is second))
        threads.add(threading.current_thread())

    places = [fr.Place(path, "split", None, 0)]
    runner.request(first, places, notify)
    assert started.wait(10)
    runner.request(second, places, notify)
    assert runner.wait(10)
    runner.close(5)
    assert got == [("cancelled", False), ("loaded", True)]
    assert len(threads) == 1 and next(iter(threads)).name == "fight-reread"


def test_a_read_that_fails_is_reported(fight, monkeypatch):
    _log, path, locator, _states = fight

    def broken(loc, places, cancel=None):
        raise ValueError("bad bytes")

    monkeypatch.setattr(fr, "read_fight", broken)
    runner = fr.RereadRunner()
    got = []
    runner.request(locator, [fr.Place(path, "split")], got.append)
    assert runner.wait(10)
    runner.close(5)
    assert [(event.kind, event.error, event.states) for event in got] == [
        ("failed", "ValueError: bad bytes", None)]
    with pytest.raises(RuntimeError):
        runner.request(locator, [], got.append)


def test_the_runner_outlives_a_notify_that_raises(fight):
    """A receiver that fails (a window's bridge already deleted raises
    RuntimeError) does not end the thread: the next request is answered."""
    _log, path, locator, _states = fight
    runner = fr.RereadRunner()
    places = [fr.Place(path, "split", None, 0)]
    got = []

    def gone(event):
        raise RuntimeError("Internal C++ object already deleted")

    runner.request(locator, places, gone)
    assert runner.wait(10)
    runner.request(locator, places, got.append)
    assert runner.wait(10)
    runner.close(5)
    assert [event.kind for event in got] == ["loaded"]


def test_the_runner_keeps_nothing_of_a_read_while_it_waits(fight, monkeypatch):
    """Once the receiver lets an answer go, its states are freed, while the
    thread lives on waiting for the next request: the positions window
    drops its states on hide, and the loop's names kept the last ones (up
    to 2.2 MB) alive (the review's finding 10)."""
    _log, path, locator, _states = fight

    class States:
        """Stands in for FightStates, which a weak reference cannot
        follow."""

    made = []

    def read(loc, places, cancel=None):
        states = States()
        made.append(weakref.ref(states))
        return states

    monkeypatch.setattr(fr, "read_fight", read)
    runner = fr.RereadRunner()
    got = []
    runner.request(locator, [fr.Place(path, "split")], got.append)
    assert runner.wait(10)
    assert [event.kind for event in got] == ["loaded"] and made[0]() is not None
    got.clear()
    assert runner._thread.is_alive()
    assert made[0]() is None
    runner.request(locator, [fr.Place(path, "split")], got.append)  # it still answers
    assert runner.wait(10)
    runner.close(5)
    assert [event.kind for event in got] == ["loaded"]


def test_a_cancel_stops_a_zipped_read(tmp_path, fight):
    """A zip's member is read through a stream that looks at the cancel on
    every read: read_fight looks first, and the stream's first look (the
    second) stops the read."""
    _log, path, locator, _states = fight
    copy = Path(shutil.copy(path, tmp_path / "261015191452-Kyne's-Aegis-vet.log"))
    split_retention.zip_split(copy)
    with pytest.raises(fr.Cancelled):
        read(locator, Path(f"{copy}.zip"), hint=0, cancel=Looks(2))



def test_a_unit_added_after_end_combat_is_not_the_rows(tmp_path):
    """The table is frozen at END_COMBAT: a unit added in the tail on an id
    a row names (an id handed out again) reads as an unknown unit, not as
    that row's (the review of PR #224)."""
    lines = opening() + [
        monster(START - 500, 88, "Old Add"),
        f"{START},BEGIN_COMBAT",
        hit(START + 1000, st(2), foe(88, 900000)),
        f"{END},END_COMBAT",
        f"{END + 300},UNIT_REMOVED,88",
        monster(END + 600, 88, "New Add"),
        effect(END + 700, foe(88, 500000, x="0.9000")),
    ]
    _log, path, fights = split_of(tmp_path, lines)
    states = read(fights[0].locator, path)
    old = [track for track in states.tracks if track.unit is not None and "88" in track.ids]
    new = [track for track in states.tracks if track.unit is None and track.ids == ("88",)]
    assert len(old) == 1 and max(old[0].t) < END
    assert len(new) == 1 and list(new[0].t) == [END + 700]
