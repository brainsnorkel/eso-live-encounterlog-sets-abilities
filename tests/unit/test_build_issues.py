#!/usr/bin/env python3
"""Possible build issues (issue #16): the per-fight rules on a logged build,
the per-session rules on proc sets, and what the engine puts on a fight
entry (no Qt needed).

The gear lines follow the log's PLAYER_INFO item fields (see
docs/reference/gear-slots.md); the item ids used are ones the bundled
tables know (200834 a dagger, 133257 a lightning staff, 187194 an ice
staff, 71130 the Maelstrom's Greatsword, 139 Webspinner's Brace, a shield)
or, for the rule tests, ids in small tables passed in.
"""

import unittest

from build_session import fights as _fights

import build_issues
from build_issues import (
    ELEMENTAL_DRAIN_IDS,
    GROUP_SETS,
    LONG_FIGHT_S,
    OAKENSOUL_SET_ID,
    PROC_EFFECT_IDS,
    PROC_SETS,
    BuildIssueTracker,
    bar_weapon_line,
    fired_proc_sets,
    heavy_pieces,
    skill_line_of_slot,
    structural_findings,
    worn_proc_sets,
)

# Item ids for the rule tests, with the tables that name them
WEIGHTS = {'h': 'heavy', 'm': 'medium', 'l': 'light'}
TYPES = {'dagger': 'dagger', 'sword': 'sword', 'axe': 'axe', 'shield': 'shield',
         'inferno': 'inferno_staff', 'ice': 'ice_staff', 'resto': 'restoration_staff',
         'gs': 'greatsword', 'bow': 'bow'}
SKILLS = {
    '38788': {'line': 'Two Handed', 'name': 'Stampede'},
    '38689': {'line': 'Bow', 'name': 'Endless Hail'},
    '39011': {'line': 'Destruction Staff', 'name': 'Elemental Blockade'},
    '38250': {'line': 'One Hand and Shield', 'name': 'Pierce Armor'},
    '37232': {'line': 'Restoration Staff', 'name': 'Steadfast Ward'},
    '39089': {'line': 'Destruction Staff', 'name': 'Elemental Susceptibility'},
    '39095': {'line': 'Destruction Staff', 'name': 'Elemental Drain'},
}
ARMOR = ('HEAD', 'SHOULDERS', 'CHEST', 'HAND', 'WAIST', 'LEGS', 'FEET')


def _item(slot, item_id='m', trait='ARMOR_DIVINES', set_id='0', enchant='MAGICKA'):
    return [slot, item_id, 'T', '16', trait, 'LEGENDARY', set_id, enchant, 'T', '16', 'LEGENDARY']


def _weapon(slot, item_id='dagger', trait='WEAPON_PRECISE', enchant='FIERY_WEAPON', set_id='0'):
    return _item(slot, item_id, trait, set_id, enchant)


def _body(weights='mmmmmmm', set_id='0'):
    """Seven armor pieces of the given weights (h, m, l per slot) and three jewels."""
    gear = {slot: _item(slot, weight, set_id=set_id) for slot, weight in zip(ARMOR, weights)}
    for slot in ('NECK', 'RING1', 'RING2'):
        gear[slot] = _item(slot, 'j', 'JEWELRY_BLOODTHIRSTY', set_id, 'INCREASE_SPELL_DAMAGE')
    return gear


def _slot(ability_id, name='Skill', icon='ability_test'):
    return {'id': str(ability_id), 'name': name, 'icon': icon}


def _findings(gear, front=(), back=(), role='D', taunted=False, **kw):
    return structural_findings(gear, list(front), list(back), role, taunted,
                               weights=WEIGHTS, types=TYPES, skills=SKILLS, **kw)


def _rules(findings):
    return [f['rule'] for f in findings]


class TestFindingShape(unittest.TestCase):

    def test_a_clean_build_has_no_findings(self):
        gear = _body('lmmmmmm')
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'inferno')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'ice', enchant='BERSERKER')
        self.assertEqual(_findings(gear, [_slot('39011')], [_slot('39089')]), [])
        self.assertEqual(_findings({}, [], []), [])

    def test_every_finding_names_its_item_and_states_its_rule(self):
        gear = _body('hhhhhmm')
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'dagger', enchant='ABSORB_STAMINA')
        gear['OFF_HAND'] = _weapon('OFF_HAND', 'dagger', 'WEAPON_NIRNHONED', 'ABSORB_STAMINA')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'inferno')
        findings = _findings(gear, [], [_slot('38788', 'Stampede'), _slot('39095', 'Elemental Drain')])
        self.assertEqual(_rules(findings), ['nirnhoned-off-hand', 'duplicate-glyph', 'heavy-armor',
                                            'wrong-weapon', 'elemental-drain'])
        for finding in findings:
            self.assertEqual(set(finding), {'rule', 'title', 'detail', 'set', 'skill'})
            self.assertTrue(finding['title'] and finding['detail'])
            # The rule is stated, not just the observation
            self.assertGreater(len(finding['detail']), len(finding['title']))


class TestNirnhoned(unittest.TestCase):

    def test_off_hand_dagger_on_either_bar(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND')
        gear['OFF_HAND'] = _weapon('OFF_HAND', trait='WEAPON_NIRNHONED', enchant='POISONED_WEAPON')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'sword')
        gear['BACKUP_OFF'] = _weapon('BACKUP_OFF', 'axe', 'WEAPON_NIRNHONED', 'POISONED_WEAPON')
        findings = _findings(gear)
        self.assertEqual([f['title'] for f in findings],
                         ['Nirnhoned on the off-hand Dagger (front bar)',
                          'Nirnhoned on the off-hand Axe (back bar)'])
        self.assertIn('6% of an off-hand weapon', findings[0]['detail'])
        self.assertIn('sixteenth', findings[0]['detail'])

    def test_main_hand_nirnhoned_and_a_nirnhoned_shield_are_fine(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'sword', 'WEAPON_NIRNHONED')
        gear['OFF_HAND'] = _item('OFF_HAND', 'shield', 'ARMOR_NIRNHONED', '0', 'HEALTH')
        self.assertEqual(_findings(gear), [])

    def test_an_unknown_off_hand_weapon_still_counts(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'unknown-id')
        gear['OFF_HAND'] = _weapon('OFF_HAND', 'unknown-id', 'WEAPON_NIRNHONED', 'POISONED_WEAPON')
        self.assertEqual([f['title'] for f in _findings(gear)],
                         ['Nirnhoned on the off-hand weapon (front bar)'])


class TestDuplicateGlyph(unittest.TestCase):

    def test_the_same_glyph_on_both_weapons_of_a_bar(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', enchant='ABSORB_STAMINA')
        gear['OFF_HAND'] = _weapon('OFF_HAND', enchant='ABSORB_STAMINA')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', enchant='BERSERKER')
        gear['BACKUP_OFF'] = _weapon('BACKUP_OFF', enchant='BERSERKER')
        findings = _findings(gear)
        self.assertEqual([f['title'] for f in findings],
                         ['Two Absorb Stamina glyphs on the front bar',
                          'Two Weapon Damage glyphs on the back bar'])
        self.assertIn('share one cooldown', findings[0]['detail'])

    def test_the_same_glyph_on_different_bars_is_fine(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', enchant='BERSERKER')
        gear['OFF_HAND'] = _weapon('OFF_HAND', enchant='FIERY_WEAPON')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'inferno', enchant='BERSERKER')
        self.assertEqual(_findings(gear), [])

    def test_a_shields_glyph_and_an_empty_glyph_are_not_compared(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'sword', enchant='MAGICKA')
        gear['OFF_HAND'] = _item('OFF_HAND', 'shield', 'ARMOR_STURDY', '0', 'MAGICKA')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', enchant='INVALID')
        gear['BACKUP_OFF'] = _weapon('BACKUP_OFF', enchant='INVALID')
        self.assertEqual(_findings(gear), [])


class TestHeavyArmor(unittest.TestCase):

    def test_two_or_more_heavy_pieces_on_a_damage_dealer(self):
        for weights, count in (('hhhhhhh', 7), ('hhhhhlm', 5), ('hhmmmmm', 2)):
            findings = _findings(_body(weights))
            self.assertEqual([f['title'] for f in findings],
                             [f'{count} heavy armor pieces on a damage dealer'], weights)
        self.assertIn('Undaunted Mettle', _findings(_body('hhmmmmm'))[0]['detail'])

    def test_one_heavy_piece_is_the_undaunted_mettle_norm(self):
        self.assertEqual(_findings(_body('hlmmmmm')), [])
        self.assertEqual(_findings(_body('mmmmmmm')), [])

    def test_tanks_healers_and_taunters_are_not_judged(self):
        gear = _body('hhhhhlm')
        self.assertEqual(_findings(gear, role='T'), [])
        self.assertEqual(_findings(gear, role='H'), [])
        self.assertEqual(_findings(gear, role='D', taunted=True), [])

    def test_pieces_the_weight_table_lacks_are_not_counted(self):
        gear = _body('h??????')
        self.assertEqual(heavy_pieces(gear, WEIGHTS), 1)
        self.assertEqual(_findings(gear), [])


class TestWrongWeapon(unittest.TestCase):

    def test_stampede_on_a_staff_back_bar(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND')
        gear['OFF_HAND'] = _weapon('OFF_HAND', enchant='POISONED_WEAPON')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'inferno')
        findings = _findings(gear, [_slot('38250', 'Pierce Armor')],
                             [_slot('38788', 'Stampede'), _slot('39011', 'Elemental Blockade')])
        self.assertEqual([f['title'] for f in findings],
                         ['Pierce Armor cannot be cast from the front bar',
                          'Stampede cannot be cast from the back bar'])
        self.assertIn('One Hand and Shield skill and the front bar holds two Daggers',
                      findings[0]['detail'])
        self.assertIn('Two Handed skill and the back bar holds an Inferno Staff',
                      findings[1]['detail'])
        self.assertEqual(findings[1]['skill'], 'Stampede')

    def test_the_bars_own_line_and_non_weapon_skills_pass(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'sword')
        gear['OFF_HAND'] = _item('OFF_HAND', 'shield', 'ARMOR_STURDY', '0', 'HEALTH')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'gs')
        self.assertEqual(_findings(gear, [_slot('38250', 'Pierce Armor'), _slot('1', 'Class Skill')],
                                   [_slot('38788', 'Stampede')]), [])

    def test_the_back_bar_under_oakensoul_is_skipped(self):
        gear = _body()
        gear['RING1'] = _item('RING1', 'j', 'JEWELRY_ARCANE', OAKENSOUL_SET_ID, 'MAGICKA')
        gear['MAIN_HAND'] = _weapon('MAIN_HAND')
        gear['OFF_HAND'] = _weapon('OFF_HAND', enchant='POISONED_WEAPON')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'bow')
        self.assertEqual(_findings(gear, [], [_slot('38788', 'Stampede')]), [])
        # The front bar is still judged
        self.assertEqual(_rules(_findings(gear, [_slot('38788', 'Stampede')], [])), ['wrong-weapon'])

    def test_an_unknown_weapon_or_a_lone_one_hander_is_not_judged(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'unknown-id')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'sword')  # no off hand logged
        self.assertEqual(_findings(gear, [_slot('38788', 'Stampede')], [_slot('38788', 'Stampede')]), [])

    def test_a_scribed_skill_is_judged_by_its_grimoire(self):
        gear = _body()
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'inferno')
        smash = _slot('999999', 'Smash', 'ability_grimoire_2handed')
        explosion = _slot('999998', 'Elemental Explosion', 'ability_grimoire_staffdestro')
        banner = _slot('999997', 'Shocking Banner', 'ability_grimoire_support')
        self.assertEqual([f['title'] for f in _findings(gear, [smash, explosion, banner])],
                         ['Smash cannot be cast from the front bar'])

    def test_bar_lines(self):
        def line(main, off=None):
            gear = {'MAIN_HAND': _weapon('MAIN_HAND', main)}
            if off == 'shield':
                gear['OFF_HAND'] = _item('OFF_HAND', 'shield', 'ARMOR_STURDY', '0', 'HEALTH')
            elif off:
                gear['OFF_HAND'] = _weapon('OFF_HAND', off)
            return bar_weapon_line(gear, 'MAIN_HAND', 'OFF_HAND', TYPES)
        self.assertEqual(line('gs'), ('Two Handed', 'a Greatsword'))
        self.assertEqual(line('bow'), ('Bow', 'a Bow'))
        self.assertEqual(line('ice'), ('Destruction Staff', 'an Ice Staff'))
        self.assertEqual(line('resto'), ('Restoration Staff', 'a Restoration Staff'))
        self.assertEqual(line('sword', 'shield'), ('One Hand and Shield', 'a Sword and a Shield'))
        self.assertEqual(line('dagger', 'dagger'), ('Dual Wield', 'two Daggers'))
        self.assertEqual(line('axe', 'dagger'), ('Dual Wield', 'an Axe and a Dagger'))
        self.assertEqual(line('sword'), ('', ''))
        self.assertEqual(line('unknown-id', 'dagger'), ('', ''))
        self.assertEqual(bar_weapon_line({}, 'MAIN_HAND', 'OFF_HAND', TYPES), ('', ''))

    def test_skill_lines_come_from_the_table_then_the_grimoire_icon(self):
        self.assertEqual(skill_line_of_slot(_slot('38689'), SKILLS), 'Bow')
        self.assertEqual(skill_line_of_slot(_slot('1', 'Class Skill'), SKILLS), '')
        self.assertEqual(skill_line_of_slot(_slot('1', 'Vault', 'ability_grimoire_bow'), SKILLS), 'Bow')
        self.assertEqual(skill_line_of_slot(_slot('1', 'Banner', 'ability_grimoire_support'), SKILLS), '')
        # The bundled table knows the weapon skills seen in real logs
        self.assertEqual(skill_line_of_slot(_slot('38788')), 'Two Handed')
        self.assertEqual(skill_line_of_slot(_slot('217228')), 'Destruction Staff')  # Elemental Explosion


class TestElementalDrain(unittest.TestCase):

    def test_drain_on_a_bar_at_any_rank(self):
        for ability_id in sorted(ELEMENTAL_DRAIN_IDS):
            findings = _findings(_body(), [], [_slot(ability_id, 'Elemental Drain')])
            self.assertEqual([f['title'] for f in findings], ['Elemental Drain slotted (back bar)'])
            self.assertIn('Elemental Susceptibility', findings[0]['detail'])
            self.assertIn('every 7.5 seconds', findings[0]['detail'])
            self.assertEqual(findings[0]['skill'], 'Elemental Drain')

    def test_susceptibility_is_fine(self):
        self.assertEqual(_findings(_body(), [_slot('39089', 'Elemental Susceptibility')]), [])


class TestGroupSetOnOneBar(unittest.TestCase):

    def test_pearlescent_ward_on_the_back_bar_only(self):
        gear = _body('mmmmmmm', set_id='648')
        gear['NECK'] = _item('NECK', 'j', 'JEWELRY_ARCANE', '0')  # four body pieces, with the rings
        gear['RING1'] = _item('RING1', 'j', 'JEWELRY_ARCANE', '0')
        gear['RING2'] = _item('RING2', 'j', 'JEWELRY_ARCANE', '0')
        for slot in ARMOR[4:]:
            gear[slot] = _item(slot, 'm', set_id='0')  # HEAD..HAND stay: four pieces of 648
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'ice')
        gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'sword', set_id='648')
        gear['BACKUP_OFF'] = _item('BACKUP_OFF', 'shield', 'ARMOR_STURDY', '0', 'HEALTH')
        findings = _findings(gear, role='T')
        self.assertEqual([f['title'] for f in findings],
                         ['Pearlescent Ward is complete only on the back bar (4/5 pieces)'])
        self.assertIn('loses it every time this player swaps', findings[0]['detail'])
        self.assertEqual(findings[0]['set'], 'Pearlescent Ward')

    def test_both_bars_a_front_bar_damage_set_oakensoul_and_one_bar_builds_pass(self):
        complete = _body('mmmmmmm', set_id='769')  # five body pieces of Xoryn's Masterpiece
        for slot in ('NECK', 'RING1', 'RING2', 'HAND', 'WAIST'):
            complete[slot] = _item(slot, 'm', set_id='0')
        complete['MAIN_HAND'] = _weapon('MAIN_HAND', 'inferno')
        complete['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'ice')
        self.assertEqual(_findings(complete, role='H'), [])
        # Deadly Strike (set 429) at 5/3 is the normal front-bar set
        deadly = _body('mmmmmmm', set_id='429')
        for slot in ('NECK', 'RING1', 'RING2', 'HAND', 'WAIST', 'LEGS', 'FEET'):
            deadly[slot] = _item(slot, 'm', set_id='0')
        deadly['MAIN_HAND'] = _weapon('MAIN_HAND', set_id='429')
        deadly['OFF_HAND'] = _weapon('OFF_HAND', set_id='429', enchant='POISONED_WEAPON')
        deadly['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', 'bow')
        self.assertEqual(_findings(deadly), [])
        # Lucent Echoes 5/3 under Oakensoul, and with no back bar at all
        lucent = dict(deadly)
        for slot in ('HEAD', 'SHOULDERS', 'CHEST', 'MAIN_HAND', 'OFF_HAND'):
            lucent[slot][6] = '768'
        lucent['RING1'] = _item('RING1', 'j', 'JEWELRY_ARCANE', OAKENSOUL_SET_ID)
        self.assertEqual(_findings(lucent), [])
        del lucent['RING1'], lucent['BACKUP_MAIN']
        self.assertEqual(_findings(lucent), [])
        self.assertEqual(set(GROUP_SETS), {'648', '651', '768', '771', '769', '770'})


class TestTankWithoutTaunt(unittest.TestCase):
    """A tank with no taunt or pull: the role, tank gear, a small share of
    the damage and no healer sign, and nothing on the bars that holds a
    boss, with no taunt logged this session."""

    def _tank(self, main='sword', off='shield', back='ice', weights='hmmmmmm'):
        gear = _body(weights)
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', main, 'WEAPON_DEFENDING', 'REDUCE_ARMOR')
        if off == 'shield':
            gear['OFF_HAND'] = _item('OFF_HAND', 'shield', 'ARMOR_STURDY', '0', 'HEALTH')
        elif off:
            gear['OFF_HAND'] = _weapon('OFF_HAND', off, enchant='POISONED_WEAPON')
        if back:
            gear['BACKUP_MAIN'] = _weapon('BACKUP_MAIN', back, 'WEAPON_INFUSED', 'REDUCE_ARMOR')
        return gear

    def _tank_findings(self, gear, front=(), back=(), **kw):
        kw.setdefault('role', 'T')
        kw.setdefault('damage_ratio', 0.2)
        return _findings(gear, front or [_slot('1', 'Heroic Slash')],
                         back or [_slot('2', 'Class Skill')], **kw)

    def test_a_shield_tank_with_nothing_to_hold_the_boss(self):
        findings = self._tank_findings(self._tank())
        self.assertEqual(_rules(findings), ['tank-no-taunt'])
        self.assertEqual(findings[0]['title'], 'Tank with no taunt or pull on either bar')
        self.assertIn('they hold a shield', findings[0]['detail'])
        self.assertIn('20% of an equal share', findings[0]['detail'])
        self.assertIn('no taunt of theirs was logged this session', findings[0]['detail'])

    def test_any_taunt_or_pull_on_either_bar_clears_it(self):
        gear = self._tank()
        grimoire = 'ability_grimoire_1handed'
        for slot in (_slot('38250', 'Pierce Armor'),            # a taunt by id
                     _slot('x', 'Inner Rage'),                  # by name, an id the tables lack
                     _slot('43393', 'Skill'),                   # a rank id, name unknown
                     _slot('20492', 'Chains of Flame'),         # a pull
                     _slot('x', 'Silver Leash'),
                     _slot('86175', 'Frozen Gate'),
                     _slot('x', 'Leashing Soul'),               # a scribed pull by name
                     {'id': '222966', 'name': 'Goading Throw', 'icon': grimoire,
                      'scripts': ['Taunt', 'Anchorite', 'Heroism']},
                     {'id': 'y', 'name': 'Shield Throw', 'icon': grimoire,
                      'scripts': ['Pull', 'Anchorite', 'Heroism']},
                     {'id': 'z', 'name': 'Shield Throw', 'icon': grimoire,
                      'script_options': [['Shield Throw', 'Physical Damage', 'a', 'b'],
                                         ['Goading Throw', 'Taunt', 'a', 'b']]}):
            # Either bar clears it (a weapon skill on the wrong bar may draw
            # that rule's own finding, which is right)
            self.assertNotIn('tank-no-taunt', _rules(self._tank_findings(gear, front=[slot])), slot)
            self.assertNotIn('tank-no-taunt', _rules(self._tank_findings(gear, back=[slot])), slot)
        # Destructive Clench taunts with the ice staff in hand, not otherwise
        clench = _slot('38984', 'Destructive Clench')
        self.assertEqual(self._tank_findings(gear, back=[clench]), [])
        self.assertEqual(_rules(self._tank_findings(gear, front=[clench])), ['tank-no-taunt'])
        self.assertEqual(_rules(self._tank_findings(self._tank(back='inferno'), back=[clench])),
                         ['tank-no-taunt'])
        self.assertEqual(build_issues.taunts_and_pulls(gear, [_slot('38250')], [_slot('20492')], TYPES),
                         {'taunt', 'pull'})

    def test_the_gates(self):
        gear = self._tank()
        self.assertEqual(self._tank_findings(gear, role='D'), [])
        self.assertEqual(self._tank_findings(gear, role='H'), [])
        self.assertEqual(self._tank_findings(gear, taunted=True), [])
        self.assertEqual(self._tank_findings(gear, damage_ratio=0.9), [])
        self.assertEqual(self._tank_findings(gear, damage_ratio=None), [])
        self.assertEqual(self._tank_findings(gear, out_heals=True), [])
        self.assertEqual(_findings(gear, [], [], role='T', damage_ratio=0.2), [])  # bars not logged
        self.assertEqual(self._tank_findings(self._tank(back='resto')), [])  # a healer's staff
        # No tank gear: two daggers, an inferno staff, one heavy piece
        plain = self._tank(main='dagger', off='dagger', back='inferno')
        self.assertEqual(self._tank_findings(plain), [])
        self.assertEqual(build_issues.tank_gear(plain, WEIGHTS, TYPES), '')
        # Each tank sign alone is enough
        ice = self._tank(main='dagger', off='dagger', back='ice')
        self.assertIn('they hold an ice staff', self._tank_findings(ice)[0]['detail'])
        heavy = self._tank(main='dagger', off='dagger', back='inferno', weights='hhhhhmm')
        self.assertIn('they hold 5 heavy pieces', self._tank_findings(heavy)[0]['detail'])
        self.assertEqual(self._tank_findings(self._tank(weights='hhhhmmm', main='dagger', off='dagger',
                                                        back='inferno')), [])


class TestTracker(unittest.TestCase):

    def test_a_long_fight_without_the_proc_is_a_finding(self):
        tracker = BuildIssueTracker()
        tracker.note_fight('p1', 1000, 90.0, {'232'}, set())
        findings = tracker.findings('p1', {'232'})
        self.assertEqual([f['title'] for f in findings],
                         ['Roar of Alkosh never fired in 1 fight of a minute or more'])
        self.assertIn('activates a synergy', findings[0]['detail'])
        self.assertEqual(findings[0]['set'], 'Roar of Alkosh')
        tracker.note_fight('p1', 200000, LONG_FIGHT_S, {'232'}, set())
        self.assertEqual(tracker.findings('p1', {'232'})[0]['title'],
                         'Roar of Alkosh never fired in 2 fights of a minute or more')
        # Another player, and a set not worn this fight, are not reported
        self.assertEqual(tracker.findings('p2', {'232'}), [])
        self.assertEqual(tracker.findings('p1', set()), [])

    def test_short_fights_do_not_count_and_one_fire_clears_the_session(self):
        tracker = BuildIssueTracker()
        tracker.note_fight('p1', 1000, 20.0, {'496'}, set())
        self.assertEqual(tracker.findings('p1', {'496'}), [])
        tracker.note_fight('p1', 50000, 15.0, {'496'}, {'496'})
        tracker.note_fight('p1', 90000, 120.0, {'496'}, set())
        self.assertEqual(tracker.findings('p1', {'496'}), [])
        self.assertEqual(tracker.long_fights('p1', '496'), (1, True))

    def test_a_fight_cut_in_two_counts_once_and_reset_forgets(self):
        tracker = BuildIssueTracker()
        tracker.note_fight('p1', 1000, 30.0, {'497'}, set())
        tracker.note_fight('p1', 1000, 70.0, {'497'}, set())  # the same fight, republished
        self.assertEqual(tracker.long_fights('p1', '497'), (1, False))
        self.assertEqual(tracker.findings('p1', {'497'})[0]['title'],
                         'Perfected Roaring Opportunist never fired in 1 fight of a minute or more')
        self.assertIn('fully charged heavy attack', tracker.findings('p1', {'497'})[0]['detail'])
        tracker.note_taunt('p1')
        self.assertTrue(tracker.has_taunted('p1'))
        tracker.reset()
        self.assertEqual(tracker.findings('p1', {'497'}), [])
        self.assertFalse(tracker.has_taunted('p1'))

    def test_worn_and_fired_sets(self):
        gear = _body('mmmmmmm', set_id='232')
        for slot in ('NECK', 'RING1', 'RING2', 'HAND', 'WAIST'):
            gear[slot] = _item(slot, 'm', set_id='0')
        self.assertEqual(worn_proc_sets(gear), {'232'})
        gear['FEET'] = _item('FEET', 'm', set_id='0')  # four pieces
        self.assertEqual(worn_proc_sets(gear), set())
        gear['MAIN_HAND'] = _weapon('MAIN_HAND', 'inferno', set_id='232')  # a two-hander is two
        self.assertEqual(worn_proc_sets(gear), {'232'})
        self.assertEqual(fired_proc_sets({'232', '496'}, {'76667', '1'}), {'232'})
        self.assertEqual(fired_proc_sets({'232', '496'}, {'135923'}), {'496'})
        self.assertEqual(fired_proc_sets({'232'}, []), set())
        self.assertTrue({'76667', '75751', '93109', '135923'} <= PROC_EFFECT_IDS)
        self.assertEqual(set(PROC_SETS), {'232', '496', '497'})


# ---- the engine ----

EPOCH = 1759600000000
BOSS = '70,105634/105634,0/0,0/0,0/0,0/0,0,0.4081,0.5662,0.0256'


def _unit(unit_id, health=22762, magicka=26657, stamina=13021):
    return (f'{unit_id},{health}/{health},{magicka}/{magicka},{stamina}/{stamina},'
            f'500/500,1000/1000,0,0.2696,0.5942,5.5492')


def _hit(ts, unit_id, damage=1000, **pools):
    return (f'{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{damage},0,4021667,12345,'
            f'{_unit(unit_id, **pools)},{BOSS}')


def _cast(ts, unit_id, **pools):
    """A BEGIN_CAST, which is where the engine reads a player's pools."""
    return f'{ts},BEGIN_CAST,0,F,4021667,12345,{_unit(unit_id, **pools)},{BOSS}'


def _gained(ts, unit_id, ability_id):
    return f'{ts},EFFECT_CHANGED,GAINED,1,4021668,{ability_id},{_unit(unit_id)},{BOSS}'


def _taunt(ts, unit_id):
    return f'{ts},COMBAT_EVENT,TAUNTED,GENERIC,0,0,0,4021669,38254,{_unit(unit_id)},{BOSS}'


def _gear(items):
    return '[' + ','.join('[' + ','.join(item) + ']' for item in items) + ']'


# Two daggers, the off hand Nirnhoned; a stamina DPS
NIRN_GEAR = _gear([
    _item('HEAD', '95044', set_id='270'), _item('CHEST', '210250', set_id='781'),
    _weapon('MAIN_HAND', '200834', 'WEAPON_PRECISE', 'POISONED_WEAPON', '726'),
    _weapon('OFF_HAND', '200834', 'WEAPON_NIRNHONED', 'FIERY_WEAPON', '726'),
    _weapon('BACKUP_MAIN', '133257', 'WEAPON_INFUSED', 'BERSERKER', '361'),
])
# Five pieces of Roar of Alkosh on the body, two staves
ALKOSH_GEAR = _gear([
    _item(slot, '95044', set_id='232') for slot in ('HEAD', 'SHOULDERS', 'CHEST', 'LEGS', 'FEET')
] + [_weapon('MAIN_HAND', '133257', 'WEAPON_INFUSED', 'FIERY_WEAPON', '0'),
     _weapon('BACKUP_MAIN', '187194', 'WEAPON_INFUSED', 'BERSERKER', '0')])


def _heavy_ids(count=5):
    """Item ids the bundled weight table lists as heavy (95044 and 210250,
    used above, are medium)."""
    import json

    from ability_icons import bundle_root
    table = json.loads(bundle_root().joinpath('data', 'items', 'armor_weights.json')
                       .read_text(encoding='utf-8'))
    return tuple(str(i) for i in (table.get('heavy') or [])[:count])


def _session(*fights, zone='"Scalecaller Peak",VETERAN'):
    lines = [
        f'1000,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
        f'1000,ZONE_CHANGED,1055,{zone}',
        '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Stabby","@nirn",1001,50,3224,0,PLAYER_ALLY,T',
        '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,1,7,"Roaring","@alkosh",1002,50,1962,0,PLAYER_ALLY,T',
        '2500,UNIT_ADDED,70,MONSTER,F,0,105634,T,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
        '2600,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
        '2600,ABILITY_INFO,38788,"Stampede","/esoui/art/icons/ability_2handed_005.dds",F,F',
        '2600,ABILITY_INFO,76667,"Roar of Alkosh","/esoui/art/icons/ability_alkosh.dds",T,T',
    ]
    for fight in fights:
        lines.extend(fight)
    return lines


def _fight(begin, end, alkosh_fires=False, player1_bars='[12345],[38788]'):
    lines = [f'{begin},BEGIN_COMBAT',
             f'{begin + 1},PLAYER_INFO,1,[],[],{NIRN_GEAR},{player1_bars}',
             f'{begin + 1},PLAYER_INFO,2,[],[],{ALKOSH_GEAR},[12345],[12345]',
             _cast(begin + 900, 1, stamina=30000),
             _hit(begin + 1000, 1, 90000, stamina=30000),
             _cast(begin + 1900, 2),
             _hit(begin + 2000, 2, 60000)]
    if alkosh_fires:
        lines.append(_gained(begin + 3000, 2, '76667'))
    lines.append(f'{end},END_COMBAT')
    return lines


class TestEngine(unittest.TestCase):

    def _players(self, entry):
        return {p['name']: p for p in entry.players}

    def test_every_player_gets_the_key_and_the_structural_findings(self):
        entries = _fights(_session(_fight(10000, 30000)))
        self.assertEqual(len(entries), 1)
        players = self._players(entries[0])
        nirn = players['@nirn']['build_issues']
        self.assertEqual([f['rule'] for f in nirn], ['nirnhoned-off-hand', 'wrong-weapon'])
        self.assertEqual(nirn[0]['title'], 'Nirnhoned on the off-hand Dagger (front bar)')
        # Stampede on the back bar's lightning staff
        self.assertEqual(nirn[1]['title'], 'Stampede cannot be cast from the back bar')
        self.assertIn('a Lightning Staff', nirn[1]['detail'])
        # A 20 s fight is too short for the proc rule
        self.assertEqual(players['@alkosh']['build_issues'], [])

    def test_a_proc_set_that_never_fires_is_judged_over_the_session(self):
        # One long fight without the proc: a finding, with the fight counted
        entries = _fights(_session(_fight(10000, 100000)))
        alkosh = self._players(entries[0])['@alkosh']['build_issues']
        self.assertEqual([f['title'] for f in alkosh],
                         ['Roar of Alkosh never fired in 1 fight of a minute or more'])
        self.assertEqual(alkosh[0]['set'], 'Roar of Alkosh')
        # Two long fights, then one in which it fires: the third fight is clean
        entries = _fights(_session(_fight(10000, 100000), _fight(200000, 300000),
                                   _fight(400000, 500000, alkosh_fires=True)))
        titles = [[f['title'] for f in self._players(e)['@alkosh']['build_issues']] for e in entries]
        self.assertEqual(titles, [['Roar of Alkosh never fired in 1 fight of a minute or more'],
                                  ['Roar of Alkosh never fired in 2 fights of a minute or more'],
                                  []])
        # It fired in a short first fight: never a finding
        entries = _fights(_session(_fight(10000, 20000, alkosh_fires=True), _fight(200000, 300000)))
        self.assertEqual([self._players(e)['@alkosh']['build_issues'] for e in entries], [[], []])

    def test_a_fight_the_game_cut_in_two_counts_once(self):
        first = ['10000,BEGIN_COMBAT',
                 f'10001,PLAYER_INFO,1,[],[],{NIRN_GEAR},[12345],[12345]',
                 f'10001,PLAYER_INFO,2,[],[],{ALKOSH_GEAR},[12345],[12345]',
                 _hit(11000, 2, 60000), _hit(39000, 2, 1000), '40000,END_COMBAT']
        second = [_hit(40020, 2, 1000), '40050,BEGIN_COMBAT',
                  f'40051,PLAYER_INFO,1,[],[],{NIRN_GEAR},[12345],[12345]',
                  f'40051,PLAYER_INFO,2,[],[],{ALKOSH_GEAR},[12345],[12345]',
                  _hit(50000, 2, 1000), '90000,END_COMBAT']
        entries = _fights(_session(first + second))
        self.assertEqual(len(entries), 1)
        self.assertAlmostEqual(entries[0].duration_s, 80.0)
        alkosh = self._players(entries[0])['@alkosh']['build_issues']
        self.assertEqual([f['title'] for f in alkosh],
                         ['Roar of Alkosh never fired in 1 fight of a minute or more'])

    def test_a_player_who_taunted_is_not_a_damage_dealer_in_heavy(self):
        heavy_ids = _heavy_ids()
        if len(heavy_ids) < 5:
            self.skipTest('the bundled weight table is missing')
        heavy = _gear([_item(slot, item_id, 'ARMOR_STURDY', '0', 'HEALTH')
                       for slot, item_id in zip(('HEAD', 'SHOULDERS', 'CHEST', 'LEGS', 'FEET'), heavy_ids)]
                      + [_weapon('MAIN_HAND', '200834', 'WEAPON_PRECISE', 'POISONED_WEAPON', '0')])
        def fight(begin, end, taunts):
            lines = [f'{begin},BEGIN_COMBAT',
                     f'{begin + 1},PLAYER_INFO,1,[],[],{heavy},[12345],[12345]',
                     _cast(begin + 900, 1, stamina=40000),
                     _hit(begin + 1000, 1, 90000, stamina=40000)]
            if taunts:
                lines.append(_taunt(begin + 1500, 1))
            lines.append(f'{end},END_COMBAT')
            return lines
        self.assertEqual(build_issues.heavy_pieces({'HEAD': _item('HEAD', heavy_ids[0])}), 1)
        # Stamina-dominant, never taunted: a damage dealer in five heavy
        entries = _fights(_session(fight(10000, 30000, taunts=False)))
        self.assertEqual([f['rule'] for f in self._players(entries[0])['@nirn']['build_issues']],
                         ['heavy-armor'])
        # The same build after a taunt in an earlier fight: a tank, whatever the pools say
        entries = _fights(_session(fight(10000, 30000, taunts=True), fight(50000, 70000, taunts=False)))
        self.assertEqual([self._players(e)['@nirn']['build_issues'] for e in entries], [[], []])

    def test_a_tank_with_no_taunt_or_pull_until_they_taunt(self):
        # A dagger and a shield (139, Webspinner's Brace), health the largest pool
        tank = _gear([_item('HEAD', '95044'),
                      _weapon('MAIN_HAND', '200834', 'WEAPON_DEFENDING', 'REDUCE_ARMOR', '0'),
                      _item('OFF_HAND', '139', 'ARMOR_STURDY', '0', 'HEALTH')])

        def fight(begin, end, taunts):
            lines = [f'{begin},BEGIN_COMBAT',
                     f'{begin + 1},PLAYER_INFO,1,[],[],{NIRN_GEAR},[12345],[12345]',
                     f'{begin + 1},PLAYER_INFO,2,[],[],{tank},[12345],[12345]',
                     _cast(begin + 900, 1, stamina=30000),
                     _hit(begin + 1000, 1, 90000, stamina=30000),
                     _cast(begin + 1900, 2, health=45000),
                     _hit(begin + 2000, 2, 1000, health=45000)]
            if taunts:
                lines.append(_taunt(begin + 2500, 2))
            lines.append(f'{end},END_COMBAT')
            return lines

        entries = _fights(_session(fight(10000, 40000, taunts=False)))
        player = self._players(entries[0])['@alkosh']
        self.assertEqual(player['role'], 'T')
        self.assertEqual([f['rule'] for f in player['build_issues']], ['tank-no-taunt'])
        # 1,000 of 91,000 damage between two players: 2% of an equal share
        self.assertIn('they hold a shield, and they dealt 2% of an equal share',
                      player['build_issues'][0]['detail'])
        # A taunt in the first fight clears it for the session
        entries = _fights(_session(fight(10000, 40000, taunts=True), fight(50000, 80000, taunts=False)))
        self.assertEqual([self._players(e)['@alkosh']['build_issues'] for e in entries], [[], []])

    def test_the_shared_fixture_session_is_clean(self):
        for player in _fights()[0].players:
            self.assertIn('build_issues', player)
        self.assertEqual([p['build_issues'] for p in _fights()[0].players if p['name'] == '@brainsnorkel'],
                         [[]])


if __name__ == '__main__':
    unittest.main()
