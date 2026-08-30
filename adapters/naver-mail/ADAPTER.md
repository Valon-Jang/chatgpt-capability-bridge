# Adapter 001 — Naver Mail

**Adapter ID:** `naver-mail`  
**Protocol target:** Capability Bridge Protocol v0.1  
**Status:** Reference adapter / experimental

This document separates the target-specific behavior of the first reference implementation from the generic Capability Bridge core.

Anything in this document that is specific to Naver Mail, its UI, authentication behavior, session behavior, mail fields, or completion signals is **adapter logic**, not a requirement of the generic protocol.

---

## 1. Historically verified observations

The first reference experiment established the following:

- ordinary ChatGPT Chat acted as the control surface;
- no Naver Mail-specific ChatGPT plugin was used in the test path;
- no Naver Mail API was used;
- a general-purpose execution substrate was used to create an external browser execution environment;
- Chrome + Selenium performed the target browser interaction;
- the user authenticated directly rather than providing login credentials to the model;
- QR-code authentication was used in the successful reference flow;
- an interactive login-screen handoff was also explored as a more general handoff pattern;
- after authentication, a structured command drove mail composition and sending;
- a real test email was sent successfully;
- the target's post-send completion state was detected and returned as verification;
- encrypted browser-state transfer between rotating hosted runners was technically possible, but Naver's IP-security behavior required reauthentication after the network identity changed.

These observations describe the reference implementation. They do not become generic protocol requirements.

---

## 2. Supported action

### `send_mail`

Candidate adapter arguments for Protocol v0.1:

```json
{
  "recipient": "<address>",
  "subject": "<subject>",
  "body": "<body>"
}
```

The generic `command_id`, `nonce`, verification request, and experiment metadata remain in the Command Envelope rather than being duplicated here.

The exact browser selectors and target interaction sequence are implementation details and are intentionally not part of the generic protocol contract.

---

## 3. Authentication handoff

### Verified path: QR handoff

```text
Adapter reaches sign-in state
        |
        v
Human receives QR authentication surface
        |
        v
Human authenticates directly
        |
        v
Adapter observes authenticated mailbox state
        |
        v
Structured action resumes
```

### Explored path: interactive login-screen handoff

A live login surface can be exposed to the human so credentials and MFA are entered directly into the authentication UI. The model does not need the password or MFA secret.

The generic protocol therefore needs only `AUTH_REQUIRED -> AUTHENTICATED`; QR versus interactive login remains an adapter/runtime implementation choice.

---

## 4. Action mapping

For `send_mail`, the adapter is responsible for target-specific steps equivalent to:

1. confirm authenticated mail state;
2. open the compose flow;
3. map `recipient`, `subject`, and `body` into target fields;
4. initiate send;
5. observe a target-generated completion state;
6. return a Result Envelope bound to the original `command_id`.

The adapter MUST NOT report `VERIFIED_SUCCESS` merely because the browser automation process exited normally.

---

## 5. Verification mapping

The original experiment detected Naver Mail's completion state after sending. For v0.1 conformance, that target-specific signal maps to:

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
    "evidence": "Naver Mail post-send completion state observed"
  }
}
```

No stronger historical claim is made here about delivery to the recipient mailbox unless separately verified by experiment evidence.

---

## 6. Persistence boundary

The reference experiment showed that transferable browser state and transferable authenticated session state are not equivalent.

Observed behavior:

```text
Encrypted browser state transfer
        |
        v
New hosted execution environment
        |
        v
Network identity changed
        |
        v
Target security required reauthentication
```

Therefore:

- browser-state persistence is an implementation concern;
- network/device identity may be part of target authentication state;
- persistent authentication across rotating execution environments is NOT guaranteed by this adapter;
- a stable machine or equivalent persistent execution identity is a candidate future substrate for IP-bound sessions.

This limitation maps to `SUBSTRATE_BOUNDARY` or `AUTH_BOUNDARY` depending on the failed property; it does not require changing the generic protocol core.

---

## 7. Core extraction result

Refitting the Naver Mail reference flow to Protocol v0.1 did not require putting the following target details into the generic core:

- mail field names;
- compose/send UI behavior;
- QR authentication;
- browser selectors;
- browser automation library;
- hosted-runner behavior;
- IP-security behavior;
- Naver-specific completion signals.

Those remain adapter or substrate details.

This is the first internal check supporting the proposed core/adapter boundary. A second meaningfully different target is still required to test portability.