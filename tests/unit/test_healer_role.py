#!/usr/bin/env python3
"""Who is a healer: magicka as the largest pool, plus a restoration staff
equipped or more healing of others than damage dealt. Covers the staff
lookup (against the bundled weapon table, whose generator is tested with the
other build data scripts), the healing total, and the role the engine puts
on a fight entry (no Qt needed)."""

import unittest

from build_session import fights  # noqa: E402
from player_build import has_restoration_staff  # noqa: E402

# Real item ids: a restoration staff, a lightning staff and a dagger
RESTO_STAFF = '224527'      # Restoration Staff of the Gorethief
LIGHTNING_STAFF = '133257'
DAGGER = '200834'


def _weapon(slot, item_id):
    return [slot, item_id, 'T', '16', 'WEAPON_POWERED', 'LEGENDARY', '0', 'ABSORB_MAGICKA',
            'T', '16', 'LEGENDARY']


def _gear(*weapons):
    return {slot: _weapon(slot, item_id) for slot, item_id in weapons}


class TestRestorationStaffLookup(unittest.TestCase):

    def test_staff_on_either_bar(self):
        staves = {RESTO_STAFF}
        self.assertTrue(has_restoration_staff(_gear(('MAIN_HAND', RESTO_STAFF)), staves))
        self.assertTrue(has_restoration_staff(
            _gear(('MAIN_HAND', LIGHTNING_STAFF), ('BACKUP_MAIN', RESTO_STAFF)), staves))

    def test_other_weapons_and_no_weapons(self):
        staves = {RESTO_STAFF}
        self.assertFalse(has_restoration_staff(
            _gear(('MAIN_HAND', DAGGER), ('OFF_HAND', DAGGER), ('BACKUP_MAIN', LIGHTNING_STAFF)),
            staves))
        self.assertFalse(has_restoration_staff({}, staves))
        self.assertFalse(has_restoration_staff({'MAIN_HAND': ['MAIN_HAND']}, staves))

    def test_ids_compare_as_text(self):
        self.assertTrue(has_restoration_staff(_gear(('MAIN_HAND', RESTO_STAFF)), [224527]))

    def test_bundled_list_knows_real_staves(self):
        self.assertTrue(has_restoration_staff(_gear(('BACKUP_MAIN', RESTO_STAFF))))
        self.assertFalse(has_restoration_staff(
            _gear(('MAIN_HAND', LIGHTNING_STAFF), ('BACKUP_MAIN', DAGGER))))


# ---- through the engine ----

STATE = '22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492'
BOSS = '70,105634/105634,0/0,0/0,0/0,0/0,0,0.4081,0.5662,0.0256'


def _cast(ms, unit):
    """A cast by *unit*: its line carries the pools the role is read from."""
    return f'{ms},BEGIN_CAST,0,F,4021667,12345,{unit},{STATE},0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000'


def _hit(ms, unit, damage):
    return f'{ms},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{damage},0,4021667,12345,{unit},{STATE},{BOSS}'


def _heal(ms, result, source, target, amount):
    target_state = '*' if target == source else f'{target},{STATE}'
    return (f'{ms},COMBAT_EVENT,{result},GENERIC,1,{amount},0,4021668,12345,'
            f'{source},{STATE},{target_state}')


def _gear_list(*weapons):
    return '[' + ','.join('[' + ','.join(_weapon(slot, item_id)) + ']'
                          for slot, item_id in weapons) + ']'


# Four magicka players. Ada has a restoration staff on her back bar and mostly
# deals damage. Bren has no such staff but heals the others for more than his
# damage, in plain HEAL lines. Cy only deals damage and heals himself. Dee has
# the staff too, and neither heals nor hits.
SESSION = [
    '1000,BEGIN_LOG,1759600000000,15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1055,"Scalecaller Peak",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,6,7,"Ada Quill","@ada",1001,50,2000,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,2,1,"Bren Ward","@bren",1002,50,2000,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,2,1,"Cy Marrow","@cy",1003,50,2000,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,4,PLAYER,F,4,0,F,4,1,"Dee Vale","@dee",1004,50,2000,0,PLAYER_ALLY,T',
    '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
    '9990,BEGIN_COMBAT',
    '9990,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    '9990,ABILITY_INFO,45549,"Grace","/esoui/art/icons/ability_armor_004.dds",T,T',
    '9991,PLAYER_INFO,1,[45549],[1],'
    + _gear_list(('MAIN_HAND', LIGHTNING_STAFF), ('BACKUP_MAIN', RESTO_STAFF)) + ',[12345],[12345]',
    '9991,PLAYER_INFO,2,[45549],[1],'
    + _gear_list(('MAIN_HAND', LIGHTNING_STAFF), ('BACKUP_MAIN', LIGHTNING_STAFF)) + ',[12345],[12345]',
    '9991,PLAYER_INFO,3,[45549],[1],'
    + _gear_list(('MAIN_HAND', DAGGER), ('OFF_HAND', DAGGER)) + ',[12345],[12345]',
    '9991,PLAYER_INFO,4,[45549],[1],'
    + _gear_list(('MAIN_HAND', RESTO_STAFF)) + ',[12345],[12345]',
    _cast(10000, 1), _cast(10000, 2), _cast(10000, 3), _cast(10000, 4),
    _hit(11000, 1, 90000),
    _heal(12000, 'HOT_TICK', 1, 2, 5000),
    _hit(13000, 2, 30000),
    _heal(14000, 'HEAL', 2, 1, 40000),
    _heal(15000, 'HEAL', 2, 3, 40000),
    _heal(16000, 'CRITICAL_HEAL', 2, 3, 2500),
    _heal(17000, 'HOT_TICK_CRITICAL', 2, 1, 500),
    _hit(18000, 3, 60000),
    _heal(19000, 'HEAL', 3, 3, 99999),          # heals himself: not counted
    '70000,END_COMBAT',
]


class TestRoleOnTheFightEntry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        entries = fights(SESSION)
        assert len(entries) == 1, len(entries)
        cls.players = {p['name']: p for p in entries[0].players}

    def test_everyone_has_magicka_as_their_largest_pool(self):
        for p in self.players.values():
            self.assertEqual((p['h'], p['m'], p['s']), (22762, 26657, 13021))

    def test_plain_heals_count_towards_healing(self):
        # HEAL, CRITICAL_HEAL, HOT_TICK and HOT_TICK_CRITICAL on other players
        self.assertEqual(self.players['@bren']['healing'], 40000 + 40000 + 2500 + 500)
        self.assertEqual(self.players['@ada']['healing'], 5000)

    def test_healing_yourself_does_not_count(self):
        self.assertEqual(self.players['@cy']['healing'], 0)

    def test_restoration_staff_makes_a_magicka_player_a_healer(self):
        # Ada dealt far more damage than she healed
        self.assertEqual(self.players['@ada']['role'], 'H')
        self.assertEqual(self.players['@dee']['role'], 'H')

    def test_out_healing_your_damage_still_makes_a_healer_without_the_staff(self):
        self.assertEqual(self.players['@bren']['role'], 'H')

    def test_magicka_damage_dealer_stays_dps(self):
        self.assertEqual(self.players['@cy']['role'], 'D')


if __name__ == '__main__':
    unittest.main()
