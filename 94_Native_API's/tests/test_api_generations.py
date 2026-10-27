"""
File: tests/test_api_generations.py

Purpose
-------
Keep per-API generation numbers contiguous and reject duplicate executable
implementations that differ only in comments, formatting or docstrings.

Communication / relationships
-----------------------------
Reads versioned modules, Official modules and README.md. Uses only the
Python standard library and does not import product modules.

Settings / parameters
---------------------
EXPECTED lists the reviewed generation set for every API. ROOT is the
repository directory containing this test's parent directory.

Edge cases
----------
Docstrings at module, class and function scope are excluded. Constants,
imports, function defaults, annotations and executable statements remain.

Known limitations
-----------------
AST inequality does not prove different behavior for every possible input.
The behavior suites and lineage probes supply additional sampled evidence.

Examples
--------
python -B -m unittest discover -s tests
"""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "codec": (1, 2, 3), "csv": (1,), "deflate": (1,),
    "hash": (1, 2, 3), "inflate": (1, 2, 3), "json": (1, 2, 3),
    "markup": (1, 2), "robots": (1, 2, 3), "url": (1, 2, 3),
}


def implementation(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr):
                value = node.body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    node.body.pop(0)
    return ast.dump(tree, include_attributes=False)


class GenerationTests(unittest.TestCase):
    def test_exact_api_inventory(self):
        actual = {}
        for folder in sorted(ROOT.glob("v[0-9]*")):
            if folder.is_dir() and folder.name[1:].isdigit():
                for path in folder.glob("brisart_*.py"):
                    actual.setdefault(path.stem[8:], []).append(int(folder.name[1:]))
        self.assertEqual({name: tuple(values) for name, values in actual.items()}, EXPECTED)

    def test_no_generation_gaps(self):
        for name, versions in EXPECTED.items():
            with self.subTest(api=name):
                self.assertEqual(versions, tuple(range(1, max(versions) + 1)))

    def test_no_duplicate_implementations(self):
        for name, versions in EXPECTED.items():
            seen = set()
            for version in versions:
                with self.subTest(api=name, version=version):
                    code = implementation(ROOT / ("v%d" % version) / ("brisart_%s.py" % name))
                    self.assertNotIn(code, seen)
                    seen.add(code)

    def test_official_matches_latest_generation(self):
        self.assertEqual({p.stem[8:] for p in (ROOT / "Official").glob("brisart_*.py")}, set(EXPECTED))
        for name, versions in EXPECTED.items():
            with self.subTest(api=name):
                filename = "brisart_%s.py" % name
                self.assertEqual((ROOT / "Official" / filename).read_bytes(),
                                 (ROOT / ("v%d" % max(versions)) / filename).read_bytes())

    def test_versioned_header_paths(self):
        for name, versions in EXPECTED.items():
            for version in versions:
                path = ROOT / ("v%d" % version) / ("brisart_%s.py" % name)
                doc = ast.get_docstring(ast.parse(path.read_text()))
                self.assertTrue(doc.startswith("File: " + path.relative_to(ROOT).as_posix()))

    def test_changelog_ownership(self):
        self.assertFalse((ROOT / "CHANGELOG.md").exists())
        for version in (1, 2, 3):
            folder = ROOT / ("v%d" % version)
            self.assertTrue((folder / "CHANGELOG.md").is_file())
        self.assertTrue((ROOT / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
