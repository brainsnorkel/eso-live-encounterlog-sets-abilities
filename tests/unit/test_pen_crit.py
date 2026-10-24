#!/usr/bin/env python3
"""Penetration and critical damage (issue #37): a player's own sources from
their PLAYER_INFO line, the fight's debuffs and buffs weighed by damage the
way Combat Metrics weighs them, the caps, the assumed Champion Point rows,
the build window's sections, and the set table's generator."""

import importlib.util
import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from build_session import SESSION, fights

import pen_crit
from eso_sets import ESOSubclassAnalyzer

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Item ids the stub tables know
KINDS = {"201": "axe", "202": "mace", "203": "maul", "204": "battle_axe",
         "205": "inferno_staff", "206": "dagger", "207": "sword"}
WEIGHTS = {"101": "light", "102": "medium", "103": "heavy"}
SETS = {
    "286": {"name": "Spriggan's Thorns", "bonuses": [{"pieces": 5, "pen": 3460}]},
    "694": {"name": "Velothi Ur-Mage's Amulet",
            "bonuses": [{"pieces": 1, "pen": 1650}, {"pieces": 1, "gives": ["Minor Force"]}]},
    "640": {"name": "Order's Wrath", "bonuses": [{"pieces": 5, "crit": 8}]},
    "586": {"name": "Sul-Xan's Torment",
            "bonuses": [{"pieces": 5, "crit_up_to": 12, "when": "Touching the soul"}]},
    "232": {"name": "Roar of Alkosh", "bonuses": [{"pieces": 5, "provides": ["Roar of Alkosh"]}]},
}
ARMOR = ("HEAD", "SHOULDERS", "CHEST", "HAND", "WAIST", "LEGS", "FEET")


def _item(slot, item_id, trait="ARMOR_DIVINES", set_id="0", enchant="MAGICKA"):
    return [slot, str(item_id), "T", "16", trait, "LEGENDARY", str(set_id), enchant, "T", "16", "LEGENDARY"]


def _armor(weight_id="102", set_id="0", pieces=7, trait="ARMOR_DIVINES"):
    return {slot: _item(slot, weight_id, trait, set_id) for slot in ARMOR[:pieces]}


def _rows(gear, effects, front=(), back=(), sets=None):
    return pen_crit.player_rows(gear, effects, front, back, set_table=SETS if sets is None else sets,
                                weight_of=lambda i: WEIGHTS.get(i, ""), kind_of=lambda i: KINDS.get(i, ""))


def _by_name(result, name):
    return next(r for r in result["rows"] if r["name"] == name)


class TestPlayerRows(unittest.TestCase):

    def test_light_armor_concentration_counts_the_pieces(self):
        gear = _armor("101", pieces=5)
        gear.update({slot: _item(slot, "102") for slot in ARMOR[5:]})
        result = _rows(gear, {"45562"})
        row = _by_name(result, "Concentration")
        self.assertEqual(row["pen"], [4695, 4695])
        self.assertIn("5 light pieces", row["note"])
        self.assertEqual(result["static_pen"], [4695, 4695])
        self.assertEqual(result["weights"], {"light": 5, "medium": 2, "heavy": 0})

    def test_medium_armor_and_khajiit_passives_add_crit(self):
        result = _rows(_armor("102", pieces=6), {"45564", "45301"})
        self.assertEqual(_by_name(result, "Dexterity")["crit"], [12.0, 12.0])
        self.assertEqual(_by_name(result, "Feline Ambush")["crit"], [12, 12])
        self.assertEqual(result["static_crit"], [24.0, 24.0])

    def test_a_lower_rank_id_carries_its_own_value_and_the_higher_wins(self):
        gear = _armor("101", pieces=5)
        self.assertEqual(_by_name(_rows(gear, {"29667"}), "Concentration")["pen"], [2345, 2345])
        self.assertEqual(_by_name(_rows(gear, {"29667", "45562"}), "Concentration")["pen"], [4695, 4695])

    def test_weapon_passives_count_axes_and_maces_per_bar(self):
        gear = {"MAIN_HAND": _item("MAIN_HAND", "201", "WEAPON_INFUSED"),
                "OFF_HAND": _item("OFF_HAND", "202", "WEAPON_INFUSED"),
                "BACKUP_MAIN": _item("BACKUP_MAIN", "203", "WEAPON_INFUSED")}
        result = _rows(gear, {"45482", "45430"})
        twin = _by_name(result, "Twin Blade and Blunt")
        self.assertEqual(twin["crit"], [6, 0])
        self.assertEqual(twin["pen"], [1487, 0])
        heavy = _by_name(result, "Heavy Weapons")
        self.assertEqual(heavy["pen"], [0, 2974])
        self.assertIsNone(heavy["crit"])  # a maul, not a battle axe
        self.assertEqual(result["static_pen"], [1487, 2974])

    def test_mundus_scales_with_divines_as_the_spreadsheet_rounds(self):
        gear = _armor("102", pieces=7)
        # 2744 + floor(0.09085 * 2744 * 7) = 2744 + 1745
        self.assertEqual(_by_name(_rows(gear, {"13981"}), "The Lover")["pen"], [4489, 4489])
        self.assertEqual(_by_name(_rows(gear, {"13984"}), "The Shadow")["crit"], [17, 17])
        bare = _armor("102", pieces=7, trait="ARMOR_INFUSED")
        self.assertEqual(_by_name(_rows(bare, {"13981"}), "The Lover")["pen"], [2744, 2744])

    def test_slotted_abilities_count_per_bar(self):
        animal = ESOSubclassAnalyzer.SKILL_LINE_ABILITIES["Animal Companions"]
        herald = ESOSubclassAnalyzer.SKILL_LINE_ABILITIES["Herald of the Tome"]
        result = _rows({}, {"86069", "184887"}, front=animal[:3] + herald[:2], back=animal[:1])
        self.assertEqual(_by_name(result, "Advanced Species")["crit"], [15, 5])
        self.assertEqual(_by_name(result, "Splintered Secrets")["pen"], [2480, 0])

    def test_conditional_and_measured_rows_are_listed_but_not_totaled(self):
        result = _rows({}, {"116194", "184847", "45060"})
        self.assertEqual(_by_name(result, "Dismember")["when"], "while a Grave Lord ability is active")
        self.assertEqual(_by_name(result, "Fated Fortune")["measured"], "194875")
        self.assertEqual(result["static_pen"], [0, 0])
        self.assertEqual(result["static_crit"], [10.0, 10.0])

    def test_above_and_beyond_raises_the_cap(self):
        result = _rows({}, {"263605"})
        self.assertEqual(_by_name(result, "Above and Beyond")["crit"], [25, 25])
        self.assertEqual(result["crit_cap"], 155)
        self.assertEqual(_rows({}, set())["crit_cap"], 125)

    def test_sets_apply_at_their_piece_counts_per_bar(self):
        gear = _armor("102", "286", pieces=5)
        gear.update({slot: _item(slot, "102", "ARMOR_DIVINES", "640") for slot in ARMOR[5:]})
        gear["RING1"] = _item("RING1", "300", "JEWELRY_BLOODTHIRSTY", "640")
        gear["RING2"] = _item("RING2", "301", "JEWELRY_BLOODTHIRSTY", "586")
        gear["NECK"] = _item("NECK", "302", "JEWELRY_BLOODTHIRSTY", "694")
        gear["MAIN_HAND"] = _item("MAIN_HAND", "206", "WEAPON_PRECISE", "586")
        gear["OFF_HAND"] = _item("OFF_HAND", "206", "WEAPON_PRECISE", "586")
        gear["BACKUP_MAIN"] = _item("BACKUP_MAIN", "205", "WEAPON_INFUSED", "640")  # two-handed: 2 pieces
        result = _rows(gear, set())
        self.assertEqual(_by_name(result, "Spriggan's Thorns 5 pieces")["pen"], [3460, 3460])
        self.assertEqual(_by_name(result, "Order's Wrath 5 pieces")["crit"], [0, 8])
        self.assertEqual(_by_name(result, "Velothi Ur-Mage's Amulet 1 piece")["pen"], [1650, 1650])
        self.assertEqual(result["gives"], {"Minor Force": "Velothi Ur-Mage's Amulet"})
        gives = [r for r in result["rows"] if r["note"].startswith("gives")]
        self.assertEqual(len(gives), 1)
        self.assertEqual(gives[0]["crit"], [0, 0])  # a reason row, nothing to add
        self.assertEqual(result["static_pen"], [5110, 5110])
        self.assertEqual(result["static_crit"], [0.0, 8.0])
        # Sul-Xan's three pieces: no row at all; make it five and it is conditional
        self.assertFalse([r for r in result["rows"] if r["name"].startswith("Sul-Xan")])
        gear["RING1"] = _item("RING1", "300", "JEWELRY_BLOODTHIRSTY", "586")
        gear["LEGS"] = _item("LEGS", "102", "ARMOR_DIVINES", "586")
        gear["BACKUP_MAIN"] = _item("BACKUP_MAIN", "205", "WEAPON_INFUSED", "586")
        result = _rows(gear, set())
        sul = _by_name(result, "Sul-Xan's Torment 5 pieces")
        self.assertEqual(sul["crit"], [12, 12])
        self.assertEqual(sul["when"], "Touching the soul")
        self.assertEqual(result["static_crit"], [0.0, 0.0])

    def test_sharpened_weapons_per_bar(self):
        gear = {"MAIN_HAND": _item("MAIN_HAND", "205", "WEAPON_SHARPENED"),
                "BACKUP_MAIN": _item("BACKUP_MAIN", "206", "WEAPON_SHARPENED"),
                "BACKUP_OFF": _item("BACKUP_OFF", "206", "WEAPON_PRECISE")}
        result = _rows(gear, set())
        pens = sorted(r["pen"] for r in result["rows"] if r["name"] == "Sharpened")
        self.assertEqual(pens, [[0, 819], [1638, 0]])

    def test_a_player_without_a_build_gets_empty_figures(self):
        result = _rows({}, set())
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["static_pen"], [0, 0])


class TestCasters(unittest.TestCase):

    def test_crusher_glyph_values(self):
        gear = {"BACKUP_MAIN": _item("BACKUP_MAIN", "205", "WEAPON_INFUSED", "0", "REDUCE_ARMOR")}
        glyph = pen_crit.crusher_weapons(gear, kind_of=lambda i: KINDS.get(i, ""))[0]
        self.assertEqual(glyph["value"], 2108)
        self.assertEqual(glyph["label"], "Infused Inferno Staff (back bar)")
        gear["BACKUP_MAIN"][4] = "WEAPON_CHARGED"
        self.assertEqual(pen_crit.crusher_weapons(gear, kind_of=lambda i: KINDS.get(i, ""))[0]["value"], 1622)
        gear["BACKUP_MAIN"][4] = "WEAPON_INFUSED"
        gear.update(_armor("103", pen_crit.TORUGS_PACT_SET_ID, pieces=5))
        glyph = pen_crit.crusher_weapons(gear, kind_of=lambda i: KINDS.get(i, ""))[0]
        self.assertEqual(glyph["value"], 3056)
        self.assertIn("Torug's Pact", glyph["label"])

    def test_caster_source_names_the_glyph_or_the_set(self):
        crusher = {"MAIN_HAND": _item("MAIN_HAND", "205", "WEAPON_INFUSED", "0", "REDUCE_ARMOR")}
        self.assertEqual(pen_crit.caster_source(crusher, "Crusher", SETS, lambda i: KINDS.get(i, "")),
                         ("Infused Inferno Staff (front bar)", 2108))
        alkosh = _armor("103", "232", pieces=5)
        self.assertEqual(pen_crit.caster_source(alkosh, "Roar of Alkosh", SETS), ("Roar of Alkosh", None))
        self.assertEqual(pen_crit.caster_source(alkosh, "Major Breach", SETS), ("", None))
        self.assertEqual(pen_crit.caster_source({}, "Crusher", SETS), ("", None))


class TestCapsAndAssumptions(unittest.TestCase):

    def test_pen_cap_by_zone_and_setting(self):
        self.assertEqual(pen_crit.pen_cap(True), 18200)
        self.assertEqual(pen_crit.pen_cap(False), 9100)
        self.assertEqual(pen_crit.pen_cap(False, 18200), 18200)
        self.assertEqual(pen_crit.pen_cap(True, "9100"), 9100)
        self.assertEqual(pen_crit.pen_cap(True, "auto"), 18200)

    def test_assumed_rows_follow_the_options_and_the_zone(self):
        options = {"piercing": True, "fighting_finesse": True, "backstabber": True}
        names = [r["name"] for r in pen_crit.assumed_rows(options, instanced=True)]
        self.assertEqual(names, ["Piercing", "Fighting Finesse", "Backstabber"])
        self.assertTrue(all(r["kind"] == "assumed" for r in pen_crit.assumed_rows(options, True)))
        names = [r["name"] for r in pen_crit.assumed_rows(options, instanced=False)]
        self.assertEqual(names, ["Piercing", "Backstabber"])
        self.assertEqual(pen_crit.assumed_rows({}, True), [])
        self.assertEqual(pen_crit.assumed_rows(None, True), [])


class TestEffective(unittest.TestCase):

    def test_effective_penetration_caps_each_second(self):
        hist = [[5948, 0.0, 50], [0, 0.0, 50]]
        out = pen_crit.effective_pen(hist, 14000, 18200)
        self.assertAlmostEqual(out["effective"], 16100)
        self.assertAlmostEqual(out["average"], 16974)
        self.assertAlmostEqual(out["over_pct"], 50)
        self.assertEqual(out["damage"], 100)

    def test_force_of_nature_adds_per_status_effect(self):
        out = pen_crit.effective_pen([[0, 2.0, 100]], 0, 18200, per_status=660)
        self.assertAlmostEqual(out["effective"], 1320)
        self.assertAlmostEqual(out["status"], 2.0)
        self.assertEqual(pen_crit.effective_pen([], 1000, 18200)["effective"], None)

    def test_effective_crit(self):
        self.assertAlmostEqual(pen_crit.effective_crit([[30, 100]], 80, 125)["effective"], 110)
        over = pen_crit.effective_crit([[80, 100]], 50, 125)
        self.assertAlmostEqual(over["effective"], 125)
        self.assertAlmostEqual(over["over_pct"], 100)


def _player_state(unit_id):
    return f"{unit_id},20000/20000,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _unit_state(unit_id):
    return f"{unit_id},105634/105634,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _effect(ts, change, ability, source, target=None):
    return f"{ts},EFFECT_CHANGED,{change},1,900,{ability},{source},{target if target is not None else '*'}"


class TestFightFields(unittest.TestCase):
    """The group part through a tracker fed by hand."""

    def test_histograms_and_rows(self):
        tracker = pen_crit.new_tracker()
        start, end = 9990, 70000
        tracker.record("GAINED", "61743", "70", 1, 10000, "boss", source_id="2")
        tracker.record("FADED", "61743", "70", 1, 40000, "boss", source_id="2")
        tracker.record("GAINED", "18084", "70", 1, 10000, "boss", source_id="1")  # Burning
        tracker.record("GAINED", "61747", "1", 1, 9990, "group", source_id="3")  # Major Force on 1
        units = {"1": ("group", None, None), "2": ("group", None, None), "3": ("self", None, None),
                 "70": ("boss", 2500, None)}
        group_buckets = {"70": {10: 1000, 20: 1000, 50: 1000}}
        player_buckets = {"1": {"70": {10: 1000, 50: 500}}, "2": {"70": {20: 1000}}, "3": {}}
        names = {"1": "@one", "2": "@two", "3": "@three"}
        entry, players = pen_crit.fight_fields(
            tracker, start, end, units, group_buckets, player_buckets,
            lambda uid: names.get(uid, uid), lambda uid: {}, instanced=True, set_table=SETS)
        self.assertEqual(entry["on"], "boss")
        self.assertEqual(entry["cap"], 18200)
        self.assertEqual(entry["pen_hist"], [[0, 1.0, 1000], [5948, 1.0, 2000]])
        self.assertEqual(entry["crit_hist"], [[0, 3000]])
        self.assertEqual(entry["damage"], 3000)
        breach = entry["debuffs"][0]
        self.assertEqual(breach["name"], "Major Breach")
        self.assertEqual(breach["pen"], 5948)
        self.assertEqual(breach["uptime_pct"], 50)
        self.assertEqual(breach["casters"], [{"name": "@two", "pct": 50, "via": "", "value": None}])
        one = players["1"]
        self.assertEqual(one["pen_hist"], [[0, 1.0, 500], [5948, 1.0, 1000]])
        self.assertEqual(one["crit_hist"], [[20, 1500]])
        self.assertEqual(one["buffs"], [{"name": "Major Force", "crit": 20, "uptime_pct": 100}])
        self.assertEqual(players["2"]["crit_hist"], [[0, 1000]])
        self.assertEqual(players["3"]["damage"], 0)

    def test_crusher_is_valued_by_the_casters_glyph(self):
        tracker = pen_crit.new_tracker()
        tracker.record("GAINED", "17906", "70", 1, 10000, "boss", source_id="2")
        units = {"2": ("group", None, None), "70": ("boss", None, None)}
        gear = {"2": {"BACKUP_MAIN": _item("BACKUP_MAIN", "205", "WEAPON_INFUSED", "0", "REDUCE_ARMOR")}}
        entry, _players = pen_crit.fight_fields(
            tracker, 9990, 20000, units, {"70": {15: 100}}, {}, lambda u: u,
            lambda u: gear.get(u, {}), instanced=True, set_table=SETS,
            kind_of=lambda i: KINDS.get(i, ""))
        row = entry["debuffs"][0]
        self.assertEqual(row["pen"], 2108)
        self.assertEqual(row["casters"][0]["via"], "Infused Inferno Staff (back bar)")
        self.assertEqual(entry["pen_hist"], [[2108, 0.0, 100]])

    def test_a_buff_a_set_gives_at_all_times_counts_for_the_whole_fight(self):
        tracker = pen_crit.new_tracker()
        tracker.record("GAINED", "61746", "1", 1, 15000, "group", source_id="1")  # a Barbed Trap's
        tracker.record("FADED", "61746", "1", 1, 16000, "group", source_id="1")
        units = {"1": ("group", None, None), "2": ("group", None, None), "70": ("boss", None, None)}
        buckets = {"1": {"70": {12: 100, 18: 100}}, "2": {"70": {12: 100}}}
        _entry, players = pen_crit.fight_fields(
            tracker, 9990, 20000, units, {"70": {12: 200, 18: 100}}, buckets, lambda u: u,
            lambda u: {}, instanced=True, set_table=SETS,
            always_on={"1": {"Minor Force": "Velothi Ur-Mage's Amulet"}})
        one = players["1"]
        self.assertEqual(one["buffs"], [{"name": "Minor Force", "crit": 10, "uptime_pct": 100,
                                         "via": "Velothi Ur-Mage's Amulet at all times"}])
        self.assertEqual(one["crit_hist"], [[10, 200]])
        two = players["2"]
        self.assertEqual(two["buffs"], [])
        self.assertEqual(two["crit_hist"], [[0, 100]])

    def test_a_targets_permanent_debuffs_count_in_full(self):
        tracker = pen_crit.new_tracker()
        # The log shows one player's Major Breach on the dummy for a while:
        # it adds nothing to a debuff the dummy keeps for good
        tracker.record("GAINED", "61743", "70", 1, 10000, "boss", source_id="1")
        tracker.record("FADED", "61743", "70", 1, 12000, "boss", source_id="1")
        units = {"1": ("self", None, None), "70": ("boss", None, None)}
        entry, _players = pen_crit.fight_fields(
            tracker, 9990, 20000, units, {"70": {11: 100, 15: 100}}, {}, lambda u: "the dummy",
            lambda u: {}, instanced=False, dummy=True, set_table=SETS,
            permanent_debuffs={"70": list(pen_crit.TRIAL_DUMMY_DEBUFFS)})
        rows = {d["name"]: d for d in entry["debuffs"]}
        self.assertEqual(sorted(rows), sorted(pen_crit.TRIAL_DUMMY_DEBUFFS))
        self.assertEqual(rows["Major Breach"]["uptime_pct"], 100)
        self.assertEqual(rows["Major Breach"]["casters"],
                         [{"name": "the dummy", "pct": 100, "via": "the dummy's own", "value": 5948}])
        self.assertEqual(rows["Crusher"]["pen"], 2108)
        self.assertEqual(rows["Elemental Catalyst"]["crit"], 15)
        self.assertEqual(entry["pen_hist"], [[17030, 0.0, 200]])  # 5948 + 2974 + 2108 + 6000
        self.assertEqual(entry["crit_hist"], [[25, 200]])  # Minor Brittle 10 + Elemental Catalyst 15
        self.assertEqual(entry["cap"], 18200)

    def test_a_trash_fight_measures_every_hostile_hit(self):
        tracker = pen_crit.new_tracker()
        tracker.record("GAINED", "61742", "80", 1, 10000, "enemy", source_id="1")
        units = {"1": ("self", None, None), "80": ("enemy", None, None), "81": ("enemy", None, None)}
        entry, _players = pen_crit.fight_fields(
            tracker, 9990, 20000, units, {"80": {12: 100}, "81": {12: 300}}, {}, lambda u: u,
            lambda u: {}, instanced=False)
        self.assertEqual(entry["on"], "enemies")
        self.assertEqual(entry["cap"], 9100)
        self.assertEqual(entry["pen_hist"], [[0, 0.0, 300], [2974, 0.0, 100]])


class TestEngine(unittest.TestCase):
    """The fields on a fight entry, through the whole engine."""

    def test_entry_and_player_fields(self):
        lines = list(SESSION)
        extra = [_effect(10000, "GAINED", 61743, _player_state(2), _unit_state(70)),
                 _effect(40000, "FADED", 61743, _player_state(2), _unit_state(70)),
                 _effect(9995, "GAINED", 61747, _player_state(3), _player_state(1))]
        # Keep the log in time order: the effects go in after BEGIN_COMBAT
        begin = next(i for i, line in enumerate(lines) if line.endswith("BEGIN_COMBAT"))
        lines[begin + 1:begin + 1] = extra
        entry = fights(lines)[0]
        self.assertEqual(entry.pen_crit["on"], "enemies")  # the fixture's boss carries no boss flag
        self.assertTrue(entry.pen_crit["instanced"])  # VETERAN zone
        self.assertFalse(entry.pen_crit["dummy"])
        breach = entry.pen_crit["debuffs"][0]
        self.assertEqual((breach["name"], breach["uptime_pct"]), ("Major Breach", 50))
        self.assertEqual(breach["casters"][0]["name"], "@dualwield")
        players = {p["name"]: p["pen_crit"] for p in entry.players}
        self.assertEqual(players["@brainsnorkel"]["pen_hist"], [[5948, 0.0, 90000]])  # hit at 11 s
        self.assertEqual(players["@brainsnorkel"]["crit_hist"], [[20, 90000]])  # Major Force on 1
        self.assertEqual(players["@brainsnorkel"]["buffs"][0]["name"], "Major Force")
        self.assertEqual(players["@dualwield"]["pen_hist"], [[5948, 0.0, 60000]])  # hit at 21 s
        self.assertEqual(players["@dualwield"]["crit_hist"], [[0, 60000]])
        self.assertEqual(players["anon"]["pen_hist"], [[5948, 0.0, 30000]])  # hit at 31 s, still up
        self.assertEqual(players["anon"]["crit_hist"], [[0, 30000]])  # no Major Force on 3
        self.assertEqual(_by_name(players["@brainsnorkel"], "Aerie's Cry 2 pieces")["pen"], [1487, 1487])

    def test_a_buff_listed_on_the_player_info_line_counts_from_combat_start(self):
        # Lucent Echoes is on @dualwield as combat starts (its id is in their
        # PLAYER_INFO list) and no GAINED line is ever written for it
        lines = [line.replace("PLAYER_INFO,2,[84732,84733,84731,13975],[1,1,1,1]",
                              "PLAYER_INFO,2,[84732,84733,84731,13975,220015],[1,1,1,1,1]")
                 for line in SESSION]
        self.assertNotEqual(lines, list(SESSION))
        entry = fights(lines)[0]
        players = {p["name"]: p["pen_crit"] for p in entry.players}
        self.assertEqual(players["@dualwield"]["buffs"],
                         [{"name": "Lucent Echoes", "crit": 11, "uptime_pct": 100}])
        self.assertEqual(players["@dualwield"]["crit_hist"], [[11, 60000]])
        self.assertEqual(players["@brainsnorkel"]["buffs"], [])

    def test_the_trial_dummy_is_known_by_name(self):
        lines = [line.replace('"Scalecaller Peak",VETERAN', '"Elinhir Private Arena",NONE')
                 .replace('"Test Boss"', f'"{pen_crit.TRIAL_DUMMY_NAME}"') for line in SESSION]
        entry = fights(lines)[0]
        self.assertTrue(entry.pen_crit["dummy"])
        self.assertTrue(entry.pen_crit["instanced"])
        self.assertEqual(entry.pen_crit["cap"], 18200)
        rows = {d["name"]: d for d in entry.pen_crit["debuffs"]}
        self.assertEqual(sorted(rows), sorted(pen_crit.TRIAL_DUMMY_DEBUFFS))
        self.assertTrue(all(d["uptime_pct"] == 100 for d in rows.values()))
        self.assertEqual(rows["Roar of Alkosh"]["casters"][0]["via"], "the dummy's own")
        players = {p["name"]: p["pen_crit"] for p in entry.players}
        self.assertEqual(players["@brainsnorkel"]["pen_hist"], [[17030, 0.0, 90000]])
        self.assertEqual(players["@brainsnorkel"]["crit_hist"], [[25, 90000]])

    def test_a_trial_dummys_debuffs_make_a_house_zone_instanced(self):
        lines = [line.replace('"Scalecaller Peak",VETERAN', '"Elinhir Private Arena",NONE') for line in SESSION]
        begin = next(i for i, line in enumerate(lines) if line.endswith("BEGIN_COMBAT"))
        lines.insert(begin + 1, _effect(9995, "GAINED", 120007, _unit_state(70)))
        entry = fights(lines)[0]
        self.assertTrue(entry.pen_crit["dummy"])
        self.assertTrue(entry.pen_crit["instanced"])
        self.assertEqual(entry.pen_crit["cap"], 18200)
        plain = fights([line.replace('"Scalecaller Peak",VETERAN', '"Reaper\'s March",NONE')
                        for line in SESSION])[0]
        self.assertFalse(plain.pen_crit["instanced"])
        self.assertEqual(plain.pen_crit["cap"], 9100)


class TestRender(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.entry = fights()[0]

    def _html(self, options, dark=False, unit="1"):
        from gui.build_render import render_build_html
        return render_build_html(self.entry, unit, dark=dark, pen_crit_options=options)

    def test_sections_with_assumed_rows(self):
        options = {"piercing": True, "fighting_finesse": True, "backstabber": False,
                   "force_of_nature": True, "force_of_nature_per_effect": 660, "cap": "auto"}
        for dark in (False, True):
            html = self._html(options, dark)
            self.assertIn("Penetration", html)
            self.assertIn("Critical damage", html)
            self.assertIn("Piercing", html)
            self.assertIn("Fighting Finesse", html)
            self.assertNotIn("Backstabber", html)
            self.assertIn("Force of Nature", html)
            self.assertIn("(assumed)", html)
            self.assertIn("cap 18,200", html)
            self.assertIn("Own 2,187", html)  # Aerie's Cry 1,487 + Piercing 700
            self.assertIn("Own 58%", html)  # 50 base + Fighting Finesse
            self.assertIn("Effective", html)
            self.assertIn("skinnycheeks.gg", html)

    def test_nothing_assumed_without_options(self):
        html = self._html(None)
        self.assertNotIn("(assumed)", html)
        self.assertIn("Own 1,487", html)
        self.assertIn("Own 50%", html)

    def test_cap_setting_overrides_the_zone(self):
        self.assertIn("cap 9,100", self._html({"cap": 9100}))

    def test_an_old_entry_without_the_fields_renders(self):
        import copy
        entry = copy.deepcopy(self.entry)
        entry.pen_crit = None
        for p in entry.players:
            p.pop("pen_crit", None)
        from gui.build_render import render_build_html
        html = render_build_html(entry, "1", pen_crit_options={"piercing": True})
        self.assertNotIn("Penetration", html)


def _load(script: str):
    path = REPO_ROOT / "scripts" / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSetOffenseGenerator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.gen = _load("generate_set_offense.py")

    def classify(self, pieces, text, name="A Set"):
        return self.gen.classify_bonus(pieces, text, name)

    def test_flat_lines(self):
        self.assertEqual(self.classify(2, "Adds 34-1487 Offensive Penetration"), {"pieces": 2, "pen": 1487})
        self.assertEqual(self.classify(5, "Gain 100000 Offensive Penetration. Reduce your damage done by 46%."),
                         {"pieces": 5, "pen": 100000})
        self.assertEqual(self.classify(5, "Increases your Critical Damage and Critical Healing by 8%."),
                         {"pieces": 5, "crit": 8})
        self.assertEqual(self.classify(1, "Increases your damage done by 16% but decreases your Critical Damage done by 50%."),
                         {"pieces": 1, "crit": -50})
        titan = self.classify(5, "Adds 2-110 Weapon and Spell Damage and 28-1240 Offensive Penetration. "
                                 "While in combat, this bonus doubles when you are under 75% Health.")
        self.assertEqual((titan["pen"], "doubles" in titan["note"]), (1240, True))

    def test_conditional_lines_are_up_to(self):
        stuhn = self.classify(5, "When you deal damage to an enemy who is Off Balance, your Offensive "
                                 "Penetration is increased by 123-5312 for 10 seconds.")
        self.assertEqual(stuhn["pen_up_to"], 5312)
        self.assertNotIn("pen", stuhn)
        oak = self.classify(5, "Gain 553 Offensive Penetration against enemies for each Major Buff they have active.")
        self.assertEqual(oak["pen_up_to"], 553)
        mora = self.classify(5, "Increase your Critical Damage done by 1% for every Minor Buff active on you, "
                                "up to 12 Critical Damage done.")
        self.assertEqual(mora["crit_up_to"], 12)

    def test_buffs_given_and_provided(self):
        self.assertEqual(self.classify(5, "Gain Minor Force at all times, increasing your Critical Damage by 10%."),
                         {"pieces": 5, "gives": ["Minor Force"]})
        gryphon = self.classify(5, "After dealing direct damage, you gain Minor Force and Minor Expedition "
                                   "for 10 seconds, increasing your Critical Damage done by 10%.")
        self.assertEqual(gryphon["gives_when"], ["Minor Force"])
        self.assertNotIn("gives", gryphon)
        self.assertNotIn("crit_up_to", gryphon)
        self.assertTrue(gryphon["when"].startswith("After dealing"))
        self.assertEqual(self.classify(5, "When you deal Critical Damage you apply Major Breach to the enemy, "
                                          "reducing their Physical and Spell Resistance by 5948 for 4 seconds.",
                                       "Night Mother's Gaze"),
                         {"pieces": 5, "provides": ["Major Breach"]})
        alkosh = self.classify(5, "When you activate a synergy, you send a shockwave that deals 318 Physical "
                                  "Damage. Reduces the Physical and Spell Resistance of any enemy hit by the "
                                  "amount of your Weapon Damage for the duration, up to a maximum of 6000.",
                               "Roar of Alkosh")
        self.assertEqual(alkosh, {"pieces": 5, "provides": ["Roar of Alkosh"]})
        self.assertEqual(self.classify(5, "Increases your damage done against enemies afflicted with Minor Brittle by 2%."), {})
        self.assertEqual(self.classify(2, "Adds 28-1206 Maximum Health"), {})

    def test_committed_table(self):
        path = REPO_ROOT / "data" / "sets" / "offense.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("CC-BY-SA", data["attribution"])
        sets = data["sets"]
        self.assertEqual(sets["286"]["bonuses"], [{"pieces": 5, "pen": 3460}])
        self.assertEqual(sets["694"]["bonuses"][0], {"pieces": 1, "pen": 1650})
        self.assertEqual(sets["694"]["bonuses"][1], {"pieces": 1, "gives": ["Minor Force"]})
        self.assertEqual(sets["430"]["bonuses"][1]["gives_when"], ["Minor Force"])  # Tzogvin's at ten stacks
        self.assertEqual(sets["658"]["bonuses"], [{"pieces": 1, "gives": ["Minor Force"]}])  # Oakensoul
        self.assertEqual(sets["640"]["bonuses"], [{"pieces": 5, "crit": 8}])
        self.assertEqual(sets["232"]["bonuses"], [{"pieces": 5, "provides": ["Roar of Alkosh"]}])
        self.assertEqual(sets["51"]["bonuses"], [{"pieces": 5, "provides": ["Major Breach"]}])
        self.assertEqual(sets["266"]["bonuses"], [{"pieces": 1, "pen": 1487}])  # Kra'gh
        self.assertEqual(sets["520"]["bonuses"], [{"pieces": 1, "crit": -50}])  # Malacath
        flat = [b["pen"] for s in sets.values() for b in s["bonuses"] if "pen" in b]
        self.assertGreater(flat.count(1487), 50)
        self.assertEqual(pen_crit.set_offense_table()["286"]["name"], "Spriggan's Thorns")


CAP_PLAYER = {"static_pen": [1000, 1000], "static_crit": [10.0, 10.0], "crit_cap": 125,
              "pen_hist": [[5948, 0.0, 100], [0, 0.0, 100]], "crit_hist": [[30, 100], [0, 100]]}
CAP_FIGHT = {"instanced": True, "cap": 18200}
CAP_OPTIONS = {"piercing": True, "fighting_finesse": True, "backstabber": False}


class TestCapShares(unittest.TestCase):

    def test_shares_of_each_cap(self):
        shares = pen_crit.cap_shares(CAP_PLAYER, CAP_FIGHT, CAP_OPTIONS)
        # pen: (1000 + 700 + 5948) * 100 + 1700 * 100 over 200 = 4674 of 18200
        self.assertEqual(shares["pen_pct"], 26)
        self.assertAlmostEqual(shares["pen"], 4674)
        self.assertEqual(shares["pen_cap"], 18200)
        # crit: 50 + 10 + 8 = 68 own; (98 + 68) / 2 = 83 of 125
        self.assertEqual(shares["crit_pct"], 66)
        self.assertAlmostEqual(shares["crit"], 83)
        self.assertEqual(shares["crit_cap"], 125)
        self.assertEqual(shares["pen_over_pct"], 0)

    def test_without_options_nothing_is_assumed(self):
        shares = pen_crit.cap_shares(CAP_PLAYER, CAP_FIGHT, None)
        self.assertAlmostEqual(shares["pen"], 3974)
        self.assertAlmostEqual(shares["crit"], 75)

    def test_capped_seconds_never_pass_the_cap(self):
        player = dict(CAP_PLAYER, static_pen=[20000, 20000], static_crit=[90.0, 90.0])
        shares = pen_crit.cap_shares(player, CAP_FIGHT, None)
        self.assertEqual((shares["pen_pct"], shares["crit_pct"]), (100, 100))
        self.assertEqual(shares["pen_over_pct"], 100)

    def test_nothing_to_weigh(self):
        self.assertIsNone(pen_crit.cap_shares(dict(CAP_PLAYER, pen_hist=[], crit_hist=[]), CAP_FIGHT, None))
        self.assertIsNone(pen_crit.cap_shares(None, None, None))
        self.assertIsNone(pen_crit.cap_shares({}, {}, {"piercing": True}))


ROW_OPTIONS = {"piercing": True, "fighting_finesse": True}


class TestRowToken(unittest.TestCase):
    """The 'pen 99% · crit 94%' token on a player's row (fight_render)."""

    @classmethod
    def setUpClass(cls):
        cls.entry = fights()[0]

    def test_token_in_both_views_and_the_copy(self):
        from gui.fight_render import pen_crit_href, render_html, render_plain_text
        for detailed in (False, True):
            html = render_html(self.entry, detailed=detailed, pen_crit_options=ROW_OPTIONS)
            # @brainsnorkel: Aerie's Cry 1,487 + Piercing 700; 50 + Fighting Finesse 8
            self.assertIn(f'<a href="{pen_crit_href("1")}" style="text-decoration:none;color:#5f6368">'
                          'p:2187 cd:58%</a>', html)
            self.assertIn(pen_crit_href("2"), html)
        text = render_plain_text(self.entry, pen_crit_options=ROW_OPTIONS)
        self.assertIn("@brainsnorkel * Warden — 90.0k (50.0%) · p:2187 cd:58%", text)
        plain = render_plain_text(self.entry)
        self.assertIn("· p:1487 cd:50%", plain)  # nothing assumed: 1,487 and the base 50

    def test_no_token_without_figures(self):
        import copy

        from gui.fight_render import PEN_CRIT_HREF, render_html, render_plain_text
        entry = copy.deepcopy(self.entry)
        for p in entry.players:
            p.pop("pen_crit", None)
        entry.pen_crit = None
        self.assertNotIn(PEN_CRIT_HREF, render_html(entry, detailed=False, pen_crit_options=ROW_OPTIONS))
        self.assertNotIn("p:", render_plain_text(entry, pen_crit_options=ROW_OPTIONS))
        # A player with figures but no damage has no token either
        entry = copy.deepcopy(self.entry)
        entry.players[0]["pen_crit"]["pen_hist"] = []
        entry.players[0]["pen_crit"]["crit_hist"] = []
        html = render_html(entry, detailed=False, pen_crit_options=ROW_OPTIONS)
        self.assertNotIn(f"{PEN_CRIT_HREF}1\"", html)
        self.assertIn(f"{PEN_CRIT_HREF}2\"", html)

    def test_tooltips_carry_the_figures(self):
        from gui.fight_render import pen_crit_href, pen_crit_tooltips
        tips = pen_crit_tooltips(self.entry, ROW_OPTIONS)
        self.assertEqual(set(tips), {pen_crit_href("1"), pen_crit_href("2"), pen_crit_href("3")})
        tip = tips[pen_crit_href("1")]
        self.assertIn("Effective penetration 2,187 of 18,200 (12% of the cap)", tip)
        self.assertIn("Effective critical damage 58.0% of 125% (46% of the cap)", tip)
        self.assertIn("Click for every source", tip)

    def test_a_click_asks_for_the_sections(self):
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtWidgets import QApplication
        except ImportError:
            self.skipTest("PySide6 not installed")
        QApplication.instance() or QApplication([])
        from gui.fight_render import pen_crit_href
        from gui.fight_view import FightView
        view = FightView()
        try:
            asked = []
            view.pen_crit_requested.connect(asked.append)
            view.anchorClicked.emit(QUrl(pen_crit_href("7")))
            self.assertEqual(asked, ["7"])
        finally:
            view.deleteLater()


if __name__ == "__main__":
    unittest.main()
