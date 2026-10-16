from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

import pagetext
from math_fonts import MathFonts

from _writing.notation_restoration import QuotationWording

FONT_SIZE = 11
ORIGIN = pymupdf.Point(72, 100)
SPACE_INSIDE_THE_LIGATURE = 2.8


class BuiltPdf:
    def __init__(self, directory: Path, name: str) -> None:
        self.path = directory / name
        self._document = pymupdf.open()
        self._page = self._document.new_page()
        self._writer = pymupdf.TextWriter(self._page.rect)
        self._point = ORIGIN

    def set(self, text: str, font: str = "helv") -> None:
        self._writer.append(self._point, text, font=pymupdf.Font(font), fontsize=FONT_SIZE)
        self._point = self._writer.last_point

    def set_a_space_with_no_advance(self) -> None:
        self._writer.append(self._point - (SPACE_INSIDE_THE_LIGATURE, 0), " ", font=pymupdf.Font("helv"),
                            fontsize=FONT_SIZE)

    def saved(self) -> Path:
        self._writer.write_text(self._page)
        self._document.save(self.path)
        return self.path


class PdfTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)


class TestASpaceWithNoAdvanceAfterALigature(PdfTestCase):
    def setUp(self) -> None:
        super().setUp()
        pdf = BuiltPdf(self.directory, "ligature.pdf")
        pdf.set("Number is peculiarly Greek in its de")
        pdf.set("ﬁ")
        pdf.set_a_space_with_no_advance()
        pdf.set("nition, and a book is taken oﬀ the shelf to read it.")
        self.pdf = pdf.saved()

    def test_the_page_text_reads_the_word_whole(self) -> None:
        [(_page, text)] = pagetext.page_texts(self.pdf)
        self.assertIn("in its deﬁnition,", text)

    def test_a_space_that_advances_after_a_ligature_is_kept(self) -> None:
        [(_page, text)] = pagetext.page_texts(self.pdf)
        self.assertIn("oﬀ the shelf", text)

    def test_the_word_as_the_corpus_file_writes_it_verifies_exactly(self) -> None:
        [hit, *_rest] = pagetext.find_quote(self.pdf, "Number is peculiarly Greek in its definition")
        self.assertTrue(hit.exact)

    def test_the_prose_text_reads_the_word_whole(self) -> None:
        self.assertIn("deﬁnition", MathFonts(self.pdf).prose_text(1))


class TestASpaceSetInsideAMathFontRun(PdfTestCase):
    QUOTE = "from a true P ∧¬P follows nothing at all in this sentence"

    def setUp(self) -> None:
        super().setUp()
        pdf = BuiltPdf(self.directory, "math-run.pdf")
        pdf.set("from a true P")
        pdf.set(" ∧¬", font="symb")
        pdf.set("P follows nothing at all in this sentence of prose, and more prose to measure.")
        self.pdf = pdf.saved()

    def test_the_prose_text_keeps_the_space_of_the_math_run(self) -> None:
        self.assertIn("a true P P follows", " ".join(MathFonts(self.pdf).prose_text(1).split()))

    def test_the_quotation_with_its_notation_verifies_exactly(self) -> None:
        quoted = pagetext.QuotedNotation(self.pdf, self.QUOTE)
        [hit, *_rest] = pagetext.find_quote_in_texts(self.pdf, quoted.prose(), quoted.prose_pages())
        self.assertTrue(hit.exact)


class TestTheQuotationAsPassed(unittest.TestCase):
    def test_a_quotation_agreeing_with_the_page_is_written_as_passed(self) -> None:
        wording = QuotationWording("Greek in its definition", "Greek in its deﬁnition", ()).written()
        self.assertEqual("Greek in its definition", wording)

    def test_a_quotation_agreeing_but_for_quotation_marks_is_written_as_passed(self) -> None:
        self.assertEqual("Hegel's notion", QuotationWording("Hegel's notion", "Hegel’s notion", ()).written())

    def test_a_quotation_differing_in_case_takes_the_pages_words(self) -> None:
        self.assertEqual("Kant has declared", QuotationWording("kant has declared", "Kant has declared", ()).written())

    def test_a_quotation_with_a_stray_space_takes_the_pages_words(self) -> None:
        self.assertEqual("its deﬁnition", QuotationWording("its deﬁ nition", "its deﬁnition", ()).written())

    def test_notation_as_passed_is_kept_where_the_prose_agrees(self) -> None:
        wording = QuotationWording("the proposition 5 + 7 = 12 is", "the proposition 5 7 12 is", ("+", "=")).written()
        self.assertEqual("the proposition 5 + 7 = 12 is", wording)

    def test_a_delimited_span_as_passed_is_kept_where_the_prose_agrees(self) -> None:
        wording = QuotationWording("so that $a + b$ is the sum", "so that is the sum", ("$a + b$",)).written()
        self.assertEqual("so that $a + b$ is the sum", wording)


if __name__ == "__main__":
    unittest.main()
