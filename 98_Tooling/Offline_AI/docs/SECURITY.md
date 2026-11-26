# Security and local data

**Offline is not encrypted.** SQLite stores indexed text, research notes, source paths and compact conversation topics without application-level encryption. Settings are local JSON. Read access to the profile, a backup or a synced copy may expose that data. Windows `%APPDATA%` may be part of a roaming profile. Use filesystem access controls and protect backups; see the [state instructions](README.md#state-and-upgrading) for choosing a directory.

**Index removal is not secure erasure.** Removing an indexed file leaves the original on disk and any separate note snapshots intact. Old content may persist in backups or database pages. The app does not promise secure deletion.

**Local import is not a sandbox.** Readers parse user-selected files in the application process and are best-effort. Use trusted inputs and a trusted external Native API directory. Imported HTML is parsed for text, not opened as a browser page. The runtime has no web-search or HTTP-fetch path; OS-managed network locations and profile synchronization are outside this boundary.

Office/OpenDocument ZIP readers reject packages whose selected XML exceeds 16 MiB per member, 64 MiB total or 2,048 members. XML members containing a DTD are skipped. The PDF reader limits raw bytes read, not stream expansion. These restrictions do not isolate parsers from the host.

For a bug report, include the affected version, platform and a minimal non-confidential input that reproduces it. Do not attach the production index or private indexed files.
