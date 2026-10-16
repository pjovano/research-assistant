from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import excluding
from _extract.policy import SectionOpening, SectionPolicy
from _extract.blocks import TEXT_KIND, Block
from _extract.spans import PAGE_BOTTOM, ExcludedSpan, ExcludedSpans, PagePlace

ABSTRACT_TOP = 300.0
BODY_TOP = 520.0


class TestNoHeadingIsDroppedByItsTitle(unittest.TestCase):
    def _kept_after(self, title: str) -> bool:
        policy = SectionPolicy.keeping_everything()
        policy.opens(SectionOpening(1, title))
        return policy.keeps(PagePlace(1))

    def test_a_section_headed_contents_is_kept_unless_a_span_excludes_it(self) -> None:
        self.assertTrue(self._kept_after("Contents"))

    def test_a_section_headed_cover_is_kept_unless_a_span_excludes_it(self) -> None:
        self.assertTrue(self._kept_after("Cover"))

    def test_an_index_and_what_follows_it_are_kept_unless_a_span_excludes_them(self) -> None:
        self.assertTrue(self._kept_after("Index"))


class TestExcludedSpans(unittest.TestCase):
    def test_a_place_inside_a_span_is_not_kept(self) -> None:
        policy = excluding(PagePlace(1, ABSTRACT_TOP), PagePlace(1, BODY_TOP))
        self.assertFalse(policy.keeps(PagePlace(1, ABSTRACT_TOP + 1)))

    def test_the_page_above_a_span_that_opens_mid_page_is_kept(self) -> None:
        policy = excluding(PagePlace(1, ABSTRACT_TOP), PagePlace(1, BODY_TOP))
        self.assertTrue(policy.keeps(PagePlace(1, ABSTRACT_TOP - 1)))

    def test_the_resume_place_itself_is_kept(self) -> None:
        policy = excluding(PagePlace(1, ABSTRACT_TOP), PagePlace(1, BODY_TOP))
        self.assertTrue(policy.keeps(PagePlace(1, BODY_TOP)))

    def test_a_span_runs_across_pages(self) -> None:
        policy = excluding(PagePlace(2, BODY_TOP), PagePlace(5))
        self.assertEqual((False, False, True), (policy.keeps(PagePlace(3, ABSTRACT_TOP)),
                                                policy.keeps(PagePlace(4, PAGE_BOTTOM)), policy.keeps(PagePlace(5))))

    def test_a_page_is_kept_whole_unless_a_span_covers_all_of_it(self) -> None:
        policy = excluding(PagePlace(1, ABSTRACT_TOP), PagePlace(3))
        self.assertEqual((True, False, True), (policy.keeps_page(1), policy.keeps_page(2), policy.keeps_page(3)))


class TestBlocksUnderSpans(unittest.TestCase):
    def _kept(self, spans: list[tuple[float, float]], top: float, bottom: float) -> bool:
        policy = SectionPolicy(ExcludedSpans([ExcludedSpan(PagePlace(1, opens), PagePlace(1, closes))
                                              for opens, closes in spans]))
        return policy.keeps_block(Block(1, TEXT_KIND, "", (0.0, top, 100.0, bottom), {}, "/page/1/Text/0"))

    def test_a_block_the_spans_cover_most_of_is_dropped_though_none_holds_its_middle(self) -> None:
        self.assertFalse(self._kept([(20.0, 30.0), (40.0, 44.0), (56.0, 70.0)], 18.0, 72.0))

    def test_a_taller_block_the_same_spans_cover_little_of_is_kept(self) -> None:
        self.assertTrue(self._kept([(20.0, 30.0), (40.0, 44.0), (56.0, 70.0)], 0.0, 200.0))

    def test_a_block_whose_top_half_a_span_covers_is_dropped(self) -> None:
        self.assertFalse(self._kept([(0.0, 60.0)], 0.0, 100.0))

    def test_overlapping_spans_are_counted_once_over_a_block(self) -> None:
        self.assertTrue(self._kept([(0.0, 40.0), (10.0, 40.0), (20.0, 40.0)], 0.0, 100.0))

    def test_a_block_with_no_height_is_judged_by_its_middle(self) -> None:
        self.assertFalse(self._kept([(40.0, 60.0)], 50.0, 50.0))


class TestEntryListHeadings(unittest.TestCase):
    def _opened(self, title: str) -> SectionPolicy:
        policy = SectionPolicy.keeping_everything()
        policy.opens(SectionOpening(1, "Introduction"))
        policy.opens(SectionOpening(2, title))
        return policy

    def test_a_notes_heading_opens_an_entry_list(self) -> None:
        self.assertTrue(self._opened("Notes").in_entry_list)

    def test_a_title_merely_containing_notes_does_not(self) -> None:
        self.assertFalse(self._opened("Notes toward a Theory").in_entry_list)

    def test_a_notes_heading_marks_a_note_list(self) -> None:
        self.assertTrue(self._opened("Notes").in_note_list)

    def test_a_bibliography_is_an_entry_list_but_not_a_note_list(self) -> None:
        policy = self._opened("Bibliography")
        self.assertEqual((True, False), (policy.in_entry_list, policy.in_note_list))

    def test_a_note_list_holds_under_a_deeper_heading(self) -> None:
        policy = self._opened("Notes")
        policy.opens(SectionOpening(3, "Note on Translations"))
        self.assertTrue(policy.in_note_list)

    def _bibliography_with_a_sub_heading(self) -> SectionPolicy:
        policy = SectionPolicy.keeping_everything()
        policy.opens(SectionOpening(1, "Bibliography"))
        policy.opens(SectionOpening(2, "Works by Hegel"))
        return policy

    def test_a_sub_heading_inside_the_bibliography_keeps_the_reference_list_treatment(self) -> None:
        self.assertTrue(self._bibliography_with_a_sub_heading().in_entry_list)

    def test_an_index_heading_ends_the_reference_list_treatment(self) -> None:
        policy = self._bibliography_with_a_sub_heading()
        policy.opens(SectionOpening(1, "Index"))
        self.assertFalse(policy.in_entry_list)


if __name__ == "__main__":
    unittest.main()
