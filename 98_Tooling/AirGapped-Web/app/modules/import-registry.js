(function () {
    "use strict";
    window.AGW = window.AGW || {};
    const core = AGW.core;
    function renderImportCard(importRecord, website, snapshot){
        const pages = snapshot ? core.snapshotPages(snapshot.id) : [];
        const websiteDisplay = website ? core.renderLink(core.websiteLink(website.id), website.title || website.id) : "Unknown Website";
        const snapshotDisplay = snapshot ? (snapshot.label || snapshot.id) : "Unknown Snapshot";
        return `
            <article class="card">
                <div class="card-meta">${core.escapeHtml(importRecord.status || "unknown")} &middot; ${core.escapeHtml(importRecord.source_type || "unspecified")}</div>
                <h2>${core.escapeHtml(importRecord.label || importRecord.id || "Unnamed Import")}</h2>
                <p><strong>Website:</strong> ${websiteDisplay}</p>
                <p><strong>Snapshot:</strong> ${core.escapeHtml(snapshotDisplay)}</p>
                <p><strong>Imported:</strong> ${core.escapeHtml(importRecord.imported)}</p>
                <p><strong>Root path:</strong> <code>${core.escapeHtml(importRecord.root_path)}</code></p>
                <p><strong>Registered pages:</strong> ${pages.length}</p>
                <p>${core.escapeHtml(importRecord.source_note)}</p>
            </article>`;
    }
    function renderImports(targetId){
        const target = document.getElementById(targetId); if (!target) return;
        const data = core.getData();
        let importHtml = "";
        for (const importRecord of data.imports)
            importHtml += renderImportCard(importRecord, core.byId(data.websites, importRecord.website_id), core.byId(data.snapshots, importRecord.snapshot_id));
        target.innerHTML = `
            <section class="panel">
                <h2>Import Workflow</h2>
                <p>Websites can enter the archive two ways: <strong>automatically</strong> via the <a href="archiver.html">Archiver</a> (crawls a site into the offline database), or <strong>manually</strong> by placing preserved files under <code>records/</code> and adding records to <code>archive/catalog/archive-data.js</code>.</p>
            </section>
            <section class="panel"><h2>Registered Imports</h2><p>${data.imports.length} import record(s) registered.</p></section>
            ${importHtml || '<section class="panel"><p class="empty">No imports recorded.</p></section>'}`;
    }
    AGW.renderImports = renderImports;
})();
