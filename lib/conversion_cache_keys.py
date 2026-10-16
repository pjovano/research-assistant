from __future__ import annotations

import json
from pathlib import Path

import pagetext
import vault

CONVERSION_CACHE_NAME_TEMPLATE = "marker-{mode}-layout.json"
CONVERSION_FINGERPRINT_KEY = "fingerprint"
_EVERY_MODE = "*"
_ENCODING = "utf-8"


class CachedConversionsKept:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path
        self._kept: list[Path] = []

    def __enter__(self) -> CachedConversionsKept:
        self._kept = [path for path in self._cache_paths() if self._is_current(path)]
        return self

    def __exit__(self, failure_type, _failure, _traceback) -> bool:
        if failure_type is None:
            for path in self._kept:
                self._rekey(path)
        return False

    def _cache_paths(self) -> list[Path]:
        directory = vault.SCRATCH_DIR / vault.basename_of(self._pdf_path)
        return sorted(directory.glob(CONVERSION_CACHE_NAME_TEMPLATE.format(mode=_EVERY_MODE)))

    def _is_current(self, path: Path) -> bool:
        entry = _entry_of(path)
        return entry is not None and entry.get(CONVERSION_FINGERPRINT_KEY) == self._fingerprint()

    def _rekey(self, path: Path) -> None:
        entry = _entry_of(path)
        if entry is not None:
            entry[CONVERSION_FINGERPRINT_KEY] = self._fingerprint()
            path.write_text(json.dumps(entry, ensure_ascii=False), encoding=_ENCODING)

    def _fingerprint(self) -> list:
        return list(pagetext.document_fingerprint(self._pdf_path))


def _entry_of(path: Path) -> dict | None:
    try:
        entry = json.loads(path.read_text(encoding=_ENCODING))
    except (OSError, ValueError):
        return None
    return entry if isinstance(entry, dict) else None
