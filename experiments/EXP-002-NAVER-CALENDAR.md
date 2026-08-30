# EXP-002 — Naver Calendar Adapter Portability

**Protocol:** Capability Bridge Protocol v0.1 — Core Freeze  
**Adapter:** `naver-calendar`  
**Status:** VERIFIED_SUCCESS  
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

Naver Calendar was selected as the second target because calendar-event creation/deletion is materially different from mail sending while still allowing a controlled browser-UI experiment.

Naver publishes a Calendar API, but this experiment deliberately did **not** use it. The execution path used no Naver Calendar ChatGPT app/plugin, MCP server, or Calendar API.

Because EXP-001 and EXP-002 both use Naver authentication, this experiment supports the narrow claim:

> **Cross-action / cross-service portability inside one Naver authentication ecosystem has been demonstrated.**

It does **not** yet demonstrate cross-vendor portability.

---

## Verified execution path

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
Navigate month card -> daily list -> actual schedule item
        |
        v
Open event detail / delete control
        |
        v
Confirm deletion
        |
        v
Reload calendar and verify exact-title absence
        |
        v
Protocol v0.1 Result Envelope: VERIFIED_SUCCESS
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

This pattern is verified only **within the lifetime of one GitHub-hosted runner**. It is not a claim of durable authentication across new hosted runners. For long-lived or IP-bound services, a stable self-hosted runner or persistent machine remains the stronger architecture.

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

After binding the adapter to the observed title textarea, the mutation attempt returned:

```json
{
  "created_title_observed": true
}
```

The exact synthetic event title was visible after calendar reload. The user also independently reported receiving the corresponding Naver Calendar notification, providing an additional target-external observation that the event had been registered by Naver.

### Daily-view duplicate-node diagnosis

The cleanup failure was not a deletion-permission problem. After opening the daily route, the exact synthetic title appeared multiple times because the page retained hidden/covered month-view copies while also rendering the actual daily list.

A structural diagnostic found **9 exact-title DOM matches**. Only matches inside:

```text
#daily_list_scroll_element
```

were the real daily-list item. The actual actionable structure was:

```text
li.schedule_item
  -> div.schedule_info
     -> strong.title
        -> span.text
```

Earlier cleanup attempts repeatedly selected covered month-view copies instead of the actual daily-list item.

### Delete confirmation diagnosis

Once the actual `li.schedule_item` was activated, the event detail route exposed:

```text
button.btn_floating_delete  -> 일정 삭제
button.btn_cancel           -> 취소
button.btn_confirm          -> 확인
```

The delete control alone did not complete cleanup. The explicit confirmation button had to be activated.

---

## Final result

Synthetic event:

```text
CB-EXP002-PERSIST-20260830-T4H7K9
```

Final cleanup command:

```text
exp002-persistent-confirm-delete-20260830-19
```

Final Result Envelope:

```json
{
  "status": "VERIFIED_SUCCESS",
  "failure_class": null,
  "execution": {
    "attempted": true,
    "completed": true
  },
  "verification": {
    "performed": true,
    "passed": true,
    "evidence": {
      "cleanup_absence_observed": true
    }
  },
  "cleanup": {
    "requested": true,
    "attempted": true,
    "completed": true
  }
}
```

Combined EXP-002 state:

```text
Authentication         PASS
Persistent session     PASS
Create mutation        PASS
Target observation     PASS
User notification      OBSERVED
Delete action          PASS
Absence verification   PASS
Core change            NONE
```

Therefore the original EXP-002 contract is satisfied:

```text
create -> observe -> delete -> verify absence
```

---

## Adapter-level lessons

The following failures were target-specific and remained outside Protocol v0.1:

- `일정 추가` launcher flow assumptions;
- Korean/English login-surface text differences;
- QR page lifetime/orchestration;
- Chrome ownership and retained-session mechanics;
- incorrect selection of `input_date` as the title control;
- duplicate hidden/covered exact-title nodes in the daily route;
- distinction between month-view event copies and the actual `li.schedule_item` inside `#daily_list_scroll_element`;
- explicit delete confirmation through `button.btn_confirm`.

These are adapter or execution-substrate implementation details, not evidence that the generic command/auth/result protocol is missing a concept.

---

## Core Freeze result

**Protocol v0.1 required no changes for EXP-002.**

The experiment fit the existing roles and contracts:

- capability discovery;
- capability-gap classification;
- human-controlled authentication;
- structured command envelope;
- structured result envelope;
- target-observable verification;
- reversible experiment / cleanup semantics;
- adapter-specific error classification.

No observed issue justified `CORE_GAP`.

---

## Privacy and security

The repository is public. The experiment avoided committing target-private calendar content, credentials, cookie values, MFA material, OAuth tokens, or private page dumps.

Safe diagnostics were limited to:

- synthetic test titles;
- control/tag/class/placeholder/action metadata;
- bounded structural metadata for the synthetic event element;
- machine-readable result state;
- implementation errors containing no credential/session values.

Authentication remained human-controlled.

---

## Portability significance

EXP-002 is stronger evidence than EXP-001 alone because the same frozen protocol and general execution substrate completed a second service with different mutation semantics:

```text
EXP-001 Mail:
compose -> send -> completion

EXP-002 Calendar:
create object -> observe exact identity -> delete object -> verify absence
```

This supports the hypothesis that Capability Bridge is not merely a mail-specific abstraction.

However, both targets still share Naver authentication. The next important research gate is:

> **EXP-003 — cross-vendor portability using a different service and authentication ecosystem.**

Full cross-vendor portability should not be claimed before that test.
