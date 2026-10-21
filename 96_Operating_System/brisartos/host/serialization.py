r"""
File: brisartos/host/serialization.py

Purpose
-------
Encode deterministic JSON mappings and decode mapping-only state documents
using the host standard library.

Public interface:
- encode_mapping(value) -- Return deterministic JSON text for a mapping; reject
  unsupported values.
- decode_mapping(text) -- Decode JSON text and require a mapping at its root.

Design notes:

Serialization is injected into stateful services. Encoding rejects non-finite
floats and unsupported objects rather than silently converting them.

Communication / relationships
-----------------------------
Standard library: json.
Imported by:
- brisartos/kernel/composition.py
Covered by tests: brisartos/kernel/tests/test_architecture.py,
brisartos/services/tests/test_services.py,
brisartos/storage/tests/test_state.py.

Settings / parameters
---------------------
Constructor arguments select the supplied components and policies; no
module-level configuration is defined.

Edge cases
----------
Invalid inputs are rejected before the documented operation; backend and
callback failures propagate unless explicitly collected.

- _plain() raises TypeError: "state keys must be text"
- _plain() raises TypeError: "state values must be JSON-compatible plain data"
- _invalid_constant() raises ValueError: "non-finite JSON number: {...}"
- encode_mapping() raises TypeError: "state must be a dictionary"
- decode_mapping() raises ValueError: "state document must contain a
  dictionary"

Known limitations
-----------------
- JSON-compatible values only; this is serialization, not authentication or
  encryption.
- Decoding does not impose a document-size or nesting budget.

Examples
--------
Run from the repository root.

::

    from brisartos.host.serialization import encode_mapping, decode_mapping
    assert decode_mapping(encode_mapping({'a': 1})) == {'a': 1}
"""
import json


def _plain(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError('state keys must be text')
            _plain(item)
    elif isinstance(value, list):
        for item in value:
            _plain(item)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise TypeError('state values must be JSON-compatible plain data')


def _invalid_constant(value):
    raise ValueError('non-finite JSON number: ' + value)

def encode_mapping(value):
    if not isinstance(value, dict):
        raise TypeError('state must be a dictionary')
    _plain(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n'

def decode_mapping(text):
    value = json.loads(text, parse_constant=_invalid_constant)
    if not isinstance(value, dict):
        raise ValueError('state document must contain a dictionary')
    return value
