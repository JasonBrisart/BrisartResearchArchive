"""
AutoExeBuilder constants.

Part of BrisartDevTools.
"""

from __future__ import annotations

APP_NAME = "AutoExeBuilder"
APP_VERSION = "1.0.1"
AUTHOR = "Jason Brisart"

REPOSITORY_NAME = "BrisartDevTools"
REPOSITORY_URL = "https://github.com/JasonBrisart/BrisartDevTools"

APPLICATION_TAGLINE = (
    "Build distributable Windows executables from local Python projects "
    "using a clean GUI or CLI workflow."
)

OUTPUT_FOLDER_NAME = "auto_exe_output"

BUILD_MANIFEST_FILENAME = "EXE_BUILD_MANIFEST.json"
BUILD_COMMAND_FILENAME = "EXE_BUILD_COMMAND.txt"
BUILD_NOTES_FILENAME = "EXE_BUILD_NOTES.md"

DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "node_modules",
    "auto_exe_output",
}

DEFAULT_EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".dll",
    ".so",
    ".dylib",
    ".exe",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".log",
}

ENTRYPOINT_PRIORITY_NAMES = [
    "main.py",
    "app.py",
    "run.py",
    "launcher.py",
    "gui.py",
    "gui_app.py",
]

PYINSTALLER_MODULE_NAME = "PyInstaller"

PYTHON_STDLIB_HINTS = {
    "__future__",
    "argparse",
    "ast",
    "collections",
    "datetime",
    "hashlib",
    "importlib",
    "inspect",
    "json",
    "logging",
    "os",
    "pathlib",
    "re",
    "shutil",
    "subprocess",
    "sys",
    "tempfile",
    "tkinter",
    "traceback",
    "typing",
    "zipfile",
}