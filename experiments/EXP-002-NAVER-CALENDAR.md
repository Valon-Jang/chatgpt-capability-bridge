# EXP-002 — Naver Calendar Adapter Portability

**Protocol:** Capability Bridge Protocol v0.1 — Core Freeze  
**Adapter:** `naver-calendar`  
**Status:** ACTION VERIFIED / CLEANUP PENDING  
**Date:** 2026-08-30

---

## Research question

Can frozen, target-independent Protocol v0.1 support a second browser-driven service/action by adding only a target adapter and target-specific runtime logic?

EXP-001 used Naver Mail:

```text
compose -> send -> observe completion
```

EXP-002 changes the action semantics to:

```text
create object -> verify exact nonce -> delete object -> verify absence
```

Protocol v0.1 remained frozen throughout the experiment. No `CORE_GAP` was demonstrated.

---

## Target and scope

Naver Calendar was selected as the second target because calendar-event creation is materially different from mail sending while still allowing a controlled browser-UI experiment.

Naver publishes a Calendar API, but this experiment deliberately did **not** use it. The execution path used no Naver Calendar ChatGPT app/plugin, MCP server, or Calendar API.

Because EXP-001 and EXP-002 both use Naver authentication, this experiment can support only the narrow claim:

> **Cross-action / cross-service portability inside one Naver authentication ecosystem has been demonstrated at the action-mutation level.**

It does **not** yet demonstrate cross-vendor portability.

---

## Execution path

```text
Ordinary ChatGPT Chat
        |
        v
GitHub repository command/state channel
        |
        v
GitHub Actions hosted runner
        |
        v
Persistent Chrome process + Selenium attachment
        |
        v
One-time human QR authentication
        |
        v
Authenticated Naver Calendar mobile web UI
        |
        v
Create nonce-bearing synthetic event
        |
        v
Reload calendar and observe exact title
        |
        v
Cleanup attempt
        |
        v
Protocol v0.1 Result Envelope
```

The browser process was retained after adapter success/failure so target-specific code could be patched and re-run without asking the human to authenticate again during the same hosted-runner lifetime.

---

## Authentication result

Human authentication handoff passed.

The final persistent-session flow enforced this order:

```text
Generate QR
   -> keep QR page open
   -> human scans and confirms
   -> detect authenticated Naver state
   -> only then begin adapter commands
```

The adapter did not receive or log the user's password, MFA secret, raw cookie values, OAuth token, or recovery material.

The authenticated Chrome session remained alive across multiple adapter diagnostics and command retries.

### Persistent Authentication Pattern observed

```text
Human auth once
   -> retain browser process/session
   -> hot-load latest adapter code
   -> execute command
   -> adapter may succeed or fail
   -> keep browser alive
   -> patch adapter
   -> execute next command without re-authentication
```

This pattern is verified only **within the lifetime of one GitHub-hosted runner**. It is not a claim of durable authentication across new hosted runners. GitHub-hosted jobs also have a platform lifetime limit, so a self-hosted persistent runner remains the stronger candidate for long-lived production use.

---

## Live findings

### Attempt 1 — authentication passed, form mapping failed

The initial live run completed human login successfully and emitted `AUTHENTICATED`, but failed with:

```text
ADAPTER_ERROR: Could not identify a visible event-title input.
```

This was correctly classified as adapter/UI mapping failure, not `AUTH_BOUNDARY` and not `CORE_GAP`.

### Form-entry routing bug

Naver Calendar mobile UI uses a multi-step add flow. Opening `일정 추가` alone did not guarantee that the schedule-writing form had been entered. The adapter was updated to follow the target-specific launcher flow and inspect the resulting form structurally.

### Persistent-session orchestration bugs

During development, two session-level mistakes were found and corrected:

1. a QR handoff could be invalidated if the command worker navigated away before authentication completed;
2. a one-shot adapter process could close Chrome and force repeated authentication.

The final session design keeps Chrome owned by the workflow, waits for authentication before command execution, and lets adapters attach/detach without quitting the browser.

### Title selector diagnosis

A non-mutating diagnostic captured safe control metadata from `https://m.calendar.naver.com/add`.

It proved that the heuristic selector had chosen the wrong field:

```text
wrong candidate: input.input_date
```

The actual event-title control was observed as:

```text
textarea[placeholder="일정을 입력하세요."]
```

The save action was a visible `저장` button.

After binding the adapter to the observed title textarea, the next mutation attempt returned:

```json
{
  "created_title_observed": true
}
```

The exact synthetic event title was visible after calendar reload.

The user also independently reported receiving the resulting Naver Calendar notification, providing an additional target-external observation that the event had actually been registered by Naver.

### Creation result

**Calendar event creation is verified.**

Verified evidence:

- one-time QR authentication succeeded;
- the authenticated Chrome session was retained;
- the adapter reached the schedule-writing surface;
- the confirmed title textarea received the synthetic nonce-bearing title;
- the target save action executed;
- the exact nonce-bearing event title was observable after returning to the calendar;
- the user's Naver client produced the corresponding calendar notification.

This establishes a real target mutation, not merely a successful script exit.

---

## Cleanup state

Cleanup is **not yet verified**.

The current residual synthetic event is:

```text
CB-EXP002-PERSIST-20260830-T4H7K9
```

The adapter can observe the event, but the current automated event-card/detail navigation has not yet reached the mobile-web deletion control reliably.

Latest cleanup result:

```text
ADAPTER_ERROR: Synthetic event was visible but its detail card could not be opened.
```

Therefore this document intentionally does **not** claim full `VERIFIED_SUCCESS` for the original create/verify/delete/absence contract yet.

Current experiment state is:

```text
Authentication       PASS
Persistent session   PASS
Create mutation      PASS
Target observation   PASS
External notification observed
Cleanup              PENDING
Core change          NONE
```

Once the same synthetic event is deleted through the browser UI and absence is verified, the experiment may be promoted from `ACTION VERIFIED / CLEANUP PENDING` to `VERIFIED_SUCCESS`.

---

## Adapter-level lessons

The following failures were target-specific and must remain outside Protocol v0.1:

- `일정 추가` launcher flow assumptions;
- Korean/English login-surface text differences;
- QR page lifetime/orchestration;
- Chrome ownership and retained-session mechanics;
- incorrect selection of `input_date` as the title control;
- event-card/detail click behavior;
- target-specific deletion navigation.

These are adapter or execution-substrate implementation details, not evidence that the generic command/auth/result protocol is missing a concept.

---

## Core Freeze result

**No Protocol v0.1 changes were required to reach a verified Naver Calendar mutation.**

The experiment continued to fit the existing roles and contracts:

- capability discovery;
- capability gap classification;
- human-controlled authentication;
- structured command envelope;
- structured result envelope;
- target-observable verification;
- adapter-specific error classification.

No issue observed so far justifies `CORE_GAP`.

---

## Privacy and security

The repository is public. The experiment therefore avoided committing target-private calendar content, credentials, cookie values, MFA material, OAuth tokens, or private page dumps.

Safe diagnostics were limited to:

- synthetic test titles;
- control/tag/class/placeholder/action metadata;
- machine-readable result state;
- implementation errors that contain no credential/session values.

Authentication remained human-controlled.

---

## Portability significance

EXP-002 is stronger evidence than EXP-001 alone because the same frozen protocol and general execution substrate reached a second service with different mutation semantics:

```text
EXP-001 Mail:
compose -> send -> completion

EXP-002 Calendar:
create object -> observe exact identity -> cleanup workflow
```

The result supports the hypothesis that Capability Bridge is not merely a mail-specific abstraction.

However, because both targets share Naver authentication, the next important research gate should be:

> **EXP-003 — cross-vendor portability using a different service and authentication ecosystem.**

Full portability should not be claimed before that test.