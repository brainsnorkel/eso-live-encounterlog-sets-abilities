"""
Fight history data structures shared by the engine and frontends.

FightHistoryEntry is the per-fight summary contract: everything a frontend
needs to render a completed fight. FightHistory is the session-scoped,
cursor-navigable collection of those summaries.
"""


class FightHistoryEntry:
    """Compact summary of a completed fight for frontend display."""
    __slots__ = ['timestamp', 'zone_name', 'is_vet', 'duration_s', 'group_dps',
                 'deaths', 'players', 'buff_summary', 'first_damage_dealer',
                 'trial_info', 'ended_at', 'boss_name', 'buff_timeline',
                 'death_recaps']

    def __init__(self):
        self.timestamp = ""
        self.ended_at = 0.0  # time.time() when fight ended, for elapsed timer
        self.zone_name = ""
        self.is_vet = False
        self.duration_s = 0.0
        self.group_dps = 0.0
        self.deaths = 0
        # dicts with keys: role, name, class_abbr, dps, dmg_pct, h, m, s, unit_id, sets, skill_lines, front_bar, back_bar,
        # front_bar_slots, back_bar_slots (a slot the player taunted with carries 'taunt': True),
        # taunts (the abilities they taunted with, see ESOLogAnalyzer._taunts_of),
        # and for the build window: character, race, gear, mundus, food (see player_build.build_fields)
        self.players = []
        self.buff_summary = ""
        self.first_damage_dealer = None
        self.trial_info = None
        self.boss_name = ""
        # EXPERIMENTAL: {'duration_ms', 'effects': {name: [interval, ...]}}
        # or None when the buff-timeline experiment is off (the default)
        self.buff_timeline = None
        # One dict per player death, in order (len == deaths): unit_id, name,
        # time_ms (into the fight), killer, ability, ability_id, icon,
        # max_health, and events: the last seconds before the death, oldest
        # first (see death_recap.py for the row keys)
        self.death_recaps = []


class FightHistory:
    """Unbounded list of completed fight summaries."""

    def __init__(self):
        self.fights = []
        self.cursor = 0
        self._live = True

    def append(self, entry: FightHistoryEntry):
        self.fights.append(entry)
        if self._live:
            self.cursor = len(self.fights) - 1

    def current(self):
        if not self.fights:
            return None
        if self._live:
            return self.fights[-1]
        return self.fights[self.cursor]

    def scroll_up(self):
        if not self.fights:
            return
        # Single-entry history: nothing to scroll to, stay live
        if len(self.fights) <= 1:
            return
        if self._live:
            self._live = False
            self.cursor = len(self.fights) - 2
        elif self.cursor > 0:
            self.cursor -= 1

    def scroll_down(self):
        if not self.fights:
            return
        if self._live:
            return
        if self.cursor < len(self.fights) - 1:
            self.cursor += 1
        if self.cursor == len(self.fights) - 1:
            self._live = True

    def snap_to_latest(self):
        self._live = True
        if self.fights:
            self.cursor = len(self.fights) - 1

    @property
    def is_live(self):
        return self._live

    @property
    def display_index(self):
        if self.cursor == -1:
            return len(self.fights)
        return self.cursor + 1

    @property
    def total(self):
        return len(self.fights)
