from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract.backfillrunner import ScriptRun
from test_extract_backfill_driver import LISTED_PAGES, PAGE_COUNT, BackfillCase, StubScript, called_commands, listing

NOTE_OF_TYPE = "---\ntitle: A Work\ntype: {item_type}\n---\n"


def without_outline(test: unittest.TestCase, item_type: str = "manuscript") -> BackfillCase:
    corpus_file = Path(test.enterContext(tempfile.TemporaryDirectory())) / "Author - 2000 - Work.md"
    corpus_file.write_text(NOTE_OF_TYPE.format(item_type=item_type), encoding="utf-8")
    probe = {"headings": [], "page_count": PAGE_COUNT, "corpus_file": str(corpus_file)}
    scope = listing(LISTED_PAGES)
    return BackfillCase(test, StubScript({"probe": ScriptRun(0, json.dumps(probe)), "scope": ScriptRun(0, json.dumps(scope))}))


class TestAFiledWorkWithoutAnOutline(unittest.TestCase):
    def test_the_preparation_asks_for_the_bookmarker(self) -> None:
        outcome = without_outline(self).invoke("prep", fonts_checked=True)
        self.assertEqual(("unbookmarked", False), (outcome["state"], outcome["pixels_only"]))

    def test_a_book_without_an_outline_is_bookmarked_as_a_book(self) -> None:
        self.assertEqual("book", without_outline(self, "book").invoke("prep", fonts_checked=True)["kind"])

    def test_a_paper_without_an_outline_is_bookmarked_as_an_article(self) -> None:
        self.assertEqual("article", without_outline(self, "conferencePaper").invoke("prep", fonts_checked=True)["kind"])

    def test_the_bookmarker_is_told_the_text_layer_the_work_reads_from_pixels(self) -> None:
        outcome = without_outline(self).invoke("prep", fonts_checked=True, pixels_only=True)
        self.assertTrue(outcome["pixels_only"])

    def test_a_work_recorded_as_one_chapter_is_converted_without_an_outline(self) -> None:
        case = without_outline(self)
        outcome = case.invoke("prep", fonts_checked=True, one_chapter=True)
        self.assertEqual(("ready", ["probe", "convert", "scope"]), (outcome["state"], called_commands(case)))

    def test_the_one_chapter_record_survives_a_later_preparation(self) -> None:
        case = without_outline(self)
        case.invoke("prep", fonts_checked=True, one_chapter=True)
        self.assertEqual("ready", case.invoke("prep")["state"])


if __name__ == "__main__":
    unittest.main()
