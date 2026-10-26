"""
What a boss is: the game's flag, and the units that carry it without being
the fight's boss (issue #67).

The encounter log flags a boss on its UNIT_ADDED line (isBoss, the sixth
field after the unit id), and the engine takes that flag as the word on
what a boss is: EnemyInfo.is_boss feeds the boss damage and boss dps time
(damage_stats), each player's boss share, the ``boss`` scope of the tracked
rules (effect_rules), the targets of the penetration figures and the
Armour row (pen_crit), and the damage window's boss-only switch. The flag
is the game's own boss health bar: it is reliable in dungeons and trials
(Z'Maja and her shade, the Lucent twins, Opulent Ordeal's three, every
dungeon boss), and the only boss definition that needs no list.

It is wrong for a few units. In Lucent Citadel the gauntlet before Xoryn
is one combat with him: the group hits five Defense Prisms (2,910,773
health, 10 to 20 s apiece) and Baron Rize (13,971,720, hit for 21 to 41 s
at about 110 s in) before Xoryn (69,858,576) is added a median 435 s into
a median 549 s fight, and all three carry the flag. Read as bosses, the
boss dps time of a Xoryn pull ran from the first hit on a Prism to the end
(a median 531 s of 561 s over 23 full pulls in 899 split logs) and divided
his damage, the Baron's and the Prisms' together; every player's boss
share counted Prism and Baron damage; a boss-scoped rule was measured on
every Prism (the taunt's ``each`` averaged over seven units); and the
penetration figures weighed the Prisms' seconds. In Kyne's Aegis the Sea
Adders of Yandir the Butcher's fight carry it too (4,657,240 health, 8%
of Yandir's, hit for about 22 s in every one of the 32 Yandir fights
logged), so the taunt was averaged over Yandir and his adders and 10% of
the "boss" damage was adder damage.

A survey over every split log on the maintainer's machine (899 logs,
9,177 fights, 2,943 that hit a flagged unit, 2026-01 to 2026-10;
scripts/survey_boss_flag.py) found no other flagged unit under a tenth of
its fight's largest flagged unit: after the Prisms (4%) and the adders
(8%) the next lowest is 20% (Baron Rize against Xoryn, and one Dreadsail
Reef pull of the Reef Guardians), then Spindleclutch's chain-pulled bosses
at 23% and Cloudrest's Shade of Z'Maja at 40%, all bosses in their own
right. The issue offered a rule instead of a list, a flagged unit under a
tenth of the largest flagged unit of its fight being an add. The survey
shows the threshold would hold, but the rule cannot be applied where the
flag is read: the largest unit, Xoryn, arrives seven minutes after the
Prisms, the tracked rules keep each span's unit kind from the moment the
effect was recorded, and the damage record keeps per-ability rows for the
bosses alone, so the fight would have to be re-kinded at its end. It would
also make the Prisms bosses on the 15 gauntlet wipes at the Baron (21% of
him) and on the wipes at the Prisms alone. A bundled list of monster ids
is read once, on the UNIT_ADDED line, so every consumer agrees.

Baron Rize is on the list, against the issue's first thought (he has a
name, a health bar and a phase of his own). The boss dps time runs from
the first hit on any boss to the last (Combat Metrics' GetBossTargetDamage,
see damage_stats), so with the Baron a boss a Xoryn pull's boss dps time
would still have been a median 446 s of 561 s, the Baron's half minute at
110 s stretching it over the gauntlet, against 129 s with him an add. The
other way out, a union of each boss's own hit window, would have changed
Nahviintaas, who lands as a new unit each time, in 27 of 136 Sunspire
fights, away from Combat Metrics' figure for a fight with one boss. A
wipe in the gauntlet before Xoryn is therefore a fight without a boss,
still named after the Baron when he took the most damage (the name follows
the most damaged hostile, flagged or not); removing his id from the list
reverses the choice.

Combat Metrics counts these units as bosses, since it reads the same boss
health bar, so its boss figures and this app's differ on Xoryn and Yandir
pulls, by design. A new trial can bring a new unit of this kind; the
survey script lists every flagged unit by zone with its health as a share
of the fight's largest, and a line here is all it takes.
"""

# Monster ids (the fifth field after the unit id on UNIT_ADDED) that carry
# the game's boss flag and are not the fight's boss: adds the group hits
# on the way to one, or during the fight
BOSS_FLAG_ADDS = {
    "121566": "Defense Prism",  # Lucent Citadel, Xoryn's gauntlet
    "122810": "Defense Prism",
    "122811": "Defense Prism",
    "122812": "Defense Prism",
    "122557": "Baron Rize",     # Lucent Citadel, the gauntlet's mini-boss
    "96308": "Sea Adder",       # Kyne's Aegis, Yandir the Butcher's adds
}


def is_fight_boss(flagged: bool, monster_id) -> bool:
    """Whether a unit the log added with boss flag *flagged* and monster id
    *monster_id* is a boss of the fight: flagged, and not one of the
    BOSS_FLAG_ADDS."""
    return bool(flagged) and str(monster_id or "") not in BOSS_FLAG_ADDS
