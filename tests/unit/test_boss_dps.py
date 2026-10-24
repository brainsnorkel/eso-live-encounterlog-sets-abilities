#!/usr/bin/env python3
"""Each player's dps against the boss sits beside their total.

The game flags a boss on UNIT_ADDED (isBoss). Damage to any unit so
flagged is the player's boss damage; the rest of their damage went to
adds. A fight without a boss shows the total alone. The lines here have
the shape of Chris's trial logs (see test_pet_damage).
"""

import unittest

from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory
from fight_history import FightHistoryEntry
from gui.fight_render import render_html, render_plain_text

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
ADD_HEALTH = 50000
PET_HEALTH = 45478
ABILITY = 12345


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _monster(unit_id, health, max_health):
    return f"{unit_id},{health}/{max_health},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _pet(unit_id):
    return _monster(unit_id, PET_HEALTH, PET_HEALTH)


def _hit(ts, source, damage, target, result='DAMAGE'):
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{damage},0,900,{ABILITY},"
            f"{source},{target}")


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    f'2600,ABILITY_INFO,{ABILITY},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
]
BOSS = f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F'
ADD = f'2500,UNIT_ADDED,71,MONSTER,F,0,{ADD_HEALTH},F,0,0,"Lesser Sea Adder","",0,50,160,0,HOSTILE,F'
# Player 1's pet, summoned before the pull
PET = f'3000,UNIT_ADDED,90,MONSTER,F,0,{PET_HEALTH},F,0,0,"Blighted Blastbones","",0,50,160,1,NPC_ALLY,F'

FIGHT_START = [
    '10000,BEGIN_COMBAT',
    *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2)],
]
FIGHT_END = ['30000,END_COMBAT']  # a twenty-second fight


def _run(lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer.fight_history.fights[0]


class TestBossDps(unittest.TestCase):

    def test_boss_and_total_dps_per_player(self):
        fight = _run([BOSS, ADD, PET] + FIGHT_START + [
            # Player 1 hits the boss, their pet hits the add
            _hit(11000, _player(1), 200000, _monster(70, 800000, BOSS_HEALTH)),
            _hit(12000, _pet(90), 20000, _monster(71, 30000, ADD_HEALTH)),
            # Player 2 hits the add, then the boss
            _hit(13000, _player(2), 30000, _monster(71, 0, ADD_HEALTH)),
            _hit(14000, _player(2), 100000, _monster(70, 700000, BOSS_HEALTH)),
        ] + FIGHT_END)
        by_unit = {p['unit_id']: p for p in fight.players}
        # Each figure divides by its own dps time, first hit to last and a
        # second at least (see damage_stats): player 1's two hits span a
        # second and their one boss hit gets the floor, player 2 likewise;
        # the group's hits span three seconds, as do its hits on the boss
        self.assertEqual(by_unit['1']['dps'], 220000.0)
        self.assertEqual(by_unit['1']['boss_dps'], 200000.0)
        self.assertEqual(by_unit['2']['dps'], 130000.0)
        self.assertEqual(by_unit['2']['boss_dps'], 100000.0)
        self.assertAlmostEqual(fight.group_dps, 350000 / 3)
        self.assertAlmostEqual(fight.group_boss_dps, 300000 / 3)
        self.assertAlmostEqual(fight.dps_time_s, 3.0)
        self.assertAlmostEqual(fight.boss_dps_time_s, 3.0)
        # Shares of the group's damage, and of its damage to the boss
        self.assertAlmostEqual(by_unit['1']['dmg_pct'], 220000 / 350000 * 100)
        self.assertAlmostEqual(by_unit['1']['boss_pct'], 200000 / 300000 * 100)
        self.assertAlmostEqual(by_unit['2']['boss_pct'], 100000 / 300000 * 100)

    def test_players_rank_by_boss_damage_then_all_damage(self):
        # Player 2 deals more damage in all (to the add) but less to the
        # boss: player 1 ranks first
        fight = _run([BOSS, ADD] + FIGHT_START + [
            _hit(11000, _player(1), 100000, _monster(70, 900000, BOSS_HEALTH)),
            _hit(12000, _player(2), 40000, _monster(70, 860000, BOSS_HEALTH)),
            _hit(13000, _player(2), 200000, _monster(71, 0, ADD_HEALTH)),
        ] + FIGHT_END)
        self.assertEqual([p['unit_id'] for p in fight.players], ['1', '2'])
        self.assertGreater(fight.players[1]['dps'], fight.players[0]['dps'])
        # No boss: all damage decides
        fight = _run([ADD] + FIGHT_START + [
            _hit(11000, _player(1), 10000, _monster(71, 40000, ADD_HEALTH)),
            _hit(12000, _player(2), 30000, _monster(71, 10000, ADD_HEALTH)),
        ] + FIGHT_END)
        self.assertEqual([p['unit_id'] for p in fight.players], ['2', '1'])

    def test_every_damaging_result_counts(self):
        """DoT ticks, blocked hits and shield absorbs are damage; a hit the
        target was immune to, and overkill, are not (see DAMAGE_RESULTS)."""
        boss = _monster(70, 900000, BOSS_HEALTH)
        fight = _run([BOSS] + FIGHT_START + [
            _hit(11000, _player(1), 100000, boss),
            _hit(12000, _player(1), 50000, boss, 'CRITICAL_DAMAGE'),
            _hit(13000, _player(1), 20000, boss, 'DOT_TICK'),
            _hit(14000, _player(1), 30000, boss, 'DOT_TICK_CRITICAL'),
            _hit(15000, _player(1), 5000, boss, 'BLOCKED_DAMAGE'),
            _hit(16000, _player(1), 15000, boss, 'DAMAGE_SHIELDED'),
            _hit(17000, _player(1), 40000, boss, 'IMMUNE'),
            _hit(18000, _player(1), 40000, boss, 'REFLECTED'),
            # 20,000 of this hit is overflow past the boss's remaining health
            (f"19000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,20000,20000,900,{ABILITY},"
             f"{_player(1)},{_monster(70, 0, BOSS_HEALTH)}"),
        ] + FIGHT_END)
        by_unit = {p['unit_id']: p for p in fight.players}
        # The counted hits span 11000 to 19000: the immune and reflected
        # ones in between neither count nor stretch the dps time
        self.assertEqual(by_unit['1']['dps'], 240000 / 8)
        self.assertEqual(by_unit['1']['boss_dps'], 240000 / 8)
        self.assertEqual(fight.group_dps, 240000 / 8)

    def test_a_fight_without_a_boss_has_no_boss_dps(self):
        fight = _run([ADD] + FIGHT_START + [
            _hit(11000, _player(1), 20000, _monster(71, 30000, ADD_HEALTH)),
        ] + FIGHT_END)
        self.assertEqual(fight.group_boss_dps, 0)
        self.assertEqual([p['boss_dps'] for p in fight.players], [0, 0])


def _entry(boss_dps):
    entry = FightHistoryEntry()
    entry.zone_name = 'Dreadsail Reef'
    entry.timestamp = '2025-08-21 09:21:25'
    entry.duration_s = 20.0
    entry.group_dps = 17500.0
    entry.group_boss_dps = boss_dps * 1.5  # another player's boss hits
    entry.players = [{
        'role': 'D', 'name': '@tester', 'class_abbr': 'NB', 'dps': 11000.0,
        'boss_dps': boss_dps, 'dmg_pct': 62.9, 'boss_pct': 66.7 if boss_dps else 0,
        'h': 20000, 'm': 30000,
        's': 15000, 'unit_id': '1', 'sets': [], 'skill_lines': [],
        'front_bar': [], 'back_bar': [], 'front_bar_slots': [], 'back_bar_slots': [],
    }]
    return entry


class TestBossDpsRendering(unittest.TestCase):

    def test_boss_fight_reads_boss_over_total(self):
        entry = _entry(10000.0)
        self.assertIn('10.0k / 11.0k', render_html(entry, detailed=False))
        # The group figure is the link to the dps over time graph, its glyph
        # inside the anchor after the unit
        self.assertIn('>15.0k / 17.5k gdps&nbsp;<img src="glyph:graph?',
                      render_html(entry, detailed=False))
        # The share cell reads the same way: of the boss damage, of all damage
        self.assertIn('66.7% / 62.9%', render_html(entry, detailed=False))
        self.assertIn('— 10.0k / 11.0k (66.7% / 62.9%)', render_plain_text(entry))

    def test_trash_fight_reads_the_total_alone(self):
        entry = _entry(0.0)
        html = render_html(entry, detailed=False)
        self.assertIn('>11.0k&nbsp;<img src="glyph:breakdown?', html)
        self.assertNotIn(' / ', html)
        self.assertIn('— 11.0k (62.9%)', render_plain_text(entry))


if __name__ == '__main__':
    unittest.main()
