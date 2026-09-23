"""
BrisartOS System API
Pure Python.
No dependencies.

Modules should use this API instead of editing BrisartOS core.

This is the stable contract for lab-owned tools.
"""

from pathlib import Path
from datetime import datetime, timezone
import secrets


class SystemAPI:
    def __init__(self, platform):
        self.platform = platform
        self.root = Path.cwd()
        self.module_data_root = self.root / "module_data"
        self.logs_root = self.root / "logs"

        self.module_data_root.mkdir(exist_ok=True)
        self.logs_root.mkdir(exist_ok=True)

    def now_utc(self):
        return datetime.now(timezone.utc).isoformat()

    def new_object_id(self):
        """
        Return a 128-bit BrisartOS object identifier.

        Used for files, archives, modules, services,
        and future BrisartOS object tracking.
        """
        return secrets.token_hex(16)

    def log(self, source, message):
        safe_source = self.safe_name(source)
        log_file = self.logs_root / f"{safe_source}.log"

        line = f"{self.now_utc()} {source}: {message}\n"

        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def module_data_path(self, module_name):
        safe_module = self.safe_name(module_name)
        path = self.module_data_root / safe_module
        path.mkdir(exist_ok=True)
        return path

    def write_module_text(self, module_name, filename, text):
        path = self.module_data_path(module_name) / self.safe_name(filename)
        path.write_text(text, encoding="utf-8")
        return path

    def read_module_text(self, module_name, filename):
        path = self.module_data_path(module_name) / self.safe_name(filename)

        if not path.exists():
            return None

        return path.read_text(encoding="utf-8")

    def get_platform_info(self):
        return self.platform.describe()

    def safe_name(self, value):
        allowed = []

        for character in str(value):
            if character.isalnum() or character in {"-", "_", "."}:
                allowed.append(character)
            else:
                allowed.append("_")

        safe = "".join(allowed).strip("._")

        if not safe:
            return "unnamed"

        return safe
