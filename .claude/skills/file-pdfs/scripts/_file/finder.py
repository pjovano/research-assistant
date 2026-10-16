from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

import identifiers

SOURCE_METADATA = "pdf metadata"
SOURCE_XMP = "xmp"
SOURCE_FILENAME = "filename"
PAGE_SOURCE_PREFIX = "file p. "
OPENING_PAGES_SEARCHED = 6
CLOSING_PAGES_SEARCHED = 3

_METADATA_KEYS_SEARCHED = ("title", "subject", "keywords", "author")
_DOI_METADATA_KEYS = ("doi", "prism:doi", "dc:identifier", "pdfx:doi")


@dataclass(frozen=True)
class FoundIdentifier:
    kind: str
    value: str
    source: str

    def as_dict(self) -> dict:
        return {"kind": self.kind, "value": self.value, "source": self.source}


class FoundIdentifiers:
    def __init__(self, found: list[FoundIdentifier]) -> None:
        self._found = found

    def as_dicts(self) -> list[dict]:
        return [item.as_dict() for item in self._found]

    def of_kind(self, kind: str) -> list[str]:
        distinct: list[str] = []
        for item in self._found:
            if item.kind == kind and item.value not in distinct:
                distinct.append(item.value)
        return distinct

    def first_of_kind(self, kind: str) -> FoundIdentifier | None:
        return next((item for item in self._found if item.kind == kind), None)

    def chapter_doi_evidence(self) -> list[str]:
        pages_by_doi: dict[str, set[str]] = {}
        for item in self._page_dois():
            pages_by_doi.setdefault(item.value, set()).add(item.source)
        by_prefix: dict[str, list[str]] = {}
        for doi in pages_by_doi:
            by_prefix.setdefault(doi.split("/")[0], []).append(doi)
        siblings = [sorted(dois) for dois in by_prefix.values() if self._on_distinct_pages(dois, pages_by_doi)]
        return [doi for group in siblings for doi in group]

    def _page_dois(self) -> list[FoundIdentifier]:
        return [item for item in self._found
                if item.kind == identifiers.KIND_DOI and item.source.startswith(PAGE_SOURCE_PREFIX)]

    def _on_distinct_pages(self, dois: list[str], pages_by_doi: dict[str, set[str]]) -> bool:
        if len(dois) < 2:
            return False
        return len(set.union(*(pages_by_doi[doi] for doi in dois))) >= len(dois)


class TextSources:
    def __init__(self, doc: "pymupdf.Document", pdf_path: Path) -> None:
        self._doc = doc
        self._pdf_path = pdf_path

    def labelled(self) -> list[tuple[str, str]]:
        return ([(SOURCE_METADATA, self._metadata_text()), (SOURCE_XMP, self._xmp_text())]
                + self._page_texts() + [(SOURCE_FILENAME, self._pdf_path.name)])

    def _metadata_text(self) -> str:
        metadata = self._doc.metadata or {}
        found = [str(metadata.get(key) or "") for key in _METADATA_KEYS_SEARCHED + _DOI_METADATA_KEYS]
        return "\n".join(found)

    def _xmp_text(self) -> str:
        xref = self._doc.xref_xml_metadata()
        if xref <= 0:
            return ""
        return self._doc.xref_stream(xref).decode("utf-8", errors="replace")

    def _page_texts(self) -> list[tuple[str, str]]:
        return [(f"{PAGE_SOURCE_PREFIX}{index + 1}", self._doc[index].get_text()) for index in self._page_indices()]

    def _page_indices(self) -> list[int]:
        count = self._doc.page_count
        opening = list(range(min(OPENING_PAGES_SEARCHED, count)))
        closing = list(range(max(count - CLOSING_PAGES_SEARCHED, 0), count))
        return opening + [index for index in closing if index not in opening]


class IdentifierFinder:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def found(self) -> FoundIdentifiers:
        doc = pymupdf.open(self._pdf_path)
        try:
            sources = TextSources(doc, self._pdf_path).labelled()
        finally:
            doc.close()
        return FoundIdentifiers([item for source, text in sources for item in self._in(text, source)])

    def _in(self, text: str, source: str) -> list[FoundIdentifier]:
        dois = [FoundIdentifier(identifiers.KIND_DOI, doi, source) for doi in identifiers.find_dois(text)]
        isbns = [FoundIdentifier(identifiers.KIND_ISBN, isbn, source) for isbn in identifiers.find_isbns(text)]
        arxiv = [FoundIdentifier(identifiers.KIND_ARXIV, arxiv_id, source)
                 for arxiv_id in identifiers.find_arxiv_ids(text)]
        return dois + isbns + arxiv
