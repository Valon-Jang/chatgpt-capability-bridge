# Capability Manifest v0.1

The Capability Manifest records **what is actually exposed and usable in the current runtime** before a bridge is designed.

It is observational, environment-specific, and time-sensitive. It MUST NOT be interpreted as a universal product capability list.

---

## Required fields

```json
{
  "manifest_version": "0.1",
  "observed_at": "<timestamp>",
  "runtime_context": "<non-secret runtime description>",
  "capabilities": [
    {
      "capability_id": "<stable local name>",
      "actions": ["<observed action>"],
      "scope": "<observed permission/resource scope>",
      "mutation": true,
      "evidence": "<how availability was established>",
      "limits": ["<known limit>"]
    }
  ],
  "missing_required_actions": ["<gap>"],
  "bootstrap_requirements": ["<minimal human or permitted external setup step>"]
}
```

---

## Rules

1. **Observed, not assumed.** Include actions only when the current runtime exposes them or they have been directly verified.
2. **Separate presence from permission scope.** An action existing in a tool surface does not imply access to every resource.
3. **Record mutation explicitly.** Read, create, update, delete, trigger, and administrative actions have different risk and verification requirements.
4. **Record missing actions.** A useful manifest includes boundaries, not only positive capabilities.
5. **Record bootstrap requirements.** When a missing action can only be completed by a human or another permitted channel, state that boundary explicitly.
6. **Do not store secrets.** Tokens, passwords, session cookies, MFA material, and private keys do not belong in the manifest.
7. **Refresh when material.** Re-discover capabilities when the runtime, connected tools, permissions, plan, workspace, or required action changes.

---

## Discovery outcome

Capability discovery should end in one of three states:

- `DIRECT`: the requested action is already directly available;
- `COMPOSABLE`: no direct action exists, but available capabilities can form a permitted bridge path;
- `CAPABILITY_GAP`: no reachable permitted capability can satisfy a required step.

Only `COMPOSABLE` proceeds into Capability Bridge composition.