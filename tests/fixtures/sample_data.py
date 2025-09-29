"""
Test fixtures and sample data for ESO analyzer tests.
"""

# Sample log lines for testing
SAMPLE_LOG_LINES = {
    'begin_log': '5,BEGIN_LOG,1755729685851,15,"NA Megaserver","en","eso.live.11.1"',
    'zone_changed': '5,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
    'unit_added_player': '5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
    'unit_added_anon': '5,UNIT_ADDED,30,PLAYER,F,2,0,F,6,1,"","",0,50,787,0,PLAYER_ALLY,F',
    'ability_info': '2928,ABILITY_INFO,84734,"Witchfest Food: Max HM, Reg M","/esoui/art/icons/ability_mage_065.dds",T,T',
    'begin_cast': '2928,BEGIN_CAST,0,F,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000',
    'effect_changed': '526,EFFECT_CHANGED,GAINED,1,1857418,28012,6,32417/32417,0/0,0/0,0/0,0/0,0,0.3851,0.7801,2.6373,16,52831/52831,0/0,0/0,0/0,0/0,0,0.3705,0.8056,6.0084',
    'combat_event_damage': '43016,COMBAT_EVENT,DAMAGE,PHYSICAL,1,1006,0,4022650,46746,30,18678/18678,9019/14560,29346/29573,500/500,1000/1000,0,0.4086,0.5534,4.8044,34,131056/136704,0/0,0/0,0/0,0/0,0,0.4112,0.5591,5.8727'
}

# Sample player info data for testing
SAMPLE_PLAYER_INFO = {
    'unit_id': '1',
    'name': 'TestPlayer',
    'handle': '@testhandle',
    'class_id': '117'  # Arcanist
}

# Sample abilities for testing subclass analysis
SAMPLE_ABILITIES = {
    'templar_healer': {
        "Breath of Life", "Honor the Dead", "Healing Ritual",
        "Puncturing Sweeps", "Radiant Destruction"
    },
    'sorcerer_dps': {
        "Crystal Fragments", "Streak", "Lightning Form",
        "Hardened Ward", "Daedric Curse"
    },
    'arcanist_dps': {
        "Cephaliarch's Flail", "Pragmatic Fatecarver", "Quick Cloak",
        "Radiant Glory", "Camouflaged Hunter", "Soul Harvest"
    }
}

# Sample gear set IDs for testing
SAMPLE_GEAR_SET_IDS = {
    'arms_of_relequen': '107202',
    'mother_ciannait': '133378',
    'bahseis_mania': '154691',
    'spell_power_cure': '66899'
}

# Test encounter data
SAMPLE_ENCOUNTER_DATA = {
    'players': [
        {
            'unit_id': '1',
            'name': 'Player1',
            'handle': '@player1',
            'class_id': '117'
        },
        {
            'unit_id': '2', 
            'name': 'Player2',
            'handle': '@player2',
            'class_id': '6'
        }
    ],
    'enemies': [
        {
            'unit_id': '70',
            'name': 'Test Enemy',
            'unit_type': 'MONSTER'
        }
    ]
}


