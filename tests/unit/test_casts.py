"""
Cast counts and casts per minute (casts.py, issue #94): the recorder, the
slot matching, the summary, the engine's fight entry and the two renderers.
"""

import unittest
from collections import Counter

import casts
from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory
from gui.build_render import render_build_html
from gui.fight_render import render_html, render_plain_text

EPOCH = 1759600000000
HIT = '12345'
FORCE_PULSE, BLUE_BETTY = '46356', '86054'
ELEMENTAL_BLOCKADE, BLOCKADE_OF_FROST = '39011', '39028'
VENOM_SKULL, VENOM_SKULL_CAST = '117624', '123704'
LIGHT_LIGHTNING, HEAVY_LIGHTNING = '18350', '18396'
SWAP, DODGE, BASH, BREAK_FREE = '28541', '28549', '21970', '16565'
CONDUIT, RESTORE_HEALTH, RECALL = '23196', '45221', '6811'
FATECARVER, FATECARVER_CHANNEL, FATECARVER_SHIELD = '186366', '189533', '201265'


class _AllIcons:
    """Stand-in for the fight view's IconCache that has every icon."""

    def has(self, stem):
        return bool(stem)


class TestRecorder(unittest.TestCase):

    def test_one_cast_per_cast_track_id(self):
        recorder = casts.CastRecorder()
        # A channelled heavy attack writes two lines under one track id
        recorder.note_cast('1', '900', HEAVY_LIGHTNING, 1000)
        recorder.note_cast('1', '900', HEAVY_LIGHTNING, 1015)
        recorder.note_cast('1', '901', FORCE_PULSE, 2000)
        self.assertEqual(recorder.fight_counts('1', 0, 5000),
                         Counter({HEAVY_LIGHTNING: 1, FORCE_PULSE: 1}))

    def test_only_the_fight_window_counts(self):
        recorder = casts.CastRecorder()
        recorder.note_cast('1', '1', FORCE_PULSE, 900)    # a pre-buff
        recorder.note_cast('1', '2', FORCE_PULSE, 1000)
        recorder.note_cast('1', '3', FORCE_PULSE, 3000)
        recorder.note_cast('1', '4', FORCE_PULSE, 3001)   # after the end
        self.assertEqual(recorder.fight_counts('1', 1000, 3000)[FORCE_PULSE], 2)
        self.assertEqual(recorder.fight_counts('2', 1000, 3000), Counter())

    def test_fight_times_of_chosen_casts(self):
        recorder = casts.CastRecorder()
        recorder.note_cast('c1-106616', '1', '163763', 900)    # before the fight
        recorder.note_cast('c1-106616', '2', '163763', 1500)
        recorder.note_cast('c1-106616', '3', FORCE_PULSE, 1600)
        recorder.note_cast('c1-106616', '4', '163763', 2500)
        self.assertEqual(recorder.fight_times('c1-106616', 1000, 3000, {'163763'}),
                         [(1500, '163763'), (2500, '163763')])

    def test_a_companions_kinds(self):
        counts = Counter({'157069': 3, '154302': 1, '156219': 2, '157039': 1, '156633': 1,
                          '157419': 1, '163684': 4})
        summary = casts.cast_summary(counts, 60.0, kinds=casts.COMPANION_EXTRA_KINDS)
        self.assertEqual(summary, {'total': 13, 'cpm': 13.0, 'light': 4, 'bash': 1,
                                   'block': 2, 'dodge': 1, 'break_free': 1})
        # No companion id is one of a player's kinds
        player_ids = set().union(*(ids for _kind, ids in casts.EXTRA_KINDS))
        companion_ids = set().union(*(ids for _kind, ids in casts.COMPANION_EXTRA_KINDS))
        self.assertFalse(player_ids & companion_ids)

    def test_prune_and_reset(self):
        recorder = casts.CastRecorder()
        recorder.note_cast('1', '1', FORCE_PULSE, 900)
        recorder.note_cast('1', '2', FORCE_PULSE, 2000)
        recorder.prune_before(1000)
        self.assertEqual(recorder.fight_counts('1', 0, 9999)[FORCE_PULSE], 1)
        recorder.reset()
        self.assertEqual(recorder.fight_counts('1', 0, 9999), Counter())


class TestSlots(unittest.TestCase):

    def test_same_skill(self):
        self.assertTrue(casts.same_skill(FORCE_PULSE, 'Force Pulse', FORCE_PULSE, 'Force Pulse'))
        # Slotted under one id, cast under another of the same name
        self.assertTrue(casts.same_skill(VENOM_SKULL, 'Venom Skull', VENOM_SKULL_CAST, 'Venom Skull'))
        # A Destruction Staff skill casts the staff's element
        self.assertTrue(casts.same_skill(ELEMENTAL_BLOCKADE, 'Elemental Blockade',
                                         BLOCKADE_OF_FROST, 'Blockade of Frost'))
        self.assertTrue(casts.same_skill('39018', 'Blockade of Storms',
                                         BLOCKADE_OF_FROST, 'Blockade of Frost'))
        self.assertFalse(casts.same_skill(FORCE_PULSE, 'Force Pulse', BLUE_BETTY, 'Blue Betty'))
        # Fatecarver's channel, noted as the morph, under either slot id
        self.assertTrue(casts.same_skill('193398', 'Pragmatic Fatecarver', '186366', ''))
        # A werewolf morph's form effect is cast under the ultimate's name
        self.assertFalse(casts.same_skill('39076', 'Werewolf Berserker', '47083',
                                          'Werewolf Berserker'))

    def test_mark_slot_casts(self):
        names = {FORCE_PULSE: 'Force Pulse', BLOCKADE_OF_FROST: 'Blockade of Frost',
                 ELEMENTAL_BLOCKADE: 'Elemental Blockade', BLUE_BETTY: 'Blue Betty',
                 '267416': 'Rampage', '39076': 'Werewolf Berserker'}
        front = [{'id': FORCE_PULSE, 'name': 'Force Pulse'},
                 {'id': ELEMENTAL_BLOCKADE, 'name': 'Elemental Blockade'}]
        back = [{'id': FORCE_PULSE, 'name': 'Force Pulse'},
                {'id': '39076', 'name': 'Werewolf Berserker', 'stand_in': 'Rampage'}]
        counts = Counter({FORCE_PULSE: 37, BLOCKADE_OF_FROST: 7, BLUE_BETTY: 3, '267416': 2})
        casts.mark_slot_casts(counts, (front, back, None), names.get)
        # A skill on both bars shows its total under each
        self.assertEqual([slot['casts'] for slot in front], [37, 7])
        self.assertEqual([slot['casts'] for slot in back], [37, 2])


class TestSummary(unittest.TestCase):

    def test_every_cast_over_the_fight(self):
        counts = Counter({FORCE_PULSE: 37, LIGHT_LIGHTNING: 52, HEAVY_LIGHTNING: 2, SWAP: 14,
                          DODGE: 1, BASH: 3, CONDUIT: 2, RESTORE_HEALTH: 1, BREAK_FREE: 1,
                          RECALL: 1})
        summary = casts.cast_summary(counts, 120.0)
        self.assertEqual(summary['total'], 114)
        self.assertAlmostEqual(summary['cpm'], 57.0)
        self.assertEqual((summary['light'], summary['heavy'], summary['swap'], summary['dodge'],
                          summary['bash'], summary['synergy'], summary['potion'],
                          summary['break_free']), (52, 2, 14, 1, 3, 2, 1, 1))

    def test_a_player_who_left_over_the_time_they_were_there(self):
        summary = casts.cast_summary(Counter({FORCE_PULSE: 30}), 120.0, present_pct=50.0)
        self.assertAlmostEqual(summary['cpm'], 30.0)
        self.assertEqual(casts.cast_summary(Counter(), 0.0)['cpm'], 0.0)

    def test_werewolf_attacks_are_light_and_heavy_attacks(self):
        self.assertEqual(casts.kind_of('32464'), 'light')
        self.assertEqual(casts.kind_of('32477'), 'heavy')
        self.assertIsNone(casts.kind_of(FORCE_PULSE))


def _unit(unit_id):
    return f"{unit_id},20000/20000,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _boss():
    return "70,1000000/1000000,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _cast(ts, unit, ability, track):
    return f"{ts},BEGIN_CAST,0,F,{track},{ability},{_unit(unit)},{_boss()}"


def _hit(ts, unit):
    return f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,900,{HIT},{_unit(unit)},{_boss()}"


def _effect(ts, unit, ability, track):
    return f"{ts},EFFECT_CHANGED,GAINED,1,{track},{ability},{_unit(unit)},*"


def _ability(ability_id, name, icon):
    return f'2600,ABILITY_INFO,{ability_id},"{name}","/esoui/art/icons/{icon}.dds",F,T'


LOG = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1121,"Sunspire",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,4,9,"Pique","@brainsnorkel",1001,50,3230,0,PLAYER_ALLY,T',
    '2500,UNIT_ADDED,70,MONSTER,F,0,1000000,T,0,0,"Lokkestiiz","",0,50,160,0,HOSTILE,F',
    _ability(HIT, "Damage Ability", "ability_weapon_001"),
    _ability(FORCE_PULSE, "Force Pulse", "ability_mageguild_003"),
    _ability(ELEMENTAL_BLOCKADE, "Elemental Blockade", "ability_destructionstaff_004"),
    _ability(BLOCKADE_OF_FROST, "Blockade of Frost", "ability_destructionstaff_002b"),
    _ability(LIGHT_LIGHTNING, "Light Attack (Lightning)", "death_recap_shock_ranged"),
    _ability(HEAVY_LIGHTNING, "Heavy Attack (Lightning)", "death_recap_shock_ranged"),
    _ability(SWAP, "Swap Weapons", "ability_warrior_003"),
    _ability(CONDUIT, "Conduit", "ability_sorcerer_lightning_splash"),
    _ability(FATECARVER, "Pragmatic Fatecarver", "ability_arcanist_002_b"),
    _cast(9000, 1, BLOCKADE_OF_FROST, 1),   # a pre-buff, before the pull
    '10000,BEGIN_COMBAT',
    f"10001,PLAYER_INFO,1,[],[],[],[{FORCE_PULSE},{FATECARVER}],[{ELEMENTAL_BLOCKADE},{FORCE_PULSE}]",
    _cast(10100, 1, LIGHT_LIGHTNING, 2),
    _cast(10200, 1, FORCE_PULSE, 3),
    _cast(11000, 1, HEAVY_LIGHTNING, 4),
    _cast(11015, 1, HEAVY_LIGHTNING, 4),    # the channel, same track
    _cast(12000, 1, SWAP, 5),
    _cast(12100, 1, BLOCKADE_OF_FROST, 6),
    _cast(13000, 1, CONDUIT, 7),
    # Fatecarver writes no BEGIN_CAST: its channel effects, one track
    _effect(13500, 1, FATECARVER_CHANNEL, 8),
    _effect(13500, 1, '186369', 8),
    _effect(15000, 1, FATECARVER_SHIELD, 9),   # the shield alone: no cast
    _hit(14000, 1),
    _hit(69000, 1),
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
        cls.player = cls.fight.players[0]

    def test_the_fight_entry_carries_the_counts(self):
        summary = self.player['casts']
        # Light, Force Pulse, heavy (once), swap, Blockade, Conduit, Fatecarver;
        # not the pre-buff
        self.assertEqual(summary['total'], 7)
        self.assertAlmostEqual(summary['cpm'], 7.0)
        self.assertEqual((summary['light'], summary['heavy'], summary['swap'],
                          summary['synergy']), (1, 1, 1, 1))

    def test_each_slot_carries_its_casts(self):
        self.assertEqual([slot['casts'] for slot in self.player['front_bar_slots']], [1, 1])
        self.assertEqual([slot['casts'] for slot in self.player['back_bar_slots']], [1, 1])


class TestRender(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fight = _fight()

    def test_the_build_window_has_counts_and_the_other_row(self):
        page = render_build_html(self.fight, '1', icons=_AllIcons())
        self.assertIn('>Other</td>', page)
        self.assertIn('Light attacks 1 · Heavy attacks 1 · Bashes 0 · Swaps 1 · Dodges 0 · '
                      'Synergies 1 · Potions 0 · Break Free 0 · 7 casts, 7 per minute', page)
        self.assertIn("<td align='center' valign='bottom'>", page)

    def test_the_fight_pane_and_the_copy_show_cpm(self):
        self.assertIn('CPM 7', render_html(self.fight, detailed=True))
        self.assertIn(' · CPM 7', render_plain_text(self.fight))

    def test_an_entry_built_before_the_counts(self):
        fight = _fight()
        player = fight.players[0]
        del player['casts']
        for slot in player['front_bar_slots'] + player['back_bar_slots']:
            del slot['casts']
        self.assertNotIn('CPM', render_html(fight, detailed=True))
        page = render_build_html(fight, '1', icons=_AllIcons())
        self.assertNotIn('>Other</td>', page)
        self.assertNotIn("valign='bottom'", page)


if __name__ == '__main__':
    unittest.main()
