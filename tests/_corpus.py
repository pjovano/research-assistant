from __future__ import annotations

from _support import FIXTURES_DIR, JsonDocument


class RecordPair:
    def __init__(self, basename: str, sidecar: dict, bib: dict) -> None:
        self._basename = basename
        self._sidecar = sidecar
        self._bib = bib

    @property
    def basename(self) -> str:
        return self._basename

    @property
    def sidecar(self) -> dict:
        return dict(self._sidecar)

    @property
    def bib(self) -> dict:
        return dict(self._bib)

    @classmethod
    def from_dict(cls, payload: dict) -> "RecordPair":
        return cls(payload["basename"], payload["sidecar"], payload["bib"])


class FrozenCorpus:
    _DOCUMENT = JsonDocument(FIXTURES_DIR / "records.json")

    @classmethod
    def pairs(cls) -> list[RecordPair]:
        return [RecordPair.from_dict(entry) for entry in cls._DOCUMENT.load()]
