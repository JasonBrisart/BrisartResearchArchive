(function () {
    "use strict";
    window.AGW = window.AGW || {};
    const core = AGW.core;
    function renderSnapshotList(snapshots){
        if (!Array.isArray(snapshots) || snapshots.length === 0) return '<li>No snapshots recorded.</li>';
        let html = "";
        for (const s of snapshots){
            const pages = core.snapshotPages(s.id);
            const snapshotHref = core.snapshotLink(s.id);
            html += `
                <li>
                    <strong>${core.escapeHtml(s.label || s.id || "Unnamed Snapshot")}</strong><br>
                    Captured: ${core.escapeHtml(s.captured || "Unspecified")}<br>
                    Root path: <code>${core.escapeHtml(s.root_path || "No root path recorded.")}</code><br>
                    Registered pages: ${pages.length}
                    <p>${core.escapeHtml(s.description || "No snapshot description recorded.")}</p>
                    <p>${core.renderLink(snapshotHref, "View Snapshot", "button")}</p>
                </li>`;
        }
        return html;
    }
    function renderImportList(imports){
        if (!Array.isArray(imports) || imports.length === 0) return '<li>No imports recorded.</li>';
        let html = "";
        for (const i of imports){
            html += `
                <li>
                    <strong>${core.escapeHtml(i.label || i.id || "Unnamed Import")}</strong><br>
                    Imported: ${core.escapeHtml(i.imported || "Unspecified")}<br>
                    Source type: ${core.escapeHtml(i.source_type || "Unspecified")}<br>
                    Status: ${core.escapeHtml(i.status || "Unknown")}<br>
                    Root path: <code>${core.escapeHtml(i.root_path || "No root path recorded.")}</code>
                </li>`;
        }
        return html;
    }
    function renderPageList(pages){
        if (!Array.isArray(pages) || pages.length === 0) return '<li>No pages recorded.</li>';
        let html = "";
        for (const p of pages){
            html += `
                <li>
                    ${core.renderLink(core.pageLink(p.id), p.title || p.id || "Unnamed Page")}<br>
                    <span>${core.escapeHtml(p.summary || "No summary recorded.")}</span><br>
                    <code>${core.escapeHtml(p.original_url || p.local_path || "No path recorded.")}</code>`;
            if (p.inline_html) html += '<br><span class="tag">offline copy stored</span>';
            html += '</li>';
        }
        return html;
    }
    function renderCrawledActions(website){
        if (!core.isArchivedWebsite(website.id)) return "";
        return `<p>
            <button class="button" id="agw-export-site" type="button">Export to Files (.zip)</button>
            <button class="button" id="agw-del-site" type="button">Delete This Crawled Site</button>
        </p>`;
    }
    function renderWebsiteDetail(targetId){
        const target = document.getElementById(targetId); if (!target) return;
        const data = core.getData();
        const website = core.byId(data.websites, core.getQueryParam("id"));
        if (!website){ target.innerHTML = core.renderNotFound("Website not found.", "The selected website does not exist in this archive."); return; }
        const snapshots = core.websiteSnapshots(website.id);
        const imports = core.websiteImports(website.id);
        const pages = core.websitePages(website.id);
        target.innerHTML = `
            <section class="panel">
                <div class="card-meta">${core.escapeHtml(website.domain || "Unknown domain")}</div>
                <h2>${core.escapeHtml(website.title || website.id || "Unnamed Website")}</h2>
                <p>${core.escapeHtml(website.description || "No website description recorded.")}</p>
                <p><strong>Original URL:</strong> <code>${core.escapeHtml(website.original_url || "No original URL recorded.")}</code></p>
                <p><strong>Website ID:</strong> <code>${core.escapeHtml(website.id)}</code></p>
                <h3>Tags</h3>
                <div class="tag-row">${core.renderTags(website.tags)}</div>
                ${renderCrawledActions(website)}
            </section>
            <section class="panel">
                <h2>Snapshots</h2>
                <ul class="record-list">${renderSnapshotList(snapshots)}</ul>
            </section>
            <section class="panel">
                <h2>Pages</h2>
                <ul class="record-list">${renderPageList(pages)}</ul>
            </section>
            <section class="panel">
                <h2>Imports</h2>
                <ul class="record-list">${renderImportList(imports)}</ul>
            </section>
            <p><a href="websites.html">Back to All Websites</a></p>`;
        const delBtn = document.getElementById("agw-del-site");
        if (delBtn) delBtn.addEventListener("click", () => {
            if (window.confirm("Delete this crawled site from the offline database?")){
                core.deleteArchivedWebsite(website.id);
                window.location.href = "websites.html";
            }
        });
        const exportBtn = document.getElementById("agw-export-site");
        if (exportBtn && AGW.exportArchivedWebsite) exportBtn.addEventListener("click", () => {
            AGW.exportArchivedWebsite(website);
        });
    }
    AGW.renderWebsiteDetail = renderWebsiteDetail;
})();
