# AirGapped-Web

**Build connected knowledge without connectivity.**

AirGapped-Web is a tiny HTML/CSS/JavaScript app for browsing preserved website records entirely from local files — and now for **crawling live sites into an offline database** you can browse without the internet, then **back that database up to a single portable file**.

> If information matters, you should be able to browse it without the Internet.

---

## What it does

- **Crawls a website** (the Archiver) and stores every reachable page + its metadata into an offline database
- Preserves websites as local files or inline captured copies you can keep forever
- Browses them through a clean, searchable interface
- Records metadata (websites, snapshots, pages, imports)
- **Backs up and restores** the whole crawled database as one portable `.json` file
- Validates its own catalog every time you open it
- Runs from a `file://` path — no install, no build step, no dependencies

---

## Quick start

1. Download or clone the folder.
2. Double-click **`index.html`**.
3. Open the **Archiver**, paste a URL, and crawl.

No installation. No server. No database engine. No dependencies.

---

## The Archiver (offline "Wayback Machine")

Think of it as a local, offline-first version of the Internet Archive's Wayback Machine:

1. Go to **Archiver**, enter a start URL, choose a page limit, and start the crawl.
2. It fetches pages with the browser's built-in `fetch`, parses them with `DOMParser`, follows same-domain links, and extracts title / description / text / links.
3. Every page is written into the offline database (browser `localStorage`) with its HTML stored **inline**, so it opens later with **no internet**.
4. Crawled sites instantly appear under **Websites**, **Search**, and the **Snapshot Viewer**.

**Honest limits (browser reality):**

- Browsers block cross-origin `fetch` for many public sites (CORS). When that happens, use **Manual Capture**: open the page, copy its source, paste it in, and archive that page offline.
- Crawling reaches the network once (to capture). Everything after is fully offline.
- Assets like images/CSS on remote pages may not render offline unless the site allowed them to be fetched; text, structure, and metadata always persist.

---

## Backup & Restore

The crawled database lives in your browser's local storage, so it is cleared with your browsing data and does not follow you to another machine. The **Backup & Restore** panel on the Archiver page fixes that:

- **Download Full Backup (.json)** writes the entire database to one portable file.
- Restore it anywhere with **Merge** (adds only new records) or **Replace** (overwrites the local database).
- A live **storage-usage** line shows how close a crawl is to the browser's limit.

Backups move entirely offline — carrying the file is the sync. For permanent, unbounded storage, use **Export to Files (.zip)** into the file-backed catalog.

---

## A 60-second tour

| Page | What you'll see |
|------|-----------------|
| **Home** | Archive summary + live catalog validation |
| **Websites** | Every preserved/crawled website as a card |
| **Website** | One site's snapshots, pages, and imports |
| **Archiver** | Crawl a site, plus Backup & Restore |
| **Snapshot** | The captured website, viewable offline |
| **Page** | A single preserved page + its metadata |
| **Search** | Instant local search across all metadata |
| **Imports** | A record of how each site entered the archive |
| **Site Map** | A flat index of everything in the archive |

---

## Where things live

```text
index.html      ->  launch here
app/            ->  the application (styles, code, pages)
archive/        ->  your content (metadata + preserved sites)
docs/           ->  the deeper docs (architecture, changelog, import workflow)
```

The only Markdown file at the repository root is `README.md`. All other
documentation — `architecture.md`, `CHANGELOG.md`, and `import-workflow.md` —
lives under `docs/`.

### Design goals

Offline, portable, auditable, human-readable, and dependency-free. No servers, databases, build tools, or package managers. The Archiver reaches the network only during a crawl; browsing is always offline.

### Status

Experimental. Expect frequent iteration.
