from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import (
    EQUATION_KIND, INLINE_MATH_KIND, NOTATION_KINDS, TEXT_KIND, Block, DocumentBlocks, PageBlocks,
)
from _extract.build import BuildInputs, CorpusBuild
from _extract.paths import CorpusFile
from _extract.readings import WorkerReadings
from _extract.spans import ExcludedSpans
from _vaults import TempVault, TextPdf

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
NOTE_TEXT = "---\ntitle: A Work\ntype: book\n---\n\n[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)\n"
BBOX = (0.0, 0.0, 100.0, 100.0)
PAGES = 3
KINDS_BY_PAGE = {1: [TEXT_KIND], 2: [EQUATION_KIND, EQUATION_KIND, INLINE_MATH_KIND], 3: [INLINE_MATH_KIND]}


def page_of(file_page: int, kinds: list[str]) -> PageBlocks:
    return PageBlocks(file_page,
                      [Block(file_page, kind, f"<p>{kind}</p>", BBOX, {}, f"/page/{file_page}/{kind}/{index}")
                                  for index, kind in enumerate(kinds)])


def document(kinds_by_page: dict[int, list[str]]) -> DocumentBlocks:
    return DocumentBlocks([page_of(file_page, kinds) for file_page, kinds in sorted(kinds_by_page.items())])


class FakePlan:
    def __init__(self, blocks: DocumentBlocks) -> None:
        self._blocks = blocks
        self.mode = "text-layer"

    @staticmethod
    def reads_pixels(_file_page: int) -> bool:
        return False

    def blocks(self, _page_count: int) -> DocumentBlocks:
        return self._blocks


class TestNotationBlockCounts(unittest.TestCase):
    def test_a_page_is_counted_by_the_notation_kinds_it_holds(self) -> None:
        self.assertEqual({EQUATION_KIND: 2, INLINE_MATH_KIND: 1},
                         document(KINDS_BY_PAGE).kind_counts(NOTATION_KINDS)[2])

    def test_a_page_holding_no_notation_block_is_left_out(self) -> None:
        self.assertEqual([2, 3], sorted(document(KINDS_BY_PAGE).kind_counts(NOTATION_KINDS)))


class TestTheReportCarriesTheCounts(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        pdf = TextPdf(self.vault.library / f"{BASENAME}.pdf", PAGES).write()
        (self.vault.corpus / f"{BASENAME}.md").write_text(NOTE_TEXT, encoding="utf-8")
        inputs = BuildInputs(pdf, CorpusFile(pdf), FakePlan(document(KINDS_BY_PAGE)), WorkerReadings([]),
                             ExcludedSpans.none())
        self.build = CorpusBuild(inputs)

    def test_the_build_counts_the_engine_notation_blocks_per_file_page(self) -> None:
        self.assertEqual({2: {EQUATION_KIND: 2, INLINE_MATH_KIND: 1}, 3: {EQUATION_KIND: 0, INLINE_MATH_KIND: 1}},
                         self.build.notation_blocks())


if __name__ == "__main__":
    unittest.main()
