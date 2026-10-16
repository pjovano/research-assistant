from __future__ import annotations

from pathlib import Path

import pagetext

from .verdict import cited_place


class TermLocation:
    def __init__(self, pdf: Path, term: str, limit: int) -> None:
        self._pdf = pdf
        self._term = term
        self._pages = self._located(limit)

    def payload(self) -> dict:
        return {"pdf": str(self._pdf), "term": self._term, "pages": self._pages}

    def rendered(self) -> str:
        if not self._pages:
            return self._absent()
        header = f"{len(self._pages)} page(s) in {self._pdf.name} mention '{self._term}':\n"
        return "\n".join([header] + [self._page_line(page) for page in self._pages])

    def _located(self, limit: int) -> list[dict]:
        needle = pagetext.normalize(self._term)
        pages = []
        for page in pagetext.normalized_pages(self._pdf):
            hit = self._page_hit(page, needle)
            if hit is not None:
                pages.append(hit)
            if len(pages) >= limit:
                break
        return pages

    @staticmethod
    def _page_hit(page: pagetext.NormalizedPage, needle: str) -> dict | None:
        count = page.text.count(needle)
        if not count:
            return None
        start = page.text.find(needle)
        return {"pdf_page": page.number, "printed_page": page.label, "occurrences": count,
                "context": pagetext.locate_context(page.text, start, len(needle))}

    @staticmethod
    def _page_line(page: dict) -> str:
        return (f"  p. {cited_place(page)}  [file page {page['pdf_page']}]  x{page['occurrences']}\n"
                f"      {page['context']}\n")

    def _absent(self) -> str:
        return (f"'{self._term}' not found in the text layer of {self._pdf.name}.\n"
                "If this PDF is a scan, its text layer may be unusable: run "
                "`quality` on it and read the pages visually instead.")


class TextLayerQuality:
    def __init__(self, pdf: Path, sample_pages: int | None) -> None:
        self._pdf = pdf
        self._pages = pagetext.page_texts(pdf, limit=sample_pages)
        self._quality = pagetext.assess("\n".join(text for _, text in self._pages), pages=len(self._pages))

    def is_good(self) -> bool:
        return self._quality.is_good

    def payload(self) -> dict:
        return {"pdf": str(self._pdf), "pages_sampled": len(self._pages), **self._quality.as_dict()}

    def rendered(self) -> str:
        lines = [f"{self._pdf.name}: text layer is {self._quality.verdict.upper()}",
                 f"  sampled {len(self._pages)} page(s), {self._quality.chars} chars, {self._quality.tokens} tokens",
                 f"  {self._quality.reason}"]
        if not self.is_good():
            lines.append("\n  Do not quote from this text layer. Read the pages visually instead.")
        return "\n".join(lines)
