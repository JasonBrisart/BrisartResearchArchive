# Brisart APIs Changelog

---

## v2.0.0

### brisart_codec.py
- Added `brisart_urlsafe_b64encode()` and `BrisartBase64Error`.
- Added optional unpadded encoding.
- Added decoder controls for padding, canonical trailing bits, whitespace handling, and maximum output size.
- Replaced automatic padding repair and whitespace stripping with explicit Base64 validation.
- Added bytes-like input validation.
- Replaced character-by-character encoding and decoding with cached pair tables and byte-translation tables.

### brisart_hash.py
- Replaced repeated buffer deletion with offset-based block processing.
- Reworked SHA-256 compression with inline rotations and eight-round loop processing.
- Added an empty-input default to `brisart_sha256()`.
- Changed invalid input handling so values such as `None` raise `TypeError`.
- Changed final message-length handling to wrap modulo 2^64.
- Changed `brisart_stable_hash()` from UTF-8 replacement encoding to `surrogatepass`.
- Added explicit string validation to `brisart_stable_hash()`.

### brisart_inflate.py
- Added `BrisartInflateError` and `BrisartInflateUnsupported`.
- Added a configurable decompressed-output limit with a 32 MiB default.
- Added trailing-data rejection with an `allow_trailing` override.
- Added `brisart_inflate_prefix()`.
- Replaced dictionary-based Huffman decoding with flat lookup tables and buffered multi-bit reads.
- Replaced byte-by-byte back-reference copying with slice-based copying.
- Added validation for stored-block length complements.
- Added validation for truncated reads, malformed Huffman tables, invalid dynamic-table counts, repeat overruns, and missing end-of-block codes.
- Added zlib window-size validation.
- Changed checksum handling to locate the Adler-32 checksum from the decoded stream boundary.
- Fixed Adler-32 normalization for empty input with a non-normalized seed.
- Added Adler-32 seed validation.
- Added an optional starting position to `BrisartBitReader`.

### brisart_json.py
- Replaced recursive parsing and serialization with explicit work stacks.
- Added configurable nesting-depth limits.
- Added a document-length limit.
- Added a numeric-literal length limit.
- Added UTF-8 bytes-like input support.
- Tightened number parsing to reject leading zeros, incomplete fractions, incomplete exponents, non-ASCII digits, and floating-point overflow.
- Added exact four-digit hexadecimal validation for Unicode escapes.
- Changed duplicate object keys to errors by default, with `first` and `last` handling available as options.
- Changed NaN and Infinity to errors by default with optional support through `allow_nan`.
- Changed lone Unicode surrogates to errors by default with an opt-in override.
- Added circular-reference detection during serialization.
- Changed object serialization to reject non-string keys instead of stringifying them.
- Added `ensure_ascii`.
- Added configurable separators.
- Added string-based indentation support.
- Added indentation and separator validation.
- Changed serialization to escape U+2028 and U+2029.
- Expanded `BrisartJSONDecodeError` with `msg`, `pos`, `lineno`, and `colno`.
- Added optimized string scanning and scalar-container serialization paths.

### brisart_markup.py
- Replaced regular-expression parsing with an index-based, quote-aware tokenizer.
- Reworked input buffering to avoid repeatedly slicing and rescanning incomplete input.
- Changed tag and attribute name normalization to ASCII-only lowercasing.
- Changed attribute whitespace handling to HTML-defined whitespace.
- Changed duplicate attributes so the first occurrence is retained.
- Replaced the original limited named-entity table with expanded HTML character-reference data.
- Added legacy semicolon-less character-reference handling.
- Added attribute-specific character-reference decoding.
- Added HTML numeric-character-reference replacement behavior.
- Separated raw-text and RCDATA processing.
- Expanded raw-text element handling.
- Added `<plaintext>` handling.
- Changed raw-text handling so character references are not decoded inside elements such as `<script>` and `<style>`.
- Changed RCDATA handling so references are decoded inside `<textarea>` and `<title>`.
- Added stricter matching for raw-text and RCDATA closing tags.
- Added `handle_comment()`.
- Added `handle_decl()`.
- Added `reset()`.
- Changed handling of incomplete tags and comments.
- Changed self-closing-tag handling.
- Added NUL replacement handling.
- Changed incremental parsing so text is buffered across `feed()` boundaries before character-reference decoding.

### brisart_robots.py
- Replaced first-matching-rule behavior with longest-matching-rule evaluation.
- Added `*` wildcard matching.
- Added terminal `$` matching.
- Changed equal-length Allow/Disallow conflicts so Allow wins.
- Replaced substring user-agent matching with product-token matching.
- Changed matching groups so applicable groups can be combined.
- Changed blank-line handling so blank lines no longer discard or split groups.
- Added internal URL path and query normalization.
- Removed the dependency on `brisart_url.py`.
- Changed percent-encoding handling so encoded reserved characters remain distinct during rule matching.
- Added robots.txt input-size limits.
- Added rule-count limits.
- Added line-length limits.
- Added target path/query length limits.
- Added `BrisartRobotsPolicy.for_status()`.
- Added `mode`.
- Added `truncated`.
- Added `rule_count`.
- Changed `parse()` to accept text, bytes-like values, or iterables of lines.
- Added UTF-8 BOM handling.
- Added bounded iterable parsing.
- Expanded crawl-delay handling to accept non-negative decimal values.
- Added a maximum crawl-delay value.
- Added caching of applicable rules.

### brisart_url.py
- Added URL input validation.
- Added stripping of leading and trailing C0 controls and spaces.
- Added removal of tabs, carriage returns, and line feeds before parsing.
- Restricted scheme parsing to ASCII syntax.
- Changed scheme and hostname case normalization to ASCII-only lowercasing.
- Added stricter authority validation.
- Added the `port` property with decimal and range validation.
- Added explicit authority, query, and fragment presence tracking.
- Changed URL reconstruction to preserve empty `?` and `#` delimiters.
- Added iteration to `BrisartSplitResult`.
- Added equality and hashing to `BrisartSplitResult`.
- Expanded `brisart_urlunsplit()` to support five-component sequences.
- Added reconstruction protection for paths that could otherwise be reinterpreted as schemes or authorities.
- Reworked RFC 3986 dot-segment removal.
- Reworked relative-reference resolution.
- Corrected trailing-slash preservation during dot-segment resolution.
- Changed empty-reference handling so the base fragment is not incorrectly retained.
- Added configurable UTF-8 error handling to `brisart_quote()`.
- Added configurable UTF-8 error handling to `brisart_unquote()`.
- Added cached quoting tables.
- Added mapping support to `brisart_urlencode()`.
- Changed bytes handling in `brisart_urlencode()` so bytes are encoded directly instead of through their string representation.
- Added a configurable query-field limit with a default of 1,000 fields.

### Shared
- Removed `from __future__ import annotations`.
- Removed `typing` imports.
- Removed the `re` dependency from `brisart_markup.py`.
- Removed the sibling-module dependency from `brisart_robots.py`.
- Removed embedded `_self_test()` functions.
- Removed direct-execution self-test blocks.
- Changed module header paths from `brisart_ai/native/` to `brisart_native/`.
- Rewrote the module documentation to describe each v2 implementation's actual interfaces, parameters, edge cases, limitations, and examples.

---

## v1.0.0

### Added

#### `brisart_codec.py`

Introduced the Brisart Base64 encoding and decoding API as a native implementation of RFC 4648 functionality.

The module provides standard and URL-safe Base64 encoding and decoding, including support for decoding input with omitted padding. Encoding operates directly on byte groups and emits standard `=` padding where required.

Public interfaces include:

- `brisart_b64encode()`
- `brisart_b64decode()`
- `brisart_urlsafe_b64decode()`

The implementation performs its own byte and integer transformations and does not depend on Python's `base64` module.

The module includes internal self-tests covering empty input, standard RFC 4648 Base64 examples, decoding, string input, and unpadded input.


#### `brisart_hash.py`

Introduced the Brisart SHA-256 hashing API.

The module implements SHA-256 using the algorithm's defined initial hash values, round constants, message schedule, compression rounds, padding rules, and modulo-2^32 arithmetic.

`BrisartHash256` provides a streaming hash interface supporting incremental `update()` operations together with `digest()`, `hexdigest()`, and `copy()`.

Public interfaces include:

- `BrisartHash256`
- `brisart_sha256()`
- `brisart_stable_hash()`

The implementation does not depend on Python's `hashlib` module.

Internal self-tests compare produced hashes against published SHA-256 test vectors, including the empty message, `abc`, and a multi-block test message.


#### `brisart_inflate.py`

Introduced the Brisart DEFLATE and zlib decompression API.

The module implements raw DEFLATE stream decompression, including stored blocks, fixed Huffman blocks, dynamic Huffman blocks, canonical Huffman table construction, length/distance decoding, and overlapping LZ77 back-references.

A zlib stream wrapper provides header validation, DEFLATE payload extraction, and optional Adler-32 checksum verification.

Public interfaces include:

- `BrisartBitReader`
- `brisart_adler32()`
- `brisart_inflate()`
- `brisart_zlib_decompress()`

Preset-dictionary zlib streams are explicitly rejected rather than silently processed without the required dictionary.

The implementation does not depend on Python's `zlib` module.

The module includes an internal stored-block DEFLATE smoke test.


#### `brisart_json.py`

Introduced the Brisart JSON parsing and serialization API.

The module provides a hand-written recursive-descent JSON parser and serializer supporting objects, arrays, strings, numbers, booleans, null values, escape sequences, Unicode escapes, indentation, and sorted object keys.

Malformed input is reported through `BrisartJSONDecodeError`, including line, column, and character-position information.

Public interfaces include:

- `BrisartJSONDecodeError`
- `brisart_loads()`
- `brisart_dumps()`

The implementation does not depend on Python's `json` module.

Internal self-tests cover primitive values, strings, arrays, nested objects, Unicode escapes, deterministic key sorting, and serialization/deserialization round trips.


#### `brisart_markup.py`

Introduced the Brisart markup parsing API.

`BrisartMarkupParser` provides a lenient HTML tokenizer designed for subclass-based event handling through start-tag, end-tag, self-closing-tag, and data callbacks.

The parser supports incremental input, attribute extraction, comments, declarations, processing-instruction-style markup, raw-text elements, numeric character references, and a defined set of named HTML character references.

Public interfaces include:

- `BrisartMarkupParser`
- `brisart_unescape()`

Raw-text handling prevents markup-like content inside elements such as `script`, `style`, `textarea`, and `title` from being interpreted as ordinary nested markup.

Internal self-tests cover element and attribute parsing, character-reference decoding, void-element handling, and raw script content.


#### `brisart_robots.py`

Introduced the Brisart robots.txt policy API.

`BrisartRobotsPolicy` parses robots.txt directives and exposes policy decisions through `can_fetch()` together with crawl-delay retrieval through `crawl_delay()`.

The implementation supports:

- `User-agent`
- `Allow`
- `Disallow`
- `Crawl-delay`
- Default `*` groups
- Named user-agent groups

Rule evaluation intentionally models the behavior targeted by the implementation rather than introducing a separate robots-policy interpretation.

Public interfaces include:

- `BrisartRobotsPolicy`

URL processing is delegated to the Brisart URL implementation.

Internal self-tests cover named and default user agents, disallowed paths, crawl delays, empty policies, and mixed user-agent groups.


#### `brisart_url.py`

Introduced the Brisart URL manipulation API based on RFC 3986 behavior.

The module provides URL splitting and reconstruction, percent encoding and decoding, query-string encoding and parsing, relative URL resolution, hostname extraction, and dot-segment normalization.

`BrisartSplitResult` provides structured access to:

- `scheme`
- `netloc`
- `path`
- `query`
- `fragment`
- `hostname`

Public interfaces include:

- `BrisartSplitResult`
- `brisart_parse_qsl()`
- `brisart_quote()`
- `brisart_unquote()`
- `brisart_urlencode()`
- `brisart_urljoin()`
- `brisart_urlsplit()`
- `brisart_urlunsplit()`

Malformed percent escapes are preserved rather than rejected, while URL joining includes relative-path and dot-segment resolution.

The implementation does not depend on Python's `urllib.parse` module.

Internal self-tests cover URL decomposition, hostname normalization, percent encoding and decoding, malformed percent escapes, relative URL resolution, absolute-path resolution, parent-directory resolution, and network-path references.


### Architecture

Established Brisart APIs as the shared native API layer for the Brisart Research Archive software ecosystem.

The API layer separates general-purpose reusable implementations from software-specific application logic. Shared functionality can therefore be maintained independently of the individual Brisart software systems that consume it.

The initial API set provides reusable functionality for:

- Base64 encoding and decoding
- SHA-256 hashing
- DEFLATE decompression
- zlib stream decompression
- Adler-32 checksums
- JSON parsing and serialization
- HTML and markup parsing
- robots.txt policy evaluation
- URL parsing and reconstruction
- URL resolution
- Percent encoding and decoding
- Query-string processing

This establishes a common foundation that Brisart Research Archive software can consume without requiring separate copies of the same implementation inside each project.


### Compatibility

The initial release exposes purpose-built Brisart interfaces while several implementations are intentionally designed around behavior corresponding to Python standard-library functionality.

The source currently identifies compatibility targets including:

- `base64`
- `hashlib.sha256`
- `zlib.decompress`
- `json.loads` / `json.dumps`
- `html.parser.HTMLParser`
- `urllib.robotparser.RobotFileParser`
- `urllib.parse`

Compatibility claims are limited to the behavior implemented and exercised by the individual modules. The source does not establish complete behavioral equivalence with every corresponding Python standard-library API, complete platform compatibility, or complete security validation.