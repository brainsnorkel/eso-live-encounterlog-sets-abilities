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