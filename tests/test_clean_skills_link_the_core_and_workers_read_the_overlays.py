from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
VENDORED_SKILLS_DIR = PROJECT_ROOT / "vendor" / "agent-core" / "skills"
CLEAN_SKILLS = ("clean-code", "clean-prose")
SYMLINK_MODE = "120000"
FRONTMATTER_FENCE = "---"
NAME_KEY = "name:"
CODE_STANDARD = (".claude/skills/clean-code/SKILL.md", ".claude/code-overlay.md")
PROSE_STANDARD = (".claude/skills/clean-prose/SKILL.md", ".claude/glossary.md")
CODE_WRITING_WORKERS = ("extraction-fixer", "page-reader", "pdf-bookmarker", "pdf-cleaner", "pdf-filer",
                        "work-classifier")
PROSE_WRITING_WORKERS = ("extraction-fixer",)


class SkillLink:
    def __init__(self, skill: str) -> None:
        self._relative = f".claude/skills/{skill}"

    def is_tracked_as_symlink(self) -> bool:
        listing = subprocess.run(["git", "ls-files", "--stage", "--", self._relative], cwd=PROJECT_ROOT,
                                 capture_output=True, text=True, check=True).stdout
        return listing.startswith(SYMLINK_MODE)

    def target(self) -> Path:
        return (PROJECT_ROOT / self._relative).resolve()

    def skill_name(self) -> str | None:
        lines = (PROJECT_ROOT / self._relative / "SKILL.md").read_text(encoding="utf-8").splitlines()
        names = [line.removeprefix(NAME_KEY).strip() for line in self._frontmatter(lines) if line.startswith(NAME_KEY)]
        return names[0] if names else None

    @staticmethod
    def _frontmatter(lines: list[str]) -> list[str]:
        if not lines or lines[0] != FRONTMATTER_FENCE or FRONTMATTER_FENCE not in lines[1:]:
            return []
        return lines[1:lines.index(FRONTMATTER_FENCE, 1)]


class WorkerInstructions:
    def __init__(self, worker: str) -> None:
        self._text = (AGENTS_DIR / f"{worker}.md").read_text(encoding="utf-8")

    def reads_in_order(self, paths: tuple[str, ...]) -> bool:
        positions = [self._text.find(f"`{path}`") for path in paths]
        return -1 not in positions and positions == sorted(positions)

    def names_any(self, paths: tuple[str, ...]) -> bool:
        return any(f"`{path}`" in self._text for path in paths)


class EachCleanSkillIsASymlinkIntoTheVendoredCore(unittest.TestCase):
    def test_each_skill_directory_is_tracked_as_a_symlink(self) -> None:
        self.assertEqual([], [skill for skill in CLEAN_SKILLS if not SkillLink(skill).is_tracked_as_symlink()])

    def test_each_link_resolves_to_its_skill_in_the_vendored_core(self) -> None:
        expected = {skill: (VENDORED_SKILLS_DIR / skill).resolve() for skill in CLEAN_SKILLS}
        self.assertEqual(expected, {skill: SkillLink(skill).target() for skill in CLEAN_SKILLS})

    def test_each_linked_skill_file_names_its_directory(self) -> None:
        self.assertEqual({skill: skill for skill in CLEAN_SKILLS},
                         {skill: SkillLink(skill).skill_name() for skill in CLEAN_SKILLS})


class EachWorkerReadsTheGeneralStandardThenTheOverlay(unittest.TestCase):
    def test_each_worker_that_writes_code_names_clean_code_then_the_code_overlay(self) -> None:
        silent = [worker for worker in CODE_WRITING_WORKERS
                  if not WorkerInstructions(worker).reads_in_order(CODE_STANDARD)]
        self.assertEqual([], silent)

    def test_each_worker_that_writes_instruction_text_names_clean_prose_then_the_glossary(self) -> None:
        silent = [worker for worker in PROSE_WRITING_WORKERS
                  if not WorkerInstructions(worker).reads_in_order(PROSE_STANDARD)]
        self.assertEqual([], silent)

    def test_no_other_worker_names_the_prose_standard(self) -> None:
        others = sorted(path.stem for path in AGENTS_DIR.glob("*.md") if path.stem not in PROSE_WRITING_WORKERS)
        self.assertEqual([], [worker for worker in others if WorkerInstructions(worker).names_any(PROSE_STANDARD)])

    def test_every_standard_path_a_worker_names_resolves(self) -> None:
        missing = [path for path in CODE_STANDARD + PROSE_STANDARD if not os.path.isfile(PROJECT_ROOT / path)]
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
