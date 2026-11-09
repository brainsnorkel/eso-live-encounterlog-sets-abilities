#!/usr/bin/env python3
"""The group's hits from the moments before a fight's BEGIN_COMBAT count in
that fight (issue #162, part 1; waiting_hits):
every damage result of the last 10 s since the last END_COMBAT, on an enemy
the fight that ended never hit and that was alive at the line, at its own
time. The fight's clock stays BEGIN_COMBAT to END_COMBAT.

The shapes follow the real logs: a group member's hit lands a moment before
the logging player's client enters combat (48.1% of 8,816 fights, #159).
"""

import unittest
from unittest import mock

import esolog_tail
from damage_stats import per_second, running_dps, smoothed_dps
from engine_events import RecordingListener
from esolog_tail import EnemyInfo, ESOLogAnalyzer, FightHistory
from waiting_hits import GroupHit, WaitingHits

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
TRASH_HEALTH = 1000000
ADD_HEALTH = 50000
PET_HEALTH = 45478
STRIKE = 12345   # the group's skill before and in the fights
SWING = 23456    # another, for the hits in a fight where kinds are compared


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _unit(unit_id, health, maximum):
    return f"{unit_id},{health}/{maximum},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def boss(health=900000):
    return _unit(70, health, BOSS_HEALTH)


def trash(health=900000):
    return _unit(71, health, TRASH_HEALTH)


def add(health=40000):
    return _unit(72, health, ADD_HEALTH)


def hit(ts, player, damage, target, result='DAMAGE', ability=STRIKE, cast=None):
    """Player *player* hits *target* (a unit state) with *ability*; each hit
    is its own cast unless *cast* says otherwise."""
    cast = cast if cast is not None else ts
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{damage},0,{cast},{ability},"
            f"{_player(player)},{target}")


def died_xp(ts, player, target):
    return (f"{ts},COMBAT_EVENT,DIED_XP,PHYSICAL,1,0,0,{ts},{STRIKE},"
            f"{_player(player)},{target}")


def builds(ts, *players):
    """The PLAYER_INFO lines the game writes after each BEGIN_COMBAT."""
    return [f'{ts},PLAYER_INFO,{unit},[45549],[1],[],[{STRIKE}],[{STRIKE}]' for unit in players]


def fight(begin, end, *lines, players=(1, 2, 3)):
    """BEGIN_COMBAT at *begin*, the builds, *lines*, END_COMBAT at *end*."""
    return [f'{begin},BEGIN_COMBAT', *builds(begin + 1, *players), *lines, f'{end},END_COMBAT']


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,2,7,"Third Wheel","@third",1003,50,1800,0,PLAYER_ALLY,T',
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F',
    f'2500,UNIT_ADDED,71,MONSTER,F,0,{TRASH_HEALTH},F,0,0,"Dreadsail Deckhand","",0,50,160,0,HOSTILE,F',
    f'2500,UNIT_ADDED,72,MONSTER,F,0,{ADD_HEALTH},F,0,0,"Sea Adder","",0,50,160,0,HOSTILE,F',
    # The logging player's pet, summoned before the pulls
    f'3000,UNIT_ADDED,90,MONSTER,F,0,{PET_HEALTH},F,0,0,"Blighted Blastbones","",0,50,160,1,NPC_ALLY,F',
    f'2600,ABILITY_INFO,{STRIKE},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    f'2600,ABILITY_INFO,{SWING},"Other Ability","/esoui/art/icons/ability_weapon_002.dds",F,F',
    '2600,ABILITY_INFO,45549,"Grace","/esoui/art/icons/ability_armor_004.dds",T,T',
]

# The fight before: the group fights the trash (71) from 10 s to 20 s
TRASH_FIGHT = fight(10000, 20000,
                    hit(11000, 2, 50000, trash(950000)),
                    hit(15000, 3, 50000, trash(900000)))


class Engine:

    def __init__(self, base=BASE):
        self.analyzer = ESOLogAnalyzer()
        self.analyzer.fight_history = FightHistory()
        self.listener = RecordingListener()
        self.analyzer.add_listener(self.listener)
        self.feed(base)

    def feed(self, lines):
        for line in lines:
            entry = self.analyzer.log_parser.parse_line(line)
            if entry is not None:
                self.analyzer.process_log_entry(entry)
        return self

    @property
    def fights(self):
        return self.analyzer.fight_history.fights


def _fights(*lines):
    return Engine().feed(lines).fights


def group_damage(entry) -> int:
    """The group's damage in a fight entry, from the DPS graph's series."""
    return sum(damage for _t, damage in entry.damage_series['all'])


def row(entry, name):
    return next(p for p in entry.players if p['name'] == name)


# The boss fight after it: BEGIN_COMBAT at 28 s, END_COMBAT at 41 s, the
# group's hits on the boss at 29 s and 38 s
BOSS_HITS = (hit(29000, 2, 100000, boss(770000)), hit(38000, 3, 100000, boss(670000)))


def boss_fight(*before):
    """The trash fight, *before* (lines between it and the boss fight),
    then the boss fight."""
    return [*TRASH_FIGHT, *before, *fight(28000, 41000, *BOSS_HITS)]


class TestCounted(unittest.TestCase):

    def test_a_hit_before_the_line_counts_in_the_fight(self):
        """The logging player hits the boss 2 s before their client enters
        combat: the hit opens the fight and counts in its figures."""
        trash_entry, entry = _fights(*boss_fight(hit(26000, 1, 30000, boss(870000))))
        self.assertEqual(group_damage(entry), 230000)
        # The opener line names the hit the figures count
        self.assertEqual((entry.opener['name'], entry.opener['time_ms']), ('@brainsnorkel', -2000))
        # The fight before is as it ended: two hits on the trash
        self.assertEqual(group_damage(trash_entry), 100000)

    def test_the_dps_time_starts_at_the_earlier_hit(self):
        """The dps time runs from the hit before the line (26 s) to the
        last (38 s); the fight's clock stays BEGIN_COMBAT to END_COMBAT."""
        entry = _fights(*boss_fight(hit(26000, 1, 30000, boss(870000))))[1]
        self.assertAlmostEqual(entry.duration_s, 13.0)
        self.assertAlmostEqual(entry.dps_time_s, 12.0)
        self.assertAlmostEqual(entry.group_dps, 230000 / 12.0)
        # The hit is on the boss: the boss figures take it too
        self.assertAlmostEqual(entry.boss_dps_time_s, 12.0)
        self.assertAlmostEqual(entry.group_boss_dps, 230000 / 12.0)
        window = entry.damage_series['window']
        self.assertEqual((window['first_s'], window['last_s']), (-2.0, 10.0))

    def test_without_it_the_figures_are_the_fights_own(self):
        """The same pulls with no hit before the line."""
        entry = _fights(*boss_fight())[1]
        self.assertEqual(group_damage(entry), 200000)
        self.assertAlmostEqual(entry.dps_time_s, 9.0)

    def test_a_player_whose_only_damage_came_before_the_line(self):
        """The logging player's one hit is before the line: their row has a
        dps (one hit, over the one-second floor) and their share."""
        entry = _fights(*boss_fight(hit(26000, 1, 30000, boss(870000))))[1]
        mine = row(entry, '@brainsnorkel')
        self.assertAlmostEqual(mine['dps'], 30000.0)
        self.assertAlmostEqual(mine['boss_dps'], 30000.0)
        self.assertAlmostEqual(mine['dmg_pct'], 30000 / 230000 * 100)
        self.assertEqual(mine['damage']['total'], 30000)
        self.assertEqual(mine['damage']['window']['first_s'], -2.0)
        self.assertEqual([a['id'] for a in mine['damage']['abilities']], [str(STRIKE)])

    def test_a_damage_over_time_tick_counts(self):
        tick = hit(27000, 2, 8000, boss(892000), result='DOT_TICK')
        entry = _fights(*boss_fight(tick))[1]
        self.assertEqual(group_damage(entry), 208000)
        kinds = row(entry, '@templar')['damage']['kinds']
        self.assertEqual(kinds['dot'], 8000)
        self.assertEqual(kinds['direct'], 100000)
        self.assertAlmostEqual(entry.dps_time_s, 11.0)

    def test_a_pet_removed_before_the_line(self):
        """A Blastbones blows up on the boss and is removed before the line:
        its hit is still its owner's, as a pet's."""
        blast = (f"26000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,30000,0,26000,{STRIKE},"
                 f"{_unit(90, PET_HEALTH, PET_HEALTH)},{boss(870000)}")
        entry = _fights(*boss_fight(blast, '26500,UNIT_REMOVED,90'))[1]
        self.assertEqual(group_damage(entry), 230000)
        mine = row(entry, '@brainsnorkel')['damage']
        self.assertEqual(mine['total'], 30000)
        self.assertEqual([(a['id'], a['pet']) for a in mine['abilities']], [(str(STRIKE), True)])

    def test_an_enemy_the_fight_before_never_hit_nor_the_new_one(self):
        """An enemy of neither fight: the rule at the line cannot know the
        new fight will not hit it, and counts it."""
        entry = _fights(*boss_fight(hit(27000, 2, 10000, add(40000))))[1]
        self.assertEqual(group_damage(entry), 210000)
        self.assertEqual(entry.boss_name, 'Tideborn Taleria')

    def test_the_ten_seconds(self):
        """From 10 s before the line, that millisecond included."""
        lines = [*fight(10000, 15000, hit(11000, 2, 50000, trash(950000))),
                 hit(17999, 2, 7000, boss(993000)),   # 10.001 s before the line
                 hit(18000, 3, 9000, boss(984000)),   # 10 s before
                 *fight(28000, 41000, *BOSS_HITS)]
        entry = _fights(*lines)[1]
        self.assertEqual(group_damage(entry), 209000)
        self.assertAlmostEqual(entry.dps_time_s, 20.0)

    def test_a_hit_in_the_lines_own_millisecond(self):
        """Written before BEGIN_COMBAT in the same millisecond: before the
        line, and counted, at the fight's very start."""
        entry = _fights(*boss_fight(hit(28000, 1, 30000, boss(870000))))[1]
        self.assertEqual(group_damage(entry), 230000)
        self.assertEqual(entry.damage_series['window']['first_s'], 0.0)


class TestNotCounted(unittest.TestCase):

    def test_an_enemy_the_fight_before_hit(self):
        """The group still hitting the trash after its fight ended: those
        hits are the fight before's (issue #162's part 2), not the boss
        fight's."""
        entry = _fights(*boss_fight(hit(26000, 2, 40000, trash(860000))))[1]
        self.assertEqual(group_damage(entry), 200000)
        self.assertAlmostEqual(entry.dps_time_s, 9.0)

    def test_an_enemy_killed_before_the_line(self):
        """It belonged to the last pack: its hits count nowhere here, and
        the opener line does not name them either (fight_opener)."""
        before = (hit(25000, 2, 40000, add(0)), died_xp(25001, 2, add(0)))
        entry = _fights(*boss_fight(*before))[1]
        self.assertEqual(group_damage(entry), 200000)
        self.assertAlmostEqual(entry.dps_time_s, 9.0)
        self.assertEqual((entry.opener['target'], entry.opener['time_ms']),
                         ('Tideborn Taleria', 1000))

    def test_an_enemy_gone_before_the_line(self):
        """Removed without a death line, as a summoned add whose summoner
        died: gone like a dead one."""
        before = (hit(25000, 2, 30000, add(10000)), '25500,UNIT_REMOVED,72')
        entry = _fights(*boss_fight(*before))[1]
        self.assertEqual(group_damage(entry), 200000)

    def test_a_player_who_left_before_the_line(self):
        """Off the new fight's list (presence.py), and so are their hits."""
        lines = [*TRASH_FIGHT, hit(25000, 3, 30000, boss(870000)), '25500,UNIT_REMOVED,3',
                 *fight(28000, 41000, hit(29000, 2, 100000, boss(770000)), players=(1, 2))]
        entry = _fights(*lines)[1]
        self.assertNotIn('@third', [p['name'] for p in entry.players])
        self.assertEqual(group_damage(entry), 100000)

    def test_a_unit_id_handed_out_again_is_a_new_enemy(self):
        """The trash's unit id given to another monster between the
        fights: a unit the fight before never hit."""
        before = ('21000,UNIT_REMOVED,71',
                  f'22000,UNIT_ADDED,71,MONSTER,F,0,{ADD_HEALTH},F,0,0,"Reef Guardian","",0,50,160,0,HOSTILE,F',
                  hit(26000, 2, 40000, _unit(71, 10000, ADD_HEALTH)))
        entry = _fights(*boss_fight(*before))[1]
        self.assertEqual(group_damage(entry), 240000)


class TestCountedOnce(unittest.TestCase):

    def test_the_zones_first_fight(self):
        """Its encounter is the zone's own and took the hit as it came."""
        fights = _fights(hit(26000, 1, 30000, boss(870000)), *fight(28000, 41000, *BOSS_HITS))
        self.assertEqual(len(fights), 1)
        self.assertEqual(group_damage(fights[0]), 230000)
        self.assertAlmostEqual(fights[0].dps_time_s, 12.0)

    def test_a_fight_the_game_cut_in_two(self):
        """END_COMBAT and BEGIN_COMBAT 36 ms apart around a resurrection
        (COMBAT_RESUME_MS): the hits between the two lines, on the boss and
        on another enemy, are the fight's once."""
        lines = [*fight(10000, 30031, hit(11000, 2, 100000, boss(900000)),
                        hit(29000, 2, 300000, boss(600000))),
                 hit(30040, 3, 50000, boss(550000)),
                 hit(30050, 3, 20000, add(30000)),
                 '30067,BEGIN_COMBAT', *builds(30067, 1, 2, 3),
                 hit(40000, 1, 100000, boss(450000)),
                 '50100,END_COMBAT']
        engine = Engine().feed(lines)
        self.assertEqual(len(engine.fights), 1)
        entry = engine.fights[0]
        self.assertAlmostEqual(entry.duration_s, 40.1)
        self.assertEqual(group_damage(entry), 570000)
        self.assertAlmostEqual(entry.dps_time_s, 29.0)

    def test_a_held_combat_listed_after_it_ended(self):
        """A combat with no enemy, listed for a death just after it ended
        (see LATE_DEATH_GRACE_MS), is built with the hits since it ended:
        the next fight's line does not count them again."""
        trap = _unit(81, 0, 0)
        lines = [*TRASH_FIGHT,
                 '21000,UNIT_ADDED,81,MONSTER,F,0,56034,F,0,0,"Storm","",0,50,160,0,NPC_NEUTRAL,F',
                 *fight(22000, 24000, (f"23000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,15000,0,1,9,"
                                       f"{trap},{_player(1, 5000)}")),
                 hit(24300, 2, 30000, boss(870000)),
                 (f"24500,COMBAT_EVENT,DIED,PHYSICAL,1,0,0,2,9,{trap},{_player(1, 0)}"),
                 *fight(28000, 41000, *BOSS_HITS)]
        _trash, held, entry = _fights(*lines)
        self.assertEqual(group_damage(held), 30000)
        self.assertEqual(group_damage(entry), 200000)


class TestBlips(unittest.TestCase):
    """A fight shorter than BLIP_MS, BEGIN_COMBAT to END_COMBAT, takes none
    of the hits from before its line: they wait for the next line, where the
    usual rules apply, the fight before the blip still the ended fight."""

    def test_a_blip_leaves_the_hits_to_the_next_line(self):
        lines = [*TRASH_FIGHT, hit(26000, 1, 30000, boss(870000)),
                 '27000,BEGIN_COMBAT', '27500,END_COMBAT',  # half a second
                 *fight(28000, 41000, *BOSS_HITS)]
        _trash, blip, entry = _fights(*lines)
        self.assertAlmostEqual(blip.duration_s, 0.5)
        self.assertEqual(group_damage(blip), 0)
        self.assertEqual(group_damage(entry), 230000)
        self.assertAlmostEqual(entry.dps_time_s, 12.0)

    def test_a_fight_of_a_second_takes_them(self):
        lines = [*TRASH_FIGHT, hit(26000, 1, 30000, boss(870000)),
                 '27000,BEGIN_COMBAT', '28000,END_COMBAT',  # one second
                 *fight(30000, 41000, hit(31000, 2, 100000, boss(770000)),
                        hit(38000, 3, 100000, boss(670000)))]
        _trash, short, entry = _fights(*lines)
        self.assertEqual(group_damage(short), 30000)
        self.assertEqual(short.damage_series['window']['first_s'], -1.0)
        self.assertEqual(group_damage(entry), 200000)

    def test_the_ten_seconds_count_from_the_next_line(self):
        lines = [*fight(10000, 15000, hit(11000, 2, 50000, trash(950000))),
                 hit(17000, 2, 7000, boss(993000)),  # 11 s before the next fight's line
                 hit(19000, 3, 9000, boss(984000)),  # 9 s before it
                 '20500,BEGIN_COMBAT', '20800,END_COMBAT',  # a blip
                 *fight(28000, 41000, *BOSS_HITS)]
        entry = _fights(*lines)[-1]
        self.assertEqual(group_damage(entry), 209000)
        self.assertAlmostEqual(entry.dps_time_s, 19.0)

    def test_the_ended_fight_is_the_one_before_the_blip(self):
        """The trash fight's enemy stays its own across the blip; the
        blip's own hit on the boss is no reason to leave the boss fight's
        hits out."""
        lines = [*TRASH_FIGHT,
                 hit(25000, 2, 40000, trash(860000)),
                 hit(26000, 1, 30000, boss(870000)),
                 '27000,BEGIN_COMBAT', hit(27100, 3, 5000, boss(865000)), '27400,END_COMBAT',
                 hit(27600, 1, 20000, boss(845000)),
                 *fight(30000, 41000, hit(31000, 2, 100000, boss(745000)),
                        hit(38000, 3, 100000, boss(645000)))]
        _trash, blip, entry = _fights(*lines)
        self.assertEqual(group_damage(blip), 5000)
        self.assertEqual(group_damage(entry), 250000)
        self.assertAlmostEqual(entry.dps_time_s, 12.0)

    def test_a_blip_the_game_carries_on(self):
        """A blip cut in two (COMBAT_RESUME_MS) is a fight of its whole
        length: it takes the hits from before its first line, once."""
        lines = [*TRASH_FIGHT, hit(26000, 1, 30000, boss(870000)),
                 '27000,BEGIN_COMBAT', hit(27100, 2, 50000, boss(820000)), '27400,END_COMBAT',
                 '27450,BEGIN_COMBAT', *builds(27450, 1, 2, 3),
                 hit(30000, 3, 100000, boss(720000)), '40000,END_COMBAT']
        fights = _fights(*lines)
        self.assertEqual(len(fights), 2)
        entry = fights[1]
        self.assertAlmostEqual(entry.duration_s, 13.0)
        self.assertEqual(group_damage(entry), 180000)
        self.assertAlmostEqual(entry.dps_time_s, 4.0)


class TestBreakdowns(unittest.TestCase):
    """No breakdown disagrees with the figures."""

    def test_the_kinds_take_the_hits(self):
        """A cast before the line strikes the boss, then the add: read
        single when it struck the boss, area by the line, as in a fight."""
        before = (hit(26000, 2, 30000, boss(870000), cast=501),
                  hit(26500, 2, 20000, add(30000), cast=501))
        lines = [*TRASH_FIGHT, *before,
                 *fight(28000, 41000, hit(29000, 2, 100000, boss(770000), ability=SWING),
                        hit(38000, 3, 100000, boss(670000), ability=SWING))]
        entry = _fights(*lines)[1]
        damage = row(entry, '@templar')['damage']
        self.assertEqual(damage['total'], 150000)
        kinds = damage['kinds']
        self.assertEqual(kinds['total'], 150000)
        self.assertEqual((kinds['area'], kinds['single']), (50000, 100000))
        self.assertEqual(kinds['rules'].get('cast'), 50000)
        strike = next(a for a in damage['abilities'] if a['id'] == str(STRIKE))
        self.assertEqual((strike['damage'], strike['hits'], strike['area_damage']),
                         (50000, 2, 50000))
        targets = {t['name']: t['damage'] for t in damage['targets']}
        self.assertEqual(targets, {'Tideborn Taleria': 130000, 'Sea Adder': 20000})

    def test_the_graph_puts_them_in_second_0(self):
        """The DPS graph's second 0 holds the hits before the line, and its
        running figure, from the first hit, ends on the fight's dps."""
        entry = _fights(*boss_fight(hit(26000, 1, 30000, boss(870000))))[1]
        series = entry.damage_series['all']
        self.assertEqual(list(series), [[-2.0, 30000], [1.0, 100000], [10.0, 100000]])
        seconds = per_second(series, entry.duration_s)
        self.assertEqual(seconds[0], 30000)
        self.assertEqual(sum(seconds), 230000)
        self.assertEqual(smoothed_dps(series, 1, entry.duration_s)[0], (0.0, 30000.0))
        window = entry.damage_series['window']
        running = running_dps(series, window['first_s'], window['last_s'], entry.duration_s)
        self.assertEqual(running[0], (0.0, 30000 / 2.0))
        self.assertAlmostEqual(running[-1][1], entry.group_dps)
        # Each player's series too
        mine = row(entry, '@brainsnorkel')['damage']
        self.assertEqual(per_second(mine['series'], entry.duration_s)[0], 30000)

    def test_the_penetration_figures_weigh_them(self):
        """The damage the penetration and crit histograms weigh is the
        fight's damage (pen_crit)."""
        entry = _fights(*boss_fight(hit(26000, 1, 30000, boss(870000))))[1]
        self.assertEqual(entry.pen_crit['damage'], 230000)
        self.assertEqual(row(entry, '@brainsnorkel')['pen_crit']['damage'], 30000)

    def test_a_cast_across_the_line_is_area_on_both_sides(self):
        """One cast strikes the boss 100 ms before the line and the add 200
        ms after it: area on both sides, as a cast is in a fight."""
        lines = [*TRASH_FIGHT,
                 hit(27900, 2, 30000, boss(870000), cast=501),
                 '28000,BEGIN_COMBAT', *builds(28001, 1, 2, 3),
                 hit(28200, 2, 20000, add(30000), cast=501),
                 hit(38000, 3, 100000, boss(770000), ability=SWING),
                 '41000,END_COMBAT']
        kinds = row(_fights(*lines)[1], '@templar')['damage']['kinds']
        self.assertEqual((kinds['area'], kinds['single']), (50000, 0))
        self.assertEqual(kinds['rules'].get('cast'), 50000)

    def test_a_hit_between_the_lines_of_a_fight_carried_on_moves_to_area(self):
        """The closed encounter keeps its cast watchers: a fight the game
        cut in two is rebuilt from it, and a hit between the two lines whose
        cast strikes a second unit after them is area, as in any fight."""
        lines = [*fight(10000, 30031, hit(11000, 2, 100000, boss(900000)),
                        hit(29000, 2, 300000, boss(600000))),
                 hit(30040, 3, 50000, boss(550000), cast=777),
                 '30067,BEGIN_COMBAT', *builds(30067, 1, 2, 3),
                 hit(31000, 3, 20000, add(30000), cast=777),
                 '50100,END_COMBAT']
        fights = _fights(*lines)
        self.assertEqual(len(fights), 1)
        kinds = row(fights[0], '@third')['damage']['kinds']
        self.assertEqual((kinds['area'], kinds['single']), (70000, 0))


class TestFightBoundaries(unittest.TestCase):
    """Each fight boundary leaves the waiting hits as the rule needs
    (waiting_hits.WaitingHits)."""

    def test_a_unit_id_handed_out_again_during_the_fight_before(self):
        """The trash dies and its unit id goes to a mob of the next pack
        before the trash fight ends: the next fight's opening hits on that
        mob are its own, not the group fighting on. The ended fight's
        enemies are the records it hit."""
        lines = [*fight(10000, 20000,
                        hit(11000, 2, 50000, trash(950000)),
                        hit(15000, 3, 950000, trash(0)),
                        died_xp(15001, 3, trash(0)),
                        '16000,UNIT_REMOVED,71',
                        f'17000,UNIT_ADDED,71,MONSTER,F,0,{ADD_HEALTH},F,0,0,"Reef Guardian","",0,50,160,0,HOSTILE,F'),
                 hit(26000, 2, 40000, _unit(71, 10000, ADD_HEALTH)),
                 *fight(28000, 41000, *BOSS_HITS)]
        self.assertEqual(group_damage(_fights(*lines)[1]), 240000)

    def test_a_blip_carried_on_into_a_blip(self):
        """A blip the game cuts in two and carries on, under a second in
        all, takes no hits either: they wait for the next line, and the
        fight before stays the ended one."""
        lines = [*TRASH_FIGHT,
                 hit(26000, 1, 30000, boss(870000)),
                 hit(26500, 2, 20000, trash(880000)),
                 '27000,BEGIN_COMBAT', hit(27100, 2, 5000, boss(865000)), '27300,END_COMBAT',
                 '27400,BEGIN_COMBAT', '27700,END_COMBAT',
                 hit(28000, 3, 20000, trash(860000)),
                 *fight(30000, 41000, hit(31000, 2, 100000, boss(765000)),
                        hit(38000, 3, 100000, boss(665000)))]
        fights = _fights(*lines)
        self.assertEqual(len(fights), 3)
        blip, entry = fights[1], fights[2]
        self.assertAlmostEqual(blip.duration_s, 0.7)
        self.assertEqual(group_damage(blip), 5000)
        self.assertEqual(group_damage(entry), 230000)

    def test_a_combat_with_no_enemy_leaves_the_ended_fight(self):
        """A trap's combat between the fights is held back and never
        listed: the group finishing the trash fight's enemy after it is
        still the trash fight's, not the boss fight's opening."""
        lines = [*TRASH_FIGHT, TRAP_ADDED,
                 '22000,BEGIN_COMBAT', trap_hit(23000), '24000,END_COMBAT',
                 hit(26000, 2, 40000, trash(860000)),
                 *fight(28000, 41000, *BOSS_HITS)]
        fights = _fights(*lines)
        self.assertEqual(len(fights), 2)
        self.assertEqual(group_damage(fights[1]), 200000)

    def test_a_combat_with_no_enemy_listed_late_settles_then(self):
        """Listed for a death just after it ended, the combat is a fight:
        its entry has the boss hit since it ended, and the next line leaves
        the boss to it."""
        lines = [*TRASH_FIGHT, TRAP_ADDED,
                 *fight(22000, 24000, trap_hit(23000)),
                 hit(24300, 2, 30000, boss(870000)),
                 f"24500,COMBAT_EVENT,DIED,PHYSICAL,1,0,0,2,9,{TRAP},{_player(1, 0)}",
                 hit(26000, 3, 40000, boss(830000)),
                 *fight(28000, 41000, *BOSS_HITS)]
        _trash, held, entry = _fights(*lines)
        self.assertEqual(group_damage(held), 30000)
        self.assertEqual(group_damage(entry), 200000)

    def test_a_fight_that_takes_hits_has_met_an_enemy(self):
        """After a blip, a fight with no line of its own between the group
        and an enemy takes the hits from before the blip: it met that enemy,
        and is listed with them."""
        lines = [*TRASH_FIGHT,
                 hit(21000, 1, 30000, boss(870000)),
                 '22000,BEGIN_COMBAT', '22300,END_COMBAT',
                 '25000,BEGIN_COMBAT', *builds(25001, 1, 2, 3), '35000,END_COMBAT']
        fights = _fights(*lines)
        self.assertEqual(len(fights), 3)
        self.assertEqual(group_damage(fights[2]), 30000)

    def test_a_player_back_on_a_new_unit_keeps_their_hits(self):
        """@third hits the boss from unit 3, drops and comes back on unit 40
        before the line, which keys the record by 40 from there
        (presence.py): the hit from unit 3 is still theirs, and their own,
        not a pet's."""
        back = ('26500,UNIT_ADDED,40,PLAYER,F,3,0,F,2,7,"Third Wheel","@third",1003,50,1800,0,'
                'PLAYER_ALLY,T')
        lines = [*TRASH_FIGHT, hit(26000, 3, 30000, boss(870000)), back,
                 *fight(28000, 41000, hit(29000, 2, 100000, boss(770000)), players=(1, 2, 40))]
        entry = _fights(*lines)[1]
        self.assertEqual(group_damage(entry), 130000)
        third = row(entry, '@third')
        self.assertEqual((third['unit_id'], third['damage']['total']), ('40', 30000))
        self.assertEqual([a['pet'] for a in third['damage']['abilities']], [False])

    def test_the_kinds_are_read_once_between_fights(self):
        """A hit between fights is read by the cast index once, for the
        closed encounter, and kept as read."""
        engine = Engine().feed(TRASH_FIGHT)
        with mock.patch.object(esolog_tail, 'area_of', wraps=esolog_tail.area_of) as read:
            engine.feed([hit(26000, 1, 30000, boss(870000))])
        self.assertEqual(read.call_count, 1)

    def test_only_a_new_encounter_takes_the_waiting_hits(self):
        """The zone's first fight is the zone's own encounter, which took
        its hits as they came: the waiting hits are not read for it."""
        engine = Engine()
        with mock.patch.object(engine.analyzer.waiting_hits, 'take',
                               wraps=engine.analyzer.waiting_hits.take) as take:
            engine.feed(fight(10000, 20000, hit(11000, 2, 50000, trash(950000))))
            self.assertEqual(take.call_count, 0)
            engine.feed(fight(28000, 41000, *BOSS_HITS))
            self.assertEqual(take.call_count, 1)


TRAP = _unit(81, 0, 0)
TRAP_ADDED = '21000,UNIT_ADDED,81,MONSTER,F,0,56034,F,0,0,"Storm","",0,50,160,0,NPC_NEUTRAL,F'


def trap_hit(ts, player=1):
    """A neutral trap's hit on a player: no meeting with an enemy."""
    return f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,15000,0,1,9,{TRAP},{_player(player, 5000)}"


def _hit_record(ts, target_id='70', enemy=None, area=(False, 'none'), cast='1'):
    return GroupHit(ts, 'DAMAGE', 1000, '1', target_id, enemy or EnemyInfo(target_id, 'X', 'MONSTER'),
                    '12345', 'PHYSICAL', cast, area, (None, None, False))


class TestWaitingHits(unittest.TestCase):
    """The ledger alone: what each boundary does to the waiting hits."""

    def test_it_keeps_the_last_ten_seconds(self):
        hits = WaitingHits()
        for ts in (1000, 5000, 11000, 12000):
            hits.keep(_hit_record(ts))
        self.assertEqual([h.timestamp for h in hits.take(12000, lambda s, c: 1)],
                         [5000, 11000, 12000])

    def test_a_take_leaves_the_hits_waiting(self):
        hits = WaitingHits()
        hits.keep(_hit_record(5000))
        self.assertEqual(len(hits.take(6000, lambda s, c: 1)), 1)
        self.assertEqual(len(hits.take(7000, lambda s, c: 1)), 1)

    def test_the_ended_fights_enemies_are_records(self):
        hits = WaitingHits()
        hit_one = EnemyInfo('55', 'Trash', 'MONSTER')
        hits.settled({hit_one})
        hits.keep(_hit_record(5000, '55', hit_one))
        hits.keep(_hit_record(5500, '55', EnemyInfo('55', 'Next pack', 'MONSTER')))
        self.assertEqual([h.timestamp for h in hits.take(6000, lambda s, c: 1)], [5500])

    def test_a_dead_enemy_is_left_out(self):
        hits = WaitingHits()
        enemy = EnemyInfo('70', 'X', 'MONSTER')
        enemy.died_at = 5200
        hits.keep(_hit_record(5000, enemy=enemy))
        self.assertEqual(hits.take(6000, lambda s, c: 1), [])

    def test_the_area_read_at_a_line_stays_on_the_waiting_copy(self):
        hits = WaitingHits()
        hits.keep(_hit_record(5000, cast='9'))
        self.assertEqual(hits.take(6000, lambda s, c: 2)[0].area, (True, 'cast'))
        # The index is emptied at the line: a later line reads one target
        self.assertEqual(hits.take(7000, lambda s, c: 1)[0].area, (True, 'cast'))

    def test_settled_starts_the_waiting_again(self):
        hits = WaitingHits()
        hits.keep(_hit_record(5000))
        hits.settled(set())
        self.assertEqual(hits.take(6000, lambda s, c: 1), [])

    def test_carried_on_and_listed_late_drop_the_hits_since(self):
        for boundary in ('carried_on', 'listed_late'):
            hits = WaitingHits()
            ended = EnemyInfo('71', 'Trash', 'MONSTER')
            hits.settled({ended})
            hits.keep(_hit_record(5000))
            hits.keep(_hit_record(6000))
            getattr(hits, boundary)(6000)
            self.assertEqual([h.timestamp for h in hits.take(7000, lambda s, c: 1)], [5000])
            hits.keep(_hit_record(7500, '71', ended))
            self.assertEqual([h.timestamp for h in hits.take(8000, lambda s, c: 1)], [5000])

    def test_a_reset_forgets_all(self):
        hits = WaitingHits()
        hits.keep(_hit_record(5000))
        hits.reset()
        self.assertEqual(hits.take(6000, lambda s, c: 1), [])


if __name__ == '__main__':
    unittest.main()
