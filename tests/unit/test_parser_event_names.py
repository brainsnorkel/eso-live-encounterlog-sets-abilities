"""Every entry reaches the engine under its line's own event name (issue
#225). Until then END_LOG, EFFECT_INFO and ENDLESS_DUNGEON_END came out as
ENDLOG, EFFECTINFO and ENDLESSDUNGEONEND (eso_log_parser._legacy_kind's
fallback), so no handler of theirs had ever run."""

import unittest

from eso_log_parser import ESOLogParser
from eso_log_structures import ESOLogStructureParser, EventType

# One line of each event type, in the shapes the game writes (names made up)
STATE = "1,18319/18319,10264/14719,26053/26053,0/500,1000/1000,0,0.3725,0.4157,1.6223"
LINES = {
    EventType.BEGIN_LOG: '5,BEGIN_LOG,1772528468599,15,"NA Megaserver","en","eso.live.11.2"',
    EventType.END_LOG: '5131274,END_LOG',
    EventType.ZONE_CHANGED: '5,ZONE_CHANGED,1436,"Infinite Archive",NORMAL',
    EventType.UNIT_ADDED: ('5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,4,"Some Player","@someone",'
                           '6442618951927617798,50,3145,0,PLAYER_ALLY,T'),
    EventType.UNIT_CHANGED: ('165508,UNIT_CHANGED,120,0,0,"Guardian of Pestilence","",0,50,'
                             '160,0,HOSTILE,F'),
    EventType.UNIT_REMOVED: '67643,UNIT_REMOVED,7',
    EventType.ABILITY_INFO: ('207,ABILITY_INFO,218930,"Dark Anchor Summons",'
                             '"/esoui/art/icons/ability_mage_065.dds",T,T'),
    EventType.MAP_CHANGED: ('208,MAP_CHANGED,2407,"Infinite Archive",'
                            '"apocrypha/u40_tomeHold_StarterArea"'),
    EventType.BEGIN_CAST: f'2179,BEGIN_CAST,0,F,16822125,185842,{STATE},*',
    EventType.END_CAST: '207,END_CAST,COMPLETED,16822124,218930',
    EventType.EFFECT_INFO: '2179,EFFECT_INFO,185842,BUFF,NONE,DEFAULT',
    EventType.EFFECT_CHANGED: f'2179,EFFECT_CHANGED,GAINED,1,16822125,185842,{STATE},*',
    EventType.COMBAT_EVENT: f'208,COMBAT_EVENT,FAILED,GENERIC,0,0,0,16822124,218930,{STATE},*',
    EventType.HEALTH_REGEN: ('42380,HEALTH_REGEN,1328,22,20006/21896,15007/15007,'
                             '26564/29534,500/500,1000/1000,0,0.4020,0.4451,3.9686'),
    EventType.BEGIN_COMBAT: '81558,BEGIN_COMBAT',
    EventType.END_COMBAT: '87254,END_COMBAT',
    EventType.PLAYER_INFO: '81560,PLAYER_INFO,1,[142210,142079],[1,1],[],[],[]',
    EventType.TRIAL_INIT: '272071,TRIAL_INIT,18,F,F,0,0,F,0',
    EventType.BEGIN_TRIAL: '421149,BEGIN_TRIAL,18,1795162517125',
    EventType.END_TRIAL: '4331938,END_TRIAL,18,3910687,T,64030,0',
    EventType.ENDLESS_DUNGEON_BEGIN: '63608,ENDLESS_DUNGEON_BEGIN,1,1772528532625,F',
    EventType.ENDLESS_DUNGEON_STAGE_END: '111866,ENDLESS_DUNGEON_STAGE_END,1,1772528532625',
    EventType.ENDLESS_DUNGEON_BUFF_ADDED: '125205,ENDLESS_DUNGEON_BUFF_ADDED,1,193597',
    EventType.ENDLESS_DUNGEON_BUFF_REMOVED: '165508,ENDLESS_DUNGEON_BUFF_REMOVED,1,193597',
    EventType.ENDLESS_DUNGEON_END: '4989677,ENDLESS_DUNGEON_END,1,4926000,132000,F',
}


class TestEventNames(unittest.TestCase):

    def test_end_log_comes_out_as_end_log(self):
        entry = ESOLogParser().parse_line('95000,END_LOG')
        self.assertEqual((entry.event_type, entry.timestamp), ('END_LOG', 95000))

    def test_every_entry_class_keeps_its_event_name(self):
        # A parser added to the table needs a line here
        self.assertEqual(set(LINES), set(ESOLogStructureParser.PARSERS))
        structured = ESOLogStructureParser()
        parser = ESOLogParser()
        for event, line in LINES.items():
            with self.subTest(event=event.value):
                # The line is one its own class reads...
                parsed = structured.parse_line(line)
                self.assertIsInstance(parsed, ESOLogStructureParser.PARSERS[event].__self__)
                # ...and the engine is handed the line's own event name
                entry = parser.parse_line(line)
                self.assertEqual(entry.event_type, line.split(',')[1])


if __name__ == '__main__':
    unittest.main()
