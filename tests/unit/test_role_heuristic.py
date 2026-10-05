"""Tests for player role inference heuristic."""

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


def _magicka_primary():
    p = PlayerInfo("9", "Mag", "@mag")
    p.max_health = 21000
    p.max_magicka = 42000
    p.max_stamina = 18000
    return p


def test_healer_magicka_with_restoration_staff():
    # The staff decides it, even in a fight where they mostly dealt damage
    p = _magicka_primary()
    assert infer_player_role(p, player_damage=100000, player_healing=5000,
                             restoration_staff=True) == 'H'
    assert infer_player_role(p, restoration_staff=True) == 'H'


def test_magicka_without_staff_still_goes_by_healing():
    p = _magicka_primary()
    assert infer_player_role(p, player_damage=8000, player_healing=50000,
                             restoration_staff=False) == 'H'
    assert infer_player_role(p, player_damage=100000, player_healing=5000,
                             restoration_staff=False) == 'D'


def test_restoration_staff_does_not_make_a_healer_without_primary_magicka():
    tank = PlayerInfo("10", "Tank", "@tank")
    tank.max_health, tank.max_magicka, tank.max_stamina = 50000, 20000, 22000
    assert infer_player_role(tank, restoration_staff=True) == 'T'
    stam = PlayerInfo("11", "Stam", "@stam")
    stam.max_health, stam.max_magicka, stam.max_stamina = 20000, 16000, 48000
    assert infer_player_role(stam, player_healing=90000, restoration_staff=True) == 'D'


def test_tied_resources_ignore_the_staff():
    p = PlayerInfo("12", "Hybrid", "@hybrid")
    p.max_health, p.max_magicka, p.max_stamina = 30000, 31000, 29000
    assert infer_player_role(p, restoration_staff=True) == 'D'
    assert infer_player_role(p, skill_line_role='tank', restoration_staff=True) == 'T'


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
