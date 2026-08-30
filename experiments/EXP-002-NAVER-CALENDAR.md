# EXP-002 — Naver Calendar Adapter Portability

**Protocol:** Capability Bridge Protocol v0.1 — Core Freeze  
**Adapter:** `naver-calendar`  
**Status:** STARTED / awaiting live execution  
**Date:** 2026-08-30

---

## Research question

Can the frozen target-independent Protocol v0.1 support a second browser-driven service/action by adding only a new adapter and target-specific runtime logic?

This experiment changes the action semantics from the first reference experiment:

```text
EXP-001 Naver Mail
compose -> send -> observe completion
```

into:

```text
EXP-002 Naver Calendar
create object -> verify exact nonce -> delete object -> verify absence
```

The protocol core is not to be edited during the first attempt.

---

## Target choice

A Todoist task was considered first because task creation/deletion would provide a clean second action type. It was rejected as the primary EXP-002 target after current research showed that Todoist added an official ChatGPT app on 2026-08-28 and also provides an official MCP integration. That makes Todoist a weaker demonstration of the specific capability-gap story this experiment is intended to test.

Naver Calendar was selected instead because:

- its browser calendar surface is currently available;
- its mobile web UI exposes an `일정 추가` flow;
- the user already demonstrated a valid human-controlled Naver authentication path in EXP-001;
- calendar-event creation/deletion is materially different from mail sending;
- Naver publishes a Calendar API, but this experiment deliberately does not use it.

A pass here should be described narrowly as **cross-action / cross-service portability inside one authentication ecosystem**, not full cross-vendor portability.

---

## Test path

```text
Ordinary ChatGPT Chat
        |
        v
GitHub repository mutation
        |
        v
GitHub Actions ephemeral runner
        |
        v
Chrome + Selenium
        |
        v
Interactive human authentication handoff
        |
        v
Naver Calendar mobile web UI
        |
        v
Create nonce-bearing event
        |
        v
Observe exact nonce-bearing title
        |
        v
Delete event
        |
        v
Observe nonce absence
        |
        v
Protocol v0.1 Result Envelope
```

---

## Explicit exclusions

The experiment MUST NOT use:

- Naver Calendar API calls;
- Naver Calendar OAuth access tokens supplied to the adapter;
- a target-specific ChatGPT plugin/app/MCP in the test path;
- model-visible passwords, MFA secrets, login cookies, or recovery codes;
- a human performing the calendar mutation itself.

The human role is limited to authentication and direct security confirmation if the target requires it.

---

## Success criteria

PASS requires all of the following:

1. Protocol v0.1 remains unchanged during the attempt.
2. Interactive authentication completes without credentials entering Chat, repository content, or logs.
3. The adapter creates exactly one disposable event whose title contains the command nonce.
4. The target UI visibly exposes the exact created title after save.
5. The adapter deletes the created event through the browser UI.
6. The target UI no longer exposes the exact nonce-bearing event after cleanup.
7. A Result Envelope returns `VERIFIED_SUCCESS` for the original `command_id`.
8. No target-private page content is committed to the public repository.

---

## Failure classification

| Observation | Classification |
|---|---|
| Human cannot complete auth through the exposed browser | `AUTH_BOUNDARY` |
| GitHub runner/tunnel/browser cannot sustain the handoff | `SUBSTRATE_BOUNDARY` |
| Naver Calendar blocks safe browser automation | `TARGET_BOUNDARY` |
| Selector/UI mapping is wrong but core semantics remain sufficient | `ADAPTER_ERROR` |
| Mutation may have happened but nonce state is not provable | `VERIFY_FAILED` |
| A genuinely target-independent missing contract is demonstrated | `CORE_GAP` |

`CORE_GAP` is not a convenience classification. Target-specific UI friction must stay in the adapter.

---

## Privacy / diagnostics rule

Because the repository is public, the workflow must not upload screenshots or DOM dumps containing the user's private calendar. Diagnostics are limited to:

- synthetic command/result data;
- non-value form/control metadata;
- implementation traceback without credential/session values.

---

## Live command

The live run is triggered by `experiments/commands/exp002-naver-calendar.json`.

The command uses a unique nonce-bearing title and requests cleanup. The workflow exposes a temporary password-protected noVNC browser only for human login, then automation resumes without receiving the user's credentials.

---

## Result

Pending live execution.