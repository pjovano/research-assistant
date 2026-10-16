from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

VENDOR_DIR = PROJECT_ROOT / "vendor" / "agent-core"
SYMLINK_MODE = "120000"
CONTRACT_NAMES = ("AGENTS.md", "CLAUDE.md")


class TrackedLinks:
    def __init__(self, repository_root: Path, directory: str) -> None:
        self._root = repository_root
        self._directory = directory

    def paths(self) -> list[Path]:
        listing = subprocess.run(["git", "ls-files", "--stage", "--", self._directory], cwd=self._root,
                                 capture_output=True, text=True, check=True).stdout
        return [self._root / line.split("\t", 1)[1] for line in listing.splitlines()
                if line.startswith(SYMLINK_MODE)]

    def absolute(self) -> list[str]:
        return [self._label(path) for path in self.paths() if os.path.isabs(os.readlink(path))]

    def outside(self, target_directory: Path) -> list[str]:
        boundary = target_directory.resolve()
        return [self._label(path) for path in self.paths() if not self._lands_inside(path, boundary)]

    def _lands_inside(self, path: Path, boundary: Path) -> bool:
        target = path.resolve()
        return target.exists() and target.is_relative_to(boundary)

    def _label(self, path: Path) -> str:
        return f"{path.relative_to(self._root).as_posix()} -> {os.readlink(path)}"


CLAUDE_LINKS = TrackedLinks(PROJECT_ROOT, ".claude")


class EveryLinkUnderClaudeResolvesIntoTheVendoredCore(unittest.TestCase):
    def test_the_domain_links_at_least_one_core_unit(self) -> None:
        self.assertTrue(CLAUDE_LINKS.paths())

    def test_every_link_is_relative(self) -> None:
        self.assertEqual([], CLAUDE_LINKS.absolute())

    def test_every_link_resolves_to_an_existing_path_inside_the_vendored_core(self) -> None:
        self.assertEqual([], CLAUDE_LINKS.outside(VENDOR_DIR))


class TheVendoredCoreCarriesNoContract(unittest.TestCase):
    def test_the_vendored_core_exists(self) -> None:
        self.assertTrue(VENDOR_DIR.is_dir())

    def test_no_contract_file_sits_at_any_depth_of_the_vendored_core(self) -> None:
        found = sorted(path.relative_to(PROJECT_ROOT).as_posix()
                       for name in CONTRACT_NAMES for path in VENDOR_DIR.rglob(name))
        self.assertEqual([], found)


if __name__ == "__main__":
    unittest.main()
