from __future__ import annotations

from pathlib import Path

from _drive import work as drive

INITIAL_STATE = {"flags": [], "scope_runs": 0}
READINGS_PATTERN = "readings-*.json"


class BackfillQueue(drive.BackfillQueue):
    def __init__(self, directory: Path) -> None:
        super().__init__(directory, INITIAL_STATE)
