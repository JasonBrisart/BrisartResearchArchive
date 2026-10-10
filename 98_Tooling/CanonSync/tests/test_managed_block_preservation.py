"""
File: tests/test_managed_block_preservation.py

Purpose
-------
Check managed-block preservation and enabled-item selection.

Communication / relationships
-----------------------------
Imports existing project modules; runs under the project-scoped CI workflow.

Settings / parameters
---------------------
Uses unittest and temporary fixtures; no application settings are changed.

Edge cases
----------
Covers normal behavior and selected invalid or missing inputs.

Known limitations
-----------------
Targeted regression coverage only; not a complete application or GUI audit.

Examples
--------
Run python -m pytest -v from the containing project directory.
"""

import unittest
from canonsync_core import (
    BEGIN_MARKER, END_MARKER, build_managed_block, compose_block,
    normalize_whole, enabled_items,
)

class ManagedBlockPreservationTests(unittest.TestCase):
    def test_empty_destination_receives_one_managed_block(self):
        block = build_managed_block('canonical')
        result = compose_block('', block)
        self.assertEqual(result, block + '\n')
        self.assertEqual(result.count(BEGIN_MARKER), 1)
        self.assertEqual(result.count(END_MARKER), 1)

    def test_existing_local_content_is_preserved_when_inserting(self):
        result = compose_block('local-rule\n', build_managed_block('canonical'))
        self.assertIn('local-rule', result)
        self.assertIn('canonical', result)

    def test_refresh_preserves_content_before_and_after_block(self):
        original = 'before\n' + build_managed_block('old-value') + '\nafter\n'
        result = compose_block(original, build_managed_block('new-value'))
        self.assertTrue(result.startswith('before\n'))
        self.assertTrue(result.endswith('after\n'))
        self.assertIn('new-value', result)
        self.assertNotIn('old-value', result)

    def test_repeated_refresh_is_idempotent(self):
        block = build_managed_block('canonical')
        first = compose_block('local-rule\n', block)
        self.assertEqual(compose_block(first, block), first)

    def test_whole_file_normalization_has_one_trailing_newline(self):
        self.assertEqual(normalize_whole('content\n\n'), 'content\n')
        self.assertEqual(normalize_whole('content'), 'content\n')

    def test_disabled_items_are_excluded(self):
        config = {'items': [{'name': 'a'}, {'name': 'b', 'enabled': False}]}
        self.assertEqual([i['name'] for i in enabled_items(config)], ['a'])

    def test_explicit_selection_does_not_reenable_disabled_items(self):
        config = {'items': [{'name': 'a'}, {'name': 'b', 'enabled': False}]}
        self.assertEqual(enabled_items(config, {'b'}), [])

