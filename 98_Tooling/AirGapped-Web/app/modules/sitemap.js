(function () {
    "use strict";
    window.AGW = window.AGW || {};
    const core = AGW.core;
    function renderWebsiteLinks(websites){
        if (!Array.isArray(websites) || websites.length === 0) return '<li>No websites recorded.</li>';
        let html = ""; for (const w of websites) html += '<li>'+core.renderLink(core.websiteLink(w.id), w.title || w.id || "Unnamed Website")+'</li>'; return html;
    }
    function renderPageLinks(pages){
        if (!Array.isArray(pages) || pages.length === 0) return '<li>No pages recorded.</li>';
        let html = ""; for (const p of pages) html += '<li>'+core.renderLink(core.pageLink(p.id), p.title || p.id || "Unnamed Page")+'</li>'; return html;
    }
    function renderSitemap(targetId){
        const target = document.getElementById(targetId); if (!target) return;
        const data = core.getData();
        target.innerHTML = `
            <section class="panel">
                <h2>Core Pages</h2>
                <ul class="record-list">
                    <li><a href="../../index.html">Home</a></li>
                    <li><a href="websites.html">Websites</a></li>
                    <li><a href="archiver.html">Archiver</a></li>
                    <li><a href="imports.html">Imports</a></li>
                    <li><a href="search.html">Search</a></li>
                    <li><a href="sitemap.html">Site Map</a></li>
                </ul>
            </section>
            <section class="panel"><h2>Websites</h2><ul class="record-list">${renderWebsiteLinks(data.websites)}</ul></section>
            <section class="panel"><h2>Pages</h2><ul class="record-list">${renderPageLinks(data.pages)}</ul></section>`;
    }
    AGW.renderSitemap = renderSitemap;
})();
