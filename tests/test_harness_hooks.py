import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import harness_hooks


class TestBashGuard(unittest.TestCase):
    def test_extract_replace_asks(self):
        decision = harness_hooks.BashGuard("python extract.py extract X.pdf --replace").decision()
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_labels_apply_asks_naming_the_filed_pdf_it_rewrites(self):
        decision = harness_hooks.BashGuard("python extract.py labels X.pdf --apply").decision()
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertIn("library PDF", decision["hookSpecificOutput"]["permissionDecisionReason"])

    def test_the_read_only_form_of_labels_passes_silently(self):
        self.assertIsNone(harness_hooks.BashGuard("python extract.py labels X.pdf").decision())

    def test_read_only_probe_passes_silently(self):
        self.assertIsNone(harness_hooks.BashGuard("python extract.py probe X.pdf").decision())

    def test_rebuild_names_its_consequence(self):
        decision = harness_hooks.BashGuard("python search.py sync --rebuild").decision()
        self.assertIn("empties the search stores", decision["hookSpecificOutput"]["permissionDecisionReason"])


class TestWriteGuard(unittest.TestCase):
    def setUp(self):
        self.vault = Path(tempfile.mkdtemp())
        self.corpus_dir = self.vault / "research vault" / "corpus"

    def _decision(self, path: Path | None) -> dict | None:
        return harness_hooks.WriteGuard(path, lambda: self.corpus_dir).decision()

    def test_a_new_corpus_file_is_denied(self):
        decision = self._decision(self.corpus_dir / "Doe - 2020 - A Work.md")
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_the_denial_names_stage_1_as_the_only_writer(self):
        decision = self._decision(self.corpus_dir / "Doe - 2020 - A Work.md")
        self.assertIn("Stage 1", decision["hookSpecificOutput"]["permissionDecisionReason"])

    def test_a_new_transcript_in_the_corpus_subfolder_is_denied(self):
        decision = self._decision(self.corpus_dir / "talk transcripts" / "Doe - 2020 - A Talk.md")
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_the_denial_names_the_transcript_writer(self):
        decision = self._decision(self.corpus_dir / "talk transcripts" / "Doe - 2020 - A Talk.md")
        self.assertIn("transcribe.py file", decision["hookSpecificOutput"]["permissionDecisionReason"])

    def test_a_path_that_escapes_the_corpus_directory_by_a_parent_segment_is_denied(self):
        self.assertIsNotNone(self._decision(self.vault / "research vault" / "writing" / ".." / "corpus" / "x.md"))

    def test_a_bibliography_passes_silently(self):
        self.assertIsNone(self._decision(self.vault / "research vault" / "bibliographies" / "Topic.md"))

    def test_a_file_whose_name_starts_with_the_corpus_directory_name_passes(self):
        self.assertIsNone(self._decision(self.vault / "research vault" / "corpus-notes.md"))

    def test_no_path_passes_silently(self):
        self.assertIsNone(self._decision(None))


class TestMainNeverFailsOpen(unittest.TestCase):
    def test_an_exception_outside_a_check_blocks_instead_of_exiting_nonzero(self):
        err = io.StringIO()
        with mock.patch.object(harness_hooks.HookCli, "run", side_effect=RuntimeError("boom")), \
                mock.patch.object(harness_hooks.sys, "argv", ["harness_hooks.py", "checks-after-edit"]), \
                mock.patch.object(harness_hooks.sys, "stdin", io.StringIO("{}")), \
                redirect_stderr(err), self.assertRaises(SystemExit) as exit:
            harness_hooks.main()
        self.assertEqual(exit.exception.code, harness_hooks.BLOCKING_EXIT_CODE)
        self.assertIn("the hook failed", err.getvalue())

    def test_a_payload_that_cannot_be_read_blocks_the_guard(self):
        err = io.StringIO()
        with mock.patch.object(harness_hooks.sys, "argv", ["harness_hooks.py", "guard-bash"]), \
                mock.patch.object(harness_hooks.sys, "stdin", io.StringIO("not json")), \
                redirect_stderr(err), self.assertRaises(SystemExit) as exit:
            harness_hooks.main()
        self.assertEqual(exit.exception.code, harness_hooks.BLOCKING_EXIT_CODE)

    def test_a_missing_subcommand_blocks_instead_of_exiting_nonzero(self):
        err = io.StringIO()
        with mock.patch.object(harness_hooks.sys, "argv", ["harness_hooks.py"]), \
                mock.patch.object(harness_hooks.sys, "stdin", io.StringIO("{}")), \
                redirect_stderr(err), self.assertRaises(SystemExit) as exit:
            harness_hooks.main()
        self.assertEqual(exit.exception.code, harness_hooks.BLOCKING_EXIT_CODE)


class TestHookCli(unittest.TestCase):
    def test_guard_writes_the_decision_to_stdout(self):
        event = harness_hooks.HookEvent({"tool_input": {"command": "clean.py drop-page a.pdf --page 3"}})
        out = io.StringIO()
        with redirect_stdout(out):
            code = harness_hooks.HookCli(Path.cwd()).run("guard-bash", event)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_the_write_guard_denies_a_file_under_the_vault_corpus_directory(self):
        corpus_dir = Path(tempfile.mkdtemp())
        event = harness_hooks.HookEvent({"tool_input": {"file_path": str(corpus_dir / "Doe - 2020 - A Work.md")}})
        out = io.StringIO()
        with mock.patch.object(harness_hooks, "corpus_directory", return_value=corpus_dir), redirect_stdout(out):
            code = harness_hooks.HookCli(Path.cwd()).run("guard-write", event)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_write_outside_the_corpus_emits_no_decision(self):
        event = harness_hooks.HookEvent({"tool_input": {"file_path": str(Path(tempfile.mkdtemp()) / "x.md")}})
        out = io.StringIO()
        with redirect_stdout(out):
            code = harness_hooks.HookCli(Path.cwd()).run("guard-write", event)
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "")

    def test_the_corpus_directory_is_the_one_vault_resolves(self):
        import vault
        self.assertEqual(harness_hooks.corpus_directory(), vault.CORPUS_DIR)

    def test_an_edit_outside_the_project_runs_no_check(self):
        event = harness_hooks.HookEvent({"tool_input": {"file_path": "/tmp/x.md"}})
        with mock.patch.object(harness_hooks.subprocess, "run") as run:
            self.assertEqual(harness_hooks.HookCli(Path.cwd()).run("checks-after-edit", event), 0)
        run.assert_not_called()

    def test_unknown_subcommand_blocks(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = harness_hooks.HookCli(Path.cwd()).run("nonsense", harness_hooks.HookEvent({}))
        self.assertEqual(code, harness_hooks.BLOCKING_EXIT_CODE)


if __name__ == "__main__":
    unittest.main()
