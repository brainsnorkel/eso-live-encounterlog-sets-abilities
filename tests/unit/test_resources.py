"""
Magicka, stamina and ultimate spent and gained (resources.py, issue #125):
the recorder, the engine's fight entry and the build window's section.
"""

import unittest

import resources
from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory
from gui.build_render import (
    DEALT_ANCHOR,
    PEN_CRIT_ANCHOR,
    RESOURCES_ANCHOR,
    RESOURCES_TITLE,
    render_build_html,
)
from gui.name_mask import NameMask

EPOCH = 1759600000000
HIT = '12345'
FORCE_PULSE, ICE_COMET, LIGHT_LIGHTNING = '46356', '40489', '18350'
BOUNTIFUL_HARVEST, UNDAUNTED_STAMINA = '263829', '55678'
FATECARVER, FATECARVER_TICK = '186366', '186370'


class TestRecorder(unittest.TestCase):

    def test_a_drop_at_a_cast_is_its_cost(self):
        recorder = resources.ResourceRecorder()
        recorder.observe('1', 1000, '20000/20000', '26000/26000', '500/500')
        recorder.note_cast('1', 1200, '7', FORCE_PULSE)
        recorder.observe('1', 1200, '17300/20000', '26000/26000', '500/500')
        # A fall with no cast at its millisecond: other spending
        recorder.observe('1', 1500, '17300/20000', '25000/26000', '500/500')
        summary = recorder.fight_summary('1', 1000, 2000, 1.0, name_of=lambda a: "Force Pulse")
        magicka, stamina = summary['pools'][0], summary['pools'][1]
        self.assertEqual((magicka['spent'], magicka['on_casts']), (2700, 2700))
        self.assertEqual((stamina['spent'], stamina['on_casts']), (1000, 0))
        self.assertEqual(summary['spent_on'], [
            {'pool': 0, 'id': FORCE_PULSE, 'name': 'Force Pulse', 'casts': 1, 'total': 2700}])

    def test_a_drop_written_just_before_the_cast_line_is_the_casts(self):
        recorder = resources.ResourceRecorder()
        recorder.observe('1', 1000, '20000/20000', '26000/26000', '500/500')
        # An effect line at the cast's millisecond already carries the cost
        recorder.observe('1', 1200, '17300/20000', '26000/26000', '500/500')
        recorder.note_cast('1', 1200, '7', FORCE_PULSE)
        recorder.observe('1', 1200, '17300/20000', '26000/26000', '500/500')
        summary = recorder.fight_summary('1', 1000, 2000, 1.0)
        self.assertEqual(summary['pools'][0]['on_casts'], 2700)
        self.assertEqual(summary['spent_on'][0]['casts'], 1)

    def test_free_casts_are_never_charged(self):
        recorder = resources.ResourceRecorder()
        recorder.observe('1', 1000, '20000/20000', '26000/26000', '500/500')
        recorder.note_cast('1', 1200, '7', LIGHT_LIGHTNING)
        recorder.observe('1', 1200, '20000/20000', '25000/26000', '500/500')
        summary = recorder.fight_summary('1', 1000, 2000, 1.0)
        self.assertEqual(summary['pools'][1]['on_casts'], 0)
        self.assertEqual(summary['spent_on'], [])

    def test_a_channel_tick_is_the_skills_cost_but_not_a_cast(self):
        recorder = resources.ResourceRecorder()
        recorder.observe('1', 1000, '20000/20000', '26000/26000', '500/500')
        recorder.note_cast('1', 1000, '8', FATECARVER)
        for i, ts in enumerate((1300, 1600, 1900)):
            recorder.note_cast('1', ts, '8', FATECARVER, counted=False)
            recorder.observe('1', ts, '20000/20000', f'{26000 - 289 * (i + 1)}/26000', '500/500')
        row = recorder.fight_summary('1', 1000, 2000, 1.0)['spent_on'][0]
        self.assertEqual((row['casts'], row['total']), (1, 867))

    def test_an_energize_row_books_the_rise_and_the_waste(self):
        recorder = resources.ResourceRecorder()
        recorder.observe('1', 1000, '18000/20000', '26000/26000', '500/500')
        recorder.observe('1', 1100, '19000/20000', '26000/26000', '500/500',
                         energize=(0, BOUNTIFUL_HARVEST, 1000, '2'))
        recorder.observe('1', 1200, '20000/20000', '26000/26000', '500/500')   # unlogged
        # At a full pool a logged gain changes nothing: waste
        recorder.observe('1', 1300, '20000/20000', '26000/26000', '500/500',
                         energize=(0, BOUNTIFUL_HARVEST, 800, '2'))
        summary = recorder.fight_summary('1', 1000, 2000, 1.0, giver_name=lambda k: '@healer')
        magicka = summary['pools'][0]
        self.assertEqual((magicka['gained'], magicka['logged'], magicka['wasted']), (2000, 1000, 800))
        self.assertEqual(summary['gained_from'][0]['givers'], ['@healer'])

    def test_a_gain_from_several_givers_is_one_row(self):
        recorder = resources.ResourceRecorder()
        recorder.observe('1', 1000, '10000/20000', '1/1', '1/1')
        recorder.observe('1', 1100, '10168/20000', '1/1', '1/1', energize=(0, '88401', 168, '2'))
        recorder.observe('1', 1200, '10504/20000', '1/1', '1/1', energize=(0, '88401', 336, '3'))
        recorder.observe('1', 1300, '10672/20000', '1/1', '1/1', energize=(0, '88401', 168, ''))
        rows = recorder.fight_summary('1', 1000, 2000, 1.0, giver_name=lambda k: f'@p{k}')['gained_from']
        self.assertEqual([(r['total'], r['givers']) for r in rows], [(672, ['@p3', '@p2'])])

    def test_time_at_full_ultimate_caps_each_step(self):
        recorder = resources.ResourceRecorder()
        recorder.observe('1', 1000, '1/1', '1/1', '500/500')
        # A minute idle before the fight counts as MAX_STEP_MS, not 60 s
        recorder.observe('1', 61000, '1/1', '1/1', '500/500')
        recorder.observe('1', 62000, '1/1', '1/1', '250/500')
        recorder.observe('1', 64000, '1/1', '1/1', '250/500')
        summary = recorder.fight_summary('1', 61000, 64000, 3.0)
        self.assertAlmostEqual(summary['full_pct'], 100.0 * 3000 / 5000)

    def test_the_window_and_pruning(self):
        recorder = resources.ResourceRecorder()
        recorder.observe('1', 1000, '20000/20000', '1/1', '1/1')
        recorder.observe('1', 1500, '19000/20000', '1/1', '1/1')
        recorder.observe('1', 5500, '18000/20000', '1/1', '1/1')
        self.assertEqual(recorder.fight_summary('1', 5000, 6000, 1.0)['pools'][0]['spent'], 1000)
        recorder.prune_before(5000)
        self.assertIsNone(recorder.fight_summary('1', 1000, 2000, 1.0))
        self.assertIsNone(recorder.fight_summary('2', 1000, 2000, 1.0))

    def test_the_top_rows_and_the_rest(self):
        recorder = resources.ResourceRecorder()
        recorder.observe('1', 1000, '20000/20000', '1/1', '1/1')
        magicka = 20000
        for i in range(resources.TOP + 2):
            magicka -= 100 * (i + 1)
            recorder.note_cast('1', 1100 + i, str(i), str(1000 + i))
            recorder.observe('1', 1100 + i, f'{magicka}/20000', '1/1', '1/1')
        rows = recorder.fight_summary('1', 1000, 2000, 1.0)['spent_on']
        self.assertEqual(len(rows), resources.TOP + 1)
        self.assertEqual(rows[0]['total'], 700)
        self.assertEqual(rows[-1], {'pool': 0, 'more': 2, 'total': 300})

    def test_energize_of(self):
        fields = ['POWER_ENERGIZE', 'GENERIC', '4', '331', '0', '9', '263901']
        self.assertEqual(resources.energize_of(fields), (1, '263901', 331))
        self.assertIsNone(resources.energize_of(['POWER_ENERGIZE', 'GENERIC', '2', '25', '0', '9', '1']))
        self.assertIsNone(resources.energize_of(['DAMAGE', 'FIRE', '1', '25', '0', '9', '1']))


def _unit(unit_id, mag=20000, sta=26000, ult=500):
    return f"{unit_id},20000/20000,{mag}/20000,{sta}/26000,{ult}/500,1000/1000,0,0.2,0.5,5.5"


def _boss():
    return "70,1000000/1000000,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _ability(ability_id, name, icon):
    return f'2600,ABILITY_INFO,{ability_id},"{name}","/esoui/art/icons/{icon}.dds",F,T'


LOG = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1121,"Sunspire",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,4,9,"Pique","@brainsnorkel",1001,50,3230,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,2,9,"Mender","@healer",1002,50,3230,0,PLAYER_ALLY,T',
    '2500,UNIT_ADDED,70,MONSTER,F,0,1000000,T,0,0,"Lokkestiiz","",0,50,160,0,HOSTILE,F',
    _ability(HIT, "Damage Ability", "ability_weapon_001"),
    _ability(FORCE_PULSE, "Force Pulse", "ability_mageguild_003"),
    _ability(ICE_COMET, "Ice Comet", "ability_mageguild_006_a"),
    _ability(BOUNTIFUL_HARVEST, "Bountiful Harvest", "ability_set_001"),
    _ability(UNDAUNTED_STAMINA, "Undaunted Command Stamina Rest", "ability_set_002"),
    '10000,BEGIN_COMBAT',
    f"10001,PLAYER_INFO,1,[],[],[],[{FORCE_PULSE},{ICE_COMET}],[{FORCE_PULSE}]",
    f"10050,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,900,{HIT},{_unit(1)},{_boss()}",
    f"10200,BEGIN_CAST,0,F,3,{FORCE_PULSE},{_unit(1, mag=17300)},{_boss()}",
    # A fall with no cast: blocking, say
    f"10300,EFFECT_CHANGED,GAINED,1,4,{HIT},{_unit(1, mag=17300, sta=25000)},*",
    # Magicka from the healer, stamina from the player's own set
    (f"10400,COMBAT_EVENT,POWER_ENERGIZE,GENERIC,1,1000,0,950,{BOUNTIFUL_HARVEST},"
     f"{_unit(2)},{_unit(1, mag=18300, sta=25000)}"),
    (f"10500,COMBAT_EVENT,POWER_ENERGIZE,GENERIC,4,500,0,951,{UNDAUNTED_STAMINA},"
     f"{_unit(1, mag=18300, sta=25500)},*"),
    f"11000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,901,{HIT},{_unit(1, mag=19000, sta=25500)},{_boss()}",
    f"12000,BEGIN_CAST,0,F,5,{ICE_COMET},{_unit(1, sta=25500, ult=250)},{_boss()}",
    # At a full pool: wasted
    (f"13000,COMBAT_EVENT,POWER_ENERGIZE,GENERIC,1,800,0,952,{BOUNTIFUL_HARVEST},"
     f"{_unit(2)},{_unit(1, sta=25500, ult=250)}"),
    f"14000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,902,{HIT},{_unit(1, sta=25500, ult=250)},{_boss()}",
    f"69000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,903,{HIT},{_unit(1, sta=25500, ult=250)},{_boss()}",
    '70000,END_COMBAT',
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
        cls.player = next(p for p in cls.fight.players if p['unit_id'] == '1')

    def test_the_pools(self):
        magicka, stamina, ultimate = self.player['resources']['pools']
        self.assertEqual((magicka['spent'], magicka['on_casts'], magicka['gained'],
                          magicka['logged'], magicka['wasted']), (2700, 2700, 2700, 1000, 800))
        self.assertEqual((stamina['spent'], stamina['on_casts'], stamina['gained'],
                          stamina['logged']), (1000, 0, 500, 500))
        self.assertEqual((ultimate['spent'], ultimate['on_casts']), (250, 250))
        self.assertAlmostEqual(magicka['spent_ps'], 2700 / 60)

    def test_the_lists_name_the_skills_and_the_giver(self):
        data = self.player['resources']
        self.assertEqual([(r['name'], r['casts'], r['total']) for r in data['spent_on']],
                         [('Force Pulse', 1, 2700), ('Ice Comet', 1, 250)])
        self.assertEqual([(r['name'], r['givers'], r['total']) for r in data['gained_from']],
                         [('Bountiful Harvest', ['@healer'], 1000),
                          ('Undaunted Command Stamina Rest', [], 500)])

    def test_time_at_full_ultimate(self):
        # Full from the first state to the Ice Comet (1,950 ms), then not
        # (2,000 ms to the next state, 2,000 more at the cap)
        self.assertAlmostEqual(self.player['resources']['full_pct'], 100.0 * 1950 / 5950)


class TestRender(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fight = _fight()

    def test_the_section_closes_the_window_after_the_cap_sections(self):
        # Damage dealt, Penetration and Critical damage first, as one block
        # about what the player did; the tallest section last (issue #143)
        page = render_build_html(self.fight, '1')
        self.assertIn(RESOURCES_TITLE, page)
        dealt, resources = page.index(f"name='{DEALT_ANCHOR}'"), page.index(f"name='{RESOURCES_ANCHOR}'")
        self.assertLess(dealt, resources)
        if f"name='{PEN_CRIT_ANCHOR}'" in page:
            self.assertLess(dealt, page.index(f"name='{PEN_CRIT_ANCHOR}'"))
            self.assertLess(page.index(f"name='{PEN_CRIT_ANCHOR}'"), resources)
        self.assertIn('2,700', page)
        self.assertIn('45.0/s', page)
        self.assertIn('Ice Comet', page)
        self.assertIn('@healer', page)
        self.assertIn('32.8%', page)  # time at full ultimate

    def test_givers_show_once_and_at_most_three(self):
        fight = _fight()
        player = next(p for p in fight.players if p['unit_id'] == '1')
        player['resources']['gained_from'][0]['givers'] = ['@a', 'anon', '@b', 'anon', '@c', '@d']
        page = render_build_html(fight, '1')
        self.assertIn('@a, anon, @b +2', page)

    def test_hide_names_masks_the_giver(self):
        page = render_build_html(self.fight, '1', names=NameMask.for_entry(self.fight, True))
        self.assertNotIn('@healer', page)

    def test_an_entry_built_before_the_section(self):
        fight = _fight()
        for p in fight.players:
            p.pop('resources', None)
        self.assertIn('Resources were not recorded for this fight.', render_build_html(fight, '1'))


if __name__ == '__main__':
    unittest.main()
