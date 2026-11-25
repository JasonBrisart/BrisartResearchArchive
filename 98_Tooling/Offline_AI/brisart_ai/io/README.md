# brisart_ai/io/

The input layer turns supported files into indexable text. `readers.py` chooses the format handler; `binary_readers.py` reads document containers; `extractor.py` flattens HTML and CSV; `input_cleaner.py` normalizes desktop input.

## `readers.py`

**Supported files.** `is_supported(path)` is true when the lowercased suffix is in `SUPPORTED_EXTENSIONS`, or the lowercased file name is one of `dockerfile`, `makefile`, `license`, `readme` or `changelog`.

- Text: `.txt .md .markdown .rst .py .pyw .html .htm .csv .tsv .log .ini .cfg .conf .toml .xml .svg .yaml .yml .json .jsonl .ndjson .css .js .mjs .cjs .ts .tsx .jsx .java .c .h .cpp .hpp .cc .cs .go .rs .sh .bash .zsh .ps1 .bat .cmd .sql .tex .rtf .srt .vtt .properties .env .gitignore .dockerfile`
- Documents: `.docx .pptx .xlsx .odt .pdf`

A file named exactly `.env` or `.gitignore` has no suffix as far as Python is concerned, so it is not matched; `config.env` is.

**Finding files.** `iter_supported_files(paths)` takes a mix of files and folders, walks folders recursively, and yields each supported file once, de-duplicated by resolved path. Anything it cannot resolve or open is skipped silently.

**Reading a file.** `read_file(path)` returns searchable text:

| Type | Result |
|---|---|
| `.docx .pptx .xlsx .odt .pdf` | `binary_readers.py` |
| `.html .htm .svg` | The text from `html_to_text()` |
| `.csv` | `csv_to_text()` |
| `.tsv` | Tabs replaced by ` \| ` |
| `.json` | Pretty-printed with sorted keys and two-space indent; text that is not valid JSON is returned as written |
| `.jsonl .ndjson` | Each line pretty-printed the same way |
| `.rtf` | A rough regex strip of control words and braces |
| anything else | The file's text as written |

Plain text is read through `util.safe_read_text()`, which keeps the first 5,000,000 bytes and decodes them as UTF-8 with replacement characters.

---

## `binary_readers.py`

Best-effort text extraction that aims at searchable words, not faithful layout. Every function returns `""` on any failure instead of raising, so one bad file never stops an import.

- **`read_docx`**: every `word/*.xml` part of the archive.
- **`read_pptx`**: every slide and every notes slide, so speaker notes are searchable.
- **`read_xlsx`**: `xl/sharedStrings.xml` and every worksheet.
- **`read_odt`**: `content.xml`.
- **`read_pdf_best_effort(path, max_bytes=10_000_000)`**: scans the first `max_bytes` of the file for text in parentheses, then inflates each `stream ... endstream` block with the native `brisart_inflate` and scans that too. It does not decode fonts or hexadecimal strings, so a PDF that stores its text another way gives little or nothing.

The Office and OpenDocument readers open the file as a ZIP and read XML with `xml.etree.ElementTree`; both are standard library. Text nodes are joined with newlines.

---

## `extractor.py`

**`html_to_text(source, base_url="")`** returns `(title, text, links)`.

- `script`, `style`, `noscript`, `svg`, `canvas` and `template` content is skipped.
- Block-level tags (paragraphs, divs, list items, table cells, headings and similar) start a new line; runs of three or more line breaks collapse to two.
- `<sup>` elements whose class is `reference`, `cite-bracket` or `citation` are skipped, which removes footnote markers such as `[3]`. An ordinary superscript is kept.
- The title is the text inside `<title>`.
- Links are `<a href>` targets resolved against `base_url`, normalized, kept only when they are `http` or `https`, and de-duplicated in order of appearance.
- Malformed HTML does not raise; whatever was parsed before the problem is returned.

**`csv_to_text(source)`** turns each non-empty row into cells joined by ` | `. If the CSV module rejects the text, each line is split on commas instead.

`HTMLTextExtractor` is a subclass of the native `BrisartMarkupParser`.

---

## `input_cleaner.py`

`normalize_shellish_input(text)` trims whitespace and removes one pair of matching outer quotes (`"` or `'`). Inner quotes and mismatched quotes are left alone, and input that is only whitespace returns an empty string. It does no spelling or command correction.

---

## `tests/`

| File | Covers |
|---|---|
| `test_readers.py` | Supported types, folder walking and de-duplication, `read_file()` for each text type |
| `test_binary_readers.py` | Each Office and OpenDocument reader, corrupt archives, PDF text and deflate streams |
| `test_extractor.py` | Title, text and links, skipped tags, footnote markers, malformed HTML, CSV |
| `test_input_cleaner.py` | Trimming and quote removal |
