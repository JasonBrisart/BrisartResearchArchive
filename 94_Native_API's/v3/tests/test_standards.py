"""
File: v3/tests/test_standards.py

Purpose
-------
Enforce the rules every v3 file follows: product modules import nothing
and call no I/O or evaluation built-ins; every Python file is ASCII with
a six-section header whose File line matches its path; every exported
name is documented; header examples run exactly as written; each module
runs alone in an empty namespace; code strings contain no over-escaped
backslash sequences; and CHANGELOG.md's newest entry is v3.0.0, names
every v3 module and cites every probe ID.

Communication / relationships
-----------------------------
Standard library: unittest, ast, os, re, pathlib, plus support.py and
v2_probe.py in this folder.
Verifies: every file under v3/ and the repository CHANGELOG.md.

Settings / parameters
---------------------
- PRODUCT -- The nine product modules.
- JSON_BACKSLASH_ALLOWLIST -- Reviewed code string constants in
  brisart_json.py that legitimately contain a backslash.

Edge cases
----------
The generated entity table in brisart_markup.py is the one code string
longer than 1000 characters and is exempt from the backslash check: it
holds the real backslash that the &bsol; reference decodes to.

Known limitations
-----------------
Parsing with feature_version=(3, 8) checks syntax only, not that every
library behaviour exists on Python 3.8.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_standards.py
"""

import ast
import os
import re
import unittest
from pathlib import Path

import support
from v2_probe import build_checks

V3 = support.V3
REPO = V3.parent
PRODUCT = ("codec", "csv", "deflate", "hash", "inflate", "json", "markup", "robots", "url")
SECTIONS = ("Purpose", "Communication / relationships", "Settings / parameters", "Edge cases", "Known limitations", "Examples")
FORBIDDEN = {"eval", "exec", "compile", "open", "print", "input", "__import__", "globals", "locals", "setattr", "delattr"}
PLACEHOLDERS = ("Inspect the definitions below", "This header update does not establish", "TODO", "TBD", "FIXME")
JSON_BACKSLASH_ALLOWLIST = {"\\", "\\\\", "\\u", '\\"', "\\b", "\\t", "\\n", "\\f", "\\r", "\\u2028", "\\u2029",
                            "\\u%04x", "\\u%04x\\u%04x", "Invalid \\u escape"}


def products():
    return [V3 / ("brisart_%s.py" % name) for name in PRODUCT]


def all_python():
    return sorted(p for p in V3.rglob("*.py") if "__pycache__" not in p.parts)


def header(path):
    return ast.get_docstring(ast.parse(path.read_text()), clean=False)


def code_strings(tree):
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docs.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            yield node.value


class ProductTests(unittest.TestCase):
    def test_layout(self):
        expected = {"tests"} | {"brisart_%s.py" % n for n in PRODUCT}
        self.assertEqual({p.name for p in V3.iterdir() if p.name != "__pycache__"}, expected)
        tests = {p.name for p in (V3 / "tests").iterdir() if p.name != "__pycache__"}
        self.assertEqual(tests, {"support.py", "v2_probe.py", "test_standards.py", "test_v2_compat.py", "test_v1_lineage.py"}
                         | {"test_%s.py" % n for n in PRODUCT})

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
        old = os.getcwd()
        os.chdir(str(V3))
        try:
            for path in products():
                block = header(path).split("Examples\n--------\n", 1)[1]
                code = "\n".join(line[4:] for line in block.splitlines() if line.startswith("    "))
                self.assertTrue(code.strip(), path.name)
                exec(compile(code, path.name + " example", "exec"), {"__name__": "example"})
        finally:
            os.chdir(old)

    def test_no_over_escaped_backslashes_in_code(self):
        for path in products():
            found = {s for s in code_strings(ast.parse(path.read_text())) if "\\" in s}
            if path.name == "brisart_markup.py":
                found = {s for s in found if len(s) <= 1000}
            if path.name == "brisart_json.py":
                found -= JSON_BACKSLASH_ALLOWLIST
            self.assertTrue(not found, "%s: unexpected backslash in code strings %r" % (path.name, sorted(found)[:5]))


class EveryFileTests(unittest.TestCase):
    def test_ascii_and_whitespace(self):
        for path in all_python():
            text = path.read_text()
            self.assertTrue(text.isascii(), path.name)
            for number, line in enumerate(text.splitlines(), 1):
                self.assertTrue("\t" not in line and line == line.rstrip(), "%s:%d" % (path.name, number))
            self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"), path.name)

    def test_six_section_headers(self):
        for path in all_python():
            doc = header(path)
            self.assertTrue(doc.lstrip().startswith("File: " + path.relative_to(REPO).as_posix()), path.name)
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


class ChangelogTests(unittest.TestCase):
    def text(self):
        return (REPO / "CHANGELOG.md").read_text()

    def test_newest_entry_is_v3(self):
        self.assertEqual(re.search(r"^## (v\d+\.\d+\.\d+)", self.text(), re.M).group(1), "v3.0.0")

    def test_entry_names_every_module_and_probe(self):
        entry = self.text().split("## v2.0.0")[0]
        for name in PRODUCT:
            self.assertTrue("brisart_%s.py" % name in entry, name)
        for ident, _, _ in build_checks():
            self.assertRegex(entry, r"\b%s\b" % ident)

    def test_v1_and_v2_are_untouched_by_the_entry(self):
        text = self.text()
        self.assertEqual(text.count("## v2.0.0"), 1)
        self.assertEqual(text.count("## v1.0.0"), 1)


if __name__ == "__main__":
    unittest.main()
