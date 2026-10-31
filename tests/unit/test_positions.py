"""
Where the group stood (positions.py, issue #148): the recorder's samples,
the engine's fight entry, and the crop and heat map_art computes from them.
"""
import unittest

import map_art
from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory
from fight_history import FightHistoryEntry
from positions import SCALE, PositionRecorder

VLC = "deadlands/u42tri_lucentcitmap001"


def _recorder(path=VLC):
    recorder = PositionRecorder()
    recorder.map_changed("2552", "Lucent Citadel", path)
    return recorder


def _points(record):
    return map_art.points(record["xy"])


class TestRecorder(unittest.TestCase):

    def test_one_sample_a_second_per_member(self):
        recorder = _recorder()
        recorder.begin_combat(1000)
        for t in range(1000, 4600, 200):
            # As the engine does: the samples due, then the line's states
            if t >= recorder.next_tick:
                recorder.sample(t, [("1",), ("2",)])
            recorder.note("1", "100/100", "0.5000", "0.2500", t)
            recorder.note("2", "100/100", "0.2500", "0.7500", t)
        maps = recorder.fight_maps(1000, 5000)
        self.assertEqual(len(maps), 1)
        # Ticks at 2000, 3000 and 4000 (the one at 1000 came before any line)
        self.assertEqual(sorted(_points(maps[0])), [(0.25, 0.75)] * 3 + [(0.5, 0.25)] * 3)
        self.assertEqual(maps[0]["seconds"], 3)
        self.assertEqual((maps[0]["path"], maps[0]["map_id"], maps[0]["name"]),
                         (VLC, "2552", "Lucent Citadel"))

    def test_a_silent_member_is_left_out_not_held(self):
        recorder = _recorder()
        recorder.note("1", "100/100", "0.5", "0.5", 900)
        recorder.begin_combat(1000)
        recorder.note("2", "100/100", "0.1", "0.1", 1000)
        for t in (2000, 3000, 4000, 5000):
            recorder.sample(t, [("1",), ("2",)])
            recorder.note("2", "100/100", "0.1", "0.1", t)
        counts = {}
        for x, _y in _points(recorder.fight_maps(0, 9000)[0]):
            counts[x] = counts.get(x, 0) + 1
        # Ticks 1000 to 5000. Member 1's position of 900 stands until 3900,
        # past STALE_MS no more; member 2 speaks every second
        self.assertEqual(counts[0.5], 3)
        self.assertEqual(counts[0.1], 5)

    def test_a_dead_member_is_left_out(self):
        recorder = _recorder()
        recorder.begin_combat(1000)
        recorder.note("1", "0/30000", "0.5", "0.5", 1500)
        recorder.sample(2000, [("1",)])
        self.assertEqual(recorder.fight_maps(0, 9000), [])
        recorder.note("1", "12000/30000", "0.5", "0.5", 2500)
        recorder.sample(3000, [("1",)])
        self.assertEqual(len(recorder.fight_maps(0, 9000)[0]["xy"]), 2)

    def test_coordinates_off_the_map_are_dropped_and_near_ones_clamped(self):
        recorder = _recorder()
        recorder.begin_combat(2000)
        recorder.note("1", "1/1", "212.9151", "-195.2606", 1500)   # loading the zone
        recorder.note("2", "1/1", "0.4", "1.19", 1500)              # past the edge
        recorder.note("3", "1/1", "0.0000", "0.0000", 1500)         # no position
        recorder.sample(2000, [("1",), ("2",), ("3",)])
        self.assertEqual(_points(recorder.fight_maps(0, 9000)[0]), [(0.4, 1.0)])

    def test_each_sample_keeps_the_map_of_its_line(self):
        recorder = _recorder()
        recorder.begin_combat(2000)
        recorder.note("1", "1/1", "0.2", "0.2", 1500)
        recorder.map_changed("2553", "Other", "deadlands/other")
        recorder.note("2", "1/1", "0.8", "0.8", 1600)
        recorder.sample(2000, [("1",), ("2",)])
        recorder.note("1", "1/1", "0.3", "0.3", 2500)
        recorder.sample(3000, [("1",), ("2",)])
        maps = recorder.fight_maps(0, 9000)
        self.assertEqual([m["path"] for m in maps], [VLC, "deadlands/other"])
        self.assertEqual(_points(maps[0]), [(0.2, 0.2)])
        self.assertEqual(sorted(_points(maps[1])), [(0.3, 0.3), (0.8, 0.8), (0.8, 0.8)])
        self.assertEqual(maps[1]["first_s"], 2.0)

    def test_the_same_path_is_one_map(self):
        recorder = _recorder()
        recorder.map_changed("1", "Kyne's Aegis", "skyrim/floor2")
        recorder.map_changed("2552", "Lucent Citadel", VLC.upper())
        recorder.begin_combat(1000)
        recorder.note("1", "1/1", "0.2", "0.2", 1500)
        recorder.sample(2000, [("1",)])
        self.assertEqual([m["path"] for m in recorder.fight_maps(0, 9000)], [VLC])

    def test_nothing_before_the_first_map_or_after_a_zone_change(self):
        recorder = PositionRecorder()
        recorder.begin_combat(1000)
        recorder.note("1", "1/1", "0.2", "0.2", 1500)
        recorder.sample(2000, [("1",)])
        self.assertEqual(recorder.fight_maps(0, 9000), [])
        recorder.map_changed("2552", "Lucent Citadel", VLC)
        recorder.zone_changed()
        recorder.note("1", "1/1", "0.2", "0.2", 2500)
        recorder.sample(3000, [("1",)])
        self.assertEqual(recorder.fight_maps(0, 9000), [])

    def test_a_long_lull_takes_only_the_fresh_ticks(self):
        recorder = _recorder()
        recorder.begin_combat(1000)
        recorder.note("1", "1/1", "0.2", "0.2", 1000)
        recorder.sample(60000, [("1",)])
        # 1000 to 4000 had the position fresh; then nothing till the line
        self.assertEqual(recorder.fight_maps(0, 99000)[0]["seconds"], 4)
        self.assertEqual(recorder.next_tick, 61000)

    def test_the_freshest_of_a_members_unit_ids(self):
        recorder = _recorder()
        recorder.begin_combat(2000)
        recorder.note("5", "1/1", "0.1", "0.1", 1100)
        recorder.note("9", "1/1", "0.9", "0.9", 1200)   # back on a new unit id
        recorder.sample(2000, [("5", "9")])
        self.assertEqual(_points(recorder.fight_maps(0, 9000)[0]), [(0.9, 0.9)])

    def test_prune_and_reset(self):
        recorder = _recorder()
        recorder.begin_combat(1000)
        for t in (1500, 2500, 3500):
            recorder.note("1", "1/1", "0.2", "0.2", t)
            recorder.sample(t + 500, [("1",)])
        recorder.prune_before(3000)
        self.assertEqual(recorder.fight_maps(0, 9000)[0]["seconds"], 2)
        recorder.reset()
        self.assertEqual(recorder.fight_maps(0, 9000), [])
        self.assertFalse(recorder.active)

    def test_samples_are_stored_in_steps_of_one_ten_thousandth(self):
        recorder = _recorder()
        recorder.begin_combat(2000)
        recorder.note("1", "1/1", "0.1235", "0.6789", 1500)
        recorder.sample(2000, [("1",)])
        self.assertEqual(list(recorder.fight_maps(0, 9000)[0]["xy"]), [1235, 6789])
        self.assertEqual(SCALE, 10000)


# ---- the engine ----

EPOCH = 1759600000000
HIT = "12345"


def _unit(unit_id, x, y, health="20000/20000"):
    return f"{unit_id},{health},26657/26657,13021/13021,500/500,1000/1000,0,{x},{y},5.5"


def _boss():
    return "70,1000000/1000000,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _hit(ts, unit, x, y):
    return f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,900,{HIT},{_unit(unit, x, y)},{_boss()}"


LOG = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1478,"Lucent Citadel",VETERAN',
    '1001,MAP_CHANGED,2552,"Lucent Citadel","deadlands/U42TRI_LucentCitMap001"',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,4,9,"Pique","@brainsnorkel",1001,50,3230,0,PLAYER_ALLY,T',
    '2001,UNIT_ADDED,2,PLAYER,F,2,0,F,4,9,"Other","@other",1002,50,3230,0,PLAYER_ALLY,T',
    '2002,UNIT_ADDED,3,PLAYER,F,3,0,F,4,9,"Passer","@passer",1003,50,3230,0,PLAYER_ALLY,F',
    '2500,UNIT_ADDED,70,MONSTER,F,0,1000000,T,0,0,"Xoryn","",0,50,160,0,HOSTILE,F',
    f'2600,ABILITY_INFO,{HIT},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,T',
    "10000,BEGIN_COMBAT",
    "10001,PLAYER_INFO,1,[],[],[],[],[]",
    _hit(10100, 1, "0.5000", "0.5000"),
    f"10200,HEALTH_REGEN,500,{_unit(2, '0.5100', '0.5100')}",
    f"10300,EFFECT_CHANGED,GAINED,1,7,{HIT},{_unit(3, '0.9000', '0.9000')},*",
    _hit(11100, 1, "0.5000", "0.5000"),
    _hit(12100, 1, "0.5000", "0.5000"),
    "12500,MAP_CHANGED,2553,\"Lucent Citadel\",\"deadlands/U42TRI_LucentCitMap002\"",
    f"12600,BEGIN_CAST,0,F,8,{HIT},{_unit(1, '0.2000', '0.3000')},*",
    _hit(13100, 1, "0.2000", "0.3000"),
    "14000,END_COMBAT",
]


def _fight():
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in LOG:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer.fight_history.fights[0]


class TestEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fight = _fight()

    def test_the_entry_has_the_maps_in_the_order_reached(self):
        self.assertEqual([m["path"] for m in self.fight.positions],
                         [VLC, "deadlands/u42tri_lucentcitmap002"])

    def test_group_members_only(self):
        first = self.fight.positions[0]
        # The logging player and the grouped one; never the passer-by at 0.9
        self.assertNotIn((0.9, 0.9), _points(first))
        self.assertIn((0.51, 0.51), _points(first))
        self.assertIn((0.5, 0.5), _points(first))

    def test_a_sample_after_the_map_changed_is_on_the_new_map(self):
        second = self.fight.positions[1]
        self.assertEqual(_points(second), [(0.2, 0.3)])

    def test_an_entry_built_without_positions_has_none(self):
        self.assertIsNone(FightHistoryEntry().positions)


# ---- the crop and the heat ----

class TestCrop(unittest.TestCase):

    def test_an_arena_gets_the_least_crop_round_its_box(self):
        pts = [(0.50 + 0.04 * (i % 10) / 10, 0.30 + 0.05 * (i // 10) / 10) for i in range(100)]
        x0, y0, side = map_art.crop_square(pts)
        self.assertAlmostEqual(side, map_art.MIN_CROP)
        left, top, right, bottom = map_art.fight_box(pts)
        self.assertLessEqual(x0, left)
        self.assertGreaterEqual(x0 + side, right)
        self.assertLessEqual(y0, top)
        self.assertGreaterEqual(y0 + side, bottom)

    def test_a_crop_is_moved_inside_the_map(self):
        x0, y0, side = map_art.crop_square([(0.01, 0.99)] * 10)
        self.assertGreaterEqual(x0, 0.0)
        self.assertLessEqual(y0 + side, 1.0 + 1e-9)

    def test_a_wide_fight_is_the_whole_map_at_most(self):
        pts = [(0.05, 0.05), (0.95, 0.95)] * 50
        self.assertEqual(map_art.crop_square(pts), (0.0, 0.0, 1.0))

    def test_a_stray_sample_does_not_set_the_box(self):
        pts = [(0.5, 0.5)] * 99 + [(0.95, 0.95)]
        self.assertEqual(map_art.fight_box(pts)[2:], (0.5, 0.5))

    def test_no_samples_is_the_whole_map(self):
        self.assertEqual(map_art.fight_box([]), (0.0, 0.0, 1.0, 1.0))


class TestHeat(unittest.TestCase):

    def test_the_hottest_cell_is_one(self):
        grid = map_art.heat_grid([(0.5, 0.5)] * 20 + [(0.2, 0.2)] * 5, (0.0, 0.0, 1.0), 32)
        peak = max(max(row) for row in grid)
        self.assertAlmostEqual(peak, 1.0)
        self.assertEqual(grid[16][16], peak)
        self.assertLess(grid[6][6], 0.5)

    def test_samples_outside_the_crop_are_not_counted(self):
        grid = map_art.heat_grid([(0.9, 0.9)], (0.0, 0.0, 0.5), 16)
        self.assertEqual(max(max(row) for row in grid), 0.0)

    def test_the_outline_closes_round_a_hot_spot(self):
        grid = [[0.0] * 5 for _ in range(5)]
        grid[2][2] = 1.0
        segments = map_art.contour_segments(grid, 0.5)
        self.assertEqual(len(segments), 4)
        ends = {}
        for a, b in segments:
            for point in (a, b):
                ends[point] = ends.get(point, 0) + 1
        self.assertTrue(all(n == 2 for n in ends.values()))

    def test_a_spot_at_the_edge_closes_too(self):
        grid = [[1.0, 0.0], [0.0, 0.0]]
        self.assertEqual(len(map_art.contour_segments(grid, 0.5)), 4)


class TestArt(unittest.TestCase):

    def test_a_bundled_map_is_found_by_its_path_in_any_case(self):
        self.assertIsNotNone(map_art.art_path("deadlands/U42TRI_LucentCitMap001"))
        self.assertIn(VLC, map_art.manifest())

    def test_an_unknown_map_has_none(self):
        self.assertIsNone(map_art.art_path("glenumbra/daggerfall_base"))
        self.assertIsNone(map_art.art_path(""))


if __name__ == "__main__":
    unittest.main()
