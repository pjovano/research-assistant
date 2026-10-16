from __future__ import annotations

from collections import Counter
from itertools import combinations

from .catalogue import AuthorCatalogue
from .glossing import PERIODS_FOLDER
from .notes import Bibliographies, CorpusNote
from .tree import BibliographyTree

MIN_SHARED_WORKS = 2


class RoutingFindings:
    def __init__(self, bibliographies: Bibliographies, notes: list[CorpusNote]) -> None:
        self._children = {entry.name: entry.children for entry in bibliographies.entries()}
        self._tree = BibliographyTree(bibliographies.entries())
        self._scholars = self._scholars_among(bibliographies)
        self._catalogue = AuthorCatalogue(bibliographies)
        self._notes = notes

    def routing_placements(self) -> list[dict]:
        return [{"work": note.basename, "on": name, "maps": self._children[name]}
                for note in self._notes for name in self._routing_placements(note)]

    def co_placed(self) -> list[dict]:
        counted = Counter(pair for note in self._notes for pair in self._pairs_of(note))
        return [{"bibliographies": list(pair), "works": self._works_on_both(pair)}
                for pair, count in sorted(counted.items()) if count >= MIN_SHARED_WORKS]

    def catalogue_gaps(self) -> list[dict]:
        return [{"work": note.basename, "missing": missing}
                for note in self._notes if (missing := self._catalogue.missing_from(note))]

    def stray_placements(self) -> list[dict]:
        return [{"work": note.basename, "on": strays}
                for note in self._notes if (strays := self._catalogue.strays_of(note))]
    def _is_judged(self, note: CorpusNote, name: str) -> bool:
        return self._catalogue.admits(note, name) and not self._catalogue.holds(note, name)

    def _scholars_among(self, bibliographies: Bibliographies) -> set[str]:
        periods = {entry.name for entry in bibliographies.entries() if entry.folder == PERIODS_FOLDER}
        return {entry.name for entry in bibliographies.entries()
                if entry.author is not None and not periods.intersection(self._tree.parents_of(entry.name))}

    def _routes(self, name: str) -> bool:
        return any(child not in self._scholars for child in self._children.get(name, []))

    def _routing_placements(self, note: CorpusNote) -> list[str]:
        return [name for name in note.bibliographies
                if self._routes(name) and self._is_judged(note, name)]

    def _pairs_of(self, note: CorpusNote) -> list[tuple[str, str]]:
        placed = sorted(name for name in note.bibliographies if self._is_judged(note, name))
        return [pair for pair in combinations(placed, 2) if self._unrelated(*pair)]

    def _unrelated(self, left: str, right: str) -> bool:
        related = left in self._tree.ancestors_of(right) or right in self._tree.ancestors_of(left)
        shared_child = set(self._children.get(left, [])) & set(self._children.get(right, []))
        return not (related or shared_child)

    def _works_on_both(self, pair: tuple[str, str]) -> list[str]:
        return sorted(note.basename for note in self._notes if set(pair) <= set(note.bibliographies))
