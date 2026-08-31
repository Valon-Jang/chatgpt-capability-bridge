# GeekNews Persistent Browser Adapter

Purpose: let the authenticated user keep one temporary GeekNews browser session alive while ChatGPT prepares drafts and executes only user-approved submissions.

## Safety / community constraints

- No autonomous posting loop.
- No voting automation.
- No bulk crawling or site-wide scraping.
- No attempt to hide automation or bypass GeekNews controls.
- `draft_*` actions may fill a form but never submit it.
- `submit_*` actions require `approved=true` and a matching SHA-256 fingerprint from the approved draft.
- The browser session is temporary and expires with the GitHub-hosted runner (hard limit 6 hours).
- Login credentials are entered by the user directly into the temporary browser. They are never committed to the repository.
- The temporary noVNC URL/password are encrypted to a one-session public key before being written to the public repository.

## Commands

- `auth_status`
- `inspect_page` — arguments: `url`
- `draft_comment` — arguments: `topic_url`, `body`
- `submit_comment` — arguments: `body`; top-level: `approved=true`, `expected_text_sha256`
- `draft_reply` — arguments: `topic_url`, `body`, plus `target_author` or `target_comment_snippet`
- `submit_reply` — same approval contract as comment
- `draft_post` — arguments: `title`, optional `url`, optional `body`
- `submit_post` — same approval contract, fingerprint covers the canonical JSON of title/url/body

The adapter intentionally uses bounded DOM heuristics. If GeekNews changes its form structure, run `inspect_page` and update selectors rather than widening automation scope.
