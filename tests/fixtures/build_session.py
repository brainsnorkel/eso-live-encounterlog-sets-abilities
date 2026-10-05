"""
A one-fight log session for the build-window tests.

Three players whose PLAYER_INFO lines cover the cases that matter:

1. @brainsnorkel: a real line (the maintainer's Warden, 2026-10-03). Two
   staves, so both bars are two-handed, and a set that reaches five pieces on
   the back bar only; a mythic ring; crafted food; one mundus stone.
2. @dualwield: two daggers, a poison on each bar (one named, one scaled by
   level), a costume, a ring below the level cap, and a drink the log writes
   as three effects.
3. An anonymous player with two mundus stones (Twice-Born Star), no food,
   and an empty equipment list.
"""

REAL_GEAR = ('[[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,MAGICKA,T,16,LEGENDARY],'
             '[NECK,187753,T,16,JEWELRY_BLOODTHIRSTY,LEGENDARY,653,INCREASE_SPELL_DAMAGE,T,16,LEGENDARY],'
             '[CHEST,210250,T,16,ARMOR_DIVINES,LEGENDARY,781,MAGICKA,T,16,LEGENDARY],'
             '[SHOULDERS,187287,T,16,ARMOR_DIVINES,LEGENDARY,653,MAGICKA,T,16,LEGENDARY],'
             '[MAIN_HAND,133257,T,16,WEAPON_CHARGED,LEGENDARY,361,POISONED_WEAPON,T,16,LEGENDARY],'
             '[WAIST,210256,T,16,ARMOR_DIVINES,LEGENDARY,781,MAGICKA,T,16,LEGENDARY],'
             '[LEGS,210254,T,16,ARMOR_DIVINES,LEGENDARY,781,MAGICKA,T,16,LEGENDARY],'
             '[FEET,210251,T,16,ARMOR_DIVINES,LEGENDARY,781,MAGICKA,T,16,LEGENDARY],'
             '[RING1,187752,T,16,JEWELRY_BLOODTHIRSTY,LEGENDARY,653,INCREASE_SPELL_DAMAGE,T,16,LEGENDARY],'
             '[RING2,224106,T,16,JEWELRY_BLOODTHIRSTY,LEGENDARY,848,INCREASE_SPELL_DAMAGE,T,16,LEGENDARY],'
             '[HAND,210252,T,16,ARMOR_DIVINES,LEGENDARY,781,MAGICKA,T,16,LEGENDARY],'
             '[BACKUP_MAIN,187194,T,16,WEAPON_INFUSED,LEGENDARY,653,BERSERKER,T,16,LEGENDARY]]')
POISON_GEAR = ('[[HEAD,59606,T,16,ARMOR_INFUSED,ARTIFACT,168,STAMINA,T,16,ARTIFACT],'
               '[MAIN_HAND,200834,T,16,WEAPON_NIRNHONED,LEGENDARY,726,FIERY_WEAPON,T,16,LEGENDARY],'
               '[OFF_HAND,200834,T,16,WEAPON_CHARGED,LEGENDARY,726,POISONED_WEAPON,T,16,LEGENDARY],'
               '[COSTUME,55262,F,1,NONE,ARCANE,0,INVALID,F,0,NORMAL],'
               '[RING1,186410,T,15,JEWELRY_BLOODTHIRSTY,ARCANE,646,INCREASE_PHYSICAL_DAMAGE,T,16,LEGENDARY],'
               '[POISON,79690,F,1,NONE,LEGENDARY,0,INVALID,F,0,NORMAL],'
               '[BACKUP_POISON,81196,T,15,NONE,NORMAL,0,INVALID,F,0,NORMAL],'
               '[BACKUP_MAIN,166283,T,16,WEAPON_INFUSED,LEGENDARY,526,BERSERKER,T,16,LEGENDARY]]')
HIT = ('COMBAT_EVENT,DAMAGE,PHYSICAL,1,{dmg},0,4021667,12345,{unit},22762/22762,26657/26657,'
       '13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,70,105634/105634,0/0,0/0,0/0,0/0,'
       '0,0.4081,0.5662,0.0256')
SESSION = [
    '1000,BEGIN_LOG,1759600000000,15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1055,"Scalecaller Peak",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,4,7,"Pïque","@brainsnorkel",14901578173200504511,50,3224,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,3,4,"Stabby","@dualwield",1002,50,1962,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,117,6,"","",0,50,467,0,PLAYER_ALLY,T',
    '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
    '9990,BEGIN_COMBAT',
    '9990,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    '9990,ABILITY_INFO,45549,"Grace","/esoui/art/icons/ability_armor_004.dds",T,T',
    '9990,ABILITY_INFO,13975,"Boon: The Thief","/esoui/art/icons/ability_mundusstones_003.dds",T,T',
    '9990,ABILITY_INFO,13982,"Boon: The Atronach","/esoui/art/icons/ability_mundusstones_009.dds",T,T',
    '9990,ABILITY_INFO,61257,"Increase Max Health & Magicka","/esoui/art/icons/crafting_cooking_grilled_vegetables.dds",T,T',
    '9990,ABILITY_INFO,226885,"Aerie\'s Cry","/esoui/art/icons/achievement_update16_017.dds",T,T',
    '9990,ABILITY_INFO,84731,"Witchmother\'s Potent Brew","/esoui/art/icons/event_halloween_2016_iron_cup_bones.dds",T,T',
    '9990,ABILITY_INFO,84732,"Increase Health Regen","/esoui/art/icons/store_magickafood_001.dds",T,T',
    '9990,ABILITY_INFO,84733,"Increase Health Regen","/esoui/art/icons/store_magickafood_001.dds",T,T',
    f'9991,PLAYER_INFO,1,[45549,61257,226885,13975],[1,1,1,1],{REAL_GEAR},[12345],[12345]',
    f'9991,PLAYER_INFO,2,[84732,84733,84731,13975],[1,1,1,1],{POISON_GEAR},[12345],[12345]',
    '9991,PLAYER_INFO,3,[13982,45549,13975],[1,1,1],[],[12345],[12345]',
    '11000,' + HIT.format(dmg=90000, unit=1),
    '21000,' + HIT.format(dmg=60000, unit=2),
    '31000,' + HIT.format(dmg=30000, unit=3),
    '70000,END_COMBAT',
]


def fights(lines=None):
    """Replay log lines through the engine; the completed fight entries."""
    from esolog_tail import ESOLogAnalyzer
    from fight_history import FightHistory
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.current_log_file = 'Encounter.log'
    for line in SESSION if lines is None else lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer.fight_history.fights


def real_gear():
    """REAL_GEAR as the engine keeps it: slot -> the item's eleven fields."""
    from eso_log_structures import PlayerInfoEntry
    parsed = PlayerInfoEntry.parse(f'9991,PLAYER_INFO,1,[45549],[1],{REAL_GEAR},[12345],[12345]')
    return {g.slot: [g.slot, str(g.item_id), g.bind_type, str(g.level), g.trait, g.quality,
                     str(g.set_id), g.enchant, g.enchant_bind_type, str(g.enchant_level),
                     g.enchant_quality] for g in parsed.gear_items}
