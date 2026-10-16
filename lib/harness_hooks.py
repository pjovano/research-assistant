from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from _health.hook import HealthWatcherHook

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTERPRETER = Path("~/.research-vault/venv/bin/python").expanduser()
LINTER = INTERPRETER.with_name("ruff")
SUITE_ARGUMENTS = ("-m", "unittest", "discover", "-s", "tests")
UNITTEST_BLOCK_SEPARATOR = "=" * 70
LINT_ARGUMENTS = ("check", "--output-format", "concise", ".")
AUDIT_SCRIPT = Path(".claude/skills/vault-audit/scripts/audit.py")
AUDIT_ARGUMENTS = (str(AUDIT_SCRIPT), "lint")
AUDIT_WORKS_KEY = "works"
PYTHON_SUFFIX = ".py"
MARKDOWN_SUFFIX = ".md"
BLOCKING_EXIT_CODE = 2
HOOK_TIMEOUT_SECONDS = 900
HOOK_OVERHEAD_SECONDS = 60
LINT_TIMEOUT_SECONDS = 60
AUDIT_TIMEOUT_SECONDS = 60
SUITE_TIMEOUT_SECONDS = HOOK_TIMEOUT_SECONDS - LINT_TIMEOUT_SECONDS - AUDIT_TIMEOUT_SECONDS - HOOK_OVERHEAD_SECONDS
REPAIR_COMMAND = ("uv pip sync --reinstall-package {package} --python ~/.research-vault/venv/bin/python "
                  "requirements.lock")
GUARDED_COMMANDS = {
    "--replace": "rewrites a corpus file's body; contract §4 allows it only on the user's instruction",
    "sync --rebuild": "empties the search stores before syncing every corpus file",
    "drop-page": "deletes a page from the only copy of the PDF when run with --apply",
    "toc clear": "destroys the whole outline",
    "revise": "changes or deletes the user's own annotations when run with --apply",
    "capture_goldens.py --apply": "overwrites the goldens, the only record of prior behaviour",
    "sweep --apply": "deletes scratch entries",
    "labels --apply": "rewrites a library PDF with the corpus file's folios as its page labels; contract §5 names "
                      "it an authorized overwrite of a filed PDF",
}
DRIVER_AUTHORIZED_COMMANDS = ("labels --apply",)
CORPUS_WRITE_REASON = ("the Write tool creates no note under the derived corpus: Stage 1, `file.py`, is the only "
                       "writer of a new corpus file, `transcribe.py file` of a new transcript, and Stage 4, "
                       "`bibliographies.py drive-classify`, writes their classification")


class HookEvent:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    @classmethod
    def from_stdin(cls) -> "HookEvent":
        return cls(json.load(sys.stdin))

    def edited_path(self) -> Path | None:
        given = self._payload.get("tool_input", {}).get("file_path")
        return None if given is None else Path(given)

    def command(self) -> str:
        return self._payload.get("tool_input", {}).get("command", "")


class EditedProjectFile:
    def __init__(self, path: Path | None, project_root: Path) -> None:
        self._path = path
        self._project_root = project_root.resolve()

    def checks(self) -> tuple[type[EditCheck], ...]:
        if self._path is None or not self._is_inside_the_project():
            return ()
        return CHECKS_BY_SUFFIX.get(self._path.suffix, ())

    def _is_inside_the_project(self) -> bool:
        absolute = self._path if self._path.is_absolute() else self._project_root / self._path
        return absolute.resolve().is_relative_to(self._project_root)


class EditCheck:
    LABEL: str
    INSTRUCTION: str
    COMMAND: tuple[str, ...]
    TIMEOUT_SECONDS: int
    REPAIR_PACKAGE: str | None = None

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def failure_report(self) -> str | None:
        try:
            completed = self._completed()
        except subprocess.TimeoutExpired as expired:
            return self._timeout_report(expired)
        except OSError as error:
            return self._spawn_failure(error)
        return self._finding(completed)

    def _finding(self, completed: subprocess.CompletedProcess) -> str | None:
        if completed.returncode == 0:
            return None
        return self._report(completed)

    def _spawn_failure(self, error: OSError) -> str:
        detail = f"{self.LABEL} cannot run {self.COMMAND[0]}: {error}"
        if self._program_is_repairable(error):
            return f"{detail}; reinstall it: {self._repair_command()}"
        return detail

    def _program_is_repairable(self, error: OSError) -> bool:
        return error.filename == self.COMMAND[0] and self.REPAIR_PACKAGE is not None

    def _repair_command(self) -> str:
        return REPAIR_COMMAND.format(package=self.REPAIR_PACKAGE)

    def _timeout_report(self, expired: subprocess.TimeoutExpired) -> str:
        heading = f"{self.LABEL} did not finish within {self.TIMEOUT_SECONDS} seconds"
        partial = self._body(expired.output, expired.stderr)
        return heading if not partial else f"{heading}; its output before the timeout:\n{partial}"

    def _report(self, completed: subprocess.CompletedProcess) -> str:
        body = self._body(completed.stdout, completed.stderr)
        if body and not self._was_killed(completed):
            return body
        heading = f"{self.LABEL} exited with code {completed.returncode}"
        return f"{heading}; its output:\n{body}" if body else f"{heading} and no output"

    @staticmethod
    def _was_killed(completed: subprocess.CompletedProcess) -> bool:
        return completed.returncode < 0

    def _body(self, stdout: str | bytes | None, stderr: str | bytes | None) -> str:
        streams = (self._text(stdout), self._text(stderr))
        return "\n".join(line for stream in streams for line in stream.splitlines() if line.strip())

    @staticmethod
    def _text(captured: str | bytes | None) -> str:
        return captured.decode("utf-8", "replace") if isinstance(captured, bytes) else captured or ""

    def _completed(self) -> subprocess.CompletedProcess:
        return subprocess.run(list(self.COMMAND), cwd=self._project_root, capture_output=True,
                              encoding="utf-8", errors="replace", env=self._environment(),
                              timeout=self.TIMEOUT_SECONDS)

    @staticmethod
    def _environment() -> dict:
        return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


class LintCheck(EditCheck):
    LABEL = "the linter"
    INSTRUCTION = "the linter fails after this edit; fix every finding it names:"
    COMMAND = (str(LINTER), *LINT_ARGUMENTS)
    TIMEOUT_SECONDS = LINT_TIMEOUT_SECONDS
    REPAIR_PACKAGE = "ruff"


class SuiteCheck(EditCheck):
    LABEL = "the test suite"
    INSTRUCTION = "the test suite fails after this edit; revert it or move the expectation with the fix:"
    COMMAND = (str(INTERPRETER), *SUITE_ARGUMENTS)
    TIMEOUT_SECONDS = SUITE_TIMEOUT_SECONDS
    REPORT_TAIL_BLOCKS = 10

    def _body(self, stdout: str | bytes | None, stderr: str | bytes | None) -> str:
        lines = super()._body(stdout, stderr).splitlines()
        return "\n".join(lines[self._tail_start(lines):])

    def _tail_start(self, lines: list[str]) -> int:
        block_starts = [index for index, line in enumerate(lines) if line == UNITTEST_BLOCK_SEPARATOR]
        if not block_starts:
            return 0
        return block_starts[-min(len(block_starts), self.REPORT_TAIL_BLOCKS)]


class AuditCheck(EditCheck):
    LABEL = "the audit linter"
    INSTRUCTION = "the audit linter fails after this edit; state the defect class instead of the work:"
    COMMAND = (str(INTERPRETER), *AUDIT_ARGUMENTS)
    TIMEOUT_SECONDS = AUDIT_TIMEOUT_SECONDS

    def _finding(self, completed: subprocess.CompletedProcess) -> str | None:
        if completed.returncode != 0:
            return self._report(completed)
        works = json.loads(completed.stdout)[AUDIT_WORKS_KEY]
        if not works:
            return None
        return "\n".join(f"{work['file']}:{work['line']}: {work['detail']}" for work in works)


CHECKS_BY_SUFFIX: dict[str, tuple[type[EditCheck], ...]] = {
    PYTHON_SUFFIX: (LintCheck, AuditCheck, SuiteCheck),
    MARKDOWN_SUFFIX: (AuditCheck,),
}
CHECKS_AFTER_EDIT = CHECKS_BY_SUFFIX[PYTHON_SUFFIX]


class BashGuard:
    def __init__(self, command: str) -> None:
        self._command = command

    def decision(self) -> dict | None:
        for fragment, consequence in GUARDED_COMMANDS.items():
            if self._names_in_order(fragment):
                return permission_decision("ask", f"`{fragment}` {consequence}")
        return None

    def _names_in_order(self, fragment: str) -> bool:
        tokens = self._command.split()
        position = 0
        for word in fragment.split():
            position = next((index + 1 for index in range(position, len(tokens)) if word in tokens[index]), None)
            if position is None:
                return False
        return True


class WriteGuard:
    def __init__(self, path: Path | None, corpus_dir: Callable[[], Path | None]) -> None:
        self._path = path
        self._corpus_dir = corpus_dir

    def decision(self) -> dict | None:
        if self._path is None or not self._creates_a_corpus_file():
            return None
        return permission_decision("deny", CORPUS_WRITE_REASON)

    def _creates_a_corpus_file(self) -> bool:
        corpus_dir = self._corpus_dir()
        return corpus_dir is not None and self._path.expanduser().resolve().is_relative_to(corpus_dir.resolve())


class VaultCorpus:
    @staticmethod
    def corpus_directory() -> Path | None:
        from _vault.root_errors import VaultRootNotFound
        try:
            import vault
        except VaultRootNotFound:
            return None
        return vault.CORPUS_DIR


corpus_directory = VaultCorpus.corpus_directory


def permission_decision(permission: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": permission,
                                   "permissionDecisionReason": reason}}


class HookCli:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def run(self, subcommand: str, event: HookEvent) -> int:
        if subcommand == "checks-after-edit":
            return self._checks_after_edit(event)
        if subcommand == "guard-bash":
            return self._emitted(BashGuard(event.command()).decision())
        if subcommand == "guard-write":
            return self._emitted(WriteGuard(event.edited_path(), corpus_directory).decision())
        if subcommand == "ensure-health-watcher":
            return self._emitted(HealthWatcherHook().report(event.command()))
        sys.stderr.write(f"harness_hooks: unknown subcommand {subcommand!r}\n")
        return BLOCKING_EXIT_CODE

    def _checks_after_edit(self, event: HookEvent) -> int:
        for check in EditedProjectFile(event.edited_path(), self._project_root).checks():
            report = check(self._project_root).failure_report()
            if report is not None:
                sys.stderr.write(f"{check.INSTRUCTION}\n{report}\n")
                return BLOCKING_EXIT_CODE
        return 0

    @staticmethod
    def _emitted(decision: dict | None) -> int:
        if decision is not None:
            sys.stdout.write(json.dumps(decision))
        return 0


def main() -> None:
    try:
        code = HookCli(PROJECT_ROOT).run(sys.argv[1], HookEvent.from_stdin())
    except Exception as error:
        sys.stderr.write(f"the hook failed: {error!r}\n")
        code = BLOCKING_EXIT_CODE
    sys.exit(code)


if __name__ == "__main__":
    main()
