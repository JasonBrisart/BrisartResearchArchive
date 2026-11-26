# IO

This folder owns local file discovery, supported-format reading, content extraction, and input cleaning. Readers operate on local paths and do not perform internet research.

Extraction limits and malformed-file handling are enforced by the relevant readers. The resulting text is handed to the knowledge ingestion path; this folder does not own the SQLite index or answer citations.

## Files and behavior

`readers.py` selects local file handlers and enumerates supported paths; `binary_readers.py` extracts text from supported document containers; `extractor.py` converts locally stored HTML and CSV to text; `input_cleaner.py` normalizes entered questions. `tests/` covers extraction and malformed inputs. HTML parsing is not internet fetching.

The Browse Files picker in Add Sources filters by the supported extension registry; the folder import recursively discovers supported files and ignores unsupported formats.
