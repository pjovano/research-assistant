from __future__ import annotations

from pathlib import Path

import vault

from _drive.script import SkillScript
from _drive.steps import StepGuard
from _drive.work import ROUTED_FIELD, IngestWorks, SetAside, Unwritten, WorkDirectory
from _vault.scratch import INGEST_ENTRY

from .drivefonts import (
    IDENTIFY_NAME,
    STATE_BOOKMARK,
    CleanScript,
    CodesLeftAsIs,
    FontScanStep,
    FontsCommand,
    ReaderAnswersFiles,
    UnsettledCodes,
    UnsettledReading,
)

VOLUMES_SCRIPT = Path(__file__).resolve().parents[3] / "extract-chapters" / "scripts" / "volumes.py"
KIND_VOLUME = "volume"
KINDS = ("article", "book", KIND_VOLUME)


class LearnStep:
    def __init__(self, work: WorkDirectory, script: SkillScript) -> None:
        self._work = work
        self._fonts = FontsCommand(script, work.pdf)
        self._unsettled = UnsettledReading(work, script)

    def run(self) -> dict:
        try:
            return self._learned_and_repaired()
        except UnsettledCodes as unsettled:
            return self._unsettled.outcome(unsettled)

    def _learned_and_repaired(self) -> dict:
        answers_files = ReaderAnswersFiles(self._work)
        answers = answers_files.merged()
        self._require_every_answers_file(answers_files, answers)
        plan = self._learned(answers) if answers else {}
        self._fonts.repair_in_place(CodesLeftAsIs(plan.get("needs_no_repair", [])))
        return {"state": STATE_BOOKMARK,
                "notes": [f"identity conflict, the table's entry kept: {row}" for row in plan.get("conflicts", [])]}

    def _require_every_answers_file(self, answers_files: ReaderAnswersFiles, answers: Path | None) -> None:
        listed_without_answers = answers is None and self._work.has(IDENTIFY_NAME)
        if listed_without_answers or answers_files.unanswered_listings():
            raise Unwritten("the glyph reader wrote no answers file for a listing")

    def _learned(self, answers: Path) -> dict:
        arguments = ("learn-reader", "--answers", str(answers), "--identify", str(self._work.path(IDENTIFY_NAME)))
        plan = self._fonts.report(*arguments)
        self._refuse(plan, answers)
        self._fonts.report(*arguments, "--apply")
        return plan

    @staticmethod
    def _refuse(plan: dict, answers: Path) -> None:
        if plan.get("set_aside"):
            reasons = sorted({row.get("reason", "") for row in plan["set_aside"]})
            raise UnsettledCodes(f"as no identity is learned for {len(plan['set_aside'])} answers: "
                                 f"{'; '.join(reasons)}")
        if plan.get("unresolved"):
            raise UnsettledCodes(f"as the glyph reader left {len(plan['unresolved'])} glyphs unresolved, with its "
                                 f"evidence in {answers}")


class RouteStep:
    def __init__(self, work: WorkDirectory, script: SkillScript, volumes: SkillScript) -> None:
        self._work = work
        self._script = script
        self._volumes = volumes

    def run(self, kind: str) -> dict:
        if kind != KIND_VOLUME:
            self._work.save_state({**self._work.state(), ROUTED_FIELD: kind})
            return {"state": "file"}
        self._script.checked("volume", self._work.pdf)
        self._script.checked("volume", self._work.pdf, "--apply")
        contents = self._volumes.checked("contents", self._work.pdf).payload()
        raise SetAside(f"an edited volume, moved among the volumes: choose the chapters to cut from "
                       f"{contents.get('chapters')}")


class CleanDriver:
    def __init__(self, script: SkillScript | None = None, volumes: SkillScript | None = None,
                 works_dir: Path | None = None) -> None:
        self._script = script or CleanScript()
        self._volumes = volumes or SkillScript(VOLUMES_SCRIPT)
        self._works = IngestWorks(works_dir or vault.SCRATCH_DIR / INGEST_ENTRY)

    def fonts(self, pdf: str) -> dict:
        return self._on(pdf, "drive-fonts", lambda work: FontScanStep(work, self._script).run())

    def learn(self, pdf: str) -> dict:
        return self._on(pdf, "drive-learn", lambda work: LearnStep(work, self._script).run())

    def route(self, pdf: str, kind: str) -> dict:
        return self._on(pdf, "drive-route", lambda work: RouteStep(work, self._script, self._volumes).run(kind))

    def _on(self, pdf: str, command: str, step) -> dict:
        return StepGuard(command).on_work(lambda: self._works.work(pdf), step)
