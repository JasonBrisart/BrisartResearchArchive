# Security and local data

## Storage and confidentiality

**Offline is not encrypted.** SQLite stores indexed text, research notes, source paths and compact conversation topics without application-level encryption. Settings are local JSON. Read access to the profile, a backup or a synced copy may expose that data. Windows `%APPDATA%` may be part of a roaming profile. Use filesystem access controls and protect backups; see the [state instructions](README.md#state-and-upgrading) for choosing a directory.

## Removal and retention

**Index removal is not secure erasure.** Removing an indexed file leaves the original on disk and any separate note snapshots intact. Old content may persist in backups or database pages. The app does not promise secure deletion.

## Input trust and parser limits

**Local import is not a sandbox.** Readers parse user-selected files in the application process and are best-effort. Use trusted inputs and a trusted external Native API directory. Imported HTML is parsed for text, not opened as a browser page. The runtime has no web-search or HTTP-fetch path; OS-managed network locations and profile synchronization are outside this boundary.

Office/OpenDocument ZIP readers reject packages whose selected XML exceeds 16 MiB per member, 64 MiB total or 2,048 members. XML members containing a DTD are skipped. The PDF reader limits raw bytes read, not stream expansion. These restrictions do not isolate parsers from the host.

## Reporting security issues

For a bug report, include the affected version, platform and a minimal non-confidential input that reproduces it. Do not attach the production index or private indexed files.

## Protecting the local library

An offline application can still expose data to users or processes with access to its storage directory. Indexed text and notes are readable in the SQLite database without application-level encryption. Backups, synchronized folders, and roaming profiles may preserve copies beyond the current workstation.

Use operating-system permissions and backup controls appropriate to the sensitivity of the research corpus. Keep the external Native API installation in a trusted location and avoid importing documents from unknown sources when possible. Moving the state directory changes where the application writes data, not whether that data is encrypted.

## Data lifecycle and deletion expectations

Removing an indexed source is a library operation. It does not remove the original file, independent note snapshots, or historical backup copies. Database pages and filesystem recovery mechanisms may retain older bytes. Treat secure erasure as a separate operating-system and storage-management requirement.

A saved note containing a verified excerpt is its own record. Review notes separately when removing material from the library. Do not assume that removing one source reference removes every derived or quoted occurrence of its content.

## Parser boundaries and safe diagnostics

The file readers apply limits to supported archive members and reject DTD-bearing XML, but they are not an isolation boundary against malicious inputs. The PDF raw-byte budget does not cover every possible decompression or parser resource cost. Parsing should therefore be performed only on material appropriate for the host environment.

When reporting a security or parsing defect, use a minimal non-confidential reproducer. Include the affected version, operating system, source format, observed behavior, and expected behavior. Avoid sharing production indexes, private notes, access tokens, or full confidential documents.


## Experimental encrypted backups

The `.bsa` export encrypts the backup copy only. It does not change the live SQLite database, settings, original documents, prior copies, swap or crash dumps. The CLI has no plaintext export fallback. Verification authenticates contents and checks the SQLite snapshot in memory; restore materializes plaintext in a new directory. Use a private parent directory with appropriate permissions, especially on Windows. Handled write failures trigger cleanup, but a crash or forced termination may leave partial plaintext files.

The upstream `97_Encryption/v4` README describes its custom construction as experimental and not independently audited. Do not rely on this export as the only protection for sensitive or valuable data. Keep using established device or storage encryption and access controls. Use only a trusted Official directory; it contains executable Python code.

## Encrypted live-library boundaries

At rest, the BrisartAI SQLite library is stored through `97_Encryption/v4`. Live-library migration has a separate 5 GiB process-safety ceiling and does not inherit the 32 MiB backup-export snapshot cap; the generated archive passphrase is protected by Windows CurrentUser DPAPI. This binds automatic unlock to the Windows profile. It does not encrypt original source documents, the settings file, operating-system paging, crash dumps, or a temporary working database while BrisartAI is open.

Migration retains a temporary recovery copy until the encrypted container has been reopened and validated. Clean shutdown checkpoints the database before deleting the temporary working directory. Abrupt termination can leave temporary plaintext under the operating-system temporary directory and can lose changes made after the last completed checkpoint. Device encryption such as BitLocker remains appropriate.

