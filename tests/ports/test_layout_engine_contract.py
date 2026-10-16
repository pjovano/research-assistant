from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeLayoutEngine
from _ports.compute import LAYOUT_MODES, Cost, LayoutEngine
from _rag_fakes import temp_directory

PAGE_COUNT = 3
PIXEL_PAGES = 1


class LayoutEngineContract:
    def engine(self) -> LayoutEngine:
        raise NotImplementedError

    def setUp(self) -> None:
        self.pdf = temp_directory(self) / "work.pdf"
        self.pdf.write_bytes(self.pdf_bytes())

    def pdf_bytes(self) -> bytes:
        return b""

    def test_each_mode_converts_to_a_document(self) -> None:
        engine = self.engine()
        for mode in LAYOUT_MODES:
            with self.subTest(mode=mode), engine.session():
                self.assertIsInstance(engine.convert(self.pdf, None, mode), dict)

    def test_named_file_pages_convert_to_a_document(self) -> None:
        engine = self.engine()
        with engine.session():
            self.assertIsInstance(engine.convert(self.pdf, [1], LAYOUT_MODES[0]), dict)

    def test_the_cost_counts_no_more_pixel_pages_than_pages(self) -> None:
        cost = self.engine().cost(self.pdf)
        self.assertIsInstance(cost, Cost)
        self.assertTrue(0 <= cost.pixel_pages <= cost.pages)

    def test_a_session_is_entered_and_left(self) -> None:
        with self.engine().session() as entered:
            self.assertIsNone(entered)


class TestFakeLayoutEngineKeepsTheContract(LayoutEngineContract, unittest.TestCase):
    def engine(self) -> LayoutEngine:
        return FakeLayoutEngine(PAGE_COUNT, PIXEL_PAGES)


if __name__ == "__main__":
    unittest.main()
