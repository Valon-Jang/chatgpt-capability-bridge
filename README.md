# chatgpt-capability-bridge

> **No target-service plugin. No target API. Still actionable from ordinary ChatGPT Chat.**

`chatgpt-capability-bridge` is an experimental methodology for discovering, composing, and extending the **effective capabilities of ordinary ChatGPT Chat** when richer execution surfaces or target-specific integrations are unavailable.

The project does **not** claim that ChatGPT uses zero integrations. A permitted general-purpose connected tool may still be used — GitHub is the first execution substrate in this research.

The narrower claim is:

> **A target service does not necessarily need its own ChatGPT plugin, native integration, MCP server, or dedicated API if ordinary Chat can compose an already-available general-purpose capability into a controlled execution path.**

This is capability composition, not unrestricted access and not a security bypass.

---

## Why ordinary Chat matters

The research starts from a practical constraint: the work must remain inside ordinary ChatGPT Chat even when richer execution surfaces such as Work, Codex, or Cloud Browser are unavailable, separated from the approved workflow, or undesirable for the current environment.

The core question is:

> **How far can ordinary Chat extend its own action boundary using only capabilities that are actually available and permitted in the current runtime?**

A model may understand a task while still lacking the direct action path required to complete it. Capability Bridge treats that mismatch as an engineering problem rather than pretending the missing tool exists.

---

## Observation #1 — documented capability vs effective runtime capability

In the runtime used for this research, the available GitHub tool surface exposed mutation actions for existing repositories, including file creation/update and Actions-related operations.

That was notable because general public descriptions of a GitHub connection can emphasize read/search use.

The repository therefore records the result narrowly:

> **This is an environment-specific runtime observation, not a claim that every ordinary ChatGPT session universally has GitHub write access.**

The first step of the methodology is therefore **Capability Discovery**: inspect the actions actually exposed in the current runtime, then stay within those permissions.

---

## Bootstrap boundary

The same runtime did not expose repository creation.

The user created this repository once in the GitHub UI. After that human bootstrap step, ordinary Chat could mutate the existing repository and construct the experimental bridge.

```text
No repository
   -> create-repository action unavailable
   -> Human bootstrap
   -> Existing repository
   -> Chat-visible GitHub mutation actions become usable
```

This establishes a hard principle:

> **Capability composition cannot synthesize a permission or action that is absent from every reachable substrate.**

---

## Capability Bridge lifecycle

```text
Discover
   -> Identify capability gap
   -> Bootstrap if required
   -> Compose available capabilities
   -> Human authentication handoff
   -> Act
   -> Verify
```

### 1. Discover
Inspect effective runtime capabilities.

### 2. Identify the gap
Define the action ordinary Chat cannot perform directly.

### 3. Bootstrap when necessary
Use the smallest human/permitted setup step only when the required substrate cannot be created through exposed actions.

### 4. Compose
Combine available capabilities into a narrow execution path.

### 5. Authenticate
Keep sensitive login under human control.

### 6. Act
Execute the target action through the bridge.

### 7. Verify
Return machine-readable and target-observable evidence to Chat.

---

## Protocol v0.1 — Core Freeze

The project separates a target-independent protocol core from target-specific adapters.

```text
chatgpt-capability-bridge/
├─ README.md
├─ protocol/
│  ├─ PROTOCOL.md
│  ├─ CAPABILITY_MANIFEST.md
│  ├─ COMMAND_ENVELOPE.md
│  ├─ AUTH_HANDOFF.md
│  └─ RESULT_ENVELOPE.md
├─ adapters/
│  ├─ naver-mail/
│  └─ naver-calendar/
└─ experiments/
   ├─ EXP-001-NAVER-MAIL.md
   └─ EXP-002-NAVER-CALENDAR.md
```

Protocol v0.1 defines:

- runtime capability discovery;
- capability-gap and bootstrap classification;
- structured command semantics;
- human authentication handoff;
- structured verification results;
- failure classes;
- a portability rule for separating adapter problems from genuine protocol gaps.

Target-specific UI flows, selectors, browser orchestration, service completion signals, and session behavior remain outside the core.

The Naver Mail reference flow was refit to Protocol v0.1 without a core change. EXP-002 then reached a verified Naver Calendar mutation while the core remained frozen.

A core change is allowed only after a documented target-independent `CORE_GAP`.

- [`protocol/PROTOCOL.md`](protocol/PROTOCOL.md)
- [`protocol/CAPABILITY_MANIFEST.md`](protocol/CAPABILITY_MANIFEST.md)
- [`protocol/COMMAND_ENVELOPE.md`](protocol/COMMAND_ENVELOPE.md)
- [`protocol/AUTH_HANDOFF.md`](protocol/AUTH_HANDOFF.md)
- [`protocol/RESULT_ENVELOPE.md`](protocol/RESULT_ENVELOPE.md)

---

## Core architecture

```text
Ordinary ChatGPT Chat
        |
        v
General-purpose connected capability
        |
        v
External execution bridge
        |
        v
Human-authenticated browser/session
        |
        v
Target web service
        |
        v
Target-observable result
        |
        v
Structured verification back to Chat
```

GitHub is the first substrate, not a required permanent dependency of the methodology.

---

## Human authentication handoff

Authentication stays human-controlled.

The model should not ask the user to paste passwords, MFA secrets, raw cookies, recovery codes, or bearer tokens into Chat.

Two useful patterns have been tested:

### QR handoff

```text
Bridge opens target QR login
   -> human scans/confirms
   -> authenticated browser session
   -> automation resumes
```

### Interactive login-screen handoff

```text
Bridge exposes live login UI
   -> human enters credentials/MFA directly
   -> authenticated browser session
   -> automation resumes
```

Design principle:

> **The human authenticates. The bridge acts through the authenticated state.**

---

## Reference implementation #1 — Naver Mail

EXP-001 demonstrated the first complete real-world action loop.

Execution path:

```text
Ordinary Chat
   -> GitHub command channel
   -> GitHub Actions browser runtime
   -> human Naver authentication
   -> structured mail command
   -> browser compose/send
   -> target completion observation
   -> result returned to Chat
```

Verified result:

- no Naver Mail-specific ChatGPT plugin in the execution path;
- no Naver Mail API in the execution path;
- real test email sent;
- target send completion detected;
- Protocol v0.1 refit required no core change.

See [`experiments/EXP-001-NAVER-MAIL.md`](experiments/EXP-001-NAVER-MAIL.md).

---

## Reference implementation #2 — Naver Calendar

EXP-002 tests portability with a different service and different mutation semantics.

```text
EXP-001 Mail
compose -> send -> completion

EXP-002 Calendar
create object -> observe exact identity -> cleanup workflow
```

The Naver Calendar API exists, but EXP-002 deliberately uses the browser UI instead.

### Current verified result

**Status: ACTION VERIFIED / CLEANUP PENDING**

The live experiment verified:

- one-time human QR authentication;
- authenticated Chrome retained across adapter failures and patches;
- command retries without repeated human authentication inside the same runner lifetime;
- entry into Naver Calendar's mobile schedule-writing UI;
- exact mapping of the title field to `textarea[placeholder="일정을 입력하세요."]`;
- target save action;
- exact nonce-bearing synthetic event observable after calendar reload;
- user-side Naver Calendar notification for the created event;
- no Protocol v0.1 changes.

Machine-readable creation evidence reached:

```json
{
  "created_title_observed": true
}
```

### Why the experiment is not marked full PASS yet

The original EXP-002 contract requires:

```text
create -> observe -> delete -> verify absence
```

Creation is proven, but automated event-card/detail navigation has not yet reliably completed deletion of the current synthetic event. Cleanup therefore remains explicit rather than inferred.

See:

- [`adapters/naver-calendar/ADAPTER.md`](adapters/naver-calendar/ADAPTER.md)
- [`experiments/EXP-002-NAVER-CALENDAR.md`](experiments/EXP-002-NAVER-CALENDAR.md)

---

## Persistent Authentication Pattern

EXP-002 produced a reusable execution pattern that is stronger than a one-shot Action:

```text
Human auth once
   -> persistent Chrome owned by workflow
   -> adapter attaches
   -> command succeeds or fails
   -> browser remains alive
   -> adapter code patched
   -> next command hot-loaded
   -> same authenticated session reused
```

This was observed working across multiple live diagnostics and retries.

Important boundary:

> **Retained browser state within one hosted runner is not the same as durable session persistence across new runners.**

Earlier Naver Mail persistence tests already showed that transferring cookies/profile state to a new GitHub-hosted runner can still trigger reauthentication when network identity changes.

For long-lived or IP-bound services, a stable self-hosted runner or persistent machine is the stronger architecture.

---

## What the experiments currently support

The evidence now supports these claims:

1. **Capability Discovery** — effective runtime actions can differ from a general integration description and should be inspected directly.
2. **Bootstrap Boundary** — capability composition cannot create absent permissions; minimal human bootstrap may still be required.
3. **Capability Composition** — a general GitHub execution substrate can host target-specific browser adapters controlled from ordinary Chat.
4. **Human Authentication Handoff** — authentication can stay outside model-visible credentials while automation acts through the authenticated state.
5. **Cross-action / cross-service portability inside one authentication ecosystem** — frozen Protocol v0.1 reached both Naver Mail send and Naver Calendar create mutation without a core change.
6. **Retained-session retry** — adapter code can fail, be patched, and run again against the same authenticated browser during one runner lifetime.

The evidence does **not** yet support:

- universal ordinary-Chat GitHub write access;
- every website being automatable;
- zero external integrations;
- a security-policy bypass;
- durable authentication across arbitrary hosts/IPs;
- full cross-vendor portability.

---

## Failure classes

Protocol v0.1 distinguishes:

- `CAPABILITY_GAP`
- `BOOTSTRAP_REQUIRED`
- `AUTH_REQUIRED`
- `AUTH_BOUNDARY`
- `SUBSTRATE_BOUNDARY`
- `TARGET_BOUNDARY`
- `ADAPTER_ERROR`
- `VERIFY_FAILED`
- `CORE_GAP`

`CORE_GAP` is intentionally hard to claim. Target UI friction, selectors, QR orchestration, event-card behavior, and service-specific navigation belong in adapters unless a genuinely reusable missing protocol concept is demonstrated.

EXP-002 has not demonstrated a `CORE_GAP`.

---

## Security principles

This repository preserves these boundaries:

- never store user passwords in source code;
- never commit private encryption keys or raw session values;
- keep MFA/recovery secrets outside Chat and command envelopes;
- prefer human-in-the-loop authentication;
- expose only the minimum browser/action surface required;
- keep public diagnostics structural and synthetic;
- verify target state rather than trusting transport/process success;
- respect target security controls, terms, and automation restrictions;
- never interpret a missing action as permission to bypass policy.

---

## Limits

Capability Bridge cannot:

- invoke a permission that no reachable tool has;
- convert read access into write access by assertion;
- guarantee browser automation against CAPTCHA, hardware authentication, device binding, IP binding, anti-bot systems, or unstable UIs;
- guarantee that runtime tools are identical across plans, workspaces, sessions, or rollouts.

All findings should be described as observations from the tested runtime and target path.

---

## Next research gate

The next major portability test should leave the Naver authentication ecosystem.

> **EXP-003 — cross-vendor portability**

A strong EXP-003 target should:

- use a different vendor/authentication environment;
- keep Protocol v0.1 frozen initially;
- add only a new target adapter;
- perform a harmless, reversible mutation;
- use human-controlled authentication;
- produce target-observable verification;
- classify any failure before considering a core change.

Only after that experiment should the project make a stronger cross-vendor portability claim.

---

## One-sentence summary

**Discover the capabilities ordinary Chat actually has, bootstrap only what is genuinely missing, compose those capabilities into a controlled external action path, keep authentication human-controlled, and verify the real target state rather than pretending unavailable tools exist.**