"""Recent activity (issue #191): which files, their order, their times."""

import os
from datetime import datetime
from pathlib import Path

import pytest

import recent_activity as ra


def _touch(path: Path, when: datetime, text: bytes = b"x" * 10) -> Path:
    path.write_bytes(text)
    os.utime(path, (when.timestamp(), when.timestamp()))
    return path


# ---- names ----

@pytest.mark.parametrize("name, stamp", [
    ("Encounter-261102210000.zip", "261102210000"),
    ("Encounter-261102210000-1.zip", "261102210000"),
    ("Encounter-261102210000-12.zip", "261102210000"),
])
def test_archive_names_parse(name, stamp):
    assert ra.parse_archive_stamp(name) == stamp


@pytest.mark.parametrize("name", [
    "Encounter.zip", "Encounter.7z", "Encounter.log", "Encounter-jabs.log",
    "Encounter-261102210000.zip.partial", "Encounter-991399999999.zip",
    "Encounter-2611022100.zip", "260902204127-Dreadsail-Reef-vet.log.zip",
    "20251004-ArchiveEncounter.log", "encounter-261102210000.zip",
])
def test_other_files_are_not_archives(name):
    assert ra.parse_archive_stamp(name) is None


# ---- folders ----

def test_archive_folder_is_the_one_set_else_the_logs_own(tmp_path):
    log = tmp_path / "Logs" / "Encounter.log"
    assert ra.archive_folder("", log) == tmp_path / "Logs"
    assert ra.archive_folder(str(tmp_path / "zips"), log) == tmp_path / "zips"
    assert ra.archive_folder("", None) is None


# ---- archives ----

def test_archives_newest_made_first_with_the_logs_last_entry(tmp_path):
    older = _touch(tmp_path / "Encounter-261027194400.zip", datetime(2026, 10, 27, 21, 14))
    newer = _touch(tmp_path / "Encounter-261102204800.zip", datetime(2026, 11, 2, 21, 0), b"y" * 20)
    # A copy made later but of an older session sorts by when it was made
    copy = _touch(tmp_path / "Encounter-261027194400-1.zip", datetime(2026, 11, 3, 8, 0))
    _touch(tmp_path / "Encounter.log", datetime(2026, 11, 3, 9, 0))
    _touch(tmp_path / "Encounter.zip", datetime(2026, 11, 3, 9, 0))
    (tmp_path / "sub").mkdir()
    _touch(tmp_path / "sub" / "Encounter-261101000000.zip", datetime(2026, 11, 1))

    found = ra.scan_archives(tmp_path)
    assert [a.path for a in found] == [copy, newer, older]
    assert found[1].made == datetime(2026, 11, 2, 21, 0)
    assert found[1].last_entry == datetime(2026, 11, 2, 20, 48)
    assert found[1].size == 20


def test_an_archive_with_an_unreadable_time_is_left_out(tmp_path, monkeypatch):
    good = _touch(tmp_path / "Encounter-261102204800.zip", datetime(2026, 11, 2, 21, 0))
    bad = _touch(tmp_path / "Encounter-261027194400.zip", datetime(2026, 10, 27, 21, 14))
    bad_mtime = bad.stat().st_mtime

    class Clock(datetime):
        @classmethod
        def fromtimestamp(cls, value, *args, **kwargs):
            if value == bad_mtime:
                raise OSError(22, "Invalid argument")  # Windows, a time before 1970
            return datetime.fromtimestamp(value, *args, **kwargs)

    monkeypatch.setattr(ra, "datetime", Clock)
    assert [a.path for a in ra.scan_archives(tmp_path)] == [good]


def test_missing_folders_give_nothing(tmp_path):
    assert ra.scan_archives(tmp_path / "nowhere") == []
    assert ra.scan_archives(None) == []
    assert ra.recent_splits(None) == []
    activity = ra.scan(None, tmp_path / "nowhere")
    assert not activity
    assert activity.newest_archive is None


# ---- the two lists ----

def test_scan_lists_five_of_each_newest_first(tmp_path):
    stamps = [f"2610{day:02d}200000" for day in range(1, 8)]  # 7 sessions
    for stamp in stamps:
        _touch(tmp_path / f"Encounter-{stamp}.zip", datetime.strptime(stamp, "%y%m%d%H%M%S"))
        _touch(tmp_path / f"{stamp}-Sunspire-vet.log", datetime(2026, 1, 1))  # rewritten long ago
    _touch(tmp_path / "261008200000-Dreadsail-Reef.log.zip", datetime(2026, 10, 8))
    _touch(tmp_path / "261009200000-temp.log", datetime(2026, 10, 9))  # still waiting for its zone
    _touch(tmp_path / "261009200000-Sunspire-vet-report.txt", datetime(2026, 10, 9))

    activity = ra.scan(tmp_path, tmp_path)
    assert activity
    assert len(activity.archives) == 5
    assert [a.path.name for a in activity.archives][:2] == [
        "Encounter-261007200000.zip", "Encounter-261006200000.zip"]
    assert activity.newest_archive.path.name == "Encounter-261007200000.zip"
    # Splits by their session stamp, newest first, whatever the file time
    assert len(activity.splits) == 5
    assert [s.stamp for s in activity.splits] == [
        "261008200000", "261007200000", "261006200000", "261005200000", "261004200000"]
    assert activity.splits[0].zipped and activity.splits[0].zone == "Dreadsail Reef"
    assert ra.split_time(activity.splits[0]) == datetime(2026, 10, 8, 20, 0)
    assert activity.archive_dir == tmp_path and activity.split_dir == tmp_path
    # All of them are counted, not only the five shown
    assert (activity.archive_count, activity.archive_bytes) == (7, 70)
    assert (activity.split_count, activity.split_bytes) == (8, 80)


def test_scan_count_can_be_changed(tmp_path):
    for day in range(1, 4):
        _touch(tmp_path / f"2610{day:02d}200000-Sunspire.log", datetime(2026, 10, day))
    assert len(ra.scan(None, tmp_path, count=2).splits) == 2


# ---- dates ----

def test_format_when_reads_as_a_date_and_a_time():
    assert ra.format_when(datetime(2026, 11, 2, 21, 14, 5)) == "2 Nov 2026, 21:14"
    assert ra.format_when(datetime(2026, 1, 12, 9, 5)) == "12 Jan 2026, 09:05"
