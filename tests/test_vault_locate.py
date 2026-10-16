from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import vault
from _vault.listing import VaultDirectory
from _vault.locating import PdfSearch
from _vaults import TempVault, TextPdf

PDF_NAME = "Doe - 2020 - A Work.pdf"
DECOMPOSED_STEM = "Fre\u0301 - 2018 - A Work"
COMPOSED_STEM = "Fr\u00e9 - 2018 - A Work"


class TestLocatePdfStaysInsideItsDirectories(unittest.TestCase):
    def setUp(self) -> None:
        self._vault = TempVault("INBOX_DIR", "LIBRARY_DIR").activate()
        self._inbox_pdf = TextPdf(self._vault.inbox / PDF_NAME).write()
        self._library_pdf = TextPdf(self._vault.library / PDF_NAME).write()

    def tearDown(self) -> None:
        self._vault.discard()

    def test_a_path_into_the_library_is_not_found_when_only_the_inbox_is_searched(self) -> None:
        self.assertIsNone(vault.locate_pdf(str(self._library_pdf), (vault.INBOX_DIR,)))

    def test_a_path_into_the_inbox_is_found_when_the_inbox_is_searched(self) -> None:
        self.assertEqual(self._inbox_pdf, vault.locate_pdf(str(self._inbox_pdf), (vault.INBOX_DIR,)))

    def test_a_bare_name_is_found_in_the_first_directory_that_holds_it(self) -> None:
        self.assertEqual(self._library_pdf, vault.locate_pdf(PDF_NAME, (vault.LIBRARY_DIR, vault.INBOX_DIR)))

    def test_a_stem_without_its_suffix_is_found(self) -> None:
        stem = PDF_NAME.removesuffix(".pdf")
        self.assertEqual(self._inbox_pdf, vault.locate_pdf(stem, (vault.INBOX_DIR,)))

    def test_the_search_class_is_what_the_frozen_name_runs(self) -> None:
        self.assertEqual(vault.locate_pdf(PDF_NAME, (vault.INBOX_DIR,)),
                         PdfSearch(PDF_NAME, (vault.INBOX_DIR,)).found())


class TestVaultDirectoryListings(unittest.TestCase):
    NUMBERED_COPY = "Doe - 2020 - A Work 2.pdf"

    def setUp(self) -> None:
        self._vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self._vault.discard)
        (self._vault.library / PDF_NAME).write_bytes(b"%PDF-1.7")
        (self._vault.library / self.NUMBERED_COPY).write_bytes(b"%PDF-1.7")
        self.listing = VaultDirectory(self._vault.library)

    def test_the_pdf_listing_hides_the_numbered_copy(self) -> None:
        self.assertEqual([PDF_NAME], [path.name for path in self.listing.pdfs()])

    def test_the_conflict_copies_name_the_numbered_copy(self) -> None:
        self.assertEqual([self.NUMBERED_COPY], [path.name for path in self.listing.conflict_copies()])

    def test_a_missing_directory_lists_nothing(self) -> None:
        self.assertEqual([], VaultDirectory(self._vault.library / "absent").markdown())


class TestNumberedSiblingsThatAreDistinctWorks(unittest.TestCase):
    ORIGINAL = "Doe - 2020 - Analysis"
    NUMBERED = "Doe - 2020 - Analysis 2"

    def setUp(self) -> None:
        self._vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self._vault.discard)
        self.note(self.ORIGINAL, "doe2020analysis")

    def note(self, stem: str, citekey: str) -> None:
        (self._vault.corpus / f"{stem}.md").write_text(f"---\ncitekey: {citekey}\n---\n", encoding="utf-8")

    def pdf(self, stem: str) -> None:
        (self._vault.library / f"{stem}.pdf").write_bytes(b"%PDF-1.7")

    def note_names(self) -> list[str]:
        return sorted(path.stem for path in vault.list_markdown(self._vault.corpus))

    def pdf_names(self) -> list[str]:
        return sorted(path.stem for path in vault.list_pdfs(self._vault.library))

    def test_a_numbered_note_carrying_another_citekey_than_its_original_is_a_distinct_work(self) -> None:
        self.note(self.NUMBERED, "doe2020analysisb")
        self.assertEqual([self.ORIGINAL, self.NUMBERED], self.note_names())

    def test_a_numbered_note_carrying_the_citekey_of_its_original_is_a_conflict_copy(self) -> None:
        self.note(self.NUMBERED, "doe2020analysis")
        self.assertEqual([self.ORIGINAL], self.note_names())

    def test_a_numbered_pdf_with_a_distinct_note_of_its_own_stem_is_a_distinct_work(self) -> None:
        self.note(self.NUMBERED, "doe2020analysisb")
        self.pdf(self.ORIGINAL)
        self.pdf(self.NUMBERED)
        self.assertEqual([self.ORIGINAL, self.NUMBERED], self.pdf_names())

    def test_a_numbered_pdf_whose_only_note_is_a_conflict_copy_is_a_conflict_copy(self) -> None:
        self.note(self.NUMBERED, "doe2020analysis")
        self.pdf(self.ORIGINAL)
        self.pdf(self.NUMBERED)
        self.assertEqual([self.ORIGINAL], self.pdf_names())


class TestLibraryConflictCopiesCoverEveryHeldDirectory(unittest.TestCase):
    TRANSCRIPT_COPY = "Doe - 2021 - A Talk (Someone's conflicted copy 2026-01-01).md"

    def setUp(self) -> None:
        self._vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self._vault.discard)
        (vault.TRANSCRIPTS_DIR / self.TRANSCRIPT_COPY).write_text("---\ntitle: copy\n---\n", encoding="utf-8")

    def test_a_conflict_copy_of_a_transcript_is_named(self) -> None:
        self.assertEqual([self.TRANSCRIPT_COPY], vault.library_conflict_copies())


class TestLibraryFilenameCutsOnlyAtASubtitleSeparator(unittest.TestCase):
    def test_a_main_title_holding_a_spaced_hyphen_is_kept_whole(self) -> None:
        built = vault.library_filename_verbatim(["Doe"], "2020", "Pre - and Post-War Logic")
        self.assertEqual("Doe - 2020 - Pre - and Post-War Logic.pdf", built)

    def test_a_title_is_cut_at_its_en_dash(self) -> None:
        built = vault.library_filename_verbatim(["Doe"], "2020", "Logic \u2013 A Study")
        self.assertEqual("Doe - 2020 - Logic.pdf", built)


class TestBasenamesAreComposed(unittest.TestCase):
    def test_the_basename_of_a_decomposed_filename_is_composed(self) -> None:
        self.assertEqual(COMPOSED_STEM, vault.basename_of(Path(f"{DECOMPOSED_STEM}.pdf")))

    def test_a_decomposed_argument_yields_the_composed_pdf_path(self) -> None:
        self.assertEqual(COMPOSED_STEM, vault.pdf_path(DECOMPOSED_STEM).stem)

    def test_a_decomposed_argument_yields_the_composed_corpus_path(self) -> None:
        self.assertEqual(COMPOSED_STEM, vault.corpus_path(DECOMPOSED_STEM).stem)

    def test_a_decomposed_argument_yields_the_composed_transcript_path(self) -> None:
        self.assertEqual(COMPOSED_STEM, vault.transcript_path(DECOMPOSED_STEM).stem)

    def test_decomposed_record_fields_yield_a_composed_library_filename(self) -> None:
        built = vault.library_filename_verbatim(["Fre\u0301"], "2018", "A Work")
        self.assertEqual(f"{COMPOSED_STEM}.pdf", built)


if __name__ == "__main__":
    unittest.main()
