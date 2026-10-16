from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import vault
from references import (
    DEFAULT_CITATION_PARSER_MODEL, PARSER_CACHE_FILENAME, CitationParser, CitationParserUnavailable, LabelledSpan,
    ParsedReference, ParsedReferenceCache, ParserSettings, SpanFields,
)
from _vaults import TempVault

BRANDOM_ENTRY = ("Brandom, R. B. (1994). Making It Explicit: Reasoning, Representing, and Discursive Commitment. "
                 "Harvard University Press, Cambridge, Mass.")


def spans(*labelled: tuple[str, str]) -> list[LabelledSpan]:
    built, position = [], 0
    for label, text in labelled:
        built.append(LabelledSpan(label, text, position, position + len(text)))
        position += len(text) + 1
    return built


def parsed(*labelled: tuple[str, str]) -> ParsedReference:
    return SpanFields(spans(*labelled)).reference()


def positioned(*placed: tuple[str, str, int, int]) -> ParsedReference:
    return SpanFields([LabelledSpan(*span) for span in placed]).reference()


def model_is_cached() -> bool:
    from huggingface_hub import try_to_load_from_cache
    return isinstance(try_to_load_from_cache(DEFAULT_CITATION_PARSER_MODEL, "config.json"), str)


class TestSpanFields(unittest.TestCase):
    def test_the_first_title_span_is_the_title_and_the_second_the_container(self) -> None:
        reference = parsed(("AUTHORS", "Angell, R. B."),
                           ("TITLE", "Deducibility, entailment and analytic containment"),
                           ("TITLE", "Directions in Relevant Logic"))
        self.assertEqual(("Deducibility, entailment and analytic containment", "Directions in Relevant Logic"),
                         (reference.title, reference.container))

    def test_a_journal_span_is_the_container_when_there_is_one_title(self) -> None:
        reference = parsed(("TITLE", "Tonk, Plonk and Plink"), ("JOURNAL", "Analysis"))
        self.assertEqual("Analysis", reference.container)

    def test_year_fragments_are_joined(self) -> None:
        reference = positioned(("PUBLICATION_YEAR", "20", 10, 12), ("PUBLICATION_YEAR", "23", 12, 14))
        self.assertEqual("2023", reference.year)

    def test_a_title_split_inside_a_word_is_joined(self) -> None:
        reference = positioned(("TITLE", "Philos", 0, 6), ("TITLE", "ophical Investigations", 6, 28))
        self.assertEqual(("Philosophical Investigations", None), (reference.title, reference.container))

    def test_a_word_split_across_two_labels_takes_the_label_of_its_first_piece(self) -> None:
        reference = positioned(("TITLE", "Philos", 0, 6), ("JOURNAL", "ophical Investigations", 6, 28))
        self.assertEqual(("Philosophical Investigations", None), (reference.title, reference.container))

    def test_a_year_span_on_bare_punctuation_is_ignored(self) -> None:
        reference = positioned(("PUBLICATION_YEAR", ".", 3, 4), ("PUBLICATION_YEAR", "1989", 10, 14))
        self.assertEqual("1989", reference.year)

    def test_a_second_year_far_from_the_first_is_not_joined(self) -> None:
        reference = positioned(("PUBLICATION_YEAR", "1994", 10, 14), ("PUBLICATION_YEAR", "2001", 60, 64))
        self.assertEqual("1994", reference.year)

    def test_a_trailing_year_letter_is_trimmed_from_the_author_span(self) -> None:
        self.assertEqual(("Boolos, G.",), parsed(("AUTHORS", "Boolos, G. 1984a")).authors)

    def test_a_repeated_author_dash_yields_no_author(self) -> None:
        self.assertEqual((), parsed(("AUTHORS", "———."), ("TITLE", "Word and Object")).authors)

    def test_two_author_spans_are_two_authors(self) -> None:
        reference = parsed(("AUTHORS", "Hlobil, U."), ("AUTHORS", "Brandom, R."))
        self.assertEqual(("Hlobil, U.", "Brandom, R."), reference.authors)

    def test_the_pages_join_first_and_last(self) -> None:
        self.assertEqual("430–449", parsed(("PAGE_FIRST", "430"), ("PAGE_LAST", "449")).pages)

    def test_a_first_page_alone_is_the_pages(self) -> None:
        self.assertEqual("147", parsed(("PAGE_FIRST", "147")).pages)

    def test_the_publisher_is_read(self) -> None:
        self.assertEqual("Harvard University Press", parsed(("PUBLISHER", "Harvard University Press")).publisher)

    def test_absent_fields_are_none(self) -> None:
        self.assertEqual(ParsedReference((), None, None, None, None, None), parsed())


class TestParserSettings(unittest.TestCase):
    def test_the_default_model_is_the_siris_parser(self) -> None:
        self.assertEqual(DEFAULT_CITATION_PARSER_MODEL, ParserSettings({}).model)

    def test_machine_json_names_the_model(self) -> None:
        self.assertEqual("other/parser", ParserSettings({"citation_parser_model": "other/parser"}).model)


UNAVAILABLE_MODEL = "no-such-org/no-such-citation-parser"
BRANDOM_PARSED = ParsedReference(("Brandom, R. B.",), "Making It Explicit", None, "1994",
                                 "Harvard University Press", None)


class DerivedCacheTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("RAG_DIR").activate()
        self.addCleanup(self.vault.discard)

    @property
    def cache_path(self) -> Path:
        return vault.RAG_DIR / PARSER_CACHE_FILENAME


class TestParsedReferenceCache(DerivedCacheTestCase):
    def test_a_remembered_reference_comes_back_whole(self) -> None:
        cache = ParsedReferenceCache(DEFAULT_CITATION_PARSER_MODEL)
        cache.remember(BRANDOM_ENTRY, BRANDOM_PARSED)
        remembered = ParsedReferenceCache(DEFAULT_CITATION_PARSER_MODEL).remembered(BRANDOM_ENTRY)
        self.assertEqual(BRANDOM_PARSED, remembered)

    def test_an_entry_never_seen_is_not_remembered(self) -> None:
        cache = ParsedReferenceCache(DEFAULT_CITATION_PARSER_MODEL)
        cache.remember(BRANDOM_ENTRY, BRANDOM_PARSED)
        self.assertIsNone(cache.remembered("Somebody else. Something else. 1999."))

    def test_another_model_does_not_read_the_first_models_entry(self) -> None:
        ParsedReferenceCache(DEFAULT_CITATION_PARSER_MODEL).remember(BRANDOM_ENTRY, BRANDOM_PARSED)
        self.assertIsNone(ParsedReferenceCache("other/parser").remembered(BRANDOM_ENTRY))

    def test_a_miss_creates_no_cache_file(self) -> None:
        ParsedReferenceCache(DEFAULT_CITATION_PARSER_MODEL).remembered(BRANDOM_ENTRY)
        self.assertFalse(self.cache_path.exists())

    def test_the_cache_file_is_created_beside_the_search_stores(self) -> None:
        ParsedReferenceCache(DEFAULT_CITATION_PARSER_MODEL).remember(BRANDOM_ENTRY, BRANDOM_PARSED)
        self.assertTrue(self.cache_path.is_file())


class TestCitationParserLoading(DerivedCacheTestCase):
    def test_a_remembered_entry_is_returned_without_loading_the_model(self) -> None:
        ParsedReferenceCache(UNAVAILABLE_MODEL).remember(BRANDOM_ENTRY, BRANDOM_PARSED)
        self.assertEqual(BRANDOM_PARSED, CitationParser(UNAVAILABLE_MODEL).parse(BRANDOM_ENTRY))

    def test_a_model_that_cannot_be_loaded_raises_an_error_naming_it(self) -> None:
        with self.assertRaises(CitationParserUnavailable) as raised:
            CitationParser(UNAVAILABLE_MODEL).parse(BRANDOM_ENTRY)
        self.assertIn(UNAVAILABLE_MODEL, str(raised.exception))

    @unittest.skipUnless(model_is_cached(), "the citation parser model is not in the Hugging Face cache")
    def test_the_cached_model_parses_an_author_date_entry(self) -> None:
        reference = CitationParser(DEFAULT_CITATION_PARSER_MODEL).parse(BRANDOM_ENTRY)
        self.assertEqual("1994", reference.year)
        self.assertIn("Brandom", reference.authors[0])
        self.assertIn("Making It Explicit", reference.title)


if __name__ == "__main__":
    unittest.main()
