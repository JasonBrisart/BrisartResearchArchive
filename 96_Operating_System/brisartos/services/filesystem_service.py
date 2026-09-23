"""
BrisartOS Filesystem Service
Pure Python.
No dependencies.
Provides sandboxed, per-module filesystem access for BrisartOS runtime
modules. Every operation is scoped to a single module's own directory
under module_data/<module_name>/ and cannot escape that directory,
regardless of the filename supplied.
This is the first built-in service with real behavior. Modules reach
it through ModuleAPI.get_service("filesystem"), gated by the
"service:filesystem" permission declared in MODULE_PERMISSIONS.
"""
from pathlib import Path
class FilesystemAccessError(Exception):
    pass
class FilesystemService:
    def __init__(self, module_data_root=None):
        self.version = "0.2.0"
        self.module_data_root = Path(module_data_root or "module_data")
        self.module_data_root.mkdir(parents=True, exist_ok=True)
    def status(self):
        return "Filesystem Service Online"
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
    def _module_dir(self, module_name):
        safe_module = self.safe_name(module_name)
        path = self.module_data_root / safe_module
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()
    def _resolve(self, module_name, filename):
        module_dir = self._module_dir(module_name)
        safe_filename = self.safe_name(filename)
        target = (module_dir / safe_filename).resolve()
        if target != module_dir and module_dir not in target.parents:
            raise FilesystemAccessError(
                f"path escapes module data directory: {filename}"
            )
        return target
    def list_files(self, module_name):
        module_dir = self._module_dir(module_name)
        return sorted(
            entry.name for entry in module_dir.iterdir() if entry.is_file()
        )
    def exists(self, module_name, filename):
        return self._resolve(module_name, filename).exists()
    def read_text(self, module_name, filename):
        target = self._resolve(module_name, filename)
        if not target.exists():
            return None
        return target.read_text(encoding="utf-8")
    def write_text(self, module_name, filename, text):
        target = self._resolve(module_name, filename)
        target.write_text(text, encoding="utf-8")
        return str(target)
    def read_bytes(self, module_name, filename):
        target = self._resolve(module_name, filename)
        if not target.exists():
            return None
        return target.read_bytes()
    def write_bytes(self, module_name, filename, data):
        target = self._resolve(module_name, filename)
        target.write_bytes(data)
        return str(target)
    def delete_file(self, module_name, filename):
        target = self._resolve(module_name, filename)
        if target.exists():
            target.unlink()
            return True
        return False
    def file_info(self, module_name, filename):
        target = self._resolve(module_name, filename)
        if not target.exists():
            return None
        stat = target.stat()
        return {
            "name": target.name,
            "size_bytes": stat.st_size,
            "path": str(target),
        }