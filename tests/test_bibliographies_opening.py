from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import bibliographies
import vault
from _bibliography_fixtures import (
    HEGEL,
    PIPPIN_TALK,
    TemporaryVault,
)


class OpeningTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)

    def run_opening(self, *argv: str) -> tuple[int, dict]:
        printed = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(printed), mock.patch.object(sys, "argv", ["bibliographies.py", *argv]):
            try:
                bibliographies.CommandLine().run()
            except SystemExit as stopped:
                code = stopped.code
        return code, json.loads(printed.getvalue())


class TestOpeningOfATranscript(OpeningTestCase):
    def test_a_transcript_is_opened_by_its_basename_and_is_unclassified(self) -> None:
        body = "[Recording](https://youtu.be/x)\n\n## Talk\n\n%% 00:00:00 %%\n**Pippin:** Logic is metaphysics.\n"
        vault.write_frontmatter(vault.TRANSCRIPTS_DIR / f"{PIPPIN_TALK}.md",
                                {"title": "Talk", "source_type": None, "source_role": None, "field": []}, body)
        code, report = self.run_opening("opening", PIPPIN_TALK)
        self.assertEqual((0, ["## Talk"]), (code, report["headings"]))


class TestOpeningReportsTheCurrentClassification(OpeningTestCase):
    def test_an_unclassified_corpus_file_reports_three_empty_fields_and_exits_zero(self) -> None:
        self.vault.note(HEGEL, title="Wissenschaft der Logik")
        code, report = self.run_opening("opening", HEGEL)
        self.assertEqual((0, None, None, None), (code, report["source_type"], report["source_role"], report["field"]))

    def test_a_classified_corpus_file_reports_its_values(self) -> None:
        self.vault.note(HEGEL, source_type="historical", source_role="primary", field=["[[Hegel]]"])
        _code, report = self.run_opening("opening", HEGEL)
        self.assertEqual(("historical", "primary", ["[[Hegel]]"]),
                         (report["source_type"], report["source_role"], report["field"]))

    def test_a_corpus_file_carrying_any_of_the_three_refuses_with_its_own_code(self) -> None:
        self.vault.note(HEGEL, source_role="primary")
        self.assertEqual(bibliographies.EXIT_ALREADY_CLASSIFIED, self.run_opening("opening", HEGEL)[0])

    def test_reclassify_reports_the_same_file_without_the_refusal(self) -> None:
        self.vault.note(HEGEL, source_role="primary")
        self.assertEqual(0, self.run_opening("opening", HEGEL, "--reclassify")[0])


if __name__ == "__main__":
    unittest.main()
