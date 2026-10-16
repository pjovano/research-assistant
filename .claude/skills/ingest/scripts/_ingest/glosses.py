from __future__ import annotations

import json
import shutil
from pathlib import Path

import vault

from _drive.script import ScriptRun, SkillScript
from _drive.steps import StepGuard
from _drive.work import Halt, IngestWorks, SetAside

from _ingest.reshape import RESHAPE_NAME, TOUCHED_NAME, TouchedFile

GLOSSES_NAME = "glosses"
PLAN_NAME = "plan.json"
LISTING_NAME = "listing.json"
ANSWERS_NAME = "answers.json"
STATE_GLOSS = "gloss"
STATE_NOTHING = "nothing"
STATE_GLOSSED = "glossed"


class GlossRun:
    def __init__(self, script: SkillScript) -> None:
        self._script = script

    def copy(self) -> None:
        self._require_ok(self._script.run("gloss-copy", "--apply"), "gloss-copy")

    def plan(self, basenames: list[str], bibliographies: list[str], everything: bool) -> list[str]:
        arguments = ["--all"] if everything else ["--works", *basenames, "--bibliographies", *bibliographies]
        run = self._script.run("gloss-plan", *arguments)
        payload = run.payload()
        if not run.ok or not isinstance(payload, dict):
            raise Halt(f"`bibliographies.py gloss-plan` failed: {run.tail}")
        return payload["bibliographies"]

    def listing(self, name: str, out: Path) -> None:
        self._require_ok(self._script.run("gloss-listing", name, "--out", str(out)), "gloss-listing")

    def write(self, name: str, answers: Path) -> list[str]:
        run = self._script.run("gloss-write", name, "--answers", str(answers))
        payload = run.payload()
        if not isinstance(payload, dict) or "problems" not in payload:
            raise Halt(f"`bibliographies.py gloss-write` failed: {run.tail}")
        return payload["problems"]

    @staticmethod
    def _require_ok(run: ScriptRun, command: str) -> None:
        if not run.ok:
            raise Halt(f"`bibliographies.py {command}` failed: {run.tail}")


class GlossDirectory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.listing = path / LISTING_NAME
        self.answers = path / ANSWERS_NAME

    def named(self, name: str) -> None:
        self.path.mkdir(parents=True)
        (self.path / PLAN_NAME).write_text(json.dumps({"name": name}, ensure_ascii=False), encoding="utf-8")

    def name(self) -> str:
        return json.loads((self.path / PLAN_NAME).read_text(encoding="utf-8"))["name"]


class GlossPlanStep:
    def __init__(self, run: GlossRun, works: IngestWorks, root: Path) -> None:
        self._run = run
        self._works = works
        self._root = root / GLOSSES_NAME

    def run(self, keys: list[str], everything: bool) -> dict:
        self._run.copy()
        touched = TouchedFile(self._root.parent / RESHAPE_NAME / TOUCHED_NAME).read()
        basenames = [vault.basename_of(Path(self._works.work(key).pdf)) for key in keys] + touched["works"]
        planned = self._run.plan(basenames, touched["bibliographies"], everything)
        if self._root.exists():
            shutil.rmtree(self._root)
        for number, name in enumerate(planned, start=1):
            self._prepare(GlossDirectory(self._root / str(number)), name)
        if not planned:
            return {"state": STATE_NOTHING}
        return {"state": STATE_GLOSS, "root": str(self._root), "count": len(planned)}

    def _prepare(self, directory: GlossDirectory, name: str) -> None:
        directory.named(name)
        self._run.listing(name, directory.listing)


class GlossFinishStep:
    def __init__(self, run: GlossRun, directory: GlossDirectory) -> None:
        self._run = run
        self._directory = directory

    def run(self) -> dict:
        name = self._directory.name()
        if not self._directory.answers.exists():
            raise SetAside(f"{name}: the bibliography introducer wrote no answers file: {self._directory.answers}")
        problems = self._run.write(name, self._directory.answers)
        if problems:
            raise SetAside(f"{name}: the bibliography introducer's answers were refused: {' | '.join(problems)}")
        return {"state": STATE_GLOSSED, "bibliography": name}


class GlossDriver:
    def __init__(self, script: SkillScript, works_dir: Path) -> None:
        self._run = GlossRun(script)
        self._works_dir = works_dir

    def plan(self, keys: list[str], everything: bool) -> dict:
        step = GlossPlanStep(self._run, IngestWorks(self._works_dir), self._works_dir)
        return StepGuard("drive-gloss-plan").outcome(lambda: step.run(keys, everything))

    def finish(self, directory: str) -> dict:
        return StepGuard("drive-gloss-finish").outcome(GlossFinishStep(self._run, GlossDirectory(Path(directory))).run)
