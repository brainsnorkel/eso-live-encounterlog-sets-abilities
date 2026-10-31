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


class TestWeaponTypes(unittest.TestCase):

    # What UESP's export returns for item type 1: weaponType is the game's
    # WEAPONTYPE constant, a shield among them (14); 7 is a prop
    SAMPLE = {'minedItemSummary': [
        {'itemId': '133257', 'weaponType': '15'},   # a lightning staff
        {'itemId': '224527', 'weaponType': '9'},    # Restoration Staff of the Gorethief
        {'itemId': '200834', 'weaponType': '11'},   # a dagger
        {'itemId': '139', 'weaponType': '14'},      # Webspinner's Brace, a shield
        {'itemId': '685', 'weaponType': '9'},
        {'itemId': '7', 'weaponType': '7'},
        {'itemId': '', 'weaponType': '9'},
        {'itemId': '685', 'weaponType': '9'},
        {'itemId': '5'},
        'not a row',
    ]}

    @classmethod
    def setUpClass(cls):
        cls.script = _load('generate_weapon_types.py')

    def test_ids_are_sorted_into_their_types(self):
        got = self.script.weapon_types(self.SAMPLE)
        self.assertEqual({kind: ids for kind, ids in got.items() if ids},
                         {'lightning_staff': [133257], 'restoration_staff': [685, 224527],
                          'dagger': [200834], 'shield': [139]})
        self.assertEqual(set(got), set(self.script.WEAPON_TYPES.values()))

    def test_a_response_without_rows_gives_empty_lists(self):
        empty = {kind: [] for kind in self.script.WEAPON_TYPES.values()}
        self.assertEqual(self.script.weapon_types({}), empty)
        self.assertEqual(self.script.weapon_types({'minedItemSummary': 'nope'}), empty)

    def test_a_short_response_would_not_overwrite(self):
        counts = [len(ids) for ids in self.script.weapon_types(self.SAMPLE).values()]
        self.assertLess(max(counts), self.script.MIN_PER_TYPE)

    def test_file_is_json_with_wrapped_ids(self):
        types = {kind: [] for kind in self.script.WEAPON_TYPES.values()}
        types.update(axe=list(range(1000, 1040)), shield=[7])
        text = self.script.render(types, '2026-10-08T00:00:00+00:00')
        data = json.loads(text)
        self.assertEqual(data['count'], 41)
        self.assertEqual({kind: data[kind] for kind in types}, types)
        # Sixteen ids to a line, so a refreshed list diffs line by line
        id_lines = [line for line in text.splitlines() if line.strip()[:1].isdigit()]
        self.assertEqual([len(line.split(',')) - line.endswith(',') for line in id_lines],
                         [16, 16, 8, 1])

    def test_a_saved_reply_is_read_in_place_of_the_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / 'reply.json'
            saved.write_text(json.dumps(self.SAMPLE), encoding='utf-8')
            payload, source = self.script.load_payload(['--from', str(saved)])
            self.assertEqual((payload, source), (self.SAMPLE, str(saved)))
            saved.write_text('not json', encoding='utf-8')
            with self.assertRaises(SystemExit):
                self.script.load_payload(['--from', str(saved)])
        with self.assertRaises(SystemExit):
            self.script.load_payload(['--bogus'])

    def test_committed_table(self):
        data = json.loads(self.script.OUT_PATH.read_text(encoding='utf-8'))
        kinds = list(self.script.WEAPON_TYPES.values())
        lists = [data[kind] for kind in kinds]
        self.assertEqual(data['count'], sum(len(ids) for ids in lists))
        for ids in lists:
            self.assertGreaterEqual(len(ids), self.script.MIN_PER_TYPE)
            self.assertEqual(ids, sorted(set(ids)))
        # No weapon has two types
        self.assertEqual(len(set().union(*lists)), data['count'])
        # Weapons wielded in real logs
        self.assertIn(133257, data['lightning_staff'])
        self.assertIn(224527, data['restoration_staff'])   # Restoration Staff of the Gorethief
        self.assertIn(55939, data['restoration_staff'])    # The Master's Restoration Staff
        self.assertIn(71152, data['inferno_staff'])        # The Maelstrom's Inferno Staff
        self.assertIn(187194, data['ice_staff'])
        self.assertIn(200834, data['dagger'])
        self.assertIn(71130, data['greatsword'])           # The Maelstrom's Greatsword
        self.assertIn(71142, data['bow'])                  # The Maelstrom's Bow
        self.assertIn(139, data['shield'])                 # Webspinner's Brace
        # A ring and a medium helmet are in none of them
        self.assertFalse({187752, 95044} & set().union(*lists))


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

    def test_names_are_spelt_as_the_game_spells_them(self):
        # The workbook has "Perfect Arms of Relequen", "Blood Spawn", "Icy Conjuror"
        from gear_set_data import SET_ID_TO_NAME
        for set_id, name in (('163', "Bloodspawn"), ('393', "Perfected Arms of Relequen"),
                             ('428', "Perfected Mender's Ward"), ('431', "Icy Conjurer"),
                             ('446', "Claw of Yolnahkriin"), ('780', "Aetheric Lancer")):
            self.assertEqual(SET_ID_TO_NAME[set_id], name)
        self.assertEqual([name for name in SET_ID_TO_NAME.values() if name.startswith('Perfect ')], [])
        path = REPO_ROOT / 'data' / 'esohub' / 'sets_en.json'
        links = json.loads(path.read_text(encoding='utf-8'))['sets']
        self.assertEqual(links["Perfected Arms of Relequen"], '/en/sets/perfected-arms-of-relequen')
        self.assertEqual(links["Bloodspawn"], '/en/sets/bloodspawn')

    def test_sets_added_since_update_49_have_a_name_and_a_link(self):
        from gear_set_data import SET_ID_TO_NAME
        path = REPO_ROOT / 'data' / 'esohub' / 'sets_en.json'
        links = json.loads(path.read_text(encoding='utf-8'))['sets']
        for set_id, name, page in (('854', "Prowler's Talisman", '/en/sets/prowlers-talisman'),
                                   ('876', "Tarcyr", '/en/sets/tarcyr'),
                                   ('877', "Mylenne Moon-Caller", '/en/sets/mylenne-moon-caller')):
            self.assertEqual(SET_ID_TO_NAME[set_id], name)
            self.assertEqual(links[name], page)

    def test_the_clients_name_wins_and_neither_source_loses_a_set(self):
        try:
            script = _load('generate_gear_data.py')
        except ImportError:
            self.skipTest('openpyxl is not installed (requirements-build.txt)')
        workbook = {'711': "Jerall Mountains Warchief", '163': "Blood Spawn",
                    '483': "Template_Drop_Magi"}
        client = {'711': "Colovian Highlands General", '163': "Bloodspawn",
                  '900': "Brand New Set"}
        with contextlib.redirect_stdout(io.StringIO()) as said:
            names = script.set_names(workbook, client)
        self.assertEqual(names, {'711': "Colovian Highlands General", '163': "Bloodspawn",
                                 '483': "Template_Drop_Magi", '900': "Brand New Set"})
        self.assertIn("2 named by the client where the workbook differs, 1 from the client only",
                      said.getvalue())
        self.assertIn("client only 900: Brand New Set", said.getvalue())

    def test_a_missing_snapshot_leaves_the_workbooks_names(self):
        try:
            script = _load('generate_gear_data.py')
        except ImportError:
            self.skipTest('openpyxl is not installed (requirements-build.txt)')
        with tempfile.TemporaryDirectory() as temp, \
                contextlib.redirect_stdout(io.StringIO()) as said:
            self.assertEqual(script.load_client_names(Path(temp) / 'none.json'), {})
        self.assertIn("Warning", said.getvalue())

    def test_every_client_name_is_in_the_committed_data(self):
        # data/client/set_names_en.json is what CI builds src/gear_set_data.py from
        from gear_set_data import SET_ID_TO_NAME, SET_INFO
        path = REPO_ROOT / 'data' / 'client' / 'set_names_en.json'
        client = json.loads(path.read_text(encoding='utf-8'))['sets']
        self.assertGreater(len(client), 700)
        for set_id, name in client.items():
            self.assertEqual(SET_ID_TO_NAME.get(set_id), name)
            self.assertEqual(SET_INFO[name]['set_id'], set_id)
        # The workbook still types the sets it has
        self.assertEqual(SET_INFO["Bloodspawn"]['set_type'], 'LIBSETS_SETTYPE_MONSTER')

    def test_every_mythic_the_workbook_types_reads_as_mythic(self):
        # The fight pane used a hand-kept list of 20 names, two of them not
        # set names ("Kilt", "Antiquarian's Eye"); it missed 19 of 36 mythics
        from player_build import is_mythic_set
        for name in ("Harpooner's Wading Kilt", "Belharza's Band", "Rourken Steamguards",
                     "Prowler's Talisman", "Oakensoul Ring"):
            self.assertTrue(is_mythic_set(name), name)
        for name in ("Bloodspawn", "Perfected Arms of Relequen", "Kilt", "Antiquarian's Eye"):
            self.assertFalse(is_mythic_set(name), name)


class TestClientNameCheck(unittest.TestCase):
    """scripts/check_client_names.py: the patch-day check of the bundled
    names against the client's en.lang (issue #79)."""

    @classmethod
    def setUpClass(cls):
        cls.script = _load('check_client_names.py')

    def test_reads_only_the_wanted_tables_and_drops_grammar_markers(self):
        rows = ('"ID","Unknown","Index","Offset","Text"\n'
                '"38727365","0","270","1","Slimecraw"\n'
                '"242841733","0","251","2","battle axe^n"\n'
                '"198758357","0","16536","3","Meteor, the ""big"" one"\n'
                '"162658389","0","1592","4","March of Sacrifices"\n')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'en.lang.csv'
            path.write_text(rows, encoding='utf-8')
            tables = self.script.read_tables(path, ('38727365', '198758357', '242841733'))
        self.assertEqual(tables, {'38727365': {'270': "Slimecraw"},
                                  '198758357': {'16536': 'Meteor, the "big" one'},
                                  '242841733': {'251': "battle axe"}})

    def test_a_rename_is_a_difference_and_an_unnamed_id_is_not(self):
        renamed, unnamed = self.script.by_id(
            "t", {'1': "Same", '2': "Old", '3': "Gone"}, {'1': "Same", '2': "New"})
        self.assertEqual(renamed, ["t: 2 is 'Old' here, 'New' in the client"])
        self.assertEqual(unnamed, ["t: 3"])
        # A hand-kept set list holds no retired id
        strict, none = self.script.by_id("t", {'3': "Gone"}, {}, strict=True)
        self.assertEqual((strict, none), (["t: 3 'Gone' is not in the client"], []))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.script.report({'s': ([], unnamed)}), 0)
            self.assertEqual(self.script.report({'s': (renamed, unnamed)}), 1)

    def test_a_skill_id_must_carry_one_of_its_lists_names(self):
        renamed, unnamed = self.script.ids_named(
            "TAUNT", {'28306', '99', '41473'}, {"Puncture"},
            {'28306': "Puncture", '99': "Meteor"})
        self.assertEqual(renamed, ["TAUNT: 99 is 'Meteor' in the client, not one of the listed names"])
        self.assertEqual(unnamed, ["TAUNT: 41473"])

    def test_reads_the_code_lists_without_importing_them(self):
        issues = REPO_ROOT / 'src' / 'build_issues.py'
        proc = self.script.literal(issues, 'PROC_SETS')
        self.assertEqual(proc['232'], "Roar of Alkosh")
        self.assertIn('39095', self.script.literal(issues, 'ELEMENTAL_DRAIN_IDS'))
        self.assertEqual(self.script.literal(issues, 'GROUP_SETS')['768'], "Lucent Echoes")
        with self.assertRaises(KeyError):
            self.script.literal(issues, 'NO_SUCH_NAME')


class TestWeaponSkillLines(unittest.TestCase):
    """scripts/generate_weapon_skill_lines.py: the active weapon-line skills
    of UESP's player skill table, by game id (build_issues)."""

    # UESP playerSkills rows cut down: two ranks of a weapon skill, a scribed
    # one with UESP's synthetic rank id, an internal rank -1 effect, a weapon
    # passive, a class skill, a broken row
    SAMPLE = {'playerSkills': [
        {'id': '38788', 'name': 'Stampede', 'skillLine': 'Two Handed', 'rank': '1',
         'isPassive': '0', 'isCrafted': '0'},
        {'id': '39797', 'name': 'Stampede', 'skillLine': 'Two Handed', 'rank': '2',
         'isPassive': '0', 'isCrafted': '0'},
        {'id': '217228', 'name': 'Elemental Explosion', 'skillLine': 'Destruction Staff',
         'rank': '1', 'isPassive': '0', 'isCrafted': '1'},
        {'id': '20217228', 'name': 'Elemental Explosion', 'skillLine': 'Destruction Staff',
         'rank': '2', 'isPassive': '0', 'isCrafted': '1'},
        {'id': '21972', 'name': 'Bash', 'skillLine': 'One Hand and Shield', 'rank': '-1',
         'isPassive': '0', 'isCrafted': '1'},
        {'id': '29388', 'name': 'Forceful', 'skillLine': 'Two Handed', 'rank': '1',
         'isPassive': '1', 'isCrafted': '0'},
        {'id': '15540', 'name': 'Toppling Charge', 'skillLine': 'Aedric Spear', 'rank': '1',
         'isPassive': '0', 'isCrafted': '0'},
        {'id': '', 'name': 'No Id', 'skillLine': 'Bow', 'rank': '1', 'isPassive': '0'},
        'not a row',
    ]}

    @classmethod
    def setUpClass(cls):
        cls.script = _load('generate_weapon_skill_lines.py')

    def test_active_weapon_skills_by_id(self):
        self.assertEqual(self.script.weapon_skill_lines(self.SAMPLE), {
            '38788': {'line': 'Two Handed', 'name': 'Stampede'},
            '39797': {'line': 'Two Handed', 'name': 'Stampede'},
            '217228': {'line': 'Destruction Staff', 'name': 'Elemental Explosion'},
        })
        self.assertEqual(self.script.weapon_skill_lines({}), {})
        self.assertEqual(self.script.weapon_skill_lines({'playerSkills': 'nope'}), {})

    def test_a_short_response_would_not_overwrite(self):
        self.assertLess(len(self.script.weapon_skill_lines(self.SAMPLE)), self.script.MIN_ROWS)

    def test_file_is_json_one_skill_per_line(self):
        skills = self.script.weapon_skill_lines(self.SAMPLE)
        text = self.script.render(skills, '2026-10-24T00:00:00+00:00')
        data = json.loads(text)
        self.assertEqual(data['skills'], skills)
        self.assertEqual(data['count'], 3)
        self.assertIn('UESP', data['attribution'])
        self.assertEqual(sum(1 for line in text.splitlines() if '"line":' in line), 3)

    def test_a_saved_reply_is_read_in_place_of_the_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / 'reply.json'
            saved.write_text(json.dumps(self.SAMPLE), encoding='utf-8')
            with mock.patch.object(self.script, 'OUT_PATH', Path(tmp) / 'out.json'), \
                    mock.patch.object(self.script, 'MIN_ROWS', 1):
                self.assertEqual(self.script.main(['--from', str(saved)]), 0)
                data = json.loads((Path(tmp) / 'out.json').read_text(encoding='utf-8'))
            self.assertEqual(set(data['skills']), {'38788', '39797', '217228'})
            saved.write_text('not json', encoding='utf-8')
            with self.assertRaises(SystemExit):
                self.script.main(['--from', str(saved)])

    def test_committed_table(self):
        data = json.loads(self.script.OUT_PATH.read_text(encoding='utf-8'))
        skills = data['skills']
        self.assertEqual(data['count'], len(skills))
        self.assertGreaterEqual(len(skills), self.script.MIN_ROWS)
        self.assertEqual(set(entry['line'] for entry in skills.values()),
                         set(self.script.WEAPON_LINES))
        # Skills slotted in real logs, at the rank the log wrote
        for ability_id, line in (('38788', 'Two Handed'), ('39807', 'Two Handed'),
                                 ('38689', 'Bow'), ('39011', 'Destruction Staff'),
                                 ('41769', 'Destruction Staff'), ('38250', 'One Hand and Shield'),
                                 ('37232', 'Restoration Staff'), ('28279', 'Two Handed'),
                                 ('217228', 'Destruction Staff'), ('39095', 'Destruction Staff')):
            self.assertEqual(skills[ability_id]['line'], line, ability_id)
        # No passive, internal effect or synthetic id
        self.assertNotIn('21972', skills)
        self.assertNotIn('20217228', skills)
        self.assertFalse(any(int(i) >= self.script.SYNTHETIC_ID for i in skills))


class TestClassPassives(unittest.TestCase):
    """scripts/generate_class_passives.py: the class passives of UESP's
    player skill table, by game id."""

    # UESP playerSkills rows cut down: a passive in two ranks, a mastery, an
    # active, a weapon passive, an effect without a class, a broken row
    SAMPLE = {'playerSkills': [
        {'id': '29424', 'name': 'Combustion', 'classType': 'Dragonknight', 'skillLine': 'Ardent Flame',
         'baseAbilityId': '29424', 'rank': '1', 'isPassive': '1', 'skillType': '1'},
        {'id': '45011', 'name': 'Combustion', 'classType': 'Dragonknight', 'skillLine': 'Ardent Flame',
         'baseAbilityId': '29424', 'rank': '2', 'isPassive': '1', 'skillType': '1'},
        {'id': '263604', 'name': 'An Eye for Exploitation', 'classType': 'Nightblade',
         'skillLine': 'Class Mastery', 'baseAbilityId': '263604', 'rank': '1', 'isPassive': '1',
         'skillType': '1'},
        {'id': '15540', 'name': 'Toppling Charge', 'classType': 'Templar', 'skillLine': 'Aedric Spear',
         'baseAbilityId': '22149', 'rank': '1', 'isPassive': '0', 'skillType': '1'},
        {'id': '45596', 'name': 'Slayer', 'classType': '', 'skillLine': 'Fighters Guild',
         'baseAbilityId': '45596', 'rank': '2', 'isPassive': '1', 'skillType': '3'},
        {'id': '', 'name': 'No Id', 'classType': 'Warden', 'skillLine': 'Green Balance',
         'isPassive': '1', 'skillType': '1'},
        'not a row',
    ]}

    @classmethod
    def setUpClass(cls):
        cls.script = _load('generate_class_passives.py')

    def test_class_passives_by_id_with_both_ranks_and_masteries(self):
        self.assertEqual(self.script.class_passives(self.SAMPLE), {
            '29424': {'class': 'Dragonknight', 'line': 'Ardent Flame', 'name': 'Combustion', 'rank': 1},
            '45011': {'class': 'Dragonknight', 'line': 'Ardent Flame', 'name': 'Combustion', 'rank': 2},
            '263604': {'class': 'Nightblade', 'line': 'Class Mastery',
                       'name': 'An Eye for Exploitation', 'rank': 1},
        })
        self.assertEqual(self.script.class_passives({}), {})
        self.assertEqual(self.script.class_passives({'playerSkills': 'nope'}), {})

    def test_a_short_response_would_not_overwrite(self):
        counts = self.script.per_class(self.script.class_passives(self.SAMPLE))
        self.assertLess(max(counts.values()), self.script.PASSIVES_PER_CLASS)

    # UESP minedSkills rows cut down: the passive itself, two effects of the
    # mastery, a monster ability of the same name, an unrelated skill
    MINED = {'minedSkills': [
        {'id': '263604', 'name': 'An Eye for Exploitation', 'isPassive': '1', 'target': 'Self'},
        {'id': '263640', 'name': 'An Eye for Exploitation', 'isPassive': '1', 'target': 'Self'},
        {'id': '263411', 'name': 'Unbound Potential', 'isPassive': '0', 'target': 'Self'},
        {'id': '107994', 'name': 'Pound of Flesh', 'isPassive': '0', 'target': 'Enemy'},
        {'id': '263549', 'name': 'Pound of Flesh', 'isPassive': '1', 'target': 'Self'},
        {'id': '45060', 'name': 'Hemorrhage', 'isPassive': '1', 'target': 'Self'},
        {'id': '263306', 'name': 'Major Berserk', 'isPassive': '0', 'target': ''},
        {'id': '61745', 'name': 'Major Berserk', 'isPassive': '0', 'target': ''},
        'not a row',
    ]}
    MASTERIES = {
        '263604': {'class': 'Nightblade', 'line': 'Class Mastery', 'name': 'An Eye for Exploitation', 'rank': 1},
        '263410': {'class': 'Arcanist', 'line': 'Class Mastery', 'name': 'Unbound Potential', 'rank': 1},
        '263549': {'class': 'Necromancer', 'line': 'Class Mastery', 'name': 'Pound of Flesh', 'rank': 1},
        '263247': {'class': 'Dragonknight', 'line': 'Class Mastery', 'name': 'Lead from the Front', 'rank': 1},
        '45060': {'class': 'Nightblade', 'line': 'Assassination', 'name': 'Hemorrhage', 'rank': 2},
    }

    def test_mastery_effects_by_id_without_the_passives_or_monster_abilities(self):
        # The buff-named signature effect comes in with the buff's name kept;
        # the ordinary Major Berserk id does not
        self.assertEqual(self.script.mastery_effects(self.MINED, self.MASTERIES), {
            '263306': {'class': 'Dragonknight', 'name': 'Lead from the Front', 'effect': 'Major Berserk'},
            '263411': {'class': 'Arcanist', 'name': 'Unbound Potential'},
            '263640': {'class': 'Nightblade', 'name': 'An Eye for Exploitation'},
        })
        self.assertEqual(self.script.mastery_effects({}, self.MASTERIES), {})
        self.assertEqual(self.script.mastery_effects(self.MINED, {}), {})
        for mastery in self.script.SIGNATURE_EFFECTS.values():
            self.assertIn(mastery, {'Lead from the Front', "Tundra's Maw", 'Bountiful Harvest',
                                    "Cutthroat's Focus", 'Devout Guardian'})

    def test_file_is_json_one_passive_per_line(self):
        passives = self.script.class_passives(self.SAMPLE)
        effects = self.script.mastery_effects(self.MINED, self.MASTERIES)
        text = self.script.render(passives, effects, '2026-10-15T00:00:00+00:00')
        data = json.loads(text)
        self.assertEqual(data['passives'], passives)
        self.assertEqual(data['count'], 3)
        self.assertEqual(data['mastery_effects'], effects)
        self.assertEqual(data['mastery_effects_count'], 3)
        self.assertIn('UESP', data['attribution'])
        self.assertEqual(sum(1 for line in text.splitlines() if '"class":' in line), 6)

    def test_committed_table_matches_the_script(self):
        data = json.loads((REPO_ROOT / 'data' / 'skills' / 'class_passives.json')
                          .read_text(encoding='utf-8'))
        self.assertEqual(data['count'], len(data['passives']))
        self.assertEqual(data['mastery_effects_count'], len(data['mastery_effects']))
        self.assertGreaterEqual(len(data['mastery_effects']), self.script.MIN_MASTERY_EFFECTS)
        masteries = {e['name'] for e in data['passives'].values() if e['line'] == 'Class Mastery'}
        for ability_id, effect in data['mastery_effects'].items():
            self.assertIn(effect['name'], masteries)
            self.assertNotIn(ability_id, data['passives'])
        counts = self.script.per_class(data['passives'])
        self.assertEqual(set(counts), set(self.script.CLASSES))
        for class_name, count in counts.items():
            self.assertEqual(count, self.script.PASSIVES_PER_CLASS, class_name)
        self.assertEqual(data['passives'], self.script.class_passives(
            {'playerSkills': [dict(id=i, isPassive='1', skillType='1', classType=e['class'],
                                   skillLine=e['line'], name=e['name'], rank=str(e['rank']))
                              for i, e in data['passives'].items()]}))


TARGETS_SAMPLE = {
    "numRecords": 8,
    "minedSkills": [
        {"id": "28800", "name": "Impulse", "target": "Area", "isPlayer": "1"},
        {"id": "46324", "name": "Crystal Fragments", "target": "Enemy", "isPlayer": "1"},
        {"id": "40161", "name": "Flawless Dawnbreaker", "target": "Cone", "isPlayer": "1"},
        {"id": "1", "name": "A ground effect", "target": "Ground", "isPlayer": "1"},
        {"id": "2", "name": "A self buff", "target": "Self", "isPlayer": "1"},
        {"id": "3", "name": "No target", "target": "", "isPlayer": "1"},
        {"id": "95687", "name": "Oppressive Bolts", "target": "Enemy", "isPlayer": "0"},
        {"id": "x", "name": "Bad id", "target": "Area", "isPlayer": "1"},
    ],
}


class TestAbilityTargets(unittest.TestCase):
    """scripts/generate_ability_targets.py: player skills' target kinds for
    the area rule (damage_kinds), from UESP's mined skill table."""

    @classmethod
    def setUpClass(cls):
        cls.script = _load('generate_ability_targets.py')

    def test_player_skills_are_sorted_into_area_and_single(self):
        kinds = self.script.ability_targets(TARGETS_SAMPLE)
        self.assertEqual(kinds['area'], [1, 28800, 40161])   # Area, Cone and Ground
        self.assertEqual(kinds['single'], [46324])            # Enemy
        self.assertEqual(kinds['read'], 7)                    # the monster row is not read
        text = self.script.render(kinds, '2026-10-27T00:00:00+00:00', 'test')
        data = json.loads(text)
        self.assertEqual((data['area'], data['single'], data['count']), ([1, 28800, 40161], [46324], 4))
        self.assertIn('UESP', data['attribution'])

    def test_main_refuses_a_short_reply_and_writes_a_full_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            reply = Path(tmp) / 'mined_skills.json'
            reply.write_text(json.dumps(TARGETS_SAMPLE), encoding='utf-8')
            out = Path(tmp) / 'ability_targets.json'
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(self.script.main(['--from', str(reply), '--out', str(out)]), 1)
            self.assertIn('not writing', err.getvalue())
            self.assertFalse(out.exists())
            with mock.patch.object(self.script, 'MIN_ROWS', 1), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.script.main(['--from', str(reply), '--out', str(out)]), 0)
            data = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(data['single'], [46324])
            self.assertIn('mined_skills.json', data['source'])
            # And the loader reads the shape the script writes
            from damage_kinds import table_target
            self.assertEqual(table_target('28800', path=out), 'area')
            self.assertEqual(table_target('46324', path=out), 'single')
            self.assertIsNone(table_target('2', path=out))

    def test_committed_table(self):
        data = json.loads((REPO_ROOT / 'data' / 'skills' / 'ability_targets.json')
                          .read_text(encoding='utf-8'))
        self.assertEqual(data['count'], len(data['area']) + len(data['single']))
        self.assertGreaterEqual(data['count'], self.script.MIN_ROWS)
        self.assertIn('UESP', data['attribution'])
        self.assertIn(28800, data['area'])        # Impulse
        self.assertIn(28858, data['area'])        # Wall of Elements
        self.assertIn(46324, data['single'])      # Crystal Fragments
        self.assertIn(18718, data['single'])      # Mages' Fury
        self.assertFalse(set(data['area']) & set(data['single']))
        from damage_kinds import reset_target_table, table_target
        reset_target_table()
        self.assertEqual(table_target('28800'), 'area')


class TestSetText(unittest.TestCase):
    """Issue #79: set bonus text (scripts/generate_set_offense.py, a second
    table from the same reply)."""

    SUMMARY = {"setSummary": [
        {"gameId": "232", "setName": "Roar of Alkosh",
         "setBonusDesc1": "(2 items) Adds 15-657 Critical Chance",
         "setBonusDesc2": "(5 items) When you activate a synergy, you send a shockwave.  It scales.",
         "setBonusDesc3": ""},
        {"gameId": "393", "setName": "Perfected Arms of Relequen",
         "setBonusDesc1": "(2 perfected items) Adds 1096 Maximum Stamina"},
        {"gameId": "", "setName": "No Id"},
        {"gameId": "999", "setName": "No Lines", "setBonusDesc1": "no piece count"},
    ]}

    def test_every_bonus_line_is_kept_with_its_piece_count(self):
        gen = _load('generate_set_offense.py')
        self.assertEqual(gen.set_texts(self.SUMMARY), {
            "232": {"name": "Roar of Alkosh", "bonuses": [
                {"pieces": 2, "text": "Adds 15-657 Critical Chance"},
                {"pieces": 5, "text": "When you activate a synergy, you send a shockwave. It scales."}]},
            "393": {"name": "Perfected Arms of Relequen", "bonuses": [
                {"pieces": 2, "text": "Adds 1096 Maximum Stamina", "perfected": True}]},
        })

    def test_the_committed_text_covers_every_set_the_offense_table_names(self):
        sets = REPO_ROOT / 'data' / 'sets'
        text = json.loads((sets / 'bonuses_en.json').read_text(encoding='utf-8'))
        offense = json.loads((sets / 'offense.json').read_text(encoding='utf-8'))
        self.assertIn('CC-BY-SA', text['attribution'])
        self.assertGreater(text['count'], 700)
        self.assertEqual(sorted(set(offense['sets']) - set(text['sets'])), [])
        alkosh = text['sets']['232']['bonuses']
        self.assertEqual([b['pieces'] for b in alkosh], [2, 3, 4, 5])
        self.assertIn("Minor Slayer", alkosh[1]['text'])


def _gear(*pieces):
    """A PLAYER_INFO gear list of (slot, set id) pairs."""
    return '[' + ','.join(f'[{slot},95044,T,16,ARMOR_DIVINES,LEGENDARY,{set_id},MAGICKA,T,16,LEGENDARY]'
                          for slot, set_id in pieces) + ']'


# Five Roaring Opportunist pieces, two of them perfected
RO_GEAR = _gear(('HEAD', 496), ('CHEST', 496), ('SHOULDERS', 496), ('LEGS', 497), ('WAIST', 497))
BEGIN_LOG = '0,BEGIN_LOG,1700000000000,15,"NA Megaserver","en","eso.live.11.0"'
SLAYER_INFO = '1,ABILITY_INFO,135923,"Major Slayer","/esoui/art/icons/x.dds",F,T'


def _effect(ability, source):
    return f'20,EFFECT_CHANGED,GAINED,1,7,{ability},{source},20000/20000,0/0,0/0,0/0,0/0,0,0.5,0.5,0.0,*'


class TestSetBuffs(unittest.TestCase):
    """Issue #79, decision 5: the set behind a Major or Minor buff, from split
    logs and the bundled bonus text (scripts/generate_set_buffs.py)."""

    def test_a_perfected_set_and_its_base_are_one_family(self):
        gen = _load('generate_set_buffs.py')
        ids, buffs, family_of = gen.set_families({
            "496": {"name": "Roaring Opportunist", "bonuses": [
                {"pieces": 5, "text": "you and up to 5 group members gain Major Slayer"}]},
            "497": {"name": "Perfected Roaring Opportunist", "bonuses": [
                {"pieces": 3, "text": "Gain Minor Slayer at all times"},
                {"pieces": 5, "text": "you and up to 5 group members gain Major Slayer"}]},
            "19": {"name": "Vestments of the Warlock", "bonuses": [
                {"pieces": 2, "text": "Adds 3-129 Magicka Recovery"}]},
        })
        self.assertEqual(ids["Roaring Opportunist"], ["496", "497"])
        self.assertEqual(buffs, {"Roaring Opportunist": {"Major Slayer": 5, "Minor Slayer": 3}})
        self.assertEqual(family_of["497"], "Roaring Opportunist")

    def test_sessions_hold_each_players_worn_sets_and_sourced_effects(self):
        gen = _load('generate_set_buffs.py')
        names = {}
        lines = [BEGIN_LOG, SLAYER_INFO,
                 f'5,PLAYER_INFO,1,[13975],[1],{RO_GEAR},[1],[2]',
                 '5,PLAYER_INFO,2,[13975],[1],[],[1],[2]',
                 _effect(135923, 1),
                 _effect(135923, 3),  # no PLAYER_INFO, so not a player session
                 BEGIN_LOG,
                 f'5,PLAYER_INFO,1,[13975],[1],{_gear(("HEAD", 496), ("CHEST", 497))},[1],[2]']
        family_of = {"496": "Roaring Opportunist", "497": "Roaring Opportunist"}
        self.assertEqual(gen.read_sessions(lines, family_of, names), [
            ({"Roaring Opportunist": 5}, {"135923"}),
            ({}, set()),
            ({"Roaring Opportunist": 2}, set()),
        ])
        self.assertEqual(names, {"135923": "Major Slayer"})

    def test_a_buff_is_tied_when_named_worn_and_rare_elsewhere(self):
        gen = _load('generate_set_buffs.py')
        family_buffs = {"Roaring Opportunist": {"Major Slayer": 5},
                        "War Machine": {"Major Slayer": 5},
                        "Mender's Ward": {"Major Vitality": 2},
                        "Few Wearers": {"Major Force": 5}}
        names = {"135923": "Major Slayer", "93442": "Major Slayer", "93109": "Major Slayer",
                 "61713": "Major Vitality", "113653": "Major Vitality", "1": "Major Force"}
        ro = {"Roaring Opportunist": 5}
        sessions = (
            [(ro, {"135923", "93109"})] * 5
            # worn with Jorvuld's Guidance, which names no Major Slayer: still RO's
            + [({**ro, "Jorvuld's Guidance": 5}, {"135923", "93109"})] * 5
            + [({"War Machine": 5}, {"93442", "93109"})] * 5
            + [({"Mender's Ward": 2}, {"61713", "113653"})] * 5
            + [({"Few Wearers": 5}, {"1"})] * 4
            + [({}, {"61713"})] * 3  # 3% of the others write that id too
            + [({}, set())] * 97)
        tied, shared = gen.tie_buffs(sessions, family_buffs, names)
        self.assertEqual({a: row[:3] for a, row in tied.items()}, {
            "135923": ("Roaring Opportunist", "Major Slayer", 10),
            "93442": ("War Machine", "Major Slayer", 5),
            "113653": ("Mender's Ward", "Major Vitality", 5),
        })
        self.assertEqual(shared, {"93109": ["Roaring Opportunist", "War Machine"]})

    def test_main_reads_a_session_copied_twice_once(self):
        gen = _load('generate_set_buffs.py')
        session = [BEGIN_LOG, SLAYER_INFO, f'5,PLAYER_INFO,1,[13975],[1],{RO_GEAR},[1],[2]',
                   '5,PLAYER_INFO,2,[13975],[1],[],[1],[2]', _effect(135923, 1)]
        text = '\n'.join(session * 5) + '\n'
        with tempfile.TemporaryDirectory() as temp:
            folder, out = Path(temp) / 'splits', Path(temp) / 'set_buffs.json'
            folder.mkdir()
            for name in ('261001120000-Sunspire-vet.log', '261001120000-Sunspire-vet-2.log',
                         '261001130000-temp.log'):
                (folder / name).write_text(text, encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(gen.main(['--dir', str(folder), '--out', str(out)]), 0)
            data = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(data['source'], "1 split logs, 10 player sessions")
        self.assertEqual(data['buffs'], {"135923": {
            "name": "Major Slayer", "set": "Roaring Opportunist", "set_ids": ["496", "497"],
            "sessions": 5, "wearers": 1.0, "others": 0.0}})

    def test_a_folder_with_no_players_writes_nothing(self):
        gen = _load('generate_set_buffs.py')
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'set_buffs.json'
            (Path(temp) / '261001120000-Sunspire-vet.log').write_text(BEGIN_LOG + '\n', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(gen.main(['--dir', temp, '--out', str(out)]), 1)
            self.assertFalse(out.exists())

    def test_the_committed_table_names_each_buff_in_its_sets_text(self):
        sets = REPO_ROOT / 'data' / 'sets'
        buffs = json.loads((sets / 'set_buffs.json').read_text(encoding='utf-8'))['buffs']
        text = json.loads((sets / 'bonuses_en.json').read_text(encoding='utf-8'))['sets']
        self.assertGreaterEqual(len(buffs), 30)
        for ability_id, row in buffs.items():
            self.assertEqual(set(row), {"name", "set", "set_ids", "sessions", "wearers", "others"})
            self.assertTrue(any(row['name'] in bonus['text']
                                for set_id in row['set_ids'] for bonus in text[set_id]['bonuses']),
                            ability_id)
        # Roaring Opportunist's own Major Slayer, while 93109 is shared with
        # War Machine and Master Architect
        self.assertEqual(buffs['135923']['set'], "Roaring Opportunist")
        self.assertNotIn('93109', buffs)


if __name__ == '__main__':
    unittest.main()
