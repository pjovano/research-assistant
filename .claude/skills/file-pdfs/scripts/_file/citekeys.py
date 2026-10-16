from __future__ import annotations

from pathlib import Path

import vault
import zotero

from _file.paths import NotePaths

_UNKNOWN_SURNAME = "unknown"


class CitekeyAllocator:
    def __init__(self) -> None:
        self._paths = NotePaths()

    def for_meta(self, meta: dict, exclude_stem: str | None = None) -> str:
        base = vault.citekey(self._first_surname(meta), vault.citekey_year(meta))
        return vault.unique_citekey(base, self._taken(exclude_stem) | zotero.held_citekeys_beginning(base))

    def _first_surname(self, meta: dict) -> str:
        authors = meta.get("authors")
        return authors[0]["lastName"] if authors else _UNKNOWN_SURNAME

    def _taken(self, exclude_stem: str | None) -> set[str]:
        paths = self._paths.notes() + self._paths.drafts()
        excluded = vault.nfc(exclude_stem or "")
        claimed = (self._citekey_in(path) for path in paths if vault.basename_of(path) != excluded)
        return {key for key in claimed if key}

    def _citekey_in(self, path: Path) -> str | None:
        return vault.read_frontmatter_only(path).get("citekey") or None
