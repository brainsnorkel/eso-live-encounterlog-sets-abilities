#!/usr/bin/env python3
"""
Export game icons and ability, skill line, mundus and set tables as a bundle
for esobuild.com (the eso-build-o-rama repository).

Why: esobuild.com shows each top build's ability bars with the game's icons
and names a build by its three class skill lines. ESO Logs gives it the game's
ability id and icon file name for every slotted skill, so it needs the icons
under the game's own file names and tables keyed by the game's ids, rebuilt
from the client after each patch rather than typed in by hand.

The bundle, esobuild-assets-<update>-<YYYYMMDD>.zip:
  manifest.json     update tag, client version, sources, counts, SHA-1 per file
  icons/<stem>.png  every ability_* icon in eso.mnf, the --extra-stems, and
                    any other icon an entry of abilities.json names
  abilities.json    game ability id -> name, icon, skill line, class, type,
                    base ability, morph, rank
  skill_lines.json  skill line -> category, class, ability ids, grimoire icons
  mundus.json       the 13 mundus boon ids -> name, icon, ESO-Hub page
  sets.json         LibSets set id -> name, type, pieces, perfected pair,
                    ESO-Hub page
  esohub/*.json     copies of data/esohub/ (run generate_esohub_links.py first)

What abilities.json holds:
  * every skill of UESP's skill tree under its game id, morphs included. The
    game uses one id for all four ranks of most skills; UESP numbers the other
    ranks 20000000 + id and up, and those are left out because they are not
    game ids;
  * scribed skills: each grimoire and focus script pair that has the
    grimoire's icon. The game names a scribed skill after the player's focus
    script, so its name differs between players; its icon and line do not;
  * "variants" (entries with "variant_of"): abilities outside the skill tree
    that carry a slottable skill's exact name and an icon of the same family.
    The game slots some of them in place of the skill (Blighted Blastbones
    while it is on cooldown, Incapacitating Strike at 120 ultimate); the rest
    are the skill's internal effects and older rank ids, which share its line;
  * BAR_SWAPS below: slotted abilities that share no name with their skill;
  * the 13 mundus boons.

Sources and what they need (Windows):
  * Icons and the client version come from the installed game: EsoExtractData
    and Pillow as for extract_ability_icons.py, which does the extraction.
  * Abilities and sets come from UESP's ESO log export (esolog.uesp.net,
    CC-BY-SA 2.5): four requests per run, a few seconds apart. Replies are
    kept in <out>/sources and reused for a day, so further runs ask UESP
    nothing. If a server refuses a request the script stops; it never retries.
    UESP can lag a new update by days: --check-log compares the tables with
    what the client itself wrote to an Encounter.log.
  * ESO-Hub page paths come from its sitemaps; a set or mundus stone without a
    page gets null, never a guessed path.

Typical run, then the same with --previous <the last bundle> to see what an
update changed:
    python scripts/generate_esohub_links.py
    python scripts/export_esobuild_assets.py --update u51 \\
        --extra-stems <fixtures>/extra-icon-stems.txt --check-fixtures <fixtures>

The bundle is published as a GitHub release asset, not committed. The game
folder is only read.
"""

import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT / "src"))
import extract_ability_icons as icon_extractor  # noqa: E402
import generate_esohub_links as esohub  # noqa: E402
from ability_icons import icon_stem, slugify  # noqa: E402
from eso_log_structures import BeginLogEntry  # noqa: E402
from gear_set_data import SET_ID_TO_NAME  # noqa: E402

BUNDLE_FORMAT = 1
DEFAULT_OUT = REPO_ROOT / "build" / "esobuild-assets"
ICON_FAMILY = "ability_"
GRIMOIRE_PREFIX = "ability_grimoire_"
# The placeholder icons of abilities that have none of their own
GENERIC_ICONS = {"ability_mage_065", "icon_missing"}
# UESP numbers ranks 2 to 4 of a skill 20000000 + id, 30000000 + id, ...
SYNTHETIC_ID_START = 10_000_000
MUNDUS_IDS = (13940, 13943, 13974, 13975, 13976, 13977, 13978, 13979,
              13980, 13981, 13982, 13984, 13985)
MUNDUS_NAME_PREFIX = "Boon: "
# UESP's skillType number -> the bundle's category
CATEGORY_BY_SKILL_TYPE = {"1": "class", "2": "weapon", "3": "armor", "4": "world",
                          "5": "guild", "6": "alliance-war", "7": "racial", "8": "craft"}
# Abilities the game slots in place of a skill under another name and icon
# family, which no rule finds: ability id -> the skill it stands in for, or
# None for one that belongs to no skill line. Each was seen on a bar, in ESO
# Logs top builds or in encounter logs; --check-log lists new ones.
BAR_SWAPS = {
    20824: "Flame Lash",                 # Power Lash, its off-balance proc
    77140: "Summon Twilight Tormentor",  # Twilight Tormentor Enrage, while the pet is out
    92163: "Eternal Guardian",           # Guardian's Savagery, while the bear is out
    267416: "Werewolf Transformation",   # Rampage, while transformed
    195031: None,                        # Crypt Transfer, from the Cryptcanon Vestments mythic
}
PERFECTED_RE = re.compile(r"^Perfect(?:ed)? (.+)$")

UESP_EXPORT = "https://esolog.uesp.net/exportJson.php"
# name -> (query, table in the reply, fewest rows a complete reply holds)
UESP_TABLES = {
    "skill_tree": ("?table=skillTree&fields=abilityId,displayId,skillTypeName,baseName,name,"
                   "rank,maxRank,type,icon", "skillTree", 3000),
    "player_skills": ("?table=playerSkills&fields=id,displayId,name,texture,isPassive,classType,"
                      "skillLine,baseAbilityId,rank,morph,skillType,isCrafted", "playerSkills", 3000),
    "mined_skills": ("?table=minedSkills&fields=id,name,texture,mechanic", "minedSkills", 100000),
    "set_summary": ("?table=setSummary&fields=gameId,setName,type,setMaxEquipCount", "setSummary", 600),
}
MUNDUS_SITEMAP = "https://eso-hub.com/sitemaps/en/sitemap_en_MundusStone.xml"
MUNDUS_PAGE_RE = re.compile(r"^https://eso-hub\.com(/en/mundus-stones/([^/]+))/?$")
REQUEST_PAUSE_S = 5
MAX_SOURCE_AGE = timedelta(hours=24)

LICENSING = ("Icons (c) ZeniMax Online Studios, extracted from the user's client for display only. "
             "Ability and set text from UESP (CC-BY-SA 2.5). Set ids from LibSets by Baertram.")

# The site's contract, checked by --check-fixtures: its 21 class skill lines
SITE_CLASS_LINES = {
    "Ardent Flame": "Dragonknight", "Draconic Power": "Dragonknight", "Earthen Heart": "Dragonknight",
    "Dark Magic": "Sorcerer", "Daedric Summoning": "Sorcerer", "Storm Calling": "Sorcerer",
    "Assassination": "Nightblade", "Shadow": "Nightblade", "Siphoning": "Nightblade",
    "Aedric Spear": "Templar", "Dawn's Wrath": "Templar", "Restoring Light": "Templar",
    "Animal Companions": "Warden", "Green Balance": "Warden", "Winter's Embrace": "Warden",
    "Grave Lord": "Necromancer", "Bone Tyrant": "Necromancer", "Living Death": "Necromancer",
    "Herald of the Tome": "Arcanist", "Curative Runeforms": "Arcanist", "Soldier of Apocrypha": "Arcanist",
}
CLASS_ICON_PREFIXES = tuple(f"ability_{c.lower()}" for c in sorted(set(SITE_CLASS_LINES.values())))
# Renamed in the 2026 class rework and unknown to the site's old name table
RENAMED_CLASS_SKILLS = {
    28311: "Vibrant Shroud", 34727: "Healthy Offering", 34721: "Shrewd Offering", 186209: "Tidal Chakram",
    32785: "Heart of Flame", 32792: "Soul of Flame", 20328: "Earthshield Mantle",
    20323: "Shatterspike Mantle", 20496: "Chains of Dominance", 32853: "Incinerate", 20668: "Searing Claw",
    32744: "Blood of the Green Dragon", 32722: "Blood of the Elder Dragon", 20779: "Fire Keeper",
    32710: "Hearth and Home", 31816: "Magma Fist", 20917: "Dragonfire Breath",
    20944: "Disintegrating Dragonfire", 20930: "Engulfing Dragonfire", 21017: "Protect the Brood",
    21014: "Fleetstep Wings", 22259: "Ritual of Retribution", 29482: "Regenerative Ward",
    86130: "Ice Fortress", 77140: "Twilight Tormentor Enrage",
}
# Names the site's substring matching gave to a class line
NOT_CLASS_SKILLS = {38745: ("Carve", "Two Handed"), 85187: ("Rend", "Dual Wield"),
                    42176: ("Bone Surge", "Undaunted")}
# ESO Logs gives a scribed skill a pseudo-id and this name: skill (script / script)
SCRIBED_PSEUDO_NAME_RE = re.compile(r"^.+ \(.+ / .+\)$")


def log(msg: str) -> None:
    print(msg, flush=True)


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def write_json(path: Path, payload) -> None:
    """Sorted keys, 1-space indent, LF: the same input always gives the same bytes."""
    text = json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def icon_family(stem: str) -> str:
    """'ability_necromancer_002_a_blackedout' -> 'ability_necromancer'."""
    return "_".join(stem.split("_")[:2])


def same_version(client: str, logged: str) -> bool:
    """True when a log's 'eso.live.12.1' names the client's 'eso.live.12.1.5'."""
    return bool(logged) and (client == logged or client.startswith(logged + "."))


# ------------------------------------------------------------------ sources --

class Sources:
    """Raw replies kept in a folder, with index.json recording each one's URL
    and fetch time. A reply younger than MAX_SOURCE_AGE is reused, so repeated
    runs do not ask the servers again."""

    def __init__(self, folder: Path, refetch: bool = False, offline: bool = False):
        self.folder = folder
        self.refetch = refetch
        self.offline = offline
        self.index_path = folder / "index.json"
        self.index = {}
        if self.index_path.is_file():
            try:
                self.index = json.loads(self.index_path.read_text(encoding="utf-8"))
            except ValueError:
                self.index = {}
        self._last_request = {}  # host -> time.monotonic() of the last request

    def get(self, name: str, url: str, suffix: str, validate) -> bytes:
        """The reply stored as <name><suffix>, fetched when missing or stale.
        *validate* raises ValueError for a reply that must not be kept."""
        path = self.folder / (name + suffix)
        entry = self.index.get(name)
        if path.is_file() and entry and not self.refetch:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(entry["fetched"])
            if self.offline or age < MAX_SOURCE_AGE:
                log(f"  {name}: reusing the reply fetched {entry['fetched']}")
                return path.read_bytes()
        if self.offline:
            sys.exit(f"--offline: no stored reply for {name} in {self.folder}")
        host = urlsplit(url).netloc
        wait = REQUEST_PAUSE_S - (time.monotonic() - self._last_request.get(host, -REQUEST_PAUSE_S))
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": esohub.USER_AGENT,
                                                       "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
        except urllib.error.HTTPError as exc:
            sys.exit(f"{host} refused {name} (HTTP {exc.code}). Not retrying: wait a while and run "
                     f"again. Replies already fetched are kept in {self.folder}.")
        except (urllib.error.URLError, OSError) as exc:
            sys.exit(f"could not fetch {name} from {host}: {exc}")
        finally:
            self._last_request[host] = time.monotonic()
        try:
            validate(body)
        except ValueError as exc:
            sys.exit(f"{host} sent an unusable reply for {name}: {exc}. Nothing was stored.")
        self.folder.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        self.index[name] = {"url": url, "bytes": len(body), "sha1": sha1_bytes(body),
                            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        write_json(self.index_path, self.index)
        log(f"  {name}: fetched {len(body):,} bytes from {host}")
        return body

    def describe(self, name: str) -> str:
        entry = self.index[name]
        return f"{entry['url']} (fetched {entry['fetched'][:10]})"


def uesp_rows(sources: Sources, name: str):
    """One UESP table as a list of row dicts."""
    query, table, fewest = UESP_TABLES[name]

    def rows_of(body: bytes):
        try:
            reply = json.loads(body.decode("utf-8"))
        except ValueError:
            raise ValueError("not JSON (a challenge page?)") from None
        rows = reply.get(table) if isinstance(reply, dict) else None
        if not isinstance(rows, list) or len(rows) < fewest:
            found = len(rows) if isinstance(rows, list) else 0
            raise ValueError(f"{found} {table} rows, expected at least {fewest}")
        return rows

    return rows_of(sources.get(name, UESP_EXPORT + query, ".json", rows_of))


def sitemap_pages(sources: Sources, name: str, url: str, pattern, fewest: int) -> dict:
    """slug -> page path for the pages of an ESO-Hub sitemap."""
    def pages_of(body: bytes):
        pages, _ = esohub.page_paths(body.decode("utf-8", errors="replace"), pattern)
        if len(pages) < fewest:
            raise ValueError(f"{len(pages)} pages, expected at least {fewest}")
        return pages

    return pages_of(sources.get(name, url, ".xml", pages_of))


# ------------------------------------------------------------------- tables --

def build_abilities(tree_rows, player_rows, mined_rows):
    """(abilities, skill_lines, origins, notes) from UESP's skillTree,
    playerSkills and minedSkills rows; see the module docstring for what
    counts as an ability here. *origins* counts the entries by where they
    came from; *notes* are lines for the run summary."""
    notes = []
    tree = {}
    for row in tree_rows:
        ability_id = to_int(row.get("abilityId"), 0)
        if 0 < ability_id < SYNTHETIC_ID_START:
            tree[ability_id] = row
    player = {}
    for row in player_rows:
        ability_id = to_int(row.get("id"), 0)
        if 0 < ability_id < SYNTHETIC_ID_START:
            player[ability_id] = row

    # UESP also flags placeholders and each script's effects as player skills:
    # keep what the skill tree lists, and the scribed skills a bar can show
    kept = {}
    for ability_id, row in sorted(player.items()):
        stem = icon_stem(row.get("texture") or "")
        if row.get("isCrafted") == "1":
            if stem.startswith(GRIMOIRE_PREFIX):
                kept[ability_id] = (row, stem, "active", "scribed")
        elif ability_id in tree:
            kind = (tree[ability_id].get("type") or "").lower()
            if kind not in ("active", "ultimate", "passive"):
                raise ValueError(f"ability {ability_id}: unknown skill type {kind!r}")
            kept[ability_id] = (row, stem, kind, "skill_tree")

    # "Class Mastery" names one line per class: those keys get the class added
    owners = defaultdict(set)
    for row, _, _, _ in kept.values():
        owners[row["skillLine"]].add((row.get("skillType"), row.get("classType") or ""))

    def line_key(row) -> str:
        name = row["skillLine"]
        if len(owners[name]) > 1 and row.get("classType"):
            return f"{name} ({row['classType']})"
        return name

    abilities, skill_lines, origins = {}, {}, Counter()
    for ability_id, (row, stem, kind, origin) in kept.items():
        key = line_key(row)
        category = CATEGORY_BY_SKILL_TYPE.get(str(row.get("skillType")))
        if category is None:
            raise ValueError(f"ability {ability_id}: unknown UESP skillType {row.get('skillType')!r}")
        line = skill_lines.setdefault(key, {"category": category, "class": row.get("classType") or None,
                                            "ability_ids": []})
        if (line["category"], line["class"]) != (category, row.get("classType") or None):
            raise ValueError(f"skill line {key!r} has two owners")
        if key != row["skillLine"]:
            line["game_name"] = row["skillLine"]
        if origin == "scribed":
            line.setdefault("grimoire_icon_stems", set()).add(stem)
        base_id = to_int(row.get("baseAbilityId"), 0)
        base = kept.get(base_id)
        morph, rank = to_int(row.get("morph"), -1), to_int(row.get("rank"), -1)
        abilities[ability_id] = {
            "name": row["name"], "icon": stem, "skill_line": key, "class": line["class"], "type": kind,
            "base_ability_id": base_id if base else None, "base_name": base[0]["name"] if base else None,
            "morph": morph if morph in (0, 1, 2) else None, "rank": rank if rank >= 1 else None,
        }
        origins[origin] += 1

    slottable = defaultdict(list)  # skill name -> its ability ids, lowest first
    for ability_id, entry in abilities.items():
        if entry["type"] != "passive":
            slottable[entry["name"]].append(ability_id)

    def stand_in(row, stem, parent_id):
        parent = abilities[parent_id]
        return {"name": row["name"], "icon": stem, "skill_line": parent["skill_line"],
                "class": parent["class"], "type": parent["type"],
                "base_ability_id": parent["base_ability_id"], "base_name": parent["base_name"],
                "morph": parent["morph"], "rank": None, "variant_of": parent_id}

    mined = {}
    for row in mined_rows:
        ability_id = to_int(row.get("id"), 0)
        if 0 < ability_id < SYNTHETIC_ID_START:
            mined[ability_id] = row

    extra = {}
    for ability_id, skill in sorted(BAR_SWAPS.items()):
        row = mined.get(ability_id)
        if ability_id in abilities or row is None:
            notes.append(f"bar swap {ability_id} skipped: "
                         + ("now a skill tree ability" if row else "not in UESP's data"))
            continue
        stem = icon_stem(row.get("texture") or "")
        if skill is None:
            extra[ability_id] = {"name": row["name"], "icon": stem, "skill_line": None, "class": None,
                                 "type": "ultimate" if row.get("mechanic") == "8" else "active",
                                 "base_ability_id": None, "base_name": None, "morph": None, "rank": None}
        elif skill in slottable:
            extra[ability_id] = stand_in(row, stem, slottable[skill][0])
        else:
            notes.append(f"bar swap {ability_id} ({row['name']}) skipped: no skill named {skill!r}")
            continue
        origins["bar_swap"] += 1

    for ability_id, row in sorted(mined.items()):
        if ability_id in abilities or ability_id in extra:
            continue
        parents = slottable.get(row.get("name") or "")
        stem = icon_stem(row.get("texture") or "")
        if not parents or not stem or stem in GENERIC_ICONS:
            continue
        related = [p for p in parents if icon_family(abilities[p]["icon"]) == icon_family(stem)]
        if not related:
            continue
        if len({abilities[p]["skill_line"] for p in related}) > 1:
            notes.append(f"variant {ability_id} ({row['name']}) skipped: skills of two lines share its name")
            continue
        same_icon = [p for p in related if abilities[p]["icon"] == stem]
        extra[ability_id] = stand_in(row, stem, (same_icon or related)[0])
        origins["variant"] += 1

    for ability_id in MUNDUS_IDS:
        row = mined.get(ability_id)
        if row is None:
            notes.append(f"mundus boon {ability_id} is not in UESP's data")
            continue
        extra[ability_id] = {"name": row["name"], "icon": icon_stem(row.get("texture") or ""),
                             "skill_line": None, "class": None, "type": "passive",
                             "base_ability_id": None, "base_name": None, "morph": None, "rank": None}
        origins["mundus"] += 1

    abilities.update(extra)
    for ability_id, entry in abilities.items():
        if entry["skill_line"] is not None:
            skill_lines[entry["skill_line"]]["ability_ids"].append(ability_id)
    for line in skill_lines.values():
        line["ability_ids"].sort()
        if "grimoire_icon_stems" in line:
            line["grimoire_icon_stems"] = sorted(line["grimoire_icon_stems"])
    return abilities, skill_lines, dict(origins), notes


def build_mundus(abilities, mundus_pages) -> dict:
    """The mundus boons among *abilities*, named as the site shows them."""
    mundus = {}
    for ability_id in MUNDUS_IDS:
        entry = abilities.get(ability_id)
        if entry is None:
            continue
        game_name = entry["name"]
        name = game_name[len(MUNDUS_NAME_PREFIX):] if game_name.startswith(MUNDUS_NAME_PREFIX) else game_name
        mundus[ability_id] = {"name": name, "game_name": game_name, "icon": entry["icon"],
                              "esohub": mundus_pages.get(slugify(name))}
    return mundus


def build_sets(set_rows, libsets_names, set_pages) -> dict:
    """LibSets set id -> name, type, pieces, perfected pair and ESO-Hub page.
    UESP's setSummary gives the game's current name; a set only LibSets knows
    keeps the LibSets name. LibSets' test and superseded entries are left out."""
    names, rows = {}, {}
    for row in set_rows:
        set_id = to_int(row.get("gameId"), 0)
        if set_id > 0 and row.get("setName"):
            names[set_id] = row["setName"]
            rows[set_id] = row
    libsets = {int(set_id): name for set_id, name in libsets_names.items()}
    for set_id, name in libsets.items():
        if set_id not in names and not esohub.SKIP_SET_RE.search(name):
            names[set_id] = name

    # UESP spells one type two ways ("PVP", "PvP"): the commoner spelling wins
    spellings = defaultdict(Counter)
    for row in rows.values():
        if row.get("type"):
            spellings[row["type"].casefold()][row["type"]] += 1
    set_type = {folded: sorted(seen.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                for folded, seen in spellings.items()}

    id_of = {name: set_id for set_id, name in names.items()}
    perfected_of, unperfected_of = {}, {}
    for set_id, name in names.items():
        match = PERFECTED_RE.match(name)
        base_id = id_of.get(match.group(1)) if match else None
        if base_id is not None:
            perfected_of[base_id] = set_id
            unperfected_of[set_id] = base_id

    sets = {}
    for set_id, name in sorted(names.items()):
        row = rows.get(set_id, {})
        page = set_pages.get(slugify(name))
        if page is None and set_id in libsets:
            page = set_pages.get(esohub.set_slug(libsets[set_id]))
        sets[set_id] = {"name": name, "type": set_type.get((row.get("type") or "").casefold()),
                        "max_equip": to_int(row.get("setMaxEquipCount"), 0) or None,
                        "perfected_id": perfected_of.get(set_id),
                        "unperfected_id": unperfected_of.get(set_id), "esohub": page}
    return sets


def string_keys(table: dict) -> dict:
    return {str(key): value for key, value in table.items()}


# --------------------------------------------------------------- the client --

def find_eso_dir(explicit: str, server: str) -> Path:
    if explicit or server == "live":
        return icon_extractor.find_eso_dir(explicit)
    for candidate in icon_extractor.ESO_DIR_CANDIDATES:
        if (Path(candidate + " PTS") / "depot" / "eso.mnf").is_file():
            return Path(candidate + " PTS")
    sys.exit("PTS eso.mnf not found. Pass --eso-dir <PTS install folder>.")


def read_databuild(eso_dir: Path) -> dict:
    """The client's own record of its data build, depot/_databuild/databuild.stamp:
    three lines, e.g. '4000.win.3303624.live.3303624', '2026/09/25:05:30:56', '12.1.5'."""
    stamp = eso_dir / "depot" / "_databuild" / "databuild.stamp"
    try:
        lines = stamp.read_text(encoding="utf-8", errors="replace").split()
    except OSError:
        return {}
    if len(lines) < 3 or not re.fullmatch(r"\d+(\.\d+)+", lines[2]):
        return {}
    parts = lines[0].split(".")
    info = {"build": lines[0], "version": lines[2], "channel": parts[3] if len(parts) == 5 else ""}
    try:
        info["built"] = datetime.strptime(lines[1], "%Y/%m/%d:%H:%M:%S").isoformat(timespec="seconds")
    except ValueError:
        pass
    return info


def last_begin_log(log_path: Path):
    """The newest BEGIN_LOG line of an encounter log as a BeginLogEntry, read
    from the end of the file; None when there is none."""
    marker, chunk_size = b",BEGIN_LOG,", 4 * 1024 * 1024
    try:
        with open(log_path, "rb") as fh:
            end = fh.seek(0, 2)
            while end > 0:
                start = max(0, end - chunk_size)
                fh.seek(start)
                found = fh.read(end - start + len(marker)).rfind(marker)
                if found >= 0:
                    fh.seek(max(0, start + found - 64))
                    for line in fh.read(1024).decode("utf-8", errors="replace").splitlines():
                        entry = BeginLogEntry.parse(line)
                        if entry:
                            return entry
                    return None
                end = start
    except OSError:
        return None
    return None


def find_user_dir(explicit_log: str, server: str):
    """The ESO user folder of *server* (holds Logs/ and AddOnSettings.txt)."""
    if explicit_log:
        return Path(explicit_log).resolve().parent.parent
    for documents in (Path.home() / "Documents", Path.home() / "OneDrive" / "Documents"):
        folder = documents / "Elder Scrolls Online" / server
        if (folder / "Logs" / "Encounter.log").is_file():
            return folder
    return None


def read_game_info(eso_dir: Path, server: str, log_arg: str) -> dict:
    """What the manifest records about the client. The version comes from the
    client's build stamp; an Encounter.log written since eso.mnf was last
    patched confirms it, or supplies it when there is no stamp. Nothing is
    inferred from dates: without either source the version stays ''."""
    mnf = eso_dir / "depot" / "eso.mnf"
    patched = datetime.fromtimestamp(mnf.stat().st_mtime, timezone.utc)
    game = {"server": server, "version": "", "eso_mnf": str(mnf), "eso_mnf_bytes": mnf.stat().st_size,
            "eso_mnf_modified": datetime.fromtimestamp(mnf.stat().st_mtime).isoformat(timespec="seconds")}
    stamp = read_databuild(eso_dir)
    if stamp:
        if (stamp["channel"] == "live") != (server == "live"):
            sys.exit(f"--server {server}, but the client in {eso_dir} is a '{stamp['channel']}' build "
                     f"({stamp['build']}). Pass the matching --server or --eso-dir.")
        game["version"] = f"eso.{stamp['channel']}.{stamp['version']}"
        game["databuild"] = stamp["build"]
        if "built" in stamp:
            game["databuild_date"] = stamp["built"]

    user_dir = find_user_dir(log_arg, server)
    if user_dir:
        log_path = Path(log_arg) if log_arg else user_dir / "Logs" / "Encounter.log"
        entry = last_begin_log(log_path)
        if entry and datetime.fromtimestamp(entry.unix_timestamp / 1000, timezone.utc) >= patched:
            game["log_version"] = entry.game_version
            if not game["version"]:
                game["version"] = entry.game_version
            elif not same_version(game["version"], entry.game_version):
                log(f"WARNING: the build stamp says {game['version']}, {log_path.name} says "
                    f"{entry.game_version}")
        settings = user_dir / "AddOnSettings.txt"
        try:
            if datetime.fromtimestamp(settings.stat().st_mtime, timezone.utc) >= patched:
                with open(settings, encoding="utf-8", errors="replace") as fh:
                    match = re.match(r"#Version (\d+)", fh.readline())
                if match:
                    game["api_version"] = int(match.group(1))
        except OSError:
            pass
    return game


def extractor_version(extractor: Path) -> str:
    try:
        proc = subprocess.run([str(extractor)], capture_output=True, text=True, errors="replace",
                              timeout=60, cwd=tempfile.gettempdir())
    except (OSError, subprocess.SubprocessError):
        return ""
    match = re.search(r"EsoExtractData v([\d.]+)", (proc.stdout or "") + (proc.stderr or ""))
    return match.group(1) if match else ""


def generator_id() -> str:
    """export_esobuild_assets.py@<commit>, with -dirty when the scripts that
    shape the bundle differ from that commit."""
    scripts = ["scripts/export_esobuild_assets.py", "scripts/extract_ability_icons.py",
               "scripts/generate_esohub_links.py"]
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", *scripts], cwd=REPO_ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return f"{Path(__file__).name}@unknown"
    return f"{Path(__file__).name}@{sha}{'-dirty' if dirty else ''}"


# ------------------------------------------------------------------- checks --

def read_stems(path: Path):
    stems = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stem = line.strip().lower()
        if stem and not stem.startswith("#"):
            stems.append(stem[:-4] if stem.endswith((".dds", ".png")) else stem)
    return stems


def check_fixtures(fixtures: Path, abilities, skill_lines, icon_stems, bundle_dir=None):
    """The site's hand-over checks (V1 to V6 of its export request) against
    its fixture files. Returns (report lines, True when every check passed)."""
    report, ok = [], True

    def result(label, passed, text, details=()):
        nonlocal ok
        ok = ok and passed
        report.append(f"{label} {'ok  ' if passed else 'FAIL'} {text}")
        report.extend(f"       {d}" for d in details)

    icon_files = sorted(fixtures.glob("referenced-icons*.txt"))
    ability_files = sorted(fixtures.glob("referenced-abilities*.json"))
    if not icon_files or not ability_files:
        return [f"no referenced-icons*.txt and referenced-abilities*.json in {fixtures}"], False
    wanted_icons = sorted({s for f in icon_files for s in read_stems(f)})
    rows = [row for f in ability_files for row in json.loads(f.read_text(encoding="utf-8"))["abilities"]]

    missing = [s for s in wanted_icons if s not in icon_stems]
    result("V1", not missing, f"icons: {len(wanted_icons) - len(missing)} of {len(wanted_icons)} referenced "
           "stems have a PNG", [f"missing {s}" for s in missing])

    grimoire_stems = {s for line in skill_lines.values() for s in line.get("grimoire_icon_stems", ())}
    known = [r for r in rows if r["ability_id"] in abilities]
    pseudo = [r for r in rows if r["ability_id"] not in abilities and r["icon"] in grimoire_stems
              and SCRIBED_PSEUDO_NAME_RE.match(r["name"])]
    unknown = [r for r in rows if r["ability_id"] not in abilities and r not in pseudo]
    name_diffs = [r for r in known if abilities[r["ability_id"]]["name"] != r["name"]]
    icon_diffs = [r for r in known if abilities[r["ability_id"]]["icon"] != r["icon"]]
    scribed_diffs = [r for r in name_diffs if r["icon"] in grimoire_stems]
    result("V2", not unknown,
           f"abilities: {len(known)} of {len(known) + len(unknown)} game ids are keys; names equal "
           f"{len(known) - len(name_diffs)}, icons equal {len(known) - len(icon_diffs)}",
           [f"unknown id {r['ability_id']} {r['name']} ({r['icon']})" for r in unknown]
           + [f"name {r['ability_id']}: fixture {r['name']!r}, game {abilities[r['ability_id']]['name']!r}"
              for r in name_diffs if r not in scribed_diffs]
           + ([f"{len(scribed_diffs)} more name differences are scribed skills, which the game names "
               "after the player's focus script"] if scribed_diffs else [])
           + [f"icon {r['ability_id']} {r['name']}: fixture {r['icon']}, game "
              f"{abilities[r['ability_id']]['icon']}" for r in icon_diffs])
    if pseudo:
        ids = sorted({r["ability_id"] for r in pseudo})
        report.append(f"       {len(pseudo)} rows are ESO Logs pseudo-ids for scribed skills "
                      f"({ids[0]} to {ids[-1]}), each resolved by its grimoire icon")

    def class_line_of(ability_id):
        line = abilities[ability_id]["skill_line"]
        if line in SITE_CLASS_LINES and SITE_CLASS_LINES[line] == abilities[ability_id]["class"]:
            return line
        return None

    class_rows = [r for r in known if r["icon"].startswith(CLASS_ICON_PREFIXES)]
    off_class = [r for r in class_rows if not class_line_of(r["ability_id"])]
    renamed = [f"{name} [{i}] " + ("is not in the table" if i not in abilities else
                                   f"is {abilities[i]['name']!r} in {abilities[i]['skill_line']!r}")
               for i, name in RENAMED_CLASS_SKILLS.items()
               if i not in abilities or abilities[i]["name"] != name or not class_line_of(i)]
    result("V3", not off_class and not renamed,
           f"class lines: {len(class_rows) - len(off_class)} of {len(class_rows)} fixture rows with a "
           f"class icon map to a class line; {len(RENAMED_CLASS_SKILLS) - len(renamed)} of "
           f"{len(RENAMED_CLASS_SKILLS)} renamed skills resolve",
           [f"{r['ability_id']} {r['name']} ({r['icon']}) -> {abilities[r['ability_id']]['skill_line']}"
            for r in off_class] + renamed)

    wrong = [f"{name} [{i}] -> {abilities.get(i, {}).get('skill_line')}, expected {line}"
             for i, (name, line) in NOT_CLASS_SKILLS.items()
             if abilities.get(i, {}).get("skill_line") != line]
    result("V4", not wrong, f"look-alike names: {len(NOT_CLASS_SKILLS) - len(wrong)} of "
           f"{len(NOT_CLASS_SKILLS)} map to their own line", wrong)

    fixture_grimoires = sorted({s for s in wanted_icons if s.startswith(GRIMOIRE_PREFIX)}
                               | {r["icon"] for r in rows if r["icon"].startswith(GRIMOIRE_PREFIX)})
    orphans = [s for s in fixture_grimoires if s not in grimoire_stems]
    result("V5", not orphans, f"grimoires: {len(fixture_grimoires) - len(orphans)} of "
           f"{len(fixture_grimoires)} grimoire icons belong to a skill line", orphans)

    lines_wrong = [f"{name} ({cls})" for name, cls in SITE_CLASS_LINES.items()
                   if (skill_lines.get(name, {}).get("category"), skill_lines.get(name, {}).get("class"))
                   != ("class", cls)]
    result("R4", not lines_wrong, f"skill lines: {len(SITE_CLASS_LINES) - len(lines_wrong)} of "
           f"{len(SITE_CLASS_LINES)} class lines present with their class", lines_wrong)
    strays = sorted((i, e["name"], e["icon"], e["skill_line"]) for i, e in abilities.items()
                    if e["icon"].startswith(CLASS_ICON_PREFIXES) and not class_line_of(i))
    report.append(f"R3 info abilities.json: {len(strays)} entries with a class icon are outside the 21 "
                  "class lines")
    report.extend(f"       {i} {name} ({icon}) -> {line}" for i, name, icon, line in strays[:20])

    if bundle_dir is not None:
        report_line, passed = verify_manifest(bundle_dir)
        result("V6", passed, report_line)
    return report, ok


def verify_manifest(bundle_dir: Path):
    """(text, ok): manifest.json's counts and SHA-1s against the files."""
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    files = sorted(p.relative_to(bundle_dir).as_posix() for p in bundle_dir.rglob("*")
                   if p.is_file() and p.name != "manifest.json")
    problems = []
    if files != sorted(manifest["files"]):
        problems.append("the file list differs")
    bad = [f for f in files if manifest["files"].get(f) != sha1_bytes((bundle_dir / f).read_bytes())]
    if bad:
        problems.append(f"{len(bad)} SHA-1 mismatches, e.g. {bad[0]}")
    actual = {"icons": sum(1 for f in files if f.startswith("icons/"))}
    for name in ("abilities", "skill_lines", "mundus", "sets"):
        actual[name] = len(json.loads((bundle_dir / f"{name}.json").read_text(encoding="utf-8"))[name])
    if actual != manifest["counts"]:
        problems.append(f"counts {manifest['counts']} but found {actual}")
    return (f"manifest: counts match and {len(files)} SHA-1s verify" if not problems
            else "manifest: " + "; ".join(problems)), not problems


# ---------------------------------------------------- comparing two bundles --

def load_bundle(path: Path) -> dict:
    """{'manifest': ..., 'abilities': ..., ...} from a bundle zip or folder."""
    names = ["manifest", "abilities", "skill_lines", "mundus", "sets"]
    if path.is_dir():
        return {n: json.loads((path / f"{n}.json").read_text(encoding="utf-8")) for n in names}
    with zipfile.ZipFile(path) as archive:
        return {n: json.loads(archive.read(f"{n}.json").decode("utf-8")) for n in names}


def compare_bundles(previous: dict, current: dict):
    """Lines describing what changed from *previous* to *current*."""
    lines = []

    def listed(label, items):
        if items:
            lines.append(f"    {label}: {', '.join(items[:15])}{' ...' if len(items) > 15 else ''}")

    def diff(title, old, new, describe):
        added, removed = sorted(set(new) - set(old)), sorted(set(old) - set(new))
        changed = sorted(k for k in set(new) & set(old) if new[k] != old[k])
        lines.append(f"  {title}: {len(new)} entries; vs previous: +{len(added)} -{len(removed)} "
                     f"~{len(changed)}")
        listed("added", [describe(k, new) for k in added])
        listed("removed", [describe(k, old) for k in removed])
        listed("changed", [describe(k, new) for k in changed])

    old_files, new_files = previous["manifest"]["files"], current["manifest"]["files"]
    diff("icons", {k: v for k, v in old_files.items() if k.startswith("icons/")},
         {k: v for k, v in new_files.items() if k.startswith("icons/")}, lambda k, _: k[6:-4])
    diff("abilities", previous["abilities"]["abilities"], current["abilities"]["abilities"],
         lambda k, table: f"{k} {table[k]['name']}")
    diff("skill lines", previous["skill_lines"]["skill_lines"], current["skill_lines"]["skill_lines"],
         lambda k, _: k)
    diff("mundus", previous["mundus"]["mundus"], current["mundus"]["mundus"],
         lambda k, table: f"{k} {table[k]['name']}")
    diff("sets", previous["sets"]["sets"], current["sets"]["sets"],
         lambda k, table: f"{k} {table[k]['name']}")
    differing = sorted(k for k in set(old_files) | set(new_files) if old_files.get(k) != new_files.get(k))
    same_client = previous["manifest"]["game"] == current["manifest"]["game"]
    lines.append(f"  V7 {'same' if same_client else 'different'} client; files that differ besides "
                 f"manifest.json: {len(differing)}"
                 + (f" ({', '.join(differing[:8])}{' ...' if len(differing) > 8 else ''})" if differing
                    else " (identical)"))
    return lines


# ---------------------------------------------------------------- log check --

def check_log(log_path: Path, abilities, game_version: str):
    """Lines comparing the tables with what the client wrote to an encounter
    log in sessions of this game version: UESP can lag a new update, and a new
    bar swap shows up here first."""
    named, slotted, current, sessions = {}, set(), False, 0
    with open(log_path, "rb") as fh:
        for raw in fh:
            head = raw[:48]
            if b",BEGIN_LOG," in head:
                entry = BeginLogEntry.parse(raw.decode("utf-8", errors="replace").strip())
                current = bool(entry) and same_version(game_version, entry.game_version)
                sessions += current
            elif not current:
                continue
            elif b",ABILITY_INFO," in head:
                match = icon_extractor.ABILITY_INFO_RE.match(raw.decode("utf-8", errors="replace"))
                if match:
                    named[int(match.group(1))] = (match.group(2).replace('""', '"'), icon_stem(match.group(3)))
            elif b",PLAYER_INFO," in head:
                groups = re.findall(r"\[([0-9,]*)\]", raw.decode("utf-8", errors="replace"))
                for group in groups[-2:]:  # [abilities],[levels],[gear],[front],[back]
                    slotted.update(int(a) for a in group.split(",") if a and a != "0")
    lines = [f"  {log_path.name}: {sessions} sessions of {game_version}, {len(named):,} abilities named, "
             f"{len(slotted)} slotted on bars"]
    shared = {i: v for i, v in named.items() if i in abilities and v[0]}
    scribed = {i for i in shared if abilities[i]["icon"].startswith(GRIMOIRE_PREFIX)}
    names = [(i, v[0]) for i, v in sorted(shared.items()) if i not in scribed and v[0] != abilities[i]["name"]]
    icons = [(i, v[1]) for i, v in sorted(shared.items()) if v[1] and v[1] != abilities[i]["icon"]]
    lines.append(f"  of {len(shared):,} table abilities the log names: {len(names)} names and "
                 f"{len(icons)} icons differ ({len(scribed)} scribed skills not compared by name)")
    lines.extend(f"    name {i}: log {name!r}, table {abilities[i]['name']!r}" for i, name in names[:25])
    lines.extend(f"    icon {i} {abilities[i]['name']}: log {icon}, table {abilities[i]['icon']}"
                 for i, icon in icons[:25])
    unknown = sorted(i for i in slotted if i not in abilities)
    lines.append(f"  slotted ids missing from the table: {len(unknown)}")
    lines.extend(f"    {i} {named.get(i, ('?', '?'))[0]} ({named.get(i, ('?', '?'))[1]})" for i in unknown[:25])
    return lines, not (names or icons or unknown)


# --------------------------------------------------------------------- main --

def write_zip(bundle_dir: Path, zip_path: Path) -> None:
    """Zip the bundle with sorted names and a fixed timestamp, so the archive
    differs between runs only where a file does."""
    with zipfile.ZipFile(zip_path, "w") as archive:
        for path in sorted(p for p in bundle_dir.rglob("*") if p.is_file()):
            name = path.relative_to(bundle_dir).as_posix()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED if name.endswith(".png") else zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", required=True, metavar="uXX",
                    help="the site's tag for the update the client is on, e.g. u51 (never inferred)")
    ap.add_argument("--server", choices=("live", "pts"), default="live", help="which client (default live)")
    ap.add_argument("--eso-dir", default="", help="ESO install folder (contains depot\\eso.mnf)")
    ap.add_argument("--extractor", default="", help="path to EsoExtractData.exe")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help=f"folder for the bundle, its zip and the stored replies (default {DEFAULT_OUT})")
    ap.add_argument("--size", type=int, default=64, help="PNG edge length in px (default 64, the game's own)")
    ap.add_argument("--extra-stems", default="", metavar="FILE",
                    help="text file of icon stems outside the ability_* family to include, one per line")
    ap.add_argument("--previous", default="", metavar="BUNDLE",
                    help="an earlier bundle (zip or folder): print what was added, removed and changed")
    ap.add_argument("--check-fixtures", default="", metavar="DIR",
                    help="folder with the site's referenced-icons*.txt and referenced-abilities*.json: "
                         "run its hand-over checks")
    ap.add_argument("--check-log", default="", metavar="LOG",
                    help="Encounter.log to compare ability names and icons with, and to look for "
                         "slotted abilities the table lacks")
    ap.add_argument("--log", default="", metavar="LOG",
                    help="Encounter.log that confirms the client version (default: the one in Documents)")
    ap.add_argument("--gap-mb", type=float, default=10.0,
                    help="bridge index gaps up to this many MB of unrelated files per range (default 10)")
    ap.add_argument("--refetch", action="store_true", help="fetch every source again, ignoring stored replies")
    ap.add_argument("--offline", action="store_true", help="use only stored replies, whatever their age")
    ap.add_argument("--dry-run", action="store_true",
                    help="build the tables and run the checks, but extract no icons and write no bundle")
    ap.add_argument("--keep-temp", action="store_true", help="keep the temp extraction folder")
    args = ap.parse_args()
    if not re.fullmatch(r"u\d+", args.update):
        ap.error("--update must look like u51")

    eso_dir = find_eso_dir(args.eso_dir, args.server)
    extractor = icon_extractor.find_extractor(args.extractor)
    mnf = eso_dir / "depot" / "eso.mnf"
    out = Path(args.out)
    game = read_game_info(eso_dir, args.server, args.log)
    log(f"client:     {game['version'] or '(version unknown)'}, eso.mnf modified {game['eso_mnf_modified']}"
        + (f", API {game['api_version']}" if "api_version" in game else ""))
    if "api_version" in game and game["api_version"] % 1000 != int(args.update[1:]):
        log(f"WARNING: --update {args.update}, but the client last ran with API version {game['api_version']}")
    if not game["version"]:
        log("WARNING: no build stamp and no Encounter.log newer than eso.mnf; the manifest's game "
            "version stays empty")

    log("sources:")
    sources = Sources(out / "sources", refetch=args.refetch, offline=args.offline)
    tree_rows = uesp_rows(sources, "skill_tree")
    player_rows = uesp_rows(sources, "player_skills")
    mined_rows = uesp_rows(sources, "mined_skills")
    set_rows = uesp_rows(sources, "set_summary")
    set_pages = sitemap_pages(sources, "esohub_sets", esohub.SET_SITEMAP, esohub.SET_PAGE_RE, 400)
    mundus_pages = sitemap_pages(sources, "esohub_mundus", MUNDUS_SITEMAP, MUNDUS_PAGE_RE, 10)

    abilities, skill_lines, origins, notes = build_abilities(tree_rows, player_rows, mined_rows)
    mundus = build_mundus(abilities, mundus_pages)
    sets = build_sets(set_rows, SET_ID_TO_NAME, set_pages)
    log(f"tables:     {len(abilities):,} abilities ({', '.join(f'{n:,} {k}' for k, n in sorted(origins.items()))}), "
        f"{len(skill_lines)} skill lines, {len(mundus)} mundus, {len(sets)} sets "
        f"({sum(1 for s in sets.values() if s['esohub'])} with an ESO-Hub page)")
    for note in notes:
        log(f"  note: {note}")

    extra_stems = read_stems(Path(args.extra_stems)) if args.extra_stems else []
    referenced = sorted({e["icon"] for e in abilities.values() if e["icon"]}
                        | {m["icon"] for m in mundus.values() if m["icon"]})
    outside = sorted(set(extra_stems) | {s for s in referenced if not s.startswith(ICON_FAMILY)})

    temp = Path(tempfile.mkdtemp(prefix="esobuild-assets-"))
    try:
        t0 = time.time()
        rows = icon_extractor.dump_file_table(extractor, mnf, temp)
        wanted = icon_extractor.icon_positions(rows, (ICON_FAMILY,), outside)
        if not wanted:
            sys.exit("no ability icons in the file table; is this the right eso.mnf?")
        in_client = {rows[i][2].rsplit("\\", 1)[-1].lower()[:-4] for i in wanted}
        missing_extra = sorted(s for s in extra_stems if s not in in_client)
        missing_referenced = sorted(s for s in referenced if s not in in_client)
        ranges = icon_extractor.merge_ranges(rows, wanted, int(args.gap_mb * 1_000_000))
        log(f"icons:      {len(rows):,} file table rows in {time.time() - t0:.1f}s; {len(wanted):,} icons "
            f"({sum(1 for s in in_client if not s.startswith(ICON_FAMILY))} outside {ICON_FAMILY}*) "
            f"-> {len(ranges)} ranges")
        for label, stems in (("extra stems not in the client", missing_extra),
                             ("icons abilities.json names that the client lacks", missing_referenced)):
            if stems:
                log(f"  WARNING: {label}: {', '.join(stems)}")

        failed = []
        bundle_dir = None
        if not args.dry_run:
            generated = datetime.now(timezone.utc)
            name = f"esobuild-assets-{args.update}-{generated:%Y%m%d}"
            bundle_dir = out / name
            if bundle_dir.exists():
                if any(bundle_dir.iterdir()) and not (bundle_dir / "manifest.json").is_file():
                    sys.exit(f"{bundle_dir} exists and is not a bundle; move it away first")
                shutil.rmtree(bundle_dir)
            icons, failed = icon_extractor.extract_icons(extractor, mnf, rows, wanted, ranges,
                                                         bundle_dir / "icons", args.size, temp)
            write_json(bundle_dir / "abilities.json",
                       {"update": args.update, "abilities": string_keys(abilities)})
            write_json(bundle_dir / "skill_lines.json", {"update": args.update, "skill_lines": skill_lines})
            write_json(bundle_dir / "mundus.json", {"update": args.update, "mundus": string_keys(mundus)})
            write_json(bundle_dir / "sets.json", {"update": args.update, "sets": string_keys(sets)})
            esohub_dates = []
            for map_name in ("skills_en.json", "sets_en.json", "scribing_en.json"):
                source = esohub.DATA_DIR / map_name
                (bundle_dir / "esohub").mkdir(exist_ok=True)
                shutil.copyfile(source, bundle_dir / "esohub" / map_name)
                made = json.loads(source.read_text(encoding="utf-8")).get("generated", "")
                esohub_dates.append(f"{map_name} generated {made[:10]}")

            import PIL
            files = {p.relative_to(bundle_dir).as_posix(): sha1_bytes(p.read_bytes())
                     for p in sorted(bundle_dir.rglob("*")) if p.is_file()}
            manifest = {
                "bundle_format": BUNDLE_FORMAT,
                "generator": generator_id(),
                "generated": generated.isoformat(timespec="seconds"),
                "update": args.update,
                "game": game,
                "sources": {
                    "icons": f"eso.mnf via EsoExtractData {extractor_version(extractor)}, "
                             f"PNG by Pillow {PIL.__version__}",
                    "abilities": "; ".join(sources.describe(n) for n in
                                           ("skill_tree", "player_skills", "mined_skills")),
                    "sets": f"LibSets_SetData.xlsm ({len(SET_ID_TO_NAME)} sets, via src/gear_set_data.py) + "
                            + sources.describe("set_summary"),
                    "esohub": "; ".join([sources.describe("esohub_sets"), sources.describe("esohub_mundus")]
                                        + esohub_dates),
                },
                "counts": {"icons": len(icons), "abilities": len(abilities), "skill_lines": len(skill_lines),
                           "mundus": len(mundus), "sets": len(sets)},
                "abilities_by_origin": origins,
                "icon_size": args.size,
                "missing_extra_stems": missing_extra,
                "missing_ability_icons": missing_referenced,
                "files": files,
                "licensing": LICENSING,
            }
            write_json(bundle_dir / "manifest.json", manifest)
            zip_path = out / f"{name}.zip"
            write_zip(bundle_dir, zip_path)
            log(f"bundle:     {zip_path}  ({zip_path.stat().st_size / 1_000_000:.1f} MB, {len(files) + 1} files, "
                f"{manifest['generator']})")

        passed = not failed
        if args.previous:
            if bundle_dir is None:
                log("--previous needs a bundle to compare; skipped in a dry run")
            else:
                log(f"compared with {args.previous}:")
                for line in compare_bundles(load_bundle(Path(args.previous)), load_bundle(bundle_dir)):
                    log(line)
        if args.check_fixtures:
            stems = {p.stem for p in (bundle_dir / "icons").glob("*.png")} if bundle_dir else in_client
            report, checks_ok = check_fixtures(Path(args.check_fixtures), abilities, skill_lines, stems,
                                               bundle_dir)
            log(f"fixture checks ({args.check_fixtures}):")
            for line in report:
                log(f"  {line}")
            passed = passed and checks_ok
        if args.check_log:
            log("log check:")
            lines, _ = check_log(Path(args.check_log), abilities, game["version"])
            for line in lines:
                log(line)
        return 0 if passed else 1
    finally:
        if args.keep_temp:
            log(f"temp kept at {temp}")
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
