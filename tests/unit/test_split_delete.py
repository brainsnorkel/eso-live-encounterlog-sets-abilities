"""Deleting old split logs to the Recycle Bin (issue #87)."""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

import recycle_bin
import split_retention as sr

WEEK = sr.WEEK_SECONDS
NOW = datetime(2026, 10, 27, 12, 0, 0).timestamp()


def _stamp(weeks_ago: float) -> str:
    return datetime.fromtimestamp(NOW - weeks_ago * WEEK).strftime("%y%m%d%H%M%S")


def _split(folder: Path, name: str, weeks_ago: float, size: int = 100) -> Path:
    path = folder / name
    path.write_bytes(b"x" * size)
    when = NOW - weeks_ago * WEEK
    os.utime(path, (when, when))
    return path


def _settings(folder, zip_weeks=None, delete_weeks=None, log_path=None):
    return sr.RetentionSettings(split_dir=folder, log_path=log_path,
                                zip_weeks=zip_weeks, delete_weeks=delete_weeks)


class FakeTrash:
    def __init__(self, refuse=()):
        self.moved, self.refuse = [], set(refuse)

    def __call__(self, path):
        if path.name in self.refuse:
            raise recycle_bin.TrashUnavailable("not on a fixed local drive")
        self.moved.append(path.name)
        path.unlink()


# ---- the plan ----

def test_delete_takes_plain_and_zipped_and_zip_takes_the_rest(tmp_path):
    very_old = _split(tmp_path, f"{_stamp(60)}-Sunspire-vet.log", 60)
    very_old_zip = _split(tmp_path, f"{_stamp(58)}-Cloudrest-vet.log.zip", 58)
    old = _split(tmp_path, f"{_stamp(10)}-Rockgrove-vet.log", 10)
    _split(tmp_path, f"{_stamp(1)}-Dreadsail-Reef-vet.log", 1)
    work = sr.plan(sr.scan_splits(tmp_path), 4, 52, NOW, set())
    assert [f.path for f in work.delete] == [very_old, very_old_zip]
    assert [f.path for f in work.zip] == [old]


def test_the_newest_session_in_the_folder_is_spared(tmp_path):
    only = _split(tmp_path, f"{_stamp(60)}-Sunspire-vet.log", 60)
    copy = _split(tmp_path, f"{_stamp(60)}-Sunspire-vet-1.log", 60)
    work = sr.plan(sr.scan_splits(tmp_path), 4, 52, NOW, set())
    assert work.delete == [] and work.zip == []
    assert only.exists() and copy.exists()


def test_settings_keep_m_above_n_even_when_hand_edited(tmp_path):
    from app_config import AppConfig
    config = AppConfig(path=tmp_path / "config.json")
    config.set("log_path", str(tmp_path / "Encounter.log"))
    config.set("split.zip_enabled", True)
    config.set("split.zip_after_weeks", 8)
    config.set("split.delete_enabled", True)
    config.set("split.delete_after_weeks", 4)
    settings = sr.settings_from_config(config)
    assert (settings.zip_weeks, settings.delete_weeks) == (8, 9)
    config.set("split.zip_enabled", False)
    assert sr.settings_from_config(config).delete_weeks == 4
    config.set("split.delete_enabled", False)
    assert not sr.settings_from_config(config).active


# ---- a run ----

def test_run_deletes_only_the_splitters_files(tmp_path):
    keep = tmp_path / sr.KEEP_FOLDER
    keep.mkdir()
    survivors = [
        _split(tmp_path, "Encounter.log", 60),
        _split(tmp_path, "Encounter-250101120000.zip", 60),
        _split(tmp_path, f"{_stamp(60)}-Sunspire-vet-report.txt", 60),
        _split(tmp_path, f"{_stamp(60)}-temp.log", 60),
        _split(keep, f"{_stamp(60)}-Kynes-Aegis-vet.log", 60),
        _split(tmp_path, f"{_stamp(0.5)}-Ossein-Cage-vet.log", 0.5),  # the newest
    ]
    doomed = [_split(tmp_path, f"{_stamp(w)}-Hel-Ra-Citadel-vet.log", w) for w in (3, 5)]
    trash = FakeTrash()
    done = sr.run_retention(_settings(tmp_path, delete_weeks=1), [].append, now=NOW, trash=trash)
    assert done.deleted == 2 and done.freed == 200
    assert sorted(trash.moved) == sorted(p.name for p in doomed)
    assert all(p.exists() for p in survivors)


def test_a_file_the_bin_refuses_is_kept_and_reported(tmp_path):
    refused = _split(tmp_path, f"{_stamp(60)}-Sunspire-vet.log", 60)
    taken = _split(tmp_path, f"{_stamp(59)}-Cloudrest-vet.log", 59)
    _split(tmp_path, f"{_stamp(1)}-Rockgrove-vet.log", 1)
    trash = FakeTrash(refuse={refused.name})
    done = sr.run_retention(_settings(tmp_path, delete_weeks=52), [].append, now=NOW, trash=trash)
    assert done.deleted == 1 and not taken.exists()
    assert refused.exists()
    assert done.skipped == [f"{refused.name}: not on a fixed local drive"]


def test_run_deletes_first_then_zips(tmp_path):
    _split(tmp_path, f"{_stamp(60)}-Sunspire-vet.log", 60)
    _split(tmp_path, f"{_stamp(10)}-Cloudrest-vet.log", 10)
    _split(tmp_path, f"{_stamp(1)}-Rockgrove-vet.log", 1)
    events = []
    done = sr.run_retention(_settings(tmp_path, zip_weeks=4, delete_weeks=52), events.append,
                            now=NOW, trash=FakeTrash())
    actions = [e.action for e in events if e.kind == "progress"]
    assert actions == ["delete", "zip"]
    assert (done.deleted, done.zipped) == (1, 1)


def test_the_live_logs_newest_session_is_never_deleted(tmp_path):
    ms = int((NOW - 60 * WEEK) * 1000)
    log = tmp_path / "Encounter.log"
    log.write_text(f'5,BEGIN_LOG,{ms},15,"NA Megaserver","en","eso.live.11.1"\n')
    newest_in_log = _split(tmp_path, f"{_stamp(60)}-Sunspire-vet.log", 60)
    older = _split(tmp_path, f"{_stamp(61)}-Cloudrest-vet.log", 61)
    _split(tmp_path, f"{_stamp(1)}-Ossein-Cage-vet.log", 1)  # newest in the folder
    sr.run_retention(_settings(tmp_path, delete_weeks=52, log_path=log), [].append,
                     now=NOW, trash=FakeTrash())
    assert newest_in_log.exists() and not older.exists()


# ---- the question ----

def test_summary_and_question_name_zones_dates_and_every_file(tmp_path):
    files = [_split(tmp_path, f"{_stamp(60 + i)}-Dreadsail-Reef-vet.log", 60 + i, 1024 ** 2)
             for i in range(3)]
    files.append(_split(tmp_path, f"{_stamp(70)}-Sunspire.log.zip", 70, 1024))
    summary = sr.summarize(sr.scan_splits(tmp_path))
    assert summary.count == 4
    assert summary.groups[0] == ("Dreadsail Reef (vet)", 3, 3 * 1024 ** 2)
    assert summary.groups[1] == ("Sunspire", 1, 1024)
    question, details, names = sr.describe_deletion(summary, "Recycle Bin")
    assert question == "Move 4 split logs (3 MB) to the Recycle Bin?"
    assert details.startswith(f"Sessions from {summary.first} to {summary.last}:")
    assert "Dreadsail Reef (vet) — 3 sessions, 3 MB" in details
    assert "keep folder" in details
    assert names.splitlines() == sorted(p.name for p in files)


def test_question_folds_the_smallest_zones(tmp_path):
    for i in range(15):
        _split(tmp_path, f"{_stamp(60 + i)}-Zone-{chr(65 + i)}.log", 60 + i, 1000 + i)
    summary = sr.summarize(sr.scan_splits(tmp_path))
    _, details, _ = sr.describe_deletion(summary, "trash", shown_groups=12)
    assert "and 3 more zones, 3 sessions" in details


# ---- the Recycle Bin ----

@pytest.mark.skipif(sys.platform != "win32", reason="the Windows shell path")
def test_windows_never_asks_the_shell_for_a_file_the_bin_refuses(tmp_path, monkeypatch):
    path = _split(tmp_path, f"{_stamp(60)}-Sunspire-vet.log", 60)
    monkeypatch.setattr(recycle_bin, "refusal", lambda p, size: "not on a fixed local drive")
    called = []
    monkeypatch.setattr(recycle_bin, "_shell32",
                        type("Shell", (), {"SHFileOperationW": lambda *a: called.append(a)})())
    with pytest.raises(recycle_bin.TrashUnavailable, match="fixed local drive"):
        recycle_bin.move_to_trash(path)
    assert called == [] and path.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows shell path")
def test_windows_refuses_a_file_larger_than_the_bins_limit(tmp_path):
    path = _split(tmp_path, f"{_stamp(60)}-Sunspire-vet.log", 60)
    assert recycle_bin.refusal(path, 1) is None
    assert "limit" in recycle_bin.refusal(path, 1 << 50)


@pytest.mark.skipif(sys.platform == "win32", reason="send2trash is for Linux and macOS")
def test_elsewhere_send2trash_failures_keep_the_file(tmp_path, monkeypatch):
    pytest.importorskip("send2trash")
    import send2trash
    path = _split(tmp_path, f"{_stamp(60)}-Sunspire-vet.log", 60)

    def refuse(name):
        raise send2trash.TrashPermissionError(name)

    monkeypatch.setattr(send2trash, "send2trash", refuse)
    with pytest.raises(recycle_bin.TrashUnavailable):
        recycle_bin.move_to_trash(path)
    assert path.exists()
