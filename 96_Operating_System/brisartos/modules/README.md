# Module API and Registry

`api.py` and `registry.py` implement module declaration validation, registration, discovery and permission-checked invocation.

## `api.py`: declaration checks and the API object

`MODULE_ABI` is `brisartos.module.v1`. `check_permissions()` accepts a tuple, list, set or frozenset, validates its entries and returns a sorted de-duplicated tuple. A bare string raises `TypeError`; an unsupported permission raises `ValueError`. Service permission suffixes must pass the shared name validator.

| Permission | Gated API calls |
| --- | --- |
| `log` | `log(message)` |
| `storage` | `write_text(filename, text)`, `read_text(filename)`, `list_files()` |
| `object_id` | `new_object_id()` |
| `platform_info` | `platform_info()` |
| `service:NAME` | `get_service(NAME)` for the named service |

`now_utc()` and `available_services()` need no permission. Missing permission raises `AccessDenied`, a `PermissionError` subclass.

`ModuleAPI(kernel, name, permissions)` validates its module name and stores permissions as a frozenset. Direct construction does not call `check_permissions()`; registry registration does. File operations normalize the filename and prepend `/modules/NAME/`. Missing `read_text()` returns `None`; `list_files()` strips the namespace prefix from results.

These checks govern API calls only. Module code runs in the same process and is not restricted to this API.

## `registry.py`: records and invocation

`ModuleRegistry(kernel)` stores module records and a discovery-failure mapping. `register()` requires a safe unused name, callable entry and valid permission declaration. It stores description, author, version, origin and display name; an absent or false display name falls back to the module name.

`describe(name)` returns a copy of metadata without the entry function. `names()` returns sorted names. Unknown records raise `KeyError`.

`run(name)` creates a ModuleAPI, logs `module started`, calls the entry and logs `module finished`. An entry exception, including `SystemExit` or `KeyboardInterrupt`, is logged as failed and re-raised. A logging failure is not separately recovered and can prevent or mask the entry outcome.

## Discovery contract

`REQUIRED_NAMES` contains these eight declarations:

| Name | Registry use |
| --- | --- |
| `MODULE_NAME` | Validated registry key |
| `MODULE_DISPLAY_NAME` | Display metadata |
| `MODULE_VERSION` | Version metadata |
| `MODULE_AUTHOR` | Author metadata |
| `MODULE_DESCRIPTION` | Description metadata |
| `MODULE_ABI` | Must equal `brisartos.module.v1` |
| `MODULE_PERMISSIONS` | Validated permission collection |
| `run` | Callable entry invoked as `run(api)` |

`discover(folder)` first retains only records whose origin is `code` and clears previous failures. It then requests sorted entry files from the loader, executes each file, checks declarations and ABI, and registers the entry. An `Exception` is recorded under the folder label and discovery continues. Base exceptions are not caught by discovery.

A duplicate declaration loses to the earlier registered name. Reload executes entry files again, replacing their module-level state; code-origin registrations survive. Loading happens before validation, so validation cannot make loading untrusted code safe.

## Checks in `tests/`

`tests/test_api.py` checks permission gates, service scoping, normalized module-local paths and permission declarations. `tests/test_registry.py` checks registration, metadata, discovery failures, reload, logged exceptions and the shipped module. Its documentation tests require this page to name the declarations, permissions and ABI above.
