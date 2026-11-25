# Local input

`readers.py` selects local file handlers and enumerates supported paths; `binary_readers.py` extracts text from supported document containers; `extractor.py` converts locally stored HTML and CSV to text; `input_cleaner.py` normalizes entered questions. `tests/` covers extraction and malformed inputs. HTML parsing is not internet fetching.

The Browse Files picker in Add Sources filters by the supported extension registry; the folder import recursively discovers supported files and ignores unsupported formats.
