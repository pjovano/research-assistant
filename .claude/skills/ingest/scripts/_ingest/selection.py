from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from _drive.script import SkillScript

from _drive.work import Halt
from _ingest.batch import STAGE_CLEAN, STAGE_EXTRACT, STAGE_FILE, BatchListing
from _ingest.runlock import RunHolder, RunLock

RECORD_NAME = "batch.json"
HOLDER_FIELD = "holder"
KEY_FIELD = "key"
PDF_SUFFIX = ".pdf"
FIRST_KEY = 1
ENGINE_STAGES = (STAGE_CLEAN, STAGE_FILE, STAGE_EXTRACT)
COSTS_FIELD = "costs"
COSTED = 0
UNCOSTED = 1


@dataclass(frozen=True)
class BatchRequest:
    origin: str
    keys: list[int] = field(default_factory=list)
    first: int | None = None
    last: int | None = None


class BatchSelection:
    def __init__(self, listing: BatchListing, queue: Path, costs: EngineWorkCosts | None = None) -> None:
        self._listing = listing
        self._queue = queue
        self._costs = costs

    def works(self, request: BatchRequest) -> list[dict]:
        listed = self._backfill_listing() if request.origin == STAGE_EXTRACT else self._batch_listing()
        keyed = [{KEY_FIELD: key, **work} for key, work in enumerate(listed, start=FIRST_KEY)]
        if request.keys:
            return chosen(keyed, request.keys)
        return in_range(keyed, request)

    def _batch_listing(self) -> list[dict]:
        works = self._listing.works()
        return works if self._costs is None else self._costs.ranked(works)

    def _backfill_listing(self) -> list[dict]:
        lines = [line.strip() for line in self._queue.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [{"basename": line.removesuffix(PDF_SUFFIX), "from": STAGE_EXTRACT} for line in lines]


def chosen(keyed: list[dict], keys: list[int]) -> list[dict]:
    by_key = {work[KEY_FIELD]: work for work in keyed}
    unlisted = [key for key in keys if key not in by_key]
    if unlisted:
        raise Halt(f"no work is listed under the keys {unlisted}: run ingest.py list, and name keys it prints")
    return [by_key[key] for key in keys]


def in_range(items: list, request: BatchRequest) -> list:
    return items[(request.first or FIRST_KEY) - 1:request.last]


def work_pdf(work: dict) -> str:
    return work.get("pdf") or work["basename"] + PDF_SUFFIX


def keys_by_stage(works: list[dict]) -> dict[str, list[int]]:
    stages: dict[str, list[int]] = {}
    for work in works:
        stages.setdefault(work["from"], []).append(work[KEY_FIELD])
    return stages


class EngineWorkCosts:
    def __init__(self, extract: SkillScript) -> None:
        self._extract = extract
        self._costed: dict[str, list[int] | None] = {}

    def ranked(self, works: list[dict]) -> list[dict]:
        self._cost(works)
        bound = [work for work in works if is_bound_for_the_engine(work)]
        return sorted(bound, key=self._rank) + [work for work in works if not is_bound_for_the_engine(work)]

    def by_key(self, keyed: list[dict]) -> dict[str, list[int]]:
        self._cost(keyed)
        costed = {str(work[KEY_FIELD]): self._costed.get(work_pdf(work)) for work in keyed
                  if is_bound_for_the_engine(work)}
        return {key: cost for key, cost in costed.items() if cost is not None}

    def _rank(self, work: dict) -> tuple:
        cost = self._costed.get(work_pdf(work))
        return (COSTED, *cost) if cost is not None else (UNCOSTED,)

    def _cost(self, works: list[dict]) -> None:
        missing = sorted({work_pdf(work) for work in works if is_bound_for_the_engine(work)} - set(self._costed))
        if not missing:
            return
        run = self._extract.run("costs", *missing)
        report = run.payload()
        if not isinstance(report, dict) or not isinstance(report.get(COSTS_FIELD), dict):
            raise Halt(f"`extract.py costs` failed: {run.tail}")
        self._costed.update(report[COSTS_FIELD])


def is_bound_for_the_engine(work: dict) -> bool:
    return work["from"] in ENGINE_STAGES


class BatchRecord:
    def __init__(self, directory: Path) -> None:
        self._path = directory / RECORD_NAME

    def write(self, holder: RunHolder, works: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        record = {"from": holder.origin, "started_at": holder.started_at, HOLDER_FIELD: holder.pid, "works": works}
        self._path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

    def read_if_held(self, lock: RunLock) -> dict | None:
        record = self._read()
        return record if record is not None and lock.is_held_by(record.get(HOLDER_FIELD)) else None

    def _read(self) -> dict | None:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
