from __future__ import annotations

from pathlib import Path

import vault

from _drive.script import ScriptRun, SkillScript
from _drive.steps import StepGuard
from _drive.work import Halt, IngestWorks, WorkDirectory

STATUS_REWRITTEN = "rewritten"
CITED_OPTION = "--cited"


class LinkRun:
    def __init__(self, cite: SkillScript) -> None:
        self._cite = cite

    def applied(self, *arguments: str) -> list[str]:
        run = self._cite.run("apply", *arguments)
        rows = run.payload()
        if not run.ok or not isinstance(rows, list):
            raise self._failure(run)
        return [row["basename"] for row in rows if row.get("status") == STATUS_REWRITTEN]

    @staticmethod
    def _failure(run: ScriptRun) -> Halt:
        return Halt(f"`cite.py apply` failed; if it names the citation parser, the model is not on this machine: "
                    f"{run.tail}")


class GraphRun:
    def __init__(self, graph: SkillScript) -> None:
        self._graph = graph

    def synced(self, basenames: list[str]) -> dict:
        run = self._graph.run("sync", *basenames)
        report = run.payload()
        if not run.ok or not isinstance(report, dict):
            raise Halt(f"`graph.py sync` failed: {run.tail}")
        return report


class WorkCiteStep:
    def __init__(self, basename: str, cite: SkillScript, graph: SkillScript) -> None:
        self._basename = basename
        self._links = LinkRun(cite)
        self._graph = GraphRun(graph)

    def run(self) -> dict:
        outbound = self._links.applied(self._basename)
        inbound = self._links.applied(CITED_OPTION, self._basename)
        rewritten = sorted(set(outbound + inbound))
        self._graph.synced(sorted({self._basename, *rewritten}))
        return {"state": "linked", "linked": rewritten}


class CiteDriver:
    def __init__(self, cite: SkillScript, graph: SkillScript, works_dir: Path) -> None:
        self._cite = cite
        self._graph = graph
        self._works = IngestWorks(works_dir)

    def link(self, key: str) -> dict:
        return StepGuard("drive-cite").on_work(lambda: self._works.work(key), self._linked)

    def _linked(self, work: WorkDirectory) -> dict:
        return WorkCiteStep(vault.basename_of(Path(work.pdf)), self._cite, self._graph).run()
