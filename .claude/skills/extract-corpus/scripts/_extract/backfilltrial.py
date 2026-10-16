from __future__ import annotations

import json
import re
from pathlib import Path

from _drive.numbered import FIRST_NUMBER, NUMBER_SLOT, NumberedFiles
from _drive.script import ScriptRun
from _drive.work import SetAside, Unwritten, WorkDirectory
from _extract.backfillaccept import FINDINGS_FIELD, TrialAcceptance
from _extract.backfillcleanup import CleanupStart
from _extract.backfillprep import CLEANUP_FIELD
from _extract.backfillrunner import ExtractFailure, ExtractScript
from _extract.backfillscope import ScopeSettlement, excluded_spans
from _extract.backfillverify import TrialVerification
from _extract.backfillwork import READINGS_PATTERN
from _extract.console import EXIT_DOUBTFUL
from _extract.pixelchapters import PixelChapters

EXTRACT_ATTEMPTS = 2
DOUBTFUL_BATCH_SIZE = 20
CLASSIFIER_UNAVAILABLE = "classifier unavailable"
CHANGED_ON_DISK = "changed on disk"
RECORDS_FILE = "extraction-records"
SCOPE_REFUSAL = re.compile(r"point|scope|resumes before")
DOUBT_READ_FROM_PIXELS_FIELD = "doubt_read_from_pixels"
DOUBTFUL_LISTING_PATTERN = "doubtful-*.json"
DOUBTFUL_LISTING_PREFIX = "doubtful-"
READINGS_PREFIX = "readings-"
DOUBTFUL_LISTING_NAME = f"{DOUBTFUL_LISTING_PREFIX}{NUMBER_SLOT}.json"
READINGS_NAME = f"{READINGS_PREFIX}{NUMBER_SLOT}.json"


class TransientFailure(Exception):
    def __init__(self, question: str) -> None:
        super().__init__(question)
        self.question = question


class TrialRun:
    def __init__(self, work: WorkDirectory, script: ExtractScript) -> None:
        self._work = work
        self._script = script
        self._state = work.state()

    def trial(self) -> dict:
        ScopeSettlement(self._work, self._state, self._script).settle()
        return self._trial_on_the_settled_scope()

    def _trial_on_the_settled_scope(self) -> dict:
        result = self._extract([])
        if "doubtful" in result:
            return self._doubtful(result["doubtful"])
        return self._accepted(result)

    def retrial(self) -> dict:
        self._work.save("readings.json", self._readings())
        result = self._extract(["--readings", str(self._work.path("readings.json"))])
        if "doubtful" in result:
            return self._trial_reading_doubtful_chapters_from_pixels(result["doubtful"])
        return self._accepted(result)

    def _trial_reading_doubtful_chapters_from_pixels(self, pages: list) -> dict:
        file_pages = [page["file_page"] for page in pages if isinstance(page.get("file_page"), int)]
        probe = self._work.load("probe.json")
        chapters = PixelChapters(probe["headings"], probe["page_count"])
        if self._state.get(DOUBT_READ_FROM_PIXELS_FIELD) or not chapters.widens(self._state["flags"], file_pages):
            listed = ", ".join(str(page.get("file_page")) for page in pages)
            raise SetAside("doubtful pages remain after the readings, with their chapters read from pixels: " + listed)
        self._state["flags"] = chapters.flags_covering(self._state["flags"], file_pages)
        self._state[DOUBT_READ_FROM_PIXELS_FIELD] = True
        self._work.save_state(self._state)
        return self._trial_on_the_settled_scope()

    def _readings(self) -> list:
        unread = [listing.name for listing in self._work.matching(DOUBTFUL_LISTING_PATTERN)
                  if not self._work.has(listing.name.replace(DOUBTFUL_LISTING_PREFIX, READINGS_PREFIX, 1))]
        if unread:
            raise Unwritten(f"the page reader wrote no readings file for {', '.join(unread)}")
        readings = [reading for path in self._work.matching(READINGS_PATTERN) for reading in self._read(path)]
        if not readings:
            raise Unwritten("the page reader wrote no readings")
        return readings

    @staticmethod
    def _read(path: Path) -> list:
        try:
            return json.loads(path.read_text())
        except ValueError:
            raise SetAside(f"the page reader wrote a malformed readings file: {path}") from None

    def _extract(self, extra: list[str]) -> dict:
        args = ["extract", self._work.pdf, "--trial", *self._state["scope"], *self._state["flags"], *extra]
        failure = None
        for _ in range(EXTRACT_ATTEMPTS):
            try:
                return self._attempt(args)
            except TransientFailure as error:
                failure = error
        raise SetAside(failure.question)

    def _attempt(self, args: list[str]) -> dict:
        run = self._script.run(*args)
        if run.ok:
            return run.payload()
        if run.returncode == EXIT_DOUBTFUL:
            return {"doubtful": self._doubtful_pages(run)}
        self._refuse(run)

    def _doubtful_pages(self, run: ScriptRun) -> list:
        payload = run.payload()
        pages = payload if isinstance(payload, list) else (payload or {}).get("doubtful", [])
        if any(CLASSIFIER_UNAVAILABLE in str(page.get("reason")) for page in pages):
            raise TransientFailure("the quality classifier stays unavailable; see ocr_error_server.log")
        return pages

    def _refuse(self, run: ScriptRun) -> None:
        failure = ExtractFailure("extract", run)
        if failure.is_machine_wide():
            raise failure.stop()
        if CHANGED_ON_DISK in run.tail:
            raise TransientFailure("extract failed: " + run.tail)
        if SCOPE_REFUSAL.search(run.tail) and RECORDS_FILE not in run.tail:
            ScopeSettlement(self._work, self._state, self._script).rescope("extract refused the scope: " + run.tail)
        raise failure.stop()

    def _doubtful(self, pages: list) -> dict:
        self._work.discard(READINGS_PATTERN)
        self._work.discard(DOUBTFUL_LISTING_PATTERN)
        self._work.save("doubtful.json", pages)
        batches = [pages[start:start + DOUBTFUL_BATCH_SIZE] for start in range(0, len(pages), DOUBTFUL_BATCH_SIZE)]
        for number, batch in enumerate(batches, start=FIRST_NUMBER):
            self._work.save(NumberedFiles.name(DOUBTFUL_LISTING_NAME, number), {"pdf": self._work.pdf, "pages": batch})
        names = {"listing": DOUBTFUL_LISTING_NAME, "readings": READINGS_NAME}
        return {"state": "doubtful", "batches": NumberedFiles(len(batches), names).as_field()}

    def _accepted(self, report: dict) -> dict:
        headings = self._work.load("probe.json")["headings"]
        verification = TrialVerification(headings, excluded_spans(self._state["scope"]))
        self._state[FINDINGS_FIELD] = verification.findings(report)
        self._work.save_state(self._state)
        if self._state.get(CLEANUP_FIELD):
            return CleanupStart(self._work, self._script).started()
        return TrialAcceptance(self._work, self._script).accepted()
