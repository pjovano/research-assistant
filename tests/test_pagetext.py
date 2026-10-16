from __future__ import annotations

import re
import shutil
import string
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _support import LiveTree

LiveTree.activate()

import pagetext
from _book_fixtures import BODY_LINES, WORDS_PER_LINE, BookPage, BookPdf, PageLabelRun, ProseLines
from _pagetext_fixtures import FakePredictor, fake_classifier, failing_classifier
from _pagetext.quotes import _context
import vault
from _pagetext import pages, quotes
from _vaults import TempVault, TextPdf

TAGGED_WORK = "Roe - 2021 - A Tagged Book"
TAGGED_PAGES = 12
TAG_LETTERS = 4
ROMAN_PAGES = 2
ROMAN_LABELS = "r"
ARABIC_LABELS = "D"
SPLIT_WORK = "Roe - 2021 - A Split Sentence"
OUTLINED_WORK = "Roe - 2021 - An Outlined Work"
OUTLINE = [[1, "One", 1], [2, "Tw\to", 3]]
SPLIT_TEXTS = [(1, "The argument ends with the first half"), (2, "second half begins the next page")]
QUOTE_LENGTH = 90
MIN_SENTENCE_LENGTH = 200

GOOD_PROSE = (
    "The committee argued that the new bridge would carry more traffic than the"
    " old ferry, and that any delay in building it would leave the two towns on"
    " either bank cut off from each other for one more winter. If this is "
    "right, then the council that votes against the bridge has not saved any "
    "money at all, but has merely moved the whole cost onto the people who "
    "wait. What the report shows is that a cheaper crossing cannot on its own "
    "meet the needs of both towns at once, and so some further plan is needed "
    "before the spring floods arrive in the low valley."
)
SCANNER_NOISE = " ".join(
    ["rn", "xvv", "qq", "zzt", "lll", "mmm", "nnn", "ppp", "qrs", "tvv", "wxy", "zbb"] * 6
)
MOJIBAKE = GOOD_PROSE.replace("e", "\ufffd")



class TestNormalize(unittest.TestCase):
    def test_curly_quotes_are_folded_to_ascii(self) -> None:
        self.assertEqual("'a' \"b\"", pagetext.normalize("‘a’ “b”"))

    def test_a_hyphen_broken_word_is_rejoined(self) -> None:
        self.assertEqual("structure", pagetext.normalize("struc-\nture"))

    def test_runs_of_whitespace_collapse(self) -> None:
        self.assertEqual("a b", pagetext.normalize("a   \n\t b"))

    def test_invisible_characters_are_removed(self) -> None:
        self.assertEqual("ab", pagetext.normalize("a​b"))

    def test_normalizing_is_idempotent(self) -> None:
        once = pagetext.normalize("struc-\nture  ‘x’")
        self.assertEqual(once, pagetext.normalize(once))


class TestNormalizedText(unittest.TestCase):
    def page_text_of(self, raw: str, needle: str) -> str:
        normalized = pagetext.NormalizedText(raw)
        start = normalized.text.find(pagetext.normalize(needle))
        self.assertNotEqual(-1, start)
        return normalized.page_text(start, len(pagetext.normalize(needle)))

    def test_the_text_is_what_normalize_returns(self) -> None:
        raw = "The  deter-\nmination of “Being” , un­done ﬁrst…"
        self.assertEqual(pagetext.normalize(raw), pagetext.NormalizedText(raw).text)

    def test_a_soft_hyphen_the_normalizer_folds_stays_in_the_page_text(self) -> None:
        self.assertEqual("sub\u00adject of logic",
                         self.page_text_of("the sub\u00adject of logic here", "subject of logic"))

    def test_a_curly_quote_the_normalizer_folds_stays_in_the_page_text(self) -> None:
        self.assertEqual("Hegel’s “Logic”", self.page_text_of("In Hegel’s “Logic” we read", "hegel's \"logic\""))

    def test_a_ligature_the_normalizer_folds_stays_in_the_page_text(self) -> None:
        self.assertEqual("ﬁrst deﬁnition", self.page_text_of("the ﬁrst deﬁnition given", "first definition"))

    def test_a_line_break_hyphen_is_joined_in_the_page_text(self) -> None:
        self.assertEqual("determination of being",
                         self.page_text_of("the deter-\nmination of being is", "determination of being"))

    def test_whitespace_is_collapsed_but_case_is_kept_in_the_page_text(self) -> None:
        self.assertEqual("Pure Being is", self.page_text_of("so  Pure\nBeing   is the", "pure being is"))

    def test_a_base_letter_and_its_combining_accent_compose_as_in_the_whole_string(self) -> None:
        self.assertEqual("été", pagetext.NormalizedText("e\u0301te\u0301").text)

    def test_a_composed_accent_keeps_the_origin_of_its_base_letter(self) -> None:
        self.assertEqual("e\u0301te\u0301", pagetext.NormalizedText("e\u0301te\u0301").page_text(0, 3))

    def test_a_final_sigma_lowers_as_in_the_whole_string(self) -> None:
        self.assertEqual("ὀδυσσεύς", pagetext.NormalizedText("ὈΔΥΣΣΕΎΣ").text)

    def test_a_soft_hyphen_at_a_line_break_is_joined(self) -> None:
        self.assertEqual("subject", pagetext.normalize("sub\u00ad\nject"))

    def test_the_raw_span_of_an_empty_match_is_empty(self) -> None:
        self.assertEqual((0, 0), pagetext.NormalizedText("abc").raw_span(0, 0))


class TestAssess(unittest.TestCase):
    def test_real_prose_the_classifier_calls_good_is_judged_good(self) -> None:
        self.assertEqual("good", pagetext.assess(GOOD_PROSE, classifier=fake_classifier()).verdict)

    def test_empty_text_is_judged_empty(self) -> None:
        self.assertEqual("empty", pagetext.assess("", classifier=fake_classifier()).verdict)

    def test_a_page_the_classifier_calls_bad_is_judged_poor(self) -> None:
        quality = pagetext.assess(SCANNER_NOISE, classifier=fake_classifier("bad", 0.9))
        self.assertEqual("poor", quality.verdict)
        self.assertIn("classifier reads the page as bad", quality.reason)

    def test_mojibake_is_judged_poor_even_when_the_classifier_calls_it_good(self) -> None:
        quality = pagetext.assess(MOJIBAKE, classifier=fake_classifier())
        self.assertEqual("poor", quality.verdict)
        self.assertIn("replacement character ratio", quality.reason)

    def test_prose_too_short_to_judge_is_called_empty(self) -> None:
        self.assertEqual("empty", pagetext.assess("Short but real prose.", classifier=fake_classifier()).verdict)

    def test_prose_spread_too_thinly_over_pages_is_called_empty(self) -> None:
        self.assertEqual("empty", pagetext.assess(GOOD_PROSE, pages=100, classifier=fake_classifier()).verdict)

    def test_a_verdict_always_carries_a_reason(self) -> None:
        for text in (GOOD_PROSE, "", SCANNER_NOISE, MOJIBAKE):
            with self.subTest(text=text[:20]):
                self.assertTrue(pagetext.assess(text, classifier=fake_classifier()).reason.strip())

    def test_the_quality_report_is_serializable(self) -> None:
        report = pagetext.assess(GOOD_PROSE, classifier=fake_classifier("good", 0.2)).as_dict()
        self.assertIn("verdict", report)
        self.assertEqual(("good", 0.2), (report["classifier_label"], report["classifier_score"]))

    def test_the_classifier_sees_the_assessed_text(self) -> None:
        predictor = FakePredictor("good")
        pagetext.assess(GOOD_PROSE, classifier=pagetext.PageClassifier(lambda: predictor))
        self.assertEqual([GOOD_PROSE], predictor.seen)

    def test_sparse_text_never_reaches_the_classifier(self) -> None:
        self.assertEqual("empty", pagetext.assess("", classifier=failing_classifier()).verdict)


class TestBatchedQuality(unittest.TestCase):
    def test_every_page_of_a_batch_is_measured_in_one_classifier_call(self) -> None:
        predictor = FakePredictor("good")
        measured = pagetext.assess_all([GOOD_PROSE] * 4, classifier=pagetext.PageClassifier(lambda: predictor))
        self.assertEqual((4, 1), (len(measured), predictor.calls))

    def test_a_sparse_page_is_measured_without_reaching_the_classifier(self) -> None:
        predictor = FakePredictor("good")
        measured = pagetext.assess_all(["", GOOD_PROSE], classifier=pagetext.PageClassifier(lambda: predictor))
        self.assertEqual(["empty", "good"], [quality.verdict for quality in measured])
        self.assertEqual([GOOD_PROSE], predictor.seen)

    def test_a_short_page_of_mojibake_measures_poor_rather_than_empty(self) -> None:
        quality = pagetext.assess(MOJIBAKE[:120], classifier=fake_classifier())
        self.assertEqual("poor", quality.verdict)

    def test_a_short_page_of_clean_prose_still_measures_empty(self) -> None:
        self.assertEqual("empty", pagetext.assess("Short but real prose.", classifier=fake_classifier()).verdict)


class TestPageClassifier(unittest.TestCase):
    def test_a_verdict_carries_the_predictor_label_and_score(self) -> None:
        self.assertEqual(pagetext.ClassifierVerdict("bad", 0.75), fake_classifier("bad", 0.75).judge(GOOD_PROSE))

    def test_the_predictor_is_built_once(self) -> None:
        builds = []
        classifier = pagetext.PageClassifier(lambda: builds.append(1) or FakePredictor("good"))
        classifier.judge(GOOD_PROSE)
        classifier.judge(GOOD_PROSE)
        self.assertEqual(1, len(builds))

    def test_a_predictor_that_cannot_start_raises_unavailable_naming_the_cause(self) -> None:
        with self.assertRaises(pagetext.ClassifierUnavailable) as raised:
            failing_classifier().judge(GOOD_PROSE)
        self.assertIn("ConnectionError: no server on port 0", str(raised.exception))

    def test_a_predictor_that_fails_mid_call_raises_unavailable(self) -> None:
        def broken(texts):
            raise TimeoutError("server gone")
        with self.assertRaises(pagetext.ClassifierUnavailable):
            pagetext.PageClassifier(lambda: broken).judge(GOOD_PROSE)

    def test_an_unavailable_classifier_is_reported_not_passed(self) -> None:
        quality = pagetext.assess(GOOD_PROSE, classifier=failing_classifier())
        self.assertEqual("unavailable", quality.verdict)
        self.assertFalse(quality.is_good)
        self.assertIn("classifier unavailable: ConnectionError", quality.reason)

    def test_a_hard_signal_still_fails_the_page_when_the_classifier_is_unavailable(self) -> None:
        quality = pagetext.assess(MOJIBAKE, classifier=failing_classifier())
        self.assertEqual("poor", quality.verdict)
        self.assertIn("classifier unavailable", quality.reason)


class TestContextWindows(unittest.TestCase):
    HAYSTACK = "x" * 400
    MATCH_START = 200
    MATCH_LENGTH = 10
    ELLIPSES = len("...") * 2

    def _width(self, rendered: str) -> int:
        return len(rendered) - self.ELLIPSES - self.MATCH_LENGTH

    def test_quote_context_pads_by_120_each_side(self) -> None:
        rendered = _context(self.HAYSTACK, self.MATCH_START, self.MATCH_LENGTH)
        self.assertEqual(240, self._width(rendered))

    def test_locate_context_pads_by_90_each_side(self) -> None:
        rendered = pagetext.locate_context(self.HAYSTACK, self.MATCH_START, self.MATCH_LENGTH)
        self.assertEqual(180, self._width(rendered))

    def test_locate_context_is_narrower_than_quote_context(self) -> None:
        quote = _context(self.HAYSTACK, self.MATCH_START, self.MATCH_LENGTH)
        locate = pagetext.locate_context(self.HAYSTACK, self.MATCH_START, self.MATCH_LENGTH)
        self.assertLess(len(locate), len(quote))

    def test_a_match_at_the_start_gets_no_leading_ellipsis(self) -> None:
        self.assertFalse(_context(self.HAYSTACK, 0, 5).startswith("..."))

    def test_a_match_in_the_middle_gets_both_ellipses(self) -> None:
        rendered = _context(self.HAYSTACK, self.MATCH_START, self.MATCH_LENGTH)
        self.assertTrue(rendered.startswith("...") and rendered.endswith("..."))


class TaggedLines:
    def __init__(self, page_index: int) -> None:
        self._page_index = page_index

    def page(self) -> BookPage:
        return BookPage(ProseLines(self._page_index).placing(self._line_tags()))

    def _line_tags(self) -> dict[int, str]:
        return {line * WORDS_PER_LINE: self._tag(self._page_index * BODY_LINES + line) for line in range(BODY_LINES)}

    @staticmethod
    def _tag(number: int) -> str:
        letters = []
        for _ in range(TAG_LETTERS):
            number, digit = divmod(number, len(string.ascii_lowercase))
            letters.append(string.ascii_lowercase[digit])
        return "".join(reversed(letters))


class BuiltBookTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vault = TempVault("LIBRARY_DIR").activate()
        cls.pdf = TAGGED_BOOK.write(cls.vault.library / f"{TAGGED_WORK}.pdf")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.vault.discard()


TAGGED_BOOK = BookPdf([TaggedLines(index).page() for index in range(TAGGED_PAGES)],
                      label_runs=(PageLabelRun(0, ROMAN_LABELS), PageLabelRun(ROMAN_PAGES, ARABIC_LABELS)))


class TestPageTexts(BuiltBookTestCase):
    def test_pages_are_numbered_from_one(self) -> None:
        self.assertEqual(1, pagetext.page_texts(self.pdf, limit=1)[0][0])

    def test_the_limit_is_respected(self) -> None:
        self.assertEqual(3, len(pagetext.page_texts(self.pdf, limit=3)))

    def test_start_offsets_the_first_page_number(self) -> None:
        self.assertEqual(3, pagetext.page_texts(self.pdf, limit=1, start=2)[0][0])

    def test_the_fixture_has_a_usable_text_layer(self) -> None:
        text = "".join(t for _, t in pagetext.page_texts(self.pdf, limit=5))
        self.assertEqual("good", pagetext.assess(text, pages=5, classifier=fake_classifier()).verdict)


class TestDocumentCache(BuiltBookTestCase):
    def test_a_repeated_read_reuses_the_parsed_document(self) -> None:
        first = pages.PDF_PAGES.records(self.pdf)
        self.assertIs(first, pages.PDF_PAGES.records(self.pdf))

    def test_a_copy_with_its_own_bytes_is_parsed_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / self.pdf.name
            shutil.copy(self.pdf, copy)
            cached = pages.PDF_PAGES.records(self.pdf)
            self.assertIsNot(cached, pages.PDF_PAGES.records(copy))

    def test_a_segment_is_sliced_from_the_cached_document(self) -> None:
        whole = pagetext.page_texts(self.pdf)
        segment = pagetext.page_texts(self.pdf, limit=2, start=1)
        self.assertEqual(whole[1:3], segment)

    def test_normalized_pages_are_reused_across_quotes(self) -> None:
        first = quotes._NORMALIZED_PAGES.of(self.pdf)
        self.assertIs(first, quotes._NORMALIZED_PAGES.of(self.pdf))


class TestPrintedPageLabel(BuiltBookTestCase):
    def test_a_page_out_of_range_returns_no_label(self) -> None:
        self.assertIsNone(pagetext.printed_page_label(self.pdf, 99999))

    def test_page_zero_returns_no_label(self) -> None:
        self.assertIsNone(pagetext.printed_page_label(self.pdf, 0))

    def test_a_label_is_either_a_string_or_absent(self) -> None:
        label = pagetext.printed_page_label(self.pdf, 2)
        self.assertTrue(label is None or isinstance(label, str))


class TestFindQuote(BuiltBookTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.page_number, cls.quote = cls._borrow_a_sentence()

    @classmethod
    def _borrow_a_sentence(cls) -> tuple[int, str]:
        for number, text in pagetext.page_texts(cls.pdf, limit=12):
            flat = pagetext.normalize(text)
            if len(flat) < MIN_SENTENCE_LENGTH or not re.search(r"[a-z]{4} [a-z]{4}", flat):
                continue
            return number, flat[100:100 + QUOTE_LENGTH]
        raise AssertionError("no page of the built book yields a usable sentence")

    def test_a_quote_taken_from_the_pdf_is_found(self) -> None:
        self.assertTrue(pagetext.find_quote(self.pdf, self.quote))

    def test_the_quote_is_found_on_the_page_it_came_from(self) -> None:
        self.assertEqual(self.page_number, pagetext.find_quote(self.pdf, self.quote)[0].pdf_page)

    def test_a_quote_taken_verbatim_matches_exactly(self) -> None:
        self.assertTrue(pagetext.find_quote(self.pdf, self.quote)[0].exact)

    def test_an_exact_match_has_full_similarity(self) -> None:
        self.assertEqual(1.0, pagetext.find_quote(self.pdf, self.quote)[0].similarity)

    def test_a_hit_carries_surrounding_context(self) -> None:
        self.assertGreater(len(pagetext.find_quote(self.pdf, self.quote)[0].context), len(self.quote))

    def test_a_hit_carries_the_page_text_whose_normal_form_is_the_quote(self) -> None:
        page_text = pagetext.find_quote(self.pdf, self.quote)[0].page_text
        self.assertEqual(pagetext.normalize(self.quote), pagetext.normalize(page_text))

    def test_a_quote_absent_from_the_pdf_is_not_found(self) -> None:
        absent = "Quixotic zebras marshalled the ineffable pumpernickel of Vladivostok."
        self.assertEqual([], pagetext.find_quote(self.pdf, absent))

    def test_a_quote_with_one_typo_still_matches_approximately(self) -> None:
        typo = self.quote[:-5] + "xqzkw"
        hits = pagetext.find_quote(self.pdf, typo, threshold=0.8)
        self.assertTrue(hits and not hits[0].exact)



class TestPageCache(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(self.vault.library / f"{SPLIT_WORK}.pdf").write()

    def test_a_cache_written_by_one_reader_answers_the_next_without_opening_the_pdf(self) -> None:
        quotes._NormalizedPages().of(self.pdf)
        with patch.object(quotes, "page_records", side_effect=AssertionError("the PDF was opened again")):
            [page, *_] = quotes._NormalizedPages().of(self.pdf)
        self.assertEqual((1, "Page 1 of the work"), (page.number, page.page_text(0, len("page 1 of the work"))))

    def test_a_cached_page_carries_the_label_the_text_layer_gave_it(self) -> None:
        [page, *_] = quotes._NormalizedPages().of(self.pdf)
        [cached, *_] = quotes._NormalizedPages().of(self.pdf)
        self.assertEqual((page.label, pagetext.printed_page_label(self.pdf, 1)), (cached.label, page.label))

    def test_a_hit_carries_the_label_of_its_page_without_opening_the_pdf(self) -> None:
        pagetext.find_quote(self.pdf, "words enough to measure")
        with patch.object(quotes, "page_records", side_effect=AssertionError("the PDF was opened again")):
            [hit, *_] = pagetext.find_quote(self.pdf, "words enough to measure")
        self.assertEqual(pagetext.printed_page_label(self.pdf, 1), hit.printed_page)

    def test_a_lone_surrogate_from_the_text_layer_survives_the_cache(self) -> None:
        cache = quotes._PageCache(self.pdf)
        key = [quotes.CACHE_VERSION, *pagetext.document_fingerprint(self.pdf)]
        cache.save(key, [quotes.NormalizedPage(1, quotes.NormalizedWording("a\ud800b", "ab"), None)])
        [page] = cache.loaded(key)
        self.assertEqual("a\ud800b", page.raw)

    def test_a_cache_of_an_earlier_version_is_not_read(self) -> None:
        quotes._NormalizedPages().of(self.pdf)
        cache = quotes._PageCache(self.pdf)
        self.assertIsNone(cache.loaded([quotes.CACHE_VERSION - 1, *pagetext.document_fingerprint(self.pdf)]))


class TestPdfPages(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(self.vault.library / f"{OUTLINED_WORK}.pdf", outline=OUTLINE).write()
        self.pages = pages.PdfPages()

    def test_a_repeated_read_reuses_the_parsed_document(self) -> None:
        self.assertIs(self.pages.records(self.pdf), self.pages.records(self.pdf))

    def test_a_pdf_rewritten_with_more_pages_is_parsed_again(self) -> None:
        before = self.pages.records(self.pdf)
        TextPdf(self.pdf, pages=5).write()
        self.assertEqual((3, 5), (len(before), len(self.pages.records(self.pdf))))

    def test_a_segment_is_a_slice_of_the_whole(self) -> None:
        self.assertEqual(pagetext.page_texts(self.pdf)[1:3], pagetext.page_texts(self.pdf, limit=2, start=1))

    def test_a_page_beyond_the_document_has_no_label(self) -> None:
        labels = (pagetext.printed_page_label(self.pdf, 0), pagetext.printed_page_label(self.pdf, 99))
        self.assertEqual((None, None), labels)

    def test_outline_entries_carry_the_level_the_title_with_a_control_character_read_as_a_space_and_the_page(
            self) -> None:
        self.assertEqual([(1, "One", 1), (2, "Tw o", 3)], pagetext.outline_entries(self.pdf))

    def test_a_render_lands_in_the_scratch_directory_named_after_the_work(self) -> None:
        [render] = pagetext.render_pages(self.pdf, [2, 99])
        self.assertEqual(vault.SCRATCH_DIR / OUTLINED_WORK / "page-0002.png", render)


class TestQuoteAcrossPages(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(self.vault.library / f"{SPLIT_WORK}.pdf").write()

    def found(self, quote: str) -> pagetext.QuoteHit:
        [hit] = pagetext.find_quote_in_texts(self.pdf, quote, SPLIT_TEXTS)
        return hit

    def test_a_quotation_across_a_page_break_is_an_exact_hit_on_the_first_page(self) -> None:
        hit = self.found("the first half second half begins")
        self.assertEqual((1, True, (1, 2)), (hit.pdf_page, hit.exact, hit.spans_pages))

    def test_the_page_text_of_a_spanning_hit_joins_the_wording_of_both_pages(self) -> None:
        self.assertEqual("the first half second half begins", self.found("the first half second half begins").page_text)

    def test_a_quotation_within_one_page_spans_nothing(self) -> None:
        self.assertIsNone(self.found("second half begins the next").spans_pages)


class TestNormalizedEscapes(unittest.TestCase):
    def test_an_escaped_bracket_matches_the_pages_plain_bracket(self) -> None:
        self.assertEqual(pagetext.normalize("the [ourselves] and"), pagetext.normalize("the \\[ourselves\\] and"))

    def test_an_escaped_pipe_matches_the_pages_plain_pipe(self) -> None:
        self.assertEqual(pagetext.normalize("a | b"), pagetext.normalize("a \\| b"))

    def test_a_latex_macro_keeps_its_backslash(self) -> None:
        self.assertIn("\\gamma", pagetext.normalize("\\Gamma holds"))


if __name__ == "__main__":
    unittest.main()
