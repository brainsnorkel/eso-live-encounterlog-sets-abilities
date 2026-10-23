"""
Pytest configuration and shared fixtures for ESO analyzer tests.
"""

import gc

import pytest


@pytest.fixture(autouse=True)
def _free_test_widgets_on_the_ui_thread():
    """Free the windows and widgets a test leaves behind before the next test
    starts, on the UI thread (issue #18).

    GUI tests close their windows but do not delete them, and several of the
    app's objects sat in reference cycles, so by the end of the suite about
    40 main windows and 50 fight views were still alive, waiting for Python's
    garbage collector. That frees things on whichever thread is allocating,
    and the engine threads the tests start run Python too: a collection was
    seen running on one. Had it found GUI objects, it would have freed them
    off the UI thread, the kind of fault the whole suite gave GitHub's
    Windows runner on 2026-10-15. So after each test this closes any window
    left open, which also stops its engine thread, deletes the app's
    top-level widgets, runs the queued deletions and collects the garbage
    here. Qt's own top-level widgets (tooltips, popups) are left alone."""
    yield
    try:
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if app is None:
        return
    ours = [w for w in app.topLevelWidgets() if not type(w).__module__.startswith("PySide6")]
    if not ours:
        return
    for widget in ours:
        thread = getattr(widget, "worker_thread", None)
        if widget.isVisible() or (thread is not None and thread.isRunning()):
            widget.close()
        widget.deleteLater()
    # Queued calls first (a finished engine thread hands its worker over),
    # then the deletions they and the loop above posted
    for _ in range(3):
        app.processEvents()
        app.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


@pytest.fixture
def sample_analyzer():
    """Create a sample ESOLogAnalyzer for testing."""
    from esolog_tail import ESOLogAnalyzer
    return ESOLogAnalyzer()


@pytest.fixture
def sample_encounter():
    """Create a sample CombatEncounter for testing."""
    from esolog_tail import CombatEncounter
    encounter = CombatEncounter()
    
    # Add sample players
    encounter.add_player("1", "Player1", "@player1", "117")
    encounter.add_player("2", "Player2", "@player2", "6")
    
    return encounter


@pytest.fixture
def sample_log_lines():
    """Provide sample log lines for testing."""
    return {
        'unit_added': '5,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
        'ability_info': '2928,ABILITY_INFO,84734,"Test Ability","/esoui/art/icons/ability_mage_065.dds",T,T',
        'begin_cast': '2928,BEGIN_CAST,0,F,4021667,84734,1,22762/22762,26657/26657,13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000',
        'effect_changed': '526,EFFECT_CHANGED,GAINED,1,1857418,28012,6,32417/32417,0/0,0/0,0/0,0/0,0,0.3851,0.7801,2.6373,16,52831/52831,0/0,0/0,0/0,0/0,0,0.3705,0.8056,6.0084'
    }


@pytest.fixture
def sample_abilities():
    """Provide sample ability sets for testing."""
    return {
        'templar_healer': {
            "Breath of Life", "Honor the Dead", "Healing Ritual",
            "Puncturing Sweeps", "Radiant Destruction"
        },
        'sorcerer_dps': {
            "Crystal Fragments", "Streak", "Lightning Form",
            "Hardened Ward", "Daedric Curse"
        }
    }


