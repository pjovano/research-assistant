from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from _correction_fixtures import BODY, FAMILY

from _extract.cli import main
from _extract.console import EXIT_OK, EXIT_USAGE
from _extract.correctionstore import TrialCorrections
from _extract.paths import CorpusFile
from _extract.records import CORRECTIONS_KEY, REVIEWED_KEY, ExtractionRecord, ExtractionRecords
from _extract.request import ExtractionRequest
from _extract.cleanuppages import FLAG_BROKEN_PARAGRAPH
from _extract.trial import TrialNote
from _vaults import LinedPdf, TempVault

BASENAME = "Doe - 2020 - A Work"
FRONTMATTER = "---\ntitle: A Work\ntype: book\n---\n"
LINK_LINE = f"[{BASENAME}.pdf](zotero://open-pdf/x)"
OUTLINE = [[1, "Introduction", 1]]
REVIEWED = "2026-10-01"
CITATION_LINK = " [[Smith - 1990 - A Book|↗]]"
SPLIT = {**FAMILY, "op": "split", "page": 1, "anchor": "The second claim follows in the same paragraph"}
SPLIT_TEXT = "in full.\n\nThe second claim follows"
PAGE_LINES = ["A line the page prints, with words enough to count as text."] * 3


class CapturedRun:
    def __init__(self, *argv: str) -> None:
        self._argv = list(argv)

    def go(self) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = main(self._argv)
        return code, output.getvalue()


class CorrectionVaultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = LinedPdf(self.vault.library / f"{BASENAME}.pdf", [PAGE_LINES] * 3, OUTLINE).write()
        (self.vault.corpus / f"{BASENAME}.md").write_text(f"{FRONTMATTER}\n{LINK_LINE}\n", encoding="utf-8")
        self.note = CorpusFile(self.pdf)
        self.corrections = self.vault.named("corrections.json")
        self.corrections.write_text(json.dumps([SPLIT]), encoding="utf-8")

    def written_trial(self) -> TrialNote:
        trial = TrialNote(self.note)
        trial.write(BODY, ExtractionRequest(()).record_fields())
        trial.write_report({})
        return trial

    def reviewed_body(self, body: str, corrections: tuple = ()) -> None:
        self.note.write(body, {})
        record = ExtractionRecord(ExtractionRequest(()), reviewed=REVIEWED, corrections=corrections)
        ExtractionRecords().write(BASENAME, record)

    def correct(self, *flags: str) -> tuple[int, str]:
        return CapturedRun("correct", f"{BASENAME}.pdf", "--corrections", str(self.corrections), *flags).go()


class TestCorrectingATrial(CorrectionVaultTestCase):
    def test_the_read_only_form_prints_each_outcome_and_writes_nothing(self) -> None:
        trial = self.written_trial()
        code, output = self.correct()
        self.assertEqual((EXIT_OK, "applied"), (code, json.loads(output)["outcomes"][0]["outcome"]))
        self.assertEqual(BODY.strip(), trial.body().strip())

    def test_the_writing_form_corrects_the_trial_and_keeps_the_applied_corrections(self) -> None:
        trial = self.written_trial()
        self.correct("--apply")
        self.assertIn(SPLIT_TEXT, trial.body())
        self.assertEqual([SPLIT], TrialCorrections(self.note).load())

    def test_the_corrected_trial_keeps_its_extraction_record(self) -> None:
        trial = self.written_trial()
        before = trial.frontmatter()
        self.correct("--apply")
        self.assertEqual(before, trial.frontmatter())

    def test_accept_carries_the_corrections_into_the_extraction_record(self) -> None:
        self.written_trial()
        self.correct("--apply")
        CapturedRun("accept", f"{BASENAME}.pdf").go()
        self.assertEqual([SPLIT], ExtractionRecords().entry(BASENAME)[CORRECTIONS_KEY])

    def test_a_malformed_corrections_file_is_refused(self) -> None:
        self.written_trial()
        self.corrections.write_text("not json", encoding="utf-8")
        self.assertEqual(EXIT_USAGE, self.correct()[0])


class TestCorrectingAReviewedBody(CorrectionVaultTestCase):
    def test_a_work_not_reviewed_is_refused(self) -> None:
        self.note.write(BODY, {})
        self.assertEqual(EXIT_USAGE, self.correct("--body")[0])

    def test_writing_a_reviewed_body_needs_replace(self) -> None:
        self.reviewed_body(BODY)
        self.assertEqual(EXIT_USAGE, self.correct("--body", "--apply")[0])
        self.assertNotIn(SPLIT_TEXT, self.note.body())

    def test_the_corrected_body_keeps_its_citation_links_and_its_review(self) -> None:
        linked = BODY.replace("Topic, Oxford: Press.", "Topic, Oxford: Press." + CITATION_LINK)
        self.reviewed_body(linked)
        self.correct("--body", "--apply", "--replace")
        entry = ExtractionRecords().entry(BASENAME)
        self.assertIn(SPLIT_TEXT, self.note.body())
        self.assertIn(CITATION_LINK, self.note.body())
        self.assertEqual((REVIEWED, [SPLIT]), (entry[REVIEWED_KEY], entry[CORRECTIONS_KEY]))


class TestCorrectionListing(CorrectionVaultTestCase):
    def test_only_the_pages_a_script_doubts_are_listed(self) -> None:
        self.written_trial()
        listing = json.loads(CapturedRun("correction-listing", f"{BASENAME}.pdf").go()[1])
        self.assertEqual([2, 3], [page["file_page"] for page in listing["pages"]])

    def test_a_listed_page_names_why_it_is_doubted(self) -> None:
        self.written_trial()
        listing = json.loads(CapturedRun("correction-listing", f"{BASENAME}.pdf").go()[1])
        self.assertIn(FLAG_BROKEN_PARAGRAPH, listing["pages"][0]["flags"])

    def test_the_text_layer_lines_are_numbered_by_page(self) -> None:
        self.written_trial()
        listing = json.loads(CapturedRun("correction-listing", f"{BASENAME}.pdf").go()[1])
        lines = Path(listing["layer_lines"]).read_text(encoding="utf-8").splitlines()
        self.assertEqual(f"p2.1: {PAGE_LINES[0]}", lines[0])

if __name__ == "__main__":
    unittest.main()
