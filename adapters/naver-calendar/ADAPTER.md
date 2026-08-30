# Adapter 002 — Naver Calendar

**Adapter ID:** `naver-calendar`  
**Protocol target:** Capability Bridge Protocol v0.1 (Core Freeze)  
**Status:** ACTION VERIFIED / CLEANUP PATH EXPERIMENTAL

This adapter demonstrates that the frozen Capability Bridge core can drive a second browser-based service/action without introducing target-specific concepts into the protocol core.

The verified mutation is Naver Calendar event creation through the mobile web UI. Full create/verify/delete/absence completion remains pending because the deletion navigation is still being mapped.

---

## 1. Test boundary

The adapter uses:

- ordinary ChatGPT Chat as controller;
- GitHub as a general-purpose execution substrate;
- GitHub Actions as the hosted runtime;
- Chrome + Selenium for browser UI interaction;
- Naver Calendar mobile web UI as the target surface;
- human-controlled Naver authentication;
- no Naver Calendar ChatGPT plugin/app in the execution path;
- no Naver Calendar MCP server in the execution path;
- no Naver Calendar API in the execution path;
- no model-visible password, MFA secret, raw session cookie, OAuth token, or recovery code.

Naver publishes a Calendar API, but this adapter intentionally does not use it.

---

## 2. Supported actions

### `create_verify_delete_event`

Arguments:

```json
{
  "title": "CB-EXP002-<nonce>",
  "cleanup": true
}
```

Current behavior:

```text
authenticated calendar
   -> open schedule-writing surface
   -> fill confirmed title textarea
   -> save
   -> reload calendar
   -> observe exact synthetic title
   -> attempt cleanup
   -> return structured result
```

Creation and exact-title observation are verified. Cleanup remains experimental until event-card/detail navigation and deletion are target-observably verified.

### `recover_verify_delete_event`

Used only for safe cleanup/recovery of a known synthetic title from an earlier attempt.

It must not create a new event. It checks whether the exact title remains observable and, when possible, deletes it and verifies absence.

### Diagnostic actions

The persistent adapter may use non-mutating diagnostic actions such as:

- `diagnose_schedule_form`
- `diagnose_event_detail`

Diagnostics must expose only safe structural metadata and must not return field values, private calendar text, passwords, cookie values, or session tokens.

---

## 3. Authentication handoff

The current verified pattern is QR-based one-time human authentication into a Chrome process retained by the workflow.

```text
Start persistent Chrome
        |
        v
Open Naver QR login
        |
        v
Publish short-lived QR handoff
        |
        v
Human scans/confirms in Naver app
        |
        v
Wait until authenticated state is detected
        |
        v
Only then start adapter commands
```

The important ordering constraint is:

> **Do not navigate away from the QR login page until authentication has been detected.**

Earlier orchestration that started commands before authentication completion invalidated the QR handoff.

---

## 4. Retained browser session

Chrome is owned by the persistent-session workflow, not by each individual adapter command.

Adapters attach through Chrome remote debugging, execute one command, then return **without calling `driver.quit()`**.

This enables:

```text
human auth once
   -> command attempt
   -> adapter failure
   -> patch target-specific code
   -> next command
   -> same authenticated browser
```

The pattern is only guaranteed inside the lifetime of the same hosted runner. It does not imply authenticated-session portability to a new runner/IP.

---

## 5. Verified schedule-writing mapping

The live mobile schedule-writing page was observed at:

```text
https://m.calendar.naver.com/add
```

The actual schedule title control is:

```css
textarea[placeholder="일정을 입력하세요."]
```

Observed structural metadata:

```text
tag: textarea
class: input_textarea
placeholder: 일정을 입력하세요.
```

The visible save action is:

```text
저장
```

A previous heuristic incorrectly selected:

```text
input.input_date
```

That failure produced save attempts without real event creation. The adapter must prefer the confirmed title textarea and must not fall back to arbitrary text/date inputs when the Naver Calendar `/add` structure is available.

---

## 6. Creation verification

Creation is verified from the calendar surface after save, not merely from the post-save route or process exit code.

Required evidence for a verified mutation:

```json
{
  "execution": {
    "attempted": true,
    "completed": true
  },
  "verification": {
    "performed": true,
    "evidence": {
      "created_title_observed": true
    }
  }
}
```

The live experiment reached `created_title_observed: true` for a nonce-bearing synthetic event after calendar reload.

The human also reported receiving the corresponding Naver Calendar notification, which is useful external corroboration but is not a substitute for machine-readable target observation.

---

## 7. Cleanup contract

The target experiment ultimately requires:

```text
open exact synthetic event
   -> reach edit/detail action
   -> delete through visible browser UI
   -> return to calendar
   -> verify exact title absence
```

A complete pass requires:

```json
{
  "status": "VERIFIED_SUCCESS",
  "verification": {
    "performed": true,
    "passed": true,
    "evidence": {
      "created_title_observed": true,
      "cleanup_absence_observed": true
    }
  },
  "cleanup": {
    "attempted": true,
    "completed": true
  }
}
```

Current live state: the synthetic event is observable, but automated event-card/detail navigation has not yet reliably reached the deletion control. Therefore cleanup must remain explicitly pending rather than being inferred.

---

## 8. Failure mapping

- Human cannot complete authentication → `AUTH_BOUNDARY`.
- Hosted browser/session cannot be sustained → `SUBSTRATE_BOUNDARY`.
- Naver prevents a safe browser-UI path → `TARGET_BOUNDARY`.
- Target selectors, routing, or event-card behavior are wrong → `ADAPTER_ERROR`.
- A mutation may have happened but target state cannot be proven → `VERIFY_FAILED`.
- Only a genuinely target-independent missing contract may be classified as `CORE_GAP`.

The observed EXP-002 failures were adapter/session-orchestration failures. None justified changing Protocol v0.1.

---

## 9. Privacy rule

Because the repository is public, diagnostics must not upload or commit:

- passwords or MFA data;
- cookie/session values;
- OAuth tokens;
- screenshots of private calendar content;
- full private DOM/page dumps;
- unrelated calendar event text.

Safe structural diagnostics may include:

- element tag/type;
- class/id;
- placeholder;
- aria-label/title;
- fixed target UI action labels;
- synthetic nonce-bearing titles;
- machine-readable result state.

---

## 10. Portability significance

Adapter 001 and Adapter 002 now cover materially different action semantics:

```text
Adapter 001 — Naver Mail
compose -> send -> observe completion

Adapter 002 — Naver Calendar
create object -> observe exact identity -> cleanup workflow
```

The Naver Calendar mutation was achieved without changing the frozen generic protocol.

This supports **cross-action / cross-service portability within the Naver authentication ecosystem**. It does not yet prove cross-vendor portability. EXP-003 should use a different vendor and authentication environment.