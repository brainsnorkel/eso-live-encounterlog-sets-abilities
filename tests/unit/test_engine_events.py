#!/usr/bin/env python3
"""Unit tests for the engine event/listener interface."""

import unittest
from datetime import datetime
from pathlib import Path

from engine_events import (
    AnalyzerListener, ArchiveEvent, ListenerMixin, LogStatus, RecordingListener,
)


class _Emitter(ListenerMixin):
    pass


class TestListenerMixin(unittest.TestCase):

    def setUp(self):
        self.emitter = _Emitter()
        self.recorder = RecordingListener()
        self.emitter.add_listener(self.recorder)

    def test_add_listener_is_idempotent(self):
        self.emitter.add_listener(self.recorder)
        self.assertEqual(len(self.emitter.listeners), 1)

    def test_remove_listener(self):
        self.emitter.remove_listener(self.recorder)
        self.emitter._notify('on_zone_changed', 'Coral Aerie', 'VETERAN')
        self.assertEqual(self.recorder.events, [])

    def test_notify_fans_out_in_order(self):
        second = RecordingListener()
        self.emitter.add_listener(second)
        self.emitter._notify('on_zone_changed', 'Coral Aerie', 'VETERAN')
        self.assertEqual(self.recorder.events, [('zone_changed', 'Coral Aerie', 'VETERAN')])
        self.assertEqual(second.events, [('zone_changed', 'Coral Aerie', 'VETERAN')])

    def test_listener_exception_does_not_break_others(self):
        class Broken(AnalyzerListener):
            def on_zone_changed(self, zone_name, difficulty):
                raise RuntimeError('frontend bug')

        self.emitter.listeners.insert(0, Broken())
        self.emitter._notify('on_zone_changed', 'Deshaan', 'NONE')
        self.assertEqual(self.recorder.of_kind('zone_changed'),
                         [('zone_changed', 'Deshaan', 'NONE')])

    def test_all_callbacks_recorded(self):
        status = LogStatus(log_path=Path('x.log'), size_bytes=10,
                           latest_entry_time=datetime(2026, 9, 27, 14, 33, 2),
                           source='exact')
        event = ArchiveEvent(kind='completed', archive_path=Path('a.zip'))
        self.emitter._notify('on_log_status', status)
        self.emitter._notify('on_archive_event', event)
        self.emitter._notify('on_diagnostic', 'hello')
        self.emitter._notify('on_fight_completed', object())
        self.emitter._notify('on_fight_updated', object())
        kinds = [e[0] for e in self.recorder.events]
        self.assertEqual(kinds, ['log_status', 'archive_event', 'diagnostic',
                                 'fight_completed', 'fight_updated'])

    def test_default_listener_callbacks_are_noops(self):
        listener = AnalyzerListener()
        listener.on_fight_completed(object())
        listener.on_fight_updated(object())
        listener.on_zone_changed('z', 'd')
        listener.on_log_status(LogStatus())
        listener.on_archive_event(ArchiveEvent(kind='skipped'))
        listener.on_diagnostic('m')


if __name__ == '__main__':
    unittest.main()
