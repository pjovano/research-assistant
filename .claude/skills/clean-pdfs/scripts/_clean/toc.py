from __future__ import annotations

from pathlib import Path

import pymupdf
import pagetext
from conversion_cache_keys import CachedConversionsKept
from vault import ReplacementFile

from .analysis import PdfAnalysis
from .inspection import ScanRange, Suspicions
from .outline import Outline

TOC_TEMPORARY_SUFFIX = ".toc.tmp.pdf"


class TocDocument:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def page_count(self) -> int:
        with pymupdf.open(self._path) as doc:
            return doc.page_count

    def outline(self) -> Outline:
        return self._outline_of(self._path)

    @staticmethod
    def _outline_of(path: Path) -> Outline:
        return Outline.from_toc(pagetext.outline_entries(path))

    def probe(self) -> dict:
        outline, pages = self.outline(), self.page_count()
        report = self._shape(outline, pages)
        report["suspicions"] = Suspicions(outline, pages).names()
        report["entries"] = outline.as_dicts()
        return report

    def _shape(self, outline: Outline, pages: int) -> dict:
        return {
            "file": self._path.name,
            "page_count": pages,
            "item_type": PdfAnalysis(self._path).report()["item_type"],
            "entry_count": len(outline.entries()),
            "max_depth": outline.max_depth(),
            "level_histogram": outline.level_histogram(),
        }

    def scan(self, first: int, last: int, dpi: int) -> list[dict]:
        pages = ScanRange(first, last, self.page_count()).pages()
        rendered = pagetext.render_pages(self._path, pages, dpi=dpi)
        return [{"page": page, "render": str(image)} for page, image in zip(pages, rendered)]

    def clear(self) -> None:
        self.write(Outline([]))

    def write(self, outline: Outline) -> None:
        with CachedConversionsKept(self._path), ReplacementFile(self._path, TOC_TEMPORARY_SUFFIX) as replacement:
            self._write_into(replacement.path, outline)
            self._verify_readback(replacement.path, outline)
            replacement.commit()

    def _write_into(self, partial: Path, outline: Outline) -> None:
        with pymupdf.open(self._path) as doc:
            doc.set_toc([self._at_page_top(doc, row) for row in outline.as_toc()])
            doc.save(partial)

    @staticmethod
    def _at_page_top(doc, row: list) -> list:
        level, title, page = row
        if not 1 <= page <= doc.page_count:
            return row
        return [level, title, page, PageTopDestination(doc[page - 1]).link()]

    def _verify_readback(self, partial: Path, expected: Outline) -> None:
        written = self._outline_of(partial)
        if written.as_toc() != expected.as_toc():
            raise SystemExit(
                f"Refusing to keep {partial.name}: the outline read back is not the one "
                f"written ({len(written.entries())} entries against "
                f"{len(expected.entries())} intended).")


class PageTopDestination:
    def __init__(self, page: pymupdf.Page) -> None:
        self._page = page

    def link(self) -> dict:
        return {"kind": pymupdf.LINK_GOTO, "to": self._point_as_set_toc_takes_it()}

    def _point_as_set_toc_takes_it(self) -> pymupdf.Point:
        unrotated = self._visible_top_left_in_user_space() * ~self._page.rotation_matrix
        return pymupdf.Point(unrotated.x, self._page.cropbox.height - unrotated.y)

    def _visible_top_left_in_user_space(self) -> pymupdf.Point:
        corner = pymupdf.Point(0.0, 0.0) * self._page.derotation_matrix
        crop_box_left = self._page.mediabox.x0 + self._page.cropbox.x0
        crop_box_top = self._page.mediabox.y1 - self._page.cropbox.y0
        return pymupdf.Point(crop_box_left + corner.x, crop_box_top - corner.y)
