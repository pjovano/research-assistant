from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pymupdf

from _clean import fontrepair
from _extract import repairs
from _extract.blocks import DocumentBlocks, PageBlocks
from _extract.build import BuildInputs, CorpusBuild
from _extract.checks import REASON_EMPTY_PIXELS
from _extract.cli import main
from _extract.ranges import PageRanges
from _extract.layer import TextLayer
from _extract.paths import CorpusFile, FrontmatterFields, NoteMissing
from _extract.readings import MalformedReadings, Reading, WorkerReadings
from _extract.spans import ExcludedSpans, PagePlace, ScopePoints, UnresolvedScopePoint
from _extract_fixtures import PROSE
from _pagetext_fixtures import FakePredictor
from _vaults import TempVault, TextPdf

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
LINK_LINE = "[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)"
FRONTMATTER = "---\ntitle: A Work\ntype: book\n---\n"
EXISTING_NOTE_TEXT = f"{FRONTMATTER}\n{LINK_LINE}\n\nThe body written by an earlier run.\n"
USAGE_EXIT = 1
SCOPE_PAGES = 10
SCOPE_OUTLINE = [[1, "Introduction", 3], [1, "Chapter One", 6]]
LINED_PAGE = ("Inquiry, Vol. 53", "Abstract This paper considers Hegel.", "Even within the recent rebirth",
              "Even within the recent rebirth, again", "I")
FIRST_LINE_BASELINE, LINE_PITCH = 100.0, 40.0
LEFT_MARGIN = 72


class CapturedRun:
    def __init__(self, argv: list[str]) -> None:
        self._argv = argv
        self.output = ""
        self.errors = ""
        self.code = 0

    def go(self) -> "CapturedRun":
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.code = main(self._argv)
        self.output, self.errors = output.getvalue(), errors.getvalue()
        return self


class ExtractVaultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)


class TestCorpusFileGuard(ExtractVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.library / f"{BASENAME}.pdf").write()
        self.corpus_path = self.vault.corpus / f"{BASENAME}.md"
        self.corpus_path.write_text(EXISTING_NOTE_TEXT, encoding="utf-8")
        self.run = CapturedRun(["extract", f"{BASENAME}.pdf"]).go()

    def test_extract_exits_one_when_the_body_exists(self) -> None:
        self.assertEqual(USAGE_EXIT, self.run.code)

    def test_the_refusal_says_the_corpus_file_exists(self) -> None:
        self.assertIn("corpus file exists", self.run.errors)

    def test_the_refusal_names_replace_as_the_way_past_it(self) -> None:
        self.assertIn("--replace", self.run.errors)

    def test_the_existing_note_is_left_untouched(self) -> None:
        self.assertEqual(EXISTING_NOTE_TEXT, self.corpus_path.read_text(encoding="utf-8"))


class TestNoteRequired(ExtractVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.library / f"{BASENAME}.pdf").write()

    def test_extract_exits_one_when_the_note_is_absent(self) -> None:
        self.assertEqual(USAGE_EXIT, CapturedRun(["extract", f"{BASENAME}.pdf"]).go().code)

    def test_the_refusal_names_stage_one(self) -> None:
        self.assertIn("Stage 1", CapturedRun(["extract", f"{BASENAME}.pdf"]).go().errors)

    def test_probe_exits_one_when_the_note_is_absent(self) -> None:
        self.assertEqual(USAGE_EXIT, CapturedRun(["probe", f"{BASENAME}.pdf"]).go().code)

    def test_probe_runs_once_the_note_exists(self) -> None:
        (self.vault.corpus / f"{BASENAME}.md").write_text(FRONTMATTER, encoding="utf-8")
        self.assertEqual(0, CapturedRun(["probe", f"{BASENAME}.pdf"]).go().code)


class TestStatusListing(ExtractVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        for name in (f"{BASENAME}.pdf", f"{BASENAME} 2.pdf", f"{BASENAME} (conflicted copy 2026-09-13).pdf"):
            TextPdf(self.vault.library / name).write()

    def test_status_lists_a_pdf_lacking_a_body_but_never_an_icloud_conflict_copy(self) -> None:
        self.assertEqual([f"{BASENAME}.pdf"], CapturedRun(["status"]).go().output.splitlines())


class TestScopeRequired(ExtractVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.library / f"{BASENAME}.pdf").write()
        self.note_path = self.vault.corpus / f"{BASENAME}.md"
        self.note_path.write_text(f"{FRONTMATTER}\n{LINK_LINE}\n", encoding="utf-8")

    def extract(self, *flags: str) -> CapturedRun:
        return CapturedRun(["extract", f"{BASENAME}.pdf", *flags]).go()

    def test_extract_exits_one_when_no_scope_is_given(self) -> None:
        self.assertEqual(USAGE_EXIT, self.extract().code)

    def test_the_refusal_names_the_scope_flags_and_the_scope_subcommand(self) -> None:
        errors = self.extract().errors
        self.assertEqual((True, True), ("--exclude-nothing" in errors, "run scope first" in errors))

    def test_extract_exits_one_on_a_point_that_opens_no_line_before_converting(self) -> None:
        self.assertEqual(USAGE_EXIT, self.extract("--exclude", "1", "2: Epilogue").code)

    def test_extract_exits_one_on_a_span_resuming_before_it_starts(self) -> None:
        self.assertEqual(USAGE_EXIT, self.extract("--exclude", "3", "2").code)

    def test_a_refused_scope_leaves_the_corpus_file_untouched(self) -> None:
        before = self.note_path.read_text(encoding="utf-8")
        self.extract("--exclude", "1", "2: Epilogue")
        self.assertEqual(before, self.note_path.read_text(encoding="utf-8"))


class TestScopeListing(ExtractVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.library / f"{BASENAME}.pdf", SCOPE_PAGES, SCOPE_OUTLINE).write()
        self.note_path = self.vault.corpus / f"{BASENAME}.md"
        self.note_path.write_text(f"{FRONTMATTER}\n{LINK_LINE}\n", encoding="utf-8")
        self.listing = json.loads(CapturedRun(["scope", f"{BASENAME}.pdf"]).go().output)

    def test_each_outline_section_is_listed_by_file_page_and_title(self) -> None:
        self.assertEqual(["3: Introduction", "6: Chapter One"],
                         [section["entry"] for section in self.listing["sections"]])

    def test_a_section_runs_to_the_page_before_the_next_and_the_last_to_the_end(self) -> None:
        self.assertEqual([(3, 5), (6, 10)],
                         [(section["first_page"], section["last_page"]) for section in self.listing["sections"]])

    def test_the_pages_to_judge_run_to_the_first_section_then_every_opening_and_the_last_three(self) -> None:
        self.assertEqual([1, 2, 3, 6, 8, 9, 10], [page["file_page"] for page in self.listing["pages"]])

    def test_every_page_to_judge_carries_its_render(self) -> None:
        self.assertTrue(all(Path(page["render"]).is_file() for page in self.listing["pages"]))

    def test_every_page_to_judge_carries_its_text_layer_lines(self) -> None:
        self.assertEqual(["Page 2 of the work, with words enough to measure."], self.listing["pages"][1]["lines"])

    def test_the_listing_writes_nothing_to_the_corpus_file(self) -> None:
        self.assertEqual(f"{FRONTMATTER}\n{LINK_LINE}\n", self.note_path.read_text(encoding="utf-8"))


class LinedPdf:
    def __init__(self, path: Path, lines: tuple[str, ...]) -> None:
        self._path = path
        self._lines = lines

    def write(self) -> Path:
        with pymupdf.open() as doc:
            page = doc.new_page()
            for row, text in enumerate(self._lines):
                page.insert_text((LEFT_MARGIN, FIRST_LINE_BASELINE + row * LINE_PITCH), text)
            doc.save(self._path)
        return self._path


class TestScopePoints(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        self.points = ScopePoints(TextLayer(LinedPdf(directory / "lined.pdf", LINED_PAGE).write()))

    def _excludes(self, start: str, resume: str, row: int) -> bool:
        baseline = FIRST_LINE_BASELINE + row * LINE_PITCH
        return self.points.spans([(start, resume)]).excludes(PagePlace(1, baseline))

    def test_a_span_from_the_page_top_to_a_mid_page_line_excludes_the_lines_above_it(self) -> None:
        self.assertTrue(self._excludes("1", "1: Abstract This paper", 0))

    def test_the_line_a_span_resumes_at_is_not_excluded(self) -> None:
        self.assertFalse(self._excludes("1: Abstract", "1: Even within the recent rebirth, again", 3))

    def test_a_point_matches_its_line_whatever_the_case_and_spacing(self) -> None:
        self.assertTrue(self._excludes("1:   abstract   THIS", "end", 1))

    def test_a_point_that_is_a_whole_line_names_it_though_it_opens_a_longer_one(self) -> None:
        self.assertTrue(self._excludes("1: I", "end", 4))

    def test_a_point_that_is_a_whole_line_leaves_the_longer_line_it_opens(self) -> None:
        self.assertFalse(self._excludes("1: I", "end", 0))

    def test_a_point_opening_two_lines_is_refused(self) -> None:
        with self.assertRaises(UnresolvedScopePoint):
            self.points.spans([("1: Even within", "end")])

    def test_a_point_outside_the_pdf_is_refused(self) -> None:
        with self.assertRaises(UnresolvedScopePoint):
            self.points.spans([("1", "7")])

    def test_a_point_in_no_recognized_form_is_refused(self) -> None:
        with self.assertRaises(UnresolvedScopePoint):
            self.points.spans([("the abstract", "end")])


class TestCorpusFileWrite(ExtractVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        pdf = TextPdf(self.vault.library / f"{BASENAME}.pdf").write()
        self.note_path = self.vault.corpus / f"{BASENAME}.md"
        self.note_path.write_text(f"{FRONTMATTER}\n{LINK_LINE}\n", encoding="utf-8")
        self.note = CorpusFile(pdf)

    def test_a_note_with_only_the_link_line_has_no_body(self) -> None:
        self.assertFalse(self.note.has_body())

    def test_the_write_keeps_the_frontmatter_and_adds_the_fields(self) -> None:
        self.note.write("# One\n\nProse.\n", {"extraction_mode": "text-layer"})
        text = self.note_path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\ntitle: A Work\ntype: book\nextraction_mode: text-layer\n---\n"))

    def test_the_write_keeps_the_link_line_before_the_body(self) -> None:
        self.note.write("# One\n\nProse.\n", {"extraction_mode": "text-layer"})
        self.assertIn(f"{LINK_LINE}\n\n# One\n\nProse.\n", self.note_path.read_text(encoding="utf-8"))

    def test_a_second_write_replaces_the_field_instead_of_repeating_it(self) -> None:
        self.note.write("Body.\n", {"extraction_mode": "text-layer"})
        self.note.write("Body.\n", {"extraction_mode": "forced-ocr"})
        text = self.note_path.read_text(encoding="utf-8")
        self.assertEqual(1, text.count("extraction_mode:"))
        self.assertIn("extraction_mode: forced-ocr", text)


class TestFrontmatterFields(unittest.TestCase):
    def test_a_field_without_a_value_is_removed(self) -> None:
        block = FrontmatterFields().upserted("---\ntitle: A\nextraction_mode: text-layer\n---\n",
                                             {"extraction_mode": None})
        self.assertEqual("---\ntitle: A\n---\n", block)

    def test_fields_are_inserted_before_the_closing_line(self) -> None:
        block = FrontmatterFields().upserted("---\ntitle: A\n---\n", {"extraction_mode": "text-layer"})
        self.assertEqual("---\ntitle: A\nextraction_mode: text-layer\n---\n", block)

    def test_a_longer_key_sharing_the_prefix_is_left_alone(self) -> None:
        block = FrontmatterFields().upserted("---\nextraction_mode_note: x\n---\n",
                                             {"extraction_mode": "forced-ocr"})
        self.assertEqual("---\nextraction_mode_note: x\nextraction_mode: forced-ocr\n---\n", block)

    def test_a_key_with_no_value_is_still_replaced(self) -> None:
        block = FrontmatterFields().upserted("---\nextraction_mode:\ntitle: A\n---\n",
                                             {"extraction_mode": "forced-ocr"})
        self.assertEqual("---\ntitle: A\nextraction_mode: forced-ocr\n---\n", block)


class TestFrontmatterBlockRequired(ExtractVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf = TextPdf(self.vault.library / f"{BASENAME}.pdf").write()
        self.note_path = self.vault.corpus / f"{BASENAME}.md"
        self.note_path.write_text(f"{LINK_LINE}\n", encoding="utf-8")

    def test_probe_exits_one_when_the_note_has_no_frontmatter_block(self) -> None:
        run = CapturedRun(["probe", f"{BASENAME}.pdf"]).go()
        self.assertEqual((USAGE_EXIT, True), (run.code, "no frontmatter block" in run.errors))

    def test_a_note_without_a_frontmatter_block_is_never_written(self) -> None:
        with self.assertRaises(NoteMissing):
            CorpusFile(self.pdf).write("Body.\n", {})
        self.assertEqual(f"{LINK_LINE}\n", self.note_path.read_text(encoding="utf-8"))


class TestPageRanges(unittest.TestCase):
    def test_ranges_and_single_pages_are_expanded_and_sorted(self) -> None:
        self.assertEqual([3, 5, 6, 7, 12], PageRanges().parse("12,5-7, 3"))

    def test_consecutive_pages_are_compacted_into_ranges(self) -> None:
        self.assertEqual("1-3,5", PageRanges().compact([3, 1, 5, 2]))

    def test_no_ranges_give_no_pages(self) -> None:
        self.assertEqual([], PageRanges().parse(None))


class TestReadingsFile(unittest.TestCase):
    def setUp(self) -> None:
        self._root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._root, True)

    def test_a_missing_readings_file_is_malformed_not_a_traceback(self) -> None:
        with self.assertRaises(MalformedReadings):
            WorkerReadings.load(self._root / "absent.json")

    def test_a_non_json_readings_file_is_malformed(self) -> None:
        path = self._root / "readings.json"
        path.write_text("not json", encoding="utf-8")
        with self.assertRaises(MalformedReadings):
            WorkerReadings.load(path)

    def test_an_unreadable_reading_carries_no_text(self) -> None:
        path = self._root / "readings.json"
        path.write_text('[{"page": 4, "unreadable": true}]', encoding="utf-8")
        reading = WorkerReadings.load(path).for_page(4)
        self.assertEqual((True, None), (reading.unreadable, reading.text))


BLANK_PAGES = 2
GOOD_LABEL = "good"
BAD_LABEL = "bad"


class FakeModels:
    def __init__(self, label: str) -> None:
        self._label = label

    def ocr_error_model(self) -> FakePredictor:
        return FakePredictor(self._label)


class FakePlan:
    def __init__(self, page_count: int, label: str, pixel_pages: set[int]) -> None:
        self._blocks = DocumentBlocks([PageBlocks(page, []) for page in range(1, page_count + 1)])
        self._pixel_pages = pixel_pages
        self.models = FakeModels(label)
        self.mode = "text-layer"

    def reads_pixels(self, file_page: int) -> bool:
        return file_page in self._pixel_pages

    def blocks(self, page_count: int) -> DocumentBlocks:
        return self._blocks


class BlankPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as doc:
            for _number in range(BLANK_PAGES):
                doc.new_page()
            doc.save(self._path)
        return self._path


class TestPageCheckRouting(ExtractVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf = BlankPdf(self.vault.library / f"{BASENAME}.pdf").write()
        (self.vault.corpus / f"{BASENAME}.md").write_text(f"{FRONTMATTER}\n{LINK_LINE}\n", encoding="utf-8")

    def _verdicts(self, label: str, pixel_pages: set[int], readings: list[Reading]) -> dict:
        plan = FakePlan(BLANK_PAGES, label, pixel_pages)
        inputs = BuildInputs(self.pdf, CorpusFile(self.pdf), plan, WorkerReadings(readings), ExcludedSpans.none())
        build = CorpusBuild(inputs)
        return {verdict.file_page: verdict for verdict in build.verdicts()}

    def test_a_scanned_page_extracted_without_force_ocr_is_doubtful_naming_the_flag(self) -> None:
        verdict = self._verdicts(GOOD_LABEL, set(), [])[1]
        self.assertEqual((True, "no text layer and no output: pass --force-ocr"),
                         (verdict.is_doubtful, verdict.reason))

    def test_a_page_read_from_pixels_into_no_text_is_doubtful_for_its_empty_reading(self) -> None:
        verdict = self._verdicts(GOOD_LABEL, {1, 2}, [])[1]
        self.assertEqual((True, REASON_EMPTY_PIXELS), (verdict.is_doubtful, verdict.reason))

    def test_a_transcription_that_passes_the_checks_is_kept(self) -> None:
        verdict = self._verdicts(GOOD_LABEL, set(), [Reading(1, PROSE)])[1]
        self.assertEqual(("kept", "worker transcription"), (verdict.status, verdict.reason))

    def test_a_transcription_the_classifier_calls_bad_is_doubtful_again(self) -> None:
        verdict = self._verdicts(BAD_LABEL, set(), [Reading(1, PROSE * 2)])[1]
        self.assertEqual(True, verdict.is_doubtful)
        self.assertIn("classifier reads the page as bad", verdict.reason)

    def test_an_unreadable_verdict_still_omits_the_page(self) -> None:
        self.assertEqual("omitted", self._verdicts(GOOD_LABEL, set(), [Reading(1, None)])[1].status)


class TestRepairRecordKey(unittest.TestCase):
    def test_the_clean_stage_writes_the_key_under_the_name_prefix_the_extract_stage_reads_without(self) -> None:
        self.assertEqual(fontrepair.RECORD_KEY, "/" + repairs.RECORD_KEY)


if __name__ == "__main__":
    unittest.main()
