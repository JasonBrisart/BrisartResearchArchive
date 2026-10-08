(function () {
    "use strict";
    window.AGW = window.AGW || {};
    const core = AGW.core;
    function renderValidationPanel(v){
        if (v.valid && v.warnings.length === 0) return "";
        let html = '<section class="panel"><h2>Catalog Validation</h2>';
        if (v.errors.length > 0){ html += '<p><strong>'+v.errors.length+' error(s) found.</strong></p><ul class="record-list">';
            for (const e of v.errors) html += '<li>'+core.escapeHtml(e)+'</li>'; html += '</ul>'; }
        if (v.warnings.length > 0){ html += '<p><strong>'+v.warnings.length+' warning(s) found.</strong></p><ul class="record-list">';
            for (const wn of v.warnings) html += '<li>'+core.escapeHtml(wn)+'</li>'; html += '</ul>'; }
        html += '</section>'; return html;
    }
    function renderArchiveSummary(targetId){
        const target = document.getElementById(targetId); if (!target) return;
        const data = core.getData(); const validation = core.validateData();
        target.innerHTML = `
            <section class="panel">
                <div class="card-meta">Version ${core.escapeHtml(data.archive.version || "Unspecified")}</div>
                <h2>${core.escapeHtml(data.archive.name || "AirGapped-Web")}</h2>
                <p>${core.escapeHtml(data.archive.description || "Portable offline website records.")}</p>
                <p><strong>Catalog status:</strong> ${validation.valid ? "Valid" : "Errors detected"}</p>
                <div class="stats">
                    <div><strong>${data.websites.length}</strong><span>Websites</span></div>
                    <div><strong>${data.pages.length}</strong><span>Pages</span></div>
                    <div><strong>${data.snapshots.length}</strong><span>Snapshots</span></div>
                    <div><strong>${data.imports.length}</strong><span>Imports</span></div>
                </div>
            </section>
            ${renderValidationPanel(validation)}`;
    }
    AGW.renderArchiveSummary = renderArchiveSummary;
})();
