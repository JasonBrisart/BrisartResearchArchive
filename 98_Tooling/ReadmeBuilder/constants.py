"""
File: constants.py

Purpose
-------
ReadmeBuilder constants.

Communication / relationships
-----------------------------
No direct module-level imports are declared.

Settings / parameters
---------------------
Module-level named settings: APP_NAME, APP_VERSION, AUTHOR, REPOSITORY_NAME, REPOSITORY_URL, README_OUTPUT_FILENAME, ANALYSIS_OUTPUT_FILENAME, MANIFEST_OUTPUT_FILENAME, DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_FILES, DEFAULT_EXCLUDE_SUFFIXES, PYTHON_STDLIB_APPROX, MAX_TREE_ITEMS, MAX_IMPORT_SCAN_FILES, MAX_ENTRYPOINTS, MAX_MODULE_SUMMARIES, MAX_FUNCTIONS_PER_MODULE, MAX_CLASSES_PER_MODULE. See their definitions below for values.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.
"""

APP_NAME = "ReadmeBuilder"
APP_VERSION = "1.0.0"

AUTHOR = "Jason Brisart"
REPOSITORY_NAME = "BrisartDevTools"
REPOSITORY_URL = "https://github.com/JasonBrisart/BrisartDevTools"

README_OUTPUT_FILENAME = "README_DRAFT.md"
ANALYSIS_OUTPUT_FILENAME = "README_ANALYSIS.md"
MANIFEST_OUTPUT_FILENAME = "README_BUILDER_MANIFEST.json"

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "build",
    "dist",
    ".idea",
    ".vscode",
    "updates",
}

DEFAULT_EXCLUDE_FILES = {
    README_OUTPUT_FILENAME,
    ANALYSIS_OUTPUT_FILENAME,
    MANIFEST_OUTPUT_FILENAME,
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
}

DEFAULT_EXCLUDE_SUFFIXES = {
    ".pem",
    ".key",
    ".crt",
    ".pfx",
    ".p12",
}

PYTHON_STDLIB_APPROX = {
    "__future__",
    "abc",
    "argparse",
    "array",
    "ast",
    "asyncio",
    "base64",
    "bisect",
    "calendar",
    "cmath",
    "collections",
    "concurrent",
    "contextlib",
    "copy",
    "csv",
    "datetime",
    "decimal",
    "difflib",
    "email",
    "enum",
    "fileinput",
    "fnmatch",
    "fractions",
    "functools",
    "glob",
    "gzip",
    "hashlib",
    "heapq",
    "html",
    "http",
    "importlib",
    "inspect",
    "io",
    "itertools",
    "json",
    "logging",
    "math",
    "multiprocessing",
    "os",
    "pathlib",
    "pickle",
    "platform",
    "pprint",
    "queue",
    "random",
    "re",
    "shutil",
    "socket",
    "sqlite3",
    "statistics",
    "string",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
    "time",
    "tkinter",
    "traceback",
    "typing",
    "unittest",
    "urllib",
    "uuid",
    "venv",
    "warnings",
    "xml",
    "zipfile",
}

MAX_TREE_ITEMS = 500
MAX_IMPORT_SCAN_FILES = 400
MAX_ENTRYPOINTS = 8
MAX_MODULE_SUMMARIES = 20
MAX_FUNCTIONS_PER_MODULE = 12
MAX_CLASSES_PER_MODULE = 12
