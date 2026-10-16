from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BODY_BOX, FOOT_BOX, BlockPlace, FakeFonts, FakeHyphens, FakeLayer, excluding
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Paragraph
from _extract.layerhtml import BlockHtml
from _extract.outline import Heading as OutlineHeading
from _extract.policy import SectionPolicy
from _extract.readings import WorkerReadings
from _extract.spans import PagePlace
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FIRST_ENTRY_BOX = (0.0, 20.0, 100.0, 30.0)
SECOND_ENTRY_BOX = (0.0, 40.0, 100.0, 50.0)
NOTES = "Notes"


def placed(kind: str, html: str, place: BlockPlace) -> Block:
    return place.block(kind, html)


def paragraph_texts(pages: list[PageBlocks], outline: list[OutlineHeading], policy: SectionPolicy) -> list[str]:
    work = WorkInputs(FakeLayer(), BlockHtml(FakeHyphens()), FakeFonts())
    inputs = StructureInputs(DocumentBlocks(pages), outline, WorkerReadings.none(), policy)
    return [element.text for element in NoteStructure(work, inputs).elements() if isinstance(element, Paragraph)]


class TestMarksOfWithheldNotes(unittest.TestCase):
    def test_the_mark_of_a_footnote_the_scope_excludes_is_dropped(self) -> None:
        page = PageBlocks(1, [placed(TEXT_KIND, "<p>The object is known<sup>31</sup> as it is.</p>",
                                     BlockPlace(BODY_BOX, 0, 1)),
                              placed(FOOTNOTE_KIND, "<p>31 I thank my colleagues.</p>", BlockPlace(FOOT_BOX, 1, 1))])
        texts = paragraph_texts([page], [], excluding(PagePlace(1, FOOT_BOX[1] - 1), PagePlace(2, 0.0)))
        self.assertEqual(["The object is known as it is."], texts)

    def test_the_mark_of_an_endnote_the_scope_excludes_is_dropped(self) -> None:
        texts = paragraph_texts(self._endnoted("19", "20"), [OutlineHeading(1, NOTES, 2, 0.0)],
                                excluding(PagePlace(2, SECOND_ENTRY_BOX[1] - 1), PagePlace(3, 0.0)))
        self.assertEqual(["Near oblivion.<sup>19</sup> Beyond it.", "19 A note."], texts)

    def test_an_endnote_mark_a_kept_entry_lists_stays(self) -> None:
        texts = paragraph_texts(self._endnoted("20", "20"), [OutlineHeading(1, NOTES, 2, 0.0)],
                                excluding(PagePlace(2, SECOND_ENTRY_BOX[1] - 1), PagePlace(3, 0.0)))
        self.assertIn("Near oblivion.<sup>19</sup> Beyond it.<sup>20</sup>", texts)

    @staticmethod
    def _endnoted(kept: str, excluded: str) -> list[PageBlocks]:
        body = "<p>Near oblivion.<sup>19</sup> Beyond it.<sup>20</sup></p>"
        return [PageBlocks(1, [placed(TEXT_KIND, body, BlockPlace(BODY_BOX, 0, 1))]),
                PageBlocks(2, [placed(TEXT_KIND, f"<p>{kept} A note.</p>", BlockPlace(FIRST_ENTRY_BOX, 0, 2)),
                               placed(TEXT_KIND, f"<p>{excluded} I thank my colleagues.</p>",
                                      BlockPlace(SECOND_ENTRY_BOX, 1, 2))])]


if __name__ == "__main__":
    unittest.main()
