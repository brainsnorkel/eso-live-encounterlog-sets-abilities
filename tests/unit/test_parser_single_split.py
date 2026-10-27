"""The structured parser splits each line once (issue #108): parse_line hands
its fields to the entry type's parse(), and the result must be the same as
parse() reading the line by itself."""

import threading
import unittest

import eso_log_structures as structures
from eso_log_structures import (
    BeginCastEntry,
    CombatEventEntry,
    EffectChangedEntry,
    ESOLogStructureParser,
    EventType,
    UnitStats,
)

# Real lines from a March of Sacrifices split
EFFECT_CHANGED = ('884,EFFECT_CHANGED,GAINED,1,11877109,220015,1,40231/40231,16370/16370,'
                  '18084/19121,500/500,1000/1000,0,0.2113,0.6907,5.6623,20,18678/18678,'
                  '13872/15007,25205/26564,182/500,1000/1000,0,0.2115,0.6907,5.6488')
COMBAT_EVENT = ('2968,COMBAT_EVENT,HOT_TICK_CRITICAL,GENERIC,4,0,1799,11878062,61506,1,'
                '40231/40231,16370/16370,16197/19121,500/500,1000/1000,0,0.2164,0.6848,'
                '5.5294,20,18678/18678,15007/15007,26564/26564,182/500,1000/1000,0,0.2120,'
                '0.6884,6.0994')
BEGIN_CAST_NO_TARGET = ('2935,BEGIN_CAST,0,F,11878062,61505,1,40231/40231,16370/16370,'
                        '16197/19121,500/500,1000/1000,0,0.2163,0.6849,5.5397,*')
BEGIN_CAST_TARGET = ('38673,BEGIN_CAST,0,F,11878231,16277,1,40231/40231,16370/16370,'
                     '16872/19121,500/500,1000/1000,0,0.3345,0.6715,5.7556,30,'
                     '136302/136704,0/0,0/0,0/0,0/0,0,0.3363,0.6688,5.5103')


class TestSingleSplit(unittest.TestCase):

    def setUp(self):
        self.parser = ESOLogStructureParser()

    def test_parse_line_matches_parse_alone(self):
        for cls, line in ((EffectChangedEntry, EFFECT_CHANGED),
                          (CombatEventEntry, COMBAT_EVENT),
                          (BeginCastEntry, BEGIN_CAST_NO_TARGET),
                          (BeginCastEntry, BEGIN_CAST_TARGET)):
            with self.subTest(line=line[:30]):
                via_parser = self.parser.parse_line(line)
                structures._last_split = (None, [])
                alone = cls.parse(line)
                self.assertIsInstance(via_parser, cls)
                self.assertEqual(via_parser, alone)

    def test_begin_cast_target_stats(self):
        self.assertIsNone(BeginCastEntry.parse(BEGIN_CAST_NO_TARGET).target_stats)
        target = BeginCastEntry.parse(BEGIN_CAST_TARGET).target_stats
        self.assertEqual((target.current_health, target.max_health), (136302, 136704))

    def test_another_lines_split_is_not_reused(self):
        # A split left by another line (another thread's, say) is ignored
        self.parser.parse_line(COMBAT_EVENT)
        entry = EffectChangedEntry.parse(EFFECT_CHANGED)
        self.assertEqual(entry.effect_id, 220015)

    def test_parsers_on_two_threads(self):
        results, errors = [], []

        # A thread that raises appends no result, which the length check sees
        def run(line, expected_type):
            for _ in range(2000):
                entry = self.parser.parse_line(line)
                if not isinstance(entry, expected_type):
                    errors.append(type(entry).__name__)
            results.append(entry)

        threads = [threading.Thread(target=run, args=(EFFECT_CHANGED, EffectChangedEntry)),
                   threading.Thread(target=run, args=(COMBAT_EVENT, CombatEventEntry))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)

    def test_unknown_event_type(self):
        self.assertIsNone(self.parser.parse_line('100,NOT_AN_EVENT,1,2'))
        self.assertIsNone(self.parser.get_event_type('100,NOT_AN_EVENT,1,2'))
        self.assertEqual(self.parser.get_event_type(COMBAT_EVENT), EventType.COMBAT_EVENT)

    def test_unit_stats_fields_match_string(self):
        fields = EFFECT_CHANGED.split(',')[7:16]
        self.assertEqual(UnitStats.from_fields(fields), UnitStats.from_string(','.join(fields)))
        self.assertEqual(UnitStats.from_fields(fields[:4]).max_health, 0)


if __name__ == '__main__':
    unittest.main()
