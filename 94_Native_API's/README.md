# Brisart Native APIs

Standalone Python APIs within the Brisart Research Archive, organized by each API's own implementation generation.

## Directories

- `v1/`: the first implementation of each API, with its changelog and tests.
- `v2/`: the first substantive revision of an existing API, with its changelog and tests.
- `v3/`: the second substantive revision, with its changelog and tests.
- `Official/`: the assembled latest implementation of each API. This is not a separate numbered generation.
- `tests/`: cross-directory generation, duplicate-implementation, header-path and Official mapping checks.

A folder number is not a collection-wide release number. New APIs start at v1 even when other APIs have reached v3. A comment, header, example or formatting change alone does not create a new implementation generation. Higher-numbered directories are not complete replacements for lower-numbered directories.

## API inventory

| API | Available generations | Official source |
|---|---|---|
| codec | v1, v2, v3 | v3/brisart_codec.py |
| csv | v1 | v1/brisart_csv.py |
| deflate | v1 | v1/brisart_deflate.py |
| hash | v1, v2, v3 | v3/brisart_hash.py |
| inflate | v1, v2, v3 | v3/brisart_inflate.py |
| json | v1, v2, v3 | v3/brisart_json.py |
| markup | v1, v2 | v2/brisart_markup.py |
| robots | v1, v2, v3 | v3/brisart_robots.py |
| url | v1, v2, v3 | v3/brisart_url.py |

## Changelogs and audit

- [v1 changelog](v1/CHANGELOG.md): initial capabilities and original behavior.
- [v2 changelog](v2/CHANGELOG.md): changes from the first generation of the same API.
- [v3 changelog](v3/CHANGELOG.md): changes from the second generation of the same API.

## Running checks

Run each version's suite in a separate Python process because the test helpers install version-specific import paths and the v1 compatibility shim.

```text
python -B -m unittest discover -s v1/tests
python -B -m unittest discover -s v2/tests
python -B -m unittest discover -s v3/tests
python -B -m unittest discover -s tests
python -B v2/tests/v1_probe.py
python -B v3/tests/v2_probe.py
```
