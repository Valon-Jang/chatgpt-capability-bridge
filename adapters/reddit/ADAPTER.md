# Reddit / r/LocalLLaMA Persistent Browser Adapter

Purpose: keep one temporary user-authenticated Reddit browser session so ChatGPT can inspect user-selected threads and later assist with explicitly approved interaction.

## Guardrails

- No autonomous posting loop, voting automation, karma farming, mass browsing, or bulk scraping.
- Default community scope is `r/LocalLLaMA`.
- User chooses or approves each thread before interaction.
- Site and subreddit eligibility restrictions are never bypassed.
- Login credentials are entered by the user directly into the temporary browser and are never committed.
- Because r/LocalLLaMA restricts low-effort/LLM-generated content, the user's own view comes first and final text must be reviewed and materially owned by the user.
- Session expires with the GitHub-hosted runner.

## Current commands

- `auth_status`
- `inspect_page` — arguments: `url`

Comment/reply submission actions are added only after live authenticated DOM inspection and eligibility checks.
