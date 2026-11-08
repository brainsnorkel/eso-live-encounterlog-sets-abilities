#!/usr/bin/env python3
"""The Instance tab (issue #196, PR 7): one instance of the fight list on
one page. Its heading, the run's result with the banner links, a row and
an anchor per boss's pulls in a row with their pull links, what ended the
pulls, the trash and a solo dungeon's Misfortunes, and the players by
handle; no result for a failed run or a dungeon; the Hide names mask; the
line for an instance that may go back before the session the app read;
the links and the places in the list they carry; and the block left as it
was."""

import copy
import html
import re
import unittest

from tests.unit.test_gui import HAVE_QT

MISFORTUNES = [["Warm Welcome", "Enemies deal double damage"],
               ["Revoke of Respite", "Healing taken is reduced by 50%"]]


def _player(unit_id, name, role="D", class_abbr="Arcanist", issues=(), **extra):
    return dict({"role": role, "name": name, "class_abbr": class_abbr, "unit_id": unit_id,
                 "build_issues": list(issues)}, **extra)


def _issue(rule, title):
    return {"rule": rule, "title": title, "detail": "", "set": "", "skill": ""}


def _recap(unit_id, name, ms, ability, killer):
    return {"unit_id": unit_id, "name": name, "time_ms": ms, "ability": ability,
            "killer": killer, "ability_id": "9", "icon": "", "max_health": 20000, "events": []}


def _pull(outcome, health_left, boss, start_s, end_s, players=12):
    return {"boss": boss, "bosses": [boss], "outcome": outcome, "health_left": health_left,
            "health_start": 100.0, "health": {boss: [100.0, health_left]},
            "boss_died": outcome == "kill", "players": players, "dead_at_end": [],
            "local_dead_at_end": False, "start_s": start_s, "end_s": end_s,
            "zone": "1121|VETERAN", "continues": False, "cut": False, "went_on": False}


# Handles the fight history matches a roster by (fight_index.ROSTER_MIN)
_OTHERS = [f"@raider{i}" for i in range(1, 7)]


def _fight(boss, start, duration, pull=None, players=(), recaps=(), time_dead=None,
           boss_dps=0.0, zone="Sunspire", zone_id="1121", difficulty="VETERAN"):
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = boss
    entry.zone_name = zone
    entry.zone_id = zone_id
    entry.difficulty = difficulty
    entry.is_vet = difficulty == "VETERAN"
    entry.timestamp = start
    entry.duration_s = duration
    entry.group_dps = 500000.0
    entry.group_boss_dps = boss_dps
    entry.dps_time_s = duration
    entry.boss_dps_time_s = duration if boss_dps else 0.0
    entry.pull = pull
    entry.players = list(players)
    entry.player_names = ([{"name": p["name"], "is_local": bool(p.get("is_local"))}
                           for p in entry.players if not p.get("companion")]
                          + [{"name": name} for name in ["@passerby"] + _OTHERS])
    entry.death_recaps = list(recaps)
    entry.deaths = len(entry.death_recaps)
    entry.time_dead = dict(time_dead or {})
    entry.game_version = "eso.live.12.1"
    return entry


def _roster(heal_role="H", me="1"):
    return [_player(me, "@me", class_abbr="NB", is_local=True,
                    issues=[_issue("set-never-fired", "Roaring Opportunist never fired")]),
            _player("2", "@tank", role="T", class_abbr="DK", issues=[_issue("food", "No food")]),
            _player("3", "@heal", role=heal_role, class_abbr="Templar"),
            _player("11", "anon", class_abbr="Sorc"),
            _player("12", "anon", class_abbr="Arcanist"),
            _player("13", "@me's Companion", role="", class_abbr="", companion=True)]


def _night():
    """Sunspire on veteran, five fights: a trash fight in which @tank dies
    and @heal reads as a damage dealer; Lokkestiiz wiped at 62%, @passerby
    (no row) dying among others, then killed; Yolnahkriin killed; and
    Nahviintaas killed, completing the trial, by @me on a new unit id."""
    trash = _fight("Ruined Atronach", "2026-11-04 20:05:00", 30.0, players=_roster(heal_role="D"),
                   recaps=[_recap("2", "@tank", 10000, "Slam", "Ruined Atronach")],
                   time_dead={"2": 5000})
    wipe = _fight("Lokkestiiz", "2026-11-04 20:10:00", 120.0,
                  _pull("wipe", 62.0, "Lokkestiiz", 1000.0, 1120.0), players=_roster(),
                  recaps=[_recap("11", "anon", 40000, "Frost Breath", "Lokkestiiz"),
                          _recap("1", "@me", 50000, "Storm Fury", "Lokkestiiz"),
                          _recap("77", "@passerby", 55000, "Frost Breath", "Lokkestiiz")],
                  time_dead={"11": 80000, "1": 70000, "77": 65000})
    kill = _fight("Lokkestiiz", "2026-11-04 20:13:00", 180.0,
                  _pull("kill", 0.0, "Lokkestiiz", 1180.0, 1360.0), boss_dps=600000.0,
                  players=[p for p in _roster() if p["name"] != "@tank"]
                  + [_player("2", "@tank", role="T", class_abbr="DK")],
                  recaps=[_recap("2", "@tank", 100000, "Bite", "Fire Atronach")],
                  time_dead={"2": 20000})
    yolnahkriin = _fight("Yolnahkriin", "2026-11-04 20:30:00", 200.0,
                         _pull("kill", 0.0, "Yolnahkriin", 2200.0, 2400.0), boss_dps=500000.0,
                         players=_roster())
    final = _fight("Nahviintaas", "2026-11-04 20:40:00", 300.0,
                   _pull("kill", 0.0, "Nahviintaas", 2800.0, 3100.0), boss_dps=400000.0,
                   players=_roster(me="101"),
                   recaps=[_recap("101", "@me", 200000, "Time Shift", "Nahviintaas")],
                   time_dead={"101": 3000})
    # The finding's words change from fight to fight; the latest are said
    final.players[0]["build_issues"] = [_issue("set-never-fired",
                                               "Roaring Opportunist never fired in 2 fights")]
    final.trial_result = {"trial_id": 12, "name": "Sunspire", "is_vet": True,
                          "duration_ms": 2100000, "score": 253117, "vitality": 33,
                          "vitality_max": 36}
    return [trash, wipe, kill, yolnahkriin, final]


def _listed(block, before=2):
    """The fight list the page is drawn from: two fights of an earlier
    instance, then *block*; and index_of over it."""
    earlier = [_fight("Daedroth", f"2026-11-04 19:0{i}:00", 20.0, zone="Craglorn", zone_id="888",
                      difficulty="NONE", players=_roster()) for i in range(before)]
    fights = earlier + list(block)
    places = {id(fight): index for index, fight in enumerate(fights)}

    def index_of(fight):
        return places.get(id(fight))

    return fights, index_of


def _text(page: str) -> str:
    """The page's text, tags dropped (a paragraph's or a line's end read as a
    space), entities read, spaces as one."""
    page = re.sub(r"</p>|<br>", " ", page)
    text = html.unescape(re.sub(r"<[^>]+>", "", page)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _tables(page: str) -> list:
    """Each table's rows, each row's cells as text, less the empty cells it
    ends with (the players' table ends each row with an empty column that
    takes the width its other columns leave)."""
    out = []
    for table in re.findall(r"<table[^>]*>(.*?)</table>", page, re.DOTALL):
        rows = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL):
            cells = [_text(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)]
            while cells and not cells[-1]:
                cells.pop()
            rows.append(cells)
        out.append(rows)
    return out


def _table(page: str, first_heading: str) -> list:
    return next(rows for rows in _tables(page) if rows and rows[0][0] == first_heading)


def _hrefs(page: str, prefix: str) -> list:
    """Each link's href starting with *prefix*, in order, either quote."""
    return re.findall(rf"""href=["']({re.escape(prefix)}[^"']*)["']""", page)


class _History:
    """A fight history (fight_index.FightIndex) holding earlier kills."""

    def __init__(self, lines):
        self.lines = lines

    def kills(self, zone_id, difficulty, boss, before_s):
        return [line for line in self.lines
                if line["boss"] == boss and (before_s is None or line["start_s"] < before_s)]


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestSections(unittest.TestCase):

    def _render(self, block=None, **kwargs):
        from gui.instance_render import render_instance_html
        block = _night() if block is None else block
        _fights, index_of = _listed(block)
        return render_instance_html(block, index_of, **kwargs)

    def test_the_heading(self):
        """The zone and difficulty, the span from the first fight's start to
        the last one's end, the fights, the group's size, the game version
        and the copy link."""
        from gui.instance_render import COPY_TEXT, INSTANCE_COPY_HREF
        page = self._render()
        self.assertTrue(_text(page).startswith(
            "Sunspire · Veteran 2026-11-04 20:05 to 20:45 · 5 fights · 12 players · game 12.1 · "
            f"{COPY_TEXT}"))
        self.assertEqual(_hrefs(page, "esolog:instance/"), [INSTANCE_COPY_HREF])

    def test_the_heading_uses_the_recaps_own_figures(self):
        """The span and the group's size are the session recap's, public now."""
        import session_recap
        night = _night()
        self.assertEqual(session_recap.span(night), "2026-11-04 20:05 to 20:45")
        self.assertEqual(session_recap.players(night), 12)
        self.assertTrue(session_recap.recap_text(night).startswith(
            "Sunspire · Veteran · 2026-11-04 20:05 to 20:45 · 12 players"))

    def test_the_result_and_its_banner_links(self):
        """A completed run's result, as the list's result row writes it, in a
        strip, with the fight pane's banner links once the banner is saved."""
        from trial_result import result_text
        night = _night()
        page = self._render(night)
        strip = _tables(page)[0]
        self.assertEqual(strip, [[result_text(night[-1].trial_result)]])
        self.assertEqual(_hrefs(page, "esolog:banner/"), [])
        night[-1].banner_path = "banner.png"
        page = self._render(night)
        self.assertEqual(_hrefs(page, "esolog:banner/"),
                         ["esolog:banner/open", "esolog:banner/save", "esolog:banner/copy"])
        self.assertIn("Score banner (save as…) (copy)", _text(page))

    def test_a_row_for_each_boss_with_its_pulls(self):
        """Every boss's pulls in a row, one pull included: the pulls, the
        run row's words after its count (or one pull's verdict), the kill's
        time and boss dps, and the deaths over all its pulls; under two or
        more pulls, each pull with its verdict."""
        rows = _table(self._render(), "Boss")
        self.assertEqual(rows, [
            ["Boss", "Pulls", "Result", "Kill", "Boss dps", "Deaths"],
            ["Lokkestiiz", "2", "killed on pull 2, 1:00 between pulls", "3:00", "600.0k", "4"],
            ["Pulls: pull 1 (wipe 62%) · pull 2 (kill)"],
            ["Yolnahkriin", "1", "kill", "3:20", "500.0k", "0"],
            ["Nahviintaas", "1", "kill", "5:00", "400.0k", "1"],
        ])

    def test_a_run_that_did_not_kill(self):
        """No kill: its best, and dashes for the kill's figures; one pull:
        its verdict."""
        night = _night()[:2]
        rows = _table(self._render(night), "Boss")
        self.assertEqual(rows[1], ["Lokkestiiz", "1", "wipe 62%", "–", "–", "3"])

    def test_the_kill_figures_are_the_copys(self):
        """A kill's time and dps on the page are what Copy this instance
        writes, a pull the log cut in two summed as the recap sums it, and a
        kill without a boss figure says its dps is of all targets."""
        import session_recap
        first = _fight("Lokkestiiz", "2026-11-04 21:00:00", 120.0,
                       _pull("unseen", 40.0, "Lokkestiiz", 0.0, 120.0), boss_dps=400000.0,
                       players=_roster())
        second = _fight("Lokkestiiz", "2026-11-04 21:02:10", 60.0,
                        _pull("kill", 0.0, "Lokkestiiz", 130.0, 190.0), boss_dps=700000.0,
                        players=_roster())
        second.pull["continues"] = True
        first.pull["cut"] = True
        rows = _table(self._render([first, second]), "Boss")
        self.assertEqual(rows[1][1:6], ["1", "kill", "3:00", "500.0k", "0"])
        self.assertIn("kill in 1 pull, 3:00, 500.0k boss dps",
                      session_recap.recap_text([first, second]))
        plain = _fight("Tho'at Replicanum", "2026-11-04 21:00:00", 90.0,
                       _pull("kill", 0.0, "Tho'at Replicanum", 0.0, 90.0), players=_roster())
        self.assertEqual(_table(self._render([plain]), "Boss")[1][4], "500.0k (all targets)")
        night = _night()
        recap = session_recap.recap_text(night)
        self.assertIn("the kill 3:00, 600.0k boss dps", recap)
        self.assertIn("Yolnahkriin: kill in 1 pull, 3:20, 500.0k boss dps", recap)

    def test_the_best_earlier_kill_with_this_roster(self):
        """With the fight history, each run says its best earlier kill with
        this roster, as the list's run row does; only kills before the run."""
        roster = ["@me", "@tank", "@heal", "@passerby"] + _OTHERS
        history = _History([
            {"boss": "Lokkestiiz", "start_s": 10.0, "group_boss_dps": 640100.0, "handles": roster},
            {"boss": "Lokkestiiz", "start_s": 20.0, "group_boss_dps": 590000.0, "handles": roster},
            {"boss": "Lokkestiiz", "start_s": 5000.0, "group_boss_dps": 900000.0, "handles": roster},
            {"boss": "Yolnahkriin", "start_s": 30.0, "group_boss_dps": 450000.0,
             "handles": ["@someone"]},
        ])
        rows = _table(self._render(fight_index=history), "Boss")
        self.assertEqual(rows[1][2], "killed on pull 2, 1:00 between pulls, "
                                     "best kill with this roster 640.1k")
        self.assertEqual(rows[3][2], "kill")

    def test_what_ended_the_pulls(self):
        """Over every pull of the instance, the trash left out: the first
        death of each pull, the killers with the share the bosses dealt (a
        killer not one of them named), and the longest dead, the top three
        of each and an ellipsis for the rest."""
        text = _text(self._render())
        self.assertIn("First deaths: Frost Breath · Bite (Fire Atronach) · Time Shift Killers:", text)
        self.assertIn("Killers: Frost Breath ×2 · Storm Fury · Bite (Fire Atronach) · …; "
                      "80% by the bosses", text)
        self.assertIn("Most time dead in the pulls: anon (D, Sorc) 1:20 · @me 1:13 · "
                      "@passerby 1:05", text)
        self.assertNotIn("Slam", text)

    def test_the_bosses_named_when_one_or_two(self):
        """Lokkestiiz alone: the share names it, as the Deaths tab does."""
        self.assertIn("; 75% by Lokkestiiz", _text(self._render(_night()[:3])))

    def test_no_one_died_in_a_pull(self):
        from gui.instance_render import FIRST_DEATHS_LEAD, KILLERS_LEAD
        night = _night()
        for fight in night[1:]:
            fight.death_recaps, fight.deaths, fight.time_dead = [], 0, {}
        text = _text(self._render(night))
        self.assertNotIn(FIRST_DEATHS_LEAD, text)
        self.assertNotIn(KILLERS_LEAD, text)

    def test_a_second_dead_at_least_is_the_longest(self):
        """A solo player's fight ends as they die, which would read '0s'."""
        night = _night()
        for fight in night:
            fight.time_dead = {key: 400 for key in fight.time_dead}
        self.assertNotIn("Most time dead", _text(self._render(night)))

    def test_the_trash(self):
        self.assertIn("Trash: 1 fight, 30s, 1 death", _text(self._render()))
        night = _night()
        night[0].death_recaps, night[0].deaths = [], 0
        text = _text(self._render(night))
        self.assertIn("Trash: 1 fight, 30s", text)
        self.assertNotIn("30s, 0 deaths", text)
        self.assertNotIn("Trash:", _text(self._render(night[1:])))

    def test_a_solo_dungeons_misfortunes_once(self):
        """The run's Misfortunes, the same at every pull, said once, each
        with a text a hover anchor as on the fight pane; none elsewhere."""
        from gui.instance_render import instance_tooltips
        solo = [_fight("Jailer Melitus", f"2026-10-26 19:3{i}:00", 60.0,
                       _pull("wipe", 46.0 - i, "Jailer Melitus", 100.0 * i, 100.0 * i + 60, 1),
                       zone="Moon Hunter Keep", zone_id="1593", difficulty="NONE",
                       players=_roster()[:1]) for i in range(2)]
        for fight in solo:
            fight.misfortunes = copy.deepcopy(MISFORTUNES)
        page = self._render(solo)
        self.assertEqual(_text(page).count("Misfortunes:"), 1)
        self.assertIn("Misfortunes: Warm Welcome · Revoke of Respite", _text(page))
        self.assertTrue(_text(page).startswith("Moon Hunter Keep 2026-10-26 19:30 to 19:32"))
        _fights, index_of = _listed(solo)
        tips = instance_tooltips(solo, index_of)
        self.assertEqual(_hrefs(page, "esolog:misfortune/"),
                         ["esolog:misfortune/0", "esolog:misfortune/1"])
        self.assertIn("Enemies deal double damage", tips["esolog:misfortune/0"])
        self.assertNotIn("Misfortunes", _text(self._render()))

    def test_the_players(self):
        """Every player once, a companion not: by handle across the
        fights, an anon by unit id and class; the role most of their fights
        read; the pulls they were in; deaths and time dead over every
        fight, the trash's too; each build issue once in its latest words,
        with how many of their fights it was found in, on a line under the
        row; a player who died with no row listed with no role, last."""
        rows = _table(self._render(), "Player")
        self.assertEqual(rows, [
            ["Player", "Role", "Class", "Pulls", "Deaths", "Time dead"],
            ["@tank", "T", "DK", "4", "2", "25s"],
            ["Possible build issues: No food ×4"],
            ["@heal", "H", "Templar", "4", "0", "–"],
            ["@me", "D", "NB", "4", "2", "1:13"],
            ["Possible build issues: Roaring Opportunist never fired in 2 fights ×5"],
            ["anon", "D", "Arcanist", "4", "0", "–"],
            ["anon", "D", "Sorc", "4", "1", "1:20"],
            ["@passerby", "", "", "1", "1", "1:05"],
        ])

    def test_anons_are_told_apart_by_unit_id_and_class(self):
        """Two anons of one role and class are two players, in the table
        and in the longest dead, as the run row's hover tells them apart;
        one the engine guesses a healer on the trash stays one player, with
        the role most of their fights read (the review of PR #208: keyed by
        role and class, the first two were one and the last two)."""
        from pull_outcome import run_details, runs
        night = _night()
        for fight in night:
            for p in fight.players:
                if p["unit_id"] == "12":
                    p["class_abbr"] = "Sorc"
        night[0].players[3]["role"] = "H"  # anon 11, on the trash
        night[1].death_recaps.append(_recap("12", "anon", 45000, "Frost Breath", "Lokkestiiz"))
        night[1].time_dead["12"] = 75000
        rows = [row for row in _table(self._render(night), "Player")[1:] if row[0] == "anon"]
        self.assertEqual([row[:3] for row in rows], [["anon", "D", "Sorc"], ["anon", "D", "Sorc"]])
        text = _text(self._render(night))
        self.assertIn("Most time dead in the pulls: anon (D, Sorc) 1:20 · anon (D, Sorc) 1:15 · "
                      "@me 1:13", text)
        run = runs(night)[0]
        self.assertIn("Most time dead: anon (D, Sorc) 1:20, anon (D, Sorc) 1:15, @me 1:10",
                      run_details(run))

    def test_the_tables_keep_their_words_whole_at_large_text(self):
        """Measured at 200% text on real splits: no heading breaks inside a
        word, the figures' columns are as narrow as their words, so the boss
        names keep the width, and the players' columns are all as narrow as
        theirs, an empty one taking the rest."""
        from gui.instance_render import FIT
        page = self._render()
        for table in re.findall(r"<table[^>]*>(.*?)</table>", page, re.DOTALL)[1:]:
            heading = re.findall(r"<tr>(.*?)</tr>", table, re.DOTALL)[0]
            cells = re.findall(r"<td([^>]*)>(.*?)</td>", heading, re.DOTALL)
            self.assertTrue(all("white-space:nowrap" in attrs for attrs, _words in cells))
            fitted = [text for attrs, text in cells if f"width='{FIT}'" in attrs]
            if cells[0][1] == "Boss":
                self.assertEqual(fitted, ["Pulls", "Kill", "Boss dps", "Deaths"])
            else:
                self.assertEqual(fitted, ["Player", "Role", "Class", "Pulls", "Deaths",
                                          "Time dead"])
                self.assertEqual(cells[-1][1], "")

    def test_no_fights(self):
        from gui.instance_render import (
            NO_FIGHTS,
            instance_tooltips,
            render_instance_html,
        )
        self.assertEqual(_text(render_instance_html([], lambda fight: None)), NO_FIGHTS)
        self.assertEqual(instance_tooltips([], lambda fight: None), {})


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestNoResult(unittest.TestCase):

    def _render(self, block):
        from gui.instance_render import render_instance_html
        _fights, index_of = _listed(block)
        return render_instance_html(block, index_of)

    def test_a_failed_run_has_no_result(self):
        """A run that fails writes no END_TRIAL: no strip, no banner links."""
        night = _night()
        night[-1].trial_result = None
        night[-1].banner_path = "banner.png"
        page = self._render(night)
        self.assertNotIn("✓", _text(page))
        self.assertEqual(_hrefs(page, "esolog:banner/"), [])
        self.assertEqual(_tables(page)[0][0][0], "Boss")

    def test_a_dungeon(self):
        """A group dungeon: the heading, its bosses and players, no result."""
        dungeon = [
            _fight("Spider Daedra", "2026-11-05 19:00:00", 40.0, zone="Fungal Grotto I",
                   zone_id="98", difficulty="NORMAL", players=_roster()[:4]),
            _fight("Kra'gh the Dreugh King", "2026-11-05 19:05:00", 95.0,
                   _pull("kill", 0.0, "Kra'gh the Dreugh King", 400.0, 495.0, players=4),
                   boss_dps=90000.0, zone="Fungal Grotto I", zone_id="98", difficulty="NORMAL",
                   players=_roster()[:4]),
        ]
        page = self._render(dungeon)
        self.assertTrue(_text(page).startswith(
            "Fungal Grotto I · Normal 2026-11-05 19:00 to 19:06 · 2 fights · 4 players"))
        self.assertNotIn("✓", _text(page))
        self.assertEqual([row[0] for row in _table(page, "Boss")[1:]], ["Kra'gh the Dreugh King"])
        self.assertEqual([row[0] for row in _table(page, "Player")[1:] if len(row) > 1],
                         ["@tank", "@heal", "@me", "anon"])

    def test_an_instance_without_a_pull(self):
        """Trash alone: no bosses, nothing of what ended the pulls."""
        page = self._render(_night()[:1])
        self.assertEqual([rows[0][0] for rows in _tables(page)], ["Player"])
        self.assertNotIn("Killers", _text(page))
        self.assertIn("Trash: 1 fight, 30s, 1 death", _text(page))


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestHideNames(unittest.TestCase):

    def test_the_other_players_are_hidden_and_the_enemies_kept(self):
        """Every other player's name goes through the mask, on the page and
        in the hover texts, a player who killed one too; the logging
        player's name, the bosses and the abilities stay."""
        from gui.instance_render import instance_tooltips, render_instance_html
        from gui.name_mask import NameMask
        night = _night()
        night[1].death_recaps[2]["killer"] = "@heal"  # friendly fire
        names = NameMask.for_entries(night, True)
        _fights, index_of = _listed(night)
        page = render_instance_html(night, index_of, names=names)
        tips = " ".join(instance_tooltips(night, index_of, names=names).values())
        for hidden in ("@tank", "@heal", "@passerby", "tank", "passerby"):
            self.assertNotIn(hidden, page)
            self.assertNotIn(hidden, tips)
        self.assertIn('alt="hidden name"', page)
        self.assertIn("@▒▒▒▒", tips)
        for kept in ("@me", "Lokkestiiz", "Frost Breath", "Fire Atronach", "anon (D, Sorc)"):
            self.assertIn(kept, _text(page))
        self.assertIn("@me", tips)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestListedFrom(unittest.TestCase):

    def test_the_live_lists_first_instance_says_where_it_is_listed_from(self):
        """It may have begun before the logging session the app read at its
        start: the line says so in words true when nothing came before."""
        from gui.instance_render import LISTED_EARLIER, render_instance_html
        night = _night()
        _fights, index_of = _listed(night)
        line = "Listed from 20:05; any earlier fights are in the previous session's log."
        self.assertIn(line, _text(render_instance_html(night, index_of, opens_list=True)))
        self.assertNotIn("Listed from", _text(render_instance_html(night, index_of)))
        for fight in night:
            fight.timestamp = "Unknown Time"
        text = _text(render_instance_html(night, index_of, opens_list=True))
        self.assertIn(LISTED_EARLIER, text)
        self.assertNotIn("Listed from", text)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestLinks(unittest.TestCase):

    def setUp(self):
        from gui.instance_render import instance_tooltips, render_instance_html
        self.night = _night()
        self.fights, self.index_of = _listed(self.night)
        self.render = lambda **kw: render_instance_html(self.night, self.index_of, **kw)
        self.tips = lambda **kw: instance_tooltips(self.night, self.index_of, **kw)

    def test_each_pull_links_to_its_place_in_the_list(self):
        """A pull of a run of two or more links to its fight by its place in
        the list the page was drawn from; a boss killed on its one pull has
        no pulls' line and no link, as the issue draws it."""
        _trash, wipe, kill, _yolnahkriin, _final = self.night
        page = self.render()
        self.assertEqual(_hrefs(page, "esolog:fight/"),
                         [f"esolog:fight/{self.fights.index(fight)}" for fight in (wipe, kill)])
        self.assertEqual(self.fights.index(wipe), 3)

    def test_a_name_opens_the_fight_on_screen_when_they_were_in_it(self):
        """With Lokkestiiz's kill on screen: a player in it opens it, by
        their unit id in it; @passerby, not in it, opens their last fight."""
        shown = self.night[2]
        page = self.render(shown=shown)
        links = _hrefs(page, "esolog:player/")
        self.assertIn("esolog:player/4/2", links)  # @tank
        self.assertIn("esolog:player/4/1", links)  # @me
        self.assertIn("esolog:player/3/77", links)  # @passerby
        tips = self.tips(shown=shown)
        self.assertEqual(_text(tips["esolog:player/4/2"]).split(" Click")[0],
                         "@tank in Lokkestiiz, pull 2 (the fight on screen)")
        self.assertEqual(_text(tips["esolog:player/3/77"]).split(" Click")[0],
                         "@passerby in Lokkestiiz, pull 1")

    def test_a_name_opens_a_fight_they_have_a_row_in(self):
        """A player who died in the fight on screen with no row of their own
        there opens their last fight with a row, on Build; one who never had
        a row opens their death, which the window shows on Deaths, and the
        hover says which (the review of PR #208: the name opened Build on a
        fight with no row for them, an empty page)."""
        from gui.instance_render import (
            DEATH_TIP,
            PLAYER_TIP,
            instance_tooltips,
            render_instance_html,
        )
        night = _night()
        final = night[-1]
        final.players = [p for p in final.players if p["name"] != "@heal"]
        final.death_recaps = final.death_recaps + [_recap("3", "@heal", 100000, "Time Shift",
                                                          "Nahviintaas")]
        final.deaths = len(final.death_recaps)
        fights, index_of = _listed(night)
        links = _hrefs(render_instance_html(night, index_of, shown=final), "esolog:player/")
        heal = f"esolog:player/{fights.index(night[3])}/3"  # Yolnahkriin, their last row
        self.assertIn(heal, links)
        self.assertNotIn(f"esolog:player/{fights.index(final)}/3", links)
        tips = instance_tooltips(night, index_of, shown=final)
        self.assertIn(PLAYER_TIP, tips[heal])
        self.assertIn(DEATH_TIP, tips["esolog:player/3/77"])  # @passerby, no row anywhere

    def test_else_their_last_fight_of_the_instance(self):
        """With no fight on screen, or one outside the instance, each name
        opens the player's last fight of it, by their unit id there; an
        anon's hover gives its role and class, a trash fight's its time."""
        for shown in (None, self.fights[0]):
            links = _hrefs(self.render(shown=shown), "esolog:player/")
            self.assertIn("esolog:player/6/101", links)  # @me, on a new unit id
            self.assertIn("esolog:player/6/2", links)
            self.assertIn("esolog:player/3/77", links)
        tips = self.tips()
        self.assertTrue(_text(tips["esolog:player/6/11"]).startswith(
            "anon (D, Sorc) in Nahviintaas, pull 1"))
        night = _night()[:1]
        _fights, index_of = _listed(night)
        from gui.instance_render import instance_tooltips
        self.assertTrue(_text(instance_tooltips(night, index_of)["esolog:player/2/2"]).startswith(
            "@tank in Ruined Atronach (trash, 20:05)"))

    def test_a_fight_the_list_does_not_place_gets_no_link(self):
        """index_of None: that pull and the names it would open are drawn
        without a link, a name opening the player's latest placed fight."""
        from gui.instance_render import instance_tooltips, render_instance_html
        wipe, final = self.night[1], self.night[-1]

        def index_of(fight):
            return None if fight is wipe or fight is final else self.index_of(fight)

        page = render_instance_html(self.night, index_of)
        self.assertEqual(_hrefs(page, "esolog:fight/"), ["esolog:fight/4"])
        self.assertIn("Pulls: pull 1 (wipe 62%) · pull 2 (kill)", _text(page))
        links = _hrefs(page, "esolog:player/")
        self.assertIn("esolog:player/5/1", links)  # @me's latest placed fight
        self.assertNotIn("esolog:player/6/101", links)
        self.assertNotIn("esolog:player/3/77", links)  # @passerby's one fight
        self.assertIn("@passerby", _text(page))
        tips = instance_tooltips(self.night, index_of)
        self.assertEqual([href for href in tips if href.startswith("esolog:fight/")],
                         ["esolog:fight/4"])
        page = render_instance_html(self.night, lambda fight: None)
        self.assertEqual(_hrefs(page, "esolog:fight/") + _hrefs(page, "esolog:player/"), [])

    def test_every_link_has_its_hover(self):
        """Each pull, name, the copy link and each Misfortune has hover text;
        a pull's names its boss, verdict, time, start and deaths."""
        from gui.instance_render import INSTANCE_COPY_HREF
        page = self.render(shown=self.night[2])
        tips = self.tips(shown=self.night[2])
        hrefs = set(re.findall(r'href="(esolog:(?:fight|player|instance)/[^"]*)"', page))
        self.assertEqual(hrefs, set(tips))
        self.assertIn(INSTANCE_COPY_HREF, tips)
        self.assertEqual(_text(tips["esolog:fight/3"]).split(" Click")[0],
                         "Lokkestiiz, pull 1: Wipe 62% · 2:00 · 20:10:00 · 3 deaths")

    def test_a_pull_the_log_cut_in_two_says_so(self):
        """A wipe, then a kill the log cut in two: the second pull links to
        its last fight, and says it was cut; a name opening that fight
        names its part."""
        from gui.instance_render import instance_tooltips, render_instance_html
        wipe = _fight("Lokkestiiz", "2026-11-04 20:55:00", 100.0,
                      _pull("wipe", 70.0, "Lokkestiiz", -300.0, -200.0), players=_roster())
        first = _fight("Lokkestiiz", "2026-11-04 21:00:00", 120.0,
                       _pull("unseen", 40.0, "Lokkestiiz", 0.0, 120.0), players=_roster())
        second = _fight("Lokkestiiz", "2026-11-04 21:02:10", 60.0,
                        _pull("kill", 0.0, "Lokkestiiz", 130.0, 190.0), players=_roster())
        first.pull["cut"], second.pull["continues"] = True, True
        block = [wipe, first, second]
        _fights, index_of = _listed(block)
        self.assertIn("Pulls: pull 1 (wipe 70%) · pull 2 (kill)",
                      _text(render_instance_html(block, index_of)))
        tips = instance_tooltips(block, index_of)
        self.assertIn("The log cut it into 2 fights; this shows the last", tips["esolog:fight/4"])
        self.assertIn("in Lokkestiiz, pull 2, part 2 of 2", _text(tips["esolog:player/4/2"]))

    def test_the_run_anchors_count_every_run_in_block_order(self):
        """Each run's row holds its anchor, numbered from 1 over every run of
        pull_outcome.runs, one pull or more, as the window matches a list
        row's run to it; on the pulls' count, never on a link, which Qt
        would leave its first letter alone (probed)."""
        from gui.instance_render import run_anchor
        from pull_outcome import run_name, runs
        page = self.render()
        anchors = re.findall(r"<a name='([^']+)'></a>(\d+)</td>", page)
        self.assertEqual(anchors, [(run_anchor(n), str(len(run)))
                                   for n, run in enumerate(runs(self.night), 1)])
        self.assertEqual(run_anchor(2), "run-2")
        rows = page.split("<tr>")
        for n, run in enumerate(runs(self.night), 1):
            row = next(row for row in rows if f"<a name='{run_anchor(n)}'>" in row)
            self.assertIn(f"<b>{run_name(run)}</b>", row)
        self.assertNotRegex(page, r"<a name='[^']+' href")

    def test_the_hrefs_read_back(self):
        from gui.instance_render import (
            FIGHT_HREF,
            INSTANCE_COPY_HREF,
            PLAYER_HREF,
            fight_from_href,
            fight_href,
            player_from_href,
            player_href,
        )
        self.assertEqual((FIGHT_HREF, PLAYER_HREF, INSTANCE_COPY_HREF),
                         ("esolog:fight/", "esolog:player/", "esolog:instance/copy"))
        self.assertEqual(fight_from_href(fight_href(12)), 12)
        self.assertEqual(player_from_href(player_href(3, "45")), (3, "45"))
        for bad in ("esolog:fight/", "esolog:fight/x", "esolog:fight/²", "esolog:fight/-1",
                    "esolog:fightdeaths/", "esolog:build/3", "", None):
            self.assertIsNone(fight_from_href(bad))
        for bad in ("esolog:player/3", "esolog:player/3/", "esolog:player//4",
                    "esolog:player/x/4", "esolog:fight/3", None):
            self.assertIsNone(player_from_href(bad))


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestEntriesUnchanged(unittest.TestCase):

    def test_the_block_is_left_as_it_was(self):
        """The engine's thread updates entries in place: the page and its
        hover texts only read them."""
        from gui.instance_render import instance_tooltips, render_instance_html
        from gui.name_mask import NameMask
        night = _night()
        night[-1].banner_path = "banner.png"
        night[0].misfortunes = copy.deepcopy(MISFORTUNES)
        _fights, index_of = _listed(night)

        def state():
            return [{slot: getattr(fight, slot) for slot in fight.__slots__} for fight in night]

        before = copy.deepcopy(state())
        history = _History([{"boss": "Lokkestiiz", "start_s": 10.0, "group_boss_dps": 640100.0,
                             "handles": ["@me", "@tank", "@heal", "@passerby"] + _OTHERS}])
        names = NameMask.for_entries(night, True)
        render_instance_html(night, index_of, shown=night[2], dark=True, names=names,
                             opens_list=True, fight_index=history)
        instance_tooltips(night, index_of, shown=night[2], names=names)
        self.assertEqual(state(), before)


if __name__ == "__main__":
    unittest.main()
