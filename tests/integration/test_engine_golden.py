#!/usr/bin/env python3
"""
Engine-level golden tests.

Replays tests/fixtures/golden_fight.log through the analysis pipeline and
compares the resulting fight-history data, saved report files, and split
files against tests/fixtures/golden_fight_expected.json.

These tests pin the engine's user-visible analysis results across the
GUI refactor: the data (not any terminal rendering) is the contract.

Regenerate goldens after an intentional behavior change with:
    UPDATE_GOLDENS=1 python -m pytest tests/integration/test_engine_golden.py
"""

import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

FIXTURE_LOG = Path(__file__).parent.parent / 'fixtures' / 'golden_fight.log'
GOLDEN_JSON = Path(__file__).parent.parent / 'fixtures' / 'golden_fight_expected.json'

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub('', text)


def _fight_entry_to_dict(entry) -> dict:
    """Serialize a FightHistoryEntry to comparable primitives.

    Excludes ended_at (wall-clock capture time, nondeterministic).
    """
    return {
        'timestamp': entry.timestamp,
        'zone_name': entry.zone_name,
        'is_vet': entry.is_vet,
        'duration_s': round(entry.duration_s, 3),
        'group_dps': round(entry.group_dps, 1),
        'deaths': entry.deaths,
        'boss_name': entry.boss_name,
        'buff_summary': _strip_ansi(entry.buff_summary or ''),
        'trial_info': entry.trial_info,
        'players': [
            {
                'role': p.get('role'),
                'name': _strip_ansi(str(p.get('name', ''))),
                'class_abbr': p.get('class_abbr'),
                'dps': round(float(p.get('dps') or 0), 1),
                'dmg_pct': round(float(p.get('dmg_pct') or 0), 2),
                'h': p.get('h'),
                'm': p.get('m'),
                's': p.get('s'),
                'sets': _strip_ansi(str(p.get('sets', ''))),
                'skill_lines': _strip_ansi(str(p.get('skill_lines', ''))),
                'front_bar': _strip_ansi(str(p.get('front_bar', ''))),
                'back_bar': _strip_ansi(str(p.get('back_bar', ''))),
            }
            for p in entry.players
        ],
    }


def _replay_pipeline(tmpdir: Path) -> dict:
    """Replay the fixture through analyzer + splitter, return observed results."""
    # Imported here so UPDATE_GOLDENS runs see import errors clearly
    from esolog_tail import ESOLogAnalyzer, LogSplitter, FightHistory
    import esolog_tail as _mod

    reports_dir = tmpdir / 'reports'
    splits_dir = tmpdir / 'splits'
    reports_dir.mkdir()
    splits_dir.mkdir()

    analyzer = ESOLogAnalyzer(save_reports=True, reports_dir=reports_dir)
    analyzer.fight_history = FightHistory()
    analyzer.current_log_file = str(FIXTURE_LOG)

    splitter = LogSplitter(FIXTURE_LOG, split_dir=splits_dir)

    lines = FIXTURE_LOG.read_text(encoding='utf-8').splitlines()
    for line in lines:
        if not line.strip():
            continue
        # Production path (LogFileMonitor._process_new_data) parses with the
        # robust parser on the analyzer, not ESOLogEntry.parse.
        entry = analyzer.log_parser.parse_line(line)
        if entry is None:
            continue
        _mod._handle_replay_log_splitting(splitter, entry, line)
        analyzer.process_log_entry(entry)

    fights = [_fight_entry_to_dict(f) for f in analyzer.fight_history.fights]

    report_files = {}
    for f in sorted(reports_dir.rglob('*')):
        if f.is_file():
            report_files[f.name] = _strip_ansi(f.read_text(encoding='utf-8'))

    split_files = {}
    for f in sorted(splits_dir.rglob('*')):
        if f.is_file():
            content = f.read_bytes()
            split_files[f.name] = {
                'lines': content.decode('utf-8').count('\n'),
                'sha256': hashlib.sha256(content).hexdigest(),
            }

    # Zone report buffers (reports may flush on zone change/END_LOG; capture both)
    zone_reports = {
        zone: [_strip_ansi(l) for l in lines_]
        for zone, lines_ in analyzer.zone_reports.items()
    }

    return {
        'fights': fights,
        'report_files': report_files,
        'split_files': split_files,
        'zone_reports': zone_reports,
    }


class TestEngineGolden(unittest.TestCase):
    """Golden replay of the fixture log through the full engine pipeline."""

    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as td:
            cls.observed = _replay_pipeline(Path(td))
        if os.environ.get('UPDATE_GOLDENS'):
            GOLDEN_JSON.write_text(
                json.dumps(cls.observed, indent=2, sort_keys=True),
                encoding='utf-8',
            )
        cls.expected = json.loads(GOLDEN_JSON.read_text(encoding='utf-8'))

    def test_fixture_produces_fights(self):
        self.assertEqual(len(self.observed['fights']), 2,
                         "fixture should produce exactly two completed fights")

    def test_fight_history_matches_golden(self):
        self.assertEqual(self.observed['fights'], self.expected['fights'])

    def test_report_files_match_golden(self):
        self.assertEqual(self.observed['report_files'], self.expected['report_files'])

    def test_zone_reports_match_golden(self):
        self.assertEqual(self.observed['zone_reports'], self.expected['zone_reports'])

    def test_split_files_match_golden(self):
        self.assertEqual(self.observed['split_files'], self.expected['split_files'])


if __name__ == '__main__':
    unittest.main()
