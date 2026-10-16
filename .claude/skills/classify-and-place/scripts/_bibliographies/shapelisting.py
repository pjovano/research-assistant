from __future__ import annotations

import vault
from citation_graph import ClusterReport, GraphStore, LibraryGraph

from .diagnostics import AuthorChecks
from .foldfinding import FoldCandidates
from .glossing import DESCRIPTION_FIELD
from .listingparts import DESCRIPTIONS_KEY, ROUTING_KEY, DescribedWorks
from .notes import Bibliographies, Corpus, NoteNotFound
from .routing import RoutingFindings
from .treeshape import TreeShape

NEIGHBOURS_SHOWN = 5
MISSING_FINDING = "missing"
PLACED_ON_FIELD = "placed_on"


class ShapeListing:
    def __init__(self, bibliographies: Bibliographies, corpus: Corpus, store: GraphStore) -> None:
        self._bibliographies = bibliographies
        self._corpus = corpus
        self._store = store

    def of(self, nominations: list[dict]) -> dict:
        graph = LibraryGraph.loaded(self._store)
        clusters = ClusterReport(graph).report()
        clusters["findings"].pop(MISSING_FINDING, None)
        authors = AuthorChecks(self._bibliographies, self._corpus.notes()).uncovered_authors()
        folds = FoldCandidates(self._bibliographies, self._corpus.notes()).found()
        shape = TreeShape(self._bibliographies, self._corpus.notes())
        listing = {"tree": [entry.summary() for entry in self._bibliographies.entries()], "clusters": clusters,
                   "authors": authors, "nominations": self._open(nominations), "author_maps": shape.author_maps(),
                   "unlinked_subtopics": shape.unlinked_subtopics(), **self._routing(graph), "fold_candidates": folds}
        return {**listing, DESCRIPTIONS_KEY: self._descriptions(DescribedWorks.named_in(listing))}

    def _routing(self, graph: LibraryGraph) -> dict:
        findings = RoutingFindings(self._bibliographies, self._corpus.notes())
        placements = [{**finding, "neighbours": self._neighbours(graph, finding["work"])}
                      for finding in findings.routing_placements()]
        return {ROUTING_KEY: placements, "co_placed": findings.co_placed(), "catalogue_gaps": findings.catalogue_gaps(),
                "stray_placements": findings.stray_placements()}

    @staticmethod
    def _neighbours(graph: LibraryGraph, work: str) -> list[dict]:
        if not graph.holds(work):
            return []
        nearest = graph.pairs_of(work)[:NEIGHBOURS_SHOWN]
        return [{"work": pair.right, "bibliographies": graph.bibliographies_of(pair.right)} for pair in nearest]

    def _open(self, nominations: list[dict]) -> list[dict]:
        still_open = [{**nomination, "works": self._unmoved(nomination)} for nomination in nominations]
        named = [nomination for nomination in still_open if nomination["works"]]
        return sorted(named, key=lambda nomination: (nomination.get("parent") or "", nomination.get("name") or ""))

    def _unmoved(self, nomination: dict) -> list[str]:
        placed_on = [vault.nfc(name) for name in nomination.get(PLACED_ON_FIELD) or []]
        return [work for work in nomination.get("works", []) if self._sits_on(work) == placed_on]

    def _sits_on(self, basename: str) -> list[str] | None:
        try:
            return self._corpus.note(basename).bibliographies
        except NoteNotFound:
            return None

    def _descriptions(self, basenames: set[str]) -> dict[str, dict]:
        return {basename: self._described(basename) for basename in sorted(basenames)}

    def _described(self, basename: str) -> dict:
        try:
            note = self._corpus.note(basename)
        except NoteNotFound:
            return {}
        return {"title": note.meta.get("title"), "author": note.authors, "source_role": note.source_role,
                DESCRIPTION_FIELD: note.meta.get(DESCRIPTION_FIELD), "bibliographies": note.bibliographies}
