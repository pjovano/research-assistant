from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import vault
from math_fonts import MathFonts

from .fontrepair import (
    STATUS_NOTHING_TO_REPAIR,
    STATUS_REPAIRED,
    STATUS_UNRESOLVED,
    STATUS_VERIFICATION_FAILED,
    STATUS_WOULD_REPAIR,
    FontRepair,
    RepairPlan,
    VerificationFailed,
)
from .fonts import FontReadError, FontRecord, PdfFonts
from .fontscan import FontScan, ScanInput
from .glyphs import IDENTITIES_PATH, Identity, IdentityResolver, IdentityTable
from .identification import GLYPHS_DIRECTORY, FontIdentification, GlyphRenders
from .keymigration import LegacyCodeKeys
from .paths import PdfLocation
from .pixels import PixelChecks, PixelResult
from .readeranswers import IdentifyReports, ReaderAnswers, ReaderLearning, literal_unicode
from .report import Report
from .textkey import TextLayerDigest
from .textlayer import CachedOccurrences, Occurrences
from .toc import TocDocument

TABLE_OPTION = "table"
CODE_OPTION = "code"
STATUS_CONFLICT = "conflict"


@dataclass(frozen=True)
class FontInputs:
    path: Path
    records: list[FontRecord]
    pixels: PixelResult
    occurrences: Occurrences


class FontCommands:
    def __init__(self, identities_path: Path = IDENTITIES_PATH, pixels: PixelChecks | None = None) -> None:
        self._identities_path = identities_path
        self._pixels = pixels or PixelChecks()

    def scan(self, args: argparse.Namespace) -> None:
        if args.all:
            Report(self._library_summaries(self._resolver(args))).print()
        else:
            self._scan_one(args)

    def _scan_one(self, args: argparse.Namespace) -> None:
        inputs = self._inputs_for(args)
        report = self._scan(inputs, self._resolver(args)).report(inputs.occurrences)
        Report({**report, "math_fonts": MathFonts(inputs.path).families(), "pixels": inputs.pixels.as_dict()}).print()

    def _inputs_for(self, args: argparse.Namespace) -> FontInputs:
        return self._inputs(PdfLocation(args.pdf).anywhere())

    def pages(self, args: argparse.Namespace) -> None:
        inputs = self._inputs_for(args)
        pages = self._scan(inputs, self._resolver(args)).flagged_file_pages(inputs.occurrences)
        Report({"pdf": inputs.path.name, "page_count": TocDocument(inputs.path).page_count(), "pages": pages}).print()

    def identify(self, args: argparse.Namespace) -> None:
        inputs = self._inputs_for(args)
        directory = vault.SCRATCH_DIR / inputs.path.stem / GLYPHS_DIRECTORY
        codes = self._scan(inputs, self._resolver(args)).used(inputs.occurrences)
        entries = FontIdentification(codes, inputs.occurrences, GlyphRenders(inputs.path, directory)).report()
        Report({"pdf": inputs.path.name, "renders": str(directory), "codes": entries}).print()

    def learn(self, args: argparse.Namespace) -> None:
        table = self._table(args)
        identity = Identity(literal_unicode(args.unicode, args.equals_sign), args.method)
        key, entry = self._learned_entry(table, args, identity)
        conflict = table.conflicting(key, entry)
        result = {"table": str(table.path), "key": key, "entry": entry, "conflict": conflict}
        if conflict is not None:
            Report({**result, "status": STATUS_CONFLICT, "written": False}).print()
        elif not args.apply:
            Report(result).print_as_dry_run("write the entry into the identity table")
        else:
            table.write(key, entry)
            Report({**result, "written": True}).print()

    @staticmethod
    def _learned_entry(table: IdentityTable, args: argparse.Namespace, identity: Identity) -> tuple[str, dict]:
        code = getattr(args, CODE_OPTION, None)
        if code is not None:
            return table.entry_for_code(args.font, code, identity)
        return table.entry_for(args.font, args.glyph, identity)

    def migrate_keys(self, args: argparse.Namespace) -> None:
        table = self._table(args)
        plan = {"table": str(table.path), **LegacyCodeKeys(table.entries()).plan()}
        if not args.apply:
            Report(plan).print_as_dry_run("rewrite the legacy code keys of the identity table")
            return
        table.rewrite(lambda entries: LegacyCodeKeys(entries).migrated())
        Report({**plan, "written": True}).print()

    def learn_reader(self, args: argparse.Namespace) -> None:
        reports = IdentifyReports(args.identify)
        learning = ReaderLearning(self._table(args), ReaderAnswers(args.answers, reports).answers(), reports)
        plan = learning.plan()
        if not args.apply:
            Report(plan).print_as_dry_run("write the learned entries into the identity table")
            return
        learning.apply()
        Report({**plan, "written": True}).print()

    def repair(self, args: argparse.Namespace) -> None:
        inputs = self._inputs_for(args)
        plan = RepairPlan(self._scan(inputs, self._resolver(args)).used(inputs.occurrences))
        reason = self._reason_not_to_apply(plan, args)
        if reason is None:
            self._apply(inputs, plan)
        elif reason == STATUS_WOULD_REPAIR:
            report = Report(self._plan_report(reason, inputs.path, plan))
            report.print_as_dry_run("rewrite the ToUnicode tables in place")
        else:
            Report(self._plan_report(reason, inputs.path, plan)).print()

    def _reason_not_to_apply(self, plan: RepairPlan, args: argparse.Namespace) -> str | None:
        if plan.is_empty():
            return STATUS_NOTHING_TO_REPAIR
        if not plan.has_patches():
            return STATUS_UNRESOLVED
        if not args.apply:
            return STATUS_WOULD_REPAIR
        if plan.is_partial() and not args.partial:
            return STATUS_UNRESOLVED
        return None

    def _apply(self, inputs: FontInputs, plan: RepairPlan) -> None:
        try:
            FontRepair(inputs.path, plan, inputs.records).run()
        except VerificationFailed as failure:
            Report({"status": STATUS_VERIFICATION_FAILED, "pdf": inputs.path.name, "reason": str(failure)}).print()
            return
        Report({**self._plan_report(STATUS_REPAIRED, inputs.path, plan), "written": str(inputs.path)}).print()

    def _plan_report(self, status: str, pdf_path: Path, plan: RepairPlan) -> dict:
        return {"status": status, "pdf": pdf_path.name, **plan.as_dict()}

    def _inputs(self, pdf_path: Path) -> FontInputs:
        digest = TextLayerDigest(pdf_path)
        records = PdfFonts(pdf_path).records()
        pixels = self._pixels.result(pdf_path, digest)
        wanted = self._wanted_glyphs(records, pixels)
        occurrences = Occurrences(CachedOccurrences(pdf_path, wanted, digest=digest).collect(), wanted)
        return FontInputs(pdf_path, records, pixels, occurrences)

    @staticmethod
    def _scan(inputs: FontInputs, resolver: IdentityResolver) -> FontScan:
        scanned = ScanInput(inputs.path, inputs.records, inputs.pixels.disagreements, inputs.occurrences)
        return FontScan(scanned, resolver)

    def _table(self, args: argparse.Namespace) -> IdentityTable:
        override = getattr(args, TABLE_OPTION, None)
        return IdentityTable(Path(override) if override else self._identities_path)

    def _resolver(self, args: argparse.Namespace) -> IdentityResolver:
        return IdentityResolver(self._table(args))

    @staticmethod
    def _wanted_glyphs(records: list[FontRecord], pixels: PixelResult) -> frozenset:
        disagreeing = {disagreement.glyph for disagreement in pixels.disagreements}
        stand_ins = {glyph for record in records for glyph in record.stand_in_glyphs()}
        return frozenset(disagreeing | stand_ins)

    def _library_summaries(self, resolver: IdentityResolver) -> list[dict]:
        summaries = [self._summary_or_error(path, resolver) for path in vault.list_pdfs(vault.LIBRARY_DIR)]
        return [summary for summary in summaries if summary.get("codes_flagged") or "error" in summary]

    def _summary_or_error(self, pdf_path: Path, resolver: IdentityResolver) -> dict:
        try:
            return FontScan(ScanInput(pdf_path, PdfFonts(pdf_path).records()), resolver).summary()
        except FontReadError as failure:
            return {"pdf": pdf_path.name, "error": str(failure)}
