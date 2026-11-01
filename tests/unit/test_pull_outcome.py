#!/usr/bin/env python3
"""Kill or wipe, time dead and a boss's pulls in a row (pull_outcome,
issues #168 and #169): the rules and the texts, without the engine."""

import unittest

import pull_outcome as po


class _Mask:
    """A stand-in for gui.name_mask.NameMask: hides every @handle but
    @me."""

    def text(self, name):
        name = str(name or "")
        return "@▒▒" if name.startswith("@") and name != "@me" else name


def _pull(outcome=None, health_left=50.0, boss="Lord Falgravn", bosses=None, start_s=0.0,
          end_s=100.0, continues=False, **facts):
    record = {"boss": boss, "bosses": bosses or [boss], "health_left": health_left,
              "health_start": 100.0, "health": {boss: [100.0, health_left]},
              "boss_died": False, "players": 12, "dead_at_end": [], "local_dead_at_end": False,
              "start_s": start_s, "end_s": end_s, "zone": "1196|VETERAN", "continues": continues}
    record.update(facts)
    record["outcome"] = outcome or po.verdict(record)
    return record


class _Entry:
    def __init__(self, pull=None, recaps=(), time_dead=None, duration_s=100.0, deaths=None):
        self.pull = pull
        self.death_recaps = list(recaps)
        self.time_dead = time_dead or {}
        self.duration_s = duration_s
        self.deaths = len(self.death_recaps) if deaths is None else deaths


def _recap(unit_id, name, ms, ability, killer):
    return {"unit_id": unit_id, "name": name, "time_ms": ms, "ability": ability, "killer": killer}


class TestVerdict(unittest.TestCase):

    def test_the_boss_dying_is_a_kill_whoever_died(self):
        self.assertEqual(po.verdict(_pull(boss_died=True, dead_at_end=list("abcdefgh"))), po.KILL)

    def test_half_the_group_dead_at_the_end_is_a_wipe(self):
        self.assertEqual(po.verdict(_pull(dead_at_end=list("abcdef"))), po.WIPE)
        self.assertEqual(po.verdict(_pull(dead_at_end=list("abcde"))), po.LEFT)

    def test_a_solo_death_is_a_wipe(self):
        self.assertEqual(po.verdict(_pull(players=1, dead_at_end=["a"])), po.WIPE)

    def test_the_writer_down_at_the_end_is_lost_sight(self):
        self.assertEqual(po.verdict(_pull(dead_at_end=["me"], local_dead_at_end=True)), po.UNSEEN)

    def test_a_boss_under_two_percent_with_the_group_standing_died_out_of_sight(self):
        self.assertEqual(po.verdict(_pull(health_left=0.2)), po.KILL)
        # Not when half the group lay dead: that was a wipe at the line
        self.assertEqual(po.verdict(_pull(health_left=0.2, dead_at_end=list("abcdef"))), po.WIPE)
        self.assertEqual(po.verdict(_pull(health_left=2.5)), po.LEFT)

    def test_a_late_death_can_turn_the_verdict(self):
        pull = _pull(dead_at_end=list("abcde"))
        self.assertEqual(pull["outcome"], po.LEFT)
        po.note_late_death(pull, "f", local=False)
        self.assertEqual(pull["outcome"], po.WIPE)
        self.assertEqual(pull["dead_at_end"], list("abcdef"))


class TestPullRecord(unittest.TestCase):

    def test_the_boss_is_the_named_unit_with_the_most_damage(self):
        health = po.BossHealth()
        health.note("70", "287485/287485")
        health.note("70", "143742/287485")
        health.note("71", "100/100")
        record = po.pull_record(
            [("70", "Lord Falgravn", 3000, False), ("71", "", 5000, False),
             ("72", "Lieutenant Njordal", 1000, False), ("73", "Sea Adder", 50, False)],
            health, False, players=12, dead_at_end=[], local_dead_at_end=False)
        self.assertEqual(record["boss"], "Lord Falgravn")
        # Njordal has 10% or more of the boss damage, the Sea Adder not
        self.assertEqual(record["bosses"], ["Lord Falgravn", "Lieutenant Njordal"])
        self.assertAlmostEqual(record["health_left"], 50.0, places=2)
        self.assertEqual(record["health_start"], 100.0)
        self.assertEqual(record["outcome"], po.LEFT)

    def test_no_named_boss_no_pull(self):
        self.assertIsNone(po.pull_record([("71", "", 5000, False)], po.BossHealth(), False,
                                         players=4, dead_at_end=[], local_dead_at_end=False))

    def test_zero_health_or_the_trial_end_is_a_kill(self):
        health = po.BossHealth()
        health.note("70", "0/287485")
        record = po.pull_record([("70", "Lokkestiiz", 900, False)], health, False,
                                players=12, dead_at_end=[], local_dead_at_end=False)
        self.assertEqual(record["outcome"], po.KILL)
        record = po.pull_record([("70", "Lokkestiiz", 900, False)], po.BossHealth(), True,
                                players=12, dead_at_end=[], local_dead_at_end=False)
        self.assertEqual(record["outcome"], po.KILL)


class TestContinues(unittest.TestCase):

    def test_a_fight_starting_where_the_last_pull_stopped_carries_it_on(self):
        before = _pull(health_left=63.0, end_s=100.0, local_dead_at_end=True, dead_at_end=["me"])
        after = _pull(health_left=48.0, start_s=112.0)
        after["health"] = {"Lord Falgravn": [61.0, 48.0]}
        self.assertTrue(po.continues(before, after))

    def test_what_breaks_it(self):
        before = _pull(health_left=63.0, end_s=100.0)
        after = _pull(start_s=112.0)
        after["health"] = {"Lord Falgravn": [100.0, 40.0]}
        self.assertFalse(po.continues(before, after))  # the boss was reset
        after["health"] = {"Lord Falgravn": [50.0, 40.0]}
        self.assertFalse(po.continues(before, after))  # not where it stopped
        after["health"] = {"Lord Falgravn": [61.0, 40.0]}
        after["start_s"] = 200.0
        self.assertFalse(po.continues(before, after))  # too long after
        after["start_s"] = 112.0
        after["zone"] = "1196|NORMAL"
        self.assertFalse(po.continues(before, after))
        after["zone"] = before["zone"]
        self.assertFalse(po.continues(_pull(po.KILL, end_s=100.0), after))
        self.assertTrue(po.continues(before, after))


class TestTimeDead(unittest.TestCase):

    def test_a_revival_closes_the_span(self):
        dead = po.TimeDead()
        dead.died("1", 10_000)
        dead.alive("1", 10_500)  # the dying line's own state
        self.assertIn("1", dead.since)
        dead.alive("1", 25_000)
        self.assertEqual(dead.totals(60_000), {"1": 15_000})

    def test_the_end_closes_what_is_open_and_says_who_was_dead(self):
        dead = po.TimeDead()
        dead.died("1", 10_000)
        dead.died("2", 50_000)
        dead.alive("1", 20_000)
        dead.end(60_000)
        self.assertEqual(dead.dead_at_end(), frozenset({"2"}))
        self.assertEqual(dead.totals(60_000), {"1": 10_000, "2": 10_000})

    def test_a_fight_the_game_cut_in_two_reopens_the_dead(self):
        dead = po.TimeDead()
        dead.died("2", 50_000)
        dead.end(60_000)
        dead.resume()
        self.assertIsNone(dead.at_end)
        dead.alive("2", 70_000)
        self.assertEqual(dead.totals(90_000), {"2": 20_000})

    def test_a_death_before_the_pull_counts_from_the_pull(self):
        dead = po.TimeDead()
        dead.died("1", 5_000)  # fell before the pull
        dead.begin(10_000)
        dead.end(130_000)
        self.assertEqual(dead.totals(130_000), {"1": 120_000})

    def test_a_late_death_stays_dead_should_the_fight_carry_on(self):
        dead = po.TimeDead()
        dead.end(60_000)
        dead.late_death("3", 60_400)
        self.assertEqual(dead.dead_at_end(), frozenset({"3"}))
        dead.resume()
        dead.end(80_000)
        self.assertEqual(dead.dead_at_end(), frozenset({"3"}))

    def test_the_dead_carried_from_the_last_fight(self):
        dead = po.TimeDead()
        dead.begin(100_000, carried={"4", "5"})
        self.assertTrue(dead.watches("4"))
        dead.alive("4", 103_000)  # back up: no 1 s wait, the death was long ago
        dead.end(160_000)
        self.assertEqual(dead.carried_at_end, frozenset({"5"}))
        self.assertEqual(dead.totals(160_000), {})
        self.assertEqual(dead.totals(160_000, carried=True), {"4": 3_000, "5": 60_000})

    def test_a_carried_player_who_dies_again_is_dead_from_then(self):
        dead = po.TimeDead()
        dead.begin(100_000, carried={"4"})
        dead.died("4", 110_000)
        self.assertNotIn("4", dead.carried)
        dead.end(120_000)
        self.assertEqual(dead.dead_at_end(), frozenset({"4"}))


class TestTexts(unittest.TestCase):

    def test_health(self):
        self.assertEqual(po.health_text(62.4), "62%")
        self.assertEqual(po.health_text(8.14), "8.1%")
        self.assertEqual(po.health_text(0.04), "0.04%")
        self.assertEqual(po.health_text(None), "")

    def test_outcome_words(self):
        self.assertEqual(po.outcome_text(_pull(po.KILL)), "Kill")
        self.assertEqual(po.outcome_text(_pull(po.WIPE, 62.4)), "Wipe 62%")
        self.assertEqual(po.outcome_text(_pull(po.LEFT, 84.0)), "Left 84%")
        self.assertEqual(po.outcome_text(_pull(po.UNSEEN, 31.0, went_on=True)),
                         "Lost sight 31%, group went on")
        self.assertEqual(po.outcome_text(_pull(po.UNSEEN, 63.0, cut=True)), "Cut 63%")
        self.assertEqual(po.outcome_text(None), "")
        # Another unit took the most damage: the row is named after it
        self.assertEqual(po.outcome_text(_pull(po.WIPE, 62.4), title="Lieutenant Njordal"),
                         "Wipe, Lord Falgravn 62%")

    def test_clocks(self):
        # One format with the fight's duration in the list
        self.assertEqual(po.clock(48.2), "48s")
        self.assertEqual(po.clock(72), "1:12")
        self.assertEqual(po.mmss(98.9), "1:38")
        self.assertEqual(po.at_clock(102_500), "1:42")

    def test_a_late_end_trial_is_a_kill(self):
        pull = _pull(dead_at_end=list("abcdef"))
        self.assertEqual(pull["outcome"], po.WIPE)
        po.note_trial_end(pull)
        self.assertEqual(pull["outcome"], po.KILL)


class TestRuns(unittest.TestCase):

    def test_pulls_join_a_cut_fight_and_runs_end_at_a_kill(self):
        a = _Entry(_pull(po.UNSEEN, 63.0, end_s=100.0))
        b = _Entry(_pull(po.WIPE, 48.0, start_s=112.0, end_s=200.0, continues=True))
        trash = _Entry(None)
        c = _Entry(_pull(po.KILL, 0.0, start_s=250.0, end_s=400.0))
        d = _Entry(_pull(po.WIPE, 90.0, boss="Captain Vrol", start_s=500.0))
        self.assertEqual(po.pulls([a, b, trash, c, d]), [[a, b], [c], [d]])
        self.assertEqual(po.runs([a, b, trash, c, d]), [[[a, b], [c]], [[d]]])

    def test_encounters_whose_top_unit_alternates_stay_one_run(self):
        both = ["Lylanar", "Turlassil"]
        a = _Entry(_pull(po.WIPE, 40.0, boss="Lylanar", bosses=both))
        b = _Entry(_pull(po.WIPE, 30.0, boss="Turlassil", bosses=both[::-1]))
        c = _Entry(_pull(po.WIPE, 35.0, boss="Turlassil", bosses=both[::-1]))
        self.assertEqual(len(po.runs([a, b, c])), 1)
        self.assertEqual(po.run_name(po.runs([a, b, c])[0]), "Turlassil and Lylanar")

    def test_an_add_on_top_once_does_not_name_the_run(self):
        both = ["Lord Falgravn", "Lieutenant Njordal"]
        fights = [_Entry(_pull(po.WIPE, 80.0, bosses=both)) for _ in range(11)]
        fights.insert(3, _Entry(_pull(po.WIPE, 85.0, boss="Lieutenant Njordal", bosses=both[::-1])))
        self.assertEqual(po.run_name(po.runs(fights)[0]), "Lord Falgravn")

    def test_mark_context(self):
        a = _Entry(_pull(po.UNSEEN, 63.0))
        b = _Entry(_pull(po.UNSEEN, 30.0, continues=True))
        c = _Entry(_pull(po.WIPE, 90.0, boss="Captain Vrol"))
        self.assertEqual(po.mark_context([a, b, c]), [a, b])
        self.assertEqual((a.pull["cut"], a.pull["went_on"]), (True, False))
        # Falgravn never came back and another boss was pulled after
        self.assertEqual((b.pull["cut"], b.pull["went_on"]), (False, True))
        self.assertEqual((c.pull["cut"], c.pull["went_on"]), (False, False))
        self.assertEqual(po.mark_context([a, b, c]), [])  # nothing changed
        # The boss came back: the group did not go on after all
        d = _Entry(_pull(po.WIPE, 70.0))
        self.assertEqual(po.mark_context([a, b, c, d]), [b])
        self.assertFalse(b.pull["went_on"])

    def test_went_on_is_said_of_lost_sight_only(self):
        wipe = _Entry(_pull(po.WIPE, 62.0))
        left = _Entry(_pull(po.LEFT, 84.0, boss="Captain Vrol"))
        po.mark_context([wipe, left, _Entry(_pull(po.KILL, 0.0, boss="Yandir the Butcher"))])
        self.assertFalse(wipe.pull["went_on"])
        self.assertFalse(left.pull["went_on"])

    def test_summary(self):
        pulls = [_Entry(_pull(po.WIPE, h, start_s=i * 100.0, end_s=i * 100.0 + 52.0))
                 for i, h in enumerate((84.0, 83.0, 86.0, 81.0, 62.0))]
        run = po.runs(pulls)[0]
        self.assertEqual(po.run_summary(run),
                         "Lord Falgravn: 5 pulls, best 62%, 4 wipes at 80 to 90%, 48s between pulls")
        pulls.append(_Entry(_pull(po.KILL, 0.0, start_s=548.0, end_s=700.0)))
        self.assertEqual(po.run_summary(po.runs(pulls)[0]),
                         "Lord Falgravn: 6 pulls, killed on pull 6, 4 wipes at 80 to 90%, "
                         "48s between pulls")

    def test_details(self):
        first = _Entry(_pull(po.WIPE, 80.0), [
            _recap("1", "@me", 5000, "Grievous Pulse", "Lord Falgravn"),
            _recap("2", "@other", 9000, "Sanguine Grasp", "Lieutenant Njordal")],
            time_dead={"1": 90_000, "2": 40_000})
        second = _Entry(_pull(po.WIPE, 70.0), [
            _recap("2", "@other", 3000, "Grievous Pulse", "Lord Falgravn")],
            time_dead={"2": 60_000})
        lines = po.run_details(po.runs([first, second])[0], _Mask())
        self.assertEqual(lines[0], "First deaths: Grievous Pulse 2")
        self.assertEqual(lines[1], "Killers: Grievous Pulse 2, Sanguine Grasp (Lieutenant Njordal) 1;"
                                   " 67% by Lord Falgravn")
        self.assertEqual(lines[2], "Most time dead: @▒▒ 1:40, @me 1:30")

    def test_players_with_no_name_stay_apart(self):
        fight = _Entry(_pull(po.WIPE, 80.0), [
            _recap("5", "anon", 5000, "Claw", "Lord Falgravn"),
            _recap("6", "anon", 6000, "Claw", "Lord Falgravn")],
            time_dead={"5": 90_000, "6": 40_000})
        fight.players = [{"unit_id": "5", "role": "T", "class_abbr": "DK"}]
        lines = po.run_details([[fight]], _Mask())
        self.assertEqual(lines[-1], "Most time dead: anon (T, DK) 1:30, anon 40s")


class TestFightTexts(unittest.TestCase):

    def test_first_death_line(self):
        entry = _Entry(_pull(po.WIPE, 62.0), [
            _recap("2", "@other", 102_000, "Grievous Pulse", "Lord Falgravn"),
            _recap("1", "@me", 150_000, "Claw", "Lord Falgravn")], duration_s=174.0, deaths=14)
        self.assertEqual(po.first_death_text(entry, _Mask()),
                         "First death: @▒▒ to Grievous Pulse (Lord Falgravn) at 1:42 · 14 deaths"
                         " · the pull ended 1:12 later")
        entry.pull = _pull(po.KILL, 0.0)
        self.assertEqual(po.first_death_text(entry),
                         "First death: @other to Grievous Pulse (Lord Falgravn) at 1:42 · 14 deaths")
        self.assertEqual(po.first_death_text(_Entry(_pull(po.KILL))), "")

    def test_time_dead_on_the_row_and_in_the_hover(self):
        entry = _Entry(time_dead={"1": 92_000, "2": 5_000}, duration_s=310.0)
        self.assertEqual(po.dead_row_text(entry, "1"), "dead 1:32")
        self.assertEqual(po.dead_row_text(entry, "2"), "")  # under a tenth of the fight
        self.assertEqual(po.dead_hover_text(entry, "1"), "Dead for 1:32 of 5:10 (30%)")
        self.assertEqual(po.dead_hover_text(entry, "3"), "")


if __name__ == "__main__":
    unittest.main()
