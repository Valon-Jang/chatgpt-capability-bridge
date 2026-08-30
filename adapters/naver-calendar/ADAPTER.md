# Adapter 002 — Naver Calendar

**Adapter ID:** `naver-calendar`  
**Protocol target:** Capability Bridge Protocol v0.1 (Core Freeze)  
**Status:** VERIFIED_SUCCESS

This adapter demonstrates that the frozen Capability Bridge core can drive a second browser-based service/action without introducing target-specific concepts into the protocol core.

The verified operation is a full reversible mutation through Naver Calendar mobile web UI:

```text
create -> observe -> delete -> verify absence
```

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

## 2. Supported experiment action

### `create_verify_delete_event`

Arguments:

```json
{
  "title": "CB-EXP002-<nonce>",
  "cleanup": true
}
```

Verified behavior:

```text
authenticated calendar
   -> open schedule-writing surface
   -> fill confirmed title textarea
   -> save
   -> reload calendar
   -> observe exact synthetic title
   -> open actual daily-list schedule item
   -> activate delete control
   -> confirm deletion
   -> reload calendar
   -> verify exact-title absence
   -> return VERIFIED_SUCCESS
```

### Recovery / diagnostic actions

During the live experiment, temporary recovery and non-mutating diagnostic actions were used to map target-specific DOM behavior. They are implementation/research helpers, not new protocol concepts.

Diagnostics expose only safe structural metadata and never field values, private calendar text, passwords, cookie values, or session tokens.

---

## 3. Authentication handoff

The verified pattern is QR-based one-time human authentication into a Chrome process retained by the workflow.

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

Ordering rule:

> **Do not navigate away from the QR login page until authentication has been detected.**

The human authenticates; the bridge acts through the authenticated state.

---

## 4. Retained browser session

Chrome is owned by the persistent-session workflow, not by each individual adapter command.

Adapters attach through Chrome remote debugging, execute one command, then return without closing the browser.

This produced the observed pattern:

```text
human auth once
   -> command attempt
   -> adapter failure
   -> patch target-specific code
   -> next command
   -> same authenticated browser
```

This pattern is verified only inside the lifetime of the same hosted runner. It does not imply authenticated-session portability to a new runner/IP.

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

The adapter must prefer the confirmed title textarea and must not fall back to arbitrary date/text inputs on the `/add` surface.

---

## 6. Creation verification

Creation must be verified from the target calendar surface after save, not from a process exit code or post-save route.

The live experiment reached:

```json
{
  "created_title_observed": true
}
```

for a nonce-bearing synthetic event after calendar reload.

The user also reported receiving the corresponding Naver Calendar notification. That external notification is useful corroboration but is not a substitute for machine-readable target observation.

---

## 7. Daily-view node selection

A major cleanup bug came from assuming every exact-title DOM match represented the same clickable event.

After switching to the daily route, the synthetic title appeared **9 times** in the DOM. Hidden/covered month-view copies remained present while the actual daily list was rendered above them.

Only elements contained within:

```css
#daily_list_scroll_element
```

were actionable daily-list entries.

The verified actionable structure was:

```text
li.schedule_item
  -> div.schedule_info
     -> strong.title
        -> span.text
```

The adapter must therefore scope cleanup/event-detail navigation to the actual daily-list container instead of selecting the first exact-title match globally.

---

## 8. Verified deletion mapping

Once the actual `li.schedule_item` was opened, the detail/delete flow exposed:

```text
button.btn_floating_delete  -> 일정 삭제
button.btn_cancel           -> 취소
button.btn_confirm          -> 확인
```

Deletion was not complete after activating `btn_floating_delete`; the explicit `button.btn_confirm` confirmation was required.

Final verified cleanup sequence:

```text
month event copy
   -> daily route
   -> actual li.schedule_item inside #daily_list_scroll_element
   -> event detail
   -> button.btn_floating_delete
   -> button.btn_confirm
   -> calendar reload
   -> exact title absent
```

Final Result Envelope evidence:

```json
{
  "status": "VERIFIED_SUCCESS",
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

---

## 9. Failure mapping

- Human cannot complete authentication → `AUTH_BOUNDARY`.
- Hosted browser/session cannot be sustained → `SUBSTRATE_BOUNDARY`.
- Naver prevents a safe browser-UI path → `TARGET_BOUNDARY`.
- Target selectors, routing, duplicate nodes, or event-card behavior are wrong → `ADAPTER_ERROR`.
- A mutation may have happened but target state cannot be proven → `VERIFY_FAILED`.
- Only a genuinely target-independent missing contract may be classified as `CORE_GAP`.

All observed EXP-002 implementation failures were adapter/session-orchestration failures. None justified changing Protocol v0.1.

---

## 10. Privacy rule

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
- bounded geometry/containment metadata needed to distinguish duplicate synthetic nodes;
- machine-readable result state.

---

## 11. Portability significance

Adapter 001 and Adapter 002 now cover materially different action semantics:

```text
Adapter 001 — Naver Mail
compose -> send -> observe completion

Adapter 002 — Naver Calendar
create object -> observe exact identity -> delete object -> verify absence
```

Naver Calendar completed the full reversible contract without changing the frozen generic protocol.

This supports **cross-action / cross-service portability within the Naver authentication ecosystem**. It does not yet prove cross-vendor portability.

The next gate is:

> **EXP-003 — a different vendor and authentication ecosystem.**
