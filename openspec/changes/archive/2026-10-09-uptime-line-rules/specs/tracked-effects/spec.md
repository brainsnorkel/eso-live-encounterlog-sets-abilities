# tracked-effects

## MODIFIED Requirements

### Requirement: Rules are plain text, one per line

The app SHALL read the user's tracked effects from a text of one rule per line, `Name = ability ids on <scope> [stacks | each]`, where ids are whole numbers separated by spaces or commas, `<scope>` is one of `self`, `group`, `pets`, `boss`, `enemies` (default `group`), and `uptime`, `stacks` or `each` names the measurement (default `uptime`; two measurement words on one line are an error). Blank lines and lines starting with `#` are ignored. A line that cannot be read is reported with its line number and skipped; the other rules still apply.

#### Scenario: A rule line
- GIVEN the text `Off-Balance = 45902 62988, 39077 on boss`
- THEN one rule named `Off-Balance` with the three ids, scope `boss`, measurement `uptime`

#### Scenario: Each
- GIVEN the text `Taunt = 38254 on boss each`
- THEN one rule with measurement `each`

#### Scenario: A bad line is reported and skipped
- GIVEN three lines, the second of which is `Bad scope = 3 on mobs`
- THEN two rules are read AND one error names line 2

### Requirement: A rule measures the effect on units of its scope

For each rule and fight, the app SHALL measure the effect across every unit of the rule's scope: `self` is the player whose client writes the log, `group` any player in the group, `pets` a unit the log names as a group member's pet, `boss` a hostile the game flags as a boss, `enemies` any hostile. An effect under any of the rule's ids counts. Uptime is the share of the fight during which the effect was on at least one unit of the scope. Stacks is the mean stack count over that time, taking the highest count among the units it was on, with the peak count. Each is the mean over the units of the scope of each unit's own share, measured over the time the unit was in the fight: from the fight's start or the unit's arrival to the fight's end or the unit's death or removal; a unit of the scope the effect never reached counts as 0. Spans that began before the pull count from the fight's start; spans still open at its end count to the end. A unit's death or removal SHALL end its open spans at that moment, since the log does not always write FADED for them, and a zone change SHALL end the open spans on hostiles and pets.

#### Scenario: Two ids on the boss overlap
- GIVEN a rule `OB = 45902 62988 on boss` AND 45902 on the boss from 10 s to 20 s AND 62988 on it from 15 s to 25 s in a 60 s fight
- THEN its uptime is 25%

#### Scenario: Each boss to its death
- GIVEN a rule `Taunt = 38254 on boss each` AND two bosses, one taunted for 30 s and killed at 40 s, the other taunted for 20 s of a 60 s fight
- THEN the rule reads 54% (the mean of 75% and 33%)

#### Scenario: A corpse's effect
- GIVEN a rule on `enemies` AND the effect on a mob from 0 s AND the mob dies at 10 s with no FADED line, in a 20 s fight
- THEN the rule reads 50% AND the next fight in the zone reads 0%

#### Scenario: Out of scope
- GIVEN a rule on `boss` AND the effect lands on a mob and on a player, in a fight where a boss was hit
- THEN the rule measures 0%

## ADDED Requirements

### Requirement: A fight without a boss measures the pack

In a fight in which the group hit no hostile the game flags as a boss, a `boss` rule SHALL measure every hostile the group fought, and a `boss` or `enemies` rule whose effect reached at least one mob SHALL append how many of the pack's mobs it reached and how many the pack held, `on N of M mobs`, where the pack is the mobs the group hit plus any a tracked effect landed on (an effect that reached none reads `0%` alone). The rule's item SHALL say it measured `mobs` (the timeline row shows the word). In a fight where a boss was hit, a `boss` rule measures the bosses alone and no count is shown.

#### Scenario: Alkosh in a trash pack
- GIVEN a rule `Alkosh = 76667 on boss` AND a fight in which the group hit twelve mobs and no boss AND the debuff was on seven of them, together covering 45% of the fight
- THEN the item reads `Alkosh:45% on 7 of 12 mobs`

#### Scenario: A boss fight
- GIVEN the same rule AND a fight in which the group hit a boss and its adds AND the debuff was on the adds only
- THEN the item reads `Alkosh:0%`

### Requirement: The uptime line's items are rules

A fresh install's rules SHALL begin with the six group buffs (`Major Courage`, `Major Force`, `Major Slayer`, `Powerful Assault`, `Lucent Echoes`, `Pearlescent Ward`, each `on group`) and `Taunt = 38254 on boss each`, before the seven boss debuffs; the example picker SHALL list these first. The app SHALL track no effect outside the rules. A rules text saved before this change (no `tracking.version` in the config) SHALL be given, once, the lines of those seven whose names it lacks, in front of it.

#### Scenario: Deleting a group buff
- GIVEN the user removes the `Major Slayer` line and saves
- THEN no Major Slayer item appears on the uptime line AND the picker offers `Major Slayer on the group` to add back

#### Scenario: An older config
- GIVEN a config with `tracking.rules` of `Mine = 1 on boss` and no `tracking.version`
- THEN the rules read are the seven lines followed by `Mine = 1 on boss`
