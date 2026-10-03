"""
Ability icons and ESO-Hub skill links: engine-side helpers (no Qt).

The encounter log names every ability's icon in its ABILITY_INFO line
("/esoui/art/icons/ability_arcanist_002_b.dds"). The app ships one PNG per
ability icon under data/icons/abilities (built by
scripts/extract_ability_icons.py from the installed game), so an icon is
resolved purely by that filename's stem; nothing is downloaded at runtime.

ESO-Hub page links come from data/esohub/ (built by
scripts/generate_esohub_links.py from ESO-Hub's sitemaps): a logged ability
name is slugified the way ESO-Hub slugs its pages and looked up in
skills_en.json; a LibSets set name is looked up as-is in sets_en.json.
Unknown names get no link.
"""

import json
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

ESOHUB_BASE = "https://eso-hub.com"


def bundle_root() -> Path:
    """Folder that holds data/: the PyInstaller bundle when frozen, else the repo."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def icons_dir() -> Path:
    return bundle_root() / "data" / "icons" / "abilities"


def esohub_data_dir() -> Path:
    return bundle_root() / "data" / "esohub"


def icon_stem(icon_path: str) -> str:
    """'/esoui/art/icons/Ability_Arcanist_002_b.dds' -> 'ability_arcanist_002_b'.

    Empty when the value is not a .dds path, so callers fall back to text.
    """
    if not icon_path:
        return ""
    name = icon_path.replace("\\", "/").rsplit("/", 1)[-1].strip().lower()
    if not name.endswith(".dds"):
        return ""
    return name[:-4]


def slugify(name: str) -> str:
    """ESO-Hub style slug: accents folded, apostrophes dropped, hyphen-separated."""
    folded = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    folded = folded.replace("\\", "").replace("'", "").lower()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")


@lru_cache(maxsize=1)
def _bundled_skill_links() -> Dict[str, str]:
    """slug -> ESO-Hub page path from the bundled map; {} when absent/invalid."""
    try:
        data = json.loads((esohub_data_dir() / "skills_en.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, dict):
        return {}
    return {str(k): str(v) for k, v in skills.items()}


def esohub_skill_url(ability_name: str,
                     links: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Full ESO-Hub skill page URL for a logged ability name, or None.

    *links* (slug -> path) overrides the bundled map; tests use it.
    """
    table = links if links is not None else _bundled_skill_links()
    path = table.get(slugify(ability_name))
    return f"{ESOHUB_BASE}{path}" if path else None


def _bundled_links(filename: str, key: str) -> Dict[str, str]:
    try:
        data = json.loads((esohub_data_dir() / filename).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    table = data.get(key) if isinstance(data, dict) else None
    if not isinstance(table, dict):
        return {}
    return {str(k): str(v) for k, v in table.items()}


@lru_cache(maxsize=1)
def _bundled_set_links() -> Dict[str, str]:
    """LibSets set name -> ESO-Hub page path; {} when the map is absent."""
    return _bundled_links("sets_en.json", "sets")


def esohub_set_url(set_name: str,
                   links: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Full ESO-Hub set page URL for a LibSets set name, or None."""
    table = links if links is not None else _bundled_set_links()
    path = table.get((set_name or "").strip())
    return f"{ESOHUB_BASE}{path}" if path else None
