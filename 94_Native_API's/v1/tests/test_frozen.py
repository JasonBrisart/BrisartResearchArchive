"""
File: v1/tests/test_frozen.py

Purpose
-------
Hold v1 to its frozen state: every v1 module must be byte-identical to
the release recorded here, and its import list must be exactly what v1
shipped with. Also checks that every file in v1/tests is ASCII and has a
six-section header. v1 is end-of-life; if a v1 file changes, this test fails
so the change is a decision rather than an accident.

Communication / relationships
-----------------------------
Standard library: unittest, ast, hashlib, pathlib, plus support.py in
this folder.
Verifies: the seven files in v1/.

Settings / parameters
---------------------
- RELEASE_SHA256 -- SHA-256 of each v1 module as exported on 2026-10-21
  (the same values as the project manifest).
- RELEASE_IMPORTS -- The top-level imports each v1 module declares.

Edge cases
----------
Hashes are taken over the raw bytes, so a line-ending conversion (for
example by a Git autocrlf setting) also counts as a change.

Known limitations
-----------------
This test cannot tell a deliberate patch from an accident; update
RELEASE_SHA256 only together with a changelog entry for v1.

Examples
--------
::

    python -B -m unittest discover -s v1/tests -p test_frozen.py
"""

import ast
import hashlib
import unittest

import support

RELEASE_SHA256 = {
    "brisart_codec.py": "89a1c032533950919be48dcf69454ebdbb987e55b32bc34e725c3d6ee737d866",
    "brisart_hash.py": "a656e0c20141d14e2da4b63ed6280fdd086ccdc57685491527de27e38631237e",
    "brisart_inflate.py": "8ce596255663e36f984523c88a71553fb7b87163530daf7d74d00a2db1ff0276",
    "brisart_json.py": "7caed6f9ee0541f01db6cb918fe7d6eda7062a5ab012ac2539c3450b38c4aabf",
    "brisart_markup.py": "a45561c2ba16cfbded01e64a97cd2f7d1143cfdc5a00044d9b15d25ea3286ed5",
    "brisart_robots.py": "4c6286d28d494f320ab01291c2c5620a3f0b21a23662c1a3b2e5063c376ccbeb",
    "brisart_url.py": "15b8131ee603cabe7724a5e5aa367f47e256a8d6433b2a39c58d9c8c23f9653f",
}

RELEASE_IMPORTS = {
    "brisart_codec.py": ["__future__"],
    "brisart_hash.py": ["__future__", "typing"],
    "brisart_inflate.py": ["__future__", "typing"],
    "brisart_json.py": ["__future__", "typing"],
    "brisart_markup.py": ["__future__", "re", "typing"],
    "brisart_robots.py": ["__future__", "brisart_ai.native.brisart_url", "typing"],
    "brisart_url.py": ["__future__", "typing"],
}


class FrozenReleaseTests(unittest.TestCase):
    def test_module_set_is_unchanged(self):
        self.assertEqual(sorted(p.name for p in support.V1.glob("brisart_*.py")), sorted(RELEASE_SHA256))

    def test_every_module_is_byte_identical_to_the_release(self):
        for name, digest in RELEASE_SHA256.items():
            self.assertEqual(hashlib.sha256((support.V1 / name).read_bytes()).hexdigest(), digest, name)

    def test_import_lists_are_unchanged(self):
        for name, expected in RELEASE_IMPORTS.items():
            found = set()
            for node in ast.walk(ast.parse((support.V1 / name).read_text())):
                if isinstance(node, ast.Import):
                    found.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    found.add(node.module)
            self.assertEqual(sorted(found), expected, name)


class TestFileTests(unittest.TestCase):
    SECTIONS = ("Purpose", "Communication / relationships", "Settings / parameters", "Edge cases",
                "Known limitations", "Examples")

    def test_test_files_are_ascii_with_six_section_headers(self):
        for path in sorted((support.V1 / "tests").glob("*.py")):
            text = path.read_text()
            self.assertTrue(text.isascii(), path.name)
            doc = ast.get_docstring(ast.parse(text), clean=False)
            self.assertTrue(doc.lstrip().startswith("File: v1/tests/" + path.name), path.name)
            positions = [doc.index("\n%s\n%s\n" % (name, "-" * len(name))) for name in self.SECTIONS]
            self.assertEqual(positions, sorted(positions), path.name)


if __name__ == "__main__":
    unittest.main()
