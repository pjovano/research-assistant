from __future__ import annotations

from pathlib import Path

import vault


class PdfLocation:
    def __init__(self, name: str) -> None:
        self._name = name

    def in_inbox(self) -> Path:
        return self._require(vault.locate_pdf(self._name, (vault.INBOX_DIR,)), "the inbox")

    def anywhere(self) -> Path:
        located = vault.locate_pdf(self._name, (vault.INBOX_DIR, vault.LIBRARY_DIR, vault.VOLUMES_DIR))
        return self._require(located, "the inbox, the library, or the volumes")

    def _require(self, located: Path | None, where: str) -> Path:
        if located is None:
            raise SystemExit(f"Not found in {where}: {self._name}")
        return located


class ScratchOutput:
    def __init__(self, given: str) -> None:
        self._given = Path(given)

    def path(self) -> Path:
        candidate = self._given if self._given.is_absolute() else vault.SCRATCH_DIR / self._given
        self._require_in_scratch(candidate)
        return candidate

    def _require_in_scratch(self, candidate: Path) -> None:
        if candidate.resolve().is_relative_to(vault.SCRATCH_DIR.resolve()):
            return
        raise SystemExit(f"--out must lie in the scratch directory {vault.SCRATCH_DIR}: {self._given}")
