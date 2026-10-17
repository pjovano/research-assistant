from __future__ import annotations

import ast
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import vault
from _vault.paths import MACHINE, VAULT_DIR_KEY
from agent_core._audit.checks import DomainChecks, PrimaryOnly
from agent_core._audit.cli import AuditSet
from agent_core._audit.contract import ContractLocations, ContractTables, HookList, JsonKeys
from agent_core._audit.rows import Row
from agent_core._audit.scope import CORE_SCOPE, ENCODING, INSTRUCTION_GROUPS, ControlPlaneFiles, RepositoryPath, Scope

WORK_BASENAME = re.compile(r"[^\s`\"'(\[][^\n`\"']{0,60}? - (?:1[5-9]|20)\d{2}[a-z]? - [^\n`\"']{1,80}")
QUOTED_COUNT = re.compile(r"\b(\d[\d,]*) (works|PDFs|corpus files)\b")
DIGIT_GROUP_SEPARATOR = ","
HELP_STALENESS = "each count of works, PDFs, or corpus files in instruction text that differs from the vault's count"
FINDING_NAMED_WORK = "work-named"
RULE_FILE_PAGE = "literal-file-page"
RULE_FONT_NAME = "exact-font-name"
PAGE_WORD = "page"
FONT_WORD = "font"
COMPARISONS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)
COLLECTIONS = (ast.Tuple, ast.List, ast.Set)
CONTRACT = "AGENTS.md"
OPERATION_SECTION = "## 4. Operation"
HOOK_LIST_MARKER = "turns `"
FIRST_AND_LAST_PAGES = (0, 1, -1)
ORPHAN_PATTERNS = ("*.tmp", "*.bak", "*~", "*.part", "*.partial")
SECONDS_PER_DAY = 86400
BYTES_PER_MEGABYTE = 1048576
HELP_RESIDUE = "the stranded work product at every residue site"
NO_REAL_VAULT = (f"machine.json names {VAULT_DIR_KEY}, which only CI and a test container set: no real vault is "
                 f"present, and this check runs only on the primary")


class VaultRoot:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def resolved(self, token: str) -> Path:
        return vault.VAULT_ROOT / token


class NamedWorks:
    def __init__(self, paths: list[Path], root: Path) -> None:
        self._paths = paths
        self._root = root

    def findings(self) -> list[dict]:
        return [finding for path in self._paths for finding in self._of_file(path)]

    def _of_file(self, path: Path) -> list[dict]:
        numbered = enumerate(path.read_text(encoding=ENCODING).splitlines(), start=1)
        return [self._finding(path, number, match.group(0).strip())
                for number, line in numbered for match in WORK_BASENAME.finditer(line)]

    def _finding(self, path: Path, line: int, detail: str) -> dict:
        return Row(FINDING_NAMED_WORK, RepositoryPath(path, self._root).label(), line, detail).as_dict()


class WorksCheck:
    name = "works"

    def findings(self, audit_set: AuditSet) -> list[dict]:
        return NamedWorks(audit_set.instructions() + audit_set.pipeline_code(), audit_set.root).findings()


class PdfKeyedSigns:
    name = "special"

    def findings(self, audit_set: AuditSet) -> list[dict]:
        return [row for path in audit_set.pipeline_code() for row in PdfKeyedComparisons(path, audit_set.root).rows()]


class PdfKeyedComparisons:
    def __init__(self, path: Path, root: Path) -> None:
        self._path = path
        self._label = RepositoryPath(path, root).label()

    def rows(self) -> list[dict]:
        try:
            tree = ast.parse(self._path.read_text(encoding=ENCODING))
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            return []
        return [row for node in ast.walk(tree) if isinstance(node, ast.Compare)
                and any(isinstance(operator, COMPARISONS) for operator in node.ops) for row in self._of(node)]

    def _of(self, node: ast.Compare) -> list[dict]:
        operands = [node.left, *node.comparators]
        named = " ".join(self._name_of(operand) for operand in operands).lower()
        literals = [value for operand in operands for value in self._literals(operand)]
        if PAGE_WORD in named and any(self._is_a_page_number(value) for value in literals):
            return [Row(RULE_FILE_PAGE, self._label, node.lineno, f"compares a page with {literals!r}").as_dict()]
        if FONT_WORD in named and any(isinstance(value, str) for value in literals):
            return [Row(RULE_FONT_NAME, self._label, node.lineno, f"compares a font with {literals!r}").as_dict()]
        return []

    @staticmethod
    def _is_a_page_number(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value not in FIRST_AND_LAST_PAGES

    @staticmethod
    def _name_of(operand: ast.expr) -> str:
        if isinstance(operand, ast.Name):
            return operand.id
        if isinstance(operand, ast.Attribute):
            return operand.attr
        if isinstance(operand, ast.Call):
            return PdfKeyedComparisons._name_of(operand.func)
        return ""

    @staticmethod
    def _literals(operand: ast.expr) -> list[object]:
        elements = operand.elts if isinstance(operand, COLLECTIONS) else [operand]
        return [element.value for element in elements if isinstance(element, ast.Constant)]


class Residue:
    name = "residue"
    help = HELP_RESIDUE

    def __init__(self, scratch: Path = vault.SCRATCH_DIR, corpus: Path = vault.CORPUS_DIR) -> None:
        self._scratch = scratch
        self._corpus = corpus

    def report(self, root: Path) -> dict:
        return {"scratch": DirectoryPile(self._scratch).summary(),
                "conflict_copies": vault.library_conflict_copies(),
                "corpus_without_pdf": self._corpus_without_pdf(),
                "bytecode_directories": self._bytecode(root),
                "orphans": self._orphans(),
                "inbox_files": sorted(path.name for path in vault.INBOX_DIR.glob("*") if path.is_file())}

    def _corpus_without_pdf(self) -> list[str]:
        held = vault.HeldBasenames((vault.LIBRARY_DIR, vault.VOLUMES_DIR)).keys()
        notes = vault.list_markdown(self._corpus)
        return sorted(vault.basename_of(path) for path in notes if vault.basename_of(path) not in held)

    @staticmethod
    def _bytecode(root: Path) -> list[str]:
        return sorted(str(path.relative_to(root)) for path in root.rglob("__pycache__"))

    @staticmethod
    def _orphans() -> list[str]:
        root = vault.VAULT_ROOT
        found = {path for pattern in ORPHAN_PATTERNS for path in root.rglob(pattern) if path.is_file()}
        return sorted(str(path.relative_to(root)) for path in found)


class DirectoryPile:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def summary(self) -> dict:
        files = [path for path in self._directory.rglob("*") if path.is_file()] if self._directory.exists() else []
        return {"path": self._directory.name, "files": len(files), "megabytes": self._megabytes(files),
                "oldest_days": self._oldest_days(files)}

    @staticmethod
    def _megabytes(files: list[Path]) -> float:
        return round(sum(path.stat().st_size for path in files) / BYTES_PER_MEGABYTE, 1)

    @staticmethod
    def _oldest_days(files: list[Path]) -> int:
        if not files:
            return 0
        oldest = min(path.stat().st_mtime for path in files)
        return int((time.time() - oldest) / SECONDS_PER_DAY)


class Staleness:
    name = "staleness"
    help = HELP_STALENESS

    def report(self, root: Path) -> dict:
        on_disk = VaultCounts.counted()
        instructions = ControlPlaneFiles(root, CORE_SCOPE.extended_by(RESEARCH_SCOPE)).of_groups(INSTRUCTION_GROUPS)
        return {"on_disk": on_disk, "figures": QuotedCounts(instructions, root).differing_from(on_disk)}


class VaultCounts:
    @staticmethod
    def counted() -> dict[str, int]:
        pdfs = vault.list_pdfs(vault.LIBRARY_DIR) + vault.list_pdfs(vault.VOLUMES_DIR)
        return {"works": len(vault.list_held_notes()), "PDFs": len(pdfs),
                "corpus files": len(vault.list_corpus_files())}


class QuotedCounts:
    def __init__(self, paths: list[Path], root: Path) -> None:
        self._paths = paths
        self._root = root

    def differing_from(self, on_disk: dict[str, int]) -> list[dict]:
        figures = [figure for path in self._paths for figure in self._of_file(path)]
        return [{**figure, "on_disk": on_disk[figure["noun"]]} for figure in figures
                if figure["quoted"] != on_disk[figure["noun"]]]

    def _of_file(self, path: Path) -> list[dict]:
        label = RepositoryPath(path, self._root).label()
        numbered = enumerate(path.read_text(encoding=ENCODING).splitlines(), start=1)
        return [{"file": label, "line": number, "quoted": self._number(match.group(1)), "noun": match.group(2)}
                for number, line in numbered for match in QUOTED_COUNT.finditer(line)]

    @staticmethod
    def _number(numeral: str) -> int:
        return int(numeral.replace(DIGIT_GROUP_SEPARATOR, ""))


class RealVault:
    def __init__(self, machine: dict) -> None:
        self._machine = machine

    def is_present(self) -> bool:
        return not self._machine.get(VAULT_DIR_KEY)

    def absence(self) -> str:
        return NO_REAL_VAULT


RESEARCH_SCOPE = Scope(
    root_files=(".mcp.json", "requirements.txt", "requirements.lock"),
    patterns={"code": (".claude/skills/*/server.py",),
              "configuration": ("lib/profiles/*.json", ".github/actions/*/*")},
    named_roots=(VaultRoot("library/"), VaultRoot("research vault/")),
)

REAL_VAULT = RealVault(MACHINE)

RESEARCH_CONTRACT = ContractLocations(
    stage_table=ContractTables(CONTRACT, OPERATION_SECTION, ("Stage", "Skill", "Model")),
    operation_tables=ContractTables(CONTRACT, OPERATION_SECTION, ("Operation", "Skill")),
    hook_list=HookList(CONTRACT, HOOK_LIST_MARKER, JsonKeys("domain.json", ("policy", "prompt_on"))),
)

DOMAIN = DomainChecks(scope=RESEARCH_SCOPE, lint=(WorksCheck(), PdfKeyedSigns()),
                      reports=(PrimaryOnly(Residue(), REAL_VAULT), PrimaryOnly(Staleness(), REAL_VAULT)),
                      contract=RESEARCH_CONTRACT)
