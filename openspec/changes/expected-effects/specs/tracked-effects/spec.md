# tracked-effects

## MODIFIED Requirements

### Requirement: Rules are plain text, one per line

The app SHALL read the user's tracked effects from a text of one rule per line, `Name = ability ids on <scope> [stacks | each] [expected <sizes>]`, where ids are whole numbers separated by spaces or commas, `<scope>` is one of `self`, `group`, `pets`, `boss`, `enemies` (default `group`), `uptime`, `stacks` or `each` names the measurement (default `uptime`; two measurement words on one line are an error), and `expected` is followed by one or more of `solo`, `small`, `large` and `all`, in any order, separated by spaces or commas; `expected` with no size word means `all`, and `all` means `solo`, `small` and `large`. The words after the `=` may come in any order. A size word without `expected` before it is an error. Blank lines and lines starting with `#` are ignored. A line that cannot be read is reported with its line number and skipped; the other rules still apply. The words `expected <sizes>` after a HyperTools export string apply to the rules it gives.

#### Scenario: A rule line
- **WHEN** the text is `Off-Balance = 45902 62988, 39077 on boss`
- **THEN** one rule named `Off-Balance` with the three ids, scope `boss`, measurement `uptime`, expected in no group size

#### Scenario: Expected in two sizes
- **WHEN** the text is `Taunt = 38254 on boss each expected small large`
- **THEN** one rule with measurement `each`, expected in small and large groups and not solo

#### Scenario: Expected alone, and all
- **WHEN** the text is `Crux = 184220 on self stacks expected` or `Crux = 184220 expected all on self stacks`
- **THEN** one rule expected in every group size

#### Scenario: A size word out of place
- **WHEN** the text is `Mine = 3 on boss large`
- **THEN** no rule is read AND the error names line 1 and says the word belongs after `expected`

#### Scenario: A bad line is reported and skipped
- **WHEN** the text has three lines, the second of which is `Bad scope = 3 on mobs`
- **THEN** two rules are read AND one error names line 2

### Requirement: The uptime line's items are rules

A fresh install's rules SHALL begin with the six group buffs (`Major Courage`, `Major Force`, `Major Slayer`, `Powerful Assault`, `Lucent Echoes`, `Pearlescent Ward`, each `on group expected large`) and `Taunt = 38254 on boss each expected small large`, before the seven boss debuffs, which carry no `expected`; the example picker SHALL list these first, with the same words. The app SHALL track no effect outside the rules. A rules text saved before the line's items became rules (no `tracking.version` in the config) SHALL be given, once, the lines of those seven whose names it lacks, in front of it. A rules text saved before `expected` existed (`tracking.version` below 3) SHALL have the default's `expected` words appended, once, to each of its lines whose rule name is one of the seven and that has no `expected` of its own; every other line is left as written.

#### Scenario: Deleting a group buff
- **WHEN** the user removes the `Major Slayer` line and saves
- **THEN** no Major Slayer item appears on the uptime line AND the picker offers `Major Slayer on the group` to add back

#### Scenario: An older config
- **WHEN** a config holds `tracking.rules` of `Mine = 1 on boss` and no `tracking.version`
- **THEN** the rules read are the seven default lines, `expected` words included, followed by `Mine = 1 on boss`

#### Scenario: A 0.9.0 config
- **WHEN** a config holds `tracking.version` 2 and the lines `Major Courage = 109966 on group`, `Taunt = 38254 on boss each`, `Mine = 1 on boss`
- **THEN** the rules read are `Major Courage = 109966 on group expected large`, `Taunt = 38254 on boss each expected small large` and `Mine = 1 on boss`, in that order

#### Scenario: A renamed or edited line is left alone
- **WHEN** a 0.9.0 config holds `Courage = 109966 on group` and `Major Force = 61747 on group expected all`
- **THEN** both lines are read as written

## ADDED Requirements

### Requirement: An item is shown when seen or expected

For each rule and fight, the app SHALL class the fight's group size as `solo` (one player), `small` (two to four players) or `large` (five or more), counting the players the fight lists. The rule's item SHALL be shown on the uptime line, in the fight pane and in the copied text, when its effect was on at least one unit of its scope during the fight, or when the rule is expected in the fight's group size; otherwise the item SHALL be left off. A fight with no item to show SHALL have no uptime line. When the fight's group size is unknown, every item is shown.

#### Scenario: A trial buff in a dungeon
- **WHEN** a rule `Major Slayer = 93109 on group expected large` AND a four-player fight in which no one had Major Slayer
- **THEN** the uptime line has no Major Slayer item

#### Scenario: A trial buff missing in a trial
- **WHEN** the same rule AND a twelve-player fight in which no one had Major Slayer
- **THEN** the uptime line reads `Major Slayer:0%`

#### Scenario: Seen though not expected
- **WHEN** the same rule AND a four-player fight in which Major Slayer was on a player for 20% of the fight
- **THEN** the uptime line reads `Major Slayer:20%`

#### Scenario: Nothing to show
- **WHEN** a solo fight AND no rule is expected solo AND no rule's effect appeared
- **THEN** the fight has no uptime line

### Requirement: The timeline strip shows the same items

When the timeline strip replaces the uptime line, every item shown on the line SHALL be a row of the strip: a rule whose effect never occurred but is expected in the fight's group size SHALL have a row with an empty track and `0%` in its label, and a rule that is neither seen nor expected SHALL have no row.

#### Scenario: An expected buff that never came
- **WHEN** the strip is on AND a rule `Lucent Echoes = 220015 on group expected large` AND a twelve-player fight in which the buff never appeared
- **THEN** the strip has a `Lucent Echoes:0%` row with nothing drawn on its track

#### Scenario: An unexpected buff that never came
- **WHEN** the strip is on AND the same rule AND a four-player fight in which the buff never appeared
- **THEN** the strip has no Lucent Echoes row
