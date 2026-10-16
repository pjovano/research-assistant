from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass

OTHER_PREFIX = "other:"


@dataclass(frozen=True)
class ProcessReading:
    pid: int
    started: float
    label: str
    rss_mb: float
    threads: int

    @property
    def identity(self) -> str:
        return f"{self.label}:{self.pid}:{int(self.started)}"

    @property
    def is_workload(self) -> bool:
        return not self.label.startswith(OTHER_PREFIX)


@dataclass(frozen=True)
class SystemReading:
    available_mb: float
    swap_used_mb: float | None
    pressure: str | None
    load: float
    disk_free_gb: float
    thermal: str | None = None


@dataclass(frozen=True)
class Sample:
    taken_at: float
    system: SystemReading
    processes: tuple[ProcessReading, ...]

    def labels(self) -> set[str]:
        return {process.label for process in self.processes}

    def as_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(record: dict) -> "Sample":
        processes = tuple(ProcessReading(**process) for process in record["processes"])
        return Sample(record["taken_at"], SystemReading(**record["system"]), processes)


@dataclass(frozen=True)
class Alert:
    key: str
    kind: str
    message: str
    raised_at: float

    def as_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(record: dict) -> "Alert":
        return Alert(**record)


def process_series(samples: list[Sample]) -> dict[str, list[tuple[float, ProcessReading]]]:
    series: dict[str, list[tuple[float, ProcessReading]]] = defaultdict(list)
    for sample in samples:
        for process in sample.processes:
            series[process.identity].append((sample.taken_at, process))
    return dict(series)
