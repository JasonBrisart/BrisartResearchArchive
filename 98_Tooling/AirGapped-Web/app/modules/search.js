(function () {
    "use strict";
    window.AGW = window.AGW || {};
    const core = AGW.core;
    function buildSearchText(page, website, snapshot){
        return [page.id, page.title, page.original_url, page.local_path, page.summary, page.text,
            Array.isArray(page.tags) ? page.tags.join(" ") : "",
            website ? website.id : "", website ? website.title : "", website ? website.domain : "",
            website ? website.description : "", website && Array.isArray(website.tags) ? website.tags.join(" ") : "",
            snapshot ? snapshot.id : "", snapshot ? snapshot.label : "", snapshot ? snapshot.description : ""
        ].join(" ");
    }
    function pageMatchesQuery(page, query, data){
        const website = core.byId(data.websites, page.website_id);
        const snapshot = core.byId(data.snapshots, page.snapshot_id);
        return core.normalize(buildSearchText(page, website, snapshot)).includes(core.normalize(query));
    }
    function renderSearchResult(page, website){
        const domain = website ? (website.domain || "Unknown domain") : "Unknown Website";
        const websiteTitle = website ? (website.title || website.id) : "Unknown Website";
        const websiteDisplay = website ? core.renderLink(core.websiteLink(website.id), websiteTitle) : core.escapeHtml(websiteTitle);
        return `
            <article class="card">
                <div class="card-meta">${core.escapeHtml(domain)}</div>
                <h2>${core.renderLink(core.pageLink(page.id), page.title || page.id || "Unnamed Page")}</h2>
                <p>${core.escapeHtml(page.summary)}</p>
                <p><strong>Website:</strong> ${websiteDisplay}</p>
                <p><strong>Original URL:</strong> <code>${core.escapeHtml(page.original_url)}</code></p>
                <p><strong>Captured:</strong> ${core.escapeHtml(page.captured)}</p>
                <div class="tag-row">${core.renderTags(page.tags)}</div>
            </article>`;
    }
    function renderSearch(inputId, resultsId){
        const input = document.getElementById(inputId);
        const results = document.getElementById(resultsId);
        if (!input || !results) return;
        const data = core.getData();
        function runSearch(){
            const query = input.value.trim();
            const matches = query ? data.pages.filter(p => pageMatchesQuery(p, query, data)) : data.pages.slice();
            if (matches.length === 0){ results.innerHTML = '<p class="empty">No archived pages found.</p>'; return; }
            let html = '<p class="result-count">'+matches.length+' archived page(s) found.</p>';
            for (const p of matches) html += renderSearchResult(p, core.byId(data.websites, p.website_id));
            results.innerHTML = html;
        }
        input.addEventListener("input", runSearch);
        runSearch();
    }
    AGW.pageMatchesQuery = function (page, query){ return pageMatchesQuery(page, query, core.getData()); };
    AGW.renderSearch = renderSearch;
})();
