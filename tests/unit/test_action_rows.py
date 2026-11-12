"""
One player's actions on the Events tab (issue #214): the cast recorder's
targets and ends (casts.CastRecorder), the packed casts on the fight entry
(fight_casts), the engine that keeps them, and the actions' rows
(action_rows).
"""

import unittest
from types import SimpleNamespace

import action_rows as ar
import casts
import fight_casts
import fight_events as fe
from casts import CAST_END, CAST_FLAGS, CAST_TARGET
from tests.unit.test_fight_events import FIGHT, _boss, _player, _run

FORCE_PULSE, BLUE_BETTY, CRYSTAL = "46356", "86054", "46324"
ELEMENTAL_BLOCKADE, BLOCKADE_OF_FROST = "39011", "39028"
METEOR, WEREWOLF_POUNCE = "16536", "32632"
LIGHT, HEAVY, SWAP, POTION, CONDUIT = "18350", "18396", "28541", "45221", "23196"

NAMES = {FORCE_PULSE: ("Force Pulse", "force"), BLUE_BETTY: ("Blue Betty", "betty"),
         CRYSTAL: ("Crystal Fragments", "crystal"),
         ELEMENTAL_BLOCKADE: ("Elemental Blockade", "blockade"),
         BLOCKADE_OF_FROST: ("Blockade of Frost", "frost"), METEOR: ("Meteor", "meteor"),
         WEREWOLF_POUNCE: ("Pounce", "pounce"),
         LIGHT: ("Light Attack (Lightning)", "light"), HEAVY: ("Heavy Attack (Lightning)", "heavy"),
         SWAP: ("Swap Weapons", "swap"), POTION: ("Restore Health", "potion"),
         CONDUIT: ("Conduit", "conduit")}


def _named(ability_id):
    return NAMES.get(ability_id, (f"Ability {ability_id}", ""))


def _slot(ability_id, **more):
    return dict({"id": ability_id, "name": NAMES[ability_id][0]}, **more)


def _row(key="1", local=True, role="D", **more):
    """A player row: Force Pulse in F2, Crystal Fragments in F3 and on the
    back bar too, Meteor the front ultimate; Elemental Blockade in B1."""
    front = [_slot(BLUE_BETTY), _slot(FORCE_PULSE), _slot(CRYSTAL), _slot(BLUE_BETTY),
             _slot(BLUE_BETTY), _slot(METEOR)]
    back = [_slot(ELEMENTAL_BLOCKADE), _slot(BLUE_BETTY), _slot(CRYSTAL), _slot(BLUE_BETTY),
            _slot(BLUE_BETTY), _slot(BLUE_BETTY)]
    row = {"unit_id": key, "name": f"@p{key}", "role": role, "class_name": "Sorcerer",
           "is_local": local, "front_bar_slots": front, "back_bar_slots": back}
    row.update(more)
    return row


def _cast(t, ability_id, target=None, end=None, interrupted=False):
    """A cast as the recorder keeps it."""
    return [t, ability_id, target, end, casts.INTERRUPTED if interrupted else 0]


def _entry(by_player, rows=None, notes=(), recaps=(), duration_s=60.0, revived=()):
    """A fight entry: *by_player* {key: [casts]}, its rows, the events from
    recorder calls (name, args...) and the deaths' recaps."""
    recorder = fe.EventRecorder()
    for name, *args in notes:
        getattr(recorder, name)(*args)
    events = recorder.fight_events(0, 600000, revived=revived, ability=_named)
    rows = rows if rows is not None else [_row(key, local=key == "1") for key in by_player]
    return SimpleNamespace(duration_s=duration_s, death_recaps=list(recaps), trial_result=None,
                           events=events, players=rows, player_names=[],
                           casts=fight_casts.pack(list(by_player.items()), 0, _named))


def _casts_of(rows):
    return [row for row in rows if row.category == ar.CASTS]


class TestRecorder(unittest.TestCase):

    def test_the_target_is_named_once_as_a_new_cast_is_noted(self):
        asked = []

        def target_of(unit_id):
            asked.append(unit_id)
            return {"70": ("Boss", "70"), "8": ("@b", "2")}.get(unit_id)

        recorder = casts.CastRecorder()
        recorder.note_cast("1", "900", HEAVY, 1000, "70", "5", target_of)
        recorder.note_cast("1", "900", HEAVY, 1015, "70", "5", target_of)  # the same cast
        recorder.note_cast("1", "901", FORCE_PULSE, 2000, "8", "5", target_of)
        recorder.note_cast("1", "902", FORCE_PULSE, 3000, "99", "5", target_of)  # unknown unit
        self.assertEqual(asked, ["70", "8", "99"])
        records = recorder.cast_records("1", 0, 9000)
        self.assertEqual([cast[CAST_TARGET] for cast in records],
                         [("Boss", "70"), ("@b", "2"), None])

    def test_no_target_for_none_or_the_caster(self):
        """'*' (the caster), '0' (none) and the caster's own unit id are
        never looked up; a unit that turns out to be the caster's record
        (back on another unit id) is dropped after the lookup."""
        asked = []

        def named(unit_id):
            asked.append(unit_id)
            return ("@a", "1") if unit_id == "6" else ("Unit", unit_id)

        recorder = casts.CastRecorder()
        recorder.note_cast("1", "1", FORCE_PULSE, 1000, "*", "5", named)
        recorder.note_cast("1", "2", FORCE_PULSE, 2000, "0", "5", named)
        recorder.note_cast("1", "3", FORCE_PULSE, 3000, "5", "5", named)
        # The caster back on another unit id: their own record
        recorder.note_cast("1", "4", FORCE_PULSE, 4000, "6", "5", named)
        recorder.note_cast("1", "5", FORCE_PULSE, 5000, "70", "5")  # no resolver: none kept
        self.assertEqual([cast[CAST_TARGET] for cast in recorder.cast_records("1", 0, 9000)],
                         [None] * 5)
        self.assertEqual(asked, ["6"])

    def test_the_end_cast_ends_the_cast_its_track_last_began(self):
        recorder = casts.CastRecorder()
        recorder.note_cast("1", "7", HEAVY, 1000)
        recorder.note_cast("1", "7", HEAVY, 1015)           # the channel: the same cast
        recorder.note_end("7", 2600)
        recorder.note_cast("1", "8", FORCE_PULSE, 3000)
        recorder.note_end("8", 3400, "INTERRUPTED")
        recorder.note_cast("1", "9", FORCE_PULSE, 4000)    # cancelled: no END_CAST
        # A synergy taken again under its first take's track: each its end
        recorder.note_cast("1", "10", CONDUIT, 5000)
        recorder.note_end("10", 5000)
        recorder.note_cast("1", "10", CONDUIT, 9000)
        recorder.note_end("10", 9002)
        recorder.note_end("11", 9500)                       # no one's track
        ends = [(cast[0], cast[CAST_END], cast[CAST_FLAGS])
                for cast in recorder.cast_records("1", 0, 10000)]
        self.assertEqual(ends, [(1000, 2600, 0), (3000, 3400, casts.INTERRUPTED),
                                (4000, None, 0), (5000, 5000, 0), (9000, 9002, 0)])

    def test_a_track_forgotten_at_a_fights_start_ends_nothing(self):
        recorder = casts.CastRecorder()
        recorder.note_cast("1", "7", FORCE_PULSE, 1000)
        recorder.note_cast("1", "8", FORCE_PULSE, 6000)
        recorder.prune_before(5000)
        self.assertNotIn("7", recorder._open)
        recorder.note_end("7", 7000)
        recorder.note_end("8", 7000)
        self.assertEqual([(cast[0], cast[CAST_END]) for cast in recorder.cast_records("1", 0, 9000)],
                         [(6000, 7000)])
        recorder.note_cast("1", "9", FORCE_PULSE, 8000)  # open at the reset
        recorder.reset()
        self.assertEqual(recorder._open, {})

    def test_the_records_are_the_counts_casts(self):
        """The casts the entry keeps are the counts' own: a proc left out
        unless it is on the bars."""
        recorder = casts.CastRecorder()
        for at in (1000, 2000, 3000):
            recorder.note_cast("1", "50", "117119", at)
            recorder.note_end("50", at)
        recorder.note_cast("1", "51", FORCE_PULSE, 1500)
        for slotted in ((), {"117119"}):
            records = recorder.cast_records("1", 0, 5000, slotted)
            self.assertEqual(len(records), sum(recorder.fight_counts("1", 0, 5000, slotted).values()))
            self.assertEqual([(cast[0], cast[1]) for cast in records],
                             recorder.casts_between("1", 0, 5000, slotted))


class TestPacked(unittest.TestCase):

    def test_packed_from_the_fights_start(self):
        packed = fight_casts.pack([("1", [_cast(10500, FORCE_PULSE, ("Boss", "70"), 10500),
                                          _cast(11700, HEAVY, ("Boss", "70"), 13300)]),
                                   ("2", [_cast(12000, POTION)]), ("3", [])], 10000, _named)
        self.assertEqual(packed.keys(), ("1", "2", "3"))
        self.assertEqual((packed.count("1"), packed.count("2"), packed.count("3"),
                          packed.count("9")), (2, 1, 0, 0))
        self.assertEqual(len(packed), 3)
        self.assertEqual(packed.nbytes, 3 * fight_casts._RECORD.size)
        self.assertEqual(fight_casts._RECORD.size, 17)
        first, second = packed.of("1")
        self.assertEqual(first, fight_casts.Cast(500, FORCE_PULSE, "Boss", "70", 0,
                                                 fight_casts.ENDED))
        self.assertEqual((second.t, second.length), (1700, 1600))
        potion, = packed.of("2")
        self.assertEqual((potion.target, potion.target_key, potion.length, potion.flags),
                         ("", "", 0, 0))
        self.assertEqual(packed.of("9"), [])
        self.assertEqual(packed.abilities(), {FORCE_PULSE: NAMES[FORCE_PULSE],
                                              HEAVY: NAMES[HEAVY], POTION: NAMES[POTION]})
        self.assertEqual(packed, fight_casts.pack([("1", [_cast(10500, FORCE_PULSE, ("Boss", "70"),
                                                                10500),
                                                          _cast(11700, HEAVY, ("Boss", "70"),
                                                                13300)]),
                                                   ("2", [_cast(12000, POTION)]), ("3", [])],
                                                  10000, _named))
        self.assertEqual(fight_casts.casts_of(SimpleNamespace(casts=None), "1"), [])

    def test_an_interrupted_cast(self):
        packed = fight_casts.pack([("1", [_cast(100, FORCE_PULSE, None, 900, interrupted=True)])],
                                  0)
        cast, = packed.of("1")
        self.assertEqual((cast.length, cast.flags),
                         (800, fight_casts.ENDED | fight_casts.INTERRUPTED))

    def test_more_than_65535_targets(self):
        """A long open-world stretch can name more units than a 16-bit
        index holds."""
        packed = fight_casts.pack([("1", [_cast(n, FORCE_PULSE, (f"Unit {n}", str(n)))
                                          for n in range(70000)])], 0)
        last = packed.of("1")[-1]
        self.assertEqual((last.target, last.target_key), ("Unit 69999", "69999"))


class TestCastRows(unittest.TestCase):

    def test_the_bar_slot(self):
        entry = _entry({"1": [_cast(1000, FORCE_PULSE), _cast(2000, METEOR),
                              _cast(3000, BLOCKADE_OF_FROST), _cast(4000, CRYSTAL),
                              _cast(5000, "999"), _cast(6000, HEAVY),
                              _cast(7000, WEREWOLF_POUNCE)]},
                       rows=[_row("1", werewolf_bar_slots=[
                           _slot(WEREWOLF_POUNCE), _slot(BLUE_BETTY, ultimate=True)])])
        rows = _casts_of(ar.action_rows(entry, "1"))
        # Blockade of Frost is cast for the slotted Elemental Blockade (a
        # family); Crystal Fragments is on both bars
        self.assertEqual([(row.action, row.bar) for row in rows],
                         [("Force Pulse", "F2"), ("Meteor", "FU"), ("Blockade of Frost", "B1"),
                          ("Crystal Fragments", "F3/B3"), ("Ability 999", ""),
                          ("Heavy Attack (Lightning)", ""), ("Pounce", "W1")])

    def test_a_light_attack_folds_into_the_skill_after_it(self):
        entry = _entry({"1": [_cast(1000, LIGHT), _cast(1250, FORCE_PULSE),   # folded
                              _cast(2000, LIGHT), _cast(2400, FORCE_PULSE),   # too long before
                              _cast(3000, LIGHT), _cast(3100, HEAVY),         # no skill after
                              _cast(4000, LIGHT), _cast(4100, POTION),
                              _cast(4250, CRYSTAL)]}, duration_s=5.0)        # past the potion
        rows = ar.action_rows(entry, "1")
        self.assertEqual([(row.t, row.la, row.action) for row in rows],
                         [(1250, "LA", "Force Pulse"), (2000, "", "Light Attack (Lightning)"),
                          (2400, "", "Force Pulse"), (3000, "", "Light Attack (Lightning)"),
                          (3100, "", "Heavy Attack (Lightning)"), (4100, "", "Restore Health"),
                          (4250, "LA", "Crystal Fragments")])
        # As rows: every light attack, no mark
        rows = ar.action_rows(entry, "1", light_rows=True)
        self.assertEqual(sum(1 for row in rows if row.action.startswith("Light")), 4)
        self.assertFalse(any(row.la for row in rows))

    def test_a_swap_is_a_mark_on_the_next_cast(self):
        entry = _entry({"1": [_cast(1000, SWAP), _cast(1200, LIGHT), _cast(1400, FORCE_PULSE),
                              _cast(5000, SWAP), _cast(8000, FORCE_PULSE),
                              _cast(9000, SWAP), _cast(9300, HEAVY)]}, duration_s=10.0)
        rows = _casts_of(ar.action_rows(entry, "1"))
        # The light attack folds into Force Pulse, which takes the swap's
        # mark; a swap no cast follows within SWAP_FOLD_MS stays a row; a
        # cast not on a bar takes the mark alone
        self.assertEqual([(row.t, row.bar, row.la, row.action) for row in rows],
                         [(1400, "⇄F2", "LA", "Force Pulse"), (5000, "", "", "Swap Weapons"),
                          (8000, "F2", "", "Force Pulse"),
                          (9300, "⇄", "", "Heavy Attack (Lightning)")])
        rows = _casts_of(ar.action_rows(entry, "1", swap_rows=True))
        self.assertEqual(sum(1 for row in rows if row.action == "Swap Weapons"), 3)
        self.assertFalse(any(row.bar.startswith(ar.SWAP_MARK) for row in rows))

    def test_the_length_only_from_an_end_cast(self):
        entry = _entry({"1": [_cast(1000, HEAVY, end=2600), _cast(3000, FORCE_PULSE, end=3001),
                              _cast(4000, FORCE_PULSE), _cast(5000, CRYSTAL, end=5900,
                                                              interrupted=True)]})
        rows = _casts_of(ar.action_rows(entry, "1"))
        self.assertEqual([(row.length, row.detail) for row in rows],
                         [("1.6 s", ""), ("", ""), ("", ""), ("0.9 s", "interrupted")])

    def test_the_gap_since_the_skill_before(self):
        entry = _entry({"1": [_cast(1000, FORCE_PULSE), _cast(1500, LIGHT), _cast(1900, POTION),
                              _cast(2100, CRYSTAL), _cast(3300, HEAVY), _cast(4500, METEOR)]},
                       duration_s=5.0)
        rows = ar.action_rows(entry, "1", light_rows=True)
        self.assertEqual([(row.action, row.gap) for row in rows],
                         [("Force Pulse", ""), ("Light Attack (Lightning)", ""),
                          ("Restore Health", ""), ("Crystal Fragments", "1.1 s"),
                          ("Heavy Attack (Lightning)", ""), ("Meteor", "2.4 s")])
        self.assertEqual([row.detail for row in rows][2], "potion")

    def test_the_target(self):
        entry = _entry({"1": [_cast(1000, FORCE_PULSE, ("Lokkestiiz", "70")),
                              _cast(2000, CRYSTAL)]}, duration_s=3.0)
        self.assertEqual([row.target for row in ar.action_rows(entry, "1")], ["Lokkestiiz", ""])

    def test_an_extra_takes_no_bar_slot(self):
        """Bar is a skill's slot: an extra reads blank even when a slot
        holds its ability (here a heavy attack's id)."""
        entry = _entry({"1": [_cast(1000, HEAVY)]},
                       rows=[_row("1", front_bar_slots=[_slot(HEAVY)])], duration_s=2.0)
        cast, = _casts_of(ar.action_rows(entry, "1"))
        self.assertEqual((cast.action, cast.bar), ("Heavy Attack (Lightning)", ""))

    def test_an_entry_before_the_casts_has_no_rows(self):
        self.assertEqual(ar.action_rows(SimpleNamespace(casts=None, players=[]), "1"), [])


def _hit(share_of_20000, blocked=False):
    """A hit's fields for note_on_player: *share_of_20000* of the player's
    20,000 health."""
    return ["BLOCKED_DAMAGE" if blocked else "DAMAGE", "", "", str(share_of_20000), "0", "7",
            "99", "70", "", "", "", "", "", "", "", "", "", "1", "5000/20000"]


def _who(name, key="70"):
    return lambda: (name, "Boss", key)


class TestEventsBetween(unittest.TestCase):

    def setUp(self):
        notes = [
            # A taunt on the boss by player 2, then player 3 takes it; then
            # player 2 taunts again (a swap back), player 1 never
            ("note_taunt", 1000, "@p2", "2", "38254", "Boss", "70", True),
            ("note_taunt", 2000, "@p3", "3", "38254", "Boss", "70", True),
            ("note_taunt", 2500, "@p3", "3", "38254", "Boss", "70", True),
            # The boss's casts: at player 1 twice in a burst, interrupted;
            # at player 2 once
            ("note_boss_cast", 3000, "Boss", "70", "t1", "555", "@p1", "1", 2000, True),
            ("note_boss_cast", 4000, "Boss", "70", "t2", "555", "@p1", "1", 2000, True),
            ("note_cast_end", 4500, "t2", "INTERRUPTED", "@p2", "2", False),
            ("note_boss_cast", 5000, "Boss", "70", "t3", "556", "@p2", "2", 2000, True),
            # Hits on player 1: 35% (a 30 to 49% hit) and 60%; then two in a
            # chain; a hit on player 2
            ("note_on_player", 2000, "DAMAGE", _hit(7000), "1", _who("@p1")),
            ("note_on_player", 7000, "DAMAGE", _hit(12000), "1", _who("@p1")),
            ("note_on_player", 7500, "DAMAGE", _hit(12000), "1", _who("@p1")),
            ("note_on_player", 6500, "DAMAGE", _hit(12000), "2", _who("@p2")),
            # The killing hit on player 1, at 20 s: the death's row tells it
            ("note_on_player", 19950, "DAMAGE", _hit(15000), "1", _who("@p1")),
            ("note_boss_health", 8000, "Boss", "70", "1000/1000"),
            ("note_boss_health", 9000, "Boss", "70", "700/1000"),
            ("note_map", 10000, "Upper"),
        ]
        recaps = [{"unit_id": "1", "name": "@p1", "time_ms": 20000, "ability": "Ability 99",
                   "ability_id": "99", "killer": "Boss", "icon": "", "cause": ""}]
        self.entry = _entry({"1": [_cast(500, FORCE_PULSE), _cast(9000, FORCE_PULSE)],
                             "2": [_cast(500, FORCE_PULSE)], "3": [_cast(500, FORCE_PULSE)]},
                            notes=notes, recaps=recaps, duration_s=40.0,
                            revived=[(30000, "@p1", "1", 10000, False)])

    def _of(self, key, category):
        return [row for row in ar.action_rows(self.entry, key) if row.category == category]

    def test_the_players_death_and_return(self):
        died, back = self._of("1", "deaths")
        self.assertEqual((died.t, died.action, died.death, died.strong),
                         (20000, "Died: Ability 99", ("1", 1), True))
        self.assertIn("dead 10.0 s", died.detail)
        self.assertEqual((back.t, back.action), (30000, "Back"))
        self.assertEqual(self._of("2", "deaths"), [])

    def test_the_hits_they_took_of_30_percent_or_more(self):
        hits = self._of("1", "hits")
        self.assertEqual([(row.t, row.action, row.detail) for row in hits],
                         [(2000, "Hit: Ability 99", "35% of max health · from Boss"),
                          (7000, "Hit: Ability 99 x2",
                           "2 hits, 60 to 60% of max health · from Boss")])
        self.assertEqual(len(self._of("2", "hits")), 1)

    def test_the_bosses_casts_at_them(self):
        cast, = self._of("1", "boss")
        self.assertEqual((cast.t, cast.action), (3000, "Boss cast: Ability 555 x2"))
        self.assertEqual(cast.detail, "from Boss · 2 casts over 1.0 s · interrupted by @p2")
        self.assertEqual([row.action for row in self._of("2", "boss")], ["Boss cast: Ability 556"])

    def test_the_taunt_swaps_they_were_in(self):
        self.assertEqual(self._of("1", "taunts"), [])
        self.assertEqual([row.detail for row in self._of("2", "taunts")],
                         ["@p2 taunted Boss first", "@p3 took Boss from @p2"])
        self.assertEqual([row.detail for row in self._of("3", "taunts")],
                         ["@p3 took Boss from @p2"])

    def test_context_rows_muted(self):
        rows = self._of("2", ar.CONTEXT)
        self.assertEqual([(row.t, row.action) for row in rows],
                         [(9000, "Boss health: 75%"), (10000, "Map: Upper")])
        self.assertTrue(all(row.muted for row in rows))
        self.assertFalse(any(row.muted for row in ar.action_rows(self.entry, "2")
                             if row.category != ar.CONTEXT))

    def test_the_phases_rows_are_context_rows(self):
        """Phases is greyed out for one player: its rows (the map, combat
        begun again, the trial's end) are context rows there, as its
        tooltip says, worded as event_rows words them."""
        import event_rows
        entry = _entry({"1": [_cast(500, FORCE_PULSE)]}, duration_s=40.0,
                       notes=[("note_map", 10000, "Upper"), ("note_resumed", 12000, 36)])
        entry.trial_result = {"score": 1}
        rows = [row for row in ar.action_rows(entry, "1") if row.category == ar.CONTEXT]
        self.assertEqual([(row.t, row.action) for row in rows],
                         [(10000, "Map: Upper"), (12000, "Combat: resumed"),
                          (40000, "Trial: ended")])
        self.assertTrue(all(row.muted for row in rows))
        phases = [row for row in event_rows.event_rows(entry) if row.category == "phases"]
        self.assertEqual([(row.t, row.detail) for row in rows[1:]],
                         [(row.t, row.detail) for row in phases[1:]])
        self.assertFalse([row for row in ar.shown(ar.action_rows(entry, "1"), [], context=False)
                          if row.category == ar.CONTEXT])

    def test_in_time_order_and_shown_by_category(self):
        rows = ar.action_rows(self.entry, "1")
        self.assertEqual([row.t for row in rows], sorted(row.t for row in rows))
        shown = ar.shown(rows, ["deaths"], context=False)
        self.assertEqual({row.category for row in shown}, {ar.CASTS, ar.IDLE, "deaths"})
        self.assertIn(ar.CONTEXT, {row.category for row in ar.shown(rows, [])})

    def test_the_summary(self):
        self.assertEqual(ar.summary_text(self.entry, "1"), "@p1 · D · Sorcerer · 2 casts · 1 death")
        self.assertEqual(ar.summary_text(self.entry, "2"),
                         "@p2 · D · Sorcerer · 1 cast · no deaths")


class TestNoCast(unittest.TestCase):

    def test_only_for_the_player_who_writes_the_log(self):
        casts_ = [_cast(1000, FORCE_PULSE), _cast(6000, FORCE_PULSE)]
        entry = _entry({"1": list(casts_), "2": list(casts_)}, duration_s=7.0)
        idle, = [row for row in ar.action_rows(entry, "1") if row.category == ar.IDLE]
        self.assertEqual((idle.t, idle.action, idle.detail), (1000, "No cast for 5.0 s", ""))
        self.assertEqual([row for row in ar.action_rows(entry, "2") if row.category == ar.IDLE], [])

    def test_from_the_end_of_a_cast_the_start_and_end_included(self):
        """From a cast's END_CAST (its start without one) to the next
        cast's start; the fight's start and its end count; under IDLE_MS
        is no row."""
        entry = _entry({"1": [_cast(3500, HEAVY, end=5000), _cast(7900, FORCE_PULSE),
                              _cast(9000, FORCE_PULSE)]}, duration_s=13.0)
        spans = ar.idle_spans(entry, "1", entry.casts.of("1"), [])
        self.assertEqual(spans, [(0, 3500), (9000, 13000)])

    def test_the_time_dead_is_cut_out(self):
        recaps = [{"unit_id": "1", "name": "@p1", "time_ms": 4000, "ability": "Melt",
                   "ability_id": "5", "killer": "Boss", "icon": "", "cause": ""},
                  {"unit_id": "1", "name": "@p1", "time_ms": 30000, "ability": "Melt",
                   "ability_id": "5", "killer": "Boss", "icon": "", "cause": ""}]
        entry = _entry({"1": [_cast(1000, FORCE_PULSE), _cast(25000, FORCE_PULSE)]},
                       recaps=recaps, duration_s=40.0,
                       revived=[(20000, "@p1", "1", 16000, False)])
        records = list(entry.events.records())
        self.assertEqual(ar.dead_spans(entry, "1", records), [(4000, 20000), (30000, 40000)])
        # 1 s to 25 s, less 4 s to 20 s; then 25 s to the end, less the
        # death at 30 s to the end
        self.assertEqual(ar.idle_spans(entry, "1", entry.casts.of("1"), records),
                         [(1000, 4000), (20000, 25000), (25000, 30000)])

    def test_dead_since_an_earlier_pull(self):
        entry = _entry({"1": [_cast(9000, FORCE_PULSE)]}, duration_s=10.0,
                       revived=[(6000, "@p1", "1", 50000, True)])
        records = list(entry.events.records())
        self.assertEqual(ar.dead_spans(entry, "1", records), [(0, 6000)])
        self.assertEqual(ar.idle_spans(entry, "1", entry.casts.of("1"), records), [(6000, 9000)])

    def test_what_the_log_says_of_the_stretch(self):
        notes = [("note_on_player", 2000, "BLOCKED_DAMAGE", _hit(9000, blocked=True), "1",
                  _who("@p1")),
                 ("note_on_player", 3000, "BLOCKED_DAMAGE", _hit(9000, blocked=True), "1",
                  _who("@p1")),
                 ("note_boss_health", 1000, "Boss", "70", "900/1000"),
                 ("note_boss_health", 8000, "Boss", "70", "800/1000"),
                 ("note_map", 5000, "Upper")]
        entry = _entry({"1": [_cast(1000, FORCE_PULSE), _cast(9000, FORCE_PULSE)]}, notes=notes,
                       duration_s=10.0)
        idle, = [row for row in ar.action_rows(entry, "1") if row.category == ar.IDLE]
        self.assertEqual(idle.detail, "2 big hits blocked · Boss lost no health from 0:01.0 to "
                                      "0:08.0 · the map changed at 0:05.0")
        self.assertNotIn("nothing", idle.detail)

    def test_a_stretch_comes_after_the_cast_it_follows(self):
        """A stretch with no cast that begins as a cast does (a cast with no
        end) is listed after that cast, not before it."""
        entry = _entry({"1": [_cast(0, FORCE_PULSE), _cast(5000, CRYSTAL)]}, duration_s=6.0)
        rows = ar.action_rows(entry, "1")
        self.assertEqual([(row.t, row.category) for row in rows],
                         [(0, ar.CASTS), (0, ar.IDLE), (5000, ar.CASTS)])


# ------------------------------------------------------------- the engine --

ABILITIES = [
    f'2600,ABILITY_INFO,{ability_id},"{name}","/esoui/art/icons/{icon}.dds",F,T'
    for ability_id, (name, icon) in NAMES.items()]


def _cast_line(ts, unit, ability, track, target, duration=0):
    """A BEGIN_CAST by *unit* (a player) aimed at the unit state *target*
    ('*': itself)."""
    return f"{ts},BEGIN_CAST,{duration},F,{track},{ability},{_player(unit)},{target}"


def _end(ts, track, ability, reason="COMPLETED"):
    return f"{ts},END_CAST,{reason},{track},{ability}"


# The fight test_fight_events replays, with the players' builds and casts:
# each line keeps the boss's health as that fight has it then
CASTS = [
    _cast_line(9000, 1, FORCE_PULSE, 500, _boss()),                  # before the pull
    *[f"10001,PLAYER_INFO,{unit},[],[],[],[{BLUE_BETTY},{FORCE_PULSE},{CRYSTAL}],"
      f"[{ELEMENTAL_BLOCKADE}]" for unit in (1, 2, 3)],
    _cast_line(10200, 1, LIGHT, 501, _boss(900000)), _end(10200, 501, LIGHT),
    _cast_line(10400, 1, FORCE_PULSE, 502, _boss(900000)), _end(10400, 502, FORCE_PULSE),
    _cast_line(11500, 1, HEAVY, 503, _boss(740000)),
    _cast_line(11515, 1, HEAVY, 503, _boss(740000)),                  # the channel
    _end(13100, 503, HEAVY),
    _cast_line(13500, 1, SWAP, 504, "*"), _end(13500, 504, SWAP),
    _cast_line(13600, 1, BLOCKADE_OF_FROST, 505, "*"),
    _cast_line(14000, 2, CRYSTAL, 506, _player(1, 11000)),            # at a player
    _cast_line(15500, 3, CRYSTAL, 507, _boss(740000), duration=1000),
    _end(16200, 507, CRYSTAL, "INTERRUPTED"),
    _cast_line(21000, 1, CRYSTAL, 508, _boss(480000)),
    _end(21500, 508, CRYSTAL, "PLAYER_CANCELLED"),                    # the parser rejects it
    _cast_line(31000, 1, FORCE_PULSE, 509, _boss(470000)),           # after the fight
]


def _fight_with_casts():
    lines = sorted(FIGHT + CASTS, key=lambda line: int(line.split(",")[0]))
    return _run(ABILITIES + lines).fight_history.fights[0]


class TestEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fight = _fight_with_casts()

    def test_the_casts_are_the_rows_counts(self):
        self.assertEqual(set(self.fight.casts.keys()), {"1", "2", "3"})
        for p in self.fight.players:
            self.assertEqual(self.fight.casts.count(p["unit_id"]), p["casts"]["total"])
        self.assertEqual(self.fight.casts.count("1"), 6)

    def test_each_casts_time_target_and_length(self):
        casts_ = self.fight.casts.of("1")
        self.assertEqual([(c.t, c.ability_id, c.target, c.target_key, c.length,
                           bool(c.flags & fight_casts.ENDED)) for c in casts_],
                         [(200, LIGHT, "Lokkestiiz", "70", 0, True),
                          (400, FORCE_PULSE, "Lokkestiiz", "70", 0, True),
                          (1500, HEAVY, "Lokkestiiz", "70", 1600, True),
                          (3500, SWAP, "", "", 0, True),
                          (3600, BLOCKADE_OF_FROST, "", "", 0, False),
                          (11000, CRYSTAL, "Lokkestiiz", "70", 0, False)])
        at_player, = self.fight.casts.of("2")
        self.assertEqual((at_player.target, at_player.target_key), ("@first", "1"))
        stopped, = self.fight.casts.of("3")
        self.assertEqual((stopped.length, stopped.flags),
                         (700, fight_casts.ENDED | fight_casts.INTERRUPTED))
        self.assertEqual(self.fight.casts.abilities()[HEAVY], ("Heavy Attack (Lightning)",
                                                              "heavy"))

    def test_the_logging_players_actions(self):
        rows = ar.action_rows(self.fight, "1")
        casts_ = _casts_of(rows)
        self.assertEqual([(row.action, row.bar, row.la, row.length) for row in casts_],
                         [("Force Pulse", "F2", "LA", ""),
                          ("Heavy Attack (Lightning)", "", "", "1.6 s"),
                          ("Blockade of Frost", "⇄B1", "", ""), ("Crystal Fragments", "F3", "", "")])
        boss, = [row for row in rows if row.category == "boss"]
        self.assertEqual(boss.detail, "from Lokkestiiz · interrupted by @second")
        hit, = [row for row in rows if row.category == "hits"]
        self.assertEqual(hit.detail, "65% of max health, 4,000 of it shielded · from Lokkestiiz")
        idle = [(row.t, row.action) for row in rows if row.category == ar.IDLE]
        self.assertEqual(idle, [(3600, "No cast for 7.4 s"), (11000, "No cast for 9.0 s")])
        # Another player's actions: no stretch with no cast
        self.assertFalse([row for row in ar.action_rows(self.fight, "2")
                          if row.category == ar.IDLE])

    def test_a_fight_the_game_cut_in_two(self):
        fight, = _run(ABILITIES + sorted(FIGHT + CASTS + [
            "30500,BEGIN_COMBAT", _cast_line(32000, 2, FORCE_PULSE, 600, _boss(470000)),
            f"33000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,800,46356,{_player(1)},{_boss(300000)}",
            "36000,END_COMBAT"], key=lambda line: int(line.split(",")[0]))).fight_history.fights
        self.assertEqual([c.t for c in fight.casts.of("2")], [4000, 22000])
        # The cast after the first END_COMBAT is in the fight now
        self.assertEqual([c.t for c in fight.casts.of("1")][-1], 21000)
        for p in fight.players:
            self.assertEqual(fight.casts.count(p["unit_id"]), p["casts"]["total"])

    def test_a_proc_is_left_out_as_the_counts_leave_it(self):
        """A track written again after its END_CAST with the same ability,
        not on the bars, is a proc (casts.py): neither the row's count nor
        the casts kept have it."""
        proc = "117119"
        lines = [_cast_line(12000, 2, proc, 700, _boss(740000)), _end(12000, 700, proc),
                 _cast_line(13000, 2, proc, 700, _boss(740000)), _end(13000, 700, proc)]
        fight, = _run(ABILITIES + sorted(FIGHT + CASTS + lines,
                                         key=lambda line: int(line.split(",")[0]))
                      ).fight_history.fights
        row = next(p for p in fight.players if p["unit_id"] == "2")
        self.assertEqual(fight.casts.count("2"), row["casts"]["total"])
        self.assertNotIn(proc, [cast.ability_id for cast in fight.casts.of("2")])


class TestFoughtOn(unittest.TestCase):
    """The group fighting on after END_COMBAT rebuilds the entry, which
    takes the casts with the events (waiting_hits.FOUGHT_ON_SLOTS): an
    END_CAST read after END_COMBAT gives the cast its length then."""

    def test_the_rebuild_carries_the_casts(self):
        from tests.unit.test_fighting_on import regen
        from tests.unit.test_hits_before_line import (
            STRIKE,
            TRASH_FIGHT,
            Engine,
            hit,
            trash,
        )
        from tests.unit.test_hits_before_line import (
            _player as player,
        )
        from waiting_hits import FOUGHT_ON_SLOTS
        self.assertIn("casts", FOUGHT_ON_SLOTS)
        channel = [f"19500,BEGIN_CAST,0,F,900,{STRIKE},{player(2)},{trash(900000)}",
                   f"21500,END_CAST,COMPLETED,900,{STRIKE}"]
        lines = sorted([*TRASH_FIGHT, *channel], key=lambda line: int(line.split(",")[0]))
        plain = Engine().feed(lines).fights[0]
        cast, = plain.casts.of("2")
        self.assertEqual((cast.t, cast.length), (9500, 0))
        fought_on = Engine().feed([*lines[:-1], hit(21000, 2, 40000, trash(860000)), lines[-1],
                                   regen(30000)])
        entry = fought_on.fights[0]
        cast, = entry.casts.of("2")
        self.assertEqual((cast.t, cast.length), (9500, 2000))
        row = next(p for p in entry.players if p["unit_id"] == "2")
        self.assertEqual(entry.casts.count("2"), row["casts"]["total"])

    def test_the_rebuild_keeps_the_first_builds_casts(self):
        """The rows keep the counts of the fight's first build, and so do
        the casts: a cast found to be a proc only after END_COMBAT (its
        track written again then) stays in the rebuilt entry."""
        from tests.unit.test_fighting_on import regen
        from tests.unit.test_hits_before_line import TRASH_FIGHT, Engine, hit, trash
        from tests.unit.test_hits_before_line import _player as player
        proc = 117119
        lines = sorted([*TRASH_FIGHT,
                        f"15500,BEGIN_CAST,0,F,700,{proc},{player(2)},{trash(900000)}",
                        f"15500,END_CAST,COMPLETED,700,{proc}"],
                       key=lambda line: int(line.split(",")[0]))
        engine = Engine().feed([*lines,
                                f"20500,BEGIN_CAST,0,F,700,{proc},{player(2)},{trash(900000)}",
                                f"20500,END_CAST,COMPLETED,700,{proc}",
                                hit(21000, 2, 40000, trash(860000)), regen(30000)])
        entry = engine.fights[0]
        row = next(p for p in entry.players if p["unit_id"] == "2")
        self.assertEqual(row["casts"]["total"], 1)
        self.assertEqual(entry.casts.count("2"), 1)
        self.assertEqual([cast.ability_id for cast in entry.casts.of("2")], [str(proc)])


if __name__ == "__main__":
    unittest.main()
