from __future__ import annotations

import atexit
import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
import rag
import vault
from rag import ERROR_KEY
from citation_graph import DEFAULT_NEIGHBOURS, CitationContexts, GraphStore, LibraryGraph, Neighbourhood
from references import CitationGraph

from mcp.server.mcpserver import MCPServer

SERVER_NAME = "vault-rag"
SUMMARY_FIELDS = ("title", "author", "year", "source_type", "source_role", "field")


TOOL_DESCRIPTIONS = {
    "search_hybrid": "Hybrid full-text and embedding search over the derived corpus and the transcripts, reranked; one "
                     "query or a list of them, fused into one ranking. Each result is a parent passage with the "
                     "offsets of the child passage that matched.",
    "index_status": "Whether the search stores agree with each other and with the corpus.",
    "get_frontmatter": "The frontmatter of one corpus file or transcript, by basename.",
    "list_works": "Every corpus file and transcript by basename, title, author, year, source_type, source_role and "
                  "field, optionally only those on one bibliography.",
    "cites": "The held works one corpus file's bibliography entries and footnotes link to, each with the folio of "
             "the linking line.",
    "cited_by": "The corpus files whose bibliography entries or footnotes link to one held work, each with the folio "
                "of the linking line.",
    "neighbours": "The works nearest one held work in the citation graph: by direct citation, by the references "
                  "they share, by the works that cite them together, and by embedding; each with its signals, the "
                  "references shared, and the bibliographies it sits on, then a tally of those bibliographies.",
    "contexts": "The passages where one held work speaks of another: the sentences calling a footnote that cites it, "
                "its author-date citations, and mentions of its title beside its author's name, each with its folio.",
    "outline": "One held work's heading tree, read from its corpus file: each heading with its path, its level, the "
               "first and last folio it spans, and its first file page.",
}


class CorpusNotes:
    def frontmatter(self, basename: str) -> dict:
        path = vault.held_note_path(basename)
        if not path.exists():
            raise LookupError(f"No corpus file or transcript for {basename}")
        metadata, _body = vault.read_frontmatter(path)
        return {"basename": basename, **metadata}

    def listed(self, field: str | None) -> list[dict]:
        summaries = (self._summary(path) for path in vault.list_held_notes())
        return [summary for summary in summaries if self._on_field(summary, field)]

    @staticmethod
    def _on_field(summary: dict, field: str | None) -> bool:
        return not field or field.strip() in vault.field_topics(summary)

    @staticmethod
    def _summary(path: Path) -> dict:
        metadata = vault.read_frontmatter_only(path)
        return {"basename": vault.basename_of(path), **{name: metadata.get(name) for name in SUMMARY_FIELDS}}


class VaultRagServer:
    def __init__(self) -> None:
        self._server = MCPServer(SERVER_NAME)
        self._notes = CorpusNotes()
        self._graph = CitationGraph()
        self._outline = rag.CorpusOutline()
        self._index = rag.SearchIndex.on_this_machine()
        self._reranker = rag.LlamaReranker(lifetime=rag.ProcessLifetime())
        self._search = rag.HybridSearch(self._index, self._reranker)
        self._idle = rag.IdleRelease([self._reranker.stop, self._index.embeddings.release])
        self._register()

    def run(self) -> None:
        atexit.register(self._reranker.stop)
        self._idle.start_watching()
        self._server.run()

    def _register(self) -> None:
        for name, description, handler in self._tools():
            self._server.tool(name=name, description=description)(self._idle.served(handler))

    def _tools(self) -> list[tuple[str, str, object]]:
        return [(name, description, getattr(self, name)) for name, description in TOOL_DESCRIPTIONS.items()]

    def search_hybrid(self, query: str | list[str], k: int = rag.DEFAULT_RESULTS) -> list[dict]:
        return self._search.results(query, k)

    def get_frontmatter(self, basename: str) -> dict:
        try:
            return self._notes.frontmatter(basename)
        except LookupError as error:
            return {ERROR_KEY: str(error)}

    def list_works(self, field: str | None = None) -> list[dict]:
        return self._notes.listed(field)

    def index_status(self) -> dict:
        return rag.IndexStatus(self._index, self._reranker).report()

    def cites(self, basename: str) -> dict:
        try:
            return self._graph.cites(basename)
        except LookupError as error:
            return {ERROR_KEY: str(error)}

    def cited_by(self, basename: str) -> dict:
        try:
            return self._graph.cited_by(basename)
        except LookupError as error:
            return {ERROR_KEY: str(error)}

    def neighbours(self, basename: str, k: int = DEFAULT_NEIGHBOURS) -> dict:
        try:
            return Neighbourhood(LibraryGraph.loaded(GraphStore()), k).of(basename)
        except LookupError as error:
            return {ERROR_KEY: str(error)}

    def contexts(self, citing: str, cited: str) -> dict:
        try:
            return {"citing": citing, "cited": cited, "passages": CitationContexts.between(citing, cited).passages()}
        except LookupError as error:
            return {ERROR_KEY: str(error)}

    def outline(self, basename: str) -> dict:
        return self._outline.of(basename)


def main() -> None:
    VaultRagServer().run()


if __name__ == "__main__":
    main()
