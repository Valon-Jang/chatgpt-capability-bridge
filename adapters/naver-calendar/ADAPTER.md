# Adapter 002 — Naver Calendar

**Adapter ID:** `naver-calendar`  
**Protocol target:** Capability Bridge Protocol v0.1 (Core Freeze)  
**Status:** EXP-002 candidate / experimental

This adapter tests whether the frozen generic Capability Bridge protocol can support a second browser-driven action without changing the protocol core.

The target-specific operation is deliberately different from Adapter 001: instead of sending mail, this adapter creates a harmless calendar event containing a unique nonce, verifies that event through the target UI, deletes it, and verifies cleanup.

---

## 1. Test boundary

EXP-002 uses:

- ordinary ChatGPT Chat as controller;
- GitHub as the already-permitted general-purpose execution substrate;
- GitHub Actions as an ephemeral bridge runtime;
- Chrome + Selenium for browser UI interaction;
- Naver Calendar mobile web UI as the target surface;
- human-controlled Naver authentication;
- no Naver Calendar ChatGPT plugin/app in the test path;
- no Naver Calendar API in the test path;
- no model-visible password, MFA secret, session cookie, or access token.

Naver publishes a Calendar API, but this adapter intentionally does not use it. The research question is whether browser capability composition alone satisfies Protocol v0.1.

---

## 2. Supported action

### `create_verify_delete_event`

Adapter arguments:

```json
{
  "title": "CB-EXP002-<nonce>",
  "cleanup": true
}
```

The event is intentionally disposable. The adapter SHOULD rely on target defaults for date/time unless a field is required to complete creation; the experiment is testing portability, not calendar scheduling semantics.

---

## 3. Authentication handoff

Authentication is target-specific and remains outside the generic core.

```text
Bridge opens Naver Calendar
        |
        v
If no authenticated Naver session exists
        |
        v
AUTH_REQUIRED
        |
        v
Human uses interactive remote browser to log in directly
        |
        v
Adapter observes authenticated browser state
        |
        v
Automation resumes
```

The runner may inspect cookie *names* or target-visible authenticated UI state to decide that login completed, but MUST NOT print cookie values or session material.

---

## 4. Action mapping

For `create_verify_delete_event`, the adapter attempts to:

1. reach Naver Calendar mobile web UI;
2. wait for human authentication if required;
3. open the target's `일정 추가` flow;
4. enter the nonce-bearing test title;
5. save the event through the browser UI;
6. verify that the exact title is observable in the target UI;
7. open the created event;
8. delete it through the browser UI;
9. verify that the nonce-bearing event is no longer observable;
10. emit a Protocol v0.1 Result Envelope.

A Selenium process exit code alone is not sufficient for `VERIFIED_SUCCESS`.

---

## 5. Verification contract

The experiment requires two target-observable checks:

### Creation verification

The exact nonce-bearing title must be observable after save.

### Cleanup verification

After deletion, the exact title must no longer be observable in the relevant calendar view.

A complete passing result therefore requires:

```json
{
  "status": "VERIFIED_SUCCESS",
  "execution": {
    "attempted": true,
    "completed": true
  },
  "verification": {
    "performed": true,
    "passed": true,
    "evidence": {
      "created_title_observed": true,
      "cleanup_absence_observed": true
    }
  }
}
```

If creation is observed but cleanup fails, the experiment MUST report partial/failed cleanup rather than hide the residual test event.

---

## 6. Failure mapping

- Login cannot complete through the interactive handoff → `AUTH_BOUNDARY`.
- GitHub-hosted runner cannot expose or sustain the interactive browser → `SUBSTRATE_BOUNDARY`.
- Calendar UI blocks automated interaction or offers no safe browser path → `TARGET_BOUNDARY`.
- Selectors or UI assumptions fail while the protocol remains sufficient → `ADAPTER_ERROR`.
- Mutation may have happened but nonce state cannot be proven → `VERIFY_FAILED`.
- Only a genuinely target-independent missing contract may be classified as `CORE_GAP`.

The frozen Protocol v0.1 MUST NOT be edited merely to make this adapter easier to implement.

---

## 7. Portability significance

This test changes action semantics from:

```text
Adapter 001: compose -> send -> observe send completion
```

to:

```text
Adapter 002: create object -> verify identity -> delete object -> verify absence
```

A pass without protocol changes would provide stronger evidence that the protocol is not merely a mail-specific abstraction.

Because both adapters currently target Naver services, a pass would primarily demonstrate **cross-action / cross-service portability inside one authentication ecosystem**, not full cross-vendor portability. A later experiment should use a different vendor and authentication environment.