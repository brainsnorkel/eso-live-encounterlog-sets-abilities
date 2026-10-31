# Changelog

All notable changes to the ESO Live Encounter Log Sets & Abilities Analyzer will be documented in this file.

## [0.28.1] - 2026-10-31

### Changed
- **Always Logging, or Easy Stalking, to keep encounter logging on** (#156): the README, the user guide, the home page and the "Waiting for Encounter.log" message now offer two addons, one or the other but not both: [Always Logging](https://github.com/brainsnorkel/AlwaysLogging), which logs everywhere and is installed from GitHub (it is not on ESOUI or in Minion), and Easy Stalking, which logs only the content you choose. Both are thanked under About

### Fixed
- **A log path with `&` or `<` in it shows as written in "Waiting for Encounter.log"** (#156), instead of being read as markup

## [0.28.0] - 2026-10-31

### Added
- For the maintainer (#134): `scripts/release.py` makes the release commit (the version, the changelog section gathered from `changelog.d/` fragments, the design notes rebuilt) and, once its pull request is merged, tags it, pushes the tag and checks the beta it publishes. Changes now add a fragment in `changelog.d/` instead of editing `CHANGELOG.md`, and a check on every pull request asks for one (or the `no-changelog` label). `docs/design.md` is rebuilt in the release commit only, and the release job refuses a tag whose design notes lag the code
- **Hover a fight's `ⓘ` in the fight list to see who has a possible build issue** (#147): each flagged player, with the class text from their row and the title of each finding, without selecting the fight. The rest of the row shows nothing on hover, as before. Names follow **Hide names**, and a screen reader hears the mark as how many players have a finding.
- **A `?` after a single Class Mastery** (#149): a character can take two, and the log often shows one late or never. `Templar: Devout Guardian, ?` on the fight pane; hover the `?` for the class's other masteries, the likeliest first for the player's role (counted over a month of trial logs, Bastion of Light last as the log never names it), or click it for the build. The build window's mastery line and the plain-text copy say the same in words

### Changed
- **The possible-build-issues `ⓘ` is easier to spot** (#140): on the fight pane it now sits right after the player's name, beside the `*` of the first damage, instead of after the class text, and it is drawn bold with a faint glow in the link colour. Rows keep their height. The fight list, the popup and the build window keep the plain `ⓘ`
- **The build window's Damage dealt section moves above Resources** (#143): under the gear grid the window now reads Damage dealt, Penetration and Critical damage as one block about what the player did with the build, with Resources, the tallest section, last. Each cap section's *Effective* line, the figure that counts, sits in a framed row with a bar at its left edge, and the Damage dealt and Resources headings get the rule the other headings have

### Fixed
- The *damage taken and healing received* link in the build window, and the death recap's link to the same window, open the fight that window shows (#143). They opened the fight selected in the list, which moves on to each new pull while the app follows the live log
- **Necromancers' Cycle Unending shows beside the class** (#149): its effect comes from the Necromancer's pets, which the app did not credit to them, so most Necromancers showed Nothing Wasted alone
- **A mastery found later in a session fills in that session's earlier fights** (#149), so the fights of one session show the same masteries

## [0.27.0] - 2026-10-31

### Added
- For the maintainer (#134): the release job refuses a tag that is not `vX.Y.Z`, does not match the tagged commit's version, or is not on `main`; `scripts/promote_release.py` makes a beta Stable (or pulls a bad Stable release back to a draft) and lists the betas that could be; a weekly workflow opens an issue when a beta that qualifies has waited more than two weeks

### Changed
- **Releases go to Beta first** (#134): every release is now published as a beta, which the Beta channel offers at once. A beta becomes the Stable release, which the Stable channel and the home page's download buttons offer, once it has been used in real fights for a while with nothing found. The home page names a newer beta in a smaller line under the buttons. Settings → Updates no longer says that both channels get every release
- The buff timeline's Armour row label drops the word "left": `Armour 18,200 · 6,456` (#137). Hovering the label says the second figure is the armour left, averaged over time

### Fixed
- **Four more Class Masteries show beside the class**: Conservation of Energy, Share the Spoils and Nocturnal Inspiration, which the log writes only as the Magicka, Stamina or Ultimate they give, and Devout Guardian, whose shield the log calls Hold the Line. Each was checked in 103 split logs of September and October 2026: every one of these lines came from a player of the mastery's own class. Bastion of Light is the one mastery the log never names

## [0.26.0] - 2026-10-30

### Added
- **Update channels** (#134): Settings → Updates has a *Channel*, **Stable** (the default) or **Beta**. Beta offers every release as soon as it is published; Stable offers a release once it has been used in real fights for a while with nothing found. Until releases are published to Beta first, which the release workflow takes up next, both channels offer the same release. On Beta the window title ends `· beta`, and About names the channel. Moving from Beta to Stable never offers a lower version: you keep the one you have until a Stable release is newer
- **Changes since your version** in the update's ⓘ popup: a link to every change between the version you run and the one on offer, however many releases lie between

### Changed
- The update check counts a release only when its tag is exactly `vX.Y.Z`, so a data release in the same list can never be read as an app version

## [0.25.0] - 2026-10-29

### Added
- **The fight list in blocks by instance** (#129): a bold header names the zone and its difficulty, `Sunspire · Veteran`, above the fights fought there one after another, and the fight lines leave the zone out. Neighbouring blocks alternate between a plain and a faintly shaded background (worked out from the theme's own colours). A new block starts in another zone or difficulty, or at the first fight after a completed run even in the same trial; walking back in after a wipe keeps the block
- **A trial's result** (#129): under the fight that completed a trial or an arena, a line gives the run's result as the game scored it, `✓ Sunspire vet · Vitality 35/36 · 253,117 · 22:31`: vitality left, score and the trial timer. The same line is a strip across the top of that fight's pane, and **Copy fight** adds it. Vitality is the game's own figure from the log's `END_TRIAL` line, out of 36 in a veteran trial; an arena's maximum is not known, so it shows the points alone. Checked against 146 completed runs from January to October 2026, among them the 35/36 Sunspire run of 21 October. The header and result lines cannot be selected, and the arrow, Home, End and page keys step over them
- **A companion's ultimate, casts and casts per minute** (#130): a companion's row ends `CPM 38 · Ult ×2` after its health when it cast its ultimate in the fight (Ember's Raging Storm, Mirri's Impeccable Shot, Isobel's Baneslayer, Zerith-var's Blade of the Crossing, Sharp-as-Night's Gore, Azandar's Vigorous Tentacular Eruption, Bastian's Unleashed Rage, Tanlorin's Ruinous Outburst), and the hover on its name gives each cast's time, `Raging Storm cast at 0:07 and 1:38 into the fight`. Its window shows how many times it cast each skill in the fight under the skill, its ultimate set apart at the end of the bar, and an **Other** row with its light attacks, bashes, blocks, dodges and Break Free, every cast and the casts per minute. **Copy fight** adds the CPM and the Ult mark. The ultimates are known by their ability ids, each checked against the companion that cast it in 214 logs; every ultimate-sized fall in a companion's ultimate pool in those logs was one of these casts
- **Healing to others** (#130): the hover on a player's or companion's name gives the healing they did to other players in the fight and its rate, `5,000 healing to others, 250 a second of the fight`, when there was some; the companion window gives it under its skills. It is the figure the role heuristic has always used: heals that landed on another player, not self-heals or overheal

### Fixed
- The user guide said a companion whose owner the log never named still counted in the group's damage; it counts nowhere

## [0.24.0] - 2026-10-28

### Changed
- **Shorter texts** (#127): the no-Minor-Slayer finding is one sentence ("No trial set at three pieces and no Oakensoul Ring, so no Minor Slayer: 5% more damage to dungeon, trial and arena monsters.") and no longer names Ossein Cage separately or lists the complete sets worn; the Resources note is two sentences. The Resources rows read **Gained over cap** and **Time at cap** instead of *Wasted at a full pool* and *Time at full*

## [0.23.0] - 2026-10-28

### Added
- **Resources in the build window** (#125): the magicka, stamina and ultimate a player spent and gained in the fight, each with its rate per second; how much of the spending went on casts and how much elsewhere (blocking, sprinting); logged gains against regeneration and unlogged gains; logged gains wasted at a full pool; the share of the fight spent on a full ultimate; and the five casts and five gains that counted most in each pool, with the group member who gave a gain (a healer's Bountiful Harvest, a Pillager's Profit). Every group member's pools are in the log, so it works for every player, not only the one who wrote the log
- **Text size** (#77): Settings → Display has a slider from 80% to 200% of the system's text, and Ctrl+=, Ctrl+- and Ctrl+0 step it from any of the app's windows. It is saved and applies to the whole app at once: the fight list, the fight pane and every window are redrawn at the new size, and the timeline strip's rows, label column and axis, the DPS graph's margins and legend, and the ability icons in every page grow with it (never shrinking below their size at 100%). Settings' helper lines and the rule editor follow it too, and Settings scrolls sideways if a line no longer fits the screen
- The bundled ability icons are the game's own 64 px rather than 40 px, so they stay sharp at a large text size or on a high-DPI screen; the icon folder grows from 15 MB to 25 MB
- **Colour-blind DPS graph** (#77): Settings → Display → *Colour-blind colours and line styles in the DPS graph*, off by default. The lines take Paul Tol's 'bright' colours, adjusted for each theme so every line stands 3:1 against the graph, and each player in turn is drawn solid, dashed, dotted or dash-dotted. The closest two colours measure 9.8 (light) and 13.1 (dark) in CIEDE2000 for normal vision and each kind of colour blindness simulated, where the default colours measure 5 and 2 for red-blindness
- **Screen readers** (#77): the fight pane and every window built like it (build, damage, damage taken, death recap) give a screen reader their text with each image read as words: an ability icon on a bar as the ability's name, the clickable glyphs as "DPS graph", "damage breakdown" and "damage taken", a hidden name as "hidden name" (Qt reads every image as an empty object otherwise). The timeline strip reads each row's label and whose effect it is, with "expected but not up" for a red row, and the DPS graph each drawn line with its dps at the end; the fight list, the search field and the fight pane are named
- The user guide has an **Accessibility** section (#77): the keys, text size, colour, colour blindness, screen readers and motion in one place, and what is not yet checked; the README lists it, and the guide's pictures are retaken with the new Display settings and colours
- **Reduce motion** (#77): Settings → Display; the ring on a taunt skill's icon stays still instead of pulsing

### Changed
- **Set names come from the game** (#79): the bundled set table takes every set's name from the installed client's own English text, committed as `data/client/set_names_en.json`, and only the set type from the LibSets workbook; the 26 hand-typed name corrections are gone. No name the app shows changes today. A set the workbook does not have yet appears under its name at once, read as a five-piece set until LibSets types it
- **`scripts/check_client_names.py`** compares every name the app bundles by id with the client after a patch: set names (the set table, the build issue rules' set lists, the penetration and critical table, the ESO-Hub link keys), class passives and mastery effects, weapon skills, the taunt, pull and Elemental Drain id lists, and poison names. It prints each name that differs and exits 1 when one does; ids the game no longer names (the old rank II to IV ids UESP keeps, 488 of them) are counted, not failed. On the Update 51 client every bundled name matches
- **Detail view is Ctrl+D, and Tab moves the focus** (#77): Tab used to toggle Detail view, so a keyboard user could not leave the fight list; Tab and Shift+Tab now move between the fight list, the search field and the fight pane, and Ctrl+D toggles Detail view from any of them, the search field included. The toolbar button's hover names the key, and the user guide lists the keys under **Keyboard**
- **Clearer colours on the light theme** (#77): the timeline strip's bars were the same pale tints in both themes and measured 1.3:1 (Major Courage) to 2.8:1 against the light window; each is now a darker shade of its hue there, 3:1 or more, and follows a live theme switch. Text under 4.5:1 is darkened a step: the link blue, the veteran and stale orange, the Trash, Legendary and Mythic gear qualities, the death recap's health colours, and Settings' grey and orange helper lines (now the theme's own muted and warning colours, in the dark theme too). A unit test pins every text colour at 4.5:1 and every bar at 3:1 against both themes

### Fixed
- **Every mythic shows on the fight pane's set row**: the row decided what was a mythic from a hand-kept list of 20 names, two of which were not set names ("Kilt" for Harpooner's Wading Kilt, "Antiquarian's Eye"), so 19 of the game's 36 mythics never showed there, among them Belharza's Band, Rourken Steamguards, Ring of the Wild Hunt and Prowler's Talisman. It now asks the set's type, as the build window already did
- The build window's Front, Back, Werewolf and Other labels no longer break a letter per line when the window is narrow or the text large

## [0.22.0] - 2026-10-28

From the speed, memory and disk review (#105).

### Added
- **Reviews run on a thread of their own** (#107): live fights keep arriving while a log opened for review loads (a live fight showed 4 s into a review that had made it wait 41 s before). **Cancel review** beside the progress bar stops it. A log over 1 GB is looked through first (a few seconds per GB) and the app offers the whole log or its last few sessions, with the time each takes: a 4.7 GB month-long log reads in about 8 minutes, its last three sessions in about one. The cut is always at a session's start, which gives exactly the fights the whole log gives; starting mid-session was measured and gave different fights
- **Lasting warnings** (#111): a red note in the status bar, kept until the problem clears, when split files cannot be written (a full disk, a removed drive) or reading the log fails poll after poll. Both were a passing status line or a diagnostic print before
- The startup replay of the current session shows its progress on the progress bar

### Changed
- **Replays are 37% faster** (#108): each log line is split once instead of three times, and event types are looked up in tables. Startup, a Settings save and a review all replay; a 390 MB trial log went from 40 to 25 seconds
- **Fight history takes 27% less memory** (#110): damage series, effect spans and repeated gear are held compactly (a trial night's history 63 → 46 MB), with every figure the same
- **Split files are written once per batch** (#109), not once per line: 72 thousand disk writes instead of 3.3 million for a 573 MB session, and the startup replay with splitting on is about a sixth quicker. A crash loses at most one second of lines, which the next start restores from the game's log
- The current session is replayed in full at startup however large it is (#107). A session over 768 MB used to get only its roster read, which could leave its early fights with the wrong companion and pet rows

### Fixed
- **Champion points** follow the log: a player seen earlier in the same log file kept the champion points first seen, and a point earned mid-session never showed (158 of 2,856 player rows in 19 split logs now show the newer figure)

## [0.21.1] - 2026-10-28

### Changed
- Healing reads **healing received** where it read "healing landed" (#102): the fight pane's shield hover, the damage taken window's header, its **Received** column under Healing received and its no-healing line, the death recap's healing star hover, and the user guide

## [0.21.0] - 2026-10-28

### Added
- **Damage taken window** (#98): a shield after every player's name on the fight pane opens the whole fight's damage taken and healing received for that player, died or not; the death recap keeps the last seconds before each death and now links to the new window from its **Damage taken this fight** block, as the build window does from its Damage dealt heading. The window leads with the figures: damage taken and the rate per second of the fight (pull to end, so two pulls compare), healing landed with the share of all healing that was overheal, what shields absorbed as a share of the damage that reached health, how many of the direct hits were blocked, and the hits dodged or missed. Then the recap's kinds bars (direct against DoT, area against single target, Martial against Magical, with the Warfare star hovers), **Damage by source** (every unit that hurt the player, bosses first, adds of one name as one row with their count, the unnamed unit for fall damage and set procs, each unit's abilities under it with damage, share, hits, largest hit, average and kind) and **Healing received** (every healer by what landed, the player's own heals marked `own`, a pet's named after its owner and marked `pet`, each healer's abilities under them, the overheal as a share per row rather than an amount, since 91 to 96% of all healing on a player is overheal in trials). Measured on three veteran trial logs (48 boss fights): a tank takes damage from a median 11 abilities and 8 units, a DPS from 7 and 6; six to eight units heal each player; bosses do 44% of the damage, adds the rest
- The engine's per-fight tally of damage taken now keeps every ability (the recap's fight block still lists its top five), the largest hit per ability, the same damage by the unit that did it, the healing by the unit that healed, and a count of every result line; nothing already shown changes (replayed on 106 fights, every existing figure identical)

### Fixed
- A fall damage row in the death recap's fight block read `fall · fall`; it reads `fall`

## [0.20.0] - 2026-10-27

### Added
- **Cast counts in the build window, and CPM on the fight pane** (#94): the fight's casts of each slotted skill in small print under its icon on the front, back and werewolf bars, and an **Other** row with light and heavy attacks, bashes, swaps, dodges, synergies, potions and Break Free, then every cast and the casts per minute; the fight pane shows `CPM 105` after `H · M · S` on each player's row, and in the plain copy. A cast is one cast track id per caster begun inside the fight, matched to a slot by id, by name or by family (Destruction Staff elements, the two Fatecarver slot ids); Fatecarver writes no `BEGIN_CAST`, so its channel effect gained on the caster counts as the cast. Checked against Combat Metrics on a Tideborn Taleria pull: every skill count equal, light attacks 66 against 67
- **The death recap window is a setting** (#95): Settings → Death recaps, 5 to 10 seconds in steps of one, 5 by default. Saving replays the session, so the fights already listed are rebuilt with the new window; each recap names the window it was recorded with

### Changed
- **The death recap window leads with the deaths** (#95): each death's table of the last 5 seconds of damage and healing now sits right under its "Killed by" line, with that death's kinds-of-damage summary under the table, and the whole fight's **Damage taken this fight** block (bars, lines and top abilities) closes the window instead of opening it. Damage over time is written `DoT` and healing over time `HoT` beside the bars, in the heal share, in the ability kind words and in the star hover text, as the Result column already wrote them; the build window's Damage dealt bars say the same

## [0.19.0] - 2026-10-27

### Fixed
- **A session split again is continued, not copied** (#85): a session's split file meets its own name when the session is split a second time (the attach replay at startup, a Settings save, which rebuilds the monitor, or a restart mid-session), and until now the two were compared by whole-file hash, which could never match (the temp file holds the lines up to the first `BEGIN_COMBAT`, the file the whole session), so the session was written out again under the next `-N`. In the maintainer's split folder 513 of 899 files were byte-identical copies, 512 of them written by the pre-GUI tool's `--read-all-then-tail` between January and April 2026, which re-split the whole log at every start, and the last by two instances of the app on one live session. Now the file on disk is the same session when it begins with the temp file's lines (an older split lacking the lines its parser rejected still matches), the temp file goes, and the existing file is continued: the lines still to come are skipped until they have passed the file's end, then appended, so a split cut short by a restart or a crash is completed (a partial last line trimmed first) and a complete one gains nothing. Only a file whose head is another session's gets the suffix. The check at the session's end compares the finished file with the folder as it is then, byte for byte, instead of a size index built at startup, which the two-instance case slipped past; a continued file is never taken for a copy
- **Two instances of the app on one split folder**: the splitter now takes a lock file in the folder (`.esolog-tail-split.lock`, holding its process id), and a second instance that finds it held by a live process writes no splits and says so in the status bar; a lock left by a crashed instance is taken over
- **Every line of a session reaches its split**: lines the parser rejects (an `END_CAST` with a cancel reason, an `OBJECT` unit) were left out, so every split was a few hundred bytes to 57 KB short of its session; they are written now
- **`scripts/dedupe_splits.py`** moves the copies already on disk to the Recycle Bin: files of one session stamp with the same size and the same bytes (whole-file SHA-256), the lowest suffix kept; a dry run lists them, `--recycle` moves them, nothing is deleted outright

## [0.18.0] - 2026-10-27

### Added
- **Zip split logs older than N weeks** (#86): a setting under Per-encounter split files, off by default (4 weeks when turned on). Shortly after startup and once a day, each old split is zipped beside itself as `<name>.log.zip`, at about a sixteenth of its size (a 573 MB Dreadsail Reef split became 35 MB). Settings shows how many splits it would zip before you save; the status bar reports each run. Age counts from the later of the session date in the name and the file's last change. The newest session's split, a `keep` folder inside the split folder, and every file that is not one of the app's splits (`Encounter.log` and its archives included) are never touched. The splitter treats a zipped split as the session's split, so it is not written out again
- **Open log for review opens zips**: a zipped split or an `Encounter-*.zip` archive is read as it stands, never unpacked to disk; a zip holding several logs asks which
- **Move split logs to the Recycle Bin when older than M weeks** (#87): off by default (52 weeks when turned on), more than N while zipping is on. Settings previews how many would go and the dates they span; saving a change that would move any asks first, listing the sessions by zone and size, every file under Show Details. On Windows a split the Recycle Bin cannot take (network or removable drive, bin set to delete at once, larger than the bin's limit) is left and reported, never deleted outright: the app checks the drive's bin settings and asks the shell to warn rather than delete, where send2trash's Windows backends delete such a file without a word. On Linux and macOS it uses send2trash, a new dependency there

### Changed
- **The Settings dialog scrolls** above fixed Save and Cancel buttons and opens no taller than the screen: it had grown taller than a 1080p screen, and Qt squeezed its wrapped help labels until lines were cut off or overlapped

### Fixed
- **Players who leave, come back, or come back on another character** (#78): a member who left stayed on the group list at 0 DPS in every later fight of the zone, a member who dropped and came back got a second row, and a member back on another character had no row in the fight they came back to while their damage was in the group total. Now a player who leaves during a fight keeps their row in it, greyed, with `left · here for 62% of the fight`, and is off the list from the next pull; the same character back in the zone stays one row, its DPS over the whole span, the time away included (as Combat Metrics counts it); another character is a new row, listed with its class and `build not in the log yet` until its next pull when the log says it is grouped with the logging player, and the old character counts as having left; an anonymous member named on joining the group takes the name; a companion follows its owner through all of it. The `Offline` placeholder the log writes while a member loads in is ignored throughout, and a monster given a departed player's unit id is no longer counted as them. Replayed over the 386 unique sessions in the maintainer's split logs, see the PR for which fights changed
- **The Warfare star links** (#73): the labels beside the kinds-of-damage bars linked to `eso-hub.com/en/champion-points/warfare/<star>`, which does not exist; ESO-Hub keeps every star at `/champion-points/star/<star>` whatever its constellation, as its star sitemap lists them, and the 19 links now go there

## [0.17.0] - 2026-10-27

### Added
- **A solo dungeon run's Misfortunes in the fight pane** (#70): in March of Sacrifices and Moon Hunter Keep solo, a line under the fight header names the Misfortunes the run was started with, `Misfortunes: Warm Welcome · Revoke of Respite · Alleviating Assault`, or reads `Misfortunes: none`; hovering a name gives the game's own description of what it does, and **Copy fight** adds the same line. They are read from the logging player's long-term effects at each pull. All five Misfortunes seen in the maintainer's logs are known: the three Moon Hunter Keep ones and, from the 2026-10-25 March of Sacrifices run (which did pick some), Weary Submission and Pulled Punches; any other solo dungeon debuff is shown by its logged name. Other zones have no such line

### Changed
- **Crux is a commented-out example** (#80): the default tracked-effect rules end with `# Crux = 184220 on self stacks`, for an Arcanist to switch on by taking the `#` off. A saved rules text that still has the Crux line as it shipped has it commented out on upgrade; a Crux line of your own is kept

## [0.16.0] - 2026-10-27

### Added
- **Companions have a row of their own** (#74): a companion that is out during a fight is listed straight under its owner, marked `↳`, with `C` for its role, its level, its own DPS, share and health, a `☠` when it died (not counted in the fight's Deaths), and in Detail view a bar of the companion skills it was seen casting this session (the log writes no companion bar or gear). Its DPS opens the damage window; its name opens a short window with its level, owner and skills. A companion that dies and is summoned again stays one row. **The owner's DPS no longer includes the companion's** by default, matching Combat Metrics, which never counts a companion as the player's; in the two solo Moon Hunter Keep runs of 2026-10-26 Isobel's share was 1 to 9%. A new box under Companions in Settings, *Count a companion's damage and healing as its owner's too*, brings the old figures back beside the companion's row (the shares then add up to more than 100%). Effect rules, expected group sizes and the penetration figures still treat a companion as a pet. The companion's window ends with the `Damage dealt` section a player's build window has (#73), over the companion's own hits

## [0.15.0] - 2026-10-27

### Added
- **The kinds of damage, in the death recap and the build window** (#73): the recap window now opens with `Damage taken this fight`, everything that reached the player's health over the fight summed by the splits the Warfare champion point stars act on, and sums each death's last five seconds the same way, above its event table: three two-colour bars, direct against over time, area against single target, Martial (physical, bleed, poison, disease) against Magical (magic, fire, frost, shock), with the amounts and percentages on either side, then the damage types behind them (`fire 64% · physical 19% · frost 17%`), Oblivion, fall and drowning damage named apart, what got through while blocking, what shields absorbed, hits avoided, the healing that landed against the overheal (direct and over time apart), and the killing blow's overkill; the fight block lists the five abilities that hurt most with their kinds and source. Each row of the event table adds its damage type (`Hit · fire`) and `area · hit 8 players` for an area hit. The build window gains a `Damage dealt` section before Penetration with the same bars over the player's damage in the fight. A side's label links to its star's ESO-Hub page (Ironclad, Enduring Resolve, Unassailable, Duelist's Rebuff, Hardy, Elemental Aegis and Preparation for damage taken; Master-at-Arms, Thaumaturge, Biting Aura, Deadly Aim, Mighty, War Mage for damage dealt; Focused Mending, Swift Renewal, Blessed, Quick Recovery, Enlivening Overflow for healing) and names every such star with the game's text on hover; the app never says which stars a player has, since the log does not carry them. Area or single target is not in the log and is read from the cast: over 87 of the maintainer's split logs (11.6 million combat lines, 6,831 player deaths) every hostile hit carried a cast id, the mechanics that kill groups (Maelstrom, Grievous Pulse, Oppressive Bolts) struck up to 12 players on one cast id and the attacks that pick one player never shared one, so a hit whose cast struck two or more units is area, an ability that did so earlier in the zone session reads as area on a lone hit, and for a player's own skills UESP's target kinds (`data/skills/ability_targets.json`, generated from the table the esobuild export caches, no new request) decide when the casts say nothing; UESP calls Oppressive Bolts "Enemy", which is why the table is never asked about a monster. Damage reaching players in those logs was 89% direct and 11% ticks, 885M Magical to 411M Martial to 44M Oblivion; shields absorbed 726M; heals landed 1.17B against 12.4B overheal; monsters never crit players. Melee against ranged is not shown (the log has no range), nor what a block or a resistance saved. Fights recorded by an older version say `Damage kinds were not recorded for this fight`
- **Hide names, for screenshots and sharing** (#72): a `Hide names` button on the toolbar, Ctrl+H, and a box under Privacy in Settings, one switch, saved whenever it flips. With it on, every player but the one writing the log has their handle and character name hidden wherever the app shows a name: the fight pane's rows and `Also died` chips, the hover texts, the build, damage and death-recap windows (title, header, the casters in the penetration section, the source of a heal), the DPS graph's legend, the timeline strip's hover and click pop-up, and the copied fight. In the pages drawn as rich text a hidden name is a pixelated word of the same length with its `@` left readable; where text is all there is it reads `@▒▒▒▒▒▒`. The pixelated word is a stand-in, not the real name blurred: pixelated or blurred text can be read back when the font and size are known, so nothing of the name goes into the picture but its length. Who is kept comes from the log's own `isLocalPlayer` flag (all 899 split logs on the maintainer's machine carry exactly one), so a reviewed log a friend wrote keeps the friend. Enemy, pet, set and ability names are never hidden. `scripts/capture_screenshots.py --hide-names` takes the guide's pictures that way, and they have been retaken
- **The character name beside the handle** (#71): the build window's title line reads `@handle · Character` (the character name was a muted fact on the line below) and its window title `Build – @handle (Character)`; hovering a handle in the fight pane shows the character name under it

## [0.14.5] - 2026-10-27

### Added
- **Armour row: what the group is hitting, second by second** (#66): the buff timeline's `Armour` row no longer goes blank where the group was not on its boss. The paler stretches read each second on whichever hostile the group hit hardest that second, the armour left on it after the group's armour debuffs, so Xoryn's seven-minute gauntlet, a dragon's flight spent on adds and the trash before a boss now show what armour the damage was meeting; the hover names the unit of the moment and says the reading is per second, and the click summary gives the pack's figures (average, lowest, share with no debuff, and the damage-weighted remainder) beside the boss's. In a fight without a boss that reading is the whole row in place of the one mob it followed, and the label's average is its own. The debuff rows and the build window's penetration figures still weigh the bosses alone; a clean boss fight gains a few paler seconds that read lower than the boss (the adds carry fewer debuffs for less time). Over the four Lucent Citadel and three Sunspire logs of #64 a Xoryn pull reads 3,200 to 6,200 left with 7 to 15% of the damaged seconds undebuffed over 130 to 210 changes of unit, and a trash fight 2,700 to 10,400 left where the one-mob row read 10,317 to 16,800. A solo dungeon's trash is drawn on its boss's 27,300 scale rather than changing the bar's scale mid-row, and the hover says its armour is 18,200. Ties go to a boss, then to the unit read the second before, so a pack of equals does not flicker
- **Survey script for the boss flag** (#67): `scripts/survey_boss_flag.py` scans a folder of encounter logs and lists every boss-flagged unit by zone with its health as a share of its fight's largest, so a new trial's Prism-like unit can be found and added to the list below

### Fixed
- **Defense Prisms, Baron Rize and Sea Adders are adds, not bosses** (#67): the game flags the five Defense Prisms and Baron Rize of Xoryn's gauntlet, and the Sea Adders of Yandir the Butcher's fight, as bosses on their `UNIT_ADDED` lines, so everything that read "boss" took them in. On a Xoryn pull the boss dps time ran from the first hit on a Prism to the end (a median 531 s of a 561 s fight over 23 pulls) and the group's boss dps divided his damage, the Baron's and the Prisms' by nearly the whole gauntlet; each player's boss share counted Prism and Baron damage; the boss-scoped rules (the taunt, Off-Balance, the Brittles, Alkosh, Z'en) were measured on every Prism, the taunt averaged over seven units; and the penetration figures weighed the Prisms' seconds. A bundled list of monster ids (`boss_units.py`) now takes the flag off those units where it is read, so every reading agrees: replayed over four Lucent Citadel and two Kyne's Aegis logs, a Xoryn pull's boss dps time is now his own 112 to 159 s instead of 561 to 623, the group's boss dps 440,000 to 625,000 instead of 188,000 to 212,000, the taunt on him 94 to 96% instead of 18 to 51%, and Yandir's boss damage drops the adders' 10%; nothing else in those logs, nor in Sunspire, Dreadsail Reef, Falkreath Hold or Moon Hunter Keep, changed. A survey over all 899 split logs on the maintainer's machine found no other flagged unit under a tenth of its fight's largest: after the Prisms (4%) and the adders (8%) the next is Baron Rize at 20%, then Spindleclutch's chain-pulled bosses at 23% and Cloudrest's Shade of Z'Maja at 40%, bosses in their own right. The Baron is on the list because the boss dps time runs from the first hit on any boss to the last (Combat Metrics' definition): with him a boss a Xoryn pull's would still have been a median 446 s. A wipe in the gauntlet before Xoryn is therefore a fight without a boss, still named after the Baron when he took the most damage; Combat Metrics counts these units as bosses, so its boss figures and this app's differ on Xoryn and Yandir pulls, by design

## [0.14.4] - 2026-10-26

### Fixed
- **Moon Hunter Keep solo** (#55): the solo Moon Hunter Keep (zone 1593, logged on 2026-10-26) is now known as a solo dungeon, so its trash reads at 18,200, Jailer Melitus and the other bosses at 27,300, and every penetration figure against them follows; until now the run read as overland, 9,100. The log also settled the open question on the Misfortunes: the three picked at the door are written as effects on the player for the whole run (Warm Welcome, Revoke of Respite, Alleviating Assault), every enemy spawns with a `Misfortune Level Three` buff, and Alleviating Assault's heal (5,100 on trash, 8,160 on a boss, at most every 3 seconds) is logged as a heal from the player to the enemy. None of them changes armour, so the figures stand under any Misfortune; the boss's logged health, 2,157,795, is the guide's figure for three Misfortunes, which is why the guide's armour figures are trusted

## [0.14.3] - 2026-10-26

### Changed
- **Updates: a toolbar button, checked every 15 minutes, no pop-up** (#56): the app now checks GitHub a few seconds after it starts and every 15 minutes after that (`update.check_interval_min` in the config file), so a release published during a raid night is noticed before the next one; until now the one check ran at startup and the offer was a modal box that took the focus from whatever was being typed. When a newer release exists an `Update to 0.15.0` button appears at the right end of the toolbar with an `ⓘ` beside it, and the window title ends with `0.15.0 available`; nothing is downloaded until the button is clicked. On Windows one click downloads the installer (progress in the status bar) and hands over to it; on Linux the button, `Get 0.15.0`, opens the release page. The `ⓘ` shows GitHub's release notes, links to the release page and the changelog, and `Don't show this version again`, the old Skip. The three dialogs (`Update available`, `Install update?`, `Could not start the installer`) are gone; a failure puts the button back with the reason in the status bar. Each repeat check is conditional (the ETag sent back as `If-None-Match`; an unchanged release is a `304` with no body, which GitHub does not count against its limit of 60 unsigned requests an hour), a rate-limit reply makes the app wait for the reset it names, and the check and the download now run on their own thread rather than the engine's, where a wedged network stalled fight updates for the 10-second timeout. The Settings box reads `Check GitHub for a newer release at startup and every 15 minutes, and show an Update button in the toolbar`; saving with it off stops the checks and hides the button

## [0.14.2] - 2026-10-26

### Changed
- **Armour row over the time the target was fought** (#64): the buff timeline's `Armour` row is now drawn and measured over the seconds the group was hitting its target, not the whole fight, so a boss reached late no longer stands as a full bar until then. Xoryn's combat starts at the Defense Prisms and runs through Baron Rize and the gauntlet: over 33 Lucent Citadel logs he was added a median 7 minutes into a median 9-minute fight, and the row read `14,500` to `16,000 left` with "77% without a debuff" where over his own two to three minutes it is `2,565` to `5,978 left` and 0 to 1%. Nothing is drawn before the first hit, after the last, or through a gap of more than five seconds between hits (a dragon in the air), and hovering the blank says why; the label's average, the lowest point and the no-debuff share are over the drawn time; the click summary names the window when it is not the whole fight and adds the remainder weighed by the damage dealt, the build window's reading, which differs from the time average by a factor of two to seven even on a clean boss fight. A boss that returns as a new unit (Nahviintaas at each landing) keeps one row, and among a trash pack's equal-damage mobs the row follows the one fought longest rather than the last to spawn. Fights recorded before this change are drawn as they were, and the boss debuff rows above the Armour row are still measured over the whole fight

## [0.14.1] - 2026-10-26

### Added
- **Build issues: no Minor Slayer in a veteran trial group** (#62): a damage dealer pulling in a veteran group of five or more with no Minor Slayer source gets the `ⓘ`. Minor Slayer is 5% more damage to dungeon, trial and arena monsters; every trial's sets grant it at three pieces, so do Ossein Cage's, and Oakensoul Ring grants it outright, so the rule looks for one of those 38 sets at three pieces on either bar, or the ring, in the gear logged at combat start, and the finding names the complete sets worn instead (`The complete sets here, Deadly Strike and Tide-Born Wildstalker, give other things`). Healers, tanks and a player who has taunted this session are not judged, nor a normal run, a group of four, or a build the log wrote with no gear. Over the 84 newest trial split logs (May to October 2026, 1,581 fights) 7% of the veteran damage-dealer player-fights and 29 of 225 characters lacked a source, against 46% in normal runs, which is why normal runs are left alone; the ring's buff is not in the log's effect list, which is why the rule reads gear

## [0.14.0] - 2026-10-26

### Added
- **The boss's armour on the buff timeline** (#55): a last row, `Armour`, draws the target's estimated armour less the group's armour debuffs on it, second by second, by height like Touch of Z'en's row: full while nothing is on the boss, dropping as Major and Minor Breach, Crusher, Roar of Alkosh and the rest land, so what is left is what each player's own penetration has to cover. The label gives the estimate and the armour left averaged over the fight (`Armour 27,300 · 15,900 left`); hovering the bar gives the figure at that moment and the debuffs behind it, hovering the label where the estimate comes from, and a click the average, the lowest point and the share of the fight with no armour debuff at all. The row follows the penetration cap in Settings when it is set to a number, and is drawn on the target the group damaged most (the mobs of a trash fight at 18,200)
- **Solo dungeons** (#55): a solo dungeon is known by its zone id (the log gives it the group dungeon's name and no difficulty, which read as overland, 9,100, until now), and its armour follows the guides: trash 18,200 like any instance, every boss 27,300 (the final boss has 36,400, which the labels say), and the game's 25,000 cap on an enemy's armour drawn as a dashed line on the row, since armour above it changes nothing until the debuffs bring it under. Every penetration figure in a solo dungeon, the row token and the build window's sections included, now reads against these. March of Sacrifices (zone 1592) is known from the 2026-10-25 log; Moon Hunter Keep's id is added once a solo run is logged
- **Build issues: Huntsman's Warmask that never fires** (#47): a wearer of the mythic whose Mark of Hircine never appeared in any fight of a minute or more this session gets the `ⓘ`, the way Roar of Alkosh and Roaring Opportunist wearers do; the mark is placed by a bash or a fully charged heavy attack, and one placed anywhere in the session clears it. The issue asked for the opposite, a flag on a wearer who bashes, since a bash can move the mark from the boss to an add; the survey over 91 split logs of September and October 2026 found 29 of 30 wearers bashing in 96% of their fights of a minute or more, and the mark on a unit other than a boss in a third of boss fights, half of those units being adds a group kills on purpose (Sunspire's Eternal Servants, Kyne's Aegis's Lieutenant Njordal), so such a flag would have sat on every wearer and been wrong a third of the time. No wearer in those logs went a session without a mark; the rule is for the one who does. No row highlight
- **Build issues: no food or drink** (#54): a player with no food or drink buff as the fight began gets the `ⓘ`, with the rule stated: the long-term effects the log lists for them are matched against the app's table of the game's 92 food and drink effects, the one the build window's Food line uses, so a consumable newer than the table reads the same way (the finding says so). A meal eaten during the fight is noted with its time, and a food that was up at the pull and faded before the end, with nothing eaten after it, gets its own finding naming it and the time; a drink the game logs as several effects is out only when all of them have faded. Over 91 split logs of September and October 2026 (1,681 fights, 14,895 player-fights) 535 player-fights (3.6%) pulled without, 39 named characters among them, and 13 saw their food run out mid-fight; no player without a match carried anything that looked like an unknown consumable, so the gap was a missing meal every time
- **Home page** (#58): a one-page site at https://xop.co/eso-live-encounterlog-sets-abilities/, published by GitHub Pages from `site/`: the icon and the tagline, download buttons for the current release (installer, portable zip, Linux tarball), the user guide link, the main-window screenshot, nine feature cards with their screenshots, the three get-started steps, the credits, and a "Fork me on GitHub" ribbon. The page has no JavaScript and loads nothing from outside the site. Its Open Graph and Twitter card tags name a 1280×640 social card (`site/social-card.png`, drawn by `scripts/build_social_card.py` from the icon and the main-window screenshot) so a pasted link unfurls with a picture; the same file is the repository's social preview. `scripts/build_site.py` fills the version and the three asset links from the latest release and copies the screenshots the page uses, and `.github/workflows/pages.yml` publishes the result after every change to the page and after every release

### Changed
- **Dependency floors**: `PySide6-Essentials` 6.12.0 or newer, the first release past Qt's October 2026 security advisories, which affect every release from 6.9.0 to 6.11.2; and `Pillow` 13.0.0 or newer, since 12.3.0, the old floor, is among the 41 advisories that 13.0.0 closed, one of them critical. Neither changes what a build installs: the 0.12.0 builds already resolved to both

## [0.13.3] - 2026-10-25

### Added
- **Elemental Catalyst tracked** (#53): a default rule `Elemental Catalyst = 142610 142652 142653 on boss`, the share of the fight any of the set's three weaknesses (Flame, Frost, Shock: critical damage taken up 5% each) was on the boss, shown when someone applied it like the other boss debuffs, and in the Examples list. The set is an alternative to Lucent Echoes for a group's critical damage. In all 891 split logs of 2026 it appears in two Kyne's Aegis sessions, both also running Lucent Echoes, with a DPS wearer in one (22 of 24 fights, median uptime 53%) and a tank in the other (one fight, 78%); all three weaknesses were up together for 7% and 51% of those fights, so the row usually shows one weakness, not the full 15%. A saved rules text is not given the line; tick it in Examples

### Changed
- **Tracked effects** (#48): Powerful Assault is no longer expected in a large group. The set's buff is usual in a trial, but nobody has to bring it, so a fight without it is not a mistake worth a red `0%` row; its row now appears only when someone had it, like the boss debuffs. The other five group buffs and the taunt are expected as before. A saved rules text has the `expected large` that 0.12.0 put on its Powerful Assault line taken off again when the app starts; a line you gave other sizes (`expected all`, say) or renamed is left as written. The Examples list offers the line without the words
### Fixed
- **Werewolf bar** (#49): the game sometimes writes a werewolf bar in place of a player's human bars, and the Rockgrove log of 2026-10-24 showed that bar can be stale: one bar written as both human bars, three werewolf skills beside Razor Caltrops and Inner Fire, for a player in form the whole log who cast Hircine's Rage and Ferocious Roar in every fight and never those two. The app took the logged bar for the werewolf bar, drew it as both human bars and left the Werewolf line empty. A logged bar holding three or more werewolf skills is now dropped before anything reads it, the build-issue rules included, and the Werewolf line is rebuilt from the player's casts for every werewolf alike. Over the September and October split logs this changes three players: that one, and two anonymous players on client 12.0 whose werewolf bar was logged as the front bar and no longer shows twice.

## [0.13.2] - 2026-10-24

### Changed
- **Buff timeline** (#45): a group buff that reached only one or two people is drawn as an unbroken, cross-hatched span rather than a dotted line. The dots read like a buff flickering at half uptime, which is a different problem (how long it lasted) from the one the row flags (whom it reached). The hatch is the effect's colour over the row's full height, so the span still reads as up, and spans that overlap or meet are drawn as one. The row's click summary says `Hatched` where it said `Dotted`

## [0.13.1] - 2026-10-24

### Changed
- **Buff timeline**: a tracked rule that is expected in a group of this size but never came reads `0%` with its label in dark red and bold, so a missing buff or debuff is seen at a glance; the dark theme uses a lighter red. The hover text still says why the row is there.

## [0.13.0] - 2026-10-24

### Added
- **Effective penetration and crit damage on every player's row** (#37): after the damage shares, `p:18199 cd:121%` gives the player's effective penetration and critical damage over the fight, computed as the build window's sections compute them (each second capped, the Settings' assumed Champion Point rows included), in both views and in the copied text. Hovering it gives the caps, the shares of them and the share of damage dealt over each; clicking it opens the build window at the two sections. A player who dealt no damage has no token
- **The Trial dummy's own debuffs are credited** (#37): the "Target Iron Atronach, Trial" puts Major and Minor Breach, Crusher, Roar of Alkosh, Minor Brittle and Elemental Catalyst on itself when it spawns and keeps them, so a log session that starts after the spawn has no line for them. The penetration and crit figures now credit them by the dummy's name for the whole fight, as Combat Metrics reads them from the game at the pull, and a fight against it counts as instanced (18,200). Checked against a Combat Metrics report of a 25 s parse: own penetration 3,126 and the dummy's 17,030 give its maximum of 20,156 exactly, and the effective figures agree (18,200 and 124.9% against its 18,200 and 124.4%). The same check showed the summoned bear's ultimate reads `Guardian's Savagery` (or `Guardian's Wrath`) on a bar, which the skill-line table did not know, so Advanced Species counted one Animal Companions ability too few; both names are now in the table
- **Penetration and critical damage in the build window** (#37): two sections under the gear grid list where a player's Offensive Penetration and Critical Damage come from and how they stand against the caps (18,200 in dungeons, trials and arenas, 9,100 overland; 125%, 155% with Above and Beyond), the way LunaCairu's PenCrit Calc sheet and the Hyperioxes calculators do with checkboxes. The player's own rows come from the log: the passives on their build (Concentration per light piece, Dexterity per medium piece, Hemorrhage, Piercing Spear, Fated Fortune, Advanced Species and Splintered Secrets per slotted ability, Dismember, Feline Ambush, Hunter's Eye, Twin Blade and Blunt and Heavy Weapons per axe or mace, Blessing at the Peak, Above and Beyond, valued by the game's own texts and by rank), the mundus stone with its Divines pieces, each set at its worn piece count from a new bundled table of UESP's set texts (`data/sets/offense.json`, `scripts/generate_set_offense.py`), and Sharpened weapons; a two-bar value reads `front / back`, a conditional bonus `up to`. The group's rows are the debuffs on the boss (Major and Minor Breach, Crusher valued from the caster's glyph, Roar of Alkosh, Crimson Oath's Rive, Runic Sunder, Crystal Weapon, Tremorscale; Minor and Major Brittle, Elemental Catalyst's weaknesses) with uptime and who applied them with what set or glyph, and the buffs on the player (Major and Minor Force, Lucent Echoes, Fated Fortune's proc), valued as Combat Metrics values them. The totals give the player's own figure, the sum with every debuff at full uptime, and the effective figure: each second's effects added to the player's own, capped, and weighed by the damage dealt that second, as Combat Metrics weighs each hit, with the share of damage dealt over the cap. Champion Point stars that only change a stat never appear in the log (four trial logs, 2,292 builds), so Settings chooses which to assume: Piercing, and Fighting Finesse in solo and small-group fights (never in a group of five or more), on by default, Backstabber and Force of Nature (valued from the status effects measured on the boss) off; they show as assumed rows and apply without a restart. The target counts as a trial boss when the zone is normal or veteran or a trial dummy's own debuffs are seen
- **The dps figures look like links** (#34): the header's group DPS, which opens the dps over time graph, and each player's DPS, which opens their damage window, looked like plain text until hovered, and the damage window had no other way in. The group figure now ends in a small line of the graph's own kind in the link colour, and each player's figure in three small bars in the muted colour, inside the link, so hovering or clicking the mark works as on the figure. Names are unchanged. The marks are drawn by the app, follow the pane's font size and stay crisp on a scaled display; copied text is unchanged
- **Possible build issues** (#16): a `ⓘ` after a player's class on the fight pane, only when the app found something in the build they pulled with; hover it for the list, click it for each finding with the rule behind it, set and skill names linking to ESO-Hub, and the build window repeats the list under its header. Eight rules, decided on 2026-10-24 and checked against 83 split logs of September and October 2026 (1,615 fights, 13,998 player-fights, 393 characters), which 17% of the characters seen would get a note from: Nirnhoned on an off-hand weapon (Dual Wield Expert counts 6% of an off-hand weapon's damage; 17 characters); the same glyph on both weapons of a bar, whatever the glyph (measured on those logs, identical glyphs share one cooldown: the same glyph from one player never fired twice within 4 seconds whether a bar carried it once or twice; 22 characters); two or more heavy armor pieces on a damage dealer who has not taunted this session (one piece is the Undaunted Mettle norm; 9 characters); a weapon skill on a bar holding another weapon, the back bar under Oakensoul Ring excepted (14 characters, Stampede on a staff back bar the commonest); Elemental Drain slotted, the finding stating both morphs (5 characters); Roar of Alkosh or Roaring Opportunist worn at five pieces and never firing, judged per logging session over fights of a minute or more and cleared by one fire (3 and 8 characters); Pearlescent Ward, Xoryn's Masterpiece or Lucent Echoes complete on one bar only (3 characters, two of them tanks at four of five on the front bar); and a tank with no taunt or pull on either bar and no taunt logged this session, a tank being a player whose largest pool is health, who holds a shield, an ice staff or five heavy pieces, who dealt under half an equal share of the group's damage and who is not a healer by staff or healing (real tanks in those logs dealt a median tenth of an equal share; 3 characters). The weapon skill lines come from a new bundled table of UESP's player skills (`data/skills/weapon_skill_lines.json`, 605 ids). Replaying 9 split logs (181 fights, 1,594 player-fights) through the old and the new engine changed nothing but the new key.

### Changed
- **The fight list's marks**: a fight in which a player died is marked `☠` in place of `(d)`, and a fight with a player whose build has a possible issue is marked `ⓘ` after it; the copied text carries neither, as before.

## [0.12.0] - 2026-10-24

### Added
- **Expected effects** (#13): a tracked-effect rule shows when its effect was up, or, with `expected solo | small | large | all`, at `0%` in those group sizes when it was not (one player, two to four, five or more; `expected` alone is all). A rule neither seen nor expected has no row on the strip and no item in the copied text. The defaults expect the six group buffs in a large group and the taunt in small and large groups; the boss debuffs and Crux show when they happened. Replaying 16 split logs (241 fights, every tenth log by name) through the old and new engine: a fight now shows 1.0 item solo, 4.0 in a small group and 9.7 in a trial, of which 1.5 are expected buffs reading 0%; every item left off had read 0, was not seen and was not expected, and nothing else on the line changed. A strip row that is expected but empty says so when clicked
- **Touch of Z'en stacks** (#27): the game logs 126597 with a stack count of 1 every time (3,577 lines in four trial logs), so the default rule read `1.0/1`. A new measure, `dots`, counts the wearer's damage-over-time effects on the boss while their Z'en is on it, at most five, the way Combat Metrics does (LibCombat's UpdateZenData); an effect counts when the log shows it ticking as damage over time. The default rule uses it: the 8 fights of that sample with Z'en now read from 0.9/3 to 4.9/5, mostly over 4, with the same uptime as before. Each wearer's Z'en is measured on its own
- **A saved rules text is upgraded once** (tracking version 3): the seven default group-buff and taunt lines get their `expected` words, by name, and a `Touch of Z'en = 126597 … stacks` line becomes `dots`. A line renamed or already flagged, and every other line, stays as written
- **Who applied a buff and who had it** (#19): a click on any row of the buff timeline strip, label or bar, opens a summary of the whole fight: each caster's uptime, how much of it no other caster covered, and their spans; each receiver's uptime, and for a stacking rule its peak and the time at the peak; and a grid of caster against receiver when there are only a few of each. It closes on a click elsewhere or Esc. Tracked-effect rules now record who applied each span; replaying 110 fights from 6 split logs gives the same uptimes as before
- **The werewolf bar** (#17): since Update 50 a werewolf fights with a bar of its own, which the game never writes into the log, so the fight view, build window and plain copy showed only human bars the player did not use. A player who spent part of a fight in werewolf form now gets a third line, `Werewolf`, with the bar rebuilt from the werewolf skills they cast this session, in the skill line's order and with their morph as the ultimate, and the share of the fight spent in form, `in form 100%`. Feral Carnage and the other Carnage casts count as their Pounce's slot; Feeding Frenzy, the Roar synergy, does not count. Measured on 55 split logs of July to October 2026: of 58 player sessions with werewolf casts, 55 cast exactly five bar skills and none ever cast a sixth, and the session's casts up to a fight's end give the whole bar in 94% of fights. Werewolf players spent 1,234 of their 1,524 fights wholly in form
- **Damage window** (#21): click a player's DPS figure for their damage in that fight, broken down the way Combat Metrics breaks it down: one row per ability (a pet's marked `(pet)`), largest first, with damage, share, hits, crit %, largest and average hit and DPS; a table of the targets hit with the damage and span on each; and a *Boss targets only* switch in a fight with a boss. Hovering the figure shows the dps time it divides by and what the figures would read over the whole fight
- **Shares beside both figures** (#21): the % column reads `boss % / total %` like the DPS column reads `boss / total`: the player's share of the group's damage to the bosses, then of all its damage. In the copied text too
- **DPS over time graph** (#21): click the group DPS in the fight header, or **DPS graph** on the toolbar, for the group's and each player's dps across the fight, drawn as Combat Metrics' graph tab draws them: the average over a window of 1, 5 (the default), 10 or 30 seconds, or the running figure (the live dps as it stood at each second). The group has the upper panel and the players the lower, each on its own scale, sharing the time axis. A legend of checkboxes picks the lines, the first eight players on to begin with and a player past the eighth dashed in a reused colour; hovering gives every line's value at that second; a *Boss targets only* switch narrows the lines to the bosses
- **Combat Metrics credited**: About and the README's Credits name Combat Metrics by Solinur and its LibCombat library as the reference the dps figures follow, with links to the addon and its source

### Changed
- **The buff timeline strip is always on** (#25): it is now the only view of the tracked effects in the fight pane, and its Settings checkbox is gone. The text uptime line under the fight header is dropped, since each row's label already carries the rule's text, mob counts and stack figures included; **Copy fight** keeps the line, as text is all a paste can carry. A fight in which none of the strip's built-in buffs was up (a solo fight, say) still draws its tracked rows. An old config's `experimental.buff_timeline` key, on or off, is ignored and left out on the next Save
- **Buffs above, debuffs below** (#26): the strip's rows on your side (`group`, `self`, `pets`) come first and the rows on the enemy (`boss`, `enemies`, `mobs`) after, with a thin line between; each side keeps its order, built-in rows first, then the rules as written in Settings
- **Documentation by reader** (#22): the README covers installing and turning on logging; the user guide holds every screen and setting, the tracked-effect rules, what the numbers are based on and troubleshooting; the development guide holds building, refreshing game data and the esobuild.com export. Corrected along the way: DoT ticks have counted in DPS since 0.10.0, a fresh install tracks six boss debuffs and Crux (not seven boss debuffs), the full default Off-Balance line, and the timeline's hover text does not show ability ids
- **DPS divides by dps time, as in Combat Metrics** (#21): every DPS figure divides by the span of the hits it sums, first hit to last and a second at least, not by the fight time: a player's by the span of their own hits, their boss DPS by the span of their hits on the bosses, the group's by the span of the group's. The fight time stays on the history line and in the header, which adds the group's dps time when the two read differently: `1:40 (dps time 1:32)`. Measured on 113 of the maintainer's split logs (1,941 fights with damage, 564 with a boss), the group's figure rises by a median 1.0% in boss fights of a minute or more (p90 5.9%), a player's own by a median 5.8% (p90 41%) and their boss DPS by a median 9.7% (p90 75%); a lone hit now reads as its own value per second. Combat Metrics' own group DPS divides by the logging player's dps time, which differs from the group's by a median 8.5%; the group's own span is used here. What the engine never counted stays uncounted, all of it negligible: hits on units the log never added (0.07% of damage), on non-hostile units (0.00%), in the two seconds before BEGIN_COMBAT (0.04%) and in the 1.3 s after END_COMBAT (0.02%)

### Fixed
- **Rampage in place of the werewolf ultimate** (#17): at full Fury the game lists Rampage (Enduring Rampage for Pack Leader) in the logging player's ultimate slot, so that slot changed from fight to fight and showed as text. It now shows the morph, Werewolf Berserker or Pack Leader, and its hover says it was listed as Rampage. Group members' slots never read Rampage, so every player now looks alike
- **Werewolf icons**: Update 50 gave Pounce, Brutal Pounce, Feral Pounce, Rending Claws and Claw Fury icons named `u50_ability_*`, and Rampage uses an achievement icon; none was bundled, so those skills showed as text. The icon extractor now also takes every update-named skill icon (`u<NN>_ability_*`, 66 icons including Crypt Transfer's) and Rampage's, 67 icons in all
- **The engine worker is freed when the window closes** (#18): the window asked the UI thread to take over the worker after the engine thread had ended, which Qt refuses ("Cannot move to target thread", printed at every close), so the worker was never deleted and was left to Python's garbage collector, on whichever thread happened to be allocating. The worker now moves itself to the UI thread as its thread finishes, takes no more requests, and is deleted there. The test suite also frees each test's windows on the UI thread before the next test (about 40 main windows used to stay alive to the end), and runs as one process again on CI

## [0.11.0] - 2026-10-15

### Added
- **Class Mastery passives beside the class** (#15): a pure-class build's masteries follow its class in the player row, `NB: An Eye for Exploitation, Above and Beyond`, on the build window's mundus and food line, and in the plain copy. A mastery is known from the player's passive list when its effect is always on, and otherwise from the effect it fires with the player as its source (kept for the rest of the session once seen), including the five that fire under their buff's name: a Dragonknight's Lead from the Front gives the group Major Berserk, a Warden's Tundra's Maw puts Major Brittle on enemies and Bountiful Harvest gives Major Heroism, a Nightblade's Cutthroat's Focus marks its attacker. Across 73 split logs of September and October 2026 that names a mastery for 90% of pure-class player rows; a twelve-player Sunspire run shows all twelve by its last fight. Five masteries fire nothing the log names (Share the Spoils, Nocturnal Inspiration, Conservation of Energy, Bastion of Light, Devout Guardian) and are not shown

### Changed
- **Players ranked by boss damage first**: the rows of a fight with a boss are ordered by damage dealt to the bosses, then by all damage; a fight without a boss keeps the order by all damage
- **Skill lines come from the passives, and only the borrowed ones show** (#14): the class skill lines are read off the class passives in each player's PLAYER_INFO list (a bundled table of 203 passive ids from UESP's player skill table, `scripts/generate_class_passives.py`) instead of being guessed from the slotted abilities, which fill in only for a line whose passives a character has not learned. The fight view and build window show just the lines a build borrows from another class, each after a plus sign, `NB +Herald`, `Arcanist +Assassination +Dawn`, so a stock build shows only its class. Measured on 7,019 distinct builds in those logs: the passives name all three lines for 98.5% and never contradict the old guess, which had missed a line in 56%; of the 489 subclassed builds, 133 show differently, 18 of them a line borrowed purely for its passives that the old guess could not see

## [0.10.0] - 2026-10-12

### Added
- **Boss DPS beside total DPS**: in a fight with a boss, each player's row and the fight header read `boss / total`, for example `34.3k / 39.5k`: the damage dealt to the units the game flags as bosses, then all damage dealt. A fight without a boss keeps the single total. The game's flag is reliable in dungeons and trials (both Z'Maja and her Shade, both Lucent Citadel twins); the Infinite Archive's arc bosses carry no flag, so those fights show the total alone

### Fixed
- **DPS counted only direct hits**: damage-over-time ticks, what got through a block and what an enemy's damage shield absorbed were never summed, so every DPS figure the app showed was low. Measured on 29 of the maintainer's split logs (990 dungeon and arena fights, 34 trial fights), the ticks were 26% of all damage dealt, and the top player's DPS in a boss fight of a minute or more was understated by a median 35% in dungeons and 52% in trials, up to 79%. The six results Combat Metrics sums now count; hits the target was immune to, reflects and overkill still do not. The figures now agree with Combat Metrics and ESO Logs in what they count

## [0.9.2] - 2026-10-12

### Added
- **The window remembers where it was**: its position, size, maximized state and the split between the fight list and the detail pane are saved when the app closes and restored on the next start. A window last seen on a monitor that is no longer attached is brought back onto a visible screen. Stored under `window` in the config file

## [0.9.1] - 2026-10-10

### Changed
- **The timeline strip no longer says "experimental"**: the word painted in the strip's top-right corner is gone. The strip and its setting are otherwise unchanged

## [0.9.0] - 2026-10-09

### Added
- **Boss debuffs in trash packs**: a rule `on boss` has nothing to measure in a fight without a boss, so it measures every hostile the group fought instead, and both it and a rule `on enemies` then say how many of the pack's mobs the effect reached: `Alkosh:45% on 7 of 12 mobs`, `Touch of Z'en:2.1/5 on 6 of 12 mobs`. The pack is the mobs the group hit plus any a tracked effect landed on, and the timeline row says `mobs` beside such a rule. In a boss fight nothing changes. Fights without a boss are most fights: 281 of 376 in twelve trial and dungeon logs of 2026, with up to 71 mobs hit, where Off-Balance reached up to 27 of 32 mobs with 7 at once, Major Vulnerability 7 of 18, Minor Brittle 18 of 32 and the taunt 20 of 32
- **`each`**, a third measurement beside `uptime` and `stacks`: the effect on every unit of the scope separately, over the time that unit was alive in the fight, averaged. `Taunt = 38254 on boss each` is the taunt's measure (#9), each boss to its death and the mean over the bosses; `Courage each = 109966 on group each` is the mean of the players' own Major Courage uptimes, an example in the picker

### Changed
- **The whole uptime line is rules**, so every item can be removed: the six group buffs and the taunt, tracked in code until now, are the first seven lines of the default rules, named in full (`Major Courage:87%` where the line read `MCourage:87%`), and **Examples…** offers them again to anyone who deleted one. A rules text saved by 0.8.0 is given the seven lines in front of it once, so nothing disappears on upgrade, and a rule already written under one of those names stays as it was. Two things follow from the buffs being rules: they are measured whatever the group size (the line needed three players before, so duo and solo fights now see them), and a buff that never appeared reads `0%` rather than being left off the line. The numbers agree: replaying twelve logs of 2026 through both, the six buffs read the same in 690 of 745 readings, and in the other 55 (46 of them Major Courage, the buff refreshed most) the rule reads higher, never lower, because the old code ignored an UPDATED refresh when it had missed the GAINED before it, though the buff was up (a 12 s fight that read 7% reads 100%). The taunt reads the same in 52 of 79 boss fights and higher in 27 of them (lower in one, by 5 points), for two reasons the rule gets right: a taunt already on the boss at the pull, which the old code dropped at BEGIN_COMBAT until the tank's next refresh (twelve fights, one 7.7 s fight read 0% and reads 100%), and a boss or add that arrived after the pull or was gone before the end, now measured over the time it was there rather than the whole fight

- **Settings no longer calls the buff timeline experimental**: its checkbox sits under the tracked-effect rules it draws, in the one Tracked effects group, and says what the strip does. The setting itself is unchanged
- **Timeline labels that do not fit**: a row label wider than its column (`Off-Balance:11% on 2 of 11 mobs`) is cut with an ellipsis instead of losing its start, and hovering any row's label shows it whole with whose effect it is; a built-in row's hover gives the effect's full name

### Fixed
- **An effect left on a corpse ran into every later fight of the zone**: the game does not always write FADED for an effect on a unit that dies or is removed, and a tracked rule kept such a span open, so Hemorrhaging or Off-Balance left on a mob that died counted as up for the rest of the zone (in 124 of the 376 fights a span was still open on a dead or removed unit when the fight ended). A unit's death or removal now ends its spans, and a zone change ends the spans on hostiles and pets

## [0.8.0] - 2026-10-09

### Changed
- **Death recap button is just the skull**: the red chip on a dead player's row reads `☠`, or `☠ ×3` for three deaths, instead of `☠ Death recap ×3`, which wrapped onto a second line next to a long class line. Hover and click are as before

### Added
- **Tracked effects** (#10): Settings → Tracked effects takes rules of your own, one per line, `Name = ability ids on self | group | pets | boss | enemies`, with `stacks` for an effect that stacks, and each rule adds an item to the uptime line of every fight, in the fight pane and in copied text, whatever the group size: `Off-Balance:17%` for the share of the fight the boss was off balance under any of the rule's ids, `Crux:2.1/3` for the mean and peak count held. The rules are plain text to share by copy and paste, and a tracker exported from the HyperTools addon can be pasted as a line as it is. A fresh install starts with seven rules (Off-Balance, The Morag Tong, Minor and Major Brittle and Roar of Alkosh on the boss, Touch of Z'en stacks on the boss, Crux stacks on yourself), the box says how many rules it holds and which lines it skips, and **Examples…** opens a list of sixteen example rules with what each tells you, to tick and add under your own or to copy for sharing. When the experimental timeline strip is on, each rule is a row of it, a stacking effect's bar rising with the count, and every row of the strip now says whose effect it is beside its label: `group` for the group buffs, `boss` for Major Vulnerability and the taunt, and a rule's own scope. Checked on nine trial and dungeon logs of 2026: Off-Balance on a trial boss reads 4 to 28% per fight, Crux 1 to 3 on the Arcanist

## [0.7.1] - 2026-10-09

### Changed
- **Taunt marks stand out** (#12): the ring on an ability a player taunted with is wider (an eighth of the icon), has a dark hairline outside it so it shows on any icon art and a light one inside, and pulses: it brightens and fades about once a second, in the fight pane and the build window. The name of a taunting ability that has no icon is bold as well as purple. The pulse redraws only the ringed icons, so the page does not move or reflow

### Added
- **User guide**: `docs/user-guide.md` walks through every screen with pictures the app draws itself: `scripts/capture_screenshots.py` renders the app offscreen over a log file, under a scratch config, and writes the pictures the guide and the README show, so they stay in step with the app. Linked from the README

### Technical
- **Design notes kept in the code**: the explanation of each hard problem (the encounter log's unit states and effect lines, fights the game cuts in two, roles, class skill lines and subclassing, ability icons and ESO-Hub links, scribed skills, builds and weapon types, set names, group buff uptimes, taunts, pets, death recaps, the timeline, the GUI and the engine thread) now lives in the docstring or a `# Design:` comment of the code that solves it, and `scripts/build_design_doc.py` collects them into `docs/design.md`, linked from the README and the development guide. Docstrings that only named their function were written out for the effect handler, group buff tracking, pets, taunts, skill line inference and the gear data generator
- **Repository tidy**: the five merged worktrees and their branches are removed

## [0.7.0] - 2026-10-09

### Added
- **Weapon types in the build window** (#8): the gear grid's Weight column is now Type, and a weapon row says what the weapon is, as the game names it: Inferno Staff, Ice Staff, Lightning Staff, Restoration Staff, Greatsword, Battle Axe, Maul, Axe, Mace, Sword, Dagger, Bow or Shield. Armor rows show their weight there as before. The log never names a weapon's type, so the item id is looked up in a bundled table of every weapon and shield in UESP's item database (`data/items/weapon_types.json`, 62,896 items, built by `scripts/generate_weapon_types.py`, which can also read a reply from UESP already saved to disk). All 174 weapon ids in 20 recent logs were in it; a weapon from a set newer than the table shows a dash. The table replaces the list of restoration staves the healer role relied on, which it answers as well

- **Taunts** (#9): for a group of three or more fighting a boss, and for anyone who taunted, the uptime line gains `Taunt:NN%`, how long the boss had a taunt on it: averaged over the bosses when a fight has several, and a boss killed before the end is measured to its death. On each player's bars, an ability they taunted with in that fight is ringed in purple (its name in purple where it has no icon), in the fight pane and the build window, and copied text lists them (`taunted with Inner Rage ×262`). The experimental timeline strip gets a Taunt row. No list of taunt skills is involved: the log records every taunt, as a TAUNTED event that shares its cast tracking id with the taunting skill's own cast, and as the Taunt debuff on the enemy, whose spans give the uptime. Destructive Clench with an ice staff is logged as Frost Clench under another id and is recognised by the icon the two share. Checked on 1,361 taunts in twelve logs of October 2026

### Fixed
- **Group buff uptimes counted a buff only on the player who cast it** (#11): the uptime line's MCourage, MForce, Mslayer, PA, LE and PW percentages are the share of the fight the buff was on any group member, but the engine never saw a buff one player put on another. An EFFECT_CHANGED line carries a ten-field unit state for the source and another for the target, and the target id was read from the source's shield value, almost always `0`, in place of the target's own id, so only a buff a player gave themself counted. Buffs that come from someone else were undercounted or missing: Lucent Echoes was absent from most uptime lines, Major Slayer and Major Force often read 0% when they were up all fight, and Major Courage read tens of points low. Replaying nine trial and dungeon logs of this year (170 fights of three or more players) through the old and the new engine, the uptime line changes in 143 of them, and each buff is now seen on all twelve players of a trial group rather than on one. The experimental timeline and the taunt tracking read the target correctly already and are unchanged. A side effect: the same wrong id had been filling the engine's table of supposed pets with shield values, and a unit whose id happened to match one had its damage or healing credited to a group member at random. That table is no longer filled, and in five of the 170 fights a player's DPS moves by up to 1%

- **Pet damage and healing count as the owner's**: the damage a player's pets deal (Blighted Blastbones, Skeletal Archer, a Warden's Wild Guardian, a Sorcerer's atronachs and Clannfear, a Nightblade's Gloom Wraith, a companion) is now in that player's DPS and in the group DPS, and the healing a pet does (an Arcanist's Glyphic of the Tides) in their healing. The log names the owner of every summoned unit (ownerUnitId, in UNIT_ADDED and UNIT_CHANGED) and the engine had ignored it, so pet damage was credited to nobody. A boss's summons have an owner too and stay nobody's; a pet that expires loses its owner a moment before the game removes it, and deals nothing after that; a unit id the game hands out again is only a pet if its new owner is a player. Across nine trial and dungeon logs of this year, pets dealt between nothing and 8% of a group's damage (Sunspire, with two Necromancers) and one Necromancer gained 17 million damage over a Maw of Lorkhaj run; the engine now credits every pet hit the logs carry, 64 million damage in all, matching an independent count of the log lines exactly, and no player's own DPS changed. The uptime line is unaffected

- **Saving settings could crash the app**: pressing Save in the Settings window restarts monitoring, which replays the current log session on the engine thread. The closed Settings window was left for Python's garbage collector to free, and its path rows pointed back at the window, a cycle only that collector could free, on whichever thread happened to be allocating at the time: the engine thread, mid-replay. Freeing the window's Qt objects there aborted the app, with nothing in the crash log but the engine's position in the log. The window now deletes the closed dialog itself, on the UI thread, and nothing in the dialog points back at it. Reproduced and confirmed on a Sunspire log: the real Save flow aborted every time; with the collector off, or with the dialog deleted on the UI thread, it never did

- **Fights listed twice after saving settings**: Save restarts monitoring, but the engine only reaches the restart once the replay it is in the middle of has finished (the session loaded at startup, or by an earlier Save), and that replay keeps sending fights meanwhile. The window cleared its history the moment Save was pressed, so the rest of the old replay refilled it and the new replay's fights were listed under them, the first copy without the timeline the new setting had just turned on. The history is now cleared when the engine reports that the restart has begun, and fights sent before that are dropped. A review opened from a file keeps its list across the restart

## [0.6.6] - 2026-10-06

### Fixed
- **Three Cyrodiil sets under each other's names**: Colovian Highlands General, Jerall Mountains Warchief and Nibenay Bay Battlereeve each showed under another of the three names, wherever a set is named: the fight view, the build window and copied text. Their ESO-Hub links opened that other set's page as well. The LibSets workbook the set names come from has the three names one set out of place; the gear data generator now gives those set ids the names the game uses

- **Three newer sets shown as numbers**: Prowler's Talisman, Tarcyr and Mylenne Moon-Caller showed as `Set#854`, `Set#876` and `Set#877` with no ESO-Hub link, and the build window did not treat Prowler's Talisman as a mythic. The bundled LibSets workbook is now the one of April 2026, which knows them

- **Set names spelt as the game spells them**: 22 sets carried the LibSets workbook's spelling in place of the game's. The perfected Cloudrest and Blackrose Prison sets read "Perfect Arms of Relequen", "Perfect Mender's Ward" and so on, where the game says "Perfected"; Bloodspawn read "Blood Spawn"; and eleven had a letter or a word out of place (Icy Conjurer, Claw of Yolnahkriin and its perfected version, Encratis's Behemoth, Lady Malygda, Languor of Peryite, Bastion of the Draoife, Judgment of Akatosh, Black-Glove Grounding, Ayleid Refuge, Aetheric Lancer). Every set name the app holds now matches the Update 51 client's own table of set names. The ESO-Hub links of these sets are unchanged

### Technical
- **Game data export for esobuild.com**: a new script, `scripts/export_esobuild_assets.py`, builds a zip of game data for the esobuild.com site: every `ability_*` icon at 64 px under the game's file names, and tables keyed by the game's ids for abilities (name, icon, skill line, type), skill lines, mundus boons and sets, with a manifest naming the client version and each source. Icons come from the installed game, abilities and sets from UESP's ESO log export, page paths from ESO-Hub's sitemaps. The bundle is published as a release asset under its own tag and is not part of the app. The steps of `scripts/extract_ability_icons.py` are now functions the export calls; the icons that script writes are byte for byte the same. No change to what the app shows

## [0.6.5] - 2026-10-06

### Security
- **Current Python and OpenSSL in the Windows build**: the Windows app was built with Python 3.11.9 (April 2024), the last 3.11 release that has a Windows installer, so it carried none of the security fixes made to Python since, and its OpenSSL was 3.0.13 from January 2024. That is the code that checks for an update and downloads the installer. Both builds now use Python 3.14, and take its newest patch release at build time rather than the copy cached on the build machine; on Windows that is 3.14.8 with OpenSSL 3.5.9 at the time of the change

- **No stray copy of OpenSSL**: the app also shipped a second pair of OpenSSL libraries, whichever ones were on the build machine's path, packed in for a Qt network module the app never uses (the update check goes through Python). That module and those libraries are no longer in the build

### Changed
- **Smaller download**: the Windows installer is about 7 MB smaller (about 37 MB, was 43 MB) and the installed app about 26 MB smaller. The build installed all of Qt for Python, and Qt's PDF, QML, virtual keyboard and network libraries were packed into the app although nothing uses them. It now installs only the part of Qt the app uses

### Technical
- **Dependency and tool versions**: `requirements.txt` asks for `PySide6-Essentials` in place of `PySide6`; the gear data generator reads the LibSets workbook with `openpyxl` directly, so `pandas` and `numpy` are no longer build dependencies (the generated module is byte-for-byte the same); minimum versions are raised: `PySide6-Essentials` 6.10.1 and `pyinstaller` 6.15.0 (the first for Python 3.14), `Pillow` 12.3.0 (earlier releases have known vulnerabilities) and `platformdirs` 4.8.0 (the first with the `WIN_PD_OVERRIDE_LOCAL_APPDATA` variable the development guide relies on); the GitHub Actions used by the build move off the deprecated Node 20 runtime (`checkout` v7, `setup-python` v7, `upload-artifact` v7, `download-artifact` v8, `action-gh-release` v3.0.3, pinned to its commit); the workflow's token is read-only except in the release job; UPX is switched off in the PyInstaller spec, where it only took effect on a machine that had UPX installed. A `return` inside a `finally` block, which Python 3.14 warns about, is removed from the archive action

## [0.6.4] - 2026-10-06

### Fixed
- **Stray backslash in four set names**: Mara's Balm, Runecarver's Blaze, Spriggan's Vigor and Siegemaster's Focus showed as `Mara\’s Balm`, `Siegemaster'\s Focus` and so on, wherever a set is named: the fight view, the build window and copied text. The LibSets workbook writes those four names with an escape character, which the gear data generator now removes. Their ESO-Hub links are unchanged.

### Technical
- **Repository tidy**: the installer zips and folders of the 0.2.3 terminal version are removed from the repository (about 90 MB); documentation moves under `docs/` (`reference/`, `research/`, and `archive/` for the terminal version's documents), with a new `docs/development.md`; completed OpenSpec changes are archived; `pyproject.toml` configures pytest in place of the path setup at the top of each test file, and the outdated `setup.py` is gone; `gear_set_database_optimized` is renamed `gear_set_database`; and about 720 lines of terminal output code that no longer ran to any effect are removed from the engine. No change to what the app shows.

## [0.6.3] - 2026-10-05

### Fixed
- **One pull shown as two fights**: the game writes `END_COMBAT` and, a moment later, `BEGIN_COMBAT` in the middle of a fight, most often as the logging player is resurrected, and the app started a new fight there. A Tideborn Taleria kill of 129.5 s showed as fights of 66.8 s and 62.7 s. Combat that starts again within a second of ending, while an enemy the group hit in the fight's last ten seconds is still alive, now carries on the same fight: its damage, deaths, death recaps and buff uptimes cover the whole pull. The first part still appears as a fight when the game ends combat, and that same history line is brought up to date when the fight really ends. 48 logs of April to October 2026 held 53 such cuts, 0 to 484 ms apart, 45 of them straight after a resurrection was accepted; none of the 51 pairs between half a second and three seconds apart was the same pull. Replayed through the fixed engine, those logs' 854 stretches of combat make 795 fights: all 53 cuts are joined, and so are six trash pulls that ran into each other with a mob alive across the cut. A pack that dies as the next one is pulled still makes two fights

## [0.6.2] - 2026-10-05

### Added
- **Armor weight in the build window**: the gear grid has a Weight column that says whether each armor piece is light, medium or heavy, and the Armor heading counts the pieces of each (`5 medium, 1 light, 1 heavy`). The log gives a piece only as an item id, so the weight is looked up in a bundled table (`data/items/armor_weights.json`, 56,439 pieces from UESP's item database, built by `scripts/generate_armor_weights.py`). All 905 armor item ids in 48 logs of April to October 2026 were in it. A piece from a set newer than the table shows a dash until the table is refreshed

## [0.6.1] - 2026-10-05

### Changed
- **Healers are recognised by their restoration staff**: a player whose largest pool is magicka is now a healer when a restoration staff is equipped on either bar. Before, they had to out-heal their own damage in that fight, so a healer read as DPS on a short pull or one with little to heal. Out-healing your own damage still marks a magicka player a healer without the staff. In six recent logs every fight with ten or more players now shows one or two healers, where 23 of 34 showed none. The log does not name weapon types, so the staff is recognised by item id against a bundled list (`data/items/restoration_staves.json`, 4,776 staves from UESP's item database, built by `scripts/generate_restoration_staves.py`)

### Fixed
- **Plain heals were left out of the healing total**: the role heuristic counted critical heals and heal-over-time ticks but not plain heals, which the log writes as `HEAL` (the code looked for `HEALED`). The total is only used to tell healers from damage dealers

## [0.6.0] - 2026-10-05

### Added
- **Scribed skills show their scripts**: a grimoire's icon and name do not say which signature and affix scripts were scribed into it. The build card now lists each scribed skill under the bars as `Shocking Banner (Class Flourish / Heroism)`, hovering its icon names the grimoire and all three scripts, and "Copy fight" and the text reports use the same label. The skill links to its ESO-Hub scribing page and each script to its script page (new map `data/esohub/scribing_en.json`; `scripts/generate_esohub_links.py` now takes the maps to regenerate as arguments). The scripts come from the three extra fields on a scribed skill's `ABILITY_INFO` line, which the game writes once per session directly before the `PLAYER_INFO` of the first player seen with that combination. A skill shows `(scripts not in log)` when the game wrote it without scripts for that player (they usually follow by a later fight), or when the player's combination was already written for someone else and it could be more than one; the hover says which, and lists the candidates. The approach follows sheumais's ESO Log Tool
- **Player build window**: click a player's name in the fight view, in the detail or the compact view, to open that player's build for that fight in a window that stays open beside the main one. It shows the account and character name, race, class, champion points and role; the mundus stone and the food or drink they pulled with; both ability bars, front above back, with the fight view's hover text, ESO-Hub links and scribed-skill line; and a gear grid with one row per slot: set (linked to ESO-Hub), pieces of that set active, quality, trait, enchant and enchant quality, plus a poison row under a bar that has one slotted. A name is underlined in the link color while the pointer is over it, and a tooltip says what a click does. Everything comes from the `PLAYER_INFO` line the game writes as combat starts, so the window shows the build the player pulled with; item names, weapon types and armor weights are not in the log and are not shown. Mythic pieces are marked as such (the log calls them legendary)
- **Set pieces counted per weapon bar** (build window): a set's armor and jewelry count on both bars, and each bar adds its own weapons, a two-handed one as two. `3/5` means three pieces active on the front bar and five on the back, which the fight view's summed `5x` cannot show
- **Bundled data for the build window**: poison names (`data/items/poisons_en.json`, 50 poisons from UESP's item database, built by `scripts/generate_poison_names.py`; the log gives a poison only as an item id, and a crafted poison is named by its primary effect) and the ids of food and drink buffs (`data/buffs/food_drink.json`, 92 buffs from the LibFoodDrinkBuff addon, built by `scripts/generate_food_buffs.py`, whose `--check-log` lists food-style effects in a log that the table does not know yet)

### Fixed
- **Gear slot documentation**: `ESO_GEAR_SLOTS.md` and the README said the log carries 13 gear slots and never the back-bar off hand. It carries 17 slot names (back-bar off hand, both poison slots and costume among them) and leaves out empty slots; both documents now say so
- **`PLAYER_INFO` with no long-term effects**: a line whose effect list is empty was not parsed, which would have dropped that player's build. No such line has been seen in a real log
- **Wrong name on another player's scribed skill**: one ability id covers several focus scripts of a grimoire (Fiery, Fortifying, Magical, Restorative, Shocking and Sundering Banner share an id), and the id was named after whichever player's line came last, so a Fortifying Banner could be listed as a Shocking Banner. Scribed skill names are now tracked per player

## [0.5.1] - 2026-10-04

### Added
- **Linux build (experimental)**: releases now carry `esolog-tail-linux-x86_64-<version>.tar.gz`, a self-contained folder to extract and run (`./esolog-gui`), for 64-bit desktops with glibc 2.35 or newer (Ubuntu 22.04, Debian 12, Fedora 36 and later), X11 or Wayland. The release workflow runs the test suite on Linux and starts the built bundle on an X server before publishing it; it has not been run against a live game yet. On Linux the app finds the log in ESO's Steam (Proton) prefix (native and Flatpak Steam) and the default Wine prefix, the update prompt opens the release page instead of running an installer, and the Windows-only *Start at login* setting is hidden

### Fixed
- **Split files on Linux**: split logs keep the game's CRLF line endings on every platform. On Linux they were written with LF, so they were not byte-for-byte copies of the game's log
- **Archiving on Linux**: the guard that skips an archive while ESO has the log open relied on Windows file locking and did nothing elsewhere, so *Delete Encounter.log after a verified archive* could remove a log the game was still writing. On Linux the archive is now skipped when another process has the log open

## [0.5.0] - 2026-10-03

### Fixed
- **Deaths missing from the count**: a player killed by another player (a shared mechanic, PvP) is logged as `KILLING_BLOW` with no `DIED` event, and was never counted; and the death of the last player standing is written about 85 ms after `END_COMBAT`, so it was dropped from the fight it ended. Both are now counted, and the late one is added to the fight that just finished (the fight on screen redraws)

### Added
- **Death recap**: a player who died in a fight gets a **☠ Death recap** button on their row, in both the detail and compact views (`×2` for two deaths; hover for when and to what they died). It opens a window that lists, for each of that player's deaths, the last 5 seconds of damage and healing, oldest first: time before death, health after the event, the ability with its icon, its source, the amount, and how the hit was taken (hit, DoT, blocked, dodged, or absorbed by a named damage shield), with the overkill on the killing blow. Players the table does not list still get a button under it. The recap is read from the log's `COMBAT_EVENT` lines, including the killing blow, which the log writes just after the `DIED` line
- **Death cue in the fight history**: a fight in which a player died shows `(d)` after its boss or mob name in the history list, so the fights worth a recap stand out. The clipboard copy is unchanged
- **Death-recap icons**: the bundled icon set gains the game's 162 `death_recap_*` icons, which is what monster attacks use. `scripts/extract_ability_icons.py` now takes several `--prefix` families and extracts `ability_` and `death_recap_` by default

## [0.4.1] - 2026-10-03

### Added
- **About… (toolbar)**: version, project link, and credits: skill and gear set links and their hover text point to ESO-Hub.com, and the ability icons are © ZeniMax Online Studios, not the property of this application. The README has the same Credits section

## [0.4.0] - 2026-10-03

### Fixed
- **Phantom fourth skill line**: skill-line detection matched ability names by substring, so the Two-Handed skill *Carve* counted as an Arcanist *Fatecarver* and *Swarming Scion* as the Warden *Swarm*, giving pure Nightblades a fourth line. Names now match exactly, and at most three lines (the best supported) are reported

### Changed
- **Detail view layout**: the fight stats sit to the right of the boss name on one line; subclass lines appear beside the class abbreviation (`NB Assassination/Shadow/Herald`) only when the build borrows a line from another class; the largest resource pool is bold; the gear line uses a 25% smaller font and `5x Name` counts

### Added
- **Ability-bar icons**: the detail view draws both bars as the game's ability icons instead of names, bar 1 left and bar 2 right on one line inside a framed build card. Icons are bundled from the installed client (`data/icons/abilities`, built by `scripts/extract_ability_icons.py`; refresh after a patch with the `refresh-ability-icons` skill) and cached in memory. Hover an icon for the ability name; click it to open the skill's page on ESO-Hub (link map in `data/esohub/skills_en.json` from `scripts/generate_esohub_links.py`). Abilities without a bundled icon still show their name, and "Copy fight" keeps names. In-fight search (Ctrl+F) matches icons by ability name and highlights them like text matches. Gear set names link to their ESO-Hub set pages (hover shows the target; map in `data/esohub/sets_en.json`)

## [0.3.3] - 2026-10-03

### Added
- **New app icon**: a shaded 3D d12 (a nod to 12-player trials) on a transparent background, rendered into all icon sizes; the window icon now matches the exe icon everywhere

### Changed
- **Fight line layout**: history entries and the detail subline now read boss/mob · duration · gdps · zone · timestamp, joined by compact middots (no em dashes)

## [0.3.2] - 2026-10-03

### Removed
- **Report file creation**: per-zone `-report.txt` files are no longer written and the Reports settings are gone. Fight summaries live in the app (with in-fight search and clipboard copy); split log files are unaffected

### Added
- **Start at login** (Settings → Startup): toggle to launch ESO Log Tail when you sign in to Windows (per-user Run registry entry, no admin rights; removed on uninstall)
- **Boss-first fight lines**: history entries and the detail header read boss name, time, zone; the player who dealt the fight's first damage is marked with *
- **Crash resilience**: unhandled errors in the windowed build are logged to `crash.log` instead of terminating the app (fixes the installed app dying on settings save)

## [0.3.1] - 2026-09-30

### Fixed
- **Death counts were always 0**: player deaths arrive as `DIED` events, not `DIED_XP` (enemy deaths). Fight cards now show that fight's player deaths (validated event-for-event against a real vet Hel-Ra log); zone reports keep the cumulative count
- **Mid-session app start lost the group**: starting the app after a logging session had begun showed fights with only the players added after attach (observed as one player per fight in a 12-person trial). On attach the latest session is now replayed: its fights load into the history, the full roster/gear/abilities are known, and a **missing split file for the session is created** (existing splits are never duplicated; sessions over 768 MB fall back to a fast roster-only sweep)
- **Dark-mode readability**: the light/dark decision is now live — when Windows switches theme mid-session (auto dark mode), the fight pane, status bar, and timeline re-render with correct-contrast colors
- **Major Berserk timeline row never appeared**: live logs apply it via ability IDs 61745/263306/36973; all are now tracked
- Interrupted archives can no longer leave a corrupt file with a `.zip` name (written as `.partial`, renamed only after verification)
- Review's "Loading…" status message no longer sticks after the load finishes

### Added
- **In-fight search** (Ctrl+F): highlights every occurrence in the fight summary with a live match count; Enter cycles matches, Esc clears, and the search follows you between fights
- **Update prompt**: the app checks GitHub releases at startup (Settings → Updates) and offers Update now / Later / Skip this version; updating downloads the installer with progress and hands over to it
- **Work progress in the status bar**: byte-accurate progress while parsing reviewed logs, a busy indicator during large live catch-ups; archive and download progress share the same bar
- **Buff timeline**: Powerful Assault row; uptime % in each row label; buffs that only reached one or two people render dotted; the fight header's text uptime line is replaced by the graph when shown

## [0.3.0] - 2026-09-27

### BREAKING
- **The terminal UI (TUI) and all command-line options are removed.** ESO Log Tail is now a windowed desktop application. Existing `.BAT` launch scripts stop working; every former CLI flag has a GUI equivalent (see the "Migrating from the terminal version" section in the README).

### Added
- **Desktop GUI application** (`esolog-gui.exe`): live fight summaries, session fight history with compact/detail toggle, clipboard copy, and an "Open log for review" mode for browsing fights in split files or old logs
- **Windows installer**: wizard-style per-user setup (no admin rights) with Start Menu/Desktop shortcuts, Apps & Features registration, in-place upgrades, and clean uninstall; a portable zip is still published
- **Automatic log archiving at startup**: when `Encounter.log` has grown past a configurable threshold (default 1 GB ≈ five veteran trials) since the last archive, the app zips it to a dated archive (`Encounter-YYMMDDHHMMSS.zip`, named from the newest log entry) with a progress bar; the settings dialog includes a sizing guide (vet trial ≈ 100–300 MB, vet dungeon ≈ 25–75 MB)
- **Archive safety**: the archiver takes exclusive (deny-all-sharing) access for the whole zip and skips with a notification when ESO has the log open; archives are verified before success is reported; deleting the original after a verified archive is strictly opt-in
- **"Archive now"** manual action for archiving mid-session after closing ESO, without restarting the app
- **Log freshness display**: the status bar shows the newest log entry's date/time and a live "how long ago" counter with live/idle/stale/no-log states, derived from log content (BEGIN_LOG epoch + entry offset) rather than file timestamps
- **Settings dialog** persisted to a per-user JSON config: log path (or auto-detect), split files, reports, and archive options
- **Experimental: buff timeline strip** (off by default, Settings → Experimental): a compact per-fight timeline — one thin colored row each for Major Slayer, Major Force, Major Courage, Major Berserk, and Major Vulnerability with time tick marks; hovering a segment shows who cast it and who received it
- **Update prompt**: the app checks GitHub releases at startup (Settings → Updates to disable) and offers Update now / Later / Skip this version; updating downloads the installer with progress and hands over to it
- **Work progress in the status bar**: byte-accurate progress while parsing reviewed logs, a busy indicator during large live catch-ups, and download/archive progress share one bar

### Changed
- Analysis engine decoupled from presentation: results flow through a typed listener interface (`engine_events.AnalyzerListener`); split files and zone reports work exactly as before
- Runtime dependencies are now just `PySide6` and `platformdirs` (build-time tooling moved to `requirements-build.txt`); `click`, `colorama`, `windows-curses`, `pandas`, `openpyxl`, `requests`, and `watchdog` removed from runtime
- CI builds a single Windows job producing the installer and portable zip; macOS/Linux build jobs removed

### Removed
- `TuiDisplay` (curses UI), the Click-based CLI, and the abandoned Tauri scaffold under `gui/`

## [0.2.6] - 2026-04-12

### Added
- **Full-Screen TUI Display**: New curses-based terminal UI renders fight summaries in a compact, full-screen layout with color-coded roles, elapsed timers, and boss names
- **Fight History with Scrolling**: Ring buffer stores up to 100 past fights; scroll through history with Up/Down arrow keys and snap back to live with Home
- **Compact & Detail Views**: Toggle between compact one-line-per-player view and expanded detail view showing skill lines, ability bars, and full gear sets (Tab to toggle)
- **Role Inference Heuristic**: Automatic Tank/Healer/DPS classification based on max resource pools and healing-vs-damage output, with ability-based fallback
- **Clipboard Copy from TUI**: Press 'c' to copy the current fight summary to clipboard, formatted with role-grouped players sorted by DPS
- **Set Name Abbreviations**: Compact display of gear set names in TUI using community-standard abbreviations (e.g., Ansuul, RO, SPC, Alkosh)
- **Elapsed Timer**: Each fight header shows how long ago it ended (e.g., "35s ago", "2m 10s ago")
- **New Mythic Items**: Added Huntsman's Warmask and Pearls of Ehlnofey to mythic set list

### Changed
- **LibSets Database Updated**: Expanded gear set database from 704 to 722 sets
- **Healer Identification**: Improved healer detection — magicka-primary players are only classified as healers when their healing output exceeds their damage output

### Technical Details
- Added `TuiDisplay` class with curses initialization, color pairs, non-blocking key input, and safe addstr rendering
- Added `FightHistory` ring buffer with cursor-based scrolling (live mode at cursor=-1)
- Added `FightHistoryEntry` dataclass with `__slots__` for memory-efficient fight storage
- Added `infer_player_role()` function with resource ratio tie-breaking and skill-line fallback
- TUI renders scrollable content with clamped offsets and scroll position indicators

## [0.2.5] - 2025-01-29

### Added
- **First Damage Dealer Tracking**: New feature to identify and mark the first player to deal damage in each encounter
- **Asterisk Prefix Display**: First damage dealer's line in encounter reports now shows with an asterisk (*) prefix
- **Pet Damage Attribution**: Pet damage is properly attributed to pet owners for first damage tracking
- **Per-Encounter Reset**: First damage tracking resets correctly between encounters

### Technical Details
- Added `first_damage_dealer` and `first_damage_timestamp` fields to CombatEncounter class
- Implemented first damage detection in `_handle_combat_event()` method
- Enhanced `_display_encounter_summary()` to display asterisk prefix for first damage dealer
- Proper pet ownership attribution ensures pet damage credits the owner

## [0.2.4] - 2025-01-29

### Fixed
- **File Locking Removal**: Eliminated unnecessary file locking that could interfere with ESO's log writing process
- **Enhanced File Tailing**: Improved reliability for high-frequency log monitoring (tested up to 1ms intervals)
- **Gear Set Classification Fix**: Corrected "Tarnished Nightmare" from mythic to 5-piece set classification
- **Improved Temp File Cleanup**: Enhanced log splitting logic to prevent orphaned temporary files
- **High-Performance Monitoring**: Validated real-time processing of 48MB+ log files without data loss

### Technical Improvements
- **File Access Optimization**: Removed `threading.Lock()` from `LogFileMonitor` class for better ESO compatibility
- **Enhanced Cleanup Logic**: Improved `end_encounter()` method in `LogSplitter` to handle edge cases
- **Temp File Management**: Added conditions to delete orphaned temp files and files with minimal combat events
- **Performance Validation**: Successfully tested with simulator at 0.001-second intervals (1000Hz)

### Quality Assurance
- **High-Frequency Testing**: Validated tool performance with extreme data rates
- **Data Integrity**: Confirmed zero data loss during high-speed monitoring
- **ESO Compatibility**: Ensured tool doesn't interfere with ESO's log writing process
- **Real-World Validation**: Tested with actual encounter log data processing

## [0.2.3] - 2025-01-29

### Fixed
- **Report Buffer Management**: Fixed critical bug where all zone reports were starting with the same encounters
- **Zone-Specific Report Isolation**: Each zone report now contains only encounters from that specific zone
- **File Naming Conflicts**: Enhanced conflict resolution with content-based deduplication using MD5 hashing
- **END_LOG Inclusion**: Ensured split log files properly include END_LOG entries for complete log structure
- **Timestamp Format Consistency**: Fixed edge cases in timestamp conversion and zone start time handling

### Technical Improvements
- **Content-Based Deduplication**: Implemented MD5 hash comparison for file conflict resolution
- **Automatic Suffix Numbering**: Files with different content get automatic -1, -2, etc. suffixes
- **Report Buffer Clearing**: Proper buffer management prevents cross-zone contamination
- **Enhanced Test Coverage**: Added comprehensive tests for file naming conflicts, END_LOG inclusion, and report isolation
- **Simulator Enhancement**: Improved ESO logging simulator to better simulate real-world file I/O behavior

### Quality Assurance
- **Comprehensive Testing**: All 101 tests passing with robust validation of new features
- **Edge Case Handling**: Proper handling of zero timestamps, missing values, and file conflicts
- **Data Integrity**: Atomic file operations ensure data safety during concurrent access

## [0.2.2] - 2025-01-29

### Removed
- **Discord Copy Feature**: Removed keyboard 'c' press functionality for copying reports to clipboard with Discord formatting
- **Keyboard Input Handling**: Removed all keyboard input detection and terminal input handling
- **Clipboard Integration**: Removed pyperclip dependency and clipboard copy functionality
- **Discord Markdown Formatting**: Removed Discord-specific report formatting methods

### Technical Changes
- Removed `pynput>=1.7.6` and `pyperclip>=1.8.2` dependencies from requirements.txt
- Cleaned up Discord-related instance variables and imports
- Simplified codebase by removing unused keyboard and clipboard functionality
- Updated documentation to remove Discord copy feature references

## [0.2.1] - 2025-01-29

### Fixed
- **Timestamp Format Bug**: Fixed incorrect timestamp generation for report filenames that was causing fallback to current time
- **Zero Timestamp Handling**: Correctly handle zero timestamps (log start) in timestamp conversion
- **Zone Start Time Preservation**: Fixed bug where zone start time was being overwritten during report generation

### Technical Improvements
- Enhanced timestamp conversion logic to properly handle edge cases
- Improved file naming conflict resolution for split logs and reports
- Added comprehensive test coverage for timestamp format validation

## [0.2.0] - 2025-01-27

### Major Features
- **Combat-Based Zone Naming**: Split files and reports are now named after the zone where combat begins, not the initial zone
- **Zone-Based Report Consolidation**: Reports are consolidated per zone instead of per encounter for better organization
- **Enhanced Log File Detection**: Automatic detection of ESO log files in multiple Windows locations including OneDrive
- **Robust File Handling**: Atomic file operations with temporary files and proper cleanup for data safety

### Added
- **New Buff Tracking**: Added Lucent Echoes (LE) and Pearlescent Ward (PW) buff tracking
- **Report Saving**: Save encounter reports to files with zone-based naming
- **Auto-Split Logs**: Automatically split encounter logs into zone-specific files
- **Enhanced Diagnostics**: Comprehensive diagnostic output for troubleshooting
- **Default Behavior Explanation**: Clear explanation when no command-line arguments are provided

### Changed
- **Buff Display Format**: Removed ticks/crosses, parentheses, and pipe separators from buff status
- **Buff Labels**: Shortened to Mslayer, MForce, MCourage, PA, LE, PW
- **Duration Format**: Display fight durations in minutes:seconds format, rounded to nearest second
- **Fight Summary**: Removed "Duration:", changed "Est. DPS" to "GrpDPS", removed "Target:"
- **Discord Formatting**: Equipment display uses "5x" instead of "5pc" and "p" instead of "Perfected "
- **Vitality Display**: Always show vitality bonus without % or + symbols
- **Timestamp Handling**: Correct conversion from relative milliseconds to absolute Unix timestamps

### Fixed
- **Critical Parsing Issues**: Fixed timestamp extraction and field indexing in log entry parsing
- **Event Routing**: Added missing ZONE_CHANGED event routing to proper handlers
- **Field Indexing**: Corrected field access for UNIT_ADDED, ZONE_CHANGED, and other events
- **Combat Zone Detection**: Fixed logic to properly detect and name files after combat zone
- **File Handle Management**: Proper file closing and reopening for robust data handling
- **Race Conditions**: Added threading locks to prevent concurrent file access issues
- **Deadlock Prevention**: Fixed polling-based tailing deadlock issues

### Testing
- ✅ 76 comprehensive tests covering all functionality
- ✅ Log splitting with combat-based zone naming
- ✅ Report saving with zone-based consolidation
- ✅ Buff tracking and display formatting
- ✅ File operations and error handling
- ✅ Integration tests for complete workflows
- ✅ Regression tests for existing functionality

### Documentation
- ✅ Updated README.md with new command-line options and features
- ✅ Added comprehensive help output integration
- ✅ Updated TESTING.md with new test coverage
- ✅ Enhanced troubleshooting and usage examples

## [0.1.29] - 2025-01-26

### Added
- **Log Splitting Tests**: Comprehensive test suite for log splitting functionality (`test_log_splitting.py`)
- **Report Saving Tests**: Complete test coverage for report saving functionality (`test_report_saving.py`)
- **Integration Tests**: Full integration tests for log splitting and report saving (`test_log_splitting_integration.py`)

### Fixed
- **LogSplitter File Handling**: Fixed issue where file handles were not properly reopened after renaming
- **End Encounter Cleanup**: Fixed cleanup logic to always clear encounter state regardless of file handle status
- **Report Buffer Management**: Fixed report buffer clearing behavior in tests

### Testing
- ✅ 75 new tests covering log splitting and report saving functionality
- ✅ File operations: creation, naming, writing, closing, and cleanup
- ✅ Zone detection: zone-based file naming and difficulty handling
- ✅ Error handling: permission errors, directory creation, and edge cases
- ✅ Integration: complete workflows combining splitting and report saving
- ✅ All tests pass successfully

### Documentation
- ✅ Updated TESTING.md with new log splitting and report saving test documentation
- ✅ Added test coverage details and integration test scenarios

## [0.1.28] - 2025-01-26

### Verified
- **Damage Attribution**: Verified that damage attribution to players is working correctly
- **Pet Ownership Tracking**: Confirmed pet damage is properly attributed to their owners
- **Unit ID Matching**: Validated short/long unit ID matching for player identification
- **Combat Event Processing**: Verified damage parsing from COMBAT_EVENT entries

### Testing
- ✅ Added comprehensive damage attribution test suite (`test_damage_attribution.py`)
- ✅ Basic damage attribution to players
- ✅ Pet damage attribution to owners
- ✅ Unit ID matching between short and long formats
- ✅ Combat event damage parsing
- ✅ Multiple players damage attribution
- ✅ Edge cases: unknown units, orphaned pets
- ✅ Real log data processing validation

### Documentation
- Updated TESTING.md with damage attribution test documentation
- Added test coverage for damage attribution verification

## [0.1.27] - 2025-01-26

### Enhanced
- **Comprehensive Test Suite**: Added extensive testing for all new features and edge cases
- **Combat-Based Zone Naming**: Split files now correctly named after zone where combat begins
- **Zone-Based Report Naming**: Report files use consistent naming with split files
- **Robust Error Handling**: Improved error handling for missing zones and invalid directories
- **Edge Case Coverage**: Comprehensive testing of missing zones, invalid paths, and large files

### Technical Details
- Enhanced LogSplitter to wait for combat before renaming files
- Added current_difficulty tracking to ESOLogAnalyzer
- Implemented zone-based naming for both split files and reports
- Added comprehensive test scenarios covering all functionality
- Improved diagnostic output for better debugging

### Testing
- ✅ Combat-based zone naming for split files
- ✅ Zone-based report naming with difficulty suffixes
- ✅ Combined splitting + report saving functionality
- ✅ Regression tests on existing functionality
- ✅ Edge cases: missing zones, invalid directories, large files
- ✅ Error handling and graceful degradation

## [0.1.26] - 2025-01-26

### Enhanced
- **Zone-Based Report Naming**: Report files now use the same naming convention as split files
- **Consistent File Naming**: Reports are named `YYMMDDHHMMSS-{Zone-Name with dashes}{-vet or blank}-report.txt`
- **Difficulty Tracking**: Added difficulty tracking to ESOLogAnalyzer for accurate report naming
- **Improved Organization**: Report files are now organized by zone and difficulty, making them easier to identify

### Technical Details
- Added `current_difficulty` tracking to ESOLogAnalyzer class
- Modified `_save_report_to_file()` method to use zone-based naming logic
- Updated `_handle_zone_changed()` to track both zone name and difficulty
- Enhanced report filename generation to match split file naming convention

## [0.1.25] - 2025-01-25

### Added
- **Combat-Based Zone Naming**: Split files are now named after the first zone encountered during combat rather than the initial zone
- **Improved Split File Accuracy**: Enhanced log splitting logic to wait for combat events before determining zone names
- **Combat State Tracking**: Added tracking of combat start events to ensure accurate zone detection

### Enhanced
- **Smart Zone Detection**: Tool now waits for BEGIN_COMBAT event and uses the first subsequent ZONE_CHANGED for naming
- **Immediate File Creation**: Split files are created immediately as temporary files, then renamed when combat zone is determined
- **Robust Data Safety**: No data loss risk - files are written immediately and renamed atomically
- **Better Diagnostic Output**: Enhanced diagnostic messages for combat and zone detection events

### Technical Details
- Added combat_started flag to LogSplitter to track combat state
- Implemented immediate temporary file creation with atomic rename operation
- Modified both live tailing and replay modes to support combat-based zone detection
- Added start_combat(), handle_zone_change(), _create_temp_file(), and _rename_to_final() methods

## [0.1.24] - 2025-01-25

### Fixed
- **Critical Parsing Issue**: Fixed ESOLogEntry parsing for events without timestamps (BEGIN_COMBAT, END_COMBAT, UNIT_ADDED, etc.)
- **Missing Event Routing**: Added missing ZONE_CHANGED event routing in process_log_entry method
- **Field Indexing**: Corrected field indexing for ZONE_CHANGED events to properly extract zone name and difficulty
- **Encounter Detection**: Fixed encounter detection and player addition that was preventing report generation

### Enhanced
- **Robust Event Parsing**: Improved parsing logic to handle events with and without timestamps correctly
- **Better Error Handling**: Enhanced diagnostic output for debugging event processing issues
- **Report Generation**: Encounter reports now generate correctly in all modes

### Technical Details
- Modified ESOLogEntry.parse() to distinguish between events with timestamps and those using line numbers
- Added ZONE_CHANGED case to process_log_entry method routing
- Fixed field access for ZONE_CHANGED events (zone_name, difficulty)
- Added comprehensive debug output for event processing flow

## [0.1.23] - 2025-01-25

### Added
- **Report Saving Feature**: New `--save-reports` option to automatically save encounter reports to timestamped files
- **Custom Reports Directory**: New `--reports-dir` option to specify where report files are created
- **Timestamped Report Files**: Reports saved with format `YYMMDDHHMMSS-report.txt` based on encounter start time
- **Clean Text Output**: Report files contain clean text without ANSI color codes for easy reading

### Enhanced
- **Early Directory Validation**: Tool validates reports directory permissions before starting processing
- **Graceful Error Handling**: Clear error messages when directory creation fails, with instructions for manual creation
- **All Modes Support**: Report saving works in tail, read-all-then-stop, and read-all-then-tail modes

### Technical Details
- Added report buffering system to capture stdout output during encounter display
- Implemented ANSI color code stripping for clean text file output
- Added comprehensive directory validation with proper error handling
- Integrated report saving into existing encounter summary display system

## [0.1.22] - 2025-01-25

### Added
- **Auto-Split Logs Feature**: New `--tail-and-split` option to automatically create individual encounter files while tailing
- **Smart File Naming**: Split files named with format `YYMMDDHHMMSS-{Zone-Name with dashes}{-vet or blank}.log`
- **Zone Detection**: Automatically extracts zone name and difficulty from ZONE_CHANGED events
- **Robust File Handling**: Split files are closed when waiting and reopened for appending to prevent data loss
- **Custom Split Directory**: New `--split-dir` option to specify where split files are created

### Enhanced
- **All Modes Support**: Auto-split functionality works in tail, read-all-then-stop, and read-all-then-tail modes
- **Timestamp Accuracy**: Fixed ESOLogEntry parsing to use correct timestamps from log entries
- **Diagnostic Output**: Enhanced diagnostic mode shows split file creation and management details

### Technical Details
- Added `LogSplitter` class for managing split file creation, writing, and cleanup
- Fixed ESOLogEntry parsing to use `fields[2]` as timestamp instead of `fields[0]` (line number)
- Implemented robust file handling with `close_for_waiting()` and `reopen_for_append()` methods
- Added support for both LogFileMonitor and replay modes with auto-split functionality

## [0.1.19] - 2025-01-24

### Fixed
- **Critical Concurrency Issues**: Fixed race conditions in file monitoring that caused read-all-then-tail to fail
- **File Monitoring Reliability**: Replaced complex watchdog directory monitoring with simple, reliable file polling
- **Multiple File Confusion**: Eliminated issues where tool was monitoring multiple log files simultaneously
- **Thread Safety**: Added threading locks to prevent concurrent file access conflicts

### Changed
- **Simplified Architecture**: Replaced watchdog-based file monitoring with simple 1-second polling
- **Better Diagnostics**: Improved diagnostic output to clearly show file monitoring status
- **Removed Dependencies**: Eliminated watchdog library dependency for more reliable operation

### Technical Details
- Added `threading.Lock()` to prevent race conditions between `_process_entire_file()` and `_process_new_lines()`
- Replaced `LogFileHandler(FileSystemEventHandler)` with `LogFileMonitor` class
- Implemented `check_for_changes()` method for reliable file change detection
- Simplified main monitoring loop to use direct file polling instead of event-driven monitoring

## [0.1.17] - 2025-01-22

### Fixed
- **Major Slayer Tracking**: Added support for both ability IDs (93120 and 931200) to properly track Major Slayer buff
- **Windows Build Error**: Fixed `ModuleNotFoundError: No module named gear_set_database_optimised` by updating PyInstaller spec file
- **Nunatak Monster Set**: Added comprehensive Nunatak variations to prevent incorrect red highlighting as incomplete 5-piece set

### Changed
- Updated PyInstaller spec file to include `gear_set_database_optimized` in hidden imports
- Updated GitHub Actions workflow to use spec file instead of command-line PyInstaller
- Added gear set data files to PyInstaller datas configuration

## [0.1.14] - 2025-01-22

### Enhanced
- **CLI Consistency**: Renamed `--scan-all-then-stop` to `--read-all-then-stop` for consistency with `--read-all-then-tail`
- **Help Text**: Updated help descriptions to use "Read mode" instead of "Scan mode" for clarity

### Fixed
- **File Position Tracking**: Resolved `OSError: telling position disabled by next() call` in `--read-all-then-tail` mode
- **File Monitoring**: Improved file position tracking compatibility with watchdog file monitoring system

### Technical
- **File I/O**: Changed from `for line in f:` loop to `while True:` with `f.readline()` for proper position tracking
- **EOF Handling**: Added proper end-of-file detection for robust file processing

## [0.1.13] - 2025-01-22

### Enhanced
- **Taunt Ability Highlighting**: Added purple highlighting for taunt abilities to easily identify tanking abilities
- **Health Thresholds**: Updated health highlighting thresholds from 19k-50k to 18.5k-44.5k for better health pool identification
- **DPS Display**: Changed DPS percentage format from `(3.1%)` to `D:3.1%` for consistency with resource indicators
- **Resource Highlighting**: Bold and underline each player's highest max resource type (health, stamina, or magicka)
- **Visual Improvements**: Changed encounter summary line color from red to dark orange for better visual distinction

### Fixed
- **Color Bleeding**: Fixed purple taunt highlighting that was affecting following text color
- **Variable Scope**: Resolved UnboundLocalError for `dps_str` variable when players had no damage data
- **Error Handling**: Improved robustness for edge cases in player data processing

### Technical
- **Taunt Detection**: Comprehensive lookup for 35+ taunt abilities across all classes and weapon lines
- **ANSI Colors**: Implemented dark orange color using `\033[38;5;208m` for encounter summaries
- **Resource Styling**: Applied bold and underline styling using ANSI escape codes for highest resources

## [Unreleased] - 2025-01-22

### Major Optimization
- **Gear Set Database**: Implemented pre-build data generation system for optimal performance
- **Startup Speed**: ~10x faster startup by eliminating Excel parsing at runtime
- **Installer Size**: ~1.8MB smaller installers by removing XLSM file dependencies
- **Reliability**: Eliminated Excel file corruption and missing file issues
- **Build Process**: Added `generate_gear_data.py` pre-build step to extract gear set data

### Enhanced
- **Build Documentation**: Updated BUILD_WINDOWS.md with gear data generation requirements
- **README**: Added comprehensive build instructions and gear set update process
- **GitHub Actions**: Updated workflow to include gear data generation step
- **File Cleanup**: Removed unused LibSets_SetData.xlsx file from repository

### Technical
- **Data Generation**: `generate_gear_data.py` extracts 704 gear sets from XLSM to optimized Python structures
- **Optimized Database**: `gear_set_database_optimized.py` provides same API with pre-generated data
- **Generated Module**: `gear_set_data.py` contains optimized dictionaries for fast lookups
- **Build Integration**: All platforms now generate gear data before building executables
- **Dependency Reduction**: Removed pandas/Excel runtime dependencies from installers

## [0.1.12] - 2025-01-22

### Enhanced
- **Documentation**: Updated README with real output examples from actual encounter logs
- **Accuracy**: Fixed installer names to match actual release artifacts (.zip files)
- **Platform Support**: Added Linux support to cross-platform description
- **Output Format**: Corrected output components to reflect actual implementation

### Fixed
- **Installer Names**: Updated from fictional .exe/.dmg to actual .zip installer names
- **Output Examples**: Replaced fictional examples with real data from Coral Aerie, Selene's Web, and Vateshran Hollows
- **Feature Descriptions**: Ensured all documented features match actual implementation

### Technical
- Comprehensive documentation review and consistency verification
- Real encounter log analysis for accurate example generation
- Updated output format documentation to match current code behavior

## [0.1.11] - 2025-01-22

### Fixed
- **GitHub Actions**: Fixed automated release creation by enabling proper repository permissions
- **Release Automation**: GitHub Actions now automatically creates releases with installer artifacts
- **Workflow Reliability**: Improved workflow stability and error handling

### Technical
- Enabled "Read and write permissions" for GitHub Actions workflows
- Automated release creation now works without manual intervention
- All platform installers are automatically attached to releases

## [0.1.10] - 2025-01-22

### Fixed
- **Default Behavior**: Changed default behavior to wait for log file instead of exiting immediately
- **User Experience**: Tool now waits for encounter log file to appear by default with status updates every minute
- **Command Line Options**: Replaced `--wait-for-file` with `--no-wait` flag (inverted logic for better UX)

### Enhanced
- **Intuitive Behavior**: Users no longer need to remember special flags to wait for log files
- **Better Defaults**: More user-friendly default behavior for new users
- **Clearer Options**: Simplified command line interface with more intuitive flag names

### Technical
- Inverted wait-for-file logic to make waiting the default behavior
- Updated all documentation to reflect new default behavior
- Improved error messages and user guidance

## [0.1.9] - 2025-01-22

### Added
- **Wait for File Option**: `--wait-for-file` flag to wait for log file to appear if it doesn't exist
- **Read All Then Tail Option**: `--read-all-then-tail` flag to read entire log file from beginning then continue tailing
- **Status Updates**: Print status updates every minute while waiting for log file to appear
- **Enhanced Log File Handling**: Improved file monitoring with better error handling and user guidance

### Enhanced
- **Command Line Options**: More flexible monitoring options for different use cases
- **User Experience**: Better status messages and progress indicators
- **Documentation**: Updated README with usage examples for new options
- **Troubleshooting**: Added guidance for common file not found scenarios

### Technical
- Added `_wait_for_file()` helper function with periodic status updates
- Enhanced `LogFileHandler` class with `read_all_then_tail` parameter
- Added `_process_entire_file()` method for reading complete log files
- Improved file position tracking for seamless tailing after full read
- Updated command line interface with new flags and help text

## [0.1.8] - 2025-01-22

### Added
- **Resource Tracking**: Real-time monitoring of player maximum health, magicka, and stamina values
- **Resource Display**: Shows resource values in player build information (e.g., "M:25k S:30k H:20k")
- **Health Anomaly Detection**: Highlights unusual health values (below 19k or above 50k) in red
- **Resource Reset**: Automatic resource tracking reset between encounters for accurate per-encounter analysis

### Enhanced
- **Player Information**: More comprehensive player statistics including resource pools
- **Visual Indicators**: Color-coded health values for quick identification of unusual builds
- **Combat Analysis**: Better understanding of player builds through resource distribution

### Technical
- Added `update_resources()` and `reset_resources()` methods to PlayerInfo class
- Enhanced BEGIN_CAST event parsing to extract resource information from sourceUnitState
- Added `_parse_and_update_player_resources()` for resource data processing
- Improved resource display formatting with rounded values (e.g., "25.5k" instead of "25500")

## [0.1.7] - 2025-01-22

### Enhanced
- **Improved Log Processing**: Enhanced log file parsing and analysis capabilities
- **Better Error Handling**: Improved error handling and edge case management
- **Code Quality**: Refactored and improved code structure for better maintainability

### Technical
- Significant code improvements across multiple modules
- Enhanced database integration and set detection
- Improved analyzer performance and reliability

## [0.1.6] - 2025-01-22

### Added
- **Intelligent Auto-Detection**: Automatically detects most likely ESO log directory based on host OS (Windows, macOS, Linux)
- **Enhanced Status Messages**: Clear, informative messages about what the tool is doing and where it's looking
- **Directory Creation**: Automatically creates log directories if they don't exist
- **Easy Stalking Integration**: Comprehensive documentation and references to Easy Stalking addon for automatic logging
- **Improved User Experience**: Better guidance for users on enabling encounter logging
- **Zone Rewind Functionality**: Automatically detects and handles scenarios where the tool starts after a zone change

### Enhanced
- **Cross-Platform Detection**: Smart detection of ESO installation paths for Windows, macOS (native/Wine), and Linux (Wine)
- **Status Reporting**: Real-time feedback on log file detection and monitoring status
- **Error Handling**: Better error messages and guidance when log files aren't found
- **Documentation**: Added troubleshooting section with common issues and solutions
- **Zone Context Recovery**: Automatically recovers zone context when starting monitoring after zone changes

### Removed
- **Resource Categorization**: Removed magicka/health/stamina resource type categorization from player build displays
- **Individual Major Courage Uptime**: Removed redundant individual Major Courage uptime calculations after player reports

### Technical
- Added `_get_most_likely_log_directory()` for OS-specific path detection
- Added `_get_host_type_description()` for user-friendly OS identification
- Enhanced main function with detailed status reporting
- Improved directory and file existence checking with automatic directory creation
- Added zone history tracking with `_add_zone_to_history()` and `_rewind_to_last_zone()`
- Enhanced LogFileHandler with `_initialize_zone_history()` for startup zone detection
- Added `_process_log_file_from_position()` for efficient log file scanning
- Removed resource tracking fields and methods from PlayerInfo class
- Simplified player build display format by removing resource type categorization
- Removed individual Major Courage uptime display code from player report section

## [0.1.5] - 2025-01-22

### Added
- **Unix Timestamp Integration**: Accurate combat start times using Unix timestamps from BEGIN_LOG events
- **Group Buff Detection**: Monitors critical group buffs (Major Courage, Major Force, Major Slayer) with visual indicators
- **Individual Buff Uptime**: Tracks Major Courage uptime percentage for each player
- **Enhanced Visual Output**: Uses ✅/❌ emojis for prominent buff status display

### Enhanced
- **Combat Timing**: Fixed combat start time calculation to prioritize BEGIN_COMBAT events over BEGIN_CAST events
- **Timestamp Accuracy**: Replaced file modification time estimation with precise Unix timestamp calculations
- **Buff Tracking**: Comprehensive buff application and removal monitoring throughout encounters
- **Output Formatting**: Improved combat report layout with better visual hierarchy

### Technical
- Added `_handle_begin_log_event()` for Unix timestamp extraction
- Enhanced `get_combat_start_time_formatted()` with Unix timestamp support
- Implemented buff tracking system with uptime calculations
- Added encounter finalization protection against post-combat timestamp overrides

## [0.1.2] - 2025-01-XX

### Enhanced
- Updated skill line mappings and aliases for improved accuracy
- Enhanced skill line detection with better subclass analysis logic
- Improved readability of skill line abbreviations in combat reports

### Technical
- Refined skill line detection algorithms for better build identification
- Enhanced ability-to-skill-line mapping accuracy

## [0.1.1] - 2025-01-XX

### Fixed
- Fixed player death tracking to only count actual player deaths, not enemy deaths
- Enhanced enemy filtering to exclude environmental hazards like 'Water', 'Fire', 'Trap', etc.
- Improved target selection with better fallback logic from damage tracking to health-based selection
- Removed unnecessary blank lines in combat report output for cleaner formatting

### Enhanced
- Added comprehensive filtering for pets, corpses, and non-combat entities
- Updated gear set database to use LibSets_SetData.xlsm for more accurate set information
- Enhanced skill line detection and aliases
- Improved combat encounter tracking and reporting accuracy

### Technical
- Added cross-platform installers (Windows, macOS, Linux) via GitHub Actions
- Improved enemy tracking logic with better validation
- Enhanced error handling and edge case management

## [0.1.0] - 2025-01-XX

### Added
- Initial release of ESO Live Encounter Log Sets & Abilities Analyzer
- Real-time monitoring of ESO encounter logs
- Comprehensive player analysis with skill line detection
- Front/back bar ability tracking
- Gear set identification using LibSets database
- Zone-based reporting system
- Cross-platform support (Windows, macOS)
- Test mode with sample log replay
- Comprehensive skill line mappings based on UESP
- Support for 634+ gear sets from LibSets database

### Features
- **Player Analysis**: Extracts player names, abilities, and gear information
- **Skill Line Detection**: Analyzes equipped abilities to infer skill lines (e.g., "Herald/Assassination/Winter's")
- **Gear Set Identification**: Uses LibSets database for accurate set identification
- **Zone Tracking**: Reports zone changes and maintains player data across encounters
- **Combat Event Handling**: Proper BEGIN_COMBAT/END_COMBAT event processing
- **Real-time Monitoring**: File system watchers for live log analysis
- **Test Mode**: Replay sample logs at various speeds for testing

### Technical Improvements
- **Robust CSV Parsing**: Handles complex ESO log format with nested arrays
- **Ability Cache System**: Efficient ability ID to name mapping
- **Combat Timeout Removal**: Eliminated unreliable timeout-based combat detection
- **Explicit Event Handling**: Uses BEGIN_COMBAT/END_COMBAT events for accurate combat tracking
- **Enhanced Skill Line Detection**: Comprehensive ability-to-skill-line mappings
- **LibSets Integration**: Full gear set database integration
- **Improved Display Format**: Cleaner, more concise output format

### Dependencies
- Python 3.7+
- watchdog (file system monitoring)
- click (command-line interface)
- pandas (Excel file processing)
- openpyxl (Excel file reading)
- colorama (cross-platform colored terminal output)

### Supported Platforms
- Windows 10/11
- macOS 10.14+
- Linux (experimental)

### Known Limitations
- Ability cache dependency on ABILITY_INFO events
- Limited to sets available in LibSets database
- Cannot identify builds for anonymous players
- ESO logs track 13 gear slots (missing backup off-hand weapon slot)

### Future Enhancements
- Web interface for real-time monitoring
- Historical encounter database
- Damage/healing number parsing
- Advanced build analysis
- Integration with ESO addons

### Acknowledgments
This project builds upon excellent community resources:
- **[LibSets](https://github.com/Baertram/LibSets/tree/LibSets-reworked/LibSets)** by Baertram for gear set database
- **[ESO Log Tool](https://github.com/sheumais/logs)** by sheumais for log parsing insights
- **UESP** for authoritative skill line information
