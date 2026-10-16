from __future__ import annotations

from dataclasses import dataclass

import zotero

from _file.notes import CorpusNote
from _file.paths import NotePaths

WRITE = "write"
UNCHANGED = "unchanged"
NO_CITEKEY = "skip (no citekey)"
UNRESOLVED = "unresolved (no link from Zotero)"
LOOKUP_FAILED = "lookup-failed"


@dataclass(frozen=True)
class RelinkRow:
    pdf_name: str
    action: str
    current: str | None
    resolved: str | None

    @property
    def is_write(self) -> bool:
        return self.action == WRITE

    def as_dict(self) -> dict:
        return {"file": self.pdf_name, "action": self.action,
                "current": self.current, "resolved": self.resolved}


class Relinker:
    def __init__(self, pdf_names: list[str]) -> None:
        self._pdf_names = pdf_names

    @classmethod
    def over_all_notes(cls) -> "Relinker":
        paths = NotePaths()
        return cls([paths.pdf_name_of(path) for path in paths.notes()])

    def rows(self) -> list[RelinkRow]:
        return [self._row(CorpusNote(name)) for name in self._pdf_names]

    def write(self, rows: list[RelinkRow]) -> None:
        for row in rows:
            if row.is_write:
                CorpusNote(row.pdf_name).relink(row.resolved)

    def _row(self, note: CorpusNote) -> RelinkRow:
        if not note.exists():
            raise SystemExit(f"No corpus file for {note.path.stem}")
        fields = note.fields()
        current = note.link()
        citekey = fields.get("citekey")
        if not citekey:
            return RelinkRow(note.pdf_name, NO_CITEKEY, current, None)
        return self._resolved_row(note, current, citekey)

    def _resolved_row(self, note: CorpusNote, current: str | None, citekey: str) -> RelinkRow:
        try:
            resolved = zotero.build_pdf_link(citekey)
        except zotero.BetterBibtexError:
            return RelinkRow(note.pdf_name, LOOKUP_FAILED, current, None)
        if not resolved:
            return RelinkRow(note.pdf_name, UNRESOLVED, current, None)
        action = UNCHANGED if resolved == current else WRITE
        return RelinkRow(note.pdf_name, action, current, resolved)


class RelinkReport:
    def __init__(self, rows: list[RelinkRow]) -> None:
        self._rows = rows

    def render_applied(self) -> dict:
        return self._render(written=self._writes())

    def render(self) -> dict:
        return self._render(written=0)

    def _render(self, written: int) -> dict:
        return {
            "notes_examined": len(self._rows),
            "links_to_write": self._writes(),
            "written": written,
            "rows": [row.as_dict() for row in self._rows if row.action != UNCHANGED],
        }

    def _writes(self) -> int:
        return sum(1 for row in self._rows if row.is_write)
