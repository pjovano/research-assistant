from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_core._domain.fields import ManifestError
from agent_core._domain.home import HomeRelative
from agent_core._domain.manifest import MANIFEST_NAME, DomainManifest
from agent_core._domain.registry import REFUSED, Registry
from agent_core._domain.schema import ValidManifest
from agent_core._domain.settings import FolderGuards, SettingsBlocks
from agent_core._domain.shelf import DEVELOPER_ROOT, ManifestShelf

PROGRAM = "domain.py"
DESCRIPTION = ("Read the domains' manifests, validate them, list the registry the dispatcher routes by, and "
               "generate a domain's settings blocks and folder guards from them.")
EXIT_FAILURE = 1
HELP_MANIFESTS = f"list every manifest: each named one, or every {DEVELOPER_ROOT}/*/{MANIFEST_NAME}"
HELP_VALIDATE = ("check the domain's manifest against the schema: every key known, and the handles, entry skills, "
                 "exposure, and unattended levels well formed")
HELP_REGISTRY = ("list each manifest's domain with its handles and entry skills, after validating it and checking "
                 "each entry skill's exposure: never all three risks, and untrusted content wherever the skill "
                 "has the web capability; exits 1 if a manifest is refused")
HELP_SETTINGS = "print the `permissions` and `sandbox` blocks of the domain's .claude/settings.json"
HELP_GUARDS = ("print the guards of the domain's .claude/settings.local.json: for each sensitive folder of the "
               "other manifests, a Read and an Edit rule in `permissions.deny` and a `sandbox.filesystem.denyRead` "
               "entry")
HELP_NAMED = f"the manifests to read; if none, every {MANIFEST_NAME} one level under the developer root"
HELP_DEVELOPER = f"the directory whose subdirectories hold the domains; default {DEVELOPER_ROOT}"
HELP_DOMAIN = f"the domain's manifest; default ./{MANIFEST_NAME}"


class CommandLine:
    def run(self, argv: list[str]) -> None:
        try:
            self._run(argv)
        except ManifestError as error:
            self._print({"error": str(error)})
            sys.exit(EXIT_FAILURE)

    def _run(self, argv: list[str]) -> None:
        parser = self._parser()
        args = parser.parse_args(argv)
        if args.handler is None:
            parser.print_help()
            return
        payload = args.handler(args)
        self._print(payload)
        if args.refuses(payload):
            sys.exit(EXIT_FAILURE)

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog=PROGRAM, description=DESCRIPTION)
        parser.set_defaults(handler=None, refuses=lambda payload: False)
        commands = parser.add_subparsers(dest="command")
        self._shelf_command(commands, "manifests", HELP_MANIFESTS, self._manifests)
        registry = self._shelf_command(commands, "registry", HELP_REGISTRY, self._registry)
        registry.set_defaults(refuses=lambda payload: bool(payload[REFUSED]))
        self._domain_command(commands, "validate", HELP_VALIDATE, self._validate)
        self._domain_command(commands, "settings", HELP_SETTINGS, self._settings)
        guards = self._shelf_command(commands, "guards", HELP_GUARDS, self._guards)
        guards.add_argument("--domain", type=Path, default=Path(MANIFEST_NAME), help=HELP_DOMAIN)
        return parser

    @staticmethod
    def _shelf_command(commands, name: str, help_text: str, handler) -> argparse.ArgumentParser:
        command = commands.add_parser(name, help=help_text, description=help_text)
        command.add_argument("named", nargs="*", type=Path, metavar="MANIFEST", help=HELP_NAMED)
        command.add_argument("--developer", type=Path, default=DEVELOPER_ROOT, help=HELP_DEVELOPER)
        command.set_defaults(handler=handler)
        return command

    @staticmethod
    def _domain_command(commands, name: str, help_text: str, handler) -> argparse.ArgumentParser:
        command = commands.add_parser(name, help=help_text, description=help_text)
        command.add_argument("--domain", type=Path, default=Path(MANIFEST_NAME), help=HELP_DOMAIN)
        command.set_defaults(handler=handler)
        return command

    @staticmethod
    def _manifests(args: argparse.Namespace) -> list[dict]:
        manifests = ManifestShelf(args.named, args.developer).manifests()
        return [ManifestListing(manifest).as_dict() for manifest in manifests]

    @staticmethod
    def _registry(args: argparse.Namespace) -> dict:
        return Registry(ManifestShelf(args.named, args.developer).paths()).as_dict()

    @staticmethod
    def _validate(args: argparse.Namespace) -> dict:
        manifest = ValidManifest.read(args.domain)
        return {"manifest": HomeRelative(args.domain).text(), "name": manifest.manifest.name, "valid": True}

    @staticmethod
    def _settings(args: argparse.Namespace) -> dict:
        return SettingsBlocks(DomainManifest.read(args.domain)).as_dict()

    @staticmethod
    def _guards(args: argparse.Namespace) -> dict:
        neighbours = ManifestShelf(args.named, args.developer).manifests()
        return FolderGuards(DomainManifest.read(args.domain), neighbours).as_dict()

    @staticmethod
    def _print(payload: object) -> None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


class ManifestListing:
    def __init__(self, manifest: DomainManifest) -> None:
        self._manifest = manifest

    def as_dict(self) -> dict:
        folders = [{"name": folder.name, "access": folder.access, "sensitive": folder.sensitive}
                   for folder in self._manifest.folders]
        return {"name": self._manifest.name, "summary": self._manifest.summary,
                "path": HomeRelative(self._manifest.path).text(), "folders": folders, "vault": self._manifest.vault}
