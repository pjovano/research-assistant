# P7d — Slice 7d: `classify-and-place` and `cite-links` take a `Vault`

| Field | Value |
| --- | --- |
| Status | deferred |
| Wave, lane | W6: not in this round |
| Repo | `research-assistant` |
| Depends on | P7c |
| Detail | `sources/hexagonal-ports-plan.md` §1 (paths row), §3.1 (Locations), §4 PR 7 step 7d, §5 row P7; `PLAN.md` §1 "Hexagonal ports plan" (65 modules, 92 test files; each slice merges promptly) |
| Trailer | `Change-class: refactor — <what>` |

**Deferred after W0.** The ports plan is cut to the Mac's part (`PLAN.md` §1, "Hexagonal ports plan"). The item workflow MUST NOT build this item; the text below is kept for a later round and predates the cut.

## Builds

The modules of `classify-and-place` and `cite-links` take a `Vault` in place of the path constants.

The slice is mechanical and merges promptly: W4 lanes rebase onto it. Count the slice's modules that read a constant `_vault/paths.py` defines, before and after, and state both counts in the PR body. `Locations`' research defaults MUST name `library` and `research vault` under `~/Documents`, the folders the research `domain.json` lists (G20).

## Acceptance

| Row | Checked by |
| --- | --- |
| No module of the slice reads a path constant | CI: a `git grep` test over the slice |
| The suite passes unchanged | CI |

## Open questions

None known.
