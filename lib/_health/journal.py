from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

SUFFIX = ".jsonl"
ENCODING = "utf-8"


class DailyJournal:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def append(self, record: dict, at: float) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        with self._path_for(self._day(at)).open("a", encoding=ENCODING) as journal:
            journal.write(json.dumps(record, ensure_ascii=False) + "\n")

    def records_since(self, cutoff: float, time_key: str) -> list[dict]:
        records = (record for path in self._paths_from(self._day(cutoff)) for record in self._read(path))
        return [record for record in records if record[time_key] >= cutoff]

    def prune(self, cutoff: float) -> None:
        first_kept = self._day(cutoff)
        for path in self._paths():
            if self._day_of(path) < first_kept:
                path.unlink(missing_ok=True)

    def _paths_from(self, first: date) -> list[Path]:
        return [path for path in self._paths() if self._day_of(path) >= first]

    def _paths(self) -> list[Path]:
        return sorted(self._directory.glob(f"*{SUFFIX}")) if self._directory.is_dir() else []

    def _path_for(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}{SUFFIX}"

    @staticmethod
    def _read(path: Path) -> list[dict]:
        parsed = (DailyJournal._parsed(line) for line in path.read_text(encoding=ENCODING).splitlines())
        return [record for record in parsed if record is not None]

    @staticmethod
    def _parsed(line: str) -> dict | None:
        try:
            return json.loads(line)
        except ValueError:
            return None

    @staticmethod
    def _day(at: float) -> date:
        return datetime.fromtimestamp(at).date()

    @staticmethod
    def _day_of(path: Path) -> date:
        return date.fromisoformat(path.stem)
