# Shipped Module Directory

This directory contains the `hello_lab/` module folder supplied with BrisartOS.

## Contents and entry shape

[hello_lab/README.md](hello_lab/README.md) describes the actual example and its effects. Its `module.py` is the entry file. There are no other shipped module directories in this snapshot.

The directory itself contains no loader implementation. The [module-system README](../brisartos/modules/README.md) owns discovery, validation, API behavior and failure handling. This page records the entry contract used by the module stored here rather than inventing additional module examples.

## Declarations used by the shipped entry

| Name | Value or role in `hello_lab/module.py` |
| --- | --- |
| `MODULE_NAME` | `hello_lab` |
| `MODULE_DISPLAY_NAME` | `Hello Lab` |
| `MODULE_VERSION` | Imported BrisartOS release version |
| `MODULE_AUTHOR` | Author metadata |
| `MODULE_DESCRIPTION` | Description metadata |
| `MODULE_ABI` | `brisartos.module.v1` |
| `MODULE_PERMISSIONS` | The four permissions needed by the entry body |
| `run` | `run(api)` performs the example's operations |

The module-system permission vocabulary is `log`, `storage`, `object_id`, `platform_info` and `service:NAME`. The shipped entry uses `log`, `storage`, `object_id` and the specific service permission `service:settings`; it does not request `platform_info`.

## Source files and runtime files are different

The source entry lives here under `modules/hello_lab/`. Files written through its API belong to the BrisartOS storage namespace `/modules/hello_lab/`, not this source directory. In disk mode the console places that storage namespace below its data root.

The module source is executed during discovery. Only trusted entry files belong in a discovered module directory; declaration and permission checks do not isolate their top-level code.

The registry's integration test loads this shipped folder. There is no local `tests/` directory here; the implementation tests live with the module system.
