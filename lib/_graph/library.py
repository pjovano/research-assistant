from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import vault
from references import HeldWorks

from _graph.signals import NO_SIGNAL, Centroids, PairSignals, ReferenceSets, Signals
from _graph.store import HELD_KEY_PREFIX, GraphStore, UnheldRow


@dataclass(frozen=True)
class ScoredPair:
    left: str
    right: str
    signals: Signals

    @property
    def score(self) -> float:
        return self.signals.combined()


class CorpusFields:
    def __init__(self) -> None:
        self._fields = {vault.basename_of(path): self._topics(path) for path in vault.list_corpus_files()}

    @staticmethod
    def _topics(path) -> list[str]:
        return [vault.nfc(topic) for topic in vault.field_topics(vault.read_frontmatter_only(path))]

    def of(self, basename: str) -> list[str]:
        return list(self._fields.get(basename, []))

    def basenames(self) -> list[str]:
        return sorted(self._fields)


class ReferenceLabels:
    def __init__(self, unheld: list[UnheldRow]) -> None:
        self._unheld = {row.key: row.text for row in unheld}

    def of(self, key: str) -> str:
        if key.startswith(HELD_KEY_PREFIX):
            return key[len(HELD_KEY_PREFIX):]
        return self._unheld.get(key, key)


class LibraryGraph:
    def __init__(self, store: GraphStore, held: HeldWorks, fields: CorpusFields) -> None:
        self._references = ReferenceSets(store.citations())
        self._labels = ReferenceLabels(store.unheld_rows())
        self._fields = fields
        surnames = {work.basename: work.surname_tokens for work in held.works}
        self._pairs = PairSignals(self._references, Centroids(store.centroids()), surnames)
        self._works = fields.basenames()

    @classmethod
    def loaded(cls, store: GraphStore) -> LibraryGraph:
        return cls(store, HeldWorks.from_corpus(), CorpusFields())

    @property
    def works(self) -> list[str]:
        return list(self._works)

    def holds(self, basename: str) -> bool:
        return basename in self._fields.basenames()

    def signals(self, left: str, right: str) -> Signals:
        return self._pairs.between(left, right)

    def pairs_of(self, basename: str) -> list[ScoredPair]:
        pairs = (ScoredPair(basename, other, self.signals(basename, other)) for other in self._works
                 if other != basename)
        return sorted((pair for pair in pairs if pair.score > NO_SIGNAL), key=lambda pair: -pair.score)

    def all_pairs(self) -> Iterator[ScoredPair]:
        for index, left in enumerate(self._works):
            for right in self._works[index + 1:]:
                pair = ScoredPair(left, right, self.signals(left, right))
                if pair.score > NO_SIGNAL:
                    yield pair

    def shared_references(self, left: str, right: str) -> list[str]:
        return sorted(self._labels.of(key) for key in self._references.shared_references(left, right))

    def references_of(self, basename: str) -> set[str]:
        return self._references.references_of(basename)

    def label_of(self, key: str) -> str:
        return self._labels.of(key)

    def bibliographies_of(self, basename: str) -> list[str]:
        return self._fields.of(basename)
