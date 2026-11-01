"""
A trial's result as the game writes it: vitality left, score and time.

Design: when a trial (or an arena) is completed the log writes one line,

    END_TRIAL,id,durationMS,success,finalScore,finalVitalityBonus

e.g. ``1415661,END_TRIAL,12,1351407,T,253117,35000``: Sunspire (id 12) in
22:31, score 253,117, 35 of 36 vitality left. What the line tells, measured
on every completed run in a year of split logs (146 runs, 2026-01 to -10):

- Vitality left is finalVitalityBonus / 1000. The bonus is always a
  multiple of 1,000, at most 36,000 (a deathless Maw of Lorkhaj) and at
  least 0 (87 runs with 36 deaths or more). The 35/36 Sunspire run of
  2026-10-21 wrote 35000 with one player death in the log.
- Only veteran runs write it, trials and arenas alike: all 267 BEGIN_TRIAL
  and 245 END_TRIAL lines in the raw logs and splits (2026-11-01) are in a
  VETERAN zone, normal Blackrose Prison splits carry no TRIAL_* line, and
  UESP's Leaderboards page says scores are set in veteran mode only.
- The maximum (VITALITY_MAX) is the game's starting pool, which UESP gives
  as "typically 15, 24 or 36", and the runs fit 15 for a solo arena, 24
  for a four-player one and 36 for a trial. Measured (issue #183):
  Maelstrom Arena 15 (11 left after the 4 deaths of a solo run, which logs
  every death), Vateshran Hollows 15 (14 left, 1 death), Dragonstar Arena
  24 (a published run's banner reads 24/24; ours kept 14 with 7 of its
  deaths logged). Blackrose Prison's 24 is from a veteran banner Chris
  saw with the Unchained achievement, 24/24: every logged run used it
  all. Sanctum Ophidia's 36 is the trial rule alone, no run being logged.
  A run of an id not in the table shows the points alone.
- success is T in every END_TRIAL: a run that fails or is abandoned writes
  none, so there is never a failed result to show. An earlier veteran
  Vateshran attempt (December 2025) has BEGIN_TRIAL and no END_TRIAL.
- Vitality is the log's figure, never 36 less the deaths the engine counts.
  In 38 runs the log holds fewer player deaths than the game charged (3
  logged against 13 in an Aetherian Archive run, 8 against 23 in Hel Ra):
  the log carries the events around the player writing it, so after a wipe
  in which that player released, the others' deaths are not all there.
  Eight runs also began in an earlier split than the one with END_TRIAL.
- The name is the zone's at the time (ZONE_CHANGED), the id's from
  TRIAL_NAMES only when there is none. A split's file name can be another
  trial's: one named for Dreadsail Reef ends Kyne's Aegis (id 13).

The line comes inside the final fight in 144 of the 146 runs (33 ms after
the last hit of a Sunspire run) and so belongs to that fight. In the other
two, both Blackrose Prison, it comes about 4 seconds after END_COMBAT, and
the engine gives it to the fight it has just sent (ESOLogAnalyzer.
_handle_end_trial), which frontends then redraw. Maelstrom Arena's comes
2.9 s after END_COMBAT and takes the same path; Vateshran Hollows' and
Dragonstar Arena's come inside the final fight.

The timer is the game's, rounded to the nearest second, half up, as the
banner shows it (ZO_FormatTimeMilliseconds): 1,351,407 ms is 22:31 and
2,649,500 ms is 44:10.
"""


# The raid ids, named as the client's en.lang table 111863941 names them
# (every id from 1 to 19 but 10, which has no name there)
TRIAL_NAMES = {
    1: "Hel Ra Citadel",
    2: "Aetherian Archive",
    3: "Sanctum Ophidia",
    4: "Dragonstar Arena",
    5: "Maw of Lorkhaj",
    6: "Maelstrom Arena",
    7: "Halls of Fabrication",
    8: "Asylum Sanctorium",
    9: "Cloudrest",
    11: "Blackrose Prison",
    12: "Sunspire",
    13: "Kyne's Aegis",
    14: "Vateshran Hollows",
    15: "Rockgrove",
    16: "Dreadsail Reef",
    17: "Sanity's Edge",
    18: "Lucent Citadel",
    19: "Ossein Cage",
}

# A veteran run's starting vitality, by raid id: 36 in the twelve-player
# trials, 24 in the four-player arenas, 15 in the solo ones (see above)
_TRIAL_VITALITY = 36
VITALITY_MAX = {
    **{trial_id: _TRIAL_VITALITY for trial_id in (1, 2, 3, 5, 7, 8, 9, 12, 13, 15, 16, 17, 18, 19)},
    4: 24,   # Dragonstar Arena
    6: 15,   # Maelstrom Arena
    11: 24,  # Blackrose Prison
    14: 15,  # Vateshran Hollows
}

# The game's bonus points per point of vitality left
POINTS_PER_VITALITY = 1000


def trial_name(trial_id: int) -> str:
    return TRIAL_NAMES.get(trial_id, f"Trial {trial_id}")


def from_end_trial(fields, zone_name: str | None, difficulty: str | None) -> dict | None:
    """The result an END_TRIAL line's *fields* (id, durationMS, success,
    finalScore, finalVitalityBonus) record, in the zone *zone_name* at
    *difficulty* (ZONE_CHANGED's: VETERAN, NORMAL or NONE); None for a run
    that did not succeed or a line too short to read. success is the log's
    'T', or 'True' as the engine's parser hands it on (eso_log_parser).

    The dict: trial_id, name, is_vet, duration_ms, score, vitality and
    vitality_max (None when the maximum is unknown)."""
    if len(fields) < 5 or fields[2] not in ('T', 'True'):
        return None
    try:
        trial_id = int(fields[0])
        duration_ms = int(fields[1])
        score = int(fields[3])
        bonus = int(fields[4])
    except ValueError:
        return None
    is_vet = str(difficulty or "").upper() == "VETERAN"
    return {
        'trial_id': trial_id,
        'name': zone_name or trial_name(trial_id),
        'is_vet': is_vet,
        'duration_ms': duration_ms,
        'score': score,
        'vitality': bonus // POINTS_PER_VITALITY,
        'vitality_max': VITALITY_MAX.get(trial_id) if is_vet else None,
    }


def duration_text(duration_ms: int) -> str:
    """The game's trial timer: '22:31', '1:02:34', rounded to the nearest
    second as the banner shows it (2,649,500 ms is '44:10')."""
    seconds = (max(0, int(duration_ms)) + 500) // 1000
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def result_text(result: dict) -> str:
    """'✓ Sunspire vet · Vitality 35/36 · 253,117 · 22:31'; a run with no
    known maximum shows the points alone: 'Vitality 14'."""
    vet = " vet" if result.get('is_vet') else ""
    vitality = str(result.get('vitality', 0))
    if result.get('vitality_max'):
        vitality = f"{vitality}/{result['vitality_max']}"
    return (f"✓ {result.get('name', '')}{vet} · Vitality {vitality}"
            f" · {int(result.get('score', 0)):,} · {duration_text(result.get('duration_ms', 0))}")
