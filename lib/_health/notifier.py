from __future__ import annotations

import subprocess

from _health.readings import Alert

NOTIFICATION_TITLE = "Research vault machine health"
REMINDER_LIST = "Machine health"
REMINDER_LEAD_SECONDS = 60
OSASCRIPT_TIMEOUT_SECONDS = 30
DISPLAY_SCRIPT = ("on run arguments", "display notification (item 1 of arguments) with title (item 2 of arguments)",
                  "end run")
REMINDER_SCRIPT = (
    "on run arguments",
    "set listName to item 2 of arguments",
    'tell application "Reminders"',
    "if not (exists list listName) then make new list with properties {name:listName}",
    "tell list listName to make new reminder with properties "
    "{name:(item 1 of arguments), remind me date:((current date) + (item 3 of arguments as integer))}",
    "end tell",
    "end run",
)


class AppleScript:
    def __init__(self, lines: tuple[str, ...]) -> None:
        self._lines = lines

    def run(self, *arguments: str) -> None:
        try:
            subprocess.run(self._command(*arguments), capture_output=True, timeout=OSASCRIPT_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError):
            return

    def _command(self, *arguments: str) -> list[str]:
        script = [part for line in self._lines for part in ("-e", line)]
        return ["osascript", *script, *arguments]


class DesktopNotifier:
    def __init__(self) -> None:
        self._script = AppleScript(DISPLAY_SCRIPT)

    def notify(self, alert: Alert) -> None:
        self._script.run(alert.message, NOTIFICATION_TITLE)


class RemindersNotifier:
    def __init__(self) -> None:
        self._script = AppleScript(REMINDER_SCRIPT)

    def notify(self, alert: Alert) -> None:
        self._script.run(alert.message, REMINDER_LIST, str(REMINDER_LEAD_SECONDS))
