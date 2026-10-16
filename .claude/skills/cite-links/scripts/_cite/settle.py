from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from _drive.runlock import RunHolder, RunLock
from references import CitationParser

from _cite.linking import ConfirmableLine, LinkResolution
from _cite.rebuild import LinksRebuild
from _cite.verdicts import CONFIRM, CitationVerdicts, Verdict

STATUS_PLANNED = "planned"
STATUS_RECORDED = "recorded"
STATUS_NOT_OFFERED = "not-offered"
VERDICT_FIELDS = ("citing", "entry", "work", "verdict")


class VerdictsFileUnreadable(LookupError):
    pass


class RunLockHeld(LookupError):
    pass


@dataclass(frozen=True)
class PlannedVerdict:
    verdict: Verdict
    score: float | None

    @property
    def is_offered(self) -> bool:
        return self.score is not None

    def as_dict(self, offered_status: str) -> dict:
        status = offered_status if self.is_offered else STATUS_NOT_OFFERED
        return {**self.verdict.as_dict(), "score": self.score, "status": status}


class Offers:
    def __init__(self, resolutions: dict[str, LinkResolution]) -> None:
        self._resolutions = resolutions

    def middle_band(self) -> list[tuple[str, ConfirmableLine]]:
        return [(citing, line) for citing, resolution in self._resolutions.items() for line in resolution.to_confirm]

    def score_of(self, verdict: Verdict) -> float | None:
        resolution = self._resolutions.get(verdict.citing)
        lines = resolution.to_confirm + resolution.settled if resolution else []
        return next((line.reported_score for line in lines if line.names(verdict.entry, verdict.work)), None)


class VerdictsFile:
    def __init__(self, path: Path) -> None:
        self._verdicts = [self._verdict(item) for item in self._items(path)]

    def citing(self) -> list[str]:
        return list(dict.fromkeys(verdict.citing for verdict in self._verdicts))

    def planned(self, offers: Offers) -> list[PlannedVerdict]:
        return [PlannedVerdict(verdict, offers.score_of(verdict)) for verdict in self._verdicts]

    @staticmethod
    def _items(path: Path) -> list:
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as failure:
            raise VerdictsFileUnreadable(f"{path} is not a readable JSON list of verdicts: {failure}") from failure
        if not isinstance(items, list) or not items:
            raise VerdictsFileUnreadable(f"{path} holds no JSON list of verdicts")
        return items

    @staticmethod
    def _verdict(item) -> Verdict:
        if not isinstance(item, dict) or any(not isinstance(item.get(name), str) for name in VERDICT_FIELDS):
            raise VerdictsFileUnreadable(f"a verdict carries the strings {', '.join(VERDICT_FIELDS)}: {item}")
        return Verdict(*(item[name] for name in VERDICT_FIELDS))


@dataclass(frozen=True)
class ScoreBand:
    low: float
    high: float
    verdict: str
    basenames: tuple[str, ...] = ()

    def citing(self) -> list[str]:
        return list(self.basenames)

    def planned(self, offers: Offers) -> list[PlannedVerdict]:
        return [self._planned(citing, line) for citing, line in offers.middle_band()
                if self.low <= line.reported_score < self.high]

    def _planned(self, citing: str, line: ConfirmableLine) -> PlannedVerdict:
        return PlannedVerdict(Verdict(citing, line.entry, line.basename, self.verdict), line.reported_score)


class RebuildFactory:
    def __init__(self, parser: CitationParser | None = None, verdicts: CitationVerdicts | None = None) -> None:
        self._parser = parser
        self._verdicts = verdicts or CitationVerdicts()

    def over(self, basenames: list[str]) -> LinksRebuild:
        return LinksRebuild(basenames, self._parser, self._verdicts)

    def record(self, verdicts: list[Verdict]) -> None:
        if verdicts:
            self._verdicts.record(verdicts)


class RunGate:
    def __init__(self, lock: RunLock | None = None, run_session: int | None = None) -> None:
        self._lock = lock or RunLock.ingest()
        self._run_session = run_session

    def require_no_other_run(self) -> None:
        holder = self._other_holder()
        if holder is not None:
            raise RunLockHeld(f"an ingest run holds the run lock ({holder.describe()}); nothing was recorded. "
                              "Run `settle --apply` again once that run returns")

    def _other_holder(self) -> RunHolder | None:
        if self._run_session is None:
            return self._lock.holder()
        return self._lock.held_by_another(self._run_session)


class Settlement:
    def __init__(self, request: VerdictsFile | ScoreBand, rebuilds: RebuildFactory | None = None,
                 gate: RunGate | None = None) -> None:
        self._request = request
        self._rebuilds = rebuilds or RebuildFactory()
        self._gate = gate or RunGate()

    def plan(self) -> dict:
        return self._report(self._planned(), STATUS_PLANNED)

    def apply(self) -> dict:
        self._gate.require_no_other_run()
        planned = self._planned()
        offered = [item.verdict for item in planned if item.is_offered]
        self._rebuilds.record(offered)
        return {**self._report(planned, STATUS_RECORDED), "rows": self._linked(offered)}

    def _planned(self) -> list[PlannedVerdict]:
        rebuild = self._rebuilds.over(self._request.citing())
        return self._request.planned(Offers(rebuild.resolutions()))

    def _linked(self, recorded: list[Verdict]) -> list[dict]:
        confirmed = list(dict.fromkeys(verdict.citing for verdict in recorded if verdict.verdict == CONFIRM))
        return self._rebuilds.over(confirmed).apply() if confirmed else []

    @staticmethod
    def _report(planned: list[PlannedVerdict], offered_status: str) -> dict:
        offered = sum(item.is_offered for item in planned)
        return {offered_status: offered, STATUS_NOT_OFFERED: len(planned) - offered,
                "verdicts": [item.as_dict(offered_status) for item in planned]}
