#!/usr/bin/env python3
"""A companion has a row of its own under its owner (issue #74), with its
casts, its ultimate and its healing to others (issue #130).

The lines have the shape of the real ones (two solo Moon Hunter Keep logs
of 2026-10-26 and the trial logs surveyed for companions.py): the logging
player's own companion is a MONSTER with reaction COMPANION and its owner
set; another member's is FRIENDLY with owner 0 until a UNIT_CHANGED names
the owner; a re-summoned companion has a new unit id; Isobel's Baneslayer
writes two BEGIN_CAST lines under one castTrackId.
"""

import json
import tempfile
import unittest
from pathlib import Path

import companions
from app_config import DEFAULTS, AppConfig
from app_startup import build_analyzer
from engine_events import RecordingListener
from esolog_tail import COMBAT_RESUME_MS, ESOLogAnalyzer, FightHistory
from fight_history import FightHistoryEntry
from gui.build_render import build_title, render_build_html
from gui.damage_render import render_damage_html
from gui.fight_render import (
    COMPANION_INDENT,
    build_href,
    build_tooltips,
    damage_href,
    render_html,
    render_plain_text,
    ultimate_gap,
)
from gui.name_mask import NameMask

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
ABILITY = 12345
ISOBEL = "106616"
BEAM = 163684
LIGHT_ATTACK = 157069
BANESLAYER = 163763  # Isobel's ultimate
BLOCK = 156219  # a companion's block


class _AllIcons:
    """Stand-in for the fight view's IconCache that has every icon."""

    def has(self, stem):
        return bool(stem)


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


def _cast(ts, source_state, ability, track=None):
    return (f"{ts},BEGIN_CAST,0,F,{track if track is not None else ts},{ability},"
            f"{source_state},{_boss(BOSS_HEALTH)}")


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
    (f'2600,ABILITY_INFO,{BANESLAYER},"Baneslayer",'
     f'"/esoui/art/icons/ability_companion_templar_baneslayer.dds",F,T'),
    f'2600,ABILITY_INFO,{BLOCK},"Block","/esoui/art/icons/ability_warrior_008.dds",F,T',
]
FIGHT_START = [
    '10000,BEGIN_COMBAT',
    *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2)],
]
FIGHT_END = ['30000,END_COMBAT']
# Player 1 hits for 300k, their Isobel (unit 23) for 100k
OWN = _companion_added(3000, 23, 1)
OWN_NAME_HTML = "@brainsnorkel&#x27;s Companion"  # her name, escaped in a page
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
                         ("@brainsnorkel's Companion", 'C', 20, '1'))
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
        # Named after the owner the UNIT_CHANGED gave
        self.assertEqual(fight.players[2]['name'], "@templar's Companion")

    def test_the_logs_name_for_a_companion_is_never_used(self):
        fight = _run([
            _companion_added(3000, 24, 2, reaction="FRIENDLY", name="@someone's Companion"),
        ] + FIGHT_START + [PLAYER_HIT, _hit(12000, _companion(24), 50000, 650000)]
            + FIGHT_END).fight_history.fights[0]
        self.assertEqual(fight.players[2]['name'], "@templar's Companion")

    def test_an_anonymous_owners_handle_never_reaches_the_fight(self):
        # The log gives each owner neither name nor handle, and names the
        # handle only in the companion's name (a Direfrost Keep log of
        # 2026-07-19 has this shape); two anonymous owners, two anon's
        fight = _run([
            '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,6,3,"","",0,50,122,0,PLAYER_ALLY,T',
            '2000,UNIT_ADDED,4,PLAYER,F,4,0,F,6,3,"","",0,50,122,0,PLAYER_ALLY,T',
            _companion_added(3000, 24, 3, reaction="FRIENDLY", name="@quietowner's Companion"),
            _companion_added(3000, 25, 4, reaction="FRIENDLY", name="@shyowner's Companion",
                             monster="103089"),
            '10000,BEGIN_COMBAT',
            *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2, 3, 4)],
            PLAYER_HIT,
            _hit(12000, _companion(24), 50000, 650000),
            _hit(12500, _companion(25), 50000, 600000),
            _heal(13000, _companion(24), 5000, _player(1)),
        ] + FIGHT_END).fight_history.fights[0]
        rows = [(p['unit_id'], p['name']) for p in fight.players]
        for owner, companion in (('3', 'c3-106616'), ('4', 'c4-103089')):
            at = rows.index((owner, 'anon'))
            self.assertEqual(rows[at + 1], (companion, "anon's Companion"))
        for slot in FightHistoryEntry.__slots__:
            text = json.dumps(getattr(fight, slot, None), default=str)
            self.assertNotIn('quietowner', text, slot)
            self.assertNotIn('shyowner', text, slot)
        for page in (render_html(fight, detailed=True), render_plain_text(fight)):
            self.assertNotIn('quietowner', page)
            self.assertNotIn('shyowner', page)

    def test_an_anonymous_owner_named_later_names_their_companion(self):
        fight = _run([
            '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,6,3,"","",0,50,122,0,PLAYER_ALLY,F',
            _companion_added(3000, 24, 3, reaction="FRIENDLY", name="@later's Companion"),
            '4000,UNIT_CHANGED,3,6,3,"Later Char","@later",3003,50,122,0,PLAYER_ALLY,T',
            '10000,BEGIN_COMBAT',
            *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2, 3)],
            PLAYER_HIT,
            _hit(12000, _companion(24), 50000, 650000),
        ] + FIGHT_END).fight_history.fights[0]
        rows = [(p['unit_id'], p['name']) for p in fight.players]
        at = rows.index(('3', '@later'))
        self.assertEqual(rows[at + 1], ('c3-106616', "@later's Companion"))

    def test_a_companion_is_named_after_its_owner(self):
        self.assertEqual(companions.shown_name("@templar"), "@templar's Companion")
        for no_handle in ("", None, '""', "0"):
            self.assertEqual(companions.shown_name(no_handle), "anon's Companion")

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

    def test_the_companion_opens_the_fight_on_its_row(self):
        fight = _run([OWN] + FIGHT_START + [COMPANION_HIT, PLAYER_HIT] + FIGHT_END
                     ).fight_history.fights[0]
        opener = fight.opener
        self.assertEqual((opener['unit_id'], opener['via'], opener['owner_id']),
                         ('c1-106616', 'companion', '1'))
        # Named from its owner, every companion alike (fight_opener)
        self.assertIn("@brainsnorkel's Companion hit Tideborn Taleria first: Beam of Reproach",
                      render_plain_text(fight))

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
        self.assertIn(OWN_NAME_HTML, html)
        self.assertIn('lvl 20', html)
        self.assertIn(build_href('c1-106616'), html)
        self.assertIn(damage_href('c1-106616'), html)
        self.assertLess(html.index('@brainsnorkel'), html.index(OWN_NAME_HTML))
        # A health pool only, and its casts per minute: one cast in 20 s
        self.assertIn('H 33.0k · CPM 3</td>', html)
        self.assertIn('☠</span>', html)  # its death, muted, no recap

    def test_the_copy_indents_the_companion(self):
        text = render_plain_text(self.fight)
        self.assertIn(f"{COMPANION_INDENT}[C] @brainsnorkel's Companion", text)

    def test_the_build_window_shows_the_companion_and_its_owner(self):
        html = render_build_html(self.fight, 'c1-106616')
        self.assertIn(OWN_NAME_HTML, html)
        self.assertIn('level 20', html)
        self.assertNotIn(' · of ', html)  # its name says whose it is
        self.assertIn('Beam of Reproach', html)
        self.assertEqual(build_title(self.fight, 'c1-106616'), "@brainsnorkel's Companion")

    def test_hide_names_hides_another_owner_and_keeps_the_logging_players(self):
        fight = _run([
            OWN, _companion_added(3000, 24, 2, reaction="FRIENDLY", monster="103089"),
        ] + FIGHT_START + [PLAYER_HIT, COMPANION_HIT, _hit(12500, _companion(24), 50000, 550000)]
            + FIGHT_END).fight_history.fights[0]
        names = NameMask.for_entry(fight, True)
        html = render_html(fight, detailed=True, names=names)
        self.assertIn(OWN_NAME_HTML, html)
        self.assertNotIn('templar', html)
        self.assertIn('&#x27;s Companion', html.split(OWN_NAME_HTML)[1])
        text = render_plain_text(fight, names=names)
        self.assertIn(f"{COMPANION_INDENT}[C] @brainsnorkel's Companion", text)
        self.assertIn(f"{COMPANION_INDENT}[C] @{'▒' * 7}'s Companion", text)
        page = render_build_html(fight, 'c2-103089', names=names)
        self.assertNotIn('templar', page)
        self.assertEqual(build_title(fight, 'c2-103089', names=names), f"@{'▒' * 7}'s Companion")

    def test_the_damage_window_reads_the_companion_row(self):
        html = render_damage_html(self.fight, 'c1-106616')
        self.assertIn('Beam of Reproach', html)


def _casting_fight():
    """Isobel casts Baneslayer at 0.5 s (two lines, one cast) and 7 s, two
    light attacks, a block and Beam of Reproach in a 20 s fight, and heals
    her owner for 5,000; the templar heals the owner for 3,000."""
    return _run([OWN] + FIGHT_START + [
        _cast(10500, _companion(23), BANESLAYER),
        _cast(10520, _companion(23), BANESLAYER, track=10500),
        _cast(11000, _companion(23), LIGHT_ATTACK),
        _cast(11500, _companion(23), LIGHT_ATTACK),
        _cast(12500, _companion(23), BLOCK),
        _cast(13000, _companion(23), BEAM),
        _cast(17000, _companion(23), BANESLAYER),
        PLAYER_HIT, COMPANION_HIT,
        _heal(14000, _companion(23), 5000, _player(1)),
        _heal(14500, _player(2), 3000, _player(1)),
    ] + FIGHT_END).fight_history.fights[0]


class TestCompanionCasts(unittest.TestCase):
    """Issue #130: the engine's fields."""

    @classmethod
    def setUpClass(cls):
        cls.fight = _casting_fight()
        cls.row = cls.fight.players[1]

    def test_its_casts_are_counted_like_a_players(self):
        summary = self.row['casts']
        self.assertEqual(summary['total'], 6)  # the two Baneslayer lines are one cast
        self.assertAlmostEqual(summary['cpm'], 18.0)  # over the 20 s fight
        self.assertEqual({kind: summary[kind] for kind in ('light', 'bash', 'block', 'dodge',
                                                           'break_free')},
                         {'light': 2, 'bash': 0, 'block': 1, 'dodge': 0, 'break_free': 0})
        self.assertNotIn('heavy', summary)  # a companion's own kinds

    def test_a_players_casts_keep_their_kinds(self):
        self.assertEqual(set(self.fight.players[0]['casts']),
                         {'total', 'cpm', 'light', 'heavy', 'bash', 'swap', 'dodge',
                          'synergy', 'potion', 'break_free'})

    def test_the_ultimate_is_last_on_the_bar_and_marked(self):
        self.assertEqual(self.row['front_bar'], ['Beam of Reproach', 'Baneslayer'])
        beam, baneslayer = self.row['front_bar_slots']
        self.assertEqual((beam['casts'], baneslayer['casts']), (1, 2))
        self.assertTrue(baneslayer['ultimate'])
        self.assertNotIn('ultimate', beam)

    def test_its_ultimates_with_their_times(self):
        self.assertEqual(self.row['ultimates'],
                         [{'id': str(BANESLAYER), 'name': 'Baneslayer', 'at': [0.5, 7.0]}])

    def test_its_healing_to_others(self):
        self.assertEqual((self.row['healing'], self.fight.players[2]['healing']), (5000, 3000))

    def test_no_ultimate_cast_is_an_empty_list(self):
        fight = _run([OWN] + FIGHT_START + [PLAYER_HIT, COMPANION_HIT] + FIGHT_END
                     ).fight_history.fights[0]
        self.assertEqual(fight.players[1]['ultimates'], [])

    def test_the_bar_order_puts_the_ultimate_last(self):
        self.assertEqual(companions.bar_order([BANESLAYER, BEAM, LIGHT_ATTACK]),
                         [str(BEAM), str(LIGHT_ATTACK), str(BANESLAYER)])


class TestCompanionCastViews(unittest.TestCase):
    """Issue #130: the pane, its hover, the copy and the companion window."""

    @classmethod
    def setUpClass(cls):
        cls.fight = _casting_fight()

    def test_the_row_has_cpm_and_the_ultimate(self):
        self.assertIn('H 33.0k · CPM 18 · Ult ×2</td>', render_html(self.fight, detailed=True))
        self.assertIn(' · CPM 18 · Ult ×2', render_plain_text(self.fight))

    def test_the_hover_names_the_ultimate_and_the_healing(self):
        tips = build_tooltips(self.fight)
        companion = tips[build_href('c1-106616')]
        self.assertIn('Baneslayer cast at 0:00 and 0:07 into the fight', companion)
        self.assertIn('5,000 healing to others, 250 a second of the fight', companion)
        self.assertIn("with this fight's casts", companion)
        # A player's healing to others too; none on the owner, who healed nobody
        self.assertIn('3,000 healing to others, 150 a second of the fight',
                      tips[build_href('2')])
        self.assertNotIn('healing to others', tips[build_href('1')])
        self.assertNotIn(' cast at ', tips[build_href('1')])

    def test_the_window_counts_its_casts(self):
        page = render_build_html(self.fight, 'c1-106616', icons=_AllIcons())
        self.assertIn('>Other</td>', page)
        self.assertIn('Light attacks 2 · Bashes 0 · Blocks 1 · Dodges 0 · Break Free 0 · '
                      '6 casts, 18 per minute', page)
        self.assertNotIn('Heavy attacks', page)
        # Counts under the icons, the ultimate set apart once
        self.assertIn("<td align='center' valign='bottom'>", page)
        self.assertEqual(page.count("<td width='10'></td>"), 1)
        self.assertIn('Baneslayer cast at 0:00 and 0:07 into the fight · '
                      '5,000 healing to others, 250 a second of the fight', page)

    def test_an_entry_built_before_the_counts(self):
        fight = _casting_fight()
        row = fight.players[1]
        del row['casts'], row['ultimates']
        for slot in row['front_bar_slots']:
            del slot['casts']
        isobel_row = render_html(fight, detailed=True).split(OWN_NAME_HTML)[1].split('</tr>')[0]
        self.assertTrue(isobel_row.endswith('H 33.0k</td>'))  # health only, as before
        self.assertNotIn('Ult ×', render_plain_text(fight))
        page = render_build_html(fight, 'c1-106616', icons=_AllIcons())
        self.assertNotIn('>Other</td>', page)
        self.assertNotIn("valign='bottom'", page)
        self.assertIn('Beam of Reproach', page)

    def test_a_marked_bar_sets_apart_only_the_marked_slot(self):
        seven = [{}] * 6 + [{'ultimate': True}]
        self.assertEqual([ultimate_gap(slot, index, True) for index, slot in enumerate(seven)],
                         [False] * 6 + [True])
        six = [{}] * 6
        self.assertEqual([ultimate_gap(slot, index, False) for index, slot in enumerate(six)],
                         [False] * 5 + [True])


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
