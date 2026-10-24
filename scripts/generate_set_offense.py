#!/usr/bin/env python3
"""
Generate data/sets/offense.json: what each gear set does for penetration and
critical damage, by the set id the encounter log writes, for the build
window's Penetration and Critical damage sections (pen_crit.py, issue #37).

The log gives an equipped item's set id and nothing about the set's bonuses.
UESP's set summary lists every set with its bonus texts, one request (714
sets, 0.8 MB); the texts are the game's own. This script keeps, per set and
per piece count, the lines that matter here:

- a flat Offensive Penetration line ("(2 items) Adds 34-1487 Offensive
  Penetration": the second figure is the value at CP 160), kept as 'pen';
- a flat Critical Damage line ("(5 items) Increases your Critical Damage and
  Critical Healing by 8%"), kept as 'crit' (Malacath's "decreases ... by 50%"
  as -50); a sentence after it that doubles or adds to the bonus under a
  condition is kept as 'note';
- a buff the wearer always has ("Gain Minor Force at all times", Oakensoul's
  list), kept under 'gives': the game writes no GAINED line and no PLAYER_INFO
  entry for such a buff (four trial logs: Velothi's aura 193447 is listed on
  917 rows, Minor Force 61746 on none), so the wearer is credited with it for
  the whole fight; a buff the wearer gets under a condition ("After dealing
  direct damage, you gain Minor Force", Tzogvin's at ten stacks) is kept
  under 'gives_when' with the text as 'when', named but measured from the
  log like any other buff;
- a conditional bonus to the wearer ("When you deal damage to an enemy who is
  Off Balance, your Offensive Penetration is increased by 123-5312 for 10
  seconds"), kept as 'pen_up_to' or 'crit_up_to' with the text as 'when',
  shown but never added to a total;
- a debuff or group buff the set puts on others (Roar of Alkosh, Crimson
  Oath's Rive and Tremorscale reducing Armor or Resistance, Night Mother's
  Gaze's Major Breach, Nunatak's Major Brittle, Elemental Catalyst's
  weaknesses, Lucent Echoes, Saxhleel Champion's Major Force), kept under
  'provides' so a group row can name the wearer's set as its source.

Of the 714 sets on the Update 51 export, 65 carry a flat 1487 line, seven
arena weapons 1190, Spriggan's Thorns and Spinner's Garments 3460; 72 sets
mention Offensive Penetration and 52 Critical Damage in some form. The
texts are classified by sentence: a first sentence that is nothing but
"Adds N Offensive Penetration" or "Increases your Critical Damage ... by N%"
is flat; a sentence that opens with a condition (When, While, After,
Whenever, Dealing, Touching, On, If, Each, Every) is conditional. A set the
export does not describe, or a bonus worded in a way this script does not
read, is simply absent: the section then shows nothing for it.

Run after an ESO update that adds or changes sets (one request to UESP; UESP
asks heavy users to go lightly, so do not loop it):
    python scripts/generate_set_offense.py
or from a reply already on disk, such as the one the esobuild export keeps:
    python scripts/generate_set_offense.py --from build/esobuild-assets/sources/set_summary.json
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "sets" / "offense.json"
EXPORT_URL = "https://esolog.uesp.net/exportJson.php?table=setSummary"
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
ATTRIBUTION = "Set data from UESP (esolog.uesp.net), CC-BY-SA 2.5"
MIN_SETS = 500  # the game has 700-odd; fewer means a bad response

_BONUS_RE = re.compile(r"^\((\d+) (?:perfected )?items?\)\s*(.*)$", re.DOTALL)
# "Adds 34-1487 Offensive Penetration", "Gain 100000 Offensive Penetration",
# "Adds 2-110 Weapon and Spell Damage and 28-1240 Offensive Penetration"
_FLAT_PEN_RE = re.compile(r"^(?:Adds|Gain)\b[^.]*?(?:\d+-)?(\d+) Offensive Penetration\.?$", re.IGNORECASE)
# "Increases your Critical Damage and Critical Healing by 8%",
# "Adds 16-708 Critical Chance and increases your Critical Damage by 0-4%"
_FLAT_CRIT_RE = re.compile(
    r"^(?:Increases|Adds)\b[^.]*?increases your Critical Damage(?: and (?:Critical )?Healing)?"
    r"(?: done)? by (?:\d+-)?(\d+)%", re.IGNORECASE)
_FLAT_CRIT_HEAD_RE = re.compile(
    r"^Increases your Critical Damage(?: and (?:Critical )?Healing)?(?: done)? by (?:\d+-)?(\d+)%", re.IGNORECASE)
_MINUS_CRIT_RE = re.compile(r"decreases your Critical Damage(?: done)? by (\d+)%", re.IGNORECASE)
_COND_PEN_RE = re.compile(r"(?:\d+-)?(\d+) Offensive Penetration|Offensive Penetration(?: is increased)? by (?:\d+-)?(\d+)", re.IGNORECASE)
_COND_CRIT_RE = re.compile(r"Critical Damage(?: and Critical Healing)?(?: done)? by (?:\d+-)?(\d+)%", re.IGNORECASE)
_CONDITION_START = re.compile(
    r"^(When|While|After|Whenever|Dealing|Touching|On |If |Each|Every|Casting|Blocking|Taking|Healing|Consuming|Upon)\b")
NAMED_BUFFS = ("Major Breach", "Minor Breach", "Major Brittle", "Minor Brittle",
               "Major Force", "Minor Force")
_OTHERS = re.compile(r"\b(group members?|allies|ally|target gains|enemies|enemy|their)\b", re.IGNORECASE)
_REDUCES_ARMOR = re.compile(
    r"reduc\w*\b[^.]*?\b(Armor|Physical and Spell Resistance|Resistance)\b"
    r"|\b(Armor|Resistance)\b[^.]*?\breduc", re.IGNORECASE)
_GAIN_SELF_FORCE = re.compile(r"\b(?:gains?|grants? you)\b[^.]*?\b(Major|Minor) Force\b", re.IGNORECASE)
_UP_TO_RE = re.compile(r"\bup to (\d+)\b", re.IGNORECASE)
_NOT_A_PROVIDER = re.compile(r"^Increases your damage done\b", re.IGNORECASE)


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read().decode("utf-8", errors="replace")


def _sentences(text: str):
    text = " ".join(text.replace("\n", " ").split())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def classify_bonus(pieces: int, text: str, set_name: str) -> dict:
    """The bonus record for one "(N items) ..." line, or {} when the line
    says nothing about penetration, critical damage or the buffs here."""
    sentences = _sentences(text)
    if not sentences:
        return {}
    first = sentences[0]
    record = {"pieces": pieces}
    rest = sentences[1:]

    flat_pen = _FLAT_PEN_RE.match(first) if not _CONDITION_START.match(first) else None
    if flat_pen:
        record["pen"] = int(flat_pen.group(1))
    flat_crit = None
    if not _CONDITION_START.match(first):
        flat_crit = _FLAT_CRIT_HEAD_RE.match(first) or _FLAT_CRIT_RE.match(first)
    if flat_crit:
        record["crit"] = int(flat_crit.group(1))
    minus = _MINUS_CRIT_RE.search(first)
    if minus and "crit" not in record:
        record["crit"] = -int(minus.group(1))
    if ("pen" in record or "crit" in record) and rest:
        note = " ".join(rest)
        if re.search(r"\b(doubles|additional|quadruples|increased|stack)", note, re.IGNORECASE):
            record["note"] = note

    # What the set does to others: a named buff or debuff, or an armor
    # reduction named after the set (Alkosh, Crimson Oath, Tremorscale)
    provides = []
    gives = []
    gives_when = []
    for sentence in sentences:
        if _NOT_A_PROVIDER.match(sentence):
            continue
        named_here = False
        for buff in NAMED_BUFFS:
            if buff not in sentence:
                continue
            named_here = True
            is_force = buff.endswith("Force")
            to_others = bool(_OTHERS.search(sentence))
            if is_force and not to_others and _GAIN_SELF_FORCE.search(sentence):
                # "at all times" (Medusa, Velothi) and Oakensoul's "While
                # equipped" are permanent; the rest need a condition met
                always = "at all times" in sentence or sentence.startswith("While equipped")
                bucket = gives if always else gives_when
                if buff not in bucket:
                    bucket.append(buff)
                if not always and "when" not in record:
                    record["when"] = sentence
            elif is_force and to_others:
                if buff not in provides:
                    provides.append(buff)
            elif not is_force and buff not in provides:
                # Breach and Brittle only ever go on enemies
                provides.append(buff)
        if "Weakness" in sentence and "Critical Damage taken" in sentence and "Elemental Weakness" not in provides:
            provides.append("Elemental Weakness")
        if ("group members" in sentence and "Critical Damage" in sentence and "increases by" in sentence
                and set_name.replace("Perfected ", "") not in provides):
            provides.append(set_name.replace("Perfected ", ""))
        if (not named_here and _REDUCES_ARMOR.search(sentence) and _OTHERS.search(sentence)
                and "pen" not in record):
            # An armor or resistance reduction of the set's own: named after it
            name = set_name.replace("Perfected ", "")
            if name not in provides:
                provides.append(name)
    if gives:
        record["gives"] = gives
    if gives_when:
        record["gives_when"] = gives_when
    if provides:
        record["provides"] = provides

    # A conditional bonus to the wearer
    if "pen" not in record and not provides:
        for sentence in sentences:
            m = _COND_PEN_RE.search(sentence)
            if m and "Penetration" in sentence and not _REDUCES_ARMOR.search(sentence):
                value = next((g for g in m.groups() if g), None)
                if value:
                    record["pen_up_to"] = int(value)
                    record["when"] = sentence
                break
    if "crit" not in record and not provides and not gives and not gives_when:
        for sentence in sentences:
            m = _COND_CRIT_RE.search(sentence)
            if m and "taken" not in sentence and "Enervation" not in sentence:
                cap = _UP_TO_RE.search(sentence[m.end():])
                record["crit_up_to"] = int(cap.group(1)) if cap else int(m.group(1))
                record["when"] = sentence
                break
    return record if len(record) > 1 else {}


def set_offense(payload: dict) -> dict:
    """set id -> {'name', 'bonuses': [...]} for every set with a bonus here."""
    rows = payload.get("setSummary") if isinstance(payload, dict) else None
    out = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        set_id = str(row.get("gameId", "")).strip()
        name = str(row.get("setName", "")).strip()
        if not set_id.isdigit() or not name:
            continue
        bonuses = []
        for index in range(1, 13):
            text = row.get(f"setBonusDesc{index}") or ""
            m = _BONUS_RE.match(text.strip())
            if not m:
                continue
            record = classify_bonus(int(m.group(1)), m.group(2), name)
            if record:
                bonuses.append(record)
        if bonuses:
            out[set_id] = {"name": name, "bonuses": bonuses}
    return out


def render(sets: dict, generated: str, source: str) -> str:
    lines = ["{",
             f' "generated": {json.dumps(generated)},',
             f' "source": {json.dumps(source)},',
             f' "attribution": {json.dumps(ATTRIBUTION)},',
             f' "count": {len(sets)},',
             ' "sets": {']
    items = sorted(sets.items(), key=lambda kv: int(kv[0]))
    for n, (set_id, data) in enumerate(items):
        comma = "," if n < len(items) - 1 else ""
        lines.append(f'  {json.dumps(set_id)}: {json.dumps(data, ensure_ascii=False)}{comma}')
    lines.append(" }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--from", dest="from_file", type=Path,
                        help="a saved setSummary reply instead of fetching one")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args(argv)
    if args.from_file:
        text = args.from_file.read_text(encoding="utf-8")
        source = EXPORT_URL + f" (from {args.from_file.name})"
    else:
        text = fetch(EXPORT_URL)
        source = EXPORT_URL
    payload = json.loads(text)
    rows = payload.get("setSummary") if isinstance(payload, dict) else None
    if not rows or len(rows) < MIN_SETS:
        print(f"Only {len(rows or [])} sets in the reply; not writing", file=sys.stderr)
        return 1
    sets = set_offense(payload)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(sets, datetime.now(timezone.utc).isoformat(timespec="seconds"), source),
                        encoding="utf-8")
    kinds = {"pen": 0, "crit": 0, "gives": 0, "provides": 0, "pen_up_to": 0, "crit_up_to": 0}
    for data in sets.values():
        for bonus in data["bonuses"]:
            for key in kinds:
                if key in bonus:
                    kinds[key] += 1
    print(f"Wrote {args.out}: {len(sets)} sets; bonus lines by kind: {kinds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
