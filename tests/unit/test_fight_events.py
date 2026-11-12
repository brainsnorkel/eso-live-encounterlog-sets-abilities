"""
A fight's notable events (fight_events, issue #214): the recorder, the
packed FightEvents, the engine's hooks and the Events tab's rows
(event_rows).
"""

import unittest
from types import SimpleNamespace

import event_rows
import fight_events as fe
from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory

EPOCH = 1759600000000
BOSS_MAX = 1000000


def _player(unit, health=20000, maximum=20000):
    return f"{unit},{health}/{maximum},26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _boss(health=BOSS_MAX):
    return f"70,{health}/{BOSS_MAX},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _event(ts, result, hit, source, target, overflow=0, cast=900, ability=12437):
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{hit},{overflow},{cast},{ability},"
            f"{source},{target}")


def _boss_hit(ts, health, cast=800):
    """Player 1 hits the boss, which is left at *health*."""
    return _event(ts, "DAMAGE", 1000, _player(1), _boss(health), cast=cast, ability=46356)


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1121,"Sunspire",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,4,9,"Pique","@first",1001,50,3230,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Tank","@second",1002,50,787,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,6,1,"Healer","@third",1003,50,787,0,PLAYER_ALLY,T',
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_MAX},T,0,0,"Lokkestiiz","",0,50,160,0,HOSTILE,F',
    '2600,ABILITY_INFO,12437,"Toppling Blow","/esoui/art/icons/death_recap_melee_basic.dds",F,T',
    '2600,ABILITY_INFO,555,"Storm Fury","/esoui/art/icons/storm.dds",F,T',
    '2600,ABILITY_INFO,38254,"Inner Fire","/esoui/art/icons/inner_fire.dds",F,T',
    '2600,ABILITY_INFO,26770,"Resurrect","/esoui/art/icons/rez.dds",F,T',
]

# Every line that carries the boss gives its health at that moment, and the
# lines come in time order (sorted below), as the log has them
FIGHT = [
    '10000,BEGIN_COMBAT',
    # Player 2 taunts the boss, then player 3 takes it
    _event(10100, "TAUNTED", 0, _player(2), _boss(), cast=901, ability=38254),
    _event(15000, "TAUNTED", 0, _player(3), _boss(740000), cast=902, ability=38254),
    _event(16000, "TAUNTED", 0, _player(3), _boss(740000), cast=903, ability=38254),  # no swap
    # The boss's health: under 75% at 11 s; nothing lost from 11 s to 18 s
    _boss_hit(10500, 900000),
    _boss_hit(11000, 740000),
    _boss_hit(18000, 600000),
    _boss_hit(19000, 480000),
    # A boss cast at player 1, which player 2 interrupts
    f"12000,BEGIN_CAST,2000,F,700,555,{_boss()},{_player(1)}",
    "12500,END_CAST,INTERRUPTED,700,555,38254,2",
    # A shield absorbs 4,000 of a 9,000 hit on player 1 (65% of 20,000)
    _event(13000, "DAMAGE_SHIELDED", 4000, _boss(740000), _player(1, 20000), cast=950),
    _event(13001, "DAMAGE", 9000, _boss(740000), _player(1, 11000), cast=950),
    # A small hit: no event
    _event(13500, "DAMAGE", 1000, _boss(740000), _player(1, 10000), cast=951),
    # Player 3 dies, and player 1 raises them; a heal shows them up
    _event(20000, "DIED", 0, _boss(480000), _player(3, 0), cast=960),
    _event(25000, "RESURRECT", 0, _player(1), _player(3, 0), cast=961, ability=26770),
    _event(26000, "HEAL", 4000, _player(1), _player(3, 4000), cast=962),
    '27000,MAP_CHANGED,1500,"The Upper Vault","sunspire/upper"',
    _boss_hit(29000, 470000),
    '30000,END_COMBAT',
]
FIGHT.sort(key=lambda line: int(line.split(",")[0]))


def _run(lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer


def _named(player):
    """What note_on_player asks for a hit it keeps: the player's name, then
    the source's name and key."""
    return lambda: (player, "Boss", "70")


def _kinds(events, kind):
    return [r for r in events.records() if r.kind == kind]


class TestRecorder(unittest.TestCase):

    def test_boss_health_marks_and_a_stretch_with_no_loss(self):
        recorder = fe.EventRecorder()
        for t, health in ((1000, 1000), (2000, 800), (3000, 760), (9000, 700), (9500, 240)):
            recorder.note_boss_health(t, "Boss", "70", f"{health}/1000")
        recorder.note_boss_health(9600, "Boss", "70", "240/1000")    # unchanged: nothing
        events = recorder.fight_events(0, 20000)
        marks = [(r.t, r.value) for r in _kinds(events, fe.BOSS_HEALTH)]
        # 760 is 76%: 75% is first reached at 700
        self.assertEqual(marks, [(9000, 75), (9500, 50), (9500, 25)])
        self.assertEqual([(r.t, r.value) for r in _kinds(events, fe.UNTOUCHED)], [(3000, 6000)])
        # A boss first seen under a mark has not reached it in this fight
        recorder = fe.EventRecorder()
        recorder.note_boss_health(1000, "Boss", "71", "600/1000")
        recorder.note_boss_health(2000, "Boss", "71", "590/1000")
        self.assertEqual(_kinds(recorder.fight_events(0, 9000), fe.BOSS_HEALTH), [])

    def test_the_overkill_counts_in_the_hit(self):
        """A killing blow writes what reached health and the rest as
        overkill: both are the hit's size."""
        recorder = fe.EventRecorder()
        blow = ["DAMAGE", "", "", "2000", "5000", "7", "99", "70", "", "",
                "", "", "", "", "", "", "", "1", "0/20000"]
        recorder.note_on_player(100, "DAMAGE", blow, "1", _named("@a"))
        hit, = _kinds(recorder.fight_events(0, 1000), fe.HIT)
        self.assertEqual((hit.value, hit.value2), (7000, 20000))

    def test_a_shield_counts_in_the_hit_it_absorbed(self):
        recorder = fe.EventRecorder()
        shield = ["DAMAGE_SHIELDED", "", "", "3000", "0", "7", "99", "70", "", "",
                  "", "", "", "", "", "", "", "1", "20000/20000"]
        hit = ["DAMAGE", "", "", "4000", "0", "7", "99", "70", "", "",
               "", "", "", "", "", "", "", "1", "16000/20000"]
        recorder.note_on_player(100, "DAMAGE_SHIELDED", shield, "1", _named("@a"))
        recorder.note_on_player(101, "DAMAGE", hit, "1", _named("@a"))
        # The same 4,000 without its shield is 20%: no event
        recorder.note_on_player(200, "DAMAGE", hit, "1", _named("@a"))
        hits = _kinds(recorder.fight_events(0, 1000), fe.HIT)
        self.assertEqual([(r.value, r.value2, r.value3) for r in hits], [(4000, 20000, 3000)])

    def test_a_stopped_cast_and_who_stopped_it(self):
        recorder = fe.EventRecorder()
        recorder.note_boss_cast(100, "Boss", "70", "7", "555", "@a", "1", 2000, True)
        self.assertTrue(recorder.holds_track("7"))
        recorder.note_cast_end(300, "7", "INTERRUPTED", "@b", "2", False)
        self.assertFalse(recorder.holds_track("7"))
        recorder.note_boss_cast(400, "Boss", "70", "8", "555", "", "", 0)
        recorder.note_cast_end(500, "8", "COMPLETED", "", "", False)       # not kept
        recorder.note_boss_cast(600, "Boss", "70", "9", "555", "", "", 0)
        recorder.note_cast_end(700, "9", "INTERRUPTED", "Boss", "70", True)
        stops = _kinds(recorder.fight_events(0, 1000), fe.CAST_STOPPED)
        self.assertEqual([(r.t, r.other, bool(r.flags & fe.BY_ITSELF)) for r in stops],
                         [(300, "@b", False), (700, "Boss", True)])

    def test_packed_in_the_fights_window_from_its_start(self):
        recorder = fe.EventRecorder()
        recorder.note_map(500, "Before")
        recorder.note_map(1500, "In the fight")
        recorder.note_map(5000, "After")
        events = recorder.fight_events(1000, 4000, revived=[(3000, "@a", "1", 1200, False)],
                                       boss_deaths=[(3500, "Boss", "70"), (9000, "Other", "71")])
        self.assertEqual([(r.t, r.kind, r.other or r.who) for r in events.records()],
                         [(500, fe.MAP, "In the fight"), (2000, fe.REVIVED, "@a"),
                          (2500, fe.BOSS_DIED, "Boss")])
        self.assertEqual(events.nbytes, 3 * fe._RECORD.size)
        self.assertEqual(len(events), 3)
        # Pruned at the fight's start: a resumed fight is packed again from it
        recorder.prune_before(1000)
        self.assertEqual(len(recorder.fight_events(0, 10000)), 2)
        recorder.reset()
        self.assertEqual(len(recorder.fight_events(0, 10000)), 0)

    def test_names_are_asked_for_only_for_a_hit_kept(self):
        asked = []

        def describe():
            asked.append(1)
            return "@a", "Boss", "70"

        recorder = fe.EventRecorder()
        small = ["DAMAGE", "", "", "1000", "0", "7", "99", "70", "", "",
                 "", "", "", "", "", "", "", "1", "19000/20000"]
        recorder.note_on_player(100, "DAMAGE", small, "1", describe)
        self.assertEqual(asked, [])

    def test_more_than_65535_names_in_a_fight(self):
        """A long open-world stretch can name more units than a 16-bit
        index holds."""
        recorder = fe.EventRecorder()
        for n in range(40000):
            recorder.note_taunt(n, f"@p{n}", f"k{n}", "1", "Boss", "70", False)
        events = recorder.fight_events(0, 10**6)
        last = list(events.records())[-1]
        self.assertEqual((last.who, last.who_key), ("@p39999", "k39999"))

    def test_marks_across_a_fight_cut_in_two_and_a_new_pull(self):
        recorder = fe.EventRecorder()
        recorder.note_boss_health(1000, "Boss", "70", "800/1000")
        recorder.note_boss_health(2000, "Boss", "70", "760/1000")
        recorder.prune_before(500)     # the first part's entry is built
        recorder.note_boss_health(3000, "Boss", "70", "740/1000")  # goes on: 75% reached
        recorder.note_boss_health(4000, "Boss", "70", "1000/1000")  # a new pull
        recorder.note_boss_health(5000, "Boss", "70", "700/1000")   # 75% again
        recorder.note_boss_health(6000, "Boss", "70", "800/1000")   # healed over 75%
        recorder.note_boss_health(7000, "Boss", "70", "690/1000")   # no mark twice
        marks = [(r.t, r.value) for r in _kinds(recorder.fight_events(0, 9000), fe.BOSS_HEALTH)]
        self.assertEqual(marks, [(3000, 75), (5000, 75)])

    def test_abilities_are_named_once(self):
        recorder = fe.EventRecorder()
        recorder.note_taunt(100, "@a", "1", "38254", "Boss", "70", True)
        recorder.note_taunt(200, "@b", "2", "38254", "Boss", "70", True)
        named = []
        events = recorder.fight_events(0, 1000, ability=lambda a: named.append(a) or ("Fire", "f"))
        self.assertEqual(named, ["38254"])
        self.assertEqual(events.abilities(), {"38254": ("Fire", "f")})


class TestEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fight = _run(FIGHT).fight_history.fights[0]
        cls.events = cls.fight.events

    def test_the_bosses_cast_and_who_stopped_it(self):
        cast, = _kinds(self.events, fe.BOSS_CAST)
        self.assertEqual((cast.t, cast.who, cast.ability_id, cast.other, cast.value),
                         (2000, "Lokkestiiz", "555", "@first", 2000))
        self.assertTrue(cast.flags & fe.AT_PLAYER)
        stop, = _kinds(self.events, fe.CAST_STOPPED)
        self.assertEqual((stop.t, stop.other, stop.other_key), (2500, "@second", "2"))

    def test_the_bosses_health(self):
        self.assertEqual([(r.t, r.value) for r in _kinds(self.events, fe.BOSS_HEALTH)],
                         [(1000, 75), (9000, 50)])
        self.assertEqual([(r.t, r.value) for r in _kinds(self.events, fe.UNTOUCHED)],
                         [(1000, 7000), (9000, 10000)])

    def test_a_big_hit_with_its_shield(self):
        hit, = _kinds(self.events, fe.HIT)
        self.assertEqual((hit.t, hit.who, hit.who_key, hit.other, hit.value, hit.value2,
                          hit.value3), (3001, "@first", "1", "Lokkestiiz", 9000, 20000, 4000))

    def test_taunts_resurrection_return_and_map(self):
        self.assertEqual([(r.t, r.who, r.other, bool(r.flags & fe.ON_BOSS))
                          for r in _kinds(self.events, fe.TAUNT)],
                         [(100, "@second", "Lokkestiiz", True), (5000, "@third", "Lokkestiiz", True),
                          (6000, "@third", "Lokkestiiz", True)])
        rez, = _kinds(self.events, fe.RESURRECT)
        self.assertEqual((rez.t, rez.who, rez.other), (15000, "@third", "@first"))
        back, = _kinds(self.events, fe.REVIVED)
        self.assertEqual((back.t, back.who, back.who_key, back.value), (16000, "@third", "3", 6000))
        self.assertEqual([r.other for r in _kinds(self.events, fe.MAP)], ["The Upper Vault"])

    def test_a_fight_the_game_cut_in_two(self):
        """END_COMBAT and BEGIN_COMBAT half a second apart, the boss still
        alive: one fight, its events from both parts, and the resume."""
        fight, = _run(FIGHT + [
            "30500,BEGIN_COMBAT",
            _boss_hit(33000, 300000),
            "36000,END_COMBAT",
        ]).fight_history.fights
        self.assertEqual([(r.t, r.value) for r in _kinds(fight.events, fe.RESUMED)],
                         [(20500, 500)])
        self.assertEqual([r.value for r in _kinds(fight.events, fe.BOSS_HEALTH)], [75, 50])
        self.assertEqual(len(_kinds(fight.events, fe.TAUNT)), 3)

    def test_an_entry_built_before_the_events_has_no_rows(self):
        self.assertEqual(event_rows.event_rows(SimpleNamespace(events=None)), [])


class TestRows(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fight = _run(FIGHT).fight_history.fights[0]
        cls.rows = event_rows.event_rows(cls.fight)

    def _of(self, category):
        return [row for row in self.rows if row.category == category]

    def test_rows_in_time_order(self):
        times = [row.t for row in self.rows]
        self.assertEqual(times, sorted(times))

    def test_death_and_back(self):
        died, back = self._of("deaths")
        self.assertEqual((died.t, died.what, died.who, died.who_keys, died.death),
                         (10000, "Died", "@third", ("3",), ("3", 1)))
        self.assertIn("from Lokkestiiz", died.detail)
        self.assertIn("dead 6.0 s, resurrected by @first at 0:16.0", died.detail)
        self.assertEqual((back.t, back.what, back.detail),
                         (16000, "Back", "resurrected by @first · dead 6.0 s"))

    def test_the_boss(self):
        rows = {row.what: row for row in self._of("boss")}
        cast = rows["Boss cast"]
        self.assertEqual((cast.ability, cast.who), ("Storm Fury", "Lokkestiiz"))
        self.assertIn("at @first", cast.detail)
        self.assertIn("interrupted by @second", cast.detail)
        self.assertEqual([row.ability for row in self._of("boss") if row.what == "Boss health"],
                         ["75%", "50%"])
        self.assertEqual([row.detail for row in self._of("boss") if row.what == "Untouched"],
                         ["lost no health for 7.0 s (0:01.0 to 0:08.0)",
                          "lost no health for 10.0 s (0:09.0 to 0:19.0)"])

    def test_a_big_hit(self):
        hit, = self._of("hits")
        self.assertEqual((hit.ability, hit.who), ("Toppling Blow", "@first"))
        self.assertEqual(hit.detail, "65% of max health, 4,000 of it shielded · from Lokkestiiz")

    def test_taunt_swaps(self):
        first, swap = self._of("taunts")
        self.assertEqual((first.who, first.detail), ("@second", "first taunt on Lokkestiiz"))
        self.assertEqual((swap.who, swap.who_keys, swap.detail),
                         ("@third", ("3", "2"), "took Lokkestiiz from @second"))

    def test_phases(self):
        row, = self._of("phases")
        self.assertEqual((row.what, row.ability), ("Map", "The Upper Vault"))

    def test_the_fought_on_rebuild_carries_the_events(self):
        """The group fighting on after END_COMBAT rebuilds the entry; its
        events go with the slots that rebuild takes (waiting_hits), as its
        deaths do."""
        from waiting_hits import FOUGHT_ON_SLOTS
        self.assertIn("events", FOUGHT_ON_SLOTS)

    def test_shown_by_category(self):
        self.assertEqual(event_rows.shown(self.rows, ["taunts"]), self._of("taunts"))
        self.assertEqual(set(event_rows.DEFAULT_CATEGORIES) | set(event_rows.MORE),
                         {key for key, _label in event_rows.CATEGORIES})


def _events(*notes):
    """A FightEvents from recorder calls (name, args...)."""
    recorder = fe.EventRecorder()
    for name, *args in notes:
        getattr(recorder, name)(*args)
    return recorder.fight_events(0, 600000, ability=lambda a: (f"Ability {a}", ""))


class TestRowRules(unittest.TestCase):

    def test_the_clock_rounds_to_tenths_first(self):
        self.assertEqual([event_rows.clock(ms) for ms in (59960, 119970, 61449, -3200, 0)],
                         ["1:00.0", "2:00.0", "1:01.4", "-0:03.2", "0:00.0"])

    def test_returns_from_the_dead(self):
        """Who raised whom, a raiser the log does not name, and a player
        dead since an earlier pull."""
        notes = [("note_resurrect", 9000, "@a", "1", "@b", "2", "26770"),
                 ("note_resurrect", 19000, "@c", "3", "", "9", "26770")]
        recorder = fe.EventRecorder()
        for name, *args in notes:
            getattr(recorder, name)(*args)
        events = recorder.fight_events(0, 60000, revived=[
            (10000, "@a", "1", 4000, False), (20000, "@c", "3", 5000, False),
            (30000, "@d", "4", 30000, True)])
        entry = SimpleNamespace(duration_s=60.0, death_recaps=[], trial_result=None,
                                events=events)
        backs = [row.detail for row in event_rows.event_rows(entry) if row.what == "Back"]
        self.assertEqual(backs, ["resurrected by @b · dead 4.0 s",
                                 "resurrected by a unit the log does not name · dead 5.0 s",
                                 "back, no line says how · dead since before the pull"])

    def test_a_burst_of_one_cast_is_one_row(self):
        entry = SimpleNamespace(duration_s=60.0, death_recaps=[], trial_result=None,
                                events=_events(*[("note_boss_cast", t, "Boss", "70", str(t), "9",
                                                  f"@{t}", str(t), 0, True)
                                                 for t in (1000, 2500, 4000, 9000)]))
        rows = event_rows.event_rows(entry)
        self.assertEqual([(row.t, row.ability) for row in rows],
                         [(1000, "Ability 9 x3"), (9000, "Ability 9")])
        self.assertIn("3 casts over 3.0 s · at 3 players", rows[0].detail)

    def test_casts_at_the_taunt_holder_and_auto_attacks(self):
        notes = [("note_taunt", 500, "@tank", "2", "38254", "Boss", "70", True)]
        # A heavy swing at the tank, every 6 s: at the tank
        notes += [("note_boss_cast", t, "Boss", "70", f"s{t}", "11", "@tank", "2", 1500, True)
                  for t in (1000, 7000)]
        # A quick strike at players, nine times in a minute: an auto-attack
        notes += [("note_boss_cast", 20000 + 4000 * i, "Boss", "70", f"a{i}", "12", "@dps", "1",
                   500, True) for i in range(9)]
        entry = SimpleNamespace(duration_s=60.0, death_recaps=[], trial_result=None,
                                events=_events(*notes))
        categories = {row.ability: row.category for row in event_rows.event_rows(entry)
                      if row.what == "Boss cast"}
        self.assertEqual(categories, {"Ability 11": "tank", "Ability 12": "auto"})

    def test_hits_chained_and_the_killing_hit_left_to_the_death(self):
        hit = ["DAMAGE", "", "", "12000", "0", "7", "99", "70", "", "",
               "", "", "", "", "", "", "", "1", "8000/20000"]
        small = ["DAMAGE", "", "", "7000", "0", "8", "98", "70", "", "",
                 "", "", "", "", "", "", "", "1", "8000/20000"]
        notes = [("note_on_player", t, "DAMAGE", hit, key, _named(name))
                 for t, key, name in ((1000, "1", "@a"), (2000, "2", "@b"), (4500, "3", "@c"))]
        notes += [("note_on_player", 9000, "DAMAGE", hit, "4", _named("@d")),
                  ("note_on_player", 12000, "DAMAGE", small, "1", _named("@a"))]
        recap = {"unit_id": "4", "name": "@d", "time_ms": 9100, "ability": "Ability 99",
                 "ability_id": "99", "killer": "Boss", "icon": "", "cause": ""}
        entry = SimpleNamespace(duration_s=60.0, death_recaps=[recap], trial_result=None,
                                events=_events(*notes))
        rows = event_rows.event_rows(entry)
        hits = [row for row in rows if row.category == "hits"]
        self.assertEqual([(row.t, row.ability, row.who) for row in hits],
                         [(1000, "Ability 99 x3", "3 players")])
        self.assertIn("3 hits on 3 players over 3.5 s, 60 to 60% of max health", hits[0].detail)
        self.assertEqual([(row.t, row.category) for row in rows if row.what == "Hit"
                          and row.category == "hits30"], [(12000, "hits30")])
        died, = [row for row in rows if row.what == "Died"]
        self.assertIn("dead to the end (50.9 s)", died.detail)

    def test_deaths_to_one_ability_at_once_are_one_row(self):
        recaps = [{"unit_id": key, "name": f"@{key}", "time_ms": t, "ability": "Melt",
                   "ability_id": "5", "killer": "Boss", "icon": "", "cause": cause}
                  for key, t, cause in (("1", 1000, ""), ("2", 1500, "health"), ("3", 9000, ""))]
        entry = SimpleNamespace(duration_s=60.0, death_recaps=recaps, trial_result={"x": 1},
                                events=_events())
        rows = event_rows.event_rows(entry)
        deaths = [row for row in rows if row.category == "deaths"]
        self.assertEqual([(row.t, row.what, row.who, row.death) for row in deaths],
                         [(1000, "Died x2", "@1, @2", None), (9000, "Died", "@3", ("3", 1))])
        self.assertIn("no death line; read from health reaching 0", deaths[0].detail)
        self.assertEqual([(row.t, row.what) for row in rows if row.category == "phases"],
                         [(60000, "Trial")])


if __name__ == "__main__":
    unittest.main()
