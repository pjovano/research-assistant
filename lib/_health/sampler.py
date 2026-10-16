from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import psutil

from _health.readings import ProcessReading, Sample, SystemReading
from _health.workloads import WorkloadLabels

BYTES_PER_MB = 1024 * 1024
BYTES_PER_GB = BYTES_PER_MB * 1024
PROCESS_ATTRIBUTES = ("pid", "create_time", "cmdline", "name", "memory_info", "num_threads")
PRESSURE_COMMAND = ("sysctl", "-n", "kern.memorystatus_vm_pressure_level")
PRESSURE_LEVELS = {"1": "normal", "2": "warn", "4": "critical"}
PRESSURE_TIMEOUT_SECONDS = 5
THERMAL_STATES = ("nominal", "fair", "serious", "critical")


class ThermalState:
    def reading(self) -> str | None:
        level = self._level()
        return THERMAL_STATES[level] if level in range(len(THERMAL_STATES)) else None

    @staticmethod
    def _level() -> int | None:
        try:
            from Foundation import NSProcessInfo
        except ImportError:
            return None
        return int(NSProcessInfo.processInfo().thermalState())


class SystemProbes:
    def __init__(self, disk: Path, thermal: ThermalState | None = None) -> None:
        self._disk = disk
        self._thermal = thermal or ThermalState()

    def reading(self) -> SystemReading:
        available_mb = psutil.virtual_memory().available / BYTES_PER_MB
        disk_free_gb = shutil.disk_usage(self._disk).free / BYTES_PER_GB
        return SystemReading(available_mb, self._swap_used_mb(), self._pressure(), os.getloadavg()[0], disk_free_gb,
                             self._thermal.reading())

    @staticmethod
    def _swap_used_mb() -> float | None:
        try:
            return psutil.swap_memory().used / BYTES_PER_MB
        except OSError:
            return None

    @staticmethod
    def _pressure() -> str | None:
        try:
            result = subprocess.run(PRESSURE_COMMAND, capture_output=True, text=True, timeout=PRESSURE_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError):
            return None
        return PRESSURE_LEVELS.get(result.stdout.strip())


class Sampler:
    def __init__(self, probes: SystemProbes, labels: WorkloadLabels, other_processes_kept: int) -> None:
        self._probes = probes
        self._labels = labels
        self._other_processes_kept = other_processes_kept

    def sample(self, taken_at: float) -> Sample:
        return Sample(taken_at, self._probes.reading(), tuple(self._kept(self._processes())))

    def _kept(self, readings: list[ProcessReading]) -> list[ProcessReading]:
        others = sorted((reading for reading in readings if not reading.is_workload),
                        key=lambda reading: reading.rss_mb, reverse=True)
        workload = [reading for reading in readings if reading.is_workload]
        return workload + others[:self._other_processes_kept]

    def _processes(self) -> list[ProcessReading]:
        readings = (self._reading(process.info) for process in psutil.process_iter(PROCESS_ATTRIBUTES))
        return [reading for reading in readings if reading]

    def _reading(self, info: dict) -> ProcessReading | None:
        if info["memory_info"] is None:
            return None
        label = self._labels.label(info["cmdline"] or [], info["name"] or str(info["pid"]))
        rss_mb = info["memory_info"].rss / BYTES_PER_MB
        return ProcessReading(info["pid"], info["create_time"], label, rss_mb, info["num_threads"] or 0)
