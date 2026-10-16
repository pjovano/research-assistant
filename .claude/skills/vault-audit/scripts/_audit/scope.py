from __future__ import annotations

import os
from pathlib import Path

import vault

REPOSITORY_ROOT = Path(vault.__file__).resolve().parents[1]
ROOT_FILES = ("AGENTS.md", "CLAUDE.md", ".mcp.json", "requirements.txt", "requirements.lock")
ENCODING = "utf-8"
GROUP_PATTERNS = {
    "contract": ROOT_FILES + (".claude/settings.json",),
    "skills": (".claude/skills/*/SKILL.md", ".claude/skills/*/reference/*", ".claude/code-overlay.md",
               ".claude/glossary.md"),
    "workers": (".claude/agents/*.md",),
    "code": ("lib/*.py", "lib/_*/*.py", ".claude/skills/*/server.py", ".claude/skills/*/scripts/*.py",
             ".claude/skills/*/scripts/_*/*.py"),
    "tests": ("tests/*.py", "tests/*/*.py", "tests/README.md", "tests/fixtures/**/*"),
    "configuration": ("pyproject.toml", "lib/profiles/*.json", ".github/workflows/*", ".github/actions/*/*"),
}
ALL_GROUPS = tuple(GROUP_PATTERNS)
INSTRUCTION_GROUPS = ("contract", "skills", "workers")
CODE_GROUPS = ("code", "tests")
PIPELINE_GROUPS = ("code",)


class ControlPlaneFiles:
    def __init__(self, root: Path = REPOSITORY_ROOT) -> None:
        self._root = root

    def by_group(self) -> dict[str, list[Path]]:
        return {group: self._matching(patterns) for group, patterns in GROUP_PATTERNS.items()}

    def of_groups(self, groups: tuple[str, ...]) -> list[Path]:
        grouped = self.by_group()
        return [path for group in groups for path in grouped[group]]

    def all(self) -> list[Path]:
        return self.of_groups(ALL_GROUPS)

    def _matching(self, patterns: tuple[str, ...]) -> list[Path]:
        found = {path for pattern in patterns for path in self._root.glob(pattern) if path.is_file()}
        return sorted(found)


class RepositoryPath:
    def __init__(self, path: Path, root: Path = REPOSITORY_ROOT) -> None:
        self._path = path
        self._root = root

    def label(self) -> str:
        lexical_path = self._lexical(self._path)
        resolved_root = self._root.resolve()
        candidates = ((lexical_path, self._lexical(self._root)), (lexical_path, resolved_root),
                      (self._path.resolve(), resolved_root))
        for path, root in candidates:
            if path.is_relative_to(root):
                return path.relative_to(root).as_posix()
        return self._path.as_posix()

    @staticmethod
    def _lexical(path: Path) -> Path:
        return Path(os.path.abspath(path))
