from __future__ import annotations

import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import transcribe
import vault
from zotero import BetterBibtexError, ConnectorResult
from _transcribe_fixtures import (BASENAME, CARD, RECORDING_URL, REVIEWED_TEXT, TALK_PART, TWO_PART_RAW, Review,
                                  TalkTestCase)


class FakeZotero:
    def __init__(self, result: ConnectorResult | None = None, taken: set[str] | None = None,
                 bibtex_down: bool = False) -> None:
        self.saved: list[tuple[dict, str]] = []
        self._result = result or ConnectorResult(True, True, False, item_key="KEY1")
        self._taken = taken or set()
        self._bibtex_down = bibtex_down

    def save_item(self, meta: dict, source_uri: str) -> ConnectorResult:
        self.saved.append((meta, source_uri))
        return self._result

    def citekeys_beginning(self, prefix: str) -> set[str]:
        if self._bibtex_down:
            raise BetterBibtexError("Better BibTeX item.search failed: connection refused")
        return {key for key in self._taken if key.startswith(prefix)}


class TestTalkRecord(TalkTestCase):
    def test_the_basename_joins_the_presenter_the_year_and_the_main_title(self) -> None:
        self.assertEqual(BASENAME, transcribe.TalkRecord(self.reviewed()).basename)

    def test_a_subtitle_stays_out_of_the_basename(self) -> None:
        card = {**CARD, "title": "Hegel on Logic as Metaphysics: A Lecture"}
        self.assertEqual(BASENAME, transcribe.TalkRecord(self.reviewed(review=Review(card=card))).basename)

    def test_two_presenters_are_joined_and_three_take_et_al(self) -> None:
        pair = {**CARD, "presenters": [{"lastName": "Pippin"}, {"lastName": "Houlgate"}]}
        trio = {**CARD, "presenters": [{"lastName": "Pippin"}, {"lastName": "Houlgate"}, {"lastName": "Ng"}]}
        self.assertEqual("Pippin and Houlgate - 2019 - Hegel on Logic as Metaphysics",
                         transcribe.TalkRecord(self.reviewed("a", Review(card=pair))).basename)
        self.assertEqual("Pippin et al. - 2019 - Hegel on Logic as Metaphysics",
                         transcribe.TalkRecord(self.reviewed("b", Review(card=trio))).basename)

    def test_the_zotero_item_is_a_presentation_by_its_presenters_at_its_meeting(self) -> None:
        meta = transcribe.TalkRecord(self.reviewed()).zotero_meta()
        self.assertEqual(("presentation", "presenter", "Philosophy Talks lecture series", RECORDING_URL),
                         (meta["type"], meta["creator_type"], meta["bib"]["meetingName"], meta["bib"]["url"]))

    def test_the_zotero_date_is_the_upload_date_when_the_talk_was_given_that_year(self) -> None:
        self.assertEqual("2019-03-14", transcribe.TalkRecord(self.reviewed()).zotero_meta()["bib"]["date"])

    def test_the_zotero_date_is_the_year_alone_when_the_upload_came_later(self) -> None:
        record = transcribe.TalkRecord(self.reviewed(review=Review(card={**CARD, "year": 2011})))
        self.assertEqual("2011", record.zotero_meta()["bib"]["date"])

    def test_the_basename_takes_the_title_in_title_case(self) -> None:
        card = {**CARD, "title": "how did judgement come to be a term of logic?"}
        self.assertEqual("Pippin - 2019 - How Did Judgement Come to Be a Term of Logic",
                         transcribe.TalkRecord(self.reviewed(review=Review(card=card))).basename)

    def test_a_card_title_not_in_title_case_is_stored_cased_in_zotero_and_the_frontmatter(self) -> None:
        record = transcribe.TalkRecord(self.reviewed(review=Review(card={**CARD,
                                                                         "title": "hegel on logic as metaphysics"})))
        stored = (record.zotero_meta()["title"], record.frontmatter("pippin2019")["title"])
        self.assertEqual((CARD["title"], CARD["title"]), stored)

    def test_an_empty_meeting_is_absent(self) -> None:
        record = transcribe.TalkRecord(self.reviewed(review=Review(card={**CARD, "meeting": ""})))
        self.assertIsNone(record.meeting)


class TestTranscriptCitekey(TalkTestCase):
    def test_the_citekey_is_the_first_surname_and_the_year(self) -> None:
        record = transcribe.TalkRecord(self.reviewed())
        self.assertEqual("pippin2019", transcribe.TranscriptCitekey(record, FakeZotero()).allocated())

    def test_a_citekey_a_held_note_carries_is_suffixed(self) -> None:
        vault.write_frontmatter(vault.CORPUS_DIR / "Pippin - 2019 - Idealism.md", {"citekey": "pippin2019"}, "")
        record = transcribe.TalkRecord(self.reviewed())
        self.assertEqual("pippin2019a", transcribe.TranscriptCitekey(record, FakeZotero()).allocated())

    def test_a_citekey_zotero_holds_is_suffixed(self) -> None:
        record = transcribe.TalkRecord(self.reviewed())
        allocated = transcribe.TranscriptCitekey(record, FakeZotero(taken={"pippin2019"})).allocated()
        self.assertEqual("pippin2019a", allocated)


class TestTalkFilingPlan(TalkTestCase):
    def test_the_plan_names_the_note_the_item_and_the_frontmatter_without_writing(self) -> None:
        entry = self.reviewed()
        plan = transcribe.TalkFiling(entry, FakeZotero()).plan()
        self.assertEqual(str(vault.transcript_path(BASENAME)), plan["note"])
        self.assertEqual("presentation", plan["zotero_item"]["itemType"])
        self.assertIsNone(plan["frontmatter"]["source_type"])
        self.assertFalse(vault.transcript_path(BASENAME).exists())
        self.assertTrue(entry.card.exists())


class TestTalkFilingApply(TalkTestCase):
    def setUp(self) -> None:
        super().setUp()
        parts = (f"{TALK_PART}\n\n**Pippin:** Logic, for Hegel, is metaphysics.",
                 "## Discussion\n\n%% 00:40:00 %%\n**Audience member:** May I ask?")
        self.entry = self.reviewed(review=Review(parts=parts, raw=TWO_PART_RAW))
        self.zotero = FakeZotero()
        self.report = transcribe.TalkFiling(self.entry, self.zotero).apply()
        self.meta, self.body = vault.read_frontmatter(vault.transcript_path(BASENAME))

    def test_the_item_is_saved_under_the_recording_url(self) -> None:
        [(meta, uri)] = self.zotero.saved
        self.assertEqual((RECORDING_URL, "presentation"), (uri, meta["type"]))

    def test_the_frontmatter_carries_the_identity_and_an_open_classification_and_no_link(self) -> None:
        expected = {"title": CARD["title"], "author": ["Pippin"], "year": 2019, "type": "presentation",
                    "citekey": "pippin2019", "meeting": CARD["meeting"],
                    "source_type": None, "source_role": None, "field": []}
        self.assertEqual(expected, self.meta)

    def test_the_recording_url_is_read_from_the_first_line(self) -> None:
        self.assertEqual(RECORDING_URL, transcribe.recording_url_of(self.body))

    def test_the_body_opens_with_the_recording_link_and_joins_the_parts_in_order(self) -> None:
        self.assertTrue(self.body.lstrip().startswith(f"[Recording]({RECORDING_URL})\n\n## Talk\n"))
        self.assertIn("\n\n## Discussion\n", self.body)

    def test_the_source_link_is_stripped_when_the_transcript_is_indexed(self) -> None:
        self.assertTrue(vault.body_after_source_link(self.body).startswith("## Talk\n"))

    def test_the_scratch_entry_is_deleted(self) -> None:
        self.assertFalse(self.entry.directory.exists())

    def test_the_report_says_filed(self) -> None:
        self.assertEqual((True, BASENAME), (self.report["filed"], self.report["basename"]))

    def test_the_report_says_the_entry_was_deleted(self) -> None:
        self.assertEqual((True, None), (self.report["entry_deleted"], self.report["entry_error"]))


class TestFiledMarkers(TalkTestCase):
    def test_no_filed_marker_falls_inside_a_sentence(self) -> None:
        entry = self.reviewed(review=Review(parts=(f"{TALK_PART}\n\n**Pippin:** Logic, for Hegel,",
                                     "%% 00:40:00 %%\n**Pippin:** is metaphysics. So it is."), raw=TWO_PART_RAW))
        transcribe.TalkFiling(entry, FakeZotero()).apply()
        _meta, body = vault.read_frontmatter(vault.transcript_path(BASENAME))
        self.assertIn("**Pippin:** Logic, for Hegel, is metaphysics.\n\n%% 00:40:00 %%\n**Pippin:** So it is.", body)


class TestPartFilesTheListingDoesNotName(TalkTestCase):
    def test_a_part_file_the_listing_does_not_name_refuses_the_filing(self) -> None:
        entry = self.reviewed(review=Review(parts=(REVIEWED_TEXT,
                                                   "## Left over\n\n**Pippin:** A part of an earlier listing.")))
        with self.assertRaises(transcribe.FilingRefused):
            transcribe.TalkFiling(entry, FakeZotero()).apply()
        self.assertFalse(vault.transcript_path(BASENAME).exists())


class TestTalkFilingRefusals(TalkTestCase):
    def test_a_review_that_fails_the_check_refuses_before_zotero_is_asked(self) -> None:
        entry = self.reviewed(review=Review(parts=("%% 00:00:00 %%\n**Pippin:** Logic, for Hegel, is metaphysics, "
                                     "and the doctrine of essence follows.\n",)))
        zotero = FakeZotero()
        with self.assertRaises(transcribe.FilingRefused):
            transcribe.TalkFiling(entry, zotero).apply()
        self.assertEqual(([], False), (zotero.saved, vault.transcript_path(BASENAME).exists()))

    def test_a_held_basename_refuses_before_zotero_is_asked(self) -> None:
        entry = self.reviewed()
        vault.write_frontmatter(vault.corpus_path(BASENAME), {"title": "Held"}, "")
        zotero = FakeZotero()
        with self.assertRaises(transcribe.FilingRefused):
            transcribe.TalkFiling(entry, zotero).apply()
        self.assertEqual([], zotero.saved)
        self.assertTrue(entry.card.exists())

    def test_zotero_offline_refuses_and_writes_nothing(self) -> None:
        entry = self.reviewed()
        with self.assertRaises(transcribe.FilingRefused):
            transcribe.TalkFiling(entry, FakeZotero(ConnectorResult.offline())).apply()
        self.assertFalse(vault.transcript_path(BASENAME).exists())
        self.assertTrue(entry.card.exists())

    def test_better_bibtex_not_answering_refuses_the_plan(self) -> None:
        with self.assertRaises(transcribe.FilingRefused):
            transcribe.TalkFiling(self.reviewed(), FakeZotero(bibtex_down=True)).plan()

    def test_a_refused_item_writes_nothing(self) -> None:
        entry = self.reviewed()
        with self.assertRaises(transcribe.FilingRefused):
            transcribe.TalkFiling(entry, FakeZotero(ConnectorResult.refused())).apply()
        self.assertFalse(vault.transcript_path(BASENAME).exists())


class NoteAppearingDuringTheSave(FakeZotero):
    def save_item(self, meta: dict, source_uri: str) -> ConnectorResult:
        vault.write_frontmatter(vault.transcript_path(BASENAME), {"title": "Synced in"}, "Another machine's note.")
        return super().save_item(meta, source_uri)


class TestANoteThatAppearsAfterTheBasenameCheck(TalkTestCase):
    def test_a_note_that_appears_during_the_save_is_never_overwritten(self) -> None:
        with self.assertRaises(transcribe.FilingRefused):
            transcribe.TalkFiling(self.reviewed(), NoteAppearingDuringTheSave()).apply()
        self.assertEqual("Synced in", vault.read_frontmatter_only(vault.transcript_path(BASENAME))["title"])


class TestANoteWriteThatFailsAfterTheItemIsSaved(TalkTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.entry = self.reviewed()
        self.zotero = FakeZotero()
        with mock.patch.object(vault, "write_frontmatter", side_effect=OSError("disk full")):
            with self.assertRaises(transcribe.FilingRefused) as refusal:
                transcribe.TalkFiling(self.entry, self.zotero).apply()
        self.refusal = str(refusal.exception)

    def test_the_refusal_names_the_saved_item_and_the_rerun(self) -> None:
        self.assertIn("KEY1", self.refusal)
        self.assertIn("file --apply", self.refusal)

    def test_a_rerun_reuses_the_saved_item_and_its_citekey(self) -> None:
        self.zotero = FakeZotero(taken={"pippin2019"})
        report = transcribe.TalkFiling(self.entry, self.zotero).apply()
        self.assertEqual(([], "pippin2019", True), (self.zotero.saved, report["citekey"], report["zotero_reused"]))


def rmtree_that_fails(path, ignore_errors=False) -> None:
    if not ignore_errors:
        raise OSError(f"cannot remove {path}: resource busy")


class TestATalkEntryThatCannotBeDeleted(TalkTestCase):
    def test_a_failed_delete_of_the_talk_entry_is_reported(self) -> None:
        with mock.patch("shutil.rmtree", side_effect=rmtree_that_fails):
            report = transcribe.TalkFiling(self.reviewed(), FakeZotero()).apply()
        self.assertEqual((True, False), (report["filed"], report["entry_deleted"]))
        self.assertIn("resource busy", report["entry_error"])


class TestTheFiledTranscriptIsReadBack(TalkTestCase):
    def test_the_filed_transcript_is_found_as_a_held_note_awaiting_stage_three(self) -> None:
        transcribe.TalkFiling(self.reviewed(review=Review(parts=(REVIEWED_TEXT,))), FakeZotero()).apply()
        meta = vault.read_frontmatter_only(vault.held_note_path(BASENAME))
        self.assertEqual((None, None, []), (meta["source_type"], meta["source_role"], meta["field"]))


if __name__ == "__main__":
    unittest.main()
