from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path

import vault

from _extract.failures import UsageFailure
from _extract.request import ExtractionRequest, RecordUnreadable

RECORDS_FILE_NAME = vault.RECORDS_FILE_NAME
MODE_KEY = "mode"
CORRECTIONS_KEY = "corrections"
REVIEWED_KEY = vault.REVIEWED_KEY
MAX_MERGE_ATTEMPTS = 3
_ENCODING = "utf-8"


class RecordsFileCorrupt(UsageFailure, ValueError):
    pass


class RecordsFileChanging(UsageFailure, RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractionRecord:
    request: ExtractionRequest
    mode: str | None = None
    reviewed: str | None = None
    corrections: tuple[dict, ...] = ()

    def stored(self) -> dict:
        optional = {MODE_KEY: self.mode, REVIEWED_KEY: self.reviewed, CORRECTIONS_KEY: list(self.corrections)}
        return {**self.request.stored(), **{key: value for key, value in optional.items() if value}}


class ExtractionRecords:
    def __init__(self, path: Path | None = None) -> None:
        self._given_path = path

    @property
    def path(self) -> Path:
        return self._given_path or vault.LIBRARY_DIR / RECORDS_FILE_NAME

    def entry(self, basename: str) -> dict | None:
        return _RecordsFile(self.path).entries().get(vault.nfc(basename))

    def request_of(self, basename: str) -> ExtractionRequest:
        stored = self.entry(basename)
        if stored is None:
            raise RecordUnreadable(f"{basename} has no extraction record in {self.path}; "
                                   "only an accepted work is rebuilt")
        return ExtractionRequest.from_stored(stored, basename)

    def reviewed(self, basename: str) -> str | None:
        return (self.entry(basename) or {}).get(REVIEWED_KEY)

    def write(self, basename: str, record: ExtractionRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _attempt in range(MAX_MERGE_ATTEMPTS):
            with contextlib.suppress(vault.NoteChangedOnDisk):
                _RecordsFile(self.path).merge(basename, record.stored())
                return
        raise RecordsFileChanging(f"{self.path} changed on disk during each of {MAX_MERGE_ATTEMPTS} attempts to "
                                  f"write the record of {basename}; nothing was written. Run the command again.")


class _RecordsFile:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._guard = vault.GuardedNote(path)

    def entries(self) -> dict:
        if not self._path.is_file():
            return {}
        return {vault.nfc(basename): stored for basename, stored in self._parsed(self._guard.text()).items()}

    def merge(self, basename: str, stored: dict) -> None:
        entries = {**self.entries(), vault.nfc(basename): stored}
        self._guard.replace(json.dumps(entries, indent=2, ensure_ascii=False, sort_keys=True) + "\n")

    def _parsed(self, text: str) -> dict:
        try:
            parsed = json.loads(text)
        except ValueError as failure:
            raise RecordsFileCorrupt(f"{self._path} is not valid JSON ({failure}); "
                                     "restore it from a backup before any record is read or written") from failure
        if not isinstance(parsed, dict):
            raise RecordsFileCorrupt(f"{self._path} holds no JSON object of records; "
                                     "restore it from a backup before any record is read or written")
        return parsed
