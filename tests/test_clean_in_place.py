from __future__ import annotations

import contextlib
import json
import re
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pymupdf
import vault
from _clean import cleaning
from _clean.analysis import PdfAnalysis
from _clean.cleaning import InPlaceClean
from _clean.commands import CleanCommands, PageCommands, TocCommands, VolumeCommands
from _clean.covers import CoverImage
from _clean.paths import PdfLocation
from _clean.repair import QpdfRepair
from _clean.verification import GuttingCheck
from _font_fixtures import SilentCommand, VaultTestCase
from _vaults import DEFAULT_PAGES, PATCHED_DIRS, TEXT_ORIGIN, TempVault, TextPdf

HIGHLIGHT_RECT = (70, 90, 300, 110)
WHOLE_SUFFIX = ".whole.pdf"
COVER_PIXELS = pymupdf.IRect(0, 0, 20, 30)
OPAQUE = 0
DAMAGED_PREFIX_BYTES = 128
BROKEN_OFFSET_RE = re.compile(rb"startxref\s+\d+")
BROKEN_OFFSET = b"startxref\n999999"


def page_count_of(pdf_path: Path) -> int:
    with pymupdf.open(pdf_path) as doc:
        return doc.page_count


class BlankImage:
    def __init__(self, pixels: pymupdf.IRect = COVER_PIXELS) -> None:
        self._pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixels, OPAQUE)

    def save(self, path: Path) -> Path:
        self._pixmap.save(path)
        return path

    def png_bytes(self) -> bytes:
        return self._pixmap.tobytes("png")


class Highlights:
    def __init__(self, path: Path) -> None:
        self._path = path

    def add_one(self) -> None:
        with pymupdf.open(self._path) as doc:
            doc[0].add_highlight_annot(pymupdf.Rect(*HIGHLIGHT_RECT))
            doc.saveIncr()

    def count(self) -> int:
        with pymupdf.open(self._path) as doc:
            return sum(1 for _ in doc[0].annots())


class TruncatedPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        whole = TextPdf(self._path.with_suffix(WHOLE_SUFFIX)).write().read_bytes()
        self._path.write_bytes(whole[:DAMAGED_PREFIX_BYTES])
        return self._path


class RepairToACleanCopy:
    def __init__(self, src_path: Path) -> None:
        self._dest = src_path.with_suffix(".repaired.pdf")

    @property
    def destination(self) -> Path:
        return self._dest

    def run(self) -> None:
        TextPdf(self._dest).write()


class ImagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_image(page.rect, stream=BlankImage().png_bytes())
            doc.new_page().insert_text(TEXT_ORIGIN, "Body text.")
            doc.save(self._path)
        return self._path


class RejectingGuttingCheck:
    def __init__(self, src_path: Path, dest: Path) -> None:
        self._dest = dest

    def run(self) -> None:
        raise SystemExit(f"Refusing to keep {self._dest.name}: the pages lost their text.")


class TestInPlaceClean(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = TextPdf(self.vault.inbox / "work.pdf").write()
        Highlights(self.pdf_path).add_one()

    def test_the_inbox_file_loses_its_annotations(self) -> None:
        InPlaceClean(self.pdf_path).run()
        self.assertEqual(0, Highlights(self.pdf_path).count())

    def test_the_rewritten_file_keeps_its_name(self) -> None:
        InPlaceClean(self.pdf_path).run()
        self.assertTrue(self.pdf_path.is_file())

    def test_no_temporary_file_survives_the_rewrite(self) -> None:
        InPlaceClean(self.pdf_path).run()
        self.assertFalse(self.temporary_of(self.pdf_path).exists())


class TestRefusedClean(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = TextPdf(self.vault.inbox / "work.pdf").write()
        self.before = self.pdf_path.read_bytes()
        cleaning.GuttingCheck = RejectingGuttingCheck
        self.addCleanup(setattr, cleaning, "GuttingCheck", GuttingCheck)

    def _refuse(self) -> None:
        with self.assertRaises(SystemExit):
            InPlaceClean(self.pdf_path).run()

    def test_the_original_stays_byte_identical(self) -> None:
        self._refuse()
        self.assertEqual(self.before, self.pdf_path.read_bytes())

    def test_no_temporary_file_is_left_behind(self) -> None:
        self._refuse()
        self.assertFalse(self.temporary_of(self.pdf_path).exists())


class TestDamagedFileRoutedToRepair(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = TruncatedPdf(self.vault.inbox / "damaged.pdf").write()

    def _refusal(self) -> str:
        with self.assertRaises(SystemExit) as raised:
            InPlaceClean(self.pdf_path).run()
        return str(raised.exception)

    def test_the_refusal_says_the_file_could_not_be_repaired(self) -> None:
        self.assertIn("could not repair", self._refusal())

    def test_the_refusal_names_qpdf_as_the_repair_tool(self) -> None:
        self.assertIn("qpdf", self._refusal())

    def test_the_refusal_names_the_damaged_file(self) -> None:
        self.assertIn(self.pdf_path.name, self._refusal())

    def test_the_damaged_file_is_left_where_it_was(self) -> None:
        self._refusal()
        self.assertTrue(self.pdf_path.is_file())

    def test_no_temporary_file_is_left_behind(self) -> None:
        self._refusal()
        self.assertFalse(self.temporary_of(self.pdf_path).exists())


class TestDamagedFileRepaired(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = TruncatedPdf(self.vault.inbox / "damaged.pdf").write()
        cleaning.QpdfRepair = RepairToACleanCopy
        self.addCleanup(setattr, cleaning, "QpdfRepair", QpdfRepair)

    def test_the_gutting_check_runs_against_the_repaired_copy(self) -> None:
        cleaner = InPlaceClean(self.pdf_path)
        cleaner.run()
        self.assertTrue(cleaner.repaired_with_qpdf())

    def test_the_inbox_file_is_the_cleaned_repaired_copy(self) -> None:
        InPlaceClean(self.pdf_path).run()
        self.assertEqual(DEFAULT_PAGES, page_count_of(self.pdf_path))

    def test_the_repaired_copy_is_deleted_after_the_clean(self) -> None:
        InPlaceClean(self.pdf_path).run()
        self.assertFalse(RepairToACleanCopy(self.pdf_path).destination.exists())

    def test_the_repaired_copy_is_deleted_when_the_clean_is_refused(self) -> None:
        cleaning.GuttingCheck = RejectingGuttingCheck
        self.addCleanup(setattr, cleaning, "GuttingCheck", GuttingCheck)
        with contextlib.suppress(SystemExit):
            InPlaceClean(self.pdf_path).run()
        self.assertFalse(RepairToACleanCopy(self.pdf_path).destination.exists())


class TestAddCoverOnce(VaultTestCase):
    def test_an_image_only_first_page_refuses_a_second_cover(self) -> None:
        covered = ImagePdf(self.vault.inbox / "covered.pdf").write()
        with self.assertRaises(SystemExit) as raised:
            PdfAnalysis(covered).require_no_cover()
        self.assertIn("--force", str(raised.exception))

    def test_a_text_first_page_admits_a_cover(self) -> None:
        plain = TextPdf(self.vault.inbox / "plain.pdf").write()
        self.assertIsNone(PdfAnalysis(plain).require_no_cover())


class TestPdfLocationAnywhere(VaultTestCase):
    def _place(self, directory: Path, name: str) -> Path:
        path = directory / name
        path.write_bytes(b"%PDF-1.7\n")
        return path

    def test_the_inbox_copy_outranks_the_library_copy(self) -> None:
        wanted = self._place(self.vault.inbox, "work.pdf")
        self._place(self.vault.library, "work.pdf")
        self.assertEqual(wanted, PdfLocation("work.pdf").anywhere())

    def test_a_pdf_only_in_the_library_is_found(self) -> None:
        wanted = self._place(self.vault.library, "work.pdf")
        self.assertEqual(wanted, PdfLocation("work.pdf").anywhere())

    def test_a_pdf_only_among_the_volumes_is_found(self) -> None:
        wanted = self._place(self.vault.volumes, "work.pdf")
        self.assertEqual(wanted, PdfLocation("work.pdf").anywhere())

    def test_a_pdf_in_none_of_the_three_names_all_three(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            PdfLocation("work.pdf").anywhere()
        self.assertEqual("Not found in the inbox, the library, or the volumes: work.pdf",
                         str(raised.exception))


class TestGeometryCommandsStayInTheInbox(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library_pdf = TextPdf(self.vault.library / "filed.pdf").write()

    def test_drop_page_refuses_a_library_pdf(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            SilentCommand(PageCommands().drop_page).run(pdf="filed.pdf", page=1, apply=True)
        self.assertEqual("Not found in the inbox: filed.pdf", str(raised.exception))

    def test_a_refused_drop_leaves_the_library_pdf_whole(self) -> None:
        with self.assertRaises(SystemExit):
            SilentCommand(PageCommands().drop_page).run(pdf="filed.pdf", page=1, apply=True)
        self.assertEqual(DEFAULT_PAGES, page_count_of(self.library_pdf))

    def test_add_cover_refuses_a_library_pdf(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            SilentCommand(PageCommands().add_cover).run(pdf="filed.pdf", image="x.png", force=True,
                                                        crop_top=0.0, crop_bottom=0.0, apply=True)
        self.assertEqual("Not found in the inbox: filed.pdf", str(raised.exception))


class TestDropPage(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = TextPdf(self.vault.inbox / "work.pdf").write()
        self.drop = SilentCommand(PageCommands().drop_page)

    def _first_page_text(self) -> str:
        with pymupdf.open(self.pdf_path) as doc:
            return doc[0].get_text()

    def test_page_is_one_based_so_page_1_deletes_the_first_page(self) -> None:
        self.drop.run(pdf="work.pdf", page=1, apply=True)
        self.assertTrue(self._first_page_text().startswith("Page 2"))

    def test_the_last_page_is_numbered_by_the_page_count(self) -> None:
        self.drop.run(pdf="work.pdf", page=DEFAULT_PAGES, apply=True)
        self.assertEqual(DEFAULT_PAGES - 1, page_count_of(self.pdf_path))
        self.assertTrue(self._first_page_text().startswith("Page 1"))

    def test_page_0_is_out_of_range(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            self.drop.run(pdf="work.pdf", page=0, apply=True)
        self.assertIn("1-based", str(raised.exception))

    def test_a_refused_drop_deletes_nothing(self) -> None:
        with self.assertRaises(SystemExit):
            self.drop.run(pdf="work.pdf", page=0, apply=True)
        self.assertEqual(DEFAULT_PAGES, page_count_of(self.pdf_path))

    def test_a_dry_run_deletes_nothing(self) -> None:
        self.drop.run(pdf="work.pdf", page=1, apply=False)
        self.assertEqual(DEFAULT_PAGES, page_count_of(self.pdf_path))

    def test_the_plan_names_the_one_based_page_and_the_resulting_count(self) -> None:
        plan = json.loads(self.drop.run(pdf="work.pdf", page=2, apply=False))
        self.assertEqual({"drop_page": 2, "pages_before": DEFAULT_PAGES, "pages_after": DEFAULT_PAGES - 1}, plan)

    def test_the_report_names_the_one_based_page_dropped(self) -> None:
        report = json.loads(self.drop.run(pdf="work.pdf", page=2, apply=True))
        self.assertEqual({"dropped_page": 2, "pages_before": DEFAULT_PAGES, "pages_after": DEFAULT_PAGES - 1}, report)


class TestAddCoverPlan(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = TextPdf(self.vault.inbox / "book.pdf").write()
        self.image = BlankImage().save(self.vault.named("cover.png"))
        self.add = SilentCommand(PageCommands().add_cover)

    def _run(self, apply: bool) -> str:
        return self.add.run(pdf="book.pdf", image=str(self.image), force=True,
                            crop_top=0.0, crop_bottom=0.0, apply=apply)

    def test_a_dry_run_prepends_nothing(self) -> None:
        self._run(apply=False)
        self.assertEqual(DEFAULT_PAGES, page_count_of(self.pdf_path))

    def test_the_plan_names_the_file_the_image_and_the_resulting_count(self) -> None:
        plan = json.loads(self._run(apply=False))
        self.assertEqual({"add_cover": str(self.pdf_path), "image": str(self.image),
                          "pages_before": DEFAULT_PAGES, "pages_after": DEFAULT_PAGES + 1}, plan)

    def test_apply_prepends_the_cover(self) -> None:
        self._run(apply=True)
        self.assertEqual(DEFAULT_PAGES + 1, page_count_of(self.pdf_path))

    def test_the_report_names_the_covered_file(self) -> None:
        report = json.loads(self._run(apply=True))
        self.assertEqual(str(self.pdf_path), report["cover_added"])


class TestCoverImageTrim(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.image = BlankImage().save(self.vault.named("cover.png"))

    def test_an_untrimmed_cover_is_the_image_itself(self) -> None:
        self.assertEqual(self.image, CoverImage(self.image).trimmed(0.0, 0.0).path)

    def test_a_trimmed_cover_is_saved_under_the_scratch_directory(self) -> None:
        trimmed = CoverImage(self.image).trimmed(0.1, 0.0).path
        self.assertEqual((vault.SCRATCH_DIR / "cover.trimmed.png", True), (trimmed, trimmed.is_file()))


class TestPlanOverTheWholeInbox(VaultTestCase):
    def test_a_numbered_copy_beside_its_original_is_not_planned(self) -> None:
        TextPdf(self.vault.inbox / "work.pdf").write()
        TextPdf(self.vault.inbox / "work 2.pdf").write()
        printed = SilentCommand(CleanCommands().plan).run(all=True, pdf=None)
        self.assertEqual(["work.pdf"], [report["file"] for report in json.loads(printed)])


class TestVolumeMove(VaultTestCase):
    OUTLINE = [[1, "Chapter One", 1]]

    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = TextPdf(self.vault.inbox / "volume.pdf", outline=self.OUTLINE).write()
        self.move = SilentCommand(VolumeCommands().move)

    def test_a_bookmarked_inbox_pdf_lands_among_the_volumes(self) -> None:
        self.move.run(pdf="volume.pdf", apply=True)
        self.assertTrue((self.vault.volumes / "volume.pdf").is_file())

    def test_the_moved_pdf_leaves_the_inbox(self) -> None:
        self.move.run(pdf="volume.pdf", apply=True)
        self.assertFalse(self.pdf_path.exists())

    def test_the_report_names_the_destination(self) -> None:
        report = json.loads(self.move.run(pdf="volume.pdf", apply=True))
        self.assertEqual(str(self.vault.volumes / "volume.pdf"), report["moved"])

    def test_a_dry_run_moves_nothing(self) -> None:
        self.move.run(pdf="volume.pdf", apply=False)
        self.assertTrue(self.pdf_path.is_file())
        self.assertFalse((self.vault.volumes / "volume.pdf").exists())

    def test_the_plan_names_the_source_the_destination_and_the_page_count(self) -> None:
        plan = json.loads(self.move.run(pdf="volume.pdf", apply=False))
        self.assertEqual({"move": str(self.pdf_path), "to": str(self.vault.volumes / "volume.pdf"),
                          "pages": DEFAULT_PAGES}, plan)

    def test_a_name_already_among_the_volumes_is_refused(self) -> None:
        (self.vault.volumes / "volume.pdf").write_bytes(b"%PDF-1.7\n")
        with self.assertRaises(SystemExit) as raised:
            self.move.run(pdf="volume.pdf", apply=True)
        self.assertEqual("Already among the volumes: volume.pdf", str(raised.exception))

    def test_a_refused_move_leaves_the_inbox_file_in_place(self) -> None:
        (self.vault.volumes / "volume.pdf").write_bytes(b"%PDF-1.7\n")
        with self.assertRaises(SystemExit):
            self.move.run(pdf="volume.pdf", apply=True)
        self.assertTrue(self.pdf_path.is_file())

    def test_a_volume_with_no_outline_is_refused_because_its_bookmarks_are_its_contents(self) -> None:
        TextPdf(self.vault.inbox / "bare.pdf").write()
        with self.assertRaises(SystemExit) as raised:
            self.move.run(pdf="bare.pdf", apply=True)
        self.assertIn("carries no outline", str(raised.exception))

    def test_a_refused_volume_does_not_reach_the_volumes(self) -> None:
        TextPdf(self.vault.inbox / "bare.pdf").write()
        with self.assertRaises(SystemExit):
            self.move.run(pdf="bare.pdf", apply=True)
        self.assertFalse((self.vault.volumes / "bare.pdf").exists())


class TestTocWrite(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = TextPdf(self.vault.inbox / "article.pdf").write()
        self.entries_path = self.vault.named("entries.json")
        self.entries_path.write_text(json.dumps([{"level": 1, "title": "Section One", "page": 2}]),
                                     encoding="utf-8")
        self.write = SilentCommand(TocCommands().write)

    def _written_toc(self) -> list:
        with pymupdf.open(self.pdf_path) as doc:
            return doc.get_toc()

    def test_a_file_too_short_to_be_a_book_still_takes_an_outline(self) -> None:
        self.write.run(pdf="article.pdf", entries=[str(self.entries_path)], apply=True, force=False)
        self.assertEqual([[1, "Section One", 2]], self._written_toc())

    def test_a_dry_run_writes_no_outline(self) -> None:
        self.write.run(pdf="article.pdf", entries=[str(self.entries_path)], apply=False, force=False)
        self.assertEqual([], self._written_toc())

    def test_repeated_entries_files_are_joined_in_the_order_given(self) -> None:
        later_path = self.vault.named("later.entries.json")
        later_path.write_text(json.dumps([{"level": 1, "title": "Section Two", "page": 3}]), encoding="utf-8")
        self.write.run(pdf="article.pdf", entries=[str(self.entries_path), str(later_path)], apply=True, force=False)
        self.assertEqual([[1, "Section One", 2], [1, "Section Two", 3]], self._written_toc())


class BrokenCrossReferencePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        whole = TextPdf(self._path.with_suffix(WHOLE_SUFFIX)).write().read_bytes()
        self._path.write_bytes(BROKEN_OFFSET_RE.sub(BROKEN_OFFSET, whole))
        return self._path


class TestQpdfRepair(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS, "SCRATCH_DIR").activate()
        self.addCleanup(self.vault.discard)

    def test_a_broken_cross_reference_table_is_rebuilt_into_a_readable_copy(self) -> None:
        repair = QpdfRepair(BrokenCrossReferencePdf(self.vault.inbox / "broken.pdf").write())
        repair.run()
        self.assertEqual(DEFAULT_PAGES, page_count_of(repair.destination))

    def test_an_unrecoverable_file_leaves_no_partial_copy(self) -> None:
        repair = QpdfRepair(TruncatedPdf(self.vault.inbox / "damaged.pdf").write())
        with contextlib.suppress(SystemExit):
            repair.run()
        self.assertFalse(repair.destination.exists())


if __name__ == "__main__":
    unittest.main()
