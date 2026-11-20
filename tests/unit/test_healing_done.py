#!/usr/bin/env python3
"""Healing done (issue #242): the receivers' healer rows turned round into
each player's heals on the others (damage_kinds.healing_done), the healing
token on a healer's row of the fight pane and in Copy fight, and the Healing
done tab's page (gui.healing_render)."""

import re
import unittest

from damage_kinds import TakenTally, healing_done
from fight_history import FightHistoryEntry
from tests.unit.test_companions import _companion, _companion_added
from tests.unit.test_gui import HAVE_QT, _ensure_app
from tests.unit.test_hits_before_line import (
    BASE,
    Engine,
    _player,
    _unit,
    boss,
    fight,
    hit,
)

HEAL_A = 70001   # a direct heal
HOT_B = 70002    # a heal over time
PET_HEAL = 70003
COMPANION_HEAL = 70004
INFOS = [
    f'2600,ABILITY_INFO,{HEAL_A},"Mending Light","/esoui/art/icons/ability_heal_001.dds",F,F',
    f'2600,ABILITY_INFO,{HOT_B},"Soothing Rain","/esoui/art/icons/ability_heal_002.dds",F,F',
    f'2600,ABILITY_INFO,{PET_HEAL},"Pet Salve","/esoui/art/icons/ability_heal_003.dds",F,F',
    f'2600,ABILITY_INFO,{COMPANION_HEAL},"Companion Balm","/esoui/art/icons/ability_heal_004.dds",F,F',
]
# A fourth player in the zone whose build never reaches the log: no row
STRANGER = '2000,UNIT_ADDED,4,PLAYER,F,4,0,F,6,3,"Stranger","@stranger",1004,50,122,0,PLAYER_ALLY,T'
PET = _unit(90, 45478, 45478)  # BASE's Blastbones, the logging player's pet


def heal(ts, source, target, value, overflow=0, result="HEAL", ability=HEAL_A):
    """*source* heals *target* (unit states) for *value*, *overflow* past
    full health."""
    return (f"{ts},COMBAT_EVENT,{result},MAGIC,1,{value},{overflow},{ts},{ability},"
            f"{source},{target}")


def _row(entry, unit_id):
    return next(p for p in entry.players if p.get("unit_id") == unit_id)


def _fight(*lines, accrue=False, before=()):
    engine = Engine(BASE + INFOS + list(before))
    engine.analyzer.companion_accrual = accrue
    return engine.feed(fight(10000, 40000, hit(11000, 1, 10000, boss(990000)), *lines)).fights[-1]


class TestTurnedRound(unittest.TestCase):
    """Through the engine, from log lines."""

    def test_a_healers_heals_on_the_others_by_ability_and_by_player(self):
        entry = _fight(
            heal(12000, _player(2), _player(1), 5000, 1000),
            heal(13000, _player(2), _player(3), 2000, 0, "HOT_TICK", HOT_B),
            # All overheal: no healing, but in the overheal and the hits
            heal(14000, _player(2), _player(1), 0, 3000, "HOT_TICK", HOT_B),
            # On themselves: their own, never healing to others
            heal(15000, _player(2), _player(2), 4000))
        p = _row(entry, "2")
        done = p["healing_done"]
        self.assertEqual(p["healing"], 7000)
        self.assertEqual((done["landed"], done["overheal"], done["hits"], done["hot"], done["direct"]),
                         (7000, 4000, 3, 2000, 5000))
        self.assertEqual([(a["name"], a["landed"], a["overheal"], a["hits"], a["via"])
                          for a in done["abilities"]],
                         [("Mending Light", 5000, 1000, 1, ""), ("Soothing Rain", 2000, 3000, 2, "")])
        self.assertEqual([(t["id"], t["landed"], t["overheal"], t["hits"]) for t in done["targets"]],
                         [("1", 5000, 4000, 2), ("3", 2000, 0, 1)])
        self.assertEqual(done["targets"][0]["name"], "@brainsnorkel")
        self.assertEqual((done["own"]["landed"], done["own"]["hits"]), (4000, 1))
        # Whoever healed nobody else has an empty view, with their own heals
        self.assertEqual(_row(entry, "3")["healing_done"]["landed"], 0)
        self.assertEqual(_row(entry, "3")["healing_done"]["targets"], [])

    def test_a_pets_heals_are_its_owners_and_its_heal_on_the_owner_their_own(self):
        entry = _fight(heal(12000, PET, _player(2), 1500, ability=PET_HEAL),
                       heal(13000, PET, _player(1), 500, ability=PET_HEAL))
        p = _row(entry, "1")
        done = p["healing_done"]
        self.assertEqual(p["healing"], 1500)
        self.assertEqual(done["landed"], 1500)
        self.assertEqual([(a["name"], a["via"]) for a in done["abilities"]], [("Pet Salve", "pet")])
        self.assertEqual(done["own"]["landed"], 500)

    def test_a_companions_heals_are_its_own_rows_unless_accrued_to_its_owner(self):
        lines = (heal(12000, _companion(95), _player(2), 2500, ability=COMPANION_HEAL),
                 heal(13000, _companion(95), _player(1), 800, ability=COMPANION_HEAL))
        before = [_companion_added(3000, 95, 1)]
        entry = _fight(*lines, before=before)
        owner = _row(entry, "1")
        self.assertEqual((owner["healing"], owner["healing_done"]["landed"]), (0, 0))
        self.assertEqual(owner["healing_done"]["own"]["landed"], 0)
        companion = next(p for p in entry.players if p.get("companion"))
        self.assertEqual(companion["healing"], 3300)  # the owner counts as another player
        # Accrued to the owner, as the row's figure is: its heal on the
        # owner is then the owner's own
        entry = _fight(*lines, before=before, accrue=True)
        owner = _row(entry, "1")
        self.assertEqual((owner["healing"], owner["healing_done"]["landed"]), (2500, 2500))
        self.assertEqual([(a["name"], a["via"]) for a in owner["healing_done"]["abilities"]],
                         [("Companion Balm", "companion")])
        self.assertEqual(owner["healing_done"]["own"]["landed"], 800)

    def test_a_player_the_table_does_not_list_is_among_the_players_healed(self):
        entry = _fight(heal(12000, _player(2), _player(4), 1000),
                       heal(13000, _player(2), _player(1), 3000), before=[STRANGER])
        self.assertNotIn("4", [p.get("unit_id") for p in entry.players])
        p = _row(entry, "2")
        self.assertEqual((p["healing"], p["healing_done"]["landed"]), (4000, 4000))
        self.assertEqual([(t["id"], t["name"], t["landed"]) for t in p["healing_done"]["targets"]],
                         [("1", "@brainsnorkel", 3000), ("4", "@stranger", 1000)])

    def test_the_landed_total_is_the_rows_figure(self):
        """The two are counted from different lines (the figure from heals
        with a hit, the view from every heal line kept for Healing
        received): they agree for every player of a mixed fight."""
        entry = _fight(
            heal(12000, _player(2), _player(1), 5000, 1000),
            heal(12500, _player(2), _player(3), 0, 2000, "HOT_TICK", HOT_B),
            heal(13000, _player(3), _player(2), 2200, 0, "CRITICAL_HEAL"),
            heal(13500, PET, _player(3), 900, ability=PET_HEAL),
            heal(14000, _player(1), _player(1), 3000),
            heal(14500, _player(2), _player(4), 1000), before=[STRANGER])
        for p in entry.players:
            self.assertEqual(p["healing_done"]["landed"], p["healing"], p["unit_id"])
            self.assertEqual(sum(a["landed"] for a in p["healing_done"]["abilities"]), p["healing"])
            self.assertEqual(sum(t["landed"] for t in p["healing_done"]["targets"]), p["healing"])


class TestHealingDoneFromTallies(unittest.TestCase):
    """damage_kinds.healing_done on tallies built by hand."""

    def _view(self, tallies, healer, record_of=None, companions=False):
        return healing_done(tallies, healer, record_of or (lambda unit: unit),
                            lambda a: f"ability {a}", lambda a: "", lambda u: f"unit {u}",
                            companions=companions)

    def test_a_pet_whose_owner_came_back_on_a_new_unit_is_still_theirs(self):
        tally = TakenTally()
        tally.note_other("HEAL", 700, 0, source_id="90", ability_id="5", pet_owner="40")
        view = self._view({"2": tally}, "1", record_of={"40": "1"}.get)
        self.assertEqual((view["landed"], view["abilities"][0]["via"]), (700, "pet"))

    def test_rows_largest_first_and_ties_by_name(self):
        tally = TakenTally()
        for ability_id, value in (("1", 100), ("2", 300), ("3", 100)):
            tally.note_other("HEAL", value, 0, source_id="7", ability_id=ability_id)
        other = TakenTally()
        other.note_other("HOT_TICK", 900, 50, source_id="7", ability_id="4")
        view = self._view({"8": tally, "9": other}, "7")
        self.assertEqual([a["id"] for a in view["abilities"]], ["4", "2", "1", "3"])
        self.assertEqual([t["id"] for t in view["targets"]], ["9", "8"])
        self.assertEqual(view["targets"][0]["name"], "unit 9")

    def test_another_healers_rows_and_a_companions_are_left_out(self):
        tally = TakenTally()
        tally.note_other("HEAL", 500, 0, source_id="6", ability_id="1")
        tally.note_other("HEAL", 400, 0, source_id="95", ability_id="2", pet_owner="7",
                         companion="c7-106616")
        self.assertEqual(self._view({"8": tally}, "7")["landed"], 0)
        self.assertEqual(self._view({"8": tally}, "7", companions=True)["landed"], 400)


def _token_entry():
    """A 100 s fight: a healer with most of the healing, a DPS with a tenth
    and more, another with little, a tank with none, and a companion."""
    entry = FightHistoryEntry()
    entry.boss_name = "Nahviintaas"
    entry.zone_name = "Sunspire"
    entry.duration_s = 100.0
    entry.players = [
        {"role": "D", "name": "@dps", "unit_id": "1", "healing": 40000, "class_abbr": "NB"},
        {"role": "D", "name": "@other", "unit_id": "2", "healing": 10000, "class_abbr": "DK"},
        {"role": "T", "name": "@tank", "unit_id": "3", "healing": 0, "class_abbr": "DK"},
        {"role": "H", "name": "@healer", "unit_id": "4", "healing": 300000, "class_abbr": "Warden"},
        {"role": "C", "name": "@dps's Companion", "unit_id": "c1-106616", "healing": 5000,
         "companion": True, "owner_unit_id": "1"},
    ]
    return entry


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestTheToken(unittest.TestCase):

    def setUp(self):
        _ensure_app()

    def test_on_a_healer_and_a_row_with_a_tenth_or_more(self):
        from gui.fight_render import healing_token
        entry = _token_entry()
        # The group's 350,000: the players' rows, the companion's left out
        self.assertEqual([healing_token(entry, p) for p in entry.players],
                         ["heal 400 · 11%", "", "", "heal 3.0k · 86%", ""])

    def test_a_link_to_the_healing_done_tab_in_both_views(self):
        from gui.fight_render import render_html
        entry = _token_entry()
        for detailed in (True, False):
            page = render_html(entry, detailed=detailed)
            token = re.search(r'<a href="esolog:healingdone/4"[^>]*>(.*?)</a>', page)
            self.assertIsNotNone(token, detailed)
            self.assertEqual(token.group(1), "heal&nbsp;3.0k&nbsp;·&nbsp;86%")
            self.assertIn("esolog:healingdone/1", page)
            for unit in ("2", "3", "c1-106616"):
                self.assertNotIn(f"esolog:healingdone/{unit}", page)

    def test_copy_fight_has_it_after_the_shares(self):
        from gui.fight_render import render_plain_text
        lines = render_plain_text(_token_entry()).splitlines()
        healer = next(line for line in lines if "@healer" in line)
        self.assertIn("· heal 3.0k (86%)", healer)
        self.assertNotIn("heal", next(line for line in lines if "@other" in line))

    def test_the_hover_gives_the_total_the_clock_and_the_share(self):
        from gui.fight_render import healing_tooltips
        tips = healing_tooltips(_token_entry())
        self.assertEqual(set(tips), {"esolog:healingdone/1", "esolog:healingdone/4"})
        tip = tips["esolog:healingdone/4"]
        for words in ("300,000 over the 1:40 fight, 3,000 a second", "86% of the group's 350,000",
                      "not their heals on themselves", "Click for Healing done"):
            self.assertIn(words, tip)

    def test_no_token_in_a_fight_nobody_healed_anyone_else_in(self):
        from gui.fight_render import healing_token, render_plain_text
        entry = _token_entry()
        for p in entry.players:
            p["healing"] = 0
        self.assertEqual({healing_token(entry, p) for p in entry.players}, {""})
        self.assertNotIn("heal ", render_plain_text(entry))

    def test_the_fight_view_announces_the_click(self):
        from PySide6.QtCore import QUrl

        from gui.fight_view import FightView
        view = FightView()
        self.addCleanup(view.deleteLater)
        heard = []
        view.healing_done_requested.connect(heard.append)
        view.healing_requested.connect(lambda unit: heard.append(f"received {unit}"))
        view.anchorClicked.emit(QUrl("esolog:healingdone/4"))
        view.anchorClicked.emit(QUrl("esolog:healing/4"))
        self.assertEqual(heard, ["4", "received 4"])


def _page_entry():
    """The healer of _token_entry with a Healing done view: one skill under
    two ids, a HoT, an ability that only overflowed, a pet's heals, the
    players healed and heals on themselves."""
    entry = _token_entry()
    rows = [
        {"id": "40079", "via": "", "name": "Radiating Regeneration", "icon": "", "landed": 90000,
         "overheal": 30000, "hits": 300, "hot": 90000, "direct": 0},
        {"id": "86000", "via": "", "name": "Combat Prayer", "icon": "", "landed": 80000,
         "overheal": 20000, "hits": 40, "hot": 0, "direct": 80000},
        {"id": "46266", "via": "", "name": "Radiating Regeneration", "icon": "", "landed": 30000,
         "overheal": 10000, "hits": 100, "hot": 0, "direct": 30000},
        {"id": "88000", "via": "pet", "name": "Pet Salve", "icon": "", "landed": 100000,
         "overheal": 0, "hits": 50, "hot": 100000, "direct": 0},
        {"id": "99999", "via": "", "name": "Healing Burst", "icon": "", "landed": 0,
         "overheal": 5000, "hits": 9, "hot": 5000, "direct": 0},
    ]
    entry.players[3]["healing_done"] = {
        "landed": 300000, "overheal": 65000, "hits": 499, "hot": 195000, "direct": 110000,
        "abilities": rows,
        "targets": [{"id": "3", "name": "@tank", "landed": 200000, "overheal": 15000, "hits": 300,
                     "hot": 0, "direct": 0},
                    {"id": "1", "name": "@dps", "landed": 100000, "overheal": 50000, "hits": 199,
                     "hot": 0, "direct": 0}],
        "own": {"landed": 45000, "overheal": 9000, "hits": 60, "hot": 0, "direct": 45000},
    }
    entry.player_names = [{"name": n, "character": "", "is_local": n == "@healer"}
                          for n in ("@dps", "@other", "@tank", "@healer")]
    return entry


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestThePage(unittest.TestCase):

    def setUp(self):
        _ensure_app()

    def _text(self, page):
        from PySide6.QtGui import QTextDocument
        document = QTextDocument()
        document.setHtml(page)
        return document.toPlainText()

    def test_the_headline_and_one_row_per_name(self):
        from gui.healing_render import render_healing_done_html
        page = render_healing_done_html(_page_entry(), "4")
        text = self._text(page)
        self.assertIn("300,000 healing to others · 3,000 a second of the 1:40 fight · 86% of the "
                      "group's 350,000", text)
        self.assertIn("18% of their healing on others was overheal", text)
        # The skill's two ids are one row, its figures summed, its kinds mixed
        self.assertEqual(text.count("Radiating Regeneration"), 1)
        row = next(r for r in page.split("<tr>") if "Radiating Regeneration" in r)
        cells = [re.sub(r"<[^>]+>", "", cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row)]
        self.assertEqual(cells[1:], ["Radiating Regeneration", "120,000", "40%", "400", "25%",
                                     "HoT 75% · direct 25%"])
        self.assertIn("Pet Salve (pet)", text)
        # Largest first: the pet's 100,000 above the skill's 80,000
        self.assertLess(text.index("Pet Salve"), text.index("Combat Prayer"))
        # Only overheal: named under the table, not a row of 0
        self.assertIn("All overheal on others: Healing Burst", text)

    def test_the_players_healed_and_the_heals_on_themselves(self):
        from gui.healing_render import render_healing_done_html
        page = render_healing_done_html(_page_entry(), "4")
        text = self._text(page)
        self.assertLess(text.index("Players healed"), text.index("@tank"))
        self.assertLess(text.index("@tank"), text.index("@dps"))
        self.assertIn("Heals on themselves: 45,000, not in these figures; listed on Healing "
                      "received, marked own", text)
        self.assertIn("href='esolog:healing/4'", page)
        self.assertIn("Damage shields are not in it", text)

    def test_the_mask_hides_the_players_healed(self):
        from gui.healing_render import render_healing_done_html
        from gui.name_mask import NameMask
        names = NameMask(True, keep={"@healer"}, hidden={"@dps", "@other", "@tank"})
        text = self._text(render_healing_done_html(_page_entry(), "4", names=names))
        self.assertNotIn("@tank", text)
        self.assertNotIn("@dps", text)

    def test_a_player_who_healed_nobody_else_and_a_fight_without_the_view(self):
        from gui.healing_render import (
            NO_HEALING_DONE,
            NOT_RECORDED,
            healing_done_title,
            render_healing_done_html,
        )
        entry = _page_entry()
        entry.players[2]["healing_done"] = {"landed": 0, "overheal": 0, "hits": 0, "hot": 0,
                                            "direct": 0, "abilities": [], "targets": [],
                                            "own": {"landed": 12000, "overheal": 0, "hits": 4,
                                                    "hot": 0, "direct": 12000}}
        text = self._text(render_healing_done_html(entry, "3"))
        self.assertIn(NO_HEALING_DONE, text)
        self.assertIn("Heals on themselves: 12,000", text)
        self.assertIn(NOT_RECORDED, self._text(render_healing_done_html(entry, "2")))
        self.assertEqual(healing_done_title(entry, "4"), "Healing done – @healer")

    def test_a_share_under_one_percent_shows(self):
        """'<1%' is text on the page, not the start of a tag that would
        swallow it and the bold after it (the review of PR #247)."""
        from gui.healing_render import render_healing_done_html
        entry = _page_entry()
        entry.players[1]["healing"] = 2000  # of the group's 342,000: 0.6%
        entry.players[1]["healing_done"] = {
            "landed": 2000, "overheal": 0, "hits": 2, "hot": 0, "direct": 2000,
            "abilities": [], "targets": [],
            "own": {"landed": 0, "overheal": 0, "hits": 0, "hot": 0, "direct": 0}}
        page = render_healing_done_html(entry, "2")
        self.assertIn("<b>&lt;1%</b>", page)
        self.assertIn("2,000 healing to others · 20 a second of the 1:40 fight · <1% of the "
                      "group's 342,000", self._text(page))


if __name__ == "__main__":
    unittest.main()
