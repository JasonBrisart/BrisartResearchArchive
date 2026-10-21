# Module Contracts, Facades and Registry

`api.py`, `contracts.py`, `manifest.py` and `registry.py` separate permission-gated module calls, compatibility/service facades, manifest parsing and discovery/lifecycle coordination.

## `api.py`: context and permission gates

`ModuleContext(storage, services, events, platform)` holds the four shared runtime objects and an accepting flag. `accepting` is a read-only property: the kernel calls `close()` before startup and during shutdown and `open()` once it is running, and callers cannot assign it directly. Module file paths are built from `MODULES_PREFIX` in `storage/schema.py`. `ModuleAPI` validates its module name; registry registration validates permission declarations. Permission-gated methods refuse work after acceptance closes.

| Permission | API operations |
| --- | --- |
| `log` | `log(message)` |
| `storage` | `write_text`, `read_text`, `list_files` |
| `object_id` | `new_object_id()` |
| `platform_info` | `platform_info()` |
| `service:NAME` | `get_service(NAME)` |

`now_utc()` and `available_services()` remain ungated inspection methods. Storage calls normalize paths under `/modules/NAME/`; a missing read returns None. Missing permissions raise AccessDenied, a PermissionError subclass. These checks govern API use, not arbitrary Python capabilities.

## `contracts.py`: compatibility and narrow service views

The explicit API requirement is `(name, major, minor)`. The runtime name is `brisartos.module`, major is 1 and minor is 0. Name and major must match exactly; the runtime minor must meet or exceed the requested minor. Booleans, negative versions and malformed requirements are refused.

`SettingsAccess` exposes get/set/delete/snapshot. `ArchiveAccess` exposes save/restore/names. `UpdatesAccess` exposes stage/inspect/discard/names. `get_service()` returns these facades, not live service instances. Unknown services require an explicitly implemented facade. Lifecycle methods are not exposed. Private attributes remain reachable by trusted Python code, so this is not isolation.

## `manifest.py`: manifest text to fields

`parse_manifest(text)` turns manifest text into a dictionary of the ten fields, with `api_major` and `api_minor` as integers and `permissions` as a tuple. It checks structure only: the exact field set, no duplicates or unknown keys, the fixed entry name and nonnegative integer API versions. It does not judge names, permissions or API compatibility, and it reads no files. `FIELDS` and `ENTRY` define the schema in one place.

## `registry.py`: discovery and execution

`register()` validates name, entry, permissions, compatibility and optional shutdown callable. Metadata includes the negotiated API requirement. `run()` requires acceptance, records start, invokes `run(api)` and records finish or failure. Entry base exceptions are logged and re-raised; a logging failure can still mask an entry failure.

New modules supply inert `manifest.txt` metadata beside `module.py`. The host loader returns the manifest text without interpreting it, and `manifest.py` parses it. Registry checks names, permissions, duplicates and API compatibility before loading Python. A malformed or incompatible manifest never falls back to legacy execution. The entry must be callable after import.

Required manifest fields are `name`, `display_name`, `version`, `author`, `description`, `api`, `api_major`, `api_minor`, `permissions` and `entry`. `entry` must be run. `version=runtime` imports the release value rather than copying it. Permissions are comma-separated; an empty value means no permissions. Duplicate/unknown/missing fields are rejected.

## Legacy declarations

Without a manifest, the existing `brisartos.module.v1` ABI remains accepted. The eight required declarations are `MODULE_NAME`, `MODULE_DISPLAY_NAME`, `MODULE_VERSION`, `MODULE_AUTHOR`, `MODULE_DESCRIPTION`, `MODULE_ABI`, `MODULE_PERMISSIONS` and `run`. Optional `MODULE_API` supplies an explicit requirement; otherwise the current baseline requirement is assumed. This does not retroactively establish compatibility with older APIs that reused the ABI string.

Legacy Python executes before declaration validation. New manifest metadata is authoritative when present; redundant Python metadata is ignored. Neither path authenticates or sandboxes code.

## Cleanup and reload

An optional module-level `stop()` takes no arguments. `stop_all()` invokes hooks in reverse registration order, collects failures and clears hooks. During kernel shutdown, hooks cannot use permission-gated ModuleAPI calls because work acceptance is already closed; release resources directly owned by the module.

Discovery retains code-origin registrations and replaces discovered entries in alphabetical order. Reload is not transactional and does not guarantee cleanup of replaced module objects; modules holding external resources should be stopped with the kernel rather than relying on reload.

## Tests

`tests/test_api.py` covers gates, namespaces and facade use. `tests/test_registry.py` covers legacy registration/discovery and the shipped manifest module. `tests/test_manifest.py` covers manifest parsing and checks that every field is documented. `../kernel/tests/test_architecture.py` checks manifest rejection before execution, explicit compatibility, facade boundaries and cleanup failures.
