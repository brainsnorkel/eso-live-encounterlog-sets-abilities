"""The skill target table is found in a frozen build (issue #237): its path
comes from ability_icons.bundle_root(), which reads sys._MEIPASS."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import damage_kinds  # noqa: E402


def test_table_loads_from_meipass(tmp_path, monkeypatch):
    skills = tmp_path / "data" / "skills"
    skills.mkdir(parents=True)
    (skills / "ability_targets.json").write_text(
        json.dumps({"area": ["999001"], "single": ["999002"]}), encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    damage_kinds.reset_target_table()
    try:
        assert damage_kinds.target_table_path() == skills / "ability_targets.json"
        assert damage_kinds.table_target("999001") == "area"
        assert damage_kinds.table_target("999002") == "single"
    finally:
        damage_kinds.reset_target_table()


def test_table_path_is_repo_data_from_source(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    repo = Path(__file__).resolve().parents[2]
    assert damage_kinds.target_table_path() == repo / "data" / "skills" / "ability_targets.json"
