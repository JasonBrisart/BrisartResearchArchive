"""
Entitle Bootstrap

Adds the sibling ``vendor/`` directory (BrisartSecurityResearch, used completely
unmodified) to ``sys.path`` so its flat, top-level imports
(``from brisart_security_primitives import ...``) resolve correctly.

BSR2's own modules are not a Python package and do not use relative imports, so
``vendor/`` cannot be imported as ``import vendor`` or ``from vendor import ...``.
It must be added to ``sys.path`` directly, as its own path entry, with its ``.py``
files sitting flat inside it.

Every Entitle entry point (the CLI in ``main.py``, the GUI in ``gui/app.py``, and
``examples/protected_app_example.py``) calls ``ensure_bsr_on_path()`` before
importing anything from ``entitle.bsr_adapter``.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor"

_done = False


def ensure_bsr_on_path():
    """Idempotently add the vendor/ directory to sys.path."""
    global _done
    if _done:
        return
    vendor_path = str(VENDOR_DIR)
    if not VENDOR_DIR.is_dir():
        raise FileNotFoundError(
            f"Expected the BrisartSecurityResearch (BSR2) directory at "
            f"'{vendor_path}', but it does not exist. Place the unmodified "
            f"BSR2 .py files there before running Entitle."
        )
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
    _done = True
