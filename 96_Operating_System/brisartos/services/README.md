# Shared Service Objects

This directory implements a service registry and three instance-local services: settings, archive snapshots and update-candidate staging.

## `registry.py`: names and live objects

`ServiceRegistry.register(name, service)` validates a safe name and rejects duplicates. It stores the supplied object without requiring a service base class or protocol. `get()` returns that live object, `names()` sorts names and `describe()` returns name, version, status and class.

Missing version metadata becomes `unknown`; absent status becomes `no status`. If a status attribute exists, it is called. Exceptions or a non-callable status attribute propagate rather than becoming a health result.

## `settings.py`: shallow key/value storage

`Settings.set(key, value)` requires a non-empty string key and retains the value by reference. `get(key, default=None)` returns the value or default. `delete()` removes a known key and returns its value; unknown keys raise `KeyError`. An unhashable lookup or deletion key can raise `TypeError`.

`snapshot()` copies the dictionary but not its values. Mutating a returned mapping does not change the store's keys; mutating an object held as a value can still affect both views.

```python
from brisartos.services.settings import Settings

settings = Settings()
settings.set("theme", "plain")
copy = settings.snapshot()
copy["theme"] = "other"
assert settings.get("theme") == "plain"
assert settings.get("missing", "fallback") == "fallback"
```

## `archive.py`: named snapshots through supplied storage

`Archive(storage)` receives an object with snapshot and restore methods. `save(name)` requires a non-empty string and stores a snapshot excluding `PROTECTED`, currently `("/logs",)`. Saving the same name replaces its earlier snapshot.

`restore(name)` requires an existing snapshot and delegates restoration with the same protected prefixes as its keep list. `names()` sorts snapshot names. Storage errors propagate; this wrapper adds no rollback or disk serialization.

Snapshots are held in this Archive instance. Their contents can consume substantial memory, and they disappear with the instance. The protected-prefix behavior concerns the supplied storage operations, not a general immutable-log guarantee.

## `updates.py`: source text that is never applied

`Updates.stage(name, source)` requires a unique non-empty string name and string source. Empty source is accepted. `inspect(name)` returns a new record containing name, source, `applied: False` and `authenticated: False`. `discard()` removes a known candidate; `names()` sorts names.

```python
from brisartos.services.updates import Updates

updates = Updates()
updates.stage("empty_candidate", "")
assert updates.inspect("empty_candidate")["source"] == ""
assert updates.inspect("empty_candidate")["applied"] is False
updates.discard("empty_candidate")
assert updates.names() == []
```

There is no download, syntax validation, authentication, installation or execution path. The flags are fixed declarations, not verification results.

All three service classes expose the imported release version and a `status()` method returning `online`. None persists its own state to disk.

## Service tests

`tests/test_services.py` checks registry names and metadata, settings round trips and shallow copies, archive restoration with protected logs, and unapplied update staging. These are in-memory checks of the service methods, not persistence tests.
