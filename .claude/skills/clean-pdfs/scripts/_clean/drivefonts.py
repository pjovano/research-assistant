from __future__ import annotations

import json
import sys
from pathlib import Path

from _drive.numbered import FIRST_NUMBER, NUMBER_SLOT, NumberedFiles
from _drive.script import ScriptRun, SkillScript
from _drive.work import Halt, SetAside, WorkDirectory, WorkStops

from .fontrepair import (
    STATUS_NOTHING_TO_REPAIR,
    STATUS_REPAIRED,
    STATUS_UNRESOLVED,
    STATUS_VERIFICATION_FAILED,
    STATUS_WOULD_REPAIR,
)
from .glyphs import normalize_glyph
from .readeranswers import MAX_UNRESOLVED_CODES, REASON_TOO_MANY_CODES

CLEAN_SCRIPT = Path(__file__).resolve().parents[1] / "clean.py"
STATUS_VISION_UNAVAILABLE = "vision-unavailable"
VISION_NAMED = "Apple Vision"
UNPARSABLE_TABLE = "is not valid JSON"
SCAN_ATTEMPTS = 2
GLYPH_GROUP_SIZE = 45
IDENTIFY_NAME = "identify.json"
ANSWERS_PATTERN = "answers-*.json"
GROUP_LISTING_PATTERN = "identify-*.json"
GROUP_LISTING_PREFIX = "identify-"
GROUP_ANSWERS_PREFIX = "answers-"
GROUP_LISTING_NAME = f"{GROUP_LISTING_PREFIX}{NUMBER_SLOT}.json"
GROUP_ANSWERS_NAME = f"{GROUP_ANSWERS_PREFIX}{NUMBER_SLOT}.json"
GLYPH_FILE_PATTERNS = ("identify*.json", "answers*.json")
PARTIAL_OPTION = "--partial"
STATE_BOOKMARK = "bookmark"
FORCE_OCR_FIELD = "force_ocr"
PIXEL_PAGES_FIELD = "pixel_pages"
PIXEL_PAGES_NAME = "pixel-pages.json"


class CleanScript(SkillScript):
    def __init__(self, interpreter: str = sys.executable) -> None:
        super().__init__(CLEAN_SCRIPT, interpreter)


class Retry(Exception):
    def __init__(self, question: str) -> None:
        super().__init__(question)
        self.question = question


class UnsettledCodes(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

    def outcome(self) -> dict:
        return self._outcome("every page")

    def outcome_on_pages(self, listing: Path, flagged: FlaggedPages) -> dict:
        return {**self._outcome(f"the {flagged.count} of {flagged.page_count} pages a flagged code occurs on"),
                PIXEL_PAGES_FIELD: str(listing)}

    def _outcome(self, read_from_pixels: str) -> dict:
        return {"state": STATE_BOOKMARK, FORCE_OCR_FIELD: True,
                "notes": [f"the font repair cannot settle the codes, {self.reason}: the font repair is skipped, "
                          f"and Stage 2 reads {read_from_pixels} from pixels"]}


class FlaggedPages:
    def __init__(self, report: dict) -> None:
        self.pages = report.get("pages") or []
        self.page_count = report.get("page_count") or 0

    @property
    def count(self) -> int:
        return len(self.pages)

    @property
    def leave_a_page_to_the_text_layer(self) -> bool:
        return 0 < self.count < self.page_count


class UnsettledReading:
    def __init__(self, work: WorkDirectory, script: SkillScript) -> None:
        self._work = work
        self._script = script

    def outcome(self, unsettled: UnsettledCodes) -> dict:
        flagged = self._flagged_pages()
        if not flagged.leave_a_page_to_the_text_layer:
            return unsettled.outcome()
        self._work.save(PIXEL_PAGES_NAME, {"pages": flagged.pages})
        return unsettled.outcome_on_pages(self._work.path(PIXEL_PAGES_NAME), flagged)

    def _flagged_pages(self) -> FlaggedPages:
        run = self._script.run("fonts", "pages", self._work.pdf)
        return FlaggedPages(run.payload() if run.ok else {})


class CodesLeftAsIs:
    def __init__(self, rows: list[dict]) -> None:
        self._keys = {(row["font"], normalize_glyph(row["glyph"])) for row in rows}

    def cover(self, unresolved: list[dict]) -> bool:
        return bool(unresolved) and all((row["font"], normalize_glyph(row["code"])) in self._keys for row in unresolved)


NO_CODES_LEFT_AS_IS = CodesLeftAsIs([])


class FontsFailure:
    def __init__(self, command: str, run: ScriptRun) -> None:
        self._command = command
        self._run = run

    def stop(self) -> WorkStops:
        if self._names_vision_unavailable():
            return Halt("Apple Vision is not available on this machine: run the font repair on a Mac")
        if self._run.names_missing_models:
            return Halt(f"the engine's models are not in the cache; run the model step the README states: "
                        f"{self._run.tail}")
        if UNPARSABLE_TABLE in self._run.tail:
            return Halt(f"the identity table does not parse: {self._run.tail}")
        return SetAside(f"`{self._command}` failed: {self._run.tail}")

    def is_vision_unresponsive(self) -> bool:
        return VISION_NAMED in self._run.tail and not self._names_vision_unavailable()

    def _names_vision_unavailable(self) -> bool:
        payload = self._run.payload()
        return isinstance(payload, dict) and payload.get("status") == STATUS_VISION_UNAVAILABLE


class FontsCommand:
    def __init__(self, script: SkillScript, pdf: str) -> None:
        self._script = script
        self._pdf = pdf

    def report(self, *args: str) -> dict:
        run = self._script.run("fonts", *args)
        if not run.ok:
            raise FontsFailure(" ".join(("fonts", *args)), run).stop()
        return run.payload()

    def repair_in_place(self, left_as_is: CodesLeftAsIs = NO_CODES_LEFT_AS_IS) -> None:
        plan = self.report("repair", self._pdf)
        status = plan.get("status")
        leaves_only_codes_as_is = left_as_is.cover(plan.get("unresolved", []))
        if status == STATUS_NOTHING_TO_REPAIR or (status == STATUS_UNRESOLVED and leaves_only_codes_as_is):
            return
        if status == STATUS_UNRESOLVED:
            raise UnsettledCodes("as `fonts repair` leaves a flagged code with no identity")
        if status != STATUS_WOULD_REPAIR:
            raise SetAside(f"`fonts repair` reported {status}")
        partial = (PARTIAL_OPTION,) if plan.get("partial") and leaves_only_codes_as_is else ()
        self._applied(self.report("repair", self._pdf, "--apply", *partial))

    @staticmethod
    def _applied(repaired: dict) -> None:
        status = repaired.get("status")
        if status == STATUS_VERIFICATION_FAILED:
            raise UnsettledCodes(f"as `fonts repair --apply` failed its verification: {repaired.get('reason', '')}")
        if status != STATUS_REPAIRED:
            raise SetAside(f"`fonts repair --apply` reported {status}: {repaired.get('reason', '')}")

    def scan(self) -> dict:
        run = self._script.run("fonts", "scan", self._pdf)
        if run.ok:
            return self._read_whole(run.payload())
        failure = FontsFailure("fonts scan", run)
        if failure.is_vision_unresponsive():
            raise Retry(f"Apple Vision gave no reading twice: {run.tail}")
        raise failure.stop()

    @staticmethod
    def _read_whole(report: dict) -> dict:
        if report.get("pixels", {}).get("unread_sheets", 0) > 0:
            raise Retry("`fonts scan` left engine line sheets unread twice")
        return report


class GlyphGroups:
    def __init__(self, work: WorkDirectory) -> None:
        self._work = work

    def written(self, identify: dict) -> dict:
        codes = identify["codes"]
        starts = range(0, len(codes), GLYPH_GROUP_SIZE)
        for number, start in enumerate(starts, start=FIRST_NUMBER):
            group = {**identify, "codes": codes[start:start + GLYPH_GROUP_SIZE]}
            self._work.save(NumberedFiles.name(GROUP_LISTING_NAME, number), group)
        return NumberedFiles(len(starts), {"codes": GROUP_LISTING_NAME, "answers": GROUP_ANSWERS_NAME}).as_field()


class FontScanStep:
    def __init__(self, work: WorkDirectory, script: SkillScript) -> None:
        self._work = work
        self._fonts = FontsCommand(script, work.pdf)
        self._unsettled = UnsettledReading(work, script)

    def run(self) -> dict:
        try:
            return self._listed_or_repaired()
        except UnsettledCodes as unsettled:
            return self._unsettled.outcome(unsettled)

    def _listed_or_repaired(self) -> dict:
        for pattern in GLYPH_FILE_PATTERNS:
            self._work.discard(pattern)
        unresolved = self._scanned()["codes_unresolved"]
        if unresolved == 0:
            self._fonts.repair_in_place()
            return {"state": STATE_BOOKMARK, "notes": []}
        if unresolved > MAX_UNRESOLVED_CODES:
            raise UnsettledCodes(f"as {REASON_TOO_MANY_CODES} ({unresolved}), more than a glyph read settles")
        identify = self._fonts.report("identify", self._work.pdf)
        self._work.save(IDENTIFY_NAME, identify)
        return {"state": "glyphs", "groups": GlyphGroups(self._work).written(identify)}

    def _scanned(self) -> dict:
        retry = None
        for _ in range(SCAN_ATTEMPTS):
            try:
                return self._fonts.scan()
            except Retry as failure:
                retry = failure
        raise SetAside(retry.question)


class ReaderAnswersFiles:
    def __init__(self, work: WorkDirectory) -> None:
        self._work = work

    def unanswered_listings(self) -> list[str]:
        listings = self._work.matching(GROUP_LISTING_PATTERN)
        return [listing.name for listing in listings
                if not self._work.has(listing.name.replace(GROUP_LISTING_PREFIX, GROUP_ANSWERS_PREFIX, 1))]

    def merged(self) -> Path | None:
        files = self._work.matching(ANSWERS_PATTERN)
        if not files:
            return None
        answers = [answer for path in files for answer in self._listed(path)]
        self._work.save("answers.json", answers)
        return self._work.path("answers.json")

    @staticmethod
    def _listed(path: Path) -> list:
        try:
            answers = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            raise SetAside(f"the glyph reader wrote a malformed answers file: {path}") from None
        if not isinstance(answers, list):
            raise SetAside(f"the glyph reader's answers file holds no list: {path}")
        return answers
