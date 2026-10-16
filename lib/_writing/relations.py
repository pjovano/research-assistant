from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .atomic_note import NOTE_RELATIONS, AtomicNote
from .claims import marked_for_review
from .linked_note import wikilink
from .tree import WritingFolders
from .saved import save_text

RELATIONS = NOTE_RELATIONS


@dataclass(frozen=True)
class RelationLine:
    kind: str
    target: str
    gloss: str = ""
    proposed: bool = False

    @property
    def text(self) -> str:
        line = ": ".join(part for part in (f"{self.kind} {wikilink(self.target)}", self.gloss.strip()) if part)
        return marked_for_review(line) if self.proposed else line


class NoteRelation:
    def __init__(self, folders: WritingFolders, source: str, line: RelationLine) -> None:
        self._source = source
        self._file = folders.atomic_note(source)
        self._line = line.text
        RelationChecks(folders, line.kind).run(source, line.target)

    def plan(self) -> dict:
        return {"note": self._source, "line": self._line}

    def apply(self) -> None:
        note = AtomicNote(self._file.read_text(encoding="utf-8"))
        save_text(self._file, note.with_explication(self._line).text)


class RelationChecks:
    def __init__(self, folders: WritingFolders, relation: str) -> None:
        self._folders = folders
        self._relation = relation

    def run(self, source: str, target: str) -> None:
        if self._relation not in RELATIONS:
            raise ValueError(f"a relation is one of {list(RELATIONS)}")
        if source == target:
            raise ValueError(f"{source!r} never relates to itself")
        for title in (source, target):
            self._require_note(self._folders.atomic_note(title), title)
        if target in self._related_to(source):
            raise ValueError(f"{source!r} relates to {target!r} already: change its line in the note")

    def _related_to(self, source: str) -> list[str]:
        note = AtomicNote(self._folders.atomic_note(source).read_text(encoding="utf-8"))
        return [relation.target for relation in note.relations()]

    def _require_note(self, path: Path, title: str) -> None:
        if not path.is_file():
            raise ValueError(f"no note named {title!r} in {self._folders.notes}")
