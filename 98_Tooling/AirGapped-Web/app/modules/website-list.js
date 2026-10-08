(function () {
    "use strict";
    window.AGW = window.AGW || {};
    const core = AGW.core;
    function renderWebsiteCard(w){
        const snapshots = core.websiteSnapshots(w.id);
        const pages = core.websitePages(w.id);
        const imports = core.websiteImports(w.id);
        const badge = core.isArchivedWebsite(w.id) ? ' <span class="tag">crawled</span>' : "";
        return `
            <article class="card">
                <div class="card-meta">${core.escapeHtml(w.domain || "Unknown domain")}</div>
                <h2>${core.renderLink(core.websiteLink(w.id), w.title || w.id || "Unnamed Website")}${badge}</h2>
                <p>${core.escapeHtml(w.description)}</p>
                <p><strong>Original URL:</strong> <code>${core.escapeHtml(w.original_url)}</code></p>
                <p><strong>Snapshots:</strong> ${snapshots.length}</p>
                <p><strong>Registered pages:</strong> ${pages.length}</p>
                <p><strong>Imports:</strong> ${imports.length}</p>
                <div class="tag-row">${core.renderTags(w.tags)}</div>
            </article>`;
    }
    function renderWebsiteList(targetId, websites){
        const target = document.getElementById(targetId); if (!target) return;
        if (!Array.isArray(websites) || websites.length === 0){
            target.innerHTML = '<section class="panel"><p class="empty">No websites found. Use the <a href="archiver.html">Archiver</a> to crawl one.</p></section>'; return; }
        let html = ""; for (const w of websites) html += renderWebsiteCard(w); target.innerHTML = html;
    }
    function renderAllWebsites(targetId){ renderWebsiteList(targetId, core.getData().websites); }
    AGW.renderWebsiteList = renderWebsiteList;
    AGW.renderAllWebsites = renderAllWebsites;
})();
