from __future__ import annotations

import contextlib
import sqlite3
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import vault
import zotero
from zotero import ConnectorResult
from _file.citekeys import CitekeyAllocator
from _file.notes import (
    AMENDED_NAME_FIELD, AMENDED_NAME_LABEL, UNCITABLE_FIELD, UNCITABLE_TOKEN, CorpusNote, DraftCard, NoteFrontmatter,
)
from _file.filing import (
    STATUS_ALREADY_FILED,
    STATUS_NOTE_COLLISION,
    STATUS_CONNECTION_LOST,
    STATUS_CONNECTOR_REFUSED,
    STATUS_FILED_NO_ATTACHMENT,
    STATUS_FILED_UNVERIFIED,
    STATUS_ZOTERO_OFFLINE,
    FilingCompletion,
    FilingOutcome,
    PlacedAttachment,
    Placement,
    Settlement,
)
from _file.paths import NotePaths, PdfLocator
from _file.records import CslRecord, FiledRecordNote, ZoteroDatabase
from _file.status import DoctorReport, StatusReport
from _file_fixtures import (
    AMENDED_NAME_REASON,
    ATTACHMENT_LINK,
    CITEKEY,
    DRAFT_CARD_NAME,
    INBOX_PDF_NAME,
    OTHER_WORK_PDF_NAME,
    PDF_BYTES,
    PLACED_NOTE_NAME,
    PLACED_PDF_NAME,
    UNCITABLE_REASON,
    ZOTERO_ITEM_KEY,
    Citation,
    VaultTestCase,
    saved_without_attachment,
)
from _vaults import TextPdf

ORIGINAL_YEAR = 1961
ITEM_ID = 1
ATTACHMENT_ID = 2


class TestCslRecord(unittest.TestCase):
    def _record(self, **fields) -> CslRecord:
        base = {"type": "book", "title": "A Work", "author": [{"family": "Doe", "given": "Jane"}],
                "issued": {"date-parts": [["2020"]]}}
        return CslRecord({**base, **fields})

    def test_a_chapter_is_a_book_section(self) -> None:
        self.assertEqual("bookSection", self._record(type="chapter").item_type)

    def test_the_generic_article_type_a_preprint_exports_as_is_a_preprint(self) -> None:
        self.assertEqual("preprint", self._record(type="article").item_type)

    def test_the_speech_type_a_presentation_exports_as_is_a_presentation(self) -> None:
        self.assertEqual("presentation", self._record(type="speech").item_type)

    def test_an_unmapped_csl_type_has_no_item_type(self) -> None:
        self.assertIsNone(self._record(type="song").item_type)

    def test_a_non_dropping_particle_joins_the_surname(self) -> None:
        author = {"family": "Lambalgen", "given": "Michiel", "non-dropping-particle": "van"}
        self.assertEqual("van Lambalgen", self._record(author=[author]).meta()["authors"][0]["lastName"])

    def test_editors_stand_in_when_no_author_is_named(self) -> None:
        record = self._record(author=[], editor=[{"family": "Roe", "given": "Rex"}])
        self.assertEqual([{"firstName": "Rex", "lastName": "Roe"}], record.meta()["authors"])

    def test_the_original_date_becomes_orig_year(self) -> None:
        record = self._record(**{"original-date": {"date-parts": [["1662"]]}})
        self.assertEqual("1662", record.meta()["orig_year"])

    def test_the_note_is_read_as_the_record_extra(self) -> None:
        meta = self._record(note=f"{UNCITABLE_TOKEN}\n{UNCITABLE_REASON}").meta()
        self.assertEqual(UNCITABLE_REASON, NoteFrontmatter(meta, CITEKEY).fields()[UNCITABLE_FIELD])


class TestFiledRecordNote(VaultTestCase):
    def test_a_pdf_with_a_corpus_file_is_reported_already_filed(self) -> None:
        pdf = TextPdf(self.vault.library / PLACED_PDF_NAME).write()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "")
        self.assertEqual(STATUS_ALREADY_FILED, FiledRecordNote(pdf).preview()["status"])


class TestOriginalDateInExtra(unittest.TestCase):
    def _extra(self, extra: str | None) -> str:
        meta = {**Citation(extra).meta(), "orig_year": ORIGINAL_YEAR}
        return zotero.build_item(meta)["extra"]

    def test_the_uncitable_token_stays_on_the_first_line(self) -> None:
        self.assertTrue(self._extra(f"{UNCITABLE_TOKEN}\n{UNCITABLE_REASON}").startswith(UNCITABLE_TOKEN))

    def test_the_original_date_follows_the_recorded_extra(self) -> None:
        self.assertTrue(self._extra("Some note").endswith(f"Original date: {ORIGINAL_YEAR}"))

    def test_an_original_date_alone_is_the_whole_extra(self) -> None:
        self.assertEqual(f"Original date: {ORIGINAL_YEAR}", self._extra(None))


class TestAmendedNameFrontmatter(unittest.TestCase):
    def test_a_labelled_line_writes_its_reason(self) -> None:
        fields = Citation(f"{AMENDED_NAME_LABEL} {AMENDED_NAME_REASON}").fields()
        self.assertEqual(AMENDED_NAME_REASON, fields[AMENDED_NAME_FIELD])

    def test_a_labelled_line_is_read_after_the_uncitable_lines(self) -> None:
        extra = f"{UNCITABLE_TOKEN}\n{UNCITABLE_REASON}\n{AMENDED_NAME_LABEL} {AMENDED_NAME_REASON}"
        fields = Citation(extra).fields()
        self.assertEqual((UNCITABLE_REASON, AMENDED_NAME_REASON),
                         (fields[UNCITABLE_FIELD], fields[AMENDED_NAME_FIELD]))

    def test_a_label_with_no_reason_writes_no_key(self) -> None:
        self.assertNotIn(AMENDED_NAME_FIELD, Citation(AMENDED_NAME_LABEL).fields())

    def test_an_extra_without_the_label_writes_no_key(self) -> None:
        self.assertNotIn(AMENDED_NAME_FIELD, Citation("Original date: 1899").fields())


class TestUncitableFrontmatter(unittest.TestCase):
    def test_a_token_with_a_reason_line_writes_the_reason(self) -> None:
        fields = Citation(f"{UNCITABLE_TOKEN}\n{UNCITABLE_REASON}\n").fields()
        self.assertEqual(UNCITABLE_REASON, fields[UNCITABLE_FIELD])

    def test_a_token_on_its_own_writes_true(self) -> None:
        self.assertIs(True, Citation(UNCITABLE_TOKEN).fields()[UNCITABLE_FIELD])

    def test_a_token_followed_by_a_blank_line_writes_true(self) -> None:
        self.assertIs(True, Citation(f"{UNCITABLE_TOKEN}\n\n").fields()[UNCITABLE_FIELD])

    def test_a_token_after_leading_whitespace_is_still_read(self) -> None:
        fields = Citation(f"\n  {UNCITABLE_TOKEN}\n{UNCITABLE_REASON}").fields()
        self.assertEqual(UNCITABLE_REASON, fields[UNCITABLE_FIELD])

    def test_an_extra_that_does_not_open_with_the_token_writes_no_key(self) -> None:
        self.assertNotIn(UNCITABLE_FIELD, Citation("Original-date: 1899").fields())

    def test_an_absent_extra_writes_no_key(self) -> None:
        self.assertNotIn(UNCITABLE_FIELD, Citation().fields())


class TestWrittenNote(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        note = CorpusNote(PLACED_PDF_NAME)
        note.write(Citation(f"{UNCITABLE_TOKEN}\n{UNCITABLE_REASON}\n").fields(), ATTACHMENT_LINK, "")
        self.note_text = note.path.read_text(encoding="utf-8")

    def test_the_note_carries_no_uncitable_token(self) -> None:
        self.assertNotIn(UNCITABLE_TOKEN, self.note_text)

    def test_the_note_carries_the_reason_in_its_frontmatter(self) -> None:
        self.assertIn(f"{UNCITABLE_FIELD}: {UNCITABLE_REASON}", self.note_text)


class TestNotePaths(VaultTestCase):
    def test_the_draft_card_sits_in_the_inbox_beside_its_pdf(self) -> None:
        self.assertEqual(self.vault.inbox / DRAFT_CARD_NAME, NotePaths().draft(INBOX_PDF_NAME))

    def test_the_corpus_file_sits_in_the_corpus(self) -> None:
        self.assertEqual(self.vault.corpus / PLACED_NOTE_NAME,
                         NotePaths().note(PLACED_PDF_NAME))


class TestPdfLocator(VaultTestCase):
    def test_a_pdf_in_the_inbox_resolves_to_its_path(self) -> None:
        wanted = self.vault.inbox / INBOX_PDF_NAME
        wanted.write_bytes(PDF_BYTES)
        self.assertEqual(wanted, PdfLocator().in_inbox(INBOX_PDF_NAME))

    def test_a_pdf_absent_from_the_inbox_names_the_inbox(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            PdfLocator().in_inbox(INBOX_PDF_NAME)
        self.assertEqual(f"Not found in the inbox: {INBOX_PDF_NAME}", str(raised.exception))


class TestFilingCompletion(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.source_pdf = self.vault.inbox / INBOX_PDF_NAME
        self.source_pdf.write_bytes(PDF_BYTES)
        self.draft_card_path = self.draft_card("---\ntitle: A Work\n---\n")
        self.placed_pdf = self.vault.library / PLACED_PDF_NAME
        self.placed_pdf.write_bytes(PDF_BYTES)
        self.note_path = self.vault.corpus / PLACED_NOTE_NAME
        FilingCompletion().complete(self._filing_outcome())

    def _filing_outcome(self) -> FilingOutcome:
        placed = PlacedAttachment(self.placed_pdf, ATTACHMENT_LINK)
        return FilingOutcome(self.source_pdf, Citation().meta(), CITEKEY, ConnectorResult.saved(),
                             Placement(placed))

    def test_the_corpus_file_is_written_under_the_placed_name(self) -> None:
        self.assertTrue(self.note_path.is_file())

    def test_the_note_links_to_the_placed_attachment(self) -> None:
        self.assertEqual(ATTACHMENT_LINK, CorpusNote(PLACED_PDF_NAME).link())

    def test_the_draft_card_is_deleted(self) -> None:
        self.assertFalse(self.draft_card_path.exists())

    def test_the_source_pdf_leaves_the_inbox(self) -> None:
        self.assertFalse(self.source_pdf.exists())

    def test_the_placed_pdf_survives(self) -> None:
        self.assertTrue(self.placed_pdf.is_file())


class TestFilingCarriesTheScratchEntries(VaultTestCase):
    KEPT_SUGGESTION = b'{"kept": true}'

    def setUp(self) -> None:
        super().setUp()
        source_pdf = self.vault.inbox / INBOX_PDF_NAME
        source_pdf.write_bytes(PDF_BYTES)
        placed_pdf = self.vault.library / PLACED_PDF_NAME
        placed_pdf.write_bytes(PDF_BYTES)
        (vault.SCRATCH_DIR / "scan").mkdir()
        (vault.SCRATCH_DIR / "scan" / "scope.json").write_text("{}", encoding="utf-8")
        (vault.SCRATCH_DIR / "scan.entries.json").write_text("[]", encoding="utf-8")
        (vault.SCRATCH_DIR / "scan.suggested.json").write_text("[]", encoding="utf-8")
        (vault.SCRATCH_DIR / "Doe - 2020 - A Work.suggested.json").write_bytes(self.KEPT_SUGGESTION)
        (vault.SCRATCH_DIR / "ingest" / "scan").mkdir(parents=True)
        (vault.SCRATCH_DIR / "ingest" / "scan" / "state.json").write_text("{}", encoding="utf-8")
        placed = PlacedAttachment(placed_pdf, ATTACHMENT_LINK)
        FilingCompletion().complete(FilingOutcome(source_pdf, Citation().meta(), CITEKEY, ConnectorResult.saved(),
                                                  Placement(placed)))

    def test_the_render_directory_takes_the_library_basename(self) -> None:
        self.assertTrue((vault.SCRATCH_DIR / "Doe - 2020 - A Work" / "scope.json").exists())
        self.assertFalse((vault.SCRATCH_DIR / "scan").exists())

    def test_the_batch_work_directory_takes_the_library_basename(self) -> None:
        self.assertEqual((True, False), ((vault.SCRATCH_DIR / "ingest" / "Doe - 2020 - A Work" / "state.json").exists(),
                                         (vault.SCRATCH_DIR / "ingest" / "scan").exists()))

    def test_the_entries_file_takes_the_library_basename(self) -> None:
        self.assertTrue((vault.SCRATCH_DIR / "Doe - 2020 - A Work.entries.json").exists())

    def test_an_entry_already_under_the_library_basename_is_kept(self) -> None:
        self.assertEqual(self.KEPT_SUGGESTION, (vault.SCRATCH_DIR / "Doe - 2020 - A Work.suggested.json").read_bytes())

    def test_the_source_of_a_kept_entry_is_left(self) -> None:
        self.assertTrue((vault.SCRATCH_DIR / "scan.suggested.json").exists())


class TestFilingOutcomeStatus(unittest.TestCase):
    def _status(self, connector: ConnectorResult) -> str:
        return FilingOutcome(Path(INBOX_PDF_NAME), Citation().meta(), CITEKEY, connector, Placement()).status

    def test_an_offline_zotero_reports_offline(self) -> None:
        self.assertEqual(STATUS_ZOTERO_OFFLINE, self._status(ConnectorResult.offline()))

    def test_a_refused_item_reports_the_refusal_not_an_offline_zotero(self) -> None:
        self.assertEqual(STATUS_CONNECTOR_REFUSED, self._status(ConnectorResult.refused()))

    def test_an_item_saved_without_its_attachment_says_so(self) -> None:
        self.assertEqual(STATUS_FILED_NO_ATTACHMENT, self._status(saved_without_attachment()))

    def test_a_dropped_connection_is_neither_offline_nor_refused(self) -> None:
        self.assertEqual(STATUS_CONNECTION_LOST, self._status(ConnectorResult.lost()))

    def test_an_item_saved_and_attached_but_not_placed_is_unverified(self) -> None:
        self.assertEqual(STATUS_FILED_UNVERIFIED, self._status(ConnectorResult.saved()))


class TestNoteCollision(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.source_pdf = self.vault.inbox / INBOX_PDF_NAME
        self.source_pdf.write_bytes(PDF_BYTES)
        self.placed_pdf = self.vault.library / PLACED_PDF_NAME
        self.placed_pdf.write_bytes(PDF_BYTES)
        self.existing_note = self.vault.corpus / PLACED_NOTE_NAME
        self.existing_note.write_text("---\ntitle: Held\n---\n\n## Introduction\n\nkept\n", encoding="utf-8")

    def _filing_outcome(self) -> FilingOutcome:
        placed = PlacedAttachment(self.placed_pdf, ATTACHMENT_LINK)
        return FilingOutcome(self.source_pdf, Citation().meta(), CITEKEY, ConnectorResult.saved(),
                             Placement(placed))

    def _settled(self) -> Settlement:
        settlement = Settlement(FilingCompletion(), DraftCard(INBOX_PDF_NAME).load(), self._filing_outcome())
        settlement.settle()
        return settlement

    def test_a_placed_name_with_a_corpus_file_already_collides(self) -> None:
        self.assertTrue(FilingCompletion().collides(self._filing_outcome()))

    def test_completion_refuses_to_overwrite_the_existing_note(self) -> None:
        with self.assertRaises(RuntimeError):
            FilingCompletion().complete(self._filing_outcome())
        self.assertIn("kept", self.existing_note.read_text(encoding="utf-8"))

    def test_the_settlement_reports_the_collision(self) -> None:
        self.assertEqual(STATUS_NOTE_COLLISION, self._settled().status)

    def test_the_settlement_keeps_the_draft_as_filed(self) -> None:
        self._settled()
        self.assertTrue(DraftCard(INBOX_PDF_NAME).load().filed)


class TestHandWrittenFieldsSurviveARewrite(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        holding_dir = self.vault.named("holding")
        holding_dir.mkdir()
        self.holding = holding_dir / PLACED_PDF_NAME
        self.holding.write_bytes(PDF_BYTES)
        self.placed_pdf = self.vault.library / PLACED_PDF_NAME
        self.placed_pdf.write_bytes(PDF_BYTES)
        self.note_path = self.vault.corpus / PLACED_NOTE_NAME
        self.note_path.write_text(
            "---\ntitle: Old\nsource_type: monograph\nsource_role: secondary\nfield:\n- '[[Logic]]'\n"
            "commentary_on: '[[Kant - 1998 - Critique of Pure Reason]]'\n---\n\n## Introduction\n\nkept\n",
            encoding="utf-8")
        placed = PlacedAttachment(self.placed_pdf, ATTACHMENT_LINK)
        FilingCompletion().complete(FilingOutcome(self.holding, Citation().meta(), CITEKEY,
                                                  ConnectorResult.saved(), Placement(placed)))
        self.fields = CorpusNote(PLACED_PDF_NAME).fields()

    def test_the_classification_is_carried_over(self) -> None:
        self.assertEqual(("monograph", "secondary"), (self.fields["source_type"], self.fields["source_role"]))

    def test_the_placement_is_carried_over(self) -> None:
        self.assertEqual(["[[Logic]]"], self.fields["field"])

    def test_the_commentary_target_is_carried_over(self) -> None:
        self.assertEqual("[[Kant - 1998 - Critique of Pure Reason]]", self.fields["commentary_on"])

    def test_the_fresh_title_replaces_the_old_one(self) -> None:
        self.assertEqual("A Work", self.fields["title"])

    def test_the_body_is_kept(self) -> None:
        self.assertIn("kept", self.note_path.read_text(encoding="utf-8"))


class TestHiddenConflictCopiesAreReported(VaultTestCase):
    NUMBERED_COPY = "Doe - 2020 - A Work 2.pdf"

    def setUp(self) -> None:
        super().setUp()
        (self.vault.library / PLACED_PDF_NAME).write_bytes(PDF_BYTES)
        (self.vault.library / self.NUMBERED_COPY).write_bytes(PDF_BYTES)
        self.stub_zotero(is_online=lambda timeout=None: False)

    def test_the_listing_hides_the_numbered_copy(self) -> None:
        self.assertEqual([PLACED_PDF_NAME], [path.name for path in vault.list_pdfs(self.vault.library)])

    def test_status_reports_the_numbered_copy(self) -> None:
        self.assertEqual([self.NUMBERED_COPY], StatusReport().render()["conflict_copies"])

    def test_doctor_reports_the_numbered_copy(self) -> None:
        self.assertEqual([self.NUMBERED_COPY], DoctorReport().render()["conflict_copies"])


class LiveZoteroDatabase:
    SCHEMA = ("CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT)",
              "CREATE TABLE itemAttachments (itemID INTEGER, parentItemID INTEGER, path TEXT)",
              "CREATE TABLE deletedItems (itemID INTEGER)")

    def __init__(self, path: Path) -> None:
        self.path = path
        self._writer = sqlite3.connect(path)
        self._writer.execute("PRAGMA journal_mode=WAL")
        for statement in self.SCHEMA:
            self._writer.execute(statement)
        self._writer.commit()

    def attach(self, item_key: str, pdf_name: str) -> None:
        self._writer.execute("INSERT INTO items VALUES (?, ?)", (ITEM_ID, item_key))
        self._writer.execute("INSERT INTO itemAttachments VALUES (?, ?, ?)",
                             (ATTACHMENT_ID, ITEM_ID, f"attachments:{pdf_name}"))
        self._writer.commit()

    def wal_size(self) -> int:
        return self.path.with_name(f"{self.path.name}-wal").stat().st_size

    def close(self) -> None:
        self._writer.close()


class TestNoteReadsTheZoteroDatabaseBehindItsWal(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.live = self.enterContext(contextlib.closing(LiveZoteroDatabase(self.vault.named("zotero.sqlite"))))
        self.live.attach(ZOTERO_ITEM_KEY, PLACED_PDF_NAME)
        self.assertGreater(self.live.wal_size(), 0)

    def test_a_row_still_in_the_write_ahead_log_is_found(self) -> None:
        self.assertEqual(ZOTERO_ITEM_KEY, ZoteroDatabase(self.live.path).parent_item_key(PLACED_PDF_NAME))

    def test_the_database_is_read_from_a_copy_in_the_scratch_directory(self) -> None:
        ZoteroDatabase(self.live.path).parent_item_key(PLACED_PDF_NAME)
        self.assertTrue((vault.SCRATCH_DIR / "zotero" / "zotero.sqlite").exists())

    def test_an_unattached_pdf_has_no_parent(self) -> None:
        self.assertIsNone(ZoteroDatabase(self.live.path).parent_item_key(OTHER_WORK_PDF_NAME))


class BodyReadForbidden:
    def __init__(self, test: unittest.TestCase) -> None:
        self._test = test

    def read(self, path: Path) -> tuple[dict, str]:
        self._test.fail(f"the whole of {path.name} was read; citekey allocation reads the frontmatter only")


class TestCitekeyAllocationReadsOnlyTheFrontmatter(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "## One\n\nA long body.\n")
        self.addCleanup(setattr, vault, "read_frontmatter", vault.read_frontmatter)
        vault.read_frontmatter = BodyReadForbidden(self).read

    def test_the_taken_citekeys_are_read_from_the_frontmatter_alone(self) -> None:
        self.assertEqual(f"{CITEKEY}a", CitekeyAllocator().for_meta(Citation().meta()))


class TestCitekeyAllocationCountsTheKeysZoteroHolds(VaultTestCase):
    def test_a_suffixed_key_held_only_in_zotero_is_taken(self) -> None:
        self.stub_zotero(held_citekeys_beginning=lambda prefix: {prefix, f"{prefix}a"})
        self.assertEqual(f"{CITEKEY}b", CitekeyAllocator().for_meta(Citation().meta()))

    def test_a_base_key_zotero_does_not_hold_stays_unsuffixed(self) -> None:
        self.assertEqual(CITEKEY, CitekeyAllocator().for_meta(Citation().meta()))


class TestDoctorReportsNoFilenameMismatches(VaultTestCase):
    def test_a_basename_the_frontmatter_does_not_predict_is_not_a_mismatch(self) -> None:
        (self.vault.library / PLACED_PDF_NAME).write_bytes(PDF_BYTES)
        CorpusNote(PLACED_PDF_NAME).write({"title": "Another Work", "author": ["Doe"], "year": 2020},
                                          ATTACHMENT_LINK, "")
        self.stub_zotero(is_online=lambda timeout=None: False)
        self.assertNotIn("filename_mismatches", DoctorReport().render())


if __name__ == "__main__":
    unittest.main()
