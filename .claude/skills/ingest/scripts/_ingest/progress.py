from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import vault

from _drive.script import SkillScript
from _drive.work import INBOX_PDF_FIELD, ROUTED_FIELD, WORKS_NAME
from _vault.scratch import BACKFILL_ENTRY, INGEST_ENTRY
from _ingest.batch import (
    STAGE_CITE,
    STAGE_CLASSIFY,
    STAGE_CLEAN,
    STAGE_EXTRACT,
    STAGE_FILE,
    BatchWorkDirectory,
    FiledWork,
)

UPDATE_MINUTES_KEY = "batch_update_minutes"
DEFAULT_UPDATE_MINUTES = 30
MINUTES_PER_HOUR = 60
SECONDS_PER_MINUTE = 60
STAGE_PLACED = "placed"
STAGE_VOLUME = "moved among the volumes"
STAGE_UNTRACED = "left the inbox, not traced"
STAGE_ORDER = (STAGE_CLEAN, STAGE_FILE, STAGE_EXTRACT, STAGE_CITE, STAGE_CLASSIFY, STAGE_VOLUME, STAGE_UNTRACED,
               STAGE_PLACED)
PROCESSES_SHOWN = 5


class UpdateInterval:
    def __init__(self, machine: dict) -> None:
        self._machine = machine

    @property
    def minutes(self) -> int:
        return int(self._machine.get(UPDATE_MINUTES_KEY) or DEFAULT_UPDATE_MINUTES)


class BatchPlaces:
    def __init__(self, inbox: Path, volumes: Path, scratch: Path) -> None:
        self.inbox = inbox
        self.volumes = volumes
        self.works_dir = scratch / INGEST_ENTRY
        self.backfill_works = scratch / BACKFILL_ENTRY / WORKS_NAME


class WorkStage:
    def __init__(self, places: BatchPlaces) -> None:
        self._places = places

    def of(self, work: dict) -> str:
        if "pdf" in work:
            return self._of_inbox_pdf(work["pdf"])
        return self._of_basename(work["basename"])

    def _of_inbox_pdf(self, pdf: str) -> str:
        if (self._places.inbox / pdf).exists():
            routed = BatchWorkDirectory(self._places.works_dir / vault.basename_of(Path(pdf))).state()
            return STAGE_FILE if routed.get(ROUTED_FIELD) else STAGE_CLEAN
        if (self._places.volumes / pdf).exists():
            return STAGE_VOLUME
        basename = self._filed_basename(pdf)
        return self._of_basename(basename) if basename else STAGE_UNTRACED

    def _filed_basename(self, pdf: str) -> str | None:
        directories = sorted(self._places.works_dir.iterdir()) if self._places.works_dir.is_dir() else []
        return next((vault.nfc(directory.name) for directory in directories
                     if directory.is_dir() and self._was_inbox_pdf(directory, pdf)), None)

    @staticmethod
    def _was_inbox_pdf(directory: Path, pdf: str) -> bool:
        state = BatchWorkDirectory(directory).state()
        return state.get(INBOX_PDF_FIELD) == pdf and vault.held_note_exists(directory.name)

    def _of_basename(self, basename: str) -> str:
        return FiledWork(basename).stage() or STAGE_PLACED


class MachineHealth:
    def __init__(self, script: SkillScript, interval: UpdateInterval) -> None:
        self._script = script
        self.interval_minutes = interval.minutes

    def over_the_interval(self) -> dict:
        hours = self.interval_minutes / MINUTES_PER_HOUR
        run = self._script.run("report", "--hours", f"{hours:g}")
        report = run.payload()
        if not isinstance(report, dict):
            return {"error": f"`health.py report` failed: {run.tail}"}
        return {**report, "processes": report.get("processes", [])[:PROCESSES_SHOWN]}


class BatchProgress:
    def __init__(self, record: dict | None, stage: WorkStage, health: MachineHealth) -> None:
        self._record = record
        self._stage = stage
        self._health = health

    def report(self, now: float) -> dict:
        minutes = self._health.interval_minutes
        if self._record is None:
            return {"state": "no-batch", "interval_minutes": minutes}
        return {"state": "progress", "interval_minutes": minutes, **self._clock(now), **self._stages(),
                "health": self._health.over_the_interval()}

    def _clock(self, now: float) -> dict:
        started = self._record["started_at"]
        stamp = datetime.fromtimestamp(started, timezone.utc).astimezone().isoformat(timespec="minutes")
        return {"started": stamp, "elapsed_minutes": round((now - started) / SECONDS_PER_MINUTE)}

    def _stages(self) -> dict:
        works = self._record["works"]
        stages: dict[str, list[str]] = {stage: [] for stage in STAGE_ORDER}
        for work in works:
            stages[self._stage.of(work)].append(work.get("pdf") or work["basename"])
        listed = {stage: names for stage, names in stages.items() if names}
        return {"works": len(works), "done": len(stages[STAGE_PLACED]), "stages": listed}
