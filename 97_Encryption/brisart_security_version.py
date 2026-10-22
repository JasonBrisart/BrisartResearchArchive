"""
File: brisart_security_version.py

Purpose
-------
Single source of truth for the release identity of the Brisart Research Archive
97_Encryption project (BrisartSecurityResearch). Every module, CLI banner,
research report, and document that names a release reads it from here.

Communication / relationships
-----------------------------
Imported by brisart_security_cli.py (``info`` and ``--version``) and by
research/run_research_suite.py (report provenance). No imports of its own.

Settings / parameters
---------------------
PROJECT_RELEASE        Semantic project release string ("0.4.0-alpha").
RELEASE_NAME           Human release name ("BSR2 Alpha 4").
PERMUTATION_ID         Identifier of the frozen BSR2 permutation.
LEGACY_ENVELOPE_ID     Algorithm identifier of the JSON/hex version 2 envelope.
SEALED_FORMAT_VERSION  Binary sealed-message format version (3).
STREAM_FORMAT_VERSION  Chunked stream format version (1).
ARCHIVE_FORMAT_VERSION Brisart Secure Archive (.bsa) format version (1).

Edge cases
----------
The release, the permutation, and each container format are versioned
independently. Bumping PROJECT_RELEASE never changes a wire format by itself.

Known limitations
-----------------
Constants only. Nothing here validates that the documents agree with it; the
release checklist in docs/TESTING.md covers that.

Examples
--------
>>> from brisart_security_version import PROJECT_RELEASE
>>> PROJECT_RELEASE
'0.4.0-alpha'
"""

PROJECT_RELEASE = "0.4.0-alpha"
RELEASE_NAME = "BSR2 Alpha 4"
PERMUTATION_ID = "BSR2-P1024"
LEGACY_ENVELOPE_ID = "BSR2-ARX-SPONGE-ETM"
SEALED_FORMAT_VERSION = 3
STREAM_FORMAT_VERSION = 1
ARCHIVE_FORMAT_VERSION = 1
