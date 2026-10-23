# Brisart Research Archive Changelog

This changelog records archive-level changes to the Brisart Research Archive.

Individual software, frameworks, libraries, and research projects may maintain
their own changelogs for project-specific development. This file records changes
that affect the structure, standards, shared infrastructure, security model, or
multiple projects within the archive.

---

## 2026-10-23

### Documentation

#### Archive-Wide Audio Documentation and Podcast Preservation

The Brisart Research Archive has begun establishing audio documentation as an archive-wide documentation and preservation format.

Software, frameworks, libraries, research projects, standards, experiments, and other maintained components within the archive should not rely exclusively on written documentation to preserve their development history and technical context.

Where appropriate, significant documentation should also be represented through recorded audio so that future researchers, maintainers, users, and archival reviewers can understand the archive through both written and spoken records.

This is an archive-level documentation standard rather than a podcast requirement limited to `07_Podcast`.

`07_Podcast` remains the location for dedicated podcast productions and podcast-specific projects. Audio documentation associated with an individual project should remain associated with that project so that its written documentation, changelog history, source material, and recorded documentation can be preserved together.

#### Audio Documentation Strategy

Audio documentation is intended to supplement the written archival record.

Written documentation remains the authoritative technical record for source behavior, interfaces, compatibility requirements, implementation details, security behavior, migration requirements, tests, and other information that requires precise reference.

Audio recordings provide an additional archival representation of that information and may preserve explanations, historical context, design reasoning, development commentary, release discussions, or walkthroughs that are useful when reviewing a project later.

#### Project Integration

Applicable projects within the Brisart Research Archive should maintain their audio documentation within an `audio/` directory at the project root alongside directories such as `docs/`.

For example:

    Project_Name/
    ├── audio/
    ├── docs/
    ├── CHANGELOG.md
    └── ...

The `audio/` directory is treated as part of the project's archival documentation rather than as a replacement for `docs/`.

Audio associated with a specific project should remain with that project rather than being moved into the central podcast collection solely because the material is recorded audio.

Dedicated podcast episodes, experimental podcast material, archive-wide discussions, and other podcast productions may continue to be organized under `07_Podcast`.

#### Documentation Coverage

Projects adopting the audio documentation standard should progressively record important documentation maintained by that project.

This may include spoken versions or explanations of:

- project overviews and README documentation;
- architectural documentation;
- technical documentation;
- standards and specifications;
- security documentation;
- migration documentation;
- compatibility documentation;
- significant research documentation;
- release documentation;
- major design decisions;
- and other material necessary to understand the purpose, structure, history, and operation of the project.

The objective is not merely to produce podcast episodes about completed software. The objective is to preserve an understandable spoken record alongside the written archive.

#### Changelog Documentation

Changelogs are included in the archive-wide audio documentation strategy.

Future significant changelog entries should have corresponding audio documentation where practical so that the development history of a project can be followed through both the written changelog and the recorded archival record.

Audio changelog documentation should explain the release or archive change being recorded, what changed, why the change was made where that information is documented, and any documented compatibility or migration limitations relevant to understanding the change.

The written changelog remains the authoritative release record.

Audio recordings should therefore correspond to the written changelog rather than introduce undocumented technical claims or become the only location in which an important change is recorded.

#### Preservation Requirements

Audio documentation should be treated as a maintained archival artifact.

Recordings should remain identifiable in relation to the project, documentation, release, or archive change they describe.

Projects should preserve sufficient accompanying metadata to determine:

- the project or archive component represented by the recording;
- the documentation or changelog material associated with it;
- the applicable software or documentation version where relevant;
- when the recording was created;
- and whether the recording supplements, explains, or directly represents an existing written document.

Audio documentation should remain understandable without requiring it to become a substitute for the corresponding written record.

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
