from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _drive.detached import DetachedLauncher, DetachedStep, StepHost
from _drive.script import REPOSITORY_ROOT, ScriptRun, first_json
from _drive.work import STATE_ASIDE, IngestWorks, SetAside

INGEST_SCRIPT = Path(__file__).resolve().parents[1] / "ingest.py"
COMMAND_SEPARATOR = "--"
STATE_RAN = "ran"


class IngestLauncher(DetachedLauncher):
    def __init__(self, interpreter: str = sys.executable) -> None:
        super().__init__(INGEST_SCRIPT, interpreter)


class DetachedCommand:
    def __init__(self, words: list[str]) -> None:
        self.words = words[1:] if words[:1] == [COMMAND_SEPARATOR] else list(words)
        if not self.words:
            raise SetAside(f"no command given after {COMMAND_SEPARATOR}")

    def outcome(self) -> dict:
        try:
            process = subprocess.run(self.words, cwd=REPOSITORY_ROOT, capture_output=True, text=True)
        except OSError as error:
            return {"state": STATE_ASIDE, "question": f"`{self}` did not start: {error}"}
        return self._read(ScriptRun(process.returncode, process.stdout, process.stderr))

    def _read(self, run: ScriptRun) -> dict:
        lines = [line for line in run.stdout.splitlines() if line.strip()]
        last = first_json(lines[-1]) if lines else None
        if isinstance(last, dict):
            return last
        if run.ok:
            return {"state": STATE_RAN}
        return {"state": STATE_ASIDE, "question": f"`{self}` failed: {run.tail}"}

    def __str__(self) -> str:
        return " ".join(self.words)


class DetachedSteps:
    def __init__(self, works: IngestWorks, host: StepHost) -> None:
        self._works = works
        self._host = host

    def start(self, key: str, command: DetachedCommand) -> dict:
        return self._step(key).start(key, COMMAND_SEPARATOR, *command.words)

    def run(self, key: str, command: DetachedCommand) -> None:
        self._step(key).record(command.outcome())

    def wait(self, key: str) -> dict:
        return self._step(key).wait()

    def _step(self, key: str) -> DetachedStep:
        return DetachedStep(self._works.work(key), self._host)
