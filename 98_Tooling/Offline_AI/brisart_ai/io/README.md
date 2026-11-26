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

## Extraction sequence

The readers enumerate selected paths, recognize supported file types, and obtain text using the appropriate extraction code. The ingestion layer then prepares that text for indexing. Keeping this division explicit prevents an extractor from acquiring responsibility for database transactions or search ranking.

Archive-based documents require additional care because compressed size and extracted content size differ. The binary readers enforce budgets on selected Office and OpenDocument XML members and reject DTD-bearing XML. The PDF raw-read limit applies to bytes read, not all possible decompression or parsing costs.

## Input quality and failure behavior

Some files may contain no searchable text, unsupported encodings, or malformed structures. The caller must distinguish a processed file from a successfully indexed one. The import progress display uses that distinction when reporting completed and indexed counts.

Input cleaning is separate from file extraction: it normalizes questions submitted for search rather than altering the original source documents. Tests should cover valid files, malformed containers, extraction budgets, and cases where the parser correctly returns no text.

