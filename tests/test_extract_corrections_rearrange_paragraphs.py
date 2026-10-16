from __future__ import annotations

import unittest

from _correction_fixtures import BODY, CorrectedBody

from _extract.correctionrun import APPLIED, REFUSED, STALE, UNMATCHED
from _extract.correctiontext import TrialText

SPLIT = {"op": "split", "page": 1, "anchor": "The second claim follows in the same paragraph"}
DROP_HEAD_2 = {"op": "drop", "page": 2, "text": "THE WORK"}
JOIN_ACROSS_PAGES = {"op": "join", "page": 2, "anchor": "ination of the evidence, which the reader follows",
                     "dehyphenate": True}
MOVE = {"op": "move", "page": 2, "anchor": "A displaced paragraph that the page prints last",
        "target_page": 2, "target_anchor": "The closing paragraph of the second page"}


class TestTheBodyModel(unittest.TestCase):
    def test_a_body_parsed_and_rendered_is_unchanged(self) -> None:
        self.assertEqual(BODY, TrialText.parsed(BODY).rendered())

    def test_a_paragraph_belongs_to_the_page_whose_marker_precedes_it(self) -> None:
        text = TrialText.parsed(BODY)
        closing = next(index for index, unit in enumerate(text.units) if unit.text.startswith("The closing"))
        self.assertEqual(frozenset({2}), text.pages()[closing])

    def test_a_mark_belongs_to_the_page_it_is_raised_on(self) -> None:
        self.assertEqual({"1": {2}, "2": {2}, "4": {3}}, TrialText.parsed(BODY).mark_pages())


class TestSplit(unittest.TestCase):
    def test_a_paragraph_breaks_before_its_anchor(self) -> None:
        rendered = CorrectedBody().rendered(SPLIT)
        self.assertIn("in full.\n\nThe second claim follows", rendered)

    def test_a_paragraph_already_opening_at_its_anchor_is_stale(self) -> None:
        self.assertEqual(STALE, CorrectedBody().outcome(SPLIT, SPLIT))

    def test_an_entry_list_breaks_into_one_entry_per_paragraph(self) -> None:
        rendered = CorrectedBody().rendered({"op": "split", "page": 3, "anchor": "Jones, B. (1991), Another Book on"})
        self.assertIn("London: Press.\n\nJones, B. (1991)", rendered)


class TestJoin(unittest.TestCase):
    def test_a_paragraph_rejoins_across_a_page_with_its_marker_after_the_rejoined_word(self) -> None:
        rendered = CorrectedBody().rendered(DROP_HEAD_2, JOIN_ACROSS_PAGES)
        self.assertIn("ends with examination %% p. 2 (file p. 2) %% of the evidence", rendered)

    def test_a_hyphen_stays_when_the_work_prints_the_rejoined_word_nowhere_else(self) -> None:
        body = BODY.replace("The examination of", "The study of")
        self.assertEqual(REFUSED, CorrectedBody(body).outcome(DROP_HEAD_2, JOIN_ACROSS_PAGES))

    def test_a_paragraph_already_running_on_is_stale(self) -> None:
        join = {"op": "join", "page": 1, "anchor": "The second claim follows in the same paragraph"}
        self.assertEqual(STALE, CorrectedBody().outcome(join))

    def test_a_heading_is_never_joined_to(self) -> None:
        join = {"op": "join", "page": 1, "anchor": "The opening paragraph states the first claim"}
        self.assertEqual(REFUSED, CorrectedBody().outcome(join))


class TestMove(unittest.TestCase):
    def test_a_paragraph_moves_after_its_target(self) -> None:
        rendered = CorrectedBody().rendered(MOVE)
        self.assertLess(rendered.index("The closing paragraph"), rendered.index("A displaced paragraph"))

    def test_a_paragraph_already_after_its_target_is_stale(self) -> None:
        self.assertEqual(STALE, CorrectedBody().outcome(MOVE, MOVE))

    def test_a_paragraph_never_moves_further_than_the_page_beside_it(self) -> None:
        far = {**MOVE, "page": 1, "anchor": "The second claim follows in the same paragraph", "target_page": 3,
               "target_anchor": "The third page raises a mark that no note answers"}
        self.assertEqual(REFUSED, CorrectedBody().outcome(SPLIT, far))

    def test_a_paragraph_crossing_a_page_never_moves(self) -> None:
        crossing = {**MOVE, "page": 1, "anchor": "The examination of the second claim runs across"}
        self.assertEqual(REFUSED, CorrectedBody().outcome(DROP_HEAD_2, JOIN_ACROSS_PAGES, crossing))


class TestDrop(unittest.TestCase):
    def test_a_running_head_recurring_at_the_edge_of_pages_is_dropped(self) -> None:
        rendered = CorrectedBody().rendered(DROP_HEAD_2)
        self.assertEqual(1, rendered.count("THE WORK"))

    def test_text_recurring_on_no_other_page_edge_is_never_dropped(self) -> None:
        drop = {"op": "drop", "page": 2, "text": "A displaced paragraph"}
        self.assertEqual(REFUSED, CorrectedBody().outcome(drop))

    def test_a_folio_is_dropped_without_recurring(self) -> None:
        body = BODY.replace("THE WORK\n\nination", "THE WORK\n\n17\n\nination")
        self.assertEqual(APPLIED, CorrectedBody(body).outcome({"op": "drop", "page": 2, "text": "17"}))

    def test_a_note_mark_is_never_dropped(self) -> None:
        drop = {"op": "drop", "page": 2, "text": "heading.[^2]"}
        self.assertEqual(REFUSED, CorrectedBody().outcome(drop))


class TestAnchors(unittest.TestCase):
    def test_an_anchor_matching_nothing_is_unmatched(self) -> None:
        self.assertEqual(UNMATCHED, CorrectedBody().outcome({**SPLIT, "anchor": "words the page never prints at all"}))

    def test_an_anchor_matching_twice_on_its_page_is_refused(self) -> None:
        body = BODY.replace("A displaced paragraph that the page prints last of all on its page.",
                            "The closing paragraph of the second page once more.")
        split = {"op": "split", "page": 2, "anchor": "The closing paragraph of the second page"}
        self.assertEqual(REFUSED, CorrectedBody(body).outcome(split))

    def test_a_short_anchor_naming_part_of_a_paragraph_is_refused(self) -> None:
        self.assertEqual(REFUSED, CorrectedBody().outcome({**SPLIT, "anchor": "The second claim"}))

    def test_an_anchor_on_another_page_is_unmatched(self) -> None:
        self.assertEqual(UNMATCHED, CorrectedBody().outcome({**SPLIT, "page": 2}))


if __name__ == "__main__":
    unittest.main()
