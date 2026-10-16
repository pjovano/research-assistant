from __future__ import annotations

import unittest
from pathlib import Path

import tiktoken

from _support import LiveTree

LiveTree.activate()

import rag

BASENAME = "Hegel - 1969 - Wissenschaft der Logik"
LINK_LINE = f"[{BASENAME}.pdf](zotero://open-pdf/library/items/ABC)"
NOTE_META = {
    "title": "Wissenschaft der Logik",
    "author": ["Hegel", "Miller"],
    "year": 1969,
    "citekey": "hegel1812",
    "field": ["[[Being]]", "[[Logic]]"],
}
SOLE_AUTHOR_META = {"title": "Wissenschaft der Logik", "author": ["Hegel"], "year": 1969, "citekey": "hegel1812"}
NESTED = "# Part Two\n\n## Chapter Nine\n\n### 9.2 Becoming\n\nBeing passes into nothing.\n"
ENCODING = tiktoken.get_encoding("cl100k_base")


def tokens_in(text: str) -> int:
    return len(ENCODING.encode(text))


class Chunks:
    def __init__(self, chunked: rag.ChunkedDocument) -> None:
        self._chunked = chunked

    @property
    def parents(self) -> list[rag.Parent]:
        return list(self._chunked.parents)

    @property
    def children(self) -> list[rag.Child]:
        return list(self._chunked.children)

    def child_texts(self) -> list[str]:
        return [child.text for child in self.children]

    def heading_paths(self) -> list[str]:
        return list(dict.fromkeys(child.metadata["heading_path"] for child in self.children))

    def child_containing(self, fragment: str) -> rag.Child:
        return next(child for child in self.children if fragment in child.text)

    def parent_containing(self, fragment: str) -> rag.Parent:
        return next(parent for parent in self.parents if fragment in parent.text)


class ChunkingTestCase(unittest.TestCase):
    def document(self, body: str, meta: dict | None = None) -> rag.IndexedDocument:
        return rag.IndexedDocument(BASENAME, Path(f"{BASENAME}.md"), NOTE_META if meta is None else meta, body)

    def chunk(self, body: str, meta: dict | None = None) -> Chunks:
        return Chunks(rag.ParentChildChunker().chunked(self.document(body, meta)))
