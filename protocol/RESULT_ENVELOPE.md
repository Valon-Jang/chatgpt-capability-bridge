# Result Envelope v0.1

The Result Envelope returns execution and verification status from a target adapter to the controlling Chat.

Its purpose is to close the loop with machine-readable evidence instead of relying on a script exit code or an unverified claim that an action probably succeeded.

---

## Minimal shape

```json
{
  "protocol_version": "0.1",
  "command_id": "<original command id>",
  "adapter_id": "<target adapter>",
  "status": "VERIFIED_SUCCESS",
  "execution": {
    "attempted": true,
    "completed": true
  },
  "verification": {
    "performed": true,
    "passed": true,
    "evidence": "<target-observable evidence summary>"
  },
  "cleanup": {
    "requested": true,
    "performed": true,
    "verified": true
  },
  "failure": null
}
```

---

## Status values

### `VERIFIED_SUCCESS`
The adapter executed the requested action and target-observable verification passed.

### `FAILED`
The action did not complete, or a known failure prevented completion.

### `PARTIAL`
Some requested effects occurred, but the complete requested state was not achieved.

### `UNKNOWN`
Execution may have occurred, but the final target state cannot be verified safely or reliably.

`UNKNOWN` MUST NOT be promoted to success merely because the bridge runtime or transport completed normally.

---

## Verification evidence

The `verification.evidence` field SHOULD summarize the strongest target-observable completion evidence available without leaking secrets or unnecessary private data.

Examples of evidence classes include:

- existence of a newly created object carrying the command nonce;
- a target-generated success state;
- an observable state transition;
- a returned target object identifier;
- successful deletion of experiment-created state during cleanup.

The specific selector, response, UI element, or target field used to establish the evidence belongs to the adapter.

---

## Failure shape

```json
{
  "status": "FAILED",
  "failure": {
    "class": "ADAPTER_ERROR",
    "code": "<adapter or bridge code>",
    "message": "<safe summary>",
    "retryable": false
  }
}
```

The `class` SHOULD use the failure taxonomy defined in `PROTOCOL.md` when applicable.

---

## Cleanup semantics

For reversible research actions, cleanup SHOULD be separately reported and verified.

An experiment can therefore distinguish:

- action success + cleanup success;
- action success + cleanup failure;
- action failure with no external state created;
- unknown action state requiring manual inspection.

Cleanup failure does not erase evidence that the original action succeeded, but it must remain visible in the result.

---

## Exactly-once research evidence

When a target supports a searchable nonce or equivalent unique marker, an experiment SHOULD verify that the intended mutation exists exactly once.

This does not guarantee distributed exactly-once execution in the formal systems sense. It provides a practical experiment-level check against accidental duplicate mutation or command replay.