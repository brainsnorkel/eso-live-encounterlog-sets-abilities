#!/usr/bin/env python3
"""
Generate the ESO-Hub link maps the app bundles under data/esohub/:

  skills_en.json  slug -> skill page path, from sitemap_en_Skill.xml, e.g.
                  "pragmatic-fatecarver": "/en/skills/arcanist/herald-of-the-tome/pragmatic-fatecarver"
  sets_en.json    LibSets set name -> set page path, from sitemap_en_ArmorSet.xml
                  matched against the names in src/gear_set_data.py, e.g.
                  "Deadly Strike": "/en/sets/deadly-strike"
  scribing_en.json  two maps for scribed skills: "skills", slug -> page of a
                  grimoire with a focus script, from
                  sitemap_en_ScribingCombination.xml, e.g.
                  "shocking-banner": "/en/scribing/combination/93/shocking-banner"
                  and "scripts", slug -> script page, from sitemap_en_Script.xml,
                  e.g. "lingering-torment": "/en/scribing/scripts/lingering-torment"

The app slugifies a logged ability or script name (ability_icons.slugify) to
look up a skill, a scribed skill or a script, and uses the LibSets name as-is
to look up a set. Unknown names get no link. Set names are matched by
ESO-Hub's slug rules plus the spelling differences listed in SET_SLUG_ALIASES
(see docs/research/esohub-icons-and-tooltips.md); unmatched names are
reported. Scripts the game has renamed since ESO-Hub named their pages are
listed in SCRIPT_SLUG_ALIASES.

Run after ESO updates that add or rename skills, sets or scripts, and after
refreshing the LibSets data (needs network access):
    python scripts/generate_esohub_links.py
Name the maps to regenerate only some of them:
    python scripts/generate_esohub_links.py scribing
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
from ability_icons import slugify  # noqa: E402
from gear_set_data import SET_ID_TO_NAME  # noqa: E402

DATA_DIR = REPO_ROOT / "data" / "esohub"
SKILL_SITEMAP = "https://eso-hub.com/sitemaps/en/sitemap_en_Skill.xml"
SET_SITEMAP = "https://eso-hub.com/sitemaps/en/sitemap_en_ArmorSet.xml"
USER_AGENT = ("esolog-tail build script "
              "(+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)")
SCRIBED_SKILL_SITEMAP = "https://eso-hub.com/sitemaps/en/sitemap_en_ScribingCombination.xml"
SCRIPT_SITEMAP = "https://eso-hub.com/sitemaps/en/sitemap_en_Script.xml"
SKILL_PAGE_RE = re.compile(r"^https://eso-hub\.com(/en/skills/[^/]+/[^/]+/([^/]+))/?$")
SET_PAGE_RE = re.compile(r"^https://eso-hub\.com(/en/sets/([^/]+))/?$")
SCRIBED_SKILL_PAGE_RE = re.compile(
    r"^https://eso-hub\.com(/en/scribing/combination/\d+/([^/]+))/?$")
SCRIPT_PAGE_RE = re.compile(r"^https://eso-hub\.com(/en/scribing/scripts/([^/]+))/?$")

# LibSets spellings that differ from ESO-Hub's page slugs
SET_SLUG_ALIASES = {
    "Blood Spawn": "bloodspawn",
    "Icy Conjuror": "icy-conjurer",
    "Claw of Yolnakhriin": "claw-of-yolnahkriin",
    "Perfected Claw of Yolnakhriin": "perfected-claw-of-yolnahkriin",
    "Encrati's Behemoth": "encratiss-behemoth",
    "Lady Malydga": "lady-malygda",
    "Langour of Peryite": "languor-of-peryite",
    "Bastion of Draoife": "bastion-of-the-draoife",
    "Judgement of Akatosh": "judgment-of-akatosh",
    "Black-Grove Grounding": "black-glove-grounding",
    "Ayleid Rufuge": "ayleid-refuge",
    "Aetheric Lance": "aetheric-lancer",
}
# Not player sets: test templates, superseded entries, dev items
SKIP_SET_RE = re.compile(r"^Template_Drop_|\(OLD\)$|^Malacath's Band of Brutality X$")
# Scripts whose name in 2026 logs differs from ESO-Hub's page (logs up to
# March 2026 still used the page's name): log name -> ESO-Hub slug
SCRIPT_SLUG_ALIASES = {
    "Class Flourish": "class-mastery",
    "Brutality": "brutality-and-sorcery",
    "Savagery": "savagery-and-prophecy",
}


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def page_paths(xml: str, pattern) -> dict:
    """slug -> page path for every sitemap <loc> the pattern matches; the first
    page wins when two share a slug (reported by the caller)."""
    paths, collisions = {}, []
    for loc in re.findall(r"<loc>(.*?)</loc>", xml):
        match = pattern.match(loc.strip())
        if not match:
            continue
        path, slug = match.group(1), match.group(2)
        if slug in paths and paths[slug] != path:
            collisions.append((slug, paths[slug], path))
            continue
        paths[slug] = path
    return paths, collisions


def set_slug(name: str) -> str:
    if name in SET_SLUG_ALIASES:
        return SET_SLUG_ALIASES[name]
    return slugify(re.sub(r"^Perfect ", "Perfected ", name))


def previous_keys(path: Path, key: str) -> set:
    if not path.is_file():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get(key, {}))
    except ValueError:
        return set()


def write(path: Path, source: str, key: str, mapping: dict, extra: dict) -> None:
    before = previous_keys(path, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "source": source, "count": len(mapping)}
    payload.update(extra)
    payload[key] = dict(sorted(mapping.items()))
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    added, removed = sorted(set(mapping) - before), sorted(before - set(mapping))
    print(f"{path.relative_to(REPO_ROOT)}: {len(mapping)} entries (+{len(added)} -{len(removed)} vs previous)")
    for label, items in (("added", added), ("removed", removed)):
        if items:
            print(f"  {label}: {', '.join(items[:12])}{' ...' if len(items) > 12 else ''}")


def generate_skills() -> None:
    skills, collisions = page_paths(fetch(SKILL_SITEMAP), SKILL_PAGE_RE)
    if len(skills) < 500:
        sys.exit(f"only {len(skills)} skill pages found in {SKILL_SITEMAP}; not overwriting")
    write(DATA_DIR / "skills_en.json", SKILL_SITEMAP, "skills", skills, {})
    for slug, kept, other in collisions:
        print(f"  ambiguous skill slug {slug!r}: kept {kept}, also {other}")


def generate_scribing() -> None:
    skills, collisions = page_paths(fetch(SCRIBED_SKILL_SITEMAP), SCRIBED_SKILL_PAGE_RE)
    if len(skills) < 80:
        sys.exit(f"only {len(skills)} scribed skill pages found in "
                 f"{SCRIBED_SKILL_SITEMAP}; not overwriting")
    scripts, _ = page_paths(fetch(SCRIPT_SITEMAP), SCRIPT_PAGE_RE)
    if len(scripts) < 50:
        sys.exit(f"only {len(scripts)} script pages found in {SCRIPT_SITEMAP}; not overwriting")
    pages = len(scripts)
    for name, target in SCRIPT_SLUG_ALIASES.items():
        if target in scripts:
            scripts.setdefault(slugify(name), scripts[target])
        else:
            print(f"  script alias {name!r}: ESO-Hub has no page {target!r}")
    write(DATA_DIR / "scribing_en.json", SCRIBED_SKILL_SITEMAP, "skills", skills,
          {"scripts_source": SCRIPT_SITEMAP, "scripts": dict(sorted(scripts.items()))})
    print(f"  {pages} script pages, {len(scripts) - pages} more names for renamed scripts")
    for slug, kept, other in collisions:
        print(f"  ambiguous scribed skill slug {slug!r}: kept {kept}, also {other}")


def generate_sets() -> None:
    set_pages, _ = page_paths(fetch(SET_SITEMAP), SET_PAGE_RE)
    if len(set_pages) < 400:
        sys.exit(f"only {len(set_pages)} set pages found in {SET_SITEMAP}; not overwriting")
    sets, unmatched = {}, []
    for name in SET_ID_TO_NAME.values():
        if SKIP_SET_RE.search(name):
            continue
        path = set_pages.get(set_slug(name))
        if path:
            sets[name] = path
        else:
            unmatched.append(name)
    write(DATA_DIR / "sets_en.json", SET_SITEMAP, "sets", sets,
          {"unmatched_libsets_names": sorted(unmatched)})
    if unmatched:
        print(f"  {len(unmatched)} LibSets names without an ESO-Hub page: "
              f"{', '.join(unmatched[:12])}{' ...' if len(unmatched) > 12 else ''}")


GENERATORS = {"skills": generate_skills, "sets": generate_sets, "scribing": generate_scribing}


def main() -> int:
    wanted = sys.argv[1:] or list(GENERATORS)
    unknown = [name for name in wanted if name not in GENERATORS]
    if unknown:
        sys.exit(f"unknown map {', '.join(unknown)}; choose from {', '.join(GENERATORS)}")
    for name in wanted:
        GENERATORS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
