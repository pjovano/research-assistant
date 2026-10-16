from __future__ import annotations

import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import machine_health as health
from agent_core._adapters.host.macos_notifiers import DesktopNotifier, RemindersNotifier

ALERT = health.Alert("pressure:critical", "pressure", "memory pressure critical, 300 MB available", 0.0)
SCRIPT_FLAG = "-e"


def osascript_command(notifier) -> list[str]:
    with mock.patch("subprocess.run") as run:
        notifier.notify(ALERT)
    return run.call_args.args[0]


def script_arguments(command: list[str]) -> list[str]:
    last_script_line = max(index for index, part in enumerate(command) if part == SCRIPT_FLAG) + 1
    return command[last_script_line + 1:]


class TestTheRemindersNotifier(unittest.TestCase):
    def test_files_the_alert_in_the_machine_health_list_due_in_a_minute(self):
        command = osascript_command(RemindersNotifier(health.HEALTH_NOTICE_HEADING))
        self.assertEqual([ALERT.message, "Machine health", "60"], script_arguments(command))

    def test_tells_the_reminders_app(self):
        command = osascript_command(RemindersNotifier(health.HEALTH_NOTICE_HEADING))
        self.assertIn('tell application "Reminders"', command)


class TestTheDesktopNotifier(unittest.TestCase):
    def test_displays_the_alert_under_its_title(self):
        command = osascript_command(DesktopNotifier(health.HEALTH_NOTICE_HEADING))
        self.assertEqual([ALERT.message, "Research vault machine health"], script_arguments(command))


class TestANotifierWhoseScriptCannotRun(unittest.TestCase):
    def test_raises_nothing(self):
        with mock.patch("subprocess.run", side_effect=OSError("no osascript")):
            RemindersNotifier(health.HEALTH_NOTICE_HEADING).notify(ALERT)


if __name__ == "__main__":
    unittest.main()
