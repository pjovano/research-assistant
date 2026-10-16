from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

GIT_TIMEOUT_SECONDS = 10
REPOSITORY_LOCATING_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")


def without_repository_locating_variables(environment: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in environment.items() if key not in REPOSITORY_LOCATING_VARIABLES}


class GitDirectory:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def top_level(self) -> Path | None:
        return self._answer("--show-toplevel")

    def common_dir(self) -> Path | None:
        return self._answer("--path-format=absolute", "--git-common-dir")

    def _answer(self, *arguments: str) -> Path | None:
        try:
            completed = subprocess.run(["git", "-C", str(self._directory), "rev-parse", *arguments],
                                       capture_output=True, text=True,
                                       env=without_repository_locating_variables(os.environ),
                                       timeout=GIT_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return Path(completed.stdout.strip()).resolve() if completed.returncode == 0 else None


class CheckedTree:
    def __init__(self, edited: Path, project_root: Path) -> None:
        self._edited = edited
        self._project_root = project_root

    def root(self) -> Path | None:
        worktree = self._worktree_of_the_project()
        if worktree is not None:
            return worktree
        return self._project_root if self._edited.is_relative_to(self._project_root) else None

    def _worktree_of_the_project(self) -> Path | None:
        holder = GitDirectory(self._nearest_directory())
        top_level = holder.top_level()
        if top_level is None or not self._shares_the_project_repository(holder):
            return None
        return top_level

    def _shares_the_project_repository(self, holder: GitDirectory) -> bool:
        common_dir = holder.common_dir()
        return common_dir is not None and common_dir == GitDirectory(self._project_root).common_dir()

    def _nearest_directory(self) -> Path:
        return next(directory for directory in self._edited.parents if directory.is_dir())
