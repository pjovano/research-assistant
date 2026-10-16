from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import vault

from _extract.acceptance import Acceptance
from _extract.build import EXTRACTION_MODE_FIELD, DoubtfulPagesRemain
from _extract.checks import PageVerdict
from _extract.cli import main
from _extract.console import EXIT_OK
from _extract.paths import CorpusFile, CorpusFileExists, FrontmatterFields
from _extract.records import MODE_KEY, REVIEWED_KEY, ExtractionRecord, ExtractionRecords
from _extract.stage import BodyTarget
from _extract.regression import (
    STATE_CHANGED, STATE_DOUBTFUL, STATE_UNCHANGED, BodyComparison, RegressionCheck, RegressionSample, ReviewedWorks,
    SampleChoice,
)
from _extract.request import FLAGS_FIELD, REVIEWED_FIELD, SCOPE_FIELD, ExtractionRequest, RecordUnreadable
from _extract.trial import TrialMissing, TrialNote
from _vaults import TempVault, TextPdf

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
LINK_LINE = "[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)"
FRONTMATTER = "---\ntitle: A Work\ntype: book\n---\n"
TODAY = "2026-09-24"
OUTLINE = [[1, "Introduction", 1], [1, "Chapter One", 3], [2, "A Section", 4]]
PAGES = 6
TRIAL_BODY = "# Introduction\n\n%% p. 1 (file p. 1) %%\nOpening prose.\n\n%% file p. 3 %%\nChapter prose.\n"
OTHER_BODY = "%% file p. 1 %%\nA body written by an earlier run.\n"
SPANS = (("1: Opening", "3"), ("end", "end"))
RECORD_FIELDS = (SCOPE_FIELD, FLAGS_FIELD, REVIEWED_FIELD, EXTRACTION_MODE_FIELD)


class ReviewVaultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(self.vault.library / f"{BASENAME}.pdf", PAGES, OUTLINE).write()
        self.corpus_path = self.vault.corpus / f"{BASENAME}.md"
        self.corpus_path.write_text(f"{FRONTMATTER}\n{LINK_LINE}\n", encoding="utf-8")
        self.note = CorpusFile(self.pdf)

    def written_trial(self, text: str = TRIAL_BODY, fields: dict | None = None,
                      report: dict | None = None) -> TrialNote:
        trial = TrialNote(self.note)
        trial.write(text, fields if fields is not None else request_of(SPANS).record_fields())
        trial.write_report(report or {})
        return trial


def request_of(spans: tuple | None, **flags) -> ExtractionRequest:
    return ExtractionRequest(spans, **flags)


class CapturedRun:
    def __init__(self, argv: list[str]) -> None:
        self._argv = argv
        self.output = ""
        self.code = 0

    def go(self) -> "CapturedRun":
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.code = main(self._argv)
        self.output = output.getvalue()
        return self


class TestExtractionRecord(unittest.TestCase):
    def _round_trip(self, request: ExtractionRequest) -> ExtractionRequest:
        block = FrontmatterFields().upserted("---\ntitle: A Work\n---\n", request.record_fields())
        meta, _body = vault.parse_note(block)
        return ExtractionRequest.from_record(meta, BASENAME)

    def test_a_scope_with_colons_in_its_points_survives_the_frontmatter(self) -> None:
        self.assertEqual(SPANS, self._round_trip(request_of(SPANS)).excluded)

    def test_a_scope_excluding_nothing_is_recorded_as_an_empty_list(self) -> None:
        self.assertEqual((), self._round_trip(request_of(())).excluded)

    def test_the_flags_survive_the_frontmatter(self) -> None:
        recorded = self._round_trip(request_of((), force_ocr=True, forced_pages="12-40"))
        self.assertEqual((True, "12-40"), (recorded.force_ocr, recorded.forced_pages))

    def test_a_record_without_a_scope_is_refused(self) -> None:
        with self.assertRaises(RecordUnreadable):
            ExtractionRequest.from_record({FLAGS_FIELD: []}, BASENAME)

    def test_a_malformed_span_is_refused(self) -> None:
        with self.assertRaises(RecordUnreadable):
            ExtractionRequest.from_record({SCOPE_FIELD: ["no separator"]}, BASENAME)

    def test_a_stored_record_survives_the_records_file(self) -> None:
        request = request_of(SPANS, force_ocr=True, forced_pages="12-40")
        recorded = ExtractionRequest.from_stored(request.stored(), BASENAME)
        self.assertEqual((SPANS, True, "12-40"), (recorded.excluded, recorded.force_ocr, recorded.forced_pages))

    def test_a_malformed_stored_record_is_refused(self) -> None:
        with self.assertRaises(RecordUnreadable):
            ExtractionRequest.from_stored({"scope": ["no pair"]}, BASENAME)

    def test_arguments_without_a_scope_give_no_scope(self) -> None:
        args = argparse.Namespace(exclude=None, exclude_nothing=False, force_ocr=False, force_ocr_pages=None,
                                  fresh=False, readings=None)
        self.assertFalse(ExtractionRequest.from_args(args).scope_given)


class TestTrialNote(ReviewVaultTestCase):
    def test_the_trial_carries_the_corpus_frontmatter_the_fields_and_the_body(self) -> None:
        trial = self.written_trial(fields={SCOPE_FIELD: [], EXTRACTION_MODE_FIELD: "forced-ocr"})
        self.assertEqual(("A Work", "forced-ocr", TRIAL_BODY.strip()),
                         (trial.frontmatter()["title"], trial.frontmatter()[EXTRACTION_MODE_FIELD],
                          trial.body().strip()))

    def test_the_trial_lives_in_the_scratch_directory_not_the_vault(self) -> None:
        trial = self.written_trial()
        self.assertTrue(trial.path.is_relative_to(vault.SCRATCH_DIR))
        self.assertFalse(self.note.has_body())

    def test_the_report_is_read_back(self) -> None:
        self.assertEqual({"omitted_pages": [2]}, self.written_trial(report={"omitted_pages": [2]}).report())

    def test_a_missing_trial_is_refused_by_name(self) -> None:
        with self.assertRaises(TrialMissing):
            TrialNote(self.note).require()


class TestAcceptance(ReviewVaultTestCase):
    def _accepted(self) -> dict:
        Acceptance(self.note, TrialNote(self.note), TODAY).accept()
        return self.note.frontmatter()

    def _accepted_replacing(self) -> dict:
        Acceptance(self.note, TrialNote(self.note), TODAY).accept_replacing()
        return self.note.frontmatter()

    def _forced_ocr_trial(self) -> None:
        self.written_trial(fields={**request_of(SPANS, force_ocr=True).record_fields(),
                                   EXTRACTION_MODE_FIELD: "forced-ocr"})

    def test_the_body_is_written_and_the_work_is_marked_reviewed(self) -> None:
        self._forced_ocr_trial()
        self._accepted()
        entry = ExtractionRecords().entry(BASENAME)
        self.assertEqual((TODAY, "forced-ocr", TRIAL_BODY.strip()),
                         (entry[REVIEWED_KEY], entry[MODE_KEY], self.note.body().strip()))

    def test_the_record_is_stored_in_the_library_and_not_in_the_frontmatter(self) -> None:
        self._forced_ocr_trial()
        meta = self._accepted()
        recorded = ExtractionRecords().request_of(BASENAME)
        self.assertEqual((SPANS, True), (recorded.excluded, recorded.force_ocr))
        self.assertEqual([], [field for field in RECORD_FIELDS if field in meta])

    def test_an_accepted_body_sheds_a_record_its_frontmatter_already_carried(self) -> None:
        self.written_trial()
        carried = {**request_of(SPANS).record_fields(), REVIEWED_FIELD: TODAY, EXTRACTION_MODE_FIELD: "forced-ocr"}
        self.note.write(TRIAL_BODY, carried)
        meta = self._accepted()
        self.assertEqual([], [field for field in RECORD_FIELDS if field in meta])

    def test_a_text_layer_work_records_no_extraction_mode(self) -> None:
        self.written_trial()
        self._accepted()
        self.assertNotIn(MODE_KEY, ExtractionRecords().entry(BASENAME))

    def test_a_different_body_is_refused_without_replace(self) -> None:
        self.written_trial()
        self.note.write(OTHER_BODY, {})
        with self.assertRaises(CorpusFileExists):
            self._accepted()

    def test_the_same_body_is_marked_reviewed_without_replace(self) -> None:
        self.written_trial()
        self.note.write(TRIAL_BODY, {})
        self._accepted()
        self.assertEqual(TODAY, self.note.reviewed())

    def test_a_body_differing_only_by_citation_links_is_marked_reviewed_and_keeps_its_links(self) -> None:
        self.written_trial()
        linked = TRIAL_BODY.replace("Chapter prose.",
                                    f"Chapter prose. [[Roe - 2001 - Another|{vault.CITATION_LINK_MARK}]]")
        self.note.write(linked, {})
        self._accepted()
        self.assertEqual(TODAY, self.note.reviewed())
        self.assertEqual(linked.strip(), self.note.body().strip())

    def test_replace_rewrites_a_different_body(self) -> None:
        self.written_trial()
        self.note.write(OTHER_BODY, {})
        self._accepted_replacing()
        self.assertEqual(TRIAL_BODY.strip(), self.note.body().strip())

    def test_a_missing_trial_is_refused(self) -> None:
        with self.assertRaises(TrialMissing):
            self._accepted()


class FakeRendered:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeBuild:
    def __init__(self, text: str | None) -> None:
        self._text = text

    def rendered(self) -> FakeRendered:
        if self._text is None:
            raise DoubtfulPagesRemain([PageVerdict(2, "doubtful", "length", "")])
        return FakeRendered(self._text)


class TestExtractionRecords(ReviewVaultTestCase):
    def test_the_records_file_lives_in_the_library(self) -> None:
        self.assertEqual(self.vault.library, ExtractionRecords().path.parent)

    def test_a_work_with_no_record_is_refused_by_name(self) -> None:
        with self.assertRaisesRegex(RecordUnreadable, BASENAME):
            ExtractionRecords().request_of(BASENAME)

    def test_a_body_written_to_the_corpus_file_stores_its_record_and_clears_the_fields(self) -> None:
        target, request = BodyTarget.corpus_file(self.note), request_of(SPANS)
        target.written(TRIAL_BODY, target.record_fields(request, None))
        target.store_record(request, None)
        self.assertEqual(SPANS, ExtractionRecords().request_of(BASENAME).excluded)
        self.assertNotIn(SCOPE_FIELD, self.note.frontmatter())

    def test_a_trial_keeps_its_record_in_its_own_frontmatter(self) -> None:
        target, request = BodyTarget.trial_of(self.note), request_of(SPANS)
        target.written(TRIAL_BODY, target.record_fields(request, None))
        target.store_record(request, None)
        self.assertEqual(SPANS, ExtractionRequest.from_record(TrialNote(self.note).frontmatter(), BASENAME).excluded)
        self.assertFalse(ExtractionRecords().path.exists())

    def test_a_body_written_to_the_corpus_file_unseen_by_the_reviewer_drops_the_stored_review_date(self) -> None:
        ExtractionRecords().write(BASENAME, ExtractionRecord(request_of(()), None, TODAY))
        target, request = BodyTarget.corpus_file(self.note), request_of(SPANS, force_ocr=True)
        target.written(TRIAL_BODY, target.record_fields(request, "forced-ocr"))
        target.store_record(request, "forced-ocr")
        entry = ExtractionRecords().entry(BASENAME)
        self.assertEqual((None, "forced-ocr", SPANS),
                         (entry.get(REVIEWED_KEY), entry[MODE_KEY], ExtractionRecords().request_of(BASENAME).excluded))

    def test_the_record_command_prints_the_works_entry(self) -> None:
        ExtractionRecords().write(BASENAME, ExtractionRecord(request_of(SPANS), "forced-ocr", TODAY))
        run = CapturedRun(["record", str(self.pdf)]).go()
        self.assertEqual((EXIT_OK, "forced-ocr"), (run.code, json.loads(run.output)["record"][MODE_KEY]))

    def test_the_record_command_prints_null_for_a_work_with_no_record(self) -> None:
        run = CapturedRun(["record", str(self.pdf)]).go()
        self.assertIsNone(json.loads(run.output)["record"])

    def test_writing_one_record_keeps_the_others(self) -> None:
        records = ExtractionRecords()
        records.write(BASENAME, request_of(SPANS))
        records.write("Roe - 2021 - Another", request_of(()))
        self.assertEqual(SPANS, records.request_of(BASENAME).excluded)


class TestRegression(ReviewVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.written_trial()
        Acceptance(self.note, TrialNote(self.note), TODAY).accept()

    def _checked(self, rebuilt: str | None) -> dict:
        return RegressionCheck(lambda _pdf, _note, _request: FakeBuild(rebuilt)).run([self.pdf])[0]

    def test_an_identical_rebuild_is_unchanged(self) -> None:
        self.assertEqual(STATE_UNCHANGED, self._checked(TRIAL_BODY)["state"])

    def test_a_differing_rebuild_writes_a_diff_into_the_scratch_directory(self) -> None:
        checked = self._checked(TRIAL_BODY.replace("Chapter prose.", "Chapter prose, changed."))
        self.assertEqual((STATE_CHANGED, 2), (checked["state"], checked["changed_lines"]))
        self.assertTrue(Path(checked["diff"]).is_relative_to(vault.SCRATCH_DIR))
        self.assertIn("+Chapter prose, changed.", Path(checked["diff"]).read_text(encoding="utf-8"))

    def test_a_rebuild_with_doubtful_pages_names_them_and_diffs_nothing(self) -> None:
        self.assertEqual({"work": BASENAME, "state": STATE_DOUBTFUL, "doubtful_pages": [2]}, self._checked(None))

    def test_the_reviewed_works_are_those_marked(self) -> None:
        TextPdf(self.vault.library / "Roe - 2021 - Another.pdf").write()
        self.assertEqual([self.pdf], ReviewedWorks().all())

    def test_a_comparison_ignores_surrounding_whitespace(self) -> None:
        self.assertEqual(STATE_UNCHANGED, BodyComparison(self.note, f"\n{TRIAL_BODY}\n\n").as_dict()["state"])

    def test_a_comparison_ignores_the_citation_links_stage_4_added(self) -> None:
        linked = TRIAL_BODY.replace("Chapter prose.",
                                    f"Chapter prose. [[Roe - 2001 - Another|{vault.CITATION_LINK_MARK}]]")
        self.note.write(linked, {})
        self.assertEqual(STATE_UNCHANGED, BodyComparison(self.note, TRIAL_BODY).as_dict()["state"])


class TestRegressionSample(unittest.TestCase):
    WORKS = [Path(f"{letter}.pdf") for letter in "abcdefgh"]
    CACHED = {Path("b.pdf"), Path("e.pdf")}

    @staticmethod
    def _first(works: list[Path], count: int) -> list[Path]:
        return works[:count]

    def _sample(self, size: int) -> RegressionSample:
        return RegressionSample(self.WORKS, size, SampleChoice(self.CACHED.__contains__, self._first))

    def test_every_cached_work_is_taken_and_random_works_fill_the_sample(self) -> None:
        chosen = self._sample(4).chosen()
        self.assertEqual([Path("b.pdf"), Path("e.pdf"), Path("a.pdf"), Path("c.pdf")], chosen)
        self.assertEqual({"reviewed": 8, "cached": 2, "random": 2}, self._sample(4).as_dict(chosen))

    def test_cached_works_past_the_sample_size_are_sampled_down_to_it(self) -> None:
        self.assertEqual([Path("b.pdf")], self._sample(1).chosen())

    def test_a_sample_takes_cached_works_before_it_converts_any(self) -> None:
        self.assertEqual({"reviewed": 8, "cached": 2, "random": 0}, self._sample(2).as_dict(self._sample(2).chosen()))

    def test_a_sample_of_the_whole_takes_every_work(self) -> None:
        self.assertEqual(len(self.WORKS), len(self._sample(len(self.WORKS)).chosen()))


class ReportingBuild(FakeBuild):
    def extraction_fields(self) -> dict:
        return {EXTRACTION_MODE_FIELD: None}

    def verdicts(self) -> list:
        return []

    def pixel_pages(self) -> list[int]:
        return []

    def structure(self) -> "ReportingBuild":
        return self

    def footnote_log(self) -> list[str]:
        return []

    def notation_log(self) -> list[str]:
        return []

    def folio_log(self) -> list[str]:
        return []

    def notation_blocks(self) -> dict:
        return {}


class TestCommandLine(ReviewVaultTestCase):
    def _trial_run(self) -> CapturedRun:
        with mock.patch("_extract.stage.EngineSession", contextlib.nullcontext), \
                mock.patch("_extract.stage.StageCommands.build", return_value=ReportingBuild(TRIAL_BODY)):
            return CapturedRun(["extract", f"{BASENAME}.pdf", "--exclude-nothing", "--trial"]).go()

    def test_a_trial_is_written_beside_an_existing_body_without_replace(self) -> None:
        self.note.write(OTHER_BODY, {})
        run = self._trial_run()
        report = json.loads(run.output)
        self.assertEqual((EXIT_OK, True, OTHER_BODY.strip()), (run.code, report["trial"], self.note.body().strip()))
        self.assertEqual(report, TrialNote(self.note).report())

    def test_probe_reports_the_trial_and_the_review_state(self) -> None:
        self._trial_run()
        probe = json.loads(CapturedRun(["probe", f"{BASENAME}.pdf"]).go().output)
        self.assertEqual((True, None), (probe["trial_exists"], probe["reviewed"]))

    def test_accept_marks_the_work_reviewed(self) -> None:
        self._trial_run()
        run = CapturedRun(["accept", f"{BASENAME}.pdf"]).go()
        self.assertEqual((EXIT_OK, json.loads(run.output)["reviewed"]), (run.code, self.note.reviewed()))
        self.assertIsNotNone(self.note.reviewed())

    def test_review_status_lists_a_body_not_yet_reviewed(self) -> None:
        self.note.write(OTHER_BODY, {})
        self.assertEqual(f"{BASENAME}.pdf\n", CapturedRun(["review-status"]).go().output)
