from __future__ import annotations

import re
from pathlib import Path

from vault import FOOTNOTE_DEFINITION_RE

from .conversion import ExportText

ABSTRACT_RE = re.compile(r"^#+ Abstract\s*\n(?P<abstract>.*?)(?=^#+ |\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE)
REFERENCES_RE = re.compile(r"^#+ (?:References|Bibliography|Works Cited)\s*\n(?P<list>.*)\Z",
                           re.MULTILINE | re.DOTALL | re.IGNORECASE)
CONTINUATION_INDENT = ("    ", "\t")


class DraftWordCount:
    def __init__(self, draft: Path) -> None:
        self._draft = draft
        self._text = ExportText(draft.read_text(encoding="utf-8")).markdown()

    def as_json(self) -> dict:
        notes, body = self._notes(), self._body()
        references = REFERENCES_RE.search(body)
        abstract = ABSTRACT_RE.search(body)
        listed = self._words(references.group("list")) if references else 0
        return {"draft": self._draft.stem, "body": self._words(body) - listed, "notes": self._words(notes),
                "reference_list": listed, "total": self._words(body) + self._words(notes),
                "abstract": self._words(abstract.group("abstract")) if abstract else 0}

    def _notes(self) -> str:
        return "\n".join(line for line, in_note in self._marked() if in_note)

    def _body(self) -> str:
        return "\n".join(line for line, in_note in self._marked() if not in_note)

    def _marked(self) -> list[tuple[str, bool]]:
        marked, in_note = [], False
        for line in self._text.splitlines():
            in_note = bool(FOOTNOTE_DEFINITION_RE.match(line)) or (in_note and line.startswith(CONTINUATION_INDENT))
            marked.append((line, in_note))
        return marked

    @staticmethod
    def _words(text: str) -> int:
        return len(text.split())
