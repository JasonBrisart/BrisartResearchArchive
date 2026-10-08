# AirGapped-Web Architecture Reference

Technical reference for AirGapped-Web v0.5.0.
For project purpose and startup instructions, see ../README.md.
For the content registration procedure, see import-workflow.md.

---

## 1. Design Constraints

| Constraint | Consequence |
|---|---|
| Runs from file:// | No server-side application layer is required |
| No dependencies | Pure browser HTML, CSS, and JavaScript |
| Fully auditable | Small, readable, single-purpose modules |
| Portable | Catalog paths are archive-relative, never machine-specific |
| Long-lived | Open standards and local files remain the foundation |

The Archiver reaches the network only when the user runs a crawl; all browsing is offline.

---

## 2. Data Sources

The application reads from two merged sources via `core.getData()`:

1. **Base catalog** — `archive/catalog/archive-data.js` (`window.AGW_DATA`). Hand-authored, file-backed records.
2. **Overlay database** — browser `localStorage` key `agw_archive_overlay_v1`. Written by the Archiver. Holds crawled websites, snapshots, pages, and imports.

`getData()` concatenates the two so every view (Websites, Search, Snapshot, etc.) sees both without any special-casing.

### Storage API (core.js)

| Function | Purpose |
|---|---|
| `readOverlay()` | Read the localStorage database (always shaped into 4 arrays) |
| `saveArchivedSite(bundle)` | Append a crawled website+snapshot+pages+import |
| `deleteArchivedWebsite(id)` | Remove a crawled site and its records |
| `clearOverlay()` | Wipe all crawled sites |
| `isArchivedWebsite(id)` | Whether a website came from the overlay |
| `overlayStats()` | Record counts + approximate byte footprint |
| `exportOverlay()` | Build a versioned backup envelope of the whole overlay |
| `importOverlay(backup, mode)` | Restore a backup (merge or replace) |

---

## 3. The Archiver (archiver.js / archiver.html)

Pipeline:

```
start URL
-> normalizeUrl()          add scheme if missing
-> crawl() (BFS queue)     fetch() + DOMParser, same-domain link discovery, page cap
-> parseHtml()             title, meta description, text, links (zero dependency)
-> buildBundle()           website + snapshot + pages(+inline_html) + import records
-> core.saveArchivedSite() persist into the overlay database
```

- **Page bytes** are stored on each page record as `inline_html`, so snapshots render offline via `<iframe srcdoc>`.
- **CORS fallback**: `crawl()` logs and skips pages the browser refuses to fetch; the Manual Capture panel lets the user paste page source to archive a single page.
- **Caps**: page count is clamped to 1–100 to respect localStorage limits.

Testable internals are exposed on `AGW._archiver`.

---

## 4. Backup & Restore (backup.json)

The overlay database lives only in `localStorage`, which is per-browser and is
cleared with browsing data. Backup & Restore makes the whole database portable
without adding a server or any dependency.

### Backup envelope

`exportOverlay()` wraps the current overlay in a self-describing envelope:

```json
{
  "format": "airgapped-web-overlay-backup",
  "schema": 1,
  "exported": "<ISO-8601 timestamp>",
  "app_version": "<archive.version>",
  "overlay": { "websites": [], "snapshots": [], "pages": [], "imports": [] }
}
```

The Archiver downloads it as `airgapped-web-backup-<date>.json`.

### Restore modes

`importOverlay(backup, mode)` accepts either the full envelope **or** a bare
overlay object, and returns `{ ok, error, mode, added, skipped }`:

- **merge** (default) — keeps existing records and appends only records whose IDs
  are not already present; duplicates are counted in `skipped`.
- **replace** — overwrites the whole overlay with the backup's records.

Restore never partially writes: an unknown format, non-JSON input, or a
localStorage quota failure returns `ok: false` with a message and leaves the
existing database untouched.

### Storage indicator

`overlayStats()` reports record counts and the serialized byte size of the
overlay, surfaced on the Archiver page so operators can gauge how close a crawl
is to the browser quota.

---

## 5. Record Schema Additions

Backward compatible additions used by crawled records:

- **page.inline_html** — the captured HTML string. `core.pageHasContent()` treats a page as renderable if it has `inline_html` OR a safe `local_path`.
- **snapshot.inline / import.inline** — flags that suppress the "invalid local root path" warning for crawler records (which are database-backed, not file-backed).

The manual file-backed schema is unchanged.

---

## 6. Rendering Inline Content

- `snapshot-viewer.js` prefers an inline home page and renders it with `<iframe srcdoc="..." sandbox="allow-popups">` (no script execution). Otherwise it falls back to the original local-file iframe.
- `page-detail.js` renders `inline_html` the same way when present.

---

## 7. Security Model

- All metadata is escaped with `escapeHtml()` before insertion.
- Inline captured HTML is rendered in a sandboxed iframe **without** `allow-scripts` and **without** `allow-same-origin`, so archived pages cannot execute scripts or reach the host app.
- File-backed snapshots keep their original `allow-same-origin allow-forms allow-popups` sandbox.
- Backup files carry only the same metadata and already-sandboxed captured HTML the app already stores; restore reuses the same escaping and sandboxed rendering paths, so importing a file grants a page no new capability.

---

## 8. Architectural Boundary

Still a static browser application: no server, no database engine, no build system, no package manager. The overlay "database" is plain JSON in localStorage, and its backup is plain JSON on disk. The only network activity is user-initiated crawling.
