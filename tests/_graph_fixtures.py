from __future__ import annotations

from _support import LiveTree

LiveTree.activate()

import vault
from citation_graph import CorpusFields, GraphStore, GraphSync, LibraryGraph
from references import HeldWorks, ParsedReference
from _references_fixtures import LINK_LINE, VaultTestCase

NOTHING_PARSED = ParsedReference((), None, None, None, None, None)
STORE_NAME = "graph.sqlite"


class FakeParser:
    def __init__(self, parsed: dict[str, ParsedReference] | None = None) -> None:
        self._parsed = parsed or {}

    def parse(self, entry_text: str) -> ParsedReference:
        return self._parsed.get(entry_text, NOTHING_PARSED)


class FakeVectors:
    def __init__(self, vectors: dict[str, list[list[float]]] | None = None) -> None:
        self._vectors = vectors or {}

    def vectors_of(self, basename: str) -> list[list[float]]:
        return list(self._vectors.get(basename, []))


class FixedCentroids:
    def __init__(self, centroids: dict[str, list[float]] | None = None) -> None:
        self._centroids = centroids or {}

    def centroid(self, basename: str) -> list[float] | None:
        return self._centroids.get(basename)


def entry_body(entries: list[str], folio: str = "300", file_page: int = 10) -> str:
    listed = "\n\n".join(entries)
    return f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n%% p. {folio} (file p. {file_page}) %%\n\n{listed}\n"


class GraphTestCase(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = GraphStore(self.vault.named(STORE_NAME))
        self.addCleanup(self.store.close)

    def write_work(self, basename: str, body: str = LINK_LINE, surname: str | None = None, year: str = "2000",
                   title: str | None = None, field: tuple[str, ...] = ()) -> None:
        author = surname or basename.split(" - ")[0]
        shown = title or basename.split(" - ")[-1]
        topics = "".join(f'\n- "[[{name}]]"' for name in field) or " []"
        frontmatter = f"title: {shown}\nauthor:\n- {author}\nyear: {year}\nfield:{topics}\n"
        self.write_pdf(basename)
        self.write_note(basename, frontmatter, body)

    def sync(self, parser: FakeParser | None = None, centroids: FixedCentroids | None = None,
             basenames: list[str] | None = None) -> dict:
        sync = GraphSync(self.store, HeldWorks.from_library(), parser or FakeParser(), centroids or FixedCentroids())
        return sync.run(basenames)

    def graph(self) -> LibraryGraph:
        return LibraryGraph(self.store, HeldWorks.from_corpus(), CorpusFields())

    def touch(self, basename: str, body: str) -> None:
        path = vault.corpus_path(basename)
        frontmatter, _old = vault.read_frontmatter(path)
        vault.write_frontmatter(path, frontmatter, body)
