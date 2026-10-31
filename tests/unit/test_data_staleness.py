"""The bundled game data against the game the log was written by (issue
#173): the version comparison, what the tracker counts and leaves out, the
status line and its hover, the engine's messages, the window's label, the
About dialog's stamps, and the two scripts (data/version.json's stamp, the
maintainer's check over a folder of logs)."""

import importlib.util
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import data_staleness
from data_staleness import (
    DataCheck,
    DataCheckTracker,
    is_newer,
    parse_game_version,
    short_version,
    status_text,
    status_tooltip,
)
from engine_events import RecordingListener
from esolog_tail import ESOLogAnalyzer, FightHistory
from tests.unit.test_gui import HAVE_QT, GuiTestCase, _ensure_app

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = REPO_ROOT / 'tests' / 'fixtures' / 'golden_fight.log'


def _load(script: str):
    path = REPO_ROOT / 'scripts' / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tracker(data_version='eso.live.12.1', sets=None, armor=None, weapons=None,
             icons=('ability_known',), links=None):
    """A tracker over small fake tables: *sets* names set ids, *armor* and
    *weapons* know item ids, *links* names the sets that have a page."""
    sets = {'1': 'Known Set', '2': 'Unlinked Set'} if sets is None else sets
    armor = {'100', '101'} if armor is None else armor
    weapons = {'200'} if weapons is None else weapons
    links = {'Known Set'} if links is None else links
    return DataCheckTracker(
        data_version=data_version, data_built='2026-11-01',
        set_name_of=sets.get,
        armor_weight_of=lambda item: 'heavy' if item in armor else '',
        weapon_type_of=lambda item: 'dagger' if item in weapons else '',
        icon_stems=icons,
        set_link_of=lambda name: 'https://eso-hub.com/x' if name in links else None)


def _item(slot, item_id, set_id='0', cp='T'):
    return [slot, item_id, cp, '16', 'NONE', 'LEGENDARY', set_id, 'INVALID', 'F', '0', 'NORMAL']


class TestGameVersion(unittest.TestCase):

    def test_the_two_numbers_after_the_branch(self):
        self.assertEqual(parse_game_version('eso.live.12.1'), (12, 1))
        self.assertEqual(parse_game_version('eso.live.12.1.5'), (12, 1))
        self.assertEqual(parse_game_version('eso.pts.12.2'), (12, 2))
        self.assertEqual(parse_game_version(' eso.live.9.10 '), (9, 10))
        for text in ('', None, '12.1', 'eso.live', 'eso.live.x.1', 'NA Megaserver'):
            self.assertIsNone(parse_game_version(text), text)
        self.assertEqual(short_version('eso.live.12.1'), '12.1')
        self.assertEqual(short_version(''), '')

    def test_newer_compares_numbers_not_text(self):
        self.assertTrue(is_newer('eso.live.12.2', 'eso.live.12.1'))
        self.assertTrue(is_newer('eso.live.13.0', 'eso.live.12.9'))
        self.assertTrue(is_newer('eso.live.12.10', 'eso.live.12.9'))
        self.assertFalse(is_newer('eso.live.12.1', 'eso.live.12.1'))
        self.assertFalse(is_newer('eso.live.12.1.7', 'eso.live.12.1'))  # a build number
        self.assertFalse(is_newer('eso.live.11.3', 'eso.live.12.1'))
        self.assertFalse(is_newer('', 'eso.live.12.1'))
        self.assertFalse(is_newer('eso.live.12.2', ''))

    def test_the_bundle_names_a_version(self):
        info = data_staleness.bundle_version()
        self.assertIsNotNone(parse_game_version(info.get('game_version')))
        self.assertRegex(info.get('built', ''), r'^\d{4}-\d{2}-\d{2}$')
        names = [t['name'] for t in info.get('tables', [])]
        self.assertIn('Set names (game client)', names)
        self.assertIn('Ability icons (game client)', names)


class TestTracker(unittest.TestCase):

    def test_nothing_unknown_is_clear(self):
        tracker = _tracker()
        tracker.reset('eso.live.12.1')
        found = tracker.note_player(
            [_item('HEAD', '100', '1'), _item('MAIN_HAND', '200', '1')],
            [{'id': '5', 'name': 'Known', 'icon': 'ability_known'}])
        self.assertFalse(found)
        check = tracker.check()
        self.assertTrue(check.clear)
        self.assertEqual(status_text(check), '')
        self.assertEqual(status_tooltip(check), '')

    def test_each_kind_is_counted_once(self):
        tracker = _tracker()
        tracker.reset('eso.live.12.1')
        gear = [_item('HEAD', '100', '9'),        # a set the data does not name
                _item('CHEST', '150', '2'),       # unknown armor, a set with no link
                _item('MAIN_HAND', '250', '1'),   # an unknown weapon
                _item('NECK', '300', '1')]        # jewelry: no weight or type to know
        bars = [{'id': '7', 'name': 'New Skill', 'icon': 'ability_new'},
                {'id': '8', 'name': 'No Icon', 'icon': ''}]
        self.assertTrue(tracker.note_player(gear, bars))
        self.assertFalse(tracker.note_player(gear, bars))  # nothing new the second time
        check = tracker.check()
        self.assertEqual(check.unknown_sets, ('9',))
        self.assertEqual(check.unlinked_sets, ('Unlinked Set',))
        self.assertEqual(check.unknown_armor, ('150',))
        self.assertEqual(check.unknown_weapons, ('250',))
        self.assertEqual(check.missing_icons, (('7', 'New Skill'),))
        self.assertEqual(check.counts, {'sets': 1, 'items': 2, 'icons': 1, 'links': 1})

    def test_plain_low_level_items_are_left_out(self):
        """A new character's Soul-Shriven clothes are in no table: an item
        of no set below champion level never reads as stale data, while a
        set item at any level does."""
        tracker = _tracker()
        tracker.reset('eso.live.12.1')
        tracker.note_player([_item('CHEST', '35029', '0', cp='F'),
                             _item('FEET', '35036', '0', cp='F')], [])
        self.assertTrue(tracker.check().clear)
        tracker.note_player([_item('LEGS', '400', '1', cp='F')], [])
        self.assertEqual(tracker.check().unknown_armor, ('400',))

    def test_a_plain_item_is_looked_up_once_worn_at_champion_level(self):
        """The log's item id is the same at every level: one first seen
        plain and low-level is still judged when worn at champion level."""
        tracker = _tracker()
        tracker.reset('eso.live.12.1')
        self.assertFalse(tracker.note_player([_item('HAND', '500', '0', cp='F')], []))
        self.assertTrue(tracker.note_player([_item('HAND', '500', '0', cp='T')], []))
        self.assertEqual(tracker.check().unknown_armor, ('500',))

    def test_a_new_session_starts_again(self):
        tracker = _tracker()
        tracker.reset('eso.live.12.1')
        tracker.note_player([_item('HEAD', '100', '9')], [])
        self.assertEqual(tracker.check().unknown_sets, ('9',))
        tracker.reset('eso.live.12.2')
        check = tracker.check()
        self.assertEqual(check.unknown_sets, ())
        self.assertEqual(check.game_version, 'eso.live.12.2')
        self.assertTrue(check.newer)
        # Found again in the new session
        self.assertTrue(tracker.note_player([_item('HEAD', '100', '9')], []))

    def test_the_bundled_tables_know_a_real_build(self):
        """The default lookups: a Kyne's Aegis build of 2026-01-13 (12.1-era
        gear, the logging player's) is known to the bundle."""
        tracker = DataCheckTracker()
        tracker.reset(tracker.data_version)
        gear = [['HEAD', '95044', 'T', '16', 'ARMOR_DIVINES', 'LEGENDARY', '270',
                 'MAGICKA', 'T', '16', 'LEGENDARY']]
        tracker.note_player(gear, [{'id': '183006', 'name': 'Cephaliarch\'s Flail',
                                    'icon': 'ability_arcanist_002_b'}])
        self.assertTrue(tracker.check().clear, tracker.check())


class TestStatusText(unittest.TestCase):

    def test_newer_game_with_and_without_findings(self):
        self.assertEqual(status_text(DataCheck('eso.live.12.2', 'eso.live.12.1')),
                         'Game 12.2, data built for 12.1')
        check = DataCheck('eso.live.12.2', 'eso.live.12.1', '2026-11-01',
                          unknown_sets=('812', '813', '814'),
                          missing_icons=(('1', 'A'), ('2', 'B')))
        self.assertEqual(status_text(check),
                         'Game 12.2, data built for 12.1: 3 unknown sets, 2 icons missing')

    def test_same_or_older_game_says_only_what_was_found(self):
        check = DataCheck('eso.live.12.1', 'eso.live.12.1', unknown_armor=('5',))
        self.assertEqual(status_text(check), 'Data built for game 12.1: 1 unknown item')
        check = DataCheck('eso.live.11.3', 'eso.live.12.1', unknown_weapons=('5', '6'))
        self.assertEqual(status_text(check), 'Data built for game 12.1: 2 unknown items')
        check = DataCheck('', '', unlinked_sets=('X',))
        self.assertEqual(status_text(check), 'Game data: 1 set with no ESO-Hub link')
        self.assertEqual(status_text(DataCheck('eso.live.11.3', 'eso.live.12.1')), '')
        self.assertEqual(status_text(None), '')

    def test_the_hover_lists_what_was_found(self):
        check = DataCheck('eso.live.12.2', 'eso.live.12.1', '2026-11-01',
                          unknown_sets=tuple(str(800 + i) for i in range(12)),
                          unknown_armor=('5',), missing_icons=(('7', 'New Skill'),),
                          unlinked_sets=('Foo',))
        text = status_tooltip(check)
        self.assertIn('game version 12.2, newer than the 12.1', text)
        self.assertIn('on 2026-11-01', text)
        self.assertIn('Set#800, Set#801', text)
        self.assertIn('and 2 more', text)  # ten listed of twelve
        self.assertNotIn('Set#811', text)
        self.assertIn('Unknown armor: item 5', text)
        self.assertIn('Icons missing: New Skill', text)
        self.assertIn('Sets with no ESO-Hub link: Foo', text)
        same = status_tooltip(DataCheck('eso.live.12.1', 'eso.live.12.1', unknown_sets=('9',)))
        self.assertIn('built for game version 12.1; this log was written by 12.1', same)


def _replay(analyzer, lines):
    for line in lines:
        entry = analyzer.log_parser.parse_line(line)
        if entry is not None:
            analyzer.process_log_entry(entry)


class TestEngine(unittest.TestCase):

    def _analyzer(self):
        analyzer = ESOLogAnalyzer()
        analyzer.fight_history = FightHistory()
        recorder = RecordingListener()
        analyzer.add_listener(recorder)
        return analyzer, recorder

    def test_a_session_begins_with_a_check_and_a_find_sends_another(self):
        """The fixture's BEGIN_LOG sends the first; its Radiant Glory names
        an icon the bundle lacks (ability_templar_under_attack), which sends
        the second, once, though every PLAYER_INFO of the player names it."""
        analyzer, recorder = self._analyzer()
        _replay(analyzer, FIXTURE.read_text(encoding='utf-8').splitlines())
        checks = [event[1] for event in recorder.of_kind('data_check')]
        self.assertEqual(len(checks), 2)
        self.assertEqual(checks[0].game_version, 'eso.live.11.1')
        self.assertTrue(checks[0].clear)  # older than the data: nothing to say yet
        self.assertEqual(checks[1].missing_icons, (('25267', 'Radiant Glory'),))
        self.assertEqual(status_text(checks[1]), 'Data built for game 12.1: 1 icon missing')

    def test_something_new_sends_another(self):
        analyzer, recorder = self._analyzer()
        analyzer.data_check = DataCheckTracker(
            data_version='eso.live.11.0', data_built='2026-11-01',
            set_name_of=lambda set_id: None, icon_stems=())
        _replay(analyzer, FIXTURE.read_text(encoding='utf-8').splitlines())
        checks = [event[1] for event in recorder.of_kind('data_check')]
        self.assertGreater(len(checks), 1)
        self.assertTrue(checks[0].newer)
        self.assertEqual(status_text(checks[0]), 'Game 11.1, data built for 11.0')
        last = checks[-1]
        self.assertTrue(last.unknown_sets)
        self.assertTrue(last.missing_icons)
        self.assertTrue(status_text(last).startswith('Game 11.1, data built for 11.0: '))

    def test_fight_entries_do_not_change(self):
        """The check only reads: the fight entries are the same with a
        tracker that finds everything unknown."""
        lines = FIXTURE.read_text(encoding='utf-8').splitlines()
        plain, _ = self._analyzer()
        _replay(plain, lines)
        flagged, _ = self._analyzer()
        flagged.data_check = DataCheckTracker(set_name_of=lambda set_id: None, icon_stems=())
        _replay(flagged, lines)
        fights = [plain.fight_history.fights, flagged.fight_history.fights]
        self.assertTrue(fights[0])
        self.assertEqual(len(fights[0]), len(fights[1]))
        for a, b in zip(*fights):
            self.assertEqual(a.players, b.players)
            self.assertEqual(a.group_dps, b.group_dps)


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestStatusLabel(GuiTestCase):

    def test_shown_only_when_there_is_something_to_say(self):
        from gui.main_window import MainWindow
        _ensure_app()
        win = MainWindow(self.config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        try:
            self.assertFalse(win.data_label.isVisibleTo(win))
            win._on_data_check(DataCheck('eso.live.12.1', 'eso.live.12.1'))
            self.assertFalse(win.data_label.isVisibleTo(win))
            win._on_data_check(DataCheck('eso.live.12.2', 'eso.live.12.1', '2026-11-01',
                                         unknown_sets=('812',)))
            self.assertTrue(win.data_label.isVisibleTo(win))
            self.assertEqual(win.data_label.text(),
                             'Game 12.2, data built for 12.1: 1 unknown set')
            self.assertIn('Set#812', win.data_label.toolTip())
            self.assertEqual(win.data_label.accessibleName(), win.data_label.text())
            # A split warning keeps its own label
            win._on_warning('split', 'Split file writing stopped: disk full')
            self.assertTrue(win.warning_label.isVisibleTo(win))
            self.assertNotIn('disk full', win.data_label.toolTip())
            # A restart starts again
            win._on_monitoring_restarting()
            self.assertFalse(win.data_label.isVisibleTo(win))
        finally:
            win.close()


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestAboutData(unittest.TestCase):

    def test_the_stamps_are_listed(self):
        from gui.about import about_html, data_html
        stamps = ('eso.live.12.1', '2026-11-01',
                  [('Set names (game client)', '2026-10-27'), ('Armor weights (UESP)', '2026-10-05')])
        html = data_html(stamps)
        self.assertIn('built for game version 12.1 on 2026-11-01', html)
        self.assertIn('Set names (game client) 2026-10-27', html)
        self.assertIn('Armor weights (UESP) 2026-10-05', html)
        self.assertIn(html, about_html('0.30.0', '', stamps))
        self.assertEqual(data_html(('', '', [])), '')
        self.assertEqual(data_html(None), '')
        self.assertIn('built for game version', about_html('0.30.0', '', data_staleness.data_stamps()))


class TestStampScript(unittest.TestCase):

    def test_data_version_json_is_current(self):
        """A refreshed table whose stamp was forgotten fails here: run
        scripts/stamp_data_version.py after a data refresh."""
        stamp = _load('stamp_data_version.py')
        self.assertEqual(stamp.check(), [])

    def test_a_changed_table_is_caught(self):
        stamp = _load('stamp_data_version.py')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data' / 'items').mkdir(parents=True)
            table = root / 'data' / 'items' / 'armor_weights.json'
            table.write_text(json.dumps({'generated': '2026-10-05T08:58:33+00:00'}), encoding='utf-8')
            (root / 'data' / 'version.json').write_text(json.dumps(
                stamp.stamp('eso.live.12.1', root, today='2026-11-01')), encoding='utf-8')
            self.assertEqual(stamp.check(root), [])
            table.write_text(json.dumps({'generated': '2026-12-01T00:00:00+00:00'}), encoding='utf-8')
            problems = stamp.check(root)
            self.assertEqual(len(problems), 1)
            self.assertIn('armor_weights.json is dated 2026-12-01', problems[0])

    def test_the_version_comes_from_the_last_begin_log(self):
        stamp = _load('stamp_data_version.py')
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'Encounter.log'
            shutil.copy(FIXTURE, log)
            with open(log, 'a', encoding='utf-8') as f:
                f.write('9,BEGIN_LOG,1755729999999,15,"NA Megaserver","en","eso.live.11.2"\n')
            self.assertEqual(stamp.begin_log_version(log), 'eso.live.11.2')

    def test_the_spec_bundles_the_stamp(self):
        spec = (REPO_ROOT / 'esolog-tail.spec').read_text(encoding='utf-8')
        self.assertTrue(re.search(r"'data/version\.json'", spec))


class TestCheckScript(unittest.TestCase):

    def test_a_log_is_read_session_by_session(self):
        check = _load('check_data_staleness.py')
        sessions = check.scan(FIXTURE, None)
        self.assertEqual(len(sessions), 1)
        session = sessions[0]
        self.assertEqual(session['version'], 'eso.live.11.1')
        self.assertTrue(session['sets'])
        self.assertTrue(session['bars'])
        # The app's own rules: the fixture's Radiant Glory icon is not bundled
        self.assertEqual(session['missing_icons'], [['25267', 'Radiant Glory']])
        self.assertTrue(session['speaks'])
        self.assertEqual(session['status'], 'Data built for game 12.1: 1 icon missing')
        # Judged against an older bundle, the version speaks too
        older = check.scan(FIXTURE, 'eso.live.11.0')[0]
        self.assertTrue(older['status'].startswith('Game 11.1, data built for 11.0'))

    def test_an_id_gone_from_the_newest_version_is_flagged(self):
        check = _load('check_data_staleness.py')
        groups = check.tracked_groups()
        index = next(i for i, group in enumerate(groups) if len(group[2]) > 1)
        gone, kept = sorted(groups[index][2])[:2]
        sessions = ([{'version': 'eso.live.11.3', 'fires': {gone: 1}}]
                    + [{'version': 'eso.live.12.0', 'fires': {gone: 3, kept: 1}}] * 4
                    + [{'version': 'eso.live.12.1', 'fires': {kept: 2}}] * 2)
        report = check.fires(sessions)
        self.assertEqual((report['previous'], report['newest']), ('eso.live.12.0', 'eso.live.12.1'))
        self.assertEqual(report['sessions'], {'eso.live.11.3': 1, 'eso.live.12.0': 4, 'eso.live.12.1': 2})
        group = report['groups'][index]
        self.assertEqual([f[0] for f in group['flagged']], [gone])
        self.assertEqual(group['flagged'][0][1], 4)  # sessions of 12.0 that saw it
        self.assertEqual((group['fired_previous'], group['fired_newest']), (2, 1))

    def test_coverage_counts_by_version(self):
        check = _load('check_data_staleness.py')
        session = {'version': 'eso.live.12.1', 'speaks': True, 'status': 'Data built for game 12.1: 1 unknown set',
                   'unknown_sets': ['999'], 'unknown_armor': [], 'unknown_weapons': [],
                   'missing_icons': [], 'unlinked_sets': [], 'sets': ['1', '999'],
                   'armor': ['100', '35029'], 'weapons': ['200'], 'bars': ['5'],
                   'armor_unknown_all': ['35029'], 'weapons_unknown_all': [],
                   'killers': {'7': 'death_recap_x', '8': 'gear_monster_head'},
                   'food_hint': [['51906', 'Q3854 Goblin Disguise', 'crafting_x', 1]], 'fires': {}}
        report = check.coverage([session, dict(session, speaks=False)])['eso.live.12.1']
        self.assertEqual(report['sessions'], 2)
        self.assertEqual(report['speaks'], 1)
        self.assertEqual(report['sets_unknown'], ['999'])
        self.assertEqual(report['armor_left_out'], ['35029'])
        self.assertEqual(report['food_hint'], [['51906', 'Q3854 Goblin Disguise', 'crafting_x', 2]])
        self.assertEqual(report['killers'], 2)


if __name__ == '__main__':
    unittest.main()
