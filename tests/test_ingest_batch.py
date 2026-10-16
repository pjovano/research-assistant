from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _ingest.batch import BatchListing
from _vaults import TempVault, TextPdf

FRESH_PDF = "fresh.pdf"
ROUTED_PDF = "routed.pdf"
UNEXTRACTED = "Doe - 2020 - A Work"
UNCLASSIFIED = "Roe - 2019 - Another Work"
PLACED = "Poe - 2018 - A Third Work"
PLACED_BEFORE_STAGE_FOUR = "Stern - 2009 - Hegelian Metaphysics"
PDF_LINK = "[x.pdf](zotero://open-pdf/library/items/ABCD)\n\n"


class TestBatchListing(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("INBOX_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.works_dir = vault.SCRATCH_DIR / "ingest"
        for pdf in (FRESH_PDF, ROUTED_PDF):
            TextPdf(self.vault.inbox / pdf).write()
        self.work_state(ROUTED_PDF.removesuffix(".pdf"), {"routed": "book"})
        self.filed(UNEXTRACTED, {"source_type": ""}, PDF_LINK)
        self.filed(UNCLASSIFIED, {"source_type": ""}, PDF_LINK + "# One\n\nText.\n")
        self.filed(PLACED, {"source_type": "monograph", "field": ["[[Logic]]"]}, PDF_LINK + "# One\n\nText.\n")
        self.filed(PLACED_BEFORE_STAGE_FOUR, {"source_type": None, "source_role": None, "field": ["[[Logic]]"]},
                   PDF_LINK + "# One\n\nText.\n")
        self.works = BatchListing(vault.INBOX_DIR, self.works_dir).works()

    def work_state(self, name: str, state: dict) -> None:
        (self.works_dir / name).mkdir(parents=True, exist_ok=True)
        (self.works_dir / name / "state.json").write_text(json.dumps(state), encoding="utf-8")

    def filed(self, basename: str, meta: dict, body: str) -> None:
        vault.write_frontmatter(vault.CORPUS_DIR / f"{basename}.md", meta, body)
        self.work_state(basename, {})

    def stage_of(self, key: str, name: str) -> str | None:
        return next((work["from"] for work in self.works if work.get(key) == name), None)

    def test_an_inbox_pdf_starts_at_the_clean(self) -> None:
        self.assertEqual("clean", self.stage_of("pdf", FRESH_PDF))

    def test_an_inbox_pdf_an_earlier_batch_routed_starts_at_the_filing(self) -> None:
        self.assertEqual("file", self.stage_of("pdf", ROUTED_PDF))

    def test_a_filed_work_with_no_body_starts_at_the_extraction(self) -> None:
        self.assertEqual("extract", self.stage_of("basename", UNEXTRACTED))

    def test_a_filed_work_with_a_body_and_no_classification_starts_at_the_citation_links(self) -> None:
        self.assertEqual("cite", self.stage_of("basename", UNCLASSIFIED))

    def test_a_work_a_bibliography_placed_before_stage_four_starts_at_the_citation_links(self) -> None:
        self.assertEqual("cite", self.stage_of("basename", PLACED_BEFORE_STAGE_FOUR))

    def test_a_placed_work_is_not_listed(self) -> None:
        self.assertIsNone(self.stage_of("basename", PLACED))


class TestBatchListingFiledWorksWithNoWorkDirectory(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("INBOX_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        vault.write_frontmatter(vault.CORPUS_DIR / f"{UNEXTRACTED}.md", {"source_type": ""}, PDF_LINK)
        vault.write_frontmatter(vault.CORPUS_DIR / f"{UNCLASSIFIED}.md", {"source_type": ""}, PDF_LINK + "# One\n\nText.\n")
        self.works = BatchListing(vault.INBOX_DIR, vault.SCRATCH_DIR / "ingest").works()

    def test_a_work_with_a_body_and_no_classification_starts_at_the_citation_links(self) -> None:
        self.assertEqual([{"basename": UNCLASSIFIED, "from": "cite"}], self.works)

    def test_a_work_with_no_body_is_left_to_the_backfill(self) -> None:
        self.assertNotIn(UNEXTRACTED, [work["basename"] for work in self.works])


if __name__ == "__main__":
    unittest.main()
