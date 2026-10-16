from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from _support import LiveTree

LiveTree.activate()

import pagetext
import pymupdf
import verify
from _vaults import TempVault, TextPdf

BASENAME = "Hegel - 1969 - Wissenschaft der Logik"
KEY = "C5KMCNIA"
LINK_LINE = f"[{BASENAME}.pdf](zotero://open-pdf/library/items/{KEY})"
QUOTE_ON_PAGE_TWO = "Page 2 of the work, with words enough"
QUOTE_ON_EVERY_PAGE = "of the work, with words enough to measure"
QUOTE_ACROSS_PAGES_ONE_AND_TWO = "enough to measure. Page 2 of the work"
PATCHED_DIRS = ("CORPUS_DIR", "LIBRARY_DIR")


class VerifyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(self.vault.library / f"{BASENAME}.pdf").write()

    def write_note(self, body: str) -> None:
        (self.vault.corpus / f"{BASENAME}.md").write_text(f"---\ntitle: x\n---\n\n{body}\n", encoding="utf-8")

    def verification(self) -> verify.QuoteVerification:
        return verify.QuoteVerification(self.pdf, QUOTE_ON_PAGE_TWO, pagetext.DEFAULT_NEAR_MATCH_THRESHOLD)


class TestDeepLink(VerifyTestCase):
    def test_the_link_opens_the_pdf_at_the_file_page_of_the_hit(self) -> None:
        self.write_note(f"{LINK_LINE}\n\n# One\n\nProse.")
        [hit, *_] = self.verification().payload()["hits"]
        self.assertEqual((2, f"zotero://open-pdf/library/items/{KEY}?page=2"), (hit["pdf_page"], hit["link"]))

    def test_the_rendering_carries_the_link_and_the_page_text(self) -> None:
        self.write_note(f"{LINK_LINE}\n\n# One\n\nProse.")
        rendered = self.verification().rendered()
        self.assertIn(f"link          : zotero://open-pdf/library/items/{KEY}?page=2", rendered)
        self.assertIn(f"page text     : {QUOTE_ON_PAGE_TWO}", rendered)

    def test_a_corpus_file_without_the_link_line_yields_no_link_and_says_why(self) -> None:
        self.write_note("# One\n\nProse.")
        payload = self.verification().payload()
        self.assertIsNone(payload["hits"][0]["link"])
        self.assertIn("PDF link line", payload["link_absent"])

    def test_a_pdf_without_a_corpus_file_yields_no_link_and_says_why(self) -> None:
        payload = self.verification().payload()
        self.assertIn("no corpus file", payload["link_absent"])

    def test_a_verified_quotation_is_reported_verified(self) -> None:
        self.write_note(f"{LINK_LINE}\n\n# One\n\nProse.")
        self.assertTrue(self.verification().verified())


class TestTheFolioComesFromTheCorpusFile(VerifyTestCase):
    def test_the_folio_of_the_hits_page_is_read_from_its_page_marker(self) -> None:
        self.write_note(f"{LINK_LINE}\n\n%% p. 47 (file p. 2) %%\n\nProse.")
        [hit, *_] = self.verification().payload()["hits"]
        self.assertEqual(("47", "corpus"), (hit["printed_page"], hit["folio_source"]))

    def test_the_rendering_names_the_corpus_as_the_folios_source(self) -> None:
        self.write_note(f"{LINK_LINE}\n\n%% p. 47 (file p. 2) %%\n\nProse.")
        self.assertIn("printed folio : 47 (corpus)", self.verification().rendered())

    def test_a_page_the_corpus_file_does_not_mark_falls_back_to_the_text_layer(self) -> None:
        self.write_note(f"{LINK_LINE}\n\n%% p. 12 (file p. 1) %%\n\nProse.")
        [hit, *_] = self.verification().payload()["hits"]
        self.assertEqual("text layer", hit["folio_source"])

    def test_a_marker_without_a_folio_falls_back_to_the_text_layer(self) -> None:
        self.write_note(f"{LINK_LINE}\n\n%% file p. 2 %%\n\nProse.")
        [hit, *_] = self.verification().payload()["hits"]
        self.assertEqual("text layer", hit["folio_source"])


class TestExactHitsComeFirst(VerifyTestCase):
    def test_an_exact_hit_is_reported_alone_and_marked_exact(self) -> None:
        self.write_note(f"{LINK_LINE}\n\nProse.")
        hits = self.verification().payload()["hits"]
        self.assertEqual([True], [hit["exact"] for hit in hits])

    def test_a_quotation_with_a_typo_still_matches_approximately(self) -> None:
        self.write_note(f"{LINK_LINE}\n\nProse.")
        typed = verify.QuoteVerification(self.pdf, QUOTE_ON_PAGE_TWO[:-6] + "xqzkw", 0.8)
        [hit, *_] = typed.payload()["hits"]
        self.assertFalse(hit["exact"])


class TestAmbiguousQuotation(VerifyTestCase):
    def verification(self) -> verify.QuoteVerification:
        return verify.QuoteVerification(self.pdf, QUOTE_ON_EVERY_PAGE, pagetext.DEFAULT_NEAR_MATCH_THRESHOLD)

    def test_a_quotation_found_on_more_than_one_page_is_ambiguous_not_verified(self) -> None:
        verification = self.verification()
        self.assertEqual((False, True), (verification.verified(), verification.ambiguous()))

    def test_the_payload_lists_every_page_the_quotation_is_on(self) -> None:
        payload = self.verification().payload()
        self.assertEqual([1, 2, 3], [hit["pdf_page"] for hit in payload["hits"]])

    def test_the_rendering_names_the_verdict_and_every_file_page(self) -> None:
        rendered = self.verification().rendered()
        self.assertTrue(rendered.startswith("AMBIGUOUS in"))
        self.assertIn("file page 1", rendered)
        self.assertIn("file page 3", rendered)

    def test_the_verify_command_exits_one_on_an_ambiguous_quotation(self) -> None:
        with redirect_stdout(io.StringIO()):
            status = verify.VerifyCli().run(["verify", BASENAME, QUOTE_ON_EVERY_PAGE])
        self.assertEqual(verify.NOT_VERIFIED_EXIT_CODE, status)


class TestLocate(VerifyTestCase):
    def test_locate_reports_every_page_naming_the_term_with_its_count(self) -> None:
        pages = verify.TermLocation(self.pdf, "words enough", 25).payload()["pages"]
        self.assertEqual([(1, 1), (2, 1), (3, 1)], [(page["pdf_page"], page["occurrences"]) for page in pages])

    def test_locate_reads_the_pages_the_quote_cache_holds_without_opening_the_pdf(self) -> None:
        pagetext.find_quote(self.pdf, QUOTE_ON_PAGE_TWO)
        with patch.object(pymupdf, "open", side_effect=AssertionError("the PDF was opened again")):
            pages = verify.TermLocation(self.pdf, "words enough", 25).payload()["pages"]
        self.assertEqual([1, 2, 3], [page["pdf_page"] for page in pages])

    def test_locate_stops_at_the_limit(self) -> None:
        self.assertEqual(2, len(verify.TermLocation(self.pdf, "words enough", 2).payload()["pages"]))


class TestQuotationAcrossPages(VerifyTestCase):
    def verification(self) -> verify.QuoteVerification:
        return verify.QuoteVerification(self.pdf, QUOTE_ACROSS_PAGES_ONE_AND_TWO,
                                        pagetext.DEFAULT_NEAR_MATCH_THRESHOLD)

    def test_a_quotation_across_a_page_break_is_verified_at_the_first_page(self) -> None:
        verification = self.verification()
        [hit] = verification.payload()["hits"]
        self.assertEqual((True, 1, (1, 2)), (verification.verified(), hit["pdf_page"], hit["spans_pages"]))

    def test_the_rendering_names_both_file_pages(self) -> None:
        self.assertIn("spans pages   : file pages 1 and 2", self.verification().rendered())

    def test_a_quotation_within_one_page_spans_nothing(self) -> None:
        [hit, *_] = verify.QuoteVerification(self.pdf, QUOTE_ON_PAGE_TWO, 0.85).payload()["hits"]
        self.assertIsNone(hit["spans_pages"])


class TestQuality(VerifyTestCase):
    def test_a_sparse_text_layer_is_not_good(self) -> None:
        self.assertFalse(verify.TextLayerQuality(self.pdf, None).is_good())

    def test_the_quality_command_exits_three_on_a_poor_text_layer(self) -> None:
        with redirect_stdout(io.StringIO()):
            status = verify.VerifyCli().run(["quality", f"{BASENAME}.pdf"])
        self.assertEqual(verify.POOR_TEXT_LAYER_EXIT_CODE, status)


class TestCli(VerifyTestCase):
    def test_a_missing_pdf_exits_four_with_its_name(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            status = verify.VerifyCli().run(["verify", "nope.pdf", "x"])
        self.assertEqual((4, True), (status, "nope.pdf" in stderr.getvalue()))


if __name__ == "__main__":
    unittest.main()
