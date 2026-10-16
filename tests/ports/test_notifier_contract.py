from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _health_fixtures import START, RecordingNotifier
from _ports.host import Notifier

import machine_health as health

ALERT = health.Alert("memory-pressure", "pressure", "Memory pressure is critical", START)


class NotifierContract:
    def notifier(self) -> Notifier:
        raise NotImplementedError

    def test_an_alert_is_accepted_without_an_answer(self) -> None:
        self.assertIsNone(self.notifier().notify(ALERT))

    def test_the_same_alert_is_accepted_again(self) -> None:
        notifier = self.notifier()
        notifier.notify(ALERT)
        self.assertIsNone(notifier.notify(ALERT))


class TestRecordingNotifierKeepsTheContract(NotifierContract, unittest.TestCase):
    def notifier(self) -> Notifier:
        return RecordingNotifier()


if __name__ == "__main__":
    unittest.main()
