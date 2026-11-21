"""
The bundle's check of its own data (issue #237). With
``ESOLOG_TAIL_SELF_CHECK=1`` in its environment the app reads every table it
bundles, prints a line for each and exits: 0 when every one loaded, 1
naming those that did not. CI runs it on every build.

Why it is needed. The app reads its tables (the ability icons, the ESO-Hub
links, the item, food, skill and set tables, the data's game version) from
data/ under ability_icons.bundle_root(): the bundle's own folder,
sys._MEIPASS, in a PyInstaller build, and the repository when run from
source. A loader that cannot read its file returns an empty table, so that
the app still starts and says nothing rather than something wrong, and a
lost table is silent. damage_kinds found the skill target table from its
own ``__file__``, which in a build is the folder above the bundled data
(dist/esolog-gui/data/ for dist/esolog-gui/_internal/data/), so no release
from 0.15.0, which brought the table, to 0.44.0 read it, and a player's
area skill counted as single target until a cast struck two units. The
tests read the repository's data/ and the start-up smoke tests see only
that the app stays up, so neither could notice.

How it works. The GUI entry (esolog_gui.main) reads the variable before
anything else, before the crash log, Qt or the config, and returns run()'s
status. run() reads each table through the function the app itself reads
it with, never a path of its own: a path rebuilt here would prove this
module's path, not the app's. It empties those functions' caches first, so
it reads the files as they are. It prints the folder it read from, one
line per table with what it found, and a verdict. A probe that raises is a
failure named with its error, and the entry prints any other error and
returns 1: a windowed build shows a raised exception in a dialog, which
would hold the CI step until its timeout. An environment variable rather
than an argument: the app takes none, and Qt reads its own from the
command line.

TABLES holds an entry for each JSON table the spec (esolog-tail.spec)
bundles and one for the folder of icons; a unit test fails when the spec
bundles a table that has none, so a table added later is checked too. CI
runs the check on the Windows and Linux bundles right after PyInstaller,
and in the smoke-macos job on the downloaded app on each macOS
(.github/workflows/build-installers.yml), each time from a folder outside
the checkout, so a path relative to the working directory, which would
find the checkout's data/, cannot pass. The module does not import Qt, so
the tests drive it with sys._MEIPASS pointed at a scratch folder.
"""

import sys

import ability_icons
import build_issues
import damage_kinds
import data_staleness
import eso_sets
import pen_crit
import player_build
import set_text

# The modules whose loaders TABLES calls; forget_loaded() empties their caches
MODULES = (ability_icons, build_issues, damage_kinds, data_staleness, eso_sets,
           pen_crit, player_build, set_text)


def _counted(table, unit: str) -> str:
    """'1,866 skills', or '' for an empty or missing table."""
    count = len(table or ())
    return f"{count:,} {unit}" if count else ""


def _target_kinds() -> str:
    """The skill target table, through the lookup area_rule makes: Impulse
    (28800) must read 'area', the lookup issue #237 found failing."""
    skills = damage_kinds._load_targets()
    if skills and damage_kinds.table_target("28800") != "area":
        raise ValueError("Impulse (28800) is not listed as an area skill")
    return _counted(skills, "skills, Impulse (28800) area")


def _data_version() -> str:
    """The game version the bundled data was stamped with."""
    version = data_staleness.bundle_version().get("game_version")
    return f"game version {version}" if version else ""


# (path under the bundle's folder, probe): a probe returns what the app's
# loader found, '' when it found nothing
TABLES = (
    ("data/icons/abilities", lambda: _counted(data_staleness.bundled_icon_stems(), "icons")),
    ("data/esohub/scribing_en.json", lambda: _counted(
        [*ability_icons._bundled_scribed_skill_links(), *ability_icons._bundled_script_links()],
        "scribed skill and script links")),
    ("data/esohub/sets_en.json", lambda: _counted(ability_icons._bundled_set_links(), "set links")),
    ("data/esohub/skills_en.json", lambda: _counted(ability_icons._bundled_skill_links(), "skill links")),
    ("data/items/armor_weights.json", lambda: _counted(player_build._bundled_armor_weights(),
                                                       "armor pieces")),
    ("data/items/poisons_en.json", lambda: _counted(player_build._bundled_poisons(), "poisons")),
    ("data/items/weapon_types.json", lambda: _counted(player_build._bundled_weapon_types(),
                                                      "weapons and shields")),
    ("data/buffs/food_drink.json", lambda: _counted(player_build.food_table(), "food and drink buffs")),
    ("data/skills/ability_targets.json", _target_kinds),
    ("data/skills/class_passives.json", lambda: _counted(eso_sets.class_passive_table(), "passives")),
    ("data/skills/weapon_skill_lines.json", lambda: _counted(build_issues._bundled_weapon_skills(),
                                                             "weapon skills")),
    ("data/sets/bonuses_en.json", lambda: _counted(set_text.bonus_table(), "sets' bonus texts")),
    ("data/sets/offense.json", lambda: _counted(pen_crit.set_offense_table(), "sets")),
    ("data/sets/set_buffs.json", lambda: _counted(set_text.buff_table(), "set buffs")),
    ("data/version.json", _data_version),
)


def forget_loaded() -> None:
    """Empty what the loaders have cached, every lru_cache in MODULES and
    damage_kinds' table, so that the next read is of the files as they are.
    The tests call it again after pointing sys._MEIPASS elsewhere."""
    for module in MODULES:
        for value in vars(module).values():
            clear = getattr(value, "cache_clear", None)
            if callable(clear):
                clear()
    damage_kinds.reset_target_table()


def check() -> list[tuple[str, bool, str]]:
    """(path, loaded, what was found or what went wrong) for each table."""
    forget_loaded()
    results = []
    for path, probe in TABLES:
        try:
            found = probe()
        except Exception as exc:  # noqa: BLE001 - a table that cannot be read is reported
            results.append((path, False, f"{type(exc).__name__}: {exc}"))
            continue
        results.append((path, bool(found), found or "not found, or empty"))
    return results


def run(out=None) -> int:
    """Check every table and print the report to *out* (stdout by default);
    0 when every table loaded, else 1."""
    results = check()
    build = "a frozen build" if getattr(sys, "frozen", False) else "run from source"
    print(f"Bundled data in {ability_icons.bundle_root()} ({build})", file=out)
    for path, loaded, found in results:
        print(f"{'ok' if loaded else 'FAILED':<7}{path}: {found}", file=out)
    failed = [path for path, loaded, _found in results if not loaded]
    if failed:
        print(f"{len(failed)} of {len(results)} bundled tables did not load: "
              + ", ".join(failed), file=out)
        return 1
    print(f"All {len(results)} bundled tables loaded", file=out)
    return 0
