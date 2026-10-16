from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.cleanuppages import (
    FLAG_BARE_NUMERAL,
    FLAG_BROKEN_PARAGRAPH,
    FLAG_EDGE_LINE,
    FLAG_ENTRY_LIST,
    FLAG_FOOT_NOTE,
    FLAG_FOOTNOTE_LOG,
    CleanupPages,
    pages_running_on,
)

PROSE = "A paragraph of plain prose that ends as a sentence does."


def flagged(slices: dict[int, str], report: dict | None = None) -> dict[int, list[str]]:
    return CleanupPages(slices, report or {}).flagged()


class TestPagesTheCleanupReads(unittest.TestCase):
    def test_a_page_of_plain_prose_is_never_listed(self) -> None:
        self.assertEqual({}, flagged({1: PROSE, 2: PROSE}))

    def test_every_page_of_an_entry_list_is_listed_until_the_next_heading(self) -> None:
        pages = {1: PROSE, 2: f"# Bibliography\n\n{PROSE}", 3: PROSE, 4: f"# Index of Names\n\n{PROSE}"}
        self.assertEqual([2, 3], [page for page, flags in flagged(pages).items() if FLAG_ENTRY_LIST in flags])

    def test_a_page_the_footnote_log_names_is_listed(self) -> None:
        report = {"footnote_log": ["file p. 2: mark 3 left in place"]}
        self.assertEqual({2: [FLAG_FOOTNOTE_LOG]}, flagged({1: PROSE, 2: PROSE}, report))

    def test_a_paragraph_running_on_across_a_running_head_is_listed(self) -> None:
        pages = {1: "A sentence that breaks off at the foot of the page with exam-",
                 2: "THE WORK\n\nination of the rest."}
        self.assertIn(FLAG_BROKEN_PARAGRAPH, flagged(pages)[2])

    def test_a_paragraph_already_running_on_across_its_page_marker_is_never_listed(self) -> None:
        body = "%% file p. 1 %%\n\nA sentence that runs on, %% file p. 2 %% across the page break as one."
        pages = {1: "A sentence that runs on,", 2: "across the page break as one."}
        self.assertEqual({}, CleanupPages(pages, {}, pages_running_on(body)).flagged())

    def test_a_short_line_at_the_edge_of_three_pages_is_listed(self) -> None:
        pages = {page: f"Running Head {page}\n\n{PROSE}" for page in (1, 2, 3)}
        self.assertTrue(all(FLAG_EDGE_LINE in flags for flags in flagged(pages).values()))

    def test_a_bare_numeral_paragraph_is_listed(self) -> None:
        self.assertEqual({1: [FLAG_BARE_NUMERAL]}, flagged({1: f"{PROSE}\n\n217"}))

    def test_a_numbered_paragraph_closing_the_page_is_listed(self) -> None:
        self.assertEqual({1: [FLAG_FOOT_NOTE]}, flagged({1: f"{PROSE}\n\n3 See the second chapter."}))


if __name__ == "__main__":
    unittest.main()
