from __future__ import annotations

import re
from dataclasses import dataclass, field

import vault
from citation_link import CITATION_LINK_PATTERN
from page_marker import PageMarker
from references import (
    DEFINITION_RE, HEADING_RE, LibraryWork, NoteLines, RepeatedAuthors, ScoredCitations, ScoredMatch,
)

from _cite.verdicts import CONFIRM, REJECT, CitingVerdicts

SCORE_DECIMALS = 1
_LINKED_ENTRY_RE = re.compile(rf"^(?P<entry>.*?){CITATION_LINK_PATTERN}$", re.DOTALL)


@dataclass(frozen=True)
class LinkedLine:
    index: int
    text: str
    basename: str


@dataclass(frozen=True)
class ConfirmableLine:
    index: int
    entry: str
    basename: str
    score: float

    @property
    def reported_score(self) -> float:
        return round(self.score, SCORE_DECIMALS)

    def names(self, entry: str, basename: str) -> bool:
        return (self.entry, self.basename) == (entry, basename)

    def as_dict(self) -> dict:
        return {"entry": self.entry, "basename": self.basename, "score": self.reported_score}


@dataclass
class LinkResolution:
    links: list[LinkedLine]
    to_confirm: list[ConfirmableLine]
    stale: list[ConfirmableLine] = field(default_factory=list)
    settled: list[ConfirmableLine] = field(default_factory=list)


class LinkTargets:
    def admits(self, work: LibraryWork) -> bool:
        return vault.corpus_path(work.basename).exists()


class EntryLine:
    def __init__(self, index: int, line: str) -> None:
        definition = DEFINITION_RE.match(line)
        self.index = index
        self._prefix = definition.group(1) if definition else ""
        text = definition.group(2) if definition else line.strip()
        linked = _LINKED_ENTRY_RE.match(text)
        self.linked_basename = linked.group("work") if linked else None
        self.entry = linked.group("entry") if linked else text

    @property
    def is_linked(self) -> bool:
        return self.linked_basename is not None

    def is_linked_to(self, work: LibraryWork) -> bool:
        return self.linked_basename == work.basename

    def linked_to(self, work: LibraryWork) -> LinkedLine:
        link = f"[[{work.basename}|{vault.CITATION_LINK_MARK}]]"
        return LinkedLine(self.index, f"{self._prefix}{self.entry} {link}", work.basename)


class EntryLines:
    def __init__(self, note: NoteLines) -> None:
        self._note = note

    def candidates(self) -> list[EntryLine]:
        lines = self._note.lines
        return [EntryLine(index, lines[index]) for index in self._indices() if self._is_candidate(lines[index])]

    def _indices(self) -> list[int]:
        return self._note.entry_indices()

    @staticmethod
    def _is_candidate(line: str) -> bool:
        stripped = line.strip()
        return bool(stripped) and not PageMarker.parsed(stripped) and not HEADING_RE.match(stripped)


@dataclass(frozen=True)
class ScoredEntry:
    line: EntryLine
    text: str


class EntryLinker:
    def __init__(self, scored: ScoredCitations, targets: LinkTargets, verdicts: CitingVerdicts) -> None:
        self._scored = scored
        self._targets = targets
        self._verdicts = verdicts

    def resolve(self, note: NoteLines) -> LinkResolution:
        resolution, authors = LinkResolution([], []), RepeatedAuthors()
        for line in EntryLines(note).candidates():
            self._resolve(ScoredEntry(line, authors.restored(line.entry)), resolution)
        return resolution

    def _resolve(self, entry: ScoredEntry, resolution: LinkResolution) -> None:
        line, match = entry.line, self._scored.best_for(entry.text)
        if match is None:
            self._resolve_unmatched(line, resolution)
        elif not self._is_settled(line, match):
            self._resolve_matched(line, match, resolution)

    def _resolve_unmatched(self, line: EntryLine, resolution: LinkResolution) -> None:
        if line.is_linked and not self._verdicts.confirms(line.entry, line.linked_basename):
            resolution.stale.append(ConfirmableLine(line.index, line.entry, line.linked_basename, 0.0))

    def _resolve_matched(self, line: EntryLine, match: ScoredMatch, resolution: LinkResolution) -> None:
        verdict = self._verdicts.on(line.entry, match.work.basename)
        offered = ConfirmableLine(line.index, line.entry, match.work.basename, match.score)
        if verdict is not None:
            resolution.settled.append(offered)
        if self._links(match, verdict) and not line.is_linked:
            resolution.links.append(line.linked_to(match.work))
        elif verdict is None:
            resolution.to_confirm.append(offered)

    @staticmethod
    def _links(match: ScoredMatch, verdict: str | None) -> bool:
        return verdict == CONFIRM or (match.is_automatic and verdict != REJECT)

    def _is_settled(self, line: EntryLine, match: ScoredMatch) -> bool:
        return line.is_linked_to(match.work) or not self._targets.admits(match.work)
