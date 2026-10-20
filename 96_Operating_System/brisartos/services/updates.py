r"""
File: brisartos/services/updates.py

Purpose
-------
Hold named source-text candidates in memory, returning their contents and fixed
unapplied, unauthenticated flags for inspection.

Public interface:
- class Updates -- A holding area for candidate update text.
- Updates.status() -- Return online.
- Updates.stage(name, source) -- Store source text under a unique name.
- Updates.inspect(name) -- Return the name, the source, applied False and
  authenticated False.
- Updates.discard(name) -- Remove a staged candidate.
- Updates.names() -- Return the sorted candidate names.

Design notes:

stage rejects an empty or non-text name, a non-text source and duplicate names.
Empty source text is accepted. inspect returns a fresh record and discard
removes one candidate. There is no parser, verifier, installer or execution
path in this class.

Communication / relationships
-----------------------------
Depends on (project modules):
- version (version.py)
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
Covered by tests: brisartos/services/tests/test_services.py.

Settings / parameters
---------------------
No module-level settings.

Edge cases
----------
A duplicate, empty or non-text name, or a non-text source, raises ValueError;
empty source text is accepted; inspecting or discarding an unknown candidate
raises KeyError.

- Updates.stage() raises ValueError: "update name and source text required"
- Updates.stage() raises ValueError: "update candidate already staged: {...}"
- Updates.inspect() raises KeyError: "unknown update candidate: {...}"
- Updates.discard() raises KeyError: "unknown update candidate: {...}"

Known limitations
-----------------
- Candidates live in memory only.
- Nothing authenticates a candidate or distinguishes a genuine update from any
  other text.

Examples
--------
Run from the repository root.

::

    from brisartos.services.updates import Updates

    updates = Updates()
    updates.stage('candidate', 'x = 1')
    result = updates.inspect('candidate')
    assert result['applied'] is False and result['authenticated'] is False
    updates.discard('candidate')
    assert updates.names() == []
"""

from version import __version__


class Updates:
    def __init__(self):
        self.version = __version__
        self._candidates = {}

    def status(self):
        return 'online'

    def stage(self, name, source):
        if not isinstance(name, str) or not name or not isinstance(source, str):
            raise ValueError('update name and source text required')
        if name in self._candidates:
            raise ValueError('update candidate already staged: ' + name)
        self._candidates[name] = source

    def inspect(self, name):
        if name not in self._candidates:
            raise KeyError('unknown update candidate: ' + str(name))
        return {'name': name, 'source': self._candidates[name],
                'applied': False, 'authenticated': False}

    def discard(self, name):
        if name not in self._candidates:
            raise KeyError('unknown update candidate: ' + str(name))
        del self._candidates[name]

    def names(self):
        return sorted(self._candidates)
