"""
Scribed skills: which scripts each player wrote into their grimoire skills
(engine side, no Qt).

A scribed skill is a grimoire (Banner Bearer, Wield Soul, ...) with a focus,
a signature and an affix script. The grimoire and the focus script give the
skill its name ("Shocking Banner" is Banner Bearer with Shock Damage); the
signature and affix scripts add effects that the name does not show. The
encounter log lists all three scripts after the two flags of the skill's
ABILITY_INFO line:

    ABILITY_INFO,217699,"Shocking Banner","/esoui/art/icons/ability_grimoire_support.dds",F,T,"Shock Damage","Class Flourish","Heroism"

The grimoire is not named, but every grimoire has its own icon (GRIMOIRES).

What the log does, as far as four logs from September 2025 to October 2026
show (225 ABILITY_INFO lines with scripts):

- An ability id does not identify the skill. One id covers several focus
  scripts of a grimoire (217699 is Fiery, Fortifying, Magical, Restorative,
  Shocking and Sundering Banner), so the name and the scripts of a bar slot
  belong to the player, not to the id.
- The game writes each (ability id, scripts) combination once per BEGIN_LOG
  session, directly before the PLAYER_INFO of the first player seen with it
  (0-1 ms earlier, with only other ABILITY_INFO lines in between). That
  PLAYER_INFO is how a combination is tied to a player.
- The game also writes the skill without scripts, as an ordinary
  seven-field line, once per session and id. Most of these lines come at
  another moment (46 of 60 in the October 2026 log, presumably when the
  skill is first used). The rest sit directly before a PLAYER_INFO, for a
  player whose scripts the game does not have; for 10 of those 11 players
  the scripts followed before a later PLAYER_INFO, 0 to 206 s on.
- A later player whose line was already written, with or without scripts,
  gets no line of their own. Their skill is then one of the lines written
  for that id: certain when there is one, otherwise a short list of options.
  The same holds for a player who re-scribes to a combination already
  written in the session; the log gives no sign of that change.

The approach follows the ESO Log Tool (github.com/sheumais/logs), which
renames scribed skills to "Name (Signature / Affix)" before uploading logs.
"""

from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple, Union

# Grimoire per ability icon stem
GRIMOIRES = {
    "ability_grimoire_1handed": "Shield Throw",
    "ability_grimoire_2handed": "Smash",
    "ability_grimoire_assault": "Trample",
    "ability_grimoire_bow": "Vault",
    "ability_grimoire_dualwield": "Traveling Knife",
    "ability_grimoire_fightersguild": "Torchbearer",
    "ability_grimoire_magesguild": "Ulfsild's Contingency",
    "ability_grimoire_soulmagic1": "Wield Soul",
    "ability_grimoire_soulmagic2": "Soul Burst",
    "ability_grimoire_staffdestro": "Elemental Explosion",
    "ability_grimoire_staffresto": "Mender's Bond",
    "ability_grimoire_support": "Banner Bearer",
}
GRIMOIRE_ICON_PREFIX = "ability_grimoire_"

# A skill's ABILITY_INFO is at most 1 ms older than the PLAYER_INFO it
# belongs to; anything further apart was written for another reason
PENDING_WINDOW_MS = 100


class ScribedSkill(NamedTuple):
    """A grimoire skill as one ABILITY_INFO line describes it. The scripts
    are empty when the game wrote the line without them."""
    name: str
    icon: str  # icon stem, e.g. "ability_grimoire_support"
    focus: str = ""
    signature: str = ""
    affix: str = ""

    @property
    def grimoire(self) -> str:
        """Grimoire name, '' for an icon this table does not know."""
        return GRIMOIRES.get(self.icon, "")

    @property
    def scripts_known(self) -> bool:
        return bool(self.focus or self.signature or self.affix)


# What a player's slot resolves to: the line written for them, or the lines
# it can be when none was
Resolution = Union[ScribedSkill, Tuple[ScribedSkill, ...]]


def scribed_label(name: str, scripts) -> str:
    """'Shocking Banner (Class Flourish / Heroism)': the skill with its
    signature and affix scripts; the focus script is already in the name."""
    extras = [str(s) for s in list(scripts or [])[1:3] if s]
    return f"{name} ({' / '.join(extras)})" if extras else str(name)


def slot_label(slot: dict) -> str:
    """A bar slot's name for text output, with the scripts of a scribed skill."""
    return scribed_label(str(slot.get("name", "")), slot.get("scripts"))


def slot_fields(resolution: Resolution) -> Dict[str, object]:
    """Bar-slot fields for a scribed skill, merged over the slot's id, name
    and icon. Always 'scribed': True, 'icon' and 'grimoire', then:

    - scripts known: 'name' and 'scripts' ([focus, signature, affix]);
    - written without scripts: 'name' only;
    - one of several lines: 'script_options', [[name, focus, signature,
      affix], ...] with empty scripts for a line written without them. The
      name is the options' shared name when they agree, else the grimoire's.
    """
    if isinstance(resolution, ScribedSkill):
        fields = {"scribed": True, "name": resolution.name, "icon": resolution.icon,
                  "grimoire": resolution.grimoire}
        if resolution.scripts_known:
            fields["scripts"] = [resolution.focus, resolution.signature, resolution.affix]
        return fields
    first = resolution[0]
    names = {option.name for option in resolution}
    fields = {"scribed": True, "icon": first.icon, "grimoire": first.grimoire,
              "script_options": [[o.name, o.focus, o.signature, o.affix]
                                 for o in resolution]}
    if len(names) == 1:
        fields["name"] = first.name
    elif first.grimoire:
        fields["name"] = first.grimoire
    return fields


class ScribingTracker:
    """Ties the scribed-skill lines of one log session to its players."""

    def __init__(self):
        # ability id -> script combinations written this session, in log order
        self._known: Dict[str, List[ScribedSkill]] = {}
        # ability id -> the line written without scripts this session
        self._plain: Dict[str, ScribedSkill] = {}
        # ability id -> (line, log ms) written since the last PLAYER_INFO
        self._pending: Dict[str, Tuple[ScribedSkill, Optional[int]]] = {}
        # (player key, ability id) -> what that player's slot resolved to
        self._bound: Dict[Tuple[str, str], Resolution] = {}

    def reset(self) -> None:
        """New BEGIN_LOG session: the game writes every line again."""
        self._known.clear()
        self._plain.clear()
        self._pending.clear()
        self._bound.clear()

    def forget_player(self, player_key: str) -> None:
        """Drop what is known about one player's skills (the key now stands
        for another character)."""
        for key in [k for k in self._bound if k[0] == player_key]:
            del self._bound[key]

    def forget_players(self, prefix: str) -> None:
        """Drop the players whose key starts with *prefix* (keys built on
        unit ids stop being valid when the zone changes)."""
        for key in [k for k in self._bound if k[0].startswith(prefix)]:
            del self._bound[key]

    def note_ability(self, ability_id: str, name: str, icon: str, scripts=None,
                     at_ms: Optional[int] = None) -> None:
        """Record an ABILITY_INFO line if it describes a grimoire skill.
        *scripts* is (focus, signature, affix), or empty for a line without
        them; *icon* the icon stem; *at_ms* the line's log timestamp."""
        ability_id, icon = str(ability_id), str(icon or "")
        scripts = [str(s) for s in scripts or []]
        if len(scripts) == 3:
            skill = ScribedSkill(str(name), icon, *scripts)
            known = self._known.setdefault(ability_id, [])
            if skill not in known:
                known.append(skill)
        elif not scripts and icon.startswith(GRIMOIRE_ICON_PREFIX):
            skill = ScribedSkill(str(name), icon)
            self._known.setdefault(ability_id, [])
            self._plain[ability_id] = skill
        else:
            return
        self._pending[ability_id] = (skill, at_ms)

    def resolve(self, player_key: str, ability_ids: Iterable[str],
                at_ms: Optional[int] = None) -> Dict[str, Resolution]:
        """What each grimoire skill on a player's bars is, at their
        PLAYER_INFO line: a ScribedSkill (with scripts, or without when the
        game wrote none), or a tuple of the lines it can be. Ids that are
        not grimoire skills are left out."""
        resolved: Dict[str, Resolution] = {}
        for ability_id in dict.fromkeys(str(a) for a in ability_ids):
            if ability_id not in self._known:
                continue
            key = (player_key, ability_id)
            bound = self._bound.get(key)
            has_scripts = isinstance(bound, ScribedSkill) and bound.scripts_known
            fresh = self._fresh(ability_id, at_ms)
            if fresh is not None and (fresh.scripts_known or not has_scripts):
                # Written for this player. A line without scripts does not
                # replace scripts the log gave for them earlier
                self._bound[key] = fresh
            elif bound is None:
                # Nothing written for this player: theirs is a line an
                # earlier player already caused
                lines = list(self._known[ability_id])
                if ability_id in self._plain:
                    lines.append(self._plain[ability_id])
                self._bound[key] = lines[0] if len(lines) == 1 else tuple(lines)
            resolved[ability_id] = self._bound[key]
        # A line is written for the PLAYER_INFO that follows it
        self._pending.clear()
        return resolved

    def _fresh(self, ability_id: str, at_ms: Optional[int]) -> Optional[ScribedSkill]:
        pending = self._pending.get(ability_id)
        if pending is None:
            return None
        skill, written_ms = pending
        if (at_ms is not None and written_ms is not None
                and abs(at_ms - written_ms) > PENDING_WINDOW_MS):
            return None
        return skill
