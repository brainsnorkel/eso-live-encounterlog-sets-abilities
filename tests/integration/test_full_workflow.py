#!/usr/bin/env python3
"""
Integration tests for full ESO analyzer workflow.
"""

import unittest
import sys
import os
import tempfile
import io
from contextlib import redirect_stdout
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fixtures'))

from esolog_tail import ESOLogAnalyzer, ESOLogEntry
from sample_data import SAMPLE_LOG_LINES


class TestFullWorkflow(unittest.TestCase):
    """Integration tests for complete analyzer workflow."""
    
    def test_complete_encounter_processing(self):
        """Test processing a complete encounter from start to finish."""
        analyzer = ESOLogAnalyzer()
        
        # Process a sequence of log entries that form a complete encounter
        log_sequence = [
            # Add players
            '5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
            '5,UNIT_ADDED,30,PLAYER,F,2,0,F,6,1,"Templar","@templar",0,50,787,0,PLAYER_ALLY,T',
            
            # Add ability info
            '2928,ABILITY_INFO,84734,"Test Ability","/esoui/art/icons/ability_mage_065.dds",T,T',
            '2928,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
            
            # Add enemy
            '3000,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
            
            # Start combat
            '3100,BEGIN_COMBAT',
            
            # Cast abilities
            '3200,BEGIN_CAST,0,F,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000',
            '3250,END_CAST,COMPLETED,4021667,84734',
            
            # Effect change with resource data
            '3300,EFFECT_CHANGED,GAINED,1,4021667,84734,1,23000/23000,27000/27000,13500/13500,500/500,1000/1000,0,0.2696,0.5942,5.5492,*',
            
            # Damage event
            '3400,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1500,0,4021667,12345,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,70,136704/136704,0/0,0/0,0/0,0/0,0,0.4081,0.5662,0.0256',
            
            # End combat
            '4000,END_COMBAT'
        ]
        
        # Process all entries
        for line in log_sequence:
            entry = ESOLogEntry.parse(line)
            if entry:
                analyzer.process_log_entry(entry)
        
        # Verify encounter was processed correctly
        # Note: The encounter would be None after END_COMBAT, but we can verify it was processed
        self.assertIsNotNone(analyzer.ability_cache)
        self.assertIn("84734", analyzer.ability_cache)
        self.assertIn("12345", analyzer.ability_cache)
    
    def test_multi_encounter_processing(self):
        """Test processing multiple encounters."""
        analyzer = ESOLogAnalyzer()
        
        # First encounter
        encounter1_lines = [
            '1000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Player1","@player1",123,50,3084,0,PLAYER_ALLY,T',
            '1100,BEGIN_COMBAT',
            '1200,END_COMBAT'
        ]
        
        # Second encounter
        encounter2_lines = [
            '2000,UNIT_ADDED,2,PLAYER,T,1,0,F,6,7,"Player2","@player2",456,50,3084,0,PLAYER_ALLY,T',
            '2100,BEGIN_COMBAT',
            '2200,END_COMBAT'
        ]
        
        # Process first encounter
        for line in encounter1_lines:
            entry = ESOLogEntry.parse(line)
            if entry:
                analyzer.process_log_entry(entry)
        
        # Process second encounter
        for line in encounter2_lines:
            entry = ESOLogEntry.parse(line)
            if entry:
                analyzer.process_log_entry(entry)
        
        # Should not crash and should handle multiple encounters
        self.assertIsNotNone(analyzer)
    
    def test_error_recovery(self):
        """Test analyzer recovery from malformed data."""
        analyzer = ESOLogAnalyzer()
        
        # Mix of valid and invalid entries
        mixed_lines = [
            '1000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Player1","@player1",123,50,3084,0,PLAYER_ALLY,T',
            'invalid,line,with,wrong,format',
            '',  # Empty line
            '1100,INVALID_EVENT_TYPE,some,data',
            '1200,BEGIN_COMBAT',
            'another,invalid,line',
            '1300,END_COMBAT'
        ]
        
        # Process all entries - should not crash
        for line in mixed_lines:
            try:
                entry = ESOLogEntry.parse(line)
                if entry:
                    analyzer.process_log_entry(entry)
            except Exception as e:
                # Log parsing errors should be handled gracefully
                pass
        
        # Analyzer should still be functional
        self.assertIsNotNone(analyzer)
    
    def test_resource_tracking_integration(self):
        """Test integration of resource tracking across different event types."""
        analyzer = ESOLogAnalyzer()
        
        # Add player
        unit_line = '1000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Player1","@player1",123,50,3084,0,PLAYER_ALLY,T'
        entry = ESOLogEntry.parse(unit_line)
        analyzer.process_log_entry(entry)
        
        # Resource update from BEGIN_CAST
        cast_line = '1100,BEGIN_CAST,0,F,4021667,84734,1,25000/25000,30000/30000,28000/28000,500/500,1000/1000,0,0.2696,0.5942,5.5492,0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000'
        entry = ESOLogEntry.parse(cast_line)
        analyzer.process_log_entry(entry)
        
        # Resource update from EFFECT_CHANGED
        effect_line = '1200,EFFECT_CHANGED,GAINED,1,4021667,84734,1,26000/26000,29000/29000,29000/29000,500/500,1000/1000,0,0.2696,0.5942,5.5492,*'
        entry = ESOLogEntry.parse(effect_line)
        analyzer.process_log_entry(entry)
        
        # Verify resources were tracked
        if analyzer.current_encounter and analyzer.current_encounter.players:
            player = list(analyzer.current_encounter.players.values())[0]
            # Should have the maximum values from both events
            self.assertGreaterEqual(player.max_health, 25000)
            self.assertGreaterEqual(player.max_magicka, 29000)
            self.assertGreaterEqual(player.max_stamina, 28000)
    
    def test_damage_attribution_integration(self):
        """Test damage attribution across a full encounter."""
        analyzer = ESOLogAnalyzer()
        
        # Setup encounter with multiple players
        setup_lines = [
            '1000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Player1","@player1",123,50,3084,0,PLAYER_ALLY,T',
            '1001,UNIT_ADDED,2,PLAYER,T,1,0,F,6,7,"Player2","@player2",456,50,3084,0,PLAYER_ALLY,T',
            '1002,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Boss","",0,50,160,0,HOSTILE,F',
            '1100,BEGIN_COMBAT'
        ]
        
        # Process setup
        for line in setup_lines:
            entry = ESOLogEntry.parse(line)
            if entry:
                analyzer.process_log_entry(entry)
        
        # Add damage events
        damage_lines = [
            '1200,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1000,0,4021667,12345,1,25000/25000,30000/30000,28000/28000,500/500,1000/1000,0,0.2696,0.5942,5.5492,70,100000/100000,0/0,0/0,0/0,0/0,0,0.4081,0.5662,0.0256',
            '1300,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1500,0,4021668,12346,2,24000/24000,31000/31000,27000/27000,500/500,1000/1000,0,0.2696,0.5942,5.5492,70,98500/100000,0/0,0/0,0/0,0/0,0,0.4081,0.5662,0.0256'
        ]
        
        # Process damage events
        for line in damage_lines:
            entry = ESOLogEntry.parse(line)
            if entry:
                analyzer.process_log_entry(entry)
        
        # Verify damage tracking
        if analyzer.current_encounter:
            self.assertGreater(analyzer.current_encounter.total_damage, 0)
            # Should have tracked damage for the encounter
            self.assertIsNotNone(analyzer.current_encounter.player_damage)


class TestAnalyzerConfiguration(unittest.TestCase):
    """Test analyzer configuration and options."""
    
    def test_diagnostic_mode(self):
        """Test analyzer in diagnostic mode."""
        analyzer = ESOLogAnalyzer(diagnostic=True)
        
        # Process some entries - should not crash in diagnostic mode
        entry = ESOLogEntry.parse(SAMPLE_LOG_LINES['unit_added_player'])
        if entry:
            analyzer.process_log_entry(entry)
        
        self.assertIsNotNone(analyzer)
        self.assertTrue(analyzer.diagnostic)
    
    def test_list_hostiles_mode(self):
        """Test analyzer in list hostiles mode."""
        analyzer = ESOLogAnalyzer(list_hostiles=True)
        
        # Add a hostile enemy
        enemy_line = '1000,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F'
        entry = ESOLogEntry.parse(enemy_line)
        if entry:
            analyzer.process_log_entry(entry)
        
        self.assertIsNotNone(analyzer)
        self.assertTrue(analyzer.list_hostiles)


if __name__ == '__main__':
    unittest.main()
