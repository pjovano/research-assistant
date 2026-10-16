from __future__ import annotations

import unittest
from http import HTTPStatus
from pathlib import Path

from _support import FIXTURES_DIR, LiveTree

LiveTree.activate()

import identifiers
import titlecase
from zotero import ConnectorResult
from _file.bib import BibEditor, BibReport, MetadataMerge
from _file.filing import FilingCompletion, FilingOutcome, PlacedAttachment, Placement
from _file.finder import IdentifierFinder
from _file.identify import STATUS_LOOKUP_FAILED, STATUS_NO_IDENTIFIER, STATUS_RESOLVED, IdentifyReport
from _file.normalize_record import SHORT_TITLE_LIMIT, RecordNormalizer
from _file.notes import IDENTIFIED_KEY, CorpusNote, DraftCard
from _file.preview import FilingPreview
from _file.probe import JOURNAL_ARTICLE_PAGE_THRESHOLD, PdfProbe
from _file.resolvers import Fetched, LookupFailed
from _file_fixtures import ATTACHMENT_LINK, PDF_BYTES, VaultTestCase

IDENTIFY_FIXTURES = FIXTURES_DIR / "identify"
ARTICLE_DOI = "10.1007/s11229-020-02614-2"
CHAPTER_DOI = "10.1017/cbo9780511597206.003"
BOOK_DOI = "10.7208/chicago/structure.001.0001"
MIND_DOI = "10.1093/mind/fzab001"
KUHN_ISBN = "9780226458083"
KUHN_ISBN_10 = "0-226-45808-3"
KUHN_ISBN_HYPHENATED = "978-0-226-45808-3"
OTHER_ISBN = "9780674576001"
KUHN_FULL_TITLE = "The Structure of Scientific Revolutions: With an Introductory Essay by Ian Hacking"
KUHN_PDF_NAME = "Kuhn - 2012 - The Structure of Scientific Revolutions.pdf"
KUHN_CITEKEY = "kuhn2012"
ARXIV_ID = "hep-th/9901001"
WORDS_BEYOND_SHORT_TITLE = "A " * SHORT_TITLE_LIMIT
XMP_WITH_DOI = (
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/">'
    f"<prism:doi>{ARTICLE_DOI}</prism:doi></rdf:Description></rdf:RDF></x:xmpmeta>"
)
ROUTES = {
    f"api.crossref.org/works/{ARTICLE_DOI}": "crossref_article.json",
    f"api.crossref.org/works/{CHAPTER_DOI}": "crossref_chapter.json",
    f"api.crossref.org/works/{BOOK_DOI}": "crossref_caps_subtitle.json",
    f"googleapis.com/books/v1/volumes?q=isbn:{KUHN_ISBN}": "google_books.json",
    f"openlibrary.org/isbn/{KUHN_ISBN}.json": "openlibrary_edition.json",
    "openlibrary.org/authors/OL531166A.json": "openlibrary_author.json",
    f"export.arxiv.org/api/query?id_list={ARXIV_ID}": "arxiv.xml",
}


class RecordedFetcher:
    def __init__(self, routes: dict = ROUTES, blocked: tuple = ()) -> None:
        self._routes = routes
        self._blocked = blocked
        self.urls: list[str] = []

    def fetch(self, url: str) -> Fetched:
        self.urls.append(url)
        if any(fragment in url for fragment in self._blocked):
            return Fetched(HTTPStatus.TOO_MANY_REQUESTS, "")
        for fragment, fixture in self._routes.items():
            if fragment in url:
                return Fetched(HTTPStatus.OK, (IDENTIFY_FIXTURES / fixture).read_text(encoding="utf-8"))
        return Fetched(HTTPStatus.NOT_FOUND, "")


class UnreachableFetcher:
    def fetch(self, url: str) -> Fetched:
        raise LookupFailed("network failure: ConnectionError")


class TestPdfProbe(VaultTestCase):
    def _type_of_pages(self, count: int) -> str:
        pdf = self.pdf().with_pages(*["A page of the work."] * count).write()
        return PdfProbe().of(pdf)["type"]

    def test_a_pdf_under_the_threshold_is_a_journal_article(self) -> None:
        self.assertEqual("journalArticle", self._type_of_pages(JOURNAL_ARTICLE_PAGE_THRESHOLD - 1))

    def test_a_pdf_at_the_threshold_is_a_book(self) -> None:
        self.assertEqual("book", self._type_of_pages(JOURNAL_ARTICLE_PAGE_THRESHOLD))


class TestIdentifierPatterns(unittest.TestCase):
    def test_a_doi_loses_its_trailing_punctuation(self) -> None:
        self.assertEqual([MIND_DOI], identifiers.find_dois(f"see {MIND_DOI}."))

    def test_a_doi_in_parentheses_loses_the_closing_bracket(self) -> None:
        self.assertEqual([MIND_DOI], identifiers.find_dois(f"(doi: {MIND_DOI})"))

    def test_a_doi_url_is_reduced_to_the_doi(self) -> None:
        self.assertEqual(MIND_DOI, identifiers.clean_doi("https://doi.org/10.1093/MIND/FZAB001"))

    def test_an_isbn_10_with_a_valid_checksum_becomes_isbn_13(self) -> None:
        self.assertEqual(KUHN_ISBN, identifiers.canonical_isbn(KUHN_ISBN_10))

    def test_an_isbn_10_with_a_bad_checksum_is_rejected(self) -> None:
        self.assertIsNone(identifiers.canonical_isbn("0-226-45808-4"))

    def test_an_isbn_13_with_a_valid_checksum_loses_its_hyphens(self) -> None:
        self.assertEqual(KUHN_ISBN, identifiers.canonical_isbn(KUHN_ISBN_HYPHENATED))

    def test_an_isbn_13_with_a_bad_checksum_is_rejected(self) -> None:
        self.assertIsNone(identifiers.canonical_isbn("978-0-226-45808-2"))

    def test_isbns_are_found_labelled_or_bare(self) -> None:
        text = f"ISBN {KUHN_ISBN_10} (pbk.) and {OTHER_ISBN}"
        self.assertEqual([KUHN_ISBN, OTHER_ISBN], identifiers.find_isbns(text))

    def test_a_bare_ten_digit_run_is_not_read_as_an_isbn(self) -> None:
        self.assertEqual([], identifiers.find_isbns("Vol.:(0123456789)"))

    def test_a_labelled_ten_digit_isbn_beside_such_a_run_is_still_found(self) -> None:
        text = f"Vol.:(0123456789)\nISBN {KUHN_ISBN_10}"
        self.assertEqual([KUHN_ISBN], identifiers.find_isbns(text))

    def test_both_arxiv_forms_are_found(self) -> None:
        text = f"arXiv:{ARXIV_ID} and arXiv:2401.12345v2 near 3.14159"
        self.assertEqual([ARXIV_ID, "2401.12345v2"], identifiers.find_arxiv_ids(text))


class TestIdentifierFinder(VaultTestCase):
    def test_a_doi_in_xmp_is_found_with_its_source(self) -> None:
        found = IdentifierFinder(self.pdf().with_xmp(XMP_WITH_DOI).write()).found()
        self.assertEqual([{"kind": "doi", "value": ARTICLE_DOI, "source": "xmp"}], found.as_dicts())

    def test_a_doi_in_page_text_loses_its_trailing_period(self) -> None:
        found = IdentifierFinder(self.pdf().with_pages(f"DOI: {ARTICLE_DOI}.").write()).found()
        self.assertEqual([ARTICLE_DOI], found.of_kind(identifiers.KIND_DOI))

    def test_dois_changing_across_pages_are_chapter_evidence(self) -> None:
        pages = ("10.1017/cbo9780511597206.002", CHAPTER_DOI, "10.1017/cbo9780511597206.004")
        found = IdentifierFinder(self.pdf().with_pages(*pages).write()).found()
        self.assertEqual(sorted(pages), found.chapter_doi_evidence())

    def test_one_doi_repeated_on_every_page_is_not_chapter_evidence(self) -> None:
        found = IdentifierFinder(self.pdf().with_pages(ARTICLE_DOI, ARTICLE_DOI, ARTICLE_DOI).write()).found()
        self.assertEqual([], found.chapter_doi_evidence())

    def test_an_isbn_in_the_filename_is_found(self) -> None:
        found = IdentifierFinder(self.pdf(f"{KUHN_ISBN}.pdf").write()).found()
        self.assertEqual([{"kind": "isbn", "value": KUHN_ISBN, "source": "filename"}], found.as_dicts())

    def test_an_arxiv_id_in_the_text_is_found(self) -> None:
        found = IdentifierFinder(self.pdf().with_pages(f"arXiv:{ARXIV_ID}v3 [hep-th]").write()).found()
        self.assertEqual([f"{ARXIV_ID}v3"], found.of_kind(identifiers.KIND_ARXIV))


class TestTitleCase(unittest.TestCase):
    def test_an_english_title_in_all_caps_is_title_cased(self) -> None:
        self.assertEqual("The Structure of Scientific Revolutions",
                         titlecase.title_case("THE STRUCTURE OF SCIENTIFIC REVOLUTIONS").text)

    def test_a_german_title_keeps_its_lowercase_articles_and_capitalized_nouns(self) -> None:
        self.assertEqual("Die Kritik der reinen Vernunft",
                         titlecase.title_case("Die Kritik der reinen Vernunft").text)

    def test_an_acronym_is_kept(self) -> None:
        self.assertEqual("Modelling DNA Repair in the Cell",
                         titlecase.title_case("Modelling DNA repair in the cell").text)

    def test_a_roman_numeral_stays_upper(self) -> None:
        self.assertEqual("Book II of the Republic", titlecase.title_case("BOOK II OF THE REPUBLIC").text)

    def test_a_year_word_is_not_capitalized(self) -> None:
        self.assertEqual("The Recovery of the 1930s", titlecase.title_case("THE RECOVERY OF THE 1930S").text)

    def test_the_word_after_a_colon_is_capitalized(self) -> None:
        self.assertEqual("Hume: A Study", titlecase.title_case("hume: a study").text)


class TestRecordNormalizer(unittest.TestCase):
    def _proposal(self, pdf_isbns: list[str] = (), **overrides):
        base = {"type": "article-journal", "title": "A Work", "author": [{"given": "Jane", "family": "Doe"}],
                "issued": {"date-parts": [[2020]]}, "container-title": "Mind"}
        return RecordNormalizer({**base, **overrides}, list(pdf_isbns)).proposal()

    def test_an_all_caps_title_is_title_cased(self) -> None:
        self.assertEqual("The Web of Belief", self._proposal(title="THE WEB OF BELIEF").fields["title"])

    def test_a_subtitle_list_is_joined_by_a_colon(self) -> None:
        proposal = self._proposal(title="A Work", subtitle=["An Essay"])
        self.assertEqual("A Work: An Essay", proposal.fields["title"])

    def test_a_spaced_em_dash_subtitle_becomes_a_colon(self) -> None:
        proposal = self._proposal(title="A Work — An Essay")
        self.assertEqual("A Work: An Essay", proposal.fields["title"])

    def test_a_spaced_em_dash_subtitle_is_flagged(self) -> None:
        proposal = self._proposal(title="A Work — An Essay")
        self.assertTrue(any("spaced dash" in flag for flag in proposal.flags))

    def test_an_unspaced_dash_in_a_year_range_is_kept(self) -> None:
        proposal = self._proposal(title="Philosophy in Germany 1831–1933")
        self.assertEqual("Philosophy in Germany 1831–1933", proposal.fields["title"])

    def test_an_unspaced_dash_in_a_year_range_is_not_a_normalization(self) -> None:
        proposal = self._proposal(title="Philosophy in Germany 1831–1933")
        self.assertEqual([], proposal.normalizations)

    def test_html_tags_are_stripped_from_the_title(self) -> None:
        self.assertEqual("On Being & Time", self._proposal(title="On <i>Being</i> &amp; Time").fields["title"])

    def test_a_trailing_period_is_stripped(self) -> None:
        self.assertEqual("A Work", self._proposal(title="A Work.").fields["title"])

    def test_a_long_main_title_flags_short_title(self) -> None:
        proposal = self._proposal(title=WORDS_BEYOND_SHORT_TITLE)
        self.assertTrue(any("shortTitle" in flag for flag in proposal.flags))

    def test_a_compound_surname_survives(self) -> None:
        creators = self._proposal(author=[{"given": "Bas C.", "family": "van Fraassen"}]).fields["creators"]
        self.assertEqual("van Fraassen", creators[0]["lastName"])

    def test_a_generational_suffix_moves_to_the_first_name(self) -> None:
        author = {"given": "Fred D.", "family": "Miller", "suffix": "Jr."}
        creators = self._proposal(author=[author]).fields["creators"]
        self.assertEqual({"creatorType": "author", "firstName": "Fred D., Jr.", "lastName": "Miller"}, creators[0])

    def test_shouted_names_are_de_shouted(self) -> None:
        creators = self._proposal(author=[{"given": "THOMAS S.", "family": "KUHN"}]).fields["creators"]
        self.assertEqual(("Thomas S.", "Kuhn"), (creators[0]["firstName"], creators[0]["lastName"]))

    def test_a_lowercase_surname_is_not_corrected(self) -> None:
        proposal = self._proposal(author=[{"given": "bell", "family": "hooks"}])
        self.assertEqual("hooks", proposal.fields["creators"][0]["lastName"])

    def test_a_lowercase_surname_is_flagged(self) -> None:
        proposal = self._proposal(author=[{"given": "bell", "family": "hooks"}])
        self.assertTrue(any("all-lowercase" in flag for flag in proposal.flags))

    def test_an_organization_is_a_single_field_creator(self) -> None:
        creators = self._proposal(author=[{"literal": "Royal Society"}]).fields["creators"]
        self.assertEqual({"creatorType": "author", "name": "Royal Society"}, creators[0])

    def test_a_container_author_becomes_a_book_author(self) -> None:
        proposal = self._proposal(type="chapter", **{"container-author": [{"given": "Jane", "family": "Doe"}]})
        self.assertIn("bookAuthor", [creator["creatorType"] for creator in proposal.fields["creators"]])

    def test_a_roman_volume_is_written_arabic(self) -> None:
        self.assertEqual("14", self._proposal(volume="XIV").fields["volume"])

    def test_an_article_number_stands_in_for_pages(self) -> None:
        proposal = self._proposal(**{"article-number": "e12345"})
        self.assertEqual("e12345", proposal.fields["pages"])

    def test_an_article_number_standing_in_for_pages_is_flagged(self) -> None:
        proposal = self._proposal(**{"article-number": "e12345"})
        self.assertTrue(any("article-number" in flag for flag in proposal.flags))

    def test_a_print_issn_is_preferred(self) -> None:
        proposal = self._proposal(**{"issn-by-type": {"electronic": "1573-0964", "print": "0039-7857"}})
        self.assertEqual("0039-7857", proposal.fields["ISSN"])

    def test_a_doi_url_prefix_is_stripped_and_lowercased(self) -> None:
        proposal = self._proposal(DOI="https://doi.org/10.1093/MIND/fzab001")
        self.assertEqual(MIND_DOI, proposal.fields["DOI"])

    def test_the_one_isbn_the_pdf_carried_is_written_without_hyphens(self) -> None:
        proposal = self._proposal(pdf_isbns=[KUHN_ISBN_HYPHENATED], type="book")
        self.assertEqual(KUHN_ISBN, proposal.fields["ISBN"])

    def test_several_isbns_leave_the_field_unset(self) -> None:
        proposal = self._proposal(pdf_isbns=[KUHN_ISBN, OTHER_ISBN], type="book")
        self.assertNotIn("ISBN", proposal.fields)

    def test_several_isbns_are_flagged_for_the_worker(self) -> None:
        proposal = self._proposal(pdf_isbns=[KUHN_ISBN, OTHER_ISBN], type="book")
        self.assertTrue(any("ISBN" in flag for flag in proposal.flags))

    def test_harvard_up_takes_cambridge_massachusetts(self) -> None:
        proposal = self._proposal(type="book", publisher="Harvard University Press",
                                  **{"publisher-place": "Cambridge, MA"})
        self.assertEqual("Cambridge, Massachusetts", proposal.fields["place"])

    def test_a_print_date_is_preferred_for_an_article(self) -> None:
        proposal = self._proposal(**{"published-print": {"date-parts": [[2021, 9]]},
                                     "issued": {"date-parts": [[2020]]}})
        self.assertEqual("2021", proposal.fields["date"])

    def test_an_original_date_sets_orig_year(self) -> None:
        self.assertEqual("1662", self._proposal(**{"original-date": {"date-parts": [[1662]]}}).orig_year)

    def test_a_preprint_carries_only_its_repository_fields(self) -> None:
        proposal = self._proposal(type="posted-content", archive="arXiv", archive_location=ARXIV_ID,
                                  URL=f"http://arxiv.org/abs/{ARXIV_ID}v3", publisher="arXiv")
        self.assertEqual({"itemType", "title", "creators", "date", "repository", "archiveID", "url"},
                         set(proposal.fields))

    def test_a_record_short_of_a_publisher_leaves_it_blank(self) -> None:
        proposal = self._proposal(type="book", publisher="")
        self.assertNotIn("publisher", proposal.fields)


class TestIdentifyReport(VaultTestCase):
    def _report(self, pdf: Path, fetcher=None) -> dict:
        return IdentifyReport(pdf, fetcher or RecordedFetcher()).render()

    def _article_report(self) -> dict:
        return self._report(self.pdf().with_xmp(XMP_WITH_DOI).write())

    def _chapter_report(self) -> dict:
        return self._report(self.pdf().with_pages(f"DOI {CHAPTER_DOI}").write())

    def _isbn_report(self, fetcher=None) -> dict:
        return self._report(self.pdf().with_pages(f"ISBN {KUHN_ISBN_HYPHENATED}").write(), fetcher)

    def _arxiv_report(self) -> dict:
        return self._report(self.pdf().with_pages(f"arXiv:{ARXIV_ID}").write())

    def test_a_crossref_article_resolves(self) -> None:
        self.assertEqual(STATUS_RESOLVED, self._article_report()["lookup"]["status"])

    def test_a_crossref_article_proposes_its_title(self) -> None:
        self.assertEqual("Against Natural Kind Eliminativism", self._article_report()["proposal"]["title"])

    def test_a_crossref_article_proposes_its_journal(self) -> None:
        self.assertEqual("Synthese", self._article_report()["proposal"]["publicationTitle"])

    def test_a_crossref_article_lacks_no_required_field(self) -> None:
        self.assertEqual([], self._article_report()["missing_for_type"])

    def test_the_article_year_comes_from_the_print_date(self) -> None:
        self.assertEqual("2021", self._article_report()["proposal"]["date"])

    def test_a_crossref_chapter_is_a_book_section(self) -> None:
        self.assertEqual("bookSection", self._chapter_report()["proposal"]["itemType"])

    def test_a_crossref_chapter_names_its_book_author(self) -> None:
        creators = self._chapter_report()["proposal"]["creators"]
        self.assertIn("bookAuthor", [creator["creatorType"] for creator in creators])

    def test_a_crossref_chapter_lacks_no_required_field(self) -> None:
        self.assertEqual([], self._chapter_report()["missing_for_type"])

    def test_an_all_caps_crossref_title_with_a_subtitle_list_is_normalized(self) -> None:
        report = self._report(self.pdf().with_pages(f"doi:{BOOK_DOI}").write())
        self.assertEqual(KUHN_FULL_TITLE, report["proposal"]["title"])

    def test_an_isbn_resolves_through_google_books(self) -> None:
        self.assertEqual("google books", self._isbn_report()["lookup"]["service"])

    def test_a_google_books_isbn_proposes_the_publisher(self) -> None:
        self.assertEqual("University of Chicago Press", self._isbn_report()["proposal"]["publisher"])

    def test_a_google_books_isbn_proposes_the_isbn_the_pdf_carried(self) -> None:
        self.assertEqual(KUHN_ISBN, self._isbn_report()["proposal"]["ISBN"])

    def test_open_library_answers_when_google_books_fails(self) -> None:
        report = self._isbn_report(RecordedFetcher(blocked=("googleapis.com",)))
        self.assertEqual("open library", report["lookup"]["service"])

    def test_an_open_library_edition_names_its_author(self) -> None:
        report = self._isbn_report(RecordedFetcher(blocked=("googleapis.com",)))
        self.assertEqual("Kuhn", report["proposal"]["creators"][0]["lastName"])

    def test_an_arxiv_id_resolves_to_a_preprint(self) -> None:
        self.assertEqual("preprint", self._arxiv_report()["proposal"]["itemType"])

    def test_an_arxiv_preprint_carries_its_archive_id(self) -> None:
        self.assertEqual(ARXIV_ID, self._arxiv_report()["proposal"]["archiveID"])

    def test_an_arxiv_preprint_carries_its_published_doi(self) -> None:
        self.assertEqual("10.1143/ptp.101.1155", self._arxiv_report()["proposal"]["DOI"])

    def test_a_pdf_without_identifiers_reports_none(self) -> None:
        self.assertEqual(STATUS_NO_IDENTIFIER, self._report(self.pdf().write())["lookup"]["status"])

    def test_a_network_failure_is_a_status(self) -> None:
        report = self._report(self.pdf().with_xmp(XMP_WITH_DOI).write(), UnreachableFetcher())
        self.assertEqual(STATUS_LOOKUP_FAILED, report["lookup"]["status"])

    def test_a_network_failure_still_lists_the_identifier(self) -> None:
        report = self._report(self.pdf().with_xmp(XMP_WITH_DOI).write(), UnreachableFetcher())
        self.assertEqual([ARTICLE_DOI], [item["value"] for item in report["identifiers"]])

    def test_the_read_only_form_writes_nothing(self) -> None:
        pdf = self.pdf().with_xmp(XMP_WITH_DOI).write()
        before = sorted(path.name for path in self.vault.inbox.iterdir())
        self._report(pdf)
        self.assertEqual(before, sorted(path.name for path in self.vault.inbox.iterdir()))


class TestIdentifyWrite(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = self.pdf().with_pages(f"doi:{BOOK_DOI}", "ISBN 978-0-226-45812-0").write()

    def _write(self) -> dict:
        return IdentifyReport(self.pdf_path, RecordedFetcher()).write()

    def test_the_draft_card_reads_the_title_back(self) -> None:
        self._write()
        self.assertEqual(KUHN_FULL_TITLE, BibReport(self.pdf_path).render()["zotero"]["title"])

    def test_the_draft_card_reads_the_isbn_back(self) -> None:
        self._write()
        self.assertEqual("9780226458120", BibReport(self.pdf_path).render()["zotero"]["ISBN"])

    def test_the_name_preview_drops_the_subtitle(self) -> None:
        self._write()
        self.assertEqual(KUHN_PDF_NAME, FilingPreview.of(self.pdf_path).library_filename())

    def test_the_identified_key_carries_the_provenance(self) -> None:
        self._write()
        identified = DraftCard(self.pdf_path.name).load().identified
        self.assertEqual(("crossref", BOOK_DOI), (identified["service"], identified["identifier"]["value"]))

    def test_a_later_bib_set_keeps_the_identified_key(self) -> None:
        self._write()
        BibEditor(self.pdf_path).apply(["numPages=264"])
        self.assertIsNotNone(DraftCard(self.pdf_path.name).load().identified)

    def test_a_differing_recorded_field_is_a_conflict(self) -> None:
        BibEditor(self.pdf_path).apply(["title=A Hand-Set Title"])
        report = self._write()
        self.assertEqual(["title"], [conflict["field"] for conflict in report["conflicts"]])

    def test_a_differing_recorded_field_is_not_overwritten(self) -> None:
        BibEditor(self.pdf_path).apply(["title=A Hand-Set Title"])
        self._write()
        self.assertEqual("A Hand-Set Title", BibReport(self.pdf_path).render()["zotero"]["title"])

    def test_a_filed_draft_card_refuses_the_write(self) -> None:
        self.draft_card("---\nfiled: true\nzotero: {}\n---\n")
        with self.assertRaises(SystemExit):
            self._write()

    def test_the_corpus_file_carries_no_identified_key(self) -> None:
        self._write()
        placed = self.vault.library / KUHN_PDF_NAME
        placed.write_bytes(PDF_BYTES)
        FilingCompletion().complete(self._filing_outcome(placed))
        self.assertNotIn(IDENTIFIED_KEY, CorpusNote(placed.name).fields())

    def _filing_outcome(self, placed: Path) -> FilingOutcome:
        meta = PdfProbe().of(self.pdf_path)
        MetadataMerge().into(meta, DraftCard(self.pdf_path.name).load())
        return FilingOutcome(self.pdf_path, meta, KUHN_CITEKEY, ConnectorResult.saved(),
                             Placement(PlacedAttachment(placed, ATTACHMENT_LINK)))


if __name__ == "__main__":
    unittest.main()
