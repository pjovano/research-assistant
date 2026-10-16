from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from page_marker import PageMarker


class TestPageMarker(unittest.TestCase):
    def test_a_page_with_a_folio_is_written_with_both_numbers(self) -> None:
        self.assertEqual("%% p. xiv (file p. 3) %%", PageMarker(3, "xiv").comment())

    def test_a_page_without_a_folio_is_written_with_its_file_page_alone(self) -> None:
        self.assertEqual("%% file p. 4 %%", PageMarker(4).comment())

    def test_a_marker_line_parses_back_to_its_page(self) -> None:
        for marker in (PageMarker(3, "xiv"), PageMarker(4)):
            with self.subTest(marker=marker):
                self.assertEqual(marker, PageMarker.parsed(marker.comment()))

    def test_a_prose_line_is_not_a_marker(self) -> None:
        self.assertIsNone(PageMarker.parsed("A sentence about p. 3 (file p. 4)."))

    def test_markers_inside_a_line_are_found_in_order(self) -> None:
        line = "runs %% p. 12 (file p. 20) %% across %% file p. 21 %% pages"
        self.assertEqual([PageMarker(20, "12"), PageMarker(21)], PageMarker.inline(line))


if __name__ == "__main__":
    unittest.main()

    def test_a_body_is_sliced_into_the_text_following_each_marker(self) -> None:
        body = "%% p. 1 (file p. 1) %%\nFirst page.\n\nRuns %% file p. 2 %% on.\n\n%% file p. 3 %%\nLast."
        self.assertEqual({1: "First page.\n\nRuns", 2: "on.", 3: "Last."}, PageMarker.sliced(body))

    def test_two_markers_of_one_page_join_their_text(self) -> None:
        body = "%% file p. 2 %%\nA note.\n%% file p. 2 %%\nIts continuation."
        self.assertEqual({2: "A note.\nIts continuation."}, PageMarker.sliced(body))

    def test_a_time_marker_is_written_as_the_time_alone(self) -> None:
        self.assertEqual("%% 01:02:03 %%", PageMarker(time="01:02:03").comment())

    def test_a_time_marker_line_parses_back_to_its_time_with_no_page(self) -> None:
        self.assertEqual(PageMarker(None, None, "00:12:34"), PageMarker.parsed("%% 00:12:34 %%"))

    def test_a_time_marker_holds_no_slice_of_file_pages(self) -> None:
        self.assertEqual({}, PageMarker.sliced("%% 00:00:00 %%\nSpoken words."))
