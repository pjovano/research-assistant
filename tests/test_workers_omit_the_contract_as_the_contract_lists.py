from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
CONTRACT_NAMES = ("AGENTS.md", "CLAUDE.md")
OMIT_KEY = "omitClaudeMd"
OMIT_SENTENCE = re.compile(rf"Every worker (?:but (?P<exempt>.+?) )?runs with `{OMIT_KEY}`")
CODE_SPAN = re.compile(r"`([^`]+)`")
WHITESPACE = re.compile(r"\s+")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
OMIT_LINE = re.compile(rf"^{OMIT_KEY}:[ \t]*true[ \t]*$", re.MULTILINE)


class OmitSentence:
    def __init__(self, contract_text: str) -> None:
        self._match = OMIT_SENTENCE.search(WHITESPACE.sub(" ", contract_text))

    def is_stated(self) -> bool:
        return self._match is not None

    def workers_loading_the_contract(self) -> set[str]:
        exempt = self._match.group("exempt") if self._match else None
        return set(CODE_SPAN.findall(exempt)) if exempt else set()


class Contract:
    def __init__(self, repository_root: Path) -> None:
        self._root = repository_root

    def omit_sentence(self) -> OmitSentence:
        stated = (sentence for sentence in map(OmitSentence, self._texts()) if sentence.is_stated())
        return next(stated, OmitSentence(""))

    def _texts(self) -> list[str]:
        paths = (self._root / name for name in CONTRACT_NAMES)
        return [path.read_text(encoding="utf-8") for path in paths if path.is_file()]


class Workers:
    def __init__(self, directory: Path) -> None:
        self._paths = sorted(directory.glob("*.md"))

    def names(self) -> set[str]:
        return {path.stem for path in self._paths}

    def omitting_the_contract(self) -> set[str]:
        return {path.stem for path in self._paths if self._omits_the_contract(path)}

    @staticmethod
    def _omits_the_contract(path: Path) -> bool:
        frontmatter = FRONTMATTER.match(path.read_text(encoding="utf-8"))
        return frontmatter is not None and OMIT_LINE.search(frontmatter.group(1)) is not None


class TheOmitSentenceNamesTheWorkersThatLoadTheContract(unittest.TestCase):
    def test_a_sentence_wrapped_across_lines_names_each_exempt_worker(self) -> None:
        text = "Every worker but `pdf-filer` and\n`work-reader` runs with\n`omitClaudeMd`, so it never loads it."
        self.assertEqual({"pdf-filer", "work-reader"}, OmitSentence(text).workers_loading_the_contract())

    def test_a_sentence_without_an_exemption_names_no_worker(self) -> None:
        self.assertEqual(set(), OmitSentence("Every worker runs with `omitClaudeMd`.").workers_loading_the_contract())

    def test_a_contract_without_the_sentence_states_none(self) -> None:
        self.assertFalse(OmitSentence("A worker inherits nothing.").is_stated())


class WorkerFiles:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def write(self, name: str, frontmatter_lines: list[str]) -> None:
        lines = ["---", f"name: {name}", "description: Stage 9 worker — reads: one thing.", *frontmatter_lines, "---"]
        (self._directory / f"{name}.md").write_text("\n".join(lines) + "\n\nThe body.\n", encoding="utf-8")


class AWorkerFileSetsOmitClaudeMdOnlyInItsFrontmatter(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        files = WorkerFiles(self.root)
        files.write("omitting", ["omitClaudeMd: true", "tools: Read"])
        files.write("loading", ["tools: Read"])
        files.write("set-false", ["omitClaudeMd: false"])
        (self.root / "in-body.md").write_text("---\nname: in-body\n---\n\nomitClaudeMd: true\n", encoding="utf-8")

    def test_only_a_frontmatter_set_to_true_omits_the_contract(self) -> None:
        self.assertEqual({"omitting"}, Workers(self.root).omitting_the_contract())


class EveryWorkerOmitsTheContractAsTheContractLists(unittest.TestCase):
    def setUp(self) -> None:
        self.sentence = Contract(PROJECT_ROOT).omit_sentence()
        self.workers = Workers(AGENTS_DIR)

    def test_the_contract_states_which_workers_run_with_omit_claude_md(self) -> None:
        self.assertTrue(self.sentence.is_stated())

    def test_every_worker_the_contract_exempts_exists(self) -> None:
        self.assertLessEqual(self.sentence.workers_loading_the_contract(), self.workers.names())

    def test_every_worker_the_contract_exempts_loads_the_contract(self) -> None:
        exempt = self.sentence.workers_loading_the_contract()
        self.assertEqual(set(), exempt & self.workers.omitting_the_contract())

    def test_every_other_worker_omits_the_contract(self) -> None:
        expected = self.workers.names() - self.sentence.workers_loading_the_contract()
        self.assertEqual(set(), expected - self.workers.omitting_the_contract())


if __name__ == "__main__":
    unittest.main()
