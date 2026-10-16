from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pymupdf

from _extract.cli import main
from _extract.matter import MAX_WHOLE_MATTER_RUN
from _vaults import LinedPdf, TempVault

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
NOTE_TEXT = "---\ntitle: A Work\ntype: book\n---\n\n[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)\n"
PROSE = ["The argument of the work runs on across this page,", "and the next line carries it further still."]
CONTENTS = ["Contents", "Introduction 1", "Chapter One 9", "Index 30"]
ACKNOWLEDGEMENTS = ["Acknowledgements", "The author thanks the library for its help."]


def prose_pages(count: int) -> list[list[str]]:
    return [PROSE] * count


class ScopedPdfCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        (self.vault.corpus / f"{BASENAME}.md").write_text(NOTE_TEXT, encoding="utf-8")
        self.pdf_path = self.vault.library / f"{BASENAME}.pdf"

    def listed_pages(self, pages: list[list[str]], outline: list) -> list[int]:
        LinedPdf(self.pdf_path, pages, outline).write()
        return self.listing()

    def listing(self) -> list[int]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            main(["scope", f"{BASENAME}.pdf"])
        return [page["file_page"] for page in json.loads(output.getvalue())["pages"]]


class TestFrontAndBackMatterListedWhole(ScopedPdfCase):
    OUTLINE = [[1, "Title Page", 1], [1, "Copyright", 2], [1, "Contents", 4], [1, "Introduction", 7],
               [1, "Chapter One", 12], [1, "Index", 26]]

    def setUp(self) -> None:
        super().setUp()
        self.listed = self.listed_pages(prose_pages(30), self.OUTLINE)

    def test_every_page_from_the_first_up_to_the_first_content_section_is_listed(self) -> None:
        self.assertEqual(list(range(1, 8)), [page for page in self.listed if page <= 7])

    def test_every_page_from_the_last_content_sections_end_to_the_end_of_the_pdf_is_listed(self) -> None:
        self.assertEqual(list(range(25, 31)), [page for page in self.listed if page >= 25])

    def test_the_content_between_is_listed_only_at_its_section_openings(self) -> None:
        self.assertEqual([12], [page for page in self.listed if 7 < page < 25])


class NulPaddedOutlinePdf(LinedPdf):
    PADDED_TITLE = "<FEFF" + ("Contents" + "\x00" * 6).encode("utf-16-be").hex().upper() + ">"

    def write(self) -> Path:
        super().write()
        with pymupdf.open(self._path) as doc:
            contents_entry = next(entry for entry in doc.get_toc(simple=False) if entry[1] == "Contents")
            doc.xref_set_key(contents_entry[3]["xref"], "Title", self.PADDED_TITLE)
            doc.saveIncr()
        return self._path


class TestOutlineTitlesPaddedWithControlCharacters(ScopedPdfCase):
    OUTLINE = [[1, "Preface", 2], [1, "Contents", 5], [1, "Chapter One", 9]]

    def test_a_padded_front_matter_title_still_ends_the_front_matter_where_content_follows_it(self) -> None:
        NulPaddedOutlinePdf(self.pdf_path, prose_pages(30), self.OUTLINE).write()
        self.assertEqual(list(range(1, 10)), [page for page in self.listing() if page <= 9])


class TestFrontMatterRunAtTheCap(ScopedPdfCase):
    def test_a_run_of_as_many_pages_as_the_cap_is_listed_whole(self) -> None:
        opening = MAX_WHOLE_MATTER_RUN
        outline = [[1, "Contents", 2], [1, "Introduction", opening]]
        listed = self.listed_pages(prose_pages(3 * opening), outline)
        self.assertEqual(list(range(1, opening + 1)), [page for page in listed if page <= opening])


class TestFrontMatterRunPastTheCap(ScopedPdfCase):
    OPENING = MAX_WHOLE_MATTER_RUN + 1
    CONTENTS_PAGES = range(2, 6)
    ACKNOWLEDGEMENTS_PAGE = 12

    def setUp(self) -> None:
        super().setUp()
        pages = prose_pages(3 * self.OPENING)
        for file_page in self.CONTENTS_PAGES:
            pages[file_page - 1] = CONTENTS
        pages[self.ACKNOWLEDGEMENTS_PAGE - 1] = ACKNOWLEDGEMENTS
        outline = [[1, "Contents", 2], [1, "Introduction", self.OPENING]]
        self.listed = [page for page in self.listed_pages(pages, outline) if page <= self.OPENING]

    def test_the_run_lists_its_edges_and_every_page_where_the_first_lines_change_kind(self) -> None:
        self.assertEqual([1, 2, 6, self.ACKNOWLEDGEMENTS_PAGE, self.ACKNOWLEDGEMENTS_PAGE + 1, self.OPENING],
                         self.listed)


if __name__ == "__main__":
    unittest.main()
