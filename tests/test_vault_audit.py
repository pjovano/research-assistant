from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import vault

from _audit.baseline import STATUS_CHANGED, STATUS_NEW, STATUS_REMOVED, Baseline, CorruptBaseline
from _audit.cli import AuditSet, CommandLine
from _audit.measures import (
    MEASURE_ARGUMENTS,
    MEASURE_COMMENT,
    MEASURE_DOCSTRING,
    MEASURE_LONG_FUNCTION,
    CodeMeasures,
)
from _audit.pointers import FINDING_FUTURE_DATE, FINDING_MISSING_PATH, InstructionPointers, NamedPath
from _audit.related import RelatedFiles
from _audit.scope import ControlPlaneFiles, RepositoryPath
from _audit.works import FINDING_NAMED_WORK, NamedWorks

LONG_FUNCTION = "def counted():\n" + "".join(f"    step_{number} = {number}\n" for number in range(25))
FOUR_ARGUMENTS = "def joined(first, second, third, fourth):\n    return first\n"
COMMENTED = "# a note to the reader\nvalue = 1\n"
DOCUMENTED = "class Work:\n    def run(self):\n        \"\"\"Run it.\"\"\"\n        return 1\n"
TODAY = date(2026, 9, 15)
FUTURE_DATE_NOTE = "Decided 2027-01-01 to keep it.\n"
PAST_DATE_NOTE = "Decided 2020-01-01 to keep it.\n"
MISSING_PATH_NOTE = "Run `.claude/skills/no-such-skill/SKILL.md` first.\n"
PRESENT_PATH = "skills/present/SKILL.md"
NAMED_WORK = "Roe - 2021 - A Split Sentence"
NAMED_WORK_RULE = f"If the PDF is `{NAMED_WORK}.pdf`, skip its first page.\n"
NAMED_WORK_CONSTANT = f'SKIPPED = "{NAMED_WORK}"\n'
BASENAME_PATTERN_RULE = "Name the PDF `<FirstCreator> - <Year> - <Title>.pdf`.\n"
PRESENT_PATH_NOTE = f"Run `{PRESENT_PATH}` first.\n"
REPOSITORY_FILES = {
    "contract": ("CLAUDE.md", ".mcp.json", "requirements.txt", ".claude/settings.json"),
    "skills": (".claude/skills/one/SKILL.md", ".claude/skills/one/reference/table.md"),
    "workers": (".claude/agents/worker.md",),
    "code": ("lib/vault.py", "lib/_vault/notes.py", ".claude/skills/one/scripts/run.py",
             ".claude/skills/one/scripts/_run/core.py"),
    "tests": ("tests/test_one.py", "tests/ports/test_two_contract.py", "tests/README.md",
              "tests/fixtures/goldens/case.json"),
    "configuration": ("pyproject.toml", "lib/profiles/mac-local.json", ".github/workflows/ci.yml",
                      ".github/actions/empty-vault/action.yml"),
}
CONFIGURATION_FILES = (*REPOSITORY_FILES["configuration"], "tests/fixtures/goldens/case.json")
STRAY_FILES = ("README.md", ".claude/skills/one/notes.txt", "lib/data.json")
INSTRUCTION_GROUPS = ("contract", "skills", "workers")
VAULT_NOTE = "research vault/corpus/x.md"
LIBRARY_PDF = "library/paper.pdf"
HOME_NOTE = "notes.md"


class TemporaryFiles:
    def __init__(self, case: unittest.TestCase) -> None:
        self._directory = tempfile.TemporaryDirectory()
        case.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)

    def written(self, name: str, text: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def populated(self, names: tuple[str, ...]) -> list[Path]:
        return [self.written(name, "") for name in names]


class FakeControlPlane:
    def __init__(self, paths: list[Path]) -> None:
        self._paths = paths

    def all(self) -> list[Path]:
        return self._paths


class TestBaseline(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.baseline = Baseline(self.files.root / "baseline.json")
        self.note = self.files.written("note.md", "first\n")

    def test_an_unaccepted_baseline_has_no_date(self) -> None:
        self.assertIsNone(self.baseline.accepted_on())

    def test_a_file_never_audited_is_new(self) -> None:
        self.assertEqual([self.note.as_posix()], self.baseline.changed([self.note])[STATUS_NEW])

    def test_an_accepted_file_is_neither_new_nor_changed(self) -> None:
        self.baseline.accept([self.note])
        expected = {STATUS_NEW: [], STATUS_CHANGED: [], STATUS_REMOVED: []}
        self.assertEqual(expected, self.baseline.changed([self.note]))

    def test_an_edited_file_is_changed(self) -> None:
        self.baseline.accept([self.note])
        self.note.write_text("second\n", encoding="utf-8")
        self.assertEqual([self.note.as_posix()], self.baseline.changed([self.note])[STATUS_CHANGED])

    def test_a_deleted_file_is_removed(self) -> None:
        self.baseline.accept([self.note])
        self.assertEqual([self.note.as_posix()], self.baseline.changed([])[STATUS_REMOVED])

    def test_accepting_records_the_day_it_ran(self) -> None:
        baseline = Baseline(self.files.root / "dated.json", TODAY)
        self.assertEqual(TODAY.isoformat(), baseline.accept([self.note])["accepted"])


class TestABaselineTornMidWrite(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.path = self.files.root / "baseline.json"
        self.note = self.files.written("note.md", "first\n")
        Baseline(self.path, TODAY).accept([self.note])

    def test_an_accept_torn_mid_write_keeps_the_earlier_baseline(self) -> None:
        original = Path.write_text

        def torn(path: Path, text: str, *args, **kwargs) -> int:
            original(path, text[: len(text) // 2], *args, **kwargs)
            raise OSError("disk full")

        with mock.patch.object(Path, "write_text", torn), self.assertRaises(OSError):
            Baseline(self.path).accept([self.note])
        self.assertEqual(TODAY.isoformat(), Baseline(self.path).accepted_on())

    def test_a_baseline_that_is_not_json_is_reported_as_corrupt(self) -> None:
        self.path.write_text('{"accepted": "2026', encoding="utf-8")
        with self.assertRaises(CorruptBaseline) as raised:
            Baseline(self.path).accepted_on()
        self.assertIn(str(self.path), str(raised.exception))

    def test_a_corrupt_baseline_is_printed_as_an_error_and_exits_one(self) -> None:
        printed = io.StringIO()
        with mock.patch.object(Baseline, "accepted_on", side_effect=CorruptBaseline("the audit baseline is torn")):
            with contextlib.redirect_stdout(printed), self.assertRaises(SystemExit) as stopped:
                CommandLine().run(["changed"])
        self.assertEqual((1, {"error": "the audit baseline is torn"}), (stopped.exception.code,
                                                                        json.loads(printed.getvalue())))


class TestCodeMeasures(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)

    def _measures(self, name: str, source: str) -> list[str]:
        findings = CodeMeasures([self.files.written(name, source)]).findings()
        return [finding["measure"] for finding in findings]

    def test_a_function_over_twenty_lines_is_measured(self) -> None:
        self.assertIn(MEASURE_LONG_FUNCTION, self._measures("long.py", LONG_FUNCTION))

    def test_a_function_with_four_arguments_is_measured(self) -> None:
        self.assertIn(MEASURE_ARGUMENTS, self._measures("arguments.py", FOUR_ARGUMENTS))

    def test_a_comment_is_measured(self) -> None:
        self.assertIn(MEASURE_COMMENT, self._measures("commented.py", COMMENTED))

    def test_a_docstring_is_measured(self) -> None:
        self.assertIn(MEASURE_DOCSTRING, self._measures("documented.py", DOCUMENTED))

    def test_code_that_meets_the_standard_measures_nothing(self) -> None:
        self.assertEqual([], self._measures("clean.py", "class Work:\n    def run(self):\n        return 1\n"))


class TestInstructionPointers(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.written(PRESENT_PATH, "")

    def _findings(self, name: str, text: str) -> list[str]:
        pointers = InstructionPointers([self.files.written(name, text)], TODAY, root=self.files.root)
        return [finding["finding"] for finding in pointers.findings()]

    def test_a_path_that_does_not_exist_is_reported(self) -> None:
        self.assertEqual([FINDING_MISSING_PATH], self._findings("missing.md", MISSING_PATH_NOTE))

    def test_a_path_that_exists_is_not_reported(self) -> None:
        self.assertEqual([], self._findings("present.md", PRESENT_PATH_NOTE))

    def test_a_date_in_the_future_is_reported(self) -> None:
        self.assertEqual([FINDING_FUTURE_DATE], self._findings("future.md", FUTURE_DATE_NOTE))

    def test_a_date_in_the_past_is_not_reported(self) -> None:
        self.assertEqual([], self._findings("past.md", PAST_DATE_NOTE))


class TestNamedWorks(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)

    def _findings(self, name: str, text: str) -> list[dict]:
        return NamedWorks([self.files.written(name, text)], root=self.files.root).findings()

    def test_a_basename_in_instruction_text_is_reported_with_its_line(self) -> None:
        expected = [{"file": "rule.md", "line": 1, "finding": FINDING_NAMED_WORK, "detail": f"{NAMED_WORK}.pdf"}]
        self.assertEqual(expected, self._findings("rule.md", NAMED_WORK_RULE))

    def test_a_basename_in_a_string_constant_is_reported(self) -> None:
        self.assertEqual([NAMED_WORK],
                         [finding["detail"] for finding in self._findings("code.py", NAMED_WORK_CONSTANT)])

    def test_the_basename_pattern_with_placeholders_is_not_reported(self) -> None:
        self.assertEqual([], self._findings("pattern.md", BASENAME_PATTERN_RULE))


class TestNamedPath(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)

    def test_a_vault_path_with_a_space_resolves_under_the_vault(self) -> None:
        self.files.written(VAULT_NOTE, "")
        with mock.patch.object(vault, "VAULT_ROOT", self.files.root):
            self.assertFalse(NamedPath(VAULT_NOTE, self.files.root / "elsewhere").is_missing())

    def test_a_library_path_resolves_under_the_vault(self) -> None:
        self.files.written(LIBRARY_PDF, "")
        with mock.patch.object(vault, "VAULT_ROOT", self.files.root):
            self.assertFalse(NamedPath(LIBRARY_PDF, self.files.root / "elsewhere").is_missing())

    def test_a_home_path_expands(self) -> None:
        self.files.written(HOME_NOTE, "")
        with mock.patch.dict(os.environ, {"HOME": str(self.files.root)}):
            self.assertFalse(NamedPath(f"~/{HOME_NOTE}", self.files.root / "elsewhere").is_missing())

    def test_a_placeholder_is_not_a_path(self) -> None:
        self.assertFalse(NamedPath("<basename>.md", self.files.root).is_missing())

    def test_a_bare_root_file_names_a_path(self) -> None:
        self.assertTrue(NamedPath("CLAUDE.md", self.files.root).is_missing())
        self.files.written("CLAUDE.md", "")
        self.assertFalse(NamedPath("CLAUDE.md", self.files.root).is_missing())


class TestControlPlaneFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        for names in REPOSITORY_FILES.values():
            self.files.populated(names)
        self.files.populated(STRAY_FILES)
        self.control_plane = ControlPlaneFiles(self.files.root)

    def test_every_repository_file_lands_in_its_group(self) -> None:
        expected = {group: sorted(self.files.root / name for name in names)
                    for group, names in REPOSITORY_FILES.items()}
        self.assertEqual(expected, self.control_plane.by_group())

    def test_a_file_outside_the_patterns_is_in_no_group(self) -> None:
        strays = {self.files.root / name for name in STRAY_FILES}
        self.assertEqual(set(), strays & set(self.control_plane.all()))


class TestControlPlaneFilesNeitherInstructionNorCode(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.configuration = self.files.populated(CONFIGURATION_FILES)
        self.control_plane = ControlPlaneFiles(self.files.root)

    def test_the_linter_configuration_the_ci_files_and_the_test_fixtures_are_control_plane_files(self) -> None:
        self.assertEqual(sorted(self.configuration), sorted(self.control_plane.all()))


class TestAChangedFileThatIsNotPython(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        for names in REPOSITORY_FILES.values():
            self.files.populated(names)
        self.files.populated(CONFIGURATION_FILES)
        self.control_plane = ControlPlaneFiles(self.files.root)
        self.baseline_path = self.files.root / "audit" / "baseline.json"
        Baseline(self.baseline_path).accept(self.control_plane.all())

    def test_a_changed_file_that_is_not_python_is_shown(self) -> None:
        edited = [self.files.written(name, "edited\n") for name in ("tests/README.md", *CONFIGURATION_FILES)]
        changed = AuditSet.of_changes(self.control_plane, self.baseline_path).as_dict()["changed"]
        self.assertEqual(sorted(RepositoryPath(path).label() for path in edited), sorted(changed))


class TestAuditSet(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        for names in REPOSITORY_FILES.values():
            self.files.populated(names)
        self.control_plane = ControlPlaneFiles(self.files.root)
        self.baseline_path = self.files.root / "audit" / "baseline.json"

    def _instructions(self) -> list[Path]:
        return sorted(AuditSet.of_changes(self.control_plane, self.baseline_path).instructions())

    def test_everything_is_unaudited_before_any_acceptance(self) -> None:
        expected = sorted(self.files.root / name for group in INSTRUCTION_GROUPS for name in REPOSITORY_FILES[group])
        self.assertEqual(expected, self._instructions())

    def test_only_the_files_changed_since_acceptance_are_unaudited(self) -> None:
        Baseline(self.baseline_path).accept(self.control_plane.all())
        edited = self.files.written("CLAUDE.md", "edited\n")
        self.assertEqual([edited], self._instructions())

    def test_the_audit_set_of_everything_holds_every_file_after_acceptance(self) -> None:
        Baseline(self.baseline_path).accept(self.control_plane.all())
        instructions = AuditSet.of_everything(self.control_plane, self.baseline_path).instructions()
        self.assertEqual(sorted(self.control_plane.of_groups(INSTRUCTION_GROUPS)), sorted(instructions))

    def test_pipeline_code_leaves_the_tests_out(self) -> None:
        pipeline_code = AuditSet.of_changes(self.control_plane, self.baseline_path).pipeline_code()
        self.assertEqual(sorted(self.files.root / name for name in REPOSITORY_FILES["code"]), sorted(pipeline_code))

    def test_counts_name_the_three_totals(self) -> None:
        counts = AuditSet.of_changes(self.control_plane, self.baseline_path).counts()
        self.assertEqual({"instructions": 7, "code": 6, "control_plane": 19}, counts)


class TestRelatedFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.changed = self.files.written("engine.py", "class Engine:\n    pass\n")
        self.caller = self.files.written("skill.md", "The stage runs `engine.py`.\n")
        self.stranger = self.files.written("other.md", "Nothing to do with it.\n")
        self.control_plane = FakeControlPlane([self.changed, self.caller, self.stranger])

    def test_a_file_that_names_a_changed_file_is_related(self) -> None:
        related = RelatedFiles(self.control_plane).of([self.changed])
        self.assertEqual(["skill.md"], [path.name for path in related])

    def test_nothing_is_related_to_an_empty_change_set(self) -> None:
        self.assertEqual([], RelatedFiles(self.control_plane).of([]))


class TestCommandLine(unittest.TestCase):
    def test_no_arguments_print_help(self) -> None:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            CommandLine().run([])
        self.assertTrue(captured.getvalue().startswith("usage: audit.py"))


if __name__ == "__main__":
    unittest.main()
