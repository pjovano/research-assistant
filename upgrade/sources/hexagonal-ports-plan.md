# Hexagonal ports plan

**This plan is the detail reference for `unified-upgrade-plan.md`.** The
unified plan governs: where the two differ, it wins. This plan gives the
worker building each item what the unified plan leaves out: the pieces, the
file references, and the acceptance. Each PR below is one unified item.

| PR | Item | Wave | Lane | Repo | Absorbs |
| --- | --- | --- | --- | --- | --- |
| 1 | P1 | W1 | b | research-assistant | — |
| 2 | P2 | W1 | b | research-assistant | — |
| 3 | P3 | W2 | c | research-assistant | — |
| 4 | P4 | W2 | c | research-assistant | — |
| 5 | P5+M3 | W2 | b | research-assistant | machines plan item 3, the Remote Control service |
| 6 | P6+M4 | W2 | b | research-assistant | machines plan item 4, the iCloud placeholder check |
| 7a–f, 7h | P7a–f, P7h | W3 | b | research-assistant | — |
| 7g | P7g | W4 | b | research-assistant | — |
| 8 | P8 | W5 | a | research-assistant | — |
| 9 | P9 | W2 | d | research-assistant | — |
| 10 | P10 | W2 | d | research-assistant | — |
| 11 | P11 | W4 | b | research-assistant | — |
| 12 | P12 | W4 | b | research-assistant | — |
| 13 | P13 | W4 | b | research-assistant | — |
| 14 | P14 | W5 | a | research-assistant | — |
| 15 | P15 | W5 | a | research-assistant | — |
| 16 | P16 | W5 | a | research-assistant | — |
| 17 | G17 | W4 | c | agent-core + research-assistant | — |
| 18 | G18 | W4 | c | agent-core + research-assistant | — |
| 19 | G19 | W4 | c | agent-core + research-assistant | — |
| 20 | G20 | W4 | c | agent-core + research-assistant | — |
| 21 | G21 | W5 | c | research-assistant | — |
| 22 | P22 | W6 | — | — | deferred: not in this round |

Restructure `research-assistant` as ports and adapters. `research-assistant`
is a new public repo, made in W0 from one squashed snapshot of
`research-tools`; the switch gives it the name, not a GitHub rename. The aims:
(1) someone installs it on macOS, Linux, or Windows through WSL2 and gets a
working vault; (2) on a machine too weak for the local models, each local
model is swapped for a hosted API by configuration, with no code change;
(3) the agent host behind the workers is a port, with Claude Code as the
reference adapter and no loss of its functionality; (4) the running setup is
untouched until the switch, and `mac-local` behaves exactly as today. Each
item checks (4) by a test in CI, or by a line in `upgrade/rehearsal.md` run
old against new at the switch rehearsal (W8).

Aims (1) and (2) serve other people installing it. The user runs one primary
Mac and reaches it from secondaries through Remote Control, and tests neither
the other OSes nor the APIs. CI and the cloud test them instead:

- **Linux:** the cloud VM (Ubuntu 24.04), and a CI job that installs
  `api-light` on a clean runner.
- **WSL2:** documented in the README; an optional Windows CI job.
- **macOS:** a `macos-latest` job on every PR (P2), free on a public repo.

**Accepted, not ported:**

- **Standard tools are requirements.** Zotero with Better BibTeX and ZotMoov,
  Obsidian, git and `gh`, `uv` and Python 3.12, pandoc, typst, ffmpeg,
  yt-dlp. Each runs on every OS and is installed with that OS's package
  manager. `lib/zotero.py` and the Obsidian Markdown dialect stay as they are.
- **Tuning is per engine.** The page checks were tuned on Marker 2.0 / Surya,
  and the pixel check on Apple Vision. Another engine or OCR adapter is
  supported but untuned. `calibrate` (P12) and `calibrate-ocr` (P13) measure
  the gap; the plan promises no parity.
- **Native Windows is out of scope.** Windows runs the tools inside WSL2.
  `fcntl`, `os.kill`, `setsid`, and the POSIX shell strings stay.

## 1. Where we start

| Area | State today | Consequence |
| --- | --- | --- |
| Model judgment | No Python calls a model. Every judgment crosses a file contract: a `drive-*` step writes a listing, a worker writes an answers file, the next step parses it (`lib/_drive/`) | The agent-host port already exists in substance; what is Claude-specific is the hosting layer |
| Search compute | `OllamaEmbedder`, `EmbeddingStore` (Chroma), `FullTextStore` (SQLite), `LlamaReranker`; `tests/_rag_fakes.py` mirrors them method for method; constructed directly in `_rag/search.py:104`, `_rag/status.py:56`, `search/search.py:58,73`, `search/server.py:77`, `_graph/cli.py:69` | Ports in all but name; construction is scattered |
| Embedding guard | The store records its model and raises `EmbeddingModelMismatch` | Switching provider already forces a rebuild |
| Layout engine | `MarkerEngine.convert(pdf, pages) -> dict` in `extract-corpus/_extract/engine.py`; built in `_extract/build.py:94` and `_extract/layersample.py:136`; lifecycle in `surya_servers.py`, `engine_turn.py`, `engine_slots.py`, `engine_guard.py`, `engine_reach.py`, `engine_environment.py`, `_extract/prefetch.py` | A clean call seam with a heavy, Mac-shaped lifecycle around it |
| Line OCR | `VisionRecognizer` / `VisionReader` through `ocrmac` (`clean-pdfs/_clean/ocr.py`, `pixels.py:198`); `ocrmac` is darwin-only in `requirements.txt` | The pixel check fails off macOS (`VisionUnavailable`) |
| Talks | `WhisperRun` over the whisper.cpp CLI through a `Subprocess` helper; `PyannotePipeline.turns(audio) -> list[Turn]` | Two clear seams |
| Citation parser | HF token classifier `SIRIS-Lab/citation-parser-ENTITY`, CPU, cached in SQLite | Small enough for any machine; stays local |
| Health | `Detector` and `Notifier` Protocols exist (`_health/watch.py`); adapters: `osascript`, Reminders, launchd, `sysctl`, `NSProcessInfo`; the job's label and plist contents are hard-coded (`installer.py:40`, `launch_agent.py:32-42`); no uninstall | Half-ported already |
| Remote Control | A hand-written `local.claude-remote-control.plist` outside git, loaded, with `--spawn worktree` and no `caffeinate`; in worktree mode no remote session can run a batch, because preflight refuses a worktree (`_ingest/checkout.py:56-59`) | The service exists but no code builds it |
| Synced folders | iCloud's "name 2.md" conflict pattern in `_ingest/preflight.py:41` and `_bibliographies/drive.py:197`; no check that a file's bytes are on disk | A batch can fail midway on an iCloud placeholder |
| Paths | `_vault/paths.py` resolves `VAULT_ROOT` and every directory constant at import, from `machine.json`; 65 non-test modules use the constants (as `vault.X`), and 92 test files patch them; `tests/_vaults.py`'s `TempVault` patches the attributes; only the CI empty-vault action sets `vault_dir`; `INBOX_DIR` is `~/Desktop/inbox` | The main obstacle to a configurable host |
| Settings | 12 modules read `machine.json` keys (13 counting `paths.py`), each with its own key constants (`_rag/settings.py`, `_transcribe/settings.py`, `_references/parsing.py`, …) | No single place chooses adapters |
| Hooks | `lib/harness_hooks.py`: `HookEvent` parses Claude's stdin JSON; `permission_decision` emits Claude's `hookSpecificOutput`; the checks themselves are host-neutral | Two small functions are the whole host coupling |
| Workers | 22 `.claude/agents/*.md`: `model:` 14 × `claude-sonnet-5`, 2 × `haiku`, 6 × `inherit`; Claude-only keys `omitClaudeMd`, `effort`, `experimental.cacheTtl`, `tools:` | Model names and host keys sit in every worker file |
| Orchestration | `.claude/workflows/ingest.js` (717 lines) and `resolve-tasks.js` (152) on the Workflow runtime (`agent`, `parallel`, `phase`); the `relay` worker exists so the workflow can run a script | The hardest coupling |
| Instruction prose | Host tool names: `SendUserFile` (4 files), the Agent tool (6), skill invocation (7), `WebSearch`/`WebFetch` (6), the browser (1) | Prose work under `clean-prose` |
| CI | `ubuntu-latest` only; 553 test modules; no `sys.platform` skip: the skips are typst, the HF model cache, and the node runtime; the lock resolves CPU torch off darwin | The core already runs on Linux |
| Setup | README "Running it": macOS, `brew`, manual `machine.json`, manual model pulls | No bootstrap, no doctor |

## 2. Target architecture

```
                        CLI scripts · vault-rag MCP server · workflows · hooks
                                      (driving adapters)
                                               │
                                     lib/providers.py
                         reads machine.json → profile → builds adapters
                                               │
   ┌──────────────────────────── core (unchanged domain logic) ────────────────────────────┐
   │ page checks · folios · references · citation graph · bibliographies · notes · drive   │
   └───────────────┬───────────────────────┬────────────────────────┬──────────────────────┘
          lib/_ports/host.py      lib/_ports/compute.py      lib/_ports/agent.py (agent-core)
                   │                       │                        │
   lib/_adapters/host/            lib/_adapters/compute/      lib/_adapters/agent/ (agent-core)
     macos.py  linux.py             local/   api/               claude_code.py  headless.py
```

| Layer | Holds | Never holds |
| --- | --- | --- |
| `lib/_ports/` | `Protocol` classes and the value types they exchange; stdlib only | an import of a third-party package, a path, a URL |
| `lib/_adapters/` | one module per adapter; the third-party import happens inside it | domain rules |
| `lib/providers.py` | the composition root: one function per port returning the configured adapter, built lazily, cached per process | any I/O beyond reading `machine.json` and the environment |
| core | everything else in `lib/` and the skill scripts | a direct construction of an adapter class |

The host and compute ports live in `research-assistant`. The agent-host port
and its adapters (Track G) live in `agent-core`, at the same paths, and reach
each domain through the `vendor/agent-core/` subtree.

### Profiles and configuration

`machine.json` gains two keys. Everything else in it stays valid, and both
keys are additive, so the old setup still reads it.

```json
{
  "profile": "mac-local",
  "providers": {
    "embedder":  {"adapter": "openai-compatible", "url": "https://…/v1", "model": "…", "key_env": "EMBEDDING_API_KEY"},
    "layout_engine": {"adapter": "datalab-api", "key_env": "DATALAB_API_KEY", "concurrency": 4}
  }
}
```

| Profile | Host adapters | Compute adapters | Install extras |
| --- | --- | --- | --- |
| `mac-local` (today) | macOS | Marker local (MPS), Apple Vision, Ollama, llama-server, whisper.cpp, pyannote | `engine`, `audio`, `mac` |
| `linux-local` | Linux | Marker local (CUDA or CPU), Tesseract, Ollama, llama-server, whisper.cpp, pyannote | `engine`, `audio` |
| `api-light` | macOS or Linux, detected | Marker API, Tesseract or a vision API, an OpenAI-compatible embedder, a hosted reranker (or none), a hosted transcriber with diarization | none |

- `providers` overrides the profile key by key.
- `api-light` ships with empty provider entries: no provider is chosen, and
  `doctor` reports each entry as unconfigured until the user fills it.
- An API key comes from the environment variable `key_env` names. It is
  never written to `machine.json`, the vault, or a log line.
- The existing per-module keys (`ollama_url`, `embedding_model`,
  `whisper_model`, …) become the local adapters' settings and keep their
  names, so today's `machine.json` needs no edit.

### Contract tests

Each port has one abstract test case in `tests/ports/` that every adapter's
test inherits: the fake, the local adapter (skipped when its binary or model
is absent, as today), and the API adapter against hand-built fixtures in
`tests/fixtures/api/`. Each fixture is written from the provider's documented
API. Recording live responses needs keys and is optional. A fixture carries
no work's text: the publish-guard's `works` check reads it. CI never makes a
live API call.

## 3. Ports

### 3.1 Host ports (`lib/_ports/host.py`)

| Port | Methods | macOS adapter (from) | Linux adapter |
| --- | --- | --- | --- |
| `Scheduler` | `install(job)`, `installed(job) -> bool`, `remove(job)`; a job is a label and its contents | launchd plist built from the job's label and contents, `launchctl bootstrap`, `launchctl bootout` (`_health/launch_agent.py`, `installer.py`) | systemd user `.service` + `.timer`, `systemctl --user enable --now`, `disable --now` |
| `Notifier` (exists) | `notify(alert)` | `DesktopNotifier`, `RemindersNotifier` (`_health/notifier.py`) | `notify-send`; `NtfyNotifier` for the phone, optional and unconfigured |
| `SystemReadings` | `memory_pressure() -> Level`, `thermal() -> Level`, `swap_used() -> int` | `sysctl kern.memorystatus_vm_pressure_level`, `NSProcessInfo.thermalState` (`_health/sampler.py`) | `/proc/pressure/memory` (PSI), `/sys/class/thermal/*/temp` against `trip_point_*` |
| `Accelerator` | `device() -> "mps" \| "cuda" \| "cpu"`, `reachable() -> str \| None` | `MetalAccess` (`engine_reach.py`), `engine_environment.py` | `torch.cuda.is_available()`, else CPU |
| `Trash` | `discard(path)` | `trash` (`_writing/conversion.py:72`) | `send2trash`, which also serves macOS |
| `SyncedFolder` | `conflict_copies(directory) -> list[Path]`, `not_downloaded(path) -> bool` | iCloud: the "name 2.md" pattern (`_ingest/preflight.py:41`, `_bibliographies/drive.py:197`); a placeholder is a dataless file (`st_flags` carries `SF_DATALESS`, `0x40000000`) or an older `.<name>.icloud` stub | Syncthing `.sync-conflict-*`, Dropbox "conflicted copy", OneDrive "-<machine>"; a service that keeps every file on disk reports no placeholder |
| `Locations` | `vault_root`, `inbox`, `state_dir`, `rag_dir` | `~/Documents`, `~/Desktop/inbox`, `~/.research-vault` | `$XDG_DOCUMENTS_DIR` or as configured, `~/inbox`, `$XDG_STATE_HOME/research-vault` |

`Level` is one enum, `normal / elevated / serious / critical`, so the
detectors read one scale. Each adapter maps its native readings onto it, and
the mapping table is part of the adapter's tests.

**Scheduler jobs.** Two jobs run on the primary's `Scheduler`:

| Job | Contents |
| --- | --- |
| health watcher | `machine-health`'s `sample` once a minute, as today |
| Remote Control server | `caffeinate -i claude remote-control --spawn same-dir`, with `KeepAlive`, in the working directory `~/Developer/assistant`; no `--name`, because the contract forbids naming a machine; installed at the switch (W8 step 4.6), never before, after one interactive run by hand (step 4.5) for the trust and enable prompts |

Both jobs take labels of their own, so the old hand-written plists stay
untouched and the rollback can reload them. The Remote Control job runs in the
dispatcher repo in `same-dir` mode, and the dispatcher hands each batch to a
background session in the research repo's main checkout, which preflight
accepts. Its code is built here, in `research-assistant`, where `Scheduler`
lives, though the job serves the dispatcher. Moving the host ports into the
core is a candidate for a later round.

**Synced folders.** Ingest preflight halts with a question on a conflict copy
or on a placeholder in the library or the inbox. Defect class: a synced file
whose bytes are not on disk. `providers.sync` chooses the adapter, `icloud`
by default.

**Locations.** `~/Documents` holds folders side by side: `library`,
`research vault`, later perhaps others. Any folder can be an Obsidian vault
of its own, and each assistant's `domain.json` lists the folders it works on.
The research defaults of `Locations` MUST name the folders the research
`domain.json` lists: `library` and `research vault` under `~/Documents`.

### 3.2 Compute ports (`lib/_ports/compute.py`)

| Port | Methods | Local adapter | API adapter |
| --- | --- | --- | --- |
| `Embedder` | `model`, `embed(texts) -> vectors`, `embed_query(text)` | `OllamaEmbedder` | `OpenAICompatibleEmbedder`: any `/v1/embeddings` (OpenAI, Mistral, Together; LM Studio and llama.cpp locally) |
| `EmbeddingStore` | as `FakeEmbeddingStore` | Chroma | — (local on every profile) |
| `FullTextStore` | as today | SQLite | — |
| `Reranker` | `scores(query, passages)`, `unavailable_cause()`, `stop()` | `LlamaReranker` | `HostedReranker`: the `query + documents → scores` shape Cohere, Jina, and Voyage share |
| `LayoutEngine` | `convert(pdf, file_pages, mode) -> dict`, `cost(pdf) -> Cost`, `session() -> ContextManager` | `MarkerLocal`: today's `MarkerEngine` plus the server lifecycle | `MarkerApi`: Datalab's hosted Marker, JSON output; the gap measured by `calibrate` (P12) |
| `LineRecognizer` | `read(images) -> list[str]` | `AppleVision` (macOS), `Tesseract` (any OS) | `CloudVisionOcr` |
| `Transcriber` | `segments(audio, language) -> list[Segment]` | `WhisperCpp` | `HostedTranscriber` with word or segment timestamps |
| `Diarizer` | `turns(audio) -> list[Turn]` | `PyannotePipeline` | `HostedDiarizer`; an adapter whose provider returns speaker-labelled segments fills both ports |
| `CitationParser` | as today | HF classifier, CPU | none: it runs on any machine |

Every API adapter is experimental: the README and `doctor` say so, because no
live provider has tested it.

**Layout engine detail.** The core keeps the engine-cost ordering (§4 of the
contract) and asks the adapter for `cost(pdf)`. `MarkerLocal.session()`
owns everything Mac-shaped today: servers, the idle reaper, the engine turn
and its yielding, the slots, the prefetch, the Metal check. `MarkerApi.session()`
is a semaphore of `concurrency` with retry and backoff. A forced-OCR mode
(`MODE_FORCED_OCR`) maps to the API's own OCR flag.

**Privacy.** An API adapter sends the PDF, the corpus text, or the audio to a
third party. Each API adapter refuses to start unless its provider entry
carries `"sends": "<what>"`, written by the profile, and `doctor` prints that
line, so the choice is visible and deliberate.

### 3.3 Agent-host ports (`agent-core`: `lib/_ports/agent.py`)

| Port | Methods | Claude Code adapter | Other adapters |
| --- | --- | --- | --- |
| `HookIo` | `event_from(stdin) -> HookEvent`, `decision(permission, reason) -> str` | today's `HookEvent` and `permission_decision` | a git pre-commit adapter running the same checks |
| `WorkerSpec` (data, not a Protocol) | role, tier, capabilities, instructions body | generates `.claude/agents/<role>.md` | generates the other host's agent file |
| `WorkerRunner` | `run(spec, prompt, files) -> answers path` | the Workflow runtime's `agent()` | a headless CLI run (`claude -p`, or another host's equivalent) |
| `Policy` (data) | the `policy` and `folders` sections of each domain's `domain.json`, read through `domain.py manifests` | the core's one settings generator, `domain.py settings`, writes the `permissions` and `sandbox` blocks of `.claude/settings.json` | generates the other host's config, or documents what it cannot enforce |

**Tiers.** `small` (today's `haiku`), `standard` (today's
`claude-sonnet-5`), `session` (today's `inherit`). `providers.agent_tiers`
maps each tier to a model name per host.

**Capabilities.** A capability is a tool class: `read`, `write`, `edit`,
`shell`, `search-files`, `web`, `vault-search` (the MCP server),
`deliver-file`, `dispatch-worker`, `browser`. The generator maps each to host
tool names. The instruction prose names capabilities; a host lacking one
declares its fallback (for `deliver-file`: print the path).

**Exposure.** The three risks the assistant plan names, private data,
untrusted content, and sending out, are a skill's **exposure**, never its
capabilities. Each skill declares its exposure in `domain.json`. The
dispatcher's `registry` (A3) cross-checks each skill's declared exposure
against its generated capabilities: a skill with `web` MUST declare untrusted
content.

**Writes under `.claude/`.** The sandbox denies Bash every write to
`.claude/agents/` and `.claude/settings.json`. A generator never writes
there: it prints, and the session writes the file with the Write tool. Where
the W0 spike (X0.4, check 2) finds that the session may not write
`.claude/settings.json`, the generated blocks ship as patches in
`upgrade/settings-patches/`, which the user applies at the switch.

## 4. Pull requests, in order

Each PR: invoke `clean-code` before code and `clean-prose` before instruction
text; the suite, ruff, and the audit linter pass before and after; one
branch from `main` per PR, reaching `main` through a PR titled by the rule it
leaves in place. Every commit carries a trailer: `Change-class: refactor|feature
— <what>` for a port or an adapter, `Defect-class:` for a fix. Every PR leaves
`mac-local` behaving exactly as before; its acceptance row says how that is
checked: a test in CI, or a line the PR adds to `upgrade/rehearsal.md`.

### Track A — foundations

#### PR 1 (P1) — Ports package, composition root, profiles

| Piece | Content |
| --- | --- |
| `lib/_ports/__init__.py`, `host.py`, `compute.py` | the Protocols of §3.1 and §3.2, empty of implementations; `agent.py` comes with Track G, in `agent-core` |
| `lib/providers.py` | `Providers.from_machine(machine, environ)`; one accessor per port; lazy, cached; raises `ProviderNotConfigured` naming the key |
| `lib/profiles/*.json` | `mac-local`, `linux-local`, `api-light` (empty provider entries) |
| `lib/_vault/machine.py` | reads `profile` and `providers`; merges profile and overrides |
| `tests/ports/` | the abstract contract test cases |
| `tests/test_providers.py` | profile merge, override, missing key, key read from the environment, key never echoed |

No caller changes yet: `mac-local` resolves to the classes in use today.

#### PR 2 (P2) — CI on both OSes

| Piece | Content |
| --- | --- |
| `.github/workflows/ci.yml` | a `macos-latest` job beside `ubuntu-latest` on every PR, both running the suite, ruff, the audit linter |
| `tests/_support.py` | a `requires_platform` decorator for the platform-bound tests; the existing skips (typst, the HF model cache, the node runtime) stay skips on an absent tool |

### Track B — search compute (first API option)

#### PR 3 (P3) — Search ports adopted

- `OllamaEmbedder`, `EmbeddingStore`, `FullTextStore`, `LlamaReranker`
  declared against the Protocols; the fakes move into
  `lib/_adapters/compute/fakes.py` so tests and the contract suite share
  them.
- Every construction site of §1 asks `providers` instead:
  `_rag/search.py:104`, `_rag/status.py:56`, `search/search.py:58,73`,
  `search/server.py:77`, `_graph/cli.py:69`.

#### PR 4 (P4) — API adapters for search

| Piece | Content |
| --- | --- |
| `_adapters/compute/api/embeddings.py` | `OpenAICompatibleEmbedder`: batching, retry on 429/5xx with backoff, the dimension recorded beside the model |
| `_adapters/compute/api/rerank.py` | `HostedReranker` |
| `search` skill, `README.md` | the `api-light` row for search, marked experimental; the rebuild a provider change forces |
| tests | the contract suite against hand-built fixtures |

### Track C — host ports and Linux

#### PR 5 (P5+M3) — Health and the Remote Control job on host ports

- `Scheduler`, `SystemReadings`, `Notifier` adapters for macOS (moved) and
  Linux (new).
- The launchd adapter takes a job's label and plist contents, hard-coded
  today at `installer.py:40` and `launch_agent.py:32-42`, and implements
  `remove`. The health job takes a new label, so the old plist stays for the
  rollback.
- `machine-health/health.py:52-65` builds them through `providers`.
- `health.py uninstall [--apply]`, read-only form first, through
  `Scheduler.remove`.
- `HealthWatcherHook` in `harness_hooks.py` installs through `Scheduler`.
- The Remote Control job of §3.1 on `Scheduler`, with `install [--apply]` and
  `uninstall [--apply]`, read-only form first, under a label of its own and
  with no `--name`. Code only: it is installed at the switch (W8 step 4.6).
  Its tests build the plist and the installed, stale, loaded, and removed
  states the way the health installer's tests do.
- The `Level` mapping tables and their tests.
- The `machine-health` skill: the Linux readings and what their levels mean;
  `uninstall`.

#### PR 6 (P6+M4) — Accelerator, Trash, SyncedFolder

- `Accelerator` replaces `MetalAccess` in `engine_reach.py`,
  `engine_environment.py`, and the device choice in `_transcribe/diarizing.py`.
- `Trash` through `send2trash`, added to `requirements.txt` with the lock
  regenerated in the same PR.
- `SyncedFolder` with the iCloud, Syncthing, Dropbox, and OneDrive patterns,
  chosen by `providers.sync` (`icloud` by default).
- `_ingest/preflight.py` halts with a question on a conflict copy, as today,
  and on a placeholder in the library or the inbox. Defect class: a synced
  file whose bytes are not on disk. `_bibliographies/drive.py:197` asks the
  same port.

#### PR 7 (P7a–h) — `Locations` and the `Vault` object (several PRs)

The largest refactor in the plan, bigger than first counted. It is mechanical
and goes in slices; each slice merges promptly, so the other lanes rebase onto
it quickly.

| Step | Content |
| --- | --- |
| 7a | `Vault` value object: every path `_vault/paths.py` names today, built by `providers` from `Locations`; the old module-level constants stay, defined from a default `Vault`, as a shim |
| 7b–7f | move the 65 modules that use the constants to take a `Vault`, about a dozen per PR, grouped by skill: `extract-corpus`; `file-pdfs` and `clean-pdfs`; `classify-and-place` and `cite-links`; `_rag`, `_graph`, `search`; `_writing`, `annotate`, `transcribe-talks`, the rest |
| 7h | `tests/_vaults.py`'s `TempVault` builds a `Vault` directly instead of patching the path attributes; the 92 test files that patch the constants take that `Vault`; the CI empty-vault action keeps setting `vault_dir` |
| 7g | after U3: delete the shim; the research `audit/checks.py` of the core audit gains a lint rule refusing a new module-level path constant |

#### PR 8 (P8) — Contract and README for other OSes

- `CLAUDE.md` §1: the rule that `vault_dir` stays absent becomes "the profile
  names the vault; on the primary it stays `~/Documents`, because
  `.claude/settings.json` names that path".
- §2's inbox row: `~/Desktop/inbox/` becomes "the inbox `Locations` names".
- §5: `brew install` becomes "with the OS's package manager"; the Metal
  sentence names the `Accelerator`.

### Track D — talks

#### PR 9 (P9) — Transcriber and Diarizer ports

- `WhisperRun` becomes the `WhisperCpp` adapter; `PyannotePipeline` the
  `Pyannote` adapter; `_transcribe/cli.py:58` and the diarizing step ask
  `providers`.

#### PR 10 (P10) — Hosted transcription

- One `HostedTranscriber` that returns speaker-labelled, timestamped
  segments and fills both ports; the merge step (`_transcribe/merging.py`)
  accepts turns from either source.
- The `transcribe-talks` skill: the `api-light` row, marked experimental; that
  the transcript reviewer's input format does not change.

### Track E — extraction

#### PR 11 (P11) — LayoutEngine port, lifecycle into the local adapter

| Step | Content |
| --- | --- |
| 11a | `MarkerLocal` wraps `MarkerEngine` and `EngineModels`; `_extract/build.py:94` and `layersample.py:136` ask `providers` |
| 11b | `session()` takes over `EngineSession`, `ConversionSession` (`_extract/stage.py:28-55`), the reaper, the turn, the slots |
| 11c | `cost(pdf)` takes over the engine-cost estimate; the backfill queue, the listing, and the prefetch read it through the port |
| 11d | `ingest/_ingest/preflight.py` and `exclusive.py` ask the port whether it needs the engine lock |

Accepted only if the `regress` sample's extraction records are byte-identical
before and after, a line in `upgrade/rehearsal.md`.

#### PR 12 (P12) — Marker API adapter and `calibrate`

| Piece | Content |
| --- | --- |
| `_adapters/compute/api/marker.py` | `MarkerApi`: upload, poll, fetch JSON; the `concurrency` semaphore; retry; the page subset; the forced-OCR flag; built against Datalab's documented API, tested on hand-built fixtures |
| `extract.py calibrate --adapter <name>` | runs the trial and the page checks of the named adapter over the reviewed works `regress` samples; prints per work the pages passed, doubtful, and rejected beside the reference adapter's, and the block-tree differences |
| `extract-corpus` skill | `calibrate`; that `MarkerApi` is experimental; that a non-reference adapter's corpus files carry `engine:` in their extraction record, so a later re-extraction knows which engine wrote them |

`calibrate` turns "needs tuning" into a number a user reads before switching.
It writes nothing to the vault. It ships without numbers: running it needs a
key, and the user does not switch engines.

#### PR 13 (P13) — LineRecognizer port

- `AppleVision` (moved from `_clean/ocr.py`), `Tesseract` (new; `tesseract`
  added to the requirements list per OS), `CloudVisionOcr` (experimental,
  hand-built fixtures).
- `_clean/pixels.py:198` asks `providers`; `VisionUnavailable` becomes
  `RecognizerUnavailable`.
- `clean.py calibrate-ocr`: the pixel check's verdicts with the named
  recognizer beside Vision's, over a sample of filed PDFs, including German,
  French, Latin, and Greek pages. It ships without numbers.

### Track F — installation

#### PR 14 (P14) — Requirement extras and locks

| Piece | Content |
| --- | --- |
| `requirements/core.txt` | pymupdf, requests, pyyaml, chromadb, tiktoken, mcp, pikepdf, pylatexenc, rapidfuzz, networkx, python-docx, send2trash, ruff, transformers (the citation parser) |
| `requirements/engine.txt` | marker-pdf and its torch |
| `requirements/audio.txt` | pyannote.audio |
| `requirements/mac.txt` | ocrmac |
| `requirements/*.lock` | one universal lock per file, each header naming its compile command |
| contract §5 | "the lock" becomes "the locks the profile names"; the reinstall commands per lock; the environment rebuilt on the primary |
| `.github/workflows/ci.yml` | a clean-runner job that installs `api-light` from `core.lock` alone |
| `bin/cloud-setup.sh` | the in-repo setup script the cloud environment `research` calls (X0.2), updated in the same PR to build `~/.research-vault/venv` from the new locks: without the venv at that path every hook exits 2. If the W0 spike (X0.4, check 8) found that the environment's setup script runs before the clone, the user updates the environment by hand here instead |

`api-light` installs `core` alone: no torch, no Marker, no pyannote.

#### PR 15 (P15) — `setup.py bootstrap` and `doctor`

| Command | Does |
| --- | --- |
| `bootstrap --profile <name>` | creates `~/.research-vault/venv` with `uv`; syncs the profile's locks; writes `machine.json` from the profile if absent; creates the inbox and the state directories; installs the health job through `Scheduler`; pulls the local models the profile names (Ollama model, citation parser, tokenizer) |
| `doctor` | one line per check, `ok` / `missing` / `failing` / `unconfigured` / `unavailable` with the fix: Python and venv; each lock in sync; Zotero connector answers on `23119`; Better BibTeX answers; ZotMoov configured (the library path in its preferences); the Obsidian vault folder exists; pandoc, typst, ffmpeg, yt-dlp, tesseract found when the profile needs them; each configured adapter reachable, and each API adapter marked experimental; each empty provider entry unconfigured; each `key_env` set; each API adapter's `sends:` line |
| `doctor`, on the primary | the Remote Control job installed and loaded; no iCloud placeholder in the library or the inbox, which stands in for Optimize Mac Storage off: no documented way to read that setting is known |

`bootstrap` runs only from a terminal, never inside the agent's sandbox. The
Remote Control job is installed by the switch (W8 step 4.6), not by
`bootstrap`. Where the host has no scheduler (a cloud VM or a container
without systemd `--user`), `bootstrap` skips the jobs and `doctor` reports
them as `unavailable`, not `failing`. `bootstrap --no-jobs` skips them on
purpose: the switch runs it at step 4.4, and step 4.6 installs the health and
Remote Control jobs.

#### PR 16 (P16) — README per OS and per role

The README takes one structure:

- **Install**, one section each for macOS, Linux, and Windows (WSL2), each
  ending in `doctor`, for anyone installing it.
  - WSL2: Zotero and Obsidian on the Windows side; mirrored networking for
    `localhost:23119`; the vault under `/mnt/c/…`, whose I/O cost is
    unmeasured; the fallback of §7.
  - The profile table and the privacy line of each API adapter; every API
    adapter marked experimental.
- **Two machines: primary and secondaries.** The primary holds the control
  plane and runs every operation, with Optimize Mac Storage off and the
  Remote Control job. A secondary holds the vault through iCloud and reaches
  the primary through Remote Control.
- **Retire a former full install.** By hand: unload each launch agent with
  `launchctl bootout` and delete its plist, because a former install keeps
  only the frozen checkout, which has no `uninstall`; delete
  `~/.research-vault`, the Ollama model, the HF, torch, and datalab caches,
  and the repo clone; optionally remove Zotero. `health.py uninstall --apply`
  serves installs that run the new code.
- `.github/workflows/ci.yml`: an optional Windows job that installs in WSL2.
- **The end-to-end Linux check.** In the cloud VM under `linux-local` (Marker
  on CPU, Ollama installed in the VM), a small fixture PDF goes from Stage 2
  to Stage 6. Stages 0 and 1 need Zotero and stay untested off the Mac.

### Track G — the agent host (lands in `agent-core`)

G17–G20 run in W4 lane c, after U3. G21 runs in W5 lane c, after U2b, and
depends on U3 and G19. The ports, the generators, the manifest reader, and
`HookIo` land in `agent-core`; each domain's specs, its `domain.json`, and its
generated files land in the domain repo.

#### PR 17 (G17) — Model tiers

- `model:` in every worker file of `research-assistant` and `agent-core`
  becomes `tier:`; the generator of G19 writes `model:` back for Claude Code
  from `providers.agent_tiers`. Until G19 lands, the tier is a comment beside
  `model:`. The audit workers run in W4 lane a beside G17: one that lands
  after G17 carries `tier:` from the start.
- U3's `xref` check is written against `model:` and the stage table's Model
  column. G17 extends that same check to tiers, so the two never disagree.
- The contract's stage table names tiers; the Model column keeps today's
  names as the Claude Code mapping.

#### PR 18 (G18) — Hook adapter and git fallback

- `HookIo` with the Claude Code adapter (today's two functions) and a
  `pre-commit` adapter. `.githooks/pre-commit` runs the post-edit hook's
  checks on the staged files: the test modules that import them (X1), ruff,
  and the audit linter. The full suite stays in CI and pre-push (X1).
  `bootstrap` sets `core.hooksPath`.
- `harness_hooks.py` keeps every check; only its I/O moves.

#### PR 19 (G19) — Worker specs and the generator

| Piece | Content |
| --- | --- |
| `lib/_ports/agent.py` (`agent-core`) | the agent-host port of §3.3; its adapters sit in `agent-core`'s `lib/_adapters/agent/` |
| `agents/<role>.md` | the neutral spec: frontmatter `role`, `tier`, `capabilities`, `dispatched_by`; the instructions body unchanged |
| `lib/_adapters/agent/claude_code.py` (`agent-core`) | renders `.claude/agents/<role>.md` with `model`, `effort`, `omitClaudeMd`, `experimental.cacheTtl`, `tools` from the spec |
| `agents.py generate --host claude-code` | prints the files; the session writes them with the Write tool (§3.3); the hook after an edit to `agents/` fails if the committed file differs from the generator's output |
| core audit | the generated files are excluded from the prose checks; the specs are included |
| Vendored workers | each repo commits the agent files rendered from its own specs, and CI fails when one differs from a fresh render. A domain symlinks the core's rendered `.claude/agents/<role>.md` files, never the core's specs. |

#### PR 20 (G20) — `domain.json`, the manifest reader, and one settings generator

- Each domain's `domain.json` carries a `policy` section: the allow rules, the
  prompt-on patterns, the network hosts, the commands excluded from the
  sandbox. Its `folders` section names the folders under `~/Documents` the
  domain works on, each `read` or `write`, and MAY mark one `sensitive: true`.
- G20 creates the research `domain.json` with its `policy` and its `folders`:
  `library` (write) and `research vault` (write). A3 completes it with
  `handles`, `entry_skills`, `exposure`, and `unattended`. A CI check confirms
  that `domain.json`, the research `Locations` defaults (P7), and the
  generated sandbox name the same folders.
- The manifest reader in the core, `domain.py manifests`, reads every
  `~/Developer/*/domain.json` on the primary, or the manifests named on the
  command line. A3's `registry` builds on the same reader.
- One generator in the core, `domain.py settings`, writes the `permissions`
  and `sandbox` blocks of `.claude/settings.json`: write access to exactly the
  `write` folders, and a read-deny on every `sensitive` folder another
  manifest lists and this one does not. The W0 spike (X0.4, check 7) confirms
  that the sandbox's read-deny blocks a folder's reads.
- `~/Developer` exists only on the primary, so the tests of the reader and
  the generator use fixture manifests.
- The generator's output reaches `.claude/settings.json` as §3.3 states: the
  Write tool, or a settings patch the user applies at the switch.
- A "what this host enforces" table per adapter in the README.

#### PR 21 (G21) — Capabilities in the prose

- Each skill, worker spec, and the contract name capabilities, never host
  tool names: about 25 files from §1's counts.
- The capability names are core terms, defined in the core's `clean-prose`,
  not in a domain glossary.
- Done in slices by skill, each audited, after U2b's sentence cleanup: both
  rewrite instruction prose.

#### PR 22 (P22) — The Python batch driver (deferred)

Not in this round. It is the largest change in the plan, and it pays off only
when a second agent host is wanted. If it is ever done, the core audit's
`audit.js` moves to the same `WorkerRunner`, because it runs scripts through
`relay` too.

| Step | Content |
| --- | --- |
| 22a | `ingest.py run`: the batch state machine in Python, reading the same `drive-*` states the workflow reads today; the locks, the four-at-once Stage 0 limit, the halt, the batch update, the one report |
| 22b | `WorkerRunner` adapters: `ClaudeWorkflow` (the workflow calls `ingest.py run` with a callback per dispatch) and `HeadlessCli` (spawns the host's headless mode per worker) |
| 22c | `ingest.js` shrinks to the adapter; `relay` is deleted; the same for `resolve-tasks.js` and `audit.js` |
| 22d | a replay test: the recorded states of a past batch drive both the old workflow and the new driver to the same dispatch sequence |

## 5. Acceptance

"CI" is a test every PR runs. "Rehearsal" is a line the PR adds to
`upgrade/rehearsal.md`, run old against new on the primary in W8.

| PR | Accepted when |
| --- | --- |
| P1 | CI: `Providers.from_machine` on today's `machine.json` returns today's classes; contract suites run against the fakes |
| P2 | CI: the `ubuntu-latest` and `macos-latest` jobs green |
| P3 | CI: no `OllamaEmbedder(`, `EmbeddingStore(`, `LlamaReranker(` outside `providers` and the adapters (`git grep`). Rehearsal: `search` answers identically on a fixed query set |
| P4 | CI: `api-light` search builds and answers on a test vault from hand-built fixtures; a provider switch is refused until `sync --rebuild` |
| P5+M3 | CI: the launchd adapter builds today's health plist from its label and contents; the Remote Control plist and the installed, stale, loaded, and removed states are tested; on Linux, `sample` writes a journal line and `report` reads it. Rehearsal: a health sample on the primary; after the switch (W8 step 4.7), the Remote Control job answers a session from a secondary |
| P6+M4 | CI: no `torch.backends.mps` outside the macOS adapter; `trash` gone from `_writing/`; preflight halts on a conflict copy and on a placeholder, each built in a test |
| P7 | CI: 7g: no module-level path constant in `lib/` or the skills; the lint rule passes; 7h: no test patches a path attribute |
| P8 | CI: the audit linter passes; the core audit finds no drift between contract and code on paths |
| P9–P10 | CI: a recorded talk yields the same transcript reviewer input from the local adapters' recorded output and the hosted adapter's hand-built fixture |
| P11 | Rehearsal: the `regress` sample's extraction records byte-identical before and after; the Stage 2 → 6 backfill of three works runs as before |
| P12 | CI: `calibrate --adapter marker-api` runs on hand-built fixtures and prints its report; README and `doctor` mark `MarkerApi` experimental. No numbers are recorded |
| P13 | CI: the pixel check runs on Linux with Tesseract; `calibrate-ocr` runs and prints its per-language report. No numbers are recorded |
| P14 | CI: `api-light` installs from `core.lock` alone on a clean Linux runner and passes the suite with the engine tests skipped; the cloud environment builds its venv from the new locks. Rehearsal: the venv built from the new locks |
| P15 | Cloud VM (Ubuntu 24.04): `bootstrap --profile api-light` then `doctor` lists only Zotero, Obsidian, and the unconfigured providers as missing or unconfigured, and the scheduled jobs as `unavailable`. Rehearsal: `doctor` green on the primary, the primary checks included |
| P16 | CI: the clean-runner Linux job runs the README's Linux install commands; the optional Windows job installs in WSL2. Cloud VM: the README's Linux install reaches `doctor`; under `linux-local`, a small fixture PDF goes from Stage 2 to Stage 6. The user walks through no install |
| G17–G21 | CI: the generated `.claude/` files identical to the committed ones apart from ordering; the audit linter passes; G17: the `xref` check covers the tiers of the research and the core's audit workers; G20: `domain.json`, `Locations`, and the generated sandbox name the same folders, and the manifest reader and the generator pass on fixture manifests. Rehearsal: the generated `.claude/` files identical to today's apart from ordering |
| P22 | deferred: the replay test passes; one live batch on the primary matches the previous batch report's shape |

## 6. Decisions settled

1. **Where the agent-host layer lives.** Track G lands in `agent-core`, so
   every domain gets the worker-spec generator, `HookIo`, and the settings
   generator.
2. **Repository name.** `research-assistant` is a new public repo, made from a
   squashed snapshot of `research-tools`. The rename is the switch, not a
   GitHub rename, so the running setup keeps its checkout and launch agents
   until then. X3 (W1-a) changes the repo's own name in the snapshot, and the
   new jobs take labels of their own at the switch.
3. **Generator writes under `.claude/`.** Per the W0 spike: the generator
   prints and the session writes with the Write tool; where the spike finds
   `.claude/settings.json` closed to the session, the blocks ship as settings
   patches the user applies at the switch.
4. **Phone notifications off macOS.** ntfy ships as an optional `Notifier`,
   unconfigured.
5. **Default API providers in `api-light`.** None: the profile ships with
   empty provider entries, and `doctor` reports each as unconfigured.
6. **PR 22.** Not in this round.

## 7. Risks

| Risk | Guard |
| --- | --- |
| A refactor changes the Mac's behaviour | each PR's acceptance compares against today: byte-identical `regress` records, identical search answers, identical generated files; the old-against-new rehearsal on the primary (W8) runs every such line before the switch |
| PR 7 is long and blocks other work | the shim keeps old imports working; slices land independently and merge promptly; the quiet ports (P3–P6, P9–P10) land before it, the extraction ports (P11–P13) after it |
| An API engine passes the page checks but differs subtly (folios, footnotes) | `calibrate` before switching; the `engine:` record; the contract's rule that every quotation is verified in the PDF still binds |
| Copyrighted PDFs and private notes leave the machine | API adapters refuse to start without a `sends:` line; `doctor` prints it; `mac-local` sends nothing; fixtures carry no work's text, and the publish-guard checks every PR |
| API cost runs away on a backfill | each API adapter takes a per-batch page or token cap from its provider entry and halts the batch when it is reached, as `halt` does today |
| WSL2 file I/O under `/mnt/c` makes batches slow | the optional Windows CI job; the README documents the fallback: the vault inside the WSL filesystem, Obsidian opening it through `\\wsl$` |
| Linux readings mislead the health detectors | the `Level` mapping tables are tested per adapter; thresholds are marked provisional in the skill until a week of samples |
| Tesseract weakens the pixel check on Greek or Latin | `calibrate-ocr` reports per language before a profile leaves Vision; `mac-local` keeps Vision |
| The extras split leaves a package unpinned on one profile | each lock is universal and CI installs every profile's set |
| The prose pass (G21) drifts from the code | it runs after G19, and the core audit checks capability names against the generator's table |
