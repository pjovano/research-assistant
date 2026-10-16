from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path

import vault

VERDICTS_FILE_NAME = "citation-verdicts.json"
CONFIRM = "confirm"
REJECT = "reject"
VERDICTS = (CONFIRM, REJECT)
MAX_MERGE_ATTEMPTS = 3


class VerdictsFileCorrupt(LookupError):
    pass


class VerdictsFileChanging(LookupError):
    pass


@dataclass(frozen=True)
class Verdict:
    citing: str
    entry: str
    work: str
    verdict: str

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise LookupError(f"a verdict is one of {', '.join(VERDICTS)}, not '{self.verdict}'")

    def as_dict(self) -> dict:
        return {"citing": self.citing, "entry": self.entry, "work": self.work, "verdict": self.verdict}


class CitingVerdicts:
    def __init__(self, by_entry: dict) -> None:
        self._by_entry = by_entry

    def on(self, entry: str, work: str) -> str | None:
        return self._by_entry.get(vault.nfc(entry), {}).get(vault.nfc(work))

    def confirms(self, entry: str, work: str) -> bool:
        return self.on(entry, work) == CONFIRM


class CitationVerdicts:
    def __init__(self, path: Path | None = None) -> None:
        self._given_path = path
        self._loaded: dict | None = None

    @property
    def path(self) -> Path:
        return self._given_path or vault.LIBRARY_DIR / VERDICTS_FILE_NAME

    def of(self, citing: str) -> CitingVerdicts:
        if self._loaded is None:
            self._loaded = _VerdictsFile(self.path).entries()
        return CitingVerdicts(self._loaded.get(vault.nfc(citing), {}))

    def record(self, verdicts: list[Verdict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _attempt in range(MAX_MERGE_ATTEMPTS):
            with contextlib.suppress(vault.NoteChangedOnDisk):
                _VerdictsFile(self.path).merge(verdicts)
                self._loaded = None
                return
        raise VerdictsFileChanging(f"{self.path} changed on disk during each of {MAX_MERGE_ATTEMPTS} attempts to "
                                   "record the verdicts; nothing was recorded. Run the command again.")


class _VerdictsFile:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._guard = vault.GuardedNote(path)

    def entries(self) -> dict:
        if not self._path.is_file():
            return {}
        return self._parsed(self._guard.text())

    def merge(self, verdicts: list[Verdict]) -> None:
        entries = self.entries()
        for verdict in verdicts:
            by_entry = entries.setdefault(vault.nfc(verdict.citing), {})
            by_entry.setdefault(vault.nfc(verdict.entry), {})[vault.nfc(verdict.work)] = verdict.verdict
        self._guard.replace(json.dumps(entries, indent=2, ensure_ascii=False, sort_keys=True) + "\n")

    def _parsed(self, text: str) -> dict:
        try:
            parsed = json.loads(text)
        except ValueError as failure:
            raise VerdictsFileCorrupt(f"{self._path} is not valid JSON ({failure}); "
                                      "restore it from a backup before any verdict is read or recorded") from failure
        if not isinstance(parsed, dict):
            raise VerdictsFileCorrupt(f"{self._path} holds no JSON object of verdicts; "
                                      "restore it from a backup before any verdict is read or recorded")
        return parsed
