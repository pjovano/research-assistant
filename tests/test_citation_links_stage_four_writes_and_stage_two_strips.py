from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import citation_link
import vault

from _cite.linking import EntryLine
from _extract.acceptance import unlinked

ENTRY = "Roe, R. 2001. Another Work. Oxford: Clarendon."
HELD_WORK = "Roe - 2001 - Another Work"


class TestACitationLinkStageFourWrites(unittest.TestCase):
    def setUp(self) -> None:
        self.linked = EntryLine(0, ENTRY).linked_to(_HeldWork()).text

    def test_the_shared_pattern_names_the_held_work(self) -> None:
        self.assertEqual(HELD_WORK, citation_link.CITATION_LINK_RE.search(self.linked).group("work"))

    def test_stage_four_reads_its_own_link_back(self) -> None:
        self.assertEqual((HELD_WORK, ENTRY),
                         (EntryLine(0, self.linked).linked_basename, EntryLine(0, self.linked).entry))

    def test_accept_strips_the_link_stage_four_writes(self) -> None:
        self.assertEqual(ENTRY, unlinked(self.linked))

    def test_the_link_carries_the_citation_mark(self) -> None:
        self.assertIn(vault.CITATION_LINK_MARK, self.linked)


class _HeldWork:
    basename = HELD_WORK


if __name__ == "__main__":
    unittest.main()
