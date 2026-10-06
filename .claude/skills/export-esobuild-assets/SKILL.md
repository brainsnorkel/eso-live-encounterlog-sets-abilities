---
name: export-esobuild-assets
description: Build and publish the game data bundle esobuild.com imports (ability icons at 64 px, and ability, skill line, mundus and set tables keyed by game ids) from the installed ESO client, UESP and ESO-Hub. Use after an ESO update or PTS cycle, when the esobuild.com site reports a missing icon or an "Unknown" skill line, or when asked to export, refresh or publish the esobuild assets.
license: MIT
compatibility: Windows only. Needs an installed ESO client, UESP's EsoExtractData v0.53+, Pillow (requirements-build.txt), network access and the gh CLI.
metadata:
  author: eso-log-tail
  version: "1.0"
---

Build the esobuild.com asset bundle from the installed game and publish it as a release asset.

esobuild.com (repository `brainsnorkel/eso-build-o-rama`) shows top builds with the game's ability icons and names each build by its class skill lines. ESO Logs gives it the game's ability id and icon file name for every slotted skill, so it imports a bundle built here by `scripts/export_esobuild_assets.py`: `icons/<stem>.png`, `abilities.json`, `skill_lines.json`, `mundus.json`, `sets.json`, copies of `data/esohub/*.json` and a `manifest.json`. The script's header describes each file and what counts as an ability. The request this was built to is `docs/handoff/uesp-game-asset-export-request.md` in the site's repository, with the fixture files the checks use beside it.

**Prerequisites** (check before running)

1. The same as for the `refresh-ability-icons` skill: a patched ESO client, `EsoExtractData.exe`, Pillow, and every path with a space quoted.
2. The update tag the site uses for the client's update (`u51`, `u52`, ...). It is passed with `--update` and never inferred; ask if it is not known. The script warns when it disagrees with the API version the client last ran with.
3. The site's fixture files, in a folder of their own outside the repository:

   ```cmd
   gh api repos/brainsnorkel/eso-build-o-rama/contents/docs/handoff --jq ".[].name"
   gh api repos/brainsnorkel/eso-build-o-rama/contents/docs/handoff/extra-icon-stems.txt -H "Accept: application/vnd.github.raw" > <fixtures>\extra-icon-stems.txt
   ```

   and the same for each `referenced-icons*.txt` and `referenced-abilities*.json`.

**Go lightly on UESP.** Abilities and sets come from UESP's ESO log export, a volunteer-run service that blocks heavy users. The script makes four requests per run, five seconds apart, keeps the replies in `build\esobuild-assets\sources\` and reuses them for a day, and stops without retrying when a request is refused. Do not add per-id lookups or loops around it, do not pass `--refetch` without a reason, and do not query UESP by hand to explore: a burst of ten quick requests drew an HTTP 403 on 2026-10-06. The stored replies are plain JSON; read those instead.

**Steps**

1. Refresh the ESO-Hub maps the bundle copies. If only their `generated` dates change, restore the committed files rather than committing the dates:

   ```cmd
   python scripts\generate_esohub_links.py
   ```

2. Dry run (about 15 seconds; extracts no icons, writes no bundle, fetches the sources once):

   ```cmd
   python scripts\export_esobuild_assets.py --update u51 --extra-stems <fixtures>\extra-icon-stems.txt --check-fixtures <fixtures> --check-log "%USERPROFILE%\OneDrive\Documents\Elder Scrolls Online\live\Logs\Encounter.log" --dry-run
   ```

   Read the summary:
   - `client:` the version from the game's build stamp (`depot\_databuild\databuild.stamp`) and the API version. If this is not the update you were asked for, the launcher has not finished patching: stop.
   - `tables:` abilities by origin. A count that falls sharply means a short or changed UESP reply.
   - `fixture checks:` V1 to V5 and R4 must read `ok`. Name differences under V2 are information: ESO Logs data from an older update carries old names, and a scribed skill is named after the player's focus script.
   - `log check:` names and icons the client itself logged, against the tables. Differences here mean UESP has not caught up with the update yet: wait and run again another day rather than publishing. `slotted ids missing from the table` lists a new bar swap (an ability the game slots in place of a skill under another name): add it to `BAR_SWAPS` in the script with the skill it stands in for.

3. Commit any script change first, so the manifest's `generator` names a commit that holds the script (it ends in `-dirty` otherwise). Then build (about 3 minutes), comparing with the last published bundle:

   ```cmd
   gh release list --limit 20
   gh release download <last esobuild-assets tag> --dir <scratch>
   python scripts\export_esobuild_assets.py --update u51 --extra-stems <fixtures>\extra-icon-stems.txt --check-fixtures <fixtures> --previous <scratch>\<last bundle>.zip
   ```

   `V6` must read `ok`. To show a build is repeatable (V7), run it twice and pass the first zip as `--previous`: the comparison must end `files that differ besides manifest.json: 0 (identical)`.

4. Publish. The app's update check reads this repository's latest release, so the bundle's release must never become the latest:

   ```cmd
   gh release create esobuild-assets-u51-<YYYYMMDD> build\esobuild-assets\esobuild-assets-u51-<YYYYMMDD>.zip --latest=false --target <commit> --title "esobuild.com assets: Update 51 (<client version>)" --notes-file <notes>
   gh api repos/brainsnorkel/eso-live-encounterlog-sets-abilities/releases/latest --jq .tag_name
   ```

   The second command must still print the newest `v*` tag. The notes carry the client version, the UESP fetch date, the counts and the check results as the script printed them, and anything the site's importer should know. The tag does not start with `v`, so it does not start the installer build.

**Notes**

- Nothing under `build\` is committed; the bundle exists only as the release asset.
- Icons outside the `ability_*` family are included when `--extra-stems` or an entry of `abilities.json` names them, so a skill that uses a `u50_*` or `achievement_*` icon is covered without the site asking.
- Set names in `sets.json` are the game's current ones from UESP. The LibSets workbook in `data/gear_sets/` spells some differently and is only the fallback for a set UESP lacks.
- ESO-Hub's mundus pages are `/en/mundus-stones/<slug>`, taken from its sitemap.
- ESO Logs numbers scribed skills with pseudo-ids from 1000 upward (1000 to 1022 in the first fixture); they are not game ids and resolve through `grimoire_icon_stems` in `skill_lines.json`.
