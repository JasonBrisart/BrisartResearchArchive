# Hello Lab Module

`module.py` demonstrates identifier generation, a module-local file write, a settings update and a log message.

## What the entry actually does

`run(api)` performs these operations in order:

1. Request a fresh identifier with `new_object_id()`.
2. Replace `hello.txt` with a greeting and the identifier.
3. Set `hello_lab.last_id` on the settings service.
4. Log the path written.
5. Return a summary containing that path and identifier.

`MODULE_PERMISSIONS` therefore declares `object_id`, `storage`, `service:settings` and `log`. This is not a demonstration of every API method: it does not read or list files, request platform facts or enumerate services.

## Metadata in `module.py`

The registry name is `hello_lab`, the display name is `Hello Lab`, and the ABI is `brisartos.module.v1`. The module version is imported from the root-level version module. Author and description are stored as metadata alongside those declarations.

## Repeated runs and failures

Each run replaces the same file and settings key with a newly generated identifier. The module's own log call appends a message; registry start/finish records are outside this entry body.

The file path returned by the API is `/modules/hello_lab/hello.txt`. Its persistence depends on the supplied storage backend. The settings value belongs to the live settings object and is not saved by this module.

The entry catches no exceptions. If identifier generation, writing, service access or logging fails, the exception propagates. Earlier successful effects are not rolled back. Removing a declared permission can therefore leave partial effects before a later call is refused.

## Running the shipped example

```text
BrisartOS> run hello_lab
```

The returned identifier varies. The entry is loaded and exercised by the module registry integration test; this directory contains no separate test file.
