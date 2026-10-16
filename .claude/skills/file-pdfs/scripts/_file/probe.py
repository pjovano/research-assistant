from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

import vault

JOURNAL_ARTICLE_PAGE_THRESHOLD = vault.ARTICLE_PAGE_THRESHOLD

_AUTHOR_CONJUNCTIONS = re.compile(r" and | & ")
_AUTHOR_DELIMITERS = re.compile(rf",|{_AUTHOR_CONJUNCTIONS.pattern}")

_LETTER = re.compile(r"[^\W\d_]")


class AuthorNames:
    def is_name_like(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped or not _LETTER.search(stripped):
            return False
        return not stripped.replace(".", "").strip().isdigit()

    def split(self, raw: str) -> list[dict]:
        text = (raw or "").strip().rstrip(";").strip()
        if not text:
            return []
        if ";" in text:
            return self._semicolon_separated(text)
        return self._single_inverted(text) or self._delimiter_separated(text)

    def _semicolon_separated(self, text: str) -> list[dict]:
        segments = (segment.strip() for segment in text.split(";"))
        return [self._inverted_or_spaced(segment) for segment in segments if segment]

    def _single_inverted(self, text: str) -> list[dict]:
        if text.count(",") != 1 or _AUTHOR_CONJUNCTIONS.search(text):
            return []
        last, first = (part.strip() for part in text.split(",", 1))
        if not last or not self.is_name_like(first):
            return []
        return [{"firstName": first, "lastName": last}]

    def _delimiter_separated(self, text: str) -> list[dict]:
        parts = (part.strip() for part in _AUTHOR_DELIMITERS.split(text))
        return [self._from_space_separated(part) for part in parts if part]

    def _inverted_or_spaced(self, segment: str) -> dict:
        if "," not in segment:
            return self._from_space_separated(segment)
        last, first = (part.strip() for part in segment.split(",", 1))
        return {"firstName": first, "lastName": last}

    def _from_space_separated(self, part: str) -> dict:
        bits = part.split()
        if len(bits) == 1:
            return {"firstName": "", "lastName": bits[0]}
        return {"firstName": " ".join(bits[:-1]), "lastName": bits[-1]}


class AuthorByline:
    _PAGES_SCANNED = 6
    _LINES_SCANNED = 150
    _MAX_LINE_LENGTH = 120

    def __init__(self) -> None:
        self._names = AuthorNames()

    def find(self, doc: "pymupdf.Document", surnames: list[str]) -> list[dict]:
        if not surnames:
            return []
        wanted = {surname.lower() for surname in surnames}
        for line in self._candidate_lines(doc):
            named_in_full = self._authors_named_in_full(line, wanted)
            if named_in_full:
                return named_in_full
        return []

    def _candidate_lines(self, doc: "pymupdf.Document") -> list[str]:
        pages = range(min(self._PAGES_SCANNED, doc.page_count))
        text = "".join(doc[index].get_text() for index in pages)
        lines = (line.strip() for line in text.splitlines()[:self._LINES_SCANNED])
        return [line for line in lines if line and len(line) <= self._MAX_LINE_LENGTH]

    def _authors_named_in_full(self, line: str, wanted: set[str]) -> list[dict]:
        if not self._mentions_all(line, wanted):
            return []
        candidate = self._names.split(line)
        return candidate if self._all_have_first_names(candidate, wanted) else []

    def _mentions_all(self, line: str, wanted: set[str]) -> bool:
        lowered = line.lower()
        return all(re.search(rf"\b{re.escape(surname)}\b", lowered) for surname in wanted)

    def _all_have_first_names(self, candidate: list[dict], wanted: set[str]) -> bool:
        if not wanted <= {author["lastName"].lower() for author in candidate}:
            return False
        return all(self._names.is_name_like(author["firstName"]) for author in candidate
                   if author["lastName"].lower() in wanted)


class PdfProbe:
    def __init__(self) -> None:
        self._names = AuthorNames()

    def of(self, pdf_path: Path) -> dict:
        doc = pymupdf.open(pdf_path)
        try:
            return self._described(doc, pdf_path)
        finally:
            doc.close()

    def _described(self, doc: "pymupdf.Document", pdf_path: Path) -> dict:
        parsed = vault.parse_library_filename(pdf_path.name)
        authors, complete = self._creators(doc, parsed)
        return {
            "file": pdf_path.name,
            "title": self._title(doc, parsed) or pdf_path.stem,
            "authors": authors,
            "authors_complete": complete,
            "year": self._year(parsed),
            "pages": doc.page_count,
            "type": self._item_type(doc.page_count),
        }

    def _title(self, doc: "pymupdf.Document", parsed: dict | None) -> str:
        return self._metadata(doc).get("title") or (parsed["title"] if parsed else "")

    def _year(self, parsed: dict | None) -> str:
        return parsed["year"] if parsed and parsed["year"] else ""

    def _item_type(self, page_count: int) -> str:
        return "journalArticle" if page_count < JOURNAL_ARTICLE_PAGE_THRESHOLD else "book"

    def _creators(self, doc: "pymupdf.Document", parsed: dict | None) -> tuple[list[dict], bool]:
        authors = self._declared_authors(doc, parsed)
        if self._need_no_byline(authors):
            return authors, bool(authors)
        return self._enriched_from_byline(doc, authors)

    def _need_no_byline(self, authors: list[dict]) -> bool:
        return not authors or all(author["firstName"] for author in authors)

    def _enriched_from_byline(self, doc: "pymupdf.Document",
                              authors: list[dict]) -> tuple[list[dict], bool]:
        surnames = [author["lastName"] for author in authors]
        richer = AuthorByline().find(doc, surnames)
        return (richer, True) if richer else (authors, False)

    def _declared_authors(self, doc: "pymupdf.Document", parsed: dict | None) -> list[dict]:
        filename_surname = self._filename_surname(parsed)
        from_metadata = self._trusted_metadata_authors(doc, filename_surname)
        if from_metadata:
            return from_metadata
        if filename_surname:
            return [self._surname_only(surname) for surname in vault.creator_surnames(parsed["creator"])]
        return []

    def _trusted_metadata_authors(self, doc: "pymupdf.Document",
                                  filename_surname: str | None) -> list[dict]:
        authors = self._names.split(self._metadata(doc).get("author") or "")
        if not authors or not filename_surname:
            return authors
        surnames = {author["lastName"].lower() for author in authors}
        return authors if filename_surname.lower() in surnames else []

    def _filename_surname(self, parsed: dict | None) -> str | None:
        surnames = vault.creator_surnames(parsed["creator"]) if parsed else []
        return surnames[0] if surnames else None

    def _surname_only(self, surname: str) -> dict:
        return {"firstName": "", "lastName": surname}

    def _metadata(self, doc: "pymupdf.Document") -> dict:
        return doc.metadata or {}


class OpeningPagesDump:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def print_pages(self, page_limit: int) -> None:
        doc = pymupdf.open(self._pdf_path)
        try:
            self._print_summary(doc)
            self._print_text(doc, page_limit)
        finally:
            doc.close()

    def _print_summary(self, doc: "pymupdf.Document") -> None:
        summary = {"pdf_metadata": doc.metadata or {}, "page_count": doc.page_count}
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    def _print_text(self, doc: "pymupdf.Document", page_limit: int) -> None:
        for index in range(min(page_limit, doc.page_count)):
            print(f"\n===== file page {index + 1} =====")
            print(doc[index].get_text())
