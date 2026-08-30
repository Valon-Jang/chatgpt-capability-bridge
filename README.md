# chatgpt-capability-bridge

> **No target-service plugin. No target API. Still actionable from ordinary ChatGPT Chat.**

`chatgpt-capability-bridge` is an experimental methodology for discovering, composing, and extending the **effective capabilities of ordinary ChatGPT Chat** when richer execution surfaces or target-specific integrations are unavailable.

The project does **not** claim that ChatGPT uses zero integrations. A permitted general-purpose connected tool may still be used — GitHub was the first execution substrate in this experiment.

The more precise claim is:

> **A target service does not necessarily need its own ChatGPT plugin, native integration, MCP server, or dedicated API if ordinary Chat can compose an already-available general-purpose capability into a controlled execution path.**

---

## Origin: why ordinary Chat mattered

This research started from a practical constraint: **the work had to remain inside ordinary ChatGPT Chat**.

There are environments where Chat is available but richer execution surfaces such as Work, Codex, or Cloud Browser are unavailable, disabled, separated from the approved workflow, or undesirable because of product access, organizational policy, workspace permissions, or security constraints.

The goal was therefore not to replace Work or Codex when they are available. The question was narrower:

> **How far can ordinary Chat extend its own action boundary using only capabilities that are actually available and permitted in the current runtime?**

This distinction matters because a model may fully understand the user's intent while still lacking a direct execution path for the requested action.

For example, ordinary Chat may understand how a webmail service works, but understanding alone does not provide a signed-in browser session, a DOM-control surface, or a target-specific send-mail integration.

This project investigates how to bridge that gap without pretending that unavailable tools are available.

---

## The documented capability gap

OpenAI currently separates **Chat**, **Work**, and **Codex** into different product surfaces.

Official documentation describes the fast conversational Chat experience separately from Work and Codex, while browser-based signed-in execution is exposed through richer execution surfaces:

- ChatGPT Work and Codex: https://help.openai.com/en/articles/20001275
- Built-in browser: https://help.openai.com/en/articles/20001277-using-the-built-in-browser-in-the-chatgpt-desktop-app
- Cloud browser: https://help.openai.com/en/articles/20001280-using-cloud-browser-in-chatgpt

The built-in browser is opened from a **Work or Codex** chat, and the cloud browser is documented as a **Work** capability.

The GitHub integration provides another useful example. OpenAI's standard GitHub documentation says that the GitHub app is used to **read repositories for analysis and search**, while direct code editing and pushing are associated with Codex:

- GitHub connection documentation: https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt-deep-research

So the practical problem is not that ordinary Chat has no tools at all. It is that **the action surface exposed to ordinary Chat may be narrower than the task requires**.

```text
User intent
   |
   v
Ordinary Chat understands the task
   |
   |  missing direct action path
   v
Capability gap
```

---

## Observation #1: documented capability vs effective runtime capability

The first important observation was that **the capabilities documented for a product integration and the capabilities actually exposed to a specific Chat runtime are not always identical**.

In the runtime used for this experiment, the available GitHub tool surface exposed mutation actions for existing repositories, including operations such as:

- creating files;
- updating files;
- creating branches;
- modifying pull-request state or metadata;
- interacting with GitHub Actions-related resources.

Those actions were actually used from ordinary Chat to modify repositories and construct experimental workflows.

This was notable because the standard public GitHub-app documentation describes the normal ChatGPT GitHub connection as read-only for repository analysis and search.

This repository therefore records the difference carefully:

> **This is an environment-specific runtime observation, not a claim that every ordinary ChatGPT session universally has GitHub write access, and not a claim that a security control was bypassed.**

A core lesson is:

> **Do not infer the full effective capability boundary only from a product label or a general integration description. Inspect the actions actually exposed in the current runtime, then stay within those actions and permissions.**

This became the first step of the methodology: **Capability Discovery**.

---

## Bootstrap boundary: the repository-creation limitation

The GitHub experiment also exposed an equally important limitation.

Although the active runtime exposed write actions **inside an existing repository**, it did **not** expose a `create repository` action.

The available mutation operations required an already-existing repository identifier such as `owner/repository`. As a result, Chat could modify files after a repository existed, but it could not create the initial repository itself through the exposed GitHub tool surface.

The user therefore created this repository manually in the GitHub UI. Once that bootstrap step existed, ordinary Chat could continue modifying the README and other repository contents through the available actions.

```text
No repository exists
        |
        |  no create-repository capability exposed
        v
Human bootstrap
(create repository once)
        |
        v
Existing repository
        |
        v
Chat runtime GitHub mutations become usable
```

This defines an important architectural boundary:

> **Capability composition cannot create a permission or action that is absent from every reachable substrate.**

A Capability Bridge can discover and compose available abilities into a new path, but some workflows still require a **human bootstrap step** or another explicitly permitted tool to create the initial substrate.

This limitation is part of the methodology, not an exception to hide.

---

## Capability Bridge lifecycle

The experiments suggest a reusable lifecycle.

### 1. Discover
Inspect the tools and actions actually exposed to the current Chat runtime.

### 2. Identify the gap
Define the action the user needs but ordinary Chat cannot directly perform.

### 3. Bootstrap when necessary
If the required substrate does not yet exist and no creation action is exposed, use a human or another permitted channel for the minimum setup step.

### 4. Compose
Combine available capabilities into a narrow execution path.

### 5. Authenticate
When sensitive authentication is required, hand control to the human rather than asking the model to receive passwords or MFA secrets.

### 6. Act
Execute the target action through the constructed bridge.

### 7. Verify
Return evidence or a machine-readable result to Chat so the loop closes.

```text
Discover
   |
   v
Identify capability gap
   |
   v
Bootstrap if required
   |
   v
Compose available capabilities
   |
   v
Human authentication handoff
   |
   v
Execute action
   |
   v
Verify result back in Chat
```

---

## Core idea

Instead of waiting for every target service to expose a dedicated ChatGPT integration:

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
Unsupported target web service
        |
        v
Verified real-world action
```

The connected tool becomes a **capability substrate**: ChatGPT uses a capability it already has access to in order to construct another controlled capability it did not directly expose before.

This is **capability composition**, not a claim of unrestricted access.

---

## What makes this different

This project does **not** claim that ChatGPT can act without any external tool at all.

It demonstrates a narrower and more practical claim:

- no target-specific ChatGPT plugin is required;
- no target-specific MCP server is required;
- no target-service API is required when the browser UI is sufficient;
- the user can remain in ordinary ChatGPT Chat;
- a permitted general-purpose execution channel can be repurposed into an action bridge;
- human authentication can be handed off without giving credentials to the model;
- structured commands can drive repeatable browser actions after authentication;
- results can be returned to Chat and verified;
- unavailable actions remain unavailable unless a human or another permitted substrate bootstraps them.

---

## Human authentication handoff

Authentication remains human-controlled.

The model should not ask the user to paste passwords, MFA secrets, or session tokens into the chat. Instead, control is temporarily handed to the user for authentication and returned to automation afterward.

Two patterns were explored in the first prototype.

### 1. QR-code handoff

```text
Chat -> remote browser -> QR login page
                       -> user scans QR
                       -> user confirms authentication
                       -> authenticated browser session
                       -> automated action resumes
```

This worked well for services that support QR authentication.

### 2. Interactive login-screen handoff

```text
Chat -> remote browser -> live login UI shown to user
                       -> user enters credentials / MFA directly
                       -> authenticated browser session
                       -> automated action resumes
```

This generalizes the pattern to services that do not provide QR login.

The design principle is:

> **The human authenticates. The bridge acts through the authenticated session.**

---

## Reference implementation #1: Naver Mail

Naver Mail was used as the first real-world validation target.

The experiment intentionally used a service that did not have a target-specific ChatGPT integration in the test path.

### Test conditions

- ordinary ChatGPT Chat was the control surface;
- ChatGPT Work was not used for the browser action;
- Codex was not used for the browser action;
- no Naver Mail-specific ChatGPT plugin was used;
- no Naver Mail API was used;
- GitHub was reused as the general-purpose execution substrate;
- GitHub Actions created the browser execution environment;
- Chrome + Selenium performed browser interaction;
- the user authenticated Naver directly through a human authentication handoff;
- QR-code authentication was used in the successful reference flow;
- an interactive login-screen handoff was also explored as a more general authentication pattern;
- subsequent email composition and sending were driven by structured commands rather than repeated full-screen visual interpretation.

### Verified action flow

```text
Ordinary ChatGPT Chat
        |
        v
GitHub command channel
        |
        v
Browser execution environment
        |
        v
Human authentication
        |
        v
Authenticated Naver Mail session
        |
        v
Structured send-mail command
        |
        v
DOM interaction / compose / send
        |
        v
Result verification
```

The prototype successfully sent real test email and detected Naver Mail's completion state after sending.

The useful result was not merely that a browser could be opened. The complete loop was demonstrated:

> **Chat intent -> capability composition -> external execution -> human authentication -> web action -> result verification -> status returned to Chat.**

---

## Why this can matter

### 1. Ordinary Chat can remain the control surface

In constrained environments, the user may be able to use ordinary Chat while Work, Codex, Cloud Browser, or other richer execution modes are unavailable or not permitted.

A bridge can provide a narrower and explicit action capability while preserving the existing Chat workflow.

This is **not** a claim that the pattern bypasses organizational security policy. The bridge and its underlying tools must themselves be permitted.

### 2. Unsupported services become candidates for controlled automation

A target does not necessarily need to ship a ChatGPT integration first. If its browser UI can be safely and reliably automated, it may be reachable through a bridge adapter.

### 3. Capability discovery can reveal useful runtime affordances

The GitHub experiment showed that the current runtime's effective tool surface can be worth inspecting directly rather than assuming it exactly matches the most general public description of an integration.

This makes **capability discovery** a first-class part of the methodology.

### 4. One generic execution channel can support multiple targets

Instead of building a completely new ChatGPT integration for every service, the same execution substrate can host multiple target adapters.

```text
                  +-> Webmail adapter
Chat -> Bridge ---+-> Internal web app adapter
                  +-> Form / portal adapter
                  +-> Other browser-action adapters
```

### 5. Human authentication stays separable from AI control

The user can authenticate directly into the browser while the model receives neither the password nor the MFA secret. Automation begins only after the authenticated session exists.

### 6. Screen interpretation is not required for every action

A browser may be used interactively for bootstrap and authentication, then switched to stable DOM selectors and structured commands for routine operations. This can reduce latency and improve repeatability compared with visually re-interpreting the whole page for every action.

---

## Persistence experiments

The Naver Mail prototype also explored persistent authenticated sessions.

A first design attempted to hand an encrypted browser state from one GitHub-hosted runner to the next before the runner timeout. The browser state transfer itself worked, but Naver Mail detected the changed runner IP and required reauthentication because of its IP-security behavior.

That failure clarified an architectural boundary:

> **Cookie persistence is not always session persistence. Network identity can be part of authentication state.**

For services with IP-bound sessions, a more durable architecture is a persistent browser on a stable machine or self-hosted runner rather than rotating ephemeral hosted runners.

---

## Limits and non-goals

This methodology has explicit limits.

- It cannot invoke actions that are not exposed by any reachable and permitted tool.
- It cannot turn read permission into write permission by assertion.
- It may require a human bootstrap step, as repository creation did in this experiment.
- It does not guarantee that every website is automatable.
- CAPTCHA, hardware-backed authentication, device binding, IP binding, anti-bot systems, service policy, or unstable interfaces can prevent automation.
- Runtime capabilities may vary by plan, workspace, installed plugins/apps, permissions, rollout state, and product surface.
- An environment-specific observation should not be presented as a universal ChatGPT capability.

The project is about **composing allowed capabilities**, not bypassing disabled ones.

---

## Security principles

This repository should preserve the following boundaries as it evolves:

- never store user passwords in source code;
- never commit private encryption keys;
- prefer human-in-the-loop authentication;
- keep target credentials outside model-visible command payloads;
- encrypt commands or session-transfer material when they cross an untrusted storage channel;
- expose only the minimum browser/action surface needed for the task;
- verify high-impact actions before execution when appropriate;
- respect the target service's security controls, terms, and automation restrictions;
- do not treat the absence of a tool action as permission to bypass platform policy;
- do not describe this pattern as a way to bypass organizational security policy.

---

## Terminology

### Effective runtime capability
An action that is actually exposed and usable in the current Chat runtime, regardless of whether a more general product description emphasizes or omits it.

### Capability discovery
The process of inspecting the current runtime to determine what actions are truly available before designing a bridge.

### Human bootstrap
A minimal setup action performed by the user when the required initial substrate cannot be created through the exposed runtime capabilities.

### Target-specific integration
An integration designed specifically for the service being controlled, such as a dedicated plugin, app, MCP server, or API adapter.

### General-purpose execution bridge
A tool ChatGPT can already reach that can host, trigger, or communicate with another execution environment. GitHub was used in the first experiment, but the pattern is not intended to be GitHub-specific.

### Authentication handoff
A temporary transfer of browser control to the human for login or MFA, followed by return of control to the automated bridge.

### Capability bridge
The overall pattern of discovering and composing existing ChatGPT-accessible capabilities into a new controlled execution path.

---

## Current status

**Experimental / proof of concept.**

Two important findings are currently documented:

1. **Capability Discovery:** the active Chat runtime exposed more GitHub mutation capability for existing repositories than the standard public GitHub-app description suggested, while still lacking repository-creation capability.
2. **Capability Composition:** those available GitHub actions were composed into a browser execution bridge that successfully performed and verified a real Naver Mail send from ordinary Chat.

The next goal is to separate the generic bridge protocol from the Naver Mail adapter and test whether the same lifecycle can reliably support additional unsupported services without adding target-specific ChatGPT integrations.

---

### One-sentence summary

**Discover the capabilities ordinary Chat actually has, bootstrap only what is genuinely missing, and compose the available pieces into controlled actions on services that have no target-specific ChatGPT plugin or API — while keeping authentication human-controlled.**
