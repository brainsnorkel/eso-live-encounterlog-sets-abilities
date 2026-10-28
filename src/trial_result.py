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
- The maximum is 36 in the 12-player trials, all of which were veteran
  runs; an arena's is not (a Dragonstar Arena run with 7 deaths kept 14),
  and a normal trial's was never seen. So the maximum is shown only for a
  veteran run of a trial in TRIALS, and an arena's or an unknown run's
  vitality as the points alone.
- success is T in every END_TRIAL: a run that fails or is abandoned writes
  none, so there is never a failed result to show.
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
_handle_end_trial), which frontends then redraw.
"""


# The trial ids the log writes, by the zone each END_TRIAL was written in
# (the 146 runs above). Ids never seen are left out rather than guessed
TRIAL_NAMES = {
    1: "Hel Ra Citadel",
    2: "Aetherian Archive",
    4: "Dragonstar Arena",
    5: "Maw of Lorkhaj",
    7: "Halls of Fabrication",
    8: "Asylum Sanctorium",
    9: "Cloudrest",
    11: "Blackrose Prison",
    12: "Sunspire",
    13: "Kyne's Aegis",
    15: "Rockgrove",
    16: "Dreadsail Reef",
    17: "Sanity's Edge",
    18: "Lucent Citadel",
    19: "Ossein Cage",
}

# The 12-player trials among them: 36 vitality on veteran. The two arenas
# (4, 11) are left out, their maximum being unknown
TRIALS = frozenset({1, 2, 5, 7, 8, 9, 12, 13, 15, 16, 17, 18, 19})
TRIAL_VITALITY = 36

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
        'vitality_max': TRIAL_VITALITY if is_vet and trial_id in TRIALS else None,
    }


def duration_text(duration_ms: int) -> str:
    """The game's trial timer: '22:31', '1:02:34' (seconds cut, not rounded)."""
    seconds = max(0, int(duration_ms)) // 1000
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def result_text(result: dict) -> str:
    """'✓ Sunspire vet · Vitality 35/36 · 253,117 · 22:31'; an arena's
    vitality without a maximum: 'Vitality 14'."""
    vet = " vet" if result.get('is_vet') else ""
    vitality = str(result.get('vitality', 0))
    if result.get('vitality_max'):
        vitality = f"{vitality}/{result['vitality_max']}"
    return (f"✓ {result.get('name', '')}{vet} · Vitality {vitality}"
            f" · {int(result.get('score', 0)):,} · {duration_text(result.get('duration_ms', 0))}")
