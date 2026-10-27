#!/usr/bin/env python3
"""Members who leave, come back, or come back on another character (issue #78).

The lines have the shape of the real ones (presence.py): leaving is a
UNIT_REMOVED, coming back a fresh UNIT_ADDED with the same character id on a
new unit id, another character the same handle with a new character id, and
Offline a placeholder with the handle and character id intact.
"""

import unittest

from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory
from gui.fight_render import render_html, render_plain_text
from presence import present_share

EPOCH = 1759600000000
BOSS_HEALTH = 10000000
ABILITY = 12345
ISOBEL = "106616"


def _state(unit_id):
    return f"{unit_id},20000/20000,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _boss(health, unit_id=70):
    return f"{unit_id},{health}/{BOSS_HEALTH},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _hit(ts, unit_id, damage, boss_health_after=9000000):
    return (f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{damage},0,900,{ABILITY},"
            f"{_state(unit_id)},{_boss(boss_health_after)}")


def _added(ts, unit_id, name="Templar Friend", handle="@templar", character="1002",
           class_id=6, grouped="T", session=2):
    return (f'{ts},UNIT_ADDED,{unit_id},PLAYER,F,{session},0,F,{class_id},1,"{name}",'
            f'"{handle}",{character},50,2547,0,PLAYER_ALLY,{grouped}')


def _removed(ts, unit_id):
    return f"{ts},UNIT_REMOVED,{unit_id}"


def _info(ts, unit_id):
    return f"{ts},PLAYER_INFO,{unit_id},[45549],[1],[],[{ABILITY}],[{ABILITY}]"


def _fight(start, end, units, body):
    return ([f"{start},BEGIN_COMBAT"] + [_info(start + 1, u) for u in units]
            + body + [f"{end},END_COMBAT"])


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    _added(2000, 2),
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F',
    f'2600,ABILITY_INFO,{ABILITY},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
]


def _run(lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer.fight_history.fights


def _rows(fight):
    return [(p['name'], p['unit_id'], p['dps']) for p in fight.players]


class TestPresentShare(unittest.TestCase):

    def test_share_of_the_fight(self):
        self.assertEqual(present_share(10000, 30000, None, 20000), 50.0)
        self.assertEqual(present_share(10000, 30000, 15000, 20000), 25.0)
        self.assertEqual(present_share(10000, 30000, 2000, None), 100.0)
        self.assertEqual(present_share(10000, 10000, None, 20000), 0.0)


class TestLeaving(unittest.TestCase):

    def test_a_member_who_left_is_off_the_next_fights_list(self):
        fights = _run(
            _fight(10000, 30000, (1, 2), [_hit(11000, 1, 100000), _hit(11000, 2, 50000)])
            + [_removed(31000, 2)]
            + _fight(40000, 60000, (1,), [_hit(41000, 1, 100000)]))
        self.assertEqual([p['name'] for p in fights[0].players], ['@brainsnorkel', '@templar'])
        self.assertNotIn('left', fights[0].players[1])  # left after the fight
        self.assertEqual(_rows(fights[1]), [('@brainsnorkel', '1', 100000.0)])

    def test_a_member_who_left_mid_fight_is_greyed_with_their_share(self):
        fights = _run(_fight(10000, 30000, (1, 2), [
            _hit(11000, 1, 100000), _hit(12000, 2, 50000), _removed(20000, 2),
            _hit(25000, 1, 100000)]))
        row = fights[0].players[1]
        self.assertEqual(row['name'], '@templar')
        self.assertTrue(row['left'])
        self.assertEqual(row['present_pct'], 50.0)
        self.assertNotIn('left', fights[0].players[0])
        self.assertIn('@templar', render_plain_text(fights[0]))
        self.assertIn('left · here for 50% of the fight', render_plain_text(fights[0]))
        self.assertIn('here for 50% of the fight', render_html(fights[0], detailed=True))

    def test_a_monster_on_a_departed_players_unit_id_is_not_them(self):
        fights = _run(_fight(10000, 30000, (1, 2), [
            _hit(11000, 2, 50000), _removed(15000, 2),
            '16000,UNIT_ADDED,2,MONSTER,F,0,8000,F,0,0,"Betty Netch","",0,50,0,0,HOSTILE,F',
            _hit(17000, 2, 70000)]))
        templar = next(p for p in fights[0].players if p['name'] == '@templar')
        self.assertEqual(templar['dps'], 50000.0)
        self.assertTrue(templar['left'])
        self.assertEqual(fights[0].group_dps, 50000.0)

    def test_offline_is_not_the_player(self):
        fights = _run(
            _fight(10000, 30000, (1, 2), [_hit(11000, 2, 50000)])
            + [_removed(31000, 2), _added(32000, 9, name="Offline"), _removed(33000, 9),
               _added(34000, 5)]
            + _fight(40000, 60000, (1, 5), [_hit(41000, 5, 60000)]))
        self.assertEqual([p['unit_id'] for p in fights[1].players], ['5', '1'])


class TestComingBack(unittest.TestCase):

    def test_back_mid_fight_on_a_new_unit_id_is_one_row(self):
        fights = _run(_fight(10000, 30000, (1, 2), [
            _hit(11000, 1, 100000), _hit(11000, 2, 30000), _removed(12000, 2),
            _added(14000, 5), _hit(13000, 1, 100000), _hit(21000, 5, 70000)]))
        rows = _rows(fights[0])
        self.assertEqual(len(rows), 2)
        templar = fights[0].players[1]
        self.assertEqual((templar['name'], templar['unit_id']), ('@templar', '2'))
        # Both halves, over the span from the first hit to the last, gap included
        self.assertEqual(templar['dps'], 100000 / 10)
        self.assertNotIn('left', templar)

    def test_back_between_fights_is_keyed_by_the_new_id_next_fight(self):
        fights = _run(
            _fight(10000, 30000, (1, 2), [_hit(11000, 2, 50000)])
            + [_removed(31000, 2), _added(32000, 5)]
            + _fight(40000, 60000, (1, 5), [_hit(41000, 5, 60000), _hit(41000, 1, 10000)]))
        self.assertEqual(_rows(fights[1]), [('@templar', '5', 60000.0),
                                            ('@brainsnorkel', '1', 10000.0)])

    def test_back_mid_fight_then_keyed_by_the_new_id_next_fight(self):
        fights = _run(
            _fight(10000, 30000, (1, 2), [_hit(11000, 2, 50000), _removed(12000, 2),
                                          _added(13000, 5), _hit(14000, 5, 10000)])
            + _fight(40000, 60000, (1, 5), [_hit(41000, 5, 60000)]))
        self.assertEqual([p['unit_id'] for p in fights[1].players], ['5', '1'])
        self.assertEqual(fights[1].players[0]['front_bar'], ['Damage Ability'])

    def test_another_character_is_a_new_row_listed_before_its_build(self):
        fights = _run(
            _fight(10000, 30000, (1, 2), [_hit(11000, 2, 50000)])
            + _fight(40000, 60000, (1, 2), [
                _hit(41000, 1, 100000), _hit(41000, 2, 20000),
                _added(45000, 6, name="Sorc Alt", character="2002", class_id=2, session=7),
                _hit(46000, 6, 80000)])
            + _fight(70000, 90000, (1, 6), [_hit(71000, 6, 90000)]))
        second = fights[1]
        by_name = {(p['name'], p['class_abbr']): p for p in second.players}
        alt = by_name[('@templar', 'Sorc')]
        self.assertTrue(alt['no_build'])
        self.assertEqual(alt['build_issues'], [])
        self.assertTrue(by_name[('@templar', 'Templar')]['left'])
        # The rows add up to the group total
        self.assertAlmostEqual(sum(p['dmg_pct'] for p in second.players), 100.0)
        self.assertIn('build not in the log yet', render_plain_text(second))
        # From the next pull: the new character alone, with its build
        self.assertEqual([(p['name'], p['class_abbr']) for p in fights[2].players],
                         [('@templar', 'Sorc'), ('@brainsnorkel', 'NB')])
        self.assertNotIn('no_build', fights[2].players[0])

    def test_another_character_not_grouped_is_not_listed_before_its_build(self):
        fights = _run(_fight(10000, 30000, (1, 2), [
            _added(15000, 6, name="Sorc Alt", character="2002", class_id=2, grouped="F"),
            _hit(16000, 6, 80000)]))
        self.assertNotIn('Sorc', [p['class_abbr'] for p in fights[0].players])


class TestAnonymous(unittest.TestCase):

    def test_an_anonymous_member_named_on_joining_takes_the_name(self):
        fights = _run(
            [_added(3000, 8, name="", handle="", character="3003", grouped="F"),
             '4000,UNIT_CHANGED,8,6,1,"Viburnum Healer","@Viburnum",3003,50,2547,0,PLAYER_ALLY,T']
            + _fight(10000, 30000, (1, 2, 8), [_hit(11000, 8, 50000)]))
        self.assertIn('@Viburnum', [p['name'] for p in fights[0].players])


class TestCompanions(unittest.TestCase):

    def _companion(self, ts, unit_id, owner):
        return (f'{ts},UNIT_ADDED,{unit_id},MONSTER,F,0,{ISOBEL},F,0,0,"Isobel Veloise","",'
                f'0,20,0,{owner},FRIENDLY,F')

    def test_a_companion_follows_its_owner_back_and_out(self):
        companion_hit = (f"{{ts}},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{{dmg}},0,900,{ABILITY},"
                         f"{{unit}},20000/33000,0/0,0/0,0/0,0/0,0,0.3,0.4,1.0,{_boss(9000000)}")
        fights = _run(
            [self._companion(3000, 23, 2)]
            + _fight(10000, 30000, (1, 2), [
                companion_hit.format(ts=11000, dmg=10000, unit=23),
                _removed(12000, 2), _removed(12000, 23), _added(13000, 5),
                self._companion(14000, 24, 5),
                companion_hit.format(ts=21000, dmg=20000, unit=24)])
            + [_removed(31000, 5)]
            + _fight(40000, 60000, (1,), [_hit(41000, 1, 10000)]))
        companions = [p for p in fights[0].players if p.get('companion')]
        self.assertEqual(len(companions), 1)
        self.assertEqual(companions[0]['owner_unit_id'], '2')
        self.assertEqual(companions[0]['dps'], 30000 / 10)
        self.assertEqual([p['name'] for p in fights[1].players], ['@brainsnorkel'])


if __name__ == "__main__":
    unittest.main()
