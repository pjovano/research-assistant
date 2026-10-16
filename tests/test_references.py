from __future__ import annotations

import json
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

import references
import vault
from _vaults import TempVault

AUTHOR_DATE_ZONE = """References
Allison, H. (1973). The Kant-Eberhard Controversy. Baltimore: Johns Hopkins.
Friedman, M. (1992). Kant and the Exact Sciences. Cambridge, MA: Harvard
University Press.
Parsons, C. (1964). Infinity and Kant's Conception of the Possibility of
Experience. Philosophical Review 73.
"""

NUMBERED_ZONE = """General Bibliography
1. Adickes, E. Kant als Naturforscher (Berlin, 1924).
2. Friedman, M. Kant and the Exact Sciences (Cambridge, Mass., 1992).
"""

REPEAT_AUTHOR_ZONE = """References
Quine, W. V. O. 1953. From a Logical Point of View. Cambridge: Harvard.
---. 1961b. "Two Dogmas of Empiricism", in Quine (1961a), pages 20-46.
"""

NOTE_BODY = "## Argument\n\nThe work argues something.\n"

PDF_TEXT_ORIGIN = (72, 72)

PDF_TEXT_SIZE = 11


class NoteFile:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def written(self, basename: str, meta: dict) -> Path:
        path = self._directory / f"{basename}.md"
        vault.write_frontmatter(path, meta, NOTE_BODY)
        return path


class PdfFile:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def written(self, basename: str, pages: list[str]) -> Path:
        path = self._directory / f"{basename}.pdf"
        document = pymupdf.open()
        for text in pages:
            document.new_page().insert_text(PDF_TEXT_ORIGIN, text, fontsize=PDF_TEXT_SIZE)
        document.save(path)
        document.close()
        return path


class TemporaryDirectoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)


class TestEntryParser(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = references.EntryParser()

    def test_author_date_entries_are_split_one_per_work(self) -> None:
        self.assertEqual(3, len(self.parser.parse(AUTHOR_DATE_ZONE)))

    def test_a_wrapped_entry_is_joined(self) -> None:
        friedman = self.parser.parse(AUTHOR_DATE_ZONE)[1]
        self.assertIn("Harvard University Press", friedman.raw)

    def test_numbered_entries_are_split(self) -> None:
        self.assertEqual(2, len(self.parser.parse(NUMBERED_ZONE)))

    def test_the_year_is_read_from_the_entry(self) -> None:
        self.assertEqual("1992", self.parser.parse(AUTHOR_DATE_ZONE)[1].year)

    def test_a_repeat_author_dash_inherits_the_previous_surname(self) -> None:
        self.assertEqual(("quine",), self.parser.parse(REPEAT_AUTHOR_ZONE)[1].surnames)

    def test_a_lettered_year_is_read_without_its_suffix(self) -> None:
        self.assertEqual("1961", self.parser.parse(REPEAT_AUTHOR_ZONE)[1].year)

    def test_the_surname_is_read_from_the_entry(self) -> None:
        self.assertIn("friedman", self.parser.parse(AUTHOR_DATE_ZONE)[1].surnames)


class TestTitleTokens(unittest.TestCase):
    def test_title_tokens_drop_stopwords_and_short_words(self) -> None:
        self.assertEqual({"exact", "sciences", "kant"},
                         references.WorkFactory.tokens_of("Kant and the Exact Sciences"))

    def test_tokens_are_case_folded(self) -> None:
        self.assertIn("critique", references.WorkFactory.tokens_of("Critique of Pure Reason"))


class TestNormalizePhrase(unittest.TestCase):
    def test_normalize_phrase_is_a_public_name_of_the_facade(self) -> None:
        self.assertIn("normalize_phrase", references.__all__)

    def test_case_is_folded(self) -> None:
        self.assertEqual("critique of pure reason",
                         references.normalize_phrase("Critique of Pure Reason"))

    def test_punctuation_becomes_a_space(self) -> None:
        self.assertEqual("kant s conception",
                         references.normalize_phrase("Kant's Conception"))

    def test_runs_of_whitespace_collapse_and_the_edges_are_stripped(self) -> None:
        self.assertEqual("science of logic",
                         references.normalize_phrase("  Science   of\n logic  "))

    def test_non_ascii_letters_survive(self) -> None:
        self.assertEqual("über die wissenschaft",
                         references.normalize_phrase("Über die Wissenschaft."))


class NoteWorkTestCase(TemporaryDirectoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.notes = NoteFile(self.vault.corpus)

    def work(self, basename: str, **meta) -> references.LibraryWork:
        return references.WorkFactory().of(self.notes.written(basename, meta))

    def logic(self) -> references.LibraryWork:
        return self.work("Hegel - 2010 - The Science of Logic",
                         title="The Science of Logic", author=["Hegel"], year=2010,
                         orig_year=1812, aliases=["Wissenschaft der Logik"],
                         source_type="monograph")


class TestWorkFromCorpusFile(NoteWorkTestCase):
    def test_the_basename_is_the_corpus_files_stem(self) -> None:
        self.assertEqual("Hegel - 2010 - The Science of Logic", self.logic().basename)

    def test_the_authors_are_read_from_the_frontmatter_and_case_folded(self) -> None:
        self.assertEqual(("hegel",), self.logic().surnames)

    def test_the_original_year_is_carried_beside_the_edition_year(self) -> None:
        self.assertEqual(("1812", "2010"), self.logic().years)

    def test_an_alias_contributes_its_own_title_tokens(self) -> None:
        self.assertIn("wissenschaft", self.logic().title_tokens)

    def test_a_corpus_file_without_authors_falls_back_to_the_filename_creator(self) -> None:
        work = self.work("Friedman - 1992 - Kant and the Exact Sciences",
                         title="Kant and the Exact Sciences", year=1992)
        self.assertEqual(("friedman",), work.surnames)


class TestSurnameTokensOfPunctuatedSurnames(NoteWorkTestCase):
    def tokens_of(self, surname: str) -> frozenset[str]:
        work = self.work(f"{surname} - 2000 - A Work", title="A Work", author=[surname], year=2000)
        return work.surname_tokens

    def test_a_hyphenated_surname_yields_the_last_word_of_its_normalized_form(self) -> None:
        self.assertEqual(frozenset({"ponty"}), self.tokens_of("Merleau-Ponty"))

    def test_a_surname_with_an_apostrophe_yields_the_last_word_of_its_normalized_form(self) -> None:
        self.assertEqual(frozenset({"neill"}), self.tokens_of("O'Neill"))

    def test_the_token_is_what_normalizing_the_cited_author_yields(self) -> None:
        cited = frozenset(references.normalize_phrase("Maurice Merleau-Ponty").split())
        self.assertEqual(frozenset({"ponty"}), cited & self.tokens_of("Merleau-Ponty"))


class TestHeldWorksAreFoundByComposedBasename(NoteWorkTestCase):
    DECOMPOSED = "Fre\u0301 - 2018 - A Work"
    COMPOSED = "Fr\u00e9 - 2018 - A Work"

    def test_a_decomposed_corpus_file_is_found_by_its_composed_basename(self) -> None:
        held = references.HeldWorks([self.work(self.DECOMPOSED, title="A Work", year=2018)])
        self.assertEqual(self.COMPOSED, held.find(self.COMPOSED).basename)

    def test_a_decomposed_argument_finds_the_same_work(self) -> None:
        held = references.HeldWorks([self.work(self.DECOMPOSED, title="A Work", year=2018)])
        self.assertIsNotNone(held.find(self.DECOMPOSED))


class TestNoteLinesEntryIndices(unittest.TestCase):
    def test_a_bibliography_heading_carrying_an_inline_page_marker_opens_the_entries(self) -> None:
        body = "# One\n\n# Bibliography %% p. 400 (file p. 420) %%\n\nKant, I. Critique.\n"
        self.assertEqual([3, 4, 5], references.NoteLines(body).entry_indices())

    def test_the_entries_after_the_heading_and_the_footnote_definitions_are_both_entry_lines(self) -> None:
        body = "# References\nKant, I. Critique.\n[^1]: A note.\n"
        self.assertEqual([1, 2], references.NoteLines(body).entry_indices())

    def test_a_lettered_footnote_label_is_a_definition(self) -> None:
        self.assertEqual([1], references.NoteLines("Prose.\n[^a]: A note.\n").entry_indices())

    def test_every_entry_list_of_a_collected_volume_is_enumerated(self) -> None:
        body = "# One\n## References\nA, B. 1990.\n# Two\n## References\nC, D. 1991.\n# Notes\n1. E, F. 1992.\n"
        self.assertEqual([2, 5, 7, 8], references.NoteLines(body).entry_indices())


class TestBibliographyHeadingIsTheVaultsRule(unittest.TestCase):
    SAMPLES = ("Works Cited", "*Bibliography*", "Notes", "Selected Bibliography and Further Reading on Kant Today")

    def test_the_zone_heading_test_agrees_with_the_vault_on_every_sample(self) -> None:
        for sample in self.SAMPLES:
            with self.subTest(sample=sample):
                self.assertEqual(vault.is_bibliography_heading(sample),
                                 references.SectionHeading.of_bibliography().matches(sample))


class ReferenceExtractionTestCase(TemporaryDirectoryTestCase):
    BODY_PAGES = ["Chapter One\n\nSome body text about Kant and mathematics.",
                  "Chapter Two\n\nMore body text on the exact sciences."]

    BIBLIOGRAPHY_PAGE = ("References\n\n"
                         "Allison, H. (1973). The Kant-Eberhard Controversy. Baltimore: Hopkins.\n"
                         "Friedman, M. (1992). Kant and the Exact Sciences. Cambridge: Harvard.")

    INDEX_PAGE = "Index\n\nKant, 3\nmathematics, 1"

    BIBLIOGRAPHY_PAGE_NUMBER = len(BODY_PAGES) + 1

    def setUp(self) -> None:
        super().setUp()
        self.pdfs = PdfFile(self.vault.library)

    def extracted(self, basename: str, pages: list[str]) -> references.ReferenceRecord:
        return references.ReferenceExtractor().extract(self.pdfs.written(basename, pages))

    def with_bibliography(self) -> references.ReferenceRecord:
        pages = self.BODY_PAGES + [self.BIBLIOGRAPHY_PAGE, self.INDEX_PAGE]
        return self.extracted("Some - 2001 - Work", pages)


class TestReferenceExtraction(ReferenceExtractionTestCase):
    def test_a_bibliography_heading_in_the_tail_is_located(self) -> None:
        self.assertEqual(references.BIBLIOGRAPHY, self.with_bibliography().method)

    def test_the_zone_starts_on_the_page_carrying_the_heading(self) -> None:
        self.assertEqual(self.BIBLIOGRAPHY_PAGE_NUMBER, self.with_bibliography().first_page)

    def test_the_zone_closes_before_the_index(self) -> None:
        self.assertEqual(self.BIBLIOGRAPHY_PAGE_NUMBER, self.with_bibliography().last_page)

    def test_the_entries_of_the_zone_are_parsed_one_per_work(self) -> None:
        self.assertEqual(2, len(self.with_bibliography().entries))

    def test_the_zone_text_is_kept_for_rematching(self) -> None:
        self.assertIn("Kant-Eberhard", self.with_bibliography().text)

    def test_the_record_takes_its_basename_from_the_file(self) -> None:
        self.assertEqual("Some - 2001 - Work", self.with_bibliography().basename)

    def test_a_pdf_with_no_reference_heading_reports_an_absent_zone(self) -> None:
        record = self.extracted("Other - 2002 - Work", self.BODY_PAGES)
        self.assertEqual(references.ABSENT, record.method)

    def test_an_absent_zone_carries_no_entries(self) -> None:
        record = self.extracted("Other - 2003 - Work", self.BODY_PAGES)
        self.assertEqual([], record.entries)


class CachedZoneTestCase(ReferenceExtractionTestCase):
    def written_pdf(self, pages: list[str] | None = None) -> Path:
        tail = pages or [self.BIBLIOGRAPHY_PAGE, self.INDEX_PAGE]
        return self.pdfs.written("Some - 2005 - Work", self.BODY_PAGES + tail)

    def cache_path(self, pdf_path: Path) -> Path:
        return vault.SCRATCH_DIR / pdf_path.stem / references.ZONE_CACHE_NAME

    def overwrite_cached_text(self, pdf_path: Path, text: str) -> None:
        path = self.cache_path(pdf_path)
        entry = json.loads(path.read_text(encoding="utf-8"))
        entry["zone"]["text"] = text
        path.write_text(json.dumps(entry), encoding="utf-8")


class TestCachedZone(CachedZoneTestCase):
    def test_the_located_zone_is_written_under_the_pdf_stem(self) -> None:
        pdf_path = self.written_pdf()
        references.CachedZone(pdf_path).locate()
        self.assertTrue(self.cache_path(pdf_path).is_file())

    def test_a_second_locate_reads_the_cache_instead_of_the_pdf(self) -> None:
        pdf_path = self.written_pdf()
        references.CachedZone(pdf_path).locate()
        self.overwrite_cached_text(pdf_path, "read from the cache")
        self.assertEqual("read from the cache", references.CachedZone(pdf_path).locate().text)

    def test_a_rewritten_pdf_is_located_again(self) -> None:
        pdf_path = self.written_pdf()
        references.CachedZone(pdf_path).locate()
        self.overwrite_cached_text(pdf_path, "read from the cache")
        self.written_pdf([self.BIBLIOGRAPHY_PAGE])
        self.assertIn("Kant-Eberhard", references.CachedZone(pdf_path).locate().text)

    def test_the_cached_zone_carries_the_same_pages_as_the_located_one(self) -> None:
        pdf_path = self.written_pdf()
        located = references.CachedZone(pdf_path).locate()
        self.assertEqual(located, references.CachedZone(pdf_path).locate())


class TestZoneLocator(ReferenceExtractionTestCase):
    def _zone(self) -> references.ReferenceZone:
        pages = self.BODY_PAGES + [self.BIBLIOGRAPHY_PAGE, self.INDEX_PAGE]
        path = self.pdfs.written("Some - 2004 - Work", pages)
        return references.ZoneLocator(path).locate()

    def test_a_located_zone_is_present(self) -> None:
        self.assertTrue(self._zone().is_present)


if __name__ == "__main__":
    unittest.main()
