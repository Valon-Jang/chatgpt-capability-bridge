# Command Envelope v0.1

The Command Envelope is the target-independent request sent from the controller to a target adapter through the selected bridge path.

The envelope describes **what should happen**, not how a particular target UI, selector set, API, browser, or runner implements it.

---

## Minimal shape

```json
{
  "protocol_version": "0.1",
  "command_id": "<unique id>",
  "adapter_id": "<target adapter>",
  "action": "<declared adapter action>",
  "arguments": {},
  "nonce": "<unique replay-detection value>",
  "verification": {
    "required": true,
    "expected": "<target-observable completion condition>"
  },
  "experiment": {
    "reversible": true,
    "cleanup_requested": true
  }
}
```

---

## Required semantics

### `command_id`
Uniquely identifies one requested bridge action and binds the request to its result envelope.

### `adapter_id`
Selects the target-specific adapter. Target-specific behavior MUST NOT be encoded into the generic protocol outside this boundary.

### `action`
Names one action declared by the adapter.

### `arguments`
Contains only the information required to perform the action. It MUST NOT contain passwords, MFA secrets, recovery codes, private authentication tokens, or equivalent user credentials.

### `nonce`
Provides a unique marker for replay detection and experiment verification. A mutating adapter SHOULD use it when the target permits.

### `verification`
States whether completion must be verified and what observable outcome is expected. The adapter decides how to observe the target-specific signal.

---

## Optional semantics

Implementations MAY add fields such as:

- expiration time;
- idempotency policy;
- human confirmation requirement;
- impact/risk classification;
- requested cleanup behavior;
- correlation or experiment ID.

Extensions MUST NOT change the meaning of the required v0.1 fields.

---

## Command states

A command may move through these logical states:

```text
RECEIVED
   |
   +--> AUTH_REQUIRED
   |        |
   |        v
   |    AUTHENTICATED
   |
   v
EXECUTING
   |
   v
VERIFYING
   |
   +--> VERIFIED_SUCCESS
   +--> FAILED
   +--> UNKNOWN
```

Transport success is not equivalent to target-action success. The final state comes from the Result Envelope after verification.