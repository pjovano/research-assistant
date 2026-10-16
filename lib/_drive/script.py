from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from _drive.work import SetAside

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_SECONDS = 3600
TAIL_CHARS = 600
JSON_OPENER = re.compile(r"[\[{]")
MISSING_MODEL_MARKERS = ("offline mode", "OfflineModeIsEnabled", "LocalEntryNotFoundError",
                         "outgoing traffic has been disabled", "cannot find the requested files")


def first_json(text: str):
    decoder = json.JSONDecoder()
    for match in JSON_OPENER.finditer(text):
        try:
            return decoder.raw_decode(text[match.start():])[0]
        except ValueError:
            continue
    return None


class ScriptRun:
    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self._stderr = stderr

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def tail(self) -> str:
        return (self.stdout + self._stderr).strip()[-TAIL_CHARS:]

    @property
    def names_missing_models(self) -> bool:
        return any(marker in self.tail for marker in MISSING_MODEL_MARKERS)

    def payload(self):
        return first_json(self.stdout)


class SkillScript:
    def __init__(self, script: Path, interpreter: str = sys.executable, timeout_seconds: int = TIMEOUT_SECONDS) -> None:
        self._script = script
        self._interpreter = interpreter
        self._timeout_seconds = timeout_seconds

    def run(self, *args: str) -> ScriptRun:
        command = [self._interpreter, str(self._script), *args]
        process = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True,
                                 timeout=self._timeout_seconds)
        return ScriptRun(process.returncode, process.stdout, process.stderr)

    def checked(self, *args: str) -> ScriptRun:
        run = self.run(*args)
        if not run.ok:
            raise SetAside(f"{args[0]} failed: {run.tail}")
        return run
