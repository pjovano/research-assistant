from __future__ import annotations

import re
import subprocess

from _drive.script import ScriptRun, SkillScript
from _drive.work import Halt, WorkStops

from _ingest.citations import JudgeListings

AUTHOR_PROPOSALS = "Authors -- five or more works and no author bibliography"
UNRECORDED_MODEL = "unrecorded"
STATE_REBUILD = "rebuild"
ERROR_KEY = "error"
INDEXED_LINE = re.compile(r": \d+ children, \d+ embedded$", re.MULTILINE)
RECONNECT_QUESTION = "the sync changed the search stores: reconnect the `vault-rag` server"


def failed(command: str, run: ScriptRun) -> Halt:
    return Halt(f"`{command}` failed: {run.tail}")


class CheckStep:
    def __init__(self, script: SkillScript) -> None:
        self._script = script

    def run(self) -> dict:
        run = self._script.run("check", "--json")
        report = run.payload()
        if not isinstance(report, dict):
            raise failed("bibliographies.py check", run)
        blocking = [f"`check` blocks on {heading}: {problems}" for heading, problems in report["blocking"].items()]
        return {"state": "checked", "questions": blocking}


class CiteStep:
    def __init__(self, script: SkillScript, listings: JudgeListings, graph: SkillScript | None = None) -> None:
        self._script = script
        self._listings = listings
        self._graph = graph

    def run(self) -> dict:
        rows = self._status()
        changed = [row["basename"] for row in rows if row.get("status") == "changed"]
        if changed:
            self._apply()
        self._sync_graph()
        matches = self._middle_band(rows)
        if not matches:
            return {"state": "linked", "linked": changed, "questions": []}
        self._listings.write(matches)
        return self._listings.line(changed)

    def _sync_graph(self) -> None:
        if self._graph is None:
            return
        run = self._graph.run("sync")
        if not run.ok:
            raise Halt(f"`graph.py sync` failed: {run.tail}")

    def _status(self) -> list[dict]:
        run = self._script.run("status")
        status = run.payload()
        if not run.ok or not isinstance(status, dict):
            raise Halt(f"`cite.py status` failed; if it names the citation parser, the model is not on this "
                       f"machine: {run.tail}")
        if status.get("conflict_copies"):
            raise Halt(f"iCloud left conflict copies; merge and delete each before any link is written: "
                       f"{status['conflict_copies']}")
        return status.get("rows", [])

    def _apply(self) -> None:
        run = self._script.run("apply")
        if not run.ok:
            raise Halt(f"`cite.py apply` failed; `cite.py status` names the corpus files it did not write: "
                       f"{run.tail}")

    @staticmethod
    def _middle_band(rows: list[dict]) -> list[dict]:
        return [{"citing": row["basename"], "entry": item["entry"], "candidate": item["basename"],
                 "score": item["score"]}
                for row in rows for item in row.get("to_confirm", [])]


class IndexStep:
    def __init__(self, script: SkillScript) -> None:
        self._script = script

    def run(self) -> dict:
        try:
            report = self._synced()
        except subprocess.TimeoutExpired as expired:
            return StoppedSync(expired).outcome()
        self._require_consistent()
        return {"state": "indexed", "questions": self._unreadable(report) + self._reconnect(report)}

    def _synced(self) -> dict:
        run = self._script.run("sync")
        report = run.payload()
        if not isinstance(report, dict):
            raise failed("search.py sync", run)
        if ERROR_KEY in report:
            raise self._stop(report[ERROR_KEY], f"`search.py sync` failed: {report[ERROR_KEY]}")
        return report

    def _require_consistent(self) -> None:
        if self._status().get("consistent"):
            return
        self._synced()
        status = self._status()
        if status.get("consistent"):
            return
        reason = status.get("inconsistency")
        raise self._stop(reason, f"the search stores still disagree after a second sync: {reason}")

    def _status(self) -> dict:
        run = self._script.run("status")
        status = run.payload()
        if not isinstance(status, dict):
            raise failed("search.py status", run)
        return status

    def _stop(self, reason: str, halt_question: str) -> WorkStops:
        if self._models_disagree():
            return WorkStops(STATE_REBUILD, question=reason)
        return Halt(halt_question)

    def _models_disagree(self) -> bool:
        status = self._status()
        recorded = status.get("recorded_embedding_model")
        return recorded not in (None, UNRECORDED_MODEL) and recorded != status.get("embedding_model")

    @staticmethod
    def _unreadable(report: dict) -> list[str]:
        return [f"the frontmatter of {note['basename']} does not parse, so it was not indexed: {note['error']}"
                for note in report.get("unreadable", [])]

    @staticmethod
    def _reconnect(report: dict) -> list[str]:
        if report.get("changed") or report.get("pruned"):
            return [RECONNECT_QUESTION]
        return []


class StoppedSync:
    def __init__(self, expired: subprocess.TimeoutExpired) -> None:
        self._limit_seconds = expired.timeout
        self._progress = text_of(expired.stderr)

    def outcome(self) -> dict:
        indexed = len(INDEXED_LINE.findall(self._progress))
        if not indexed:
            raise Halt(f"`search.py sync` reached its {self._limit_seconds:g}-second limit before it indexed a work")
        stopped = (f"`search.py sync` stopped at its {self._limit_seconds:g}-second limit after indexing {indexed} "
                   "works; the next sync carries on where it stopped")
        return {"state": "indexed", "questions": [stopped, RECONNECT_QUESTION]}


def text_of(output: bytes | str | None) -> str:
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output or ""
