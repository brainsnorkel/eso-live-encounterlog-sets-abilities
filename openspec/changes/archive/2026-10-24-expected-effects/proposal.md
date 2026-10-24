# Proposal: Expected effects on the uptime line

## Why

Since 0.9.0 every rule is an item on the uptime line of every fight, reading `0%` when its effect never appeared, so a four-player dungeon fight shows ten zeros on average among its fourteen items (the trial buffs, the boss debuffs no one in the group applies), a solo fight thirteen, and a trial fight six (196 fights of 13 split logs of 2026, see design.md). Issue #13 asks for a way to say which rules are *expected* for a given group size: an expected rule stays on the line whether or not its effect was present, so a missing Major Courage in a trial reads `0%` and stands out, while a rule that is not expected shows only when its effect was seen. This answers the open question left by 0.8.0 and 0.9.0 (whether an item that reads 0 should be shown at all) with a per-rule, per-group-size choice.

## What Changes

- **`expected` in the rule text**: a rule line may end with `expected` followed by one or more of `solo` (one player), `small` (two to four players), `large` (five or more) or `all` (the three together); `expected` on its own means `all`. The words sit anywhere after the `=`, like `on <scope>` and `stacks`, and work after a HyperTools export string too.
- **An item is shown when its effect was seen, or when its rule is expected for the fight's group size**; otherwise it is left off the uptime line and out of the copied text. A fight with nothing to show has no line, as before 0.9.0.
- **The timeline strip follows the line**: a rule shown without any occurrence gets an empty row reading `0%`, so the gap is visible in the strip too; a rule that is neither seen nor expected has no row (as today).
- **Defaults**: the six group buffs become `expected large` and the taunt `expected small large`; the boss debuffs and Crux stay unflagged (shown when seen). The example picker's lines carry the same words.
- **A saved rules text is upgraded once**: a rule saved by 0.9.0 under one of the seven uptime-line names, with no `expected` word of its own, is given the default's words, so the group buffs do not vanish from a trial fight that lacks one. Any other line is left exactly as written.
- Settings help text, the README, the user guide and the design notes describe the word and the rule for showing an item.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `tracked-effects`: the rule grammar gains `expected <sizes>`; the requirement that every rule is an item of every fight is replaced by the seen-or-expected rule; the default rules and examples carry `expected`; a saved rules text is upgraded by name.

## Impact

- Engine: `effect_rules` (the `expected` words in the parser and `Rule`, the group-size classes, `seen`, `expected` and `shown` per snapshot item, the defaults and examples), `esolog_tail` (the uptime line built from the shown items only), `app_config` (`tracking.version` 3 and the one-time upgrade of the seven lines).
- GUI: the strip adds a row for every shown item, with or without intervals; Settings help text.
- Behaviour: fewer items on the line in small groups and solo play; a trial fight reads the same as today except that a boss debuff no one applied is left off.
- Docs: README, user guide, changelog, `docs/design.md` regenerated from the docstrings.
