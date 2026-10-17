from __future__ import annotations

import re
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

VENDORED_CLEAN_PROSE = PROJECT_ROOT / "vendor" / "agent-core" / "skills" / "clean-prose" / "SKILL.md"
INSTRUCTION_GLOBS = ("AGENTS.md", ".claude/glossary.md", ".claude/code-overlay.md", ".claude/agents/*.md",
                     ".claude/skills/*/SKILL.md", ".claude/skills/*/reference/*.md")
SECTION_REFERENCE = re.compile(r"`clean-prose`(?:'s)? §(\d+)")
SECTION_HEADING = re.compile(r"^## (\d+)\. ", re.MULTILINE)


class CleanProseSections:
    def __init__(self, skill: Path) -> None:
        self._numbers = set(SECTION_HEADING.findall(skill.read_text(encoding="utf-8")))

    def holds(self, number: str) -> bool:
        return number in self._numbers


class InstructionText:
    def __init__(self, root: Path) -> None:
        self._root = root

    def section_references(self) -> list[tuple[str, str]]:
        return [(self._label(path), number) for path in self._files()
                for number in SECTION_REFERENCE.findall(path.read_text(encoding="utf-8"))]

    def _files(self) -> list[Path]:
        return sorted({path for pattern in INSTRUCTION_GLOBS for path in self._root.glob(pattern)})

    def _label(self, path: Path) -> str:
        return path.relative_to(self._root).as_posix()


class EveryCleanProseSectionTheDomainCitesExists(unittest.TestCase):
    def test_each_cited_section_names_a_heading_of_the_vendored_clean_prose(self) -> None:
        sections = CleanProseSections(VENDORED_CLEAN_PROSE)
        dangling = [reference for reference in InstructionText(PROJECT_ROOT).section_references()
                    if not sections.holds(reference[1])]
        self.assertEqual([], dangling)

    def test_the_domain_cites_at_least_one_section(self) -> None:
        self.assertNotEqual([], InstructionText(PROJECT_ROOT).section_references())


if __name__ == "__main__":
    unittest.main()
