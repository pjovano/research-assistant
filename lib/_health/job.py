from __future__ import annotations

from pathlib import Path

from agent_core._ports.host import Job

from _health.settings import HEALTH_DIR
from _vault.machine import MACHINE_CONFIG_PATH

AGENT_LABEL = "com.research-assistant.machine-health"
SAMPLE_INTERVAL_SECONDS = 60
SAMPLE_COMMAND = "sample"
LOG_NAME = "launchd.log"
VENV_PYTHON = MACHINE_CONFIG_PATH.parent / "venv" / "bin" / "python"
CONTROL_PLANE = Path.home() / "Developer" / "research-assistant"
HEALTH_SCRIPT = CONTROL_PLANE / ".claude" / "skills" / "machine-health" / "scripts" / "health.py"


class HealthJob:
    def __init__(self, script: Path = HEALTH_SCRIPT, log: Path = HEALTH_DIR / LOG_NAME) -> None:
        self._script = script
        self._log = log

    @property
    def script_exists(self) -> bool:
        return self._script.is_file()

    def job(self) -> Job:
        return Job(AGENT_LABEL, (str(VENV_PYTHON), str(self._script), SAMPLE_COMMAND),
                   interval_seconds=SAMPLE_INTERVAL_SECONDS, run_at_load=True, log=self._log, background=True)
