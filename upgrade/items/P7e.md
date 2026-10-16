# P7e — Slice 7e: `_rag`, `_graph`, and `search` take a `Vault`

| Field | Value |
| --- | --- |
| Status | planned |
| Wave, lane | W3-b: P7a → … → P7f → P7h |
| Repo | `research-assistant` |
| Depends on | P7d |
| Detail | `sources/hexagonal-ports-plan.md` §1 (paths row), §3.1 (Locations), §4 PR 7 step 7e, §5 row P7; `PLAN.md` §1 "Hexagonal ports plan" (65 modules, 92 test files; each slice merges promptly) |
| Trailer | `Change-class: refactor — <what>` |

## Builds

The modules of `lib/_rag`, `lib/_graph`, and the `search` skill take a `Vault` in place of the path constants.

The slice is mechanical and merges promptly: W4 lanes rebase onto it. Count the slice's modules that read a constant `_vault/paths.py` defines, before and after, and state both counts in the PR body. `Locations`' research defaults MUST name `library` and `research vault` under `~/Documents`, the folders the research `domain.json` lists (G20).

## Acceptance

| Row | Checked by |
| --- | --- |
| No module of the slice reads a path constant | CI: a `git grep` test over the slice |
| The suite passes unchanged | CI |

## Open questions

None known.
