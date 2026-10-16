from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

INSTRUCTION_PATTERNS = ("CLAUDE.md", "AGENTS.md", "README.md", ".claude/*.md", ".claude/**/*.md")
PEER_PHRASES = ("on each machine", "each machine's", "either machine", "both machines", "both environments",
                "per machine", "two machines", "two macs")
KEPT_SENTENCES = ("two machines editing the same corpus file through iCloud at once",
                  "when two machines change it at once")
WHITESPACE_RUN = re.compile(r"\s+")
IMPORT_LINE = "@AGENTS.md"
VOCABULARY_FILE = PROJECT_ROOT / ".claude" / "glossary.md"
ROLE_AND_TRAILER_TERMS = ("primary", "secondary", "`Defect-class:` trailer", "`Change-class:` trailer")
TABLE_CELL_SEPARATOR = "|"


class PeerPhrases:
    def found_in(self, text: str) -> list[str]:
        searched = self._without_kept_sentences(WHITESPACE_RUN.sub(" ", text).lower())
        return [phrase for phrase in PEER_PHRASES if phrase in searched]

    @staticmethod
    def _without_kept_sentences(text: str) -> str:
        for sentence in KEPT_SENTENCES:
            text = text.replace(sentence.lower(), "")
        return text


class InstructionFiles:
    def __init__(self, repository_root: Path) -> None:
        self._root = repository_root

    def peer_phrases_found(self) -> list[str]:
        phrases = PeerPhrases()
        return [f"{label}: {phrase}" for label in self._tracked() for phrase in phrases.found_in(self._text(label))]

    def _tracked(self) -> list[str]:
        listing = subprocess.run(["git", "ls-files", "--", *INSTRUCTION_PATTERNS], cwd=self._root,
                                 capture_output=True, text=True, check=True).stdout
        return sorted(set(listing.splitlines()))

    def _text(self, label: str) -> str:
        return (self._root / label).read_text(encoding="utf-8")


class VocabularyTerms:
    def __init__(self, skill_file: Path) -> None:
        self._skill_file = skill_file

    def terms(self) -> set[str]:
        lines = self._skill_file.read_text(encoding="utf-8").splitlines()
        return {self._first_cell(line) for line in lines if line.startswith(TABLE_CELL_SEPARATOR)}

    @staticmethod
    def _first_cell(row: str) -> str:
        return row.split(TABLE_CELL_SEPARATOR)[1].strip()


class NoInstructionFileNamesTwoMachinesAsPeers(unittest.TestCase):
    def test_no_instruction_file_names_a_peer_machine_phrase(self) -> None:
        self.assertEqual([], InstructionFiles(PROJECT_ROOT).peer_phrases_found())

    def test_a_peer_phrase_wrapped_across_lines_is_found(self) -> None:
        self.assertEqual(["either machine"], PeerPhrases().found_in("On either\nmachine the key MUST be absent."))

    def test_a_kept_sentence_names_no_peer_phrase(self) -> None:
        kept = "a sibling file a sync service leaves when two machines\nchange it at once"
        self.assertEqual([], PeerPhrases().found_in(kept))

    def test_both_used_of_anything_but_machines_is_no_peer_phrase(self) -> None:
        self.assertEqual([], PeerPhrases().found_in("The two works are tied on both keys."))


class ClaudeMdImportsTheContract(unittest.TestCase):
    def test_claude_md_holds_only_the_import_line(self) -> None:
        self.assertEqual(IMPORT_LINE, (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8").strip())

    def test_the_imported_contract_exists_at_the_repository_root(self) -> None:
        self.assertTrue((PROJECT_ROOT / "AGENTS.md").is_file())


class TheVocabularyDefinesTheMachineRolesAndTheTrailers(unittest.TestCase):
    def test_each_role_and_trailer_is_a_vocabulary_term(self) -> None:
        missing = set(ROLE_AND_TRAILER_TERMS) - VocabularyTerms(VOCABULARY_FILE).terms()
        self.assertEqual(set(), missing)


if __name__ == "__main__":
    unittest.main()
