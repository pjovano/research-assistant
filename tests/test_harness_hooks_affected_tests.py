import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import harness_hooks
from _hooks.affected_tests import AffectedModules, AffectedTests, FullSuite

WIRED_SOURCES = {
    "lib/alpha.py": "ALPHA = 1\n",
    ".claude/skills/demo/scripts/beta.py": "import alpha\n",
    "lib/kit/__init__.py": "from .gamma import GAMMA\n",
    "lib/kit/gamma.py": "GAMMA = 3\n",
    "tests/_helper.py": "from beta import alpha\n",
    "tests/test_alpha.py": "import alpha\n",
    "tests/test_beta.py": "def run():\n    from beta import alpha\n",
    "tests/test_kit.py": "import kit\n",
    "tests/test_helper_user.py": "from _helper import alpha\n",
    "tests/fixtures/data.py": "import alpha\n",
    "bin/tool.py": "import alpha\n",
}
PASSING_TEST = ("import unittest\nfrom _shared import VALUE\n\n\nclass TestShared(unittest.TestCase):\n"
                "    def test_value(self):\n        self.assertEqual(1, VALUE)\n")


class SourceTree:
    def __init__(self, root: Path, sources: dict[str, str]) -> None:
        self.root = root
        for relative, source in sources.items():
            self.write(relative, source)

    def write(self, relative: str, source: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)

    def selection(self, relative: str) -> FullSuite | AffectedModules:
        return AffectedTests(self.root).selection(self.root / relative)

    def suite_check(self, relative: str) -> harness_hooks.SuiteCheck:
        return harness_hooks.SuiteCheck(self.root, (self.root / relative).resolve())


class TestTheSelectionFollowsTheImportClosure(unittest.TestCase):
    def setUp(self):
        self.tree = SourceTree(Path(self.enterContext(tempfile.TemporaryDirectory())), WIRED_SOURCES)

    def _selected(self, relative: str) -> tuple[str, ...]:
        selection = self.tree.selection(relative)
        self.assertIsInstance(selection, AffectedModules)
        return selection.unittest_arguments()

    def test_a_module_imported_through_a_chain_selects_every_test_module_whose_closure_holds_it(self):
        self.assertEqual(("test_alpha", "test_beta", "test_helper_user"), self._selected("lib/alpha.py"))

    def test_a_skill_script_selects_the_test_modules_that_import_it(self):
        self.assertEqual(("test_beta", "test_helper_user"),
                         self._selected(".claude/skills/demo/scripts/beta.py"))

    def test_a_module_reached_through_a_relative_import_of_its_package_selects_its_importers(self):
        self.assertEqual(("test_kit",), self._selected("lib/kit/gamma.py"))

    def test_an_edited_test_module_selects_itself(self):
        self.assertEqual(("test_kit",), self._selected("tests/test_kit.py"))

    def test_an_edited_test_helper_selects_every_test_module_that_imports_it(self):
        self.assertEqual(("test_helper_user",), self._selected("tests/_helper.py"))

    def test_a_module_no_test_imports_selects_nothing(self):
        self.tree.write("lib/unused.py", "import alpha\n")
        self.assertTrue(self.tree.selection("lib/unused.py").runs_nothing())

    def test_the_selected_modules_run_with_the_tests_directory_on_the_search_path(self):
        self.assertEqual((self.tree.root.resolve() / "tests",),
                         self.tree.selection("lib/alpha.py").search_directories())


class TestTheFullSuiteRunsWhereTheGraphCannotAnswer(unittest.TestCase):
    def setUp(self):
        self.tree = SourceTree(Path(self.enterContext(tempfile.TemporaryDirectory())), WIRED_SOURCES)

    def test_a_file_that_fails_to_parse_selects_the_full_suite(self):
        self.tree.write("lib/broken.py", "def broken(:\n")
        self.assertIsInstance(self.tree.selection("lib/alpha.py"), FullSuite)

    def test_a_python_file_outside_the_module_search_path_selects_the_full_suite(self):
        self.assertIsInstance(self.tree.selection("bin/tool.py"), FullSuite)

    def test_a_python_file_in_a_directory_that_is_not_a_package_selects_the_full_suite(self):
        self.assertIsInstance(self.tree.selection("tests/fixtures/data.py"), FullSuite)


class TestTheSuiteCheckRunsTheSelection(unittest.TestCase):
    def setUp(self):
        self.tree = SourceTree(Path(self.enterContext(tempfile.TemporaryDirectory())), WIRED_SOURCES)
        self.passed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    def _run_arguments(self, relative: str) -> mock.MagicMock:
        with mock.patch.object(harness_hooks.subprocess, "run", return_value=self.passed) as run:
            self.assertIsNone(self.tree.suite_check(relative).failure_report())
        return run

    def test_an_edit_runs_the_affected_modules_by_name(self):
        command = self._run_arguments("lib/kit/gamma.py").call_args.args[0]
        self.assertEqual([str(harness_hooks.INTERPRETER), "-m", "unittest", "test_kit"], command)

    def test_an_unparsable_file_makes_the_check_discover_the_whole_suite(self):
        self.tree.write("lib/broken.py", "def broken(:\n")
        command = self._run_arguments("lib/alpha.py").call_args.args[0]
        self.assertEqual(["discover", "-s", "tests"], command[-3:])

    def test_an_edit_no_test_module_imports_runs_no_test(self):
        self.tree.write("lib/unused.py", "UNUSED = 0\n")
        self._run_arguments("lib/unused.py").assert_not_called()


class TestTheAffectedModulesRunForReal(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.tree = SourceTree(root, {"tests/_shared.py": "VALUE = 1\n", "tests/test_shared.py": PASSING_TEST})
        self.enterContext(mock.patch.object(harness_hooks.SuiteCheck, "COMMAND", (sys.executable, "-m", "unittest")))

    def test_a_passing_module_that_imports_the_edited_helper_reports_nothing(self):
        self.assertIsNone(self.tree.suite_check("tests/_shared.py").failure_report())

    def test_a_failing_module_that_imports_the_edited_helper_is_reported(self):
        self.tree.write("tests/_shared.py", "VALUE = 2\n")
        self.assertIn("FAIL: test_value", self.tree.suite_check("tests/_shared.py").failure_report())


if __name__ == "__main__":
    unittest.main()
