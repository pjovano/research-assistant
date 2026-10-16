from __future__ import annotations

import os
import shutil
from pathlib import Path

import psutil
from agent_core._ports.host import Level, SystemReadings

from _health.readings import ProcessReading, Sample, SystemReading
from _health.workloads import WorkloadLabels

BYTES_PER_MB = 1024 * 1024
BYTES_PER_GB = BYTES_PER_MB * 1024
PROCESS_ATTRIBUTES = ("pid", "create_time", "cmdline", "name", "memory_info", "num_threads")
PRESSURE_SPELLINGS = {Level.NORMAL: "normal", Level.ELEVATED: "warn", Level.CRITICAL: "critical"}
THERMAL_SPELLINGS = {Level.NORMAL: "nominal", Level.ELEVATED: "fair", Level.SERIOUS: "serious",
                     Level.CRITICAL: "critical"}


class SystemProbes:
    def __init__(self, disk: Path, readings: SystemReadings) -> None:
        self._disk = disk
        self._readings = readings

    def reading(self) -> SystemReading:
        available_mb = psutil.virtual_memory().available / BYTES_PER_MB
        disk_free_gb = shutil.disk_usage(self._disk).free / BYTES_PER_GB
        pressure = PRESSURE_SPELLINGS.get(self._readings.memory_pressure())
        thermal = THERMAL_SPELLINGS.get(self._readings.thermal())
        return SystemReading(available_mb, self._swap_used_mb(), pressure, os.getloadavg()[0], disk_free_gb, thermal)

    def _swap_used_mb(self) -> float | None:
        swap_bytes = self._readings.swap_used()
        return None if swap_bytes is None else swap_bytes / BYTES_PER_MB


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
