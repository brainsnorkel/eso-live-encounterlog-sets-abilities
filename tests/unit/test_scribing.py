#!/usr/bin/env python3
"""Scribed skills: script fields on ABILITY_INFO, tying them to players, and
how the fight pane presents them (no Qt needed)."""

import os
import unittest

from ability_icons import (  # noqa: E402
    esohub_ability_url, esohub_scribed_skill_url, esohub_script_url)
from scribing import (  # noqa: E402
    GRIMOIRES, ScribedSkill, ScribingTracker, scribed_label, slot_fields, slot_label)

BANNER_ICON = 'ability_grimoire_support'
SOUL_ICON = 'ability_grimoire_soulmagic1'
SHOCKING = ScribedSkill('Shocking Banner', BANNER_ICON, 'Shock Damage', 'Class Flourish', 'Heroism')
FORTIFYING = ScribedSkill('Fortifying Banner', BANNER_ICON, 'Mitigation', "Warmage's Defense", 'Resolve')

GEAR = '[[HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,MAGICKA,T,16,LEGENDARY]]'
HIT = ('COMBAT_EVENT,DAMAGE,PHYSICAL,1,{dmg},0,4021667,12345,{unit},22762/22762,26657/26657,'
       '13021/13021,500/500,1000/1000,0,0.2696,0.5942,5.5492,70,105634/105634,0/0,0/0,0/0,0/0,'
       '0,0.4081,0.5662,0.0256')


def _banner(ms, name, focus, signature, affix):
    return (f'{ms},ABILITY_INFO,217699,"{name}","/esoui/art/icons/ability_grimoire_support.dds",'
            f'F,T,"{focus}","{signature}","{affix}"')


# Two fights in one session. Ada, Bren and Cy slot the same Banner Bearer
# ability id: Ada's and Bren's script combinations are new to the log, so the
# game writes them before their PLAYER_INFO; Cy's is not (it matches one
# already written). Before the second fight Bren has scribed a new banner.
SESSION = [
    '1000,BEGIN_LOG,1759600000000,15,"NA Megaserver","en","eso.live.11.2"',
    '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
    '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Ada Quill","@ada",1001,50,2000,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,2,PLAYER,F,2,0,F,6,1,"Bren Ward","@bren",1002,50,2000,0,PLAYER_ALLY,T',
    '2000,UNIT_ADDED,3,PLAYER,F,3,0,F,3,1,"Cy Marrow","@cy",1003,50,2000,0,PLAYER_ALLY,T',
    '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
    '9990,BEGIN_COMBAT',
    '9990,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    _banner(9990, 'Shocking Banner', 'Shock Damage', 'Class Flourish', 'Heroism'),
    '9990,ABILITY_INFO,217784,"Leashing Soul","/esoui/art/icons/ability_grimoire_soulmagic1.dds",'
    'F,T,"Pull","Druid\'s Resurgence","Cowardice"',
    f'9991,PLAYER_INFO,1,[45549],[1],{GEAR},[12345,217699],[217784,217699]',
    _banner(9991, 'Fortifying Banner', 'Mitigation', "Warmage's Defense", 'Resolve'),
    f'9991,PLAYER_INFO,2,[45549],[1],{GEAR},[12345,217699],[12345]',
    f'9991,PLAYER_INFO,3,[45549],[1],{GEAR},[12345,217699],[217784]',
    '11000,' + HIT.format(dmg=90000, unit=1),
    '21000,' + HIT.format(dmg=60000, unit=2),
    '31000,' + HIT.format(dmg=30000, unit=3),
    '70000,END_COMBAT',
    '100000,BEGIN_COMBAT',
    f'100000,PLAYER_INFO,1,[45549],[1],{GEAR},[12345,217699],[217784,217699]',
    _banner(100000, 'Shocking Banner', 'Shock Damage', "Cavalier's Charge", 'Brutality'),
    f'100000,PLAYER_INFO,2,[45549],[1],{GEAR},[12345,217699],[12345]',
    f'100000,PLAYER_INFO,3,[45549],[1],{GEAR},[12345,217699],[217784]',
    '101000,' + HIT.format(dmg=60000, unit=1),
    '111000,' + HIT.format(dmg=15000, unit=2),
    '130000,END_COMBAT',
]


def _fights(lines):
    from esolog_tail import ESOLogAnalyzer
    from fight_history import FightHistory
    analyzer = ESOLogAnalyzer()
    analyzer.fight_history = FightHistory()
    analyzer.current_log_file = 'Encounter.log'
    for line in lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)
    return analyzer.fight_history.fights


def _player(fight, handle):
    return next(p for p in fight.players if p['name'] == handle)


def _slot(player, ability_id, bar='front_bar_slots'):
    return next(s for s in player[bar] if s['id'] == ability_id)


class TestAbilityInfoScripts(unittest.TestCase):

    def test_scribed_line_carries_focus_signature_affix(self):
        from eso_log_structures import AbilityInfoEntry
        parsed = AbilityInfoEntry.parse(
            '2408,ABILITY_INFO,217784,"Leashing Soul",'
            '"/esoui/art/icons/ability_grimoire_soulmagic1.dds",F,T,"Pull","Druid\'s Resurgence","Maim"')
        self.assertEqual(parsed.scribing, ('Pull', "Druid's Resurgence", 'Maim'))
        self.assertEqual(parsed.ability_name, 'Leashing Soul')
        # The icon is still field 4, not the last quoted field
        self.assertTrue(parsed.icon_path.endswith('ability_grimoire_soulmagic1.dds'))

    def test_ordinary_ability_has_no_scripts(self):
        from eso_log_structures import AbilityInfoEntry
        parsed = AbilityInfoEntry.parse(
            '2928,ABILITY_INFO,84734,"Witchfest Food: Max HM, Reg M",'
            '"/esoui/art/icons/ability_mage_065.dds",T,T')
        self.assertIsNone(parsed.scribing)
        self.assertEqual(parsed.ability_name, 'Witchfest Food: Max HM, Reg M')

    def test_scripts_reach_the_legacy_entry(self):
        from eso_log_parser import ESOLogParser
        parser = ESOLogParser()
        entry = parser.parse_line(_banner(9990, 'Shocking Banner', 'Shock Damage',
                                          'Class Flourish', 'Heroism'))
        parsed = parser.parse_ability_info(entry)
        self.assertEqual(parsed.scribing, ('Shock Damage', 'Class Flourish', 'Heroism'))
        self.assertEqual(parsed.timestamp, 9990)


class TestScribingTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = ScribingTracker()

    def _note(self, skill, ability_id='217699', at_ms=100):
        self.tracker.note_ability(ability_id, skill.name, skill.icon,
                                  (skill.focus, skill.signature, skill.affix), at_ms)

    def test_combination_belongs_to_the_player_info_that_follows(self):
        self._note(SHOCKING)
        self.assertEqual(self.tracker.resolve('@ada+Ada', ['1', '217699'], 100),
                         {'217699': SHOCKING})
        # Same ability id, another player, another focus script: another skill
        self._note(FORTIFYING, at_ms=101)
        self.assertEqual(self.tracker.resolve('@bren+Bren', ['217699'], 101),
                         {'217699': FORTIFYING})
        # Later PLAYER_INFO lines come without a new ABILITY_INFO
        self.assertEqual(self.tracker.resolve('@ada+Ada', ['217699'], 5000)['217699'], SHOCKING)
        self.assertEqual(self.tracker.resolve('@bren+Bren', ['217699'], 5000)['217699'], FORTIFYING)

    def test_combination_is_not_handed_to_the_next_player(self):
        self._note(SHOCKING)
        self.tracker.resolve('@ada+Ada', ['217699'], 100)
        self._note(FORTIFYING, at_ms=101)
        # Bren does not slot the banner: the pending line is not kept for Cy
        self.assertEqual(self.tracker.resolve('@bren+Bren', ['12345'], 101), {})
        self.assertEqual(self.tracker.resolve('@cy+Cy', ['217699'], 101)['217699'],
                         (SHOCKING, FORTIFYING))

    def test_rescribed_skill_replaces_the_players_combination(self):
        self._note(SHOCKING)
        self.tracker.resolve('@ada+Ada', ['217699'], 100)
        changed = SHOCKING._replace(signature="Cavalier's Charge", affix='Brutality')
        self._note(changed, at_ms=9000)
        self.assertEqual(self.tracker.resolve('@ada+Ada', ['217699'], 9000)['217699'], changed)

    def test_player_without_a_line_gets_the_only_known_combination(self):
        self._note(SHOCKING)
        self.tracker.resolve('@ada+Ada', ['217699'], 100)
        self.assertEqual(self.tracker.resolve('@cy+Cy', ['217699'], 101)['217699'], SHOCKING)

    def test_player_without_a_line_gets_options_when_several_are_known(self):
        self._note(SHOCKING)
        self.tracker.resolve('@ada+Ada', ['217699'], 100)
        self._note(FORTIFYING, at_ms=101)
        self.tracker.resolve('@bren+Bren', ['217699'], 101)
        options = self.tracker.resolve('@cy+Cy', ['217699'], 101)['217699']
        self.assertEqual(options, (SHOCKING, FORTIFYING))
        # A combination first written for someone later is not Cy's
        third = SHOCKING._replace(affix='Berserk')
        self._note(third, at_ms=9000)
        self.tracker.resolve('@dag+Dag', ['217699'], 9000)
        self.assertEqual(self.tracker.resolve('@cy+Cy', ['217699'], 9000)['217699'], options)

    def test_line_written_long_before_a_player_info_is_not_theirs(self):
        self._note(SHOCKING, at_ms=100)
        self._note(FORTIFYING, at_ms=101)  # e.g. cast by an ungrouped player
        resolved = self.tracker.resolve('@cy+Cy', ['217699'], 60000)['217699']
        self.assertEqual(resolved, (SHOCKING, FORTIFYING))

    def test_reset_and_forget(self):
        self._note(SHOCKING)
        self.tracker.resolve('unit:7', ['217699'], 100)
        self._note(FORTIFYING, at_ms=101)
        self.tracker.resolve('@bren+Bren', ['217699'], 101)
        self.tracker.forget_players('unit:')
        # Unit 7 is someone else after a zone change; Bren is still Bren
        self.assertEqual(self.tracker.resolve('unit:7', ['217699'], 500)['217699'],
                         (SHOCKING, FORTIFYING))
        self.assertEqual(self.tracker.resolve('@bren+Bren', ['217699'], 500)['217699'], FORTIFYING)
        self.tracker.reset()
        self.assertEqual(self.tracker.resolve('@bren+Bren', ['217699'], 600), {})

    def test_malformed_scripts_are_ignored(self):
        self.tracker.note_ability('217699', 'Shocking Banner', BANNER_ICON, ('Shock Damage',), 100)
        self.assertEqual(self.tracker.resolve('@ada+Ada', ['217699'], 100), {})

    def test_ordinary_abilities_are_not_tracked(self):
        self.tracker.note_ability('26792', 'Biting Jabs', 'ability_templar_trained_attacker', None, 100)
        self.assertEqual(self.tracker.resolve('@ada+Ada', ['26792'], 100), {})


class TestLinesWithoutScripts(unittest.TestCase):
    """The game also writes grimoire skills as ordinary seven-field lines."""

    PLAIN = ScribedSkill('Shocking Banner', BANNER_ICON)

    def setUp(self):
        self.tracker = ScribingTracker()

    def _note(self, skill, at_ms):
        scripts = (skill.focus, skill.signature, skill.affix) if skill.scripts_known else None
        self.tracker.note_ability('217699', skill.name, skill.icon, scripts, at_ms)

    def test_line_before_a_player_info_means_their_scripts_are_unknown(self):
        self._note(self.PLAIN, 100)
        self.assertEqual(self.tracker.resolve('ada', ['217699'], 100), {'217699': self.PLAIN})
        self.assertFalse(self.PLAIN.scripts_known)
        self.assertEqual(self.tracker.resolve('ada', ['217699'], 5000)['217699'], self.PLAIN)
        # The scripts follow once the game has them
        self._note(SHOCKING, 9000)
        self.assertEqual(self.tracker.resolve('ada', ['217699'], 9000)['217699'], SHOCKING)

    def test_line_without_scripts_does_not_replace_known_scripts(self):
        self._note(SHOCKING, 100)
        self.tracker.resolve('ada', ['217699'], 100)
        self._note(self.PLAIN, 9000)
        self.assertEqual(self.tracker.resolve('ada', ['217699'], 9000)['217699'], SHOCKING)

    def test_later_player_may_be_the_one_without_scripts(self):
        self._note(SHOCKING, 100)
        self.tracker.resolve('ada', ['217699'], 100)
        # Written when the skill was first used, not for a PLAYER_INFO
        self._note(self.PLAIN, 30000)
        # Bren got no line: the same scripts as Ada, or scripts the game lacks
        self.assertEqual(self.tracker.resolve('bren', ['217699'], 60000)['217699'],
                         (SHOCKING, self.PLAIN))

    def test_later_player_with_only_a_scriptless_line_known(self):
        self._note(self.PLAIN, 30000)
        self.assertEqual(self.tracker.resolve('bren', ['217699'], 60000)['217699'], self.PLAIN)

    def test_before_the_skill_is_used_one_known_combination_is_certain(self):
        self._note(SHOCKING, 100)
        self.tracker.resolve('ada', ['217699'], 100)
        self.assertEqual(self.tracker.resolve('bren', ['217699'], 100)['217699'], SHOCKING)


class TestSlotFields(unittest.TestCase):

    def test_known_combination(self):
        self.assertEqual(slot_fields(SHOCKING), {
            'scribed': True, 'name': 'Shocking Banner', 'icon': BANNER_ICON,
            'grimoire': 'Banner Bearer',
            'scripts': ['Shock Damage', 'Class Flourish', 'Heroism']})

    def test_skill_written_without_scripts(self):
        self.assertEqual(slot_fields(ScribedSkill('Warding Soul', SOUL_ICON)), {
            'scribed': True, 'name': 'Warding Soul', 'icon': SOUL_ICON, 'grimoire': 'Wield Soul'})
        options = slot_fields((SHOCKING, ScribedSkill('Shocking Banner', BANNER_ICON)))
        self.assertEqual(options['script_options'][1], ['Shocking Banner', '', '', ''])
        self.assertEqual(options['name'], 'Shocking Banner')

    def test_options_with_different_names_fall_back_to_the_grimoire(self):
        fields = slot_fields((SHOCKING, FORTIFYING))
        self.assertEqual(fields['name'], 'Banner Bearer')
        self.assertNotIn('scripts', fields)
        self.assertEqual(fields['script_options'], [
            ['Shocking Banner', 'Shock Damage', 'Class Flourish', 'Heroism'],
            ['Fortifying Banner', 'Mitigation', "Warmage's Defense", 'Resolve']])

    def test_options_sharing_a_name_keep_it(self):
        other = SHOCKING._replace(affix='Berserk')
        self.assertEqual(slot_fields((SHOCKING, other))['name'], 'Shocking Banner')

    def test_unknown_grimoire_icon_keeps_the_logged_name(self):
        new = ScribedSkill('Odd Skill', 'ability_grimoire_new', 'Stun', 'A', 'B')
        self.assertEqual(slot_fields(new)['grimoire'], '')
        self.assertNotIn('name', slot_fields((new, new._replace(name='Other Skill'))))

    def test_labels(self):
        self.assertEqual(scribed_label('Shocking Banner', ['Shock Damage', 'Class Flourish', 'Heroism']),
                         'Shocking Banner (Class Flourish / Heroism)')
        self.assertEqual(scribed_label('Biting Jabs', None), 'Biting Jabs')
        self.assertEqual(slot_label({'name': 'Biting Jabs'}), 'Biting Jabs')
        self.assertEqual(slot_label(dict(slot_fields(SHOCKING), id='217699')),
                         'Shocking Banner (Class Flourish / Heroism)')
        self.assertEqual(slot_label(slot_fields((SHOCKING, FORTIFYING))), 'Banner Bearer')

    def test_every_bundled_grimoire_icon_has_a_name(self):
        icons = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'icons', 'abilities')
        bundled = {name[:-4] for name in os.listdir(icons) if name.startswith('ability_grimoire_')}
        self.assertEqual(bundled, set(GRIMOIRES))


class TestScribedSkillsFromEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fights = _fights(SESSION)

    def test_each_player_gets_their_own_name_and_scripts(self):
        self.assertEqual(len(self.fights), 2)
        fight = self.fights[0]
        ada = _slot(_player(fight, '@ada'), '217699')
        self.assertEqual(ada['name'], 'Shocking Banner')
        self.assertEqual(ada['scripts'], ['Shock Damage', 'Class Flourish', 'Heroism'])
        self.assertEqual(ada['grimoire'], 'Banner Bearer')
        self.assertEqual(ada['icon'], BANNER_ICON)
        # Same ability id on Bren's bar is a different skill
        bren = _slot(_player(fight, '@bren'), '217699')
        self.assertEqual(bren['name'], 'Fortifying Banner')
        self.assertEqual(bren['scripts'], ['Mitigation', "Warmage's Defense", 'Resolve'])
        # Name lists follow the slots, and ordinary skills are untouched
        self.assertEqual(_player(fight, '@ada')['front_bar'], ['Damage Ability', 'Shocking Banner'])
        self.assertEqual(_player(fight, '@bren')['front_bar'], ['Damage Ability', 'Fortifying Banner'])
        self.assertNotIn('scripts', _slot(_player(fight, '@ada'), '12345'))

    def test_skill_on_both_bars_resolves_on_both(self):
        ada = _player(self.fights[0], '@ada')
        self.assertEqual(_slot(ada, '217699', 'back_bar_slots')['scripts'],
                         ['Shock Damage', 'Class Flourish', 'Heroism'])
        self.assertEqual(_slot(ada, '217784', 'back_bar_slots')['scripts'],
                         ['Pull', "Druid's Resurgence", 'Cowardice'])

    def test_player_without_a_line_of_their_own(self):
        cy = _player(self.fights[0], '@cy')
        banner = _slot(cy, '217699')
        # Two banners are known and Cy's is one of them: no name, no scripts
        self.assertEqual(banner['name'], 'Banner Bearer')
        self.assertNotIn('scripts', banner)
        self.assertEqual([option[0] for option in banner['script_options']],
                         ['Shocking Banner', 'Fortifying Banner'])
        self.assertEqual(cy['front_bar'], ['Damage Ability', 'Banner Bearer'])
        # One Wield Soul combination is known, so it is Cy's
        soul = _slot(cy, '217784', 'back_bar_slots')
        self.assertEqual(soul['name'], 'Leashing Soul')
        self.assertEqual(soul['scripts'], ['Pull', "Druid's Resurgence", 'Cowardice'])
        self.assertEqual(soul['grimoire'], 'Wield Soul')

    def test_rescribing_between_fights(self):
        second = self.fights[1]
        bren = _slot(_player(second, '@bren'), '217699')
        self.assertEqual(bren['name'], 'Shocking Banner')
        self.assertEqual(bren['scripts'], ['Shock Damage', "Cavalier's Charge", 'Brutality'])
        # The others keep theirs, and the first fight's entry is not rewritten
        self.assertEqual(_slot(_player(second, '@ada'), '217699')['scripts'],
                         ['Shock Damage', 'Class Flourish', 'Heroism'])
        self.assertEqual([o[0] for o in _slot(_player(second, '@cy'), '217699')['script_options']],
                         ['Shocking Banner', 'Fortifying Banner'])
        self.assertEqual(_slot(_player(self.fights[0], '@bren'), '217699')['name'],
                         'Fortifying Banner')

    def test_anonymous_player_keeps_scripts_across_zones(self):
        """Unit ids change with the zone; the per-session player id does not."""
        def anonymous(unit, session_id):
            return f'2000,UNIT_ADDED,{unit},PLAYER,F,{session_id},0,F,2,1,"","",0,50,2000,0,PLAYER_ALLY,T'
        ada = '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Ada Quill","@ada",1001,50,2000,0,PLAYER_ALLY,T'
        boss = '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F'
        bars = f'[45549],[1],{GEAR},[12345,217699],[12345]'
        fights = _fights([
            '1000,BEGIN_LOG,1759600000000,15,"NA Megaserver","en","eso.live.11.2"',
            '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
            ada, anonymous(5, 7), boss,
            '9990,BEGIN_COMBAT',
            '9990,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
            _banner(9990, 'Shocking Banner', 'Shock Damage', 'Class Flourish', 'Heroism'),
            f'9991,PLAYER_INFO,1,{bars}',
            _banner(9991, 'Fortifying Banner', 'Mitigation', "Warmage's Defense", 'Resolve'),
            f'9991,PLAYER_INFO,5,{bars}',
            '11000,' + HIT.format(dmg=90000, unit=1),
            '12000,' + HIT.format(dmg=50000, unit=5),
            '70000,END_COMBAT',
            # Next zone: the anonymous player is unit 9 now, and unit 5 is
            # someone else
            '80000,ZONE_CHANGED,1302,"Shipwright\'s Regret",VETERAN',
            ada, anonymous(9, 7), anonymous(5, 8), boss,
            '100000,BEGIN_COMBAT',
            f'100000,PLAYER_INFO,1,{bars}',
            f'100000,PLAYER_INFO,9,{bars}',
            f'100000,PLAYER_INFO,5,{bars}',
            '101000,' + HIT.format(dmg=60000, unit=1),
            '102000,' + HIT.format(dmg=50000, unit=9),
            '103000,' + HIT.format(dmg=40000, unit=5),
            '130000,END_COMBAT',
        ])
        self.assertEqual(len(fights), 2)
        by_unit = {p['unit_id']: p for p in fights[1].players}
        self.assertEqual(_slot(by_unit['9'], '217699')['scripts'],
                         ['Mitigation', "Warmage's Defense", 'Resolve'])
        self.assertEqual(_slot(by_unit['5'], '217699')['name'], 'Banner Bearer')
        self.assertIn('script_options', _slot(by_unit['5'], '217699'))

    def test_another_character_on_the_same_session_id_starts_over(self):
        from esolog_tail import ESOLogAnalyzer
        analyzer = ESOLogAnalyzer()
        scribing = analyzer.scribing
        analyzer._note_scribing_identity('2', '13', '111')
        scribing.note_ability('217699', *SHOCKING[:2], SHOCKING[2:], 100)
        scribing.resolve(analyzer._scribing_player_key('2'), ['217699'], 100)
        scribing.note_ability('217699', *FORTIFYING[:2], FORTIFYING[2:], 101)
        scribing.resolve('session:99', ['217699'], 101)
        # Same character under a new unit id: still theirs
        analyzer._note_scribing_identity('8', '13', '111')
        self.assertEqual(scribing.resolve(analyzer._scribing_player_key('8'), ['217699'], 500),
                         {'217699': SHOCKING})
        # The player relogs to another character
        analyzer._note_scribing_identity('4', '13', '222')
        self.assertEqual(scribing.resolve(analyzer._scribing_player_key('4'), ['217699'], 900),
                         {'217699': (SHOCKING, FORTIFYING)})
        # A unit the log never introduced falls back to its unit id
        self.assertEqual(analyzer._scribing_player_key('77'), 'unit:77')

    def test_scripts_missing_in_one_fight_arrive_in_the_next(self):
        """A skill the game first writes without scripts, then with them."""
        soul = '{ms},ABILITY_INFO,216802,"Warding Soul","/esoui/art/icons/ability_grimoire_soulmagic1.dds",F,T'
        bars = f'[45549],[1],{GEAR},[12345,216802],[12345]'
        fights = _fights([
            '1000,BEGIN_LOG,1759600000000,15,"NA Megaserver","en","eso.live.11.2"',
            '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
            '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Ada Quill","@ada",1001,50,2000,0,PLAYER_ALLY,T',
            '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
            '9990,BEGIN_COMBAT',
            '9990,ABILITY_INFO,12345,"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
            soul.format(ms=9990),
            f'9991,PLAYER_INFO,1,{bars}',
            '11000,' + HIT.format(dmg=90000, unit=1),
            '70000,END_COMBAT',
            '100000,BEGIN_COMBAT',
            soul.format(ms=100000) + ',"Damage Shield","Sage\'s Remedy","Resolve"',
            f'100000,PLAYER_INFO,1,{bars}',
            '101000,' + HIT.format(dmg=60000, unit=1),
            '130000,END_COMBAT',
        ])
        first = _slot(_player(fights[0], '@ada'), '216802')
        self.assertEqual((first['name'], first['grimoire'], first['scribed']),
                         ('Warding Soul', 'Wield Soul', True))
        self.assertNotIn('scripts', first)
        self.assertNotIn('script_options', first)
        self.assertEqual(_slot(_player(fights[1], '@ada'), '216802')['scripts'],
                         ['Damage Shield', "Sage's Remedy", 'Resolve'])
        # The fight pane says so instead of showing a bare grimoire icon
        from gui.fight_render import anchor_tooltips, render_html, render_plain_text
        self.assertIn('>Warding Soul</a> (scripts not in log)',
                      render_html(fights[0], detailed=True, icons=_Icons()))
        tip = anchor_tooltips(fights[0])['esolog:ability/216802#scripts-unknown']
        self.assertIn('<b>Warding Soul</b><br>Grimoire: Wield Soul<br>'
                      'The log has this skill without its scripts.', tip)
        self.assertIn('      Damage Ability, Warding Soul\n', render_plain_text(fights[0]))

    def test_new_session_starts_over(self):
        again = SESSION + [
            '140000,END_LOG',
            '1000,BEGIN_LOG,1759700000000,15,"NA Megaserver","en","eso.live.11.2"',
            '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
            '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Ada Quill","@ada",1001,50,2000,0,PLAYER_ALLY,T',
            '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
            '9990,BEGIN_COMBAT',
            _banner(9990, 'Magical Banner', 'Magic Damage', "Sage's Remedy", 'Breach'),
            f'9991,PLAYER_INFO,1,[45549],[1],{GEAR},[12345,217699],[12345]',
            '11000,' + HIT.format(dmg=90000, unit=1),
            '70000,END_COMBAT',
        ]
        fights = _fights(again)
        self.assertEqual(len(fights), 3)
        banner = _slot(_player(fights[2], '@ada'), '217699')
        self.assertEqual(banner['name'], 'Magical Banner')
        self.assertEqual(banner['scripts'], ['Magic Damage', "Sage's Remedy", 'Breach'])


class _Icons:
    """Stand-in for the fight view's IconCache."""

    def has(self, stem):
        return stem.startswith('ability_grimoire_')


def _links(name):
    return {'Shocking Banner': 'https://eso-hub.com/en/scribing/combination/93/shocking-banner',
            'Banner Bearer': 'https://eso-hub.com/en/skills/alliance-war/support/banner-bearer',
            }.get(name)


def _script_links(name):
    return {'Class Flourish': 'https://eso-hub.com/en/scribing/scripts/class-mastery',
            'Heroism': 'https://eso-hub.com/en/scribing/scripts/heroism'}.get(name)


class TestScribedSkillRendering(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fight = _fights(SESSION)[0]

    def _html(self, **kwargs):
        from gui.fight_render import render_html
        return render_html(self.fight, detailed=True, links=_links,
                           script_links=_script_links, **kwargs)

    def test_scripts_are_listed_under_the_bars(self):
        html = self._html(icons=_Icons())
        self.assertIn('>Shocking Banner</a> (', html)
        self.assertIn('>Class Flourish</a> / ', html)
        self.assertIn('href="https://eso-hub.com/en/scribing/scripts/class-mastery"', html)
        self.assertIn('>Heroism</a>)', html)
        # Scripts without a known page stay plain text
        self.assertIn("(Warmage&#x27;s Defense / Resolve)", html)
        # The small grimoire icon sits outside the anchor, so a search for the
        # skill does not count it as a second icon match
        self.assertIn('<img src="icon:ability_grimoire_support" width="14" height="14" '
                      'style="vertical-align:middle">&nbsp;<a ', html)
        # Smaller than the 9pt pane font, inside the build card
        self.assertIn("<span style='font-size:7.65pt'>", html)

    def test_skill_on_both_bars_is_listed_once(self):
        html = self._html(icons=_Icons())
        ada = html[html.index('@ada'):html.index('@bren')]
        self.assertEqual(ada.count('>Shocking Banner</a>'), 1)
        self.assertEqual(ada.count('>Leashing Soul</a>'), 1)

    def test_unknown_scripts_say_so(self):
        html = self._html(icons=_Icons())
        cy = html[html.index('@cy'):]
        self.assertIn('>Banner Bearer</a> (scripts not in log)', cy)
        self.assertIn('href="https://eso-hub.com/en/skills/alliance-war/support/banner-bearer#options-', cy)

    def test_text_bars_get_the_scripts_line_too(self):
        html = self._html()
        self.assertNotIn('<img', html)
        self.assertIn('Damage Ability, Shocking Banner', html)
        self.assertIn('>Shocking Banner</a> (', html)

    def test_no_line_for_players_without_scribed_skills(self):
        from fight_history import FightHistoryEntry
        from gui.fight_render import render_html
        entry = FightHistoryEntry()
        entry.players = [{'name': '@plain', 'unit_id': '1', 'front_bar': ['Biting Jabs'],
                          'front_bar_slots': [{'id': '1', 'name': 'Biting Jabs', 'icon': 'x'}]}]
        html = render_html(entry, detailed=True, icons=_Icons(), script_links=_script_links)
        self.assertNotIn('font-size:7.65pt', html)
        self.assertNotIn('scripts not in log', html)

    def test_same_skill_with_other_scripts_gets_its_own_anchor_and_hover(self):
        from gui.fight_render import anchor_tooltips
        second = _fights(SESSION)[1]  # Ada and Bren both run a Shocking Banner
        tips = anchor_tooltips(second, links=_links, script_links=_script_links)
        page = 'https://eso-hub.com/en/scribing/combination/93/shocking-banner'
        ada = tips[f'{page}#class-flourish.heroism']
        bren = tips[f'{page}#cavaliers-charge.brutality']
        self.assertIn('<b>Shocking Banner</b><br>Grimoire: Banner Bearer<br>Focus: Shock Damage'
                      '<br>Signature: Class Flourish<br>Affix: Heroism', ada)
        self.assertIn("Signature: Cavalier&#x27;s Charge<br>Affix: Brutality", bren)
        # The fragment only tells the anchors apart; the tip shows the page
        self.assertIn(f'Click to open on ESO-Hub<br>{page}</span>', ada)
        self.assertNotIn('#', ada)

    def test_hover_for_unknown_scripts_lists_the_options(self):
        from gui.fight_render import anchor_tooltips
        tips = anchor_tooltips(self.fight, links=_links, script_links=_script_links)
        key = next(k for k in tips if '#options-' in k)
        self.assertIn('<b>Banner Bearer</b>', tips[key])
        self.assertIn('• Shocking Banner (Class Flourish / Heroism)', tips[key])
        self.assertIn("• Fortifying Banner (Warmage&#x27;s Defense / Resolve)", tips[key])

    def test_hover_names_the_option_without_scripts(self):
        from fight_history import FightHistoryEntry
        from gui.fight_render import anchor_tooltips
        entry = FightHistoryEntry()
        slot = dict(slot_fields((SHOCKING, ScribedSkill('Shocking Banner', BANNER_ICON))),
                    id='217699')
        entry.players = [{'name': '@bren', 'unit_id': '2', 'front_bar': ['Shocking Banner'],
                          'front_bar_slots': [slot]}]
        (tip,) = anchor_tooltips(entry).values()
        self.assertIn('• Shocking Banner (Class Flourish / Heroism)<br>'
                      '• or one the log has without its scripts', tip)

    def test_script_anchors_have_hover_text(self):
        from gui.fight_render import anchor_tooltips
        tips = anchor_tooltips(self.fight, links=_links, script_links=_script_links)
        tip = tips['https://eso-hub.com/en/scribing/scripts/class-mastery']
        self.assertIn('<b>Class Flourish</b><br>Signature script', tip)
        self.assertIn('eso-hub.com/en/scribing/scripts/class-mastery', tip)
        self.assertIn('Affix script', tips['https://eso-hub.com/en/scribing/scripts/heroism'])

    def test_skill_without_a_page_still_gets_its_hover(self):
        from gui.fight_render import anchor_tooltips
        tips = anchor_tooltips(self.fight)
        tip = tips['esolog:ability/217699#class-flourish.heroism']
        self.assertIn('Signature: Class Flourish', tip)
        self.assertNotIn('eso-hub.com', tip)

    def test_plain_text_copy_names_the_scripts(self):
        from gui.fight_render import render_plain_text
        text = render_plain_text(self.fight)
        self.assertIn('      Damage Ability, Shocking Banner (Class Flourish / Heroism)', text)
        self.assertIn("      Damage Ability, Fortifying Banner (Warmage's Defense / Resolve)", text)
        self.assertIn('      Damage Ability, Banner Bearer\n', text)


class TestScribingLinks(unittest.TestCase):

    def test_link_tables(self):
        skills = {'shocking-banner': '/en/scribing/combination/93/shocking-banner'}
        self.assertEqual(esohub_scribed_skill_url('Shocking Banner', skills),
                         'https://eso-hub.com/en/scribing/combination/93/shocking-banner')
        self.assertIsNone(esohub_scribed_skill_url('Biting Jabs', skills))
        scripts = {'druids-resurgence': '/en/scribing/scripts/druids-resurgence'}
        self.assertEqual(esohub_script_url("Druid's Resurgence", scripts),
                         'https://eso-hub.com/en/scribing/scripts/druids-resurgence')
        self.assertIsNone(esohub_script_url('', scripts))

    def test_bundled_map_covers_logged_names(self):
        # Names as 2026 logs write them, including three renamed scripts
        self.assertRegex(
            esohub_scribed_skill_url('Chilling Contingency'),
            r'^https://eso-hub\.com/en/scribing/combination/\d+/chilling-contingency$')
        self.assertTrue(esohub_ability_url('Magic Knife').endswith('/magic-knife'))
        self.assertTrue(esohub_ability_url('Banner Bearer').endswith(
            '/en/skills/alliance-war/support/banner-bearer'))
        for script, slug in (('Lingering Torment', 'lingering-torment'),
                             ("Warmage's Defense", 'warmages-defense'),
                             ('Intellect and Endurance', 'intellect-and-endurance'),
                             ('Class Flourish', 'class-mastery'),
                             ('Brutality', 'brutality-and-sorcery'),
                             ('Savagery', 'savagery-and-prophecy')):
            self.assertEqual(esohub_script_url(script),
                             f'https://eso-hub.com/en/scribing/scripts/{slug}')
        # Every grimoire has a skill page of its own
        for grimoire in GRIMOIRES.values():
            self.assertIsNotNone(esohub_ability_url(grimoire), grimoire)


if __name__ == '__main__':
    unittest.main()
