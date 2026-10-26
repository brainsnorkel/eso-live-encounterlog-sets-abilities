"""
Fight history data structures shared by the engine and frontends.

FightHistoryEntry is the per-fight summary contract: everything a frontend
needs to render a completed fight. FightHistory is the session-scoped,
cursor-navigable collection of those summaries.
"""


class FightHistoryEntry:
    """Compact summary of a completed fight for frontend display."""
    __slots__ = ['timestamp', 'zone_name', 'is_vet', 'duration_s', 'group_dps',
                 'group_boss_dps', 'deaths', 'players', 'buff_summary', 'first_damage_dealer',
                 'trial_info', 'ended_at', 'boss_name', 'buff_timeline',
                 'death_recaps', 'tracked', 'dps_time_s', 'boss_dps_time_s',
                 'damage_series', 'pen_crit', 'player_names']

    def __init__(self):
        self.timestamp = ""
        self.ended_at = 0.0  # time.time() when fight ended, for elapsed timer
        self.zone_name = ""
        self.is_vet = False
        # The fight time: BEGIN_COMBAT to END_COMBAT
        self.duration_s = 0.0
        # The spans the dps figures divide by (damage_stats): first hit of
        # the group to its last, and the same for the hits on the bosses
        self.dps_time_s = 0.0
        self.boss_dps_time_s = 0.0
        # The group's damage per second of the fight for the graph window
        # (damage_stats.FightDamage.series): {'all', 'boss', 'window',
        # 'boss_window'}; None on an entry built without it
        self.damage_series = None
        self.group_dps = 0.0
        # The group's dps against the units the game flags as bosses (0 in
        # a fight without one); each player's share is their 'boss_dps'
        self.group_boss_dps = 0.0
        self.deaths = 0
        # dicts with keys: role, name, class_abbr, dps, boss_dps, dmg_pct, boss_pct (the player's
        # share of the group's damage, and of its damage to the bosses), damage (the damage
        # window's data, see damage_stats.PlayerDamage.snapshot), h, m, s, unit_id, sets,
        # skill_lines, front_bar, back_bar,
        # front_bar_slots, back_bar_slots (a slot the player taunted with carries 'taunt': True),
        # taunts (the abilities they taunted with, see ESOLogAnalyzer._taunts_of),
        # build_issues (the possible build issues behind the row's (i), see build_issues),
        # and for the build window: character, race, gear, mundus, food (see player_build.build_fields)
        self.players = []
        # Every player unit of the fight, rows or not: one dict per player
        # with name (the display name), character and is_local. The Hide
        # names mask (gui.name_mask) reads it, since a player whose build
        # never reached the log has no row above but still casts, heals
        # and dies in the fight's other data
        self.player_names = []
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
        # The tracked effects for this fight (every item of the uptime line
        # is one), one dict per rule in rule order: name, scope, kind, units
        # (what it measured: the scope, or 'mobs' in a fight without a boss),
        # uptime_pct, avg_stacks, max_stacks, mobs_reached, mobs, text (the
        # uptime line's item) and intervals (see
        # effect_rules.EffectTracker.snapshot); [] when there are no rules
        self.tracked = []
        # The group-provided penetration and critical damage of the fight
        # (pen_crit.fight_fields): the cap, the debuffs on the bosses with
        # uptime and casters, and the damage-weighted histograms; each
        # player's own part is their 'pen_crit' dict. None on an entry built
        # without it
        self.pen_crit = None


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
