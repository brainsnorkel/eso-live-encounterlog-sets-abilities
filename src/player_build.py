"""
Player builds: the gear, mundus stone and food a player started a fight with
(engine side, no Qt).

The encounter log writes one PLAYER_INFO line per group member as combat
starts. Besides the two ability bars it lists the player's long-term effects
(passives, set auras, the mundus boon, food) and one entry per equipped item:

    slot, id, isCP, level, trait, displayQuality, setId,
    enchantType, isEnchantCP, enchantLevel, enchantQuality

    [MAIN_HAND,133257,T,16,WEAPON_CHARGED,LEGENDARY,361,POISONED_WEAPON,T,16,LEGENDARY]

What 4,279 such lines from 32 logs of October 2026 show:

- Seventeen slot names occur. An empty slot is left out of the list, so a
  two-handed weapon is a main hand with no off hand beside it. COSTUME is
  cosmetic and skipped here.
- A slotted poison (POISON, BACKUP_POISON) is an item id and a quality. Its
  name comes from data/items/poisons_en.json, built by
  scripts/generate_poison_names.py.
- A mythic item is logged as LEGENDARY; only its set's LibSets type says it
  is mythic.
- The line is written once per fight, so a build is the one the player
  pulled with. Item names, weapon types and armor weights are not logged.

build_fields turns a player's line into the 'gear', 'mundus' and 'food' keys
of their fight-entry dict. The label functions name the log's values for
display; a value they do not know is shown in a readable form of itself.

has_restoration_staff answers the one weapon-type question the app asks (the
role heuristic's): by item id, against the list of restoration staves in
data/items/restoration_staves.json, built by
scripts/generate_restoration_staves.py.
"""

import json
from collections import Counter
from functools import lru_cache
from typing import Callable, Dict, FrozenSet, Iterable, List, Optional

from ability_icons import bundle_root

ARMOR_SLOTS = ("HEAD", "SHOULDERS", "CHEST", "HAND", "WAIST", "LEGS", "FEET")
JEWELRY_SLOTS = ("NECK", "RING1", "RING2")
FRONT_BAR_SLOTS = ("MAIN_HAND", "OFF_HAND", "POISON")
BACK_BAR_SLOTS = ("BACKUP_MAIN", "BACKUP_OFF", "BACKUP_POISON")
POISON_SLOTS = ("POISON", "BACKUP_POISON")
# Display order of the build window's gear grid
SLOT_GROUPS = (
    ("Armor", ARMOR_SLOTS),
    ("Jewelry", JEWELRY_SLOTS),
    ("Front bar", FRONT_BAR_SLOTS),
    ("Back bar", BACK_BAR_SLOTS),
)
SLOT_ORDER = tuple(slot for _group, slots in SLOT_GROUPS for slot in slots)
SLOT_LABELS = {
    "HEAD": "Head", "SHOULDERS": "Shoulders", "CHEST": "Chest", "HAND": "Hands",
    "WAIST": "Waist", "LEGS": "Legs", "FEET": "Feet",
    "NECK": "Neck", "RING1": "Ring 1", "RING2": "Ring 2",
    "MAIN_HAND": "Main hand", "OFF_HAND": "Off hand", "POISON": "Poison",
    "BACKUP_MAIN": "Main hand", "BACKUP_OFF": "Off hand", "BACKUP_POISON": "Poison",
}
# Each main hand's off hand: with none logged, the main hand is two-handed
OFF_HAND_OF = {"MAIN_HAND": "OFF_HAND", "BACKUP_MAIN": "BACKUP_OFF"}
_BODY_SLOTS = frozenset(ARMOR_SLOTS + JEWELRY_SLOTS)
_FRONT_WEAPONS = ("MAIN_HAND", "OFF_HAND")
_BACK_WEAPONS = ("BACKUP_MAIN", "BACKUP_OFF")

RACE_NAMES = {
    "1": "Breton", "2": "Redguard", "3": "Orc", "4": "Dark Elf", "5": "Nord",
    "6": "Argonian", "7": "High Elf", "8": "Wood Elf", "9": "Khajiit", "10": "Imperial",
}

MYTHIC_QUALITY = "MYTHIC_OVERRIDE"
MYTHIC_SET_TYPE = "LIBSETS_SETTYPE_MYTHIC"
QUALITY_LABELS = {
    "TRASH": "Trash", "NORMAL": "Normal", "MAGIC": "Fine", "ARCANE": "Superior",
    "ARTIFACT": "Epic", "LEGENDARY": "Legendary", MYTHIC_QUALITY: "Mythic",
}
TRAIT_PREFIXES = ("ARMOR_", "WEAPON_", "JEWELRY_")
# Traits whose name in the game is not their log value
TRAIT_LABELS = {"PROSPEROUS": "Invigorating", "WELL_FITTED": "Well-fitted"}
# Enchants are named after the glyph that applies them ("Glyph of Flame");
# the values not listed here read well as they are (MAGICKA, ABSORB_HEALTH)
ENCHANT_LABELS = {
    "FIERY_WEAPON": "Flame", "FROZEN_WEAPON": "Frost", "CHARGED_WEAPON": "Shock",
    "POISONED_WEAPON": "Poison", "BEFOULED_WEAPON": "Foulness",
    "BERSERKER": "Weapon Damage", "REDUCE_ARMOR": "Crushing",
    "REDUCE_POWER": "Weakening", "DAMAGE_SHIELD": "Hardening",
    "DAMAGE_HEALTH": "Decrease Health",
    "INCREASE_PHYSICAL_DAMAGE": "Increase Physical Harm",
    "INCREASE_SPELL_DAMAGE": "Increase Magical Harm",
    "DECREASE_PHYSICAL_DAMAGE": "Decrease Physical Harm",
    "DECREASE_SPELL_DAMAGE": "Decrease Spell Harm",
    "HEALTH_REGEN": "Health Recovery", "MAGICKA_REGEN": "Magicka Recovery",
    "STAMINA_REGEN": "Stamina Recovery", "PRISMATIC_REGEN": "Prismatic Recovery",
    "REDUCE_BLOCK_AND_BASH": "Bracing", "INCREASE_BASH_DAMAGE": "Bashing",
    "REDUCE_POTION_COOLDOWN": "Potion Speed",
    "INCREASE_POTION_EFFECTIVENESS": "Potion Boost",
    "FIRE_RESISTANT": "Flame Resist", "FROST_RESISTANT": "Frost Resist",
    "SHOCK_RESISTANT": "Shock Resist", "POISON_RESISTANT": "Poison Resist",
    "DISEASE_RESISTANT": "Disease Resist",
}
NO_VALUE = ("", "NONE", "INVALID")  # the log's ways of saying "nothing here"

MAX_CP_LEVEL = 16  # the level field of a champion-rank 160 item
# Poison tier per solvent: below each level the tier applies, else the last
_POISON_TIERS = ((10, "I"), (20, "II"), (30, "III"), (40, "IV"))
_POISON_TIERS_CP = ((5, "VI"), (10, "VII"), (15, "VIII"))

# The thirteen mundus boons. Their icons share a family, which also covers
# a stone these ids do not list
MUNDUS_IDS = frozenset(
    ["13940", "13943", "13984", "13985"] + [str(i) for i in range(13974, 13983)])
MUNDUS_ICON_PREFIX = "ability_mundusstones_"
MUNDUS_NAME_PREFIX = "Boon: "

_FOOD_STATS = {"HEALTH": 1, "MAGICKA": 1, "STAMINA": 1, "ALL": 3}


def _humanize(value: str, prefixes: Iterable[str] = ()) -> str:
    """'WEAPON_NEW_TRAIT' -> 'New Trait': a log value the tables lack."""
    text = str(value or "")
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return " ".join(word.capitalize() for word in text.split("_") if word)


def race_name(race_id) -> str:
    """Race for UNIT_ADDED's race id, '' when unknown."""
    return RACE_NAMES.get(str(race_id or ""), "")


def display_quality(item: dict) -> str:
    """An item's quality as the game shows it: mythic for a piece of a mythic
    set, which the log reports as legendary."""
    return MYTHIC_QUALITY if item.get("mythic") else str(item.get("quality") or "")


def quality_label(quality: str) -> str:
    """In-game name of a displayQuality value: 'ARTIFACT' -> 'Epic'."""
    quality = str(quality or "")
    if quality in NO_VALUE:
        return ""
    return QUALITY_LABELS.get(quality) or _humanize(quality)


def trait_label(trait: str) -> str:
    """'ARMOR_DIVINES' -> 'Divines'; '' for an item without a trait."""
    trait = str(trait or "")
    if trait in NO_VALUE:
        return ""
    bare = next((trait[len(p):] for p in TRAIT_PREFIXES if trait.startswith(p)), trait)
    return TRAIT_LABELS.get(bare) or _humanize(bare)


def enchant_label(enchant: str) -> str:
    """'FIERY_WEAPON' -> 'Flame'; '' for an item without an enchant."""
    enchant = str(enchant or "")
    if enchant in NO_VALUE:
        return ""
    return ENCHANT_LABELS.get(enchant) or _humanize(enchant)


def level_label(cp, level) -> str:
    """'' for a champion-rank 160 item, else 'CP150' or 'Level 32'."""
    try:
        level = int(level)
    except (TypeError, ValueError):
        return ""
    if cp:
        return "" if level >= MAX_CP_LEVEL else f"CP{level * 10}"
    return f"Level {level}"


# ---- poisons ----

def _load_table(*path_parts: str, key: str) -> Optional[Dict[str, dict]]:
    """A bundled id -> dict table, or None when it is absent or malformed."""
    try:
        data = json.loads(bundle_root().joinpath("data", *path_parts)
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    table = data.get(key) if isinstance(data, dict) else None
    if not isinstance(table, dict):
        return None
    return {str(k): v for k, v in table.items() if isinstance(v, dict)}


@lru_cache(maxsize=1)
def _bundled_poisons() -> Dict[str, dict]:
    """Poison item id -> {'name', 'tiered'}; {} when the table is absent."""
    return _load_table("items", "poisons_en.json", key="poisons") or {}


def poison_tier(cp, level) -> str:
    """Tier numeral of a level-scaled poison, from the level of its solvent:
    I to V below champion ranks, VI to IX at champion rank 10, 50, 100, 150."""
    try:
        level = int(level)
    except (TypeError, ValueError):
        return ""
    tiers, top = (_POISON_TIERS_CP, "IX") if cp else (_POISON_TIERS, "V")
    return next((tier for below, tier in tiers if level < below), top)


def poison_name(item_id, cp=False, level=0,
                table: Optional[Dict[str, dict]] = None) -> str:
    """Name of a slotted poison: 'Crown Lethal Poison', 'Damage Health
    Poison IX' for a level-scaled one, 'Poison (item 123)' for an id the
    bundled table lacks. *table* overrides the bundled one; tests use it."""
    known = (table if table is not None else _bundled_poisons()).get(str(item_id))
    if not known or not known.get("name"):
        return f"Poison (item {item_id})"
    name = str(known["name"])
    tier = poison_tier(cp, level) if known.get("tiered") else ""
    return f"{name} {tier}" if tier else name


# ---- mundus and food, from the long-term effects ----

def mundus_stones(effect_ids: Iterable[str], name_of: Callable[[str], Optional[str]],
                  icon_of: Callable[[str], Optional[str]]) -> List[dict]:
    """The player's mundus boons as [{'id', 'name', 'icon'}], in log order
    (two with the Twice-Born Star set). A boon is known by its icon family or
    its id, not its name, so a translated log works too."""
    stones, seen = [], set()
    for effect in effect_ids or []:
        effect = str(effect)
        icon = str(icon_of(effect) or "")
        if effect in seen or not (effect in MUNDUS_IDS
                                  or icon.startswith(MUNDUS_ICON_PREFIX)):
            continue
        seen.add(effect)
        name = str(name_of(effect) or "")
        if name.startswith(MUNDUS_NAME_PREFIX):
            name = name[len(MUNDUS_NAME_PREFIX):]
        stones.append({"id": effect, "name": name or f"Mundus {effect}", "icon": icon})
    return stones


@lru_cache(maxsize=1)
def _bundled_food() -> Optional[Dict[str, dict]]:
    """Food and drink buff id -> {'kind', 'type'}, from
    scripts/generate_food_buffs.py; None when the table is absent."""
    return _load_table("buffs", "food_drink.json", key="buffs") or None


def food_table() -> Optional[Dict[str, dict]]:
    """The bundled food and drink table, None when it cannot be loaded (the
    caller then says nothing about food rather than "none")."""
    return _bundled_food()


def _stats_named(buff_type: str) -> int:
    """How many stats a LibFoodDrinkBuff type names: MAX_HEALTH_REGEN_ALL -> 4."""
    return sum(_FOOD_STATS.get(part, 0) for part in str(buff_type or "").split("_"))


def food_buff(effect_ids: Iterable[str], name_of: Callable[[str], Optional[str]],
              table: Dict[str, dict]) -> Optional[dict]:
    """The player's food or drink as {'id', 'name', 'kind'}, None without one.

    A consumable can be logged as several effects, and the table knows some
    of those companions too (Witchmother's Potent Brew with its two "Increase
    Health Regen" effects). The effect whose type names the most stats is the
    consumable itself; the lowest id settles a tie.
    """
    matches = [str(e) for e in dict.fromkeys(effect_ids or []) if str(e) in table]
    if not matches:
        return None
    best = min(matches, key=lambda e: (-_stats_named(table[e].get("type")), int(e)))
    return {"id": best, "name": str(name_of(best) or f"Ability {best}"),
            "kind": str(table[best].get("kind") or "food")}


# ---- gear ----

@lru_cache(maxsize=1)
def _bundled_restoration_staves() -> FrozenSet[str]:
    """Item ids of every restoration staff; empty when the list is absent."""
    try:
        data = json.loads(bundle_root().joinpath("data", "items", "restoration_staves.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    ids = data.get("ids") if isinstance(data, dict) else None
    return frozenset(str(i) for i in ids) if isinstance(ids, list) else frozenset()


def has_restoration_staff(gear: Dict[str, List[str]],
                          staves: Optional[Iterable[str]] = None) -> bool:
    """Whether a restoration staff is the main-hand weapon of either bar.

    The log does not name weapon types, so the item id is looked up in the
    bundled list of restoration staves (*staves* overrides it; tests use
    that). A Restoration Staff skill on a bar is no substitute: real logs
    have such skills slotted with another weapon in hand, and staves in hand
    with none of the skills slotted.
    """
    known = _bundled_restoration_staves() if staves is None else frozenset(map(str, staves))
    return any(len(gear.get(slot) or []) > 1 and str(gear[slot][1]) in known
               for slot in OFF_HAND_OF)


def is_two_handed(slot: str, item_id: str, gear: Dict[str, List[str]]) -> bool:
    """Whether the main-hand item in *slot* fills both hands: no item is
    logged in that bar's off hand. Always False for other slots."""
    off_slot = OFF_HAND_OF.get(slot)
    if off_slot is None:
        return False
    off = gear.get(off_slot) or []
    if len(off) > 1:
        if off[1] == item_id or off[1] not in ("0", ""):
            return False
        # A shield carries an armor trait
        if len(off) > 4 and "ARMOR" in off[4]:
            return False
    return True


def _set_id(item: List[str]) -> str:
    set_id = str(item[6]) if len(item) > 6 else ""
    return "" if set_id in ("0", "", "nan") else set_id


def piece_counts(gear: Dict[str, List[str]]) -> Dict[str, List[Optional[int]]]:
    """set id -> [pieces active on the front bar, on the back bar].

    A set's armor and jewelry count on both bars and each bar adds its own
    weapons, a two-handed one as two pieces. The back-bar count is None when
    the log lists no back-bar weapon, so there is only one bar to speak of.
    """
    body, front, back = Counter(), Counter(), Counter()
    for slot, item in gear.items():
        set_id = _set_id(item)
        if not set_id:
            continue
        if slot in _BODY_SLOTS:
            body[set_id] += 1
        elif slot in _FRONT_WEAPONS or slot in _BACK_WEAPONS:
            pieces = 2 if is_two_handed(slot, item[1], gear) else 1
            (front if slot in _FRONT_WEAPONS else back)[set_id] += pieces
    has_back_bar = any(slot in gear for slot in _BACK_WEAPONS)
    return {set_id: [body[set_id] + front[set_id],
                     body[set_id] + back[set_id] if has_back_bar else None]
            for set_id in set(body) | set(front) | set(back)}


def _default_set_name(set_id: str) -> Optional[str]:
    from gear_set_database_optimized import gear_set_db
    return gear_set_db.get_set_name_by_set_id(set_id)


def _default_is_mythic(set_name: str) -> bool:
    from gear_set_database_optimized import gear_set_db
    info = gear_set_db.get_set_info(set_name) or {}
    return info.get("set_type") == MYTHIC_SET_TYPE


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def gear_rows(gear: Dict[str, List[str]],
              set_name_of: Optional[Callable[[str], Optional[str]]] = None,
              is_mythic: Optional[Callable[[str], bool]] = None,
              poisons: Optional[Dict[str, dict]] = None) -> List[dict]:
    """A player's equipment as one dict per logged slot, in display order.

    *gear* is slot -> the item's eleven log fields. Each dict has 'slot',
    'item_id', 'set_id', 'set' (the LibSets name, 'Set#<id>' for an unknown
    id, '' for an item of no set), 'mythic', 'quality', 'trait', 'enchant'
    and 'enchant_quality' as logged, 'cp', 'level', and 'pieces' (see
    piece_counts; None for an item of no set). A poison has 'name' and no
    trait or enchant. The lookups default to the bundled set data and poison
    table; tests pass their own.
    """
    set_name_of = set_name_of or _default_set_name
    is_mythic = is_mythic or _default_is_mythic
    counts = piece_counts(gear)
    rows = []
    for slot in SLOT_ORDER:
        item = gear.get(slot)
        if not item or len(item) < 11:
            continue
        cp, level = item[2] == "T", _to_int(item[3])
        row = {"slot": slot, "item_id": str(item[1]), "set_id": "", "set": "",
               "mythic": False, "quality": str(item[5]), "trait": "", "enchant": "",
               "enchant_quality": "", "cp": cp, "level": level, "pieces": None}
        if slot in POISON_SLOTS:
            row["name"] = poison_name(item[1], cp, level, poisons)
        else:
            set_id = _set_id(item)
            if set_id:
                name = set_name_of(set_id)
                row.update(set_id=set_id, set=name or f"Set#{set_id}",
                           mythic=bool(name and is_mythic(name)),
                           pieces=counts.get(set_id))
            row.update(trait=str(item[4]), enchant=str(item[7]))
            if enchant_label(item[7]):
                row["enchant_quality"] = str(item[10])
        rows.append(row)
    return rows


def build_fields(gear: Dict[str, List[str]], effect_ids: Iterable[str],
                 name_of: Callable[[str], Optional[str]],
                 icon_of: Callable[[str], Optional[str]]) -> dict:
    """The build keys of a fight entry's player dict: 'gear', 'mundus', and
    'food' (left out when the food table cannot be loaded, so a frontend can
    tell "no food" from "not checked")."""
    effect_ids = [str(e) for e in effect_ids or []]
    fields = {"gear": gear_rows(gear or {}),
              "mundus": mundus_stones(effect_ids, name_of, icon_of)}
    table = food_table()
    if table is not None:
        fields["food"] = food_buff(effect_ids, name_of, table)
    return fields
