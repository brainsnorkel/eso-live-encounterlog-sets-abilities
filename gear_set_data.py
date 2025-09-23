"""
Auto-generated gear set data module.
Generated from LibSets_SetData.xlsm - DO NOT EDIT MANUALLY.

This module contains optimized data structures for fast gear set lookups
without requiring Excel file parsing at runtime.
"""

from typing import Dict, List, Optional, Set

# Set ID to Set Name mapping
SET_ID_TO_NAME: Dict[str, str] = {
    "100": "Hawk's Eye",
    "101": "Affliction",
    "102": "Duneripper's Scales",
    "103": "Magicka Furnace",
    "104": "Curse Eater",
    "105": "Twin Sisters",
    "106": "Wilderqueen's Arch",
    "107": "Wyrd Tree's Blessing",
    "108": "Ravager",
    "109": "Light of Cyrodiil",
    "110": "Sanctuary",
    "111": "Ward of Cyrodiil",
    "112": "Night Terror",
    "113": "Crest of Cyrodiil",
    "114": "Soulshine",
    "116": "The Destruction Suite",
    "117": "Relics of the Physician, Ansur",
    "118": "Treasures of the Earthforge",
    "119": "Relics of the Rebellion",
    "120": "Arms of Infernace",
    "121": "Arms of the Ancestors",
    "122": "Ebon Armory",
    "123": "Hircine's Veneer",
    "124": "The Worm's Raiment",
    "125": "Wrath of the Imperium",
    "126": "Grace of the Ancients",
    "127": "Deadly Strike",
    "128": "Blessing of the Potentates",
    "129": "Vengeance Leech",
    "130": "Eagle Eye",
    "131": "Bastion of the Heartland",
    "132": "Shield of the Valiant",
    "133": "Buffer of the Swift",
    "134": "Shroud of the Lich",
    "135": "Draugr's Heritage",
    "136": "Immortal Warrior",
    "137": "Berserking Warrior",
    "138": "Defending Warrior",
    "139": "Wise Mage",
    "140": "Destructive Mage",
    "141": "Healing Mage",
    "142": "Quick Serpent",
    "143": "Poisonous Serpent",
    "144": "Twice-Fanged Serpent",
    "145": "Way of Fire",
    "146": "Way of Air",
    "147": "Way of Martial Knowledge",
    "148": "Way of the Arena",
    "155": "Undaunted Bastion",
    "156": "Undaunted Infiltrator",
    "157": "Undaunted Unweaver",
    "158": "Embershield",
    "159": "Sunderflame",
    "160": "Burning Spellweave",
    "161": "Twice-Born Star",
    "162": "Spawn of Mephala",
    "163": "Blood Spawn",
    "164": "Lord Warden",
    "165": "Scourge Harvester",
    "166": "Engine Guardian",
    "167": "Nightflame",
    "168": "Nerien'eth",
    "169": "Valkyn Skoria",
    "170": "Maw of the Infernal",
    "171": "Eternal Warrior",
    "172": "Infallible Mage",
    "173": "Vicious Serpent",
    "176": "Noble's Conquest",
    "177": "Redistributor",
    "178": "Armor Master",
    "179": "Black Rose",
    "180": "Powerful Assault",
    "181": "Meritorious Service",
    "183": "Molag Kena",
    "184": "Brands of Imperium",
    "185": "Spell Power Cure",
    "186": "Jolting Arms",
    "187": "Swamp Raider",
    "188": "Storm Master",
    "19": "Vestments of the Warlock",
    "190": "Scathing Mage",
    "193": "Overwhelming Surge",
    "194": "Combat Physician",
    "195": "Sheer Venom",
    "196": "Leeching Plate",
    "197": "Tormentor",
    "198": "Essence Thief",
    "199": "Shield Breaker",
    "20": "Witchman Armor",
    "200": "Phoenix",
    "201": "Reactive Armor",
    "204": "Endurance",
    "205": "Willpower",
    "206": "Agility",
    "207": "Law of Julianos",
    "208": "Trial by Fire",
    "209": "Armor of the Code",
    "21": "Akaviri Dragonguard",
    "210": "Mark of the Pariah",
    "211": "Permafrost",
    "212": "Briarheart",
    "213": "Glorious Defender",
    "214": "Para Bellum",
    "215": "Elemental Succession",
    "216": "Hunt Leader",
    "217": "Winterborn",
    "218": "Trinimac's Valor",
    "219": "Morkuldin",
    "22": "Dreamer's Mantle",
    "224": "Tava's Favor",
    "225": "Clever Alchemist",
    "226": "Eternal Hunt",
    "227": "Bahraha's Curse",
    "228": "Syvarra's Scales",
    "229": "Twilight Remedy",
    "23": "Archer's Mind",
    "230": "Moondancer",
    "231": "Lunar Bastion",
    "232": "Roar of Alkosh",
    "234": "Marksman's Crest",
    "235": "Robes of Transmutation",
    "236": "Vicious Death",
    "237": "Leki's Focus",
    "238": "Fasalla's Guile",
    "239": "Warrior's Fury",
    "24": "Footman's Fortune",
    "240": "Kvatch Gladiator",
    "241": "Varen's Legacy",
    "242": "Pelinal's Aptitude",
    "243": "Hide of Morihaus",
    "244": "Flanking Strategist",
    "245": "Sithis' Touch",
    "246": "Galerion's Revenge",
    "247": "Vicecanon of Venom",
    "248": "Thews of the Harbinger",
    "25": "Desert Rose",
    "253": "Imperial Physique",
    "256": "Mighty Chudan",
    "257": "Velidreth",
    "258": "Amber Plasm",
    "259": "Heem-Jas' Retribution",
    "26": "Prisoner's Rags",
    "260": "Aspect of Mazzatun",
    "261": "Gossamer",
    "262": "Widowmaker",
    "263": "Hand of Mephala",
    "264": "Giant Spider",
    "265": "Shadowrend",
    "266": "Kra'gh",
    "267": "Swarm Mother",
    "268": "Sentinel of Rkugamz",
    "269": "Chokethorn",
    "27": "Fiord's Legacy",
    "270": "Slimecraw",
    "271": "Sellistrix",
    "272": "Infernal Guardian",
    "273": "Ilambris",
    "274": "Iceheart",
    "275": "Stormfist",
    "276": "Tremorscale",
    "277": "Pirate Skeleton",
    "278": "The Troll King",
    "279": "Selene",
    "28": "Barkskin",
    "280": "Grothdarr",
    "281": "Armor of the Trainee",
    "282": "Vampire Cloak",
    "283": "Sword-Singer",
    "284": "Order of Diagna",
    "285": "Vampire Lord",
    "286": "Spriggan's Thorns",
    "287": "Green Pact",
    "288": "Beekeeper's Gear",
    "289": "Spinner's Garments",
    "29": "Sergeant's Mail",
    "290": "Skooma Smuggler",
    "291": "Shalk Exoskeleton",
    "292": "Mother's Sorrow",
    "293": "Plague Doctor",
    "294": "Ysgramor's Birthright",
    "295": "Jailbreaker",
    "296": "Spelunker",
    "297": "Spider Cultist Cowl",
    "298": "Light Speaker",
    "299": "Toothrow",
    "30": "Thunderbug's Carapace",
    "300": "Netch's Touch",
    "301": "Strength of the Automaton",
    "302": "Leviathan",
    "303": "Lamia's Song",
    "304": "Medusa",
    "305": "Treasure Hunter",
    "307": "Draugr Hulk",
    "308": "Bone Pirate's Tatters",
    "309": "Knight-errant's Mail",
    "31": "Silks of the Sun",
    "310": "Sword Dancer",
    "311": "Rattlecage",
    "313": "Titanic Cleave",
    "314": "Puncturing Remedy",
    "315": "Stinging Slashes",
    "316": "Caustic Arrow",
    "317": "Destructive Impact",
    "318": "Grand Rejuvenation",
    "32": "Healer's Habit",
    "320": "War Maiden",
    "321": "Defiler",
    "322": "Warrior-Poet",
    "323": "Assassin's Guile",
    "324": "Daedric Trickery",
    "325": "Shacklebreaker",
    "326": "Vanguard's Challenge",
    "327": "Coward's Gear",
    "328": "Knight Slayer",
    "329": "Wizard's Riposte",
    "33": "Viper's Sting",
    "330": "Automated Defense",
    "331": "War Machine",
    "332": "Master Architect",
    "333": "Inventor's Guard",
    "334": "Impregnable Armor",
    "335": "Draugr's Rest",
    "336": "Pillar of Nirn",
    "337": "Ironblood",
    "338": "Flame Blossom",
    "339": "Blooddrinker",
    "34": "Night Mother's Embrace",
    "340": "Hagraven's Garden",
    "341": "Earthgore",
    "342": "Domihaus",
    "343": "Caluurion's Legacy",
    "344": "Trappings of Invigoration",
    "345": "Ulfnor's Favor",
    "346": "Jorvuld's Guidance",
    "347": "Plague Slinger",
    "348": "Curse of Doylemish",
    "349": "Thurvokun",
    "35": "Knightmare",
    "350": "Zaan",
    "351": "Innate Axiom",
    "352": "Fortified Brass",
    "353": "Mechanical Acuity",
    "354": "Mad Tinkerer",
    "355": "Unfathomable Darkness",
    "356": "Livewire",
    "357": "Disciplined Slash (Perfected)",
    "358": "Defensive Position (Perfected)",
    "359": "Chaotic Whirlwind (Perfected)",
    "36": "Armor of the Veiled Heritance",
    "360": "Piercing Spray (Perfected)",
    "361": "Concentrated Force (Perfected)",
    "362": "Timeless Blessing (Perfected)",
    "363": "Disciplined Slash",
    "364": "Defensive Position",
    "365": "Chaotic Whirlwind",
    "366": "Piercing Spray",
    "367": "Concentrated Force",
    "368": "Timeless Blessing",
    "369": "Merciless Charge",
    "37": "Death's Wind",
    "370": "Rampaging Slash",
    "371": "Cruel Flurry",
    "372": "Thunderous Volley",
    "373": "Crushing Wall",
    "374": "Precise Regeneration",
    "38": "Twilight's Embrace",
    "380": "Prophet's",
    "381": "Broken Soul",
    "382": "Grace of Gloom",
    "383": "Gryphon's Ferocity",
    "384": "Wisdom of Vanus",
    "385": "Adept Rider",
    "386": "Sload's Semblance",
    "387": "Nocturnal's Favor",
    "388": "Aegis of Galenwe",
    "389": "Arms of Relequen",
    "39": "Alessian Order",
    "390": "Mantle of Siroria",
    "391": "Vestment of Olorime",
    "392": "Perfect Aegis of Galenwe",
    "393": "Perfect Arms of Relequen",
    "394": "Perfect Mantle of Siroria",
    "395": "Perfect Vestment of Olorime",
    "397": "Balorgh",
    "398": "Vykosa",
    "399": "Hanu's Compassion",
    "40": "Night's Silence",
    "400": "Blood Moon",
    "401": "Haven of Ursus",
    "402": "Moon Hunter",
    "403": "Savage Werewolf",
    "404": "Jailer's Tenacity",
    "405": "Bright-Throat's Boast",
    "406": "Dead-Water's Guile",
    "407": "Champion of the Hist",
    "408": "Grave-Stake Collector",
    "409": "Naga Shaman",
    "41": "Whitestrake's Retribution",
    "410": "Might of the Lost Legion",
    "411": "Gallant Charge",
    "412": "Radial Uppercut",
    "413": "Spectral Cloak",
    "414": "Virulent Shot",
    "415": "Wild Impulse",
    "416": "Mender's Ward",
    "417": "Indomitable Fury",
    "418": "Spell Strategist",
    "419": "Battlefield Acrobat",
    "420": "Soldier of Anguish",
    "421": "Steadfast Hero",
    "422": "Battalion Defender",
    "423": "Perfect Gallant Charge",
    "424": "Perfect Radial Uppercut",
    "425": "Perfect Spectral Cloak",
    "426": "Perfect Virulent Shot",
    "427": "Perfect Wild Impulse",
    "428": "Perfect Mender's Ward",
    "429": "Mighty Glacier",
    "43": "Armor of the Seducer",
    "430": "Tzogvin's Warband",
    "431": "Icy Conjuror",
    "432": "Stonekeeper",
    "433": "Frozen Watcher",
    "434": "Scavenging Demise",
    "435": "Auroran's Thunder",
    "436": "Symphony of Blades",
    "437": "Coldharbour's Favorite",
    "438": "Senche-raht's Grit",
    "439": "Vastarie's Tutelage",
    "44": "Vampire's Kiss",
    "440": "Crafty Alfiq",
    "441": "Vesture of Darloc Brae",
    "442": "Call of the Undertaker",
    "443": "Eye of Nahviintaas",
    "444": "False God's Devotion",
    "445": "Tooth of Lokkestiiz",
    "446": "Claw of Yolnakhriin",
    "448": "Perfected Eye of Nahviintaas",
    "449": "Perfected False God's Devotion",
    "450": "Perfected Tooth of Lokkestiiz",
    "451": "Perfected Claw of Yolnakhriin",
    "452": "Hollowfang Thirst",
    "453": "Dro'Zakar's Claws",
    "454": "Renald's Resolve",
    "455": "Z'en's Redress",
    "456": "Azureblight Reaper",
    "457": "Dragon's Defilement",
    "458": "Grundwulf",
    "459": "Maarselok",
    "46": "Noble Duelist's Silks",
    "465": "Senchal Defender",
    "466": "Marauder's Haste",
    "467": "Dragonguard Elite",
    "468": "Daring Corsair",
    "469": "Ancient Dragonguard",
    "47": "Robes of the Withered Hand",
    "470": "New Moon Acolyte",
    "471": "Hiti's Hearth",
    "472": "Titanborn Strength",
    "473": "Bani's Torment",
    "474": "Draugrkin's Grip",
    "475": "Aegis Caller",
    "476": "Grave Guardian",
    "478": "Mother Ciannait",
    "479": "Kjalnar's Nightmare",
    "48": "Magnus' Gift",
    "480": "Critical Riposte",
    "481": "Unchained Aggressor",
    "482": "Dauntless Combatant",
    "483": "Template_Drop_Magi",
    "484": "Template_Drop_Stamina",
    "485": "Template_Drop_Tank",
    "486": "Template_Drop_Healer",
    "487": "Winter's Respite",
    "488": "Venomous Smite",
    "489": "Eternal Vigor",
    "49": "Shadow of the Red Mountain",
    "490": "Stuhn's Favor",
    "491": "Dragon's Appetite",
    "492": "Kyne's Wind",
    "493": "Perfected Kyne's Wind",
    "494": "Vrol's Command",
    "495": "Perfected Vrol's Command",
    "496": "Roaring Opportunist",
    "497": "Perfected Roaring Opportunist",
    "498": "Yandir's Might",
    "499": "Perfected Yandir's Might",
    "50": "The Morag Tong",
    "500": "Bloodlord's Embrace (OLD)",
    "501": "Thrassian Stranglers",
    "502": "Snow Treaders (OLD)",
    "503": "Ring of the Wild Hunt",
    "504": "Malacath's Band of Brutality X",
    "505": "Torc of Tonal Constancy",
    "506": "Spell Parasite",
    "509": "Template_Drop_Healer P",
    "51": "Night Mother's Gaze",
    "510": "Template_Drop_Tank P",
    "511": "Template_Drop_Stamina P",
    "512": "Template_Drop_Magi P",
    "513": "Talfyg's Treachery",
    "514": "Unleashed Terror",
    "515": "Crimson Twilight",
    "516": "Elemental Catalyst",
    "517": "Kraglen's Howl",
    "518": "Arkasis's Genius",
    "519": "Snow Treaders",
    "52": "Beckoning Steel",
    "520": "Malacath's Band of Brutality",
    "521": "Bloodlord's Embrace",
    "522": "Perfected Merciless Charge",
    "523": "Perfected Rampaging Slash",
    "524": "Perfected Cruel Flurry",
    "525": "Perfected Thunderous Volley",
    "526": "Perfected Crushing Wall",
    "527": "Perfected Precise Regeneration",
    "528": "Perfected Titanic Cleave",
    "529": "Perfected Puncturing Remedy",
    "53": "The Ice Furnace",
    "530": "Perfected Stinging Slashes",
    "531": "Perfected Caustic Arrow",
    "532": "Perfected Destructive Impact",
    "533": "Perfected Grand Rejuvenation",
    "534": "Stone Husk",
    "535": "Lady Thorn",
    "536": "Radiant Bastion",
    "537": "Voidcaller",
    "538": "Witch-Knight's Defiance",
    "539": "Red Eagle's Fury",
    "54": "Ashen Grip",
    "540": "Legacy of Karth",
    "541": "Aetherial Ascension",
    "542": "Hex Siphon",
    "543": "Pestilent Host",
    "544": "Explosive Rebuke",
    "55": "Prayer Shawl",
    "557": "Executioner's Blade",
    "558": "Void Bash",
    "559": "Frenzied Momentum",
    "56": "Stendarr's Embrace",
    "560": "Point-Blank Snipe",
    "561": "Wrath of Elements",
    "562": "Force Overflow",
    "563": "Perfected Executioner's Blade",
    "564": "Perfected Void Bash",
    "565": "Perfected Frenzied Momentum",
    "566": "Perfected Point-Blank Snipe",
    "567": "Perfected Wrath of Elements",
    "568": "Perfected Force Overflow",
    "569": "True-Sworn Fury",
    "57": "Syrabane's Grip",
    "570": "Kinras's Wrath",
    "571": "Drake's Rush",
    "572": "Unleashed Ritualist",
    "573": "Dagon's Dominion",
    "574": "Foolkiller's Ward",
    "575": "Ring of the Pale Order",
    "576": "Pearls of Ehlnofey",
    "577": "Encrati's Behemoth",
    "578": "Baron Zaudrus",
    "579": "Frostbite",
    "58": "Hide of the Werewolf",
    "580": "Deadlands Assassin",
    "581": "Bog Raider",
    "582": "Hist Whisperer",
    "583": "Heartland Conqueror",
    "584": "Diamond's Victory",
    "585": "Saxhleel Champion",
    "586": "Sul-Xan's Torment",
    "587": "Bahsei's Mania",
    "588": "Stone-Talker's Oath",
    "589": "Perfected Saxhleel Champion",
    "59": "Kyne's Kiss",
    "590": "Perfected Sul-Xan's Torment",
    "591": "Perfected Bahsei's Mania",
    "592": "Perfected Stone-Talker's Oath",
    "593": "Gaze of Sithis",
    "594": "Harpooner's Wading Kilt",
    "596": "Death Dealer's Fete",
    "597": "Shapeshifter's Chain",
    "598": "Zoal the Ever-Wakeful",
    "599": "Immolator Charr",
    "60": "Darkstride",
    "600": "Glorgoloch the Destroyer",
    "602": "Crimson Oath's Rive",
    "603": "Scorion's Feast",
    "604": "Rush of Agony",
    "605": "Silver Rose Vigil",
    "606": "Thunder Caller",
    "607": "Grisly Gourmet",
    "608": "Prior Thierric",
    "609": "Magma Incarnate",
    "61": "Dreugh King Slayer",
    "610": "Wretched Vitality",
    "611": "Deadlands Demolisher",
    "612": "Iron Flask",
    "613": "Eye of the Grasp",
    "614": "Hexos' Ward",
    "615": "Kynmarcher's Cruelty",
    "616": "Dark Convergence",
    "617": "Plaguebreak",
    "618": "Hrothgar's Chill",
    "619": "Maligalig's Maelstrom",
    "62": "Hatchling's Shell",
    "620": "Gryphon's Reprisal",
    "621": "Glacial Guardian",
    "622": "Turning Tide",
    "623": "Storm-Cursed's Revenge",
    "624": "Spriggan\’s Vigor",
    "625": "Markyn Ring of Majesty",
    "626": "Belharza's Band",
    "627": "Spaulder of Ruin",
    "629": "Rallying Cry",
    "63": "The Juggernaut",
    "630": "Hew and Sunder",
    "631": "Enervating Aura",
    "632": "Kargaeda",
    "633": "Nazaray",
    "634": "Nunatak",
    "635": "Lady Malydga",
    "636": "Baron Thirsk",
    "64": "Shadow Dancer's Raiment",
    "640": "Order's Wrath",
    "641": "Serpent's Disdain",
    "642": "Druid's Braid",
    "643": "Blessing of High Isle",
    "644": "Steadfast's Mettle",
    "645": "Systres' Scowl",
    "646": "Whorl of the Depths",
    "647": "Coral Riptide",
    "648": "Pearlescent Ward",
    "649": "Pillager's Profit",
    "65": "Bloodthorn's Touch",
    "650": "Perfected Pillager's Profit",
    "651": "Perfected Pearlescent Ward",
    "652": "Perfected Coral Riptide",
    "653": "Perfected Whorl of the Depths",
    "654": "Mora's Whispers",
    "655": "Dov-rha Sabatons",
    "656": "Lefthander's Aegis Belt",
    "657": "Sea-Serpent's Coil",
    "658": "Oakensoul Ring",
    "66": "Robes of the Hist",
    "660": "Deeproot Zeal",
    "661": "Stone's Accord",
    "662": "Rage of the Ursauk",
    "663": "Pangrit Denmother",
    "664": "Grave Inevitability",
    "665": "Phylactery's Grasp",
    "666": "Archdruid Devyric",
    "667": "Euphotic Gatekeeper",
    "668": "Langour of Peryite",
    "669": "Nocturnal's Ploy",
    "67": "Shadow Walker",
    "670": "Mara\’s Balm",
    "671": "Back-Alley Gourmand",
    "672": "Phoenix Moth Theurge",
    "673": "Bastion of Draoife",
    "674": "Faun's Lark Cladding",
    "675": "Stormweaver's Cavort",
    "676": "Syrabane's Ward",
    "677": "Chimera's Rebuke",
    "678": "Old Growth Brewer",
    "679": "Claw of the Forest Wraith",
    "68": "Stygian",
    "680": "Ritemaster's Bond",
    "681": "Nix-Hound's Howl",
    "682": "Telvanni Enforcer",
    "683": "Roksa the Warped",
    "684": "Runecarver\’s Blaze",
    "685": "Apocryphal Inspiration",
    "686": "Abyssal Brace",
    "687": "Ozezan the Inferno",
    "688": "Snake in the Stars",
    "689": "Shell Splitter",
    "69": "Ranger's Gait",
    "690": "Judgement of Akatosh",
    "691": "Cryptcanon Vestments",
    "692": "Esoteric Environment Greaves",
    "693": "Torc of the Last Ayleid King",
    "694": "Velothi Ur-Mage's Amulet",
    "695": "Shattered Fate",
    "696": "Telvanni Efficiency",
    "697": "Seeker Synthesis",
    "698": "Vivec's Duality",
    "699": "Camonna Tong",
    "70": "Seventh Legion Brute",
    "700": "Adamant Lurker",
    "701": "Peace and Serenity",
    "702": "Ansuul's Torment",
    "703": "Test of Resolve",
    "704": "Transformative Hope",
    "705": "Perfected Transformative Hope",
    "706": "Perfected Test of Resolve",
    "707": "Perfected Ansuul's Torment",
    "708": "Perfected Peace and Serenity",
    "71": "Durok's Bane",
    "711": "Jerall Mountains Warchief",
    "712": "Nibenay Bay Battlereeve",
    "713": "Colovian Highlands General",
    "72": "Nikulas' Heavy Armor",
    "722": "Reawakened Hierophant",
    "723": "Basalt-Blooded Warrior",
    "724": "Nobility in Decay",
    "726": "Soulcleaver",
    "727": "Monolith of Storms",
    "728": "Wrathsun",
    "729": "Gardener of Seasons",
    "73": "Oblivion's Foe",
    "730": "Cinders of Anthelmir",
    "731": "Sluthrug's Hunger",
    "732": "Black-Grove Grounding",
    "734": "Anthelmir's Construct",
    "735": "Blind Path Induction",
    "736": "Tarnished Nightmare",
    "737": "Reflected Fury",
    "738": "The Blind",
    "74": "Spectre's Eye",
    "75": "Torug's Pact",
    "754": "Oakfather's Retribution",
    "755": "Blunted Blades",
    "756": "Baan Dar's Blessing",
    "757": "Symmetry of the Weald",
    "758": "Macabre Vintage",
    "759": "Ayleid Rufuge",
    "76": "Robes of Alteration Mastery",
    "760": "Rourken Steamguards",
    "761": "The Shadow Queen's Cowl",
    "762": "The Saint and the Seducer",
    "763": "Tharriker's Strike",
    "764": "Highland Sentinel",
    "765": "Threads of War",
    "766": "Mora Scribe's Thesis",
    "767": "Slivers of the Null Arca",
    "768": "Lucent Echoes",
    "769": "Xoryn's Masterpiece",
    "77": "Crusader",
    "770": "Perfected Xoryn's Masterpiece",
    "771": "Perfected Lucent Echoes",
    "772": "Perfected Slivers of the Null Arca",
    "773": "Perfected Mora Scribe's Thesis",
    "775": "Spattering Disjunction",
    "776": "Pyrebrand",
    "777": "Corpseburster",
    "778": "Umbral Edge",
    "779": "Beacon of Oblivion",
    "78": "Hist Bark",
    "780": "Aetheric Lance",
    "781": "Aerie's Cry",
    "782": "Tracker's Lash",
    "783": "Shared Pain",
    "784": "Siegemaster'\s Focus",
    "79": "Willow's Path",
    "791": "Bulwark Ruination",
    "792": "Farstrider",
    "793": "Netch Oil",
    "794": "Vandorallen's Resonance",
    "795": "Jerensi's Bladestorm",
    "796": "Lucilla's Windshield",
    "797": "Squall of Retribution",
    "798": "Heroic Unity",
    "799": "Fledgling's Nest",
    "80": "Hunding's Rage",
    "800": "Noxious Boulder",
    "801": "Orpheon the Tactician",
    "802": "Arkay's Charity",
    "803": "Lamp Knight's Art",
    "804": "Blackfeather Flight",
    "805": "Three Queens Wellspring",
    "806": "Death-Dancer",
    "807": "Full Belly Barricade",
    "808": "Shared Burden",
    "809": "Tide-Born Wildstalker",
    "81": "Song of Lamae",
    "810": "Fellowship's Fortitude",
    "811": "Mad God's Dancing Shoes",
    "812": "Rakkhat's Voidmantle",
    "813": "Monomyth Reforged",
    "814": "Harmony in Chaos",
    "815": "Kazpian's Cruel Signet",
    "816": "Dolorous Arena",
    "817": "Recovery Convergence",
    "818": "Perfected Recovery Convergence",
    "819": "Perfected Dolorous Arena",
    "82": "Alessia's Bulwark",
    "820": "Perfected Kazpian's Cruel Signet",
    "821": "Perfected Harmony in Chaos",
    "83": "Elf Bane",
    "84": "Orgnum's Scales",
    "85": "Almalexia's Mercy",
    "86": "Queen's Elegance",
    "87": "Eyes of Mara",
    "88": "Robes of Destruction Mastery",
    "89": "Sentry",
    "90": "Senche's Bite",
    "91": "Oblivion's Edge",
    "92": "Kagrenac's Hope",
    "93": "Storm Knight's Plate",
    "94": "Meridia's Blessed Armor",
    "95": "Shalidor's Curse",
    "96": "Armor of Truth",
    "97": "The Arch-Mage",
    "98": "Necropotence",
    "99": "Salvation",
}

# Set Name to Set ID mapping
SET_NAME_TO_ID: Dict[str, str] = {
    "Abyssal Brace": "686",
    "Adamant Lurker": "700",
    "Adept Rider": "385",
    "Aegis Caller": "475",
    "Aegis of Galenwe": "388",
    "Aerie's Cry": "781",
    "Aetherial Ascension": "541",
    "Aetheric Lance": "780",
    "Affliction": "101",
    "Agility": "206",
    "Akaviri Dragonguard": "21",
    "Alessia's Bulwark": "82",
    "Alessian Order": "39",
    "Almalexia's Mercy": "85",
    "Amber Plasm": "258",
    "Ancient Dragonguard": "469",
    "Ansuul's Torment": "702",
    "Anthelmir's Construct": "734",
    "Apocryphal Inspiration": "685",
    "Archdruid Devyric": "666",
    "Archer's Mind": "23",
    "Arkasis's Genius": "518",
    "Arkay's Charity": "802",
    "Armor Master": "178",
    "Armor of Truth": "96",
    "Armor of the Code": "209",
    "Armor of the Seducer": "43",
    "Armor of the Trainee": "281",
    "Armor of the Veiled Heritance": "36",
    "Arms of Infernace": "120",
    "Arms of Relequen": "389",
    "Arms of the Ancestors": "121",
    "Ashen Grip": "54",
    "Aspect of Mazzatun": "260",
    "Assassin's Guile": "323",
    "Auroran's Thunder": "435",
    "Automated Defense": "330",
    "Ayleid Rufuge": "759",
    "Azureblight Reaper": "456",
    "Baan Dar's Blessing": "756",
    "Back-Alley Gourmand": "671",
    "Bahraha's Curse": "227",
    "Bahsei's Mania": "587",
    "Balorgh": "397",
    "Bani's Torment": "473",
    "Barkskin": "28",
    "Baron Thirsk": "636",
    "Baron Zaudrus": "578",
    "Basalt-Blooded Warrior": "723",
    "Bastion of Draoife": "673",
    "Bastion of the Heartland": "131",
    "Battalion Defender": "422",
    "Battlefield Acrobat": "419",
    "Beacon of Oblivion": "779",
    "Beckoning Steel": "52",
    "Beekeeper's Gear": "288",
    "Belharza's Band": "626",
    "Berserking Warrior": "137",
    "Black Rose": "179",
    "Black-Grove Grounding": "732",
    "Blackfeather Flight": "804",
    "Blessing of High Isle": "643",
    "Blessing of the Potentates": "128",
    "Blind Path Induction": "735",
    "Blood Moon": "400",
    "Blood Spawn": "163",
    "Blooddrinker": "339",
    "Bloodlord's Embrace": "521",
    "Bloodlord's Embrace (OLD)": "500",
    "Bloodthorn's Touch": "65",
    "Blunted Blades": "755",
    "Bog Raider": "581",
    "Bone Pirate's Tatters": "308",
    "Brands of Imperium": "184",
    "Briarheart": "212",
    "Bright-Throat's Boast": "405",
    "Broken Soul": "381",
    "Buffer of the Swift": "133",
    "Bulwark Ruination": "791",
    "Burning Spellweave": "160",
    "Call of the Undertaker": "442",
    "Caluurion's Legacy": "343",
    "Camonna Tong": "699",
    "Caustic Arrow": "316",
    "Champion of the Hist": "407",
    "Chaotic Whirlwind": "365",
    "Chaotic Whirlwind (Perfected)": "359",
    "Chimera's Rebuke": "677",
    "Chokethorn": "269",
    "Cinders of Anthelmir": "730",
    "Claw of Yolnakhriin": "446",
    "Claw of the Forest Wraith": "679",
    "Clever Alchemist": "225",
    "Coldharbour's Favorite": "437",
    "Colovian Highlands General": "713",
    "Combat Physician": "194",
    "Concentrated Force": "367",
    "Concentrated Force (Perfected)": "361",
    "Coral Riptide": "647",
    "Corpseburster": "777",
    "Coward's Gear": "327",
    "Crafty Alfiq": "440",
    "Crest of Cyrodiil": "113",
    "Crimson Oath's Rive": "602",
    "Crimson Twilight": "515",
    "Critical Riposte": "480",
    "Cruel Flurry": "371",
    "Crusader": "77",
    "Crushing Wall": "373",
    "Cryptcanon Vestments": "691",
    "Curse Eater": "104",
    "Curse of Doylemish": "348",
    "Daedric Trickery": "324",
    "Dagon's Dominion": "573",
    "Daring Corsair": "468",
    "Dark Convergence": "616",
    "Darkstride": "60",
    "Dauntless Combatant": "482",
    "Dead-Water's Guile": "406",
    "Deadlands Assassin": "580",
    "Deadlands Demolisher": "611",
    "Deadly Strike": "127",
    "Death Dealer's Fete": "596",
    "Death's Wind": "37",
    "Death-Dancer": "806",
    "Deeproot Zeal": "660",
    "Defending Warrior": "138",
    "Defensive Position": "364",
    "Defensive Position (Perfected)": "358",
    "Defiler": "321",
    "Desert Rose": "25",
    "Destructive Impact": "317",
    "Destructive Mage": "140",
    "Diamond's Victory": "584",
    "Disciplined Slash": "363",
    "Disciplined Slash (Perfected)": "357",
    "Dolorous Arena": "816",
    "Domihaus": "342",
    "Dov-rha Sabatons": "655",
    "Dragon's Appetite": "491",
    "Dragon's Defilement": "457",
    "Dragonguard Elite": "467",
    "Drake's Rush": "571",
    "Draugr Hulk": "307",
    "Draugr's Heritage": "135",
    "Draugr's Rest": "335",
    "Draugrkin's Grip": "474",
    "Dreamer's Mantle": "22",
    "Dreugh King Slayer": "61",
    "Dro'Zakar's Claws": "453",
    "Druid's Braid": "642",
    "Duneripper's Scales": "102",
    "Durok's Bane": "71",
    "Eagle Eye": "130",
    "Earthgore": "341",
    "Ebon Armory": "122",
    "Elemental Catalyst": "516",
    "Elemental Succession": "215",
    "Elf Bane": "83",
    "Embershield": "158",
    "Encrati's Behemoth": "577",
    "Endurance": "204",
    "Enervating Aura": "631",
    "Engine Guardian": "166",
    "Esoteric Environment Greaves": "692",
    "Essence Thief": "198",
    "Eternal Hunt": "226",
    "Eternal Vigor": "489",
    "Eternal Warrior": "171",
    "Euphotic Gatekeeper": "667",
    "Executioner's Blade": "557",
    "Explosive Rebuke": "544",
    "Eye of Nahviintaas": "443",
    "Eye of the Grasp": "613",
    "Eyes of Mara": "87",
    "False God's Devotion": "444",
    "Farstrider": "792",
    "Fasalla's Guile": "238",
    "Faun's Lark Cladding": "674",
    "Fellowship's Fortitude": "810",
    "Fiord's Legacy": "27",
    "Flame Blossom": "338",
    "Flanking Strategist": "244",
    "Fledgling's Nest": "799",
    "Foolkiller's Ward": "574",
    "Footman's Fortune": "24",
    "Force Overflow": "562",
    "Fortified Brass": "352",
    "Frenzied Momentum": "559",
    "Frostbite": "579",
    "Frozen Watcher": "433",
    "Full Belly Barricade": "807",
    "Galerion's Revenge": "246",
    "Gallant Charge": "411",
    "Gardener of Seasons": "729",
    "Gaze of Sithis": "593",
    "Giant Spider": "264",
    "Glacial Guardian": "621",
    "Glorgoloch the Destroyer": "600",
    "Glorious Defender": "213",
    "Gossamer": "261",
    "Grace of Gloom": "382",
    "Grace of the Ancients": "126",
    "Grand Rejuvenation": "318",
    "Grave Guardian": "476",
    "Grave Inevitability": "664",
    "Grave-Stake Collector": "408",
    "Green Pact": "287",
    "Grisly Gourmet": "607",
    "Grothdarr": "280",
    "Grundwulf": "458",
    "Gryphon's Ferocity": "383",
    "Gryphon's Reprisal": "620",
    "Hagraven's Garden": "340",
    "Hand of Mephala": "263",
    "Hanu's Compassion": "399",
    "Harmony in Chaos": "814",
    "Harpooner's Wading Kilt": "594",
    "Hatchling's Shell": "62",
    "Haven of Ursus": "401",
    "Hawk's Eye": "100",
    "Healer's Habit": "32",
    "Healing Mage": "141",
    "Heartland Conqueror": "583",
    "Heem-Jas' Retribution": "259",
    "Heroic Unity": "798",
    "Hew and Sunder": "630",
    "Hex Siphon": "542",
    "Hexos' Ward": "614",
    "Hide of Morihaus": "243",
    "Hide of the Werewolf": "58",
    "Highland Sentinel": "764",
    "Hircine's Veneer": "123",
    "Hist Bark": "78",
    "Hist Whisperer": "582",
    "Hiti's Hearth": "471",
    "Hollowfang Thirst": "452",
    "Hrothgar's Chill": "618",
    "Hunding's Rage": "80",
    "Hunt Leader": "216",
    "Iceheart": "274",
    "Icy Conjuror": "431",
    "Ilambris": "273",
    "Immolator Charr": "599",
    "Immortal Warrior": "136",
    "Imperial Physique": "253",
    "Impregnable Armor": "334",
    "Indomitable Fury": "417",
    "Infallible Mage": "172",
    "Infernal Guardian": "272",
    "Innate Axiom": "351",
    "Inventor's Guard": "333",
    "Iron Flask": "612",
    "Ironblood": "337",
    "Jailbreaker": "295",
    "Jailer's Tenacity": "404",
    "Jerall Mountains Warchief": "711",
    "Jerensi's Bladestorm": "795",
    "Jolting Arms": "186",
    "Jorvuld's Guidance": "346",
    "Judgement of Akatosh": "690",
    "Kagrenac's Hope": "92",
    "Kargaeda": "632",
    "Kazpian's Cruel Signet": "815",
    "Kinras's Wrath": "570",
    "Kjalnar's Nightmare": "479",
    "Knight Slayer": "328",
    "Knight-errant's Mail": "309",
    "Knightmare": "35",
    "Kra'gh": "266",
    "Kraglen's Howl": "517",
    "Kvatch Gladiator": "240",
    "Kyne's Kiss": "59",
    "Kyne's Wind": "492",
    "Kynmarcher's Cruelty": "615",
    "Lady Malydga": "635",
    "Lady Thorn": "535",
    "Lamia's Song": "303",
    "Lamp Knight's Art": "803",
    "Langour of Peryite": "668",
    "Law of Julianos": "207",
    "Leeching Plate": "196",
    "Lefthander's Aegis Belt": "656",
    "Legacy of Karth": "540",
    "Leki's Focus": "237",
    "Leviathan": "302",
    "Light Speaker": "298",
    "Light of Cyrodiil": "109",
    "Livewire": "356",
    "Lord Warden": "164",
    "Lucent Echoes": "768",
    "Lucilla's Windshield": "796",
    "Lunar Bastion": "231",
    "Maarselok": "459",
    "Macabre Vintage": "758",
    "Mad God's Dancing Shoes": "811",
    "Mad Tinkerer": "354",
    "Magicka Furnace": "103",
    "Magma Incarnate": "609",
    "Magnus' Gift": "48",
    "Malacath's Band of Brutality": "520",
    "Malacath's Band of Brutality X": "504",
    "Maligalig's Maelstrom": "619",
    "Mantle of Siroria": "390",
    "Mara\’s Balm": "670",
    "Marauder's Haste": "466",
    "Mark of the Pariah": "210",
    "Marksman's Crest": "234",
    "Markyn Ring of Majesty": "625",
    "Master Architect": "332",
    "Maw of the Infernal": "170",
    "Mechanical Acuity": "353",
    "Medusa": "304",
    "Mender's Ward": "416",
    "Merciless Charge": "369",
    "Meridia's Blessed Armor": "94",
    "Meritorious Service": "181",
    "Might of the Lost Legion": "410",
    "Mighty Chudan": "256",
    "Mighty Glacier": "429",
    "Molag Kena": "183",
    "Monolith of Storms": "727",
    "Monomyth Reforged": "813",
    "Moon Hunter": "402",
    "Moondancer": "230",
    "Mora Scribe's Thesis": "766",
    "Mora's Whispers": "654",
    "Morkuldin": "219",
    "Mother Ciannait": "478",
    "Mother's Sorrow": "292",
    "Naga Shaman": "409",
    "Nazaray": "633",
    "Necropotence": "98",
    "Nerien'eth": "168",
    "Netch Oil": "793",
    "Netch's Touch": "300",
    "New Moon Acolyte": "470",
    "Nibenay Bay Battlereeve": "712",
    "Night Mother's Embrace": "34",
    "Night Mother's Gaze": "51",
    "Night Terror": "112",
    "Night's Silence": "40",
    "Nightflame": "167",
    "Nikulas' Heavy Armor": "72",
    "Nix-Hound's Howl": "681",
    "Nobility in Decay": "724",
    "Noble Duelist's Silks": "46",
    "Noble's Conquest": "176",
    "Nocturnal's Favor": "387",
    "Nocturnal's Ploy": "669",
    "Noxious Boulder": "800",
    "Nunatak": "634",
    "Oakensoul Ring": "658",
    "Oakfather's Retribution": "754",
    "Oblivion's Edge": "91",
    "Oblivion's Foe": "73",
    "Old Growth Brewer": "678",
    "Order of Diagna": "284",
    "Order's Wrath": "640",
    "Orgnum's Scales": "84",
    "Orpheon the Tactician": "801",
    "Overwhelming Surge": "193",
    "Ozezan the Inferno": "687",
    "Pangrit Denmother": "663",
    "Para Bellum": "214",
    "Peace and Serenity": "701",
    "Pearlescent Ward": "648",
    "Pearls of Ehlnofey": "576",
    "Pelinal's Aptitude": "242",
    "Perfect Aegis of Galenwe": "392",
    "Perfect Arms of Relequen": "393",
    "Perfect Gallant Charge": "423",
    "Perfect Mantle of Siroria": "394",
    "Perfect Mender's Ward": "428",
    "Perfect Radial Uppercut": "424",
    "Perfect Spectral Cloak": "425",
    "Perfect Vestment of Olorime": "395",
    "Perfect Virulent Shot": "426",
    "Perfect Wild Impulse": "427",
    "Perfected Ansuul's Torment": "707",
    "Perfected Bahsei's Mania": "591",
    "Perfected Caustic Arrow": "531",
    "Perfected Claw of Yolnakhriin": "451",
    "Perfected Coral Riptide": "652",
    "Perfected Cruel Flurry": "524",
    "Perfected Crushing Wall": "526",
    "Perfected Destructive Impact": "532",
    "Perfected Dolorous Arena": "819",
    "Perfected Executioner's Blade": "563",
    "Perfected Eye of Nahviintaas": "448",
    "Perfected False God's Devotion": "449",
    "Perfected Force Overflow": "568",
    "Perfected Frenzied Momentum": "565",
    "Perfected Grand Rejuvenation": "533",
    "Perfected Harmony in Chaos": "821",
    "Perfected Kazpian's Cruel Signet": "820",
    "Perfected Kyne's Wind": "493",
    "Perfected Lucent Echoes": "771",
    "Perfected Merciless Charge": "522",
    "Perfected Mora Scribe's Thesis": "773",
    "Perfected Peace and Serenity": "708",
    "Perfected Pearlescent Ward": "651",
    "Perfected Pillager's Profit": "650",
    "Perfected Point-Blank Snipe": "566",
    "Perfected Precise Regeneration": "527",
    "Perfected Puncturing Remedy": "529",
    "Perfected Rampaging Slash": "523",
    "Perfected Recovery Convergence": "818",
    "Perfected Roaring Opportunist": "497",
    "Perfected Saxhleel Champion": "589",
    "Perfected Slivers of the Null Arca": "772",
    "Perfected Stinging Slashes": "530",
    "Perfected Stone-Talker's Oath": "592",
    "Perfected Sul-Xan's Torment": "590",
    "Perfected Test of Resolve": "706",
    "Perfected Thunderous Volley": "525",
    "Perfected Titanic Cleave": "528",
    "Perfected Tooth of Lokkestiiz": "450",
    "Perfected Transformative Hope": "705",
    "Perfected Void Bash": "564",
    "Perfected Vrol's Command": "495",
    "Perfected Whorl of the Depths": "653",
    "Perfected Wrath of Elements": "567",
    "Perfected Xoryn's Masterpiece": "770",
    "Perfected Yandir's Might": "499",
    "Permafrost": "211",
    "Pestilent Host": "543",
    "Phoenix": "200",
    "Phoenix Moth Theurge": "672",
    "Phylactery's Grasp": "665",
    "Piercing Spray": "366",
    "Piercing Spray (Perfected)": "360",
    "Pillager's Profit": "649",
    "Pillar of Nirn": "336",
    "Pirate Skeleton": "277",
    "Plague Doctor": "293",
    "Plague Slinger": "347",
    "Plaguebreak": "617",
    "Point-Blank Snipe": "560",
    "Poisonous Serpent": "143",
    "Powerful Assault": "180",
    "Prayer Shawl": "55",
    "Precise Regeneration": "374",
    "Prior Thierric": "608",
    "Prisoner's Rags": "26",
    "Prophet's": "380",
    "Puncturing Remedy": "314",
    "Pyrebrand": "776",
    "Queen's Elegance": "86",
    "Quick Serpent": "142",
    "Radial Uppercut": "412",
    "Radiant Bastion": "536",
    "Rage of the Ursauk": "662",
    "Rakkhat's Voidmantle": "812",
    "Rallying Cry": "629",
    "Rampaging Slash": "370",
    "Ranger's Gait": "69",
    "Rattlecage": "311",
    "Ravager": "108",
    "Reactive Armor": "201",
    "Reawakened Hierophant": "722",
    "Recovery Convergence": "817",
    "Red Eagle's Fury": "539",
    "Redistributor": "177",
    "Reflected Fury": "737",
    "Relics of the Physician, Ansur": "117",
    "Relics of the Rebellion": "119",
    "Renald's Resolve": "454",
    "Ring of the Pale Order": "575",
    "Ring of the Wild Hunt": "503",
    "Ritemaster's Bond": "680",
    "Roar of Alkosh": "232",
    "Roaring Opportunist": "496",
    "Robes of Alteration Mastery": "76",
    "Robes of Destruction Mastery": "88",
    "Robes of Transmutation": "235",
    "Robes of the Hist": "66",
    "Robes of the Withered Hand": "47",
    "Roksa the Warped": "683",
    "Rourken Steamguards": "760",
    "Runecarver\’s Blaze": "684",
    "Rush of Agony": "604",
    "Salvation": "99",
    "Sanctuary": "110",
    "Savage Werewolf": "403",
    "Saxhleel Champion": "585",
    "Scathing Mage": "190",
    "Scavenging Demise": "434",
    "Scorion's Feast": "603",
    "Scourge Harvester": "165",
    "Sea-Serpent's Coil": "657",
    "Seeker Synthesis": "697",
    "Selene": "279",
    "Sellistrix": "271",
    "Senchal Defender": "465",
    "Senche's Bite": "90",
    "Senche-raht's Grit": "438",
    "Sentinel of Rkugamz": "268",
    "Sentry": "89",
    "Sergeant's Mail": "29",
    "Serpent's Disdain": "641",
    "Seventh Legion Brute": "70",
    "Shacklebreaker": "325",
    "Shadow Dancer's Raiment": "64",
    "Shadow Walker": "67",
    "Shadow of the Red Mountain": "49",
    "Shadowrend": "265",
    "Shalidor's Curse": "95",
    "Shalk Exoskeleton": "291",
    "Shapeshifter's Chain": "597",
    "Shared Burden": "808",
    "Shared Pain": "783",
    "Shattered Fate": "695",
    "Sheer Venom": "195",
    "Shell Splitter": "689",
    "Shield Breaker": "199",
    "Shield of the Valiant": "132",
    "Shroud of the Lich": "134",
    "Siegemaster'\s Focus": "784",
    "Silks of the Sun": "31",
    "Silver Rose Vigil": "605",
    "Sithis' Touch": "245",
    "Skooma Smuggler": "290",
    "Slimecraw": "270",
    "Slivers of the Null Arca": "767",
    "Sload's Semblance": "386",
    "Sluthrug's Hunger": "731",
    "Snake in the Stars": "688",
    "Snow Treaders": "519",
    "Snow Treaders (OLD)": "502",
    "Soldier of Anguish": "420",
    "Song of Lamae": "81",
    "Soulcleaver": "726",
    "Soulshine": "114",
    "Spattering Disjunction": "775",
    "Spaulder of Ruin": "627",
    "Spawn of Mephala": "162",
    "Spectral Cloak": "413",
    "Spectre's Eye": "74",
    "Spell Parasite": "506",
    "Spell Power Cure": "185",
    "Spell Strategist": "418",
    "Spelunker": "296",
    "Spider Cultist Cowl": "297",
    "Spinner's Garments": "289",
    "Spriggan's Thorns": "286",
    "Spriggan\’s Vigor": "624",
    "Squall of Retribution": "797",
    "Steadfast Hero": "421",
    "Steadfast's Mettle": "644",
    "Stendarr's Embrace": "56",
    "Stinging Slashes": "315",
    "Stone Husk": "534",
    "Stone's Accord": "661",
    "Stone-Talker's Oath": "588",
    "Stonekeeper": "432",
    "Storm Knight's Plate": "93",
    "Storm Master": "188",
    "Storm-Cursed's Revenge": "623",
    "Stormfist": "275",
    "Stormweaver's Cavort": "675",
    "Strength of the Automaton": "301",
    "Stuhn's Favor": "490",
    "Stygian": "68",
    "Sul-Xan's Torment": "586",
    "Sunderflame": "159",
    "Swamp Raider": "187",
    "Swarm Mother": "267",
    "Sword Dancer": "310",
    "Sword-Singer": "283",
    "Symmetry of the Weald": "757",
    "Symphony of Blades": "436",
    "Syrabane's Grip": "57",
    "Syrabane's Ward": "676",
    "Systres' Scowl": "645",
    "Syvarra's Scales": "228",
    "Talfyg's Treachery": "513",
    "Tarnished Nightmare": "736",
    "Tava's Favor": "224",
    "Telvanni Efficiency": "696",
    "Telvanni Enforcer": "682",
    "Template_Drop_Healer": "486",
    "Template_Drop_Healer P": "509",
    "Template_Drop_Magi": "483",
    "Template_Drop_Magi P": "512",
    "Template_Drop_Stamina": "484",
    "Template_Drop_Stamina P": "511",
    "Template_Drop_Tank": "485",
    "Template_Drop_Tank P": "510",
    "Test of Resolve": "703",
    "Tharriker's Strike": "763",
    "The Arch-Mage": "97",
    "The Blind": "738",
    "The Destruction Suite": "116",
    "The Ice Furnace": "53",
    "The Juggernaut": "63",
    "The Morag Tong": "50",
    "The Saint and the Seducer": "762",
    "The Shadow Queen's Cowl": "761",
    "The Troll King": "278",
    "The Worm's Raiment": "124",
    "Thews of the Harbinger": "248",
    "Thrassian Stranglers": "501",
    "Threads of War": "765",
    "Three Queens Wellspring": "805",
    "Thunder Caller": "606",
    "Thunderbug's Carapace": "30",
    "Thunderous Volley": "372",
    "Thurvokun": "349",
    "Tide-Born Wildstalker": "809",
    "Timeless Blessing": "368",
    "Timeless Blessing (Perfected)": "362",
    "Titanborn Strength": "472",
    "Titanic Cleave": "313",
    "Tooth of Lokkestiiz": "445",
    "Toothrow": "299",
    "Torc of Tonal Constancy": "505",
    "Torc of the Last Ayleid King": "693",
    "Tormentor": "197",
    "Torug's Pact": "75",
    "Tracker's Lash": "782",
    "Transformative Hope": "704",
    "Trappings of Invigoration": "344",
    "Treasure Hunter": "305",
    "Treasures of the Earthforge": "118",
    "Tremorscale": "276",
    "Trial by Fire": "208",
    "Trinimac's Valor": "218",
    "True-Sworn Fury": "569",
    "Turning Tide": "622",
    "Twice-Born Star": "161",
    "Twice-Fanged Serpent": "144",
    "Twilight Remedy": "229",
    "Twilight's Embrace": "38",
    "Twin Sisters": "105",
    "Tzogvin's Warband": "430",
    "Ulfnor's Favor": "345",
    "Umbral Edge": "778",
    "Unchained Aggressor": "481",
    "Undaunted Bastion": "155",
    "Undaunted Infiltrator": "156",
    "Undaunted Unweaver": "157",
    "Unfathomable Darkness": "355",
    "Unleashed Ritualist": "572",
    "Unleashed Terror": "514",
    "Valkyn Skoria": "169",
    "Vampire Cloak": "282",
    "Vampire Lord": "285",
    "Vampire's Kiss": "44",
    "Vandorallen's Resonance": "794",
    "Vanguard's Challenge": "326",
    "Varen's Legacy": "241",
    "Vastarie's Tutelage": "439",
    "Velidreth": "257",
    "Velothi Ur-Mage's Amulet": "694",
    "Vengeance Leech": "129",
    "Venomous Smite": "488",
    "Vestment of Olorime": "391",
    "Vestments of the Warlock": "19",
    "Vesture of Darloc Brae": "441",
    "Vicecanon of Venom": "247",
    "Vicious Death": "236",
    "Vicious Serpent": "173",
    "Viper's Sting": "33",
    "Virulent Shot": "414",
    "Vivec's Duality": "698",
    "Void Bash": "558",
    "Voidcaller": "537",
    "Vrol's Command": "494",
    "Vykosa": "398",
    "War Machine": "331",
    "War Maiden": "320",
    "Ward of Cyrodiil": "111",
    "Warrior's Fury": "239",
    "Warrior-Poet": "322",
    "Way of Air": "146",
    "Way of Fire": "145",
    "Way of Martial Knowledge": "147",
    "Way of the Arena": "148",
    "Whitestrake's Retribution": "41",
    "Whorl of the Depths": "646",
    "Widowmaker": "262",
    "Wild Impulse": "415",
    "Wilderqueen's Arch": "106",
    "Willow's Path": "79",
    "Willpower": "205",
    "Winter's Respite": "487",
    "Winterborn": "217",
    "Wisdom of Vanus": "384",
    "Wise Mage": "139",
    "Witch-Knight's Defiance": "538",
    "Witchman Armor": "20",
    "Wizard's Riposte": "329",
    "Wrath of Elements": "561",
    "Wrath of the Imperium": "125",
    "Wrathsun": "728",
    "Wretched Vitality": "610",
    "Wyrd Tree's Blessing": "107",
    "Xoryn's Masterpiece": "769",
    "Yandir's Might": "498",
    "Ysgramor's Birthright": "294",
    "Z'en's Redress": "455",
    "Zaan": "350",
    "Zoal the Ever-Wakeful": "598",
}

# Detailed set information
SET_INFO: Dict[str, Dict] = {
    "Abyssal Brace": {
        "set_id": "686",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Adamant Lurker": {
        "set_id": "700",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Adept Rider": {
        "set_id": "385",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Aegis Caller": {
        "set_id": "475",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Aegis of Galenwe": {
        "set_id": "388",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Aerie's Cry": {
        "set_id": "781",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Warden",
        "items": [],
        "abilities": []
    },
    "Aetherial Ascension": {
        "set_id": "541",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Aetheric Lance": {
        "set_id": "780",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Templar",
        "items": [],
        "abilities": []
    },
    "Affliction": {
        "set_id": "101",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Agility": {
        "set_id": "206",
        "set_type": "LIBSETS_SETTYPE_DAILYRANDOMDUNGEONANDICREWARD",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Akaviri Dragonguard": {
        "set_id": "21",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Alessia's Bulwark": {
        "set_id": "82",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Alessian Order": {
        "set_id": "39",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Almalexia's Mercy": {
        "set_id": "85",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Amber Plasm": {
        "set_id": "258",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ancient Dragonguard": {
        "set_id": "469",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ansuul's Torment": {
        "set_id": "702",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Anthelmir's Construct": {
        "set_id": "734",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Apocryphal Inspiration": {
        "set_id": "685",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Archdruid Devyric": {
        "set_id": "666",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Archer's Mind": {
        "set_id": "23",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Arkasis's Genius": {
        "set_id": "518",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Arkay's Charity": {
        "set_id": "802",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Armor Master": {
        "set_id": "178",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Armor of Truth": {
        "set_id": "96",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Armor of the Code": {
        "set_id": "209",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "Not in the game (anymore)",
        "items": [],
        "abilities": []
    },
    "Armor of the Seducer": {
        "set_id": "43",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Armor of the Trainee": {
        "set_id": "281",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Armor of the Veiled Heritance": {
        "set_id": "36",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Arms of Infernace": {
        "set_id": "120",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Arms of Relequen": {
        "set_id": "389",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Arms of the Ancestors": {
        "set_id": "121",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ashen Grip": {
        "set_id": "54",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Aspect of Mazzatun": {
        "set_id": "260",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Assassin's Guile": {
        "set_id": "323",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Auroran's Thunder": {
        "set_id": "435",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Automated Defense": {
        "set_id": "330",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ayleid Rufuge": {
        "set_id": "759",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Azureblight Reaper": {
        "set_id": "456",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Baan Dar's Blessing": {
        "set_id": "756",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Back-Alley Gourmand": {
        "set_id": "671",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bahraha's Curse": {
        "set_id": "227",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bahsei's Mania": {
        "set_id": "587",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Balorgh": {
        "set_id": "397",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bani's Torment": {
        "set_id": "473",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Barkskin": {
        "set_id": "28",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Baron Thirsk": {
        "set_id": "636",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Baron Zaudrus": {
        "set_id": "578",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Basalt-Blooded Warrior": {
        "set_id": "723",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Dragonknight",
        "items": [],
        "abilities": []
    },
    "Bastion of Draoife": {
        "set_id": "673",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bastion of the Heartland": {
        "set_id": "131",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Battalion Defender": {
        "set_id": "422",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Battlefield Acrobat": {
        "set_id": "419",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Beacon of Oblivion": {
        "set_id": "779",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Sorcerer",
        "items": [],
        "abilities": []
    },
    "Beckoning Steel": {
        "set_id": "52",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Beekeeper's Gear": {
        "set_id": "288",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Belharza's Band": {
        "set_id": "626",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Berserking Warrior": {
        "set_id": "137",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Black Rose": {
        "set_id": "179",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Black-Grove Grounding": {
        "set_id": "732",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Blackfeather Flight": {
        "set_id": "804",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Blessing of High Isle": {
        "set_id": "643",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Blessing of the Potentates": {
        "set_id": "128",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Blind Path Induction": {
        "set_id": "735",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Blood Moon": {
        "set_id": "400",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Blood Spawn": {
        "set_id": "163",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Blooddrinker": {
        "set_id": "339",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bloodlord's Embrace": {
        "set_id": "521",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bloodlord's Embrace (OLD)": {
        "set_id": "500",
        "set_type": "",
        "comment": "See setId 521",
        "items": [],
        "abilities": []
    },
    "Bloodthorn's Touch": {
        "set_id": "65",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Blunted Blades": {
        "set_id": "755",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bog Raider": {
        "set_id": "581",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bone Pirate's Tatters": {
        "set_id": "308",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Brands of Imperium": {
        "set_id": "184",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Briarheart": {
        "set_id": "212",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bright-Throat's Boast": {
        "set_id": "405",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Broken Soul": {
        "set_id": "381",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "Level up advisor grants this set during levelling",
        "items": [],
        "abilities": []
    },
    "Buffer of the Swift": {
        "set_id": "133",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Bulwark Ruination": {
        "set_id": "791",
        "set_type": "LIBSETS_SETTYPE_BATTLEGROUND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Burning Spellweave": {
        "set_id": "160",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Call of the Undertaker": {
        "set_id": "442",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Caluurion's Legacy": {
        "set_id": "343",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Camonna Tong": {
        "set_id": "699",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Caustic Arrow": {
        "set_id": "316",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Champion of the Hist": {
        "set_id": "407",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Chaotic Whirlwind": {
        "set_id": "365",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Chaotic Whirlwind (Perfected)": {
        "set_id": "359",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Chimera's Rebuke": {
        "set_id": "677",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Chokethorn": {
        "set_id": "269",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Cinders of Anthelmir": {
        "set_id": "730",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Claw of Yolnakhriin": {
        "set_id": "446",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Claw of the Forest Wraith": {
        "set_id": "679",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Clever Alchemist": {
        "set_id": "225",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Coldharbour's Favorite": {
        "set_id": "437",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Colovian Highlands General": {
        "set_id": "713",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Combat Physician": {
        "set_id": "194",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Concentrated Force": {
        "set_id": "367",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Concentrated Force (Perfected)": {
        "set_id": "361",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Coral Riptide": {
        "set_id": "647",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Corpseburster": {
        "set_id": "777",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Necromancer",
        "items": [],
        "abilities": []
    },
    "Coward's Gear": {
        "set_id": "327",
        "set_type": "LIBSETS_SETTYPE_BATTLEGROUND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Crafty Alfiq": {
        "set_id": "440",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Crest of Cyrodiil": {
        "set_id": "113",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Crimson Oath's Rive": {
        "set_id": "602",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Crimson Twilight": {
        "set_id": "515",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Critical Riposte": {
        "set_id": "480",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Cruel Flurry": {
        "set_id": "371",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Crusader": {
        "set_id": "77",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Crushing Wall": {
        "set_id": "373",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Cryptcanon Vestments": {
        "set_id": "691",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Curse Eater": {
        "set_id": "104",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Curse of Doylemish": {
        "set_id": "348",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Daedric Trickery": {
        "set_id": "324",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dagon's Dominion": {
        "set_id": "573",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Daring Corsair": {
        "set_id": "468",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dark Convergence": {
        "set_id": "616",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Darkstride": {
        "set_id": "60",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dauntless Combatant": {
        "set_id": "482",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dead-Water's Guile": {
        "set_id": "406",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Deadlands Assassin": {
        "set_id": "580",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Deadlands Demolisher": {
        "set_id": "611",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Deadly Strike": {
        "set_id": "127",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Death Dealer's Fete": {
        "set_id": "596",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Death's Wind": {
        "set_id": "37",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Death-Dancer": {
        "set_id": "806",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Deeproot Zeal": {
        "set_id": "660",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Defending Warrior": {
        "set_id": "138",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Defensive Position": {
        "set_id": "364",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Defensive Position (Perfected)": {
        "set_id": "358",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Defiler": {
        "set_id": "321",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Desert Rose": {
        "set_id": "25",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Destructive Impact": {
        "set_id": "317",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Destructive Mage": {
        "set_id": "140",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Diamond's Victory": {
        "set_id": "584",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Disciplined Slash": {
        "set_id": "363",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Disciplined Slash (Perfected)": {
        "set_id": "357",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dolorous Arena": {
        "set_id": "816",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Domihaus": {
        "set_id": "342",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dov-rha Sabatons": {
        "set_id": "655",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dragon's Appetite": {
        "set_id": "491",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dragon's Defilement": {
        "set_id": "457",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dragonguard Elite": {
        "set_id": "467",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Drake's Rush": {
        "set_id": "571",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Draugr Hulk": {
        "set_id": "307",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Draugr's Heritage": {
        "set_id": "135",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Draugr's Rest": {
        "set_id": "335",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Draugrkin's Grip": {
        "set_id": "474",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dreamer's Mantle": {
        "set_id": "22",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dreugh King Slayer": {
        "set_id": "61",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Dro'Zakar's Claws": {
        "set_id": "453",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Druid's Braid": {
        "set_id": "642",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Duneripper's Scales": {
        "set_id": "102",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Durok's Bane": {
        "set_id": "71",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Eagle Eye": {
        "set_id": "130",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Earthgore": {
        "set_id": "341",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ebon Armory": {
        "set_id": "122",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Elemental Catalyst": {
        "set_id": "516",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Elemental Succession": {
        "set_id": "215",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Elf Bane": {
        "set_id": "83",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Embershield": {
        "set_id": "158",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Encrati's Behemoth": {
        "set_id": "577",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Endurance": {
        "set_id": "204",
        "set_type": "LIBSETS_SETTYPE_DAILYRANDOMDUNGEONANDICREWARD",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Enervating Aura": {
        "set_id": "631",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Engine Guardian": {
        "set_id": "166",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Esoteric Environment Greaves": {
        "set_id": "692",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Essence Thief": {
        "set_id": "198",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Eternal Hunt": {
        "set_id": "226",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Eternal Vigor": {
        "set_id": "489",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Eternal Warrior": {
        "set_id": "171",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Euphotic Gatekeeper": {
        "set_id": "667",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Executioner's Blade": {
        "set_id": "557",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Explosive Rebuke": {
        "set_id": "544",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Eye of Nahviintaas": {
        "set_id": "443",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Eye of the Grasp": {
        "set_id": "613",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Eyes of Mara": {
        "set_id": "87",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "False God's Devotion": {
        "set_id": "444",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Farstrider": {
        "set_id": "792",
        "set_type": "LIBSETS_SETTYPE_BATTLEGROUND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Fasalla's Guile": {
        "set_id": "238",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Faun's Lark Cladding": {
        "set_id": "674",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Fellowship's Fortitude": {
        "set_id": "810",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Fiord's Legacy": {
        "set_id": "27",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Flame Blossom": {
        "set_id": "338",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Flanking Strategist": {
        "set_id": "244",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Fledgling's Nest": {
        "set_id": "799",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Foolkiller's Ward": {
        "set_id": "574",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Footman's Fortune": {
        "set_id": "24",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Force Overflow": {
        "set_id": "562",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Fortified Brass": {
        "set_id": "352",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Frenzied Momentum": {
        "set_id": "559",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Frostbite": {
        "set_id": "579",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Frozen Watcher": {
        "set_id": "433",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Full Belly Barricade": {
        "set_id": "807",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Galerion's Revenge": {
        "set_id": "246",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Gallant Charge": {
        "set_id": "411",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Gardener of Seasons": {
        "set_id": "729",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Warden",
        "items": [],
        "abilities": []
    },
    "Gaze of Sithis": {
        "set_id": "593",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Giant Spider": {
        "set_id": "264",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "Not in the game anymore -> Swarm mother replaced it",
        "items": [],
        "abilities": []
    },
    "Glacial Guardian": {
        "set_id": "621",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Glorgoloch the Destroyer": {
        "set_id": "600",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Glorious Defender": {
        "set_id": "213",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Gossamer": {
        "set_id": "261",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Grace of Gloom": {
        "set_id": "382",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Grace of the Ancients": {
        "set_id": "126",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Grand Rejuvenation": {
        "set_id": "318",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Grave Guardian": {
        "set_id": "476",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Grave Inevitability": {
        "set_id": "664",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Grave-Stake Collector": {
        "set_id": "408",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Green Pact": {
        "set_id": "287",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Grisly Gourmet": {
        "set_id": "607",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Grothdarr": {
        "set_id": "280",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Grundwulf": {
        "set_id": "458",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Gryphon's Ferocity": {
        "set_id": "383",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Gryphon's Reprisal": {
        "set_id": "620",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hagraven's Garden": {
        "set_id": "340",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hand of Mephala": {
        "set_id": "263",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hanu's Compassion": {
        "set_id": "399",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Harmony in Chaos": {
        "set_id": "814",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Harpooner's Wading Kilt": {
        "set_id": "594",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hatchling's Shell": {
        "set_id": "62",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Haven of Ursus": {
        "set_id": "401",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hawk's Eye": {
        "set_id": "100",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Healer's Habit": {
        "set_id": "32",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Healing Mage": {
        "set_id": "141",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Heartland Conqueror": {
        "set_id": "583",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Heem-Jas' Retribution": {
        "set_id": "259",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Heroic Unity": {
        "set_id": "798",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hew and Sunder": {
        "set_id": "630",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hex Siphon": {
        "set_id": "542",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hexos' Ward": {
        "set_id": "614",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hide of Morihaus": {
        "set_id": "243",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hide of the Werewolf": {
        "set_id": "58",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Highland Sentinel": {
        "set_id": "764",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hircine's Veneer": {
        "set_id": "123",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hist Bark": {
        "set_id": "78",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hist Whisperer": {
        "set_id": "582",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hiti's Hearth": {
        "set_id": "471",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hollowfang Thirst": {
        "set_id": "452",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hrothgar's Chill": {
        "set_id": "618",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hunding's Rage": {
        "set_id": "80",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Hunt Leader": {
        "set_id": "216",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Iceheart": {
        "set_id": "274",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Icy Conjuror": {
        "set_id": "431",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ilambris": {
        "set_id": "273",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Immolator Charr": {
        "set_id": "599",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Immortal Warrior": {
        "set_id": "136",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Imperial Physique": {
        "set_id": "253",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Impregnable Armor": {
        "set_id": "334",
        "set_type": "LIBSETS_SETTYPE_BATTLEGROUND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Indomitable Fury": {
        "set_id": "417",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Infallible Mage": {
        "set_id": "172",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Infernal Guardian": {
        "set_id": "272",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Innate Axiom": {
        "set_id": "351",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Inventor's Guard": {
        "set_id": "333",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Iron Flask": {
        "set_id": "612",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ironblood": {
        "set_id": "337",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Jailbreaker": {
        "set_id": "295",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Jailer's Tenacity": {
        "set_id": "404",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Jerall Mountains Warchief": {
        "set_id": "711",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Jerensi's Bladestorm": {
        "set_id": "795",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Jolting Arms": {
        "set_id": "186",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Jorvuld's Guidance": {
        "set_id": "346",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Judgement of Akatosh": {
        "set_id": "690",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kagrenac's Hope": {
        "set_id": "92",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kargaeda": {
        "set_id": "632",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kazpian's Cruel Signet": {
        "set_id": "815",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kinras's Wrath": {
        "set_id": "570",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kjalnar's Nightmare": {
        "set_id": "479",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Knight Slayer": {
        "set_id": "328",
        "set_type": "LIBSETS_SETTYPE_BATTLEGROUND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Knight-errant's Mail": {
        "set_id": "309",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Knightmare": {
        "set_id": "35",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kra'gh": {
        "set_id": "266",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kraglen's Howl": {
        "set_id": "517",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kvatch Gladiator": {
        "set_id": "240",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kyne's Kiss": {
        "set_id": "59",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kyne's Wind": {
        "set_id": "492",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Kynmarcher's Cruelty": {
        "set_id": "615",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Lady Malydga": {
        "set_id": "635",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Lady Thorn": {
        "set_id": "535",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Lamia's Song": {
        "set_id": "303",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Lamp Knight's Art": {
        "set_id": "803",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Langour of Peryite": {
        "set_id": "668",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Law of Julianos": {
        "set_id": "207",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Leeching Plate": {
        "set_id": "196",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Lefthander's Aegis Belt": {
        "set_id": "656",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Legacy of Karth": {
        "set_id": "540",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Leki's Focus": {
        "set_id": "237",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Leviathan": {
        "set_id": "302",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Light Speaker": {
        "set_id": "298",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Light of Cyrodiil": {
        "set_id": "109",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Livewire": {
        "set_id": "356",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Lord Warden": {
        "set_id": "164",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Lucent Echoes": {
        "set_id": "768",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Lucilla's Windshield": {
        "set_id": "796",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Lunar Bastion": {
        "set_id": "231",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Maarselok": {
        "set_id": "459",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Macabre Vintage": {
        "set_id": "758",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mad God's Dancing Shoes": {
        "set_id": "811",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mad Tinkerer": {
        "set_id": "354",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Magicka Furnace": {
        "set_id": "103",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Magma Incarnate": {
        "set_id": "609",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Magnus' Gift": {
        "set_id": "48",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Malacath's Band of Brutality": {
        "set_id": "520",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Malacath's Band of Brutality X": {
        "set_id": "504",
        "set_type": "",
        "comment": "See setId 520",
        "items": [],
        "abilities": []
    },
    "Maligalig's Maelstrom": {
        "set_id": "619",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mantle of Siroria": {
        "set_id": "390",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mara\’s Balm": {
        "set_id": "670",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Marauder's Haste": {
        "set_id": "466",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mark of the Pariah": {
        "set_id": "210",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Marksman's Crest": {
        "set_id": "234",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Markyn Ring of Majesty": {
        "set_id": "625",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Master Architect": {
        "set_id": "332",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Maw of the Infernal": {
        "set_id": "170",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mechanical Acuity": {
        "set_id": "353",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Medusa": {
        "set_id": "304",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mender's Ward": {
        "set_id": "416",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Merciless Charge": {
        "set_id": "369",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Meridia's Blessed Armor": {
        "set_id": "94",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Meritorious Service": {
        "set_id": "181",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Might of the Lost Legion": {
        "set_id": "410",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mighty Chudan": {
        "set_id": "256",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mighty Glacier": {
        "set_id": "429",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Molag Kena": {
        "set_id": "183",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Monolith of Storms": {
        "set_id": "727",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Sorcerer",
        "items": [],
        "abilities": []
    },
    "Monomyth Reforged": {
        "set_id": "813",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Moon Hunter": {
        "set_id": "402",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Moondancer": {
        "set_id": "230",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mora Scribe's Thesis": {
        "set_id": "766",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mora's Whispers": {
        "set_id": "654",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Morkuldin": {
        "set_id": "219",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mother Ciannait": {
        "set_id": "478",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Mother's Sorrow": {
        "set_id": "292",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Naga Shaman": {
        "set_id": "409",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nazaray": {
        "set_id": "633",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Necropotence": {
        "set_id": "98",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nerien'eth": {
        "set_id": "168",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Netch Oil": {
        "set_id": "793",
        "set_type": "LIBSETS_SETTYPE_BATTLEGROUND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Netch's Touch": {
        "set_id": "300",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "New Moon Acolyte": {
        "set_id": "470",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nibenay Bay Battlereeve": {
        "set_id": "712",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Night Mother's Embrace": {
        "set_id": "34",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Night Mother's Gaze": {
        "set_id": "51",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Night Terror": {
        "set_id": "112",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Night's Silence": {
        "set_id": "40",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nightflame": {
        "set_id": "167",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nikulas' Heavy Armor": {
        "set_id": "72",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nix-Hound's Howl": {
        "set_id": "681",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nobility in Decay": {
        "set_id": "724",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Necromancer",
        "items": [],
        "abilities": []
    },
    "Noble Duelist's Silks": {
        "set_id": "46",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Noble's Conquest": {
        "set_id": "176",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nocturnal's Favor": {
        "set_id": "387",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nocturnal's Ploy": {
        "set_id": "669",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Noxious Boulder": {
        "set_id": "800",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Nunatak": {
        "set_id": "634",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Oakensoul Ring": {
        "set_id": "658",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Oakfather's Retribution": {
        "set_id": "754",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Oblivion's Edge": {
        "set_id": "91",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Oblivion's Foe": {
        "set_id": "73",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Old Growth Brewer": {
        "set_id": "678",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Order of Diagna": {
        "set_id": "284",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Order's Wrath": {
        "set_id": "640",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Orgnum's Scales": {
        "set_id": "84",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Orpheon the Tactician": {
        "set_id": "801",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Overwhelming Surge": {
        "set_id": "193",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ozezan the Inferno": {
        "set_id": "687",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Pangrit Denmother": {
        "set_id": "663",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Para Bellum": {
        "set_id": "214",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Peace and Serenity": {
        "set_id": "701",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Pearlescent Ward": {
        "set_id": "648",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Pearls of Ehlnofey": {
        "set_id": "576",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Pelinal's Aptitude": {
        "set_id": "242",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Aegis of Galenwe": {
        "set_id": "392",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Arms of Relequen": {
        "set_id": "393",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Gallant Charge": {
        "set_id": "423",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Mantle of Siroria": {
        "set_id": "394",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Mender's Ward": {
        "set_id": "428",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Radial Uppercut": {
        "set_id": "424",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Spectral Cloak": {
        "set_id": "425",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Vestment of Olorime": {
        "set_id": "395",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Virulent Shot": {
        "set_id": "426",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfect Wild Impulse": {
        "set_id": "427",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Ansuul's Torment": {
        "set_id": "707",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Bahsei's Mania": {
        "set_id": "591",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Caustic Arrow": {
        "set_id": "531",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Claw of Yolnakhriin": {
        "set_id": "451",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Coral Riptide": {
        "set_id": "652",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Cruel Flurry": {
        "set_id": "524",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Crushing Wall": {
        "set_id": "526",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Destructive Impact": {
        "set_id": "532",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Dolorous Arena": {
        "set_id": "819",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Executioner's Blade": {
        "set_id": "563",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Eye of Nahviintaas": {
        "set_id": "448",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected False God's Devotion": {
        "set_id": "449",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Force Overflow": {
        "set_id": "568",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Frenzied Momentum": {
        "set_id": "565",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Grand Rejuvenation": {
        "set_id": "533",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Harmony in Chaos": {
        "set_id": "821",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Kazpian's Cruel Signet": {
        "set_id": "820",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Kyne's Wind": {
        "set_id": "493",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Lucent Echoes": {
        "set_id": "771",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Merciless Charge": {
        "set_id": "522",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Mora Scribe's Thesis": {
        "set_id": "773",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Peace and Serenity": {
        "set_id": "708",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Pearlescent Ward": {
        "set_id": "651",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Pillager's Profit": {
        "set_id": "650",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Point-Blank Snipe": {
        "set_id": "566",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Precise Regeneration": {
        "set_id": "527",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Puncturing Remedy": {
        "set_id": "529",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Rampaging Slash": {
        "set_id": "523",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Recovery Convergence": {
        "set_id": "818",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Roaring Opportunist": {
        "set_id": "497",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Saxhleel Champion": {
        "set_id": "589",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Slivers of the Null Arca": {
        "set_id": "772",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Stinging Slashes": {
        "set_id": "530",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Stone-Talker's Oath": {
        "set_id": "592",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Sul-Xan's Torment": {
        "set_id": "590",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Test of Resolve": {
        "set_id": "706",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Thunderous Volley": {
        "set_id": "525",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Titanic Cleave": {
        "set_id": "528",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Tooth of Lokkestiiz": {
        "set_id": "450",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Transformative Hope": {
        "set_id": "705",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Void Bash": {
        "set_id": "564",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Vrol's Command": {
        "set_id": "495",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Whorl of the Depths": {
        "set_id": "653",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Wrath of Elements": {
        "set_id": "567",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Xoryn's Masterpiece": {
        "set_id": "770",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Perfected Yandir's Might": {
        "set_id": "499",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Permafrost": {
        "set_id": "211",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Pestilent Host": {
        "set_id": "543",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Phoenix": {
        "set_id": "200",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Phoenix Moth Theurge": {
        "set_id": "672",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Phylactery's Grasp": {
        "set_id": "665",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Piercing Spray": {
        "set_id": "366",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Piercing Spray (Perfected)": {
        "set_id": "360",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Pillager's Profit": {
        "set_id": "649",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Pillar of Nirn": {
        "set_id": "336",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Pirate Skeleton": {
        "set_id": "277",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Plague Doctor": {
        "set_id": "293",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Plague Slinger": {
        "set_id": "347",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Plaguebreak": {
        "set_id": "617",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Point-Blank Snipe": {
        "set_id": "560",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Poisonous Serpent": {
        "set_id": "143",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Powerful Assault": {
        "set_id": "180",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Prayer Shawl": {
        "set_id": "55",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Precise Regeneration": {
        "set_id": "374",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Prior Thierric": {
        "set_id": "608",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Prisoner's Rags": {
        "set_id": "26",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Prophet's": {
        "set_id": "380",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "Level up advisor grants this set during levelling",
        "items": [],
        "abilities": []
    },
    "Puncturing Remedy": {
        "set_id": "314",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Pyrebrand": {
        "set_id": "776",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Dragonknight",
        "items": [],
        "abilities": []
    },
    "Queen's Elegance": {
        "set_id": "86",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Quick Serpent": {
        "set_id": "142",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Radial Uppercut": {
        "set_id": "412",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Radiant Bastion": {
        "set_id": "536",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Rage of the Ursauk": {
        "set_id": "662",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Rakkhat's Voidmantle": {
        "set_id": "812",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Rallying Cry": {
        "set_id": "629",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Rampaging Slash": {
        "set_id": "370",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ranger's Gait": {
        "set_id": "69",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Rattlecage": {
        "set_id": "311",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ravager": {
        "set_id": "108",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Reactive Armor": {
        "set_id": "201",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Reawakened Hierophant": {
        "set_id": "722",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Arcanist",
        "items": [],
        "abilities": []
    },
    "Recovery Convergence": {
        "set_id": "817",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Red Eagle's Fury": {
        "set_id": "539",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Redistributor": {
        "set_id": "177",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Reflected Fury": {
        "set_id": "737",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Relics of the Physician, Ansur": {
        "set_id": "117",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Relics of the Rebellion": {
        "set_id": "119",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Renald's Resolve": {
        "set_id": "454",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ring of the Pale Order": {
        "set_id": "575",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ring of the Wild Hunt": {
        "set_id": "503",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ritemaster's Bond": {
        "set_id": "680",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Roar of Alkosh": {
        "set_id": "232",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Roaring Opportunist": {
        "set_id": "496",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Robes of Alteration Mastery": {
        "set_id": "76",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Robes of Destruction Mastery": {
        "set_id": "88",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Robes of Transmutation": {
        "set_id": "235",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Robes of the Hist": {
        "set_id": "66",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Robes of the Withered Hand": {
        "set_id": "47",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Roksa the Warped": {
        "set_id": "683",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Rourken Steamguards": {
        "set_id": "760",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Runecarver\’s Blaze": {
        "set_id": "684",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Rush of Agony": {
        "set_id": "604",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Salvation": {
        "set_id": "99",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sanctuary": {
        "set_id": "110",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Savage Werewolf": {
        "set_id": "403",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Saxhleel Champion": {
        "set_id": "585",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Scathing Mage": {
        "set_id": "190",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Scavenging Demise": {
        "set_id": "434",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Scorion's Feast": {
        "set_id": "603",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Scourge Harvester": {
        "set_id": "165",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sea-Serpent's Coil": {
        "set_id": "657",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Seeker Synthesis": {
        "set_id": "697",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Selene": {
        "set_id": "279",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sellistrix": {
        "set_id": "271",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Senchal Defender": {
        "set_id": "465",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Senche's Bite": {
        "set_id": "90",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Senche-raht's Grit": {
        "set_id": "438",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sentinel of Rkugamz": {
        "set_id": "268",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sentry": {
        "set_id": "89",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sergeant's Mail": {
        "set_id": "29",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Serpent's Disdain": {
        "set_id": "641",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Seventh Legion Brute": {
        "set_id": "70",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shacklebreaker": {
        "set_id": "325",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shadow Dancer's Raiment": {
        "set_id": "64",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shadow Walker": {
        "set_id": "67",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shadow of the Red Mountain": {
        "set_id": "49",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shadowrend": {
        "set_id": "265",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shalidor's Curse": {
        "set_id": "95",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shalk Exoskeleton": {
        "set_id": "291",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shapeshifter's Chain": {
        "set_id": "597",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shared Burden": {
        "set_id": "808",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shared Pain": {
        "set_id": "783",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shattered Fate": {
        "set_id": "695",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sheer Venom": {
        "set_id": "195",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shell Splitter": {
        "set_id": "689",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shield Breaker": {
        "set_id": "199",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shield of the Valiant": {
        "set_id": "132",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Shroud of the Lich": {
        "set_id": "134",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Siegemaster'\s Focus": {
        "set_id": "784",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Silks of the Sun": {
        "set_id": "31",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Silver Rose Vigil": {
        "set_id": "605",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sithis' Touch": {
        "set_id": "245",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Skooma Smuggler": {
        "set_id": "290",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Slimecraw": {
        "set_id": "270",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Slivers of the Null Arca": {
        "set_id": "767",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sload's Semblance": {
        "set_id": "386",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sluthrug's Hunger": {
        "set_id": "731",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Snake in the Stars": {
        "set_id": "688",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Snow Treaders": {
        "set_id": "519",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Snow Treaders (OLD)": {
        "set_id": "502",
        "set_type": "",
        "comment": "See setId 519",
        "items": [],
        "abilities": []
    },
    "Soldier of Anguish": {
        "set_id": "420",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Song of Lamae": {
        "set_id": "81",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Soulcleaver": {
        "set_id": "726",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Nightblade",
        "items": [],
        "abilities": []
    },
    "Soulshine": {
        "set_id": "114",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spattering Disjunction": {
        "set_id": "775",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Arcanist",
        "items": [],
        "abilities": []
    },
    "Spaulder of Ruin": {
        "set_id": "627",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spawn of Mephala": {
        "set_id": "162",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spectral Cloak": {
        "set_id": "413",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spectre's Eye": {
        "set_id": "74",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spell Parasite": {
        "set_id": "506",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spell Power Cure": {
        "set_id": "185",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spell Strategist": {
        "set_id": "418",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spelunker": {
        "set_id": "296",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spider Cultist Cowl": {
        "set_id": "297",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spinner's Garments": {
        "set_id": "289",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spriggan's Thorns": {
        "set_id": "286",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Spriggan\’s Vigor": {
        "set_id": "624",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Squall of Retribution": {
        "set_id": "797",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Steadfast Hero": {
        "set_id": "421",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Steadfast's Mettle": {
        "set_id": "644",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stendarr's Embrace": {
        "set_id": "56",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stinging Slashes": {
        "set_id": "315",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stone Husk": {
        "set_id": "534",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stone's Accord": {
        "set_id": "661",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stone-Talker's Oath": {
        "set_id": "588",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stonekeeper": {
        "set_id": "432",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Storm Knight's Plate": {
        "set_id": "93",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Storm Master": {
        "set_id": "188",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Storm-Cursed's Revenge": {
        "set_id": "623",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stormfist": {
        "set_id": "275",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stormweaver's Cavort": {
        "set_id": "675",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Strength of the Automaton": {
        "set_id": "301",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stuhn's Favor": {
        "set_id": "490",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Stygian": {
        "set_id": "68",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sul-Xan's Torment": {
        "set_id": "586",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sunderflame": {
        "set_id": "159",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Swamp Raider": {
        "set_id": "187",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Swarm Mother": {
        "set_id": "267",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sword Dancer": {
        "set_id": "310",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Sword-Singer": {
        "set_id": "283",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Symmetry of the Weald": {
        "set_id": "757",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Symphony of Blades": {
        "set_id": "436",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Syrabane's Grip": {
        "set_id": "57",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Syrabane's Ward": {
        "set_id": "676",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Systres' Scowl": {
        "set_id": "645",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Syvarra's Scales": {
        "set_id": "228",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Talfyg's Treachery": {
        "set_id": "513",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Tarnished Nightmare": {
        "set_id": "736",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Tava's Favor": {
        "set_id": "224",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Telvanni Efficiency": {
        "set_id": "696",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Telvanni Enforcer": {
        "set_id": "682",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Template_Drop_Healer": {
        "set_id": "486",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "PTS spawn sets for template created chars?",
        "items": [],
        "abilities": []
    },
    "Template_Drop_Healer P": {
        "set_id": "509",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "PTS spawn sets for template created chars?",
        "items": [],
        "abilities": []
    },
    "Template_Drop_Magi": {
        "set_id": "483",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "PTS spawn sets for template created chars?",
        "items": [],
        "abilities": []
    },
    "Template_Drop_Magi P": {
        "set_id": "512",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "PTS spawn sets for template created chars?",
        "items": [],
        "abilities": []
    },
    "Template_Drop_Stamina": {
        "set_id": "484",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "PTS spawn sets for template created chars?",
        "items": [],
        "abilities": []
    },
    "Template_Drop_Stamina P": {
        "set_id": "511",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "PTS spawn sets for template created chars?",
        "items": [],
        "abilities": []
    },
    "Template_Drop_Tank": {
        "set_id": "485",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "PTS spawn sets for template created chars?",
        "items": [],
        "abilities": []
    },
    "Template_Drop_Tank P": {
        "set_id": "510",
        "set_type": "LIBSETS_SETTYPE_SPECIAL",
        "comment": "PTS spawn sets for template created chars?",
        "items": [],
        "abilities": []
    },
    "Test of Resolve": {
        "set_id": "703",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Tharriker's Strike": {
        "set_id": "763",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Arch-Mage": {
        "set_id": "97",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Blind": {
        "set_id": "738",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Destruction Suite": {
        "set_id": "116",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Ice Furnace": {
        "set_id": "53",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Juggernaut": {
        "set_id": "63",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Morag Tong": {
        "set_id": "50",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Saint and the Seducer": {
        "set_id": "762",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Shadow Queen's Cowl": {
        "set_id": "761",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Troll King": {
        "set_id": "278",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "The Worm's Raiment": {
        "set_id": "124",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Thews of the Harbinger": {
        "set_id": "248",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Thrassian Stranglers": {
        "set_id": "501",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Threads of War": {
        "set_id": "765",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Three Queens Wellspring": {
        "set_id": "805",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Thunder Caller": {
        "set_id": "606",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Thunderbug's Carapace": {
        "set_id": "30",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Thunderous Volley": {
        "set_id": "372",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Thurvokun": {
        "set_id": "349",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Tide-Born Wildstalker": {
        "set_id": "809",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Timeless Blessing": {
        "set_id": "368",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Timeless Blessing (Perfected)": {
        "set_id": "362",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Titanborn Strength": {
        "set_id": "472",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Titanic Cleave": {
        "set_id": "313",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Tooth of Lokkestiiz": {
        "set_id": "445",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Toothrow": {
        "set_id": "299",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Torc of Tonal Constancy": {
        "set_id": "505",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Torc of the Last Ayleid King": {
        "set_id": "693",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Tormentor": {
        "set_id": "197",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Torug's Pact": {
        "set_id": "75",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Tracker's Lash": {
        "set_id": "782",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Transformative Hope": {
        "set_id": "704",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Trappings of Invigoration": {
        "set_id": "344",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Treasure Hunter": {
        "set_id": "305",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Treasures of the Earthforge": {
        "set_id": "118",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Tremorscale": {
        "set_id": "276",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Trial by Fire": {
        "set_id": "208",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Trinimac's Valor": {
        "set_id": "218",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "True-Sworn Fury": {
        "set_id": "569",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Turning Tide": {
        "set_id": "622",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Twice-Born Star": {
        "set_id": "161",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Twice-Fanged Serpent": {
        "set_id": "144",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Twilight Remedy": {
        "set_id": "229",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Twilight's Embrace": {
        "set_id": "38",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Twin Sisters": {
        "set_id": "105",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Tzogvin's Warband": {
        "set_id": "430",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ulfnor's Favor": {
        "set_id": "345",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Umbral Edge": {
        "set_id": "778",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Nightblade",
        "items": [],
        "abilities": []
    },
    "Unchained Aggressor": {
        "set_id": "481",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Undaunted Bastion": {
        "set_id": "155",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Undaunted Infiltrator": {
        "set_id": "156",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Undaunted Unweaver": {
        "set_id": "157",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Unfathomable Darkness": {
        "set_id": "355",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Unleashed Ritualist": {
        "set_id": "572",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Unleashed Terror": {
        "set_id": "514",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Valkyn Skoria": {
        "set_id": "169",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vampire Cloak": {
        "set_id": "282",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vampire Lord": {
        "set_id": "285",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vampire's Kiss": {
        "set_id": "44",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vandorallen's Resonance": {
        "set_id": "794",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vanguard's Challenge": {
        "set_id": "326",
        "set_type": "LIBSETS_SETTYPE_BATTLEGROUND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Varen's Legacy": {
        "set_id": "241",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vastarie's Tutelage": {
        "set_id": "439",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Velidreth": {
        "set_id": "257",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Velothi Ur-Mage's Amulet": {
        "set_id": "694",
        "set_type": "LIBSETS_SETTYPE_MYTHIC",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vengeance Leech": {
        "set_id": "129",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Venomous Smite": {
        "set_id": "488",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vestment of Olorime": {
        "set_id": "391",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vestments of the Warlock": {
        "set_id": "19",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vesture of Darloc Brae": {
        "set_id": "441",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vicecanon of Venom": {
        "set_id": "247",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vicious Death": {
        "set_id": "236",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vicious Serpent": {
        "set_id": "173",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Viper's Sting": {
        "set_id": "33",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Virulent Shot": {
        "set_id": "414",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vivec's Duality": {
        "set_id": "698",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Void Bash": {
        "set_id": "558",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Voidcaller": {
        "set_id": "537",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vrol's Command": {
        "set_id": "494",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Vykosa": {
        "set_id": "398",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "War Machine": {
        "set_id": "331",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "War Maiden": {
        "set_id": "320",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ward of Cyrodiil": {
        "set_id": "111",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Warrior's Fury": {
        "set_id": "239",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Warrior-Poet": {
        "set_id": "322",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Way of Air": {
        "set_id": "146",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Way of Fire": {
        "set_id": "145",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Way of Martial Knowledge": {
        "set_id": "147",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Way of the Arena": {
        "set_id": "148",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Whitestrake's Retribution": {
        "set_id": "41",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Whorl of the Depths": {
        "set_id": "646",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Widowmaker": {
        "set_id": "262",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Wild Impulse": {
        "set_id": "415",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Wilderqueen's Arch": {
        "set_id": "106",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Willow's Path": {
        "set_id": "79",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Willpower": {
        "set_id": "205",
        "set_type": "LIBSETS_SETTYPE_DAILYRANDOMDUNGEONANDICREWARD",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Winter's Respite": {
        "set_id": "487",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Winterborn": {
        "set_id": "217",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Wisdom of Vanus": {
        "set_id": "384",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Wise Mage": {
        "set_id": "139",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Witch-Knight's Defiance": {
        "set_id": "538",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Witchman Armor": {
        "set_id": "20",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Wizard's Riposte": {
        "set_id": "329",
        "set_type": "LIBSETS_SETTYPE_BATTLEGROUND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Wrath of Elements": {
        "set_id": "561",
        "set_type": "LIBSETS_SETTYPE_ARENA",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Wrath of the Imperium": {
        "set_id": "125",
        "set_type": "LIBSETS_SETTYPE_CYRODIIL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Wrathsun": {
        "set_id": "728",
        "set_type": "LIBSETS_SETTYPE_CLASS",
        "comment": "Templar",
        "items": [],
        "abilities": []
    },
    "Wretched Vitality": {
        "set_id": "610",
        "set_type": "LIBSETS_SETTYPE_CRAFTED",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Wyrd Tree's Blessing": {
        "set_id": "107",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Xoryn's Masterpiece": {
        "set_id": "769",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Yandir's Might": {
        "set_id": "498",
        "set_type": "LIBSETS_SETTYPE_TRIAL",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Ysgramor's Birthright": {
        "set_id": "294",
        "set_type": "LIBSETS_SETTYPE_OVERLAND",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Z'en's Redress": {
        "set_id": "455",
        "set_type": "LIBSETS_SETTYPE_DUNGEON",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Zaan": {
        "set_id": "350",
        "set_type": "LIBSETS_SETTYPE_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
    "Zoal the Ever-Wakeful": {
        "set_id": "598",
        "set_type": "LIBSETS_SETTYPE_IMPERIALCITY_MONSTER",
        "comment": "",
        "items": [],
        "abilities": []
    },
}

# Known item ID to set name mappings
KNOWN_ITEM_MAPPINGS: Dict[str, str] = {
    "154691": "Bahsei's Mania",
}

# Known ability ID to set name mappings
KNOWN_ABILITY_MAPPINGS: Dict[str, str] = {
    "107202": "Arms of Relequen",
    "107203": "Arms of Relequen",
    "133378": "Mother Ciannait",
    "154691": "Bahsei's Mania",
    "66899": "Spell Power Cure",
    "84731": "Witchmother's Potent Brew",
}

def get_set_name_by_id(set_id: str) -> Optional[str]:
    """Get set name by set ID."""
    return SET_ID_TO_NAME.get(set_id)

def get_set_id_by_name(set_name: str) -> Optional[str]:
    """Get set ID by set name."""
    return SET_NAME_TO_ID.get(set_name)

def get_set_info(set_name: str) -> Optional[Dict]:
    """Get detailed set information by set name."""
    return SET_INFO.get(set_name)

def get_set_name_by_item_id(item_id: str) -> Optional[str]:
    """Get set name by item ID."""
    return KNOWN_ITEM_MAPPINGS.get(item_id)

def get_set_name_by_ability_id(ability_id: str) -> Optional[str]:
    """Get set name by ability ID."""
    return KNOWN_ABILITY_MAPPINGS.get(ability_id)

# Statistics
TOTAL_SETS = len(SET_ID_TO_NAME)
TOTAL_KNOWN_ITEMS = len(KNOWN_ITEM_MAPPINGS)
TOTAL_KNOWN_ABILITIES = len(KNOWN_ABILITY_MAPPINGS)

def get_stats() -> Dict[str, int]:
    """Get database statistics."""
    return {
        'total_sets': TOTAL_SETS,
        'total_known_items': TOTAL_KNOWN_ITEMS,
        'total_known_abilities': TOTAL_KNOWN_ABILITIES
    }
