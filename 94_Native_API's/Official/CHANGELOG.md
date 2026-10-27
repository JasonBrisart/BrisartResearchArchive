# Brisart APIs Changelog

This changelog records substantial changes to the Brisart APIs, including new capabilities, behavioral changes, compatibility boundaries, security hardening, architectural revisions, and material fixes.

---

## v3.0.0

### Release overview

Introduced the third-generation Brisart Native APIs under `v3/`, alongside the existing `v1/` and `v2/` implementations.

This release does two things. It closes five residual limits recorded in the v2.0.0 entry, one of which turned out to be a policy bug: a robots.txt line cut by the size budget was parsed as a shorter, broader rule. It also adds the standard-library replacements v2 did not cover: Base32/Base32hex/Base16, SHA-224, HMAC and digest comparison, CRC-32 and gzip decoding, a DEFLATE/zlib/gzip compressor, and an RFC 4180 CSV reader and writer. The compressor completes the zero-import compression path in both directions, which v2 had only for decoding.

All nine v3 modules import nothing, as in v2. The two new modules (`brisart_deflate.py`, `brisart_csv.py`) follow the same rules: one file each, no sibling imports, six-section headers.

Everything v3 inherits from v2 behaves as v2 did except where this entry says otherwise. That is checked by a test that feeds the same random and hostile inputs to both versions and requires identical results.

Every "v2 did X" statement below carries a probe ID. `v3/tests/v2_probe.py` loads `v2/` and `v3/` and reproduces each one, so the claims can be checked rather than taken on trust.

No stored data format is involved. There is no migration.

### Security

- **`v3/brisart_robots.py`: a line cut by the size budget is dropped, not parsed (V3).** When `parse()` truncated input at `max_bytes`, v2 parsed the partial last line. A cut-off `Allow: /public/reports/only` became `Allow: /public/r`, a broader rule that opened paths the site had not allowed. The probe reproduces this: with the budget ending 15 characters before the end of that line, v2 allows `/public/x` under a `Disallow: /` policy. v3 drops a partial final line whole, for str and bytes input; iterable input was already cut at whole lines. A cut-off Disallow line is also dropped. That is not fail-closed, so callers must still inspect `truncated`, as the v2 entry recorded.

- **`v3/brisart_robots.py`: the `max_bytes` budget counts UTF-8 bytes for every input form (V2).** v2 counted bytes for bytes input but characters for str and line-iterable input, so a str of multi-byte characters could exceed the stated budget by up to four times. The probe parses 100 lines of three euro signs (21 bytes per line) under a 224-byte budget: v2 keeps 14 rules (it counted 224 characters, about 300 bytes), v3 keeps the 10 that fit. ASCII input is unaffected.

### Fixed

- **`v3/brisart_json.py`: oversized bytes input is refused before it is decoded (V1).** v2 applied `max_length` only after decoding bytes to str, so a very large bytes argument was fully decoded, and any decoding error was reported, before the size check ran. v3 first rejects bytes input longer than `4 * max_length`. UTF-8 needs at most 4 bytes per character, so no input this check rejects could have passed the character limit. Input within that bound is decoded and checked exactly as before. The probe passes 1,202 bytes ending in an invalid byte with `max_length=100`: v2 reports the UTF-8 error, v3 reports the size limit.

- **`v3/brisart_url.py`: `BrisartSplitResult` is immutable and type-checked (V4, V5).** v2's result object defined `__hash__` but allowed attribute assignment, so mutating a result already used as a dictionary key or set member silently broke the lookup. The v2 entry recorded this as a caller obligation. In v3, assignment and deletion raise `AttributeError`. A new `replace(**components)` method returns a modified copy; when it changes the query, fragment or netloc, the matching "present" flag follows the new value unless given explicitly. The constructor also now requires str components; v2 accepted any value, so a non-str path surfaced only later as an unrelated error.

- **`v3/brisart_inflate.py`: the output cap is checked before a literal byte is written.** v2 appended a literal and then compared the length with `max_output`, contradicting its own header ("every write is checked ... before it happens"). Outputs and accept/reject decisions are identical, and the extra byte was never returned, so this has no probe; the header claim is now accurate.

### Added

- **`v3/brisart_codec.py`: Base32, Base32hex and Base16 (RFC 4648 sections 6-8) (A1).** New functions: `brisart_b32encode`, `brisart_b32decode`, `brisart_b16encode` and `brisart_b16decode`. A new exception, `BrisartBase32Error`, subclasses `BrisartBase64Error` and therefore `ValueError`. Decoding is strict in the same way as v2's Base64:
  - Only the valid group remainders (2, 4, 5 or 7 characters) are accepted, with exactly the matching padding count.
  - Trailing bits must be zero while `canonical=True`.
  - Characters outside the alphabet are rejected.
  - Base16 validates before calling `bytes.fromhex`, so the whitespace `fromhex` would skip is never accepted.

  Padding defaults to `"required"` for Base32 and case-sensitive matching for both, as in `base64.b32decode` and `b16decode`. `casefold=True` and `padding="optional"` relax these.

- **`v3/brisart_hash.py`: SHA-224, HMAC and digest comparison (A2).**
  - `BrisartHash224` and `brisart_sha224` (FIPS 180-4 section 6.3) share the SHA-256 core with their own IV. `copy()` now preserves the hash class.
  - `BrisartHMAC` and `brisart_hmac` implement RFC 2104 over SHA-256 or SHA-224, with `update()`, `digest()`, `hexdigest()` and `copy()`. A str key or an unsupported `digestmod` such as `"md5"` raises.
  - `brisart_compare_digest(a, b)` returns the same results and enforces the same type rules as `hmac.compare_digest`, without returning early at the first difference.

- **`v3/brisart_inflate.py`: CRC-32 and gzip decoding (A3).**
  - `brisart_crc32(data, value=0)` matches `zlib.crc32`.
  - `brisart_gzip_decompress` decodes RFC 1952 members. It validates the magic bytes, method, reserved flag bits, the bounds of the extra/name/comment fields, the optional header CRC16, the output CRC-32 and ISIZE. Concatenated members are joined, as `gzip.decompress` does, and `max_output` applies to their total.
  - It is stricter than `gzip.decompress` (CPython 3.12) in three documented ways: it checks FHCRC, which `gzip` skips; it rejects reserved flag bits, which `gzip` ignores; and it rejects trailing NUL padding, which `gzip` accepts. `allow_trailing=True` and `verify_checksum=False` relax the trailing and checksum checks.

- **`v3/brisart_deflate.py`: a DEFLATE compressor with zlib and gzip framing (A4).** The new module provides `brisart_deflate`, `brisart_zlib_compress` and `brisart_gzip_compress`, with levels 0-9 and `DEFAULT_LEVEL = 6`.
  - Matches are found with a 32 KiB hash-chain window and lazy matching from level 4 upward, using zlib's per-level table plus its TOO_FAR rule for distant 3-byte matches.
  - Each block is written as whichever of stored, fixed-Huffman or dynamic-Huffman is smallest. Dynamic codes use package-merge (optimal under the 15-bit and 7-bit limits) and run-length-encoded code lengths.
  - Output is deterministic. The gzip header records mtime 0 by default, no file name, and OS 255 ("unknown"), so archives do not reveal the host or the time of compression.

- **`v3/brisart_csv.py`: an RFC 4180 CSV reader and writer (A5).** The new module provides `brisart_csv_reader`, `brisart_csv_loads`, `brisart_csv_dumps`, `BrisartCSVError` (which carries `line` and `column`) and `DEFAULT_MAX_FIELD_SIZE`.
  - Reading agrees with `csv.reader(strict=True)` except that a quote inside an unquoted field is rejected by default (`strict_quotes=False` accepts it).
  - Fields are limited to 131,072 characters (as in `csv.field_size_limit`) and `max_rows` is optional. Scanning uses cached `str.find` positions, so reading stays linear even when a separator never occurs.
  - Writing matches `csv.writer` with `QUOTE_MINIMAL` or `QUOTE_ALL`. It refuses values other than str, int, float, bool and None instead of calling `str()` on them, and can optionally prefix formula-like fields with `'` to mitigate CSV injection (`escape_formulas=True`; off by default because it changes the data).

- **`v3/tests/`: 142 tests, a v2 probe and a v2-equivalence check.**
  - Per-module tests: `test_codec.py` (17), `test_hash.py` (15), `test_inflate.py` (15), `test_deflate.py` (13), `test_json.py` (11), `test_url.py` (17), `test_robots.py` (13), `test_markup.py` (12) and `test_csv.py` (9).
  - `test_v2_compat.py` (7) requires v2 and v3 to agree on random and hostile inputs for every behaviour this entry does not change.
  - `test_standards.py` (13) enforces zero imports, six-section headers, runnable header examples, and that this entry names every module and probe.
  - `v2_probe.py` reproduces probes V1-V5 and A1-A5.
  - The test suite written for v2 was not in this repository. These files are new and run against `v3/` and `v2/` in place.

### Changed

- **`v3/brisart_markup.py` is unchanged from v2 except for its header.** Its code is byte-identical to `v2/brisart_markup.py`; only the header's file path, example imports and test references changed.
- **Header paths and examples.** All module headers read `File: v3/...` and their examples import directly (`from brisart_json import ...`) with the `v3/` folder on `sys.path`, matching this repository's `v1/` / `v2/` / `v3/` layout instead of the earlier `brisart_native` package path.
- **Headers updated for the new behaviour and measured costs.** These cover Base32/Base16, SHA-224/HMAC, CRC-32/gzip, the robots budget and partial-line rule, the JSON bytes bound, and URL immutability. Every speed figure in a v3 header comes from a measurement on CPython 3.12.

### Compatibility and residual risk

- **Inherited behaviour.** For the seven modules inherited from v2, behaviour is unchanged apart from the items under Security and Fixed. `test_v2_compat.py` checks this on sampled inputs; it is not a proof.
- **`BrisartSplitResult` is now immutable.** Code that assigned to `.path`, `.query` or another attribute must use `replace()`. Code that passed non-str components to the constructor now gets `TypeError`.
- **robots.txt under a budget.** A policy parsed under a size budget can contain fewer rules than in v2 when the input contains multi-byte characters or is cut mid-line. Truncation is still not fail-closed in either direction: inspect `truncated` and apply your own policy.
- **JSON bytes errors.** Very large bytes input to `brisart_loads` now fails with the size-limit error instead of a UTF-8 error. Both are `BrisartJSONDecodeError`.
- **Compressor output is not zlib's.** Compressed streams are valid and decode everywhere tested, but they are not byte-identical to zlib's output; never compare compressed bytes across implementations. The compressor is slow: avoid levels 6-9 on large or short-token text, and use levels 1-3 for bulk data.
- **gzip strictness.** `brisart_gzip_decompress` rejects some files `gzip.decompress` accepts (bad header CRC, reserved flag bits, trailing NUL padding). Header fields (name, comment, mtime) are skipped, not returned.
- **`brisart_compare_digest` is not constant-time.** It avoids an early exit, but CPython makes no constant-time guarantee; prefer `hmac.compare_digest` where a timing attacker is realistic. SHA-224, SHA-256 and HMAC remain reference implementations, not hardened ones.
- **CSV limits.** Formula escaping is a mitigation, not a guarantee, and it changes the data. The CSV module has no dialect sniffing, escapechar or streaming file input.
- **Dependencies.** No external dependencies were introduced. Every module requires only a Python interpreter.

---

## v2.0.0

### Release overview

Introduced the second-generation Brisart Native APIs under `v2/`, alongside the existing `v1/` implementations.

This release replaces permissive or application-specific behavior with more explicit validation, configurable resource limits, expanded interfaces, and revised parsing semantics. Changes affect Base64 decoding, string fingerprinting, decompression, JSON handling, HTML tokenization, robots.txt evaluation, and URL processing.

The separate major-version directory preserves the v1 implementations while allowing consumers to migrate deliberately. v2 is not a behaviorally interchangeable replacement for v1: existing callers must account for changed defaults, rejected inputs, different policy decisions, and changed output representations.

### Changed: `v2/brisart_codec.py`

Reworked Base64 encoding and decoding around explicit input policies rather than v1's automatic whitespace stripping and padding repair.

- Added `brisart_urlsafe_b64encode()` to complement the existing URL-safe decoder.
- Added the encoder's `padding` option so callers can emit padded or unpadded output.
- Added decoder padding policies: `"optional"`, `"required"`, and `"forbidden"`.
- Added `canonical=True` to reject non-zero unused trailing bits.
- Added `allow_whitespace=False`; callers may explicitly permit removal of ASCII space, tab, carriage return, and line feed.
- Added `max_output` to reject inputs whose calculated decoded size exceeds the configured limit.
- Added `BrisartBase64Error`, derived from `ValueError`, for rejected Base64 content.
- Added explicit handling for `bytes`, `bytearray`, and `memoryview`; textual decoding input must be ASCII.
- Replaced per-character encoding assembly with cached two-character encoding tables.
- Replaced dictionary-based character decoding with byte-translation tables.

These changes make accepted input forms more deliberate and reduce reliance on silent normalization.

#### Compatibility and residual limits

Missing padding remains accepted under the default `"optional"` policy. Whitespace and non-zero trailing bits that v1 tolerated may now cause rejection.

Unsupported input types raise `TypeError`; invalid configuration may raise ordinary `ValueError`. Callers must not assume every failure is a `BrisartBase64Error`.

The decoder adds padding checks, but this release does not establish exhaustive rejection of every malformed padding combination. With optional padding, both padded and unpadded representations may remain accepted; `canonical=True` does not establish one unique textual representation.

The implementation remains whole-buffer and is not constant-time. `max_output` is optional and does not bound all input-validation allocations.

### Changed: `v2/brisart_hash.py`

Reworked SHA-256 block processing while retaining the streaming hash-object interface.

- Replaced repeated deletion from the front of the working buffer with offset-based processing of complete input blocks.
- Retained only the incomplete trailing block between updates.
- Replaced the previous round loop with inline rotation expressions and eight-round loop groups.
- Added an empty-input default to `brisart_sha256()`.
- Made construction validate input even when the supplied value is false-like, preventing values such as `None`, `0`, or an empty string from silently producing an empty-message hash.
- Added explicit bytes-like input handling.
- Changed final padding to mask the encoded bit length to 64 bits.
- Added explicit string validation to `brisart_stable_hash()`.
- Changed stable-string encoding from UTF-8 `"replace"` to `"surrogatepass"`.

The stable-string change prevents distinct lone-surrogate strings from being collapsed into replacement characters before hashing.

#### Compatibility and residual limits

Ordinary strings without lone surrogates retain the same UTF-8 input bytes. Strings containing lone surrogates can produce different fingerprints from v1. Persisted identifiers, deduplication indexes, or caches derived from those values require migration consideration.

`BrisartHash256` changes its constructor parameter name from `initial_data` to `data`. Callers using `initial_data=` must update their calls.

`update()` continues returning the hash object; this release does not establish complete behavioral equivalence with every `hashlib` interface.

Preserving distinct encoded input bytes does not make SHA-256 collision-free. The implementation is not constant-time or side-channel hardened. The processing changes do not establish a measured performance improvement without reproducible benchmark results.

### Changed and fixed: `v2/brisart_inflate.py`

Reworked raw DEFLATE and zlib decompression to expose stream boundaries, constrain output, and reject additional malformed structures.

- Added `BrisartInflateError`, derived from `ValueError`.
- Added `BrisartInflateUnsupported`, also derived from `NotImplementedError`, for unsupported preset-dictionary streams.
- Added `DEFAULT_MAX_OUTPUT`, set to 32 MiB, and configurable `max_output` arguments.
- Added default trailing-data rejection with an `allow_trailing` override.
- Added `brisart_inflate_prefix()`, returning decompressed bytes and the ending byte offset of one raw DEFLATE stream.
- Added an optional starting position to `BrisartBitReader`.
- Replaced dictionary-based Huffman decoding with flat lookup tables and buffered multi-bit reads.
- Replaced byte-by-byte LZ77 copying with slices for non-overlapping references and repeated-slice expansion for overlapping references.
- Added stored-block `LEN`/`NLEN` complement validation.
- Added checks for truncated reads, oversubscribed or unsupported incomplete Huffman tables, invalid dynamic-table counts, repeat overruns, and missing end-of-block codes.
- Added zlib window-size-field validation.
- Changed checksum extraction to use the decoded stream boundary rather than assuming the final four input bytes contain the checksum.
- Added unsigned 32-bit Adler-32 seed validation.
- Fixed Adler-32 normalization for empty input with a non-normalized seed.

These changes distinguish a complete stream from surrounding data and constrain decompressed output rather than accepting unbounded expansion by default.

#### Compatibility and residual limits

Streams producing more than 32 MiB now require an explicitly increased limit or `max_output=None`. Inputs with trailing bytes require `allow_trailing=True` or deliberate prefix decoding.

Previously tolerated malformed streams may now fail. Disabling checksum comparison still requires checksum bytes to be present.

The output cap is not a complete process-memory or execution-time budget. Input copies, decoding tables, temporary allocations, and repeated calls remain outside that guarantee. Literal output is checked immediately after appending, rather than every output write being checked beforehand.

The interface remains whole-buffer. gzip framing, preset dictionaries, and incremental output remain unsupported.

### Changed: `v2/brisart_json.py`

Replaced recursive parsing and serialization with explicit work stacks and introduced stricter defaults.

- Added a default nesting-depth limit of 100.
- Added a default parsing limit of 64 Mi characters.
- Added a 4,300-character numeric-literal limit.
- Added UTF-8 `bytes`, `bytearray`, and `memoryview` input.
- Tightened numeric scanning to reject leading zeros, incomplete fractions or exponents, non-ASCII digits, and floating-point overflow.
- Added exact four-ASCII-hex-digit validation for Unicode escapes.
- Changed duplicate object keys to errors by default; `"first"` and `"last"` policies are available.
- Changed NaN and Infinity parsing and serialization to require `allow_nan=True`.
- Changed lone-surrogate handling to rejection by default, with an explicit override.
- Added circular-reference detection during serialization.
- Changed serialization to reject non-string object keys instead of converting them to strings.
- Added `ensure_ascii`, configurable separators, and whitespace-string indentation.
- Added indentation and separator validation.
- Changed serialization to escape U+2028 and U+2029.
- Expanded `BrisartJSONDecodeError` with `msg`, `pos`, `lineno`, and `colno`, retaining `position`.
- Added string-scanning and scalar-container serialization fast paths.

These changes reduce ambiguous interpretation and replace interpreter-recursion dependence with explicit container tracking.

#### Compatibility and residual limits

v1 documents containing duplicate keys, non-finite numeric tokens, lone surrogates, or newly rejected numeric forms may no longer load with default settings.

`duplicate_keys="last"`, `allow_nan=True`, and `allow_lone_surrogates=True` restore selected permissive behaviors, not complete v1 compatibility.

Non-string dictionary keys must be converted deliberately before serialization. Serialized text may differ because of escaping and formatting changes even when its decoded value is equivalent.

The document-length limit is checked after bytes input is decoded and therefore is not an input-allocation ceiling. Serialization has no overall output-size cap. Empty-container serialization also uses a fast path, so the depth setting should not be described as an independently proven universal resource boundary.

Streaming, custom encoders, and object hooks remain unsupported.

### Changed: `v2/brisart_markup.py`

Removed regular-expression-based tag and attribute recognition and replaced the v1 scanner with an index-based, quote-aware tokenizer.

- Changed tag scanning so `>` inside a quoted attribute value does not prematurely terminate the tag.
- Reworked buffering to reduce repeated concatenation, slicing, and rescanning of incomplete constructs.
- Changed tag and attribute normalization from Unicode case folding to ASCII-only lowercasing.
- Changed attribute separators to HTML-defined whitespace.
- Changed duplicate attributes so the first occurrence is retained.
- Replaced the limited entity table with expanded embedded character-reference data.
- Added legacy semicolon-less references and attribute-specific decoding through `brisart_unescape(..., attribute=True)`.
- Added numeric-reference replacement and filtering tables.
- Separated raw-text handling from RCDATA handling.
- Expanded raw-text elements and added `plaintext` handling.
- Stopped decoding character references inside raw-text elements while retaining configurable decoding in RCDATA.
- Tightened matching of raw-text and RCDATA closing tags.
- Added `handle_comment()`, `handle_decl()`, and `reset()`.
- Revised incomplete-tag, comment, declaration, and self-closing-tag handling.
- Added NUL replacement in tag names, attribute names, and attribute values.
- Buffered ordinary text across `feed()` boundaries before character-reference decoding.

These changes address cases where naive scanning or normalization could make extracted attributes and text differ from the intended HTML interpretation.

#### Compatibility and residual limits

Callback contents, callback timing, duplicate attributes, entity expansion, malformed-input handling, and raw-text output can differ from v1. Consumers must not depend on one data callback per input chunk.

The implementation remains a tokenizer, not a browser-equivalent tree builder. It does not implement complete script-data states, foreign-content handling, encoding sniffing, or implied-tag repair.

The token stream is not a security sanitizer. Buffering improvements do not impose a document-size or retained-text limit.

### Changed: `v2/brisart_robots.py`

Replaced v1's first-matching-rule policy with longest-pattern matching and revised group selection.

- Added `*` wildcard matching and terminal `$` anchoring.
- Changed equal-length Allow/Disallow conflicts so Allow wins.
- Replaced substring user-agent matching with normalized product-token matching.
- Combined applicable named groups, falling back to wildcard groups when no named group applies.
- Changed blank lines and comments so they do not discard or split groups.
- Added internal path/query normalization and removed the runtime dependency on the URL module.
- Preserved encoded reserved characters as distinct from literal reserved characters.
- Expanded `parse()` to accept text, bytes-like input, or iterables of lines.
- Added UTF-8 BOM handling.
- Added input-budget, rule-count, line-length, and target-length controls.
- Added `mode`, `truncated`, and `rule_count` inspection.
- Added `BrisartRobotsPolicy.for_status()`.
- Expanded crawl-delay parsing to non-negative decimals, capped at 86,400 seconds.
- Added bounded caching of applicable rules.

These changes make policy evaluation less dependent on rule order and provide explicit handling for unavailable or failed robots.txt responses.

#### Compatibility and residual limits

The same policy and URL can produce a different decision from v1. Migration requires reviewing expected crawl decisions, not merely checking method signatures.

`for_status()` parses successful responses when content is supplied, denies HTTP 429 and server-error or unusable statuses, and allows unresolved redirects and other 4xx responses. This is the implemented policy, not a claim of exhaustive RFC conformance.

The `max_bytes` budget counts bytes for bytes-like input but characters for text and decoded iterable input. It is not uniformly a UTF-8 byte limit.

Truncation or ignored overlong lines can omit restrictive rules. Callers must inspect `truncated` and apply their own acceptance policy rather than treating every limited parse as fail-closed.

Fetching, redirect resolution, caching, and origin association remain caller responsibilities. robots.txt evaluation is advisory, not access control.

### Changed and fixed: `v2/brisart_url.py`

Reworked URL decomposition, reconstruction, quoting, and reference resolution.

- Added explicit input-type validation, retaining `None` as an empty URL.
- Added trimming of leading/trailing C0 controls and spaces and removal of tabs, carriage returns, and line feeds.
- Restricted scheme recognition and case normalization to ASCII rules.
- Added stricter authority inspection through `hostname` and the new `port` property.
- Added authority, query, and fragment presence flags.
- Preserved empty `?` and `#` delimiters during split/reconstruction.
- Added iteration, equality, and hashing to `BrisartSplitResult`.
- Expanded `brisart_urlunsplit()` to accept five-component sequences.
- Added reconstruction protection against paths being reinterpreted as schemes or authorities.
- Reworked dot-segment removal and relative-reference resolution.
- Corrected trailing-slash handling and changed empty-reference resolution so the base fragment is not retained.
- Added configurable UTF-8 error handling to quoting and unquoting.
- Added cached quoting tables.
- Added mapping input to `brisart_urlencode()`.
- Changed form encoding to encode bytes directly instead of encoding their string representation.
- Added a default query-field limit of 1,000.

These changes preserve more URL structure and make ambiguous authority handling visible to callers.

#### Compatibility and residual limits

Cleaning, joining, quoting, and reconstruction can produce different results from v1. Quoting now defaults to strict UTF-8 encoding rather than replacement encoding.

Splitting does not itself reject every malformed authority. Callers must inspect `hostname` and handle `port` errors; a returned split object is not proof that a URL is safe to fetch.

The implementation does not provide complete WHATWG parsing, IDNA processing, IP-address validation, or destination authorization.

`BrisartSplitResult` remains mutable despite exposing hashing. Callers must not mutate instances while using them as dictionary keys or set members.

Query-field limits do not bound total query length or all decoding allocations.

### Changed: shared implementation and documentation

- Removed `typing` imports and postponed-annotation imports from the v2 implementations.
- Removed the markup module's `re` dependency.
- Removed the robots module's sibling-module import.
- Made all seven v2 modules import-free and independently reusable at the module level.
- Removed embedded `_self_test()` functions and direct-execution self-test blocks.
- Rewrote six-section module headers to describe interfaces, parameters, edge cases, limitations, and examples.
- Changed header paths and examples from the earlier application-specific namespace to `brisart_native`.

The supplied directory layout remains `v1/` and `v2/`; the `brisart_native` examples do not establish an installed package or consumer import mechanism.

The headers reference external tests and measured benchmarks, but those artifacts and execution results are not included in the supplied comparison. Those statements are not promoted here into confirmed release results. Removing embedded tests does not establish replacement test coverage.

### Compatibility boundary

v2 introduces intentional behavioral and interface changes. Consumers must select the intended major-version implementation explicitly and regression-test their own inputs, persisted data, and error handling before migration.

Keeping v1 and v2 in separate directories preserves source separation; it does not automatically provide dependency pinning, import isolation, rollback, or ecosystem-wide compatibility.

This entry records source-visible changes and remaining limits. It does not establish exhaustive specification conformance, security certification, platform coverage, performance gains, or successful integration with every Brisart consumer.

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