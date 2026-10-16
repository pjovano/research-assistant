from __future__ import annotations

import unittest

from _correction_fixtures import CorrectedBody, FakeLayer

from _extract.correctionrun import APPLIED, REFUSED, STALE

TO_HEADING = {"op": "role", "page": 3, "anchor": "Bold Line Of Text", "to": "heading", "level": 2}
FRESH_NOTE = {"op": "to-note", "page": 3, "anchor": "3 A note the engine left in the body"}
PAIR = {"op": "pair", "page": 2, "mark": "2", "anchor": "The first note's text as the page prints"}
RESTORE = {"op": "restore", "page": 3, "lines": [1, 2], "anchor": "The third page raises a mark that no note"}


class TestRole(unittest.TestCase):
    def test_a_bold_line_becomes_a_heading_at_its_level(self) -> None:
        self.assertIn("\n\n## Bold Line Of Text\n\n", CorrectedBody().rendered(TO_HEADING))

    def test_a_line_already_in_its_role_is_stale(self) -> None:
        self.assertEqual(STALE, CorrectedBody().outcome(TO_HEADING, TO_HEADING))

    def test_an_outline_heading_never_changes_its_role(self) -> None:
        demote = {"op": "role", "page": 1, "anchor": "Introduction", "to": "paragraph"}
        self.assertEqual(REFUSED, CorrectedBody().outcome(demote))

    def test_a_line_carrying_a_note_mark_never_becomes_a_heading(self) -> None:
        promote = {**TO_HEADING, "anchor": "The third page raises a mark that no note answers yet.[^4]"}
        self.assertEqual(REFUSED, CorrectedBody().outcome(promote))


class TestToNote(unittest.TestCase):
    def test_a_paragraph_opening_with_its_printed_key_becomes_a_fresh_note(self) -> None:
        rendered = CorrectedBody().rendered(FRESH_NOTE)
        self.assertTrue(rendered.endswith("[^3]: 3 A note the engine left in the body that the page prints at its "
                                          "foot."))

    def test_a_paragraph_becomes_the_note_of_an_unanswered_mark(self) -> None:
        rendered = CorrectedBody().rendered({**FRESH_NOTE, "mark": "4"})
        self.assertIn("[^4]: 3 A note the engine left", rendered)
        self.assertNotIn("\n\n3 A note the engine left", rendered)

    def test_a_mark_raised_nowhere_near_the_page_is_refused(self) -> None:
        self.assertEqual(REFUSED, CorrectedBody().outcome({**FRESH_NOTE, "mark": "9"}))

    def test_an_unmarked_paragraph_without_a_printed_key_is_refused(self) -> None:
        unkeyed = {"op": "to-note", "page": 2, "anchor": "A displaced paragraph that the page prints last"}
        self.assertEqual(REFUSED, CorrectedBody().outcome(unkeyed))


class TestPair(unittest.TestCase):
    def test_a_mark_and_its_note_swap_labels_with_the_note_it_led_to(self) -> None:
        rendered = CorrectedBody().rendered(PAIR)
        self.assertIn("[^2]: The first note's text", rendered)
        self.assertIn("[^1]: The second note's text", rendered)

    def test_a_mark_already_leading_to_its_note_is_stale(self) -> None:
        self.assertEqual(STALE, CorrectedBody().outcome(PAIR, PAIR))


class TestRestore(unittest.TestCase):
    def test_lost_lines_are_copied_from_the_text_layer_after_the_anchor(self) -> None:
        rendered = CorrectedBody().rendered(RESTORE)
        self.assertIn("answers yet.[^4]\n\nA line the trial lost ends with a broken hyph-enated word", rendered)

    def test_a_line_end_hyphen_goes_where_the_work_prints_the_word_whole(self) -> None:
        rendered = CorrectedBody().rendered({**RESTORE, "lines": [3, 4]})
        self.assertIn("breaks the word examination at its end.", rendered)

    def test_text_the_page_already_holds_is_stale(self) -> None:
        self.assertEqual(STALE, CorrectedBody().outcome(RESTORE, RESTORE))

    def test_a_page_drawing_no_text_layer_restores_nothing(self) -> None:
        layer = FakeLayer(undrawn=frozenset({3}))
        self.assertEqual(REFUSED, CorrectedBody(layer=layer).outcome(RESTORE))

    def test_lines_outside_the_page_are_refused(self) -> None:
        self.assertEqual(REFUSED, CorrectedBody().outcome({**RESTORE, "lines": [3, 9]}))

    def test_restored_letters_are_the_only_letters_the_body_gains(self) -> None:
        self.assertEqual(APPLIED, CorrectedBody().outcome(RESTORE))


if __name__ == "__main__":
    unittest.main()
