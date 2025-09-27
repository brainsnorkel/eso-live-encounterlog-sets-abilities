"""
Pytest configuration and shared fixtures for ESO analyzer tests.
"""

import pytest
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def sample_analyzer():
    """Create a sample ESOLogAnalyzer for testing."""
    from esolog_tail import ESOLogAnalyzer
    return ESOLogAnalyzer()


@pytest.fixture
def sample_encounter():
    """Create a sample CombatEncounter for testing."""
    from esolog_tail import CombatEncounter
    encounter = CombatEncounter()
    
    # Add sample players
    encounter.add_player("1", "Player1", "@player1", "117")
    encounter.add_player("2", "Player2", "@player2", "6")
    
    return encounter


@pytest.fixture
def sample_log_lines():
    """Provide sample log lines for testing."""
    return {
        'unit_added': '5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
        'ability_info': '2928,ABILITY_INFO,84734,"Test Ability","/esoui/art/icons/ability_mage_065.dds",T,T',
        'begin_cast': '2928,BEGIN_CAST,0,F,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000',
        'effect_changed': '526,EFFECT_CHANGED,GAINED,1,1857418,28012,6,32417/32417,0/0,0/0,0/0,0/0,0,0.3851,0.7801,2.6373,16,52831/52831,0/0,0/0,0/0,0/0,0,0.3705,0.8056,6.0084'
    }


@pytest.fixture
def sample_abilities():
    """Provide sample ability sets for testing."""
    return {
        'templar_healer': {
            "Breath of Life", "Honor the Dead", "Healing Ritual",
            "Puncturing Sweeps", "Radiant Destruction"
        },
        'sorcerer_dps': {
            "Crystal Fragments", "Streak", "Lightning Form",
            "Hardened Ward", "Daedric Curse"
        }
    }
