#!/usr/bin/env python3
"""The esobuild.com asset export (scripts/export_esobuild_assets.py): the
tables it builds from UESP rows, the client version it reads, the site's
hand-over checks and the bundle files. No network and no game files."""

import importlib.util
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load(script: str):
    path = REPO_ROOT / 'scripts' / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


export = _load('export_esobuild_assets.py')
ICONS = '/esoui/art/icons/'


def tree_row(ability_id, name, line, kind='Active', base=None):
    return {"abilityId": str(ability_id), "displayId": str(ability_id), "skillTypeName": line,
            "baseName": base or name, "name": name, "rank": "1", "maxRank": "4", "type": kind,
            "icon": ICONS + "x.dds"}


def player_row(ability_id, name, icon, line, cls='', skill_type='1', base=None, morph=0, rank=1,
               passive=False, crafted=False):
    return {"id": str(ability_id), "displayId": str(ability_id), "name": name, "texture": ICONS + icon + ".dds",
            "isPassive": "1" if passive else "0", "classType": cls, "skillLine": line,
            "baseAbilityId": str(base if base is not None else ability_id), "rank": str(rank),
            "morph": str(morph), "skillType": skill_type, "isCrafted": "1" if crafted else "0"}


def mined_row(ability_id, name, icon, mechanic='1'):
    return {"id": str(ability_id), "name": name, "texture": ICONS + icon + ".dds", "mechanic": mechanic}


# A cut-down game: two Dragonknight skills with a morph and a second rank, a
# passive, a weapon skill, one Class Mastery passive for each of two classes,
# and a grimoire
TREE = [
    tree_row(100, "Lava Whip", "Dragonknight::Ardent Flame"),
    tree_row(101, "Molten Whip", "Dragonknight::Ardent Flame", base="Lava Whip"),
    tree_row(102, "Molten Whip", "Dragonknight::Ardent Flame", base="Lava Whip"),
    tree_row(20000101, "Molten Whip", "Dragonknight::Ardent Flame", base="Lava Whip"),
    tree_row(110, "Dragonknight Standard", "Dragonknight::Ardent Flame", kind="Ultimate"),
    tree_row(120, "Combustion", "Dragonknight::Ardent Flame", kind="Passive"),
    tree_row(200, "Cleave", "Weapon::Two Handed"),
    tree_row(300, "Draconic Verve", "Dragonknight::Class Mastery", kind="Passive"),
    tree_row(301, "Storm Verve", "Sorcerer::Class Mastery", kind="Passive"),
]
PLAYER = [
    player_row(100, "Lava Whip", "ability_dragonknight_001", "Ardent Flame", "Dragonknight"),
    player_row(101, "Molten Whip", "ability_dragonknight_001_b", "Ardent Flame", "Dragonknight", base=100, morph=1),
    player_row(102, "Molten Whip", "ability_dragonknight_001_b", "Ardent Flame", "Dragonknight", base=100,
               morph=1, rank=2),
    player_row(20000101, "Molten Whip", "ability_dragonknight_001_b", "Ardent Flame", "Dragonknight", base=100,
               morph=1, rank=3),
    player_row(110, "Dragonknight Standard", "ability_dragonknight_006", "Ardent Flame", "Dragonknight"),
    player_row(120, "Combustion", "ability_dragonknight_024", "Ardent Flame", "Dragonknight", passive=True),
    player_row(150, "Petrify dummy", "ability_mage_065", "Ardent Flame", "Dragonknight", base=-1, rank=-1),
    player_row(200, "Cleave", "ability_2handed_002", "Two Handed", skill_type="2"),
    player_row(300, "Draconic Verve", "passive_dragonknight_01", "Class Mastery", "Dragonknight", passive=True),
    player_row(301, "Storm Verve", "passive_sorcerer_01", "Class Mastery", "Sorcerer", passive=True),
    player_row(400, "Banner Bearer", "ability_grimoire_support", "Support", skill_type="6", base=-1, rank=-1,
               crafted=True),
    player_row(401, "Minor Force", "ability_mage_065", "Support", skill_type="6", base=-1, rank=-1, crafted=True),
]
MINED = [mined_row(int(r["id"]), r["name"], r["texture"][len(ICONS):-4]) for r in PLAYER] + [
    mined_row(500, "Molten Whip", "ability_dragonknight_001_b"),          # same icon as 101
    mined_row(501, "Lava Whip", "ability_dragonknight_001_blackedout"),   # same family
    mined_row(502, "Lava Whip", "death_recap_fire_melee"),                # another family
    mined_row(503, "Lava Whip", "ability_mage_065"),                      # placeholder icon
    mined_row(504, "Combustion", "ability_dragonknight_024"),             # a passive's name
    mined_row(20000500, "Lava Whip", "ability_dragonknight_001"),         # not a game id
    mined_row(600, "Power Lash", "ability_warrior_025"),
    mined_row(601, "Crypt Transfer", "u38_ability_armor_ultimatetransfer", mechanic="8"),
    mined_row(602, "Lost Swap", "ability_warrior_001"),
    mined_row(13940, "Boon: The Warrior", "ability_mundusstones_001"),
]
SWAPS = {600: "Molten Whip", 601: None, 602: "No Such Skill", 603: "Lava Whip", 100: "Lava Whip"}


def build():
    with mock.patch.object(export, "BAR_SWAPS", SWAPS):
        return export.build_abilities(TREE, PLAYER, MINED)


class TestAbilityTables(unittest.TestCase):

    def test_skill_tree_abilities_keep_their_game_ids(self):
        abilities, _, origins, _ = build()
        self.assertEqual(abilities[101], {
            "name": "Molten Whip", "icon": "ability_dragonknight_001_b", "skill_line": "Ardent Flame",
            "class": "Dragonknight", "type": "active", "base_ability_id": 100, "base_name": "Lava Whip",
            "morph": 1, "rank": 1})
        self.assertEqual(abilities[102]["rank"], 2)
        self.assertEqual(abilities[110]["type"], "ultimate")
        self.assertEqual(abilities[120]["type"], "passive")
        self.assertEqual(abilities[200]["class"], None)
        self.assertEqual(origins["skill_tree"], 8)

    def test_what_is_not_a_game_skill_is_left_out(self):
        abilities, _, _, _ = build()
        self.assertNotIn(20000101, abilities, "UESP's numbering of a rank")
        self.assertNotIn(150, abilities, "a placeholder UESP flags as a player skill")
        self.assertNotIn(401, abilities, "a script's effect, not a slottable scribed skill")

    def test_scribed_skill_names_its_line_and_grimoire_icon(self):
        abilities, lines, origins, _ = build()
        self.assertEqual(abilities[400]["skill_line"], "Support")
        self.assertEqual((abilities[400]["type"], abilities[400]["base_ability_id"], abilities[400]["rank"]),
                         ("active", None, None))
        self.assertEqual(lines["Support"]["category"], "alliance-war")
        self.assertEqual(lines["Support"]["grimoire_icon_stems"], ["ability_grimoire_support"])
        self.assertNotIn("grimoire_icon_stems", lines["Two Handed"])
        self.assertEqual(origins["scribed"], 1)

    def test_variant_shares_a_slottable_skills_name_and_icon_family(self):
        abilities, _, origins, _ = build()
        self.assertEqual(abilities[500]["variant_of"], 101)
        self.assertEqual((abilities[501]["variant_of"], abilities[501]["icon"], abilities[501]["rank"]),
                         (100, "ability_dragonknight_001_blackedout", None))
        self.assertEqual(abilities[501]["skill_line"], "Ardent Flame")
        for ability_id in (502, 503, 504, 20000500):
            self.assertNotIn(ability_id, abilities)
        self.assertEqual(origins["variant"], 2)

    def test_bar_swaps_take_the_named_skills_line_or_none(self):
        abilities, lines, origins, notes = build()
        self.assertEqual((abilities[600]["name"], abilities[600]["skill_line"], abilities[600]["variant_of"]),
                         ("Power Lash", "Ardent Flame", 101))
        self.assertEqual((abilities[601]["skill_line"], abilities[601]["type"]), (None, "ultimate"))
        self.assertNotIn("variant_of", abilities[601])
        self.assertNotIn(602, abilities)
        self.assertNotIn(603, abilities)
        self.assertEqual(origins["bar_swap"], 2)
        self.assertIn(600, lines["Ardent Flame"]["ability_ids"])
        self.assertTrue(any("602" in n and "No Such Skill" in n for n in notes))
        self.assertTrue(any("603" in n and "not in UESP" in n for n in notes))
        self.assertTrue(any("100" in n and "skill tree" in n for n in notes))

    def test_a_line_name_shared_by_classes_gets_the_class(self):
        abilities, lines, _, _ = build()
        self.assertEqual(abilities[300]["skill_line"], "Class Mastery (Dragonknight)")
        self.assertEqual(lines["Class Mastery (Sorcerer)"],
                         {"category": "class", "class": "Sorcerer", "ability_ids": [301],
                          "game_name": "Class Mastery"})
        self.assertNotIn("game_name", lines["Ardent Flame"])
        self.assertEqual(lines["Ardent Flame"]["ability_ids"], [100, 101, 102, 110, 120, 500, 501, 600])

    def test_mundus_boons_are_abilities_without_a_line(self):
        abilities, _, origins, notes = build()
        self.assertEqual((abilities[13940]["name"], abilities[13940]["skill_line"], abilities[13940]["type"]),
                         ("Boon: The Warrior", None, "passive"))
        self.assertEqual(origins["mundus"], 1)
        self.assertTrue(any("13943" in n for n in notes), "a boon UESP lacks is reported")
        mundus = export.build_mundus(abilities, {"the-warrior": "/en/mundus-stones/the-warrior"})
        self.assertEqual(mundus, {13940: {"name": "The Warrior", "game_name": "Boon: The Warrior",
                                          "icon": "ability_mundusstones_001",
                                          "esohub": "/en/mundus-stones/the-warrior"}})
        self.assertIsNone(export.build_mundus(abilities, {})[13940]["esohub"], "no page, no guessed path")


class TestSets(unittest.TestCase):

    ROWS = [
        {"gameId": "270", "setName": "Slimecraw", "type": "Monster", "setMaxEquipCount": "2"},
        {"gameId": "388", "setName": "Aegis of Galenwe", "type": "Trial", "setMaxEquipCount": "5"},
        {"gameId": "392", "setName": "Perfected Aegis of Galenwe", "type": "Trial", "setMaxEquipCount": "5"},
        {"gameId": "163", "setName": "Bloodspawn", "type": "Monster", "setMaxEquipCount": "2"},
        {"gameId": "50", "setName": "The Morag Tong", "type": "PVP", "setMaxEquipCount": "5"},
        {"gameId": "51", "setName": "Night Mother's Embrace", "type": "PVP", "setMaxEquipCount": "5"},
        {"gameId": "855", "setName": "Gorethief", "type": "PvP", "setMaxEquipCount": "5"},
        {"gameId": "877", "setName": "Mylenne Moon-Caller", "type": "", "setMaxEquipCount": "0"},
        {"gameId": "0", "setName": "No Id", "type": "", "setMaxEquipCount": "5"},
    ]
    LIBSETS = {"163": "Blood Spawn", "392": "Perfect Aegis of Galenwe", "431": "Icy Conjuror",
               "483": "Template_Drop_Magi"}
    PAGES = {"slimecraw": "/en/sets/slimecraw", "bloodspawn": "/en/sets/bloodspawn",
             "icy-conjurer": "/en/sets/icy-conjurer",
             "perfected-aegis-of-galenwe": "/en/sets/perfected-aegis-of-galenwe"}

    def setUp(self):
        self.sets = export.build_sets(self.ROWS, self.LIBSETS, self.PAGES)

    def test_entry_shape(self):
        self.assertEqual(self.sets[270], {"name": "Slimecraw", "type": "Monster", "max_equip": 2,
                                          "perfected_id": None, "unperfected_id": None,
                                          "esohub": "/en/sets/slimecraw"})

    def test_perfected_sets_are_paired_by_name(self):
        self.assertEqual((self.sets[388]["perfected_id"], self.sets[388]["unperfected_id"]), (392, None))
        self.assertEqual((self.sets[392]["perfected_id"], self.sets[392]["unperfected_id"]), (None, 388))

    def test_the_games_name_wins_over_the_libsets_spelling(self):
        self.assertEqual(self.sets[163]["name"], "Bloodspawn")
        self.assertEqual(self.sets[392]["name"], "Perfected Aegis of Galenwe")

    def test_no_page_means_null_not_a_guess(self):
        self.assertIsNone(self.sets[388]["esohub"])
        self.assertEqual((self.sets[877]["type"], self.sets[877]["max_equip"], self.sets[877]["esohub"]),
                         (None, None, None))

    def test_set_only_libsets_knows_keeps_its_name_and_alias(self):
        self.assertEqual(self.sets[431], {"name": "Icy Conjuror", "type": None, "max_equip": None,
                                          "perfected_id": None, "unperfected_id": None,
                                          "esohub": "/en/sets/icy-conjurer"})
        self.assertNotIn(483, self.sets, "LibSets' test templates are not sets")
        self.assertNotIn(0, self.sets)

    def test_one_spelling_per_set_type(self):
        self.assertEqual(self.sets[855]["type"], "PVP")


class TestClientVersion(unittest.TestCase):

    def test_build_stamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            stamp = Path(tmp) / "depot" / "_databuild" / "databuild.stamp"
            stamp.parent.mkdir(parents=True)
            stamp.write_bytes(b"4000.win.3303624.live.3303624\r\n2026/09/25:05:30:56\r\n12.1.5")
            self.assertEqual(export.read_databuild(Path(tmp)),
                             {"build": "4000.win.3303624.live.3303624", "version": "12.1.5",
                              "channel": "live", "built": "2026-09-25T05:30:56"})
            stamp.write_text("something else")
            self.assertEqual(export.read_databuild(Path(tmp)), {})
        self.assertEqual(export.read_databuild(Path(tmp)), {}, "no stamp, no guess")

    def test_newest_begin_log_is_read_from_the_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "Encounter.log"
            log_path.write_text('5,BEGIN_LOG,1790000000000,15,"NA Megaserver","en","eso.live.12.0"\n'
                                + '100,UNIT_ADDED,1,PLAYER\n' * 50
                                + '4,BEGIN_LOG,1791186808935,15,"NA Megaserver","en","eso.live.12.1"\n'
                                + '100,UNIT_ADDED,1,PLAYER\n' * 50, encoding="utf-8")
            entry = export.last_begin_log(log_path)
            self.assertEqual((entry.game_version, entry.unix_timestamp), ("eso.live.12.1", 1791186808935))
            log_path.write_text('100,UNIT_ADDED,1,PLAYER\n', encoding="utf-8")
            self.assertIsNone(export.last_begin_log(log_path))
            self.assertIsNone(export.last_begin_log(Path(tmp) / "missing.log"))

    def test_log_version_names_the_client_version(self):
        self.assertTrue(export.same_version("eso.live.12.1.5", "eso.live.12.1"))
        self.assertTrue(export.same_version("eso.live.12.1", "eso.live.12.1"))
        self.assertFalse(export.same_version("eso.live.12.10.1", "eso.live.12.1"))
        self.assertFalse(export.same_version("eso.live.12.1.5", ""))


class TestFixtureChecks(unittest.TestCase):

    def run_checks(self, icons, rows, icon_stems):
        abilities, lines, _, _ = build()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "referenced-icons-u51.txt").write_text("\n".join(icons) + "\n", encoding="utf-8")
            (Path(tmp) / "referenced-abilities-u51.json").write_text(json.dumps({"abilities": rows}),
                                                                     encoding="utf-8")
            with mock.patch.multiple(export, SITE_CLASS_LINES={"Ardent Flame": "Dragonknight"},
                                     RENAMED_CLASS_SKILLS={101: "Molten Whip"},
                                     NOT_CLASS_SKILLS={200: ("Cleave", "Two Handed")}):
                return export.check_fixtures(Path(tmp), abilities, lines, icon_stems)

    ROWS = [
        {"ability_id": 101, "name": "Molten Whip", "icon": "ability_dragonknight_001_b"},
        {"ability_id": 501, "name": "Lava Whip", "icon": "ability_dragonknight_001_blackedout"},
        {"ability_id": 400, "name": "Sundering Banner", "icon": "ability_grimoire_support"},
        {"ability_id": 1013, "name": "Shocking Banner (Class Mastery / Courage)",
         "icon": "ability_grimoire_support"},
    ]

    def test_all_pass(self):
        icons = ["ability_dragonknight_001_b", "ability_grimoire_support"]
        report, ok = self.run_checks(icons, self.ROWS, set(icons))
        text = "\n".join(report)
        self.assertTrue(ok, text)
        self.assertIn("V1 ok   icons: 2 of 2", text)
        self.assertIn("V2 ok   abilities: 3 of 3 game ids are keys; names equal 2, icons equal 3", text)
        self.assertIn("1 more name differences are scribed skills", text)
        self.assertIn("1 rows are ESO Logs pseudo-ids for scribed skills (1013 to 1013)", text)
        self.assertIn("V3 ok   class lines: 2 of 2", text)
        self.assertIn("V5 ok   grimoires: 1 of 1", text)

    def test_missing_icon_and_unknown_id_fail(self):
        rows = self.ROWS + [{"ability_id": 999999, "name": "New Skill", "icon": "ability_dragonknight_099"}]
        report, ok = self.run_checks(["ability_dragonknight_001_b", "ability_u52_new"], rows,
                                     {"ability_dragonknight_001_b"})
        text = "\n".join(report)
        self.assertFalse(ok)
        self.assertIn("V1 FAIL icons: 1 of 2", text)
        self.assertIn("missing ability_u52_new", text)
        self.assertIn("V2 FAIL abilities: 3 of 4 game ids are keys", text)
        self.assertIn("unknown id 999999 New Skill", text)

    def test_a_weapon_skill_is_not_a_class_line(self):
        abilities, lines, _, _ = build()
        abilities[200]["skill_line"] = "Ardent Flame"  # what substring matching did to Carve
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "referenced-icons.txt").write_text("", encoding="utf-8")
            (Path(tmp) / "referenced-abilities.json").write_text('{"abilities": []}', encoding="utf-8")
            with mock.patch.multiple(export, SITE_CLASS_LINES={"Ardent Flame": "Dragonknight"},
                                     RENAMED_CLASS_SKILLS={}, NOT_CLASS_SKILLS={200: ("Cleave", "Two Handed")}):
                report, ok = export.check_fixtures(Path(tmp), abilities, lines, set())
        self.assertFalse(ok)
        self.assertIn("V4 FAIL", "\n".join(report))


class TestBundleFiles(unittest.TestCase):

    def make_bundle(self, folder: Path, abilities: dict) -> Path:
        (folder / "icons").mkdir(parents=True)
        (folder / "icons" / "ability_x.png").write_bytes(b"png-bytes")
        export.write_json(folder / "abilities.json", {"update": "u51", "abilities": abilities})
        export.write_json(folder / "skill_lines.json", {"update": "u51", "skill_lines": {"Two Handed": {}}})
        export.write_json(folder / "mundus.json", {"update": "u51", "mundus": {}})
        export.write_json(folder / "sets.json", {"update": "u51", "sets": {"270": {"name": "Slimecraw"}}})
        files = {p.relative_to(folder).as_posix(): export.sha1_bytes(p.read_bytes())
                 for p in folder.rglob("*") if p.is_file()}
        export.write_json(folder / "manifest.json", {
            "game": {"version": "eso.live.12.1.5"}, "files": files,
            "counts": {"icons": 1, "abilities": len(abilities), "skill_lines": 1, "mundus": 0, "sets": 1}})
        return folder

    def test_json_is_sorted_utf8_with_lf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            export.write_json(path, {"b": 1, "a": {"name": "Coup De Grâce"}})
            self.assertEqual(path.read_bytes(),
                             '{\n "a": {\n  "name": "Coup De Grâce"\n },\n "b": 1\n}\n'.encode("utf-8"))

    def test_manifest_verifies_and_notices_a_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self.make_bundle(Path(tmp) / "b", {"100": {"name": "Lava Whip"}})
            text, ok = export.verify_manifest(bundle)
            self.assertTrue(ok, text)
            self.assertIn("5 SHA-1s verify", text)
            (bundle / "icons" / "ability_x.png").write_bytes(b"other")
            text, ok = export.verify_manifest(bundle)
            self.assertFalse(ok)
            self.assertIn("1 SHA-1 mismatches", text)

    def test_zip_is_the_same_for_the_same_files_and_compares_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self.make_bundle(Path(tmp) / "one", {"100": {"name": "Lava Whip"}})
            second = self.make_bundle(Path(tmp) / "two", {"100": {"name": "Lava Whip"}})
            export.write_zip(first, Path(tmp) / "one.zip")
            export.write_zip(second, Path(tmp) / "two.zip")
            self.assertEqual((Path(tmp) / "one.zip").read_bytes(), (Path(tmp) / "two.zip").read_bytes())
            with zipfile.ZipFile(Path(tmp) / "one.zip") as archive:
                self.assertEqual(archive.namelist(), ["abilities.json", "icons/ability_x.png", "manifest.json",
                                                      "mundus.json", "sets.json", "skill_lines.json"])
            lines = export.compare_bundles(export.load_bundle(Path(tmp) / "one.zip"), export.load_bundle(second))
            self.assertIn("  V7 same client; files that differ besides manifest.json: 0 (identical)", lines)

    def test_comparison_lists_added_removed_and_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = self.make_bundle(Path(tmp) / "old", {"100": {"name": "Lava Whip"}, "101": {"name": "Old"}})
            new = self.make_bundle(Path(tmp) / "new", {"100": {"name": "Magma Whip"}, "102": {"name": "New"}})
            text = "\n".join(export.compare_bundles(export.load_bundle(old), export.load_bundle(new)))
        self.assertIn("abilities: 2 entries; vs previous: +1 -1 ~1", text)
        self.assertIn("added: 102 New", text)
        self.assertIn("removed: 101 Old", text)
        self.assertIn("changed: 100 Magma Whip", text)
        self.assertIn("files that differ besides manifest.json: 1 (abilities.json)", text)


class TestSources(unittest.TestCase):
    """Stored replies are reused, so a second run asks the servers nothing."""

    def store(self, folder: Path, age: timedelta):
        (folder / "skill_tree.json").write_bytes(b'{"rows": 1}')
        fetched = (datetime.now(timezone.utc) - age).isoformat(timespec="seconds")
        export.write_json(folder / "index.json", {"skill_tree": {"url": "https://example.invalid/x",
                                                                 "fetched": fetched}})

    def test_fresh_reply_is_reused_without_a_request(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(export.urllib.request, "urlopen", side_effect=AssertionError("no network")), \
                mock.patch.object(export, "log"):
            self.store(Path(tmp), timedelta(hours=1))
            sources = export.Sources(Path(tmp))
            self.assertEqual(sources.get("skill_tree", "https://example.invalid/x", ".json", lambda b: None),
                             b'{"rows": 1}')
            self.assertIn("https://example.invalid/x (fetched ", sources.describe("skill_tree"))

    def test_offline_uses_an_old_reply_and_refuses_a_missing_one(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(export.urllib.request, "urlopen", side_effect=AssertionError("no network")), \
                mock.patch.object(export, "log"):
            self.store(Path(tmp), timedelta(days=30))
            sources = export.Sources(Path(tmp), offline=True)
            self.assertEqual(sources.get("skill_tree", "https://example.invalid/x", ".json", lambda b: None),
                             b'{"rows": 1}')
            with self.assertRaises(SystemExit):
                sources.get("set_summary", "https://example.invalid/y", ".json", lambda b: None)

    def test_refused_request_stops_the_run_and_stores_nothing(self):
        refusal = export.urllib.error.HTTPError("https://example.invalid/x", 403, "Forbidden", {}, None)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(export.urllib.request, "urlopen", side_effect=refusal) as urlopen, \
                mock.patch.object(export, "log"):
            sources = export.Sources(Path(tmp))
            with self.assertRaises(SystemExit) as stopped:
                sources.get("skill_tree", "https://example.invalid/x", ".json", lambda b: None)
            self.assertIn("HTTP 403", str(stopped.exception))
            self.assertIn("Not retrying", str(stopped.exception))
            self.assertEqual(urlopen.call_count, 1)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
