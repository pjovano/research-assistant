from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import PROJECT_ROOT, LiveTree

LiveTree.activate()

import vault
from _audit_plane import COMPARED_ROWS, NAMED_WORK, OLD_ENGINE_LINT, AuditPlane
from _vaults import TempVault

from agent_core._audit.checks import SKIPPED_KEY, PrimaryOnly
from agent_core._audit.pointers import NamedPath
from agent_core._audit.scope import CORE_SCOPE, ControlPlaneFiles

CHECKS_FILE = PROJECT_ROOT / "audit" / "checks.py"
AUDIT_SCRIPT = PROJECT_ROOT / ".claude" / "skills" / "control-plane-audit" / "scripts" / "audit.py"
CORE_SKILL_LINK = PROJECT_ROOT / ".claude" / "skills" / "control-plane-audit"
VENDORED_CORE = PROJECT_ROOT / "vendor" / "agent-core"
NAMED_WORK_RULE = f"If the PDF is `{NAMED_WORK}.pdf`, skip its first page.\n"
NAMED_WORK_CONSTANT = f'SKIPPED = "{NAMED_WORK}"\n'
BASENAME_PATTERN_RULE = "Name the PDF `<FirstCreator> - <Year> - <Title>.pdf`.\n"
VAULT_NOTE = "research vault/corpus/x.md"
LIBRARY_PDF = "library/paper.pdf"
TEST_CONTAINER_MACHINE = {"vault_dir": "~/.research-vault/empty-vault"}
UPGRADE_DIRECTORY = "upgrade/"
REPOSITORY_FILES = {
    "contract": ("AGENTS.md", "CLAUDE.md", ".mcp.json", "requirements.txt", ".claude/settings.json"),
    "skills": (".claude/skills/one/SKILL.md", ".claude/skills/one/reference/table.md", ".claude/code-overlay.md",
               ".claude/glossary.md"),
    "workers": (".claude/agents/worker.md",),
    "code": ("lib/vault.py", "lib/_vault/notes.py", ".claude/skills/one/scripts/run.py",
             ".claude/skills/one/scripts/_run/core.py", ".claude/skills/one/server.py", "audit/checks.py"),
    "tests": ("tests/test_one.py", "tests/ports/test_two_contract.py", "tests/README.md",
              "tests/fixtures/goldens/case.json"),
    "configuration": ("pyproject.toml", "lib/profiles/mac-local.json", ".github/workflows/ci.yml",
                      ".github/actions/empty-vault/action.yml"),
}


class ResearchChecks:
    _module = None

    @classmethod
    def module(cls):
        if cls._module is None:
            specification = importlib.util.spec_from_file_location("research_audit_checks", CHECKS_FILE)
            cls._module = importlib.util.module_from_spec(specification)
            sys.modules[specification.name] = cls._module
            specification.loader.exec_module(cls._module)
        return cls._module

    @classmethod
    def control_plane(cls, root: Path) -> ControlPlaneFiles:
        return ControlPlaneFiles(root, CORE_SCOPE.extended_by(cls.module().RESEARCH_SCOPE))


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


class TestNamedWorks(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)

    def _findings(self, name: str, text: str) -> list[dict]:
        named_works = ResearchChecks.module().NamedWorks
        return named_works([self.files.written(name, text)], self.files.root).findings()

    def test_a_basename_in_instruction_text_is_reported_with_its_line(self) -> None:
        expected = [{"file": "rule.md", "line": 1, "finding": "work-named", "detail": f"{NAMED_WORK}.pdf"}]
        self.assertEqual(expected, self._findings("rule.md", NAMED_WORK_RULE))

    def test_a_basename_in_a_string_constant_is_reported(self) -> None:
        self.assertEqual([NAMED_WORK],
                         [finding["detail"] for finding in self._findings("code.py", NAMED_WORK_CONSTANT)])

    def test_the_basename_pattern_with_placeholders_is_not_reported(self) -> None:
        self.assertEqual([], self._findings("pattern.md", BASENAME_PATTERN_RULE))


class TestNamedPathUnderTheVault(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.elsewhere = ResearchChecks.control_plane(self.files.root / "elsewhere")

    def test_a_vault_path_with_a_space_resolves_under_the_vault(self) -> None:
        self.files.written(VAULT_NOTE, "")
        with mock.patch.object(vault, "VAULT_ROOT", self.files.root):
            self.assertFalse(NamedPath(VAULT_NOTE, self.elsewhere).is_missing())

    def test_a_library_path_resolves_under_the_vault(self) -> None:
        self.files.written(LIBRARY_PDF, "")
        with mock.patch.object(vault, "VAULT_ROOT", self.files.root):
            self.assertFalse(NamedPath(LIBRARY_PDF, self.elsewhere).is_missing())

    def test_a_missing_vault_path_is_reported(self) -> None:
        with mock.patch.object(vault, "VAULT_ROOT", self.files.root):
            self.assertTrue(NamedPath(VAULT_NOTE, self.elsewhere).is_missing())


class TestTheResearchScope(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        for names in REPOSITORY_FILES.values():
            for name in names:
                self.files.written(name, "")

    def test_every_repository_file_lands_in_its_group(self) -> None:
        expected = {group: sorted(self.files.root / name for name in names)
                    for group, names in REPOSITORY_FILES.items()}
        self.assertEqual(expected, ResearchChecks.control_plane(self.files.root).by_group())

    def test_no_scope_pattern_names_a_path_under_upgrade(self) -> None:
        groups = ResearchChecks.control_plane(self.files.root).scope.group_patterns()
        patterns = [pattern for group in groups.values() for pattern in group]
        self.assertEqual([], [pattern for pattern in patterns if pattern.startswith(UPGRADE_DIRECTORY)])


class TestResidueOnlyOnThePrimary(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.checks = ResearchChecks.module()

    def test_machine_json_naming_vault_dir_means_no_real_vault(self) -> None:
        self.assertFalse(self.checks.RealVault(TEST_CONTAINER_MACHINE).is_present())

    def test_machine_json_without_vault_dir_means_the_real_vault(self) -> None:
        self.assertTrue(self.checks.RealVault({}).is_present())

    def test_residue_reports_itself_skipped_where_machine_json_names_vault_dir(self) -> None:
        residue = PrimaryOnly(self.checks.Residue(self.files.root, self.files.root),
                              self.checks.RealVault(TEST_CONTAINER_MACHINE))
        self.assertEqual({SKIPPED_KEY: self.checks.NO_REAL_VAULT}, residue.report(self.files.root))

    def test_the_residue_subcommand_is_wired_through_the_primary_only_check(self) -> None:
        self.assertEqual(["residue"], [report.name for report in self.checks.DOMAIN.reports])
        self.assertIsInstance(self.checks.DOMAIN.reports[0], PrimaryOnly)


class TestResidueOnARealVault(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("INBOX_DIR", "LIBRARY_DIR", "VOLUMES_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        root_patch = mock.patch.object(vault, "VAULT_ROOT", self.vault.named(""))
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.files = TemporaryFiles(self)
        (self.files.root / "lib" / "__pycache__").mkdir(parents=True)
        (vault.INBOX_DIR / "waiting.pdf").write_bytes(b"")
        (vault.CORPUS_DIR / "unheld.md").write_text("", encoding="utf-8")
        (vault.LIBRARY_DIR / "torn.partial").write_bytes(b"")
        checks = ResearchChecks.module()
        self.report = PrimaryOnly(checks.Residue(vault.SCRATCH_DIR, vault.CORPUS_DIR),
                                  checks.RealVault({})).report(self.files.root)

    def test_the_residue_runs_and_reports_every_site(self) -> None:
        expected = {"bytecode_directories": ["lib/__pycache__"], "conflict_copies": [],
                    "corpus_without_pdf": ["unheld"], "inbox_files": ["waiting.pdf"],
                    "orphans": ["library/torn.partial"]}
        self.assertEqual(expected, {key: value for key, value in self.report.items() if key != "scratch"})


class TestTheVerdictsOfTheOldEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        plane = AuditPlane(self.files.root).built()
        (plane / "audit").mkdir()
        (plane / "audit" / "checks.py").symlink_to(CHECKS_FILE)
        completed = subprocess.run([sys.executable, str(AUDIT_SCRIPT), "--root", str(plane), "lint"],
                                   cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.lint = json.loads(completed.stdout)

    def test_the_core_engine_with_the_research_checks_gives_the_old_engines_rows(self) -> None:
        old = json.loads(OLD_ENGINE_LINT.read_text(encoding="utf-8"))
        self.assertEqual(old, {row: self.lint[row] for row in COMPARED_ROWS})


class TestTheBaselineOfTheResearchDomain(unittest.TestCase):
    def test_the_audit_baseline_sits_at_audit_baseline_json(self) -> None:
        recorded = json.loads((PROJECT_ROOT / "audit" / "baseline.json").read_text(encoding="utf-8"))
        self.assertIn("accepted", recorded)

    def test_accept_writes_the_baseline_under_the_root(self) -> None:
        files = TemporaryFiles(self)
        plane = AuditPlane(files.root).built()
        subprocess.run([sys.executable, str(AUDIT_SCRIPT), "--root", str(plane), "accept"], cwd=PROJECT_ROOT,
                       capture_output=True, check=True)
        self.assertTrue((plane / "audit" / "baseline.json").is_file())


class TestTheCoreAuditLink(unittest.TestCase):
    def test_the_link_is_relative(self) -> None:
        self.assertFalse(os.path.isabs(os.readlink(CORE_SKILL_LINK)))

    def test_the_link_resolves_into_the_vendored_core(self) -> None:
        self.assertTrue(CORE_SKILL_LINK.resolve().is_relative_to(VENDORED_CORE.resolve()))


if __name__ == "__main__":
    unittest.main()
