#!/usr/bin/env python3
"""A companion has a row of its own under its owner (issue #74).

The lines have the shape of the real ones (two solo Moon Hunter Keep logs
of 2026-10-26 and the trial logs surveyed for companions.py): the logging
player's own companion is a MONSTER with reaction COMPANION and its owner
set; another member's is FRIENDLY with owner 0 until a UNIT_CHANGED names
the owner; a re-summoned companion has a new unit id.
"""

import tempfile
import unittest
from pathlib import Path

from app_config import DEFAULTS, AppConfig
from app_startup import build_analyzer
from engine_events import RecordingListener
from esolog_tail import COMBAT_RESUME_MS, ESOLogAnalyzer, FightHistory
from gui.build_render import build_title, render_build_html
from gui.damage_render import render_damage_html
from gui.fight_render import (
    COMPANION_INDENT,
    build_href,
    damage_href,
    render_html,
    render_plain_text,
)

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
ABILITY = 12345
ISOBEL = "106616"
BEAM = 163684
LIGHT_ATTACK = 157069


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _boss(health, unit_id=70):
    return f"{unit_id},{health}/{BOSS_HEALTH},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _companion(unit_id, health=33000):
    return f"{unit_id},{health}/33000,0/0,0/0,0/0,0/0,0,0.3,0.4,1.0"


def _companion_added(ts, unit_id, owner, reaction="COMPANION", monster=ISOBEL,
                     name="Isobel Veloise", level=20):
    return (f'{ts},UNIT_ADDED,{unit_id},MONSTER,F,0,{monster},F,0,0,"{name}","",'
            f'0,{level},0,{owner},{reaction},F')


def _unit_changed(ts, unit_id, name, owner, reaction="FRIENDLY"):
    return f'{ts},UNIT_CHANGED,{unit_id},0,0,"{name}","",0,20,0,{owner},{reaction},F'


def _hit(ts, source_state, damage, boss_health_after, ability=ABILITY):
    return (f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{damage},0,900,{ability},"
            f"{source_state},{_boss(boss_health_after)}")


def _heal(ts, source_state, value, target_state):
    return f"{ts},COMBAT_EVENT,HEAL,MAGIC,1,{value},0,901,{ABILITY},{source_state},{target_state}"


def _cast(ts, source_state, ability):
    return f"{ts},BEGIN_CAST,0,F,{ts},{ability},{source_state},{_boss(BOSS_HEALTH)}"


def _died(ts, unit_state):
    return f"{ts},COMBAT_EVENT,DIED,GENERIC,0,0,0,0,0,{_boss(500000)},{unit_state}"


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F',
    f'2600,ABILITY_INFO,{ABILITY},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    (f'2600,ABILITY_INFO,{BEAM},"Beam of Reproach",'
     f'"/esoui/art/icons/ability_companion_templar_purifying_light.dds",F,T'),
    f'2600,ABILITY_INFO,{LIGHT_ATTACK},"Light Attack","/esoui/art/icons/death_recap_magic_ranged.dds",F,T',
]
FIGHT_START = [
    '10000,BEGIN_COMBAT',
    *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2)],
]
FIGHT_END = ['30000,END_COMBAT']
# Player 1 hits for 300k, their Isobel (unit 23) for 100k
OWN = _companion_added(3000, 23, 1)
PLAYER_HIT = _hit(11000, _player(1), 300000, 700000)
COMPANION_HIT = _hit(12000, _companion(23), 100000, 600000, ability=BEAM)


def _run(lines, accrue=False):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.companion_accrual = accrue
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer


def _rows(fight):
    return [(p['unit_id'], p['dps']) for p in fight.players]


class TestCompanionRow(unittest.TestCase):

    def test_own_companion_has_its_own_row_under_its_owner(self):
        fight = _run([OWN] + FIGHT_START + [PLAYER_HIT, COMPANION_HIT] + FIGHT_END
                     ).fight_history.fights[0]
        self.assertEqual(_rows(fight), [('1', 300000.0), ('c1-106616', 100000.0), ('2', 0.0)])
        row = fight.players[1]
        self.assertTrue(row['companion'])
        self.assertEqual((row['name'], row['role'], row['level'], row['owner_unit_id']),
                         ('Isobel Veloise', 'C', 20, '1'))
        self.assertAlmostEqual(row['dmg_pct'], 25.0)
        self.assertEqual(fight.group_dps, 400000.0)  # every hit counted once

    def test_accrual_puts_the_companions_damage_on_its_owner_too(self):
        fight = _run([OWN] + FIGHT_START + [PLAYER_HIT, COMPANION_HIT] + FIGHT_END,
                     accrue=True).fight_history.fights[0]
        owner, companion = fight.players[0], fight.players[1]
        self.assertEqual(owner['dps'], 400000.0)  # both hits, a second apart
        self.assertEqual(companion['dps'], 100000.0)
        self.assertEqual(fight.group_dps, 400000.0)
        self.assertAlmostEqual(owner['dmg_pct'] + companion['dmg_pct'], 125.0)
        # The owner's breakdown shows the companion's skill as a pet's
        self.assertTrue(any(a['pet'] for a in owner['damage']['abilities']))

    def test_another_members_companion_is_owned_by_unit_changed(self):
        fight = _run([
            _companion_added(3000, 24, 0, reaction="FRIENDLY"),
            _unit_changed(3500, 24, "@templar's Companion", 2),
        ] + FIGHT_START + [PLAYER_HIT, _hit(12000, _companion(24), 50000, 650000)]
            + FIGHT_END).fight_history.fights[0]
        self.assertEqual([p['unit_id'] for p in fight.players], ['1', '2', 'c2-106616'])
        # The name is the one UNIT_ADDED gave, not the rename
        self.assertEqual(fight.players[2]['name'], 'Isobel Veloise')

    def test_a_companion_without_an_owner_gets_no_row(self):
        fight = _run([_companion_added(3000, 24, 0, reaction="FRIENDLY")] + FIGHT_START
                     + [PLAYER_HIT, _hit(12000, _companion(24), 50000, 650000)]
                     + FIGHT_END).fight_history.fights[0]
        self.assertEqual([p['unit_id'] for p in fight.players], ['1', '2'])

    def test_a_resummoned_companion_is_one_row(self):
        fight = _run([OWN] + FIGHT_START + [
            COMPANION_HIT,
            _died(13000, _companion(23, 0)),
            '13500,UNIT_REMOVED,23',
            _companion_added(14000, 31, 1),
            _hit(15000, _companion(31), 100000, 500000, ability=BEAM),
        ] + FIGHT_END).fight_history.fights[0]
        rows = [p for p in fight.players if p.get('companion')]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['dps'], 200000.0 / 3)  # 200k over 12 s to 15 s
        self.assertEqual(rows[0]['deaths'], 1)
        self.assertEqual(fight.deaths, 0)  # the fight's deaths stay player deaths

    def test_the_bar_is_the_companion_skills_it_cast(self):
        fight = _run([OWN] + FIGHT_START + [
            _cast(10500, _companion(23), LIGHT_ATTACK),
            _cast(10600, _companion(23), BEAM),
            COMPANION_HIT,
        ] + FIGHT_END).fight_history.fights[0]
        row = fight.players[1]
        self.assertEqual(row['front_bar'], ['Beam of Reproach'])
        self.assertEqual(row['h'], 33000)

    def test_a_companions_heal_on_its_owner_is_its_own(self):
        heal = _heal(12000, _companion(23), 5000, _player(1))
        quiet = _run([OWN] + FIGHT_START + [PLAYER_HIT, heal] + FIGHT_END).fight_history.fights[0]
        self.assertEqual((quiet.players[0]['healing'], quiet.players[1]['healing']), (0, 5000))
        accrued = _run([OWN] + FIGHT_START + [PLAYER_HIT, heal] + FIGHT_END,
                       accrue=True).fight_history.fights[0]
        # A heal on the owner is a self-heal for the owner, as before
        self.assertEqual((accrued.players[0]['healing'], accrued.players[1]['healing']), (0, 5000))

    def test_a_companion_out_but_idle_is_listed_until_dismissed(self):
        later = 30000 + COMBAT_RESUME_MS + 60000
        analyzer = _run([OWN] + FIGHT_START + [PLAYER_HIT] + FIGHT_END + [
            f'{later - 1000},UNIT_REMOVED,23',
            f'{later},BEGIN_COMBAT',
            *[f'{later + 1},PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2)],
            _hit(later + 2000, _player(1), 100000, 600000),
            f'{later + 20000},END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        self.assertIn('c1-106616', [p['unit_id'] for p in first.players])
        self.assertNotIn('c1-106616', [p['unit_id'] for p in second.players])

    def test_the_companion_opens_the_fight_with_a_star_on_its_row(self):
        fight = _run([OWN] + FIGHT_START + [COMPANION_HIT, PLAYER_HIT] + FIGHT_END
                     ).fight_history.fights[0]
        self.assertEqual(fight.first_damage_dealer, 'c1-106616')

    def test_rules_still_see_a_companion_as_a_pet(self):
        analyzer = _run([OWN] + FIGHT_START)
        self.assertEqual(analyzer._unit_kind('23'), 'pet')


class TestCompanionViews(unittest.TestCase):

    def setUp(self):
        self.fight = _run([OWN] + FIGHT_START + [
            _cast(10600, _companion(23), BEAM),
            PLAYER_HIT, COMPANION_HIT, _died(20000, _companion(23, 0)),
        ] + FIGHT_END).fight_history.fights[0]

    def test_the_pane_hangs_the_row_under_its_owner(self):
        html = render_html(self.fight, detailed=True)
        self.assertIn(COMPANION_INDENT, html)
        self.assertIn('Isobel Veloise', html)
        self.assertIn('lvl 20', html)
        self.assertIn(build_href('c1-106616'), html)
        self.assertIn(damage_href('c1-106616'), html)
        self.assertLess(html.index('@brainsnorkel'), html.index('Isobel Veloise'))
        self.assertIn('H 33.0k</td>', html)  # health only
        self.assertIn('☠</span>', html)  # its death, muted, no recap

    def test_the_copy_indents_the_companion(self):
        text = render_plain_text(self.fight)
        self.assertIn(f"{COMPANION_INDENT}[C] Isobel Veloise", text)

    def test_the_build_window_shows_the_companion_and_its_owner(self):
        html = render_build_html(self.fight, 'c1-106616')
        self.assertIn('Isobel Veloise', html)
        self.assertIn('level 20', html)
        self.assertIn('@brainsnorkel', html)
        self.assertIn('Beam of Reproach', html)
        self.assertEqual(build_title(self.fight, 'c1-106616'), 'Companion – Isobel Veloise')

    def test_the_damage_window_reads_the_companion_row(self):
        html = render_damage_html(self.fight, 'c1-106616')
        self.assertIn('Beam of Reproach', html)


class TestCompanionSetting(unittest.TestCase):

    def test_off_by_default(self):
        self.assertIs(DEFAULTS["companions"]["accrue_to_owner"], False)

    def test_build_analyzer_reads_the_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(path=Path(tmp) / "config.json")
            self.assertFalse(build_analyzer(config, []).companion_accrual)
            config.set("companions.accrue_to_owner", True)
            self.assertTrue(build_analyzer(config, []).companion_accrual)


if __name__ == '__main__':
    unittest.main()
