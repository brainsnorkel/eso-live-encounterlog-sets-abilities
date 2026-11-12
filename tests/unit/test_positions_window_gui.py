#!/usr/bin/env python3
"""The positions window (issue #214), offscreen: one fight paused at a
moment on a plain canvas, the table beside it, the boss bars, the scrub
bar and the controls.

Every fight here is the engine's own: a session written as CRLF bytes to
a temporary split, run through review_load.replay_log with a fresh
ESOLogAnalyzer and FightHistory, then read back with fight_reread, as the
main window's runner reads it. The session holds a tank, a healer and a
damage dealer with fight-table rows (ranked by boss damage, so their
numbers are not their unit ids), a grouped player with no handle who left
during the lead-in, an ungrouped player, a boss, three adds (one only in
the lead-in, one at health 0), a friendly NPC, a pet, a unit the log never
announced, a tank who stands far off the map for a while, a map change in
the fight and two deaths. Times are the log's own clock (ms since
BEGIN_LOG); the expected marks follow from the lines written, as the
comments beside them say."""

import copy
import os
import tempfile
import unittest
import weakref
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.unit.test_fight_reread import EPOCH, Log, replay
from tests.unit.test_gui import HAVE_QT, _ensure_app

_app = None
START, END = 20_000, 32_000
MAP_AT = 25_000         # the map changes: frame 1 from here
DEATH = 26_000          # the damage dealer dies, in frame 1
TANK_DEATH = 31_000     # the tank dies, in frame 1
FAR_AT = 22_000         # the tank stands far off the map until MAP_AT + 100
TANK, HEALER, DPS, LEAVER, STRANGER = "1", "2", "3", "4", "5"
BOSS, ADD, EARLY_ADD, DOOMED_ADD, NPC, PET, UNKNOWN = "70", "80", "81", "82", "85", "90", "99"
# The fight table's numbers: ranked by damage to the boss (the damage
# dealer hit it twice, the tank once, the healer never)
NUMBERS = {DPS: 1, TANK: 2, HEALER: 3}


def state(unit, hp="20000/20000", mag="10000/10000", stam="15000/20000", x="0.5000",
          y="0.5000", heading="0.0000", shield=0, ult="100/500"):
    """A unit's ten state fields as the log writes them."""
    return f"{unit},{hp},{mag},{stam},{ult},0/1000,{shield},{x},{y},{heading}"


def tank(x, y, hp="50000/50000", shield=0, heading="0.0000"):
    return state(TANK, hp=hp, x=x, y=y, shield=shield, heading=heading)


def healer(x, y):
    return state(HEALER, hp="20000/20000", mag="40000/40000", x=x, y=y)


def dps(x, y, hp="18000/18000"):
    return state(DPS, hp=hp, x=x, y=y, heading="1.5708")


def boss(x, y, hp=990_000):
    return state(BOSS, hp=f"{hp}/1000000", mag="0/0", stam="0/0", ult="0/0", x=x, y=y,
                 heading="3.1416")


def foe(unit, hp, x, y):
    return state(unit, hp=hp, mag="0/0", stam="0/0", ult="0/0", x=x, y=y, heading="1.0000")


def effect(t, source, target="*"):
    return f"{t},EFFECT_CHANGED,GAINED,1,{t},61744,{source},{target}"


def hit(t, source, target, result="DAMAGE", amount=5000):
    return f"{t},COMBAT_EVENT,{result},FIRE,1,{amount},0,{t},39012,{source},{target}"


def died(t, killer, target):
    return f"{t},COMBAT_EVENT,DIED,GENERIC,0,0,0,{t},39012,{killer},{target}"


def cast(t, source):
    return f"{t},BEGIN_CAST,0,F,{t},12345,{source},*"


def heal(t, source, target):
    return f"{t},COMBAT_EVENT,HEAL,GENERIC,1,3000,0,{t},12345,{source},{target}"


def player(t, unit, name, handle, character, local="F", grouped="T"):
    return (f'{t},UNIT_ADDED,{unit},PLAYER,{local},{unit},0,F,117,7,"{name}",'
            f'"{handle}",{character},50,3000,0,PLAYER_ALLY,{grouped}')


def monster(t, unit, name, is_boss="F", monster_id="5555", owner=0, reaction="HOSTILE"):
    return (f'{t},UNIT_ADDED,{unit},MONSTER,F,0,{monster_id},{is_boss},0,0,"{name}","",0,50,160,'
            f'{owner},{reaction},F')


def session(epoch=EPOCH):
    """The session (see the module)."""
    dead_dps = dps("0.2200", "0.2400", hp="0/18000")
    dead_tank = tank("0.2200", "0.2100", hp="0/50000")
    return [
        f'5,BEGIN_LOG,{epoch},15,"NA Megaserver","en","eso.live.12.1"',
        '1000,ZONE_CHANGED,1196,"Test Arena",VETERAN',
        '1029,MAP_CHANGED,1805,"Arena","test/arena001"',
        player(1100, TANK, "Tank Char", "@tester", 1001, local="T"),
        player(1100, HEALER, "Heal Char", "@healer", 1002),
        player(1100, DPS, "Dps Char", "@dps", 1003),
        player(1100, LEAVER, "Lead Leaver", "", 1004),          # no handle
        player(1100, STRANGER, "Stranger Char", "@stranger", 1005, grouped="F"),
        '1150,ABILITY_INFO,12345,"Test Skill","/esoui/art/icons/ability_weapon_001.dds",F,F',
        '1150,ABILITY_INFO,39012,"Grievous Pulse","/esoui/art/icons/ability_weapon_002.dds",F,F',
        monster(1200, BOSS, "Test Boss", is_boss="T", monster_id="105634"),
        monster(1200, ADD, "Test Add"),
        monster(1200, EARLY_ADD, "Early Add"),
        monster(1200, DOOMED_ADD, "Doomed Add"),
        monster(1200, NPC, "Friendly Npc", reaction="NPC_ALLY"),
        monster(1200, PET, "Test Pet", owner=DPS, reaction="PLAYER_ALLY"),
        effect(11_000, state(LEAVER, x="0.3000", y="0.3000")),
        f"12000,UNIT_REMOVED,{LEAVER}",                          # left in the lead-in
        effect(12_000, foe(EARLY_ADD, "3000/3000", "0.5200", "0.4200")),
        effect(15_000, tank("0.4000", "0.5000")),
        effect(19_000, dps("0.6000", "0.5000")),
        f"{START},BEGIN_COMBAT",
        # The game writes each member's build just after BEGIN_COMBAT
        *[f"{START + 1},PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]"
          for unit in (TANK, HEALER, DPS)],
        # A cast each: the engine reads a player's maximum pools, and so
        # their role, from their casts
        cast(START + 50, tank("0.4000", "0.5000")),
        cast(START + 60, healer("0.4500", "0.5500")),                # the healer's only state
        cast(START + 70, dps("0.6000", "0.5000")),
        hit(START + 100, tank("0.4000", "0.5000"), boss("0.5000", "0.4000", 990_000)),
        hit(START + 200, dps("0.6000", "0.5000"), boss("0.5000", "0.4000", 980_000)),
        hit(START + 300, dps("0.6000", "0.5000"), boss("0.5000", "0.4000", 970_000)),
        heal(START + 500, healer("0.4500", "0.5500"), tank("0.4000", "0.5000")),
        effect(START + 1000, foe(ADD, "5000/10000", "0.5500", "0.4500")),
        effect(START + 1500, state(PET, hp="900/1000", x="0.6200", y="0.5200")),
        effect(START + 1600, state(NPC, hp="900/1000", x="0.7000", y="0.7000")),
        effect(FAR_AT, tank("-270.1234", "15.5000")),             # far off the map
        effect(FAR_AT, foe(DOOMED_ADD, "0/8000", "0.5800", "0.4800")),
        effect(START + 2000, state(UNKNOWN, hp="10/10", x="0.5000", y="0.6000")),
        effect(START + 2500, state(STRANGER, x="0.3500", y="0.6500")),
        hit(START + 4000, boss("0.5000", "0.4000", 960_000), dps("0.6000", "0.5000", hp="9000/18000")),
        f'{MAP_AT},MAP_CHANGED,1806,"Floor","test/floor001"',
        effect(MAP_AT + 100, tank("0.2000", "0.2000", shield=5000)),
        effect(MAP_AT + 200, boss("0.2500", "0.2500", 950_000)),
        effect(MAP_AT + 500, state(STRANGER, x="0.3000", y="0.3000")),
        hit(DEATH, boss("0.2500", "0.2500", 950_000), dead_dps, amount=9000),
        died(DEATH, boss("0.2500", "0.2500", 950_000), dead_dps),
        effect(DEATH + 1000, tank("0.2200", "0.2100", shield=5000)),
        effect(DEATH + 2000, boss("0.2600", "0.2500", 900_000)),
        hit(TANK_DEATH, boss("0.2600", "0.2500", 900_000), dead_tank, amount=50000),
        died(TANK_DEATH, boss("0.2600", "0.2500", 900_000), dead_tank),
        f"{END},END_COMBAT",
    ]


def merged(lines, extra):
    """*lines* with the *extra* lines put in at their times, each after the
    lines of its own time."""
    return sorted(list(lines) + list(extra), key=lambda line: int(line.split(",", 1)[0]))


# A boss the game removes and adds again as a new unit, as Z'Maja between
# her phases, and two more bosses: four boss rows at TWIN_BACK_AT + 3000
TWIN, TWIN_BACK, KEEPER, WARDEN = "71", "72", "73", "74"
TWIN_GONE_AT, TWIN_BACK_AT = START + 3000, START + 5000


def boss_twins():
    """The session (see the module) with Twin, removed at TWIN_GONE_AT and
    added again as another unit at TWIN_BACK_AT, and Gate Keeper and
    Warden, whose first states are at START + 3500 and START + 5700."""
    return merged(session(), [
        monster(1200, TWIN, "Twin", is_boss="T", monster_id="105640"),
        monster(1200, KEEPER, "Gate Keeper", is_boss="T", monster_id="105641"),
        monster(1200, WARDEN, "Warden", is_boss="T", monster_id="105642"),
        effect(START + 500, foe(TWIN, "900000/1000000", "0.5200", "0.4000")),
        effect(START + 2500, foe(TWIN, "600000/1000000", "0.5200", "0.4000")),
        f"{TWIN_GONE_AT},UNIT_REMOVED,{TWIN}",
        monster(TWIN_BACK_AT, TWIN_BACK, "Twin", is_boss="T", monster_id="105640"),
        effect(START + 3500, foe(KEEPER, "500000/1000000", "0.5300", "0.4100")),
        effect(TWIN_BACK_AT + 500, foe(TWIN_BACK, "800000/1000000", "0.2400", "0.2400")),
        effect(START + 5600, foe(KEEPER, "500000/1000000", "0.2300", "0.2300")),
        effect(START + 5700, foe(WARDEN, "400000/1000000", "0.2350", "0.2350")),
    ])


def corpse_ticks():
    """The session (see the module) where the log writes the dead above 0
    health: in the damage dealer's death's own millisecond, after the DIED
    line, a regeneration tick on the corpse (631 health, magicka and
    stamina 0), repeated a second later, and a revive at DEATH + 3000; the
    tank killed by a mechanic whose hit and DIED line carry the health
    before the kill, 0 written 30 ms later, then a corpse's tick."""
    def regen(t, unit, hp):
        return f"{t},HEALTH_REGEN,631,{state(unit, hp=hp, mag='0/10000', stam='0/20000')}"
    lines = [line for line in session()
             if not line.startswith((f"{TANK_DEATH},COMBAT_EVENT",))]
    killed = tank("0.2200", "0.2100", hp="40000/50000")
    return merged(lines, [
        regen(DEATH, DPS, "631/18000"),
        regen(DEATH + 1000, DPS, "631/18000"),
        effect(DEATH + 3000, dps("0.2200", "0.2400", hp="9000/18000")),
        hit(TANK_DEATH, boss("0.2600", "0.2500", 900_000), killed, amount=50000),
        died(TANK_DEATH, boss("0.2600", "0.2500", 900_000), killed),
        effect(TANK_DEATH + 30, tank("0.2200", "0.2100", hp="0/50000")),
        regen(TANK_DEATH + 500, TANK, "631/50000"),
    ])


def split_and_states(root, lines, name="split.log"):
    """(log, path, fights, states of the first fight) of *lines* written
    to a split under *root*."""
    import fight_reread as fr
    log = Log().add(lines)
    path = log.save(Path(root) / name)
    fights = replay(path)
    states = fr.read_fight(fights[0].locator, [fr.Place(path, "split", None, 0)])
    return log, path, fights, states


def _palette(window_hex):
    from PySide6.QtGui import QColor, QPalette
    palette = QPalette()
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        palette.setColor(group, QPalette.Window, QColor(window_hex))
    return palette


def _icon_image(icon, mode=None):
    """A table picture (a QIcon) in *mode*, Normal by default, as an
    image."""
    from PySide6.QtGui import QIcon
    return icon.pixmap(icon.availableSizes()[0], mode or QIcon.Normal).toImage()


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class PositionsTestCase(unittest.TestCase):
    """The fight is read once for the class; a test that changes the entry
    works on a copy (copy.copy, its slots replaced, never written into)."""

    @classmethod
    def setUpClass(cls):
        global _app
        _app = _ensure_app()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.log, cls.path, cls.fights, cls.states = split_and_states(cls.root, session())
        cls.entry = cls.fights[0]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        global _app
        _app = _ensure_app()

    def tearDown(self):
        from gui import text_size
        text_size.apply(text_size.DEFAULT_PCT)  # the application font is shared

    def _window(self, entry=None, t=DEATH, unit=DPS, hide=False, load=True, size=(1120, 700)):
        from fight_reread import RereadEvent
        from gui.name_mask import NameMask
        from gui.positions_window import PositionsWindow
        entry = entry or self.entry
        window = PositionsWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        window.resize(*size)
        window.open(entry, t, unit, dark=False, names=NameMask.for_entry(entry, hide))
        if load:
            window.reread_done(RereadEvent("loaded", entry.locator, self.states))
        _app.processEvents()
        return window

    def _unit(self, window, key):
        return next(u for u in window.scene().units if u.key == key)

    def _units_by_mark(self, window, mark):
        return [u for u in window.scene().units if u.mark == mark]

    def _active(self, window):
        from PySide6.QtTest import QTest
        window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(window, 2000))

    def _press(self, target, keys):
        from PySide6.QtGui import QKeySequence
        from PySide6.QtTest import QTest
        combo = QKeySequence(keys)[0]
        QTest.keyClick(target, combo.key(), combo.keyboardModifiers())
        _app.processEvents()


# ------------------------------------------------------------- the moment --

class TestTheMoment(PositionsTestCase):

    def test_the_engine_made_the_fight_the_tests_expect(self):
        """The ground the other tests stand on: rows in boss-damage order
        with their roles, two deaths, the leaver in the unit table only."""
        entry = self.entry
        self.assertEqual([(p["unit_id"], p["role"]) for p in entry.players],
                         [(DPS, "D"), (TANK, "T"), (HEALER, "H")])
        self.assertEqual([(r["unit_id"], r["time_ms"]) for r in entry.death_recaps],
                         [(DPS, DEATH - START), (TANK, TANK_DEATH - START)])
        self.assertIn(LEAVER, {u.key for u in entry.locator.units})
        self.assertNotIn("Lead Leaver", {p["name"] for p in entry.player_names})
        self.assertEqual(len(self.states.frames), 2)

    def test_numbers_and_roles_follow_the_fight_tables_rows(self):
        from gui.positions_canvas import MARK_BOSS, MARK_LOOSE, MARK_PLAYER
        from gui.positions_window import NUMBER_COL, ROLE_COL, cell_text
        window = self._window()
        units = window.model.units()
        self.assertEqual([(u.key, u.number, u.role) for u in units if u.mark == MARK_PLAYER],
                         [(DPS, 1, "D"), (TANK, 2, "T"), (HEALER, 3, "H")])
        # Players with no row, then the boss, after the numbered ones
        self.assertEqual([u.mark for u in units],
                         [MARK_PLAYER] * 3 + [MARK_LOOSE, MARK_LOOSE, MARK_BOSS])
        self.assertEqual([cell_text(u, ROLE_COL) for u in units],
                         ["DPS", "Tank", "Healer", "", "", "Boss"])
        self.assertEqual([cell_text(u, NUMBER_COL) for u in units], ["1", "2", "3", "", "", ""])

    def test_the_marks_at_the_first_death(self):
        """At the damage dealer's death, in frame 1: dead and drawn; the
        tank alive; the healer's only state is in frame 0 and 5.94 s old,
        so not on this map and lost; the leaver left; the stranger, with
        no row, drawn."""
        from gui.positions_canvas import ALIVE, DEAD, DRAWN, LEFT, LOST, OTHER_MAP
        window = self._window()
        scene = window.scene()
        self.assertEqual((scene.t, scene.frame, scene.frame_name), (DEATH, 1, "Floor"))
        marks = {u.key: (u.where, u.look) for u in scene.units}
        self.assertEqual(marks[DPS], (DRAWN, DEAD))
        self.assertEqual(marks[TANK], (DRAWN, ALIVE))
        self.assertEqual(marks[HEALER], (OTHER_MAP, LOST))
        self.assertEqual(marks[LEAVER][0], LEFT)
        self.assertEqual(marks[STRANGER], (DRAWN, ALIVE))
        drawn = {item.unit.key for item in window.canvas.placed()}
        self.assertIn(DPS, drawn)
        self.assertNotIn(HEALER, drawn)
        self.assertNotIn(LEAVER, drawn)
        from gui.positions_window import STATE_COL, cell_text
        states = {u.key: cell_text(u, STATE_COL) for u in window.model.units()}
        self.assertEqual(states[DPS], "dead")
        self.assertEqual(states[TANK], "alive")
        self.assertEqual(states[HEALER], "not on this map")
        self.assertEqual(states[LEAVER], "left")
        self.assertEqual(window.elsewhere_label.text(), "Map: Floor (2 of 2) · Not on this map: 3")

    def test_stale_and_lost_by_the_age_of_the_last_state(self):
        """The tank's last state is at DEATH + 1000: 1.5 s later it is
        stale (dashed); the stranger's at MAP_AT + 500: 7 s later lost
        (dotted, its number muted)."""
        from gui.positions_canvas import LOST, STALE
        from gui.positions_window import STATE_COL, cell_text
        window = self._window(t=DEATH + 2500)
        self.assertEqual(self._unit(window, TANK).look, STALE)
        self.assertEqual(cell_text(self._unit(window, TANK), STATE_COL), "last seen 1 s ago")
        window._go_to(MAP_AT + 500 + 5001)
        self.assertEqual(self._unit(window, STRANGER).look, LOST)
        self.assertIn(STRANGER, {item.unit.key for item in window.canvas.placed()})

    def test_a_seen_column_ages_from_the_last_line(self):
        """When the reader keeps when a state was last written (a 'seen'
        column), the age runs from that line and the words say 'last
        seen'."""
        from typing import NamedTuple

        from gui.positions_canvas import UnitAt, age_words, state_age

        class Seen(NamedTuple):
            t: int
            seen: int
        self.assertEqual(state_age(Seen(1000, 4000), 6000), 2000)
        self.assertEqual(state_age(Seen(1000, 9000), 6000), 0)  # written again after the moment
        unit = UnitAt("1", "1", "player", 1, "D", "@a", Seen(1000, 4000), 2000, "drawn", "stale")
        self.assertEqual(age_words(unit), "last seen 2 s ago")

    def test_not_in_the_log_yet(self):
        """In the lead-in, before any numbered player's first state, with
        the boss not yet written either."""
        from gui.positions_canvas import DRAWN, NOT_YET
        window = self._window(t=11_500, unit=None)
        scene = window.scene()
        for key in (DPS, TANK, HEALER):
            self.assertEqual(self._unit(window, key).where, NOT_YET, key)
        self.assertEqual(self._unit(window, LEAVER).where, DRAWN)  # 0.5 s old, not yet left
        self.assertEqual(window.elsewhere_label.text(),
                         "Map: Arena (1 of 2) · Not in the log yet: 1, 2, 3, Test Boss")
        self.assertEqual(window.boss_bars.rows(), [("Test Boss", 0, 0, False)])
        self.assertIn("Test Boss not in the log yet", window.canvas.accessibleDescription())
        self.assertEqual(scene.frame, 0)

    def test_far_off_the_map(self):
        """The tank's place at FAR_AT is far off its map (another zone or
        instance): not drawn, named under the canvas."""
        from gui.positions_canvas import OFF_MAP
        window = self._window(t=FAR_AT + 500, unit=None)
        self.assertEqual(self._unit(window, TANK).where, OFF_MAP)
        self.assertNotIn(TANK, {item.unit.key for item in window.canvas.placed()})
        self.assertIn("Not on this map: 2", window.elsewhere_label.text())

    def test_the_frame_follows_the_selection(self):
        """Most drawn players are in frame 1 at the death; with the healer
        selected, whose last state is in frame 0, the canvas shows frame 0,
        where the others are not."""
        from gui.positions_canvas import DRAWN, OTHER_MAP
        window = self._window(unit=HEALER)
        scene = window.scene()
        self.assertEqual((scene.frame, scene.frame_name), (0, "Arena"))
        self.assertEqual(self._unit(window, HEALER).where, DRAWN)
        self.assertEqual(self._unit(window, DPS).where, OTHER_MAP)
        self.assertEqual(window.elsewhere_label.text(),
                         "Map: Arena (1 of 2) · Not on this map: 1, 2, Test Boss")

    def test_one_box_per_frame_and_one_scale(self):
        """Each frame's box is fitted to the 2nd to 98th percentile of the
        players' and bosses' places in it: the outliers fall outside;
        padded by 12% of the longer side; the canvas keeps one scale."""
        from gui.positions_canvas import FIT_PAD, MIN_SIDE, box_of, fit_boxes
        xs = [0.0] + [0.4] * 49 + [0.6] * 49 + [1.0]
        x0, x1, y0, y1 = box_of(xs, [0.5] * 100)
        pad = FIT_PAD * 0.2
        self.assertAlmostEqual(x0, 0.4 - pad)
        self.assertAlmostEqual(x1, 0.6 + pad)
        self.assertAlmostEqual(y1 - y0, MIN_SIDE + 2 * pad)
        self.assertGreater(x0, 0.0)
        self.assertLess(x1, 1.0)
        boxes = fit_boxes(self.states)
        self.assertEqual(set(boxes), {0, 1})
        # Frame 0's box is of frame 0's places: the tank's (0.2, 0.2) in
        # frame 1, and its far place, are outside it
        bx0, bx1, by0, by1 = boxes[0]
        self.assertFalse(bx0 <= 0.2 <= bx1 and by0 <= 0.2 <= by1)
        self.assertTrue(bx0 <= 0.45 <= bx1 and by0 <= 0.55 <= by1)
        window = self._window()
        scale, ox, oy = window.canvas.transform()
        # A square in the map is a square on the canvas
        a = (ox + 0.2 * scale, oy + 0.2 * scale)
        b = (ox + 0.25 * scale, oy + 0.25 * scale)
        self.assertAlmostEqual(b[0] - a[0], b[1] - a[1])

    def test_a_unit_outside_the_box_is_pinned_to_the_edge(self):
        """The stranger's place in frame 1, (0.3, 0.3), is beyond the 98th
        percentile of the frame's places: drawn at the canvas's edge."""
        window = self._window()
        item = next(item for item in window.canvas.placed() if item.unit.key == STRANGER)
        self.assertTrue(item.pinned)
        inside = window.canvas.rect()
        self.assertTrue(inside.contains(item.point.toPoint()))
        others = [i for i in window.canvas.placed() if i.unit.key in (TANK, DPS)]
        self.assertFalse(any(i.pinned for i in others))

    def test_adds_are_forgotten_after_15_s_and_crossed_for_2_s_at_health_0(self):
        from gui.positions_canvas import DEAD, DRAWN, GONE, OTHER_MAP
        window = self._window(t=FAR_AT + 1500, unit=None)
        self.assertEqual(self._unit(window, f"{DOOMED_ADD}@1200").where, DRAWN)
        self.assertEqual(self._unit(window, f"{DOOMED_ADD}@1200").look, DEAD)
        window._go_to(FAR_AT + 2500)
        self.assertEqual(self._unit(window, f"{DOOMED_ADD}@1200").where, GONE)
        # The early add's only state is at 12 s
        window._go_to(12_000 + 14_000)
        self.assertEqual(self._unit(window, f"{EARLY_ADD}@1200").where, OTHER_MAP)
        window._go_to(12_000 + 15_001)
        self.assertEqual(self._unit(window, f"{EARLY_ADD}@1200").where, GONE)

    def test_the_show_menu(self):
        """Adds drawn by default; pets, companions, unannounced and other
        units each one toggle away."""
        from gui.positions_canvas import (
            DRAWN,
            HIDDEN,
            MARK_ADD,
            MARK_OTHER,
            MARK_PET,
            MARK_UNKNOWN,
        )
        window = self._window(t=START + 2100, unit=None)
        where = {u.mark: u.where for u in window.scene().units
                 if u.mark in (MARK_ADD, MARK_PET, MARK_UNKNOWN, MARK_OTHER) and u.key != "81@1200"
                 and u.key != "82@1200"}
        self.assertEqual(where, {MARK_ADD: DRAWN, MARK_PET: HIDDEN, MARK_UNKNOWN: HIDDEN,
                                 MARK_OTHER: HIDDEN})
        self.assertEqual([a.text() for a in window.show_menu.actions()],
                         ["Adds", "Pets", "Companions", "Unannounced units", "Other units"])
        for mark in (MARK_PET, MARK_UNKNOWN, MARK_OTHER):
            window.set_shown(mark, True)
        window.set_shown(MARK_ADD, False)
        where = {u.key: u.where for u in window.scene().units}
        self.assertEqual((where[f"{PET}@1200"], where["?" + UNKNOWN], where[f"{NPC}@1200"],
                          where[f"{ADD}@1200"]), (DRAWN, DRAWN, DRAWN, HIDDEN))
        drawn = {item.unit.key for item in window.canvas.placed()}
        self.assertTrue({f"{PET}@1200", "?" + UNKNOWN, f"{NPC}@1200"} <= drawn)

    def test_the_notes_name_the_deaths_near_the_moment(self):
        """Deaths from 4 s before the moment to 3 s after it, by number,
        with their offsets."""
        from gui.positions_canvas import note_text, offset_text

        def notes(window):
            return [(offset_text(n.offset_ms), note_text(n)) for n in window.scene().notes]
        window = self._window(t=DEATH - 400, unit=None)
        self.assertEqual(notes(window), [("+0.4 s", "1 died: Grievous Pulse (Test Boss)")])
        window._go_to(DEATH + 4000)
        self.assertEqual(notes(window), [("-4.0 s", "1 died: Grievous Pulse (Test Boss)"),
                                         ("+1.0 s", "2 died: Grievous Pulse (Test Boss)")])
        window._go_to(DEATH + 4001)
        self.assertEqual(notes(window), [("+1.0 s", "2 died: Grievous Pulse (Test Boss)")])
        window._go_to(TANK_DEATH - 3001)
        self.assertEqual(notes(window), [("-2.0 s", "1 died: Grievous Pulse (Test Boss)")])

    def test_the_boss_bars(self):
        window = self._window()
        self.assertEqual(window.boss_bars.rows(), [("Test Boss", 950_000, 1_000_000, True)])
        self.assertEqual(window.boss_bars.accessibleDescription(),
                         "Test Boss 95% (950,000 of 1,000,000)")

    def test_the_description_names_who_is_not_in_the_log_yet(self):
        """The review's finding 04: in the lead-in, players the log has not
        written yet were counted as not alive ('3 players, 0 alive'), which
        reads as dead; they are counted apart."""
        from gui.positions_window import moment_summary
        window = self._window(t=11_500, unit=None)
        self.assertTrue(window.canvas.accessibleDescription().endswith(
            "3 players, 0 alive, 3 not in the log yet."))
        window._go_to(16_000)  # the tank's first state is at 15 s
        self.assertTrue(moment_summary(window.scene(), START, END).endswith(
            "3 players, 1 alive, 2 not in the log yet."))
        window._go_to(DEATH)
        self.assertTrue(window.canvas.accessibleDescription().endswith("3 players, 2 alive."))

    def test_a_selected_bosss_name_is_drawn_once(self):
        """The review's finding 05: every drawn boss's name is beside it
        (_paint_boss_names), so a selected boss gets no second label; a
        selected player still does."""
        window = self._window(t=START + 3000, unit=f"{BOSS}@1200")
        canvas = window.canvas
        self.assertEqual(canvas.scene().selected, f"{BOSS}@1200")
        labels, names = [], []
        real_label, real_names = canvas._paint_label, canvas._paint_boss_names

        def label(painter, colours, item, *args):
            labels.append(item.unit.key)
            return real_label(painter, colours, item, *args)

        def boss_names(painter, colours, singles, *args):
            names.extend(item.unit.key for item in singles if item.unit.mark == "boss")
            return real_names(painter, colours, singles, *args)
        canvas._paint_label, canvas._paint_boss_names = label, boss_names
        try:
            canvas.grab()
            self.assertEqual((labels, names), ([], [f"{BOSS}@1200"]))
            window._on_canvas_clicked(DPS)
            canvas.grab()
            self.assertEqual(labels, [DPS])
        finally:
            del canvas._paint_label, canvas._paint_boss_names

    def test_the_header_and_the_clock(self):
        window = self._window()
        self.assertIn("Test Boss · Test Arena VET", window.fight_label.text())
        self.assertIn("0:06.0 of 12s", window.fight_label.text())
        self.assertEqual(window.clock.text(), "0:06.0")
        self.assertEqual(window.windowTitle(), "Positions – Test Boss")
        window._go_to(START - 3000)
        self.assertEqual(window.clock.text(), "-0:03.0")


# ----------------------------------------------------------------- piles --

class TestPiles(PositionsTestCase):
    """Numbered players whose markers overlap by over a quarter make one
    badge listing them; the selected player is never piled; a click on a
    member in the badge selects that member. A scene made by hand puts
    the players where the test needs them."""

    def _canvas(self, places, selected="4"):
        from fight_reread import State
        from gui.positions_canvas import (
            ALIVE,
            DRAWN,
            MARK_PLAYER,
            PositionsCanvas,
            Scene,
            UnitAt,
        )
        units = tuple(UnitAt(str(n), str(n), MARK_PLAYER, n, "D", f"@p{n}",
                             State(0, x, y, 0.0, 100, 100, 0, 0, 0, 0, 0, 0, 0, 0), 0, DRAWN,
                             ALIVE)
                      for n, (x, y) in enumerate(places, start=1))
        canvas = PositionsCanvas()
        self.addCleanup(canvas.deleteLater)
        canvas.resize(400, 400)
        canvas.set_scene(Scene(0, 0, "Map", (0.0, 1.0, 0.0, 1.0), units, (), selected))
        return canvas

    def test_close_players_make_one_badge_and_the_selected_stays_out(self):
        # 1, 2 and 3 within a few pixels; 4 near them but selected; 5 far
        canvas = self._canvas([(0.5, 0.5), (0.505, 0.5), (0.51, 0.505), (0.52, 0.5), (0.9, 0.2)])
        singles, piles = canvas.layout()
        self.assertEqual(len(piles), 1)
        self.assertEqual([m.unit.number for m in piles[0].members], [1, 2, 3])
        self.assertEqual({s.unit.key for s in singles}, {"4", "5"})
        self.assertTrue(canvas.rect().contains(piles[0].rect.toRect()))
        # Where there is room the badge keeps off the selected player
        selected = next(s for s in singles if s.unit.key == "4")
        self.assertFalse(piles[0].rect.intersects(canvas._extent(selected, canvas.radius())))

    def test_players_a_marker_apart_are_not_piled(self):
        r = 8  # scaled_px(RADIUS_PX) at 100%
        canvas = self._canvas([(0.5, 0.5), (0.5 + 2 * r / 360, 0.5)], selected=None)
        self.assertEqual(canvas.piles(), [])

    def test_a_click_on_a_member_of_a_badge_selects_it(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        canvas = self._canvas([(0.5, 0.5), (0.505, 0.5), (0.51, 0.505)], selected=None)
        pile = canvas.piles()[0]
        cell = pile.cells[1]
        self.assertEqual(canvas.point_of("2"), cell)
        clicked = []
        canvas.unit_clicked.connect(clicked.append)
        QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, cell.toPoint())
        self.assertEqual(clicked, ["2"])
        self.assertFalse(canvas.grab().isNull())


# ---------------------------------------------------------------- moving --

class TestMoving(PositionsTestCase):

    def test_the_buttons_step_a_second(self):
        window = self._window()
        window.back.click()
        self.assertEqual(window.moment(), DEATH - 1000)
        window.forward.click()
        window.forward.click()
        self.assertEqual(window.moment(), DEATH + 1000)
        self.assertEqual(window.selected(), DPS)  # the selection is kept

    def test_the_moment_stays_in_the_range(self):
        window = self._window()
        window._go_to(0)
        self.assertEqual(window.moment(), self.states.range_start_ms)
        self.assertFalse(window.back.isEnabled())
        window._go_to(10 ** 9)
        self.assertEqual(window.moment(), END + 1000)
        self.assertFalse(window.forward.isEnabled())

    def test_the_window_keys(self):
        """Ctrl+Left and Ctrl+Right a second, with Shift a tenth; Ctrl+PgUp
        and Ctrl+PgDn the deaths; Ctrl+Down the next unit."""
        window = self._window(t=START, unit=None)
        self._active(window)
        window.table.setFocus()
        self._press(window, "Ctrl+Right")
        self.assertEqual(window.moment(), START + 1000)
        self._press(window, "Ctrl+Shift+Left")
        self.assertEqual(window.moment(), START + 900)
        self._press(window, "Ctrl+PgDown")
        self.assertEqual((window.moment(), window.selected()), (DEATH, DPS))
        self._press(window, "Ctrl+PgDown")
        self.assertEqual((window.moment(), window.selected()), (TANK_DEATH, TANK))
        self._press(window, "Ctrl+PgUp")
        self.assertEqual((window.moment(), window.selected()), (DEATH, DPS))
        self._press(window, "Ctrl+Down")
        self.assertEqual(window.selected(), TANK)  # the row after the damage dealer's
        self._press(window, "Ctrl+Up")
        self.assertEqual(window.selected(), DPS)

    def test_the_death_buttons(self):
        window = self._window(t=START, unit=None)
        self.assertFalse(window.previous_death.isEnabled())
        window.next_death.click()
        self.assertEqual((window.moment(), window.selected()), (DEATH, DPS))
        window.next_death.click()
        self.assertEqual((window.moment(), window.selected()), (TANK_DEATH, TANK))
        self.assertFalse(window.next_death.isEnabled())
        window.previous_death.click()
        self.assertEqual((window.moment(), window.selected()), (DEATH, DPS))
        self.assertFalse(window.previous_death.isEnabled())

    def test_the_scrub_bars_keys(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        window = self._window(t=START, unit=None)
        self._active(window)
        bar = window.scrub
        bar.setFocus()
        QTest.keyClick(bar, Qt.Key_Right)
        self.assertEqual(window.moment(), START + 1000)
        QTest.keyClick(bar, Qt.Key_Left, Qt.ShiftModifier)
        self.assertEqual(window.moment(), START + 900)
        QTest.keyClick(bar, Qt.Key_PageDown)
        self.assertEqual(window.moment(), DEATH)
        QTest.keyClick(bar, Qt.Key_End)
        self.assertEqual(window.moment(), END + 1000)
        QTest.keyClick(bar, Qt.Key_Home)
        self.assertEqual(window.moment(), self.states.range_start_ms)
        QTest.keyClick(bar, Qt.Key_PageUp)  # no death before the range's start
        self.assertEqual(window.moment(), self.states.range_start_ms)

    def test_a_click_and_a_drag_on_the_scrub_bar(self):
        from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtTest import QTest
        window = self._window(t=START, unit=None)
        bar = window.scrub
        y = int(bar._band().center().y())
        x = round(bar.x_of(DEATH))
        QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier, QPoint(x, y))
        per_pixel = (END + 1000 - self.states.range_start_ms) / bar._band().width()
        self.assertLessEqual(abs(window.moment() - DEATH), per_pixel)
        self.assertTrue(bar.hasFocus() or not window.isActiveWindow())
        # A drag: press, move with the button held, release
        QTest.mousePress(bar, Qt.LeftButton, Qt.NoModifier, QPoint(x, y))
        to = QPointF(bar.x_of(TANK_DEATH), y)
        _app.sendEvent(bar, QMouseEvent(QEvent.MouseMove, to, bar.mapToGlobal(to), Qt.NoButton,
                                        Qt.LeftButton, Qt.NoModifier))
        QTest.mouseRelease(bar, Qt.LeftButton, Qt.NoModifier, to.toPoint())
        self.assertLessEqual(abs(window.moment() - TANK_DEATH), per_pixel)

    def test_a_value_set_on_the_scrub_bar_goes_to_that_moment(self):
        """The review's finding 18: a screen reader that sets the slider's
        value (UIA's RangeValue) moved the slider and not the moment, so it
        read 2 s while the window showed 6 s. The value set is a moment
        asked for; the window's own steps set it silently."""
        from PySide6.QtGui import QAccessible
        window = self._window()
        moments = []
        window.scrub.moment_requested.connect(moments.append)
        window.forward.click()
        self.assertEqual((window.moment(), window.scrub.value(), moments), (DEATH + 1000, 7, []))
        iface = QAccessible.queryAccessibleInterface(window.scrub)
        iface.valueInterface().setCurrentValue(2)
        self.assertEqual(moments, [START + 2000])
        self.assertEqual((window.moment(), window.scrub.value()), (START + 2000, 2))
        self.assertEqual(window.clock.text(), "0:02.0")
        self.assertEqual(iface.text(QAccessible.Description), "0:02.0 into the fight, of 12s")

    def test_the_scrub_bar_marks_the_deaths_the_map_change_and_the_ends(self):
        window = self._window()
        bar = window.scrub
        self.assertEqual(bar.span(), (self.states.range_start_ms, START, END, END + 1000))
        self.assertEqual(bar.deaths(), (DEATH, TANK_DEATH))
        # The first state of frame 1 is the tank's, just after the line
        self.assertEqual(bar.map_changes(), (MAP_AT + 100,))
        self.assertEqual(bar.moment(), DEATH)


# ------------------------------------------------------------- selecting --

class TestSelecting(PositionsTestCase):

    def test_a_click_on_a_marker_selects_its_row(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        window = self._window()
        point = window.canvas.point_of(TANK)
        self.assertIsNotNone(point)
        QTest.mouseClick(window.canvas, Qt.LeftButton, Qt.NoModifier, point.toPoint())
        self.assertEqual(window.selected(), TANK)
        row = window.table.currentIndex().row()
        self.assertEqual(window.model.unit_at(row).key, TANK)
        self.assertTrue(window.table.selectionModel().isRowSelected(row))
        self.assertEqual(window.canvas.scene().selected, TANK)

    def test_a_row_selects_its_marker(self):
        window = self._window()
        row = window.model.row_of(STRANGER)
        window.table.setCurrentIndex(window.model.index(row, 0))
        self.assertEqual(window.selected(), STRANGER)
        self.assertEqual(window.canvas.scene().selected, STRANGER)

    def test_a_click_on_an_add_selects_it_with_no_row(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        window = self._window(t=START + 1500, unit=None)
        point = window.canvas.point_of(f"{ADD}@1200")
        QTest.mouseClick(window.canvas, Qt.LeftButton, Qt.NoModifier, point.toPoint())
        self.assertEqual(window.selected(), f"{ADD}@1200")
        self.assertFalse(window.table.selectionModel().hasSelection())

    def test_coming_back_to_the_window_selects_nothing_by_itself(self):
        """The review's finding 00: a table given the focus with no
        current row makes its first row current, unselected, and the
        window took that as the reader's choice, so coming back to it from
        another window selected player 1 (the canvas framing their map),
        and replaced an add the reader had clicked. Rows still select."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QWidget
        window = self._window(t=START + 1500, unit=None)
        other = QWidget()
        self.addCleanup(other.deleteLater)
        self.addCleanup(other.close)
        other.resize(200, 100)

        def away_and_back():
            other.show()
            other.activateWindow()
            self.assertTrue(QTest.qWaitForWindowActive(other, 2000))
            self._active(window)
            _app.processEvents()
        self._active(window)
        self.assertIs(window.focusWidget(), window.table)
        self.assertIsNone(window.selected())
        away_and_back()
        self.assertIsNone(window.selected())
        self.assertIsNone(window.scene().selected)
        point = window.canvas.point_of(f"{ADD}@1200")
        QTest.mouseClick(window.canvas, Qt.LeftButton, Qt.NoModifier, point.toPoint())
        self.assertEqual(window.selected(), f"{ADD}@1200")
        away_and_back()
        self.assertEqual(window.selected(), f"{ADD}@1200")
        # A row clicked, and Ctrl+Down, still select
        rect = window.table.visualRect(window.model.index(window.model.row_of(TANK), 1))
        QTest.mouseClick(window.table.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
        self.assertEqual(window.selected(), TANK)
        self._press(window, "Ctrl+Down")
        self.assertEqual(window.selected(), HEALER)

    def test_enter_on_a_player_asks_for_the_player_window(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        window = self._window(unit=TANK)
        self._active(window)
        asked = []
        window.player_requested.connect(lambda entry, key: asked.append((entry, key)))
        window.table.setFocus()
        QTest.keyClick(window.table, Qt.Key_Return)
        self.assertEqual(asked, [(self.entry, TANK)])
        self.assertTrue(window.isVisible())  # Enter never closes it
        boss_row = window.model.row_of(f"{BOSS}@1200")
        window.table.setCurrentIndex(window.model.index(boss_row, 0))
        QTest.keyClick(window.table, Qt.Key_Return)
        self.assertEqual(len(asked), 1)  # a boss has no player window

    def test_show_in_list(self):
        window = self._window()
        asked = []
        window.show_in_list_requested.connect(asked.append)
        window.show_in_list.click()
        self.assertEqual(asked, [self.entry])
        window.set_listed(False)
        self.assertFalse(window.show_in_list.isEnabled())

    def test_the_tab_order_and_esc(self):
        """Tab goes from the scrub bar to the table to Play and the speed
        (#232), then the buttons (a button that is off is passed: at the
        first death there is no death before); Esc hides the window."""
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        window = self._window()
        self._active(window)
        self.assertFalse(window.previous_death.isEnabled())
        window.scrub.setFocus()
        seen = [window.focusWidget()]
        for _ in range(8):
            QTest.keyClick(window.focusWidget(), Qt.Key_Tab)
            seen.append(window.focusWidget())
        self.assertEqual(seen, [window.scrub, window.table, window.play_button, window.speed_box,
                                window.back, window.forward, window.next_death, window.show_button,
                                window.show_in_list])
        QTest.keyClick(window.table, Qt.Key_Escape)
        self.assertFalse(window.isVisible())

    def test_ctrl_c_copies_the_moment(self):
        from PySide6.QtGui import QGuiApplication
        window = self._window(hide=True)
        self._active(window)
        QGuiApplication.clipboard().setText("")
        self._press(window, "Ctrl+C")
        text = QGuiApplication.clipboard().text()
        self.assertTrue(text.startswith(window.fight_label.text()))
        self.assertIn("0:06.0 into the fight. Test Boss 95%.", text)
        self.assertIn("@tester", text)
        for name in ("@dps", "@healer", "Lead Leaver", "@stranger"):
            self.assertNotIn(name, text)

    def test_the_window_never_binds_the_main_windows_keys(self):
        from PySide6.QtGui import QKeySequence, QShortcut
        window = self._window()
        keys = {shortcut.key().toString() for shortcut in window.findChildren(QShortcut)}
        for taken in ("Ctrl+H", "Ctrl+=", "Ctrl++", "Ctrl+-", "Ctrl+0"):
            self.assertNotIn(QKeySequence(taken).toString(), keys)
        self.assertTrue({"Ctrl+Left", "Ctrl+Right", "Ctrl+PgUp", "Ctrl+PgDown", "Ctrl+Up",
                         "Ctrl+Down", "Ctrl+C"} <= keys)
        from PySide6.QtWidgets import QPushButton
        self.assertEqual(window.findChildren(QPushButton), [])


# ---------------------------------------------------------- hidden names --

class TestHiddenNames(PositionsTestCase):

    def test_the_table_hides_the_others_and_reads_hidden_name(self):
        from PySide6.QtCore import Qt

        from gui.positions_window import HIDDEN_NAME, NAME_COL
        window = self._window(hide=True)
        model = window.model
        names = {model.unit_at(row).key: model.index(row, NAME_COL) for row in range(model.rowCount())}
        self.assertEqual(model.data(names[TANK]), "@tester")  # the player writing the log
        self.assertIsNone(model.data(names[TANK], Qt.AccessibleTextRole))
        for key in (DPS, HEALER, STRANGER, LEAVER):
            self.assertNotIn(model.data(names[key]), ("@dps", "@healer", "@stranger", "Lead Leaver"))
            self.assertEqual(model.data(names[key], Qt.AccessibleTextRole), HIDDEN_NAME, key)
        self.assertEqual(model.data(names[f"{BOSS}@1200"]), "Test Boss")  # never hidden

    def test_a_player_who_left_in_the_lead_in_is_hidden_too(self):
        """Not in the entry's player_names, so the main window's mask lets
        the name through; the window's own mask, from the locator, hides
        it."""
        from gui.name_mask import NameMask
        from gui.positions_window import window_mask
        given = NameMask.for_entry(self.entry, True)
        self.assertFalse(given.hides("Lead Leaver"))
        mask = window_mask(given, self.entry.locator)
        self.assertTrue(mask.hides("Lead Leaver"))
        self.assertFalse(mask.hides("@tester"))
        self.assertFalse(mask.hides("Tank Char"))
        self.assertFalse(mask.hides("Test Boss"))
        self.assertIs(window_mask(NameMask.for_entry(self.entry, False), self.entry.locator).active,
                      False)

    def test_the_canvas_label_and_hover_are_masked(self):
        from gui.positions_canvas import label_parts
        window = self._window(hide=True)
        names = window.names()
        self.assertEqual(label_parts(names, "@dps"), ("@", "@dps", ""))
        self.assertEqual(label_parts(names, "@tester"), ("@tester", "", ""))
        self.assertEqual(label_parts(names, "@dps's Companion"), ("@", "@dps", "'s Companion"))
        hover = window.canvas.tooltip_text(self._unit(window, DPS))
        self.assertNotIn("@dps", hover)
        self.assertTrue(hover.startswith("1 @"))
        # The selected unit's label is drawn without error, masked
        self.assertFalse(window.canvas.grab().isNull())

    def test_a_flip_redraws_with_the_new_mask_and_none_keeps_it(self):
        from gui.name_mask import NameMask
        from gui.positions_window import NAME_COL
        window = self._window()
        row = window.model.row_of(DPS)
        self.assertEqual(window.model.data(window.model.index(row, NAME_COL)), "@dps")
        window.refresh(False, names=NameMask.for_entry(self.entry, True))
        self.assertNotEqual(window.model.data(window.model.index(row, NAME_COL)), "@dps")
        window.refresh(True)  # a theme switch keeps the mask
        self.assertNotEqual(window.model.data(window.model.index(row, NAME_COL)), "@dps")
        window.refresh(False, names=NameMask.for_entry(self.entry, False))
        self.assertEqual(window.model.data(window.model.index(row, NAME_COL)), "@dps")


# ---------------------------------------------------------- what is read --

class TestReadingAndUpdates(PositionsTestCase):

    def test_reading_until_the_states_come(self):
        from fight_reread import RereadEvent
        from gui.positions_window import READING
        window = self._window(load=False)
        self.assertIs(window.wanted_locator, self.entry.locator)
        self.assertFalse(window.has_states_for(self.entry.locator))
        self.assertEqual(window.canvas.message(), READING)
        self.assertEqual(window.model.rowCount(), 0)
        # A stale locator's answer, even an equal one, and a cancelled read
        # are dropped without a word
        window.reread_done(RereadEvent("loaded", self.entry.locator._replace(), self.states))
        self.assertIsNone(window.states())
        window.reread_done(RereadEvent("cancelled", self.entry.locator))
        self.assertEqual(window.canvas.message(), READING)
        window.reread_done(RereadEvent("loaded", self.entry.locator, self.states))
        self.assertIs(window.states(), self.states)
        self.assertTrue(window.has_states_for(self.entry.locator))
        self.assertTrue(window.has_states_for(self.entry.locator._replace()))  # by value
        self.assertEqual(window.canvas.message(), "")

    def test_missing_names_files_never_paths(self):
        from fight_reread import RereadEvent
        from gui.positions_window import FAILED, MISSING
        window = self._window(load=False)
        error = ("split 260520190643-Kyne's-Aegis-vet.log: no such file; live Encounter.log: "
                 "unreadable ([Errno 13] Permission denied: "
                 "'C:\\\\Users\\\\Some Body\\\\Documents\\\\Logs\\\\Encounter.log')")
        window.reread_done(RereadEvent("missing", self.entry.locator, error=error))
        text = window.canvas.message()
        self.assertTrue(text.startswith(MISSING))
        self.assertIn("260520190643-Kyne's-Aegis-vet.log", text)
        self.assertIn("'Encounter.log'", text)
        for part in ("Users", "Some Body", "Documents", "\\"):
            self.assertNotIn(part, text)
        window.reread_done(RereadEvent("failed", self.entry.locator,
                                       error="OSError: /home/someone/logs/Encounter.log"))
        self.assertTrue(window.canvas.message().startswith(FAILED))
        self.assertNotIn("someone", window.canvas.message())

    def test_a_folder_with_an_apostrophe_is_cut_too(self):
        """The review's finding 17: a folder such as "Kim O'Neil" (Windows
        allows the apostrophe in a profile folder) stopped the cut, and the
        message showed it glued to the file name. Python's repr puts such
        a path in double quotes."""
        from fight_reread import RereadEvent
        from gui.positions_window import file_names_only
        window = self._window(load=False)
        error = ("live Encounter.log: unreadable ([Errno 13] Permission denied: "
                 "\"C:\\\\Users\\\\Kim O'Neil\\\\OneDrive - Bob's Co\\\\Logs\\\\Encounter.log\"); "
                 "archive a.zip: unreadable ([Errno 13] Permission denied: "
                 "'C:\\\\Users\\\\Some Body\\\\a.zip')")
        window.reread_done(RereadEvent("missing", self.entry.locator, error=error))
        text = window.canvas.message()
        self.assertIn('"Encounter.log"', text)
        self.assertIn("'a.zip'", text)
        for part in ("Kim", "Neil", "OneDrive", "Bob", "Users", "Logs", "\\"):
            self.assertNotIn(part, text)
        self.assertEqual(file_names_only("C:\\Users\\Kim O'Neil\\Documents\\Encounter.log"),
                         "Encounter.log")
        self.assertEqual(file_names_only("/home/o'neil/logs/Encounter.log"), "Encounter.log")

    def test_a_long_message_keeps_its_first_line(self):
        """The review's finding 16: at 200% text in the 1280x648 window a
        'missing' answer naming many archives is taller than the canvas;
        drawn centred, it lost its first line, which says what happened.
        It is drawn from the top then, the end of the list cut."""
        from PySide6.QtGui import QFontMetricsF

        from fight_reread import RereadEvent
        from gui import text_size
        text_size.apply(200)
        window = self._window(load=False, size=(1280, 720 - 40 - 32))
        error = "; ".join(f"archive Encounter-2026-10-{day:02d}-20-00-00.zip: session not in the file"
                          for day in range(1, 13))
        window.reread_done(RereadEvent("missing", self.entry.locator, error=error))
        _app.processEvents()
        canvas = window.canvas
        room, flags = canvas.message_layout()
        need = QFontMetricsF(canvas.font()).boundingRect(room, int(flags), canvas.message())
        self.assertGreater(need.height(), room.height())  # it does overflow
        self.assertGreaterEqual(need.top(), room.top())
        self.assertFalse(canvas.grab().isNull())
        # A short message stays in the middle
        window.reread_done(RereadEvent("missing", self.entry.locator, error="split a.log: no such file"))
        room, flags = canvas.message_layout()
        need = QFontMetricsF(canvas.font()).boundingRect(room, int(flags), canvas.message())
        self.assertAlmostEqual(need.center().y(), room.center().y(), delta=1)

    def test_a_window_hidden_drops_the_states_and_the_locator(self):
        from fight_reread import RereadEvent
        window = self._window()
        window.hide()
        self.assertIsNone(window.states())
        self.assertIsNone(window.wanted_locator)
        self.assertIs(window.entry, self.entry)
        # A read answered after the hide is dropped
        window.reread_done(RereadEvent("loaded", self.entry.locator, self.states))
        self.assertIsNone(window.states())

    def test_updates_draw_once_at_the_same_moment_and_selection(self):
        """A burst of updates draws once, on the next turn of the event
        loop; the rows re-ranked renumber the players; another fight's
        update, or a copy of this one, is left alone."""
        entry = copy.copy(self.entry)
        window = self._window(entry=entry, unit=TANK)
        draws = []
        real = window._draw

        def counting(*args, **kwargs):
            draws.append(1)
            return real(*args, **kwargs)
        window._draw = counting
        entry.players = [entry.players[1], entry.players[0], entry.players[2]]  # replaced, not sorted
        for _ in range(3):
            window.entry_updated(entry, False, None)
        window.entry_updated(copy.copy(entry), False, None)
        self.assertEqual(draws, [])
        _app.processEvents()
        self.assertEqual(len(draws), 1)
        self.assertEqual((window.moment(), window.selected()), (DEATH, TANK))
        numbers = {u.key: u.number for u in window.model.units() if u.number}
        self.assertEqual(numbers, {TANK: 1, DPS: 2, HEALER: 3})
        window._draw = real

    def test_a_new_locator_is_read_and_the_moment_kept(self):
        """The game cut the fight in two and it went on: a new locator
        (here with a later end). The window follows it on its redraw and
        reads until the new states come, keeping the moment and the
        selection."""
        from fight_reread import RereadEvent
        from gui.positions_window import READING
        entry = copy.copy(self.entry)
        window = self._window(entry=entry, unit=TANK)
        old = entry.locator
        entry.locator = old._replace(end_ms=old.end_ms + 5000)
        window.entry_updated(entry, False, None)
        # Before the redraw the window still wants the old locator, so a
        # main window comparing either side of entry_updated asks for a read
        self.assertIs(window.wanted_locator, old)
        _app.processEvents()
        self.assertIs(window.wanted_locator, entry.locator)
        self.assertEqual(window.canvas.message(), READING)
        window.reread_done(RereadEvent("cancelled", old))
        window.reread_done(RereadEvent("loaded", entry.locator, self.states))
        self.assertIs(window.states(), self.states)
        self.assertEqual((window.moment(), window.selected()), (DEATH, TANK))

    def test_an_answer_before_the_redraw_is_taken(self):
        from fight_reread import RereadEvent
        entry = copy.copy(self.entry)
        window = self._window(entry=entry, load=False)
        entry.locator = entry.locator._replace(end_ms=entry.locator.end_ms + 5000)
        window.entry_updated(entry, False, None)
        window.reread_done(RereadEvent("loaded", entry.locator, self.states))
        self.assertIs(window.states(), self.states)
        _app.processEvents()
        self.assertIs(window.states(), self.states)
        self.assertIs(window.wanted_locator, entry.locator)

    def test_a_rebind_keeps_the_states_of_an_equal_locator(self):
        window = self._window()
        replayed = copy.copy(self.entry)
        replayed.locator = self.entry.locator._replace()  # equal, another object
        window.rebind(replayed, None)
        self.assertIs(window.entry, replayed)
        self.assertIs(window.states(), self.states)
        self.assertIs(window.wanted_locator, replayed.locator)
        self.assertTrue(window.has_states_for(replayed.locator))
        other = copy.copy(self.entry)
        other.locator = self.entry.locator._replace(end_ms=END + 5000)
        window.rebind(other, None)
        self.assertFalse(window.has_states_for(other.locator))
        self.assertIs(window.wanted_locator, other.locator)

    def test_mark_replayed(self):
        from gui.positions_window import REPLAYED_NOTE
        window = self._window()
        window.mark_replayed()
        self.assertTrue(window.replayed_label.isVisibleTo(window))
        self.assertEqual(window.replayed_label.text(), REPLAYED_NOTE)
        window.open(self.entry, DEATH, DPS, dark=False, names=None)
        self.assertFalse(window.replayed_label.isVisibleTo(window))

    def test_views_are_none(self):
        self.assertEqual(self._window().views(), [])

    def test_a_window_alone_is_freed_when_deleted(self):
        """No reference to the main window, no lambda on a child: deleted,
        it is freed at once, with the collector off (conftest)."""
        from PySide6.QtCore import QCoreApplication, QEvent

        from fight_reread import RereadEvent
        from gui.positions_window import PositionsWindow
        window = PositionsWindow()
        window.open(self.entry, DEATH, DPS, dark=False, names=None)
        window.reread_done(RereadEvent("loaded", self.entry.locator, self.states))
        window.set_shown("pet", True)
        _app.processEvents()
        freed = weakref.ref(window)
        window.deleteLater()
        del window
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertIsNone(freed())


# ------------------------------------------------------- reading it out --

class TestAccessible(PositionsTestCase):

    def test_the_canvas_is_named_and_described_in_numbers(self):
        from PySide6.QtGui import QAccessible
        window = self._window(hide=False)
        iface = QAccessible.queryAccessibleInterface(window.canvas)
        self.assertEqual(iface.text(QAccessible.Name), "Positions")
        self.assertEqual(iface.text(QAccessible.Description),
                         "0:06.0 into the fight. Test Boss 95%. 3 players, 2 alive.")
        window._go_to(TANK_DEATH - 500)
        description = window.canvas.accessibleDescription()
        self.assertEqual(description, "0:10.5 into the fight. Test Boss 90%. 3 players, 2 alive.")
        self.assertNotIn("@", description)
        from PySide6.QtCore import Qt
        self.assertEqual(window.canvas.focusPolicy(), Qt.NoFocus)

    def test_the_lowest_is_named_by_number(self):
        from gui.positions_window import moment_summary
        window = self._window(t=START + 4500, unit=None)
        self.assertEqual(moment_summary(window.scene(), START, END),
                         "0:04.5 into the fight. Test Boss 96%. 3 players, 3 alive. Lowest: 1 at 50%.")

    def test_the_table_reads_as_a_table_with_hidden_names(self):
        from PySide6.QtGui import QAccessible

        from gui.positions_window import HIDDEN_NAME
        window = self._window(hide=True)
        window.show()
        iface = QAccessible.queryAccessibleInterface(window.table)
        self.assertEqual(iface.role(), QAccessible.Table)
        names = [iface.child(i).text(QAccessible.Name) for i in range(iface.childCount())]
        self.assertIn(HIDDEN_NAME, names)
        self.assertIn("@tester", names)
        self.assertFalse(any("@dps" in name for name in names))

    def test_the_scrub_bar_is_a_slider_of_seconds_with_the_moment_in_words(self):
        from PySide6.QtGui import QAccessible
        window = self._window()
        iface = QAccessible.queryAccessibleInterface(window.scrub)
        self.assertEqual(iface.role(), QAccessible.Slider)
        self.assertEqual(iface.text(QAccessible.Name), "Moment")
        self.assertEqual(iface.text(QAccessible.Value), "6")
        self.assertEqual(iface.text(QAccessible.Description), "0:06.0 into the fight, of 12s")
        window._go_to(START - 2500)
        self.assertEqual(iface.text(QAccessible.Description), "2.5 s before the fight began, of 12s")
        from PySide6.QtCore import Qt
        self.assertEqual(window.scrub.focusPolicy(), Qt.StrongFocus)

    def test_the_parts_are_named(self):
        window = self._window()
        self.assertEqual(window.table.accessibleName(), "Players and bosses")
        self.assertEqual(window.boss_bars.accessibleName(), "Boss health")
        self.assertEqual([window.previous_death.accessibleName(), window.back.accessibleName(),
                          window.forward.accessibleName(), window.next_death.accessibleName(),
                          window.show_button.accessibleName()],
                         ["Previous death", "Back one second", "On one second", "Next death",
                          "Show"])
        self.assertEqual(window.table.accessibleDescription(),
                         window.canvas.accessibleDescription())


# ------------------------------------------------- text size and themes --

class TestTextSizeAndThemes(PositionsTestCase):

    def test_markers_rows_and_columns_grow_and_never_shrink(self):
        from gui import text_size
        window = self._window()
        canvas, table = window.canvas, window.table
        sizes = {}
        for pct in (80, 100, 150, 200):
            text_size.apply(pct)
            _app.processEvents()
            sizes[pct] = (canvas.radius(), table.rowHeight(0), table.columnWidth(3),
                          table.iconSize().width())
        self.assertEqual([sizes[pct][0] for pct in (80, 100, 150, 200)], [8, 8, 12, 16])
        self.assertGreater(sizes[150][1], sizes[100][1])
        self.assertGreater(sizes[200][1], sizes[150][1])
        self.assertGreater(sizes[200][2], sizes[100][2])
        self.assertEqual(sizes[80][3], sizes[100][3])
        self.assertGreater(sizes[200][3], sizes[100][3])
        # A row holds its text: no word wrap, rows sized to their contents
        self.assertFalse(table.wordWrap())
        self.assertGreaterEqual(table.rowHeight(0), table.fontMetrics().height())

    def test_the_pools_columns_leave_at_large_text(self):
        from gui import text_size
        from gui.positions_window import MAGICKA_COL, STAMINA_COL
        window = self._window()
        self.assertFalse(window.table.isColumnHidden(MAGICKA_COL))
        text_size.apply(200)
        _app.processEvents()
        self.assertTrue(window.table.isColumnHidden(MAGICKA_COL))
        self.assertTrue(window.table.isColumnHidden(STAMINA_COL))
        text_size.apply(100)
        _app.processEvents()
        self.assertFalse(window.table.isColumnHidden(STAMINA_COL))

    def test_it_fits_1280_by_720_at_200_percent(self):
        """At 200% text the window fits a 1280x720 screen less a 40 px
        taskbar and a 32 px title bar: its least size within it, the
        canvas at its floor or more, the controls and the scrub bar in the
        window, and the table compact (no magicka or stamina, the health
        as a share), first given at most TABLE_SHARE of the width. How
        many columns then show depends on the font (the tests draw boxes
        twice Segoe UI's width); measured with Segoe UI, the number, name,
        health and state fit (POOLS_UP_TO)."""
        from gui import text_size
        from gui.positions_canvas import CANVAS_LEAST
        from gui.positions_window import (
            HEALTH_COL,
            MAGICKA_COL,
            STAMINA_COL,
            TABLE_SHARE,
            cell_text,
        )
        budget = (1280, 720 - 40 - 32)
        text_size.apply(200)
        window = self._window(size=budget)
        least = window.minimumSizeHint()
        self.assertLessEqual(least.width(), budget[0])
        self.assertLessEqual(least.height(), budget[1])
        self.assertGreaterEqual(window.canvas.width(), CANVAS_LEAST[0])
        self.assertGreaterEqual(window.canvas.height(), CANVAS_LEAST[1])
        from PySide6.QtCore import QPoint, QRect
        for part in (window.previous_death, window.back, window.forward, window.next_death,
                     window.show_button, window.scrub):
            place = QRect(part.mapTo(window, QPoint(0, 0)), part.size())
            self.assertTrue(window.rect().contains(place), part.accessibleName())
        self.assertTrue(window.table.isColumnHidden(MAGICKA_COL))
        self.assertTrue(window.table.isColumnHidden(STAMINA_COL))
        tank_row = window.model.unit_at(window.model.row_of(TANK))
        self.assertEqual(window.model.data(window.model.index(window.model.row_of(TANK), HEALTH_COL)),
                         "100%")
        self.assertEqual(cell_text(tank_row, HEALTH_COL), "100% 50,000")  # the copy keeps it whole
        sizes = window.splitter.sizes()
        self.assertLessEqual(sizes[1], TABLE_SHARE * sum(sizes) + 1)

    def test_the_colours_follow_the_palette(self):
        from gui.positions_canvas import BOSS_COLORS, HOSTILE_COLORS
        window = self._window()
        canvas = window.canvas
        canvas.setPalette(_palette("#f3f3f3"))
        self.assertEqual(canvas.hostile_color().name(), HOSTILE_COLORS[False])
        self.assertEqual(canvas.boss_color().name(), BOSS_COLORS[False])
        canvas.setPalette(_palette("#1e1e1e"))  # a live theme switch
        self.assertEqual(canvas.hostile_color().name(), HOSTILE_COLORS[True])
        self.assertEqual(canvas.boss_color().name(), BOSS_COLORS[True])
        self.assertFalse(canvas.grab().isNull())

    def test_the_table_icons_follow_the_tables_palette(self):
        from PySide6.QtCore import Qt

        from gui.positions_window import NUMBER_COL
        window = self._window()
        index = window.model.index(window.model.row_of(TANK), NUMBER_COL)
        light = _icon_image(window.model.data(index, Qt.DecorationRole))
        window.table.setPalette(_palette("#1e1e1e"))
        from PySide6.QtGui import QColor, QPalette
        palette = window.table.palette()
        palette.setColor(QPalette.Base, QColor("#2d2d2d"))
        window.table.setPalette(palette)
        window.refresh(True)
        dark = _icon_image(window.model.data(index, Qt.DecorationRole))
        self.assertNotEqual(light.pixelColor(light.width() // 2, light.height() // 2),
                            dark.pixelColor(dark.width() // 2, dark.height() // 2))

    def test_a_selected_rows_icon_is_drawn_in_the_highlighted_text(self):
        """Finding 15 (#214 review): the selected row's picture, on the
        dark theme's light blue highlight (Windows 11's #4cc2ff), was the
        light ink at 1.3:1; it is drawn in the table's highlighted text,
        3:1 or more, the row's other pictures staying in the ink."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QIcon, QPalette

        from gui.positions_canvas import colors
        from gui.positions_window import NUMBER_COL
        from tests.unit.colour_measure import contrast
        window = self._window(unit=TANK)
        palette = _palette("#1e1e1e")
        for role, value in ((QPalette.Base, "#2d2d2d"), (QPalette.Highlight, "#4cc2ff"),
                            (QPalette.HighlightedText, "#000000")):
            palette.setColor(role, QColor(value))
        window.table.setPalette(palette)
        window.refresh(True)
        row = window.model.row_of(TANK)
        self.assertTrue(window.table.selectionModel().isRowSelected(row))
        icon = window.model.data(window.model.index(row, NUMBER_COL), Qt.DecorationRole)
        selected = _icon_image(icon, QIcon.Selected)
        middle = selected.pixelColor(selected.width() // 2, selected.height() // 2)
        self.assertEqual(middle.alpha(), 255)
        self.assertGreaterEqual(contrast(middle.name(), "#4cc2ff"), 3.0)  # a mark's floor
        normal = _icon_image(icon)
        self.assertEqual(normal.pixelColor(normal.width() // 2, normal.height() // 2).name(),
                         colors(True)["ink"].name())


    def test_the_lines_over_and_under_the_canvas_keep_off_it_at_the_least_size(self):
        """The review's finding 13: the header and the line under the
        canvas wrap, and the window's least size counted each at one line,
        so at its least size the canvas, which keeps its floor, was drawn
        under the line beneath it and the controls. Each label claims its
        lines' height at its width, and the least size grows with them."""
        from PySide6.QtCore import QCoreApplication, QEvent, QPoint

        from gui import text_size
        text_size.apply(200)
        window = self._window(size=(1120, 700))
        self.assertTrue(window.elsewhere_label.text())
        window.resize(545, 1)
        for _ in range(6):
            QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
            _app.processEvents()

        def top(widget):
            return widget.mapTo(window, QPoint(0, 0)).y()
        canvas, below, header = window.canvas, window.elsewhere_label, window.fight_label
        self.assertGreater(below.heightForWidth(below.width()), below.fontMetrics().height())
        self.assertGreater(header.heightForWidth(header.width()), header.fontMetrics().height())
        self.assertGreaterEqual(below.height(), below.heightForWidth(below.width()))
        self.assertGreaterEqual(header.height(), header.heightForWidth(header.width()))
        self.assertLessEqual(top(canvas) + canvas.height(), top(below))
        self.assertLessEqual(top(header) + header.height(), top(window.boss_bars))
        self.assertLessEqual(top(below) + below.height(), top(window.back))
        self.assertGreaterEqual(canvas.height(), 260)


class TestTheGuide(unittest.TestCase):
    """The user guide's Positions section says what the window draws and
    shows, in the code's own numbers (the review's findings 06 and 20)."""

    def _section(self, path, heading):
        text = (Path(__file__).resolve().parents[2] / path).read_text(encoding="utf-8")
        start = text.index(heading)
        end = text.find("\n## ", start + len(heading))
        return text[start:end if end >= 0 else None]

    def test_the_picture_and_the_table_at_large_text(self):
        from gui.positions_canvas import DEAD_ADD_MS, FORGET_MS
        from gui.positions_window import POOLS_UP_TO
        guide = self._section("docs/user-guide.md", "\n## Positions\n")
        for words in ("share one box", "a short bar of their health",
                      "held at the picture's edge", "not the way it faces",
                      f"for {FORGET_MS // 1000} seconds", f"a cross for {DEAD_ADD_MS // 1000} seconds",
                      f"above {round(POOLS_UP_TO * 100)}% it leaves out magicka and stamina",
                      "**Ctrl+C** still copies them", "The time on each row of the [Deaths tab]"):
            self.assertIn(words, guide)
        # The release notes: the fragment until a release commit folds it
        # into CHANGELOG.md
        root = Path(__file__).resolve().parents[2]
        fragment = root / "changelog.d" / "214-positions.md"
        notes = fragment if fragment.exists() else root / "CHANGELOG.md"
        self.assertIn(f"above {round(POOLS_UP_TO * 100)}% text it leaves out magicka and stamina",
                      notes.read_text(encoding="utf-8"))


# ----------------------------------------------- bosses added again --

class TestBossesAddedAgain(PositionsTestCase):
    """The review's findings 01 and 12, 02 and 11: a boss the game removes
    and adds again as a new unit (Z'Maja between her phases) is one boss to
    the bars, the description and the line under the canvas, at the unit
    present; four boss rows fit 1280x720 at 200% text."""

    @classmethod
    def setUpClass(cls):
        global _app
        _app = _ensure_app()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.log, cls.path, cls.fights, cls.states = split_and_states(cls.root, boss_twins())
        cls.entry = cls.fights[0]

    def test_the_session(self):
        twins = [u for u in self.entry.locator.units if u.name == "Twin"]
        self.assertEqual([(u.key, u.since_ms, u.until_ms) for u in twins],
                         [(TWIN, 1200, TWIN_GONE_AT), (TWIN_BACK, TWIN_BACK_AT, None)])

    def test_one_twin_at_the_unit_present(self):
        from gui.positions_canvas import LEFT, MARK_BOSS
        from gui.positions_window import boss_rows
        window = self._window(t=TWIN_BACK_AT + 3000, unit=None)
        self.assertEqual(len([u for u in window.scene().units if u.mark == MARK_BOSS]), 5)
        # The table keeps every unit
        self.assertEqual(len([u for u in window.model.units() if u.mark == MARK_BOSS]), 5)
        self.assertEqual(window.boss_bars.rows(), [("Test Boss", 900_000, 1_000_000, True),
                                                   ("Twin", 800_000, 1_000_000, True),
                                                   ("Gate Keeper", 500_000, 1_000_000, True),
                                                   ("Warden", 400_000, 1_000_000, True)])
        self.assertEqual([u.key for u in boss_rows(window.scene().units)][1], f"{TWIN_BACK}@{TWIN_BACK_AT}")
        description = window.canvas.accessibleDescription()
        self.assertIn("Test Boss 90%. Twin 80%. Gate Keeper 50%. Warden 40%. 3 players", description)
        self.assertEqual(description.count("Twin"), 1)
        self.assertNotIn("Twin", window.elsewhere_label.text())
        # The first unit, present; the second not yet: one Twin, no 'not
        # in the log yet' for it
        window._go_to(START + 2600)
        self.assertIn(("Twin", 600_000, 1_000_000, True), window.boss_bars.rows())
        self.assertEqual([row[0] for row in window.boss_bars.rows()].count("Twin"), 1)
        self.assertNotIn("Twin not in the log yet", window.canvas.accessibleDescription())
        self.assertNotIn("Twin", window.elsewhere_label.text())
        # Between the two: the first left, the second not yet: 'left'
        window._go_to(TWIN_GONE_AT + 1000)
        self.assertIn(("Twin", 0, 0, LEFT), window.boss_bars.rows())
        self.assertIn("Twin left.", window.canvas.accessibleDescription())
        self.assertIn("Twin left", window.boss_bars.accessibleDescription())
        self.assertNotIn("Twin", window.elsewhere_label.text())
        self.assertIn("Not in the log yet: Warden", window.elsewhere_label.text())
        # Before either has a state: one 'not in the log yet'
        window._go_to(START + 100)
        self.assertEqual([row for row in window.boss_bars.rows() if row[0] == "Twin"],
                         [("Twin", 0, 0, False)])
        self.assertEqual(window.elsewhere_label.text().count("Twin"), 1)

    def test_two_units_of_one_name_present_together_both_stay(self):
        from gui.positions_canvas import DRAWN, MARK_BOSS, UnitAt
        from gui.positions_window import boss_rows
        here = [u for u in self._window(t=TWIN_BACK_AT + 3000, unit=None).scene().units
                if u.mark == MARK_BOSS and u.name == "Twin" and u.state is not None]
        first = here[0]._replace(where=DRAWN, until=None)
        both = boss_rows([first, here[1]])
        self.assertEqual([u.key for u in both], [first.key, here[1].key])
        self.assertIsInstance(both[0], UnitAt)

    def test_four_boss_rows_fit_1280_by_720_at_200_percent(self):
        """The bars take BOSS_ROWS_MAX lines at most, living bosses first,
        the last counting the rest; their description keeps them all; the
        window's least size fits the budget, the canvas at its floor or
        more, and the line under it keeps off it."""
        from PySide6.QtCore import QPoint

        from gui import text_size
        from gui.positions_canvas import BOSS_ROWS_MAX, CANVAS_LEAST, more_bosses_text
        budget = (1280, 720 - 40 - 32)
        text_size.apply(200)
        window = self._window(t=TWIN_BACK_AT + 3000, unit=None, size=budget)
        bars = window.boss_bars
        self.assertEqual(len(bars.rows()), 4)
        shown, more = bars.shown_rows()
        self.assertEqual(([row[0] for row in shown], more), (["Test Boss", "Twin"], 2))
        self.assertEqual(more_bosses_text(more), "and 2 more bosses (in the table)")
        self.assertEqual(bars.accessibleDescription().count("%"), 4)
        self.assertLessEqual(bars.sizeHint().height(),
                             round(bars._line() * BOSS_ROWS_MAX) + 4)
        least = window.minimumSizeHint()
        self.assertLessEqual(least.height(), budget[1])
        self.assertLessEqual(window.height(), budget[1])
        self.assertGreaterEqual(window.canvas.height(), CANVAS_LEAST[1])
        canvas, below = window.canvas, window.elsewhere_label
        self.assertLessEqual(canvas.mapTo(window, QPoint(0, canvas.height())).y(),
                             below.mapTo(window, QPoint(0, 0)).y())
        self.assertFalse(bars.grab().isNull())
        # A living boss comes before one that left
        window._go_to(TWIN_GONE_AT + 1000)
        self.assertEqual([row[0] for row in bars.rows()],
                         ["Test Boss", "Twin", "Gate Keeper", "Warden"])
        shown, more = bars.shown_rows()
        self.assertEqual(([row[0] for row in shown], more), (["Test Boss", "Gate Keeper"], 2))


# ------------------------------------------------- the dead above 0 --

class TestTheDeadAboveZero(PositionsTestCase):
    """The review's finding 03: the log can write a dead player's health
    above 0, and a death's link opens at its own millisecond. A death the
    fight counts makes the player dead until their health rises."""

    @classmethod
    def setUpClass(cls):
        global _app
        _app = _ensure_app()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.log, cls.path, cls.fights, cls.states = split_and_states(cls.root, corpse_ticks())
        cls.entry = cls.fights[0]

    def test_the_session(self):
        self.assertEqual([(r["unit_id"], r["time_ms"]) for r in self.entry.death_recaps],
                         [(DPS, DEATH - START), (TANK, TANK_DEATH - START)])
        dps_track = next(t for t in self.states.tracks if t.unit is not None and t.unit.key == DPS)
        self.assertEqual(dps_track.row(dps_track.at(DEATH)).health, 631)

    def test_a_corpses_tick_in_the_deaths_millisecond(self):
        """The damage dealer at 631 health from their death's own
        millisecond: dead until the revive at DEATH + 3000."""
        from gui.positions_canvas import ALIVE, DEAD
        from gui.positions_window import STATE_COL, cell_text
        window = self._window(t=DEATH, unit=DPS)
        unit = self._unit(window, DPS)
        self.assertEqual(unit.look, DEAD)
        self.assertEqual(cell_text(unit, STATE_COL), "dead")
        self.assertIn("3 players, 2 alive.", window.canvas.accessibleDescription())
        window._go_to(DEATH + 2900)
        self.assertEqual(self._unit(window, DPS).look, DEAD)
        window._go_to(DEATH + 3000)
        self.assertEqual(self._unit(window, DPS).look, ALIVE)
        window._go_to(DEATH - 1)
        self.assertNotEqual(self._unit(window, DPS).look, DEAD)

    def test_a_died_line_with_the_health_before_the_kill(self):
        """The tank's hit and DIED line carry 40,000 health; 0 is written
        30 ms later, then a corpse's tick at 631 with magicka and stamina
        at 0, which is no revive."""
        from gui.positions_canvas import DEAD
        window = self._window(t=TANK_DEATH, unit=TANK)
        self.assertEqual(self._unit(window, TANK).state.health, 40_000)
        self.assertEqual(self._unit(window, TANK).look, DEAD)
        for t in (TANK_DEATH + 30, TANK_DEATH + 600, END + 1000):
            window._go_to(t)
            self.assertEqual(self._unit(window, TANK).look, DEAD, t)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestTheLineUnderTheCanvas(unittest.TestCase):

    def test_copies_of_one_boss_are_named_once_with_their_count(self):
        """A boss the game splits into copies (Dreadsail Reef's Reef
        Guardian) is named once with its count, so the line does not wrap
        past the 200% budget."""
        from gui.positions_window import _counted
        self.assertEqual(_counted(["6", "Reef Guardian", "11", "Reef Guardian", "Reef Guardian"]),
                         ["6", "Reef Guardian ×3", "11"])
        self.assertEqual(_counted([]), [])



@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TestADeathPastTheRange(PositionsTestCase):

    def test_next_death_goes_no_further_than_a_death_shown_at_the_end(self):
        """A death counted past the range's end (one read from health 0
        settled at the next fight) is shown at the range's end; Next from
        there goes no further and Previous goes back (the review of PR
        #224)."""
        entry = copy.copy(self.entry)
        late = dict(self.entry.death_recaps[-1], unit_id=HEALER,
                    time_ms=END + 5000 - entry.locator.start_ms)
        entry.death_recaps = list(self.entry.death_recaps) + [late]
        window = self._window(entry, t=TANK_DEATH, unit=TANK)
        window.next_death.click()
        self.assertEqual((window.moment(), window.selected()), (END + 1000, HEALER))
        self.assertFalse(window.next_death.isEnabled())
        window.previous_death.click()
        self.assertEqual((window.moment(), window.selected()), (TANK_DEATH, TANK))

if __name__ == "__main__":
    unittest.main()
