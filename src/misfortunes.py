"""The Misfortunes a solo dungeon run was started with (engine side, no Qt).
Issue #70.

The solo dungeons of October 2026 (pen_crit.SOLO_DUNGEON_ZONES: March of
Sacrifices 1592, Moon Hunter Keep 1593) let the player pick Misfortunes at
the door, each one making the run harder. The log writes each picked
Misfortune as a DEBUFF on the player, gained at the door and never faded,
and every PLAYER_INFO line of the run lists its id among the player's
long-term effects (the 2026-10-26 solo Moon Hunter Keep run: six lines, six
hits for each of the three), so the logging player's long_term_effects at
BEGIN_COMBAT, the list the food rule and the passives already read, carry
them at every pull and no new parsing is needed.

Known ids: Warm Welcome 269749, Revoke of Respite 269803 and Alleviating
Assault 269792 from that run; Weary Submission 269799 and Pulled Punches
269804 from the 2026-10-25 solo March of Sacrifices run, which picked those
two and Warm Welcome (each of its PLAYER_INFO lines lists all three). The
texts are the game's own descriptions (the client's en.lang, table
132143172 by ability id), shortened; where the game leaves the figure to a
placeholder, the figure is the hyperioxes.com guide's (Revoke of Respite's
50%), the log's (Alleviating Assault's heals: 5,100 on trash, 8,160 on a
boss) or left out (Weary Submission's). Every ABILITY_INFO icon of these
effects starts with ``debuff_solodungeon_`` (``..._monster_warmwelcome``,
``..._player_pulledpunches``, ``..._player_wearywarriorssubmission``), so a
long-term effect whose icon stem starts with that is named by its logged
name, with no text, until its id goes in the table.

The engine stores them on the fight entry (entry.misfortunes, a list of
[name, text]), in the table's order whatever order the log lists them in
(it differed between pulls of one run): None outside a solo dungeon, so the
fight pane shows nothing there and an entry built before this renders as
before; [] in a solo dungeon run without Misfortunes, which the pane shows
as ``Misfortunes: none``.
"""

from collections.abc import Callable, Iterable

# ability id -> (name, what it does)
MISFORTUNES: dict[str, tuple[str, str]] = {
    "269749": ("Warm Welcome", "Enemies deal double damage"),
    "269803": ("Revoke of Respite", "Healing taken is reduced by 50%"),
    "269792": ("Alleviating Assault",
               ("Direct damage on an enemy heals it: 5,100 on trash, 8,160 on a "
                "boss, at most every 3 seconds")),
    "269799": ("Weary Submission", "Health, stamina and magicka recovery are reduced"),
    "269804": ("Pulled Punches", "You deal 30% less damage from all sources"),
}

# The icon stem every Misfortune's ABILITY_INFO line has been seen with
ICON_PREFIX = "debuff_solodungeon_"


def run_misfortunes(effect_ids: Iterable[str], icon_of: Callable[[str], str],
                    name_of: Callable[[str], str]) -> list[tuple[str, str]]:
    """The Misfortunes among a player's long-term *effect_ids*, as (name,
    text), each once: the known ids in the table's order, by the table,
    then any other id whose icon stem (*icon_of*) starts with ICON_PREFIX,
    by its logged name (*name_of*) and with no text."""
    ids = [str(ability_id) for ability_id in effect_ids]
    found = [item for ability_id, item in MISFORTUNES.items() if ability_id in ids]
    names = {name for name, _text in found}
    for ability_id in ids:
        if ability_id not in MISFORTUNES and (icon_of(ability_id) or "").startswith(ICON_PREFIX):
            name = name_of(ability_id) or ability_id
            if name not in names:
                names.add(name)
                found.append((name, ""))
    return found
