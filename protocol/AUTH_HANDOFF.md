# Authentication Handoff v0.1

Authentication Handoff defines how a Capability Bridge temporarily transfers control to a human when login, MFA, consent, device confirmation, or equivalent authentication is required.

The central rule is:

> **The human authenticates. The bridge acts through the authenticated state.**

The model does not need the user's authentication secrets in order to continue the workflow.

---

## Security boundary

A conforming handoff MUST NOT require the user to place any of the following into a model-visible command payload:

- passwords;
- MFA or OTP values;
- recovery codes;
- private keys;
- bearer tokens;
- raw session cookies;
- equivalent reusable authentication secrets.

The user may enter or approve those values directly on the authentication surface controlled by the target or identity provider.

---

## Generic flow

```text
Bridge requests authenticated state
        |
        v
AUTH_REQUIRED
        |
        v
Human receives authentication surface
        |
        v
Human enters credentials / approves MFA directly
        |
        v
Bridge observes authenticated state
        |
        +--> AUTHENTICATED -> action resumes
        |
        +--> AUTH_FAILED
        |
        +--> AUTH_EXPIRED
```

The authentication surface may be visual, interactive, device-based, QR-based, redirect-based, or another human-controlled mechanism. The protocol core does not prescribe the mechanism.

---

## Handoff record

A handoff SHOULD be representable without secrets:

```json
{
  "handoff_version": "0.1",
  "command_id": "<command id>",
  "handoff_id": "<unique id>",
  "state": "AUTH_REQUIRED",
  "instructions": "<safe human-facing instruction>",
  "expires_at": "<optional timestamp>",
  "auth_context_id": null
}
```

After successful authentication:

```json
{
  "handoff_version": "0.1",
  "command_id": "<command id>",
  "handoff_id": "<same id>",
  "state": "AUTHENTICATED",
  "auth_context_id": "<opaque non-secret reference to authenticated execution state>"
}
```

`auth_context_id` is a reference usable by the bridge runtime. It MUST NOT be a model-visible credential or a raw session secret.

---

## Required behaviors

1. **Direct human entry.** Secrets are entered on the authentication surface, not sent through Chat as command arguments.
2. **Explicit state transition.** Automation resumes only after authenticated state is observed or confirmed.
3. **Timeout awareness.** Expired handoffs must not be treated as successful authentication.
4. **Target policy respect.** Device binding, IP binding, CAPTCHA, anti-bot controls, or service policy may make a handoff non-portable or non-automatable.
5. **No silent credential persistence.** Persistent authenticated state must be treated as a separate security and lifecycle concern.
6. **Failure classification.** If the authentication mechanism itself prevents the current bridge design, return `AUTH_BOUNDARY` rather than weakening the security boundary.

---

## Authentication is not persistence

A successful handoff establishes authenticated state for the current usable execution context. It does not guarantee that the state can be transferred to another machine, network identity, process, or future session.

Session persistence is therefore an implementation property, not a guarantee of the generic authentication contract.