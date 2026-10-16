from __future__ import annotations

import sys
from pathlib import Path

import vault
from engine_guard import FailedInferenceRequests

from _drive.script import ScriptRun, SkillScript
from _drive.work import Halt, SetAside, WorkStops

EXTRACT_SCRIPT = Path(__file__).resolve().parents[1] / "extract.py"
ENGINE_STEP_TIMEOUT_SECONDS = 4 * 3600
RECORDS_FILE_NAME = vault.RECORDS_FILE_NAME
UNPARSABLE = "is not valid JSON"

__all__ = ["EXTRACT_SCRIPT", "ExtractFailure", "ExtractScript", "ScriptRun"]


class ExtractFailure:
    def __init__(self, command: str, run: ScriptRun) -> None:
        self._command = command
        self._run = run

    def is_machine_wide(self) -> bool:
        return self._run.names_missing_models or self._names_unparsable_records() or self._names_failed_requests()

    def stop(self) -> WorkStops:
        if self._run.names_missing_models:
            return Halt(f"the engine's models are not in the cache; run the model step the README states: "
                        f"{self._run.tail}")
        if self._names_failed_requests():
            return Halt(f"the engine's model servers failed its requests, and nothing was cached; the engine steps "
                        f"must run outside the sandbox, with Metal: {self._run.tail}")
        if self._names_unparsable_records():
            return Halt(f"the extraction records file does not parse, and every work's record is in it: "
                        f"{self._run.tail}")
        return SetAside(f"{self._command} failed: {self._run.tail}")

    def _names_failed_requests(self) -> bool:
        return FailedInferenceRequests.__name__ in self._run.tail

    def _names_unparsable_records(self) -> bool:
        return RECORDS_FILE_NAME in self._run.tail and UNPARSABLE in self._run.tail


class ExtractScript(SkillScript):
    def __init__(self, interpreter: str = sys.executable) -> None:
        super().__init__(EXTRACT_SCRIPT, interpreter, ENGINE_STEP_TIMEOUT_SECONDS)

    def checked(self, *args: str) -> ScriptRun:
        run = self.run(*args)
        if not run.ok:
            raise ExtractFailure(args[0], run).stop()
        return run
