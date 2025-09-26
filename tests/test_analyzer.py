#!/usr/bin/env python3
"""
Test script for ESO Analyzer
Verifies that the analyzer works correctly with sample data.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from esolog_tail import ESOLogEntry, ESOLogAnalyzer
from eso_sets import ESOSubclassAnalyzer

def test_log_parsing():
    """Test basic log entry parsing."""
    print("Testing log entry parsing...")

    # Test UNIT_ADDED parsing
    line = '5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T'
    entry = ESOLogEntry.parse(line)

    assert entry is not None
    assert entry.timestamp == 5
    assert entry.event_type == "UNIT_ADDED"
    assert len(entry.fields) >= 10
    print("✓ UNIT_ADDED parsing works")

    # Test ABILITY_INFO parsing
    line = '2928,ABILITY_INFO,84734,"Witchfest Food: Max HM, Reg M","/esoui/art/icons/ability_mage_065.dds",T,T'
    entry = ESOLogEntry.parse(line)

    assert entry is not None
    assert entry.timestamp == 2928
    assert entry.event_type == "ABILITY_INFO"
    print("✓ ABILITY_INFO parsing works")

    # Test BEGIN_CAST parsing
    line = '2928,BEGIN_CAST,0,F,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000'
    entry = ESOLogEntry.parse(line)

    assert entry is not None
    assert entry.timestamp == 2928
    assert entry.event_type == "BEGIN_CAST"
    print("✓ BEGIN_CAST parsing works")

    print("Log parsing tests passed!\n")

def test_subclass_analysis():
    """Test subclass analysis functionality."""
    print("Testing subclass analysis...")

    analyzer = ESOSubclassAnalyzer()

    # Test Templar healer
    templar_abilities = {
        "Breath of Life", "Honor the Dead", "Healing Ritual",
        "Puncturing Sweeps", "Radiant Destruction"
    }

    result = analyzer.analyze_subclass(templar_abilities)
    print(f"Templar test: {result}")
    assert 'Restoring Light' in result['skill_lines']
    assert result['role'] == 'healer'
    print("✓ Templar healer detection works")

    # Test Sorcerer magicka DPS
    sorc_abilities = {
        "Crystal Fragments", "Streak", "Lightning Form",
        "Hardened Ward", "Daedric Curse"
    }

    result = analyzer.analyze_subclass(sorc_abilities)
    print(f"Sorcerer test: {result}")
    assert 'Dark Magic' in result['skill_lines'] or 'Storm Calling' in result['skill_lines']
    assert result['role'] == 'dps'
    print("✓ Sorcerer magicka DPS detection works")

    print("Subclass analysis tests passed!\n")

def test_set_database():
    """Test gear set database functionality."""
    print("Testing set database...")

    from gear_set_database_optimized import OptimizedGearSetDatabase
    db = OptimizedGearSetDatabase()

    # Test set identification
    abilities = {"False God's Devotion", "Crystal Fragments", "Spell Critical"}
    sets = db.identify_sets_from_abilities(abilities, "magicka_dps")

    print(f"Set identification result: {sets}")
    assert len(sets) > 0
    print("✓ Set identification works")

    # Test role-based suggestions
    sets = db.identify_sets_from_abilities(set(), "healer")
    print(f"Healer suggestions: {sets}")
    assert len(sets) > 0
    print("✓ Role-based set suggestions work")

    print("Set database tests passed!\n")

def test_full_analyzer():
    """Test the full analyzer with sample data."""
    print("Testing full analyzer...")

    analyzer = ESOLogAnalyzer()

    # Test with minimal data
    # Add a player
    unit_entry = ESOLogEntry(100, "UNIT_ADDED",
                           ["1", "PLAYER", "T", "1", "0", "F", "117", "7",
                            "Test Player", "@testhandle", "123456789", "50", "3084", "0", "PLAYER_ALLY", "T"])
    analyzer.process_log_entry(unit_entry)

    # Add ability info
    ability_entry = ESOLogEntry(200, "ABILITY_INFO", ["12345", "Test Ability", "/path/to/icon.dds", "T", "T"])
    analyzer.process_log_entry(ability_entry)

    # Add combat event
    cast_entry = ESOLogEntry(300, "BEGIN_CAST", ["0", "F", "1", "12345", "1", "100/100", "50/50", "25/25"])
    analyzer.process_log_entry(cast_entry)

    # Verify encounter was created
    assert analyzer.current_encounter is not None
    assert len(analyzer.current_encounter.players) == 1
    print("✓ Full analyzer integration works")

    print("Full analyzer tests passed!\n")

def main():
    """Run all tests."""
    print("Running ESO Analyzer Tests\n")

    try:
        test_log_parsing()
        test_subclass_analysis()
        test_set_database()
        test_full_analyzer()

        print("🎉 All tests passed! ESO Analyzer is ready to use.")
        print("\nTo test with real data, run:")
        print("  python3 src/esolog_tail.py --test-mode")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())