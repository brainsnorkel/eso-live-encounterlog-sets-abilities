"""
Group members who leave, come back, or come back on another character
(engine side, no Qt). Issue #78.

Design: a group list should name the people who were in the fight, once
each. Before this, a member who left stayed on the list at 0 dps in every
later fight of the zone (656 of 9,435 fights in the split logs, 1,256 stale
rows), a member who came back on a new unit id got a second row, and a
member back on another character had no row in the fight they came back to
while their damage was in the group total. The rules below were chosen so
that a player with no UNIT_REMOVED and no second UNIT_ADDED in the zone
keeps every figure they had.

What the log writes, from 386 unique sessions (October 2026):

- ``Offline`` is a loading placeholder: a UNIT_ADDED named ``Offline`` with
  the handle and character id intact, replaced by the real unit (a new unit
  id) within 0 to 29 s. It is skipped.
- Leaving is UNIT_REMOVED. Coming back is always a fresh UNIT_ADDED: the
  same character keeps its character id, and its unit id only on an
  instance reload (a ZONE_CHANGED between, which starts the zone afresh
  anyway). Without a zone change the id is always new.
- Another character of the same account is the same handle with a new
  character id (and a new per-session id); its PLAYER_INFO comes at the
  next pull, or never. In 14 of 17 cases the old character's unit was never
  removed.
- A player's UNIT_CHANGED never changes who they are, except an anonymous
  member (empty name and handle) becoming named on joining the group.
- A departed player's unit id can be handed to a monster.

The rules (Chris, 2026-10-27):

1. A player is their character: handle and character id, the character id
   alone being unique. Rows stay per character.
2. UNIT_REMOVED marks the player gone (``left_at``). The fight in progress
   keeps their row, greyed, with the share of the fight they were there for
   (present_share); from the next BEGIN_COMBAT they are off the list. A
   MONSTER added on their unit id marks them gone too, and that id is no
   longer theirs.
3. The same character back in the zone is the same row: the new unit id is
   an alias of the record, so the damage before and after the drop lands on
   one row and its dps time spans both, the gap included (as Combat Metrics
   counts it). At the next BEGIN_COMBAT the record takes the new id as its
   own, its companion and pets following, so later fights are keyed as for
   anyone else.
4. Another character is a new row, and the old character is gone. Until its
   PLAYER_INFO arrives it has no build; it is listed anyway, with the class
   from UNIT_ADDED and empty bars, when the log says it is grouped with the
   logging player, so the fight's rows add up to its group total. Anyone
   else without a build stays off the list, as before (passers-by in the
   Infinite Archive and overland).
5. Offline stays skipped.
6. An anonymous member named by a UNIT_CHANGED takes that name and handle.
7. A companion follows its owner: its row is keyed by the owner's record,
   so a re-summon, or a summon on the owner's new unit id, is the same row,
   and it leaves the list with its owner.

What is per unit id and not merged in the fight a member comes back to:
the timeline strip, the uptime spans and the pen/crit buffs on them, which
the trackers keep by the unit id the log names. From the next pull they
are keyed as for anyone else.
"""

def present_share(start_ms: int, end_ms: int, joined_ms: int | None,
                  left_ms: int | None) -> float:
    """The percentage of the fight from *start_ms* to *end_ms* that a player
    who joined at *joined_ms* (None: before the fight) and left at *left_ms*
    (None: still there) was present for."""
    span = end_ms - start_ms
    if span <= 0:
        return 0.0
    since = max(start_ms, joined_ms if joined_ms is not None else start_ms)
    until = min(end_ms, left_ms if left_ms is not None else end_ms)
    return max(0, until - since) / span * 100
