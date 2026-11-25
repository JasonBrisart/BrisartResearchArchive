# Testing

From the Offline_AI directory, run:

```text
python scripts/run_tests.py -q
python scripts/debug_offline_replay.py
```

The test runner installs the external Native API path before collecting the co-located `unittest` tests through pytest. Set `BRISART_NATIVE_API` when the Archive's `94_Native_API's/Official` folder is not in the usual parent layout.

The tests cover local ingestion, ranking, citations, notes, settings, state migration, module resolution, layout and the absence of public-web runtime routes. The offline replay uses fixed fixtures and does not contact providers. Web provider, crawler and fetch tests are removed with their implementation.

No desktop GUI or Windows-specific file-locking behavior is exercised in this headless environment. Existing historical web rows are retained but are not eligible for answers.

On Windows, open Add Sources and drop a file and a folder from Explorer into the list. Verify that import begins only after clicking Import Sources. Then open Add Note, select the imported file, attach a highlighted passage, and verify that the note includes the excerpt and its original path. These desktop steps are not covered by the headless run.
