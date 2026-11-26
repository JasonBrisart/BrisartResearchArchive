# IO

This folder handles local input and text extraction. Its readers work with selected files and supported document containers; they do not fetch web pages or maintain the research index.

## File discovery and extraction

- `readers.py`: Enumerates supported local paths and dispatches extraction.
- `binary_readers.py`: Extracts text from supported binary and archive-based formats, with size and XML safety limits.
- `extractor.py`: Converts supported text-oriented content, including HTML and CSV, to searchable text.
- `input_cleaner.py`: Normalizes submitted questions before retrieval.
- `tests/`: Exercises format handling, malformed inputs, resource limits and cleaning behavior.

## Boundaries and limitations

Extraction returns text to the ingestion layer; it does not write SQLite records or decide which passage answers a question. Document parsing is best-effort and is not a security sandbox. See [Security](../../docs/SECURITY.md) for input limits and local-data considerations.
