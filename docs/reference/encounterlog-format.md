## Unofficial encounter log version 15 documentation:

All lines begin with the time in milliseconds since logging began and the line type. Every field is comma separated. All strings are annotated with "surrounding" inverted commas. All texturePaths and iconPaths are filepaths to BC3 DXT5 DirectDraw Surface files which can be extracted using [EsoExtractData](https://en.uesp.net/wiki/ESO_Mod:EsoExtractData). Timestamps are Unix time in milliseconds. Booleans are represented using T or F characters.

`<unitState>` refers to the following fields for a unit: unitId, health/max, magicka/max, stamina/max, ultimate/max, werewolf/max, shield, mapNormalisedX, mapNormalisedY, headingRadians.

`<targetUnitState>` is replaced with an asterisk if the source and target are the same.

`<equipmentInfo>` refers to the following fields for a piece of equipment: slot, id, isCP, level, trait, displayQuality, setId, enchantType, isEnchantCP, enchantLevel, enchantQuality.

`<scribingInfo>` refers to the following fields for an ability: focusScript, signatureScript, affixScript. The game writes each (abilityId, scripts) combination once per BEGIN_LOG session, directly before the PLAYER_INFO of the first player seen with it, and one abilityId covers several focus scripts of a grimoire, so the scripts belong to that player rather than to the id. The same ability is also written once without `<scribingInfo>`. `src/scribing.py` has the details and the measurements behind them.

## Line types

BEGIN_LOG, timeSinceEpochMS, logVersion, realmName, language, gameVersion

END_LOG

BEGIN_COMBAT

END_COMBAT

The game also writes END_COMBAT and then BEGIN_COMBAT, with every group member's PLAYER_INFO again, in the middle of a fight. It happens most often as the logging player accepts a resurrection: 48 logs of April to October 2026 held 53 such pairs, 0 to 484 ms apart, 45 of them straight after a `SOUL_GEM_RESURRECTION_ACCEPTED` on the logging player. The engine treats such a pair as one fight (`COMBAT_RESUME_MS` in `src/esolog_tail.py`).

BEGIN_COMBAT and END_COMBAT follow the logging player's combat state, not the group's: a group member's hit often lands first. In 393 split logs of January to October 2026 (8,816 fights), a player's hit or taunt came before the BEGIN_COMBAT line in 4,243 fights (48.1%), a median 14 ms early, often in the line's own millisecond and written before it. See "Who acted first" below and `src/fight_opener.py`.

PLAYER_INFO, unitId, [longTermEffectAbilityId,...], [longTermEffectStackCounts,...], [`<equipmentInfo>`,...], [primaryAbilityId,...], [backupAbilityId,...]

BEGIN_CAST, durationMS, channeled, castTrackId, abilityId, `<sourceUnitState>`, `<targetUnitState>`

END_CAST, endReason, castTrackId, interruptedAbilityId, interruptingAbilityId:optional, interruptingUnitId:optional

COMBAT_EVENT, actionResult, damageType, powerType, hitValue, overflow, castTrackId, abilityId, `<sourceUnitState>`, `<targetUnitState>`

HEALTH_REGEN, effectiveRegen, `<unitState>`

UNIT_ADDED, unitId, unitType, isLocalPlayer, playerPerSessionId, monsterId, isBoss, classId, raceId, name, displayName, characterId, level, championPoints, ownerUnitId, reaction, isGroupedWithLocalPlayer

UNIT_CHANGED, unitId, classId, raceId, name, displayName, characterId, level, championPoints, ownerUnitId, reaction, isGroupedWithLocalPlayer

UNIT_REMOVED, unitId

EFFECT_CHANGED, changeType, stackCount, castTrackId, abilityId, `<sourceUnitState>`, `<targetUnitState>`, playerInitiatedRemoveCastTrackId:optional

ABILITY_INFO, abilityId, name, iconPath, interruptible, blockable, `<scribingInfo>`:optional

EFFECT_INFO, abilityId, effectType, statusEffectType, effectBarDisplayBehaviour, grantsSynergyAbilityId:optional

MAP_CHANGED, id, name, texturePath

ZONE_CHANGED, id, name, dungeonDifficulty

TRIAL_INIT, id, inProgress, completed, startTimeMS, durationMS, success, finalScore

BEGIN_TRIAL, id, startTimeMS

END_TRIAL, id, durationMS, success, finalScore, finalVitalityBonus

ENDLESS_DUNGEON_BEGIN, id, startTimeMS, unknownBoolean

ENDLESS_DUNGEON_END, id, durationMS, finalScore, unknownBoolean

ENDLESS_DUNGEON_STAGE_END, id, dungeonBeginStartTimeMS

ENDLESS_DUNGEON_BUFF_ADDED, id, abilityId

ENDLESS_DUNGEON_BUFF_REMOVED, id, abilityId

## Undocumented/unknown line types
ENDLESS_DUNGEON_INIT

## Taunts, as live logs record them

Found while building the taunt uptime line and the marks on taunting abilities (October 2026, twelve logs, 1,361 taunts):

- A taunt that lands writes `COMBAT_EVENT,TAUNTED,GENERIC,0,0,0,<castTrackId>,38254,<source>,<target>`. Its abilityId is always 38254 (the generic "Taunt"), so the event alone does not say which skill taunted. Its `castTrackId` is the one the taunting skill's own `BEGIN_CAST` and `COMBAT_EVENT` hits carry, which names the skill in every one of the 1,361 cases (1,357 through the cast, 4 through a hit alone).
- The game keeps one debuff on the taunted enemy, ability 38254 "Taunt", written as `EFFECT_CHANGED` GAINED, UPDATED (a fresh taunt while one is up) and FADED lines whose target unit state is the enemy's. Its spans are the taunt uptime.
- The skill a player slots is not always the id that casts and hits. Destructive Clench (38984) with an ice staff is logged as Frost Clench (38989), a separate id with the same icon (`ability_destructionstaff_005_a`); 175 of the 1,361 taunts were of that kind. Inner Rage, Pierce Armor, Ransack, Inner Fire, Inner Beast, Leashing Soul, Goading Throw and Chains of Dominance are logged under their slotted ids.
- `UNIT_ADDED` flags bosses with `isBoss` (the seventh field after the line type: `UNIT_ADDED,125,MONSTER,F,0,89037,T,...` is Nahviintaas). Enemies stay in the engine's unit list from fight to fight within a zone, so a boss is only measured in a fight that hit or taunted it.
- A TAUNTED can trail its skill's first hit by a millisecond, carrying the hit's `castTrackId`: 173 of 5,382 opening hits had the same player's TAUNTED 1 to 5 ms later.

## Who acted first, as live logs record it

Found while building the line under the fight pane that says who opened the fight (issue #159; 393 split logs, 8,816 fights):

- The log has no threat or aggro line. A hostile's `BEGIN_CAST` names its target in `<targetUnitState>`, and so does its `COMBAT_EVENT`, which is how the log shows whom a monster went for first. A monster acted before any player hit or taunt in 1,545 fights (17.5%).
- A `DAMAGE_SHIELDED` line names the absorbing shield's ability, not the attack. The attack follows on the next line with the same `castTrackId`, source, target and time, carrying the rest of the damage or 0: in one Halls of Fabrication log 10,077 of 10,111 partners were on the next line, and 520 absorb lines had none.
- A dead monster's leftover area or damage over time still writes hits on players after its `DIED_XP`, with the monster's health at 0 in the source unit state. A hazard is a unit named as its own ability (Scorching Barrier).
- A hostile monster's `UNIT_ADDED` is written lazily: in 30 logs, 96.6% came in the same millisecond as the monster's first logged line, and all within a second.
- `castTrackId` 0 occurs on real hits, Inspired Scholarship's procs among them, and names no cast.
- `mapNormalisedX` and `mapNormalisedY` are normalised to the map the last `MAP_CHANGED` named, usually from 0 to 1 but not always; the heading is in radians.

Found while building the fight's map (issue #148; 414 split logs):

- The x and y of every unit, not just the logging player's, are fractions of the **logging player's** current map. When that player's map changes, every unit's coordinates jump to the new map's frame: in Sunspire on 2026-09-23 a trash pull ran from the Shrine of Jone Vestibule into the Temple Grounds, and at the `MAP_CHANGED` all 23 units seen on both sides moved by a median 0.63 of the map's width, some to a y of 1.19, past the map's edge.
- Some maps share one frame: Kyne's Aegis's Lord Falgravn changes between his three floor maps (`KynesAegisBoss3Floor001` to `003`) up to five times in a fight, and across each change units moved a median of only 0.004 to 0.021.
- Right after a zone's first `MAP_CHANGED`, while the zone loads, unit states can carry coordinates that are not fractions at all: `212.9151,-195.2606` in Lucent Citadel on 2026-10-11.
- Sanity's Edge and Dreadsail Reef give every one of their sub-maps the zone's name, so a map is known by its `texturePath`. That path, lower-cased, is the map art in the client's `depot\eso.mnf`: `\art\maps\<path>_<n>.dds`, 256 px tiles numbered row by row from the top left (3×3 for most maps; 4×4 or 5×5 for some). The positions map straight onto the stitched tiles, with no offset or scale. The 282 paths in the split logs all have art there.
- The Night Market (Update 49's event zone) and its areas, Opulent Ordeal among them, and the Elinhir Private Arena log their `ZONE_CHANGED` difficulty as `NONE`, like overland zones.
- `HEALTH_REGEN`'s unit state carries a position too.