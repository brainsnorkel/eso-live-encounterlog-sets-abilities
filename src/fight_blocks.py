"""
The fights of one instance, as the fight list groups them (issue #129),
in one place with no Qt: gui.fight_list draws them as blocks, the engine
reads the newest one for the pulls' 'Cut' and 'group went on'
(pull_outcome.mark_context), and the session recap writes one per block
(session_recap). gui.fight_list's docstring has the design.

A new block starts at a fight in another zone or at another difficulty
than the fight before, or at the first fight after a completed run, even
in the same zone. The zone is told by its id (a solo dungeon shares its
name with the group dungeon) and by its name only when the entry has none.
"""

DIFFICULTY_NAMES = {"VETERAN": "Veteran", "NORMAL": "Normal"}


def difficulty_of(entry) -> str:
    """'VETERAN', 'NORMAL' or '' (an entry from before the difficulty was
    kept reads its old is_vet)."""
    difficulty = str(getattr(entry, "difficulty", "") or "").upper()
    if not difficulty and getattr(entry, "is_vet", False):
        difficulty = "VETERAN"
    return difficulty


def block_key(entry) -> tuple:
    """What fights of one block share: the zone and its difficulty."""
    zone = str(getattr(entry, "zone_id", "") or "") or str(entry.zone_name or "")
    return zone, difficulty_of(entry)


def starts_block(previous, entry) -> bool:
    """Whether *entry* opens a block after *previous* (None: the first)."""
    return (previous is None or block_key(previous) != block_key(entry)
            or bool(getattr(previous, "trial_result", None)))


def header_text(entry) -> str:
    """'Sunspire · Veteran'; the name alone for a zone without one."""
    zone = entry.zone_name or "Unknown"
    difficulty = DIFFICULTY_NAMES.get(difficulty_of(entry))
    return f"{zone} · {difficulty}" if difficulty else zone


def blocks(entries) -> list:
    """*entries* in their blocks, in order."""
    out, previous = [], None
    for entry in entries:
        if starts_block(previous, entry):
            out.append([])
        out[-1].append(entry)
        previous = entry
    return out


def last_block(entries) -> list:
    """The newest block of *entries*, read back from the end."""
    out = []
    for entry in reversed(entries):
        if out and starts_block(entry, out[-1]):
            break
        out.append(entry)
    out.reverse()
    return out
