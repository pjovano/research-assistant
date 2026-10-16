from __future__ import annotations

import contextlib
import io
import json
import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _vaults import TempVault

HELD_PDF = "Doe - 2020 - A Work.pdf"
INBOX_PDF = "scan.pdf"
DECOMPOSED_ENTRY = "Fré - 2018 - A Work.entries.json"
COMPOSED_PDF = "Fré - 2018 - A Work.pdf"
GONE = "Old - 1999 - Gone"
PDF_BYTES = b"%PDF-1.7\n"
RENDER_BYTES = b"0123456789"


class ScratchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "VOLUMES_DIR", "INBOX_DIR").activate()
        self.addCleanup(self.vault.discard)
        (self.vault.library / HELD_PDF).write_bytes(PDF_BYTES)
        (self.vault.library / COMPOSED_PDF).write_bytes(PDF_BYTES)
        (self.vault.inbox / INBOX_PDF).write_bytes(PDF_BYTES)
        self.scratch = vault.SCRATCH_DIR
        for name in ("Doe - 2020 - A Work", GONE):
            (self.scratch / name).mkdir()
            (self.scratch / name / "page-1.png").write_bytes(RENDER_BYTES)
        for name in ("Doe - 2020 - A Work.entries.json", "scan.suggested.json", f"{GONE}.entries.json",
                     DECOMPOSED_ENTRY, "engine-run.json"):
            (self.scratch / name).write_bytes(RENDER_BYTES)

    def stale_names(self) -> list[str]:
        return [entry["entry"] for entry in self.report(["sweep"])["stale"]]

    def report(self, argv: list[str]) -> dict:
        return json.loads(self.printed(argv))

    def printed(self, argv: list[str]) -> str:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            vault.VaultCommandLine().run(argv)
        return printed.getvalue()


class TestSweepListsTheStaleEntries(ScratchTestCase):
    def test_only_the_entries_keyed_to_no_pdf_are_stale(self) -> None:
        self.assertEqual([GONE, f"{GONE}.entries.json"], self.stale_names())

    def test_a_decomposed_entry_of_a_composed_pdf_is_held(self) -> None:
        self.assertNotIn(DECOMPOSED_ENTRY, self.stale_names())

    def test_the_engine_run_file_is_never_stale(self) -> None:
        (self.vault.library / HELD_PDF).unlink()
        self.assertNotIn("engine-run.json", self.stale_names())

    def test_a_working_directory_holding_pending_trials_or_regression_diffs_is_never_stale(self) -> None:
        for name in ("trials", "regressions"):
            (self.scratch / name).mkdir()
            (self.scratch / name / f"{GONE}.md").write_bytes(RENDER_BYTES)
        stale = self.stale_names()
        for name in ("trials", "regressions"):
            with self.subTest(name=name):
                self.assertNotIn(name, stale)

    def test_the_ingest_batch_directory_is_never_stale(self) -> None:
        (self.scratch / "ingest" / GONE).mkdir(parents=True)
        self.assertNotIn("ingest", self.stale_names())

    def test_a_directory_reports_the_size_of_its_files(self) -> None:
        sizes = {entry["entry"]: entry["bytes"] for entry in self.report(["sweep"])["stale"]}
        self.assertEqual(len(RENDER_BYTES), sizes[GONE])

    def test_the_listing_deletes_nothing(self) -> None:
        self.report(["sweep"])
        self.assertTrue((self.scratch / GONE).exists())


class TestSweepApplyDeletesOnlyTheStaleEntries(ScratchTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.report(["sweep", "--apply"])

    def test_the_stale_entries_are_gone(self) -> None:
        self.assertFalse((self.scratch / GONE).exists())
        self.assertFalse((self.scratch / f"{GONE}.entries.json").exists())

    def test_the_held_entries_survive(self) -> None:
        survivors = sorted(path.name for path in self.scratch.iterdir())
        self.assertEqual(sorted(["Doe - 2020 - A Work", "Doe - 2020 - A Work.entries.json", "scan.suggested.json",
                                 DECOMPOSED_ENTRY, "engine-run.json"]), survivors)

    def test_a_second_sweep_finds_nothing(self) -> None:
        self.assertEqual([], self.stale_names())


class TestNoArgumentsPrintsTheResolvedPaths(ScratchTestCase):
    def test_every_resolved_path_and_the_machine_config_are_printed(self) -> None:
        printed = self.printed([])
        for label in ("VAULT_ROOT", "LIBRARY_DIR", "CORPUS_DIR", "INBOX_DIR", "RAG_DIR", "SCRATCH_DIR",
                      "MACHINE_CONFIG"):
            with self.subTest(label=label):
                self.assertIn(f"{label:<18} = ", printed)


if __name__ == "__main__":
    unittest.main()
