from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from cite import CONFIRM
from test_cite_links import CITING, CITING_FRONTMATTER, EARLIER, LINK_LINE, REVIEW_ENTRY, linked
from test_cite_links_settles_a_middle_band_match_by_its_recorded_verdict import VerdictTestCase

REPEATED_ENTRY_BODY = f"{LINK_LINE}\n\n# One\n\nProse.\n\n# Bibliography\n\n{REVIEW_ENTRY}\n\n{REVIEW_ENTRY}\n"
REPEATS = 2


class TestARepeatedEntryLinksOnEveryLine(VerdictTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER, REPEATED_ENTRY_BODY)

    def linked_lines(self) -> int:
        return self.note_text(CITING).count(linked(REVIEW_ENTRY, EARLIER))

    def test_each_repeat_of_an_unsettled_entry_is_reported(self) -> None:
        self.assertEqual([(REVIEW_ENTRY, EARLIER)] * REPEATS, self.offered())

    def test_one_confirm_verdict_links_every_repeat(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, CONFIRM)
        self.links().apply()
        self.assertEqual(REPEATS, self.linked_lines())

    def test_no_repeat_is_reported_once_the_verdict_confirms_it(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, CONFIRM)
        self.links().apply()
        self.assertEqual([], self.offered())

    def test_a_second_apply_adds_no_link_to_a_linked_repeat(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, CONFIRM)
        self.links().apply()
        self.links().apply()
        self.assertEqual(REPEATS, self.linked_lines())


if __name__ == "__main__":
    unittest.main()
