"""
About dialog: version, project link, and the credits the app owes.

Kept as plain HTML so the same wording can be checked by tests and mirrored
in the README's Credits section.
"""

from PySide6.QtWidgets import QMessageBox

REPO_URL = "https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities"
ESOHUB_URL = "https://eso-hub.com"
LIBSETS_URL = "https://github.com/Baertram/LibSets"
EXTRACTOR_URL = "https://en.uesp.net/wiki/ESO_Mod:EsoExtractData"
UESP_URL = "https://en.uesp.net/wiki/Online:Online"
LIBFOODDRINKBUFF_URL = "https://www.esoui.com/downloads/info1902-LibFoodDrinkBuff.html"


def about_html(version: str) -> str:
    return (
        f"<h3 style='margin-bottom:2px'>ESO Log Tail {version}</h3>"
        f"<p style='margin-top:0'>Live fight summaries from Elder Scrolls Online "
        f"encounter logs.<br><a href='{REPO_URL}'>{REPO_URL}</a></p>"
        f"<p><b>Credits</b></p>"
        f"<ul>"
        f"<li><b>ESO-Hub.com</b>: skill and gear set links open pages on "
        f"<a href='{ESOHUB_URL}'>ESO-Hub</a>, and the hover text names those "
        f"targets. Thanks to the ESO-Hub team for supporting community tools "
        f"that link to their site.</li>"
        f"<li><b>Game icons</b>: ability icons are extracted from your own game "
        f"installation. They are &copy; ZeniMax Online Studios and are not the "
        f"property of this application.</li>"
        f"<li><b>Gear set data</b>: <a href='{LIBSETS_URL}'>LibSets</a> by Baertram.</li>"
        f"<li><b>Food and drink buffs</b>: the buff list of "
        f"<a href='{LIBFOODDRINKBUFF_URL}'>LibFoodDrinkBuff</a> by Scootworks and "
        f"Baertram.</li>"
        f"<li><b>Poison names, armor weights and restoration staves</b>: the ESO "
        f"item database of <a href='{UESP_URL}'>UESP</a>.</li>"
        f"<li><b>Icon extraction</b>: <a href='{EXTRACTOR_URL}'>EsoExtractData</a> "
        f"by UESP.</li>"
        f"</ul>"
        f"<p style='color:gray'>The Elder Scrolls Online and its artwork are "
        f"&copy; ZeniMax Online Studios. ESO Log Tail is an unofficial fan tool, "
        f"not affiliated with or endorsed by ZeniMax.</p>"
    )


def show_about(parent, version: str) -> None:
    QMessageBox.about(parent, "About ESO Log Tail", about_html(version))
