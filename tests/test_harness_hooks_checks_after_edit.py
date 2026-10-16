import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import harness_hooks
from _hooks.affected_tests import FullSuite


def suite_output(failures: int) -> str:
    block = (f"{harness_hooks.UNITTEST_BLOCK_SEPARATOR}\nFAIL: test_{{number}} (tests.TestX.test_{{number}})\n"
             f"{'-' * 70}\nTraceback (most recent call last):\n"
             + "".join(f'  File "tests/test_x.py", line {line}, in test\n    frame {line}\n' for line in range(4))
             + "AssertionError: 1 != 2\n\n")
    blocks = "".join(block.format(number=number) for number in range(failures))
    return f"{'F' * failures}\n{blocks}{'-' * 70}\nRan {failures} tests in 0.1s\n\nFAILED (failures={failures})\n"


HOOK_SCRIPT = Path("lib/harness_hooks.py")
RUFF_REINSTALL = "uv pip sync --reinstall-package ruff --python ~/.research-vault/venv/bin/python requirements.lock"


class TestEditedProjectFile(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _check_labels(self, path: Path | None) -> list[str]:
        return [check.LABEL for check in harness_hooks.EditedProjectFile(path, self.root).checks()]

    def test_a_python_file_runs_the_linter_the_audit_linter_and_the_suite_in_that_order(self):
        self.assertEqual(["the linter", "the audit linter", "the test suite"],
                         self._check_labels(self.root / "lib/x.py"))

    def test_a_markdown_file_runs_the_audit_linter_alone(self):
        self.assertEqual(["the audit linter"], self._check_labels(self.root / "CLAUDE.md"))

    def test_a_relative_project_path_runs_checks(self):
        self.assertTrue(self._check_labels(Path("tests/test_x.py")))

    def test_another_suffix_runs_nothing(self):
        self.assertEqual([], self._check_labels(self.root / "settings.json"))

    def test_a_file_outside_the_project_runs_nothing(self):
        self.assertEqual([], self._check_labels(self.root.parent / "elsewhere/x.py"))

    def test_no_path_runs_nothing(self):
        self.assertEqual([], self._check_labels(None))


class TestAuditCheck(unittest.TestCase):
    def _report_of(self, completed: subprocess.CompletedProcess) -> str | None:
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=completed):
            return harness_hooks.AuditCheck(Path.cwd()).failure_report()

    def test_an_empty_works_list_reports_nothing(self):
        clean = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps({"works": []}), stderr="")
        self.assertIsNone(self._report_of(clean))

    def test_a_named_work_is_reported_with_its_file_and_line(self):
        work = {"file": "lib/x.py", "line": 4, "finding": "work-named", "detail": "Doe - 2020 - A Work"}
        found = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps({"works": [work]}), stderr="")
        self.assertEqual("lib/x.py:4: Doe - 2020 - A Work", self._report_of(found))

    def test_a_linter_that_crashes_is_reported_with_its_output(self):
        crashed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Traceback: boom\n")
        self.assertIn("Traceback: boom", self._report_of(crashed))

    def test_the_audit_script_exists_at_the_path_the_check_runs(self):
        self.assertTrue((harness_hooks.PROJECT_ROOT / harness_hooks.AUDIT_SCRIPT).is_file())

    def test_the_control_plane_passes_the_real_script(self):
        under_this_interpreter = (sys.executable, *harness_hooks.AUDIT_ARGUMENTS)
        with mock.patch.object(harness_hooks.AuditCheck, "COMMAND", under_this_interpreter):
            self.assertIsNone(harness_hooks.AuditCheck(harness_hooks.PROJECT_ROOT).failure_report())


class TestEditCheckReport(unittest.TestCase):
    def test_a_failure_with_no_output_names_the_exit_code(self):
        silent = subprocess.CompletedProcess(args=[], returncode=-9, stdout="", stderr="")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=silent):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn("-9", report)

    def test_a_failure_whose_only_output_is_blank_names_the_exit_code(self):
        blank = subprocess.CompletedProcess(args=[], returncode=-9, stdout="\n \n", stderr="")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=blank):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn("-9", report)

    def test_a_check_killed_by_a_signal_names_the_code_beside_its_partial_output(self):
        killed = subprocess.CompletedProcess(args=[], returncode=-11, stdout="", stderr="....E...F..\n")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=killed):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn("-11", report)
        self.assertIn("....E...F..", report)

    def test_stdout_without_a_trailing_newline_does_not_splice_onto_stderr(self):
        unfinished = subprocess.CompletedProcess(args=[], returncode=1, stdout="Found 1 error.", stderr="warning: x\n")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=unfinished):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn("Found 1 error.\nwarning: x", report)

    def test_a_spawn_failure_names_its_cause(self):
        denied = PermissionError(13, "Permission denied", str(harness_hooks.INTERPRETER))
        with mock.patch.object(harness_hooks.subprocess, "run", side_effect=denied):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn("Permission denied", report)

    def test_a_failure_of_the_working_directory_does_not_prescribe_a_reinstall(self):
        gone = FileNotFoundError(2, "No such file or directory", "renamed-root")
        with mock.patch.object(harness_hooks.subprocess, "run", side_effect=gone):
            report = harness_hooks.LintCheck(Path.cwd()).failure_report()
        self.assertIn("No such file or directory", report)
        self.assertNotIn("uv pip sync", report)


class TestSuiteCheck(unittest.TestCase):
    def test_a_suite_that_outruns_its_limit_is_reported_as_a_failure(self):
        expired = subprocess.TimeoutExpired(cmd="unittest", timeout=harness_hooks.SUITE_TIMEOUT_SECONDS)
        with mock.patch.object(harness_hooks.subprocess, "run", side_effect=expired):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn(f"within {harness_hooks.SUITE_TIMEOUT_SECONDS} seconds", report)

    def test_a_timeout_reports_the_output_the_check_wrote_before_it_was_killed(self):
        expired = subprocess.TimeoutExpired(cmd="unittest", timeout=harness_hooks.SUITE_TIMEOUT_SECONDS,
                                             output=b"FAIL: test_hangs\n")
        with mock.patch.object(harness_hooks.subprocess, "run", side_effect=expired):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn("test_hangs", report)

    def test_a_timeout_with_undecodable_output_still_reports(self):
        expired = subprocess.TimeoutExpired(cmd="unittest", timeout=harness_hooks.SUITE_TIMEOUT_SECONDS,
                                             output=b"\xff\xfe cannot decode\n")
        with mock.patch.object(harness_hooks.subprocess, "run", side_effect=expired):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn("cannot decode", report)

    def test_every_failure_the_bound_admits_is_reported_whole(self):
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout=suite_output(failures=3), stderr="")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=failed):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        for number in range(3):
            self.assertIn(f"FAIL: test_{number}", report)
        self.assertIn("FAILED (failures=3)", report)
        self.assertTrue(report.startswith(harness_hooks.UNITTEST_BLOCK_SEPARATOR), report[:80])

    def test_output_without_failure_blocks_is_kept_whole(self):
        crashed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Traceback:\n  frame\nBoom\n")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=crashed):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn("Traceback:\n  frame\nBoom", report)

    def test_the_tail_drops_the_oldest_failures_whole_and_keeps_the_summary(self):
        over = harness_hooks.SuiteCheck.REPORT_TAIL_BLOCKS + 2
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout=suite_output(failures=over), stderr="")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=failed):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertNotIn("FAIL: test_0 ", report)
        self.assertNotIn("FAIL: test_1 ", report)
        self.assertTrue(report.startswith(harness_hooks.UNITTEST_BLOCK_SEPARATOR))
        self.assertIn(f"FAIL: test_{over - 1} ", report)
        self.assertIn(f"FAILED (failures={over})", report)

    def test_a_missing_interpreter_is_reported_without_a_repair_hint(self):
        missing = FileNotFoundError(2, "No such file or directory", str(harness_hooks.INTERPRETER))
        with mock.patch.object(harness_hooks.subprocess, "run", side_effect=missing):
            report = harness_hooks.SuiteCheck(Path.cwd(), FullSuite()).failure_report()
        self.assertIn(str(harness_hooks.INTERPRETER), report)
        self.assertNotIn("uv pip sync", report)


class TestLintCheck(unittest.TestCase):
    def test_a_clean_run_reports_nothing(self):
        clean = subprocess.CompletedProcess(args=[], returncode=0, stdout="All checks passed!\n", stderr="")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=clean):
            self.assertIsNone(harness_hooks.LintCheck(Path.cwd()).failure_report())

    def test_a_finding_is_reported_from_the_linter_output(self):
        finding = "lib/x.py:1:8: F401 `os` imported but unused\n"
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout=finding, stderr="")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=failed):
            self.assertIn("F401", harness_hooks.LintCheck(Path.cwd()).failure_report())

    def test_every_finding_is_reported_however_many(self):
        findings = "\n".join(f"lib/x.py:{number}:8: F401 unused" for number in range(40))
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout=findings + "\n", stderr="")
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=failed):
            report = harness_hooks.LintCheck(Path.cwd()).failure_report()
        self.assertIn("lib/x.py:0:8", report)
        self.assertIn("lib/x.py:39:8", report)

    def test_a_linter_that_outruns_its_limit_is_reported_as_a_failure(self):
        expired = subprocess.TimeoutExpired(cmd="ruff", timeout=harness_hooks.LINT_TIMEOUT_SECONDS)
        with mock.patch.object(harness_hooks.subprocess, "run", side_effect=expired):
            report = harness_hooks.LintCheck(Path.cwd()).failure_report()
        self.assertIn(f"within {harness_hooks.LINT_TIMEOUT_SECONDS} seconds", report)

    def test_undecodable_output_is_reported_rather_than_escaping_the_hook(self):
        emits_invalid_utf8 = (sys.executable, "-c",
                              "import sys; sys.stdout.buffer.write(b'lib/x.py:1:8: E501 \\xff\\n'); sys.exit(1)")
        with mock.patch.object(harness_hooks.LintCheck, "COMMAND", emits_invalid_utf8):
            report = harness_hooks.LintCheck(Path.cwd()).failure_report()
        self.assertIn("E501", report)

    def test_a_missing_linter_is_reported_with_its_own_reinstall(self):
        missing = FileNotFoundError(2, "No such file or directory", str(harness_hooks.LINTER))
        with mock.patch.object(harness_hooks.subprocess, "run", side_effect=missing):
            report = harness_hooks.LintCheck(Path.cwd()).failure_report()
        self.assertIn(str(harness_hooks.LINTER), report)
        self.assertIn(RUFF_REINSTALL, report)

    def test_a_linter_that_cannot_be_executed_is_reported_with_its_own_reinstall(self):
        denied = PermissionError(13, "Permission denied", str(harness_hooks.LINTER))
        with mock.patch.object(harness_hooks.subprocess, "run", side_effect=denied):
            report = harness_hooks.LintCheck(Path.cwd()).failure_report()
        self.assertIn(RUFF_REINSTALL, report)


class TestChecksAfterEdit(unittest.TestCase):
    EVENT = harness_hooks.HookEvent({"tool_input": {"file_path": str(HOOK_SCRIPT)}})
    MARKDOWN_EVENT = harness_hooks.HookEvent({"tool_input": {"file_path": "CLAUDE.md"}})

    def test_a_lint_failure_blocks_before_the_other_checks_run(self):
        err = io.StringIO()
        with mock.patch.object(harness_hooks.LintCheck, "failure_report", return_value="lib/x.py:1:8: F401"), \
                mock.patch.object(harness_hooks.AuditCheck, "failure_report") as audit, \
                mock.patch.object(harness_hooks.SuiteCheck, "failure_report") as suite, redirect_stderr(err):
            code = harness_hooks.HookCli(Path.cwd()).run("checks-after-edit", self.EVENT)
        self.assertEqual(code, harness_hooks.BLOCKING_EXIT_CODE)
        audit.assert_not_called()
        suite.assert_not_called()
        self.assertIn("the linter fails after this edit", err.getvalue())

    def test_a_named_work_blocks_before_the_suite_runs(self):
        err = io.StringIO()
        with mock.patch.object(harness_hooks.LintCheck, "failure_report", return_value=None), \
                mock.patch.object(harness_hooks.AuditCheck, "failure_report",
                                  return_value="lib/x.py:4: Doe - 2020 - A"), \
                mock.patch.object(harness_hooks.SuiteCheck, "failure_report") as suite, redirect_stderr(err):
            code = harness_hooks.HookCli(Path.cwd()).run("checks-after-edit", self.EVENT)
        self.assertEqual(code, harness_hooks.BLOCKING_EXIT_CODE)
        suite.assert_not_called()
        self.assertIn("state the defect class instead of the work", err.getvalue())

    def test_a_suite_failure_after_clean_linters_blocks(self):
        err = io.StringIO()
        with mock.patch.object(harness_hooks.LintCheck, "failure_report", return_value=None), \
                mock.patch.object(harness_hooks.AuditCheck, "failure_report", return_value=None), \
                mock.patch.object(harness_hooks.SuiteCheck, "failure_report", return_value="FAIL: test_x"), \
                redirect_stderr(err):
            code = harness_hooks.HookCli(Path.cwd()).run("checks-after-edit", self.EVENT)
        self.assertEqual(code, harness_hooks.BLOCKING_EXIT_CODE)
        self.assertIn("the test suite fails after this edit", err.getvalue())
        self.assertIn("FAIL: test_x", err.getvalue())

    def test_clean_linters_run_the_suite(self):
        with mock.patch.object(harness_hooks.LintCheck, "failure_report", return_value=None), \
                mock.patch.object(harness_hooks.AuditCheck, "failure_report", return_value=None), \
                mock.patch.object(harness_hooks.SuiteCheck, "failure_report", return_value=None) as suite:
            code = harness_hooks.HookCli(Path.cwd()).run("checks-after-edit", self.EVENT)
        self.assertEqual(code, 0)
        suite.assert_called_once()

    def test_a_markdown_edit_runs_the_audit_linter_and_nothing_else(self):
        with mock.patch.object(harness_hooks.LintCheck, "failure_report") as lint, \
                mock.patch.object(harness_hooks.AuditCheck, "failure_report", return_value=None) as audit, \
                mock.patch.object(harness_hooks.SuiteCheck, "failure_report") as suite:
            code = harness_hooks.HookCli(harness_hooks.PROJECT_ROOT).run("checks-after-edit", self.MARKDOWN_EVENT)
        self.assertEqual(code, 0)
        audit.assert_called_once()
        lint.assert_not_called()
        suite.assert_not_called()


class TestCheckEnvironment(unittest.TestCase):
    def test_a_check_runs_without_the_variables_that_locate_a_repository(self):
        passed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with (mock.patch.dict(harness_hooks.os.environ, {"GIT_DIR": "elsewhere.git"}),
              mock.patch.object(harness_hooks.subprocess, "run", return_value=passed) as run):
            harness_hooks.LintCheck(Path.cwd()).failure_report()
        self.assertNotIn("GIT_DIR", run.call_args.kwargs["env"])


class TestCheckTimeouts(unittest.TestCase):
    def test_every_check_carries_a_positive_timeout(self):
        for check in harness_hooks.CHECKS_AFTER_EDIT:
            self.assertGreater(check.TIMEOUT_SECONDS, 0, check.LABEL)

    def test_the_granted_timeout_covers_every_check_plus_the_overhead(self):
        settings = json.loads((harness_hooks.PROJECT_ROOT / ".claude" / "settings.json").read_text())
        hooks = [hook for matcher in settings["hooks"]["PostToolUse"] for hook in matcher["hooks"]]
        granted = next(hook["timeout"] for hook in hooks if "checks-after-edit" in hook["command"])
        check_limits = sum(check.TIMEOUT_SECONDS for check in harness_hooks.CHECKS_AFTER_EDIT)
        self.assertEqual(granted, harness_hooks.HOOK_TIMEOUT_SECONDS)
        self.assertGreater(harness_hooks.SUITE_TIMEOUT_SECONDS, 0)
        self.assertGreater(harness_hooks.HOOK_OVERHEAD_SECONDS, 0)
        self.assertLessEqual(check_limits + harness_hooks.HOOK_OVERHEAD_SECONDS, granted)


if __name__ == "__main__":
    unittest.main()
