from __future__ import annotations

import ast
import contextlib
import io
import json
import logging
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _support import PROJECT_ROOT, LiveTree

LiveTree.activate()

import providers
from _adapters.host.icloud import ICloudFolder
from _clean.ocr import VisionReader
from agent_core._adapters.host.launchd import LaunchdScheduler
from agent_core._adapters.host.macos_notifiers import DesktopNotifier, RemindersNotifier
from agent_core._adapters.host.macos_readings import MacosReadings
from _extract.engine import MarkerEngine
from _rag.chroma import EmbeddingStore
from _rag.embedding import OllamaEmbedder
from _rag.fulltext import FullTextStore
from _rag.reranking import LlamaReranker
from _references.parsing import CitationParser
from _transcribe.diarizing import PyannotePipeline
from _transcribe.whispering import WhisperRun
from _vault.machine import DEFAULT_PROFILE, PROFILES_DIR, MalformedProviders, ProviderChoices, UnknownProfile
from _writing.conversion import Trash
from engine_reach import MetalAccess
from providers import ApiKey, ProviderNotConfigured, ProviderReport, Providers

PORTS_DIR = PROJECT_ROOT / "lib" / "_ports"
RELATIVE_IMPORT = "."
LIB_DIR = PROJECT_ROOT / "lib"
TODAYS_CLASSES = {
    providers.SCHEDULER: LaunchdScheduler,
    providers.NOTIFIER: (DesktopNotifier, RemindersNotifier),
    providers.SYSTEM_READINGS: MacosReadings,
    providers.ACCELERATOR: MetalAccess,
    providers.TRASH: Trash,
    providers.SYNC: ICloudFolder,
    providers.EMBEDDER: OllamaEmbedder,
    providers.EMBEDDING_STORE: EmbeddingStore,
    providers.FULLTEXT_STORE: FullTextStore,
    providers.RERANKER: LlamaReranker,
    providers.LAYOUT_ENGINE: MarkerEngine,
    providers.LINE_RECOGNIZER: VisionReader,
    providers.TRANSCRIBER: WhisperRun,
    providers.DIARIZER: PyannotePipeline,
    providers.CITATION_PARSER: CitationParser,
}
PORTS_WITHOUT_AN_ADAPTER_YET = {providers.LOCATIONS: "macos"}
TODAYS_MACHINES = {
    "no keys": {},
    "the empty vault of CI": {"vault_dir": "~/.research-vault/empty-vault"},
    "the local settings": {"ollama_url": "http://localhost:11434", "embedding_model": "qwen3-embedding:4b",
                           "whisper_model": "~/models/whisper.bin", "engine_slots": 8},
}
HEAVY_MODULES = ("torch", "ocrmac", "pyannote", "chromadb", "transformers", "marker", "surya")
ADAPTER_MODULES = ("agent_core._adapters.host.launchd", "_rag.embedding", "_extract.engine", "_clean.ocr",
                   "_transcribe.whispering", "_references.parsing", "_writing.conversion", "_adapters.host.icloud")
PLACEHOLDER_KEY = "placeholder-value-of-the-test-key"
OTHER_PLACEHOLDER = "placeholder-value-of-another-variable"
KEY_VARIABLE = "EMBEDDING_API_KEY"
API_EMBEDDER = {"adapter": "openai-compatible", "url": "https://embeddings.invalid/v1", "model": "placeholder",
                "key_env": KEY_VARIABLE}
GIVEN_MACHINE = Path("copies") / "machine.json"
GIVEN_MACHINE_PATTERN = re.escape(str(GIVEN_MACHINE))


def profile_entries(name: str) -> dict:
    return json.loads((PROFILES_DIR / f"{name}.json").read_text(encoding="utf-8"))["providers"]


class FreshInterpreter:
    def __init__(self, statements: str) -> None:
        self._statements = statements

    def printed(self) -> object:
        program = (f"import json, sys\nsys.path.insert(0, {str(LIB_DIR)!r})\nimport providers\n"
                   f"built = providers.Providers.from_machine({{}}, {{}})\n{self._statements}")
        completed = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
        return json.loads(completed.stdout)


class CountingAdapter:
    def __init__(self, adapter: type) -> None:
        self._adapter = adapter
        self.loads = 0

    def load(self) -> type:
        self.loads += 1
        return self._adapter


class LogLines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))

    @contextlib.contextmanager
    def captured(self):
        root = logging.getLogger()
        previous = root.level
        root.addHandler(self)
        root.setLevel(logging.DEBUG)
        try:
            yield self
        finally:
            root.removeHandler(self)
            root.setLevel(previous)


class TestTodaysMachineJsonResolvesToTodaysClasses(unittest.TestCase):
    def test_every_accessor_returns_the_class_constructed_today(self) -> None:
        for shape, machine in TODAYS_MACHINES.items():
            built = Providers.from_machine(machine, {})
            for port, expected in TODAYS_CLASSES.items():
                with self.subTest(machine=shape, port=port):
                    self.assertEqual(expected, built.adapter(port))

    def test_each_named_accessor_answers_for_its_port(self) -> None:
        built = Providers.from_machine({}, {})
        for port, expected in TODAYS_CLASSES.items():
            with self.subTest(port=port):
                self.assertIs(built.adapter(port), getattr(built, port)())

    def test_a_port_whose_adapter_is_not_built_yet_names_the_adapter(self) -> None:
        built = Providers.from_machine({}, {})
        for port, adapter in PORTS_WITHOUT_AN_ADAPTER_YET.items():
            with self.subTest(port=port):
                with self.assertRaisesRegex(ProviderNotConfigured, rf"providers\.{port}\.adapter names '{adapter}'"):
                    getattr(built, port)()

    def test_resolving_every_accessor_imports_no_heavy_dependency(self) -> None:
        statements = ("[built.adapter(port) for port in providers.PORTS if port != providers.LOCATIONS]\n"
                      f"print(json.dumps(sorted(set({HEAVY_MODULES!r}) & set(sys.modules))))")
        self.assertEqual([], FreshInterpreter(statements).printed())


class TestTheProfile(unittest.TestCase):
    def test_a_machine_json_without_a_profile_takes_mac_local(self) -> None:
        self.assertEqual("mac-local", DEFAULT_PROFILE)
        self.assertEqual(profile_entries("mac-local"), ProviderChoices({}).entries())

    def test_every_profile_names_every_port(self) -> None:
        for name in ProviderChoices({}).available():
            with self.subTest(profile=name):
                self.assertEqual(set(providers.PORTS), set(profile_entries(name)))

    def test_the_three_profiles_ship(self) -> None:
        self.assertEqual(["api-light", "linux-local", "mac-local"], ProviderChoices({}).available())

    def test_linux_local_resolves_the_local_engine_and_names_the_host_adapters_it_awaits(self) -> None:
        built = Providers.from_machine({"profile": "linux-local"}, {})
        self.assertIs(MarkerEngine, built.layout_engine())
        with self.assertRaisesRegex(ProviderNotConfigured, r"providers\.scheduler\.adapter names 'systemd'"):
            built.scheduler()

    def test_api_light_leaves_each_hosted_port_unconfigured_naming_its_key(self) -> None:
        built = Providers.from_machine({"profile": "api-light"}, {})
        for port, entry in profile_entries("api-light").items():
            if entry:
                continue
            with self.subTest(port=port):
                with self.assertRaisesRegex(ProviderNotConfigured, rf"providers\.{port}\.adapter is not set"):
                    built.adapter(port)

    def test_api_light_keeps_the_stores_and_the_citation_parser_local(self) -> None:
        built = Providers.from_machine({"profile": "api-light"}, {})
        local = (built.embedding_store(), built.fulltext_store(), built.citation_parser())
        self.assertEqual((EmbeddingStore, FullTextStore, CitationParser), local)

    def test_an_unknown_profile_is_refused_naming_the_profiles(self) -> None:
        with self.assertRaisesRegex(UnknownProfile, r"'gpu-farm'.*api-light, linux-local, mac-local"):
            ProviderChoices({"profile": "gpu-farm"}).entries()

    def test_providers_that_are_not_an_object_are_refused_as_malformed_providers(self) -> None:
        with self.assertRaisesRegex(MalformedProviders, r"providers must be an object"):
            ProviderChoices({"providers": ["embedder"]}).entries()

    def test_malformed_providers_are_not_reported_as_an_unknown_profile(self) -> None:
        with self.assertRaises(MalformedProviders) as raised:
            ProviderChoices({"providers": ["embedder"]}).entries()
        self.assertNotIsInstance(raised.exception, UnknownProfile)


class TestAConfigurationErrorNamesTheFileItCameFrom(unittest.TestCase):
    def test_an_unknown_profile_names_the_file(self) -> None:
        with self.assertRaisesRegex(UnknownProfile, rf"^{GIVEN_MACHINE_PATTERN} names the profile"):
            ProviderChoices({"profile": "gpu-farm"}, GIVEN_MACHINE).entries()

    def test_malformed_providers_name_the_file(self) -> None:
        with self.assertRaisesRegex(MalformedProviders, rf"^{GIVEN_MACHINE_PATTERN}'s providers"):
            ProviderChoices({"providers": ["embedder"]}, GIVEN_MACHINE).entries()

    def test_an_unset_adapter_names_the_file(self) -> None:
        built = Providers.from_machine({"providers": {providers.EMBEDDER: {}}}, {}, GIVEN_MACHINE)
        with self.assertRaisesRegex(ProviderNotConfigured, rf"under providers\.embedder in {GIVEN_MACHINE_PATTERN},"):
            built.embedder()

    def test_an_entry_that_is_not_an_object_names_the_file(self) -> None:
        built = Providers.from_machine({"providers": {providers.EMBEDDER: "ollama"}}, {}, GIVEN_MACHINE)
        with self.assertRaisesRegex(ProviderNotConfigured, rf"providers\.embedder in {GIVEN_MACHINE_PATTERN} must"):
            built.embedder()


class TestAnOverride(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = ProviderChoices({"providers": {providers.EMBEDDER: API_EMBEDDER}}).entries()

    def test_the_override_replaces_the_profiles_entry_for_its_port_whole(self) -> None:
        self.assertEqual(API_EMBEDDER, self.entries[providers.EMBEDDER])

    def test_every_other_port_keeps_the_profiles_entry(self) -> None:
        expected = {port: entry for port, entry in profile_entries("mac-local").items() if port != providers.EMBEDDER}
        kept = {port: entry for port, entry in self.entries.items() if port != providers.EMBEDDER}
        self.assertEqual(expected, kept)

    def test_an_override_of_a_port_the_profile_left_empty_is_taken(self) -> None:
        machine = {"profile": "api-light", "providers": {providers.LAYOUT_ENGINE: {"adapter": "marker-local"}}}
        self.assertIs(MarkerEngine, Providers.from_machine(machine, {}).layout_engine())

    def test_an_override_naming_an_adapter_this_version_lacks_names_it(self) -> None:
        built = Providers.from_machine({"providers": {providers.EMBEDDER: API_EMBEDDER}}, {})
        with self.assertRaisesRegex(ProviderNotConfigured, r"providers\.embedder\.adapter names 'openai-compatible'"):
            built.embedder()


class TestAMissingKey(unittest.TestCase):
    def test_a_port_without_an_entry_names_the_port_and_the_key(self) -> None:
        with self.assertRaisesRegex(ProviderNotConfigured, r"providers\.reranker\.adapter is not set"):
            Providers({}, {}).reranker()

    def test_an_entry_without_an_adapter_names_the_key(self) -> None:
        with self.assertRaisesRegex(ProviderNotConfigured, r"providers\.embedder\.adapter is not set"):
            Providers({providers.EMBEDDER: {"model": "placeholder"}}, {}).embedder()

    def test_an_entry_that_is_not_an_object_is_refused_naming_the_port_and_the_file(self) -> None:
        with self.assertRaisesRegex(ProviderNotConfigured, r"providers\.embedder in .* must be an object"):
            Providers({providers.EMBEDDER: "ollama"}, {}).embedder()


class TestTheApiKey(unittest.TestCase):
    def setUp(self) -> None:
        self.environ = {KEY_VARIABLE: PLACEHOLDER_KEY, "OTHER_VARIABLE": OTHER_PLACEHOLDER}
        self.built = Providers({providers.EMBEDDER: API_EMBEDDER}, self.environ)

    def test_the_key_comes_from_the_variable_key_env_names(self) -> None:
        key = self.built.api_key(providers.EMBEDDER)
        self.assertEqual((ApiKey, KEY_VARIABLE, PLACEHOLDER_KEY), (type(key), key.variable, key.value))

    def test_the_key_shows_its_variable(self) -> None:
        self.assertIn(KEY_VARIABLE, repr(self.built.api_key(providers.EMBEDDER)))

    def test_neither_the_key_nor_the_providers_show_its_value(self) -> None:
        key = self.built.api_key(providers.EMBEDDER)
        for shown in (repr(key), str(key), f"{key}", repr(self.built), str(self.built)):
            with self.subTest(shown=shown):
                self.assertNotIn(PLACEHOLDER_KEY, shown)

    def test_an_unset_variable_is_reported_by_its_name_alone(self) -> None:
        built = Providers({providers.EMBEDDER: API_EMBEDDER}, {"OTHER_VARIABLE": OTHER_PLACEHOLDER})
        with self.assertRaises(ProviderNotConfigured) as raised:
            built.api_key(providers.EMBEDDER)
        self.assertIn(KEY_VARIABLE, str(raised.exception))
        self.assertNotIn(OTHER_PLACEHOLDER, f"{raised.exception!s}{raised.exception!r}")

    def test_an_entry_without_key_env_names_the_key(self) -> None:
        built = Providers({providers.EMBEDDER: {"adapter": "openai-compatible"}}, self.environ)
        with self.assertRaisesRegex(ProviderNotConfigured, r"providers\.embedder\.key_env is not set"):
            built.api_key(providers.EMBEDDER)

    def test_no_error_and_no_log_line_echoes_the_key(self) -> None:
        with LogLines().captured() as log:
            self.built.api_key(providers.EMBEDDER)
            with self.assertRaises(ProviderNotConfigured) as raised:
                self.built.embedder()
        shown = [str(raised.exception), repr(raised.exception), *log.lines]
        self.assertEqual([], [line for line in shown if PLACEHOLDER_KEY in line])


class TestTheAccessorIsLazyAndCached(unittest.TestCase):
    def setUp(self) -> None:
        self.counting = CountingAdapter(OllamaEmbedder)
        self.built = Providers({providers.EMBEDDER: {"adapter": "counted"}}, {},
                               {providers.EMBEDDER: {"counted": self.counting}})

    def test_nothing_is_loaded_before_the_first_call(self) -> None:
        self.assertEqual(0, self.counting.loads)

    def test_the_second_call_returns_the_same_object_without_loading_again(self) -> None:
        first = self.built.embedder()
        self.assertIs(first, self.built.embedder())
        self.assertEqual(1, self.counting.loads)

    def test_building_the_providers_imports_no_adapter_module(self) -> None:
        statements = f"print(json.dumps(sorted(set({ADAPTER_MODULES!r}) & set(sys.modules))))"
        self.assertEqual([], FreshInterpreter(statements).printed())


class TestTheReport(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.machine_path = Path(directory.name) / "machine.json"

    def test_the_report_names_each_ports_class_and_each_unconfigured_port(self) -> None:
        ports = ProviderReport(Providers.from_machine({}, {}), DEFAULT_PROFILE).as_dict()["ports"]
        self.assertEqual("_rag.embedding.OllamaEmbedder", ports[providers.EMBEDDER])
        self.assertEqual(["agent_core._adapters.host.macos_notifiers.DesktopNotifier",
                          "agent_core._adapters.host.macos_notifiers.RemindersNotifier"], ports[providers.NOTIFIER])
        self.assertEqual("_adapters.host.icloud.ICloudFolder", ports[providers.SYNC])
        self.assertIn("'macos'", ports[providers.LOCATIONS]["unconfigured"])

    def test_the_script_prints_the_report_of_the_machine_json_it_is_given(self) -> None:
        self.machine_path.write_text(json.dumps({"profile": "linux-local"}), encoding="utf-8")
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            providers.main(["--machine", str(self.machine_path)])
        report = json.loads(printed.getvalue())
        self.assertEqual(("linux-local", "_extract.engine.MarkerEngine"),
                         (report["profile"], report["ports"][providers.LAYOUT_ENGINE]))

    def test_the_script_exits_naming_the_machine_json_it_is_given_when_its_profile_is_unknown(self) -> None:
        self.machine_path.write_text(json.dumps({"profile": "gpu-farm"}), encoding="utf-8")
        with self.assertRaises(SystemExit) as raised:
            providers.main(["--machine", str(self.machine_path)])
        self.assertTrue(str(raised.exception.code).startswith(f"{self.machine_path} names the profile 'gpu-farm'"))

    def test_the_report_names_the_machine_json_it_is_given_for_an_unset_adapter(self) -> None:
        self.machine_path.write_text(json.dumps({"providers": {providers.EMBEDDER: {}}}), encoding="utf-8")
        report = ProviderReport.of_machine_file(self.machine_path, {}).as_dict()
        self.assertIn(f"in {self.machine_path},", report["ports"][providers.EMBEDDER]["unconfigured"])


class TestThePortsImportOnlyTheStandardLibrary(unittest.TestCase):
    def test_every_import_of_the_ports_package_is_of_the_standard_library(self) -> None:
        foreign = [f"{path.name}: {name}" for path in sorted(PORTS_DIR.glob("*.py")) for name in self._imported(path)
                   if name not in sys.stdlib_module_names and name != "__future__"]
        self.assertEqual([], foreign)

    def test_the_ports_package_holds_the_host_and_the_compute_ports(self) -> None:
        self.assertEqual(["__init__.py", "compute.py", "host.py"], sorted(path.name for path in PORTS_DIR.glob("*.py")))

    @classmethod
    def _imported(cls, path: Path) -> list[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return [name for node in ast.walk(tree) for name in cls._top_level_names(node)]

    @staticmethod
    def _top_level_names(node: ast.AST) -> list[str]:
        if isinstance(node, ast.Import):
            return [alias.name.split(".")[0] for alias in node.names]
        if isinstance(node, ast.ImportFrom):
            return [RELATIVE_IMPORT if node.level else node.module.split(".")[0]]
        return []


if __name__ == "__main__":
    unittest.main()
