# Shipped Module Sources

This directory contains trusted drop-in module source folders; it is distinct from files written under the runtime storage namespace.

## Contents

[hello_lab/README.md](hello_lab/README.md) describes the shipped example. Its `manifest.txt` declares inert metadata and `module.py` provides `run(api)`. The loader implementation lives in [the extension system](../brisartos/extensions/README.md).

## Preferred manifest contract

Place `manifest.txt` beside `module.py`. Required fields are name, display_name, version, author, description, api, api_major, api_minor, permissions and entry. The shipped manifest uses `version=runtime`, `api=brisartos.module`, major 1, minor 0 and `entry=run`. Registry validates compatibility and permission declarations before executing the entry file. Invalid manifests are rejected without legacy fallback.

The permission vocabulary is `log`, `storage`, `object_id`, `platform_info` and `service:NAME`. The example uses `service:settings` plus log, storage and object_id. Service access returns narrow facades, not live lifecycle objects.

## Legacy compatibility

Manifest-free entries still require `MODULE_NAME`, `MODULE_DISPLAY_NAME`, `MODULE_VERSION`, `MODULE_AUTHOR`, `MODULE_DESCRIPTION`, `MODULE_ABI`, `MODULE_PERMISSIONS` and `run`. The legacy ABI is `brisartos.module.v1`; optional MODULE_API declares the explicit name/major/minor requirement. Legacy loading executes code before validation and is only suitable for trusted modules.

## Source and state

`modules/hello_lab/module.py` is source. `/modules/hello_lab/hello.txt` is a runtime file below the selected storage root. They are not the same path. Disk mode retains files and built-in service state; memory mode retains neither across new instances. An optional module-level stop() releases owned resources during kernel shutdown.

Manifests are compatibility metadata, not signatures. All loaded Python shares the host process. The registry integration tests and kernel architecture tests exercise the shipped entry and manifest-first path; no local tests/ directory is shipped here.
