#!/usr/bin/env python3
"""The generators behind the build window's bundled tables: poison names
(scripts/generate_poison_names.py), armor weights
(scripts/generate_armor_weights.py) and food and drink buff ids
(scripts/generate_food_buffs.py), and the tables they committed."""

import ast
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load(script: str):
    path = REPO_ROOT / 'scripts' / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# What UESP's export returns for item type 30, cut down to four rows
UESP_SAMPLE = {
    "numRecords": 4,
    "minedItemSummary": [
        {"itemId": "76827", "name": "Damage Health Poison I"},
        {"itemId": "81196", "name": "Cloudy Hindering Poison I"},
        {"itemId": "79690", "name": "Crown Lethal Poison"},
        {"itemId": "224310", "name": "Trauma Poison"},
        {"itemId": "", "name": "No Id Poison"},
        {"itemId": "12", "name": ""},
    ],
}

DATA_LUA_EXCERPT = """local lib = LIB_FOOD_DRINK_BUFF

-- The drink buff abilityIds and their LibFoodDrinkBuff_buffTypeConstant
lib.DRINK_BUFF_ABILITIES = {
\t[61322] \t= LFDB_BUFF_TYPE_REGEN_HEALTH, -- Health Recovery
\t[84731] \t= LFDB_BUFF_TYPE_MAX_HEALTH_MAGICKA_REGEN_MAGICKA, -- 2h Witches event: Witchmother's Potent Brew
\t--[99999] \t= LFDB_BUFF_TYPE_REGEN_ALL, -- retired
}

-- The food buff abilityIds and their LibFoodDrinkBuff_buffTypeConstant
lib.FOOD_BUFF_ABILITIES = {
\t[61255] \t= LFDB_BUFF_TYPE_MAX_HEALTH_STAMINA, -- Increase Max Health & Stamina
\t[107789] \t= LFDB_BUFF_TYPE_MAX_HEALTH_STAMINA_REGEN_HEALTH_STAMINA, -- Artaeum Takeaway Broth
}

lib.SOMETHING_ELSE = {
\t[11111] \t= LFDB_BUFF_TYPE_MAX_HEALTH,
}
"""


class TestPoisonNames(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.script = _load('generate_poison_names.py')

    def test_tier_numeral_moves_into_a_flag(self):
        entries = self.script.poison_entries(UESP_SAMPLE)
        self.assertEqual(entries['76827'], {'name': 'Damage Health Poison', 'tiered': True})
        self.assertEqual(entries['81196'], {'name': 'Cloudy Hindering Poison', 'tiered': True})

    def test_untiered_names_are_kept_whole(self):
        entries = self.script.poison_entries(UESP_SAMPLE)
        self.assertEqual(entries['79690'], {'name': 'Crown Lethal Poison', 'tiered': False})
        self.assertEqual(entries['224310'], {'name': 'Trauma Poison', 'tiered': False})

    def test_rows_without_an_id_or_a_name_are_skipped(self):
        self.assertEqual(set(self.script.poison_entries(UESP_SAMPLE)),
                         {'76827', '81196', '79690', '224310'})
        self.assertEqual(self.script.poison_entries({}), {})
        self.assertEqual(self.script.poison_entries({'minedItemSummary': 'nope'}), {})

    def test_a_short_response_would_not_overwrite(self):
        # Four rows are a bad response: the game has about fifty poisons
        self.assertLess(len(self.script.poison_entries(UESP_SAMPLE)), self.script.MIN_POISONS)

    def test_committed_table_names_the_poisons_seen_in_real_logs(self):
        table = json.loads(self.script.OUT_PATH.read_text(encoding='utf-8'))
        self.assertEqual(table['count'], len(table['poisons']))
        self.assertGreaterEqual(table['count'], self.script.MIN_POISONS)
        for item_id in ('76826', '76827', '76834', '76839', '79690', '79691', '81195', '81196'):
            self.assertIn(item_id, table['poisons'])
            self.assertTrue(table['poisons'][item_id]['name'])
        self.assertEqual(table['poisons']['79690'],
                         {'name': 'Crown Lethal Poison', 'tiered': False})
        self.assertEqual(table['poisons']['76827'],
                         {'name': 'Damage Health Poison', 'tiered': True})


class TestArmorWeights(unittest.TestCase):

    # What UESP's export returns for item type 2: armorType 1, 2 and 3 are
    # light, medium and heavy, and 0 is an item without a weight (a ring here)
    SAMPLE = {'minedItemSummary': [
        {'itemId': '95044', 'armorType': '2'},      # Slimecraw Mask
        {'itemId': '187287', 'armorType': '1'},     # Perfected Epaulets of the Depths
        {'itemId': '108766', 'armorType': '3'},     # Cuirass of the Sergeant
        {'itemId': '144', 'armorType': '1'},
        {'itemId': '187752', 'armorType': '0'},
        {'itemId': '', 'armorType': '3'},
        {'itemId': '95044', 'armorType': '2'},
        {'itemId': '5'},
        'not a row',
    ]}

    @classmethod
    def setUpClass(cls):
        cls.script = _load('generate_armor_weights.py')

    def test_ids_are_sorted_into_the_three_weights(self):
        self.assertEqual(self.script.armor_weights(self.SAMPLE),
                         {'light': [144, 187287], 'medium': [95044], 'heavy': [108766]})

    def test_a_response_without_rows_gives_empty_lists(self):
        empty = {'light': [], 'medium': [], 'heavy': []}
        self.assertEqual(self.script.armor_weights({}), empty)
        self.assertEqual(self.script.armor_weights({'minedItemSummary': 'nope'}), empty)

    def test_a_short_response_would_not_overwrite(self):
        counts = [len(ids) for ids in self.script.armor_weights(self.SAMPLE).values()]
        self.assertLess(max(counts), self.script.MIN_PER_WEIGHT)

    def test_file_is_json_with_wrapped_ids(self):
        weights = {'light': list(range(1000, 1040)), 'medium': [7], 'heavy': []}
        text = self.script.render(weights, '2026-10-05T00:00:00+00:00')
        data = json.loads(text)
        self.assertEqual(data['count'], 41)
        self.assertEqual({w: data[w] for w in weights}, weights)
        # Sixteen ids to a line, so a refreshed list diffs line by line
        id_lines = [line for line in text.splitlines() if line.strip()[:1].isdigit()]
        self.assertEqual([len(line.split(',')) - line.endswith(',') for line in id_lines],
                         [16, 16, 8, 1])

    def test_committed_table(self):
        data = json.loads(self.script.OUT_PATH.read_text(encoding='utf-8'))
        lists = [data[weight] for weight in ('light', 'medium', 'heavy')]
        self.assertEqual(data['count'], sum(len(ids) for ids in lists))
        for ids in lists:
            self.assertGreaterEqual(len(ids), self.script.MIN_PER_WEIGHT)
            self.assertEqual(ids, sorted(set(ids)))
        # No piece has two weights
        self.assertEqual(len(set().union(*lists)), data['count'])
        # Pieces worn in real logs
        self.assertIn(187287, data['light'])     # Perfected Epaulets of the Depths
        self.assertIn(95044, data['medium'])     # Slimecraw Mask
        self.assertIn(108766, data['heavy'])     # Cuirass of the Sergeant
        # A ring and a lightning staff are in none of them
        self.assertFalse({187752, 133257} & set().union(*lists))


class TestFoodBuffs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.script = _load('generate_food_buffs.py')

    def test_both_tables_are_read_with_their_kind_and_type(self):
        buffs = self.script.parse_data_lua(DATA_LUA_EXCERPT)
        self.assertEqual(buffs['61322'], {'kind': 'drink', 'type': 'REGEN_HEALTH'})
        self.assertEqual(buffs['84731'],
                         {'kind': 'drink', 'type': 'MAX_HEALTH_MAGICKA_REGEN_MAGICKA'})
        self.assertEqual(buffs['61255'], {'kind': 'food', 'type': 'MAX_HEALTH_STAMINA'})
        self.assertEqual(buffs['107789']['kind'], 'food')

    def test_comments_and_other_tables_are_ignored(self):
        buffs = self.script.parse_data_lua(DATA_LUA_EXCERPT)
        self.assertNotIn('99999', buffs)   # commented out
        self.assertNotIn('11111', buffs)   # another table
        self.assertEqual(len(buffs), 4)

    def test_version_comes_from_the_addon_manifest(self):
        self.assertEqual(self.script.addon_version('## Title: X\n## Version: 19\n'), '19')
        self.assertEqual(self.script.addon_version(''), 'unknown')

    def test_source_can_be_a_folder_or_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'LibFoodDrinkBuff'
            folder.mkdir()
            (folder / 'Data.lua').write_text(DATA_LUA_EXCERPT, encoding='utf-8')
            (folder / 'LibFoodDrinkBuff.txt').write_text('## Version: 7\n', encoding='utf-8')
            text, version, origin = self.script.load_source(str(folder))
            self.assertEqual((len(self.script.parse_data_lua(text)), version), (4, '7'))
            self.assertEqual(origin, str(folder))
            text, version, _origin = self.script.load_source(str(folder / 'Data.lua'))
            self.assertEqual(len(self.script.parse_data_lua(text)), 4)

    def test_committed_table_holds_both_kinds(self):
        table = json.loads(self.script.OUT_PATH.read_text(encoding='utf-8'))
        buffs = table['buffs']
        self.assertEqual(table['count'], len(buffs))
        self.assertGreaterEqual(table['count'], self.script.MIN_BUFFS)
        kinds = [entry['kind'] for entry in buffs.values()]
        self.assertEqual((kinds.count('food'), kinds.count('drink')),
                         (table['food'], table['drink']))
        self.assertEqual(set(kinds), {'food', 'drink'})
        self.assertTrue(all(entry['type'] for entry in buffs.values()))
        # Foods and drinks found in real logs, companions included
        self.assertEqual(buffs['107789']['kind'], 'food')    # Artaeum Takeaway Broth
        self.assertEqual(buffs['89957']['kind'], 'drink')    # Dubious Camoran Throne
        for effect in ('61255', '127596', '84731', '84732', '84733', '127572', '100488'):
            self.assertIn(effect, buffs)

    def test_check_log_reports_food_style_effects_on_players_without_known_food(self):
        lines = [
            '1,ABILITY_INFO,61255,"Increase Max Health & Stamina","/esoui/art/icons/crafting_cooking_grilled_vegetables.dds",F,F',
            '1,ABILITY_INFO,555555,"Brand New Stew","/esoui/art/icons/crafting_meat_009.dds",F,F',
            '1,ABILITY_INFO,89958,"Increase Stamina","/esoui/art/icons/store_magickafood_001.dds",F,F',
            '1,ABILITY_INFO,13975,"Boon: The Thief","/esoui/art/icons/ability_mundusstones_003.dds",F,F',
            # Known food, with a companion effect the table lacks: not reported
            '5,PLAYER_INFO,1,[61255,89958,13975],[1,1,1],[],[1],[2]',
            # No known food, but a food-style effect: reported
            '5,PLAYER_INFO,2,[555555,13975],[1,1],[],[1],[2]',
            # No food at all
            '5,PLAYER_INFO,3,[13975],[1],[],[1],[2]',
        ]
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'Encounter.log'
            log.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            total, without, suspects = self.script.unknown_food(log, {'61255'})
        self.assertEqual((total, without), (3, 2))
        self.assertEqual(dict(suspects),
                         {('555555', 'Brand New Stew', 'crafting_meat_009'): 1})


class TestGearSetNames(unittest.TestCase):
    """The set names scripts/generate_gear_data.py writes into
    src/gear_set_data.py, and the ESO-Hub link table keyed by them."""

    def test_names_carry_no_escape_artefacts(self):
        # The LibSets workbook writes "Mara\’s Balm" and "Siegemaster'\s Focus"
        from gear_set_data import SET_ID_TO_NAME
        odd = sorted(name for name in SET_ID_TO_NAME.values()
                     if '\\' in name or '’' in name)
        self.assertEqual(odd, [])
        self.assertEqual(SET_ID_TO_NAME['670'], "Mara's Balm")
        self.assertEqual(SET_ID_TO_NAME['784'], "Siegemaster's Focus")

    def test_every_set_link_is_keyed_by_a_known_set_name(self):
        from gear_set_data import SET_NAME_TO_ID
        path = REPO_ROOT / 'data' / 'esohub' / 'sets_en.json'
        links = json.loads(path.read_text(encoding='utf-8'))['sets']
        self.assertEqual(sorted(set(links) - set(SET_NAME_TO_ID)), [])
        self.assertEqual(links["Mara's Balm"], '/en/sets/maras-balm')

    def test_generated_literals_survive_quotes_and_backslashes(self):
        try:
            script = _load('generate_gear_data.py')
        except ImportError:
            self.skipTest('openpyxl is not installed (requirements-build.txt)')
        for text in ("Mara's Balm", 'a "quoted" word', 'back\\slash'):
            self.assertEqual(ast.literal_eval(script.quoted(text)), text)

    def test_three_cyrodiil_sets_carry_the_games_names(self):
        # The LibSets workbook has these three names one set out of place; the
        # client's own language table (Update 51) has them this way
        from gear_set_data import SET_ID_TO_NAME, SET_NAME_TO_ID, SET_INFO
        self.assertEqual([SET_ID_TO_NAME[set_id] for set_id in ('711', '712', '713')],
                         ["Colovian Highlands General", "Jerall Mountains Warchief",
                          "Nibenay Bay Battlereeve"])
        for set_id in ('711', '712', '713'):
            name = SET_ID_TO_NAME[set_id]
            self.assertEqual(SET_NAME_TO_ID[name], set_id)
            self.assertEqual(SET_INFO[name]['set_id'], set_id)

    def test_sets_added_since_update_49_have_a_name_and_a_link(self):
        from gear_set_data import SET_ID_TO_NAME
        path = REPO_ROOT / 'data' / 'esohub' / 'sets_en.json'
        links = json.loads(path.read_text(encoding='utf-8'))['sets']
        for set_id, name, page in (('854', "Prowler's Talisman", '/en/sets/prowlers-talisman'),
                                   ('876', "Tarcyr", '/en/sets/tarcyr'),
                                   ('877', "Mylenne Moon-Caller", '/en/sets/mylenne-moon-caller')):
            self.assertEqual(SET_ID_TO_NAME[set_id], name)
            self.assertEqual(links[name], page)

    def test_a_correction_replaces_the_workbooks_name_for_its_set_only(self):
        try:
            script = _load('generate_gear_data.py')
        except ImportError:
            self.skipTest('openpyxl is not installed (requirements-build.txt)')
        said = io.StringIO()
        with mock.patch.object(script, 'NAME_CORRECTIONS', {'711': "Right Name"}), \
                contextlib.redirect_stdout(said):
            self.assertEqual(script.corrected_name('711', "Wrong Name"), "Right Name")
            self.assertEqual(script.corrected_name('712', "Wrong Name"), "Wrong Name")
            self.assertNotIn("can go", said.getvalue())
            # A workbook that has caught up: same result, and it says so
            self.assertEqual(script.corrected_name('711', "Right Name"), "Right Name")
        self.assertIn("NAME_CORRECTIONS can go", said.getvalue())

    def test_every_correction_is_in_the_committed_data(self):
        try:
            script = _load('generate_gear_data.py')
        except ImportError:
            self.skipTest('openpyxl is not installed (requirements-build.txt)')
        from gear_set_data import SET_ID_TO_NAME
        for set_id, name in script.NAME_CORRECTIONS.items():
            self.assertEqual(SET_ID_TO_NAME.get(set_id), name)


if __name__ == '__main__':
    unittest.main()
