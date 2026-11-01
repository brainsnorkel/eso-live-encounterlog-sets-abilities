#!/usr/bin/env python3
"""A second copy of a group buff set, or a second holder of a Champion
Point star, that added next to nothing (issue #172): the record of whose
copy each player had, the session rules and their texts, the tables, and
what the engine puts on a fight entry."""

import json
import unittest

from build_session import fights

from ability_icons import bundle_root
from build_issues import (
    GROUP_BUFF_EFFECT_IDS,
    GROUP_BUFF_SET_OF_EFFECT,
    GROUP_BUFF_SETS,
    LONG_FIGHT_S,
    SECOND_SOURCE_SHARE,
    STAR_PROC_IDS,
    STARS,
    BuildIssueTracker,
    GroupBuffCredit,
    group_buff_sets_worn,
    group_buff_shares,
    stars_slotted,
)

WARD = '172621'
ECHOES = '220015'


def _identity(unit_id):
    return unit_id if not unit_id.startswith('pet') else None


def _item(slot, set_id, item_id='95044'):
    return [slot, item_id, 'T', '16', 'ARMOR_DIVINES', 'LEGENDARY', set_id, 'MAGICKA', 'T',
            '16', 'LEGENDARY']


def _gear(set_ids):
    """Body pieces in order HEAD, SHOULDERS, CHEST, LEGS, FEET, HAND, WAIST
    with the given set ids; a staff on each bar of no set."""
    slots = ('HEAD', 'SHOULDERS', 'CHEST', 'LEGS', 'FEET', 'HAND', 'WAIST')
    gear = {slot: _item(slot, set_id) for slot, set_id in zip(slots, set_ids)}
    gear['MAIN_HAND'] = _item('MAIN_HAND', '0', '133257')
    gear['BACKUP_MAIN'] = _item('BACKUP_MAIN', '0', '187194')
    return gear


class TestGroupBuffCredit(unittest.TestCase):

    def test_spans_per_wearer_and_receiver(self):
        credit = GroupBuffCredit()
        credit.record('GAINED', WARD, 'a', 'x', 1000)
        credit.record('FADED', WARD, 'a', 'x', 5000)
        credit.record('GAINED', WARD, 'b', 'y', 2000)  # still up at the window's end
        self.assertEqual(credit.credited(0, 10000, _identity),
                         {(WARD, 'a', 'x'): 4000, (WARD, 'b', 'y'): 8000})
        # The window clips both
        self.assertEqual(credit.credited(3000, 4000, _identity),
                         {(WARD, 'a', 'x'): 1000, (WARD, 'b', 'y'): 1000})

    def test_a_refresh_every_second_is_one_span(self):
        # Pearlescent Ward is written as a FADED and a GAINED each second
        credit = GroupBuffCredit()
        credit.record('GAINED', WARD, 'a', 'x', 1000)
        for ts in range(2000, 11000, 1000):
            credit.record('FADED', WARD, 'a', 'x', ts)
            credit.record('GAINED', WARD, 'a', 'x', ts)
            credit.record('UPDATED', WARD, 'a', 'x', ts)
        credit.record('FADED', WARD, 'a', 'x', 11000)
        self.assertEqual(credit.credited(0, 20000, _identity), {(WARD, 'a', 'x'): 10000})
        self.assertEqual(credit._closed[(WARD, 'a', 'x')], [[1000, 11000]])

    def test_updated_opens_a_span_after_a_missed_gained(self):
        credit = GroupBuffCredit()
        credit.record('UPDATED', ECHOES, 'a', 'x', 1000)
        credit.record('FADED', ECHOES, 'a', 'x', 4000)
        self.assertEqual(credit.credited(0, 9000, _identity), {(ECHOES, 'a', 'x'): 3000})

    def test_units_that_are_no_players_and_other_ids_are_left_out(self):
        credit = GroupBuffCredit()
        credit.record('GAINED', WARD, 'a', 'pet1', 1000)
        credit.record('GAINED', '61747', 'a', 'x', 1000)  # Major Force: not a set's buff here
        self.assertEqual(credit.credited(0, 9000, _identity), {})

    def test_a_returned_player_sums_over_both_unit_ids(self):
        credit = GroupBuffCredit()
        credit.record('GAINED', WARD, 'a', 'x', 1000)
        credit.record('FADED', WARD, 'a', 'x', 3000)
        credit.record('GAINED', WARD, 'a', 'x2', 5000)  # x came back as x2
        credit.record('FADED', WARD, 'a', 'x2', 6000)
        self.assertEqual(credit.credited(0, 9000, lambda u: 'x' if u.startswith('x') else u),
                         {(WARD, 'a', 'x'): 3000})

    def test_a_removed_unit_ends_its_spans_as_wearer_and_receiver(self):
        # The game writes no FADED for a unit that has gone
        credit = GroupBuffCredit()
        credit.record('GAINED', ECHOES, 'a', 'x', 1000)
        credit.record('GAINED', ECHOES, 'x', 'y', 1000)
        credit.record('GAINED', ECHOES, 'b', 'y', 1000)
        credit.forget_unit('x', 3000)
        self.assertEqual(credit.credited(0, 9000, _identity),
                         {(ECHOES, 'a', 'x'): 2000, (ECHOES, 'x', 'y'): 2000,
                          (ECHOES, 'b', 'y'): 8000})

    def test_zone_change_reset_and_prune(self):
        credit = GroupBuffCredit()
        credit.record('GAINED', WARD, 'a', 'x', 1000)
        credit.zone_changed(4000)
        self.assertEqual(credit.credited(0, 9000, _identity), {(WARD, 'a', 'x'): 3000})
        credit.prune_before(5000)
        self.assertEqual(credit.credited(0, 9000, _identity), {})
        credit.record('GAINED', WARD, 'a', 'x', 6000)
        credit.reset()
        self.assertEqual(credit.credited(0, 9000, _identity), {})

    def test_a_sets_two_buffs_at_once_count_once(self):
        # Magma Incarnate gives Minor Courage and Minor Resolve together
        credit = GroupBuffCredit()
        credit.record('GAINED', '159310', 'a', 'x', 1000)
        credit.record('GAINED', '159311', 'a', 'x', 1000)
        credit.record('FADED', '159310', 'a', 'x', 11000)
        credit.record('FADED', '159311', 'a', 'x', 11000)
        credit.record('GAINED', '159311', 'a', 'x', 15000)  # Resolve alone, 2 s more
        credit.record('FADED', '159311', 'a', 'x', 17000)
        self.assertEqual(credit.credited(0, 20000, _identity, group_of=GROUP_BUFF_SET_OF_EFFECT.get),
                         {('Magma Incarnate', 'a', 'x'): 12000})
        # By id, each is its own
        self.assertEqual(credit.credited(0, 20000, _identity),
                         {('159310', 'a', 'x'): 10000, ('159311', 'a', 'x'): 12000})


class TestWornAndSlotted(unittest.TestCase):

    def test_perfected_and_plain_pieces_count_together(self):
        self.assertEqual([s.name for s in group_buff_sets_worn(_gear(['651'] * 3 + ['648'] * 2))],
                         ['Pearlescent Ward'])
        self.assertEqual(group_buff_sets_worn(_gear(['648'] * 4)), [])

    def test_a_monster_set_is_complete_at_two_pieces(self):
        self.assertEqual([s.name for s in group_buff_sets_worn(_gear(['687', '687']))],
                         ['Ozezan the Inferno'])
        self.assertEqual(group_buff_sets_worn(_gear(['687'])), [])
        self.assertEqual(group_buff_sets_worn({}), [])

    def test_stars_slotted_from_the_long_term_effects(self):
        self.assertEqual([s.name for s in stars_slotted(['61257', '156008', '156017'])],
                         ['Enlivening Overflow', 'From the Brink'])
        self.assertEqual(stars_slotted([]), [])
        self.assertEqual(stars_slotted(None), [])


CREDITED = {('Lucent Echoes', 'a', 'c'): 1000, ('Lucent Echoes', 'a', 'b'): 2000,
            ('Pearlescent Ward', 'a', 'b'): 2000, ('Pearlescent Ward', 'a', 'c'): 1000}
GROUP = {'a': 2000, 'b': 2000, 'c': 2000, 'd': 2000}


class TestShares(unittest.TestCase):

    def test_lucent_echoes_leaves_its_wearers_out(self):
        shares = group_buff_shares({'Lucent Echoes': [('a', 'pa'), ('b', 'pb')]}, CREDITED, GROUP)
        # The others are c and d: b wears it, and a wearer never benefits
        self.assertEqual(shares, {'Lucent Echoes': {'pa': (1000, 4000), 'pb': (0, 4000)}})

    def test_pearlescent_ward_counts_the_other_wearer(self):
        shares = group_buff_shares({'Pearlescent Ward': [('a', 'pa'), ('b', 'pb')]},
                                   CREDITED, GROUP)
        self.assertEqual(shares, {'Pearlescent Ward': {'pa': (3000, 6000), 'pb': (0, 6000)}})

    def test_the_others_time_is_the_groups_presence(self):
        # c joined half way; a player of the zone outside the group is not
        # in the group's presence at all, so never counts
        shares = group_buff_shares({'Pearlescent Ward': [('a', 'pa'), ('b', 'pb')]},
                                   CREDITED, {'a': 2000, 'b': 2000, 'c': 1000, 'd': 2000})
        self.assertEqual(shares, {'Pearlescent Ward': {'pa': (3000, 5000), 'pb': (0, 5000)}})

    def test_a_set_with_one_wearer_is_not_measured(self):
        self.assertEqual(group_buff_shares({'Pearlescent Ward': [('a', 'pa')]},
                                           CREDITED, {'a': 2000, 'b': 2000}), {})


class TestGroupSetRule(unittest.TestCase):

    def test_a_copy_credited_with_nothing_is_a_finding_on_it_alone(self):
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {'Pearlescent Ward': {
            'p1': (180000, 270000), 'p2': (0, 270000)}}, {})
        found = tracker.second_source_findings(1000, 'p2')
        self.assertEqual([f['title'] for f in found],
                         ['Second Pearlescent Ward gave the others nothing (1 fight)'])
        self.assertEqual(found[0]['rule'], 'second-group-set')
        self.assertEqual(found[0]['set'], 'Pearlescent Ward')
        self.assertIn('with 0.0% of the other players', found[0]['detail'])
        self.assertIn('one wearer at a time', found[0]['detail'])
        self.assertEqual(tracker.second_source_findings(1000, 'p1'), [])

    def test_under_the_share_in_every_fight_and_over_once_clears(self):
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {'Spell Power Cure': {
            'p1': (100000, 270000), 'p2': (4000, 270000)}}, {})
        tracker.note_second_sources(200000, 120.0, {'Spell Power Cure': {
            'p1': (100000, 360000), 'p2': (6000, 360000)}}, {})
        found = tracker.second_source_findings(200000, 'p2')
        self.assertEqual([f['title'] for f in found],
                         ['Second Spell Power Cure gave the others 1.6% of their time (2 fights)'])
        # One fight over the share: the copy did reach the group
        tracker.note_second_sources(400000, 90.0, {'Spell Power Cure': {
            'p1': (100000, 270000), 'p2': (27000, 270000)}}, {})
        self.assertEqual(tracker.second_source_findings(400000, 'p2'), [])
        self.assertGreater(27000 / 270000, SECOND_SOURCE_SHARE)

    def test_quiet_copies_beside_a_working_one_are_each_flagged(self):
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {'Powerful Assault': {
            'p1': (1000, 270000), 'p2': (0, 270000), 'p3': (90000, 270000)}}, {})
        self.assertEqual(tracker.second_source_findings(1000, 'p1')[0]['title'],
                         'Second Powerful Assault gave the others 0.4% of their time (1 fight)')
        self.assertEqual(len(tracker.second_source_findings(1000, 'p2')), 1)
        self.assertEqual(tracker.second_source_findings(1000, 'p3'), [])

    def test_two_copies_that_both_reached_no_one_are_not_flagged(self):
        # Two Master Architects in a fight with no ultimate cast
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 104.0, {'Master Architect': {
            'p1': (0, 1144000), 'p2': (0, 1144000)}}, {})
        self.assertEqual(tracker.second_source_findings(1000, 'p1'), [])
        self.assertEqual(tracker.second_source_findings(1000, 'p2'), [])
        # Once one copy reaches the group, the other that never did is flagged
        tracker.note_second_sources(200000, 99.0, {'Master Architect': {
            'p1': (0, 1089000), 'p2': (180000, 1089000)}}, {})
        self.assertEqual(tracker.second_source_findings(200000, 'p1')[0]['title'],
                         'Second Master Architect gave the others nothing (2 fights)')
        self.assertEqual(tracker.second_source_findings(200000, 'p2'), [])

    def test_short_fights_are_not_judged_and_a_republished_fight_counts_once(self):
        tracker = BuildIssueTracker()
        quiet = {'Pearlescent Ward': {'p1': (50000, 90000), 'p2': (0, 90000)}}
        tracker.note_second_sources(1000, 30.0, quiet, {})
        self.assertEqual(tracker.second_source_findings(1000, 'p2'), [])
        tracker.note_second_sources(1000, LONG_FIGHT_S, quiet, {})  # the same fight, longer
        self.assertEqual(tracker.second_source_findings(1000, 'p2')[0]['title'],
                         'Second Pearlescent Ward gave the others nothing (1 fight)')
        tracker.reset()
        self.assertEqual(tracker.second_source_findings(1000, 'p2'), [])

    def test_lucent_echoes_says_its_wearers_never_benefit(self):
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {'Lucent Echoes': {
            'p1': (180000, 270000), 'p2': (0, 270000)}}, {})
        detail = tracker.second_source_findings(1000, 'p2')[0]['detail']
        self.assertIn("never counts for the set's own wearers", detail)

    def test_a_unit_id_key_is_retired_at_a_zone_change(self):
        # 'unit:7' names one player until the zone changes; another player
        # on unit 7 afterwards must not inherit the first one's fights
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {'Spell Power Cure': {
            'p1': (90000, 270000), 'unit:7': (0, 270000)}}, {})
        self.assertEqual(len(tracker.second_source_findings(1000, 'unit:7')), 1)
        tracker.retire_players('unit:')
        tracker.note_second_sources(200000, 90.0, {'Spell Power Cure': {
            'p1': (90000, 270000), 'unit:7': (60000, 270000)}}, {})
        self.assertEqual(tracker.second_source_findings(200000, 'unit:7'), [])
        # The first fight still counts for the other wearer's record
        self.assertEqual(len(tracker._group_buffs['Spell Power Cure'][1000][1]), 2)


class TestStarRule(unittest.TestCase):

    def test_an_enlivening_overflow_holder_under_fifteen_percent(self):
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {}, {'Enlivening Overflow': {'p1': 18, 'p2': 2}})
        found = tracker.second_source_findings(1000, 'p2')
        self.assertEqual([f['title'] for f in found],
                         ['Second Enlivening Overflow: 10% of its procs (1 fight)'])
        self.assertEqual(found[0]['rule'], 'second-star')
        self.assertEqual(found[0]['star'], 'Enlivening Overflow')
        self.assertEqual(found[0]['star_url'],
                         'https://eso-hub.com/en/champion-points/star/enlivening-overflow')
        self.assertIn('once every 12 seconds per player', found[0]['detail'])
        self.assertIn("this player's procs were 10% of the holders', where an even share was 50%",
                      found[0]['detail'])
        self.assertEqual(tracker.second_source_findings(1000, 'p1'), [])

    def test_the_bar_follows_the_holder_count(self):
        # Seven holders sharing evenly: 1/7 each is no finding for anyone
        tracker = BuildIssueTracker()
        even = {f'p{n}': 10 for n in range(7)}
        tracker.note_second_sources(1000, 90.0, {}, {'Enlivening Overflow': even})
        self.assertEqual([k for k in even if tracker.second_source_findings(1000, k)], [])
        # Three holders: an even share is a third, so 9% is under 30% of it
        tracker.note_second_sources(200000, 90.0, {}, {'Enlivening Overflow': {
            'q1': 50, 'q2': 41, 'q3': 9}})
        found = tracker.second_source_findings(200000, 'q3')
        self.assertEqual([f['title'] for f in found],
                         ['Second Enlivening Overflow: 9.0% of its procs (1 fight)'])
        self.assertIn('where an even share was 33%', found[0]['detail'])
        self.assertEqual(tracker.second_source_findings(200000, 'q2'), [])

    def test_from_the_brink_only_when_it_never_procced(self):
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {}, {'From the Brink': {'p1': 8, 'p2': 1}})
        self.assertEqual(tracker.second_source_findings(1000, 'p2'), [])
        tracker.note_second_sources(200000, 90.0, {}, {'From the Brink': {'p1': 6, 'p3': 0}})
        found = tracker.second_source_findings(200000, 'p3')
        self.assertEqual([f['title'] for f in found], ['Second From the Brink: no proc in 1 fight'])
        self.assertIn('once every 30 seconds per player', found[0]['detail'])
        self.assertIn("never procced while the other holder's did", found[0]['detail'])

    def test_too_few_procs_by_the_others_is_chance_not_a_finding(self):
        # One or two shields between two holders leave one with none half
        # the time: judged only once the others have procced five times
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {}, {'From the Brink': {'p1': 2, 'p2': 0}})
        self.assertEqual(tracker.second_source_findings(1000, 'p2'), [])
        tracker.note_second_sources(200000, 90.0, {}, {'From the Brink': {'p1': 3, 'p2': 0}})
        self.assertEqual(tracker.second_source_findings(200000, 'p2')[0]['title'],
                         'Second From the Brink: no proc in 2 fights')

    def test_counted_over_the_session_and_no_procs_at_all_is_not_judged(self):
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {}, {'Enlivening Overflow': {'p1': 0, 'p2': 0}})
        self.assertEqual(tracker.second_source_findings(1000, 'p2'), [])
        tracker.note_second_sources(200000, 90.0, {}, {'Enlivening Overflow': {'p1': 10, 'p2': 1}})
        tracker.note_second_sources(400000, 90.0, {}, {'Enlivening Overflow': {'p1': 10, 'p2': 9}})
        # 10 of 30 over the session: a third, not flagged
        self.assertEqual(tracker.second_source_findings(400000, 'p2'), [])
        # A short fight is not judged
        tracker.note_second_sources(600000, 30.0, {}, {'Enlivening Overflow': {'p1': 9, 'p2': 0}})
        self.assertEqual(tracker.second_source_findings(600000, 'p2'), [])


class TestTables(unittest.TestCase):

    def test_every_listed_buff_of_a_judged_set_is_recorded(self):
        table = json.loads(bundle_root().joinpath('data', 'sets', 'set_buffs.json')
                           .read_text(encoding='utf-8'))['buffs']
        for group_set in GROUP_BUFF_SETS:
            listed = {buff_id for buff_id, buff in table.items()
                      if set(buff['set_ids']) & group_set.set_ids}
            self.assertLessEqual(listed, group_set.effect_ids, group_set.name)
        self.assertEqual(GROUP_BUFF_EFFECT_IDS,
                         frozenset().union(*(s.effect_ids for s in GROUP_BUFF_SETS)))

    def test_a_damage_set_or_a_debuff_set_is_never_judged(self):
        judged = set().union(*(s.set_ids for s in GROUP_BUFF_SETS))
        # Kinras's Wrath, Huntsman's Warmask, Turning Tide, Corpseburster
        self.assertFalse(judged & {'570', '845', '622', '777'})

    def test_the_stars(self):
        self.assertEqual(STAR_PROC_IDS, {'156012': 'Enlivening Overflow',
                                         '156020': 'From the Brink'})
        self.assertEqual([(s.slotted_id, s.cooldown_s) for s in STARS],
                         [('156008', 12), ('156017', 30)])


# ---- the engine ----

EPOCH = 1759600000000
BOSS = '70,105634/105634,0/0,0/0,0/0,0/0,0,0.4081,0.5662,0.0256'
WARD_GEAR = ('[' + ','.join(
    f'[{slot},95044,T,16,ARMOR_DIVINES,LEGENDARY,648,MAGICKA,T,16,LEGENDARY]'
    for slot in ('HEAD', 'SHOULDERS', 'CHEST', 'LEGS', 'FEET'))
    + ',[MAIN_HAND,133257,T,16,WEAPON_INFUSED,LEGENDARY,0,FIERY_WEAPON,T,16,LEGENDARY]]')
PLAIN_GEAR = '[[MAIN_HAND,133257,T,16,WEAPON_INFUSED,LEGENDARY,0,FIERY_WEAPON,T,16,LEGENDARY]]'


def _state(unit_id):
    return f'{unit_id},22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492'


def _effect(ts, change, ability_id, source, target):
    return f'{ts},EFFECT_CHANGED,{change},1,4021668,{ability_id},{_state(source)},{_state(target)}'


def _hit(ts, unit_id):
    return f'{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,50000,0,4021667,12345,{_state(unit_id)},{BOSS}'


def _session(*fights_lines):
    lines = [
        f'1000,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
        '1000,ZONE_CHANGED,1055,"Scalecaller Peak",VETERAN',
        '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,6,4,"First","@ward1",1001,50,3224,0,PLAYER_ALLY,T',
        '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,7,"Second","@ward2",1002,50,1962,0,PLAYER_ALLY,T',
        '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,3,4,"Third","@healer",1003,50,1962,0,PLAYER_ALLY,T',
        '2000,UNIT_ADDED,4,PLAYER,F,4,0,F,1,4,"Fourth","@tank",1004,50,1962,0,PLAYER_ALLY,T',
        '2500,UNIT_ADDED,70,MONSTER,F,0,105634,T,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
        '2600,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    ]
    for fight in fights_lines:
        lines.extend(fight)
    return lines


def _fight(begin, end):
    """@ward1 and @ward2 wear Pearlescent Ward, and @ward1's is the one every
    player has; @ward1 and @ward2 slot Enlivening Overflow (nine procs to
    one), @healer and @tank From the Brink (five shields to none)."""
    lines = [f'{begin},BEGIN_COMBAT',
             f'{begin + 1},PLAYER_INFO,1,[61257,156008],[1,1],{WARD_GEAR},[12345],[12345]',
             f'{begin + 1},PLAYER_INFO,2,[61257,156008],[1,1],{WARD_GEAR},[12345],[12345]',
             f'{begin + 1},PLAYER_INFO,3,[61257,156017],[1,1],{PLAIN_GEAR},[12345],[12345]',
             f'{begin + 1},PLAYER_INFO,4,[61257,156017],[1,1],{PLAIN_GEAR},[12345],[12345]']
    lines += [_effect(begin + 5, 'GAINED', WARD, 1, target) for target in (1, 2, 3, 4)]
    lines += [_effect(begin + 1000 + 100 * n, 'GAINED', '156012', 1, 3) for n in range(9)]
    lines.append(_effect(begin + 3000, 'GAINED', '156012', 2, 4))
    lines += [_effect(begin + 4000 + 100 * n, 'GAINED', '156020', 3, target)
              for n, target in enumerate((4, 1, 2, 4, 1))]
    lines += [_hit(begin + 1000 + 10 * unit, unit) for unit in (1, 2, 3, 4)]
    lines += [_hit(end - 1000 + 10 * unit, unit) for unit in (1, 2, 3, 4)]
    lines.append(f'{end},END_COMBAT')
    return lines


class TestEngine(unittest.TestCase):

    def _found(self, entry):
        return {p['name']: [(f['rule'], f['title']) for f in p['build_issues']
                            if f['rule'] in ('second-group-set', 'second-star')]
                for p in entry.players}

    def test_the_findings_land_on_the_second_copy(self):
        entries = fights(_session(_fight(10000, 100000)))
        self.assertEqual(len(entries), 1)
        found = self._found(entries[0])
        self.assertEqual(found['@ward1'], [])
        self.assertEqual(found['@healer'], [])
        self.assertEqual(found['@ward2'], [
            ('second-group-set', 'Second Pearlescent Ward gave the others nothing (1 fight)'),
            ('second-star', 'Second Enlivening Overflow: 10% of its procs (1 fight)')])
        self.assertEqual(found['@tank'], [('second-star', 'Second From the Brink: no proc in 1 fight')])

    def test_a_short_fight_is_not_judged_and_the_session_counts_on(self):
        entries = fights(_session(_fight(10000, 40000), _fight(200000, 290000),
                                  _fight(400000, 490000)))
        self.assertEqual([self._found(e)['@ward2'] for e in entries], [
            [],
            [('second-group-set', 'Second Pearlescent Ward gave the others nothing (1 fight)'),
             ('second-star', 'Second Enlivening Overflow: 10% of its procs (1 fight)')],
            [('second-group-set', 'Second Pearlescent Ward gave the others nothing (2 fights)'),
             ('second-star', 'Second Enlivening Overflow: 10% of its procs (2 fights)')]])

    def test_star_procs_before_the_pull_are_not_the_fights(self):
        # The zone's first encounter is made before the pull and reused at
        # BEGIN_COMBAT: twenty procs of @ward2's while the group buffs up
        # would put it at 21 of 30 if they counted
        before = [_effect(5000 + 10 * n, 'GAINED', '156012', 2, 3) for n in range(20)]
        entries = fights(_session(before, _fight(10000, 100000)))
        self.assertIn(('second-star', 'Second Enlivening Overflow: 10% of its procs (1 fight)'),
                      self._found(entries[0])['@ward2'])

    def test_players_of_the_zone_outside_the_group_are_no_receivers(self):
        # @ward2's Ward is on @healer for 9 s of the 90 s fight: 3.3% of the
        # three other members' time, a copy that reached the group. Twenty
        # players of the zone who are not in the group (a city, Cyrodiil)
        # must not dilute it to 0.4%
        strangers = [f'2000,UNIT_ADDED,{100 + n},PLAYER,F,{100 + n},0,F,1,4,"Passer {n}",'
                     f'"@passer{n}",{2000 + n},50,500,0,PLAYER_ALLY,F' for n in range(20)]
        fight = _fight(10000, 100000)
        fight[-1:-1] = [_effect(20000, 'GAINED', WARD, 2, 3), _effect(29000, 'FADED', WARD, 2, 3)]
        entries = fights(_session(strangers, fight))
        self.assertNotIn('second-group-set', [rule for rule, _title in self._found(entries[0])['@ward2']])


class TestPopupLink(unittest.TestCase):

    def test_the_star_finding_links_its_page(self):
        try:
            from gui.fight_render import issues_html
        except ImportError:  # pragma: no cover - the GUI is not installed
            self.skipTest('the GUI modules need PySide6')
        tracker = BuildIssueTracker()
        tracker.note_second_sources(1000, 90.0, {}, {'Enlivening Overflow': {'p1': 18, 'p2': 2}})
        html = issues_html({'build_issues': tracker.second_source_findings(1000, 'p2')})
        self.assertIn('href="https://eso-hub.com/en/champion-points/star/enlivening-overflow"', html)
        self.assertIn('Enlivening Overflow on ESO-Hub', html)


if __name__ == '__main__':
    unittest.main()
