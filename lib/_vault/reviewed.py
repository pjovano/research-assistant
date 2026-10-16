from __future__ import annotations

import json
from pathlib import Path

from _vault.naming import nfc

RECORDS_FILE_NAME = "extraction-records.json"
REVIEWED_KEY = "reviewed"


class ExtractionRecordsUnreadable(ValueError):
    pass


class ReviewedBasenames:
    def __init__(self, records_path: Path) -> None:
        self._records_path = records_path

    def keys(self) -> set[str]:
        return {nfc(basename) for basename, record in self._records().items() if record.get(REVIEWED_KEY)}

    def _records(self) -> dict:
        if not self._records_path.is_file():
            return {}
        try:
            records = json.loads(self._records_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as failure:
            raise ExtractionRecordsUnreadable(f"{self._records_path} could not be read as JSON ({failure}); "
                                              "no reviewed work is known") from failure
        if not isinstance(records, dict):
            raise ExtractionRecordsUnreadable(f"{self._records_path} holds no JSON object of records; "
                                              "no reviewed work is known")
        return records
