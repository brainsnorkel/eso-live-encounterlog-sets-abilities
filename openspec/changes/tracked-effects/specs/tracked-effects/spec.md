# tracked-effects

User-defined effect rules, in a text anyone can share, measured per fight.

## Requirements

### Requirement: Rules are plain text, one per line

The app SHALL read the user's tracked effects from a text of one rule per line, `Name = ability ids on <scope> [stacks]`, where ids are whole numbers separated by spaces or commas, `<scope>` is one of `self`, `group`, `pets`, `boss`, `enemies` (default `group`), and `stacks` or `uptime` names the measurement (default `uptime`). Blank lines and lines starting with `#` are ignored. A line that cannot be read is reported with its line number and skipped; the other rules still apply.

#### Scenario: A rule line
- GIVEN the text `Off-Balance = 45902 62988, 39077 on boss`
- THEN one rule named `Off-Balance` with the three ids, scope `boss`, measurement `uptime`

#### Scenario: A bad line is reported and skipped
- GIVEN three lines, the second of which is `Bad scope = 3 on mobs`
- THEN two rules are read AND one error names line 2

### Requirement: HyperTools export strings are rules

A line that starts with `$` SHALL be read as a HyperTools tracker export string. Each tracker in it that names ability ids becomes a rule: its name, its ids (the tracker's own and its effect events'), and its target (`Yourself` → self, `Group` and `Group Member` → group, `Boss` and `Current Target` → boss). Groups are walked and children inherit the group's target. Words after the string (`stacks`, `on boss`) apply to every rule it gives. A string that decodes to no ids is an error for that line.

#### Scenario: A pasted HyperTools tracker
- GIVEN a line holding a HyperTools export of a tracker named `Major Resolve` targeting `Yourself` with ids 61694 and 61693
- THEN one rule `Major Resolve` with those ids and scope `self`

### Requirement: A rule measures the effect on units of its scope

For each rule and fight, the app SHALL measure the effect across every unit of the rule's scope: `self` is the player whose client writes the log, `group` any player in the group, `pets` a unit the log names as a group member's pet, `boss` a hostile the game flags as a boss, `enemies` any hostile. An effect under any of the rule's ids counts. Uptime is the share of the fight during which the effect was on at least one unit of the scope. Stacks is the mean stack count over that time, taking the highest count among the units it was on, with the peak count. Spans that began before the pull count from the fight's start; spans still open at its end count to the end.

#### Scenario: Two ids on the boss overlap
- GIVEN a rule `OB = 45902 62988 on boss` AND 45902 on the boss from 10 s to 20 s AND 62988 on it from 15 s to 25 s in a 60 s fight
- THEN its uptime is 25%

#### Scenario: Stacks on the logging player
- GIVEN a rule `Crux = 184220 on self stacks` AND Crux at 1, 2 and 3 stacks for 10 s each in a 40 s fight
- THEN the mean is 2.0, the peak 3 and the uptime 75%

#### Scenario: Out of scope
- GIVEN a rule on `boss` AND the effect lands on a mob and on a player
- THEN the rule measures 0%

### Requirement: Tracked effects appear on the uptime line

For every fight, each rule SHALL add an item to the uptime line after the built-in buffs and the taunt, whatever the group size: `Name:NN%` for uptime, `Name:mean/peak` for stacks (`Name:0` when the effect never appeared). The items appear in the fight pane and in the copied text of the fight.

#### Scenario: A solo fight
- GIVEN one player in the group AND a `Crux ... on self stacks` rule
- THEN the uptime line shows `Crux:2.0/3` even though the built-in group buffs are not shown

### Requirement: Rules live in Settings and start as the bundled examples

Settings SHALL show the rule text in an editable box with the number of rules it holds and the errors of lines it skips, and keep the text in the per-user settings; saving applies the rules by restarting monitoring. A fresh install starts with the examples of issue #10. An Examples button SHALL open a picker listing a library of example rules, each with a title, what it tells you and its line; the user ticks rules and adds them under the box's text (a rule whose name the box already has starts unticked and is never added twice) or copies the ticked lines to the clipboard to share.

#### Scenario: Picking examples
- GIVEN the box holds `Mine = 1 on boss` AND the picker is opened and two examples ticked
- THEN the two lines are appended under it AND the status says 2 rules added

#### Scenario: Live feedback
- GIVEN the box holds four good lines and one bad line
- THEN the status under it says 4 rules and names the bad line

### Requirement: Timeline rows for tracked effects

When the experimental timeline strip is on, the strip SHALL show one row per rule after the built-in rows, labelled with the rule's uptime-line text; a stacking effect's filled bar SHALL vary in height with the stack count, the peak reaching the row's full height. Every row, built-in or tracked, SHALL say whose effect it is beside its label (`group`, `self`, `pets`, `boss` or `enemies`): the built-in group buffs are `group`, Major Vulnerability and Taunt are `boss`.

#### Scenario: Scope beside each row
- GIVEN the strip shows Major Force, Taunt and a `Crux ... on self stacks` rule
- THEN the rows read `group`, `boss` and `self` beside their labels

#### Scenario: Stacks drawn by height
- GIVEN a `stacks` rule whose effect held 1 then 3 stacks
- THEN the first part of the bar is a third of the row's height and the second the full height
