"""
Single source of truth for the Entitle version.

This lives in a standalone root module (rather than inside ``entitle/__init__.py``)
so every surface of the project -- the ``entitle`` package, the CLI in ``main.py``,
the GUI, packaging metadata, and any release/verification tooling -- reads the
version from exactly one place. Keeping it here mirrors the convention used across
the wider Brisart ecosystem, where each project exposes a top-level ``version.py``
whose ``__version__`` string is the authoritative release identifier.

The value is a plain string with no imports and no side effects, so it can be
read cheaply by tooling (including offline/air-gapped release scripts) without
importing the whole package.
"""

__version__ = "0.4.1"
