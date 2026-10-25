"""
Werewolf form: the bar the log never writes, and the ultimate it renames
(engine side, no Qt). Issue #17.

Design: since Update 50 a werewolf's skills sit on a bar of their own, which
the game switches to on transforming. PLAYER_INFO writes only the two human
bars, so a player who spends a fight in form shows bars they never used. Of
1,068 PLAYER_INFO rows written while a player was in form (55 split logs of
July to October 2026, client versions 12.0 and 12.1, about 25 characters),
1,053 carry the human bars. The other 15, from two anonymous players on
12.0, carry the werewolf bar in place of the front bar, in the slots' real
order and agreeing with their casts. A Rockgrove log of 2026-10-24 (client
12.1, issue #49) showed a third shape: all 11 rows of one player list a
single bar as both the front and the back bar, three werewolf skills beside
Razor Caltrops and Inner Fire, while the player, in form the whole log,
cast Hircine's Rage and Ferocious Roar in every fight and never those two.
The form is one bar of five skills with no swap, so that bar was stale. A
logged bar holding three or more werewolf skills (``is_werewolf_bar``) is
therefore no human bar and no trusted werewolf bar: the engine drops it
before anything reads it, and the werewolf bar is rebuilt from casts for
every werewolf alike. A human bar can hold one werewolf skill for its
while-slotted bonus (Hircine's Fortitude on one player's front bar, 18
rows), which the threshold spares. Werewolf players spent 1,234 of their
1,524 fights of 5 s or more wholly in form, 110 partly, and 180 not at all.

The bar is rebuilt from casts. Each werewolf skill is cast under the id of
the skill its slot holds, one id for all four ranks, with one exception:
within close range a Pounce morph becomes its Carnage version, cast from
the same slot, so SLOT_SKILLS maps Carnage, Brutal Carnage and Feral
Carnage to their Pounce. Feeding Frenzy is not a slot: it is Roar's
synergy, which every group member activates. The light and heavy werewolf
attacks and Devour are not slots either, though they prove the form. Of 58
player sessions with werewolf casts, 55 cast exactly five distinct bar
skills, three cast fewer, and none ever cast a sixth or two morphs of one
skill, so the casts of a whole session can be pooled. A fight's own casts
show the whole bar in only 58% of fights; the session's casts up to the
fight's end show it in 94%, which is the rule here. In the two 12.0 cases
where the game logged the werewolf bar, the rebuilt bar agreed with it; in
the 12.1 case the casts were right and the log was not. Casts
say nothing of the slots' order, so the bar follows the skill line's order
(LINE_POSITION): Pounce, Hircine's Bounty, Roar, Gnash, Rending Claws. A
skill slotted but never cast stays unknown.

The form itself is a hidden effect, 39038 "Werewolf Transformation", plus
the morph's own effect (47083 Werewolf Berserker, 47069 Pack Leader, 47028
for the unmorphed transformation in older logs). On client 12.1, 39038 is
on for 99.9% of in-form casts and for none of the casts of human-bar
skills. A log that starts mid-form has no GAINED: the werewolf casts are
the only sign, and the form is taken to have begun with the session. Death
does not end the form: after 241 of 251 deaths in form the player's next
skill was a werewolf skill, with no new transformation logged.

The ultimate: the unit state's werewolf field is Fury, from 0 to 1000. At
full Fury the transformation ultimate becomes Rampage, or Enduring Rampage
for Pack Leader, and PLAYER_INFO then lists that in the slot, but only for
the player who writes the log. For that player, 170 of 171 fight starts in
form with full Fury listed Rampage, and 1 of 181 other starts did. For
group members, 0 of 424 such starts did. So Rampage in a bar is the morph
caught at full Fury, and the bar shows the morph instead (``stand_in_for``):
the player's active morph effect names it, else the morph slotted in their
earlier rows, else STAND_INS. The client names more Rampage ids than the
two seen in a slot; the unseen ones are left unmapped.

Icons: five of the werewolf skills (Pounce, Brutal Pounce, Feral Pounce,
Rending Claws, Claw Fury) carry Update 50 icons named u50_ability_*, and
Rampage an achievement icon, all outside the ability_* family the app used
to bundle (see scripts/extract_ability_icons.py).
"""

from dataclasses import dataclass, field

# The transformation ultimates as a human bar lists them
TRANSFORMATIONS = ("32455", "39075", "39076")  # Werewolf Transformation, Pack Leader, Werewolf Berserker

# Effects that mark the form: the hidden form effect, then each morph's own
FORM_EFFECT = "39038"
MORPH_EFFECTS = {"47028": "32455", "47069": "39075", "47083": "39076"}
FORM_EFFECTS = frozenset({FORM_EFFECT, *MORPH_EFFECTS})

# Casts that name the morph: the ultimate itself and its transformation cast
TRANSFORM_CASTS = {**{ability_id: ability_id for ability_id in TRANSFORMATIONS}, **MORPH_EFFECTS}

# The werewolf bar's skills by cast id -> the skill the slot holds
SLOT_SKILLS: dict[str, str] = {
    "32632": "32632", "137156": "32632",   # Pounce, and Carnage at close range
    "39105": "39105", "137184": "39105",   # Brutal Pounce, Brutal Carnage
    "39104": "39104", "137164": "39104",   # Feral Pounce, Feral Carnage
    "58310": "58310",                      # Hircine's Bounty
    "58317": "58317",                      # Hircine's Rage
    "58325": "58325",                      # Hircine's Fortitude
    "32633": "32633",                      # Roar
    "39113": "39113",                      # Ferocious Roar
    "39114": "39114",                      # Deafening Roar
    "58405": "58405",                      # Gnash
    "58742": "58742",                      # Rip and Tear
    "58798": "58798",                      # Bloody Gnash
    "58855": "58855",                      # Rending Claws
    "58864": "58864",                      # Claw Fury
    "58879": "58879",                      # Bloodclaws
}

# Each slot skill's place in the Werewolf skill line (UESP skillIndex; the
# transformation ultimate is 1)
LINE_POSITION: dict[str, int] = {
    "32632": 2, "39105": 2, "39104": 2,
    "58310": 3, "58317": 3, "58325": 3,
    "32633": 4, "39113": 4, "39114": 4,
    "58405": 5, "58742": 5, "58798": 5,
    "58855": 6, "58864": 6, "58879": 6,
}

# A Rampage in a bar -> the morph it stands in for, None when not known.
# 267416 was seen for Werewolf Berserker; Enduring Rampage is Pack Leader's
STAND_INS: dict[str, str | None] = {
    "267416": "39076", "267417": None, "267418": None,                         # Rampage
    "267425": "39075", "267426": "39075", "267427": "39075", "267428": "39075",  # Enduring Rampage
}

# Casts only made in form that hold no slot: the werewolf light and heavy
# attacks, and Devour
FORM_ONLY_CASTS = frozenset({"32464", "32477", "32480", "33208"})

# Every cast and effect id the tracker reads, for a cheap test before a call
CAST_IDS = frozenset({*SLOT_SKILLS, *TRANSFORM_CASTS, *STAND_INS, *FORM_ONLY_CASTS})
EFFECT_IDS = FORM_EFFECTS

# Names and icon stems on the Update 51 client, for an id the log has no
# ABILITY_INFO line for (a player who only ever cast Feral Carnage logs no
# line for the Feral Pounce slot)
SKILLS: dict[str, tuple] = {
    "32455": ("Werewolf Transformation", "ability_werewolf_001"),
    "39075": ("Pack Leader", "ability_werewolf_001_a"),
    "39076": ("Werewolf Berserker", "ability_werewolf_001_b"),
    "32632": ("Pounce", "u50_ability_werewolf_pounce"),
    "39105": ("Brutal Pounce", "u50_ability_werewolf_brutal_pounce"),
    "39104": ("Feral Pounce", "u50_ability_werewolf_feral_pounce"),
    "58310": ("Hircine's Bounty", "ability_werewolf_004_a"),
    "58317": ("Hircine's Rage", "ability_werewolf_004_b"),
    "58325": ("Hircine's Fortitude", "ability_werewolf_004_c"),
    "32633": ("Roar", "ability_werewolf_003"),
    "39113": ("Ferocious Roar", "ability_werewolf_003_b"),
    "39114": ("Deafening Roar", "ability_werewolf_003_a"),
    "58405": ("Gnash", "ability_werewolf_002_rend"),
    "58742": ("Rip and Tear", "ability_werewolf_002_rend_a"),
    "58798": ("Bloody Gnash", "ability_werewolf_002_rend_b"),
    "58855": ("Rending Claws", "u50_ability_werewolf_raking_claws"),
    "58864": ("Claw Fury", "u50_ability_werewolf_claws_of_anguish"),
    "58879": ("Bloodclaws", "ability_werewolf_006_c"),
}

# A logged bar holding this many werewolf skills is the werewolf bar itself,
# stale or not; one or two are human-bar picks for a skill's while-slotted bonus
LOGGED_BAR_SKILLS = 3


def is_werewolf_bar(bar) -> bool:
    """Whether a logged bar (a list of slot dicts or of ids) is the werewolf
    bar, which the game writes in place of a human bar for a few players
    and which the engine drops unread (see the module notes)."""
    ids = [str(slot.get("id", "")) if isinstance(slot, dict) else str(slot)
           for slot in bar or []]
    return sum(1 for ability_id in ids if ability_id in SLOT_SKILLS) >= LOGGED_BAR_SKILLS


@dataclass
class FightBar:
    """A player's werewolf bar for one fight: the slot skills in skill-line
    order, the transformation morph (None when unknown) and the share of
    the fight spent in form."""
    skills: list[str]
    ultimate: str | None
    share: float


@dataclass
class _Form:
    spans: list[list] = field(default_factory=list)  # [start, end or None], oldest first
    active: set[str] = field(default_factory=set)    # form effects on now
    seen_effect: bool = False                        # any form effect this session
    skills: dict[str, int] = field(default_factory=dict)  # slot skill -> first cast
    morph: str | None = None                      # from effects and casts
    slotted_morph: str | None = None              # from the human bars

    def open(self, timestamp: int) -> None:
        if not (self.spans and self.spans[-1][1] is None):
            self.spans.append([timestamp, None])

    def close(self, timestamp: int) -> None:
        if self.spans and self.spans[-1][1] is None:
            self.spans[-1][1] = timestamp


class WerewolfTracker:
    """Each player's werewolf form over a BEGIN_LOG session: when they were
    in form, the werewolf skills they cast, and their morph. A player's key
    is the analyzer's per-session player key: unit ids change with every
    zone, the per-session id does not."""

    def __init__(self):
        self._players: dict[str, _Form] = {}

    def reset(self) -> None:
        """A new BEGIN_LOG session: timestamps restart and players are
        numbered anew."""
        self._players.clear()

    def _player(self, key: str) -> _Form:
        return self._players.setdefault(key, _Form())

    def note_effect(self, key: str, change: str, ability_id: str, timestamp: int) -> None:
        """A form effect GAINED, UPDATED or FADED on the player."""
        if ability_id not in FORM_EFFECTS:
            return
        form = self._player(key)
        form.seen_effect = True
        if change in ("GAINED", "UPDATED"):
            if not form.active:
                form.open(timestamp)
            form.active.add(ability_id)
            if ability_id in MORPH_EFFECTS:
                form.morph = MORPH_EFFECTS[ability_id]
        elif change == "FADED":
            form.active.discard(ability_id)
            if not form.active:
                form.close(timestamp)

    def note_cast(self, key: str, ability_id: str, timestamp: int) -> None:
        """A BEGIN_CAST by the player."""
        if ability_id in TRANSFORM_CASTS:
            self._player(key).morph = TRANSFORM_CASTS[ability_id]
            return
        if ability_id not in SLOT_SKILLS and ability_id not in STAND_INS \
                and ability_id not in FORM_ONLY_CASTS:
            return
        form = self._player(key)
        skill = SLOT_SKILLS.get(ability_id)
        if skill is not None:
            form.skills.setdefault(skill, timestamp)
        if not form.morph and STAND_INS.get(ability_id):
            form.morph = STAND_INS[ability_id]
        if not form.active and not (form.spans and form.spans[-1][1] is None):
            # Only cast in form: the transformation came before the log did,
            # or its effect was missed
            form.open(timestamp if form.seen_effect else 0)

    def note_bars(self, key: str, ability_ids) -> None:
        """The ids of the player's logged bars: a transformation ultimate
        there is their morph."""
        for ability_id in ability_ids:
            if str(ability_id) in TRANSFORMATIONS:
                self._player(key).slotted_morph = str(ability_id)

    def morph_of(self, key: str) -> str | None:
        """The player's transformation ultimate, None when not known."""
        form = self._players.get(key)
        if form is None:
            return None
        return form.morph or form.slotted_morph

    def stand_in_for(self, key: str, ability_id: str) -> str | None:
        """The morph a Rampage in the player's bar stands in for, None when
        *ability_id* is no Rampage or the morph is not known."""
        if ability_id not in STAND_INS:
            return None
        return self.morph_of(key) or STAND_INS[ability_id]

    def fight_bar(self, key: str, start: int, end: int) -> FightBar | None:
        """The player's werewolf bar for the fight from *start* to *end*:
        the skills cast so far this session, None when they were never in
        form during the fight."""
        form = self._players.get(key)
        if form is None or end <= start:
            return None
        inside = 0
        for span_start, span_end in form.spans:
            inside += max(0, min(end if span_end is None else span_end, end) - max(span_start, start))
        if inside <= 0:
            return None
        skills = sorted((skill for skill, first in form.skills.items() if first <= end),
                        key=lambda skill: (LINE_POSITION.get(skill, 99), form.skills[skill]))
        return FightBar(skills=skills, ultimate=self.morph_of(key),
                        share=min(1.0, inside / (end - start)))
