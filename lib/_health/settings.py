from __future__ import annotations

from pathlib import Path

from _vault.machine import MACHINE_CONFIG_PATH

HEALTH_KEY = "health"
HEALTH_DIR = MACHINE_CONFIG_PATH.parent / "cache" / "health"
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400

DEFAULTS = {
    "alert_cooldown_minutes": 60,
    "retention_days": 14,
    "other_processes_kept": 5,
}


class HealthSettings:
    def __init__(self, machine: dict, directory: Path = HEALTH_DIR) -> None:
        self._values = {**DEFAULTS, **(machine.get(HEALTH_KEY) or {})}
        self._directory = directory

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def alert_cooldown_seconds(self) -> float:
        return self._minutes("alert_cooldown_minutes")

    @property
    def retention_seconds(self) -> float:
        return float(self._values["retention_days"]) * SECONDS_PER_DAY

    @property
    def other_processes_kept(self) -> int:
        return int(self._values["other_processes_kept"])

    def _minutes(self, key: str) -> float:
        return float(self._values[key]) * SECONDS_PER_MINUTE
