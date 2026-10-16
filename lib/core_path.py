from __future__ import annotations

import sys
from pathlib import Path

VENDORED_CORE_LIB = Path(__file__).resolve().parent.parent / "vendor" / "agent-core" / "lib"


class VendoredCore:
    @staticmethod
    def join_module_path() -> None:
        entry = str(VENDORED_CORE_LIB)
        if entry not in sys.path:
            sys.path.append(entry)
