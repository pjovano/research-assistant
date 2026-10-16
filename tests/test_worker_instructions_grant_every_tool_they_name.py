from __future__ import annotations

import re
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
TOOLS_LINE = re.compile(r"^tools:(.*)$", re.MULTILINE)
NAMED_TOOL = re.compile(r"\bthe ([A-Z][A-Za-z]+) tool\b")


class WorkerInstructions:
    def __init__(self, path: Path) -> None:
        self._text = path.read_text(encoding="utf-8")

    def granted_tools(self) -> set[str]:
        line = TOOLS_LINE.search(self._text)
        return {tool.strip() for tool in line.group(1).split(",")} if line else set()

    def named_tools(self) -> set[str]:
        return set(NAMED_TOOL.findall(self._text))


class WorkerInstructionsGrantEveryToolTheyName(unittest.TestCase):
    def test_every_tool_a_worker_is_told_to_use_is_in_its_tools_list(self) -> None:
        for path in sorted(AGENTS_DIR.glob("*.md")):
            instructions = WorkerInstructions(path)
            with self.subTest(worker=path.stem):
                self.assertLessEqual(instructions.named_tools(), instructions.granted_tools())


if __name__ == "__main__":
    unittest.main()
