from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from zotero import ConnectorResult
from _file.filing import FilingCompletion, FilingOutcome, PlacedAttachment, Placement
from _file.notes import UNCITABLE_TOKEN, CorpusNote
from _file_fixtures import (
    ATTACHMENT_LINK,
    CITEKEY,
    PDF_BYTES,
    PLACED_NOTE_NAME,
    PLACED_PDF_NAME,
    Citation,
    VaultTestCase,
)

CORPUS_ALIAS = "Wissenschaft der Logik"
STALE_ALIAS = "A Stale Alias"


class StaleDraftTestCase(VaultTestCase):
    def refiled_aliases(self, corpus_aliases: str, draft_aliases: list[str]) -> list[str]:
        return self.refiled_fields(corpus_aliases, {"aliases": draft_aliases})["aliases"]

    def refiled_fields(self, corpus_fields: str, draft_meta: dict) -> dict:
        holding_dir = self.vault.named("holding")
        holding_dir.mkdir()
        holding = holding_dir / PLACED_PDF_NAME
        holding.write_bytes(PDF_BYTES)
        placed_pdf = self.vault.library / PLACED_PDF_NAME
        placed_pdf.write_bytes(PDF_BYTES)
        (self.vault.corpus / PLACED_NOTE_NAME).write_text(f"---\ntitle: A Work\n{corpus_fields}---\n\nbody\n",
                                                          encoding="utf-8")
        meta = {**Citation().meta(), **draft_meta}
        placement = Placement(PlacedAttachment(placed_pdf, ATTACHMENT_LINK))
        FilingCompletion().complete(FilingOutcome(holding, meta, CITEKEY, ConnectorResult.saved(), placement))
        return CorpusNote(PLACED_PDF_NAME).fields()


class TestARefileWhoseStaleDraftCardRecordsNoAliases(StaleDraftTestCase):
    def test_the_corpus_files_aliases_are_kept(self) -> None:
        self.assertEqual([CORPUS_ALIAS], self.refiled_aliases(f"aliases:\n- {CORPUS_ALIAS}\n", []))


class TestARefileWhoseStaleDraftCardRecordsOtherAliases(StaleDraftTestCase):
    def test_the_corpus_files_aliases_are_kept(self) -> None:
        self.assertEqual([CORPUS_ALIAS], self.refiled_aliases(f"aliases:\n- {CORPUS_ALIAS}\n", [STALE_ALIAS]))


class TestARefileOfACorpusFileWithoutAliases(StaleDraftTestCase):
    def test_the_draft_cards_aliases_are_written(self) -> None:
        self.assertEqual([STALE_ALIAS], self.refiled_aliases("aliases: []\n", [STALE_ALIAS]))


class TestARefileOfACorpusFileWhoseUncitableReasonWasWrittenByHand(StaleDraftTestCase):
    def test_the_hand_written_reason_is_kept(self) -> None:
        record = {"bib": {"extra": f"{UNCITABLE_TOKEN}\nThe record's reason."}}
        fields = self.refiled_fields("uncitable: The reason written by hand.\n", record)
        self.assertEqual("The reason written by hand.", fields["uncitable"])


if __name__ == "__main__":
    unittest.main()
