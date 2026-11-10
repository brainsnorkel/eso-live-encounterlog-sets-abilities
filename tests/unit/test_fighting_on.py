#!/usr/bin/env python3
"""The group fighting on after the logging player's END_COMBAT counts in
the fight that ended (issue #162, part 2; waiting_hits): its hits on that
fight's enemies, from END_COMBAT while each comes within FIGHT_ON_MS of the
last, and the fight's entry is built again once the group stops. Combat
beginning again while the group is still hitting an enemy it was fighting
as the fight ended carries the fight on, however long after.

The shapes follow the real logs: the logging player dies or steps out of
combat while the rest of the group fights on (250 fights over 395 split
logs, a third of a Hel Ra Citadel boss fight's damage in one).
"""

import unittest

from esolog_tail import EnemyInfo
from tests.unit.test_hits_before_line import (
    BOSS_HITS,
    STRIKE,
    TRASH_FIGHT,
    Engine,
    _hit_record,
    _player,
    _unit,
    add,
    boss,
    builds,
    died_xp,
    fight,
    group_damage,
    hit,
    row,
    trash,
)
from waiting_hits import FIGHT_ON_MS, WaitingHits, take_damage_figures


def heal(ts, source, target, value):
    return (f"{ts},COMBAT_EVENT,HEAL,MAGIC,1,{value},0,{ts},22250,"
            f"{_player(source)},{_player(target)}")


def player_died(ts, player):
    """Killed by the add, whose health no pull reads."""
    return (f"{ts},COMBAT_EVENT,DIED,PHYSICAL,1,0,0,{ts},12345,"
            f"{add()},{_player(player, 0)}")


def fight_events(engine):
    """The fight events the frontends were sent, in order."""
    return [event[0] for event in engine.listener.events
            if event[0] in ('fight_completed', 'fight_updated')]


def regen(ts):
    """A line with nothing in it for the fight: the log goes on."""
    return f"{ts},HEALTH_REGEN,50,{_player(1)}"


# The trash fight (10 s to 20 s) and the group fighting on its trash after
# it: 40,000 at 21 s and 30,000 at 23 s
FOUGHT_ON = (hit(21000, 2, 40000, trash(860000)), hit(23000, 3, 30000, trash(830000)))
# The boss fight, well after
LATER_BOSS = fight(40000, 50000, hit(41000, 2, 100000, boss(900000)),
                   hit(49000, 3, 100000, boss(800000)))


class TestFoughtOn(unittest.TestCase):

    def test_the_group_fighting_on_counts_in_the_fight(self):
        engine = Engine().feed([*TRASH_FIGHT, *FOUGHT_ON, *LATER_BOSS])
        trash_fight, boss_fight = engine.fights
        self.assertEqual(group_damage(trash_fight), 170000)
        # The fight's clock stays the log's; the dps time runs to the last hit
        self.assertAlmostEqual(trash_fight.duration_s, 10.0)
        self.assertAlmostEqual(trash_fight.dps_time_s, 12.0)
        self.assertAlmostEqual(trash_fight.group_dps, 170000 / 12.0)
        self.assertEqual(row(trash_fight, '@templar')['damage']['total'], 90000)
        self.assertEqual(group_damage(boss_fight), 200000)
        # The trash fight is sent, then sent again once the group stopped
        self.assertEqual(fight_events(engine),
                         ['fight_completed', 'fight_updated', 'fight_completed'])

    def test_the_entry_is_the_one_frontends_hold(self):
        engine = Engine().feed([*TRASH_FIGHT, *FOUGHT_ON])
        sent = engine.fights[0]
        engine.feed([regen(30000)])
        self.assertIs(engine.fights[0], sent)
        self.assertEqual(group_damage(sent), 170000)

    def test_without_it_the_figures_are_the_fights_own(self):
        trash_fight, _boss = Engine().feed([*TRASH_FIGHT, *LATER_BOSS]).fights
        self.assertEqual(group_damage(trash_fight), 100000)
        self.assertAlmostEqual(trash_fight.dps_time_s, 4.0)

    def test_the_wait(self):
        """A hit FIGHT_ON_MS after the last still fights on; a moment later
        the group has stopped, and the hit waits as any other."""
        on_time = Engine().feed([*TRASH_FIGHT, hit(21000, 2, 40000, trash(860000)),
                                 hit(21000 + FIGHT_ON_MS, 3, 30000, trash(830000)),
                                 *LATER_BOSS]).fights[0]
        self.assertEqual(group_damage(on_time), 170000)
        late = Engine().feed([*TRASH_FIGHT, hit(21000, 2, 40000, trash(860000)),
                              hit(21001 + FIGHT_ON_MS, 3, 30000, trash(830000)),
                              *LATER_BOSS]).fights[0]
        self.assertEqual(group_damage(late), 140000)

    def test_the_wait_starts_at_end_combat(self):
        engine = Engine().feed([*TRASH_FIGHT, hit(20000 + FIGHT_ON_MS + 1, 2, 40000,
                                                  trash(860000)), *LATER_BOSS])
        self.assertEqual(group_damage(engine.fights[0]), 100000)
        self.assertEqual(fight_events(engine),
                         ['fight_completed', 'fight_completed'])

    def test_a_damage_over_time_tick_fights_on(self):
        entry = Engine().feed([*TRASH_FIGHT, hit(21000, 2, 4000, trash(890000), 'DOT_TICK'),
                               hit(23000, 2, 4000, trash(886000), 'DOT_TICK_CRITICAL'),
                               *LATER_BOSS]).fights[0]
        self.assertEqual(group_damage(entry), 108000)

    def test_hits_on_other_enemies_wait_for_the_next_line(self):
        """The boss hit while the group finishes the trash is the boss
        fight's opening (part 1), never the trash fight's."""
        lines = [*TRASH_FIGHT, hit(21000, 2, 40000, trash(860000)),
                 hit(22000, 3, 30000, boss(970000)),
                 *fight(28000, 41000, *BOSS_HITS)]
        trash_fight, boss_fight = Engine().feed(lines).fights
        self.assertEqual(group_damage(trash_fight), 140000)
        self.assertEqual(group_damage(boss_fight), 230000)

    def test_an_enemy_of_the_fight_before_is_not_the_next_fights(self):
        """Hit after the group stopped, the trash is still the trash fight's
        enemy: in neither fight, as before part 2."""
        lines = [*TRASH_FIGHT, hit(21000, 2, 40000, trash(860000)),
                 hit(26000, 3, 30000, trash(830000)),
                 *fight(28000, 41000, *BOSS_HITS)]
        trash_fight, boss_fight = Engine().feed(lines).fights
        self.assertEqual(group_damage(trash_fight), 140000)
        self.assertEqual(group_damage(boss_fight), 200000)

    def test_a_unit_id_handed_out_again_is_another_enemy(self):
        lines = [*TRASH_FIGHT, '20500,UNIT_REMOVED,71',
                 ('20600,UNIT_ADDED,71,MONSTER,F,0,50000,F,0,0,"Reef Guardian","",0,50,160,0,'
                  'HOSTILE,F'),
                 hit(21000, 2, 40000, _unit(71, 10000, 50000)), *LATER_BOSS]
        self.assertEqual(group_damage(Engine().feed(lines).fights[0]), 100000)


class TestWhenTheGroupStops(unittest.TestCase):
    """The fight's entry takes the hits once the group has stopped: the
    first log line past the wait, the next fight's line, a zone change, a
    new session, or the log's end."""

    def test_a_line_past_the_wait(self):
        engine = Engine().feed([*TRASH_FIGHT, *FOUGHT_ON])
        self.assertEqual(group_damage(engine.fights[0]), 100000)
        engine.feed([regen(23000 + FIGHT_ON_MS)])
        self.assertEqual(group_damage(engine.fights[0]), 100000)
        engine.feed([regen(23001 + FIGHT_ON_MS)])
        self.assertEqual(group_damage(engine.fights[0]), 170000)

    def test_the_next_fights_line(self):
        """A new fight's line: the trash died, so it carries nothing on."""
        engine = Engine().feed([*TRASH_FIGHT, hit(21000, 2, 40000, trash(860000)),
                                hit(23000, 3, 860000, trash(0)), died_xp(23001, 3, trash(0)),
                                '24000,BEGIN_COMBAT'])
        self.assertEqual(group_damage(engine.fights[0]), 1000000)

    def test_a_zone_change(self):
        engine = Engine().feed([*TRASH_FIGHT, *FOUGHT_ON,
                                '24000,ZONE_CHANGED,1000,"Craglorn",NONE'])
        self.assertEqual(group_damage(engine.fights[0]), 170000)

    def test_a_new_session(self):
        engine = Engine().feed([*TRASH_FIGHT, *FOUGHT_ON,
                                '5,BEGIN_LOG,1759700000000,15,"NA Megaserver","en","eso.live.12.1"'])
        entry = engine.fights[0]
        self.assertEqual(group_damage(entry), 170000)
        # Read with the session's own times
        self.assertEqual(entry.timestamp, Engine().feed(TRASH_FIGHT).fights[0].timestamp)

    def test_the_logs_end(self):
        engine = Engine().feed([*TRASH_FIGHT, *FOUGHT_ON])
        engine.analyzer.finish()
        self.assertEqual(group_damage(engine.fights[0]), 170000)
        # Once
        engine.analyzer.finish()
        self.assertEqual(fight_events(engine).count('fight_updated'), 1)

    def test_a_replay_ends_it(self):
        import tempfile
        from pathlib import Path

        from esolog_tail import ESOLogAnalyzer, FightHistory
        from review_load import replay_log
        from tests.unit.test_hits_before_line import BASE
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Encounter.log'
            path.write_text('\n'.join([*BASE, *TRASH_FIGHT, *FOUGHT_ON]) + '\n', encoding='utf-8')
            analyzer = ESOLogAnalyzer()
            analyzer.fight_history = FightHistory()
            _shown, fights = replay_log(analyzer, path)
        self.assertEqual(group_damage(fights[0]), 170000)


class TestWhatStays(unittest.TestCase):
    """Only the figures the hits decide change: everything else in the
    entry stays as END_COMBAT left it."""

    def test_deaths_heals_and_newcomers_after_the_end(self):
        newcomer = ('22000,UNIT_ADDED,4,PLAYER,F,4,0,F,1,1,"Late Comer","@late",1004,50,1800,0,'
                    'PLAYER_ALLY,T')
        lines = [*TRASH_FIGHT, hit(21000, 2, 40000, trash(860000)), newcomer,
                 *builds(22001, 4), heal(22100, 1, 2, 9000), player_died(22500, 3),
                 hit(23000, 4, 30000, trash(830000)), *LATER_BOSS]
        baseline = Engine().feed([*TRASH_FIGHT, *LATER_BOSS]).fights[0]
        entry = Engine().feed(lines).fights[0]
        self.assertEqual(entry.deaths, 0)
        self.assertEqual(entry.death_recaps, [])
        self.assertEqual([p['name'] for p in entry.players if not p.get('companion')],
                         ['@templar', '@third', '@brainsnorkel'])
        self.assertEqual(row(entry, '@brainsnorkel')['healing'],
                         row(baseline, '@brainsnorkel')['healing'])
        # The newcomer's hit is the group's, in the total, with no row
        self.assertEqual(group_damage(entry), 170000)
        for slot in ('duration_s', 'timestamp', 'tracked', 'buff_summary', 'opener',
                     'player_names', 'time_dead'):
            self.assertEqual(getattr(entry, slot), getattr(baseline, slot), slot)

    def test_the_build_again_changes_nothing_else(self):
        """Built again at the next fight's line, the fight leaves the
        trackers alone: a cast written over that line (two BEGIN_CAST lines
        of one cast) is still one cast begun before the next fight."""
        cast = [f"23900,BEGIN_CAST,0,F,777,{STRIKE},{_player(2)},{boss()}",
                '24000,BEGIN_COMBAT', *builds(24001, 1, 2, 3),
                f"24100,BEGIN_CAST,0,F,777,{STRIKE},{_player(2)},{boss()}",
                hit(25000, 2, 100000, boss(900000)), '34000,END_COMBAT']
        fought_on = Engine().feed([*TRASH_FIGHT, hit(21000, 2, 40000, trash(860000)), *cast])
        plain = Engine().feed([*TRASH_FIGHT, *cast])
        self.assertEqual(group_damage(fought_on.fights[0]), 140000)
        self.assertEqual(row(fought_on.fights[1], '@templar')['casts'],
                         row(plain.fights[1], '@templar')['casts'])

    def test_nothing_is_noted_for_the_session_again(self):
        """A taunt while the group fought on is not the fight's: the build
        findings of the session (build_issues) do not take it."""
        taunt = (f"21500,COMBAT_EVENT,TAUNTED,GENERIC,0,0,0,21500,{STRIKE},"
                 f"{_player(3)},{trash(860000)}")
        engine = Engine().feed([*TRASH_FIGHT, hit(21000, 2, 40000, trash(860000)), taunt,
                                *LATER_BOSS])
        self.assertEqual(group_damage(engine.fights[0]), 140000)
        analyzer = engine.analyzer
        self.assertFalse(analyzer.build_issues.has_taunted(analyzer._scribing_player_key('3')))

    def test_take_damage_figures_alone(self):
        from fight_history import FightHistoryEntry
        sent, rebuilt = FightHistoryEntry(), FightHistoryEntry()
        sent.deaths, rebuilt.deaths = 1, 3
        sent.group_dps, rebuilt.group_dps = 1000.0, 1200.0
        sent.banner_path = 'banner.png'
        sent.players = [{'unit_id': '1', 'dps': 500, 'healing': 10, 'role': 'Healer'},
                        {'unit_id': '2', 'dps': 500, 'healing': 0, 'role': 'DPS'}]
        rebuilt.players = [{'unit_id': '2', 'dps': 900, 'healing': 99, 'role': 'Tank'},
                           {'unit_id': '1', 'dps': 300, 'healing': 99, 'role': 'DPS'},
                           {'unit_id': '4', 'dps': 1, 'healing': 0, 'role': 'DPS'}]
        rows = sent.players
        take_damage_figures(sent, rebuilt)
        self.assertEqual((sent.deaths, sent.group_dps, sent.banner_path), (1, 1200.0, 'banner.png'))
        self.assertEqual(sent.players, [{'unit_id': '2', 'dps': 900, 'healing': 0, 'role': 'DPS'},
                                        {'unit_id': '1', 'dps': 300, 'healing': 10,
                                         'role': 'Healer'}])
        # The same rows, which the engine holds for a mastery found later,
        # in a new list
        self.assertIs(sent.players[0], rows[1])
        self.assertIs(sent.players[1], rows[0])
        self.assertIsNot(sent.players, rows)

    def test_a_mastery_found_later_reaches_the_row(self):
        """The engine keeps each row for a mastery found later in the
        session (_backfill_mastery): the row fought on is still that one."""
        engine = Engine().feed([*TRASH_FIGHT, *FOUGHT_ON, *LATER_BOSS])
        entry = engine.fights[0]
        held = [row for fight, row in engine.analyzer._mastery_rows.get(
            engine.analyzer._mastery_key(engine.analyzer.current_encounter.players['2']), ())
            if fight is entry]
        self.assertEqual(len(held), 1)
        self.assertIs(held[0], row(entry, '@templar'))


class TestThePull(unittest.TestCase):

    def test_a_boss_the_group_killed_after_the_logging_player_fell(self):
        """The logging player dies, which ends the fight for the log; the
        group kills the boss: Lost sight before part 2, now a kill."""
        lines = [*TRASH_FIGHT,
                 *fight(28000, 41000, *BOSS_HITS, player_died(40000, 1)),
                 hit(42000, 2, 400000, boss(270000)), hit(44000, 3, 270000, boss(0)),
                 died_xp(44001, 3, boss(0)), regen(50000)]
        entry = Engine().feed(lines).fights[1]
        self.assertEqual(entry.pull['outcome'], 'kill')
        self.assertTrue(entry.pull['boss_died'])
        before = Engine().feed([*TRASH_FIGHT,
                                *fight(28000, 41000, *BOSS_HITS, player_died(40000, 1))]).fights[1]
        self.assertEqual(before.pull['outcome'], 'unseen')

    def test_the_pull_is_judged_against_the_one_before(self):
        """The pull read again carries on the pull before it, not itself."""
        lines = [*fight(10000, 20000, hit(19000, 2, 300000, boss(700000)),
                        player_died(19500, 1), player_died(19600, 2), player_died(19700, 3)),
                 *fight(40000, 50000, hit(41000, 2, 100000, boss(680000))),
                 hit(51000, 3, 100000, boss(580000)), regen(60000)]
        _first, second = Engine().feed(lines).fights
        self.assertEqual(group_damage(second), 200000)
        self.assertTrue(second.pull['continues'])


class TestJoined(unittest.TestCase):
    """Combat beginning again while the group is still hitting an enemy it
    was fighting as the fight ended carries the fight on, however long
    after its END_COMBAT (COMBAT_RESUME_MS asks for a second)."""

    def _parts(self, *gap):
        return [*fight(10000, 20000, hit(11000, 2, 100000, boss(900000)),
                       hit(19000, 3, 100000, boss(800000))),
                *gap, '27000,BEGIN_COMBAT', *builds(27001, 1, 2, 3),
                hit(30000, 2, 100000, boss(500000)), '40000,END_COMBAT']

    def test_combat_beginning_again_while_the_group_still_hits(self):
        engine = Engine().feed(self._parts(hit(22000, 2, 100000, boss(700000)),
                                           hit(25000, 3, 100000, boss(600000))))
        (entry,) = engine.fights
        self.assertAlmostEqual(entry.duration_s, 30.0)
        self.assertEqual(group_damage(entry), 500000)
        self.assertEqual(fight_events(engine),
                         ['fight_completed', 'fight_updated'])

    def test_not_after_a_fight_without_a_boss(self):
        """The maintainer's decision (2026-11-11): a boss pull only. Trash
        the group is still finishing as the next combat begins counts in
        its own fight, and the next fight is a fight of its own."""
        lines = [*TRASH_FIGHT, hit(21000, 2, 40000, trash(860000)),
                 hit(23000, 3, 30000, trash(830000)),
                 *fight(24000, 41000, hit(25000, 2, 100000, boss(900000)))]
        trash_fight, boss_fight = Engine().feed(lines).fights
        self.assertEqual(group_damage(trash_fight), 170000)
        self.assertAlmostEqual(trash_fight.duration_s, 10.0)
        self.assertEqual(group_damage(boss_fight), 100000)

    def test_not_once_the_group_stopped(self):
        fights = Engine().feed(self._parts(hit(22000, 2, 100000, boss(700000)))).fights
        self.assertEqual(len(fights), 2)
        self.assertEqual(group_damage(fights[0]), 300000)

    def test_not_without_a_hit_since_the_end(self):
        """A second and a half after END_COMBAT with no hit between: two
        fights, as before."""
        lines = [*fight(10000, 20000, hit(19000, 2, 100000, boss(900000))),
                 '21500,BEGIN_COMBAT', hit(25000, 2, 100000, boss(800000)), '30000,END_COMBAT']
        self.assertEqual(len(Engine().feed(lines).fights), 2)

    def test_not_on_an_enemy_left_before_the_end(self):
        """The trash, last hit 19 s before END_COMBAT, was not being fought
        as the fight ended: hitting it after counts in the fight, but the
        next line is a new fight."""
        lines = [*fight(10000, 30000, hit(11000, 2, 50000, trash(950000)),
                        hit(29000, 3, 100000, boss(900000))),
                 hit(31000, 2, 40000, trash(910000)), hit(33000, 2, 40000, trash(870000)),
                 *fight(34000, 41000, hit(35000, 2, 100000, boss(800000)))]
        first, second = Engine().feed(lines).fights
        self.assertEqual(group_damage(first), 230000)
        self.assertEqual(group_damage(second), 100000)

    def test_a_unit_id_handed_out_again_does_not_carry_it_on(self):
        """The trash, hit as the fight ended, is gone and its unit id given
        to another monster, which the group hits as combat begins again:
        not the enemy the group was fighting, so a new fight."""
        lines = [*fight(10000, 20000, hit(18000, 2, 50000, trash(950000)),
                        hit(19000, 3, 100000, boss(900000))),
                 hit(21000, 2, 800000, boss(100000)), hit(22000, 3, 100000, boss(0)),
                 died_xp(22001, 3, boss(0)),
                 '22100,UNIT_REMOVED,71',
                 ('22200,UNIT_ADDED,71,MONSTER,F,0,50000,F,0,0,"Reef Guardian","",0,50,160,0,'
                  'HOSTILE,F'),
                 hit(23000, 2, 40000, _unit(71, 10000, 50000)),
                 *fight(24000, 30000, hit(25000, 2, 10000, _unit(71, 0, 50000)))]
        self.assertEqual(len(Engine().feed(lines).fights), 2)

    def test_an_enemy_dead_by_the_line(self):
        engine = Engine().feed(self._parts(hit(22000, 2, 100000, boss(700000)),
                                           hit(25000, 3, 700000, boss(0)),
                                           died_xp(25001, 3, boss(0))))
        self.assertEqual(len(engine.fights), 2)

    def test_the_other_hits_between_the_lines_are_the_fights(self):
        """The add hit while the group fought on is the carried-on
        fight's."""
        engine = Engine().feed(self._parts(hit(21000, 2, 20000, add(30000)),
                                           hit(22000, 2, 100000, boss(700000)),
                                           hit(25000, 3, 100000, boss(600000))))
        (entry,) = engine.fights
        self.assertEqual(group_damage(entry), 520000)

    def test_the_hits_since_the_end_however_long(self):
        """Fighting on for 14 s with an add hit at its start: the ten
        seconds of the hits before a line do not apply to a fight carried
        on."""
        gap = [hit(21000, 2, 20000, add(30000)),
               *(hit(ts, 3, 10000, boss(800000 - ts)) for ts in range(22000, 35000, 2000))]
        lines = [*fight(10000, 20000, hit(19000, 3, 100000, boss(800000))), *gap,
                 '35000,BEGIN_COMBAT', hit(36000, 2, 100000, boss(500000)), '40000,END_COMBAT']
        (entry,) = Engine().feed(lines).fights
        self.assertEqual(group_damage(entry), 100000 + 20000 + 7 * 10000 + 100000)

    def test_a_blip_fights_on_no_one(self):
        """A blip (BLIP_MS) settles nothing: the group's hits after it are
        no blip's."""
        lines = [*TRASH_FIGHT, '27000,BEGIN_COMBAT', hit(27100, 2, 5000, boss(865000)),
                 '27400,END_COMBAT', hit(28000, 3, 20000, boss(845000)), regen(40000)]
        blip = Engine().feed(lines).fights[1]
        self.assertEqual(group_damage(blip), 5000)


class TestTheLedger(unittest.TestCase):
    """The fighting on in WaitingHits alone."""

    def test_the_window(self):
        hits = WaitingHits()
        ended = EnemyInfo('71', 'Trash', 'MONSTER')
        other = EnemyInfo('72', 'Add', 'MONSTER')
        self.assertFalse(hits.fighting_on)
        self.assertFalse(hits.fought_on(ended, 1000))
        hits.settled({ended}, 20000)
        self.assertTrue(hits.fighting_on)
        self.assertFalse(hits.fought_on(other, 21000))
        self.assertTrue(hits.fought_on(ended, 21000))
        self.assertFalse(hits.due(21000 + FIGHT_ON_MS))
        self.assertTrue(hits.due(21001 + FIGHT_ON_MS))
        self.assertFalse(hits.fought_on(ended, 21001 + FIGHT_ON_MS))
        self.assertTrue(hits.stop())
        self.assertFalse(hits.fighting_on)
        self.assertFalse(hits.stop())

    def test_a_fight_nobody_fought_on(self):
        hits = WaitingHits()
        hits.settled(set(), 20000)
        self.assertFalse(hits.stop())

    def test_the_hits_since_end_combat_are_kept_while_it_lasts(self):
        hits = WaitingHits()
        hits.settled(set(), 20000)
        hits.keep(_hit_record(20500))
        hits.keep(_hit_record(34000))
        self.assertEqual([h.timestamp for h in hits.carried_on(20000)], [20500, 34000])
        # Stopped, the last ten seconds again
        hits.settled(set(), 40000)
        hits.stop()
        hits.keep(_hit_record(40500))
        hits.keep(_hit_record(54000))
        self.assertEqual([h.timestamp for h in hits.carried_on(40000)], [54000])


if __name__ == '__main__':
    unittest.main()
