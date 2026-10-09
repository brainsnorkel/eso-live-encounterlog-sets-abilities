#!/usr/bin/env python3
"""Death recap in the GUI (offscreen Qt): the button on a dead player's row,
its hover summary, click routing, and the recap window."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def _row(offset_ms, kind, result, source, ability, amount, health, icon='',
         overflow=0, absorbed=0, shields=()):
    return {
        'offset_ms': offset_ms, 'kind': kind, 'result': result, 'source': source,
        'ability': ability, 'ability_id': '1', 'icon': icon, 'amount': amount,
        'overflow': overflow, 'absorbed': absorbed, 'shields': list(shields),
        'health': health, 'max_health': 18678,
    }


def _death(unit_id, name, time_ms, killer, ability, events, icon=''):
    return {'unit_id': unit_id, 'name': name, 'time_ms': time_ms, 'killer': killer,
            'ability': ability, 'ability_id': '9', 'icon': icon,
            'max_health': 18678, 'events': events}


def _player(unit_id, name):
    return {'role': 'D', 'name': name, 'class_abbr': 'NB', 'dps': 1000.0,
            'dmg_pct': 50.0, 'h': 20000, 'm': 30000, 's': 15000, 'unit_id': unit_id,
            'sets': [], 'all_sets': [], 'skill_lines': [], 'class_lines': [],
            'front_bar': [], 'back_bar': [], 'front_bar_slots': [], 'back_bar_slots': []}


def _entry_with_deaths():
    """@tester dies twice, @friend survives, and a player the table does not
    list (no build logged for them) dies once."""
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = 'Sharpfang'
    entry.zone_name = 'Moonlit Cove'
    entry.timestamp = '2026-10-03 16:54:04'
    entry.players = [_player('1', '@tester'), _player('2', '@friend')]
    first = _death('1', '@tester', 54000, 'Sharpfang', 'Slap', [
        _row(-3200, 'damage', 'BLOCKED_DAMAGE', 'Sharpfang', 'Swinging Cleave', 2102, 6413,
             icon='death_recap_test', absorbed=5603, shields=['Bone Shield']),
        _row(-1500, 'heal', 'HOT_TICK', '@friend', 'Radiating Regeneration', 2500, 8913),
        _row(-900, 'avoided', 'DODGED', 'Sharpfang', 'Tremor', 0, 8913),
        _row(-400, 'heal_absorbed', 'HEAL_ABSORBED', '@friend', 'Hindered', 1328, 8913),
        _row(1, 'damage', 'DAMAGE', 'Sharpfang', 'Slap', 8913, 0,
             icon='death_recap_test', overflow=4983),
    ], icon='death_recap_test')
    second = _death('1', '@tester', 95000, '', 'Fall Snare', [
        _row(0, 'damage', 'FALL_DAMAGE', '', 'Fall Snare', 9000, 0),
    ])
    stranger = _death('77', '@passerby', 61000, 'Sharpfang', 'Tremor', [])
    entry.death_recaps = [first, stranger, second]
    entry.deaths = 3
    return entry


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class DeathRecapGuiTestCase(unittest.TestCase):

    def setUp(self):
        _ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.icons_root = Path(self.tmp.name)
        from PySide6.QtGui import QColor, QImage
        image = QImage(40, 40, QImage.Format_ARGB32)
        image.fill(QColor('red'))
        self.assertTrue(image.save(str(self.icons_root / 'death_recap_test.png')))

    def tearDown(self):
        self.tmp.cleanup()

    def _cache(self):
        from gui.icon_cache import IconCache
        return IconCache(self.icons_root)


class TestDeathButtonInFightView(DeathRecapGuiTestCase):

    def test_dead_players_get_a_button_and_survivors_do_not(self):
        from gui.fight_render import render_html
        for detailed in (True, False):
            html = render_html(_entry_with_deaths(), detailed=detailed)
            tester_row = html[html.index('@tester'):html.index('@friend')]
            self.assertIn('href="esolog:deaths/1"', tester_row)
            self.assertIn('☠ ×2', tester_row)
            friend_row = html[html.index('@friend'):html.index('</table>')]
            self.assertNotIn('esolog:deaths', friend_row)
        self.assertNotIn('esolog:deaths', render_html(_entry_no_deaths(), detailed=True))

    def test_deaths_of_unlisted_players_are_still_reachable(self):
        from gui.fight_render import render_html
        html = render_html(_entry_with_deaths(), detailed=True)
        tail = html[html.index('</table>'):]
        self.assertIn('Also died:', tail)
        self.assertIn('href="esolog:deaths/77"', tail)
        self.assertIn('@passerby', tail)
        self.assertNotIn('Also died', render_html(_entry_no_deaths(), detailed=True))

    def test_hover_summarises_each_death(self):
        from gui.death_render import death_tooltips
        tips = death_tooltips(_entry_with_deaths())
        self.assertEqual(set(tips), {'esolog:deaths/1', 'esolog:deaths/77'})
        tip = tips['esolog:deaths/1']
        self.assertIn('@tester: 2 deaths', tip)
        self.assertIn('0:54', tip)
        self.assertIn('Slap (Sharpfang)', tip)
        self.assertIn('1:35', tip)
        self.assertIn('Fall Snare', tip)       # no killer named: ability alone
        self.assertNotIn('Fall Snare (', tip)
        self.assertIn('@passerby: 1 death<', tips['esolog:deaths/77'])
        self.assertEqual(death_tooltips(_entry_no_deaths()), {})

    def test_click_is_announced_with_the_players_unit_id(self):
        from PySide6.QtCore import QUrl
        from gui.fight_view import FightView
        opened, requested = [], []
        view = FightView(icons=self._cache(),
                         open_external=lambda url: opened.append(url.toString()) or True)
        view.death_recap_requested.connect(requested.append)
        view.anchorClicked.emit(QUrl('esolog:deaths/77'))
        view.anchorClicked.emit(QUrl('esolog:ability/99'))
        view.anchorClicked.emit(QUrl('https://eso-hub.com/en/skills/x/y/z'))
        self.assertEqual(requested, ['77'])
        self.assertEqual(opened, ['https://eso-hub.com/en/skills/x/y/z'])


class TestDeathCueInHistoryList(DeathRecapGuiTestCase):
    """Fights in which a player died carry "(d)" after their name."""

    def test_cue_follows_the_boss_name_only_when_someone_died(self):
        from gui.fight_render import summary_line
        died, clean = _entry_with_deaths(), _entry_no_deaths()
        self.assertTrue(summary_line(died, death_cue=True).startswith('Sharpfang (d) · '))
        self.assertEqual(summary_line(died, death_cue=True).count('(d)'), 1)
        self.assertNotIn('(d)', summary_line(clean, death_cue=True))
        # A fight with no boss or mob name: the cue follows the duration
        died.boss_name = ''
        died.duration_s = 39.0
        self.assertTrue(summary_line(died, death_cue=True).startswith('39s (d) · '))

    def test_clipboard_copy_carries_no_cue(self):
        from gui.fight_render import render_plain_text, summary_line
        died = _entry_with_deaths()
        self.assertNotIn('(d)', summary_line(died))
        self.assertNotIn('(d)', render_plain_text(died))

    def test_history_list_marks_fights_with_deaths(self):
        from app_config import AppConfig
        from gui.main_window import MainWindow
        config = AppConfig(path=self.icons_root / 'config.json')
        config.set('log_path', str(self.icons_root / 'Encounter.log'))
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        try:
            win._on_fight_completed(_entry_no_deaths())
            win._on_fight_completed(_entry_with_deaths())
            texts = [win.history_list.item(i).text() for i in range(2)]
            self.assertNotIn('(d)', texts[0])
            self.assertTrue(texts[1].startswith('Sharpfang (d) · '))
            # Review mode builds its list the same way
            win._on_review_loaded('old.log', [_entry_with_deaths(), _entry_no_deaths()])
            texts = [win.history_list.item(i).text() for i in range(2)]
            self.assertIn('(d)', texts[0])
            self.assertNotIn('(d)', texts[1])
        finally:
            win.close()


class TestRecapRendering(DeathRecapGuiTestCase):

    def _html(self, unit_id='1', **kwargs):
        from gui.death_render import render_death_recap_html
        return render_death_recap_html(_entry_with_deaths(), unit_id,
                                       icons=self._cache(), **kwargs)

    def test_each_death_has_its_chronology(self):
        html = self._html()
        self.assertIn('@tester', html)
        self.assertIn('Sharpfang · Moonlit Cove · 2026-10-03 16:54:04', html)
        first, second = html.index('Death 1 of 2'), html.index('Death 2 of 2')
        self.assertLess(first, second)
        one, two = html[first:second], html[second:]
        self.assertIn('0:54 into the fight', one)
        self.assertIn('18,678 max health', one)
        # Rows in log order: cleave, heal, dodge, absorbed heal, killing blow
        order = [one.index(text) for text in
                 ('>Swinging Cleave<', '>Radiating Regeneration<', '>Tremor<',
                  '>Hindered<', '>Slap</td>')]
        self.assertEqual(order, sorted(order))
        self.assertIn('-3.2s', one)
        self.assertIn('1:35 into the fight', two)
        self.assertNotIn('@passerby', html)   # another player's death

    def test_damage_rows_say_how_the_hit_was_taken(self):
        one = self._html()
        self.assertIn('Blocked', one)
        self.assertIn('5,603 absorbed by Bone Shield', one)
        self.assertIn('>2,102<', one)
        self.assertIn('Dodged', one)
        self.assertIn('4,983 overkill', one)
        self.assertIn('>8,913<', one)
        self.assertIn('Fall', one)

    def test_heals_show_their_source_and_what_was_absorbed(self):
        html = self._html()
        self.assertIn('+2,500', html)
        self.assertIn('HoT', html)
        self.assertIn('>@friend<', html)
        self.assertIn('Heal absorbed', html)
        self.assertIn('>1,328<', html)

    def test_killer_line_and_missing_source(self):
        html = self._html()
        one, two = html.split('Death 2 of 2')
        self.assertRegex(one, r'Killed by <b>.*Slap</b>.*from</span> Sharpfang')
        # The log named no unit for the fall: no "from", and a dash as source
        self.assertIn('Killed by <b>Fall Snare</b></p>', two)
        self.assertIn('>–<', two)

    def test_health_after_each_event_with_its_share_of_max(self):
        html = self._html()
        self.assertIn('>6,413</span>', html)
        self.assertIn('>34%</span>', html)
        self.assertIn('>0</span>', html)

    def test_bundled_icons_are_drawn_and_missing_ones_are_not(self):
        html = self._html()
        self.assertEqual(html.count('<img src="icon:death_recap_test"'), 3)  # 2 rows + killer line
        self.assertNotIn('<img src="icon:"', html)
        from gui.death_render import render_death_recap_html
        self.assertNotIn('<img', render_death_recap_html(_entry_with_deaths(), '1'))

    def test_death_with_nothing_logged_before_it(self):
        html = self._html(unit_id='77')
        self.assertIn('Death 1 of 1', html)
        self.assertIn('No damage or healing was logged in the 5 seconds', html)
        self.assertNotIn('<table', html)

    def test_themes_use_different_colors(self):
        self.assertNotEqual(self._html(dark=True), self._html(dark=False))

    def test_names_are_escaped(self):
        from gui.death_render import death_tooltips, render_death_recap_html
        from gui.fight_render import render_html
        entry = _entry_with_deaths()
        entry.death_recaps[1]['name'] = '<b>@x</b>'
        entry.death_recaps[1]['ability'] = 'A<i>'
        self.assertNotIn('<b>@x</b>', render_html(entry, detailed=True))
        self.assertNotIn('<b>@x</b>:', death_tooltips(entry)['esolog:deaths/77'])
        self.assertIn('A&lt;i&gt;', render_death_recap_html(entry, '77'))


class TestRecapWindow(DeathRecapGuiTestCase):

    def _window(self):
        from app_config import AppConfig
        from gui.icon_cache import IconCache
        from gui.main_window import MainWindow
        config = AppConfig(path=self.icons_root / 'config.json')
        config.set('log_path', str(self.icons_root / 'Encounter.log'))
        win = MainWindow(config)
        win.worker_thread.quit()
        win.worker_thread.wait(3000)
        win.fight_view.icons = IconCache(self.icons_root)
        return win

    def test_button_click_opens_the_players_recap(self):
        from PySide6.QtCore import QUrl
        win = self._window()
        try:
            win._on_fight_completed(_entry_with_deaths())
            win.history_list.setCurrentRow(0)
            self.assertIn('☠', win.fight_view.toPlainText())
            self.assertIsNone(win._death_dialog)

            win.fight_view.anchorClicked.emit(QUrl('esolog:deaths/1'))
            dialog = win._death_dialog
            self.assertTrue(dialog.isVisible())
            self.assertIn('@tester', dialog.windowTitle())
            text = dialog.view.toPlainText()
            for expected in ('Death 1 of 2', 'Death 2 of 2', 'Swinging Cleave',
                             'Sharpfang', 'Bone Shield', 'overkill'):
                self.assertIn(expected, text)

            # Another player's button reuses the window
            win.fight_view.anchorClicked.emit(QUrl('esolog:deaths/77'))
            self.assertIs(win._death_dialog, dialog)
            self.assertIn('@passerby', dialog.windowTitle())
            self.assertIn('Death 1 of 1', dialog.view.toPlainText())
        finally:
            win.close()

    def test_real_mouse_click_on_the_button(self):
        """End to end: a click on the rendered button, not an emitted signal."""
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QTextCursor
        from PySide6.QtTest import QTest
        win = self._window()
        try:
            win.resize(1080, 720)
            win.show()
            # Flush the worker's queued startup signals (its "waiting for
            # log" placeholder would replace the fight drawn below)
            _app.processEvents()
            win._on_fight_completed(_entry_with_deaths())
            win.history_list.setCurrentRow(0)
            view = win.fight_view
            found = view.document().find('☠')
            self.assertFalse(found.isNull())
            inside = QTextCursor(view.document())
            inside.setPosition(found.selectionStart() + 3)
            self.assertEqual(inside.charFormat().anchorHref(), 'esolog:deaths/1')
            point = view.cursorRect(inside).center() + QPoint(2, 0)
            QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, point)
            _app.processEvents()
            self.assertIsNotNone(win._death_dialog)
            self.assertTrue(win._death_dialog.isVisible())
            self.assertIn('Death 1 of 2', win._death_dialog.view.toPlainText())
        finally:
            win.close()

    def test_button_hover_works_in_both_views(self):
        win = self._window()
        try:
            win._on_fight_completed(_entry_with_deaths())
            win.history_list.setCurrentRow(0)
            self.assertIn('esolog:deaths/1', win.fight_view._tooltips)
            win.detail_action.setChecked(False)
            self.assertIn('☠', win.fight_view.toPlainText())
            self.assertIn('esolog:deaths/1', win.fight_view._tooltips)
        finally:
            win.close()

    def test_fight_on_screen_redraws_when_a_late_death_arrives(self):
        win = self._window()
        try:
            entry = _entry_no_deaths()
            win._on_fight_completed(entry)
            win.history_list.setCurrentRow(0)
            self.assertNotIn('☠', win.fight_view.toPlainText())
            self.assertIn('Deaths 0', win.fight_view.toPlainText())
            self.assertNotIn('(d)', win.history_list.item(0).text())

            entry.deaths = 1
            entry.death_recaps = [_death('1', '@tester', 20085, 'Sharpfang', 'Slap', [])]
            win._on_fight_updated(entry)
            self.assertIn('☠', win.fight_view.toPlainText())
            self.assertIn('Deaths 1', win.fight_view.toPlainText())
            self.assertTrue(win.history_list.item(0).text().startswith('Sharpfang (d) '))

            # An update for a fight that is not on screen leaves the pane
            # alone, but its history line still gets the cue
            other = _entry_no_deaths()
            win._on_fight_completed(other)
            win.history_list.setCurrentRow(1)
            shown = win.fight_view.toHtml()
            win.history_list.item(0).setText('stale')
            win._on_fight_updated(entry)
            self.assertEqual(win.fight_view.toHtml(), shown)
            self.assertTrue(win.history_list.item(0).text().startswith('Sharpfang (d) '))
            self.assertNotIn('(d)', win.history_list.item(1).text())

            # A fight the list does not hold (the live one, while reviewing
            # another log) is ignored
            win._on_fight_updated(_entry_with_deaths())
            self.assertNotIn('(d)', win.history_list.item(1).text())
        finally:
            win.close()

    def test_fight_the_game_cut_in_two_stays_one_history_line(self):
        """The engine reports the first part as a fight, then the same entry
        again once the fight has really ended."""
        win = self._window()
        try:
            entry = _entry_no_deaths()
            entry.duration_s, entry.group_dps = 66.8, 544635.0
            win._on_fight_completed(entry)
            win.history_list.setCurrentRow(0)
            self.assertIn(' · 1:07 · 544.6k gdps · ', win.history_list.item(0).text())

            entry.duration_s, entry.group_dps, entry.deaths = 129.5, 558974.0, 2
            win._on_fight_updated(entry)
            self.assertEqual(win.history_list.count(), 1)
            self.assertEqual(win.history_list.currentRow(), 0)
            self.assertTrue(win.history_list.item(0).text().startswith(
                'Sharpfang (d) · 2:10 · 559.0k gdps · '))
            shown = win.fight_view.toPlainText()
            self.assertIn('2:10', shown)
            self.assertNotIn('1:07', shown)
        finally:
            win.close()

    def test_open_recap_follows_a_theme_switch(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QColor, QPalette
        from gui.death_render import _THEMES
        win = self._window()
        try:
            win._on_fight_completed(_entry_with_deaths())
            win.history_list.setCurrentRow(0)
            win.fight_view.anchorClicked.emit(QUrl('esolog:deaths/1'))
            dialog = win._death_dialog
            self.assertIn(_THEMES[False]['damage'], dialog.view.toHtml())

            palette = QPalette()
            for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
                palette.setColor(group, QPalette.Window, QColor('#1e1e1e'))
                palette.setColor(group, QPalette.WindowText, QColor('#eeeeee'))
            win.setPalette(palette)
            win._on_theme_maybe_changed()
            self.assertIn(_THEMES[True]['damage'], dialog.view.toHtml())
            self.assertNotIn(_THEMES[False]['damage'], dialog.view.toHtml())
        finally:
            win.close()


EPOCH_MS = 1755729685851
_BOSS = "70,287485/287485,0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"
_NO_UNIT = "0,0/0,0/0,0/0,0/0,0/0,0,0.0000,0.0000,0.0000"
_DEAD_PLAYER = "1,0/20000,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


@unittest.skipUnless(HAVE_QT, 'PySide6 not installed')
class TestLiveTail(DeathRecapGuiTestCase):
    """The engine worker tailing a growing log, as in a live session."""

    def _append(self, lines):
        with open(self.log, 'a', encoding='utf-8') as f:
            for line in lines:
                f.write(line + '\n')

    def test_death_written_after_end_combat_arrives_as_a_fight_update(self):
        from app_config import AppConfig
        from gui.engine_worker import EngineWorker
        self.log = self.icons_root / 'Encounter.log'
        config = AppConfig(path=self.icons_root / 'config.json')
        config.set('log_path', str(self.log))
        config.set('update.check_enabled', False)
        self._append([f'5,BEGIN_LOG,{EPOCH_MS},15,"NA Megaserver","en","eso.live.11.1"'])
        worker = EngineWorker(config)
        completed, updated = [], []
        worker.fight_completed.connect(completed.append)
        worker.fight_updated.connect(updated.append)
        worker.start()
        try:
            self._append([
                '1000,ZONE_CHANGED,1301,"Coral Aerie",VETERAN',
                '2000,UNIT_ADDED,1,PLAYER,T,1,0,F,117,7,"Beam Hal","@brainsnorkel",17085246191555785013,50,3084,0,PLAYER_ALLY,T',
                '2500,UNIT_ADDED,70,MONSTER,F,0,105634,F,0,0,"Test Boss","",0,50,160,0,HOSTILE,F',
                '2600,ABILITY_INFO,12437,"Toppling Blow","/esoui/art/icons/death_recap_test.dds",F,T',
                '10000,BEGIN_COMBAT',
                f'19900,COMBAT_EVENT,DAMAGE,PHYSICAL,1,719,1224,900,12437,{_BOSS},{_DEAD_PLAYER}',
                '20000,END_COMBAT',
            ])
            worker._poll()
            _app.processEvents()
            self.assertEqual(len(completed), 1)
            self.assertEqual((completed[0].deaths, completed[0].death_recaps), (0, []))
            self.assertEqual(updated, [])

            # The DIED line lands in a later poll than the fight it belongs to
            self._append([f'20085,COMBAT_EVENT,DIED,PHYSICAL,0,0,0,901,12437,{_NO_UNIT},{_DEAD_PLAYER}'])
            worker._poll()
            _app.processEvents()
            self.assertEqual(len(updated), 1)
            self.assertIs(updated[0], completed[0])
            self.assertEqual(completed[0].deaths, 1)
            recap = completed[0].death_recaps[0]
            self.assertEqual((recap['name'], recap['killer'], recap['ability']),
                             ('@brainsnorkel', 'Test Boss', 'Toppling Blow'))
            self.assertEqual([(r['amount'], r['overflow']) for r in recap['events']],
                             [(719, 1224)])
        finally:
            worker.stop()


def _entry_no_deaths():
    from fight_history import FightHistoryEntry
    entry = FightHistoryEntry()
    entry.boss_name = 'Sharpfang'
    entry.zone_name = 'Moonlit Cove'
    entry.timestamp = '2026-10-03 16:54:04'
    entry.players = [_player('1', '@tester'), _player('2', '@friend')]
    return entry


if __name__ == '__main__':
    unittest.main()
