# P7a — Slice 7a: the `Vault` value object and its shim

| Field | Value |
| --- | --- |
| Status | deferred |
| Wave, lane | W6: not in this round |
| Repo | `research-assistant` |
| Depends on | P6+M4, P4, P10 |
| Detail | `sources/hexagonal-ports-plan.md` §1 (paths row), §3.1 (Locations), §4 PR 7 step 7a, §5 row P7; `PLAN.md` §1 "Hexagonal ports plan" (65 modules, 92 test files; each slice merges promptly) |
| Trailer | `Change-class: refactor — <what>` |

**Deferred after W0.** The ports plan is cut to the Mac's part (`PLAN.md` §1, "Hexagonal ports plan"). The item workflow MUST NOT build this item; the text below is kept for a later round and predates the cut.

## Builds

Every path `_vault/paths.py` names today becomes a field of a `Vault` value object, built by `providers` from `Locations`. The module-level constants stay, defined from a default `Vault`, as a shim, so no caller changes.

The slice is mechanical and merges promptly: W4 lanes rebase onto it. Count the slice's modules that read a constant `_vault/paths.py` defines, before and after, and state both counts in the PR body. `Locations`' research defaults MUST name `library` and `research vault` under `~/Documents`, the folders the research `domain.json` lists (G20).

## Acceptance

| Row | Checked by |
| --- | --- |
| The `Vault` built from today's `machine.json` names every path the constants name today | CI: a test comparing every constant with its `Vault` field |
| Every path resolves on the primary as the old constants do | Rehearsal: R-P7a-1 |
| The suite passes unchanged | CI |

## Open questions

None known.
