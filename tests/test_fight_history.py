"""Tests for FightHistory ring buffer."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from esolog_tail import FightHistory, FightHistoryEntry


def _make_entry(zone="Test Zone"):
    e = FightHistoryEntry()
    e.zone_name = zone
    return e


def test_append_and_current():
    h = FightHistory(max_size=5)
    h.append(_make_entry("Zone1"))
    assert h.current().zone_name == "Zone1"
    assert h.is_live


def test_scroll_up_down():
    h = FightHistory()
    for i in range(5):
        h.append(_make_entry(f"Zone{i}"))
    assert h.current().zone_name == "Zone4"
    h.scroll_up()
    assert h.current().zone_name == "Zone3"
    assert not h.is_live
    h.scroll_down()
    assert h.current().zone_name == "Zone4"
    assert h.is_live


def test_snap_to_latest():
    h = FightHistory()
    for i in range(5):
        h.append(_make_entry(f"Zone{i}"))
    h.scroll_up()
    h.scroll_up()
    assert h.current().zone_name == "Zone2"
    h.snap_to_latest()
    assert h.current().zone_name == "Zone4"
    assert h.is_live


def test_cap_at_max():
    h = FightHistory(max_size=3)
    for i in range(5):
        h.append(_make_entry(f"Zone{i}"))
    assert h.total == 3
    assert h.fights[0].zone_name == "Zone2"


def test_auto_advance_in_live():
    h = FightHistory()
    h.append(_make_entry("Zone1"))
    assert h.is_live
    h.append(_make_entry("Zone2"))
    assert h.current().zone_name == "Zone2"
    assert h.is_live


def test_no_auto_advance_when_scrolled():
    h = FightHistory()
    for i in range(3):
        h.append(_make_entry(f"Zone{i}"))
    h.scroll_up()  # Now viewing Zone1
    h.append(_make_entry("Zone3"))
    # Should NOT auto-advance
    assert h.current().zone_name == "Zone1"
    assert not h.is_live


def test_display_index():
    h = FightHistory()
    for i in range(3):
        h.append(_make_entry(f"Zone{i}"))
    assert h.display_index == 3
    h.scroll_up()
    assert h.display_index == 2


def test_empty_history():
    h = FightHistory()
    assert h.current() is None
    assert h.total == 0
    h.scroll_up()  # Should not crash
    h.scroll_down()


def test_overflow_while_scrolled_preserves_view():
    """Regression: when buffer evicts entries while cursor is non-live,
    the viewed entry should not silently shift (bead 47e)."""
    h = FightHistory(max_size=3)
    for i in range(3):
        h.append(_make_entry(f"Zone{i}"))
    # Buffer: [Zone0, Zone1, Zone2], cursor live at Zone2
    h.scroll_up()  # Viewing Zone1
    assert h.current().zone_name == "Zone1"
    assert not h.is_live

    # Overflow: append Zone3 -> evicts Zone0
    # Buffer becomes [Zone1, Zone2, Zone3], cursor should still point at Zone1
    h.append(_make_entry("Zone3"))
    assert h.current().zone_name == "Zone1", (
        f"Expected still viewing Zone1 after overflow, got {h.current().zone_name}"
    )
    assert not h.is_live

    # Overflow again: evicts Zone1 (what we were viewing)
    # Buffer becomes [Zone2, Zone3, Zone4], cursor should clamp, not wrap to live
    h.append(_make_entry("Zone4"))
    assert not h.is_live, "Should not silently return to live mode after eviction"
    # Cursor clamped to 0 (oldest remaining entry)
    assert h.current().zone_name == "Zone2"


def test_overflow_during_live_mode_stays_live():
    """Live mode should remain live through buffer overflow."""
    h = FightHistory(max_size=3)
    for i in range(10):
        h.append(_make_entry(f"Zone{i}"))
    assert h.is_live
    assert h.current().zone_name == "Zone9"
    assert h.total == 3
