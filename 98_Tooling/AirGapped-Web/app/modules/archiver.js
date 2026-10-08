(function () {
    "use strict";
    window.AGW = window.AGW || {};
    const core = AGW.core;
    // ---- URL helpers -----------------------------------------------------
    function normalizeUrl(raw) {
        const value = String(raw || "").trim();
        if (!value) return "";
        if (/^https?:\/\//i.test(value)) return value;
        if (/^\/\//.test(value)) return "https:" + value;
        return "https://" + value;
    }
    function parseUrl(u){ try { return new URL(u); } catch (e) { return null; } }
    function sameDomain(a, b){
        const ua = parseUrl(a), ub = parseUrl(b);
        return !!(ua && ub && ua.hostname === ub.hostname);
    }
    function resolveLink(href, base){
        try { const u = new URL(href, base); u.hash = ""; return u.href; } catch (e) { return ""; }
    }
    function slugify(value){
        return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-+|-+$)/g, "").slice(0, 60) || "site";
    }
    function today(){
        const d = new Date();
        const p = n => String(n).padStart(2, "0");
        return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
    }
    // Human-readable byte size for the storage-usage indicator.
    function formatBytes(n){
        if (!n || n < 1024) return (n || 0) + " B";
        if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
        return (n / (1024 * 1024)).toFixed(2) + " MB";
    }
    // Trigger a browser download of a text blob (used for the JSON backup).
    function downloadText(filename, text, mime){
        const blob = new Blob([text], { type: mime || "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename || "download.txt";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    // ---- Base64 asset inlining ------------------------------------------
    // Fetch a binary asset and return a data: URI. Subject to CORS like any
    // browser fetch; failures are swallowed so capture still succeeds.
    async function fetchAsDataUri(url){
        const res = await fetch(url, { redirect: "follow" });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const blob = await res.blob();
        return await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error("read failed"));
            reader.readAsDataURL(blob);
        });
    }
    // Walk a parsed document, inline <img src>, <link rel=stylesheet>, and
    // rewrite them in place. Returns counts for the log.
    async function inlineAssets(doc, pageUrl, log){
        let imgOk = 0, imgFail = 0, cssOk = 0, cssFail = 0;
        const imgs = Array.from(doc.querySelectorAll("img[src]"));
        for (const img of imgs){
            const src = img.getAttribute("src");
            if (!src || src.startsWith("data:")) continue;
            const abs = resolveLink(src, pageUrl);
            if (!/^https?:\/\//i.test(abs)) continue;
            try { img.setAttribute("src", await fetchAsDataUri(abs)); imgOk++; }
            catch (e) { imgFail++; }
        }
        const links = Array.from(doc.querySelectorAll('link[rel~="stylesheet"][href]'));
        for (const link of links){
            const href = link.getAttribute("href");
            if (!href) continue;
            const abs = resolveLink(href, pageUrl);
            if (!/^https?:\/\//i.test(abs)) continue;
            try {
                const res = await fetch(abs, { redirect: "follow" });
                if (!res.ok) throw new Error("HTTP " + res.status);
                const cssText = await res.text();
                const style = doc.createElement("style");
                style.textContent = cssText;
                link.parentNode.replaceChild(style, link);
                cssOk++;
            } catch (e) { cssFail++; }
        }
        if (imgs.length || links.length){
            log("    assets: " + imgOk + "/" + imgs.length + " images, " +
                cssOk + "/" + links.length + " stylesheets inlined" +
                ((imgFail + cssFail) ? " (" + (imgFail + cssFail) + " blocked)" : ""));
        }
        return { imgOk, imgFail, cssOk, cssFail };
    }
    // ---- HTML parsing ----------------------------------------------------
    function extractMeta(doc, pageUrl){
        const titleEl = doc.querySelector("title");
        const title = titleEl ? (titleEl.textContent || "").trim() : "";
        const metaDesc = doc.querySelector('meta[name="description"]');
        const description = metaDesc ? (metaDesc.getAttribute("content") || "").trim() : "";
        const body = doc.body ? (doc.body.textContent || "") : "";
        const text = body.replace(/\s+/g, " ").trim().slice(0, 4000);
        const links = [];
        const anchors = doc.querySelectorAll("a[href]");
        for (const a of anchors){
            const abs = resolveLink(a.getAttribute("href"), pageUrl);
            if (/^https?:\/\//i.test(abs)) links.push(abs);
        }
        return { title, description, text, links };
    }
    function serializeDoc(doc){
        const dt = doc.doctype ? "<!DOCTYPE html>\n" : "";
        return dt + (doc.documentElement ? doc.documentElement.outerHTML : "");
    }
    // Parse text into a doc, optionally inline assets, return meta + final html.
    async function processPage(htmlText, pageUrl, inline, log){
        const doc = new DOMParser().parseFromString(htmlText, "text/html");
        const meta = extractMeta(doc, pageUrl);
        if (inline){
            try { await inlineAssets(doc, pageUrl, log); }
            catch (e) { log("    asset inlining error: " + e.message); }
        }
        const html = inline ? serializeDoc(doc) : htmlText;
        return { meta, html };
    }
    async function fetchPage(url){
        const res = await fetch(url, { redirect: "follow" });
        if (!res.ok) throw new Error("HTTP " + res.status);
        return await res.text();
    }
    // ---- Build catalog records from a completed crawl --------------------
    function buildBundle(startUrl, crawled){
        const host = (parseUrl(startUrl) || {}).hostname || "site";
        const date = today();
        const siteSlug = slugify(host);
        const websiteId = "website-" + siteSlug + "-" + Date.now().toString(36);
        const snapshotId = "snapshot-" + siteSlug + "-" + date;
        const root = "records/" + siteSlug + "/" + date + "/";
        const usedNames = {};
        const pages = crawled.map((c, idx) => {
            const isHome = idx === 0;
            let base = isHome ? "index" : (slugify(c.title || ("page-" + idx)));
            // Ensure unique filenames (bug fix: title collisions).
            let name = base + ".html";
            let n = 1;
            while (usedNames[name]) { name = base + "-" + n + ".html"; n++; }
            usedNames[name] = true;
            return {
                id: "page-" + siteSlug + "-" + idx,
                website_id: websiteId,
                snapshot_id: snapshotId,
                title: c.title || c.url,
                original_url: c.url,
                local_path: root + name,
                inline_html: c.html,
                summary: c.description || (c.text ? c.text.slice(0, 160) : "Archived page."),
                captured: date,
                tags: ["archived", host],
                text: c.text || ""
            };
        });
        const website = {
            id: websiteId,
            title: (crawled[0] && crawled[0].title) || host,
            original_url: startUrl,
            domain: host,
            description: (crawled[0] && crawled[0].description) || ("Archived copy of " + host + "."),
            tags: ["archived", host, "offline"],
            snapshot_ids: [snapshotId]
        };
        const snapshot = {
            id: snapshotId,
            website_id: websiteId,
            label: "Crawl of " + host + " (" + date + ")",
            captured: date,
            root_path: root,
            inline: true,
            description: "Automatically crawled snapshot of " + host + ". " + pages.length + " page(s) captured.",
            page_ids: pages.map(p => p.id)
        };
        const importRecord = {
            id: "import-" + siteSlug + "-" + date + "-" + Date.now().toString(36),
            website_id: websiteId,
            snapshot_id: snapshotId,
            label: "Crawler import of " + host,
            imported: date,
            source_type: "in-browser-crawler",
            inline: true,
            source_note: "Captured with the AirGapped-Web Archiver from " + startUrl + ".",
            root_path: root,
            status: "active"
        };
        return { website, snapshot, pages, import: importRecord };
    }
    // ---- Export a stored site to real repo files (zip download) ----------
    // Produces records/<slug>/<date>/*.html (from inline_html) plus a
    // catalog-snippet.js to paste into archive/catalog/archive-data.js.
    function exportBundleToZip(website){
        const overlay = core.readOverlay();
        const snapshots = overlay.snapshots.filter(s => s.website_id === website.id);
        const pages = overlay.pages.filter(p => p.website_id === website.id);
        const imports = overlay.imports.filter(i => i.website_id === website.id);
        if (!pages.length){ return false; }
        const files = [];
        // Write each page's HTML to its notional local_path.
        for (const p of pages){
            const path = core.normalizeLocalPath(p.local_path);
            files.push({ name: path, text: p.inline_html || "<!-- no captured html -->" });
        }
        // Build catalog objects WITHOUT inline_html (file-backed form).
        const stripPage = p => ({
            id: p.id, website_id: p.website_id, snapshot_id: p.snapshot_id,
            title: p.title, original_url: p.original_url, local_path: p.local_path,
            summary: p.summary, captured: p.captured, tags: p.tags, text: p.text
        });
        const stripSnap = s => ({
            id: s.id, website_id: s.website_id, label: s.label, captured: s.captured,
            root_path: s.root_path, description: s.description, page_ids: s.page_ids
        });
        const stripImp = i => ({
            id: i.id, website_id: i.website_id, snapshot_id: i.snapshot_id, label: i.label,
            imported: i.imported, source_type: i.source_type, source_note: i.source_note,
            root_path: i.root_path, status: i.status
        });
        const snippet =
            "// Paste these into the matching arrays in archive/catalog/archive-data.js\n" +
            "// websites:\n" + JSON.stringify(website, null, 4) + ",\n\n" +
            "// snapshots:\n" + snapshots.map(s => JSON.stringify(stripSnap(s), null, 4)).join(",\n") + ",\n\n" +
            "// pages:\n" + pages.map(p => JSON.stringify(stripPage(p), null, 4)).join(",\n") + ",\n\n" +
            "// imports:\n" + imports.map(i => JSON.stringify(stripImp(i), null, 4)).join(",\n") + ",\n";
        files.push({ name: "catalog-snippet.js", text: snippet });
        files.push({ name: "README-EXPORT.txt", text:
            "AirGapped-Web export for: " + (website.title || website.id) + "\n" +
            "Original URL: " + (website.original_url || "") + "\n\n" +
            "1. Copy the 'records/...' folder into your project's archive/ directory.\n" +
            "2. Open catalog-snippet.js and paste each block into the matching array\n" +
            "   in archive/catalog/archive-data.js.\n" +
            "3. Open index.html and confirm Catalog status: Valid.\n" });
        const zipName = slugify(website.domain || website.title || "site") + "-export.zip";
        AGW.zip.download(files, zipName);
        return true;
    }
    // ---- The crawl loop --------------------------------------------------
    async function crawl(startUrl, opts, log){
        const maxPages = Math.max(1, Math.min(opts.maxPages || 10, 100));
        const sameOnly = opts.sameDomainOnly !== false;
        const inline = !!opts.inlineAssets;
        const seen = new Set();
        const queue = [startUrl];
        const crawled = [];
        while (queue.length && crawled.length < maxPages){
            const url = queue.shift();
            if (seen.has(url)) continue;
            seen.add(url);
            log("Fetching: " + url);
            let html;
            try {
                html = await fetchPage(url);
            } catch (e) {
                log("  \u2717 Could not fetch (" + e.message + "). Likely CORS-blocked or offline.");
                continue;
            }
            const processed = await processPage(html, url, inline, log);
            crawled.push({
                url, html: processed.html,
                title: processed.meta.title, description: processed.meta.description, text: processed.meta.text
            });
            log("  \u2713 Captured: " + (processed.meta.title || url) + " (" + processed.meta.links.length + " links found)");
            for (const link of processed.meta.links){
                if (seen.has(link) || queue.includes(link)) continue;
                if (sameOnly && !sameDomain(link, startUrl)) continue;
                queue.push(link);
            }
        }
        return crawled;
    }
    // ---- UI --------------------------------------------------------------
    function renderArchiver(targetId){
        const target = document.getElementById(targetId);
        if (!target) return;
        target.innerHTML = `
            <section class="panel">
                <h2>Website Archiver</h2>
                <p>Crawl a website and store every reachable page &mdash; with its metadata &mdash; directly into your offline database. Captured pages then appear under <a href="websites.html">Websites</a>, <a href="search.html">Search</a>, and the Snapshot Viewer, and open with no internet connection.</p>
                <label for="agw-arc-url">Start URL</label>
                <input id="agw-arc-url" class="search-box" type="url" autocomplete="off" placeholder="https://example.com">
                <label for="agw-arc-max">Maximum pages to crawl (1&ndash;100)</label>
                <input id="agw-arc-max" class="search-box" type="number" min="1" max="100" value="10">
                <p>
                    <label style="display:inline;font-weight:normal;">
                        <input id="agw-arc-same" type="checkbox" checked> Stay on the same domain
                    </label>
                </p>
                <p>
                    <label style="display:inline;font-weight:normal;">
                        <input id="agw-arc-inline" type="checkbox" checked> Inline images &amp; CSS as base64 (view offline)
                    </label>
                </p>
                <p>
                    <button id="agw-arc-start" class="button" type="button">Start Crawl &amp; Archive</button>
                </p>
                <p class="empty" id="agw-arc-note">Note: browsers block cross-origin crawling of many public sites. If a fetch fails, use the manual capture below.</p>
            </section>
            <section class="panel">
                <h2>Crawl Log</h2>
                <pre id="agw-arc-log" style="white-space:pre-wrap;background:#fafafa;border:1px solid var(--border);border-radius:6px;padding:12px;max-height:320px;overflow:auto;">Idle.</pre>
            </section>
            <section class="panel">
                <h2>Manual Capture (fallback)</h2>
                <p>If a site is CORS-blocked, open it in your browser, copy its page source (Ctrl+U &rarr; Ctrl+A &rarr; Ctrl+C), paste it here with the page URL, and archive that single page offline.</p>
                <label for="agw-man-url">Page URL</label>
                <input id="agw-man-url" class="search-box" type="url" autocomplete="off" placeholder="https://example.com/">
                <label for="agw-man-html">Page source (HTML)</label>
                <textarea id="agw-man-html" class="search-box" style="height:160px;font-family:monospace;" placeholder="Paste full page HTML here..."></textarea>
                <p><button id="agw-man-save" class="button" type="button">Archive This Page</button></p>
            </section>
            <section class="panel">
                <h2>Stored Archives</h2>
                <div id="agw-arc-stored"></div>
            </section>
            <section class="panel">
                <h2>Backup &amp; Restore</h2>
                <p>Your crawled sites live only in this browser's local database. Back the whole thing up to a single portable <code>.json</code> file so you can move it to another machine or browser, keep it on a USB stick, or recover after clearing browser data &mdash; all fully offline.</p>
                <p id="agw-backup-stats" class="card-meta"></p>
                <p><button id="agw-backup-export" class="button" type="button">Download Full Backup (.json)</button></p>
                <hr>
                <label for="agw-backup-file">Restore from a backup file</label>
                <input id="agw-backup-file" class="search-box" type="file" accept=".json,application/json">
                <p>
                    <button id="agw-backup-merge" class="button" type="button">Merge into Database</button>
                    <button id="agw-backup-replace" class="button" type="button">Replace Database</button>
                </p>
                <p class="empty">Merge keeps your current sites and adds only records with new IDs. Replace overwrites the entire local database with the backup.</p>
            </section>`;
        const urlInput = document.getElementById("agw-arc-url");
        const maxInput = document.getElementById("agw-arc-max");
        const sameInput = document.getElementById("agw-arc-same");
        const inlineInput = document.getElementById("agw-arc-inline");
        const startBtn = document.getElementById("agw-arc-start");
        const logEl = document.getElementById("agw-arc-log");
        const manUrl = document.getElementById("agw-man-url");
        const manHtml = document.getElementById("agw-man-html");
        const manSave = document.getElementById("agw-man-save");
        const storedEl = document.getElementById("agw-arc-stored");
        const backupStatsEl = document.getElementById("agw-backup-stats");
        const backupExportBtn = document.getElementById("agw-backup-export");
        const backupFileInput = document.getElementById("agw-backup-file");
        const backupMergeBtn = document.getElementById("agw-backup-merge");
        const backupReplaceBtn = document.getElementById("agw-backup-replace");
        let logBuffer = "";
        function log(line){ logBuffer += line + "\n"; logEl.textContent = logBuffer; logEl.scrollTop = logEl.scrollHeight; }
        function resetLog(){ logBuffer = ""; logEl.textContent = ""; }
        function refreshBackupStats(){
            if (!backupStatsEl) return;
            const st = core.overlayStats();
            backupStatsEl.textContent =
                st.websites + " site(s), " + st.pages + " page(s), " + st.snapshots +
                " snapshot(s), " + st.imports + " import(s) \u2014 " + formatBytes(st.bytes) + " stored locally";
        }
        function refreshStored(){
            const overlay = core.readOverlay();
            if (!overlay.websites.length){ storedEl.innerHTML = '<p class="empty">No crawled sites stored yet.</p>'; refreshBackupStats(); return; }
            let html = '<ul class="record-list">';
            for (const w of overlay.websites){
                const pageCount = overlay.pages.filter(p => p.website_id === w.id).length;
                html += '<li><strong>' + core.escapeHtml(w.title || w.id) + '</strong> &middot; ' +
                    pageCount + ' page(s)<br>' +
                    '<code>' + core.escapeHtml(w.original_url || "") + '</code><br>' +
                    core.renderLink(core.websiteLink(w.id), "Open") + ' &middot; ' +
                    '<a href="#" data-export="' + core.escapeHtml(w.id) + '">Export to files (.zip)</a> &middot; ' +
                    '<a href="#" data-del="' + core.escapeHtml(w.id) + '">Delete</a></li>';
            }
            html += '</ul><p><button class="button" id="agw-clear-all" type="button">Clear all crawled sites</button></p>';
            storedEl.innerHTML = html;
            const clearBtn = document.getElementById("agw-clear-all");
            if (clearBtn) clearBtn.addEventListener("click", () => {
                if (window.confirm("Delete ALL crawled sites from the offline database?")){ core.clearOverlay(); refreshStored(); }
            });
            storedEl.querySelectorAll("a[data-del]").forEach(a => {
                a.addEventListener("click", (e) => {
                    e.preventDefault();
                    core.deleteArchivedWebsite(a.getAttribute("data-del"));
                    refreshStored();
                });
            });
            storedEl.querySelectorAll("a[data-export]").forEach(a => {
                a.addEventListener("click", (e) => {
                    e.preventDefault();
                    const w = core.byId(core.readOverlay().websites, a.getAttribute("data-export"));
                    if (w && exportBundleToZip(w)) log("Exported " + (w.title || w.id) + " to a downloadable .zip.");
                    else log("Nothing to export for that site.");
                });
            });
            refreshBackupStats();
        }
        startBtn.addEventListener("click", async () => {
            const start = normalizeUrl(urlInput.value);
            if (!/^https?:\/\//i.test(start)){ log("Enter a valid http:// or https:// URL."); return; }
            resetLog();
            startBtn.disabled = true;
            log("Starting crawl at " + start);
            try {
                const crawled = await crawl(start, {
                    maxPages: parseInt(maxInput.value, 10) || 10,
                    sameDomainOnly: sameInput.checked,
                    inlineAssets: inlineInput.checked
                }, log);
                if (!crawled.length){
                    log("No pages captured. The site likely blocks cross-origin fetches \u2014 use Manual Capture below.");
                } else {
                    const bundle = buildBundle(start, crawled);
                    const ok = core.saveArchivedSite(bundle);
                    log("");
                    if (ok){
                        log("Archived " + crawled.length + " page(s) into the offline database.");
                        log("Website ID: " + bundle.website.id);
                        log("Open it under Websites, or view the snapshot to browse offline.");
                    } else {
                        log("\u2717 Could not save: browser storage quota exceeded.");
                        log("  Try again with fewer pages or with image inlining turned off.");
                    }
                    refreshStored();
                }
            } catch (e) {
                log("Crawl error: " + e.message);
            } finally {
                startBtn.disabled = false;
            }
        });
        manSave.addEventListener("click", async () => {
            const url = normalizeUrl(manUrl.value);
            const html = manHtml.value;
            if (!/^https?:\/\//i.test(url)){ log("Manual capture: enter a valid URL."); return; }
            if (!html.trim()){ log("Manual capture: paste the page HTML first."); return; }
            resetLog();
            log("Processing manual capture: " + url);
            const processed = await processPage(html, url, inlineInput.checked, log);
            const bundle = buildBundle(url, [{
                url, html: processed.html,
                title: processed.meta.title, description: processed.meta.description, text: processed.meta.text
            }]);
            const ok = core.saveArchivedSite(bundle);
            if (ok){
                log("Manually archived: " + (processed.meta.title || url));
                log("Website ID: " + bundle.website.id);
                manUrl.value = ""; manHtml.value = "";
            } else {
                log("\u2717 Could not save: browser storage quota exceeded.");
            }
            refreshStored();
        });
        // ---- Backup & Restore handlers -----------------------------------
        function reportImport(result){
            if (!result.ok){ log("\u2717 Restore failed: " + result.error); return; }
            const a = result.added;
            log("Restore (" + result.mode + ") complete: added " +
                a.websites + " site(s), " + a.snapshots + " snapshot(s), " +
                a.pages + " page(s), " + a.imports + " import(s).");
            if (result.mode === "merge"){
                const s = result.skipped;
                const dupes = s.websites + s.snapshots + s.pages + s.imports;
                if (dupes) log("  Skipped " + dupes + " record(s) that already existed (matching IDs).");
            }
        }
        function runRestore(mode){
            const file = backupFileInput.files && backupFileInput.files[0];
            if (!file){ log("Select a backup .json file first."); return; }
            if (mode === "replace" &&
                !window.confirm("Replace the ENTIRE local database with this backup? Current crawled sites will be overwritten.")) return;
            const reader = new FileReader();
            reader.onload = () => {
                let parsed;
                try { parsed = JSON.parse(reader.result); }
                catch (e) { log("\u2717 Restore failed: the file is not valid JSON."); return; }
                resetLog();
                log("Restoring from " + file.name + " (" + mode + ")...");
                reportImport(core.importOverlay(parsed, mode));
                backupFileInput.value = "";
                refreshStored();
            };
            reader.onerror = () => log("\u2717 Could not read the selected file.");
            reader.readAsText(file);
        }
        if (backupExportBtn) backupExportBtn.addEventListener("click", () => {
            const st = core.overlayStats();
            if (!st.websites){ log("Nothing to back up yet \u2014 crawl or capture a site first."); return; }
            const backup = core.exportOverlay();
            downloadText("airgapped-web-backup-" + today() + ".json", JSON.stringify(backup, null, 2), "application/json");
            log("Downloaded full database backup (" + st.websites + " site(s), " + formatBytes(st.bytes) + ").");
        });
        if (backupMergeBtn) backupMergeBtn.addEventListener("click", () => runRestore("merge"));
        if (backupReplaceBtn) backupReplaceBtn.addEventListener("click", () => runRestore("replace"));
        refreshStored();
    }
    AGW.renderArchiver = renderArchiver;
    // Reusable export entry point (used by the Website detail page too).
    AGW.exportArchivedWebsite = exportBundleToZip;
    // Expose internals for testing.
    AGW._archiver = { normalizeUrl, sameDomain, resolveLink, slugify, extractMeta, buildBundle, exportBundleToZip, formatBytes };
})();
