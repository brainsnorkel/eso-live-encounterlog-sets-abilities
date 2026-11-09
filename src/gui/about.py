"""
About dialog: version, project link, and the credits the app owes.

Kept as plain HTML so the same wording can be checked by tests and mirrored
in the README's Credits section.
"""

import html

from PySide6.QtWidgets import QMessageBox

from data_staleness import data_stamps, short_version

REPO_URL = "https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities"
ESOHUB_URL = "https://eso-hub.com"
LIBSETS_URL = "https://github.com/Baertram/LibSets"
EXTRACTOR_URL = "https://en.uesp.net/wiki/ESO_Mod:EsoExtractData"
UESP_URL = "https://en.uesp.net/wiki/Online:Online"
LIBFOODDRINKBUFF_URL = "https://www.esoui.com/downloads/info1902-LibFoodDrinkBuff.html"
COMBATMETRICS_URL = "https://www.esoui.com/downloads/info1360-CombatMetrics.html"
COMBATMETRICS_SOURCE_URL = "https://github.com/Solinur/CombatMetrics"
LIBCOMBAT_URL = "https://github.com/Solinur/LibCombat"
EASYSTALKING_URL = "https://www.esoui.com/downloads/info2332-EasyStalking-Encounterlog.html"
ALWAYSLOGGING_URL = "https://github.com/brainsnorkel/AlwaysLogging"


def data_html(data) -> str:
    """The bundled game data's version and each table's date (issue #173),
    from data_staleness.data_stamps(): '' when the bundle carries none."""
    game_version, built, tables = data or ("", "", [])
    if not game_version and not tables:
        return ""
    head = "<b>Game data</b>"
    if game_version:
        head += f": built for game version {html.escape(short_version(game_version))}"
        if built:
            head += f" on {html.escape(built)}"
    stamps = " · ".join(f"{html.escape(name)} {html.escape(date)}".strip()
                        for name, date in tables)
    return f"<p>{head}" + (f"<br><span style='color:gray'>{stamps}</span>" if stamps else "") + "</p>"


def about_html(version: str, updates: str = "", data=None) -> str:
    """*updates* is the update channel line (issue #134), left out when empty;
    *data* the bundled data's stamps (data_staleness.data_stamps)."""
    return (
        f"<h3 style='margin-bottom:2px'>ESO Log Tail {version}</h3>"
        f"<p style='margin-top:0'>Live fight summaries from Elder Scrolls Online "
        f"encounter logs.<br><a href='{REPO_URL}'>{REPO_URL}</a></p>"
        + (f"<p>{updates}</p>" if updates else "")
        + data_html(data) +
        f"<p><b>Credits</b></p>"
        f"<ul>"
        f"<li><b>ESO-Hub.com</b>: skill and gear set links open pages on "
        f"<a href='{ESOHUB_URL}'>ESO-Hub</a>, and the hover text names those "
        f"targets. Thanks to the ESO-Hub team for supporting community tools "
        f"that link to their site.</li>"
        f"<li><b>DPS definitions</b>: the dps time, the boss and per-target spans, "
        f"what counts as damage, the breakdown by ability and the graph's curves "
        f"follow <a href='{COMBATMETRICS_URL}'>Combat Metrics</a> by Solinur and its "
        f"<a href='{LIBCOMBAT_URL}'>LibCombat</a> library, the addon ESO players "
        f"measure dps with, so the figures here agree with it. Read from the "
        f"<a href='{COMBATMETRICS_SOURCE_URL}'>Combat Metrics source</a>; no code "
        f"is shared.</li>"
        f"<li><b>Game icons</b>: ability icons are extracted from your own game "
        f"installation. They are &copy; ZeniMax Online Studios and are not the "
        f"property of this application.</li>"
        f"<li><b>Gear set data</b>: <a href='{LIBSETS_URL}'>LibSets</a> by Baertram.</li>"
        f"<li><b>Food and drink buffs</b>: the buff list of "
        f"<a href='{LIBFOODDRINKBUFF_URL}'>LibFoodDrinkBuff</a> by Scootworks and "
        f"Baertram.</li>"
        f"<li><b>Poison names, armor weights and weapon types</b>: the ESO "
        f"item database of <a href='{UESP_URL}'>UESP</a>.</li>"
        f"<li><b>Icon extraction</b>: <a href='{EXTRACTOR_URL}'>EsoExtractData</a> "
        f"by UESP.</li>"
        f"<li><b>Turning logging on</b>: the "
        f"<a href='{EASYSTALKING_URL}'>Easy Stalking - Encounterlog</a> addon, and "
        f"<a href='{ALWAYSLOGGING_URL}'>Always Logging</a>, a simpler take on it "
        f"that logs everywhere.</li>"
        f"</ul>"
        f"<p style='color:gray'>The Elder Scrolls Online and its artwork are "
        f"&copy; ZeniMax Online Studios. ESO Log Tail is an unofficial fan tool, "
        f"not affiliated with or endorsed by ZeniMax.</p>"
    )


def show_about(parent, version: str, updates: str = "") -> None:
    QMessageBox.about(parent, "About ESO Log Tail",
                      about_html(version, updates, data_stamps()))
