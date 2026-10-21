# Brisart APIs Changelog

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