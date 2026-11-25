# Security Policy

This policy covers reporting, disclosure and the trust boundaries of a local-first application. Pay particular attention to untrusted files, the optional web boundary, and the permissions on saved research and shared native code.

## Reporting a Vulnerability

**Do not open a public GitHub issue for a security report.** Public issues are indexed and searchable immediately, giving an attacker a head start before a fix ships.

Instead:

1. **Preferred: GitHub Private Vulnerability Reporting.** This repository's **Security** tab → **Report a vulnerability**. This opens a private advisory thread visible only to the maintainer and you.
2. **Fallback: Direct contact.** If private reporting is unavailable, contact the maintainer, Jason Brisart, through a private channel (e.g. a direct message via the maintainer's listed GitHub profile contact) rather than a public one.

Please include, where possible:

- Which component is affected (`web/`, `io/`, `knowledge/`, external native APIs, `ui/`, or the shared `util`/`intent`/`blocklist` layer).
- Steps to reproduce, or a minimal proof of concept.
- What you believe the impact is (e.g. local-file disclosure, SSRF via the crawler, code execution during file parsing, denial of service, a decompression-bomb-style resource exhaustion).

## Response Expectations

This is a solo-maintained research project, not a company with a security team on call. On a best-effort basis:

- **Acknowledgement** of a private report: within a few days.
- **Initial assessment** (confirmed / not applicable / needs more information): within roughly two weeks.
- **Fix or mitigation timeline** once a report is confirmed, communicated in the private advisory thread.

There is no bug bounty program at this time.

## Coordinated Disclosure

Please allow a reasonable window to investigate and ship a fix before any public disclosure. Once a fix is released, the advisory can be made public and credit given to the reporter (by name, handle, or anonymously) unless requested otherwise.

## Scope

**In scope:**

- **`web/`** — the crawler, fetcher, search providers, and `policy.py`. Server-Side Request Forgery (SSRF), private-address access, and robots/redirect handling are the highest-value area here.
- **`io/`** — file and HTML/PDF/Office parsing. A crafted file that causes code execution, resource exhaustion, or path traversal during ingestion is in scope.
- **`knowledge/`** — the SQLite schema and query construction (e.g. any injection path into the index).
- **external native APIs** — the from-spec stdlib-equivalent primitives (hashing, URL parsing, JSON, HTML tokenizing, DEFLATE decompression, robots.txt interpretation). A crafted input that causes one of these to disagree with the real stdlib function it replaces in a security-relevant way (e.g. a URL that `brisart_url` parses differently than `urllib.parse` in a way that could bypass `web/policy.py`'s private-host check) is of particular interest, since these modules are a trust boundary between untrusted external bytes and the rest of the application.
- **`ui/`** and the entry point — path handling and how untrusted input reaches the layers above.

**Out of scope, but still worth reporting if you find something:** reachability of a genuinely public page that a user explicitly asked to research.

## Standing Caveats

- **The crawler talks to the public internet when enabled.** `web/policy.py` refuses local/private/loopback/link-local destinations before any fetch, and honours a successfully-parsed `robots.txt`. By design, an unreachable or malformed `robots.txt` is treated as "allowed," not "denied" — a retrieval failure must never be readable as a site-wide block. This is a deliberate availability trade-off, not an oversight.
- **Untrusted documents.** Office, OpenDocument and PDF extraction processes input under the user account. Extraction is best-effort, not a sandbox or a guarantee against resource exhaustion. PDF decompression uses the external native stack.
- **The native stack is trusted local code.** The loader checks that its files are outside Offline_AI and does not download them. Point `BRISART_NATIVE_API` only at a trusted checkout of the shared modules.
- **Saved data is not encrypted.** The index holds the full text of every imported file and crawled page in a plain SQLite file in the per-user state folder (`brisart_ai/state.py`), readable by anyone with access to that user's profile. On Windows that folder is under `%APPDATA%`, the roaming profile, which a domain can sync between computers. Set `BRISARTAI_STATE_DIR` to keep it somewhere else.
- **No sandbox.** BrisartAI runs with the privileges of the user who launched it and reads whatever local files that user points it at.

## Air-Gapped Use

Internet research is optional and can be disabled entirely (`auto_web_research = false`, and avoiding the desktop Research Web action, `cli.py research`, and `cli.py ask --web`). In that configuration BrisartAI makes no outbound network requests and operates purely over local files and notes.
