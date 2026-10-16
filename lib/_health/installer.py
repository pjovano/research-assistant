from __future__ import annotations

import os
import subprocess
from collections.abc import Callable

from _health.launch_agent import AGENT_LABEL, LaunchAgent

LAUNCHCTL_TIMEOUT_SECONDS = 10

Runner = Callable[[list[str]], subprocess.CompletedProcess]


class LaunchAgentError(RuntimeError):
    pass


def run_launchctl(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *arguments], capture_output=True, text=True,
                          timeout=LAUNCHCTL_TIMEOUT_SECONDS)


class Launchctl:
    def __init__(self, run: Runner = run_launchctl) -> None:
        self._run = run
        self._domain = f"gui/{os.getuid()}"

    def is_loaded(self) -> bool:
        return self._run(["print", self._service()]).returncode == 0

    def bootout(self) -> None:
        self._run(["bootout", self._service()])

    def bootstrap(self, agent: LaunchAgent) -> None:
        completed = self._run(["bootstrap", self._domain, str(agent.path)])
        if completed.returncode != 0:
            raise LaunchAgentError(f"launchctl bootstrap {agent.path} failed: {completed.stderr.strip()}")

    def _service(self) -> str:
        return f"{self._domain}/{AGENT_LABEL}"


class LaunchAgentInstaller:
    def __init__(self, agent: LaunchAgent, launchctl: Launchctl) -> None:
        self._agent = agent
        self._launchctl = launchctl

    def needs_install(self) -> bool:
        return self._agent.script_exists and (not self._agent.is_current() or not self._launchctl.is_loaded())

    def install(self) -> None:
        if not self._agent.is_current():
            self._agent.write()
            self._launchctl.bootout()
        if not self._launchctl.is_loaded():
            self._launchctl.bootstrap(self._agent)
