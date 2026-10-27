"""Opening a log for review: plain, a zipped split, an archive (issue #86)."""

import zipfile
from pathlib import Path

import pytest

from log_open import NoLogInZip, is_zip, log_members, open_log_text

FIXTURE_LOG = Path(__file__).parent.parent / "fixtures" / "golden_fight.log"


def _zip(path: Path, members: dict) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in members.items():
            zf.writestr(name, text)
    return path


def test_plain_log_reads_as_before():
    with open_log_text(FIXTURE_LOG) as (f, total, shown):
        text = f.read()
    assert total == FIXTURE_LOG.stat().st_size
    assert shown == str(FIXTURE_LOG)
    assert text == FIXTURE_LOG.read_text(encoding="utf-8", errors="ignore")


def test_zipped_split_streams_its_log_with_the_logs_size(tmp_path):
    raw = FIXTURE_LOG.read_bytes()
    path = _zip(tmp_path / "260902204127-Dreadsail-Reef-vet.log.zip",
                {"260902204127-Dreadsail-Reef-vet.log": raw})
    with open_log_text(path) as (f, total, shown):
        lines = list(f)
    assert total == len(raw)  # the member's size, not the zip's
    assert shown == str(path)
    assert "".join(lines) == raw.decode("utf-8", errors="ignore").replace("\r\n", "\n")


def test_archive_with_one_log_opens_by_content_not_name(tmp_path):
    path = _zip(tmp_path / "Encounter-260101120000.dat", {"Encounter.log": "a\nb\n"})
    assert is_zip(path)
    with open_log_text(path) as (f, total, _):
        assert f.read() == "a\nb\n" and total == 4


def test_several_logs_need_a_choice(tmp_path):
    path = _zip(tmp_path / "two.zip", {"a.log": "A\n", "notes.txt": "x", "b.log": "B\n"})
    assert log_members(path) == ["a.log", "b.log"]
    with pytest.raises(NoLogInZip), open_log_text(path):
        pass
    with open_log_text(path, "b.log") as (f, _, shown):
        assert f.read() == "B\n" and shown.endswith("› b.log")


def test_a_zip_without_a_log_says_so(tmp_path):
    path = _zip(tmp_path / "pictures.zip", {"a.png": b"png"})
    with pytest.raises(NoLogInZip, match="no encounter log"), open_log_text(path):
        pass
