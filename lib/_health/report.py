from __future__ import annotations

from datetime import datetime

from _health.readings import Alert, ProcessReading, Sample, process_series
from _health.settings import SECONDS_PER_HOUR

PRESSURE_RANK = {None: 0, "normal": 1, "warn": 2, "critical": 3}
THERMAL_RANK = {None: 0, "nominal": 1, "fair": 2, "serious": 3, "critical": 4}


class HealthReport:
    def __init__(self, samples: list[Sample], alerts: list[Alert]) -> None:
        self._samples = samples
        self._alerts = alerts

    def as_dict(self) -> dict:
        if not self._samples:
            return {"samples": 0, "alerts": [self._alert(alert) for alert in self._alerts]}
        return {"from": self._stamp(self._samples[0].taken_at), "to": self._stamp(self._samples[-1].taken_at),
                "samples": len(self._samples), "system": self._system(), "processes": self._processes(),
                "alerts": [self._alert(alert) for alert in self._alerts]}

    def _system(self) -> dict:
        systems = [sample.system for sample in self._samples]
        swaps = [system.swap_used_mb for system in systems if system.swap_used_mb is not None]
        return {"min_available_mb": round(min(system.available_mb for system in systems)),
                "max_swap_used_mb": round(max(swaps)) if swaps else None,
                "worst_pressure": max((system.pressure for system in systems), key=PRESSURE_RANK.get),
                "max_load": round(max(system.load for system in systems), 1),
                "min_disk_free_gb": round(min(system.disk_free_gb for system in systems), 1),
                "worst_thermal": max((system.thermal for system in systems), key=THERMAL_RANK.get)}

    def _processes(self) -> list[dict]:
        rows = [self._process(points) for points in process_series(self._samples).values()]
        return sorted(rows, key=lambda row: row["growth_mb_per_hour"], reverse=True)

    @staticmethod
    def _process(points: list[tuple[float, ProcessReading]]) -> dict:
        (first_time, first), (last_time, last) = points[0], points[-1]
        hours = (last_time - first_time) / SECONDS_PER_HOUR
        growth = (last.rss_mb - first.rss_mb) / hours if hours > 0 else 0.0
        return {"label": last.label, "pid": last.pid, "first_mb": round(first.rss_mb), "last_mb": round(last.rss_mb),
                "peak_mb": round(max(reading.rss_mb for _, reading in points)),
                "growth_mb_per_hour": round(growth), "hours_seen": round(hours, 2)}

    def _alert(self, alert: Alert) -> dict:
        return {"at": self._stamp(alert.raised_at), "kind": alert.kind, "message": alert.message}

    @staticmethod
    def _stamp(at: float) -> str:
        return datetime.fromtimestamp(at).isoformat(timespec="minutes")
