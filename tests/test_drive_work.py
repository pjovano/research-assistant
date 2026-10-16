from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unicodedata
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.steps import JsonLine, StepGuard
from _drive.work import BackfillQueue, Halt, IngestWorks, ListedWorks, WorkDirectory

PDF = "Author - 2000 - Work.pdf"
BASENAME = "Author - 2000 - Work"
WORK_KEY = 1
UNLISTED_KEY = 9
INITIAL_STATE = {"flags": [], "runs": 0}
DECOMPOSED_BASENAME = unicodedata.normalize("NFD", "Fré - 2018 - Œuvre")
QUOTED_PDF = "Beth - 1957 - Über Lockes „Allgemeines Dreieck“.pdf"
DOTTED_BASENAME = "Author - 2001 - Logic, Vol. 2"


class QueueCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.listed = ListedWorks(self.directory / "ingest")
        self.listed.list(WORK_KEY, PDF)
        self.queue = BackfillQueue(self.directory / "backfill", INITIAL_STATE)
        self.queue.write([PDF])


class TestKeyAddressing(QueueCase):
    def test_a_key_finds_the_directory_its_basename_finds(self) -> None:
        self.assertEqual(self.queue.work(BASENAME).directory.resolve(), self.queue.work(WORK_KEY).directory.resolve())

    def test_a_key_given_as_digits_is_a_key(self) -> None:
        self.assertEqual(self.queue.work(WORK_KEY).directory, self.queue.work(str(WORK_KEY)).directory)

    def test_a_keys_directory_path_carries_no_character_of_the_works_name(self) -> None:
        self.listed.list(WORK_KEY, QUOTED_PDF)
        self.assertTrue(str(self.queue.work(WORK_KEY).directory).isascii())

    def test_a_key_names_its_library_pdf(self) -> None:
        self.assertEqual(PDF, self.queue.work(WORK_KEY).pdf)

    def test_a_key_listed_again_keeps_the_works_directory(self) -> None:
        first = self.queue.work(WORK_KEY).directory.resolve()
        self.listed.list(WORK_KEY + 1, PDF)
        self.assertEqual(first, self.queue.work(WORK_KEY + 1).directory.resolve())

    def test_an_unlisted_key_sets_the_work_aside(self) -> None:
        outcome = StepGuard("drive-prep").on_work(lambda: self.queue.work(UNLISTED_KEY), lambda work: {})
        self.assertEqual(("aside", True), (outcome["state"], str(UNLISTED_KEY) in outcome["question"]))


class TestBasenameAddressing(QueueCase):
    def test_a_basename_names_its_library_pdf(self) -> None:
        self.assertEqual(PDF, self.queue.work(BASENAME).pdf)

    def test_a_library_filename_is_taken_as_it_stands(self) -> None:
        self.assertEqual(PDF, self.queue.work(PDF).pdf)

    def test_a_basename_outside_the_listing_needs_no_key(self) -> None:
        self.assertEqual("Other - 1999 - Work.pdf", self.queue.work("Other - 1999 - Work").pdf)

    def test_a_decomposed_basename_keys_its_directory_in_composed_form(self) -> None:
        name = self.queue.work(DECOMPOSED_BASENAME).directory.name
        self.assertEqual(unicodedata.normalize("NFC", DECOMPOSED_BASENAME), name)


class TestTheListing(QueueCase):
    def test_a_listed_work_carries_a_work_file_naming_its_pdf(self) -> None:
        work_file = json.loads((self.listed.directory(WORK_KEY) / "work.json").read_text(encoding="utf-8"))
        self.assertEqual({"pdf": PDF, "basename": BASENAME}, work_file)

    def test_an_ingest_work_under_a_key_is_the_basenames_directory(self) -> None:
        works = IngestWorks(self.directory / "ingest")
        self.assertEqual(works.work(PDF).directory.resolve(), works.work(str(WORK_KEY)).directory.resolve())

    def test_a_decomposed_name_is_listed_in_composed_form(self) -> None:
        self.listed.list(WORK_KEY + 1, DECOMPOSED_BASENAME + ".pdf")
        self.assertEqual(unicodedata.normalize("NFC", DECOMPOSED_BASENAME) + ".pdf", self.listed.pdf(WORK_KEY + 1))


class TestANameAddressedIngestWork(QueueCase):
    def test_a_basename_ending_in_a_dotted_word_keys_its_whole_name(self) -> None:
        self.assertEqual(DOTTED_BASENAME, IngestWorks(self.directory / "ingest").work(DOTTED_BASENAME).directory.name)

    def test_a_pdf_name_keys_its_basename(self) -> None:
        self.assertEqual(BASENAME, IngestWorks(self.directory / "ingest").work(PDF).directory.name)


class TestInitialState(QueueCase):
    def test_a_fresh_work_starts_from_the_initial_state(self) -> None:
        self.assertEqual(INITIAL_STATE, self.queue.work(WORK_KEY).state())

    def test_a_changed_state_leaves_the_initial_state_untouched(self) -> None:
        self.queue.work(WORK_KEY).state()["flags"].append("--force-ocr")
        self.assertEqual([], self.queue.work(WORK_KEY).state()["flags"])


class TestHalt(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.work = WorkDirectory(PDF, directory / BASENAME, INITIAL_STATE)

    def test_a_halt_prints_the_halt_state_with_its_question(self) -> None:
        outcome = self.printed(StepGuard("drive-file").on_work(lambda: self.work, self.halting))
        self.assertEqual(("halt", "Zotero is offline", PDF),
                         (outcome["state"], outcome["question"], outcome["pdf"]))

    @staticmethod
    def halting(_work: WorkDirectory) -> dict:
        raise Halt("Zotero is offline")

    @staticmethod
    def printed(outcome: dict) -> dict:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            JsonLine.emit(outcome)
        return json.loads(output.getvalue())


if __name__ == "__main__":
    unittest.main()
