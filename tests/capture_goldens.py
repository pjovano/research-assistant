from __future__ import annotations

import argparse
import sys

from _support import GOLDENS_DIR, Golden, LiveTree

LiveTree.activate()

from _snapshots import ALL_SNAPSHOTS

DESCRIPTION = (
    "Compare the pure functions' output against the pinned goldens. Updating a "
    "golden is a deliberate act -- nothing is written without --apply."
)
APPLY_HELP = "Overwrite the goldens with freshly captured output."


class GoldenCapture:
    def __init__(self, snapshots) -> None:
        self._snapshots = snapshots

    def compare(self) -> int:
        print(f"Comparing goldens under {GOLDENS_DIR}")
        drifted = [name for name in map(self._compared, self._snapshots) if name]
        return self._verdict(drifted)

    def rewrite(self) -> int:
        print(f"Capturing into {GOLDENS_DIR}")
        for snapshot in self._snapshots:
            self._rewrite(snapshot)
        return 0

    def _compared(self, snapshot) -> str:
        golden, payload = Golden(snapshot.name), snapshot.build()
        state = self._state(golden, payload)
        print(f"  {snapshot.name}: {len(payload)} entries -- {state}")
        return "" if state == "unchanged" else snapshot.name

    def _state(self, golden: Golden, payload: object) -> str:
        if not golden.exists():
            return "MISSING"
        return "unchanged" if golden.matches(payload) else "CHANGED"

    def _verdict(self, drifted: list[str]) -> int:
        if not drifted:
            return 0
        print(f"\n{len(drifted)} golden(s) differ: {', '.join(drifted)}", file=sys.stderr)
        print("A refactor that moves one is a regression -- revert it. Only an "
              "intentional fix earns --apply.", file=sys.stderr)
        return 1

    def _rewrite(self, snapshot) -> None:
        golden, payload = Golden(snapshot.name), snapshot.build()
        golden.save(payload)
        print(f"  {snapshot.name}: {len(payload)} entries -> {golden.path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--apply", action="store_true", help=APPLY_HELP)
    capture = GoldenCapture(ALL_SNAPSHOTS)
    return capture.rewrite() if parser.parse_args().apply else capture.compare()


if __name__ == "__main__":
    sys.exit(main())
