from __future__ import annotations

from pathlib import Path

import vault
import yaml
from _writing.reading_list import ProjectReadingLists, ReadingListFile, ReadingListRefresh

STATE_READ = "read"


class PlacedWorks:
    def __init__(self, notes: list[Path]) -> None:
        self._notes = notes

    def basenames(self) -> list[str]:
        return [vault.basename_of(note) for note in self._notes if self._is_placed(note)]

    @staticmethod
    def _is_placed(note: Path) -> bool:
        try:
            meta = vault.read_frontmatter_only(note)
        except yaml.YAMLError:
            return False
        return bool(vault.field_topics(meta))


class ReadingsStep:
    def __init__(self, lists: ProjectReadingLists, placed: PlacedWorks) -> None:
        self._lists = lists
        self._placed = placed

    def run(self) -> dict:
        wanting = self._lists.wanting()
        placed = self._placed.basenames() if wanting else []
        checked_off = [line for file in wanting for line in self._checked_off(file, placed)]
        return {"state": STATE_READ, "checked_off": checked_off, "questions": []}

    @staticmethod
    def _checked_off(file: ReadingListFile, placed: list[str]) -> list[str]:
        refresh = ReadingListRefresh(file, placed)
        moved = refresh.plan()["moved_to_held"]
        if moved:
            refresh.apply()
        return [f"{file.project}: {line}" for line in moved]
