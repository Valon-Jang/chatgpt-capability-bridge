# Capability Bridge Protocol v0.1

**Status:** Experimental / Core Freeze v0.1  
**Purpose:** Define the smallest target-independent contract for composing capabilities that are actually available to an ordinary Chat runtime into a controlled, verifiable action path.

This protocol describes a method for **capability composition**. It does not create permissions, bypass disabled controls, or claim that every runtime exposes the same tools.

---

## 1. Scope

The protocol applies when:

1. a user requests an action that the current Chat runtime cannot perform directly;
2. the runtime has at least one permitted capability that can participate in an execution path;
3. any missing bootstrap or authentication step can be performed by a human or another explicitly permitted channel;
4. the action can return verifiable evidence to the controlling Chat.

The protocol is deliberately independent of any particular target service, execution substrate, browser engine, automation library, or authentication provider.

---

## 2. Non-goals

A conforming bridge MUST NOT claim to:

- create an action or permission that is absent from every reachable substrate;
- convert read permission into write permission by assertion;
- bypass organizational, platform, target-service, or authentication policy;
- obtain passwords, MFA secrets, recovery codes, or private session material through model-visible command payloads;
- guarantee that every website or application can be automated;
- treat one environment-specific capability observation as a universal ChatGPT capability.

---

## 3. Roles

### Controller
The ordinary Chat session that receives user intent, discovers available capabilities, constructs commands, and interprets verified results.

### Capability substrate
A general-purpose capability already exposed and permitted in the current runtime that can host, trigger, transport, or coordinate execution.

### Bridge runtime
The execution environment reached through the substrate. It receives structured commands and invokes a target adapter.

### Target adapter
Target-specific logic that translates a generic command into actions supported by one target service.

### Human authenticator
The user acting directly on an authentication surface when credentials, MFA, consent, or device confirmation are required.

### Target service
The external service on which the requested action is performed.

### Verifier
Logic that determines whether the requested action actually completed and emits structured evidence.

One implementation may combine several roles, but the responsibilities remain logically separate.

---

## 4. Lifecycle

A conforming bridge follows this lifecycle:

```text
Discover
   |
   v
Identify Gap
   |
   v
Bootstrap if required
   |
   v
Compose
   |
   v
Human Authentication
   |
   v
Act
   |
   v
Verify
```

### 4.1 Discover
Inspect the actions that are actually exposed and usable in the current runtime.

Output: a capability manifest describing observed actions, permissions, and known limits.

### 4.2 Identify Gap
State the requested action and the missing direct capability precisely.

Output: either a direct-action path or a declared capability gap requiring composition.

### 4.3 Bootstrap if required
If a required substrate or resource does not yet exist and no exposed capability can create it, request the smallest necessary human bootstrap step.

Output: a usable substrate or `BOOTSTRAP_REQUIRED`.

### 4.4 Compose
Bind a capability substrate, bridge runtime, target adapter, command envelope, authentication handoff policy, and verification path.

Output: an executable bridge path.

### 4.5 Human Authentication
When authentication requires secrets or direct human confirmation, transfer control to the human authentication surface. The model MUST NOT require the secret itself in the command envelope.

Output: authenticated execution state or an authentication failure classification.

### 4.6 Act
Execute one declared adapter action using the structured command envelope.

Output: an execution record associated with the command ID.

### 4.7 Verify
Use target-observable evidence to determine whether the intended state change occurred. A successful transport or script exit alone is insufficient when stronger target evidence is available.

Output: a result envelope.

---

## 5. Core invariants

### I1. Effective capability truth
The bridge MUST distinguish documented product capability from capability actually exposed in the current runtime.

### I2. No synthetic permission
Composition may combine available capabilities, but it MUST NOT represent an unavailable action as available.

### I3. Minimal bootstrap
Human bootstrap MUST be limited to the smallest missing setup step necessary to make the permitted substrate usable.

### I4. Adapter isolation
Target-specific selectors, URLs, workflows, field mappings, completion signals, and authentication quirks MUST live outside the generic protocol core.

### I5. Human-controlled authentication
Passwords, MFA secrets, recovery codes, and equivalent credentials MUST remain outside model-visible command payloads. Authentication handoff is a control transfer, not credential collection.

### I6. Structured commands
Every bridge action MUST have a machine-readable command ID, adapter ID, action name, arguments, and verification intent.

### I7. Structured results
Every attempted action MUST return a machine-readable result associated with the original command ID.

### I8. Verifiable completion
`SUCCESS` requires target-observable verification. If the action outcome cannot be verified, the result MUST not be promoted to verified success.

### I9. Replay awareness
Commands that may mutate external state SHOULD include a unique nonce or idempotency key. Adapters SHOULD detect or safely reject accidental replay when the target permits it.

### I10. Reversible experimentation
Research experiments SHOULD prefer harmless, scoped, reversible actions and SHOULD clean up test state when cleanup is available.

---

## 6. Generic artifacts

The protocol core is represented by four companion contracts:

- [`CAPABILITY_MANIFEST.md`](./CAPABILITY_MANIFEST.md) — what the current runtime and selected substrate can actually do;
- [`COMMAND_ENVELOPE.md`](./COMMAND_ENVELOPE.md) — how a controller requests one adapter action;
- [`AUTH_HANDOFF.md`](./AUTH_HANDOFF.md) — how control is transferred to a human for authentication without exposing secrets to the model;
- [`RESULT_ENVELOPE.md`](./RESULT_ENVELOPE.md) — how execution and verification results are returned.

An implementation may serialize these contracts as JSON, YAML, database rows, messages, files, or another transport. The semantics matter more than the transport.

---

## 7. Failure classification

A bridge SHOULD classify failures instead of collapsing them into a generic error.

| Code | Meaning |
|---|---|
| `CAPABILITY_GAP` | No currently exposed capability can perform a required step. |
| `BOOTSTRAP_REQUIRED` | A minimal external setup step is required before composition can continue. |
| `AUTH_REQUIRED` | Human authentication is needed before the action can proceed. |
| `AUTH_BOUNDARY` | Authentication policy or mechanism prevents the current handoff design from completing. |
| `SUBSTRATE_BOUNDARY` | The selected execution substrate cannot satisfy a required execution property. |
| `TARGET_BOUNDARY` | The target service blocks or does not expose a safe/reliable path for the requested action. |
| `ADAPTER_ERROR` | Target-specific implementation failed while the generic contract remains sufficient. |
| `VERIFY_FAILED` | Execution may have occurred, but the requested result could not be verified. |
| `CORE_GAP` | A target-independent requirement is missing from the frozen protocol core. |

A `CORE_GAP` classification requires evidence that the missing concept is not specific to one target adapter or one substrate implementation.

---

## 8. Adapter conformance

A target adapter conforms to v0.1 when it:

1. declares an adapter ID and supported actions;
2. accepts the generic command envelope semantics;
3. keeps target-specific implementation details outside the protocol core;
4. declares its authentication handoff requirements;
5. performs or requests target-observable verification;
6. returns a result envelope for every attempted command;
7. does not require model-visible user credentials;
8. declares known replay, cleanup, persistence, and target-policy limitations.

---

## 9. Core Freeze rule for portability experiments

For the next portability experiment, this protocol is treated as **Core Freeze v0.1**.

The experiment MUST first attempt to add a second target by implementing only a new adapter and target-specific execution details.

The core MAY change only when the experiment produces a documented `CORE_GAP` showing that:

1. the missing concept is required to complete the lifecycle;
2. the concept is not merely a target-specific selector, field, authentication quirk, verification signal, or substrate detail;
3. adding it improves the generic contract rather than encoding the new target into the core.

This rule turns portability into a falsifiable test: if a second, meaningfully different target works without core changes, the evidence for a reusable Capability Bridge architecture becomes stronger.

---

## 10. v0.1 research question

> Can a frozen target-independent bridge contract support a second unsupported service through adapter replacement alone, while preserving human-controlled authentication and machine-verifiable completion?

That question is the basis of the next experiment.