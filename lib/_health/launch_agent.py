from __future__ import annotations

import plistlib
from pathlib import Path

from _vault.machine import MACHINE_CONFIG_PATH

AGENT_LABEL = "com.research-vault.machine-health"
SAMPLE_INTERVAL_SECONDS = 60
BACKGROUND_NICE = 10
VENV_PYTHON = MACHINE_CONFIG_PATH.parent / "venv" / "bin" / "python"
CONTROL_PLANE = Path.home() / "Developer" / "research-assistant"
HEALTH_SCRIPT = CONTROL_PLANE / ".claude" / "skills" / "machine-health" / "scripts" / "health.py"
DEFAULT_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{AGENT_LABEL}.plist"


class LaunchAgent:
    def __init__(self, script: Path, log: Path, plist: Path = DEFAULT_PLIST) -> None:
        self._script = script
        self._log = log
        self._plist = plist

    @property
    def path(self) -> Path:
        return self._plist

    @property
    def script_exists(self) -> bool:
        return self._script.is_file()

    def contents(self) -> bytes:
        return plistlib.dumps({
            "Label": AGENT_LABEL,
            "ProgramArguments": [str(VENV_PYTHON), str(self._script), "sample"],
            "StartInterval": SAMPLE_INTERVAL_SECONDS,
            "RunAtLoad": True,
            "ProcessType": "Background",
            "LowPriorityIO": True,
            "Nice": BACKGROUND_NICE,
            "StandardOutPath": str(self._log),
            "StandardErrorPath": str(self._log),
        })

    def is_current(self) -> bool:
        try:
            return self._plist.read_bytes() == self.contents()
        except OSError:
            return False

    def write(self) -> None:
        self._plist.parent.mkdir(parents=True, exist_ok=True)
        self._log.parent.mkdir(parents=True, exist_ok=True)
        self._plist.write_bytes(self.contents())

    def bootstrap_command(self) -> str:
        return f"launchctl bootstrap gui/$(id -u) '{self._plist}'"
