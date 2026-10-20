# Source Maintenance Tools

`audit.py` inspects repository rules and `headers.py` refreshes code-derived portions of Python file headers.

## Read-only audit: `audit.py`

```bash
python -B run.py audit
```

`audit()` returns status, Python-file count, sorted errors, import roots and a static-check caveat. `main()` prints the JSON report and returns 0 for PASS or 1 for FAIL.

The checks cover delivered file types and path names; required header structure and prose presence; relative imports and configured layer direction; selected host-only imports/calls/bytes literals; README mentions of Python files and subdirectories; and stale generated header content.

`LAYERS` maps the seven runtime directories to their import levels. Test files are exempt from product-layer/host restrictions but still require valid headers and imports. The README check uses substring presence, not a semantic comparison between prose and implementation.

This audit does not validate Markdown links or execute documentation examples. Those checks are implemented by the repository-wide tests. It also cannot prove runtime isolation, security or bootability.

## Header refresh: `headers.py`

```bash
python -B run.py headers
python -B tools/headers.py --check
```

`refresh(write, root=None)` parses selected Python files, builds static dependency information and reconstructs headers. `--check` reports stale files without writing. Normal mode writes files whose generated content changed and whose required descriptions are present.

Every Python header has six ordered sections:

- Purpose
- Communication / relationships
- Settings / parameters
- Edge cases
- Known limitations
- Examples

The tool derives public signatures, constants, import relationships, explicit raise/catch sites and test-method lists. Authored summaries, interface descriptions, design rationale, limitations and examples are retained. A missing public-name description, missing handler description or undescribed long constant is reported instead of silently producing an incomplete header.

Public descriptions are matched by name rather than full signature. Leading-underscore helpers and command-decorated handlers are omitted from the public-interface list. Test headings and method lists are generated differently from product interfaces.

## Reading the relationships accurately

The graph recognizes import statements and selected router string references. An `Imported by` line may therefore represent a router launch reference rather than an actual import. `Covered by tests` is based on static imports and is not a measured coverage report. Dynamic loading and child-process tests can exercise a file without appearing in that list.

Header refresh does not rewrite Markdown pages or judge whether authored prose remains true. Syntax errors encountered while building the source-tree map can stop refresh before per-file processing. A missing or malformed header is reported and left unchanged.

## Tests of the tools

`tests/test_tools.py` copies the project into temporary directories. It checks that a clean copy passes, deliberately breaks individual audit rules, and checks that header refresh preserves authored content while repairing generated fields. The tests launch child interpreters against those copies, not against an edited production tree.
