from __future__ import annotations

import re
from itertools import permutations

from .catalogue import AuthorCatalogue
from .notes import Bibliographies, CorpusNote
from .tree import BibliographyTree

_WORD_RE = re.compile(r"[^\W\d_]+")
_POSSESSIVE_RE = re.compile(r"['’]s\b")
_FUNCTION_WORDS = frozenset({"a", "an", "and", "in", "of", "on", "the", "to"})
MIN_WORKS_FOR_A_BIBLIOGRAPHY = 5
BY_NAME = "name"
BY_HEAD = "head"
BY_SIZE = "size"


class SubjectName:
    def __init__(self, name: str) -> None:
        plain = _POSSESSIVE_RE.sub("", name.casefold())
        self.words = [word for word in _WORD_RE.findall(plain) if word not in _FUNCTION_WORDS]

    @property
    def head(self) -> str | None:
        return self.words[-1] if self.words else None

    def holds_all_of(self, other: SubjectName) -> bool:
        return set(other.words) < set(self.words)

    def names_head_of(self, other: SubjectName) -> bool:
        return other.head is not None and other.head in self.words


class GatheredWorks:
    def __init__(self, bibliographies: Bibliographies, notes: list[CorpusNote]) -> None:
        self._tree = BibliographyTree(bibliographies.entries())
        catalogue = AuthorCatalogue(bibliographies)
        self._admitted = [(note.basename, name) for note in notes for name in note.bibliographies
                          if catalogue.admits(note, name)]

    def on_and_beneath(self, name: str) -> set[str]:
        subtree = self._subtree(name)
        return {basename for basename, placed_on in self._admitted if placed_on in subtree}

    def _subtree(self, name: str) -> set[str]:
        reached, frontier = {name}, [name]
        while frontier:
            frontier = [child for parent in frontier for child in self._tree.children_of(parent)
                        if child not in reached]
            reached.update(frontier)
        return reached


class FoldCandidates:
    def __init__(self, bibliographies: Bibliographies, notes: list[CorpusNote]) -> None:
        self._subjects = {entry.name: SubjectName(entry.name) for entry in bibliographies.entries()
                          if entry.author is None}
        self._tree = BibliographyTree(bibliographies.entries())
        self._gathered = GatheredWorks(bibliographies, notes)
        self._notes = notes

    def found(self) -> list[dict]:
        worded = {(narrower, broader): found_by for narrower, broader in permutations(sorted(self._subjects), 2)
                  if (found_by := self._found_by_wording(narrower, broader))}
        sized = {(narrower, parent): BY_SIZE for narrower in sorted(self._subjects) if self._is_small(narrower)
                 for parent in self._tree.parents_of(narrower)}
        return [self._candidate(narrower, broader, found_by)
                for (narrower, broader), found_by in {**worded, **sized}.items()]

    def _found_by_wording(self, narrower: str, broader: str) -> str | None:
        narrow, broad = self._subjects[narrower], self._subjects[broader]
        if narrow.holds_all_of(broad):
            return BY_NAME
        if broader in self._tree.parents_of(narrower) and narrow.names_head_of(broad):
            return BY_HEAD
        return None

    def _is_small(self, name: str) -> bool:
        return len(self._gathered.on_and_beneath(name)) < MIN_WORKS_FOR_A_BIBLIOGRAPHY

    def _candidate(self, narrower: str, broader: str, found_by: str) -> dict:
        return {"narrower": narrower, "broader": broader, "by": found_by, "works": self._works_on(narrower),
                "shared": sorted(set(self._works_on(narrower)) & set(self._works_on(broader)))}

    def _works_on(self, name: str) -> list[str]:
        return sorted(note.basename for note in self._notes if name in note.bibliographies)
