from __future__ import annotations

import json

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_DOUBTFUL = 2
EXIT_CHANGED = 3
EXIT_ENGINE_FAILED = 4
FORCE_OCR_FLAG = "--force-ocr"


class JsonOutput:
    def emit(self, payload: dict) -> None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
