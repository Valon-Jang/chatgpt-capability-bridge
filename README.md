# chatgpt-capability-bridge

> **No target-service plugin. No target API. Still actionable from ordinary ChatGPT Chat.**

`chatgpt-capability-bridge` is an experimental pattern for extending **ordinary ChatGPT Chat** beyond its native execution boundary by reusing a general-purpose connected tool as an external execution bridge.

The key idea is not that ChatGPT uses *zero* integrations. A general-purpose integration or execution channel may still be used — GitHub was used in the first prototype.

The important distinction is:

> **The target service itself does not need a ChatGPT plugin, native integration, MCP server, or dedicated API.**

This can be useful when ChatGPT Work, Codex, Cloud Browser, or other advanced execution surfaces are unavailable because of product access, organizational policy, security constraints, or environment limitations — while an approved general-purpose execution channel is still available.

## Core idea

Instead of waiting for every target service to expose a dedicated ChatGPT integration:

```text
Ordinary ChatGPT Chat
        |
        v
General-purpose connected tool
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

The connected tool becomes a **capability substrate**: ChatGPT uses a capability it already has access to in order to construct another capability it did not originally have.

## What makes this different

This project does **not** claim that ChatGPT can act without any external tool at all.

It demonstrates a narrower and more practical claim:

- no target-specific ChatGPT plugin is required;
- no target-specific MCP server is required;
- no target-service API is required when the browser UI is sufficient;
- the user can remain in ordinary ChatGPT Chat;
- a general-purpose execution channel can be repurposed into an action bridge;
- human authentication can be handed off without giving credentials to the model;
- after authentication, structured commands can drive repeatable browser actions and return verified results.

## Human authentication handoff

Authentication remains human-controlled.

The model should not ask the user to paste passwords, MFA secrets, or session tokens into the chat. Instead, control is temporarily handed to the user for authentication and returned to the automation afterward.

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

This generalizes the approach to services that do not provide QR login.

The design principle is:

> **The human authenticates. The bridge acts through the authenticated session.**

## Reference implementation #1: Naver Mail

Naver Mail was used as the first real-world validation target.

The experiment intentionally used a service that did not have a target-specific ChatGPT integration in the test path.

### Test conditions

- ordinary ChatGPT Chat was used as the control surface;
- ChatGPT Work was not used for the browser action;
- Codex was not used for the browser action;
- no Naver Mail-specific ChatGPT plugin was used;
- no Naver Mail API was used;
- GitHub was reused as the general-purpose execution bridge;
- GitHub Actions created the browser execution environment;
- Chrome + Selenium performed browser interaction;
- the user authenticated Naver directly through a QR-code handoff;
- subsequent email composition and sending were driven by structured commands rather than repeated visual screen interpretation.

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
Human QR authentication
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

This was important because the useful result was not merely "the browser opened." The complete loop was demonstrated:

**Chat intent -> external execution -> authenticated web action -> result verification -> status returned to Chat.**

## Why this can matter

### 1. Unsupported services become candidates for automation

A target does not necessarily need to ship a ChatGPT integration first. If its browser UI can be safely and reliably automated, it may be reachable through a bridge adapter.

### 2. Ordinary Chat can gain controlled action capabilities

Some environments allow ChatGPT Chat but do not allow Work, Codex, Cloud Browser, or similar execution modes. A bridge can provide a narrower capability while preserving the existing Chat interface.

This is **not** a claim that the pattern bypasses security policy. The general-purpose bridge itself must still be permitted in the environment.

### 3. One generic execution channel can support multiple targets

Instead of building a completely new ChatGPT integration for every service, the same execution substrate can host multiple target adapters.

```text
                  +-> Webmail adapter
Chat -> Bridge ---+-> Internal web app adapter
                  +-> Form / portal adapter
                  +-> Other browser-action adapters
```

### 4. Human authentication stays separable from AI control

The user can authenticate directly into the browser while the model receives neither the password nor the MFA secret. Automation begins only after the authenticated session exists.

### 5. Screen interpretation is not required for every action

A browser may be used interactively for bootstrap and authentication, then switched to stable DOM selectors and structured commands for routine operations. This can reduce latency and improve repeatability compared with visually re-interpreting the whole page for every action.

## Persistence experiments

The Naver Mail prototype also explored persistent authenticated sessions.

A first design attempted to hand an encrypted browser state from one GitHub-hosted runner to the next before the runner timeout. The browser state transfer itself worked, but Naver Mail detected the changed runner IP and required reauthentication because of its IP-security behavior.

That failure clarified an architectural boundary:

> **Cookie persistence is not always session persistence. Network identity can be part of authentication state.**

For services with IP-bound sessions, a more durable architecture is a persistent browser on a stable machine or self-hosted runner rather than rotating ephemeral hosted runners.

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
- do not describe this pattern as a way to bypass organizational security policy.

## Current scope

This repository is currently a **methodology + experimental reference implementation**, not a universal web automation framework.

The Naver Mail experiment proves one end-to-end case. It does **not** imply that every website can be automated. CAPTCHA, hardware-backed authentication, anti-bot systems, device binding, IP binding, service policy, or unstable interfaces can prevent or restrict automation.

## Terminology

### Target-specific integration
An integration designed specifically for the service being controlled, such as a dedicated plugin, app, MCP server, or API adapter.

### General-purpose execution bridge
A tool ChatGPT can already reach that can host, trigger, or communicate with another execution environment. GitHub was used in the first experiment, but the pattern is not intended to be GitHub-specific.

### Authentication handoff
A temporary transfer of browser control to the human for login or MFA, followed by return of control to the automated bridge.

### Capability bridge
The overall pattern of composing an existing ChatGPT-accessible capability into a new controlled execution capability.

## Status

**Experimental / proof of concept.**

The next goal is to separate the generic bridge protocol from the Naver Mail adapter and test whether the same architecture can reliably support additional unsupported web services without adding target-specific ChatGPT integrations.

---

### One-sentence summary

**Use a general-purpose execution bridge to let ordinary ChatGPT Chat perform controlled actions on web services that have no target-specific ChatGPT plugin or API, while keeping authentication human-controlled.**
