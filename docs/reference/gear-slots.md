# ESO Encounter Log Gear Slot Structure

## Overview

Each `PLAYER_INFO` line lists one entry per **equipped** item. An empty slot has no entry at all, so the list varies in length, and a two-handed weapon is simply a main hand with no off hand beside it.

The facts below come from a survey of 32 encounter logs written by game version `eso.live.12.1` in October 2026 (4,279 `PLAYER_INFO` lines). 66 of those lines had an empty equipment list.

## Slot names

Seventeen slot names occur. The count is the number of lines, out of the 4,213 with any equipment, that listed the slot.

| Slot name | Item | Lines | Notes |
|-----------|------|-------|-------|
| `HEAD` | Helmet | 4,213 | |
| `SHOULDERS` | Shoulders | 4,213 | |
| `CHEST` | Chest | 4,213 | |
| `HAND` | Gloves | 4,213 | The log says `HAND`, not "arms" or "hands" |
| `WAIST` | Belt | 4,213 | The log says `WAIST`, not "belt" |
| `LEGS` | Legs | 4,213 | |
| `FEET` | Boots | 4,213 | |
| `NECK` | Necklace | 4,213 | |
| `RING1` | First ring | 4,213 | |
| `RING2` | Second ring | 4,213 | |
| `MAIN_HAND` | Front-bar main hand | 4,213 | |
| `OFF_HAND` | Front-bar off hand or shield | 2,501 | Absent beside a two-handed weapon |
| `POISON` | Front-bar poison | 122 | Only when a poison is slotted |
| `BACKUP_MAIN` | Back-bar main hand | 3,931 | Absent for one-bar builds |
| `BACKUP_OFF` | Back-bar off hand or shield | 149 | Absent beside a two-handed weapon |
| `BACKUP_POISON` | Back-bar poison | 62 | Only when a poison is slotted |
| `COSTUME` | Costume | 164 | Cosmetic; the app ignores it |

## Item fields

Every entry has eleven fields (see [encounterlog-format.md](encounterlog-format.md)):

```
[slot, id, isCP, level, trait, displayQuality, setId, enchantType, isEnchantCP, enchantLevel, enchantQuality]
```

Examples:

```
[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,MAGICKA,T,16,LEGENDARY]
[MAIN_HAND,133257,T,16,WEAPON_CHARGED,LEGENDARY,361,POISONED_WEAPON,T,16,LEGENDARY]
[POISON,79690,F,1,NONE,LEGENDARY,0,INVALID,F,0,NORMAL]
```

- **`isCP`, `level`**: `T,16` is champion rank 160, `T,15` champion rank 150, `F,32` level 32.
- **`trait`**: prefixed by item kind, for example `ARMOR_DIVINES`, `WEAPON_NIRNHONED`, `JEWELRY_BLOODTHIRSTY`; `NONE` for none. `ARMOR_PROSPEROUS` is the Invigorating trait.
- **`displayQuality`**: `TRASH`, `NORMAL`, `MAGIC` (Fine; the one value the survey did not meet), `ARCANE` (Superior), `ARTIFACT` (Epic), `LEGENDARY`. A mythic item is logged as `LEGENDARY`; only its set says it is mythic.
- **`setId`**: the game's set id, `0` for an item of no set. The app names it through the LibSets data.
- **`enchantType`**: for example `MAGICKA`, `FIERY_WEAPON`, `BERSERKER` (the Weapon Damage glyph), `INCREASE_SPELL_DAMAGE`; `INVALID` for no enchant.
- **`enchantQuality`**: the same quality names as `displayQuality`.
- **Poisons** carry an item id and a quality, and nothing in the trait, set and enchant fields. The item id is all the log says about which poison it is.

## What the log does not carry

Item names, weapon types (dagger or staff) and armor weights are not logged. The line is written once per fight, as combat starts, so gear swapped during a fight does not show.

## Where the app reads this

`src/player_build.py` turns these entries into the build window's gear rows: slot order, readable trait, quality and enchant names, set piece counts per weapon bar, and poison names from `data/items/poisons_en.json`.

Armor weight is shown although the log lacks it. The item id of each piece in the seven armor slots is looked up in `data/items/armor_weights.json`, the item ids of every light, medium and heavy armor piece in UESP's item database. All 905 armor item ids found in 48 logs of April to October 2026 were in it.

It also answers the one weapon-type question the app asks, whether a restoration staff is equipped (the role heuristic uses it to tell healers). The log has no weapon types, so the main-hand item ids are looked up in `data/items/restoration_staves.json`, the item ids of every restoration staff in UESP's item database.
