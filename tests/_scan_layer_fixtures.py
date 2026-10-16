from __future__ import annotations

import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.layer import TextLayer
from _extract.layersample import LayerSample, PixelSampleReader, SampleUnits
from _extract.pixelchapters import PixelChapters
from _scan_fixtures import INVISIBLE, SCAN_GREY
from _vaults import TempVault

BASENAME = "Doe - 1971 - A Scanned Book"
CHAPTER_PAGES = 20
CHAPTERS = 2
PAGE_COUNT = CHAPTER_PAGES * CHAPTERS
WORDS_PER_PAGE = 110
TEXT_BOX = pymupdf.Rect(60, 60, 552, 760)
VOCABULARY = ("reason", "nature", "concept", "intuition", "object", "judgment", "synthesis", "experience",
              "freedom", "spirit", "subject", "appearance", "category", "unity", "consciousness", "ground",
              "form", "matter", "law", "will", "idea", "being", "essence", "relation", "quality", "measure")
MISREAD_EVERY = 4
NOTATION_SPAN = "<math display='inline'>x</math>"


def page_words(file_page: int) -> list[str]:
    return [VOCABULARY[(file_page * 7 + index * 3 + index // 5) % len(VOCABULARY)] for index in range(WORDS_PER_PAGE)]


def page_prose(file_page: int) -> str:
    return " ".join(page_words(file_page))


def misread_prose(file_page: int) -> str:
    return " ".join(word[::-1] + "q" if index % MISREAD_EVERY == 0 else word
                    for index, word in enumerate(page_words(file_page)))


class ScannedBook:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, layer_prose=page_prose, pages_with_layer: int = PAGE_COUNT) -> Path:
        with pymupdf.open() as document:
            for file_page in range(1, PAGE_COUNT + 1):
                page = document.new_page()
                self._scan(page)
                if file_page <= pages_with_layer:
                    page.insert_textbox(TEXT_BOX, layer_prose(file_page), fontname="helv", fontsize=8,
                                        render_mode=INVISIBLE)
            document.set_toc([[1, f"Chapter {index + 1}", index * CHAPTER_PAGES + 1] for index in range(CHAPTERS)])
            document.save(self._path)
        return self._path

    @staticmethod
    def _scan(page: pymupdf.Page) -> None:
        scan = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 80), False)
        scan.set_rect(scan.irect, (SCAN_GREY,))
        page.insert_image(page.rect, pixmap=scan, keep_proportion=False)


class PixelEngine:
    def __init__(self, html_of) -> None:
        self._html_of = html_of
        self.converted: list[list[int]] = []

    def convert(self, _pdf_path: Path, file_pages: list[int]) -> dict:
        self.converted.append(list(file_pages))
        return {"children": [self._page(file_page) for file_page in file_pages]}

    def _page(self, file_page: int) -> dict:
        text = {"block_type": "Text", "id": f"/page/{file_page - 1}/Text/0", "bbox": [60, 60, 552, 760],
                "html": f"<p>{self._html_of(file_page)}</p>"}
        return {"block_type": "Page", "id": f"/page/{file_page - 1}/Page/0", "bbox": [0, 0, 612, 792],
                "children": [text]}


def pixels_matching_the_layer(file_page: int) -> str:
    return page_prose(file_page)


class ScanLayerCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf_path = self.vault.library / f"{BASENAME}.pdf"

    def sample(self, layer_prose=page_prose, pixels=pixels_matching_the_layer) -> tuple[LayerSample, PixelEngine]:
        pdf = ScannedBook(self.pdf_path).write(layer_prose)
        layer = TextLayer(pdf)
        self.addCleanup(layer.close)
        headings = [{"level": 1, "file_page": index * CHAPTER_PAGES + 1} for index in range(CHAPTERS)]
        units = SampleUnits(PixelChapters(headings, PAGE_COUNT).chapters()).units()
        engine = PixelEngine(pixels)
        return LayerSample(layer, units, PixelSampleReader(pdf, engine)), engine
