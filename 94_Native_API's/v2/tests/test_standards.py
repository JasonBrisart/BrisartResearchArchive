"""
File: v2/tests/test_standards.py

Purpose
-------
Enforce the rules v2 shipped with and hold it to its released state:
product modules import nothing and call no I/O or evaluation built-ins;
each runs alone in an empty namespace; every exported name is documented;
the header examples run as written; every Python file under v2/ is ASCII
with a six-section header whose File line matches its path; and each v2
module is byte-identical to the release.

Communication / relationships
-----------------------------
Standard library: unittest, ast, hashlib, sys, types, plus support.py in
this folder.
Verifies: every file under v2/.

Settings / parameters
---------------------
- PRODUCT -- The seven v2 modules.
- RELEASE_SHA256 -- SHA-256 of each v2 module as exported on 2026-10-21.

Edge cases
----------
The v2 header examples import from a package named brisart_native, the
name v2 was developed under. The example test registers brisart_native
as an alias package whose path is v2/, so the examples run exactly as
written without editing the released files.

Known limitations
-----------------
Parsing with feature_version=(3, 8) checks syntax only. The release
hashes cannot tell a deliberate patch from an accident; update them only
together with a changelog entry.

Examples
--------
::

    python -B -m unittest discover -s v2/tests -p test_standards.py
"""

import ast
import hashlib
import sys
import types
import unittest

import support

V2 = support.V2
PRODUCT = ("codec", "hash", "inflate", "json", "markup", "robots", "url")
SECTIONS = ("Purpose", "Communication / relationships", "Settings / parameters", "Edge cases", "Known limitations", "Examples")
FORBIDDEN = {"eval", "exec", "compile", "open", "print", "input", "__import__", "globals", "locals", "setattr", "delattr"}
PLACEHOLDERS = ("Inspect the definitions below", "This header update does not establish", "TODO", "TBD", "FIXME")

RELEASE_SHA256 = {
    "brisart_codec.py": "1a3bb1ae8d837da0206d6b4bc89b64ef9cd5102e19de4247f6c8ae134ee7a56e",
    "brisart_hash.py": "5c07e5324afc29a63a3cf7e5e7b6311639bd5dd90e61f7823e9013f128d6d6a1",
    "brisart_inflate.py": "a6e6b47ae19365e997858f16a351923f91f08480caccb1e833eccd8a963ccff1",
    "brisart_json.py": "94968f4cac4b395cb71bfcd9756a0a8cf8cdfd20a75b99c9024011953e7269a3",
    "brisart_markup.py": "433be4cd8225c9d42ef3b846ae79926e3f134df17bc9a1c434fc6ea67123fc6c",
    "brisart_robots.py": "b226fb9d462a706f41da9e469e2db65f77fc1069f7aadaa06412fdefcf713be1",
    "brisart_url.py": "33c28188ea4a8313c6f523f11a6d2a01af945f55f7ead8179a834d68d2a40dad",
}


def products():
    return [V2 / ("brisart_%s.py" % name) for name in PRODUCT]


def header(path):
    return ast.get_docstring(ast.parse(path.read_text()), clean=False)


class ProductTests(unittest.TestCase):
    def test_modules_are_byte_identical_to_the_release(self):
        self.assertEqual(sorted(p.name for p in V2.glob("brisart_*.py")), sorted(RELEASE_SHA256))
        for name, digest in RELEASE_SHA256.items():
            self.assertEqual(hashlib.sha256((V2 / name).read_bytes()).hexdigest(), digest, name)

    def test_no_imports_and_no_forbidden_calls(self):
        for path in products():
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    self.fail("%s imports something at line %d" % (path.name, node.lineno))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertTrue(node.func.id not in FORBIDDEN, "%s calls %s" % (path.name, node.func.id))

    def test_python_3_8_syntax(self):
        for path in products():
            ast.parse(path.read_text(), feature_version=(3, 8))

    def test_each_module_runs_alone(self):
        for path in products():
            namespace = {"__name__": "alone_" + path.stem}
            exec(compile(path.read_text(), str(path), "exec"), namespace)
            for name in namespace["__all__"]:
                self.assertTrue(name in namespace, "%s: __all__ names undefined %s" % (path.name, name))

    def test_exports_are_complete_and_documented(self):
        for path in products():
            tree = ast.parse(path.read_text())
            doc = header(path)
            exported = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets))
            exported = [e.value for e in exported.elts]
            for name in exported:
                self.assertTrue(name in doc, "%s exports %s but its header never mentions it" % (path.name, name))
            public = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")}
            public |= {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
                       if isinstance(t, ast.Name) and t.id.isupper() and not t.id.startswith("_")}
            for name in public:
                self.assertTrue(name in exported, "%s defines public %s but does not export it" % (path.name, name))

    def test_header_examples_run_as_written(self):
        alias = types.ModuleType("brisart_native")
        alias.__path__ = [str(V2)]
        saved = {k: v for k, v in sys.modules.items() if k == "brisart_native" or k.startswith("brisart_native.")}
        for key in saved:
            del sys.modules[key]
        sys.modules["brisart_native"] = alias
        try:
            for path in products():
                block = header(path).split("Examples\n--------\n", 1)[1]
                code = "\n".join(line[4:] for line in block.splitlines() if line.startswith("    "))
                self.assertTrue(code.strip(), path.name)
                exec(compile(code, path.name + " example", "exec"), {"__name__": "example"})
        finally:
            for key in [k for k in sys.modules if k == "brisart_native" or k.startswith("brisart_native.")]:
                del sys.modules[key]
            sys.modules.update(saved)


class EveryFileTests(unittest.TestCase):
    def all_python(self):
        return sorted(p for p in V2.rglob("*.py") if "__pycache__" not in p.parts)

    def test_ascii_and_whitespace(self):
        for path in self.all_python():
            text = path.read_text()
            self.assertTrue(text.isascii(), path.name)
            for number, line in enumerate(text.splitlines(), 1):
                self.assertTrue("\t" not in line and line == line.rstrip(), "%s:%d" % (path.name, number))

    def test_six_section_headers(self):
        for path in self.all_python():
            doc = header(path)
            self.assertTrue(doc.lstrip().startswith("File: " + path.relative_to(V2.parent).as_posix()), path.name)
            positions = []
            for name in SECTIONS:
                marker = "\n%s\n%s\n" % (name, "-" * len(name))
                self.assertEqual(doc.count(marker), 1, "%s: %s" % (path.name, name))
                positions.append(doc.index(marker))
            self.assertEqual(positions, sorted(positions), path.name)
            for phrase in PLACEHOLDERS:
                self.assertTrue(phrase not in doc, "%s contains %r" % (path.name, phrase))

    def test_product_header_subsections(self):
        for path in products():
            doc = header(path)
            for needle in ("Public interface:", "Design notes:", "Standard library: none.", "Verified on CPython 3.12 only"):
                self.assertTrue(needle in doc, "%s lacks %r" % (path.name, needle))


if __name__ == "__main__":
    unittest.main()
