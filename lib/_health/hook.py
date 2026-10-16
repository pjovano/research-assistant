from __future__ import annotations

import subprocess
import sys

from _health.installer import Launchctl, LaunchAgentInstaller
from _health.launch_agent import HEALTH_SCRIPT, LaunchAgent
from _health.settings import HEALTH_DIR

PIPELINE_SKILLS = ("clean-pdfs", "file-pdfs", "extract-corpus", "classify-and-place", "cite-links", "search",
                   "extract-chapters", "transcribe-talks")
WATCHED_PLATFORM = "darwin"
LOG_NAME = "launchd.log"
HEALTH_WATCHER_STARTED = "Started the health watcher: launchd now samples this machine every minute."
HEALTH_WATCHER_FAILED = "The health watcher did not start: {error}"


class PipelineCommand:
    def __init__(self, command: str) -> None:
        self._command = command

    def runs_a_stage(self) -> bool:
        return any(f"skills/{skill}/scripts/" in self._command for skill in PIPELINE_SKILLS)


class HealthWatcherHook:
    def __init__(self, installer: LaunchAgentInstaller | None = None, platform: str = sys.platform) -> None:
        self._installer = installer or LaunchAgentInstaller(LaunchAgent(HEALTH_SCRIPT, HEALTH_DIR / LOG_NAME),
                                                            Launchctl())
        self._platform = platform

    def report(self, command: str) -> dict | None:
        if self._platform != WATCHED_PLATFORM or not PipelineCommand(command).runs_a_stage():
            return None
        return self._installed() if self._installer.needs_install() else None

    def _installed(self) -> dict:
        try:
            self._installer.install()
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            return {"systemMessage": HEALTH_WATCHER_FAILED.format(error=error)}
        return {"systemMessage": HEALTH_WATCHER_STARTED}
