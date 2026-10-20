# Repository-Wide Tests

`test_project.py` checks rules spanning the BrisartOS tree rather than the behavior of a single runtime component.

## Three test classes in one file

`LayoutTests` checks path naming, the package-root layout, README/test presence in runtime directories, the allowed contents of `docs/` and a passing audit subprocess.

`VersionOwnershipTests` checks that the version module contains its header and one string assignment, that release literals are not copied into product files, and that the first changelog release heading names the current version. It does not compare release ordering or verify a distribution's provenance.

`DocumentationTests` checks relative Markdown links, closed fences, README openings and architecture coverage of the configured layers. It also extracts Python examples from file headers and fenced Markdown blocks and executes them in a child interpreter.

## Example execution is selective

Each extracted Python example receives a fresh namespace, but examples share one child process and run from the project root. Header examples beginning with a `python ` command are displayed rather than executed. Markdown Python blocks beginning with `# not run` are skipped. Non-Python fences are not replayed by these tests.

Links are checked for target existence, not anchor validity. README checks verify opening structure, not prose accuracy. A passing result does not establish that a documented capability exists beyond the checked code and examples.

## Running this directory

```bash
python -B -m unittest discover -s tests -p test_project.py
```

The root router's `test` command also discovers this directory. Its substring filter `tests` matches every test-folder path, so `run.py test tests` is not a way to isolate this one file.

The file defines `ROOT`, `RETIRED` and `HISTORY` fixtures and a `delivered()` helper. It reads the project tree and launches audit/example subprocesses; it does not create a fresh kernel in a shared setup fixture.
