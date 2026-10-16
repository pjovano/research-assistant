from __future__ import annotations

from pathlib import Path
from typing import Callable

from citation_link import CITATION_LINK_RE

from _extract.correctionstore import TrialCorrections
from _extract.paths import CorpusFile
from _extract.records import ExtractionRecord, ExtractionRecords
from _extract.request import CLEARED_RECORD_FIELDS, EXTRACTION_MODE_FIELD, ExtractionRequest
from _extract.trial import TrialNote


class Acceptance:
    def __init__(self, note: CorpusFile, trial: TrialNote, today: str) -> None:
        self._note = note
        self._trial = trial
        self._today = today

    def accept(self) -> Path:
        return self._written(self._body_unless_another_is_written)

    def accept_replacing(self) -> Path:
        return self._written(self._trial.body)

    def _written(self, body: Callable[[], str]) -> Path:
        self._trial.require()
        written = self._note.write(body(), CLEARED_RECORD_FIELDS)
        ExtractionRecords().write(self._note.basename, self._record())
        return written

    def _body_unless_another_is_written(self) -> str:
        if self._body_is_already_written():
            return self._note.body()
        self._note.require_absent()
        return self._trial.body()

    def _body_is_already_written(self) -> bool:
        return self._note.has_body() and unlinked(self._note.body()) == unlinked(self._trial.body())

    def _record(self) -> ExtractionRecord:
        meta = self._trial.frontmatter()
        request = ExtractionRequest.from_record(meta, self._note.basename)
        corrections = tuple(TrialCorrections(self._note).load())
        return ExtractionRecord(request, meta.get(EXTRACTION_MODE_FIELD), self._today, corrections)


def unlinked(body: str) -> str:
    return CITATION_LINK_RE.sub("", body).strip()
