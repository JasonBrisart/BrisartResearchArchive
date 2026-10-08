# Changelog
All notable changes to AirGapped-Web are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.5.0] - 2026-09-10

The largest release since the Archiver landed. **0.5.0 makes the offline crawled
database portable** — the whole thing can now travel as a single self-describing
JSON file, restored anywhere, fully offline, with zero dependencies — and it
**repairs the documentation layout** that had drifted out of sync during the
0.5.0 development cycle. Until now, crawled sites lived only in the browser's
`localStorage` overlay: durable within one browser, but lost on "clear browsing
data" and impossible to carry to another machine or browser without exporting
each site to a zip and hand-pasting it into the file-backed catalog. This release
closes that gap and consolidates every document under a single canonical
`docs/` tree.

### Added — Backup & Restore (portable JSON)

- **Download Full Backup (.json).** A new panel on the Archiver page serializes
  the whole overlay database (all crawled websites, snapshots, pages, and
  imports) into one versioned JSON file named `airgapped-web-backup-<date>.json`.
  The file carries a self-describing envelope (`format`, `schema`, `exported`
  timestamp, `app_version`) so future versions can recognize and migrate it.
- **Restore from a backup file** with two explicit modes:
  - **Merge** — keeps the current database and adds only records whose IDs are
    not already present; duplicate IDs are skipped and counted.
  - **Replace** — overwrites the entire local database with the backup (guarded
    by a confirmation prompt).
- **Live storage-usage indicator.** The Backup & Restore panel shows the current
  record counts and the approximate number of bytes the overlay occupies in
  `localStorage`, so operators can see how close they are to the browser quota
  before a large crawl.
- **New `core.js` API:** `exportOverlay()` (build the backup envelope),
  `importOverlay(backup, mode)` (merge/replace with an added/skipped report and
  quota-safe write), and `overlayStats()` (counts + byte footprint).

### Changed

- **`core.js`** now centralizes overlay shaping in a `sanitizeOverlay()` helper
  used by `readOverlay()`, restore, and stats, guaranteeing the four record
  arrays are always well-formed regardless of what a backup file contains.
- **Archiver page** gains the Backup & Restore section beneath Stored Archives;
  every crawl, capture, delete, and restore refreshes the storage-usage line.
- **`archiver.js`** adds `formatBytes()` and a `downloadText()` helper used to
  build and deliver the JSON backup entirely client-side.
- **Catalog version** bumped from `0.4.0` to `0.5.0` in
  `archive/catalog/archive-data.js`, with an updated archive description that
  mentions portable backups.

### Fixed

- **Documentation layout drift (the big one).** During the 0.5.0 cycle the docs
  had been duplicated at the repository root *and* under `docs/`, then partially
  reverted, leaving the tree in an inconsistent state where the root copies and
  the `docs/` copies disagreed on version and content. This release removes the
  root-level `architecture.md`, `CHANGELOG.md`, and `import-workflow.md`
  duplicates entirely and establishes `docs/` as the single canonical home for
  all three, all updated to 0.5.0. `README.md` remains the only Markdown file at
  the root.
- **Feature regression recovered.** The Backup & Restore capability that had been
  reverted out of `core.js` and `archiver.js` during the layout cleanup is fully
  restored and re-applied on top of the current tree, so no 0.5.0 work is lost.
- **Restore robustness.** `importOverlay()` accepts either a full backup
  envelope or a bare overlay object, rejects unknown formats and non-JSON input
  with a clear message, and never partially writes: a `localStorage` quota
  failure during restore is caught and reported instead of corrupting the
  database.

### Security

- Backup files contain only the same catalog metadata and already-sandboxed
  captured HTML the app stores locally; import reuses the existing escaping and
  sandboxed-iframe rendering paths, so restoring a file grants a page no new
  ability to execute scripts or reach the host app.

### Docs

- `README.md`, `docs/architecture.md`, and `docs/import-workflow.md` now document
  the backup envelope format, the merge/replace restore modes, and the
  storage-usage indicator. `docs/architecture.md` gains a dedicated
  "4. Backup & Restore" section and an expanded security note covering imported
  files. `docs/import-workflow.md` gains a "Backup & Restore (moving the crawled
  database)" section alongside the automatic and manual import paths.

---

## [0.4.0] - 2026-08-23
A large release that turns AirGapped-Web from a passive, file-backed viewer
(0.3.1) into an active offline web archiver: it can crawl a live site, inline
its assets, store everything in an offline database, browse it with no internet,
and export a crawled site back out to real repository files. Everything below
landed in this single 0.4.0 cycle on top of 0.3.1.

### Added — Website Archiver (offline crawler)
- **New module `app/modules/archiver.js` and page `app/pages/archiver.html`.**
  An in-browser crawler that captures a website into the offline database —
  conceptually an offline-first Wayback Machine.
  - Breadth-first crawl using the browser's built-in `fetch` + `DOMParser`
    (zero dependencies). Follows same-domain links from each captured page.
  - Configurable **maximum page count (1–100)** and a **"stay on the same
    domain"** toggle.
  - Extracts **title**, **meta description**, **visible text** (for search),
    and **outbound links** (for the crawl frontier) from every page.
  - **Live crawl log** panel that streams each fetch, capture, link count,
    asset-inlining result, and any CORS/skip messages.
  - **Manual Capture fallback** for CORS-blocked public sites: paste a page URL
    and its HTML source and archive that single page offline.
  - **Stored Archives manager**: list every crawled site with page counts, and
    Open / Export / Delete / Clear-all controls.

- **Base64 asset inlining (offline rendering fidelity).**
  - New **"Inline images & CSS as base64"** option (on by default).
  - During capture, `<img src>` assets are fetched and rewritten as `data:` URIs
    via `FileReader`, and `<link rel="stylesheet">` files are fetched and inlined
    as `<style>` blocks, so captured pages **look right offline**, not just read
    as text.
  - Inlining is best-effort and CORS-aware: assets that can't be fetched are
    skipped and counted in the log rather than breaking the capture.

- **Export a crawled site back to real repository files.**
  - New **"Export to Files (.zip)"** action on both the Archiver's Stored
    Archives list and the Website detail page.
  - Produces a downloadable `.zip` containing `records/<site>/<date>/*.html`
    (rebuilt from the captured HTML) plus a `catalog-snippet.js` with the
    website/snapshot/page/import objects (in **file-backed form**, without the
    inline HTML) ready to paste into `archive/catalog/archive-data.js`, and a
    `README-EXPORT.txt` with step-by-step instructions.
  - This bridges the automatic overlay database and the permanent, file-backed
    manual import workflow.

- **New module `app/modules/zip.js`** — a tiny, dependency-free ZIP writer
  (STORE method, CRC-32, UTF-8 filenames, correct local + central directory
  records and EOCD) used to build the export download entirely in the browser.

- **Offline database overlay in `core.js`.**
  - Crawled sites are persisted to browser `localStorage` under
    `agw_archive_overlay_v1` and **merged** into `core.getData()`, so they
    appear immediately under Websites, Search, and the Snapshot Viewer with no
    file editing and no page reload logic elsewhere.
  - New storage API: `readOverlay()`, `saveArchivedSite()` (quota-safe, returns
    success), `deleteArchivedWebsite()`, `clearOverlay()`, `isArchivedWebsite()`.

- **Inline content rendering across viewers.**
  - `snapshot-viewer.js` now prefers a captured inline home page and renders it
    with `<iframe srcdoc>`; it falls back to the original local-file iframe for
    file-backed snapshots.
  - `page-detail.js` renders a page's captured `inline_html` the same way when
    present.
  - Both inline frames use a locked-down sandbox (**no** `allow-scripts`, **no**
    `allow-same-origin`) so archived pages can't execute scripts or reach the
    host app.

### Changed
- **`core.getData()`** merges the base file catalog (`window.AGW_DATA`) with the
  localStorage overlay database on every read.
- **`validateData()`** now understands inline records: a page is valid if it has
  `inline_html` **or** a safe `local_path`; crawler snapshots/imports carry an
  `inline` flag that suppresses the "invalid local root path" warning (they are
  database-backed, not file-backed).
- **New `core.pageHasContent()`** helper centralizes the "is this page
  renderable?" check.
- **Navigation** — an **Archiver** link was added to the nav bar on every page
  and on `index.html`, plus a Start-Here entry on the home page. Imports and
  Site Map now reference the Archiver.
- **`website-list.js` / `website-detail.js`** — crawled sites show a
  **"crawled"** badge; the detail page gains **Export to Files** and
  **Delete This Crawled Site** actions.
- **`import-registry.js`** — the Import Workflow panel now documents both the
  automatic (Archiver) and manual (file-backed) paths.
- **Catalog version** bumped from `0.3.1` to `0.4.0` in
  `archive/catalog/archive-data.js`, with an updated archive description.
- **Docs rewritten** — `README.md`, `docs/architecture.md`, and
  `docs/import-workflow.md` now cover the Archiver, the overlay database,
  inline assets, export, and the honest browser limits.

### Fixed
- **Duplicate page filenames.** `buildBundle()` now de-duplicates generated
  page filenames (e.g. two pages with the same title no longer collide on
  `index.html` / `<title>.html`); each gets a unique `-N` suffix.
- **Silent storage failures.** `saveArchivedSite()`/`writeOverlay()` now catch
  `localStorage` quota (and other write) errors and return a success flag; the
  Archiver reports "storage quota exceeded" and suggests fewer pages or turning
  off image inlining, instead of failing silently.
- **Home-page selection for snapshots.** The Snapshot Viewer now explicitly
  picks the first inline page as the offline home view rather than relying on a
  file-path heuristic that never matched crawled records.
- **Page-record links in the Snapshot Viewer** no longer render a broken
  "Open Preserved File" link for inline (database-backed) pages that have no
  on-disk file.
- **Metadata escaping** is applied consistently to all crawled titles,
  descriptions, URLs, and tags before they are inserted into the DOM.

### Security
- Captured HTML is rendered only in a sandboxed iframe **without** script
  execution and **without** same-origin access to the host application.
- The ZIP export is generated fully client-side; nothing is uploaded anywhere.

### Notes / Known limits (browser reality)
- **CORS:** browsers block cross-origin `fetch` for many public sites, so a
  from-`file://` crawler cannot silently crawl arbitrary public sites the way a
  server-side archiver can. The **Manual Capture** panel covers those cases.
- **Asset inlining** is likewise subject to CORS; images/CSS that refuse
  cross-origin fetches are skipped (text, structure, and metadata always
  persist).
- **Storage size:** base64 inlining increases the stored size; very large crawls
  can hit the browser's `localStorage` quota. Use **Export to Files** for
  permanent, unbounded storage in the repo.
- Crawling and inlining touch the network **once** (during capture); all
  browsing afterward is fully offline.
- Fully backward compatible with the existing file-backed manual import workflow
  and the original record schema. Zero dependencies, no build step, still runs
  directly from `file://`.
