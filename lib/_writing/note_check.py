from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .atomic_note import PARTS, RELATION_RE, AtomicNote, source_of
from .claims import MAX_CLAIMS, MAX_STATEMENT_LINES, REVIEW_MARK, ClaimsBlock
from .task_list import ACCEPT_TASK, TAG_SEPARATOR, TaskList
from .tree import WritingFolders

QUOTATION_RELATIONS = ("states", "supports", "explicates", "discusses")
QUOTE_MARK = ">"
QUOTATION_LINE_RE = re.compile(r"^> \*\*(?P<relation>[^*]+)\*\* · “(?P<quotation>.+)”(?: #(?:review|accepted))?$")
SOURCE_LINE_RE = re.compile(r"^> \t\[\[(?P<source>[^\]|#]+)\]\], \S")
MIN_REFERENCE_LINES = 2
MAX_EXPLICATIONS = 1
SECONDARY = "secondary"


@dataclass(frozen=True)
class HeldSources:
    basenames: set[str]
    roles: Mapping[str, str] = field(default_factory=dict)


class Reference:
    def __init__(self, block: str) -> None:
        self._lines = block.strip().splitlines()

    def findings(self, held_sources: HeldSources) -> list[str]:
        if any(not line.startswith(QUOTE_MARK) for line in self._lines):
            return [f"{self._opening!r}: a reference is a block of lines that each open with {QUOTE_MARK!r}"]
        if len(self._lines) < MIN_REFERENCE_LINES:
            return [f"{self._opening!r}: a reference carries its quotation line, then its source line"]
        return self._quotation_findings() + self._source_findings(held_sources)

    @property
    def _opening(self) -> str:
        return self._lines[0]

    def _quotation_findings(self) -> list[str]:
        hit = QUOTATION_LINE_RE.match(self._opening)
        if hit is None:
            return [f"{self._opening!r}: a quotation line reads > **<relation>** · “<quotation>”"]
        if hit.group("relation") not in QUOTATION_RELATIONS:
            return [f"{self._opening!r}: a quotation's relation is one of {list(QUOTATION_RELATIONS)}"]
        return []

    def _source_findings(self, held_sources: HeldSources) -> list[str]:
        hit = SOURCE_LINE_RE.match(self._lines[1])
        if hit is None:
            return [f"{self._lines[1]!r}: a source line reads >, a tab, then [[<basename>]], <folio or time marker>"]
        if hit.group("source").strip() not in held_sources.basenames:
            return [f"{hit.group('source')!r}: no corpus file or transcript carries this basename"]
        return []


class NoteCheck:
    def __init__(self, folders: WritingFolders, title: str, held_sources: HeldSources) -> None:
        self._folders = folders
        self._title = title
        self._held_sources = held_sources
        self._text = self._file().read_text(encoding="utf-8")
        self._note = AtomicNote(self._text)

    def report(self) -> dict:
        return {"note": self._title, "claims": len(self._note.claims()), "references": len(self._references()),
                "to_review": self._text.count(REVIEW_MARK.strip()), "open_tasks": TaskList(self._note).open_tasks(),
                "findings": self.findings()}

    def findings(self) -> list[str]:
        return [*self._claim_findings(), *self._explication_findings(), *self._statement_findings(), *self._heading_findings(),
                *self._relation_findings(), *self._group_findings(), *self._primary_findings(), *self._task_findings(),
                *(finding for reference in self._references() for finding in reference.findings(self._held_sources))]

    def _file(self) -> Path:
        path = self._folders.atomic_note(self._title)
        if not path.is_file():
            raise ValueError(f"no note named {self._title!r} in {self._folders.notes}")
        return path

    def _references(self) -> list[Reference]:
        return [Reference(block) for block in self._note.reference_blocks()]

    def _claim_findings(self) -> list[str]:
        claims = self._note.claims()
        if not claims or len(claims) > MAX_CLAIMS:
            return [f"a note opens with one to {MAX_CLAIMS} claims: it holds {len(claims)}"]
        return ["a claim is blank"] if not all(claims) else []

    def _explication_findings(self) -> list[str]:
        return [f"claim {number} carries {count} explications besides its relations, and at most {MAX_EXPLICATIONS}"
                for number, count in enumerate(self._explication_counts(), start=1) if count > MAX_EXPLICATIONS]

    def _explication_counts(self) -> list[int]:
        return [sum(1 for line in lines if not RELATION_RE.match(line))
                for lines in ClaimsBlock(self._note.claims_block).explications()]

    def _statement_findings(self) -> list[str]:
        lines = len(self._note.claims()) + sum(self._explication_counts())
        if lines > MAX_STATEMENT_LINES:
            return [f"the claims and their explications besides relations come to {lines} lines, and at most {MAX_STATEMENT_LINES}"]
        return []

    def _primary_findings(self) -> list[str]:
        roles = {self._held_sources.roles.get(source_of(block), "") for block in self._note.reference_blocks()}
        if roles == {SECONDARY}:
            return ["every reference of the note is to secondary literature: write the primary passages it discusses"]
        return []

    def _task_findings(self) -> list[str]:
        tasks = TaskList(self._note)
        untagged = [f"{line!r}: a task opens with its thread's tag, then {TAG_SEPARATOR.strip()!r}"
                    for line in tasks.untagged()]
        if tasks.opens_with_accept_task():
            return untagged
        return [f"the tasks open with the accept task, {ACCEPT_TASK!r}: run accept --apply", *untagged]

    def _heading_findings(self) -> list[str]:
        headings = self._note.headings()
        return [] if headings == list(PARTS) else [f"a note's headings are {list(PARTS)}, in order: it holds {headings}"]

    def _group_findings(self) -> list[str]:
        groups = self._note.reference_groups()
        loose = len(groups.ungrouped())
        parted = [f"{source!r}: the references to one work stand together in their group" for source in groups.parted_works()]
        return [*([f"{loose} references stand under no group: a reference stands under a ### group"] if loose else []),
                *parted]

    def _relation_findings(self) -> list[str]:
        return [f"{relation.kind} [[{relation.target}]]: no note named {relation.target!r}"
                for relation in self._note.relations() if not self._folders.atomic_note(relation.target).is_file()]


class NoteListing:
    def __init__(self, folders: WritingFolders) -> None:
        self._files = sorted(folders.notes.glob("*.md")) if folders.notes.is_dir() else []

    def as_json(self) -> list[dict]:
        return [self._listed(file.stem, AtomicNote(file.read_text(encoding="utf-8"))) for file in self._files]

    @staticmethod
    def _listed(title: str, note: AtomicNote) -> dict:
        return {"note": title, "claims": note.claims(), "projects": note.links("projects"), "field": note.links("field"),
                "references": len(note.reference_blocks()), "open_tasks": TaskList(note).open_tasks(),
                "to_review": note.awaits_review()}
