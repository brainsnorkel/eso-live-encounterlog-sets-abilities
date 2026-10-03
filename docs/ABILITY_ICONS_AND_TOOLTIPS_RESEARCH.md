# Ability icons and ESO-Hub tooltips: research notes

*2026-10-03, branch `worktree-eso-hub-research`. Everything below was verified against the live site, the installed Update 49 client (`eso.mnf` dated 2026-09-29) and the current `Encounter.log`, unless marked otherwise.*

## Questions and short answers

| Question | Answer |
|---|---|
| Hover tooltips with ESO-Hub's skill descriptions and set bonuses? | Yes. ESO-Hub has an undocumented JSON tooltip API, the one its own WordPress plugin uses. Two endpoints cover skills and sets; one request header is required. |
| Click to open the exact ESO-Hub page? | Yes. Set pages are `/en/sets/<slug>`, skill pages `/en/skills/<category>/<line>/<slug>`. The sitemap lists every page, so slug maps can be generated at build time instead of guessed at runtime. |
| Icons for the ability bars? | From the game files, not the site. `scripts/extract_ability_icons.py` pulls all 1,794 `ability_*.dds` icons out of `depot\eso.mnf` in about 2.5 minutes and converts them to PNG; the skill `refresh-ability-icons` documents the routine. |
| Which abilities' icons are required? | None need identifying by hand. Every `ABILITY_INFO` line in the log names the ability's icon file, so the app resolves icons by filename. Shipping the whole `ability_*` family (about 7.8 MB at 40 px) covers everything; all 251 icons slotted on bars in the current log are in it. |

## 1. ESO-Hub: what the WordPress plugin actually is

The plugin (`eso-hub` v1.1.13, author Woeler / Pathfinder Media Group, GPL-3; source at `https://plugins.svn.wordpress.org/eso-hub/trunk/`) is a single PHP file that does two things:

- enqueues `https://eso-hub.com/css/external/tooltips.css` and `https://eso-hub.com/js/external/tooltips.js`;
- provides an `[esohub_skillbar]` shortcode that turns skill page links into `<img src="https://eso-hub.com/storage/skills/<category>/<line>/<slug>.png">`.

All the data work happens in `tooltips.js`: it watches `<a href>` elements pointing at eso-hub.com and, on hover, calls the JSON API below and renders the tooltip. The GitHub repo named in the plugin header no longer exists (404).

### 1.1 The tooltip API (read from tooltips.js, verified with curl)

| Endpoint | Returns |
|---|---|
| `GET https://eso-hub.com/api/armor-sets/tooltip/<set-slug>?lang=en` | `name`, `category`, `bonus_1` … `bonus_12` (HTML or `null`), `icon`, `icon_webp` |
| `GET https://eso-hub.com/api/skills/tooltip/<skill-slug>?lang=en` | `name`, `effect_1` (HTML), `effect_2` (morph "new effect", HTML or `null`), `header`, `passive` (bool), `icon`, `icon_webp` |
| also `collectibles`, `furniture`, `food-drinks`, `glyphs`, `champion-points/star`, `companions/skill`, `scribing/combination?combination=…` | not needed here |

Observed behaviour:

- The header `X-Requested-With: XMLHttpRequest` is mandatory; without it the API answers 401.
- Responses carry `Content-Type: application/json`, `Cache-Control: no-cache, private`, `access-control-allow-origin: *` (it is built to be called from third-party pages) and a Laravel session cookie (ignore it). No rate-limit headers; 12 sequential requests all returned 200 in about 0.4 s each.
- Lookups are by slug only. A numeric ability id returns 404 (`No query results for model [App\Models\Skill]`).
- `lang=de` with an English slug returns 404. German pages have German slugs (`/de/sets/adlerauge`), so a localized client needs a per-language slug map. The log's `BEGIN_LOG` line carries the client language and `BeginLogEntry.language` already parses it.
- Text fields are HTML fragments: `<span class="stamina">129 Weapon</span>`, `<span class="magic-damage">879 Magic Damage</span>`, `<a href="https://eso-hub.com/en/buffs-debuffs/minor-slayer"><span class="buff">Minor Slayer</span></a>`; paragraphs are separated by `\n\n`.
- Perfected trial sets, monster sets, mythics and passives all resolve (`perfected-arms-of-relequen`, `zaan`, `oakensoul-ring`, `medicinal-use`).
- Every tooltip the site renders ends with "Tooltips by ESO-Hub.com". Keep that line.

Samples (shortened): `deadly-strike` → category "PvP", `bonus_2` "Adds 129 Weapon and Spell Damage", `bonus_5` "Increase the damage your damage over time and channeled attacks do by 15%.", icon `gear_breton_medium_head_d.png`. `pragmatic-fatecarver` → `effect_1` "Channel a beam of energy in front of you for up to 4 seconds, dealing 879 Magic Damage every 0.3 seconds …", `effect_2` "Gain a damage shield while channeling …", `passive` false, icon `ability_arcanist_002_b.png`.

### 1.2 Page URLs for deep links

- Sets: `https://eso-hub.com/en/sets/<slug>`; 715 pages listed in `https://eso-hub.com/sitemaps/en/sitemap_en_ArmorSet.xml`.
- Skills: `https://eso-hub.com/en/skills/<category>/<line>/<slug>`; 1,182 pages in `sitemap_en_Skill.xml`. Categories: the seven classes, `weapon`, `armor`, `guild`, `world`, `alliance-war`, `racial`, `craft`, `pvp-artifacts`, each with `vengeance-*` variants of the lines.
- Renamed skills keep a redirect on the page (`.../ardent-flame/fiery-breath` → `.../draconic-power/dragonfire-breath`), but the tooltip API does not (404 for `fiery-breath`).

### 1.3 Mapping the app's data to slugs (measured)

**Sets.** Naive slugify (lowercase, drop apostrophes, other non-alphanumerics to `-`) maps 684 of the 722 bundled LibSets names onto an ESO-Hub set page. The 38 misses break down as:

- 12 "Perfect X" names in LibSets vs `perfected-x` on ESO-Hub (the Cloudrest and Blackrose Prison sets): a rule.
- 11 non-player entries: `Template_Drop_*` (8), two "(OLD)" sets, "Malacath's Band of Brutality X": ignore.
- 4 generated-data artefacts: `Spriggan\’s Vigor`, `Mara\’s Balm`, `Runecarver\’s Blaze`, `Siegemaster'\s Focus` (see section 5): fix the generator.
- 1 accent: "Coup De Grâce" → `coup-de-grace`: fold with `unicodedata`.
- 10 genuine spelling differences: alias table in Appendix A.

ESO-Hub also has 31 set pages the bundled LibSets workbook does not know (`harvesters-hope-ring`, `mylenne-moon-caller`, …): newer sets, which will keep showing as `Set#<id>` until the workbook is refreshed.

**Skills.** Names taken from the live log slugify straight to ESO-Hub's slug (27 of 30 sampled; the three misses were names that no longer exist in-game after the 2026 skill rework). Of 1,181 unique skill slugs exactly one is ambiguous, `executioner` (Nightblade passive vs the Two-Handed morph); the API returns the passive. Scribed skills ("Magical Banner", "Bloody Knife", …) are not skill pages: ESO-Hub models them as scribing combinations keyed by an id the log does not carry, so they get no tooltip and stay as text.

**Recommendation.** Do not slugify at runtime. Generate two JSON files at build time from the two sitemaps plus the rules and aliases above, and bundle them like `gear_set_data.py`:

- `data/esohub/sets_en.json`: LibSets set id → slug;
- `data/esohub/skills_en.json`: skill slug → page path.

At runtime the app slugifies the live ability name only to look it up in the map; unknown means no link and no tooltip. Regenerate whenever LibSets data is refreshed. Appendix B sketches the generator (it is the script that produced the numbers above).

## 2. Etiquette, terms and privacy

- The API is undocumented and exists for ESO-Hub's own tooltip plugin. Nothing on the site states terms for it: the static-page sitemap lists no terms or privacy page, and the plugin readme only says "This api is only used to retrieve data" and links `https://pathfindermediagroup.com/privacy`. `access-control-allow-origin: *` and the GPL plugin show they expect third parties to call it from web pages; a desktop app is a new context. Ask Woeler (ESO-Hub Discord, or Patreon `patreon.com/esohub`) before shipping, describe the volume (one request per hovered ability or set, cached), and keep the attribution line.
- Privacy: each lookup sends the user's IP (Cloudflare) and the hovered slug to eso-hub.com. Make it an explicit Settings toggle like the GitHub update check (`update.check_enabled`), default off or with a first-run notice, and mention it in the README.
- Fallback or alternative: UESP's documented exports are keyed by game ids. `https://esolog.uesp.net/exportJson.php?table=minedSkills&id=<abilityId>` returns name, description, texture and more for an ability id; `?table=setSummary` (838 KB, 714 sets) carries every set's bonus text with `gameId` equal to the LibSets set id (checked for 309 = Knight-errant's Mail). Licence CC-BY-SA 2.5; "excessive usage may result in site blacklisting and IP blocking". Single-id lookups work from a script, but list queries were answered with a Cloudflare challenge page, so treat it as a build-time source, not a runtime one. Descriptions contain `|cffffff…|r` colour codes to strip.

## 3. App integration design for tooltips and links

Engine side (no Qt):

1. `parse_ability_info` already parses `icon_path` and the passive and ultimate flags; keep them in the cache next to the name (`ability_cache` currently stores only id → name). Scribed skills append three extra quoted fields after the two flags (`…,F,T,"Magic Damage","Assassin's Misery","Berserk"`); field 4 is still the icon, so never read the icon from the end of the line.
2. `get_front_bar_abilities` returns names only. Add an id-preserving variant so each `FightHistoryEntry.players[*]` entry can carry `front_bar` and `back_bar` as `[{id, name, icon, passive}]` (or parallel lists) without breaking the string lists that `render_plain_text` and the tests use. Carry the LibSets set id in the `all_sets` tuples.
3. Slug lookup is a pure function over the bundled JSON maps: unit-testable and offline.

GUI side (verified offscreen with PySide6 6.11.2):

- `QTextBrowser` renders `<a href="…"><img src="…"></a>`; `anchorAt()` reports the link over the image, `highlighted(QUrl)` fires on hover and `anchorClicked(QUrl)` on click. `main_window.py` already sets `setOpenExternalLinks(False)`, so connect `anchorClicked` to `QDesktopServices.openUrl` for eso-hub URLs.
- Icons: `<img src="file:///…/data/icons/abilities/ability_x.png" width="22" height="22">`, or register them with `document().addResource`. In the frozen build locate the folder via `sys._MEIPASS` exactly as `esolog_gui.py` does for `icon.ico`, and add `data/icons/abilities` to `datas` in `esolog-tail.spec`.
- Tooltips: on `highlighted`, look the slug up in a memory cache; on a miss show "Loading…" with `QToolTip.showText` and fetch off the UI thread (stdlib `urllib` as in `update_check.py` on a `QThreadPool` task, or `QNetworkAccessManager`; `PySide6.QtNetwork` is bundled, it is not in the spec's excludes). When the reply arrives and the pointer is still on the same anchor, show the tooltip again. Persist the cache as JSON in the config directory with a TTL, keyed by the game version from `BEGIN_LOG` (`eso.live.x.y`), since patches change tooltip numbers quarterly.
- Convert the API HTML to Qt rich text: strip `<a>` (keep the inner text), map `class="stamina|magicka|health|buff|*-damage"` to theme-aware colours (`fight_render._THEMES`), turn `\n` into `<br>`, append `<small>Tooltips by ESO-Hub.com</small>`.
- Search: Ctrl+F searches document text, so icons replacing names would hide ability names from it. The prototype solves this in `FightView.anchor_matches`: image anchors whose ability name contains the query become extra matches (a cursor over the icon's object character), merged in document order with the text matches, so the count, highlight and Enter cycling all include icons. Qt tints a selected inline image with the selection background, so the amber highlight shows on the icon. "Copy fight" keeps names.
- Tests: `tests/unit/test_gui.py::test_render_functions` is the pattern for HTML assertions. Add offline fixtures with the two JSON samples above for the HTML conversion and the slug maps; never hit the network in tests.

## 4. Icons from the game files (verified pipeline)

Facts:

- The icons live in `depot\eso.mnf` (a 50 MB index over 258 `.dat` files, 117.7 GB), not in `game\client\game.mnf` (UI code and lang files only). The Oct 2025 export in `D:\extracted-eso` came from `eso.mnf` through the GUI build of the tool.
- `esoui\art\icons\` holds 34,598 files; 1,794 are `ability_*.dds` (64×64, block-compressed, 16.5 KB each, 30 MB in total). The 2026-09-29 client has 137 more ability icons than the Oct 2025 export, for example `ability_dragonknight_013_stonefist_b.dds` (Magma Fist).
- Pillow, already in `requirements-build.txt`, decodes all of them with zero failures. Measured PNG set sizes on the 1,657-icon old export: 64 px 16.2 MB (9.8 KB each), 40 px 7.2 MB (4.3 KB), 32 px 4.8 MB (2.9 KB); today's set is 8% larger.
- EsoExtractData v0.53 (`D:\extract-eso`): dumps the file table in about 5 s (`-k -m`). `-n` matches exact filenames only and reloads the MNF on every run (3 s each, so 1.5 hours for all icons). `-s`/`-e` extracts a range in seconds, but its counter is offset from the dumped `Index` column (2,337 on this client) and it names output files `<archive>\<Index>.dds`. The `-c` convert option described on the wiki does not exist in the command-line build ("Unknown command option '-c'"). `-a` would extract the 11 archives that hold the icons (7.4 GB).
- Live log (391 MB, NA, English): 925 `PLAYER_INFO` lines, 261 distinct slotted ability ids, 251 distinct icon files, all `ability_*` and all present in the new set. 834 distinct icons appear in `ABILITY_INFO` overall (NPC, boss and buff icons), which the bars never need.

`scripts/extract_ability_icons.py` (new) with the project skill `.claude/skills/refresh-ability-icons/SKILL.md`:

1. `-k -m` table dump, find the `\esoui\art\icons\ability_*.dds` rows, merge them into 36 `-s`/`-e` ranges (gaps of up to 10 MB of unrelated files are bridged: 940 extra files, 44 MB).
2. Two one-file probes calibrate the `-s`/`-e` offset and verify it is constant across the span.
3. Extract the ranges, map the numbered outputs back to names through the table, convert with Pillow into `data/icons/abilities/<basename>.png` (default 40 px, `--size 64` for native), write `manifest.json` (eso.mnf date, per-icon SHA-1) and print added, removed and changed icons against the previous run. `--check-log <Encounter.log>` verifies bar coverage; `--dry-run` previews the ranges.

Verified run on 2026-10-03: 1,794 icons in 2.3 minutes (5.7 s table dump, 114 s extraction, 14 s conversion); `--check-log` on the live log reported 0 missing. The output was written to a scratch folder, not committed: pick the size and location first (the 40 px set is about 7.8 MB).

Runtime lookup: `basename(icon_path)` lowercased without extension → `data/icons/abilities/<stem>.png`; fall back to the name when the file is missing (a new patch before the icons were refreshed).

## 5. Side findings

- `src/gear_set_data.py` contains invalid escape sequences (`"Siegemaster'\s Focus"`, `\’`), which raise `SyntaxWarning` on Python 3.12+ and will become a `SyntaxError`. `generate_gear_data.py` should emit names with `repr()` or `json.dumps` instead of manual quoting. The same artefacts break slug matching for those sets.
- `ESOSubclassAnalyzer.SKILL_LINE_ABILITIES` in `eso_sets.py` is stale after the 2026 class and skill rework: 39 of its 378 names no longer exist (Fiery Breath became Dragonfire Breath under Draconic Power, Blastbones became Blighted Blastbones, and so on), so skill-line detection silently misses them. ESO-Hub's `sitemap_en_Skill.xml`, or the generated slug map, is a cheap source of current names per line.
- The earlier command-line extraction attempt (`D:\extract-eso\exportmnf.log`) failed because the unquoted `C:\Users\Nebula PC\…` path split into two arguments and because `-c` is not a valid option; the GUI run then succeeded. The new script quotes paths and does not use `-c`.
- The bundled LibSets workbook lacks 31 sets that ESO-Hub knows; refresh `LibSets_SetData.xlsm` when convenient.

## Appendix A: set name aliases (LibSets name → ESO-Hub slug)

```python
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
# Rules applied before the alias lookup:
#   strip "\" artefacts and all apostrophes (' and ’); fold accents (NFKD);
#   "Perfect <name>" -> "perfected-<slug>"; skip Template_Drop_*, "(OLD)" and
#   "Malacath's Band of Brutality X".
```

## Appendix B: slug map generator sketch

```python
# scripts/generate_esohub_links.py (sketch; the research version lived in the scratchpad)
import re, json, unicodedata, urllib.request
from gear_set_data import SET_ID_TO_NAME

UA = {"User-Agent": "esolog-tail build script"}
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8")
def locs(xml):
    return re.findall(r"<loc>(.*?)</loc>", xml)
def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.replace("\\", "").replace("'", "").lower()
    s = re.sub(r"^perfect ", "perfected ", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

set_pages = {u.rsplit("/", 1)[1]: u for u in locs(fetch("https://eso-hub.com/sitemaps/en/sitemap_en_ArmorSet.xml"))
             if "/en/sets/" in u}
sets = {}
for set_id, name in SET_ID_TO_NAME.items():
    s = SET_SLUG_ALIASES.get(name) or slug(name)
    if s in set_pages:
        sets[set_id] = s
skills = {u.rsplit("/", 1)[1]: u.split("eso-hub.com", 1)[1]
          for u in locs(fetch("https://eso-hub.com/sitemaps/en/sitemap_en_Skill.xml"))
          if re.search(r"/en/skills/[^/]+/[^/]+/[^/]+$", u)}
json.dump(sets, open("data/esohub/sets_en.json", "w"), indent=1)
json.dump(skills, open("data/esohub/skills_en.json", "w"), indent=1)
```

## Appendix C: request recipe

```text
GET https://eso-hub.com/api/skills/tooltip/pragmatic-fatecarver?lang=en
X-Requested-With: XMLHttpRequest
Accept: application/json
User-Agent: esolog-tail/<version> (+https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities)

200 application/json
{"name":"Pragmatic Fatecarver","effect_1":"Channel a beam of energy ...","effect_2":"Gain a damage shield ...",
 "icon":"ability_arcanist_002_b.png","icon_webp":"ability_arcanist_002_b.webp","passive":false,"header":null}

GET https://eso-hub.com/api/armor-sets/tooltip/deadly-strike?lang=en   (same headers)
{"name":"Deadly Strike","category":"PvP","bonus_1":null,"bonus_2":"Adds <span class=\"stamina\">129 Weapon</span> and <span class=\"magicka\">Spell Damage</span>", ...,
 "bonus_5":"Increase the damage your damage over time and channeled attacks do by 15%.","icon":"gear_breton_medium_head_d.png"}

404 -> {"message":"No query results for model [App\\Models\\Skill]."}   (unknown slug, wrong lang)
401 -> missing X-Requested-With header
```
