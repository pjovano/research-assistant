from __future__ import annotations

import sys
from pathlib import Path

from _drive.script import SkillScript

SKILLS_DIR = Path(__file__).resolve().parents[3]


class SiblingScript(SkillScript):
    def __init__(self, skill: str, script: str, interpreter: str = sys.executable) -> None:
        super().__init__(SKILLS_DIR / skill / "scripts" / script, interpreter)


class SiblingScripts:
    @staticmethod
    def file() -> SkillScript:
        return SiblingScript("file-pdfs", "file.py")

    @staticmethod
    def bibliographies() -> SkillScript:
        return SiblingScript("classify-and-place", "bibliographies.py")

    @staticmethod
    def cite() -> SkillScript:
        return SiblingScript("cite-links", "cite.py")

    @staticmethod
    def graph() -> SkillScript:
        return SiblingScript("cite-links", "graph.py")

    @staticmethod
    def extract() -> SkillScript:
        return SiblingScript("extract-corpus", "extract.py")

    @staticmethod
    def search() -> SkillScript:
        return SiblingScript("search", "search.py")

    @staticmethod
    def health() -> SkillScript:
        return SiblingScript("machine-health", "health.py")
