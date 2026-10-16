from __future__ import annotations

import subprocess

MAX_REPORTED_STDERR = 2000


class ToolFailed(RuntimeError):
    pass


class Subprocess:
    def run(self, arguments: list[str]) -> str:
        try:
            completed = subprocess.run(arguments, capture_output=True, text=True, check=False)
        except OSError as error:
            raise ToolFailed(f"could not start {arguments[0]}: {error}") from error
        if completed.returncode != 0:
            raise ToolFailed(f"{arguments[0]} exited {completed.returncode}: "
                             f"{completed.stderr.strip()[-MAX_REPORTED_STDERR:]}")
        return completed.stdout
