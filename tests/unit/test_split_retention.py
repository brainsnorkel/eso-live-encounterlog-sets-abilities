"""Split log retention: which files, how old, zipping safely (issue #86)."""

import os
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

import split_retention as sr
from esolog_tail import LogFileMonitor, LogSplitter

WEEK = sr.WEEK_SECONDS
NOW = datetime(2026, 10, 27, 12, 0, 0).timestamp()


def _stamp(weeks_ago: float) -> str:
    return datetime.fromtimestamp(NOW - weeks_ago * WEEK).strftime("%y%m%d%H%M%S")


def _split(folder: Path, name: str, weeks_ago: float, text: str = "line\r\n" * 50) -> Path:
    path = folder / name
    path.write_text(text, encoding="utf-8", newline="")
    when = NOW - weeks_ago * WEEK
    os.utime(path, (when, when))
    return path


def _settings(folder: Path, zip_weeks=4, log_path=None) -> sr.RetentionSettings:
    return sr.RetentionSettings(split_dir=folder, log_path=log_path, zip_weeks=zip_weeks)


# ---- names ----

@pytest.mark.parametrize("name, expected", [
    ("260902204127-Dreadsail-Reef-vet.log", ("260902204127", "Dreadsail Reef", True, False)),
    ("260902204127-Dreadsail-Reef-vet-3.log", ("260902204127", "Dreadsail Reef", True, False)),
    ("260301191700-Hel-Ra-Citadel.log.zip", ("260301191700", "Hel Ra Citadel", False, True)),
    ("260301191700-Unknown-Zone.log", ("260301191700", "Unknown Zone", False, False)),
])
def test_splitter_names_parse(name, expected):
    assert sr.parse_split_name(name) == expected


@pytest.mark.parametrize("name", [
    "Encounter.log", "Encounter-260101120000.zip", "Encounter-260101120000-1.zip",
    "260927120455-Aetherian-Archive-report.txt", "260114000000-temp.log",
    "260902204127-Dreadsail-Reef.log.zip.partial", "991399999999-Bad-Stamp.log",
    "notes.log", "260902204127-Dreadsail-Reef.zip",
])
def test_other_files_are_never_selected(name):
    assert sr.parse_split_name(name) is None


def test_scan_skips_subfolders_and_other_files(tmp_path):
    _split(tmp_path, f"{_stamp(10)}-Sunspire-vet.log", 10)
    _split(tmp_path, "Encounter.log", 10)
    _split(tmp_path, f"{_stamp(10)}-Sunspire-vet-report.txt", 10)
    keep = tmp_path / sr.KEEP_FOLDER
    keep.mkdir()
    _split(keep, f"{_stamp(10)}-Cloudrest-vet.log", 10)
    names = [f.path.name for f in sr.scan_splits(tmp_path)]
    assert names == [f"{_stamp(10)}-Sunspire-vet.log"]


# ---- age ----

def test_age_runs_from_the_later_of_stamp_and_mtime(tmp_path):
    # Stamp ten weeks old, but written again a week ago (#85): one week old
    _split(tmp_path, f"{_stamp(10)}-Sunspire-vet.log", 1)
    # Stamp a week old, mtime ten weeks old (copied back): one week old
    _split(tmp_path, f"{_stamp(1)}-Cloudrest-vet.log", 10)
    old = _split(tmp_path, f"{_stamp(10)}-Rockgrove-vet.log", 10)
    due = sr.select_for_zip(sr.scan_splits(tmp_path), 4, NOW)
    assert [f.path for f in due] == [old]


def test_a_protected_session_is_never_due(tmp_path):
    stamp = _stamp(10)
    _split(tmp_path, f"{stamp}-Sunspire-vet.log", 10)
    _split(tmp_path, f"{stamp}-Sunspire-vet-1.log", 10)
    assert sr.select_for_zip(sr.scan_splits(tmp_path), 4, NOW, {stamp}) == []


def test_zipped_splits_are_not_zipped_again(tmp_path):
    _split(tmp_path, f"{_stamp(10)}-Sunspire-vet.log.zip", 10)
    assert sr.select_for_zip(sr.scan_splits(tmp_path), 4, NOW) == []


# ---- zipping ----

def test_zip_round_trip_keeps_content_and_time(tmp_path):
    text = "".join(f"{i},COMBAT_EVENT,x\r\n" for i in range(5000))
    log = _split(tmp_path, f"{_stamp(10)}-Sunspire-vet.log", 10, text)
    mtime = log.stat().st_mtime
    result = sr.zip_split(log)
    target = tmp_path / (log.name + ".zip")
    assert result.kind == "zipped" and result.saved > 0
    assert not log.exists() and target.exists()
    assert abs(target.stat().st_mtime - mtime) < 2
    with zipfile.ZipFile(target) as zf:
        assert zf.namelist() == [log.name]
        assert zf.read(log.name).decode("utf-8") == text
        assert zf.getinfo(log.name).date_time[:3] == time.localtime(mtime)[:3]
    assert sr.zipped_log_size(target) == len(text.encode("utf-8"))


def test_a_failed_check_keeps_the_log(tmp_path, monkeypatch):
    log = _split(tmp_path, f"{_stamp(10)}-Sunspire-vet.log", 10)
    monkeypatch.setattr(sr, "_verify", lambda *a: False)
    result = sr.zip_split(log)
    assert result.kind == "skipped"
    assert log.exists()
    assert list(tmp_path.glob("*.zip*")) == []


def test_cancel_leaves_the_log_and_no_zip(tmp_path):
    log = _split(tmp_path, f"{_stamp(10)}-Sunspire-vet.log", 10)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(sr.Cancelled):
        sr.zip_split(log, cancel)
    assert log.exists()
    assert list(tmp_path.glob("*.zip*")) == []


def test_a_log_that_changes_while_zipped_is_kept(tmp_path, monkeypatch):
    log = _split(tmp_path, f"{_stamp(10)}-Sunspire-vet.log", 10)
    real_verify = sr._verify

    def verify_then_append(*args):
        ok = real_verify(*args)
        with open(log, "a") as f:
            f.write("more\r\n")
        return ok

    monkeypatch.setattr(sr, "_verify", verify_then_append)
    result = sr.zip_split(log)
    assert result.kind == "skipped"
    assert log.exists() and not (tmp_path / (log.name + ".zip")).exists()


def test_same_zip_already_there_removes_the_copy(tmp_path):
    log = _split(tmp_path, f"{_stamp(10)}-Sunspire-vet.log", 10)
    text = log.read_bytes()
    assert sr.zip_split(log).kind == "zipped"
    log.write_bytes(text)  # the same session written out again
    result = sr.zip_split(log)
    assert result.kind == "copy" and not log.exists()


def test_different_zip_already_there_is_left(tmp_path):
    log = _split(tmp_path, f"{_stamp(10)}-Sunspire-vet.log", 10)
    assert sr.zip_split(log).kind == "zipped"
    log.write_text("another session\r\n")
    result = sr.zip_split(log)
    assert result.kind == "skipped" and log.exists()


def test_partials_from_an_interrupted_run_are_removed(tmp_path):
    partial = tmp_path / f"{_stamp(10)}-Sunspire-vet.log.zip.partial"
    partial.write_bytes(b"half")
    other = tmp_path / "Encounter-260101120000.zip.partial"
    other.write_bytes(b"the archiver's")
    assert sr.clean_partials(tmp_path) == 1
    assert not partial.exists() and other.exists()


# ---- a whole run ----

def _log_with_session(folder: Path, weeks_ago: float) -> Path:
    ms = int((NOW - weeks_ago * WEEK) * 1000)
    log = folder / "Encounter.log"
    log.write_text(f'5,BEGIN_LOG,{ms},15,"NA Megaserver","en","eso.live.11.1"\n')
    return log


def test_run_zips_what_is_due_and_spares_the_rest(tmp_path):
    log = _log_with_session(tmp_path, 9)  # the newest session, nine weeks ago
    newest = _split(tmp_path, f"{_stamp(9)}-Sunspire-vet.log", 9)
    old = _split(tmp_path, f"{_stamp(10)}-Rockgrove-vet.log", 10)
    young = _split(tmp_path, f"{_stamp(1)}-Cloudrest-vet.log", 1)
    events = []
    done = sr.run_retention(_settings(tmp_path, log_path=log), events.append, now=NOW)
    assert done.zipped == 1 and not done.skipped
    assert [e.kind for e in events] == ["started", "progress", "completed"]
    assert not old.exists() and (tmp_path / (old.name + ".zip")).exists()
    assert newest.exists() and young.exists() and log.exists()
    assert (tmp_path / sr.KEEP_FOLDER).is_dir()


def test_run_does_nothing_when_off(tmp_path):
    old = _split(tmp_path, f"{_stamp(10)}-Rockgrove-vet.log", 10)
    assert sr.run_retention(_settings(tmp_path, zip_weeks=None), [].append, now=NOW) is None
    assert old.exists()


def test_settings_follow_the_splitters_folder_rule(tmp_path):
    from app_config import AppConfig
    config = AppConfig(path=tmp_path / "config.json")
    config.set("log_path", str(tmp_path / "logs" / "Encounter.log"))
    assert sr.settings_from_config(config).split_dir == tmp_path / "logs"
    assert sr.settings_from_config(config).zip_weeks is None
    config.set("split.dir", str(tmp_path / "splits"))
    config.set("split.zip_enabled", True)
    config.set("split.zip_after_weeks", 6)
    settings = sr.settings_from_config(config)
    assert settings.split_dir == tmp_path / "splits" and settings.zip_weeks == 6


def test_runner_runs_on_its_own_thread(tmp_path):
    old = _split(tmp_path, f"{_stamp(10)}-Rockgrove-vet.log", 10)
    _split(tmp_path, f"{_stamp(1)}-Cloudrest-vet.log", 1)  # the newest, spared
    events = []
    runner = sr.RetentionRunner()
    assert runner.start(_settings(tmp_path, zip_weeks=4), events.append)
    runner.wait(timeout=30)
    assert not runner.running
    assert events[-1].kind == "completed" and not old.exists()


def test_stop_cancels_a_run(tmp_path):
    old = _split(tmp_path, f"{_stamp(10)}-Rockgrove-vet.log", 10, "x" * (20 * 1024 * 1024))
    _split(tmp_path, f"{_stamp(1)}-Cloudrest-vet.log", 1)  # the newest, spared
    runner = sr.RetentionRunner()
    gate = threading.Event()

    def notify(event):
        if event.kind == "progress":
            runner._cancel.set()  # as stop() would, mid-file
        gate.set()

    assert runner.start(_settings(tmp_path, zip_weeks=4), notify)
    runner.wait(timeout=30)
    assert gate.is_set() and old.exists()
    assert list(tmp_path.glob("*.zip*")) == []


# ---- the splitter sees zipped splits ----

def test_splitter_indexes_a_zipped_split_by_its_logs_size(tmp_path):
    log = _split(tmp_path, "260112192756-Maw-of-Lorkhaj-vet.log", 10, "x" * 1000)
    sr.zip_split(log)
    splitter = LogSplitter(tmp_path / "Encounter.log", split_dir=tmp_path)
    assert splitter.existing_splits["260112192756-Maw-of-Lorkhaj-vet"] == {1000}


def test_a_zipped_split_stops_the_session_being_split_again(tmp_path):
    log = _log_with_session(tmp_path, 10)
    stamp = _stamp(10)
    sr.zip_split(_split(tmp_path, f"{stamp}-Sunspire-vet.log", 10))
    # Only the two attributes the check reads; a full monitor would replay the log
    monitor = LogFileMonitor.__new__(LogFileMonitor)
    monitor.log_file = log
    monitor.log_splitter = LogSplitter(log, split_dir=tmp_path)
    assert monitor._session_split_exists(0)
