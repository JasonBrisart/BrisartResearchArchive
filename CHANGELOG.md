# Brisart Research Archive Changelog

This changelog records archive-level changes to the Brisart Research Archive.

Individual software, frameworks, libraries, and research projects may maintain
their own changelogs for project-specific development. This file records changes
that affect the structure, standards, shared infrastructure, security model, or
multiple projects within the archive.

---

## 2026-10-23

### Security

#### Archive-Wide Cryptography Migration

The Brisart Research Archive has begun transitioning software that stores or
processes encrypted data toward the current Brisart cryptography implementation.

This is an archive-level change rather than a change limited to a single
application. Software within the archive may require its own integration and
migration work depending on how it currently stores, accesses, or manages
encrypted data.

The migration strategy is intended to establish the current cryptography
implementation as shared security infrastructure for applicable Brisart
software rather than allowing individual projects to independently maintain
diverging encryption implementations.

### Migration Strategy

Existing encrypted data must be considered separately from the cryptography
implementation used for newly written data.

Where an existing Brisart application contains data encrypted using an older
supported format, that application's migration path must preserve the ability
to process the existing data long enough to migrate it to the replacement
format.

Migration behavior must be implemented and verified by the individual software
being migrated. Archive-wide adoption of the new cryptography implementation
does not, by itself, establish compatibility with historical encrypted data.

### Software Integration

Applicable software within the Brisart Research Archive will transition to the
shared cryptography implementation individually.

Each integration should document:

- the previous cryptography implementation used by the software;
- the replacement implementation being adopted;
- which encrypted data or storage formats are affected;
- how existing encrypted data is migrated;
- whether migration modifies data in place or produces replacement data;
- what compatibility remains with historical encrypted data;
- what recovery or rollback limitations exist after migration;
- the tests used to verify encryption, decryption, and migration behavior.

Project-specific implementation details remain in the changelog and
documentation belonging to that software.

The root archive changelog records the broader architectural transition and
identifies which projects have adopted it.

### Compatibility

This change does not claim that every project in the Brisart Research Archive
has already migrated to the new cryptography implementation.

Projects should only be identified as migrated after their integration,
migration behavior, and relevant compatibility requirements have been
implemented and tested.

Until then, those projects remain pending migration.