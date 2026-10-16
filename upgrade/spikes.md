# W0 spike results (X0.4)

**Session.** One cloud session on `research-assistant` at `main` 7418832,
2026-10-16, Claude Code 2.1.301, Ubuntu 24.04.5, 4 vCPU, 15 GB. The session
ran in Auto mode. This file records each of the eight spike items of
`PLAN.md` §4, X0.4: the command or action, what happened, and what it means
for the plan. Item 7 runs on the Mac.

**Headline.** The SessionStart hook ran and failed: the environment's network
policy denies `pypi.org` and `files.pythonhosted.org`, so the venv holds no
packages. Every result below that needs the venv is either unmeasured or was
taken with a named substitute. Items 3 to 6 and the subtree item do not need
the venv, and each has a full answer. The section "Rerun after the network
fix" records the same session after the network setting and PRs #3 and #4:
the setup builds, and the suite and the post-edit hook are timed.

## Item 8 and item 1, setup

### Item 8: the environment's setup script

| Attempt | What happened | Cause |
| --- | --- | --- |
| 1 | the setup script ran `bin/cloud-setup.sh` by a relative path and failed | the setup script does not run inside the repository |
| 2 | the setup script failed in a `find` | `find` exited non-zero under `set -o pipefail` |
| 3 | `uv pip sync` failed | no DNS for `pypi.org`: the setup script runs as root before Claude's network gateway starts |

Resolution, PR #1: the environment's setup script is now a single `echo`.
The SessionStart hook in `.claude/settings.json` runs
`bin/cloud-session-start.sh`, which runs `bin/cloud-setup.sh` until
`~/.research-vault/cloud-setup.done` exists.

**Unsettled.** The three attempts show that the setup script runs outside the
repository directory and without network. They do not show whether the clone
exists on disk when the setup script runs. That question no longer decides
anything, because the setup now runs from the SessionStart hook, after the
clone.

**Consequence for X0.2.** The sentence "the environment's setup script only
calls `bin/cloud-setup.sh` in the repo, so a PR can change the setup" does not
hold. Restate it as: the environment's setup script is an `echo`; the
SessionStart hook runs `bin/cloud-setup.sh`, so a PR changes the setup. The
fallback "you update the environment by hand at P14" is not needed: P14
changes `bin/cloud-setup.sh` by PR.

### Item 1: the session start, as observed

| Check | Command | Result |
| --- | --- | --- |
| SessionStart hook | the session transcript's hook record | ran; exit 1, reported as non-blocking; 4,851 ms |
| setup log | `cat ~/.research-vault/cloud-setup.log` | venv created at `/root/.research-vault/venv` with CPython 3.12.3; then `uv pip sync` failed: `Failed to fetch: https://pypi.org/simple/pikepdf/` … `dns error` … `Name or service not known` |
| user | `id`; `echo $HOME`; `pwd` | `uid=0(root)`; `/root`; `/home/user/research-assistant` |
| interpreter | `~/.research-vault/venv/bin/python -c "import vault"` | the interpreter exists (a symlink to `/usr/bin/python3.12`); `import vault` fails: `No module named 'vault'` on the bare path, `No module named 'yaml'` with `lib/` on the path |
| `machine.json` | `ls ~/.research-vault/machine.json` | absent: the setup stops before `point_at_empty_vault` |
| pandoc | `pandoc --version` | 3.1.3, the image's `/usr/bin/pandoc`; the setup never reached its pandoc 3.12 step |
| node | `node --version` | v22.22.0 |
| tiktoken cache | `ls ~/.research-vault/tiktoken` | absent |
| cloud flag | `echo $CLAUDE_CODE_REMOTE` | `true` |
| built mark | `ls ~/.research-vault/cloud-setup.done` | absent |

**Proxy variables (names only).** `HTTPS_PROXY`, `https_proxy`, `NO_PROXY`,
`no_proxy`, `GLOBAL_AGENT_HTTPS_PROXY`, `GLOBAL_AGENT_NO_PROXY`,
`DOCKER_HTTPS_PROXY`, `YARN_HTTPS_PROXY`, `npm_config_https_proxy`,
`npm_config_noproxy`, `ELECTRON_GET_USE_PROXY`, `CLOUDSDK_PROXY_ADDRESS`,
`CLOUDSDK_PROXY_PORT`, `CLOUDSDK_PROXY_TYPE`, `CCR_AGENT_PROXY_ENABLED`,
`CCR_UPSTREAM_PROXY_ENABLED`, `CCR_AGENT_PROXY_CA_WATCH_ENABLED`,
`CLAUDE_CODE_PROXY_RESOLVES_HOSTS`. CA variables: `SSL_CERT_FILE`,
`REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, `PIP_CERT`, `NODE_EXTRA_CA_CERTS`,
`GIT_SSL_CAINFO`, `AWS_CA_BUNDLE`, `CARGO_HTTP_CAINFO`, `DENO_CERT`,
`NIX_SSL_CERT_FILE`, `HEX_CACERTS_PATH`, `HTTPLIB2_CA_CERTS`,
`CLOUDSDK_CORE_CUSTOM_CA_CERTS_FILE`. No `HTTP_PROXY` is set.

**Reachability at session time**, by `curl` through the gateway:

| Host | Result |
| --- | --- |
| `pypi.org`, `files.pythonhosted.org` | denied: the gateway answers 403 to CONNECT; the direct route has no DNS |
| `registry.npmjs.org`, `astral.sh`, `archive.ubuntu.com`, `example.com` | denied (403 or no DNS) |
| `download.pytorch.org` | 200 |
| `openaipublic.blob.core.windows.net` | reachable (400 on the bare root) |
| `github.com`, its release assets (the pandoc 3.12 `.deb`) | reachable |

`NO_PROXY` lists `pypi.org` and `files.pythonhosted.org`, so `uv` bypasses the
gateway for them, and the container has no DNS of its own
(`CLAUDE_CODE_PROXY_RESOLVES_HOSTS=true`). Forced through the gateway, the same
hosts get 403. The two hosts X0.2 adds are allowed and the package-manager
hosts are not. The likely cause is that the environment's network setting
has custom allowed domains with the package-manager defaults left out. That
cause is an inference from the pattern of allowed hosts, and this session did
not read the setting itself. A uv cache of 425 MB exists in
`~/.cache/uv`; `uv pip sync --offline` cannot resolve from it
(`aiohappyeyeballs` absent).

**What a bare venv does to the hooks.** `cloud-setup.sh` deletes the venv,
creates it, and then fails in `uv pip sync`, so the venv exists with no
packages. The plan's sentence "without the venv at that exact path, every
hook exits 2 and blocks all Bash and Write" holds only for an absent venv.
With a bare venv:

| Hook | Imports | Effect |
| --- | --- | --- |
| `guard-bash`, `ensure-health-watcher` | standard library only | exit 0: Bash works |
| `guard-write` | `yaml` | `ModuleNotFoundError`: exit 2, so every Write call is blocked, the session scratchpad included |
| `checks-after-edit` | the venv's `ruff` | exit 2 after every Edit of a `.py` or `.md` file; the edit stays applied |
| `vault-rag` MCP server | the venv's packages | fails to connect |

The built mark is never written, so every session start retries the build,
nested headless runs included (each retry took about 5 s and deleted and
recreated the bare venv).

**Consequences.**

- X0.2: the environment `research` MUST allow `pypi.org` and
  `files.pythonhosted.org` (the package-manager defaults) beside
  `download.pytorch.org` and `openaipublic.blob.core.windows.net`. This is a
  change you make in the environment's network settings; no PR can make it.
  The rerun found two more hosts the build and the suite need; the rerun
  section lists the whole set.
- X0.2's "every hook exits 2" sentence: restate it for a bare venv (Bash
  works, Write is blocked, each Edit reports a hook error).
- `bin/cloud-setup.sh` leaves nothing usable after a failed sync. A later PR
  SHOULD order the steps that need no PyPI (`machine.json`, pandoc) before
  the sync, or build the venv in a temporary directory and move it into place
  only on success. This spike changes no file but this one, so the proposal
  is left for that PR (P14, or a fix PR before W1). Done in PR #3, which
  took the first option: the temporary-directory option would leave no
  interpreter after a first failed build, and every hook would then block
  Bash as well.
- Item 1 needs a rerun once the network allows PyPI: the build time, the
  pandoc version, and the tiktoken cache are unmeasured. Done: see the rerun
  section.

## Item 1, hooks and checks

| Check | Command | Result |
| --- | --- | --- |
| PreToolUse hooks run | every Bash call of the session; by hand, `echo '<event>' \| ~/.research-vault/venv/bin/python lib/harness_hooks.py guard-bash` | they run: each Bash call succeeded through `guard-bash` and `ensure-health-watcher`; each hook took 0.04 s by hand and exited 0 |
| full suite | `~/.research-vault/venv/bin/python -m unittest discover -s tests` | not measurable: the venv holds no packages |
| full suite, substitute | `python3 -m unittest discover -s tests` (system 3.12, which has `yaml` and lacks the rest) | 1,403 tests ran in 16.3 s (20 s wall); 525 errors, nearly all module-level import errors (`pymupdf` 436, `psutil` 36, `pikepdf` 19, `rapidfuzz` 13, `pylatexenc` 5); 554 test modules on disk. This is no timing of the suite. |
| linter | `~/.research-vault/venv/bin/ruff check .` | not runnable: the venv has no `ruff` |
| linter, substitute | `ruff check .` with `/root/.local/bin/ruff` 0.16.8, the version `requirements.lock` pins | `All checks passed!`, 0.1 s |
| audit linter | `~/.research-vault/venv/bin/python .claude/skills/vault-audit/scripts/audit.py lint` | not runnable: no `yaml` in the venv |
| audit linter, substitute | `python3 .claude/skills/vault-audit/scripts/audit.py lint`, after writing the empty-vault `machine.json` that `cloud-setup.sh` writes | exit 0, 2.5 s; `files`: instructions 51, code 1,065, control plane 1,131; `code` 35 (33 `more-than-three-arguments`, 1 `function-over-20-lines`, 1 `file-over-500-lines`); `pointers` 73, all `path-does-not-exist`, 51 of them vault paths absent from the empty vault; `works` 0 |
| post-edit hook | Edit `class PageCounts:` to `class PageCounts :` in `lib/page_counts.py`, then revert | the hook ran after both edits and blocked each with `the linter cannot run /root/.research-vault/venv/bin/ruff`; by hand it exits 2 in 0.05 s. The suite step never ran, so the hook's real time is unmeasured. The file is back to its committed state. |
| sandbox | `echo probe > /var/tmp/spike-sandbox-probe`; `touch .claude/skills/.spike-probe` | both writes succeeded: the sandbox is not enforced. A nested `claude -p` run prints the cause: `Sandbox disabled: sandbox is enabled but dependencies are missing: bubblewrap (bwrap) not installed, socat not installed`. Network limits come from the egress gateway, not from the sandbox's `allowedDomains`. |

**Consequences.**

- X1 holds and stays first. Its cost basis, the plan's "about 4,940 tests,
  single-process", is unmeasured here; measure the full suite in the first
  session whose venv builds. The rerun section measures it.
- The audit linter's 33 `more-than-three-arguments` findings match §1's count
  of 33 too-many-arguments findings.
- In the cloud the sandbox block of `.claude/settings.json` is inert, and
  `archive.ubuntu.com` is denied, so `bubblewrap` and `socat` cannot be
  installed under the current network setting. CLAUDE.md's "the sandbox
  denies Bash every write to `.claude/skills/`" does not hold in a cloud
  session. No cloud PR can verify a sandbox rule: G20's generated sandbox
  block and the cross-domain read guard need checks in `rehearsal.md`.

## Item 2, settings edits

| Action | Result |
| --- | --- |
| Edit tool: add `"spinnerTipsEnabled": true,` after `"autoMemoryEnabled": false,` in `.claude/settings.json` | allowed silently: no prompt, no denial |
| Edit tool: remove the same line | allowed silently |
| `git status --short` afterwards | clean; nothing committed |

**Consequence.** In Auto mode a cloud session may edit `.claude/settings.json`.
Settings changes can ship in the item PRs themselves, and the fallback
`upgrade/settings-patches/` is not needed. The result is for Auto mode; this
session did not test another permission mode. A nested headless run reports
`Ignoring 56 permissions.allow entries from .claude/settings.json: this
workspace has not been trusted`: a headless session in an untrusted checkout
does not apply the project's allow rules.

## Item 3, symlinked core files

**Setup.** Branch `spike/probes`, cut from `main` and pushed (commit 4e993a0,
never to be merged), adds:

| Probe | Real file | Symlink |
| --- | --- | --- |
| skill | `vendor/probe/skills/spike-probe/SKILL.md`, which says to reply `PROBE-SKILL-OK` | `.claude/skills/spike-probe` → `../../vendor/probe/skills/spike-probe` |
| agent | `vendor/probe/agents/spike-probe.md`, which replies `PROBE-AGENT-OK` | `.claude/agents/spike-probe.md` → `../../vendor/probe/agents/spike-probe.md` |
| workflow | `vendor/probe/workflows/spike-probe.js`, one agent that returns `PROBE-WORKFLOW-OK` | `.claude/workflows/spike-probe.js` → `../../vendor/probe/workflows/spike-probe.js` |

Git stores the three symlinks as mode `120000`.

**Test.** Three nested headless runs from the repository root, on
`spike/probes`, each `claude -p "<check>" --permission-mode
bypassPermissions`:

| Check | Output | Wall time |
| --- | --- | --- |
| is `spike-probe` in the skills list; invoke it with the Skill tool | `SKILL-LISTED=yes RESULT=PROBE-SKILL-OK` | 13.7 s |
| is `spike-probe` an agent type; dispatch it with the Agent tool | `AGENT-LISTED=yes RESULT=PROBE-AGENT-OK` | 15.5 s |
| is `spike-probe` a saved workflow; run it with the Workflow tool | `WORKFLOW-LISTED=yes RESULT="PROBE-WORKFLOW-OK"` | 20.8 s |

The running session also listed the `spike-probe` skill as soon as the
checkout switched to `spike/probes`.

**Consequence.** A0's symlink layout holds: skills, agents, and workflows load
through relative symlinks, and the generated copy checked by CI is not needed.
**Limits.** The nested runs shared this container and checkout and ran in an
untrusted workspace; a fresh cloud session started on `spike/probes` was not
run. macOS was not tested; git checks symlinks out there by default.

## Item 4, the Workflow tool

**Action.** A workflow of 8 parallel agents (`parallel` over 8 `agent` calls,
effort `low`), each making one Bash call `date +%s && sleep 20 && date +%s`.
The launch time was passed in as `args.t0`.

| Agents | Start, seconds after launch | End |
| --- | --- | --- |
| 0, 1 | 10, 12 | 30, 32 |
| 2, 3 | 38, 40 | 58, 60 |
| 4, 5 | 65, 67 | 85, 87 |
| 6, 7 | 93, 95 | 113, 115 |

Total wall time 113.3 s; 8 of 8 agents completed; 543,340 subagent tokens in
all, about 68,000 per agent for a one-command task. No `sleep` was refused.

**Result.** Two agents ran at once. The Workflow tool caps concurrent agents
at min(16, CPUs − 2), which is 2 on a 4-vCPU VM.

**Consequences for §4, the orchestration.**

- "3 refuters in parallel" runs as two, then one: the Verify phase takes two
  rounds of agent time.
- Each item's six agents run at most two at a time. One lane per cloud
  session still holds, and adding lanes inside one VM gains nothing.
- Each agent costs about 68,000 tokens before it does any work. Budget the
  item workflow on that overhead.

## Item 5, push and PR

| Action | Result |
| --- | --- |
| `git push -u origin spike/probes` | worked through the gateway |
| `git push -u origin claude/confident-knuth-0aiz8z` | worked |
| open the PR | the session opened this PR itself, with the GitHub MCP tool `create_pull_request`, base `main` |

`gh` is installed and `GH_TOKEN` is set, but the session's rules route GitHub
through the MCP tools, so `gh` was not tested.

**Consequence.** The plan's Publish phase holds: a cloud session pushes its
branch and opens its PR against `main` without you.

## Item 6, `git subtree` round trip

All of the following ran in `/tmp/spike-subtree`; nothing was pushed to
GitHub.

| Step | Command | Result |
| --- | --- | --- |
| installed | `git subtree --help` | git 2.43.0; `git subtree` present |
| core | a bare repo `core.git` with one commit `core v1` on `main` | made |
| add | in a throwaway clone of this repo: `git subtree add --prefix vendor/agent-core /tmp/spike-subtree/core.git main --squash` | worked, 0.20 s: a squash commit and a merge commit; `vendor/agent-core/README.md` reads `v1` |
| change | commit `core v2` to the core: changed `README.md`, added `CORE.md` | made |
| pull | `git subtree pull --prefix vendor/agent-core /tmp/spike-subtree/core.git main --squash` | worked, 0.23 s: `README.md` reads `v2`, `CORE.md` arrived |
| split | `git subtree split --prefix vendor/agent-core` | worked, 0.08 s; it printed af9ec92, the core's own `main` |

The session's global `push.negotiate=true` printed `fatal: expected
'acknowledgments', received 'packfile'` on the push to the local bare
repository, then pushed. The message is harmless on a file remote.

**Consequence.** A0's vendored subtree at `vendor/agent-core/` holds, and so
does the "pinned ref" update by `git subtree pull --squash`. `split` returns
the core's own commit, so changes made in a domain can be carried back to
`agent-core`.

## Item 7, the sandbox's read-deny setting

**Runs on the Mac.** This session did not test it. The cloud cannot test it:
its sandbox is not enforced (item 1).

## Summary

| Item | Result | Consequence for PLAN.md |
| --- | --- | --- |
| 8 setup script sees the repo | no | the setup script is an `echo`; the SessionStart hook runs `bin/cloud-setup.sh`; P14 changes the setup by PR, no hand update |
| 1 setup and hooks | partly | the hook runs, but the network denies PyPI: allow `pypi.org` and `files.pythonhosted.org` in `research`; a bare venv blocks Write; suite timing unmeasured; the sandbox is inert in the cloud, so sandbox checks go to `rehearsal.md` |
| 2 settings edits | works | edit `.claude/settings.json` in the PRs; no `settings-patches/` |
| 3 symlinked core files | works | A0's symlink layout holds; no generated copy |
| 4 Workflow tool | partly | runs; 2 agents at once on 4 vCPU; the 3 refuters take two rounds; about 68,000 tokens per agent |
| 5 push and PR | works | a cloud session publishes its own PRs against `main` |
| 6 `git subtree` | works | the vendored core and `subtree pull --squash` hold |
| 7 sandbox read-deny | runs on the Mac | — |
