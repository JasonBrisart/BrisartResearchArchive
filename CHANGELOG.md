# Brisart Research Archive Changelog

This changelog records archive-level changes to the Brisart Research Archive.

Individual software, frameworks, libraries, and research projects may maintain
their own changelogs for project-specific development. This file records changes
that affect the structure, standards, shared infrastructure, security model, or
multiple projects within the archive.

---

## 2026-10-27 — Unified Archive Architecture

### Overview

The Brisart Research Archive has begun transitioning from independently
self-contained software projects toward a unified archive architecture.

Shared functionality is intended to remain at its authoritative location within
the archive rather than being copied into every project that uses it.

Projects may therefore directly use shared implementations maintained elsewhere
in the archive, including `94_Native_APIs`, `97_Encryption`, BrisartAI, and
other shared infrastructure.

This establishes the complete Brisart Research Archive as the supported
distribution and dependency boundary. Individual projects remain independently
defined and maintained but are no longer required to operate as self-contained
distributions.

### Shared Implementations

Shared implementations are maintained once at their authoritative archive
location.

For example, software requiring Brisart cryptography may use the implementation
maintained by `97_Encryption` rather than maintain another copy within its own
project.

Compatible fixes and internal improvements to shared implementations can
therefore become available to consuming projects without requiring the same
implementation code to be rewritten separately throughout the archive.

New capabilities, incompatible interface changes, or changes requiring
project-specific behavior may still require updates to consuming projects.

### Official and Preserved Versions

Shared components participating in the unified architecture use `Official` as
their current, actively maintained, and most up-to-date implementation.

Previous Official states are preserved sequentially as `v1`, `v2`, `v3`, `v4`,
and later `vX` versions.

For example:

    97_Encryption/
    ├── Official/
    ├── v1/
    ├── v2/
    └── v3/

Before an Official implementation is superseded, its outgoing state is
preserved as the next applicable `vX` version.

Current compatible projects may use `Official` so compatible fixes and
improvements are inherited from the authoritative shared implementation without
requiring equivalent implementation code to be rewritten within each consuming
project.

Preserved `vX` versions remain available for historical compatibility, LTS
support, migration, testing, reproducibility, and archival review.

### Compatibility

Updating `Official` does not override an established compatibility or LTS
contract.

Software requiring an older shared implementation may remain associated with
the applicable preserved version until deliberately migrated.

This allows shared infrastructure to evolve centrally without requiring every
consumer or established release line to migrate simultaneously.

### Distribution

The complete Brisart Research Archive is becoming the supported installation
for projects participating in the unified architecture.

An individual project directory may therefore no longer contain all components
required to operate that project. The complete archive should be preserved and
transferred when its shared dependencies are required.

Shared dependencies should remain archive-relative rather than use
machine-specific absolute paths so that the archive can be relocated between
supported offline, air-gapped, or other environments without rewriting
internal dependency locations.

The archive remains modular at the project and implementation level while
operating as one integrated software and research environment.

---

## 2026-10-23 — Archive-Wide Audio Documentation

### Overview

The Brisart Research Archive has begun establishing audio documentation as an
archive-wide documentation and preservation format.

Software, frameworks, libraries, research projects, standards, experiments, and
other maintained components within the archive should not rely exclusively on
written documentation to preserve their development history and technical
context.

Where appropriate, significant documentation should also be represented through
recorded audio so that future researchers, maintainers, users, and archival
reviewers can understand the archive through both written and spoken records.

This is an archive-level documentation standard rather than a podcast
requirement limited to `07_Podcast`.

`07_Podcast` remains the location for dedicated podcast productions and
podcast-specific projects. Audio documentation associated with an individual
project should remain associated with that project so that its written
documentation, changelog history, source material, and recorded documentation
can be preserved together.

Audio documentation supplements the written archival record.

Written documentation remains the authoritative technical record for source
behavior, interfaces, compatibility requirements, implementation details,
security behavior, migration requirements, tests, and other information that
requires precise reference.

Audio recordings provide an additional archival representation of that
information and may preserve explanations, historical context, design
reasoning, development commentary, release discussions, or walkthroughs useful
when reviewing a project later.

### Project Integration

Applicable projects within the Brisart Research Archive should maintain their
audio documentation within an `audio/` directory at the project root alongside
directories such as `docs/`.

For example:

    Project_Name/
    ├── audio/
    ├── docs/
    ├── CHANGELOG.md
    └── ...

The `audio/` directory is treated as part of the project's archival
documentation rather than as a replacement for `docs/`.

Audio associated with a specific project should remain with that project rather
than being moved into the central podcast collection solely because the
material is recorded audio.

Dedicated podcast episodes, experimental podcast material, archive-wide
discussions, and other podcast productions may continue to be organized under
`07_Podcast`.

### Documentation Coverage

Projects adopting the audio documentation standard should progressively record
important documentation maintained by that project.

This may include spoken versions or explanations of:

- project overviews and README documentation;
- architectural and technical documentation;
- standards and specifications;
- security and migration documentation;
- compatibility documentation;
- significant research documentation;
- release documentation;
- major design decisions;
- and other material necessary to understand the purpose, structure, history,
  and operation of the project.

The objective is not merely to produce podcast episodes about completed
software. The objective is to preserve an understandable spoken record
alongside the written archive.

### Changelog Documentation

Changelogs are included in the archive-wide audio documentation strategy.

Future significant changelog entries should have corresponding audio
documentation where practical so that the development history of a project can
be followed through both the written changelog and the recorded archival
record.

Audio changelog documentation should explain the recorded change, what changed,
why the change was made where that information is documented, and any relevant
compatibility or migration limitations.

The written changelog remains the authoritative release record.

Audio documentation should correspond to that record rather than introduce
undocumented technical claims or become the only location in which an important
change is recorded.

### Preservation

Audio documentation should be treated as a maintained archival artifact.

Recordings should remain identifiable in relation to the project,
documentation, release, or archive change they describe.

Projects should preserve sufficient accompanying metadata to identify:

- the represented project or archive component;
- the associated documentation or changelog material;
- the applicable software or documentation version where relevant;
- and when the recording was created.

---

## 2026-10-23 — Archive-Wide Cryptography Migration

### Overview

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

### Migration

Existing encrypted data must be considered separately from the cryptography
implementation used for newly written data.

Where an existing Brisart application contains data encrypted using an older
supported format, that application's migration path must preserve the ability
to process the existing data long enough to migrate it to the replacement
format.

Migration behavior must be implemented and verified by the individual software
being migrated. Archive-wide adoption of the new cryptography implementation
does not, by itself, establish compatibility with historical encrypted data.

### Project Integration

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
- and the tests used to verify encryption, decryption, and migration behavior.

Project-specific implementation details remain in the changelog and
documentation belonging to that software.

The root archive changelog records the broader transition and identifies which
projects have adopted it.

### Compatibility

This change does not claim that every project in the Brisart Research Archive
has already migrated to the new cryptography implementation.

Projects should only be identified as migrated after their integration,
migration behavior, and relevant compatibility requirements have been
implemented and tested.

Until then, those projects remain pending migration.

The shared cryptography implementation does not override an established LTS
compatibility contract.

Where adopting a replacement cryptography implementation would require changes
that violate an existing LTS contract, the migration should occur outside that
established LTS line.

An established LTS line may remain associated with its compatible cryptography
implementation until the replacement architecture has been completed, tested,
and is appropriate for adoption by a future LTS baseline.
