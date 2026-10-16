from __future__ import annotations

from _drive.work import WorkDirectory
from _extract.backfillrunner import ExtractScript
from _extract.backfillscope import SCOPE_NOTES_FIELD

UNCITABLE = "uncitable"
FINDINGS_FIELD = "findings"


class TrialAcceptance:
    def __init__(self, work: WorkDirectory, script: ExtractScript) -> None:
        self._work = work
        self._script = script

    def accepted(self) -> dict:
        state = self._work.state()
        notes = state.get(SCOPE_NOTES_FIELD, []) + state.get(FINDINGS_FIELD, [])
        self._script.checked("accept", self._work.pdf)
        return {"state": "accepted", "notes": notes + self._labelled()}

    def _labelled(self) -> list[str]:
        plan = self._script.run("labels", self._work.pdf)
        if not plan.ok and UNCITABLE in plan.tail:
            return ["uncitable: no labels"]
        applied = self._script.run("labels", self._work.pdf, "--apply")
        return [] if applied.ok else ["labels --apply failed: " + applied.tail]
