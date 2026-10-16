from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from _extract.failures import UsageFailure

PAGE_KEY = "page"
TEXT_KEY = "text"
UNREADABLE_KEY = "unreadable"


class MalformedReadings(UsageFailure, ValueError):
    pass


@dataclass(frozen=True)
class Reading:
    file_page: int
    text: str | None

    @property
    def unreadable(self) -> bool:
        return self.text is None


class WorkerReadings:
    def __init__(self, readings: list[Reading]) -> None:
        self._by_page = {reading.file_page: reading for reading in readings}

    @classmethod
    def none(cls) -> WorkerReadings:
        return cls([])

    @classmethod
    def load(cls, path: Path) -> WorkerReadings:
        entries = cls._entries_of(path)
        if not isinstance(entries, list):
            raise MalformedReadings(f"{path}: expected a JSON list of readings")
        return cls([_ReadingParser(path).parse(entry) for entry in entries])

    @staticmethod
    def _entries_of(path: Path) -> object:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise MalformedReadings(f"{path}: the readings file cannot be read: {error}") from error
        except json.JSONDecodeError as error:
            raise MalformedReadings(f"{path}: the readings file is not valid JSON: {error}") from error

    def for_page(self, file_page: int) -> Reading | None:
        return self._by_page.get(file_page)


class _ReadingParser:
    def __init__(self, path: Path) -> None:
        self._path = path

    def parse(self, entry: object) -> Reading:
        if not isinstance(entry, dict) or not isinstance(entry.get(PAGE_KEY), int):
            raise MalformedReadings(f"{self._path}: every reading needs an integer '{PAGE_KEY}'")
        if entry.get(UNREADABLE_KEY) is True:
            return Reading(entry[PAGE_KEY], None)
        return Reading(entry[PAGE_KEY], self._text(entry))

    def _text(self, entry: dict) -> str:
        text = entry.get(TEXT_KEY)
        if not isinstance(text, str) or not text.strip():
            raise MalformedReadings(
                f"{self._path}: page {entry[PAGE_KEY]} carries neither '{TEXT_KEY}' nor '{UNREADABLE_KEY}': true")
        return text
