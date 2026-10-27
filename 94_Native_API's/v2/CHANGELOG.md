# v2 Changelog

v2 contains the first substantive revision of applicable Brisart Native APIs.

Only APIs with a v2 implementation are listed below. APIs are listed alphabetically.

---

## codec

**File:** `brisart_codec.py`

### Changed

- Replaced automatic Base64 normalization with explicit padding, whitespace, canonical-form, and output-limit policies.
- Invalid content is rejected instead of being silently repaired or partially decoded.
- Encoding and decoding use lookup tables rather than per-character dictionary processing.

### Why

v1 accepted malformed padding, ignored surrounding whitespace, accepted non-zero trailing bits, and could decode content after padding. Those behaviors made it difficult for callers to know whether input had been preserved exactly or silently normalized.

### How

- Added explicit decoder padding modes: `"optional"`, `"required"`, and `"forbidden"`.
- Added opt-in whitespace removal through `allow_whitespace`.
- Added canonical trailing-bit validation.
- Added decoded-output size checking before decoding begins.
- Added explicit bytes-like and ASCII-text input handling.

### Added

- `BrisartBase64Error`
- `brisart_urlsafe_b64encode()`
- Encoder `padding`
- Decoder `padding`
- `canonical`
- `allow_whitespace`
- `max_output`

### Compatibility

- Missing padding remains accepted under the default `"optional"` policy.
- Inputs accepted or repaired by v1 can be rejected by v2.
- Unsupported input types raise `TypeError`.
- Invalid option values can raise `ValueError` rather than `BrisartBase64Error`.
- The implementation remains whole-buffer and is not constant-time.

---

## hash

**File:** `brisart_hash.py`

### Changed

- Reworked SHA-256 block processing while preserving the incremental hash-object interface.
- Tightened constructor and helper input validation.
- Changed stable-string encoding from UTF-8 `"replace"` to `"surrogatepass"`.
- Renamed the `BrisartHash256` constructor parameter from `initial_data` to `data`.

### Why

v1 treated false-like unsupported values as empty input and converted lone surrogates to replacement characters before hashing. That allowed distinct inputs to collapse to the same encoded bytes and made the convenience interface behave differently from the intended bytes-like contract.

### How

- Complete blocks are processed by offset, retaining only the incomplete trailing block between updates.
- Construction validates supplied input even when the value is false-like.
- Stable hashing requires `str` and preserves lone surrogates through `"surrogatepass"`.
- Final message length is masked to the SHA-256 64-bit length field.

### Added

- An empty-input default for `brisart_sha256()`.
- Explicit bytes-like input handling.

### Compatibility

- `None`, integers, and text passed to the hash constructor are rejected instead of being treated as empty input.
- Calls using `initial_data=` must use `data=`.
- Strings containing lone surrogates produce different fingerprints from v1. Stored identifiers, indexes, or caches derived from those values may require migration.
- The implementation is not constant-time or side-channel hardened.

---

## inflate

**File:** `brisart_inflate.py`

### Changed

- Added decompressed-output limits and explicit stream-boundary handling.
- Rejects additional malformed DEFLATE and zlib structures.
- Reworked Huffman decoding and back-reference copying.
- Corrected Adler-32 seed normalization and checksum-boundary handling.

### Why

v1 allowed unbounded decompressed output, accepted several malformed stream structures, and assumed that the final four input bytes contained the zlib checksum. Callers could not safely distinguish one complete stream from trailing data or constrain decompression growth.

### How

- Added a default 32 MiB output limit with an explicit override.
- Added prefix decoding that reports where one raw DEFLATE stream ends.
- Added trailing-data rejection by default.
- Added stored-block complement validation, Huffman-table validation, truncated-read checks, dynamic-table bounds, and end-of-block checks.
- Reads the checksum at the decoded stream boundary.
- Uses flat Huffman lookup tables, buffered bit reads, and slice-based LZ77 copying.

### Added

- `BrisartInflateError`
- `BrisartInflateUnsupported`
- `DEFAULT_MAX_OUTPUT`
- `max_output`
- `allow_trailing`
- `brisart_inflate_prefix()`
- Optional starting position for `BrisartBitReader`

### Compatibility

- Streams producing more than 32 MiB require a larger `max_output` or `max_output=None`.
- Inputs with trailing bytes require `allow_trailing=True` or deliberate prefix decoding.
- Malformed streams tolerated by v1 can now fail.
- Disabling checksum comparison still requires checksum bytes to be present.
- The output limit is not a complete memory or execution-time budget.
- The interface remains whole-buffer. v2 does not add gzip framing, preset dictionaries, or incremental output.

---

## json

**File:** `brisart_json.py`

### Changed

- Replaced recursive parsing and serialization with explicit work stacks.
- Tightened number, Unicode-escape, duplicate-key, surrogate, and non-finite-number handling.
- Added configurable resource limits and serialization policies.
- Expanded structured decoding errors.

### Why

v1 accepted malformed numeric forms, nonstandard values, duplicate keys, and lone surrogates by default. Deep nesting and circular structures depended on Python recursion failures rather than deliberate limits and errors.

### How

- Added iterative container processing and explicit nesting tracking.
- Enforced RFC 8259 number grammar and exact four-digit Unicode escapes.
- Added policies for duplicate keys, non-finite numbers, and lone surrogates.
- Added circular-reference detection during serialization.
- Added input depth, document length, and numeric-literal limits.
- Rejects non-string object keys instead of converting them implicitly.

### Added

- `max_depth`
- `max_length`
- Numeric-literal length limit
- UTF-8 bytes-like input
- `duplicate_keys`
- `allow_nan`
- `allow_lone_surrogates`
- `ensure_ascii`
- Configurable `separators`
- Whitespace-string indentation
- `msg`, `pos`, `lineno`, and `colno` on `BrisartJSONDecodeError`

### Compatibility

- Documents accepted by v1 can fail under v2 defaults, including documents with duplicate keys, non-finite numeric values, lone surrogates, or malformed number forms.
- Individual compatibility options restore selected permissive behavior, not complete v1 behavior.
- Non-string dictionary keys must be converted deliberately before serialization.
- Serialized text can differ from v1 even when the decoded value is equivalent.
- The bytes-input length check occurs after decoding in v2 and is not an input-allocation ceiling.
- Streaming, custom encoders, and object hooks remain unsupported.

---

## markup

**File:** `brisart_markup.py`

### Changed

- Replaced regular-expression-based tag and attribute recognition with an index-based, quote-aware tokenizer.
- Expanded character-reference handling.
- Separated raw-text and RCDATA processing.
- Stabilized behavior across incremental `feed()` boundaries.
- Bounded rescanning of incomplete constructs.

### Why

v1 could terminate tags inside quoted values, normalize names with Unicode case folding, report duplicate attributes inconsistently, decode references in the wrong contexts, and produce results that depended on how input was split between `feed()` calls. Its scanning strategy could also grow poorly on adversarial input.

### How

- Uses quote-aware index scanning and HTML-defined whitespace.
- Uses ASCII-only lowercasing for tag and attribute names.
- Keeps the first duplicate attribute value.
- Replaces the limited entity table with expanded character-reference data and numeric-reference filtering.
- Buffers ordinary text before decoding character references.
- Handles raw-text, RCDATA, and plaintext contexts separately.
- Replaces NUL characters in names and attribute values with U+FFFD.

### Added

- `handle_comment()`
- `handle_decl()`
- `reset()`
- `brisart_unescape(..., attribute=True)`
- Expanded raw-text element handling
- `plaintext` handling

### Compatibility

- Callback contents and timing can differ from v1.
- Duplicate attributes, entity expansion, malformed input, and raw-text output can differ from v1.
- Consumers must not depend on one data callback per input chunk.
- The implementation remains a tokenizer rather than a browser-equivalent tree builder.
- The token stream is not a security sanitizer.
- No document-size or retained-text limit is imposed.

---

## robots

**File:** `brisart_robots.py`

### Changed

- Replaced v1's first-matching-rule policy with longest-pattern matching.
- Revised user-agent group selection and matching.
- Added internal path normalization and removed the runtime dependency on the URL module.
- Added parsing limits, status-based policies, and inspection fields.

### Why

v1 inherited order-dependent and substring-based behavior that could select broader or unintended groups and rules. It also lacked explicit input limits and a standard way to represent common HTTP-response outcomes.

### How

- Supports `*` wildcards and terminal `$` anchoring.
- Uses the longest matching rule, with `Allow` winning equal-length ties.
- Matches normalized user-agent product tokens rather than arbitrary substrings.
- Merges applicable named groups and uses wildcard groups only when no named group applies.
- Normalizes target paths while preserving encoded reserved characters as distinct values.
- Uses sequential matching rather than regular-expression backtracking.
- Caches applicable rules by user-agent token.

### Added

- Text, bytes-like, and iterable input to `parse()`.
- UTF-8 byte-order-mark handling.
- `max_bytes`, rule-count, line-length, and path-length limits.
- `mode`
- `truncated`
- `rule_count`
- `BrisartRobotsPolicy.for_status()`
- Decimal crawl-delay handling capped at 86,400 seconds.

### Compatibility

- The same policy and URL can produce a different decision from v1.
- In v2, `max_bytes` counts bytes for bytes-like input but characters for text and iterable input.
- Truncation or ignored overlong lines can omit restrictive rules. Callers must inspect `truncated` and apply their own acceptance policy.
- Fetching, redirects, caching, and origin association remain caller responsibilities.
- robots.txt evaluation is advisory and is not access control.

---

## url

**File:** `brisart_url.py`

### Changed

- Reworked URL splitting, reconstruction, quoting, query handling, and relative-reference resolution.
- Added stricter input validation and authority inspection.
- Preserved the presence of empty authorities, queries, and fragments.
- Corrected dot-segment and trailing-slash behavior.

### Why

v1 accepted ambiguous input, used Unicode case folding for schemes and hosts, replaced encoding errors, mishandled some RFC 3986 resolutions, and exposed limited authority validation. Those behaviors could hide important distinctions in URLs and delay malformed-authority errors until later use.

### How

- Trims leading and trailing C0 controls and spaces and removes tabs, carriage returns, and line feeds before parsing.
- Restricts schemes and case normalization to ASCII rules.
- Adds stricter `hostname` and `port` interpretation.
- Tracks whether authority, query, and fragment delimiters were present.
- Reworks dot-segment removal and relative-reference resolution around RFC 3986 section 5.2.
- Adds strict UTF-8 quoting by default with configurable error handling.
- Encodes bytes directly in form encoding.

### Added

- `port` on `BrisartSplitResult`
- Authority, query, and fragment presence flags
- Iteration, equality, and hashing for `BrisartSplitResult`
- Five-component sequence input to `brisart_urlunsplit()`
- Configurable quoting and unquoting errors
- Mapping input to `brisart_urlencode()`
- Default query-field limit of 1,000

### Compatibility

- Cleaning, joining, quoting, and reconstruction can produce different results from v1.
- Quoting uses strict UTF-8 by default instead of replacement encoding.
- Splitting does not reject every malformed authority. Callers must inspect `hostname` and handle `port` errors.
- A returned split result is not proof that a URL is safe to fetch.
- v2 does not provide WHATWG parsing, IDNA processing, IP-address validation, or destination authorization.
- `BrisartSplitResult` is mutable despite being hashable in v2. Do not mutate an instance while it is used as a dictionary key or set member.
- The query-field limit does not bound total query length or all decoding allocations.
