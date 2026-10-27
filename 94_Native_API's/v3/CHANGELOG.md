# v3 Changelog

v3 contains the second substantive revision of applicable Brisart Native APIs.

Only APIs with a genuine v3 implementation are listed below. APIs are listed alphabetically.

---

## codec

**File:** `brisart_codec.py`

### Changed

- Expanded the encoding API beyond Base64 with Base32, Base32hex, and Base16 support.
- Preserved v2 Base64 behavior while applying the same explicit validation model to the new decoders.

### Why

v2 provided strict and configurable Base64 handling but did not cover the other RFC 4648 base encodings. v3 fills that gap without creating separate modules or a different validation model for each encoding.

### How

- Base32 decoding validates legal final-group lengths and matching padding.
- Canonical decoding rejects non-zero unused trailing bits.
- Invalid alphabet characters are rejected before decoding.
- Base16 validates input before using hexadecimal conversion, preventing whitespace from being silently accepted.
- Base32hex uses the same interface as Base32 through the `hex` option.

### Added

- `brisart_b32encode()`
- `brisart_b32decode()`
- `brisart_b16encode()`
- `brisart_b16decode()`
- `BrisartBase32Error`
- Base32hex through `hex=True`
- Base32 `padding`, `casefold`, `canonical`, and `max_output` controls
- Base16 `casefold` and `max_output` controls

### Compatibility

- Existing Base64 behavior remains as in v2.
- Base32 requires padding by default and is case-sensitive by default.
- Optional padding permits both padded and unpadded representations of the same Base32 value.
- `BrisartBase32Error` also covers Base16 decoding errors.

---

## hash

**File:** `brisart_hash.py`

### Changed

- Expanded the hashing API with SHA-224, HMAC, and digest comparison.
- Corrected hash-object copying so the copied object preserves its concrete hash class.

### Why

v2 supplied SHA-256 hashing but lacked a shorter SHA-2 digest, keyed message authentication, and a dedicated digest-comparison helper. Sharing the existing SHA-256 core allows those capabilities to be added without duplicating the underlying block-processing implementation.

### How

- SHA-224 uses the SHA-256 processing core with SHA-224 initial values and digest truncation.
- HMAC implements RFC 2104 over the supported SHA-256 and SHA-224 implementations.
- Digest comparison checks complete inputs without returning immediately at the first differing element.
- `copy()` constructs the same hash class as the object being copied.

### Added

- `BrisartHash224`
- `brisart_sha224()`
- `BrisartHMAC`
- `brisart_hmac()`
- `brisart_compare_digest()`
- SHA-224 and SHA-256 selection for HMAC

### Compatibility

- Existing SHA-256 behavior remains available.
- HMAC accepts only the supported digest implementations; unsupported algorithms are rejected.
- `brisart_compare_digest()` is not guaranteed constant-time by CPython. Use a hardened platform implementation where timing attacks are a realistic threat.
- The hashing and HMAC implementations are reference Python implementations rather than side-channel-hardened cryptographic implementations.

---

## inflate

**File:** `brisart_inflate.py`

### Changed

- Expanded decompression support with CRC-32 and gzip decoding.
- Corrected output-limit enforcement so a literal byte is checked before it is written rather than immediately afterward.

### Why

v2 supported raw DEFLATE and zlib but could not decode gzip framing. Adding gzip required CRC-32 support and header/trailer validation. The literal-write change also brings the output-limit implementation into line with its documented pre-write enforcement rule.

### How

- CRC-32 is implemented within the module rather than importing `zlib`.
- gzip parsing validates the magic bytes, compression method, reserved flags, bounded optional fields, optional header CRC, output CRC-32, and ISIZE.
- Concatenated gzip members can be decoded into one output while sharing the total output limit.
- Output-limit checking occurs before appending a literal byte.

### Added

- `brisart_crc32()`
- `brisart_gzip_decompress()`
- gzip checksum validation
- Concatenated gzip-member decoding
- `multiple_members`
- gzip `allow_trailing` behavior

### Fixed

- Literal output is checked against `max_output` before the write occurs.

### Compatibility

- gzip decoding is intentionally stricter than Python's `gzip.decompress()` in some malformed-header and trailing-data cases.
- `allow_trailing=True` can permit trailing data where supported.
- `verify_checksum=False` disables checksum comparison but does not turn the parser into an unrestricted framing parser.
- gzip metadata such as file name, comment, extra data, and modification time is parsed or skipped as framing information and is not returned to the caller.

---

## json

**File:** `brisart_json.py`

### Changed

- Added an early size guard for bytes-like JSON input before UTF-8 decoding.

### Why

v2 applied `max_length` after decoding bytes to text. An oversized bytes input could therefore be fully decoded, or fail with a UTF-8 error, before the configured document-size policy was considered. v3 rejects bytes input that cannot possibly fit within the character limit before decoding it.

### How

- When `max_length` is set, bytes-like input longer than `4 * max_length` is rejected before UTF-8 decoding.
- The factor of four reflects the maximum number of bytes used by one UTF-8 encoded Unicode code point.
- Inputs within that bound continue through the existing v2 decode and character-length validation path.

### Compatibility

- JSON behavior otherwise remains as in v2.
- Very large bytes input can now report the size-limit error before a UTF-8 decoding error.
- Both failures remain `BrisartJSONDecodeError` conditions.

---

## robots

**File:** `brisart_robots.py`

### Changed

- Made `max_bytes` consistently represent UTF-8 bytes for text, bytes-like, and iterable input.
- Changed truncation handling so a final line cut by the byte budget is discarded instead of being parsed as a shorter rule.

### Why

v2 counted bytes for bytes-like input but characters for text input, allowing multi-byte text to consume more encoded data than the stated budget. It could also parse an incomplete final rule after truncation. A partially retained `Allow` or `Disallow` line can describe a different policy than the source document intended.

### How

- Text and iterable input are budgeted according to their UTF-8 encoded size.
- A line that cannot fit completely inside the byte budget is not parsed.
- Complete lines that fit inside the budget continue through the existing v2 policy parser.

### Fixed

- UTF-8 byte-budget accounting is consistent across supported input forms.
- Partial final rules created by byte-budget truncation are discarded.

### Compatibility

- A limited parse can contain fewer rules than v2 when the source contains multi-byte text or when the byte budget ends in the middle of a line.
- Truncation is still not inherently fail-closed. Dropping an incomplete restrictive rule can also make a policy less restrictive.
- Callers using a limited parse must inspect `truncated` and apply their own acceptance policy.

---

## url

**File:** `brisart_url.py`

### Changed

- Made `BrisartSplitResult` immutable.
- Added constructor type validation for URL components.
- Added a replacement-copy interface for deliberate modifications.

### Why

v2 made `BrisartSplitResult` hashable while still allowing its attributes to be changed. Mutating an object after using it as a dictionary key or set member could invalidate the lookup relationship. v2 also accepted non-string constructor components and could surface the resulting type problem later in an unrelated operation.

### How

- Attribute assignment and deletion are rejected after construction.
- Constructor components must be `str` values.
- `replace(**components)` creates a new result instead of modifying the existing one.
- Replacing the authority, query, or fragment updates the corresponding presence flag unless that flag is explicitly supplied.

### Added

- `BrisartSplitResult.replace(**components)`

### Fixed

- Hashable split results can no longer be mutated after insertion into a mapping or set.
- Invalid component types fail at construction instead of surfacing later.

### Compatibility

- Code that assigned directly to `.scheme`, `.netloc`, `.path`, `.query`, `.fragment`, or related fields must use `replace()`.
- Code that constructed a result with non-string components now receives `TypeError`.
- Other URL behavior remains as in v2.
