#!/usr/bin/env python3
"""Mid-session attach must backfill the session's player roster."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from esolog_tail import ESOLogAnalyzer, FightHistory, LogFileMonitor

EPOCH = 1755729685851

PREAMBLE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.11.1"',
    '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1708524619155578000,50,787,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,2,1,"Sorc Friend","@sorc",1708524619155578001,50,787,0,PLAYER_ALLY,T',
    '2100,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/x.dds",F,F',
    '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
    '3000,PLAYER_INFO,1,[45549,45557],[1,1],[[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,MAGICKA,T,16,LEGENDARY]],[12345,25267],[39028,86169]',
    '3100,PLAYER_INFO,2,[45549,45557],[1,1],[[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,MAGICKA,T,16,LEGENDARY]],[12345,25267],[39028,86169]',
]

OLD_FIGHT = [
    '10000,BEGIN_COMBAT',
    '11000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,90000,0,4021667,12345,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5,70,105634/105634,0/0,0/0,0/0,0/0,0,0.4,0.5,0.0',
    '70000,END_COMBAT',
]

NEW_FIGHT = [
    '100000,BEGIN_COMBAT',
    '101000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,60000,0,4021667,12345,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5,70,105634/105634,0/0,0/0,0/0,0/0,0,0.4,0.5,0.0',
    '111000,COMBAT_EVENT,DAMAGE,PHYSICAL,2,15000,0,4021700,12345,2,20000/20000,30000/30000,12000/12000,500/500,1000/1000,0,0.2,0.5,5.5,70,45634/105634,0/0,0/0,0/0,0/0,0,0.4,0.5,0.0',
    '130000,END_COMBAT',
]


class TestPreambleBackfill(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / 'Encounter.log'

    def tearDown(self):
        self.tmp.cleanup()

    def _attach_and_fight(self, split_dir=None):
        """Attach a tail-mode monitor at current EOF, then append a fight."""
        analyzer = ESOLogAnalyzer()
        analyzer.fight_history = FightHistory()
        monitor = LogFileMonitor(analyzer, self.log,
                                 tail_and_split=split_dir is not None,
                                 split_dir=split_dir)
        with open(self.log, 'a', encoding='utf-8') as f:
            for line in NEW_FIGHT:
                f.write(line + '\n')
        monitor._process_new_lines()
        return analyzer

    def test_mid_session_attach_replays_session(self):
        """A mid-session attach loads the session's fights and roster."""
        self.log.write_text('\n'.join(PREAMBLE + OLD_FIGHT) + '\n',
                            encoding='utf-8')
        analyzer = self._attach_and_fight()
        fights = analyzer.fight_history.fights
        # The pre-attach fight is loaded into history, plus the new one
        self.assertEqual(len(fights), 2)
        for fight in fights:
            names = sorted(p.get('name') for p in fight.players)
            self.assertIn('@brainsnorkel', names)
        self.assertEqual(analyzer.current_zone, 'Coral Aerie')
        # Epoch learned from the replayed BEGIN_LOG
        self.assertEqual(analyzer.log_start_unix_timestamp, EPOCH // 1000)

    def test_missing_split_created_at_attach(self):
        """The Dreadsail case: session had no split; attach creates it."""
        self.log.write_text('\n'.join(PREAMBLE + OLD_FIGHT) + '\n',
                            encoding='utf-8')
        split_dir = Path(self.tmp.name) / 'splits'
        split_dir.mkdir()
        self._attach_and_fight(split_dir=split_dir)
        import datetime
        stamp = datetime.datetime.fromtimestamp(EPOCH / 1000).strftime('%y%m%d%H%M%S')
        splits = list(split_dir.glob(f'{stamp}*.log'))
        self.assertEqual(len(splits), 1)
        content = splits[0].read_text(encoding='utf-8')
        self.assertIn('BEGIN_LOG', content)
        self.assertIn('BEGIN_COMBAT', content)

    def test_existing_split_not_duplicated(self):
        self.log.write_text('\n'.join(PREAMBLE + OLD_FIGHT) + '\n',
                            encoding='utf-8')
        split_dir = Path(self.tmp.name) / 'splits'
        split_dir.mkdir()
        import datetime
        stamp = datetime.datetime.fromtimestamp(EPOCH / 1000).strftime('%y%m%d%H%M%S')
        existing = split_dir / f'{stamp}-Coral-Aerie-vet.log'
        existing.write_text('partial split from earlier run\n', encoding='utf-8')
        self._attach_and_fight(split_dir=split_dir)
        # No new split for the session stamp; the existing file is untouched
        splits = sorted(split_dir.glob(f'{stamp}*'))
        self.assertEqual(splits, [existing])
        self.assertIn('partial split', existing.read_text(encoding='utf-8'))

    def test_oversized_session_falls_back_to_roster_sweep(self):
        self.log.write_text('\n'.join(PREAMBLE + OLD_FIGHT) + '\n',
                            encoding='utf-8')
        from unittest.mock import patch
        with patch.object(LogFileMonitor, 'SESSION_REPLAY_CAP', 10):
            analyzer = self._attach_and_fight()
        fights = analyzer.fight_history.fights
        # Old combat is not replayed, but the roster is still known
        self.assertEqual(len(fights), 1)
        self.assertEqual(sorted(p.get('name') for p in fights[0].players),
                         ['@brainsnorkel', '@templar'])

    def test_no_begin_log_still_sweeps_roster(self):
        """Fallback: roster events are swept even without a reachable BEGIN_LOG."""
        self.log.write_text('\n'.join(PREAMBLE[1:] + OLD_FIGHT) + '\n',
                            encoding='utf-8')
        analyzer = self._attach_and_fight()
        fights = analyzer.fight_history.fights
        self.assertEqual(len(fights), 1)
        self.assertEqual(sorted(p.get('name') for p in fights[0].players),
                         ['@brainsnorkel', '@templar'])

    def test_empty_log_attach_is_harmless(self):
        self.log.write_text('', encoding='utf-8')
        analyzer = ESOLogAnalyzer()
        analyzer.fight_history = FightHistory()
        LogFileMonitor(analyzer, self.log)  # must not raise


if __name__ == '__main__':
    unittest.main()
