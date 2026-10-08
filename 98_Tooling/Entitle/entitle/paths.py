"""
Entitle Paths

Single source of truth for Entitle's default runtime data locations.

Entitle deliberately keeps *record* placement under explicit operator control:
the CLI always requires ``--store`` to be passed, so the operator never writes to
a surprise location. The GUI, however, needs a sensible default path to
pre-populate its fields, and before 0.4.0 that default (``records/...``,
``entitlements/...``) was duplicated as literal strings across several GUI tab
modules. When one default moved, the others silently drifted.

This module centralizes those defaults so the GUI (and any future tooling) share
one definition of "where data lives by default", while the CLI keeps requiring an
explicit ``--store``. None of these directories are created on import; they are
only computed. The runtime data directories are gitignored and never contain
source.

All paths are resolved relative to the repository root so they behave the same
regardless of the current working directory the tool is launched from.
"""
from pathlib import Path

# Repository root is the parent of the entitle/ package directory.
REPO_ROOT = Path(__file__).resolve().parent.parent

# Default runtime data directories (gitignored; never source).
ENTITLEMENTS_DIR = REPO_ROOT / "entitlements"
RECORDS_DIR = REPO_ROOT / "records"
REPORTS_DIR = REPO_ROOT / "reports"

# Default file locations used to pre-populate GUI fields.
DEFAULT_RECORD_STORE = RECORDS_DIR / "entitle_records.log"
DEFAULT_ENTITLEMENT_FILE = ENTITLEMENTS_DIR / "lab_a.entitle"
DEFAULT_NEW_ENTITLEMENT_FILE = ENTITLEMENTS_DIR / "new.entitle"


def default_record_store() -> str:
    """Return the default record-store path as a string (for GUI defaults)."""
    return str(DEFAULT_RECORD_STORE)


def default_entitlement_file() -> str:
    """Return the default entitlement-file path as a string (for GUI defaults)."""
    return str(DEFAULT_ENTITLEMENT_FILE)


def default_new_entitlement_file() -> str:
    """Return the default output path for a newly issued entitlement."""
    return str(DEFAULT_NEW_ENTITLEMENT_FILE)
