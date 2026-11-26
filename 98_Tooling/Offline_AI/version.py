"""Purpose
-------
Declare the BrisartAI release version.

This application module defines the constants and module-level declarations. Its scope is
deliberately limited to the responsibilities visible in this file rather than duplicating the
application-wide workflow. Callers use these declarations through the module interface; the
file is not a separate service or background daemon unless explicitly stated above.

Communication / relationships
-----------------------------
BrisartAI version_info reads this value for the application.

The direct in-project imports visible in this module are the standard library and its direct
caller. Public entry points are represented by its module-level declarations; this identifies
where behavior is invoked without implying a separate hidden dependency. Higher-level
coordination remains with the calling layer rather than being introduced here.

Settings / parameters
---------------------
Keep the release version aligned with docs/CHANGELOG.md.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
The version loader handles a missing or unreadable version file.

The behaviors documented above must be read together with the actual branches in version.py; a
caller must not infer success from an empty, rejected, or unsupported result. Error handling,
input validation, and early returns remain the responsibility of the concrete functions in
this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Changing the version does not migrate state or install an update.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
__version__ = "1.6.0"

For a concrete entry point, inspect the constants and module-level declarations; invoke it
through the existing application entry point or its documented caller. The example above is
illustrative of this file's present interface; do not treat it as an instruction to create
additional state or call private functions directly.
"""

__version__ = "1.6.0"
