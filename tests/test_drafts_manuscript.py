from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from docx import Document

from _writing.citations import Citation, CitationReport, DraftCitations, HeldCitekeys
from _writing.docx_style import STYLES
from _writing.manuscript import DOCX, PDF, CslStyle, ManuscriptExport, ManuscriptFormat
from _writing.word_count import DraftWordCount

DRAFT = ("Kant says so [@kant1998, p. 193; see also @friedman1992, ch. 2]. As @kant1998 [A51] has it, "
         "and @hegel2010 agrees.[^1] Write to someone@example.org.\n\n[^1]: Compare [@kant1998].\n")
RECORDS = [{"id": "kant1998", "type": "book", "title": "Critique of Pure Reason",
            "author": [{"family": "Kant", "given": "Immanuel"}], "issued": {"date-parts": [[1998]]}}]
SUBMISSION = STYLES["submission"]


class StubRecords:
    def of(self, keys: list[str]) -> list[dict]:
        return [record for record in RECORDS if record["id"] in keys]


class TestDraftCitations(unittest.TestCase):
    def cited(self) -> list[Citation]:
        return DraftCitations(DRAFT).cited()

    def test_each_citation_of_a_bracket_is_read_with_its_locator(self) -> None:
        self.assertEqual([("kant1998", "p. 193"), ("friedman1992", "ch. 2")],
                         [(each.key, each.locator) for each in self.cited()[:2]])

    def test_a_citation_in_the_text_takes_the_locator_bracketed_after_it(self) -> None:
        self.assertIn(Citation(1, "kant1998", "A51"), self.cited())

    def test_a_citation_in_the_text_without_a_bracket_has_no_locator(self) -> None:
        self.assertIn(Citation(1, "hegel2010", ""), self.cited())

    def test_a_citation_is_read_in_a_footnote_on_its_own_line(self) -> None:
        self.assertIn(Citation(3, "kant1998", ""), self.cited())

    def test_an_email_address_is_no_citation(self) -> None:
        self.assertNotIn("example.org", [each.key for each in self.cited()])

    def test_each_key_is_named_once_in_the_order_cited(self) -> None:
        self.assertEqual(["kant1998", "friedman1992", "hegel2010"], DraftCitations(DRAFT).keys())


class FilesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def file(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path


class TestCitationReport(FilesTestCase):
    def test_a_corpus_files_citekey_names_its_basename(self) -> None:
        held = self.file("Kant - 1998 - Critique of Pure Reason.md", "---\ncitekey: kant1998\n---\n\nbody\n")
        bare = self.file("A note without frontmatter.md", "body\n")
        self.assertEqual({"kant1998": "Kant - 1998 - Critique of Pure Reason"}, HeldCitekeys([held, bare]).by_key())

    def test_the_report_names_the_keys_held_and_not_held(self) -> None:
        report = CitationReport(self.file("Paper - v01.md", DRAFT), {"kant1998": "Kant - 1998 - Critique"}).as_json()
        self.assertEqual((["kant1998"], ["friedman1992", "hegel2010"], "Kant - 1998 - Critique"),
                         (report["held"], report["not_held"], report["citations"][0]["held_as"]))


class TestDraftWordCount(FilesTestCase):
    DRAFT = ("# Abstract\n\nThree word abstract.\n\n# Introduction\n\nFive words of body text.[^1] %% editor: a comment %%\n\n"
             "[^1]: Four words of note.\n    Two more.\n\n# References\n\nKant 1998. Critique.\n")

    def count(self) -> dict:
        return DraftWordCount(self.file("Paper - v01.md", self.DRAFT)).as_json()

    def test_an_editors_comment_is_not_counted(self) -> None:
        plain = self.DRAFT.replace(" %% editor: a comment %%", "")
        self.assertEqual(DraftWordCount(self.file("Plain - v01.md", plain)).as_json()["total"], self.count()["total"])

    def test_the_notes_are_counted_apart_with_their_continuation_lines(self) -> None:
        self.assertEqual(7, self.count()["notes"])

    def test_the_abstract_is_counted_under_its_heading(self) -> None:
        self.assertEqual(3, self.count()["abstract"])

    def test_the_reference_list_is_counted_apart_from_the_body(self) -> None:
        self.assertEqual(3, self.count()["reference_list"])

    def test_the_total_holds_the_body_the_notes_and_the_reference_list_and_no_editors_comment(self) -> None:
        counted = self.count()
        self.assertEqual(counted["total"], counted["body"] + counted["notes"] + counted["reference_list"])


class TestManuscriptExport(FilesTestCase):
    CITING = "Kant says so [@kant1998, p. 193].\n\n# References\n"

    def export(self, text: str, kind: str = DOCX) -> ManuscriptExport:
        return ManuscriptExport(self.file("Paper - v01.md", text), self.root / "out", ManuscriptFormat(kind, SUBMISSION))

    def test_a_draft_that_cites_is_exported_with_its_citation_resolved_and_its_bibliography(self) -> None:
        self.export(self.CITING).apply(StubRecords())
        text = "\n".join(paragraph.text for paragraph in Document(str(self.root / "out" / "Paper - v01.docx")).paragraphs)
        self.assertIn("(Kant 1998, 193)", text)
        self.assertIn("Critique of Pure Reason", text)

    def test_a_draft_that_cites_nothing_is_exported_without_asking_for_records(self) -> None:
        self.export("Plain prose.\n").apply(records=None)
        self.assertTrue((self.root / "out" / "Paper - v01.docx").is_file())

    def test_the_plan_names_the_citekeys_and_writes_nothing(self) -> None:
        plan = self.export(self.CITING).plan()
        self.assertEqual((["kant1998"], False), (plan["citekeys"], (self.root / "out").exists()))

    def test_an_existing_file_is_never_overwritten(self) -> None:
        self.export("Plain prose.\n").apply()
        with self.assertRaisesRegex(ValueError, "exists"):
            self.export("Plain prose.\n")

    @unittest.skipUnless(shutil.which("typst"), "typst is not installed on this machine")
    def test_a_draft_is_exported_as_a_pdf(self) -> None:
        self.export(self.CITING, PDF).apply(StubRecords())
        self.assertTrue((self.root / "out" / "Paper - v01.pdf").read_bytes().startswith(b"%PDF"))


class TestCslStyle(FilesTestCase):
    def test_no_named_style_adds_no_option(self) -> None:
        self.assertEqual([], CslStyle(None, self.root).options())

    def test_a_held_style_is_passed_by_its_path(self) -> None:
        style = self.file("chicago-note.csl", "<style/>")
        self.assertEqual(["--csl", str(style)], CslStyle("chicago-note", self.root).options())

    def test_a_style_the_directory_lacks_is_refused_with_the_styles_it_holds(self) -> None:
        self.file("apa.csl", "<style/>")
        with self.assertRaisesRegex(ValueError, "it holds \\['apa'\\]"):
            CslStyle("mla", self.root).options()


if __name__ == "__main__":
    unittest.main()
