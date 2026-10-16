from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from _support import SKILLS_DIR

INGEST = SKILLS_DIR / "ingest" / "scripts" / "ingest.py"
EXTRACT = SKILLS_DIR / "extract-corpus" / "scripts" / "extract.py"
QUEUED_WORK = "Author - 2020 - Title.pdf"
STEP_TIMEOUT_SECONDS = 300


class TemporaryHome:
    def __init__(self, base: Path) -> None:
        self.home = base / "home"
        self.elsewhere = base / "elsewhere"
        self._machine = self.home / ".research-vault"

    def build(self) -> "TemporaryHome":
        (self.home / "vault" / "research vault").mkdir(parents=True)
        self.elsewhere.mkdir()
        self._machine.mkdir()
        (self._machine / "machine.json").write_text(json.dumps({"vault_dir": "~/vault"}), encoding="utf-8")
        return self

    def with_queued_work(self) -> "TemporaryHome":
        queue = self.scratch / "backfill" / "queue.txt"
        queue.parent.mkdir(parents=True)
        queue.write_text(f"{QUEUED_WORK}\n", encoding="utf-8")
        return self

    def last_line(self, script: Path, *args: str) -> dict:
        process = subprocess.run([sys.executable, str(script), *args], cwd=self.elsewhere, env=self._environment(),
                                 capture_output=True, text=True, timeout=STEP_TIMEOUT_SECONDS)
        return json.loads(process.stdout.splitlines()[-1])

    def _environment(self) -> dict:
        return {**os.environ, "HOME": str(self.home)}

    @property
    def scratch(self) -> Path:
        return self._machine / "cache"
