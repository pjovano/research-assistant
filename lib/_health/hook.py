from __future__ import annotations

import subprocess
import sys

from agent_core._adapters.host.launchd import LaunchdScheduler
from agent_core._ports.host import Scheduler

from _health.job import HealthJob

PIPELINE_SKILLS = ("clean-pdfs", "file-pdfs", "extract-corpus", "classify-and-place", "cite-links", "search",
                   "extract-chapters", "transcribe-talks")
WATCHED_PLATFORM = "darwin"
HEALTH_WATCHER_STARTED = "Started the health watcher: launchd now samples this machine every minute."
HEALTH_WATCHER_FAILED = "The health watcher did not start: {error}"


class PipelineCommand:
    def __init__(self, command: str) -> None:
        self._command = command

    def runs_a_stage(self) -> bool:
        return any(f"skills/{skill}/scripts/" in self._command for skill in PIPELINE_SKILLS)


class HealthWatcherHook:
    def __init__(self, scheduler: Scheduler | None = None, health_job: HealthJob | None = None,
                 platform: str = sys.platform) -> None:
        self._scheduler = scheduler or LaunchdScheduler()
        self._health_job = health_job or HealthJob()
        self._platform = platform

    def report(self, command: str) -> dict | None:
        if not self._watches(command) or not self._needs_install():
            return None
        return self._installed()

    def _watches(self, command: str) -> bool:
        return self._platform == WATCHED_PLATFORM and PipelineCommand(command).runs_a_stage()

    def _needs_install(self) -> bool:
        return self._health_job.script_exists and not self._scheduler.installed(self._health_job.job())

    def _installed(self) -> dict:
        try:
            self._scheduler.install(self._health_job.job())
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            return {"systemMessage": HEALTH_WATCHER_FAILED.format(error=error)}
        return {"systemMessage": HEALTH_WATCHER_STARTED}
