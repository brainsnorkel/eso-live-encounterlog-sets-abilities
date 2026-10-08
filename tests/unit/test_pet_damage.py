#!/usr/bin/env python3
"""Damage and healing by a player's pet count as that player's.

The log names a summoned unit's owner (ownerUnitId) in UNIT_ADDED and in
UNIT_CHANGED. The engine used to ignore the field and credit pet damage to
nobody. The lines here have the shape of Chris's trial logs: a pet is a
MONSTER with reaction NPC_ALLY, loses its owner when it expires, and the
game hands its unit id out again later.
"""

import unittest

from engine_events import RecordingListener
from esolog_tail import COMBAT_RESUME_MS, ESOLogAnalyzer, FightHistory

EPOCH = 1759600000000
BOSS_HEALTH = 1000000
PET_HEALTH = 45478
ABILITY = 12345


def _player(unit_id, health=20000):
    return (f"{unit_id},{health}/20000,26657/26657,13021/13021,"
            f"500/500,1000/1000,0,0.2,0.5,5.5")


def _boss(health, unit_id=70):
    return f"{unit_id},{health}/{BOSS_HEALTH},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _pet(unit_id):
    return f"{unit_id},{PET_HEALTH}/{PET_HEALTH},0/0,0/0,0/0,0/0,0,0.3,0.4,1.0"


def _unit_added(ts, unit_id, name, owner, reaction='NPC_ALLY'):
    return (f'{ts},UNIT_ADDED,{unit_id},MONSTER,F,0,{PET_HEALTH},F,0,0,"{name}","",'
            f'0,50,160,{owner},{reaction},F')


def _unit_changed(ts, unit_id, name, owner, reaction='NPC_ALLY'):
    return f'{ts},UNIT_CHANGED,{unit_id},0,0,"{name}","",0,50,160,{owner},{reaction},F'


def _event(ts, result, value, source, target):
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{value},0,900,{ABILITY},"
            f"{source},{target}")


def _hit(ts, source, damage, boss_health_after):
    return _event(ts, 'DAMAGE', damage, source, _boss(boss_health_after))


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1344,"Dreadsail Reef",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,4,"Coworker","@brainsnorkel",1001,50,3225,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,2,7,"Third Wheel","@third",1003,50,1800,0,PLAYER_ALLY,T',
    f'2500,UNIT_ADDED,70,MONSTER,F,0,{BOSS_HEALTH},T,0,0,"Tideborn Taleria","",0,50,160,0,HOSTILE,F',
    f'2600,ABILITY_INFO,{ABILITY},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
]
# Player 1's Blighted Blastbones, summoned before the pull
PET = _unit_added(3000, 90, 'Blighted Blastbones', 1)

# A twenty-second fight: player 2 hits once, the pet hits once
FIGHT_START = [
    '10000,BEGIN_COMBAT',
    *[f'10001,PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2, 3)],
]
PLAYER_HIT = _hit(11000, _player(2), 300000, 700000)
PET_HIT = _hit(12000, _pet(90), 100000, 600000)
FIGHT_END = ['30000,END_COMBAT']


def _run(lines):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in BASE + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer


def _dps(fight):
    return {p['unit_id']: p['dps'] for p in fight.players}


class TestPetDamage(unittest.TestCase):

    def test_a_pets_damage_counts_as_its_owners(self):
        analyzer = _run([PET] + FIGHT_START + [PLAYER_HIT, PET_HIT] + FIGHT_END)
        fight = analyzer.fight_history.fights[0]
        self.assertEqual(_dps(fight), {'1': 5000.0, '2': 15000.0, '3': 0.0})
        self.assertEqual(fight.group_dps, 20000.0)

    def test_a_pet_summoned_during_the_fight(self):
        analyzer = _run(FIGHT_START + [
            PLAYER_HIT,
            _unit_added(11500, 90, 'Blighted Blastbones', 1),
            PET_HIT,
        ] + FIGHT_END)
        self.assertEqual(_dps(analyzer.fight_history.fights[0]), {'1': 5000.0, '2': 15000.0, '3': 0.0})

    def test_the_pets_hit_can_open_the_fight(self):
        analyzer = _run([PET] + FIGHT_START + [PET_HIT, PLAYER_HIT] + FIGHT_END)
        self.assertEqual(analyzer.fight_history.fights[0].first_damage_dealer, '1')

    def test_a_pet_from_before_the_pull_is_still_the_players_in_the_next_fight(self):
        later = 30000 + COMBAT_RESUME_MS + 60000
        analyzer = _run([PET] + FIGHT_START + [PLAYER_HIT] + FIGHT_END + [
            f'{later},BEGIN_COMBAT',
            *[f'{later + 1},PLAYER_INFO,{unit},[45549],[1],[],[12345],[12345]' for unit in (1, 2, 3)],
            _hit(later + 2000, _pet(90), 100000, 600000),
            _hit(later + 3000, _player(2), 100000, 500000),
            f'{later + 20000},END_COMBAT',
        ])
        first, second = analyzer.fight_history.fights
        self.assertEqual(_dps(first), {'1': 0.0, '2': 15000.0, '3': 0.0})
        self.assertEqual(_dps(second), {'1': 5000.0, '2': 5000.0, '3': 0.0})

    def test_a_bosss_summons_are_nobodys_pet(self):
        analyzer = _run([
            _unit_added(3000, 91, 'Storm Atronach', 70, reaction='HOSTILE'),
        ] + FIGHT_START + [PLAYER_HIT] + FIGHT_END)
        self.assertEqual(analyzer.current_encounter.pet_ownership, {})

    def test_an_expired_pet_loses_its_owner(self):
        analyzer = _run([PET] + FIGHT_START + [
            PET_HIT,
            _unit_changed(13000, 90, 'Blighted Blastbones', 0, reaction='HOSTILE'),
        ] + FIGHT_END)
        self.assertEqual(analyzer.current_encounter.pet_ownership, {})
        # The hit it landed while it had an owner stays with player 1
        self.assertEqual(_dps(analyzer.fight_history.fights[0])['1'], 5000.0)

    def test_a_unit_id_handed_out_again_is_not_the_pet(self):
        analyzer = _run([PET] + FIGHT_START + [
            PET_HIT,
            '13000,UNIT_REMOVED,90',
            _unit_added(14000, 90, 'Dreadsail Deckhand', 0, reaction='HOSTILE'),
        ] + FIGHT_END)
        self.assertEqual(analyzer.current_encounter.pet_ownership, {})

    def test_a_pet_removed_without_a_change_line_is_forgotten(self):
        analyzer = _run([PET] + FIGHT_START + ['13000,UNIT_REMOVED,90'] + FIGHT_END)
        self.assertEqual(analyzer.current_encounter.pet_ownership, {})

    def test_a_pets_healing_of_another_player_counts_as_its_owners(self):
        analyzer = _run([
            _unit_added(3000, 92, 'Glyphic of the Tides', 1),
        ] + FIGHT_START + [
            PLAYER_HIT,
            _event(12000, 'HEAL', 5000, _pet(92), _player(2)),
            # Healing its own owner is a self-heal, as for players
            _event(13000, 'HEAL', 5000, _pet(92), _player(1)),
        ] + FIGHT_END)
        self.assertEqual(analyzer.current_encounter.player_healing, {'1': 5000})


if __name__ == '__main__':
    unittest.main()
