from __future__ import annotations

import contextlib
import io
import json
import unicodedata
import unittest

from _support import LiveTree

LiveTree.activate()

import vault

from _extract.cache import MarkerCache
from _extract.cli import main
from _extract.engine import MODE_TEXT_LAYER
from _extract.paths import CorpusFile
from _extract.records import ExtractionRecord, ExtractionRecords
from _extract.regression import CachedConversion
from _extract.request import ExtractionRequest
from _extract.trial import TrialNote
from _vaults import TempVault, TextPdf

COMPOSED_BASENAME = unicodedata.normalize("NFC", "Dürer - 2020 - Über Die Proportion")
DECOMPOSED_BASENAME = unicodedata.normalize("NFD", COMPOSED_BASENAME)
FRONTMATTER = "---\ntitle: Über Die Proportion\n---\n"
REVIEWED = "2026-09-30"


class TestLibraryFilenamesInADecomposedUnicodeForm(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(vault.LIBRARY_DIR / f"{DECOMPOSED_BASENAME}.pdf").write()
        vault.corpus_path(COMPOSED_BASENAME).write_text(f"{FRONTMATTER}\n", encoding="utf-8")
        record = ExtractionRecord(ExtractionRequest(()), None, REVIEWED)
        ExtractionRecords().write(COMPOSED_BASENAME, record)

    def test_the_corpus_file_keys_the_work_by_its_composed_basename(self) -> None:
        self.assertEqual(COMPOSED_BASENAME, CorpusFile(self.pdf).basename)

    def test_the_trial_is_named_by_the_composed_basename(self) -> None:
        self.assertEqual(f"{COMPOSED_BASENAME}.md", TrialNote(CorpusFile(self.pdf)).path.name)

    def test_the_engine_cache_is_kept_under_the_composed_basename(self) -> None:
        MarkerCache(self.pdf, MODE_TEXT_LAYER).save([1], {})
        self.assertTrue((vault.SCRATCH_DIR / COMPOSED_BASENAME).is_dir())

    def test_the_record_command_finds_the_record_stored_under_the_composed_basename(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(["record", str(self.pdf)])
        self.assertEqual(REVIEWED, json.loads(output.getvalue())["record"]["reviewed"])

    def test_the_regression_sample_reads_the_record_stored_under_the_composed_basename(self) -> None:
        self.assertFalse(CachedConversion().holds(self.pdf))


if __name__ == "__main__":
    unittest.main()
