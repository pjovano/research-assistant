from __future__ import annotations

import json
from pathlib import Path

import vault

from _extract.failures import UsageFailure
from _extract.paths import CorpusFile

TRIALS_DIR_NAME = "trials"
REPORT_SUFFIX = ".report.json"
_ENCODING = "utf-8"


class TrialMissing(UsageFailure, FileNotFoundError):
    pass


class TrialNote:
    def __init__(self, note: CorpusFile) -> None:
        self._note = note
        self._path = vault.SCRATCH_DIR / TRIALS_DIR_NAME / f"{note.basename}.md"

    @property
    def path(self) -> Path:
        return self._path

    @property
    def report_path(self) -> Path:
        return self._path.with_name(self._path.stem + REPORT_SUFFIX)

    def exists(self) -> bool:
        return self._path.is_file()

    def require(self) -> TrialNote:
        if not self.exists():
            raise TrialMissing(f"no trial for {self._note.basename}: run extract --trial first ({self._path})")
        return self

    def write(self, text: str, fields: dict) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self._note.note_text_with(text, fields), encoding=_ENCODING)
        return self._path

    def write_body(self, text: str) -> Path:
        frontmatter, body = vault.split_note(self._path.read_text(encoding=_ENCODING))
        linked = vault.upsert_pdf_link(text, self._note.basename, vault.pdf_link_of(body))
        self._path.write_text(vault.join_note(frontmatter, linked), encoding=_ENCODING)
        return self._path

    def write_report(self, report: dict) -> None:
        self.report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding=_ENCODING)

    def report(self) -> dict:
        if not self.report_path.is_file():
            return {}
        return json.loads(self.report_path.read_text(encoding=_ENCODING))

    def frontmatter(self) -> dict:
        return vault.read_frontmatter_only(self._path)

    def body(self) -> str:
        _frontmatter, body = vault.split_note(self._path.read_text(encoding=_ENCODING))
        return vault.body_after_pdf_link(body)
