#!/usr/bin/env python3
"""Werewolf form (issue #17): the bar the log never writes, rebuilt from
casts; the share of a fight spent in form; and a Rampage in a human bar
shown as the morph it stands in for. No Qt needed.

The log's shape is from split logs of July to October 2026 (client 12.0 and
12.1): the form is the hidden effect 39038 with the morph's own effect
47083 beside it, PLAYER_INFO lists only the human bars, and the logging
player's ultimate slot reads Rampage (267416) at a pull with full Fury.
Within close range Feral Pounce is cast as Feral Carnage, and Feeding
Frenzy is Roar's synergy, which anyone in the group activates.
"""

import importlib.util
import unittest
from pathlib import Path

import werewolf
from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory
from gui.build_render import render_build_html
from gui.fight_render import anchor_tooltips, render_html, render_plain_text

EPOCH = 1759600000000
HIT, CONCEALED, KILLERS = '12345', '25267', '34843'
BERSERKER, BERSERKER_FORM, FORM, RAMPAGE = '39076', '47083', '39038', '267416'
FERAL_POUNCE, FERAL_CARNAGE, BLOODY_GNASH = '39104', '137164', '58798'
HIRCINES_RAGE, FEROCIOUS_ROAR, BLOODCLAWS = '58317', '39113', '58879'
FEEDING_FRENZY, WEREWOLF_LIGHT_ATTACK = '58775', '32464'
CALTROPS, INNER_FIRE = '40242', '39475'


def _unit(unit_id, health=20000):
    return f"{unit_id},{health}/20000,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def _boss(health=1000000):
    return f"70,{health}/1000000,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def _cast(ts, unit, ability, cast=900):
    return f"{ts},BEGIN_CAST,0,F,{cast},{ability},{_unit(unit)},{_boss()}"


def _hit(ts, unit, damage=1000):
    return f"{ts},COMBAT_EVENT,DAMAGE,PHYSICAL,1,{damage},0,900,{HIT},{_unit(unit)},{_boss()}"


def _effect(ts, change, unit, ability):
    return f"{ts},EFFECT_CHANGED,{change},1,800,{ability},{_unit(unit)},*"


def _info(ts, unit, front, back=HIT):
    return f"{ts},PLAYER_INFO,{unit},[],[],[],[{front}],[{back}]"


def _ability(ability_id, name, icon):
    return f'2600,ABILITY_INFO,{ability_id},"{name}","/esoui/art/icons/{icon}.dds",F,T'


BASE = [
    f'5,BEGIN_LOG,{EPOCH},15,"NA Megaserver","en","eso.live.12.1"',
    '1000,ZONE_CHANGED,1121,"Sunspire",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,3,9,"Tendentious","@brainsnorkel",1001,50,3230,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Templar Friend","@templar",1002,50,2547,0,PLAYER_ALLY,T',
    '2500,UNIT_ADDED,70,MONSTER,F,0,1000000,T,0,0,"Lokkestiiz","",0,50,160,0,HOSTILE,F',
    _ability(HIT, "Damage Ability", "ability_weapon_001"),
    _ability(CONCEALED, "Concealed Weapon", "ability_nightblade_014_a"),
    _ability(KILLERS, "Killer's Blade", "ability_nightblade_007_a"),
    _ability(BERSERKER, "Werewolf Berserker", "ability_werewolf_001_b"),
    _ability(BERSERKER_FORM, "Werewolf Berserker", "ability_werewolf_001_b"),
    _ability(FORM, "Werewolf Transformation", "ability_mage_065"),
    _ability(RAMPAGE, "Rampage", "achievement_u26_skyrim_werewolfdevour100"),
    # No line for Feral Pounce: the player only ever cast Feral Carnage
    _ability(FERAL_CARNAGE, "Feral Carnage", "ability_werewolf_002_a"),
    _ability(BLOODY_GNASH, "Bloody Gnash", "ability_werewolf_002_rend_b"),
    _ability(HIRCINES_RAGE, "Hircine's Rage", "ability_werewolf_004_b"),
    _ability(FEROCIOUS_ROAR, "Ferocious Roar", "ability_werewolf_003_b"),
    _ability(BLOODCLAWS, "Bloodclaws", "ability_werewolf_006_c"),
    _ability(FEEDING_FRENZY, "Feeding Frenzy", "ability_werewolf_005_b"),
    _ability(WEREWOLF_LIGHT_ATTACK, "Light Attack (Werewolf)", "death_recap_monster_melee_base"),
    _ability(CALTROPS, "Razor Caltrops", "ability_ava_003_a"),
    _ability(INNER_FIRE, "Inner Fire", "ability_undaunted_002"),
]

HUMAN_FRONT = f"{CONCEALED},{KILLERS},{BERSERKER}"

# Two fights. The player transforms half a second into the first and stays
# in form; at the second pull Fury is full and the slot reads Rampage.
FIGHTS = [
    '10000,BEGIN_COMBAT',
    _info(10001, 1, HUMAN_FRONT),
    _info(10001, 2, HIT),
    _hit(10200, 2),
    _cast(10500, 1, BERSERKER),
    _cast(10500, 1, BERSERKER_FORM),
    _effect(10500, 'GAINED', 1, FORM),
    _effect(10500, 'GAINED', 1, BERSERKER_FORM),
    _cast(12000, 1, BLOODCLAWS),
    _cast(14000, 1, FERAL_CARNAGE),
    _cast(16000, 1, HIRCINES_RAGE),
    _cast(17000, 1, WEREWOLF_LIGHT_ATTACK),
    _cast(18000, 2, FEEDING_FRENZY),
    _hit(20000, 1),
    '30000,END_COMBAT',
    '40000,BEGIN_COMBAT',
    _info(40001, 1, f"{CONCEALED},{KILLERS},{RAMPAGE}"),
    _info(40001, 2, HIT),
    _cast(45000, 1, BLOODY_GNASH),
    _cast(46000, 1, FEROCIOUS_ROAR),
    _cast(47000, 1, RAMPAGE),
    _hit(50000, 1),
    _hit(51000, 2),
    '60000,END_COMBAT',
]


def _fights(lines, base=None):
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.add_listener(RecordingListener())
    for line in (BASE if base is None else base) + lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer.fight_history.fights


def _player(fight, name):
    return next(p for p in fight.players if p['name'] == name)


def _names(slots):
    return [slot['name'] for slot in slots]


class _AllIcons:
    """Stand-in for the fight view's IconCache that has every icon."""

    def has(self, stem):
        return bool(stem)


class TestTracker(unittest.TestCase):
    """werewolf.WerewolfTracker on its own."""

    def test_the_form_effects_give_the_share_of_the_fight(self):
        tracker = werewolf.WerewolfTracker()
        tracker.note_effect('p', 'GAINED', FORM, 10000)
        tracker.note_effect('p', 'GAINED', BERSERKER_FORM, 10000)
        tracker.note_effect('p', 'FADED', FORM, 30000)
        # Still in form while the morph's effect is on
        self.assertEqual(tracker.fight_bar('p', 0, 40000).share, 0.75)
        tracker.note_effect('p', 'FADED', BERSERKER_FORM, 30000)
        self.assertEqual(tracker.fight_bar('p', 0, 40000).share, 0.5)
        self.assertIsNone(tracker.fight_bar('p', 30000, 40000))

    def test_a_form_still_on_counts_to_the_end_of_the_fight(self):
        tracker = werewolf.WerewolfTracker()
        tracker.note_effect('p', 'GAINED', FORM, 15000)
        self.assertEqual(tracker.fight_bar('p', 10000, 20000).share, 0.5)
        self.assertEqual(tracker.fight_bar('p', 30000, 40000).share, 1.0)

    def test_a_log_that_starts_in_form_counts_from_the_session_start(self):
        # No effect yet: a werewolf skill is only ever cast in form
        tracker = werewolf.WerewolfTracker()
        tracker.note_cast('p', BLOODY_GNASH, 25000)
        self.assertEqual(tracker.fight_bar('p', 20000, 30000).share, 1.0)

    def test_a_werewolf_cast_after_the_form_faded_reopens_it_from_the_cast(self):
        tracker = werewolf.WerewolfTracker()
        tracker.note_effect('p', 'GAINED', FORM, 1000)
        tracker.note_effect('p', 'FADED', FORM, 2000)
        tracker.note_cast('p', WEREWOLF_LIGHT_ATTACK, 25000)
        self.assertEqual(tracker.fight_bar('p', 20000, 30000).share, 0.5)

    def test_slots_follow_the_skill_line_and_carnage_holds_its_pounce(self):
        tracker = werewolf.WerewolfTracker()
        for ts, ability in ((1000, BLOODCLAWS), (2000, FERAL_CARNAGE), (3000, HIRCINES_RAGE),
                            (4000, FERAL_POUNCE), (5000, WEREWOLF_LIGHT_ATTACK)):
            tracker.note_cast('p', ability, ts)
        self.assertEqual(tracker.fight_bar('p', 0, 10000).skills,
                         [FERAL_POUNCE, HIRCINES_RAGE, BLOODCLAWS])

    def test_the_bar_holds_the_skills_cast_so_far_in_the_session(self):
        tracker = werewolf.WerewolfTracker()
        tracker.note_cast('p', BLOODCLAWS, 1000)
        tracker.note_cast('p', BLOODY_GNASH, 25000)
        self.assertEqual(tracker.fight_bar('p', 0, 10000).skills, [BLOODCLAWS])
        self.assertEqual(tracker.fight_bar('p', 20000, 30000).skills, [BLOODY_GNASH, BLOODCLAWS])

    def test_a_synergy_and_other_casts_are_ignored(self):
        tracker = werewolf.WerewolfTracker()
        tracker.note_cast('p', FEEDING_FRENZY, 1000)
        tracker.note_cast('p', HIT, 1000)
        self.assertIsNone(tracker.fight_bar('p', 0, 10000))

    def test_the_morph_comes_from_the_form_casts_and_bars(self):
        tracker = werewolf.WerewolfTracker()
        self.assertIsNone(tracker.morph_of('p'))
        tracker.note_bars('p', [CONCEALED, '39075'])
        self.assertEqual(tracker.morph_of('p'), '39075')
        # The morph the player transformed with outranks the bars
        tracker.note_effect('p', 'GAINED', BERSERKER_FORM, 1000)
        self.assertEqual(tracker.morph_of('p'), BERSERKER)

    def test_a_rampage_stands_in_for_the_players_morph(self):
        tracker = werewolf.WerewolfTracker()
        # Unknown player: the morph Rampage 267416 was seen for
        self.assertEqual(tracker.stand_in_for('p', RAMPAGE), BERSERKER)
        # Enduring Rampage is Pack Leader's
        self.assertEqual(tracker.stand_in_for('p', '267425'), '39075')
        # A Rampage id never seen in a slot is left alone
        self.assertIsNone(tracker.stand_in_for('p', '267417'))
        self.assertIsNone(tracker.stand_in_for('p', CONCEALED))
        tracker.note_bars('p', ['39075'])
        self.assertEqual(tracker.stand_in_for('p', '267417'), '39075')

    def test_a_new_session_forgets_everything(self):
        tracker = werewolf.WerewolfTracker()
        tracker.note_effect('p', 'GAINED', BERSERKER_FORM, 1000)
        tracker.note_cast('p', BLOODCLAWS, 2000)
        tracker.reset()
        self.assertIsNone(tracker.fight_bar('p', 0, 10000))
        self.assertIsNone(tracker.morph_of('p'))

    def test_a_logged_bar_of_werewolf_skills_is_the_werewolf_bar(self):
        self.assertTrue(werewolf.is_werewolf_bar(
            [BLOODY_GNASH, BLOODCLAWS, HIRCINES_RAGE, FEROCIOUS_ROAR, FERAL_POUNCE, BERSERKER]))
        self.assertTrue(werewolf.is_werewolf_bar(
            [{'id': BLOODY_GNASH}, {'id': BLOODCLAWS}, {'id': HIRCINES_RAGE}]))
        # The stale bar of issue #49: three werewolf skills beside two others
        self.assertTrue(werewolf.is_werewolf_bar(
            [FERAL_POUNCE, BLOODY_GNASH, CALTROPS, INNER_FIRE, BLOODCLAWS, BERSERKER]))
        # One werewolf skill on a human bar, for its while-slotted bonus
        self.assertFalse(werewolf.is_werewolf_bar([CONCEALED, '58325', BERSERKER]))
        self.assertFalse(werewolf.is_werewolf_bar([HIT]))
        self.assertFalse(werewolf.is_werewolf_bar([]))


class TestEngine(unittest.TestCase):
    """The analyzer fed a werewolf's fights."""

    def setUp(self):
        self.fights = _fights(FIGHTS)

    def test_the_werewolf_bar_is_rebuilt_in_the_skill_lines_order(self):
        first = _player(self.fights[0], '@brainsnorkel')
        slots = first['werewolf_bar_slots']
        self.assertEqual(_names(slots),
                         ['Feral Pounce', "Hircine's Rage", 'Bloodclaws', 'Werewolf Berserker'])
        self.assertTrue(all(slot['werewolf'] for slot in slots))
        self.assertTrue(slots[-1]['ultimate'])
        # The log has no line for Feral Pounce: the bundled table names it
        self.assertEqual(slots[0], {'id': FERAL_POUNCE, 'name': 'Feral Pounce',
                                    'icon': 'u50_ability_werewolf_feral_pounce', 'werewolf': True})
        # The second fight adds what was cast since
        second = _player(self.fights[1], '@brainsnorkel')
        self.assertEqual(_names(second['werewolf_bar_slots']),
                         ['Feral Pounce', "Hircine's Rage", 'Ferocious Roar', 'Bloody Gnash',
                          'Bloodclaws', 'Werewolf Berserker'])

    def test_the_share_of_each_fight_spent_in_form(self):
        self.assertAlmostEqual(_player(self.fights[0], '@brainsnorkel')['werewolf_share'], 0.975)
        self.assertEqual(_player(self.fights[1], '@brainsnorkel')['werewolf_share'], 1.0)

    def test_a_rampage_in_the_human_bar_shows_the_morph(self):
        second = _player(self.fights[1], '@brainsnorkel')
        self.assertEqual(second['front_bar_slots'][-1],
                         {'id': BERSERKER, 'name': 'Werewolf Berserker',
                          'icon': 'ability_werewolf_001_b', 'stand_in': 'Rampage'})
        self.assertEqual(second['front_bar'][-1], 'Werewolf Berserker')
        first = _player(self.fights[0], '@brainsnorkel')
        self.assertNotIn('stand_in', first['front_bar_slots'][-1])

    def test_a_player_never_in_form_gets_nothing(self):
        # Templar Friend activated the Roar synergy, which proves nothing
        for fight in self.fights:
            friend = _player(fight, '@templar')
            self.assertNotIn('werewolf_share', friend)
            self.assertNotIn('werewolf_bar_slots', friend)

    def test_a_fight_after_the_form_ended_has_no_werewolf_bar(self):
        later = FIGHTS + [
            _effect(65000, 'FADED', 1, FORM),
            _effect(65000, 'FADED', 1, BERSERKER_FORM),
            '70000,BEGIN_COMBAT',
            _info(70001, 1, HUMAN_FRONT),
            _hit(75000, 1),
            '80000,END_COMBAT',
        ]
        third = _player(_fights(later)[2], '@brainsnorkel')
        self.assertNotIn('werewolf_share', third)
        self.assertNotIn('werewolf_bar_slots', third)

    def test_a_werewolf_bar_the_log_wrote_as_the_front_bar_is_dropped(self):
        # An anonymous player's front bar logged as the werewolf bar itself,
        # in the slots' order, beside a human back bar (client 12.0)
        logged = f"{BLOODY_GNASH},{BLOODCLAWS},{HIRCINES_RAGE},{FEROCIOUS_ROAR},{FERAL_CARNAGE},{BERSERKER}"
        lines = [
            '10000,BEGIN_COMBAT',
            _info(10001, 1, logged, f"{CONCEALED},{KILLERS}"),
            _effect(10002, 'GAINED', 1, FORM),
            _cast(12000, 1, BLOODY_GNASH),
            _hit(13000, 1),
            '30000,END_COMBAT',
        ]
        player = _player(_fights(lines)[0], '@brainsnorkel')
        self.assertEqual(player['front_bar_slots'], [])
        self.assertEqual(player['front_bar'], [])
        self.assertEqual(_names(player['back_bar_slots']), ['Concealed Weapon', "Killer's Blade"])
        self.assertGreater(player['werewolf_share'], 0.9)
        # Rebuilt from the casts as for any werewolf; the morph from the logged ultimate
        self.assertEqual(_names(player['werewolf_bar_slots']), ['Bloody Gnash', 'Werewolf Berserker'])

    def test_a_stale_werewolf_bar_written_as_both_bars_is_dropped(self):
        # Issue #49: one bar as both the front and the back bar, three
        # werewolf skills beside two the player never cast, while the casts
        # show Hircine's Rage and Ferocious Roar in their place
        stale = f"{FERAL_POUNCE},{BLOODY_GNASH},{CALTROPS},{INNER_FIRE},{BLOODCLAWS},{BERSERKER}"
        lines = [
            '10000,BEGIN_COMBAT',
            _info(10001, 1, stale, stale),
            _effect(10002, 'GAINED', 1, FORM),
            _cast(12000, 1, HIRCINES_RAGE),
            _cast(13000, 1, FEROCIOUS_ROAR),
            _cast(14000, 1, BLOODY_GNASH),
            _hit(15000, 1),
            '30000,END_COMBAT',
        ]
        fight = _fights(lines)[0]
        player = _player(fight, '@brainsnorkel')
        self.assertEqual(player['front_bar_slots'], [])
        self.assertEqual(player['back_bar_slots'], [])
        self.assertEqual(_names(player['werewolf_bar_slots']),
                         ["Hircine's Rage", 'Ferocious Roar', 'Bloody Gnash', 'Werewolf Berserker'])
        text = render_plain_text(fight)
        self.assertIn("Werewolf (in form 100%): Hircine's Rage, Ferocious Roar, Bloody Gnash, "
                      "Werewolf Berserker", text)
        self.assertNotIn('Inner Fire', text)
        page = render_html(fight, detailed=True)
        self.assertIn('Werewolf</span>', page)
        self.assertNotIn('Razor Caltrops', page)
        self.assertIn('Werewolf</td>', render_build_html(fight, '1', icons=_AllIcons()))
        self.assertNotIn('>Front</td>', render_build_html(fight, '1', icons=_AllIcons()))

    def test_a_new_log_session_starts_afresh(self):
        lines = FIGHTS + BASE + [
            '70000,BEGIN_COMBAT',
            _info(70001, 1, HUMAN_FRONT),
            _hit(75000, 1),
            '80000,END_COMBAT',
        ]
        third = _player(_fights(lines)[2], '@brainsnorkel')
        self.assertNotIn('werewolf_share', third)

    def test_a_sliver_of_form_never_reads_zero(self):
        from gui.fight_render import form_share_text
        self.assertEqual(form_share_text(0.004), 'in form <1%')
        # Exactly 0.5%: the format alone would round it to 0%
        self.assertEqual(form_share_text(0.005), 'in form <1%')
        self.assertEqual(form_share_text(0.0099), 'in form <1%')
        self.assertEqual(form_share_text(0.01), 'in form 1%')
        self.assertEqual(form_share_text(0.975), 'in form 98%')
        self.assertEqual(form_share_text(1.0), 'in form 100%')


class TestRender(unittest.TestCase):
    """The werewolf bar in the fight view, the plain copy and the build window."""

    @classmethod
    def setUpClass(cls):
        cls.fights = _fights(FIGHTS)

    def test_the_plain_copy_lists_the_werewolf_bar(self):
        text = render_plain_text(self.fights[1])
        self.assertIn("      Werewolf (in form 100%): Feral Pounce, Hircine's Rage, Ferocious Roar, "
                      "Bloody Gnash, Bloodclaws, Werewolf Berserker", text)
        self.assertIn("Concealed Weapon, Killer's Blade, Werewolf Berserker", text)
        self.assertNotIn('Rampage', text)
        self.assertIn('Werewolf (in form 98%)', render_plain_text(self.fights[0]))

    def test_the_detail_view_has_a_werewolf_line(self):
        page = render_html(self.fights[1], detailed=True)
        self.assertIn('Werewolf</span>', page)
        self.assertIn('in form 100%', page)
        self.assertIn('Feral Pounce', page)

    def test_the_ultimate_sits_apart_on_a_bar_of_fewer_skills(self):
        page = render_html(self.fights[0], detailed=True, icons=_AllIcons())
        self.assertIn('src="icon:u50_ability_werewolf_feral_pounce"', page)
        # Three skills, then the gap, then Werewolf Berserker
        self.assertIn('&nbsp;&nbsp;&nbsp;&nbsp;<a href="esolog:ability/39076#werewolf-bar"', page)

    def test_hover_text_says_what_was_rebuilt_or_renamed(self):
        tips = anchor_tooltips(self.fights[1])
        self.assertIn('Listed as Rampage', tips['esolog:ability/39076#shown-as-rampage'])
        self.assertIn('rebuilt from the skills', tips[f'esolog:ability/{BLOODY_GNASH}#werewolf-bar'])
        # The plain Werewolf Berserker of a human bar keeps its plain hover
        first = anchor_tooltips(self.fights[0])
        self.assertEqual(first['esolog:ability/39076'], '<b>Werewolf Berserker</b>')

    def test_the_build_window_has_a_werewolf_row(self):
        page = render_build_html(self.fights[1], '1', icons=_AllIcons())
        self.assertIn('>Werewolf</td>', page)
        self.assertIn('in form 100%', page)
        self.assertIn('src="icon:ability_werewolf_006_c"', page)
        friend = render_build_html(self.fights[1], '2', icons=_AllIcons())
        self.assertNotIn('>Werewolf</td>', friend)


def _load_extractor():
    path = Path(__file__).resolve().parent.parent.parent / 'scripts' / 'extract_ability_icons.py'
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestIconFamilies(unittest.TestCase):
    """The icon extractor's default families take the werewolf icons."""

    def test_update_named_skill_icons_and_rampage_are_extracted(self):
        extractor = _load_extractor()
        names = ['ability_werewolf_006_c.dds', 'u50_ability_werewolf_feral_pounce.dds',
                 'u50_antiquity_thievesboard.dds', 'achievement_u26_skyrim_werewolfdevour100.dds',
                 'achievement_u26_skyrim_werewolfdevour10.dds', 'u38_ability_armor_ultimatetransfer.dds',
                 'death_recap_melee_basic.dds', 'gear_dromathra_medium_head_a.dds']
        rows = [(index, 100, extractor.ICON_DIR + name) for index, name in enumerate(names)]
        wanted = extractor.icon_positions(rows, extractor.DEFAULT_PREFIXES, extractor.DEFAULT_STEMS,
                                          (extractor.UPDATE_ICON_PATTERN,))
        self.assertEqual([names[i] for i in wanted],
                         ['ability_werewolf_006_c.dds', 'u50_ability_werewolf_feral_pounce.dds',
                          'achievement_u26_skyrim_werewolfdevour100.dds',
                          'u38_ability_armor_ultimatetransfer.dds', 'death_recap_melee_basic.dds'])

    def test_the_bundled_names_and_icons_cover_every_slot_skill(self):
        for skill in set(werewolf.SLOT_SKILLS.values()) | set(werewolf.TRANSFORMATIONS):
            name, icon = werewolf.SKILLS[skill]
            self.assertTrue(name and icon, skill)
        self.assertEqual(set(werewolf.LINE_POSITION), set(werewolf.SLOT_SKILLS.values()))


if __name__ == '__main__':
    unittest.main()
