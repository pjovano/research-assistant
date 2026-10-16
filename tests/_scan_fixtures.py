from __future__ import annotations

import contextlib
import io
import json
import unittest
from collections.abc import Callable
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.cli import main
from _extract.layer import TextLayer
from _extract_fixtures import PROSE
from _vaults import TempVault

BASENAME = "Doe - 1984 - A Scanned Work"
FRONTMATTER = "---\ntitle: A Scanned Work\ntype: journalArticle\n---\n"
PAGES = 3
TEXT_BOX = pymupdf.Rect(72, 72, 520, 700)
FOOT_STRIP_HEIGHT = 40
FOOT_LINE_RISE = 20
FIRST_LINE_BOX = pymupdf.Rect(0, 0, 595, 90)
FOOT_LINE = "Downloaded from a repository on 1 January 2020"
VISIBLE = 0
INVISIBLE = 3
SCAN_GREY = 230
TRACED_FONT = "traced"
TRACED_FONT_MARK = "Bezier"
TRACED_FONT_MARK_VALUE = "1"


class PagePainting:
    @staticmethod
    def image(page: pymupdf.Page) -> None:
        PagePainting._scan(page, page.rect)

    @staticmethod
    def image_above_a_foot_strip(page: pymupdf.Page) -> None:
        PagePainting._scan(page, pymupdf.Rect(0, 0, page.rect.width, page.rect.height - FOOT_STRIP_HEIGHT))

    @staticmethod
    def image_over_the_first_line(page: pymupdf.Page) -> None:
        PagePainting._scan(page, FIRST_LINE_BOX)

    @staticmethod
    def invisible_text(page: pymupdf.Page) -> None:
        page.insert_textbox(TEXT_BOX, PROSE, fontname="helv", fontsize=10, render_mode=INVISIBLE)

    @staticmethod
    def visible_text(page: pymupdf.Page) -> None:
        page.insert_textbox(TEXT_BOX, PROSE, fontname="helv", fontsize=10, render_mode=VISIBLE)

    @staticmethod
    def visible_line_in_the_foot_strip(page: pymupdf.Page) -> None:
        page.insert_text((TEXT_BOX.x0, page.rect.height - FOOT_LINE_RISE), FOOT_LINE, fontname="tiro", fontsize=8)

    @staticmethod
    def visible_text_in_a_font_traced_from_a_scan(page: pymupdf.Page) -> None:
        PagePainting._traced_font(page)
        page.insert_textbox(TEXT_BOX, PROSE, fontname=TRACED_FONT, fontsize=10, render_mode=VISIBLE)

    @staticmethod
    def visible_line_in_the_foot_strip_in_a_font_traced_from_a_scan(page: pymupdf.Page) -> None:
        PagePainting._traced_font(page)
        page.insert_text((TEXT_BOX.x0, page.rect.height - FOOT_LINE_RISE), FOOT_LINE, fontname=TRACED_FONT, fontsize=8)

    @staticmethod
    def _traced_font(page: pymupdf.Page) -> None:
        xref = page.insert_font(fontname=TRACED_FONT, fontbuffer=pymupdf.Font("tiro").buffer)
        page.parent.xref_set_key(xref, TRACED_FONT_MARK, TRACED_FONT_MARK_VALUE)

    @staticmethod
    def _scan(page: pymupdf.Page, area: pymupdf.Rect) -> None:
        scan = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 80), False)
        scan.set_rect(scan.irect, (SCAN_GREY,))
        page.insert_image(area, pixmap=scan, keep_proportion=False)


class PaintedPdf:
    def __init__(self, path: Path, painting_order: tuple[Callable[[pymupdf.Page], None], ...]) -> None:
        self._path = path
        self._painting_order = painting_order

    def write(self) -> Path:
        with pymupdf.open() as document:
            for _page in range(PAGES):
                page = document.new_page()
                for paint in self._painting_order:
                    paint(page)
            document.save(self._path)
        return self._path


class ScanVault:
    def __init__(self, test: unittest.TestCase) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        test.addCleanup(self.vault.discard)
        self._test = test

    def filed(self, painting_order: tuple) -> Path:
        pdf = PaintedPdf(self.vault.library / f"{BASENAME}.pdf", painting_order).write()
        (self.vault.corpus / f"{BASENAME}.md").write_text(FRONTMATTER, encoding="utf-8")
        return pdf

    def layer(self, pdf: Path) -> TextLayer:
        layer = TextLayer(pdf)
        self._test.addCleanup(layer.close)
        return layer

    @staticmethod
    def probed() -> dict:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            main(["probe", f"{BASENAME}.pdf"])
        return json.loads(output.getvalue())
