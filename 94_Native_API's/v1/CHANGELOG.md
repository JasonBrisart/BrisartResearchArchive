# v1 Changelog

v1 contains the first implementation of each Brisart Native API listed below.

APIs are listed alphabetically.

---

## codec

**File:** `brisart_codec.py`

### Added

- Standard Base64 encoding and decoding.
- URL-safe Base64 decoding.
- Support for decoding unpadded Base64 input.

### Public API

- `brisart_b64encode()`
- `brisart_b64decode()`
- `brisart_urlsafe_b64decode()`

### Compatibility

- Implements RFC 4648 Base64 functionality through a standalone Brisart implementation.
- Does not depend on Python's `base64` module.
- The original decoder accepts some malformed or noncanonical input that later generations reject.

---

## csv

**File:** `brisart_csv.py`

### Added

- RFC 4180 CSV reading and writing.
- Configurable delimiter and quote characters.
- Field-size and row-count limits.
- Optional spreadsheet-formula escaping.

### Public API

- `BrisartCSVError`
- `brisart_csv_reader()`
- `brisart_csv_loads()`
- `brisart_csv_dumps()`

### Compatibility

- Accepts text input as `str`.
- Parsing is intentionally stricter than Python's `csv.reader` for quotes inside unquoted fields.
- Does not provide dialect sniffing, `escapechar`, `skipinitialspace`, `QUOTE_NONNUMERIC`, or streaming file input.
- Formula escaping changes field data and is disabled by default.

---

## deflate

**File:** `brisart_deflate.py`

### Added

- Raw DEFLATE compression.
- zlib stream compression.
- gzip stream compression.
- Compression levels from 0 through 9.
- Deterministic gzip output by default.

### Public API

- `brisart_deflate()`
- `brisart_zlib_compress()`
- `brisart_gzip_compress()`

### Compatibility

- Produces valid DEFLATE, zlib, and gzip streams, but output is not expected to be byte-identical to Python's `zlib` or `gzip` output.
- Uses a whole-buffer interface rather than a streaming compression interface.
- Does not provide flush modes or preset dictionaries.

---

## hash

**File:** `brisart_hash.py`

### Added

- SHA-256 hashing.
- Incremental hash updates.
- Digest, hexadecimal digest, and hash-object copying.
- Stable string fingerprinting.

### Public API

- `BrisartHash256`
- `brisart_sha256()`
- `brisart_stable_hash()`

### Compatibility

- Implements SHA-256 through a standalone Brisart implementation.
- Does not depend on Python's `hashlib` module.
- The original convenience interfaces accept some values differently from `hashlib`; later generations tighten those rules.

---

## inflate

**File:** `brisart_inflate.py`

### Added

- Raw DEFLATE decompression.
- zlib stream decompression.
- Adler-32 checksum calculation.
- Stored, fixed-Huffman, and dynamic-Huffman block support.

### Public API

- `BrisartBitReader`
- `brisart_inflate()`
- `brisart_adler32()`
- `brisart_zlib_decompress()`

### Compatibility

- Implements whole-buffer decompression rather than incremental streaming.
- Does not support preset dictionaries.
- The original implementation does not impose a decompressed-output limit and accepts some malformed streams that later generations reject.

---

## json

**File:** `brisart_json.py`

### Added

- JSON parsing.
- JSON serialization.
- Indented output.
- Deterministic key sorting.
- Structured decode errors.

### Public API

- `BrisartJSONDecodeError`
- `brisart_loads()`
- `brisart_dumps()`

### Compatibility

- Implements JSON parsing and serialization through a standalone Brisart implementation.
- Does not depend on Python's `json` module.
- The original implementation accepts several nonstandard or malformed values that later generations reject.
- Deeply nested or self-referential values can reach Python's recursion limit.

---

## markup

**File:** `brisart_markup.py`

### Added

- Lenient HTML tokenization.
- Incremental input through `feed()` and `close()`.
- Start-tag, end-tag, self-closing-tag, and text callbacks.
- Numeric and selected named character-reference decoding.
- Raw-text handling for `script`, `style`, `textarea`, and `title`.

### Public API

- `BrisartMarkupParser`
- `brisart_unescape()`

### Compatibility

- Provides a standalone Brisart alternative to the supported portions of `html.parser.HTMLParser` and `html.unescape`.
- Implements a limited named-character-reference table rather than the complete HTML entity set.
- The original tokenizer has parsing and performance limitations corrected in v2.

---

## robots

**File:** `brisart_robots.py`

### Added

- robots.txt parsing.
- User-agent group handling.
- `Allow`, `Disallow`, and `Crawl-delay` directives.
- URL fetch-policy evaluation.

### Public API

- `BrisartRobotsPolicy`

### Compatibility

- Models the original targeted `urllib.robotparser.RobotFileParser` behavior, including several of its policy quirks.
- URL processing depends on the Brisart URL API.
- The original matching and group rules are revised in v2.

---

## url

**File:** `brisart_url.py`

### Added

- URL splitting and reconstruction.
- Relative URL resolution.
- Percent encoding and decoding.
- Query-string encoding and parsing.
- Hostname extraction and dot-segment normalization.

### Public API

- `BrisartSplitResult`
- `brisart_urlsplit()`
- `brisart_urlunsplit()`
- `brisart_quote()`
- `brisart_unquote()`
- `brisart_urlencode()`
- `brisart_parse_qsl()`
- `brisart_urljoin()`

### Compatibility

- Implements the supported URL operations through a standalone Brisart implementation.
- Does not depend on Python's `urllib.parse` module.
- Malformed percent escapes are preserved rather than rejected.
- The original implementation accepts ambiguous authorities and other malformed input that later generations reject.
