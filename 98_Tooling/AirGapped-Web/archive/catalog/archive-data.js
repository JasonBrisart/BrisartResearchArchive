window.AGW_DATA = {
    archive: {
        id: "airgapped-web",
        name: "AirGapped-Web",
        version: "0.5.0",
        mode: "offline-website-records",
        description:
            "A portable offline website record system that stores websites, " +
            "pages, snapshots, import records, and searchable metadata using local files only, " +
            "can crawl live sites into an offline database, and can back that database up to " +
            "a single portable JSON file for restore on any machine.",
        created: "2026-07-16",
        maintainer: "Jason Brisart"
    },
    websites: [
        {
            id: "website-example",
            title: "Example Preserved Website",
            original_url: "https://example.com",
            domain: "example.com",
            description:
                "A sample preserved website used to demonstrate AirGapped-Web website records.",
            tags: ["example", "website", "records", "offline"],
            snapshot_ids: ["snapshot-example-2026-07-16"]
        }
    ],
    snapshots: [
        {
            id: "snapshot-example-2026-07-16",
            website_id: "website-example",
            label: "Initial Example Website Snapshot",
            captured: "2026-07-16",
            root_path: "records/example-site/2026-07-16/",
            description: "Initial preserved copy of the example website.",
            page_ids: ["page-example-home"]
        }
    ],
    pages: [
        {
            id: "page-example-home",
            website_id: "website-example",
            snapshot_id: "snapshot-example-2026-07-16",
            title: "Example Website Home Page",
            original_url: "https://example.com/",
            local_path: "records/example-site/2026-07-16/index.html",
            summary: "The preserved home page for the example website.",
            captured: "2026-07-16",
            tags: ["home", "example", "snapshot"],
            text:
                "This is a sample offline page preserved inside AirGapped-Web. " +
                "It demonstrates a local website record and local page access."
        }
    ],
    imports: [
        {
            id: "import-example-site-2026-07-16",
            website_id: "website-example",
            snapshot_id: "snapshot-example-2026-07-16",
            label: "Example Website Initial Import",
            imported: "2026-07-16",
            source_type: "manual-folder-import",
            source_note:
                "Example preserved website manually placed into the records folder.",
            root_path: "records/example-site/2026-07-16/",
            status: "active"
        }
    ]
};
