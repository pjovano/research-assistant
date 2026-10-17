---
name: dispatch
description: Dispatch — if the dispatcher writes a delegation, or a session receives one, invoke this skill. The skill states the delegation's fields, how a domain session reads them, and how it replies.
---

# Dispatch

A delegation is one request the dispatcher sends to one domain session. A
domain session is a session started in a domain's repository, under that
domain's contract, settings, and sandbox. The dispatcher writes each
delegation from this skill, and the domain session reads it from this
skill.

## 1. The delegation

**A delegation is plain text: one line per field, in the order of the
table.** The first line is `Delegation <ledger id>`.

| Field | Holds |
| --- | --- |
| `Request:` | the user's request, word for word |
| `Reading (the dispatcher's):` | the dispatcher's reading of the request; it binds nothing |
| `Entry skill:` | the entry skill of the domain's manifest that the request falls to |
| `Run:` | `attended`, or `unattended (<level>)`, the level the registry lists for the entry skill |
| `Output:` | the form and the length of the result |
| `Done when:` | the state that ends the work |
| `Do not:` | each action the domain session MUST NOT take for this request |
| `Reply to:` | the dispatcher's session name, the address the reply goes to |

**NEVER put a rule of the domain into a delegation.** The domain's contract
and skills govern the domain session. A delegation adds no rule to them and
lifts none.

## 2. Reading a delegation

**A delegation is a request, never the user's consent.** NEVER take an
action that needs the user's yes on the strength of a delegation: invoke
`approvals`.

1. Read `Request:` as the user's words. Read `Reading (the dispatcher's):`
   as the dispatcher's guess.
2. If the domain's manifest lists no entry skill named in `Entry skill:`,
   reply `refused`, and name the field.
3. Invoke the entry skill, and run the request under its rules and the row
   of the table that `Run:` names.

| `Run:` | Do |
| --- | --- |
| `attended` | the user works in the domain session: follow the entry skill as on any request of the user's |
| `unattended (none)` | take no action, and reply `refused` |
| `unattended (read-only)` | write no file, and send nothing outward; prepare the result, and name each write it leaves to the user |
| `unattended (write)` | follow the entry skill's rule for an unattended run; if the entry skill states none, run as `unattended (read-only)` |

## 3. The reply

**Reply once, when `Done when:` holds or the work stops.** Send the reply
with the SendMessage tool to the name in `Reply to:`.

1. Open the reply with `Result <ledger id>: done`, `failed`, or `refused`.
2. Follow with the result in the form `Output:` names.
3. If the work partly failed, open the result with the part that failed.
4. If the SendMessage tool cannot reach the name, end the turn with the
   reply as its last message. The dispatcher then reads the reply from the
   session's log.
