# EXP-001 — Naver Mail Reference Implementation

**Experiment ID:** `EXP-001-NAVER-MAIL`  
**Role:** First end-to-end reference implementation  
**Status:** Completed reference experiment; architecture remains experimental

---

## Research question

Can ordinary ChatGPT Chat compose a permitted general-purpose capability into an external execution path that performs and verifies a real action on a target service without using a target-specific ChatGPT plugin, MCP server, or target-service API?

---

## Test conditions

The recorded experiment used the following conditions:

- ordinary ChatGPT Chat remained the control surface;
- Work was not used for the browser action;
- Codex was not used for the browser action;
- no Naver Mail-specific ChatGPT plugin was used;
- no Naver Mail API was used;
- an available general-purpose GitHub capability was used as the execution substrate;
- GitHub Actions provided an external execution environment;
- Chrome + Selenium performed browser interaction;
- the human performed authentication directly;
- QR-code authentication was used in the successful reference path;
- structured commands were used after authentication rather than requiring repeated full-screen interpretation for every mail action.

---

## Lifecycle mapping

### 1. Discover
The active Chat runtime exposed mutation capabilities on an existing repository that were usable for constructing the experiment.

### 2. Identify Gap
Ordinary Chat did not directly expose an authenticated Naver Mail browser action or Naver-specific send-mail integration in the experiment path.

### 3. Bootstrap
The runtime did not expose repository creation. The user created the repository once through the GitHub UI. This established the Human Bootstrap / Bootstrap Boundary case.

### 4. Compose
The available repository/action capabilities were composed into a command and browser execution path.

### 5. Human Authentication
The human authenticated Naver directly. The successful reference flow used QR-code authentication. Credentials were not required as model-visible command arguments.

### 6. Act
A structured command drove composition and sending of a real test email.

### 7. Verify
The automation detected Naver Mail's completion state after the send action and returned completion status to Chat.

---

## Verified result

**Result:** PASS for the scoped reference claim.

The experiment demonstrated the complete loop:

```text
Chat intent
   -> available capability composition
   -> external execution
   -> human authentication
   -> target action
   -> target completion verification
   -> result returned to Chat
```

A real test email was sent successfully and a target post-send completion state was observed.

This experiment does **not** by itself prove universal target portability or universal ChatGPT write capability.

---

## Capability Discovery observation

A separate but related result was that the effective capability surface observed in the active runtime was broader for existing repository mutation than the standard public description of the normal GitHub connection emphasized.

The experiment records this only as an **environment-specific runtime observation**.

It is not evidence that:

- every ChatGPT session exposes the same actions;
- a security control was bypassed;
- unavailable permissions can be manufactured through composition.

---

## Bootstrap Boundary observation

The same runtime lacked a create-repository action.

Therefore:

```text
required initial repository
        +
no exposed create-repository action
        =
minimal human bootstrap required
```

Once the repository existed, the available repository mutation capabilities could be used inside its permitted scope.

This became the `Bootstrap if required` stage in Protocol v0.1.

---

## Authentication handoff findings

Two patterns were identified:

1. **QR-code handoff** — used in the successful reference flow;
2. **interactive login-screen handoff** — explored as a more general pattern for services without QR login.

The reusable finding is not the QR mechanism itself. It is the separation:

> Human handles the authentication secret; automation resumes after authenticated state exists.

---

## Persistence follow-up

A follow-up attempted encrypted transfer of browser state between rotating hosted runners.

### Result

- encrypted browser-state handoff itself succeeded;
- the target detected the changed runner/network identity;
- reauthentication was required.

### Finding

> Cookie or browser-state persistence is not necessarily authenticated-session persistence.

Network identity, device binding, or other target security context may participate in session validity.

For targets with such behavior, stable execution identity is a candidate follow-up architecture.

---

## Protocol v0.1 refit

After the initial experiment, the implementation was conceptually refit into the frozen generic protocol.

Target-independent concepts extracted into the core:

- capability discovery;
- precise capability-gap identification;
- minimal bootstrap;
- composition;
- human authentication handoff;
- structured command envelope;
- target-observable verification;
- structured result envelope;
- failure classification.

Target-specific details retained in `adapters/naver-mail/`:

- mail fields and send semantics;
- target UI behavior;
- authentication mechanism details;
- target completion signal;
- target session/IP behavior.

**Refit result:** no Core v0.1 change was required to describe the verified Naver flow.

---

## Limitations of EXP-001

EXP-001 is one target and one action family. It cannot distinguish a genuinely reusable architecture from a well-structured single-target solution by itself.

The strongest next test is therefore not another improvement to this target. It is a portability experiment against a meaningfully different action type while keeping the generic core frozen.

---

## Next experiment gate

`EXP-002` should pass only if, at minimum:

- a second target uses Protocol v0.1 without core changes;
- only a new target adapter and target-specific execution details are added;
- authentication remains human-controlled;
- no target-specific ChatGPT plugin/API/MCP is required in the test path;
- one harmless mutation is performed;
- a unique nonce or equivalent marker is used where the target allows;
- target-observable verification is returned to Chat;
- experiment-created state is cleaned up when safely possible;
- any failure is classified as adapter, authentication, substrate, target, verification, or genuine core gap.

A required core change is not automatically a failed research outcome, but it must be documented as `CORE_GAP` rather than silently modifying the protocol during the portability test.