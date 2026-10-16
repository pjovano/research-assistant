# P7f — Slice 7f: `_writing`, `annotate-pdfs`, `transcribe-talks`, and the rest take a `Vault`

| Field | Value |
| --- | --- |
| Status | deferred |
| Wave, lane | W6: not in this round |
| Repo | `research-assistant` |
| Depends on | P7e |
| Detail | `sources/hexagonal-ports-plan.md` §1 (paths row), §3.1 (Locations), §4 PR 7 step 7f, §5 row P7; `PLAN.md` §1 "Hexagonal ports plan" (65 modules, 92 test files; each slice merges promptly) |
| Trailer | `Change-class: refactor — <what>` |

**The item workflow MUST NOT build this item.** It is deferred: `PLAN.md` §3,
"Deferred", names the need it waits for. It runs only if the user says so.

## Builds

Every remaining module that reads a path constant takes a `Vault`: `lib/_writing`, `annotate-pdfs`, `transcribe-talks`, and the rest, so that only the shim names the constants.

The slice is mechanical and merges promptly: W4 lanes rebase onto it. Count the slice's modules that read a constant `_vault/paths.py` defines, before and after, and state both counts in the PR body. `Locations`' research defaults MUST name `library` and `research vault` under `~/Documents`, the folders the research `domain.json` lists (G20).

## Acceptance

| Row | Checked by |
| --- | --- |
| Only the shim names a path constant outside the tests | CI: a `git grep` test over `lib/` and the skills |
| The suite passes unchanged | CI |

## Open questions

None known.
