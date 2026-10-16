from __future__ import annotations

import json
from pathlib import Path

import pagetext
import vault
from conversion_cache_keys import CONVERSION_CACHE_NAME_TEMPLATE as _CACHE_NAME_TEMPLATE
from conversion_cache_keys import CONVERSION_FINGERPRINT_KEY as _FINGERPRINT_KEY

from _extract.blocks import DocumentBlocks
from _extract.heldpages import HeldConversion, HeldPages, held_conversion

_CACHE_NAME_PREFIX, _CACHE_NAME_SUFFIX = _CACHE_NAME_TEMPLATE.split("{mode}")
_PAGES_KEY = "pages"
_PAYLOAD_KEY = "payload"


class MarkerCache:
    def __init__(self, pdf_path: Path, mode: str) -> None:
        self._pdf_path = pdf_path
        self._path = vault.SCRATCH_DIR / vault.basename_of(pdf_path) / _CACHE_NAME_TEMPLATE.format(mode=mode)

    def load(self, file_pages: list[int]) -> dict | None:
        return self._current().payload(file_pages)

    def holds(self, file_pages: list[int]) -> bool:
        return not self.missing(file_pages)

    def missing(self, file_pages: list[int]) -> list[int]:
        return self._current().missing(file_pages)

    def save(self, file_pages: list[int], payload: dict) -> None:
        self._write(held_conversion(file_pages, payload).merged_over(self._current()))

    def is_current(self) -> bool:
        return self._is_current(self._entry())

    def _current(self) -> HeldConversion:
        entry = self._entry()
        return _held_in(entry) if self._is_current(entry) else HeldPages({})

    def _is_current(self, entry: dict | None) -> bool:
        return entry is not None and entry.get(_FINGERPRINT_KEY) == self._fingerprint()

    def _write(self, held: HeldConversion) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        file_pages = held.file_pages
        entry = {_FINGERPRINT_KEY: self._fingerprint(), _PAGES_KEY: file_pages, _PAYLOAD_KEY: held.payload(file_pages)}
        self._path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")

    def _entry(self) -> dict | None:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _fingerprint(self) -> list:
        return list(pagetext.document_fingerprint(self._pdf_path))


def _held_in(entry: dict) -> HeldConversion:
    return held_conversion(entry.get(_PAGES_KEY) or [], entry.get(_PAYLOAD_KEY) or {})


class CachedConversion:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._read: dict | None = None

    def empty_pages(self) -> list[int]:
        entry = self._entry()
        file_pages = entry.get(_PAGES_KEY) or []
        pages = DocumentBlocks.from_json(entry.get(_PAYLOAD_KEY) or {}, file_pages).pages
        return [page.file_page for page in pages if not page.blocks]

    def as_dict(self) -> dict:
        return {"basename": self._path.parent.name, "mode": self._mode(), "cache": str(self._path),
                "pages": len(self._entry().get(_PAGES_KEY) or []), "empty_pages": self.empty_pages()}

    def _mode(self) -> str:
        return self._path.name.removeprefix(_CACHE_NAME_PREFIX).removesuffix(_CACHE_NAME_SUFFIX)

    def _entry(self) -> dict:
        if self._read is None:
            self._read = self._parsed()
        return self._read

    def _parsed(self) -> dict:
        try:
            entry = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return entry if isinstance(entry, dict) else {}


class CachedConversions:
    def __init__(self, scratch_dir: Path | None = None) -> None:
        self._scratch_dir = scratch_dir or vault.SCRATCH_DIR

    def with_empty_pages(self) -> list[dict]:
        listed = [conversion.as_dict() for conversion in self._conversions() if conversion.empty_pages()]
        return sorted(listed, key=_share_of_empty_pages, reverse=True)

    def _conversions(self) -> list[CachedConversion]:
        pattern = _CACHE_NAME_TEMPLATE.format(mode="*")
        return [CachedConversion(path) for path in sorted(self._scratch_dir.glob(f"*/{pattern}"))]


def _share_of_empty_pages(listed: dict) -> float:
    return len(listed["empty_pages"]) / max(listed["pages"], 1)
