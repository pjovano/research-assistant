from __future__ import annotations

from collections import defaultdict

from .notes import Bibliography


class BibliographyTree:
    def __init__(self, bibliographies: list[Bibliography]) -> None:
        self._names = {entry.name for entry in bibliographies}
        self._parents_of = self._read(bibliographies)

    def names(self) -> set[str]:
        return set(self._names)

    def parents_of(self, name: str) -> list[str]:
        return sorted(self._parents_of.get(name, []))

    def children_of(self, name: str) -> list[str]:
        return sorted(child for child, parents in self._parents_of.items() if name in parents)

    def ancestors_of(self, name: str) -> list[str]:
        ancestors: list[str] = []
        parents = self.parents_of(name)
        while parents:
            unseen = [parent for parent in parents if parent not in ancestors]
            ancestors.extend(unseen)
            parents = [above for parent in unseen for above in self.parents_of(parent)]
        return ancestors

    @staticmethod
    def _read(bibliographies: list[Bibliography]) -> dict[str, set[str]]:
        parents_of: dict[str, set[str]] = defaultdict(set)
        for entry in bibliographies:
            for child in entry.children:
                parents_of[child].add(entry.name)
        return parents_of
