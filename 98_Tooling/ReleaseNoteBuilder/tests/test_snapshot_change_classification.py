"""
File: tests/test_snapshot_change_classification.py

Purpose
-------
Check added, removed, modified, and unchanged snapshot classification.

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

import copy
import unittest
from diff_engine import compare_snapshots

class SnapshotChangeClassificationTests(unittest.TestCase):
    def record(self, path, digest):
        return {'path': path, 'hash': digest}

    def test_empty_snapshots_have_no_changes(self):
        self.assertEqual(compare_snapshots({}, {}),
                         {'added': [], 'removed': [], 'modified': [], 'unchanged': []})

    def test_new_file_is_added(self):
        item = self.record('new.py', 'new')
        self.assertEqual(compare_snapshots({}, {'new.py': item})['added'], [item])

    def test_deleted_file_is_removed(self):
        item = self.record('old.py', 'old')
        self.assertEqual(compare_snapshots({'old.py': item}, {})['removed'], [item])

    def test_changed_hash_is_modified(self):
        old = self.record('main.py', 'old')
        new = self.record('main.py', 'new')
        result = compare_snapshots({'main.py': old}, {'main.py': new})
        self.assertEqual(result['modified'], [{'path': 'main.py', 'old': old, 'new': new}])
        self.assertEqual(result['unchanged'], [])

    def test_equal_hash_is_unchanged(self):
        item = self.record('main.py', 'same')
        result = compare_snapshots({'main.py': item}, {'main.py': dict(item)})
        self.assertEqual(result['unchanged'], [item])
        self.assertEqual(result['modified'], [])

    def test_added_results_are_sorted_by_path(self):
        new = {p: self.record(p, p) for p in ['z.py', 'a.py', 'm.py']}
        self.assertEqual([r['path'] for r in compare_snapshots({}, new)['added']],
                         ['a.py', 'm.py', 'z.py'])

    def test_comparison_does_not_mutate_input_snapshots(self):
        old = {'main.py': self.record('main.py', 'old')}
        new = {'main.py': self.record('main.py', 'new')}
        before = copy.deepcopy((old, new))
        compare_snapshots(old, new)
        self.assertEqual((old, new), before)

