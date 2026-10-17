from __future__ import annotations

import ast
import unittest
from pathlib import Path

from _support import PROJECT_ROOT, SKILLS_DIR, LiveTree

LiveTree.activate()

import harness_hooks

DRIVER_MODULE_PATTERNS = ((PROJECT_ROOT / "lib" / "_drive", "*.py"), (SKILLS_DIR, "*/scripts/_*/drive*.py"),
                          (SKILLS_DIR, "extract-corpus/scripts/_extract/backfill*.py"),
                          (SKILLS_DIR, "ingest/scripts/_ingest/*.py"))


class DriverModule:
    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def all(cls) -> list[DriverModule]:
        return [cls(path) for root, pattern in DRIVER_MODULE_PATTERNS for path in sorted(root.glob(pattern))]

    def names(self, fragment: str) -> bool:
        tokens = self._tokens()
        return all(any(word in token for token in tokens) for word in fragment.split())

    def _tokens(self) -> list[str]:
        tree = ast.parse(self.path.read_text(encoding="utf-8"))
        constants = (node.value for node in ast.walk(tree) if isinstance(node, ast.Constant))
        return [token for value in constants if isinstance(value, str) for token in value.split()]


class TestDriversRunNoGuardedCommand(unittest.TestCase):
    def test_the_driver_modules_are_found(self) -> None:
        self.assertGreater(len(DriverModule.all()), 10)

    def test_no_driver_names_a_guarded_command_the_contract_does_not_authorize(self) -> None:
        guarded = [fragment for fragment in harness_hooks.PROJECT_PROMPT_ON.consequences()
                   if fragment not in harness_hooks.DRIVER_AUTHORIZED_COMMANDS]
        for module in DriverModule.all():
            for fragment in guarded:
                with self.subTest(module=module.path.name, fragment=fragment):
                    self.assertFalse(module.names(fragment))


if __name__ == "__main__":
    unittest.main()
