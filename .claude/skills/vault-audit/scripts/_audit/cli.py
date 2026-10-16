from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from _audit.baseline import BASELINE_NAME, STATUS_CHANGED, STATUS_NEW, STATUS_REMOVED, Baseline, CorruptBaseline
from _audit.measures import CodeMeasures
from _audit.pointers import InstructionPointers
from _audit.related import RelatedFiles
from _audit.residue import Residue
from _audit.scope import (
    ALL_GROUPS,
    CODE_GROUPS,
    INSTRUCTION_GROUPS,
    PIPELINE_GROUPS,
    ControlPlaneFiles,
    RepositoryPath,
)
from _audit.works import NamedWorks

DESCRIPTION = "Vault Maintenance: the mechanical half of an audit, over what changed since the last one."
BASELINE_PATH = Path(__file__).resolve().parents[2] / BASELINE_NAME
CODE_SUFFIX = ".py"
EXIT_FAILURE = 1
FLAG_ALL = "--all"
FLAG_CHANGED = "--changed"
HELP_CHANGED = "the audit set: the files changed since the last accepted audit, and the files that name them"
HELP_LINT = "the mechanical checks over the whole control plane"
HELP_RESIDUE = "the stranded work product at every residue site"
HELP_ACCEPT = "record every control-plane file as audited, ending this audit"
HELP_ALL = "cover every control-plane file"
HELP_CHANGED_ONLY = "cover only the files changed since the last accepted audit"

Handler = Callable[[argparse.Namespace], dict]


class CommandLine:
    def run(self, argv: list[str]) -> None:
        parser = self._parser()
        if not argv:
            parser.print_help()
            return
        args = parser.parse_args(argv)
        try:
            self._print(args.handler(args))
        except CorruptBaseline as error:
            self._print({"error": str(error)})
            sys.exit(EXIT_FAILURE)

    @staticmethod
    def _print(payload: dict) -> None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="audit.py", description=DESCRIPTION)
        commands = parser.add_subparsers(dest="command")
        changed = Subcommand("changed", HELP_CHANGED, self._changed).added_to(commands)
        changed.add_argument(FLAG_ALL, action="store_true", help=HELP_ALL)
        lint = Subcommand("lint", HELP_LINT, self._lint).added_to(commands)
        lint.add_argument(FLAG_CHANGED, action="store_true", help=HELP_CHANGED_ONLY)
        Subcommand("residue", HELP_RESIDUE, self._residue).added_to(commands)
        Subcommand("accept", HELP_ACCEPT, self._accept).added_to(commands)
        return parser

    def _changed(self, args: argparse.Namespace) -> dict:
        audit_set = AuditSet.of_everything() if args.all else AuditSet.of_changes()
        return audit_set.as_dict()

    def _lint(self, args: argparse.Namespace) -> dict:
        audit_set = AuditSet.of_changes() if args.changed else AuditSet.of_everything()
        return {"files": audit_set.counts(), "code": CodeMeasures(audit_set.code()).findings(),
                "pointers": InstructionPointers(audit_set.instructions()).findings(),
                "works": NamedWorks(audit_set.instructions() + audit_set.pipeline_code()).findings()}

    @staticmethod
    def _residue(_args: argparse.Namespace) -> dict:
        return Residue().report()

    @staticmethod
    def _accept(_args: argparse.Namespace) -> dict:
        return Baseline(BASELINE_PATH).accept(ControlPlaneFiles().all())


class Subcommand:
    def __init__(self, name: str, help_text: str, handler: Handler) -> None:
        self._name = name
        self._help = help_text
        self._handler = handler

    def added_to(self, commands: argparse._SubParsersAction) -> argparse.ArgumentParser:
        command = commands.add_parser(self._name, help=self._help)
        command.set_defaults(handler=self._handler)
        return command


class EveryFile:
    def selected(self, paths: list[Path], _baseline: Baseline) -> list[Path]:
        return paths


class ChangedFiles:
    def selected(self, paths: list[Path], baseline: Baseline) -> list[Path]:
        if baseline.accepted_on() is None:
            return paths
        changed = baseline.changed(paths)
        unaudited = set(changed[STATUS_NEW]) | set(changed[STATUS_CHANGED])
        return [path for path in paths if RepositoryPath(path).label() in unaudited]


class AuditSet:
    def __init__(self, selection: EveryFile | ChangedFiles, files: ControlPlaneFiles | None = None,
                 baseline_path: Path = BASELINE_PATH) -> None:
        self._selection = selection
        self._files = ControlPlaneFiles() if files is None else files
        self._baseline = Baseline(baseline_path)

    @classmethod
    def of_everything(cls, files: ControlPlaneFiles | None = None, baseline_path: Path = BASELINE_PATH) -> AuditSet:
        return cls(EveryFile(), files, baseline_path)

    @classmethod
    def of_changes(cls, files: ControlPlaneFiles | None = None, baseline_path: Path = BASELINE_PATH) -> AuditSet:
        return cls(ChangedFiles(), files, baseline_path)

    def as_dict(self) -> dict:
        changed = self._baseline.changed(self._files.all())
        read_first = self._selected(ALL_GROUPS)
        return {"accepted": self._baseline.accepted_on(), "changed": self._named(read_first),
                "related": self._named(RelatedFiles(self._files).of(read_first)),
                STATUS_REMOVED: changed[STATUS_REMOVED], "counts": self.counts()}

    def instructions(self) -> list[Path]:
        return self._selected(INSTRUCTION_GROUPS)

    def code(self) -> list[Path]:
        return [path for path in self._selected(CODE_GROUPS) if path.suffix == CODE_SUFFIX]

    def pipeline_code(self) -> list[Path]:
        return [path for path in self._selected(PIPELINE_GROUPS) if path.suffix == CODE_SUFFIX]

    def counts(self) -> dict:
        return {"instructions": len(self.instructions()), "code": len(self.code()),
                "control_plane": len(self._files.all())}

    def _selected(self, groups: tuple[str, ...]) -> list[Path]:
        return self._selection.selected(self._files.of_groups(groups), self._baseline)

    @staticmethod
    def _named(paths: list[Path]) -> list[str]:
        return [RepositoryPath(path).label() for path in paths]
