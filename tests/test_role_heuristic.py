"""Tests for player role inference heuristic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from esolog_tail import PlayerInfo, infer_player_role


def test_tank_health_primary():
    p = PlayerInfo("1", "Tank", "@tank")
    p.max_health = 50000
    p.max_magicka = 20000
    p.max_stamina = 22000
    assert infer_player_role(p) == 'T'


def test_dps_stamina_primary():
    p = PlayerInfo("2", "StamDPS", "@stamdps")
    p.max_health = 20000
    p.max_magicka = 16000
    p.max_stamina = 48000
    assert infer_player_role(p) == 'D'


def test_dps_magicka_more_damage():
    p = PlayerInfo("3", "MagDPS", "@magdps")
    p.max_health = 22000
    p.max_magicka = 42000
    p.max_stamina = 18000
    assert infer_player_role(p, player_damage=100000, player_healing=5000) == 'D'


def test_healer_magicka_more_healing():
    p = PlayerInfo("4", "Healer", "@healer")
    p.max_health = 21000
    p.max_magicka = 42000
    p.max_stamina = 18000
    assert infer_player_role(p, player_damage=8000, player_healing=50000) == 'H'


def test_tied_resources_fallback_tank():
    p = PlayerInfo("5", "Hybrid", "@hybrid")
    p.max_health = 30000
    p.max_magicka = 31000
    p.max_stamina = 29000
    assert infer_player_role(p, skill_line_role='tank') == 'T'


def test_tied_resources_no_fallback():
    p = PlayerInfo("6", "Hybrid", "@hybrid")
    p.max_health = 30000
    p.max_magicka = 31000
    p.max_stamina = 29000
    assert infer_player_role(p) == 'D'  # Default


def test_zero_resources():
    p = PlayerInfo("7", "New", "@new")
    assert infer_player_role(p) == 'D'


def test_zero_resources_with_skill_role():
    p = PlayerInfo("8", "New", "@new")
    assert infer_player_role(p, skill_line_role='healer') == 'H'
