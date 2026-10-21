r"""
File: brisartos/extensions/tests/test_manifest.py

Purpose
-------
Exercise manifest parsing (field set, duplicates, integer versions, permission
splitting) and check that it applies no name, permission or API policy.

Verifies: brisartos/extensions/manifest.py.

Contains 11 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.extensions.manifest (brisartos/extensions/manifest.py)
Standard library: pathlib, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/extensions/tests); nothing imports it.

Settings / parameters
---------------------
Module fixtures: ROOT, GOOD.

Edge cases
----------
Parsing is checked as text only: no module code is imported and no kernel is
started. Policy decisions (names, permissions, API compatibility) belong to the
registry and are tested there.

ManifestTests:
- A complete manifest parses.
- Blank lines comments and spaces are ignored.
- Empty and spaced permissions.
- Unknown duplicate and malformed lines are refused.
- Missing fields are named.
- The entry must be run.
- Api versions must be nonnegative integers.
- The manifest must be text.
- Parsing does not judge names permissions or api.
- The shipped example manifest parses.
- Every field is documented.

Known limitations
-----------------
- Whether a manifest is accepted by the registry is tested in test_registry.py
  and the kernel architecture tests, not here.
- Passing proves only the 11 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/extensions/tests -p test_manifest.py
"""
import unittest
from pathlib import Path

from brisartos.extensions.manifest import FIELDS, parse_manifest

ROOT = Path(__file__).resolve().parents[3]
GOOD = ('name=demo\ndisplay_name=Demo\nversion=runtime\nauthor=Test\ndescription=A test module\n'
        'api=brisartos.module\napi_major=1\napi_minor=0\npermissions=log,storage\nentry=run\n')


class ManifestTests(unittest.TestCase):
    def test_a_complete_manifest_parses(self):
        fields = parse_manifest(GOOD)
        self.assertEqual(sorted(fields), sorted(FIELDS))
        self.assertEqual(fields['name'], 'demo')
        self.assertEqual(fields['description'], 'A test module')
        self.assertEqual((fields['api_major'], fields['api_minor']), (1, 0))
        self.assertEqual(fields['permissions'], ('log', 'storage'))

    def test_blank_lines_comments_and_spaces_are_ignored(self):
        text = '# a comment\n\n  name = demo  \n' + GOOD.split('\n', 1)[1]
        self.assertEqual(parse_manifest(text)['name'], 'demo')

    def test_empty_and_spaced_permissions(self):
        self.assertEqual(parse_manifest(GOOD.replace('log,storage', ''))['permissions'], ())
        self.assertEqual(parse_manifest(GOOD.replace('log,storage', ' log , service:settings '))['permissions'],
                         ('log', 'service:settings'))

    def test_unknown_duplicate_and_malformed_lines_are_refused(self):
        for bad in (GOOD + 'colour=red\n', GOOD + 'name=again\n', GOOD + 'no separator here\n', GOOD + '=x\n'):
            with self.assertRaisesRegex(ValueError, 'invalid or duplicate manifest field'):
                parse_manifest(bad)

    def test_missing_fields_are_named(self):
        with self.assertRaisesRegex(ValueError, 'missing manifest fields: author, version'):
            parse_manifest(GOOD.replace('author=Test\n', '').replace('version=runtime\n', ''))

    def test_the_entry_must_be_run(self):
        with self.assertRaisesRegex(ValueError, 'entry must be run'):
            parse_manifest(GOOD.replace('entry=run', 'entry=main'))

    def test_api_versions_must_be_nonnegative_integers(self):
        for bad in ('x', '-1', '1.5', '', '\u0661'):
            with self.assertRaisesRegex(ValueError, 'api_major must be a nonnegative integer'):
                parse_manifest(GOOD.replace('api_major=1', 'api_major=' + bad))

    def test_the_manifest_must_be_text(self):
        for bad in (None, b'name=demo', ['name=demo']):
            with self.assertRaises(TypeError):
                parse_manifest(bad)

    def test_parsing_does_not_judge_names_permissions_or_api(self):
        fields = parse_manifest(GOOD.replace('name=demo', 'name=../x').replace('log,storage', 'bogus')
                                .replace('api=brisartos.module', 'api=other').replace('api_major=1', 'api_major=9'))
        self.assertEqual((fields['name'], fields['permissions'], fields['api'], fields['api_major']),
                         ('../x', ('bogus',), 'other', 9))

    def test_the_shipped_example_manifest_parses(self):
        fields = parse_manifest((ROOT / 'modules' / 'hello_lab' / 'manifest.txt').read_text(encoding='utf-8'))
        self.assertEqual(fields['name'], 'hello_lab')
        self.assertEqual(fields['api'], 'brisartos.module')

    def test_every_field_is_documented(self):
        for path in (ROOT / 'brisartos' / 'extensions' / 'README.md', ROOT / 'modules' / 'README.md'):
            page = path.read_text(encoding='utf-8')
            for name in FIELDS:
                self.assertIn(name, page, str(path) + ': ' + name)


if __name__ == '__main__':
    unittest.main()
