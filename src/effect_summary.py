"""
Who applied an effect and who had it, over a whole fight (issue #19).

A row of the uptime strip is a list of intervals, each naming its caster
('source') and receiver ('target'): the built-in rows from the buff
timeline recorder, the tracked rows from the effect tracker. Hovering the
strip shows the intervals at one instant; summarise() adds them up over
the fight for the pop-up a click on the row opens.

Every figure is a union of intervals as a share of the fight, the rule the
row's own uptime uses (timeline_strip.uptime_pct), so the receivers' lines
and the casters' lines each union back to the headline:

- a caster's *uptime* is the time any of their intervals was up, and their
  *sole* time the part of it no other caster's interval covered; two
  supports keeping Major Courage up between them show the overlap in the
  gap between the two;
- a receiver's *uptime* is the time the effect was on that unit;
- *spans* counts intervals, not casts: the recorders merge a recast that
  follows a fade within moments into the span before it.

An interval without a caster (an old saved fight, or a proc the log writes
without a unit) is counted under UNKNOWN_SOURCE rather than dropped.
"""

from typing import Dict, List, Optional

UNKNOWN_SOURCE = "unknown source"

# What a recorder writes for a caster it could not name
_UNNAMED = {"", "unknown", "0"}


def _union_ms(spans) -> int:
    covered = 0
    cur_start = cur_end = None
    for start, end in sorted(spans):
        if cur_end is None or start > cur_end:
            if cur_end is not None:
                covered += cur_end - cur_start
            cur_start, cur_end = start, end
        else:
            cur_end = max(cur_end, end)
    if cur_end is not None:
        covered += cur_end - cur_start
    return covered


def _sole_ms(own, others) -> int:
    """The part of *own*'s union that *others* does not cover."""
    return _union_ms(own) - _union_ms(
        [(max(s, os), min(e, oe)) for s, e in own for os, oe in others
         if min(e, oe) > max(s, os)])


def _pct(ms: int, duration_ms: int) -> int:
    return min(100, round(100 * ms / duration_ms)) if duration_ms > 0 else 0


def source_of(interval: dict) -> str:
    source = interval.get("source")
    return UNKNOWN_SOURCE if source is None or str(source) in _UNNAMED else str(source)


def summarise(intervals: List[dict], duration_ms: int,
              stacks: bool = False) -> Dict[str, object]:
    """{'uptime_pct', 'sources': [...], 'targets': [...]} for one row.

    sources: {'name', 'uptime_pct', 'sole_pct', 'spans'}, longest first.
    targets: {'name', 'uptime_pct', 'spans'}, longest first, and for a
    stacking rule (*stacks*) 'max_stacks' and 'at_max_pct', the share of
    the fight the unit spent at its own peak."""
    spans = [iv for iv in intervals if iv.get("end_ms", 0) > iv.get("start_ms", 0)]
    by_source: Dict[str, list] = {}
    by_target: Dict[str, list] = {}
    for iv in spans:
        by_source.setdefault(source_of(iv), []).append(iv)
        by_target.setdefault(str(iv.get("target") or "?"), []).append(iv)

    def pairs(ivs):
        return [(iv["start_ms"], iv["end_ms"]) for iv in ivs]

    sources = []
    for name, own in by_source.items():
        others = [pair for other, ivs in by_source.items() if other != name
                  for pair in pairs(ivs)]
        sources.append({"name": name,
                        "uptime_pct": _pct(_union_ms(pairs(own)), duration_ms),
                        "sole_pct": _pct(_sole_ms(pairs(own), others), duration_ms),
                        "spans": len(own)})
    targets = []
    for name, own in by_target.items():
        line = {"name": name,
                "uptime_pct": _pct(_union_ms(pairs(own)), duration_ms),
                "spans": len(own)}
        if stacks:
            peak = max(int(iv.get("stacks") or 1) for iv in own)
            line["max_stacks"] = peak
            line["at_max_pct"] = _pct(_union_ms(pairs(
                [iv for iv in own if int(iv.get("stacks") or 1) == peak])), duration_ms)
        targets.append(line)

    def order(line):
        # Longest first; the unknown caster after the named ones it ties with
        return (-line["uptime_pct"], line["name"] == UNKNOWN_SOURCE, line["name"].lower())

    return {"uptime_pct": _pct(_union_ms(pairs(spans)), duration_ms),
            "sources": sorted(sources, key=order),
            "targets": sorted(targets, key=order)}


def matrix(intervals: List[dict], duration_ms: int) -> Optional[Dict[str, Dict[str, int]]]:
    """caster -> receiver -> uptime % of the effect from that caster on that
    receiver, when there is more than one of each; None otherwise."""
    cells: Dict[str, Dict[str, list]] = {}
    for iv in intervals:
        if iv.get("end_ms", 0) > iv.get("start_ms", 0):
            cells.setdefault(source_of(iv), {}).setdefault(
                str(iv.get("target") or "?"), []).append((iv["start_ms"], iv["end_ms"]))
    receivers = {target for row in cells.values() for target in row}
    if len(cells) < 2 or len(receivers) < 2:
        return None
    return {source: {target: _pct(_union_ms(pairs), duration_ms)
                     for target, pairs in row.items()}
            for source, row in cells.items()}
