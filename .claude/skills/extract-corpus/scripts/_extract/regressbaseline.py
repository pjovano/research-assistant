from __future__ import annotations

from pathlib import Path

import vault

from _extract.acceptance import unlinked
from _extract.paths import CorpusFile

REGRESSIONS_DIR_NAME = "regressions"
BASELINE_DIR_NAME = "baseline"
BASELINE_SAVE = "save"
BASELINE_COMPARE = "compare"
BASELINE_MODES = (BASELINE_SAVE, BASELINE_COMPARE)
_ENCODING = "utf-8"


class CorpusReference:
    def stored(self, note: CorpusFile) -> str | None:
        return unlinked(note.body())

    def keep(self, note: CorpusFile, rebuilt: str) -> None:
        pass


class BaselineSaving(CorpusReference):
    def keep(self, note: CorpusFile, rebuilt: str) -> None:
        path = baseline_path(note)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rebuilt.strip() + "\n", encoding=_ENCODING)


class BaselineReference(CorpusReference):
    def stored(self, note: CorpusFile) -> str | None:
        path = baseline_path(note)
        return path.read_text(encoding=_ENCODING).strip() if path.is_file() else None


def reference_for(mode: str | None) -> CorpusReference:
    if mode == BASELINE_SAVE:
        return BaselineSaving()
    return BaselineReference() if mode == BASELINE_COMPARE else CorpusReference()


def baseline_path(note: CorpusFile) -> Path:
    return vault.SCRATCH_DIR / REGRESSIONS_DIR_NAME / BASELINE_DIR_NAME / f"{note.basename}.md"
