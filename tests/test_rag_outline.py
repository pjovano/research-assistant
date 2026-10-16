from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import rag
import vault
from _rag_chunks import BASENAME, LINK_LINE
from _vaults import TempVault

BODY = ("%% p. xi (file p. 12) %%\n\n# Preface\n\nThanks.\n\n%% p. 1 (file p. 20) %%\n\n# Part One\n\n"
        "## Chapter One\n\nBeing, %% p. 2 (file p. 21) %% pure being.\n\n%% p. 3 (file p. 22) %%\n\n"
        "### Becoming %% p. 4 (file p. 23) %%\n\nUnity.\n\n%% p. 9 (file p. 28) %%\n\n"
        "## Chapter Two\n\nQuantity.\n\n%% file p. 40 %%\n\n# Part Two\n\nEssence.\n")


def outline(body: str) -> list[dict]:
    return rag.CorpusOutline.entries(body)


def entry_named(body: str, path: str) -> dict:
    return next(entry for entry in outline(body) if entry["heading_path"] == path)


class TestHeadingTree(unittest.TestCase):
    def test_entries_come_in_document_order_with_their_levels(self) -> None:
        expected = [("Preface", 1), ("Part One", 1), ("Part One > Chapter One", 2),
                    ("Part One > Chapter One > Becoming", 3), ("Part One > Chapter Two", 2), ("Part Two", 1)]
        self.assertEqual(expected, [(entry["heading_path"], entry["level"]) for entry in outline(BODY)])

    def test_a_heading_takes_the_folio_and_file_page_in_force_where_it_stands(self) -> None:
        entry = entry_named(BODY, "Part One > Chapter Two")
        self.assertEqual(("9", 28), (entry["folio_first"], entry["file_page_first"]))

    def test_a_heading_with_no_marker_before_it_shares_the_folio_of_the_heading_above(self) -> None:
        part, chapter = entry_named(BODY, "Part One"), entry_named(BODY, "Part One > Chapter One")
        self.assertEqual((part["folio_first"], part["file_page_first"]),
                         (chapter["folio_first"], chapter["file_page_first"]))

    def test_a_section_runs_to_the_last_folio_printed_before_the_next_heading_at_its_level_or_above(self) -> None:
        self.assertEqual("9", entry_named(BODY, "Part One")["folio_last"])

    def test_a_section_reaches_the_page_its_successor_begins_on(self) -> None:
        self.assertEqual("9", entry_named(BODY, "Part One > Chapter One")["folio_last"])

    def test_an_inline_marker_on_a_heading_line_counts_for_the_section_it_opens(self) -> None:
        entry = entry_named(BODY, "Part One > Chapter One > Becoming")
        self.assertEqual(("3", "9"), (entry["folio_first"], entry["folio_last"]))

    def test_an_inline_marker_in_prose_advances_the_folio_of_every_open_section(self) -> None:
        body = "# One\n\n## Two\n\nA sentence %% p. 5 (file p. 6) %% runs on.\n"
        self.assertEqual(["5", "5"], [entry["folio_last"] for entry in outline(body)])

    def test_a_page_without_a_folio_yields_none_for_the_folio_and_its_file_page(self) -> None:
        entry = entry_named(BODY, "Part Two")
        self.assertEqual((None, None, 40), (entry["folio_first"], entry["folio_last"], entry["file_page_first"]))

    def test_the_last_section_runs_to_the_final_marker(self) -> None:
        self.assertEqual("9", entry_named("# One\n\n%% p. 1 (file p. 2) %%\n\nA.\n\n%% p. 9 (file p. 10) %%\n\nB.\n",
                                          "One")["folio_last"])

    def test_a_heading_before_any_marker_has_no_page(self) -> None:
        entry = entry_named("# One\n\nA.\n", "One")
        self.assertEqual((None, None), (entry["folio_first"], entry["file_page_first"]))

    def test_an_entry_counts_the_words_of_its_own_section_without_markers(self) -> None:
        self.assertEqual(3, entry_named(BODY, "Part One > Chapter One")["words"])

    def test_a_heading_with_no_prose_of_its_own_counts_no_words(self) -> None:
        self.assertEqual(0, entry_named(BODY, "Part One")["words"])

    def test_a_body_without_headings_has_no_entries(self) -> None:
        self.assertEqual([], outline("%% p. 1 (file p. 2) %%\n\nProse only.\n"))

    def test_a_comment_inside_a_heading_is_stripped_from_the_path(self) -> None:
        [entry] = outline("# One %% p. 3 (file p. 4) %%\n\nA.\n")
        self.assertEqual("One", entry["heading_path"])


class TestCorpusOutline(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("CORPUS_DIR", "TRANSCRIPTS_DIR").activate()
        self.addCleanup(self.vault.discard)
        note = f"---\ntitle: {BASENAME}\n---\n\n{LINK_LINE}\n\n{BODY}"
        (self.vault.corpus / f"{BASENAME}.md").write_text(note, encoding="utf-8")

    def test_the_outline_of_a_held_work_is_read_from_its_corpus_file(self) -> None:
        report = rag.CorpusOutline().of(BASENAME)
        self.assertEqual((BASENAME, 6), (report["basename"], len(report["outline"])))

    def test_the_report_carries_the_word_count_of_the_whole_body(self) -> None:
        self.assertEqual(7, rag.CorpusOutline().of(BASENAME)["words"])

    def test_an_unknown_basename_is_an_error(self) -> None:
        self.assertIn("error", rag.CorpusOutline().of("Nobody - 1999 - Nothing"))

    def test_the_outline_of_a_transcript_is_read_from_the_transcripts_directory(self) -> None:
        talk = "Pippin - 2019 - Hegel on Logic as Metaphysics"
        note = ("---\ntitle: Talk\n---\n\n[Recording](https://youtu.be/x)\n\n"
                "## Talk\n\nSpoken.\n\n## Discussion\n\nAsked.\n")
        (vault.TRANSCRIPTS_DIR / f"{talk}.md").write_text(note, encoding="utf-8")
        report = rag.CorpusOutline().of(talk)
        self.assertEqual(["Talk", "Discussion"], [entry["heading_path"] for entry in report["outline"]])

    def test_a_transcript_heading_carries_the_time_it_begins_at(self) -> None:
        talk = "Pippin - 2019 - Hegel on Logic as Metaphysics"
        note = ("---\ntitle: Talk\n---\n\n%% 00:00:03 %%\n## Talk\n\nSpoken.\n\n"
                "%% 00:41:10 %%\n## Discussion\n\nAsked.\n")
        (vault.TRANSCRIPTS_DIR / f"{talk}.md").write_text(note, encoding="utf-8")
        report = rag.CorpusOutline().of(talk)
        self.assertEqual(["00:00:03", "00:41:10"], [entry["time_first"] for entry in report["outline"]])


if __name__ == "__main__":
    unittest.main()
