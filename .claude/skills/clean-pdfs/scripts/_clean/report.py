from __future__ import annotations

import json
import sys


class Report:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def print(self) -> None:
        print(json.dumps(self._payload, indent=2, ensure_ascii=False))

    def print_as_dry_run(self, next_step: str) -> None:
        self.print()
        print(f"\n(dry run -- pass --apply to {next_step})", file=sys.stderr)
