# AirGapped-Web Import Workflow

There are now two ways to add a website to AirGapped-Web, plus a Backup & Restore
path for moving the whole crawled database between browsers or machines.

---

## Option A — Automatic (Archiver)

1. Open **Archiver** (`app/pages/archiver.html`).
2. Enter a start URL, a page limit, and whether to stay on the same domain.
3. Click **Start Crawl & Archive**. Captured pages are written into the offline database (browser localStorage) and appear instantly under Websites, Search, and the Snapshot Viewer.
4. If a public site is CORS-blocked, use **Manual Capture**: open the page in your browser, copy its source, paste it with the URL, and archive that single page.

Crawled sites can be removed from the Website page ("Delete This Crawled Site") or from the Archiver's "Stored Archives" list.

---

## Option B — Manual file-backed import

For permanent, file-backed archives that live in the repo itself:

1. Place preserved files under `archive/records/<site-id>/<date>/`.
2. Add website, snapshot, page, and import records to `archive/catalog/archive-data.js`.
3. Open `index.html` and confirm **Catalog status: Valid**.

### Catalog path rule

Stored paths are archive-relative and must begin with `records/`. Do not store `archive/...`, parent-directory traversal, absolute machine paths, or remote URLs.

### Record schema

- **website**: id, title, original_url, domain, description, tags, snapshot_ids
- **snapshot**: id, website_id, label, captured, root_path, description, page_ids
- **page**: id, website_id, snapshot_id, title, original_url, local_path, summary, captured, tags, text
- **import**: id, website_id, snapshot_id, label, imported, source_type, source_note, root_path, status

Crawler records additionally use `page.inline_html` (offline bytes) and an `inline` flag on snapshots/imports.

---

## Backup & Restore (moving the crawled database)

The crawled database (Option A) lives only in the browser's local storage. To
move it, keep it safe, or recover it after clearing browser data, use the
**Backup & Restore** panel on the Archiver page.

1. **Download Full Backup (.json)** writes the entire overlay database — every
   crawled website, snapshot, page, and import — to a single portable file named
   `airgapped-web-backup-<date>.json`.
2. On another machine or browser, choose that file under **Restore from a backup
   file**, then:
   - **Merge into Database** — keeps whatever is already there and adds only
     records with new IDs (duplicates are skipped and counted), or
   - **Replace Database** — overwrites the whole local database with the backup.
3. The panel also shows a running **storage-usage** line (record counts and
   bytes stored) so you can watch how close a large crawl is to the browser's
   storage limit.

Backup files are plain JSON and move entirely offline — there is no server and
no sync service; carrying the file *is* the sync mechanism. For permanent,
unbounded storage, prefer **Export to Files (.zip)** into the file-backed catalog
(Option B).
