from __future__ import annotations

import json
from pathlib import Path

from _drive.script import ScriptRun, SkillScript
from _drive.steps import StepGuard
from _drive.work import Halt, SetAside

RESHAPE_NAME = "reshape"
NOMINATIONS_NAME = "nominations.json"
LISTING_NAME = "listing.json"
ANSWERS_NAME = "answers.json"
PARTS_NAME = "parts"
PART_FILES = {"listing": "{n}/listing.json", "answers": "{n}/answers.json"}
TOUCHED_NAME = "touched.json"
OUTCOME_NAME = "outcome.json"
STATE_SHAPE = "shape"
STATE_NOTHING = "nothing"
STATE_MERGED = "merged"
STATE_RESHAPED = "reshaped"
FINDING_KINDS = ("new", "split", "misfit")
LISTING_KINDS = ("authors", "nominations", "unlinked_subtopics", "routing_placements", "co_placed", "catalogue_gaps",
                 "stray_placements", "fold_candidates")


class ShapeListingFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def has_findings(self) -> bool:
        listing = json.loads(self._path.read_text(encoding="utf-8"))
        findings = listing.get("clusters", {}).get("findings", {})
        found = any(findings.get(kind) for kind in FINDING_KINDS)
        return found or any(listing.get(key) for key in LISTING_KINDS)


class TouchedFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, report: dict) -> None:
        touched = {"bibliographies": report.get("touched", []), "works": report.get("works", [])}
        self._path.write_text(json.dumps(touched, ensure_ascii=False), encoding="utf-8")

    def read(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"bibliographies": [], "works": []}


class ClustersStep:
    def __init__(self, script: SkillScript, works_dir: Path) -> None:
        self._script = script
        self._works_dir = works_dir

    def run(self) -> dict:
        directory = self._works_dir / RESHAPE_NAME
        directory.mkdir(parents=True, exist_ok=True)
        listing = directory / LISTING_NAME
        outcome = directory / OUTCOME_NAME
        outcome.unlink(missing_ok=True)
        (directory / ANSWERS_NAME).unlink(missing_ok=True)
        count = self._parts_cut(listing, directory / PARTS_NAME)
        if not ShapeListingFile(listing).has_findings():
            return {"state": STATE_NOTHING}
        return {"state": STATE_SHAPE, "dir": str(directory / PARTS_NAME), "parts": {"count": count, **PART_FILES},
                "outcome": str(outcome)}

    def _parts_cut(self, listing: Path, parts: Path) -> int:
        nominations = self._works_dir / NOMINATIONS_NAME
        run = self._script.run("shape-listing", "--nominations", str(nominations), "--out", str(listing),
                               "--parts", str(parts))
        report = run.payload()
        if not run.ok or not isinstance(report, dict) or "parts" not in report:
            raise Halt(f"`bibliographies.py shape-listing` failed: {run.tail}")
        return report["parts"]


class MergeStep:
    def __init__(self, script: SkillScript, works_dir: Path) -> None:
        self._script = script
        self._directory = works_dir / RESHAPE_NAME

    def run(self) -> dict:
        answers = self._directory / ANSWERS_NAME
        run = self._script.run("merge-answers", "--parts", str(self._directory / PARTS_NAME), "--out", str(answers))
        report = run.payload()
        if not run.ok or not isinstance(report, dict):
            raise SetAside(f"`bibliographies.py merge-answers` failed: {run.tail}")
        if not report.get("answered"):
            raise SetAside(f"the bibliography shaper wrote no answers file for any of the {report.get('parts')} "
                           "parts of the listing")
        return {"state": STATE_MERGED, "answers": str(answers), "parts": report["parts"],
                "answered": report["answered"]}


class ReshapeStep:
    def __init__(self, script: SkillScript, works_dir: Path) -> None:
        self._script = script
        self._works_dir = works_dir

    def run(self, answers: Path) -> dict:
        if not answers.exists():
            raise SetAside(f"the bibliography shaper wrote no answers file: {answers}")
        report = self._applied(answers)
        TouchedFile(self._works_dir / RESHAPE_NAME / TOUCHED_NAME).write(report)
        outcome = self._outcome_of(report)
        self._record(outcome)
        return outcome

    @staticmethod
    def _outcome_of(report: dict) -> dict:
        return {"state": STATE_RESHAPED, "created": report["created"], "moved": report["moved"],
                "linked": report.get("linked", []), "unlinked": report.get("unlinked", []),
                "added": report.get("added", []), "folded": report.get("folded", []),
                "questions": report.get("questions", [])}

    def _record(self, outcome: dict) -> None:
        path = self._works_dir / RESHAPE_NAME / OUTCOME_NAME
        path.write_text(json.dumps(outcome, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def _applied(self, answers: Path) -> dict:
        run = self._script.run("reshape", "--answers", str(answers), "--apply")
        payload = run.payload()
        if not run.ok or not isinstance(payload, dict) or "created" not in payload:
            raise SetAside(self._refusal(run, payload))
        return payload

    @staticmethod
    def _refusal(run: ScriptRun, payload) -> str:
        refused = payload.get("refused") if isinstance(payload, dict) else None
        return f"the shaper's answers were refused: {refused}" if refused else f"`reshape` failed: {run.tail}"


class ReshapeDriver:
    def __init__(self, script: SkillScript, works_dir: Path) -> None:
        self._script = script
        self._works_dir = works_dir

    def clusters(self) -> dict:
        return StepGuard("drive-clusters").outcome(ClustersStep(self._script, self._works_dir).run)

    def merge(self) -> dict:
        return StepGuard("drive-merge").outcome(MergeStep(self._script, self._works_dir).run)

    def reshape(self, answers: str) -> dict:
        return StepGuard("drive-reshape").outcome(lambda: ReshapeStep(self._script, self._works_dir).run(Path(answers)))
