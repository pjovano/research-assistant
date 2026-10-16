from __future__ import annotations

import sys
from pathlib import Path

import vault

from _drive.script import ScriptRun, SkillScript
from _drive.steps import StepGuard
from _drive.work import (
    INBOX_PDF_FIELD,
    PDF_SUFFIX,
    ROUTED_FIELD,
    Halt,
    IngestWorks,
    SetAside,
    WorkDirectory,
    WorkStops,
    is_work_key,
)
from _vault.scratch import INGEST_ENTRY

from _file.filing import STATUS_CONNECTION_LOST, STATUS_FILED, STATUS_FILED_UNVERIFIED, STATUS_ZOTERO_OFFLINE
from _file.retry import (
    STATUS_RETRIED_OK,
    STATUS_RETRIED_UNVERIFIED,
    STATUS_RETRY_FAILED,
    STATUS_STILL_UNVERIFIED,
    STATUS_VERIFIED_ON_RETRY,
    STATUS_ZOTERO_STILL_OFFLINE,
)

FILE_SCRIPT = Path(__file__).resolve().parents[1] / "file.py"
BETTER_BIBTEX = "Better BibTeX"
CARD_REDOS = "card_redos"
MAX_CARD_REDOS = 1
FILED = frozenset({STATUS_FILED, STATUS_RETRIED_OK, STATUS_VERIFIED_ON_RETRY})
OFFLINE = frozenset({STATUS_ZOTERO_OFFLINE, STATUS_ZOTERO_STILL_OFFLINE})
NEEDS_RETRY = frozenset({STATUS_FILED_UNVERIFIED, STATUS_CONNECTION_LOST})
UNPLACED = frozenset({STATUS_STILL_UNVERIFIED, STATUS_RETRIED_UNVERIFIED})
ZOTERO_OFFLINE_QUESTION = "Zotero is not running: start Zotero, then run the batch again"


class FileScript(SkillScript):
    def __init__(self, interpreter: str = sys.executable) -> None:
        super().__init__(FILE_SCRIPT, interpreter)


class FailedRun:
    def __init__(self, command: str, run: ScriptRun) -> None:
        self._command = command
        self._run = run

    def stop(self) -> WorkStops:
        if BETTER_BIBTEX in self._run.tail:
            return Halt(f"`{self._command}` failed in Better BibTeX, so the duplicate check cannot run: "
                        f"{self._run.tail}")
        return SetAside(f"`{self._command}` failed: {self._run.tail}")


class DraftCardCheck:
    def __init__(self, work: WorkDirectory, script: SkillScript) -> None:
        self._work = work
        self._script = script

    def run(self) -> dict:
        self._work.save_state({**self._work.state(), ROUTED_FIELD: True, INBOX_PDF_FIELD: self._work.pdf})
        missing = self._checked("bib").payload().get("missing_for_type") or []
        filename = self._checked("name").stdout.strip().splitlines()[-1]
        if missing:
            return self._redo(missing)
        return {"state": "card-ok", "title": self._title_of(filename)}

    def _checked(self, command: str) -> ScriptRun:
        run = self._script.run(command, self._work.pdf)
        if not run.ok:
            raise FailedRun(command, run).stop()
        return run

    def _redo(self, missing: list[str]) -> dict:
        state = self._work.state()
        redos = state.get(CARD_REDOS, 0)
        if redos >= MAX_CARD_REDOS:
            raise SetAside(f"the draft card still lacks {', '.join(missing)} after a second dispatch: "
                           "the connector cannot add a field later")
        state[CARD_REDOS] = redos + 1
        self._work.save_state(state)
        return {"state": "redo-card", "missing": missing}

    @staticmethod
    def _title_of(filename: str) -> str:
        parsed = vault.parse_library_filename(filename)
        return parsed["title"] if parsed else Path(filename).stem


class FilingRow:
    def __init__(self, row: dict) -> None:
        self._row = row
        self.status = row.get("status")

    @property
    def basename(self) -> str:
        return vault.basename_of(Path(self._row["file"]))

    @property
    def is_stalled(self) -> bool:
        return self.status in UNPLACED and "placed_elsewhere" not in self._row

    def question(self, command: str) -> str:
        return f"`{command}` reported {self.status}: {self._row}"


class FilingRun:
    def __init__(self, pdf: str, script: SkillScript) -> None:
        self._pdf = pdf
        self._script = script

    def run(self) -> dict:
        filed = self._filed_row()
        if filed.status not in NEEDS_RETRY:
            return self._settled(filed, "file")
        retried = self._retried_row()
        if filed.status == STATUS_CONNECTION_LOST and retried.status == STATUS_RETRY_FAILED:
            raise Halt(f"the connection to Zotero dropped twice while the record of {self._pdf} was posted, so "
                       "whether Zotero created it is unknown: check Zotero, then run the batch again")
        return self._settled(retried, "retry")

    def _settled(self, row: FilingRow, command: str) -> dict:
        if row.status in FILED:
            return {"state": "filed", "basename": row.basename}
        if row.status in OFFLINE:
            raise Halt(ZOTERO_OFFLINE_QUESTION)
        if row.is_stalled:
            raise Halt(f"the stall signature: ZotMoov left {self._pdf} unplaced; run ZotMoov's Move to ZotMoov "
                       "directory on its record, or restart Zotero, then run the batch again")
        raise SetAside(row.question(command))

    def _filed_row(self) -> FilingRow:
        payload = self._payload("file", "file", self._pdf, "--only")
        rows = payload.get("filed") if isinstance(payload, dict) else None
        if not rows:
            raise SetAside(f"`file` filed nothing: {payload}")
        return FilingRow(rows[0])

    def _retried_row(self) -> FilingRow:
        payload = self._payload("retry", "retry", "--only", self._pdf)
        rows = payload if isinstance(payload, list) else [payload]
        if not rows:
            raise SetAside(f"`retry` found no draft card of {self._pdf}")
        return FilingRow(rows[0])

    def _payload(self, command: str, *args: str):
        run = self._script.run(*args)
        payload = run.payload()
        if payload is None:
            raise FailedRun(command, run).stop()
        return payload


class FileDriver:
    def __init__(self, script: SkillScript | None = None, works_dir: Path | None = None) -> None:
        self._script = script or FileScript()
        self._works = IngestWorks(works_dir or vault.SCRATCH_DIR / INGEST_ENTRY)

    def card(self, key: str) -> dict:
        return StepGuard("drive-card").on_work(lambda: self._works.work(key),
                                               lambda work: DraftCardCheck(work, self._script).run())

    def file(self, key: str) -> dict:
        return StepGuard("drive-file").on_work(lambda: self._works.work(key), lambda work: self._filed(key, work))

    def _filed(self, key: str, work: WorkDirectory) -> dict:
        outcome = FilingRun(work.pdf, self._script).run()
        if is_work_key(key):
            self._works.listed.list(int(key), outcome["basename"] + PDF_SUFFIX)
        return outcome
