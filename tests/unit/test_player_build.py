#!/usr/bin/env python3
"""Player builds from PLAYER_INFO: gear rows with labels, armor weights and
per-bar piece counts, poison names, mundus stones, food, and what the engine
puts on a fight entry (no Qt needed)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fixtures'))

import player_build  # noqa: E402
from build_session import (  # noqa: E402
    SESSION, fights as _fights, real_gear as _real_gear)
from player_build import (  # noqa: E402
    SLOT_GROUPS, SLOT_LABELS, SLOT_ORDER, armor_weight, build_fields, display_quality,
    enchant_label, food_buff, food_table, gear_rows, is_two_handed, level_label,
    mundus_stones, piece_counts, poison_name, poison_tier, quality_label, race_name,
    trait_label, weight_label)

# Every value the October 2026 survey found (design.md), with what it shows as
TRAITS = {
    'ARMOR_DIVINES': 'Divines', 'JEWELRY_BLOODTHIRSTY': 'Bloodthirsty',
    'WEAPON_INFUSED': 'Infused', 'JEWELRY_INFUSED': 'Infused', 'WEAPON_CHARGED': 'Charged',
    'ARMOR_REINFORCED': 'Reinforced', 'WEAPON_NIRNHONED': 'Nirnhoned',
    'ARMOR_STURDY': 'Sturdy', 'ARMOR_INFUSED': 'Infused', 'WEAPON_PRECISE': 'Precise',
    'JEWELRY_HARMONY': 'Harmony', 'JEWELRY_ARCANE': 'Arcane', 'WEAPON_DECISIVE': 'Decisive',
    'ARMOR_IMPENETRABLE': 'Impenetrable', 'JEWELRY_HEALTHY': 'Healthy',
    'ARMOR_TRAINING': 'Training', 'WEAPON_POWERED': 'Powered', 'NONE': '',
    'ARMOR_NIRNHONED': 'Nirnhoned', 'WEAPON_DEFENDING': 'Defending',
    'ARMOR_PROSPEROUS': 'Invigorating', 'ARMOR_WELL_FITTED': 'Well-fitted',
    'WEAPON_SHARPENED': 'Sharpened', 'JEWELRY_ROBUST': 'Robust',
    'JEWELRY_PROTECTIVE': 'Protective', 'JEWELRY_TRIUNE': 'Triune', 'JEWELRY_SWIFT': 'Swift',
    'WEAPON_TRAINING': 'Training',
}
ENCHANTS = {
    'STAMINA': 'Stamina', 'MAGICKA': 'Magicka', 'HEALTH': 'Health',
    'INCREASE_PHYSICAL_DAMAGE': 'Increase Physical Harm',
    'INCREASE_SPELL_DAMAGE': 'Increase Magical Harm',
    'PRISMATIC_DEFENSE': 'Prismatic Defense', 'PRISMATIC_ONSLAUGHT': 'Prismatic Onslaught',
    'BERSERKER': 'Weapon Damage', 'POISONED_WEAPON': 'Poison', 'FIERY_WEAPON': 'Flame',
    'CHARGED_WEAPON': 'Shock', 'FROZEN_WEAPON': 'Frost', 'BEFOULED_WEAPON': 'Foulness',
    'REDUCE_SPELL_COST': 'Reduce Spell Cost', 'REDUCE_FEAT_COST': 'Reduce Feat Cost',
    'MAGICKA_REGEN': 'Magicka Recovery', 'STAMINA_REGEN': 'Stamina Recovery',
    'HEALTH_REGEN': 'Health Recovery', 'ABSORB_STAMINA': 'Absorb Stamina',
    'ABSORB_MAGICKA': 'Absorb Magicka', 'ABSORB_HEALTH': 'Absorb Health',
    'REDUCE_ARMOR': 'Crushing', 'REDUCE_POWER': 'Weakening', 'DAMAGE_SHIELD': 'Hardening',
    'DAMAGE_HEALTH': 'Decrease Health', 'DECREASE_PHYSICAL_DAMAGE': 'Decrease Physical Harm',
    'REDUCE_POTION_COOLDOWN': 'Potion Speed', 'REDUCE_BLOCK_AND_BASH': 'Bracing',
    'INCREASE_BASH_DAMAGE': 'Bashing', 'INVALID': '',
}
SLOTS = ('HEAD', 'SHOULDERS', 'CHEST', 'HAND', 'WAIST', 'LEGS', 'FEET', 'NECK', 'RING1',
         'RING2', 'MAIN_HAND', 'OFF_HAND', 'POISON', 'BACKUP_MAIN', 'BACKUP_OFF',
         'BACKUP_POISON')

POISONS = {'79690': {'name': 'Crown Lethal Poison', 'tiered': False},
           '76827': {'name': 'Damage Health Poison', 'tiered': True}}
FOOD = {'61255': {'kind': 'food', 'type': 'MAX_HEALTH_STAMINA'},
        '107789': {'kind': 'food', 'type': 'MAX_HEALTH_STAMINA_REGEN_HEALTH_STAMINA'},
        '84731': {'kind': 'drink', 'type': 'MAX_HEALTH_MAGICKA_REGEN_MAGICKA'},
        '84732': {'kind': 'drink', 'type': 'REGEN_HEALTH'},
        '84733': {'kind': 'drink', 'type': 'REGEN_HEALTH'}}
SET_NAMES = {'1': 'Alpha', '2': 'Beta', '3': 'Gamma', '9': 'Lone Ring'}
WEIGHTS = {'95044': 'medium', '501': 'light', '502': 'heavy'}
# Real pieces: Slimecraw Mask, Perfected Epaulets of the Depths, Spell Power
# Cure Robe, Cuirass of the Sergeant, Girdle of the Crimson Oath
REAL_WEIGHTS = {'95044': 'medium', '187287': 'light', '111885': 'light',
                '108766': 'heavy', '177413': 'heavy'}


def item(slot, set_id='0', item_id='100', trait=None, quality='LEGENDARY', enchant='STAMINA',
         enchant_quality='LEGENDARY', cp='T', level='16'):
    if trait is None:
        trait = ('WEAPON_INFUSED' if 'HAND' in slot and slot != 'HAND' or 'MAIN' in slot
                 or 'OFF' in slot else 'ARMOR_DIVINES')
    return [slot, item_id, cp, level, trait, quality, set_id, enchant, 'T', '16',
            enchant_quality]


def gear_of(*items):
    return {entry[0]: entry for entry in items}


def rows(gear, **kwargs):
    kwargs.setdefault('set_name_of', SET_NAMES.get)
    kwargs.setdefault('is_mythic', lambda name: name == 'Lone Ring')
    kwargs.setdefault('poisons', POISONS)
    kwargs.setdefault('weights', WEIGHTS)
    return {row['slot']: row for row in gear_rows(gear, **kwargs)}


class TestLabels(unittest.TestCase):

    def test_every_surveyed_trait_has_a_readable_name(self):
        for value, label in TRAITS.items():
            self.assertEqual(trait_label(value), label, value)

    def test_every_surveyed_enchant_has_a_readable_name(self):
        for value, label in ENCHANTS.items():
            self.assertEqual(enchant_label(value), label, value)

    def test_qualities_use_the_games_names(self):
        self.assertEqual([quality_label(q) for q in
                          ('TRASH', 'NORMAL', 'MAGIC', 'ARCANE', 'ARTIFACT', 'LEGENDARY',
                           'MYTHIC_OVERRIDE')],
                         ['Trash', 'Normal', 'Fine', 'Superior', 'Epic', 'Legendary', 'Mythic'])

    def test_a_piece_of_a_mythic_set_is_mythic_whatever_the_log_says(self):
        self.assertEqual(display_quality({'quality': 'LEGENDARY', 'mythic': True}),
                         'MYTHIC_OVERRIDE')
        self.assertEqual(display_quality({'quality': 'LEGENDARY', 'mythic': False}),
                         'LEGENDARY')

    def test_unknown_values_are_shown_in_a_readable_form(self):
        self.assertEqual(trait_label('WEAPON_NEW_TRAIT'), 'New Trait')
        self.assertEqual(trait_label('SOMETHING_ELSE'), 'Something Else')
        self.assertEqual(enchant_label('BRAND_NEW_GLYPH'), 'Brand New Glyph')
        self.assertEqual(quality_label('SHINY'), 'Shiny')

    def test_nothing_values_are_empty(self):
        for nothing in ('', 'NONE', 'INVALID', None):
            self.assertEqual((trait_label(nothing), enchant_label(nothing),
                              quality_label(nothing)), ('', '', ''))

    def test_level_is_named_only_below_the_cap(self):
        self.assertEqual(level_label(True, 16), '')
        self.assertEqual(level_label(True, 15), 'CP150')
        self.assertEqual(level_label(True, 6), 'CP60')
        self.assertEqual(level_label(False, 32), 'Level 32')
        self.assertEqual(level_label(False, 'x'), '')

    def test_slots_are_grouped_in_display_order(self):
        self.assertEqual(SLOT_ORDER, SLOTS)
        self.assertEqual([group for group, _slots in SLOT_GROUPS],
                         ['Armor', 'Jewelry', 'Front bar', 'Back bar'])
        self.assertEqual([SLOT_LABELS[s] for s in SLOTS],
                         ['Head', 'Shoulders', 'Chest', 'Hands', 'Waist', 'Legs', 'Feet',
                          'Neck', 'Ring 1', 'Ring 2', 'Main hand', 'Off hand', 'Poison',
                          'Main hand', 'Off hand', 'Poison'])

    def test_races(self):
        self.assertEqual([race_name(i) for i in range(1, 11)],
                         ['Breton', 'Redguard', 'Orc', 'Dark Elf', 'Nord', 'Argonian',
                          'High Elf', 'Wood Elf', 'Khajiit', 'Imperial'])
        self.assertEqual((race_name('7'), race_name(''), race_name('99')),
                         ('High Elf', '', ''))


class TestPoisons(unittest.TestCase):

    def test_named_poison(self):
        self.assertEqual(poison_name('79690', False, 1, POISONS), 'Crown Lethal Poison')

    def test_level_scaled_poison_gets_its_tier(self):
        self.assertEqual(poison_name('76827', True, 15, POISONS), 'Damage Health Poison IX')
        self.assertEqual(poison_name('76827', False, 3, POISONS), 'Damage Health Poison I')

    def test_unknown_poison_shows_its_item_id(self):
        self.assertEqual(poison_name('99999', True, 15, POISONS), 'Poison (item 99999)')

    def test_tier_follows_the_solvent_levels(self):
        normal = [poison_tier(False, level) for level in (3, 10, 20, 30, 40, 50)]
        self.assertEqual(normal, ['I', 'II', 'III', 'IV', 'V', 'V'])
        champion = [poison_tier(True, level) for level in (1, 5, 10, 15, 16)]
        self.assertEqual(champion, ['VI', 'VII', 'VIII', 'IX', 'IX'])

    def test_bundled_table_names_real_poisons(self):
        self.assertEqual(poison_name('79690'), 'Crown Lethal Poison')
        self.assertEqual(poison_name('81196', True, 15), 'Cloudy Hindering Poison IX')


class TestMundus(unittest.TestCase):

    NAMES = {'13975': 'Boon: The Thief', '13982': 'Boon: The Atronach',
             '45549': 'Grace', '61255': 'Increase Max Health & Stamina'}
    ICONS = {'13975': 'ability_mundusstones_003', '13982': 'ability_mundusstones_009',
             '45549': 'ability_armor_004'}

    def stones(self, effects, names=None, icons=None):
        names = self.NAMES if names is None else names
        icons = self.ICONS if icons is None else icons
        return mundus_stones(effects, names.get, icons.get)

    def test_one_stone(self):
        self.assertEqual(self.stones(['45549', '13975', '61255']),
                         [{'id': '13975', 'name': 'The Thief',
                           'icon': 'ability_mundusstones_003'}])

    def test_two_stones_in_log_order(self):
        self.assertEqual([s['name'] for s in self.stones(['13982', '45549', '13975'])],
                         ['The Atronach', 'The Thief'])

    def test_the_same_boon_listed_twice_is_one_stone(self):
        # Real logs do this (one player in each of several September 2026
        # trials had their boon's id in the list twice)
        self.assertEqual([s['name'] for s in self.stones(['13975', '45549', '13975'])],
                         ['The Thief'])

    def test_translated_log_is_recognised_by_id_and_keeps_its_name(self):
        stones = self.stones(['13975'], names={'13975': 'Segen: Der Dieb'}, icons={})
        self.assertEqual(stones, [{'id': '13975', 'name': 'Segen: Der Dieb', 'icon': ''}])

    def test_a_stone_outside_the_id_list_is_recognised_by_its_icon(self):
        stones = self.stones(['777'], names={'777': 'Boon: The New Sign'},
                             icons={'777': 'ability_mundusstones_014'})
        self.assertEqual(stones[0]['name'], 'The New Sign')

    def test_no_stone(self):
        self.assertEqual(self.stones(['45549', '61255']), [])
        self.assertEqual(self.stones([]), [])

    def test_all_thirteen_boon_ids_are_known(self):
        self.assertEqual(len(player_build.MUNDUS_IDS), 13)
        for boon in ('13940', '13943', '13974', '13975', '13982', '13984', '13985'):
            self.assertIn(boon, player_build.MUNDUS_IDS)
        self.assertNotIn('13983', player_build.MUNDUS_IDS)


class TestFood(unittest.TestCase):

    NAMES = {'107789': 'Artaeum Takeaway Broth', '61255': 'Increase Max Health & Stamina',
             '84731': "Witchmother's Potent Brew", '84732': 'Increase Health Regen',
             '84733': 'Increase Health Regen', '13975': 'Boon: The Thief'}

    def food(self, effects):
        return food_buff(effects, self.NAMES.get, FOOD)

    def test_named_food(self):
        self.assertEqual(self.food(['13975', '107789']),
                         {'id': '107789', 'name': 'Artaeum Takeaway Broth', 'kind': 'food'})

    def test_crafted_food_is_shown_by_its_effect_name(self):
        self.assertEqual(self.food(['61255']),
                         {'id': '61255', 'name': 'Increase Max Health & Stamina',
                          'kind': 'food'})

    def test_drink_logged_as_several_effects_is_one_drink(self):
        for order in (['84732', '84733', '84731'], ['84731', '84732', '84733']):
            self.assertEqual(self.food(order),
                             {'id': '84731', 'name': "Witchmother's Potent Brew",
                              'kind': 'drink'})

    def test_no_food(self):
        self.assertIsNone(self.food(['13975']))
        self.assertIsNone(self.food([]))

    def test_name_missing_from_the_log(self):
        self.assertEqual(food_buff(['61255'], {}.get, FOOD)['name'], 'Ability 61255')

    def test_bundled_table_loads(self):
        table = food_table()
        self.assertIsNotNone(table)
        self.assertEqual(table['107789']['kind'], 'food')

    def test_missing_table_leaves_food_out_instead_of_saying_none(self):
        with mock.patch.object(player_build, 'food_table', return_value=None):
            fields = build_fields({}, ['13975'], self.NAMES.get, {}.get)
        self.assertNotIn('food', fields)
        self.assertEqual(set(build_fields({}, [], {}.get, {}.get)), {'gear', 'mundus', 'food'})


class TestGearRows(unittest.TestCase):

    def test_rows_follow_display_order_and_skip_costume(self):
        gear = gear_of(item('BACKUP_MAIN', '1'), item('COSTUME'), item('RING2', '1'),
                       item('HEAD', '1'), item('MAIN_HAND', '2'), item('CHEST', '1'))
        self.assertEqual([row['slot'] for row in gear_rows(gear, SET_NAMES.get, lambda n: False)],
                         ['HEAD', 'CHEST', 'RING2', 'MAIN_HAND', 'BACKUP_MAIN'])

    def test_item_fields_keep_the_logged_values(self):
        gear = gear_of(item('HEAD', '1', item_id='95044', trait='ARMOR_PROSPEROUS',
                            quality='ARTIFACT', enchant='MAGICKA', enchant_quality='ARCANE',
                            level='15'))
        row = rows(gear)['HEAD']
        self.assertEqual(row, {
            'slot': 'HEAD', 'item_id': '95044', 'set_id': '1', 'set': 'Alpha',
            'mythic': False, 'quality': 'ARTIFACT', 'trait': 'ARMOR_PROSPEROUS',
            'enchant': 'MAGICKA', 'enchant_quality': 'ARCANE', 'cp': True, 'level': 15,
            'pieces': [1, None], 'weight': 'medium'})

    def test_item_of_no_set(self):
        row = rows(gear_of(item('WAIST', '0')))['WAIST']
        self.assertEqual((row['set'], row['set_id'], row['pieces'], row['mythic']),
                         ('', '', None, False))
        self.assertEqual(row['trait'], 'ARMOR_DIVINES')

    def test_set_the_bundled_data_does_not_know(self):
        row = rows(gear_of(item('WAIST', '4242')))['WAIST']
        self.assertEqual((row['set'], row['mythic'], row['pieces']),
                         ('Set#4242', False, [1, None]))

    def test_mythic_comes_from_the_set_not_the_logged_quality(self):
        row = rows(gear_of(item('RING2', '9', quality='LEGENDARY')))['RING2']
        self.assertTrue(row['mythic'])
        self.assertEqual(row['quality'], 'LEGENDARY')

    def test_item_without_an_enchant_has_no_enchant_quality(self):
        row = rows(gear_of(item('RING1', '1', enchant='INVALID', enchant_quality='NORMAL')))['RING1']
        self.assertEqual((row['enchant'], row['enchant_quality']), ('INVALID', ''))

    def test_poison_rows_are_named_and_carry_no_enchant(self):
        gear = gear_of(item('MAIN_HAND', '1'), item('OFF_HAND', '1'),
                       ['POISON', '79690', 'F', '1', 'NONE', 'LEGENDARY', '0', 'INVALID',
                        'F', '0', 'NORMAL'],
                       ['BACKUP_POISON', '76827', 'T', '15', 'NONE', 'NORMAL', '0', 'INVALID',
                        'F', '0', 'NORMAL'],
                       item('BACKUP_MAIN', '2'))
        got = rows(gear)
        self.assertEqual((got['POISON']['name'], got['POISON']['quality']),
                         ('Crown Lethal Poison', 'LEGENDARY'))
        self.assertEqual(got['BACKUP_POISON']['name'], 'Damage Health Poison IX')
        for slot in ('POISON', 'BACKUP_POISON'):
            self.assertEqual((got[slot]['trait'], got[slot]['enchant'],
                              got[slot]['enchant_quality'], got[slot]['set'],
                              got[slot]['pieces']), ('', '', '', '', None))
        self.assertNotIn('name', got['MAIN_HAND'])

    def test_short_or_empty_entries_are_skipped(self):
        self.assertEqual(gear_rows({'HEAD': ['HEAD', '1'], 'CHEST': []}), [])
        self.assertEqual(gear_rows({}), [])


class TestArmorWeights(unittest.TestCase):

    def test_weight_is_looked_up_by_item_id(self):
        self.assertEqual([armor_weight(i, WEIGHTS) for i in ('95044', '501', '502')],
                         ['medium', 'light', 'heavy'])
        self.assertEqual(armor_weight(95044, WEIGHTS), 'medium')   # ids compare as text

    def test_piece_the_table_lacks_has_no_weight(self):
        self.assertEqual(armor_weight('999999', WEIGHTS), '')
        self.assertEqual(armor_weight('', WEIGHTS), '')
        self.assertEqual(armor_weight('95044', {}), '')

    def test_labels(self):
        self.assertEqual([weight_label(w) for w in ('light', 'medium', 'heavy')],
                         ['Light', 'Medium', 'Heavy'])
        self.assertEqual([weight_label(w) for w in ('', None, 'plate')], ['', '', ''])

    def test_every_armor_row_carries_its_weight(self):
        gear = gear_of(item('HEAD', '1', item_id='95044'), item('CHEST', '1', item_id='502'),
                       item('WAIST', '1', item_id='501'), item('FEET', '1', item_id='777'))
        got = rows(gear)
        self.assertEqual([got[slot]['weight'] for slot in ('HEAD', 'CHEST', 'WAIST', 'FEET')],
                         ['medium', 'heavy', 'light', ''])

    def test_only_armor_slots_have_a_weight(self):
        # Even with an id the table knows: jewelry, weapons, shields and
        # poisons are not looked up
        gear = gear_of(item('NECK', '1', item_id='502'), item('RING1', '1', item_id='502'),
                       item('MAIN_HAND', '1', item_id='502'),
                       item('OFF_HAND', '1', item_id='502', trait='ARMOR_STURDY'),
                       ['POISON', '502', 'F', '1', 'NONE', 'LEGENDARY', '0', 'INVALID',
                        'F', '0', 'NORMAL'])
        self.assertEqual({row['weight'] for row in rows(gear).values()}, {''})

    def test_bundled_table_knows_real_pieces(self):
        for item_id, weight in REAL_WEIGHTS.items():
            self.assertEqual(armor_weight(item_id), weight, item_id)
        # A lightning staff and a ring are no armor
        self.assertEqual((armor_weight('133257'), armor_weight('187752')), ('', ''))

    def test_worked_example_from_a_real_log(self):
        got = {row['slot']: row['weight'] for row in gear_rows(_real_gear())}
        self.assertEqual(got, {
            'HEAD': 'medium', 'SHOULDERS': 'light', 'CHEST': 'medium', 'HAND': 'medium',
            'WAIST': 'medium', 'LEGS': 'medium', 'FEET': 'medium',
            'NECK': '', 'RING1': '', 'RING2': '', 'MAIN_HAND': '', 'BACKUP_MAIN': ''})

    def test_missing_or_malformed_table_gives_no_weights(self):
        load = player_build._bundled_armor_weights.__wrapped__
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(player_build, 'bundle_root', return_value=Path(tmp)):
                self.assertEqual(load(), {})
                table = Path(tmp) / 'data' / 'items' / 'armor_weights.json'
                table.parent.mkdir(parents=True)
                table.write_text('{"light": "nope", "medium": [7, 8], "heavy": {}}',
                                 encoding='utf-8')
                self.assertEqual(load(), {'7': 'medium', '8': 'medium'})
                table.write_text('[1, 2]', encoding='utf-8')
                self.assertEqual(load(), {})
                table.write_text('not json', encoding='utf-8')
                self.assertEqual(load(), {})


class TestPieceCounts(unittest.TestCase):

    BODY = ('HEAD', 'SHOULDERS', 'CHEST', 'HAND', 'WAIST')

    def test_same_count_on_both_bars(self):
        gear = gear_of(*(item(slot, '1') for slot in self.BODY),
                       item('MAIN_HAND', '2'), item('BACKUP_MAIN', '3'))
        got = rows(gear)
        for slot in self.BODY:
            self.assertEqual(got[slot]['pieces'], [5, 5])

    def test_set_completed_by_front_bar_weapons_only(self):
        gear = gear_of(item('NECK', '1'), item('RING1', '1'), item('RING2', '1'),
                       item('MAIN_HAND', '1', item_id='7'), item('OFF_HAND', '1', item_id='7'),
                       item('BACKUP_MAIN', '2'))
        got = rows(gear)
        for slot in ('NECK', 'RING1', 'RING2', 'MAIN_HAND', 'OFF_HAND'):
            self.assertEqual(got[slot]['pieces'], [5, 3], slot)
        # The staff of the other set: two-handed, back bar only
        self.assertEqual(got['BACKUP_MAIN']['pieces'], [0, 2])

    def test_two_handed_weapon_counts_as_two(self):
        gear = gear_of(item('HEAD', '1'), item('MAIN_HAND', '1'), item('BACKUP_MAIN', '3'))
        got = rows(gear)
        self.assertEqual(got['BACKUP_MAIN']['pieces'], [0, 2])
        self.assertEqual(got['MAIN_HAND']['pieces'], [3, 1])
        self.assertEqual(got['HEAD']['pieces'], [3, 1])

    def test_no_back_bar_gives_a_single_count(self):
        gear = gear_of(item('HEAD', '1'), item('MAIN_HAND', '1'), item('OFF_HAND', '1'))
        got = rows(gear)
        for slot in ('HEAD', 'MAIN_HAND', 'OFF_HAND'):
            self.assertEqual(got[slot]['pieces'], [3, None])

    def test_shield_and_dual_wield_are_one_handed(self):
        dual = gear_of(item('MAIN_HAND', '1', item_id='5'), item('OFF_HAND', '1', item_id='5'))
        self.assertFalse(is_two_handed('MAIN_HAND', '5', dual))
        shield = gear_of(item('BACKUP_MAIN', '1', item_id='5'),
                         item('BACKUP_OFF', '2', item_id='6', trait='ARMOR_STURDY'))
        self.assertFalse(is_two_handed('BACKUP_MAIN', '5', shield))
        self.assertTrue(is_two_handed('MAIN_HAND', '5', shield))   # no front off hand
        self.assertFalse(is_two_handed('OFF_HAND', '6', shield))   # not a main hand
        self.assertEqual(piece_counts(dual), {'1': [2, None]})

    def test_worked_example_from_a_real_log(self):
        """design.md D5: a set whose five pieces are live on the back bar only."""
        got = {row['slot']: row for row in gear_rows(_real_gear())}
        whorl = 'Perfected Whorl of the Depths'
        for slot in ('NECK', 'RING1', 'SHOULDERS'):
            self.assertEqual((got[slot]['set'], got[slot]['pieces']), (whorl, [3, 5]), slot)
        self.assertEqual((got['BACKUP_MAIN']['set'], got['BACKUP_MAIN']['pieces']),
                         (whorl, [3, 5]))
        for slot in ('CHEST', 'HAND', 'WAIST', 'LEGS', 'FEET'):
            self.assertEqual((got[slot]['set'], got[slot]['pieces']), ("Aerie's Cry", [5, 5]))
        self.assertEqual((got['MAIN_HAND']['set'], got['MAIN_HAND']['pieces']),
                         ('Perfected Concentrated Force', [2, 0]))
        self.assertEqual((got['HEAD']['set'], got['HEAD']['pieces']), ('Slimecraw', [1, 1]))
        self.assertEqual((got['RING2']['set'], got['RING2']['mythic'], got['RING2']['pieces']),
                         ('Shattered Paths Signet', True, [1, 1]))

    def test_the_analyzer_uses_the_same_two_handed_rule(self):
        from esolog_tail import ESOLogAnalyzer
        analyzer = ESOLogAnalyzer()
        cases = [
            gear_of(item('MAIN_HAND', '1', item_id='5')),
            gear_of(item('MAIN_HAND', '1', item_id='5'), item('OFF_HAND', '1', item_id='5')),
            gear_of(item('MAIN_HAND', '1', item_id='5'), item('OFF_HAND', '2', item_id='6')),
            gear_of(item('BACKUP_MAIN', '1', item_id='5')),
            gear_of(item('BACKUP_MAIN', '1', item_id='5'),
                    item('BACKUP_OFF', '2', item_id='6', trait='ARMOR_STURDY')),
        ]
        for gear in cases:
            for slot, entry in gear.items():
                self.assertEqual(analyzer._is_two_handed_weapon(entry, gear),
                                 is_two_handed(slot, entry[1], gear), (slot, sorted(gear)))
        self.assertFalse(analyzer._is_two_handed_weapon(['MAIN_HAND'], {}))


class TestParserAcceptsEmptyEffectLists(unittest.TestCase):

    LINE = ('100,PLAYER_INFO,7,[],[],[[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,MAGICKA,'
            'T,16,LEGENDARY]],[25267,39028],[86169]')

    def test_structured_parse(self):
        from eso_log_structures import PlayerInfoEntry
        parsed = PlayerInfoEntry.parse(self.LINE)
        self.assertIsNotNone(parsed)
        self.assertEqual((parsed.unit_id, parsed.ability_ids, parsed.ability_levels),
                         (7, [], []))
        self.assertEqual([g.slot for g in parsed.gear_items], ['HEAD'])
        self.assertEqual((parsed.front_bar_abilities, parsed.back_bar_abilities),
                         ([25267, 39028], [86169]))

    def test_legacy_entry_keeps_bars_and_gear(self):
        from eso_log_parser import ESOLogParser
        parser = ESOLogParser()
        info = parser.parse_player_info(parser.parse_line(self.LINE))
        self.assertEqual(info.ability_ids, [])
        self.assertEqual(info.champion_points, ['25267', '39028'])
        self.assertEqual(info.gear_data[0][0], 'HEAD')

    def test_lists_with_effects_still_parse(self):
        from eso_log_structures import PlayerInfoEntry
        parsed = PlayerInfoEntry.parse(self.LINE.replace('[],[]', '[45549,13975],[1,1]'))
        self.assertEqual(parsed.ability_ids, [45549, 13975])
        self.assertEqual(parsed.ability_levels, [1, 1])


class TestBuildOnTheFightEntry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        fights = _fights(SESSION)
        assert len(fights) == 1, len(fights)
        cls.players = {p['unit_id']: p for p in fights[0].players}

    def test_identity_fields(self):
        me = self.players['1']
        self.assertEqual((me['name'], me['character'], me['race'], me['class_name'], me['cp']),
                         ('@brainsnorkel', 'Pïque', 'High Elf', 'Warden', 3224))
        self.assertEqual(self.players['2']['race'], 'Dark Elf')
        anonymous = self.players['3']
        self.assertEqual((anonymous['name'], anonymous['character'], anonymous['race']),
                         ('anon', '', 'Argonian'))

    def test_gear_rows_in_display_order_with_set_names_and_counts(self):
        gear = self.players['1']['gear']
        self.assertEqual([row['slot'] for row in gear],
                         ['HEAD', 'SHOULDERS', 'CHEST', 'HAND', 'WAIST', 'LEGS', 'FEET',
                          'NECK', 'RING1', 'RING2', 'MAIN_HAND', 'BACKUP_MAIN'])
        by_slot = {row['slot']: row for row in gear}
        self.assertEqual(by_slot['HEAD'], {
            'slot': 'HEAD', 'item_id': '95044', 'set_id': '270', 'set': 'Slimecraw',
            'mythic': False, 'quality': 'LEGENDARY', 'trait': 'ARMOR_DIVINES',
            'enchant': 'MAGICKA', 'enchant_quality': 'LEGENDARY', 'cp': True, 'level': 16,
            'pieces': [1, 1], 'weight': 'medium'})
        self.assertEqual((by_slot['SHOULDERS']['set'], by_slot['SHOULDERS']['pieces'],
                          by_slot['SHOULDERS']['weight']),
                         ('Perfected Whorl of the Depths', [3, 5], 'light'))
        self.assertEqual(by_slot['NECK']['weight'], '')
        self.assertEqual((by_slot['MAIN_HAND']['trait'], by_slot['MAIN_HAND']['enchant'],
                          by_slot['MAIN_HAND']['pieces']),
                         ('WEAPON_CHARGED', 'POISONED_WEAPON', [2, 0]))
        self.assertTrue(by_slot['RING2']['mythic'])

    def test_fight_view_counts_are_unchanged(self):
        # The summed counts the fight view shows today, two-handed as two
        self.assertEqual(sorted(self.players['1']['all_sets']),
                         sorted([(5, 'Perfected Whorl of the Depths'), (5, "Aerie's Cry"),
                                 (2, 'Perfected Concentrated Force'), (1, 'Slimecraw'),
                                 (1, 'Shattered Paths Signet')]))

    def test_poisons_and_costume(self):
        by_slot = {row['slot']: row for row in self.players['2']['gear']}
        self.assertNotIn('COSTUME', by_slot)
        self.assertEqual((by_slot['POISON']['name'], by_slot['POISON']['quality']),
                         ('Crown Lethal Poison', 'LEGENDARY'))
        self.assertEqual(by_slot['BACKUP_POISON']['name'], 'Cloudy Hindering Poison IX')
        self.assertEqual((by_slot['RING1']['quality'], by_slot['RING1']['cp'],
                          by_slot['RING1']['level']), ('ARCANE', True, 15))
        # Two daggers of one set: one piece each
        self.assertEqual(by_slot['MAIN_HAND']['pieces'], [2, 0])
        self.assertEqual(by_slot['BACKUP_MAIN']['pieces'], [0, 2])

    def test_mundus(self):
        self.assertEqual(self.players['1']['mundus'],
                         [{'id': '13975', 'name': 'The Thief',
                           'icon': 'ability_mundusstones_003'}])
        self.assertEqual([s['name'] for s in self.players['3']['mundus']],
                         ['The Atronach', 'The Thief'])

    def test_food(self):
        self.assertEqual(self.players['1']['food'],
                         {'id': '61257', 'name': 'Increase Max Health & Magicka',
                          'kind': 'food'})
        self.assertEqual(self.players['2']['food'],
                         {'id': '84731', 'name': "Witchmother's Potent Brew", 'kind': 'drink'})
        self.assertIsNone(self.players['3']['food'])

    def test_player_without_logged_gear_is_still_listed(self):
        nobody = self.players['3']
        self.assertEqual(nobody['gear'], [])
        self.assertEqual(nobody['front_bar'], ['Damage Ability'])


if __name__ == '__main__':
    unittest.main()
