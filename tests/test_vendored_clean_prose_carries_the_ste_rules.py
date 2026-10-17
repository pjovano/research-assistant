from __future__ import annotations

import re
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

VENDORED_CLEAN_PROSE = PROJECT_ROOT / "vendor" / "agent-core" / "skills" / "clean-prose" / "SKILL.md"
GLOSSARY = PROJECT_ROOT / ".claude" / "glossary.md"
STE_SECTIONS = {
    "13": "The STE rules: scope and ratchet",
    "14": "The STE rules and their limits",
    "15": "How the STE rules count",
}
STE_TERMS = ("STE rule", "adoption ratchet", "technical name", "force word", "main clause", "noun cluster")
SECTION_HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)
VOCABULARY_ROW = re.compile(r"^\| ([^|]+?) \|", re.MULTILINE)


class MarkdownFile:
    def __init__(self, path: Path) -> None:
        self._text = path.read_text(encoding="utf-8")

    def section_titles(self) -> dict[str, str]:
        return dict(SECTION_HEADING.findall(self._text))

    def vocabulary_terms(self) -> set[str]:
        return set(VOCABULARY_ROW.findall(self._text))


class TheVendoredCleanProseCarriesTheSteRules(unittest.TestCase):
    def test_sections_thirteen_to_fifteen_state_the_ste_rules(self) -> None:
        titles = MarkdownFile(VENDORED_CLEAN_PROSE).section_titles()
        self.assertEqual(STE_SECTIONS, {number: titles.get(number) for number in STE_SECTIONS})

    def test_the_vendored_vocabulary_defines_each_ste_term(self) -> None:
        terms = MarkdownFile(VENDORED_CLEAN_PROSE).vocabulary_terms()
        self.assertEqual([], [term for term in STE_TERMS if term not in terms])

    def test_the_glossary_redefines_no_ste_term(self) -> None:
        terms = MarkdownFile(GLOSSARY).vocabulary_terms()
        self.assertEqual([], [term for term in STE_TERMS if term in terms])


if __name__ == "__main__":
    unittest.main()
