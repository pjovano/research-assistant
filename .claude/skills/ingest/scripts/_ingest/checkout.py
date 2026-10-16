from __future__ import annotations

import subprocess
from pathlib import Path

MAIN_BRANCH = "main"
WORKTREES_PARTS = (".claude", "worktrees")
CHANGES_NAMED = 5


class Checkout:
    def __init__(self, root: Path) -> None:
        self._root = root

    def branch(self) -> str:
        return self._git("branch", "--show-current").strip()

    def changes(self) -> list[str]:
        return [line for line in self._git("status", "--porcelain").splitlines() if line.strip()]

    def _git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self._root), *args], capture_output=True, text=True,
                              check=True).stdout


class CheckoutReadiness:
    def __init__(self, checkout: Checkout) -> None:
        self._checkout = checkout

    def failures(self) -> list[str]:
        try:
            return self._off_main() + self._uncommitted()
        except (OSError, subprocess.CalledProcessError) as failure:
            return [f"git cannot read the control plane's checkout: {failure}"]

    def _off_main(self) -> list[str]:
        branch = self._checkout.branch()
        if branch == MAIN_BRANCH:
            return []
        return [f"the control plane is on {branch or 'a detached HEAD'}, not {MAIN_BRANCH}: switch it to "
                f"{MAIN_BRANCH}"]

    def _uncommitted(self) -> list[str]:
        changes = self._checkout.changes()
        if not changes:
            return []
        return [f"the control plane carries {len(changes)} uncommitted changes ({'; '.join(changes[:CHANGES_NAMED])}):"
                f" commit them through a pull request, or discard them"]


class WorkingDirectoryReadiness:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def failures(self) -> list[str]:
        if not self._is_in_a_worktree():
            return []
        return [f"the working directory {self._directory} lies under .claude/worktrees/: run the batch from a "
                f"session whose working directory is the control plane"]

    def _is_in_a_worktree(self) -> bool:
        parts = self._directory.parts
        width = len(WORKTREES_PARTS)
        return any(parts[index:index + width] == WORKTREES_PARTS for index in range(len(parts) - width + 1))
