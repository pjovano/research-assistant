from __future__ import annotations

from _support import LiveTree

LiveTree.activate()

import machine_health as health

MINUTE = 60.0
START = 1_790_000_000.0
BASE_RSS_MB = 1000.0
AVAILABLE_MB = 8000.0
DISK_FREE_GB = 200.0


def process(label: str, rss_mb: float, pid: int = 100) -> health.ProcessReading:
    return health.ProcessReading(pid, START - MINUTE, label, rss_mb, 4)


def system(pressure: str | None = "normal", thermal: str | None = "nominal") -> health.SystemReading:
    return health.SystemReading(AVAILABLE_MB, 0.0, pressure, 1.0, DISK_FREE_GB, thermal)


def sample(minute: int, processes: tuple[health.ProcessReading, ...] = (),
           reading: health.SystemReading | None = None) -> health.Sample:
    return health.Sample(START + minute * MINUTE, reading or system(), processes)


def rss_series(rss_at_minute, minutes: int = 60, label: str = "model-server") -> list[health.Sample]:
    return [sample(minute, (process(label, rss_at_minute(minute)),)) for minute in range(minutes + 1)]



class ScriptedSampler:
    def __init__(self, samples: list[health.Sample]) -> None:
        self._samples = {sample.taken_at: sample for sample in samples}

    def sample(self, taken_at: float) -> health.Sample:
        return self._samples[taken_at]


class RecordingNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def notify(self, alert: health.Alert) -> None:
        self.messages.append(alert.message)
