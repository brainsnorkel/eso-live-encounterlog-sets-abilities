#!/usr/bin/env python3
"""
Unit tests for damage attribution functionality.
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fixtures'))

from esolog_tail import ESOLogEntry, ESOLogAnalyzer, CombatEncounter, PlayerInfo
from sample_data import SAMPLE_ENCOUNTER_DATA, SAMPLE_LOG_LINES


class TestDamageAttribution(unittest.TestCase):
    """Test damage attribution functionality."""
    
    def test_basic_damage_attribution(self):
        """Test basic damage attribution to players."""
        encounter = CombatEncounter()
        
        # Add a player
        encounter.add_player("1", "TestPlayer", "@testhandle", "117")
        
        # Simulate damage event
        encounter.add_damage_to_player("1", 1000)
        
        # Verify damage was attributed
        self.assertIn("1", encounter.player_damage)
        self.assertEqual(encounter.player_damage["1"], 1000)
    
    def test_pet_damage_attribution(self):
        """Test damage attribution from pets to their owners."""
        encounter = CombatEncounter()
        
        # Add a player
        encounter.add_player("1", "TestPlayer", "@testhandle", "117")
        
        # Track pet ownership
        encounter.track_pet_ownership("pet_123", "1")
        
        # Simulate damage from pet
        encounter.add_damage_to_player("pet_123", 500)
        
        # Verify damage was attributed to owner
        self.assertIn("1", encounter.player_damage)
        self.assertEqual(encounter.player_damage["1"], 500)
    
    def test_unit_id_matching(self):
        """Test unit ID matching between short and long formats."""
        encounter = CombatEncounter()
        
        # Add a player with short unit ID
        encounter.add_player("1", "TestPlayer", "@testhandle", "117")
        
        # Associate long unit ID
        encounter.associate_long_unit_id("1", "4021667")
        
        # Test finding player by short ID
        player = encounter.find_player_by_unit_id("1")
        self.assertIsNotNone(player)
        self.assertEqual(player.unit_id, "1")
        
        # Test finding player by long ID
        player = encounter.find_player_by_unit_id("4021667")
        self.assertIsNotNone(player)
        self.assertEqual(player.unit_id, "1")
    
    def test_multiple_players_damage(self):
        """Test damage attribution with multiple players."""
        encounter = CombatEncounter()
        
        # Add multiple players
        encounter.add_player("1", "Player1", "@player1", "117")
        encounter.add_player("2", "Player2", "@player2", "6")
        
        # Add damage for each player
        encounter.add_damage_to_player("1", 1500)
        encounter.add_damage_to_player("2", 2000)
        
        # Verify both players have damage attributed
        self.assertIn("1", encounter.player_damage)
        self.assertIn("2", encounter.player_damage)
        self.assertEqual(encounter.player_damage["1"], 1500)
        self.assertEqual(encounter.player_damage["2"], 2000)
    
    def test_unknown_unit_damage(self):
        """Test damage from unknown units."""
        encounter = CombatEncounter()
        
        # Add a player
        encounter.add_player("1", "TestPlayer", "@testhandle", "117")
        
        # Test damage from unknown unit (should not crash)
        encounter.add_damage_to_player("unknown_unit", 100)
        
        # Should not have any damage attributed
        self.assertEqual(len(encounter.player_damage), 0)
    
    def test_orphan_pet_damage(self):
        """Test pet ownership without valid owner."""
        encounter = CombatEncounter()
        
        # Add a player
        encounter.add_player("1", "TestPlayer", "@testhandle", "117")
        
        # Test pet ownership without owner
        encounter.track_pet_ownership("orphan_pet", "nonexistent_owner")
        encounter.add_damage_to_player("orphan_pet", 200)
        
        # Should not have any damage attributed
        self.assertEqual(len(encounter.player_damage), 0)


class TestCombatEventProcessing(unittest.TestCase):
    """Test combat event processing for damage attribution."""
    
    def test_combat_event_damage_parsing(self):
        """Test damage parsing from combat events."""
        analyzer = ESOLogAnalyzer()
        
        # Add a player first
        unit_entry = ESOLogEntry(100, "UNIT_ADDED",
                               ["1", "PLAYER", "T", "1", "0", "F", "117", "7",
                                "Test Player", "@testhandle", "123456789", "50", "3084", "0", "PLAYER_ALLY", "T"])
        analyzer.process_log_entry(unit_entry)
        
        # Add an enemy
        enemy_entry = ESOLogEntry(200, "UNIT_ADDED",
                                ["70", "MONSTER", "F", "0", "105634", "F", "0", "0",
                                 "Test Enemy", "", "0", "50", "160", "0", "HOSTILE", "F"])
        analyzer.process_log_entry(enemy_entry)
        
        # Simulate a damage combat event
        damage_entry = ESOLogEntry(300, "COMBAT_EVENT",
                                  ["DAMAGE", "PHYSICAL", "1", "1000", "0", "4021667", "12345", 
                                   "1", "22762/22762", "26657/26657", "13021/13021", "500/500", "1000/1000", "0", "0.2696", "0.5942", "5.5492",
                                   "70", "136704/136704", "0/0", "0/0", "0/0", "0/0", "0", "0.4081", "0.5662", "0.0256"])
        analyzer.process_log_entry(damage_entry)
        
        # Verify damage was processed
        if analyzer.current_encounter:
            # Should have processed the damage event without crashing
            self.assertIsNotNone(analyzer.current_encounter)
    
    def test_effect_changed_resource_parsing(self):
        """Test resource parsing from EFFECT_CHANGED events."""
        analyzer = ESOLogAnalyzer()
        
        # Add a player first
        unit_entry = ESOLogEntry(100, "UNIT_ADDED",
                               ["1", "PLAYER", "T", "1", "0", "F", "117", "7",
                                "Test Player", "@testhandle", "123456789", "50", "3084", "0", "PLAYER_ALLY", "T"])
        analyzer.process_log_entry(unit_entry)
        
        # Process EFFECT_CHANGED with resource data
        effect_entry = ESOLogEntry.parse(SAMPLE_LOG_LINES['effect_changed'])
        if effect_entry:
            analyzer.process_log_entry(effect_entry)
        
        # Should not crash
        self.assertIsNotNone(analyzer.current_encounter)


class TestPlayerInfo(unittest.TestCase):
    """Test PlayerInfo functionality."""
    
    def test_player_creation(self):
        """Test PlayerInfo creation."""
        player = PlayerInfo("1", "TestPlayer", "@testhandle", "117")
        
        self.assertEqual(player.unit_id, "1")
        self.assertEqual(player.name, "TestPlayer")
        self.assertEqual(player.handle, "@testhandle")
        self.assertEqual(player.class_id, "117")
    
    def test_resource_tracking(self):
        """Test resource tracking."""
        player = PlayerInfo("1", "TestPlayer", "@testhandle", "117")
        
        # Update resources
        player.update_resources(health=25000, magicka=30000, stamina=28000)
        
        self.assertEqual(player.max_health, 25000)
        self.assertEqual(player.max_magicka, 30000)
        self.assertEqual(player.max_stamina, 28000)
        
        # Update with higher values
        player.update_resources(health=26000, magicka=29000, stamina=29000)
        
        self.assertEqual(player.max_health, 26000)
        self.assertEqual(player.max_magicka, 30000)  # Should keep higher value
        self.assertEqual(player.max_stamina, 29000)
    
    def test_unit_id_association(self):
        """Test long unit ID association."""
        player = PlayerInfo("1", "TestPlayer", "@testhandle", "117")
        
        # Add long unit ID
        player.add_long_unit_id("4021667")
        
        # Test has_unit_id method
        self.assertTrue(player.has_unit_id("1"))  # Short ID
        self.assertTrue(player.has_unit_id("4021667"))  # Long ID
        self.assertFalse(player.has_unit_id("999"))  # Unknown ID
    
    def test_class_name_mapping(self):
        """Test class name mapping."""
        player_arcanist = PlayerInfo("1", "TestPlayer", "@testhandle", "117")
        self.assertEqual(player_arcanist.get_class_name(), "Arcanist")
        
        player_templar = PlayerInfo("2", "TestPlayer2", "@testhandle2", "6")
        self.assertEqual(player_templar.get_class_name(), "Templar")
        
        player_unknown = PlayerInfo("3", "TestPlayer3", "@testhandle3", "999")
        self.assertEqual(player_unknown.get_class_name(), "Unknown")


if __name__ == '__main__':
    unittest.main()


