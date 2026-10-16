from __future__ import annotations

import json

from _drive.work import WorkDirectory, WorkStops
from _extract.backfillaccept import TrialAcceptance
from _extract.backfillparts import CLEANUP_PARTS, PAGES_KEY, PartedDispatch
from _extract.backfillrunner import ExtractScript
from _extract.correctionrun import Correction, MalformedCorrections

CLEANUP_ROUND = 1
CLEANUP_NOTES_FIELD = "cleanup_notes"
BAD_CLEANUPS_FIELD = "bad_cleanups"
MERGED_CORRECTIONS_NAME = "corrections-merged.json"


class CleanupStart:
    def __init__(self, work: WorkDirectory, script: ExtractScript) -> None:
        self._work = work
        self._script = script

    def started(self) -> dict:
        listing = self._script.checked("correction-listing", self._work.pdf).stdout
        if not json.loads(listing)[PAGES_KEY]:
            return TrialAcceptance(self._work, self._script).accepted()
        dispatch = PartedDispatch(self._work, CLEANUP_PARTS)
        dispatch.write(listing)
        return {"state": "cleanup", "parts": dispatch.dispatch(CLEANUP_ROUND)}


class CleanupRouting:
    def __init__(self, work: WorkDirectory, script: ExtractScript) -> None:
        self._work = work
        self._script = script
        self._dispatch = PartedDispatch(work, CLEANUP_PARTS)

    def route(self) -> dict:
        corrections, notes = self._read_corrections()
        counts = self._applied(corrections) if corrections else {}
        refused = counts.get("refused", 0) + counts.get("unmatched", 0)
        notes += [f"cleanup: {counts.get('applied', 0)} corrections applied, {refused} refused or unmatched"]
        self._work.save_state({**self._work.state(), CLEANUP_NOTES_FIELD: notes})
        accepted = TrialAcceptance(self._work, self._script).accepted()
        return {**accepted, "notes": accepted["notes"] + notes}

    def _read_corrections(self) -> tuple[list[dict], list[str]]:
        merged = self._dispatch.merged(CLEANUP_ROUND)
        omitted = merged.omitted(self._dispatch.listed())
        notes = self._skipped(omitted) if omitted else []
        valid = [correction for correction in merged.findings if _is_wellformed(correction)]
        malformed = len(merged.findings) - len(valid)
        return valid, notes + ([f"cleanup: {malformed} malformed corrections dropped"] if malformed else [])

    def _skipped(self, omitted: list[int]) -> list[str]:
        state = self._work.state()
        failed_before = state.get(BAD_CLEANUPS_FIELD, 0) >= 1
        self._work.save_state({**state, BAD_CLEANUPS_FIELD: state.get(BAD_CLEANUPS_FIELD, 0) + 1})
        if not failed_before:
            raise WorkStops("recleanup", parts=self._dispatch.repair(CLEANUP_ROUND, omitted))
        return [f"cleanup: no corrections read for file pages {', '.join(map(str, omitted))}"]

    def _applied(self, corrections: list[dict]) -> dict:
        self._work.save(MERGED_CORRECTIONS_NAME, corrections)
        path = str(self._work.path(MERGED_CORRECTIONS_NAME))
        return json.loads(self._script.checked("correct", self._work.pdf, "--corrections", path, "--apply").stdout)[
            "counts"]


def _is_wellformed(correction: object) -> bool:
    try:
        Correction.parsed(correction, 0)
    except MalformedCorrections:
        return False
    return True
