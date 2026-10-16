from __future__ import annotations

import json
import shutil
from pathlib import Path

from _drive.script import SkillScript
from _drive.work import Halt

from _ingest.cite import GraphRun

JUDGE_ENTRY = "citations"
LISTING_NAME = "listing.json"
ANSWERS_NAME = "answers.json"
VERDICTS_NAME = "verdicts.json"
MATCHES_PER_LISTING = 120
VERDICTS = ("confirm", "reject")
STATUS_REWRITTEN = "rewritten"
STATE_JUDGE = "judge"
STATE_SETTLED = "settled"


class JudgeListings:
    def __init__(self, root: Path) -> None:
        self._root = root

    def write(self, matches: list[dict]) -> None:
        shutil.rmtree(self._root, ignore_errors=True)
        for number, start in enumerate(range(0, len(matches), MATCHES_PER_LISTING), 1):
            listing = self._root / str(number) / LISTING_NAME
            listing.parent.mkdir(parents=True)
            numbered = [{"n": start + offset, **match}
                        for offset, match in enumerate(matches[start:start + MATCHES_PER_LISTING])]
            listing.write_text(json.dumps(numbered, ensure_ascii=False), encoding="utf-8")

    def line(self, linked: list[str]) -> dict:
        return {"state": STATE_JUDGE, "linked": linked, "root": str(self._root), "count": self._count(),
                "questions": []}

    def _count(self) -> int:
        return sum(1 for directory in self._root.iterdir() if (directory / LISTING_NAME).exists())


class JudgedMatches:
    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def verdicts_path(self) -> Path:
        return self._root / VERDICTS_NAME

    def verdicts(self) -> list[dict]:
        return [self._verdict(match, answer) for match, answer in self._pairs() if answer is not None]

    def unanswered(self) -> int:
        return sum(1 for _, answer in self._pairs() if answer is None)

    def _pairs(self) -> list[tuple[dict, dict | None]]:
        return [pair for directory in self._directories() for pair in self._pairs_in(directory)]

    def _pairs_in(self, directory: Path) -> list[tuple[dict, dict | None]]:
        answers = self._answers(directory)
        return [(match, answers.get(match["n"])) for match in self._listing(directory)]

    def _directories(self) -> list[Path]:
        return sorted(directory for directory in self._root.iterdir() if (directory / LISTING_NAME).exists())

    @staticmethod
    def _listing(directory: Path) -> list[dict]:
        return json.loads((directory / LISTING_NAME).read_text(encoding="utf-8"))

    @staticmethod
    def _answers(directory: Path) -> dict[int, dict]:
        try:
            answers = json.loads((directory / ANSWERS_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        listed = answers if isinstance(answers, list) else []
        return {answer["n"]: answer for answer in listed
                if isinstance(answer, dict) and answer.get("verdict") in VERDICTS and "n" in answer}

    @staticmethod
    def _verdict(match: dict, answer: dict) -> dict:
        return {"citing": match["citing"], "entry": match["entry"], "work": match["candidate"],
                "verdict": answer["verdict"]}


class VerdictsRecorder:
    def __init__(self, cite: SkillScript, run_session: int) -> None:
        self._cite = cite
        self._run_session = run_session

    def recorded(self, verdicts_file: Path) -> dict:
        run = self._cite.run("settle", "--verdicts", str(verdicts_file), "--apply", "--in-run", str(self._run_session))
        report = run.payload()
        if not run.ok or not isinstance(report, dict):
            raise Halt(f"`cite.py settle --apply` failed: {run.tail}")
        return report


class SettleStep:
    def __init__(self, judged: JudgedMatches, recorder: VerdictsRecorder, graph: GraphRun) -> None:
        self._judged = judged
        self._recorder = recorder
        self._graph = graph

    def run(self) -> dict:
        verdicts = self._judged.verdicts()
        verdicts_file = self._judged.verdicts_path
        verdicts_file.write_text(json.dumps(verdicts, ensure_ascii=False), encoding="utf-8")
        linked = self._linked(self._recorder.recorded(verdicts_file)) if verdicts else []
        if linked:
            self._graph.synced(linked)
        return {"state": STATE_SETTLED, "confirmed": self._count(verdicts, "confirm"),
                "rejected": self._count(verdicts, "reject"), "linked": linked, "questions": self._questions()}

    @staticmethod
    def _linked(report: dict) -> list[str]:
        return [row["basename"] for row in report.get("rows", []) if row.get("status") == STATUS_REWRITTEN]

    @staticmethod
    def _count(verdicts: list[dict], verdict: str) -> int:
        return sum(1 for item in verdicts if item["verdict"] == verdict)

    def _questions(self) -> list[str]:
        unanswered = self._judged.unanswered()
        if not unanswered:
            return []
        return [f"the citation judge gave no verdict on {unanswered} middle-band matches; they stay unlinked "
                "until a later batch judges them again"]
