#!/usr/bin/env python3
"""The fight's Deaths tab (issue #196, PR 5): every death of a fight on
one page. The deaths in time order, each name a link to that death's
recap; the summary line; a fall; a player the table does not list; how
long a death kept the player down where the log tells it, a dash where it
does not; who was dead at the end; the killers and the bosses' share; the
Hide names mask; the companions' deaths; and the entry left as it was."""

import copy
import html
import re
import unittest

from tests.unit.test_gui import HAVE_QT


def _player(unit_id, name, role="D", class_abbr="NB", **extra):
    return dict({"role": role, "name": name, "class_abbr": class_abbr, "unit_id": unit_id},
                **extra)


def _death(unit_id, name, time_ms, killer, ability, icon="", cause=""):
    return {"unit_id": unit_id, "name": name, "time_ms": time_ms, "killer": killer,
            "ability": ability, "ability_id": "9", "icon": icon, "cause": cause,
            "max_health": 18678, "events": []}


def _entry():
    """A wipe on Sharpfang, 120 s: @tester dies twice (the second time to a
    fall, dead at the end), @friend once and is revived, and @passerby, who
    has no row, once, dead at the end. The engine logged @passerby's death
    before @friend's, which came first: the list is not in time order, so a
    sort of it in place would show."""
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = "Sharpfang"
    entry.zone_name = "Moonlit Cove"
    entry.duration_s = 120.0
    entry.players = [
        _player("1", "@tester", is_local=True),
        _player("2", "@friend", role="H", class_abbr="TPL"),
        _player("3", "@tester's Companion", role="", class_abbr="", companion=True, deaths=2),
    ]
    entry.player_names = [{"name": "@tester", "is_local": True}, {"name": "@friend"},
                          {"name": "@passerby"}]
    entry.death_recaps = [
        _death("1", "@tester", 54000, "Sharpfang", "Slap", icon="slap_icon"),
        _death("77", "@passerby", 61000, "Sharpfang", "Tremor"),
        _death("2", "@friend", 60500, "Sharpfang", "Tremor"),
        _death("1", "@tester", 95000, "", "a fall or lava", cause="fall"),
    ]
    entry.deaths = 4
    entry.time_dead = {"1": 51000, "2": 12000, "77": 59000}
    entry.pull = {"boss": "Sharpfang", "bosses": ["Sharpfang"], "outcome": "wipe",
                  "dead_at_end": ["1", "77"], "continues": False}
    return entry


def _text(page: str) -> str:
    """The page's text, tags dropped, entities read."""
    return html.unescape(re.sub(r"<[^>]+>", "", page))


def _cells(page: str) -> list:
    """Each table row's cells as text, the heading row first."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.DOTALL)
    return [[_text(cell).strip() for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)]
            for row in rows]


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestFightDeathsPage(unittest.TestCase):

    def _render(self, entry, **kwargs):
        from gui.fight_deaths_render import render_fight_deaths_html
        return render_fight_deaths_html(entry, **kwargs)

    def test_the_deaths_in_time_order_each_linked_to_its_recap(self):
        """The table runs in time order, whatever order the engine logged
        the deaths in; each name links to that player's death by its number
        among theirs, as the player window's Deaths tab numbers them."""
        page = self._render(_entry())
        rows = _cells(page)
        self.assertEqual(rows[0], ["Time", "Role", "Player", "Killed by", "From", "Dead for"])
        self.assertEqual([row[0] for row in rows[1:]], ["0:54", "1:00", "1:01", "1:35"])
        self.assertEqual([row[2] for row in rows[1:]],
                         ["@tester", "@friend", "@passerby", "@tester"])
        self.assertEqual(re.findall(r'href="(esolog:recap/[^"]+)"', page),
                         ["esolog:recap/1/1", "esolog:recap/2/1", "esolog:recap/77/1",
                          "esolog:recap/1/2"])

    def test_deaths_at_the_same_moment_keep_the_engines_order(self):
        entry = _entry()
        for recap in entry.death_recaps:
            recap["time_ms"] = 4512
        page = self._render(entry)
        self.assertEqual([row[2] for row in _cells(page)[1:]],
                         ["@tester", "@passerby", "@friend", "@tester"])
        self.assertEqual(re.findall(r'href="(esolog:recap/[^"]+)"', page)[-1], "esolog:recap/1/2")

    def test_the_summary_line(self):
        """How many died, of how many players, the first death, how long a
        wipe went on after it, and how many were dead at the end; a kill
        with everyone revived says no one was; a fight without a pull says
        nothing of the end."""
        from gui.fight_deaths_render import render_fight_deaths_html
        entry = _entry()
        self.assertTrue(_text(self._render(entry)).startswith(
            "4 deaths of 3 players · first at 0:54 · the pull ended 1:06 after it · "
            "2 dead at the end"))
        entry.pull = dict(entry.pull, outcome="kill", dead_at_end=[])
        self.assertTrue(_text(render_fight_deaths_html(entry)).startswith(
            "4 deaths of 3 players · first at 0:54 · no one dead at the end"))
        entry.pull = None
        first = _text(render_fight_deaths_html(entry)).split("Time")[0].strip()
        self.assertEqual(first, "4 deaths of 3 players · first at 0:54")

    def test_a_fall_has_no_killer_and_counts_among_the_killers(self):
        """A fall or lava (#184) names no killer: a dash under From, and in
        the killers it stands alone, outside the bosses' share."""
        page = self._render(_entry())
        fall = _cells(page)[4]
        self.assertEqual(fall[4:6], ["a fall or lava", "–"])
        text = _text(page)
        self.assertIn("Killers: Tremor from Sharpfang ×2 · Slap from Sharpfang · a fall or lava; "
                      "75% by Sharpfang", text)

    def test_a_player_the_table_does_not_list_is_there_without_a_role(self):
        page = self._render(_entry())
        passerby = _cells(page)[3]
        self.assertEqual(passerby[1:3], ["", "@passerby"])
        self.assertEqual(_cells(page)[1][1], "D")

    def test_how_long_each_death_kept_the_player_down(self):
        """An only death: the player's time dead. A last death with the
        player dead at the end: to the end of the fight. A player's other
        deaths: a dash, which a note explains, their total in the time
        dead line, longest first, with its share of the fight."""
        from gui.fight_deaths_render import DEAD_FOR_NOTE
        page = self._render(_entry())
        dead_for = [row[6] for row in _cells(page)[1:]]
        self.assertEqual(dead_for, ["–", "12s", "59s to the end", "25s to the end"])
        text = _text(page)
        self.assertIn(DEAD_FOR_NOTE, text)
        self.assertIn("Time dead: @passerby 59s (49%) · @tester 51s (42%) · @friend 12s (10%)",
                      text)
        # No dash, no note
        entry = _entry()
        entry.death_recaps = entry.death_recaps[1:3]  # @passerby's and @friend's
        self.assertNotIn(DEAD_FOR_NOTE, _text(self._render(entry)))

    def test_a_fight_that_carries_on_the_last_pull_gives_no_time_it_cannot_tell(self):
        """Its time dead can hold a span carried from the fight before: an
        only death is no longer its own measure, though one that lasted to
        the end still is."""
        entry = _entry()
        entry.pull["continues"] = True
        dead_for = [row[6] for row in _cells(self._render(entry))[1:]]
        self.assertEqual(dead_for, ["–", "–", "59s to the end", "25s to the end"])

    def test_without_a_pull_nothing_is_said_of_the_end(self):
        entry = _entry()
        entry.pull = None
        page = self._render(entry)
        self.assertNotIn("to the end", _text(page))
        self.assertEqual([row[6] for row in _cells(page)[1:]], ["–", "12s", "59s", "–"])
        self.assertNotIn("% by", _text(page))

    def test_hide_names_hides_the_other_players_and_keeps_the_enemies(self):
        """Every other player's name goes through the mask, in the table,
        the time dead line, the companions and the hover; the enemies and
        the writer's own name stay; a player who killed is hidden too."""
        from gui.fight_deaths_render import fight_deaths_tooltips
        from gui.name_mask import NameMask
        entry = _entry()
        entry.death_recaps[1]["killer"] = "@passerby"  # friendly fire
        names = NameMask.for_entry(entry, True)
        page = self._render(entry, names=names)
        tips = " ".join(fight_deaths_tooltips(entry, names).values())
        for hidden in ("friend", "passerby"):
            self.assertNotIn(hidden, page)
            self.assertNotIn(hidden, tips)
        self.assertIn("@tester", _text(page))
        self.assertIn("Sharpfang", _text(page))
        self.assertIn("alt=\"hidden name\"", page)

    def test_the_companions_deaths_as_a_count(self):
        """The log keeps no recap of a companion's death, so its deaths are
        counted under the players'; a fight where only companions died
        says no player did."""
        from gui.fight_deaths_render import NO_DEATHS, NO_PLAYER_DEATHS
        entry = _entry()
        self.assertTrue(_text(self._render(entry)).rstrip().endswith(
            "Companions: @tester's Companion ☠ ×2"))
        entry.death_recaps = []
        text = _text(self._render(entry))
        self.assertTrue(text.startswith(NO_PLAYER_DEATHS))
        self.assertIn("Companions: @tester's Companion ☠ ×2", text)
        entry.players[2]["deaths"] = 0
        self.assertEqual(_text(self._render(entry)), NO_DEATHS)

    def test_anon_players_are_told_apart_by_their_row(self):
        """Two players the log gives no name: each with its row's class in
        the table, its role and class in the time dead line."""
        entry = _entry()
        entry.players += [_player("8", "anon", role="T", class_abbr="DK"),
                          _player("9", "anon", role="D", class_abbr="ARC")]
        entry.death_recaps += [_death("8", "anon", 100000, "Sharpfang", "Slap"),
                               _death("9", "anon", 101000, "Sharpfang", "Slap")]
        entry.time_dead.update({"8": 20000, "9": 19000})
        page = self._render(entry)
        self.assertEqual([row[2] for row in _cells(page)[-2:]], ["anon (DK)", "anon (ARC)"])
        text = _text(page)
        self.assertIn("anon (T, DK) 20s", text)
        self.assertIn("anon (D, ARC) 19s", text)

    def test_the_killing_abilitys_icon(self):
        class Icons:
            def has(self, stem):
                return stem == "slap_icon"

        page = self._render(_entry(), icons=Icons())
        self.assertEqual(re.findall(r'src="icon:([^"]+)"', page), ["slap_icon"])
        self.assertNotIn("icon:", self._render(_entry()))

    def test_the_hover_on_each_name(self):
        from gui.fight_deaths_render import fight_deaths_tooltips
        tips = fight_deaths_tooltips(_entry())
        self.assertEqual(sorted(tips), ["esolog:recap/1/1", "esolog:recap/1/2",
                                        "esolog:recap/2/1", "esolog:recap/77/1"])
        tip = _text(tips["esolog:recap/1/2"].replace("<br>", "\n"))
        self.assertEqual(tip.splitlines()[:2], ["@tester: death 2 of 2, at 1:35",
                                                "Killed by a fall or lava"])

    def test_the_entry_is_left_as_it_was(self):
        """The engine's thread updates an entry in place: the page and its
        hover only read it."""
        from gui.fight_deaths_render import fight_deaths_tooltips
        from gui.name_mask import NameMask
        entry = _entry()
        before = copy.deepcopy({slot: getattr(entry, slot) for slot in entry.__slots__})
        self._render(entry, dark=True, names=NameMask.for_entry(entry, True))
        fight_deaths_tooltips(entry)
        self.assertEqual({slot: getattr(entry, slot) for slot in entry.__slots__}, before)


if __name__ == "__main__":
    unittest.main()
