from __future__ import annotations

from pathlib import Path

import pymupdf
from vault import ARTICLE_PAGE_THRESHOLD

from .constants import ARTICLE_ITEM_TYPE, BOOK_ITEM_TYPE
from .render import FIRST_PAGE, PageRender


class PdfAnalysis:
    def __init__(self, pdf_path: Path) -> None:
        self._path = pdf_path

    def report(self) -> dict:
        with pymupdf.open(self._path) as doc:
            return self._base_report(doc)

    def report_with_preview(self) -> dict:
        report = self.report()
        if report["page_count"]:
            report["first_page_render"] = str(PageRender(self._path).save(FIRST_PAGE))
        return report

    def require_no_cover(self) -> None:
        if not self._first_page_is_image_only():
            return
        raise SystemExit(
            f"{self._path.name} already opens on an image-only page, a cover. "
            "Pass --force to prepend another."
        )

    def _first_page_is_image_only(self) -> bool:
        with pymupdf.open(self._path) as doc:
            if not doc.page_count:
                return False
            first = doc[0]
            return bool(first.get_images()) and not first.get_text().strip()

    def require_book(self) -> None:
        report = self.report()
        if report["item_type"] == BOOK_ITEM_TYPE:
            return
        raise SystemExit(
            f"{self._path.name} looks like a {report['item_type']} "
            f"({report['page_count']} pages). Articles start on their own first page "
            "and get no cover. Pass --force to override."
        )

    def _base_report(self, doc: pymupdf.Document) -> dict:
        item_type = self._classify(doc.page_count)
        return {
            "file": self._path.name,
            "page_count": doc.page_count,
            "annotation_count": self._count_annotations(doc),
            "item_type": item_type,
            "first_page_image_count": self._first_page_image_count(doc),
            "cover_applies": item_type == BOOK_ITEM_TYPE,
        }

    def _classify(self, page_count: int) -> str:
        return ARTICLE_ITEM_TYPE if page_count < ARTICLE_PAGE_THRESHOLD else BOOK_ITEM_TYPE

    def _count_annotations(self, doc: pymupdf.Document) -> int:
        return sum(sum(1 for _ in (page.annots() or [])) for page in doc)

    def _first_page_image_count(self, doc: pymupdf.Document) -> int:
        return len(doc[0].get_images()) if doc.page_count else 0
