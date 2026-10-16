from __future__ import annotations

import re
from dataclasses import dataclass

import vault
from notation import blanked_notation
from references import HeldWorks, LibraryWork, MarkedLines, NoteLines, normalize_phrase

from _references.matching import MIN_TITLE_CHARS

KIND_FOOTNOTE = "footnote"
KIND_AUTHOR_DATE = "author-date"
KIND_MENTION = "mention"
CONTEXT_CHARS = 400
MAX_CITATION_GAP_CHARS = 60
_POSSESSIVE = r"(?:['’]?s)?"


@dataclass(frozen=True)
class Passage:
    index: int
    kind: str
    start: int

    def located(self, folio: str | None, file_page: int | None, text: str) -> dict:
        return {"kind": self.kind, "folio": folio, "file_page": file_page, "text": self._window(text)}

    def _window(self, text: str) -> str:
        if len(text) <= 2 * CONTEXT_CHARS:
            return text
        start = max(0, self.start - CONTEXT_CHARS)
        return text[start:start + 2 * CONTEXT_CHARS].strip()


class CitedWorkPatterns:
    def __init__(self, cited: LibraryWork) -> None:
        self._cited = cited
        surnames = "|".join(re.escape(name) for name in sorted(cited.surname_tokens))
        self._surname = re.compile(rf"\b(?:{surnames}){_POSSESSIVE}\b", re.IGNORECASE) if surnames else None
        years = "|".join(re.escape(year) for year in cited.years)
        self._author_date = re.compile(rf"\b(?:{surnames}){_POSSESSIVE}\b.{{0,{MAX_CITATION_GAP_CHARS}}}?"
                                       rf"\b(?:{years})[a-z]?\b", re.IGNORECASE) if surnames and years else None
        self._titles = [title for title in cited.titles if len(title) >= MIN_TITLE_CHARS]

    def author_date_at(self, line: str) -> int | None:
        match = self._author_date.search(line) if self._author_date else None
        return match.start() if match else None

    def mention_at(self, line: str) -> int | None:
        if self._surname is None or not self._surname.search(line):
            return None
        normalized = f" {normalize_phrase(line)} "
        return next((max(0, normalized.find(f" {title} ")) for title in self._titles if f" {title} " in normalized),
                    None)


class CitationContexts:
    def __init__(self, citing: LibraryWork, cited: LibraryWork, body: str) -> None:
        self._citing = citing
        self._cited = cited
        self._note = NoteLines(blanked_notation(body))
        self._lines = self._note.lines
        self._patterns = CitedWorkPatterns(cited)

    @classmethod
    def between(cls, citing_basename: str, cited_basename: str) -> CitationContexts:
        held = HeldWorks.from_corpus()
        citing, cited = held.find(citing_basename), held.find(cited_basename)
        if citing is None or cited is None:
            raise LookupError(f"'{citing_basename}' and '{cited_basename}' must both have corpus files")
        _frontmatter, body = vault.read_frontmatter(vault.corpus_path(citing.basename))
        return cls(citing, cited, body)

    def passages(self) -> list[dict]:
        found = self._footnote_calls() + self._prose_citations()
        by_index = {passage.index: passage for passage in reversed(found)}
        located = MarkedLines(self._lines).located(sorted(by_index))
        return [by_index[index].located(*MarkedLines.page_of(marker), text)
                for index, (marker, text) in zip(sorted(by_index), located)]

    def _footnote_calls(self) -> list[Passage]:
        sites = vault.FootnoteCallSites(self._lines)
        linked = [index for index in self._note.entry_indices() if self._links_cited(index)]
        labels = sites.labels_defined_at(linked)
        return [Passage(index, KIND_FOOTNOTE, self._call_start(index, labels))
                for index in sites.indices_calling(labels)]

    def _links_cited(self, index: int) -> bool:
        target = vault.wikilink_target(self._lines[index])
        return bool(target) and vault.nfc(target) == self._cited.basename

    def _call_start(self, index: int, labels: set[str]) -> int:
        marks = [mark.start() for mark in vault.FOOTNOTE_MARK_RE.finditer(self._lines[index])
                 if mark.group("label") in labels]
        return min(marks) if marks else 0

    def _prose_citations(self) -> list[Passage]:
        entries = set(self._note.entry_indices())
        found = (self._prose_citation(index, line) for index, line in enumerate(self._lines) if index not in entries)
        return [passage for passage in found if passage is not None]

    def _prose_citation(self, index: int, line: str) -> Passage | None:
        author_date = self._patterns.author_date_at(line)
        if author_date is not None:
            return Passage(index, KIND_AUTHOR_DATE, author_date)
        mention = self._patterns.mention_at(line)
        return Passage(index, KIND_MENTION, mention) if mention is not None else None
