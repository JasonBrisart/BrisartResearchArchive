(function () {
    "use strict";
    window.AGW = window.AGW || {};
    const core = AGW.core;
    function renderPageNavigation(pages){
        if (!Array.isArray(pages) || pages.length === 0) return '<p class="empty">No registered pages are available for this snapshot.</p>';
        let html = '<ul class="record-list">';
        for (const page of pages){
            const safePath = core.localArchiveLink(page.local_path);
            html += '<li>';
            if (page.id) html += core.renderLink(core.pageLink(page.id), page.title || page.id || "Unnamed Page");
            else html += core.escapeHtml(page.title || "Unnamed Page");
            html += '<br>';
            html += '<span>' + core.escapeHtml(page.summary || "No summary recorded.") + '</span><br>';
            html += '<code>' + core.escapeHtml(page.original_url || page.local_path || "No path recorded.") + '</code>';
            if (!page.inline_html && safePath) html += '<br>' + core.renderLink(safePath, "Open Preserved File");
            html += '</li>';
        }
        html += '</ul>';
        return html;
    }
    function renderInlineFrame(page){
        const safe = core.escapeHtml(page.inline_html);
        return `
            <section class="panel">
                <h2>Website Viewer</h2>
                <p><strong>Viewing:</strong> ${core.escapeHtml(page.title || page.original_url || "Captured page")}</p>
                <iframe srcdoc="${safe}" title="Captured website snapshot" style="width:100%;height:700px;border:1px solid var(--border);border-radius:8px;background:white;" sandbox="allow-popups"></iframe>
            </section>`;
    }
    function renderFileFrame(defaultPath){
        if (!defaultPath){
            return `
                <section class="panel">
                    <h2>Website Viewer</h2>
                    <p class="empty">No safe local page could be selected for this snapshot.</p>
                </section>`;
        }
        const safe = core.escapeHtml(defaultPath);
        return `
            <section class="panel">
                <h2>Website Viewer</h2>
                <p>${core.renderLink(defaultPath, "Open Snapshot in Full Page", "button")}</p>
                <iframe src="${safe}" title="Preserved website snapshot" style="width:100%;height:700px;border:1px solid var(--border);border-radius:8px;background:white;" sandbox="allow-same-origin allow-forms allow-popups"></iframe>
            </section>`;
    }
    function renderSnapshotViewer(targetId){
        const target = document.getElementById(targetId); if (!target) return;
        const data = core.getData();
        const snapshot = core.byId(data.snapshots, core.getQueryParam("id"));
        if (!snapshot){ target.innerHTML = core.renderNotFound("Snapshot not found.", "The selected snapshot does not exist in this archive."); return; }
        const website = core.byId(data.websites, snapshot.website_id);
        const pages = core.snapshotPages(snapshot.id);
        const websiteTitle = website ? (website.title || website.id) : "Unknown Website";
        const backHref = website ? core.websiteLink(website.id) : "websites.html";
        // Prefer an inline (crawled) home page; fall back to a local file path.
        const inlineHome = pages.find(p => p && p.inline_html);
        const frame = inlineHome ? renderInlineFrame(inlineHome) : renderFileFrame(core.snapshotPreferredPage(snapshot, pages));
        target.innerHTML = `
            <section class="panel">
                <div class="card-meta">${core.escapeHtml(websiteTitle)}</div>
                <h2>${core.escapeHtml(snapshot.label || snapshot.id || "Unnamed Snapshot")}</h2>
                <p>${core.escapeHtml(snapshot.description || "No snapshot description recorded.")}</p>
                <p><strong>Snapshot ID:</strong> <code>${core.escapeHtml(snapshot.id)}</code></p>
                <p><strong>Captured:</strong> ${core.escapeHtml(snapshot.captured || "Unspecified")}</p>
                <p><strong>Root path:</strong> <code>${core.escapeHtml(snapshot.root_path || "No root path recorded.")}</code></p>
                <p><strong>Registered pages:</strong> ${pages.length}</p>
                <p>${core.renderLink(backHref, "Back to Website")}</p>
            </section>
            ${frame}
            <section class="panel">
                <h2>Registered Pages in This Snapshot</h2>
                ${renderPageNavigation(pages)}
            </section>`;
    }
    AGW.renderSnapshotViewer = renderSnapshotViewer;
})();
