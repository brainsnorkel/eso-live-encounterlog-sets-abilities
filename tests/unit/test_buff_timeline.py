#!/usr/bin/env python3
"""Unit tests for the experimental buff/debuff timeline (buff-timeline spec)."""

import unittest

from buff_timeline import (
    MERGE_GAP_MS, TRACKED_TIMELINE_EFFECTS, BuffTimelineRecorder,
    extract_effect_fields,
)


def _names(unit_id):
    return {'1': '@caster', '2': '@receiver', '70': 'Test Boss'}.get(
        unit_id, f'unit {unit_id}')


class TestRecorder(unittest.TestCase):

    def setUp(self):
        self.rec = BuffTimelineRecorder()

    def test_gained_faded_interval_with_attribution(self):
        """Spec scenario: buff gained and faded."""
        self.rec.record('GAINED', '61747', '1', '2', 10_000)  # Major Force
        self.rec.record('FADED', '61747', '1', '2', 20_000)
        snap = self.rec.snapshot_fight(0, 60_000, _names)
        force = snap['effects']['Major Force']
        self.assertEqual(force, [{'start_ms': 10_000, 'end_ms': 20_000,
                                  'source': '@caster', 'target': '@receiver'}])
        self.assertEqual(snap['duration_ms'], 60_000)

    def test_active_at_fight_end_is_closed(self):
        """Spec scenario: buff active at fight end."""
        self.rec.record('GAINED', '109966', '1', '2', 30_000)  # Major Courage
        snap = self.rec.snapshot_fight(0, 60_000, _names)
        courage = snap['effects']['Major Courage']
        self.assertEqual(courage[0]['end_ms'], 60_000)

    def test_intervals_clipped_to_fight_window(self):
        # Gained pre-combat, faded mid-fight
        self.rec.record('GAINED', '93109', '1', '2', 5_000)   # Major Slayer
        self.rec.record('FADED', '93109', '1', '2', 25_000)
        snap = self.rec.snapshot_fight(10_000, 70_000, _names)
        slayer = snap['effects']['Major Slayer']
        self.assertEqual((slayer[0]['start_ms'], slayer[0]['end_ms']),
                         (0, 15_000))

    def test_untracked_ability_ignored(self):
        self.rec.record('GAINED', '99999', '1', '2', 1_000)
        self.rec.record('FADED', '99999', '1', '2', 2_000)
        self.assertIsNone(self.rec.snapshot_fight(0, 10_000, _names))

    def test_updated_opens_when_attached_mid_effect(self):
        self.rec.record('UPDATED', '61747', '1', '2', 15_000)
        self.rec.record('FADED', '61747', '1', '2', 25_000)
        snap = self.rec.snapshot_fight(0, 60_000, _names)
        self.assertEqual(snap['effects']['Major Force'][0]['start_ms'], 15_000)

    def test_gap_merge(self):
        """Sub-500ms FADED/GAINED flickers merge into one interval."""
        self.rec.record('GAINED', '61747', '1', '2', 10_000)
        self.rec.record('FADED', '61747', '1', '2', 20_000)
        self.rec.record('GAINED', '61747', '1', '2', 20_000 + MERGE_GAP_MS - 1)
        self.rec.record('FADED', '61747', '1', '2', 30_000)
        snap = self.rec.snapshot_fight(0, 60_000, _names)
        force = snap['effects']['Major Force']
        self.assertEqual(len(force), 1)
        self.assertEqual((force[0]['start_ms'], force[0]['end_ms']),
                         (10_000, 30_000))

    def test_gap_beyond_merge_stays_separate(self):
        self.rec.record('GAINED', '61747', '1', '2', 10_000)
        self.rec.record('FADED', '61747', '1', '2', 20_000)
        self.rec.record('GAINED', '61747', '1', '2', 21_000)
        self.rec.record('FADED', '61747', '1', '2', 30_000)
        snap = self.rec.snapshot_fight(0, 60_000, _names)
        self.assertEqual(len(snap['effects']['Major Force']), 2)

    def test_powerful_assault_tracked(self):
        self.rec.record('GAINED', '61771', '1', '2', 10_000)
        self.rec.record('FADED', '61771', '1', '2', 20_000)
        snap = self.rec.snapshot_fight(0, 60_000, _names)
        self.assertIn('Powerful Assault', snap['effects'])

    def test_multiple_ability_ids_map_to_one_effect(self):
        for ability_id in ('106754', '122389', '167061'):
            self.rec.record('GAINED', ability_id, '1', '70', 10_000)
            self.rec.record('FADED', ability_id, '1', '70', 11_000)
        snap = self.rec.snapshot_fight(0, 60_000, _names)
        vuln = snap['effects']['Major Vulnerability']
        # Same (source, target) back-to-back at identical times merges
        self.assertTrue(all(i['target'] == 'Test Boss' for i in vuln))

    def test_overlapping_receivers_kept_separate(self):
        self.rec.record('GAINED', '93109', '1', '2', 10_000)
        self.rec.record('GAINED', '93109', '1', '3', 10_000)
        self.rec.record('FADED', '93109', '1', '2', 20_000)
        self.rec.record('FADED', '93109', '1', '3', 22_000)
        snap = self.rec.snapshot_fight(0, 60_000, _names)
        self.assertEqual(len(snap['effects']['Major Slayer']), 2)

    def test_reset_clears_everything(self):
        self.rec.record('GAINED', '61747', '1', '2', 10_000)
        self.rec.reset()
        self.assertIsNone(self.rec.snapshot_fight(0, 60_000, _names))

    def test_prune_before_frees_old_intervals(self):
        self.rec.record('GAINED', '61747', '1', '2', 10_000)
        self.rec.record('FADED', '61747', '1', '2', 20_000)
        self.rec.prune_before(25_000)
        self.assertIsNone(self.rec.snapshot_fight(0, 60_000, _names))

    def test_interval_cap(self):
        from buff_timeline import MAX_INTERVALS_PER_EFFECT
        for i in range(MAX_INTERVALS_PER_EFFECT + 50):
            base = i * 10_000
            # Alternate source so the gap-merge never applies
            self.rec.record('GAINED', '61747', str(i % 7), '2', base)
            self.rec.record('FADED', '61747', str(i % 7), '2', base + 5_000)
        self.assertLessEqual(len(self.rec._closed['Major Force']),
                             MAX_INTERVALS_PER_EFFECT)

    def test_no_data_returns_none(self):
        self.assertIsNone(self.rec.snapshot_fight(0, 60_000, _names))
        self.assertIsNone(self.rec.snapshot_fight(60_000, 60_000, _names))


class TestExtractEffectFields(unittest.TestCase):

    def test_self_target_star(self):
        fields = ['GAINED', '1', '4021667', '84734', '1',
                  '22762/22762', '26657/26657', '13021/13021', '500/500',
                  '1000/1000', '0', '0.2696', '0.5942', '5.5492', '*']
        self.assertEqual(extract_effect_fields(fields),
                         ('GAINED', '84734', '1', '1'))

    def test_explicit_target(self):
        fields = ['GAINED', '1', '1857418', '28012', '6',
                  '32417/32417', '0/0', '0/0', '0/0', '0/0', '0',
                  '0.3851', '0.7801', '2.6373',
                  '16', '52831/52831', '0/0', '0/0', '0/0', '0/0', '0',
                  '0.3705', '0.8056', '6.0084']
        self.assertEqual(extract_effect_fields(fields),
                         ('GAINED', '28012', '6', '16'))

    def test_short_fields_rejected(self):
        self.assertIsNone(extract_effect_fields(['GAINED', '1', '2']))


class TestAnalyzerIntegration(unittest.TestCase):
    """Timeline capture through the real analyzer pipeline."""

    EPOCH = 1755729685851

    def _run_fight(self, track: bool):
        from esolog_tail import ESOLogAnalyzer, FightHistory
        analyzer = ESOLogAnalyzer()
        analyzer.track_buff_timeline = track
        analyzer.fight_history = FightHistory()
        # Major Force (61747) from unit 1 onto unit 2; Major Vulnerability
        # (106754) from unit 1 onto boss 70, still active at END_COMBAT.
        lines = [
            f'5,BEGIN_LOG,{self.EPOCH},15,"NA Megaserver","en","eso.live.11.1"',
            '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
            '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
            '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1708524619155578000,50,787,0,PLAYER_ALLY,T',
            '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
            '10000,BEGIN_COMBAT',
            '11000,COMBAT_EVENT,DAMAGE,PHYSICAL,1,90000,0,4021667,12345,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,70,105634/105634,0/0,0/0,0/0,0/0,0,0.4081,0.5662,0.0256',
            '15000,EFFECT_CHANGED,GAINED,1,111,61747,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,2,20000/20000,30000/30000,12000/12000,500/500,1000/1000,0,0.3,0.5,1.0',
            '20000,EFFECT_CHANGED,GAINED,1,112,106754,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,70,105634/105634,0/0,0/0,0/0,0/0,0,0.4,0.5,0.0',
            '25000,EFFECT_CHANGED,FADED,1,111,61747,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,2,20000/20000,30000/30000,12000/12000,500/500,1000/1000,0,0.3,0.5,1.0',
            '70000,END_COMBAT',
        ]
        for line in lines:
            entry = analyzer.log_parser.parse_line(line)
            if entry is not None:
                analyzer.process_log_entry(entry)
        return analyzer.fight_history.fights

    def test_enabled_captures_timeline_with_names(self):
        fights = self._run_fight(track=True)
        self.assertEqual(len(fights), 1)
        timeline = fights[0].buff_timeline
        self.assertIsNotNone(timeline)
        self.assertEqual(timeline['duration_ms'], 60_000)

        force = timeline['effects']['Major Force']
        self.assertEqual(force, [{'start_ms': 5_000, 'end_ms': 15_000,
                                  'source': '@brainsnorkel',
                                  'target': '@templar'}])

        vuln = timeline['effects']['Major Vulnerability']
        self.assertEqual(vuln[0]['target'], 'Test Boss')
        self.assertEqual(vuln[0]['end_ms'], 60_000)  # closed at fight end

    def test_disabled_retains_nothing(self):
        """Spec scenario: toggle off."""
        fights = self._run_fight(track=False)
        self.assertEqual(len(fights), 1)
        self.assertIsNone(fights[0].buff_timeline)


if __name__ == '__main__':
    unittest.main()
