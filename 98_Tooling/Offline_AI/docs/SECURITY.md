# Security

## Local data

The SQLite index stores imported document text and notes unencrypted under the current user's profile. On Windows the default is `%APPDATA%\Brisart Research Archive\BrisartAI`. Restrict filesystem access appropriately; use `BRISARTAI_STATE_DIR` to choose a different location.

## Input boundary

BrisartAI parses user-selected local files, including potentially malformed Office, OpenDocument, HTML and PDF content. Readers are best-effort and do not sandbox untrusted files. Native decompression comes from the separately maintained `94_Native_API's/Official` project.

## Network boundary

BrisartAI has no internet search command, GUI action, automatic web setting, crawler, provider client or HTTP fetcher. Its local-file readers can still process URLs as text and HTML documents saved on disk. Historical web rows in a preexisting database are preserved, not used as answer evidence.

## Reporting

When reporting a vulnerability, provide a reproducible input, the affected module and environment, and avoid sending confidential indexed content. Coordinate disclosure before publishing exploit details.
