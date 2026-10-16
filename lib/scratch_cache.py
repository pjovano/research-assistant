from __future__ import annotations

import json
import sys
from pathlib import Path

import vault

CACHE_TEMPORARY_SUFFIX = ".partial"
CACHE_NOT_WRITTEN = "cache not written"
_ENCODING = "utf-8"


class ScratchCache:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def entry(self) -> dict | None:
        try:
            loaded = json.loads(self._path.read_text(encoding=_ENCODING))
        except (OSError, ValueError):
            return None
        return loaded if isinstance(loaded, dict) else None

    def save(self, entry: dict) -> None:
        try:
            self._replaced(json.dumps(entry, ensure_ascii=True))
        except OSError as error:
            sys.stderr.write(f"{CACHE_NOT_WRITTEN}: {self._path} ({error})\n")

    def _replaced(self, text: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with vault.ReplacementFile(self._path, CACHE_TEMPORARY_SUFFIX) as replacement:
            replacement.path.write_text(text, encoding=_ENCODING)
            replacement.commit()
