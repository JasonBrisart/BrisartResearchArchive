# BSR2 Wire Formats

This document gives the exact byte layout of every format produced by release `0.4.0-alpha`. Unless stated otherwise, integers are unsigned big-endian. `frame(x)` means `u64(len(x)) || x`. Each BSR2-S64 call names its domain string in quotes.

Every format here is research material and has not been independently reviewed.

---

## 1. BSR2-S64 sponge (`brisart_security_sponge.py`)

| Property | Value |
|---|---|
| Permutation | BSR2-P1024, 16 × 64-bit words, 32 rounds (frozen) |
| Rate | 64 bytes (words 0–7) |
| Capacity | 64 bytes (words 8–15), never output |
| IV | `(ROUND_CONSTANTS[(i+7) mod 24] XOR (i+1)·INITIAL_STATE_CONSTANT) mod 2^64`, with word 15 also XORed with `0x4253523253363401` |
| Domain | `frame(domain)` absorbed and padded first, so every domain starts from a distinct state |
| Padding | pad10\*1 within the rate: `0x80`, zero bytes, final byte OR `0x01` |
| Word order | big-endian bytes ↔ words |

Modes:

```text
hash64(m, D, n)          = S64(D).absorb(m).squeeze(n)
mac64(k, D, p1..pj, n)   = S64(D).absorb(frame(k) | frame(p1) | ... | frame(pj)).squeeze(n)
keystream64(k, N, n, D)  = S64(D).absorb(frame(k) | frame(N)).squeeze(n)
derive_keys64(k, D, ...) = mac64(k, D, ..., count·size) split into count keys
```

---

## 2. Sealed message v3: `BSR2-S64-SIV` (`brisart_security_aead.py`)

```text
offset  size  field
0       4     magic "BSRE"
4       1     format version = 3
5       1     suite id = 1
6       1     flags = 0 (any other value rejected)
7       1     padding id: 0 none, 1 padme, 2 block-256
8       32    randomizer
40      32    commitment
72      32    siv
104     n     ciphertext of payload
```

```text
prefix              = bytes[0:40]
enc, mac, commit    = derive_keys64(K, "BSR2/v3/seal/keys", prefix[0:8], randomizer)   (3 × 32 bytes)
payload             = u64(len(P)) | P | zero padding to the canonical padded length
siv                 = mac64(mac, "BSR2/v3/seal/siv", prefix | commit, context, ad, payload)
ciphertext          = payload XOR keystream64(enc, siv, len(payload), "BSR2/v3/seal/stream")
randomizer          = OS entropy(32) [XOR rng.generate(32, ...) when a generator is supplied]
```

Opening a sealed message checks things in this order: the header structure, the size ceiling, the commitment (constant-time compare), decryption, the SIV, the declared length, whether the padding is canonical, and whether the padding bytes are zero. Every failure after parsing raises the same message, `authentication failed`.

Padded payload length for `L = 8 + len(P)`:

- **none:** `L`
- **padme:** `E = floor(log2 L)`, `S = floor(log2 E) + 1`, mask = `2^(E−S) − 1`, padded = `(L + mask) & ~mask`
- **block:** round `L` up to a multiple of 256

### Armor

```text
-----BEGIN BSR2 SEALED MESSAGE-----
<lowercase hex, 64 characters per line>
=<hex of hash64(sealed, "BSR2/v3/armor/checksum", 4)>
-----END BSR2 SEALED MESSAGE-----
```

The checksum detects transport damage. It is not a security mechanism.

---

## 3. Stream v1: `BSR-STREAM-1` (`brisart_security_stream.py`)

```text
header (108 bytes)
0    4   magic "BSRS"
4    1   version = 1
5    1   suite = 1
6    1   flags = 0
7    1   reserved = 0
8    4   chunk_size (64 .. 16 MiB)
12   32  randomizer
44   32  commitment
76   32  header_tag

records
  tag(32) | ciphertext(chunk_size)        every chunk except the last
  tag(32) | ciphertext(0..chunk_size)     final chunk (always present; empty input gives one empty final chunk)
```

```text
enc, mac, commit = derive_keys64(K, "BSR2/v3/stream/keys", header[0:12], randomizer)
header_tag       = mac64(mac, "BSR2/v3/stream/header", header[0:44] | commit, context, ad)
tag_i            = mac64(mac, "BSR2/v3/stream/chunk", u64(i) | final_i, header_tag, P_i)
C_i              = P_i XOR keystream64(enc, tag_i | u64(i) | final_i, len(P_i), "BSR2/v3/stream/keystream")
```

The reader looks one record ahead to decide `final_i`. Because the final flag is authenticated, cutting the stream at a chunk boundary fails, and so does any byte after the final record.

### CLI password files

```text
"BSRPW001" | BSR2-MHF-1 parameter block (73 bytes) | BSR-STREAM-1 stream
```

The stream's associated data is `"BSRPW001" | parameter block`, so editing the parameters (for example, downgrading the memory size) fails authentication.

---

## 4. BSR2-MHF-1 (`brisart_security_kdf.py`)

Parameter block (73 bytes):

```text
0    1   kdf id = 1
1    1   rounds = 8
2    2   passes (1..16)
4    4   memory_blocks (power of two, 64 .. 2^20)
8    1   salt length (16..64)
9    64  salt, zero-filled (non-zero filler rejected)
```

```text
pw   = NFC(password) as UTF-8, or raw bytes
X    = S64("BSR2/v3/mhf/init").absorb(frame(pw) | frame(salt) | frame(id|rounds|u32 t|u32 m|u32 out)).squeeze(128)
F(B, c) = P8(B with word15 XOR c) XOR B
for i in 0..m-1:     V[i] = X;  X = F(X, i)
for k in 0..m·t-1:   j = X[0] mod m;  X = F(X XOR V[j], m + k);  V[j] = X
key  = S64("BSR2/v3/mhf/final").absorb(frame(X) | frame(pw) | frame(salt)).squeeze(out)
```

`P8` is the BSR2 permutation run for 8 rounds.

---

## 5. Recovery record: `BSRR-1` (`brisart_security_recovery.py`)

```text
0    8   magic "BSRR\x00\x01\r\n"
8    4   chunk_size (64 .. 1 MiB)
12   4   parity_count P
16   8   data_length
24   4   CRC-32 of the whole protected data
28   2   aux length (<= 256)
30   a   aux
..   8n  per data chunk: CRC-32 | Adler-32
..   8P  per parity block: CRC-32 | Adler-32
..   4   CRC-32 of everything above
..   P·chunk_size  parity blocks
```

Data chunk `i` belongs to parity group `i mod P`. Each parity block is the XOR of its group, with the final chunk zero-padded to full size. `P = ceil(n · percent / 100)`. Each group can repair one damaged chunk, so any burst of up to `P` consecutive damaged chunks is repairable.

---

## 6. Brisart Secure Archive v1 (`brisart_security_archive.py`)

```text
preamble (137 bytes)
0    8   magic "BSA\x00\r\n\x1a\n"
8    2   format version = 1
10   2   flags: 0x0001 solid, 0x0002 password (others rejected)
12   16  archive_id (random)
28   73  BSR2-MHF-1 parameter block, or 73 zero bytes in key-file mode
101  32  key_check
133  4   CRC-32 of bytes 0..132

data region      one BSR-STREAM-1 blob per entry (per-file), or one blob (solid)
directory        sealed v3 message, padme padding
recovery record  BSRR-1 over [0, end of directory), optional
footer × 2       two identical 64-byte footers
```

```text
master       = key file key | BSR2-MHF-1(password, params, 32)
archive_key  = derive_keys64(master, "BSR2/v3/archive/key", preamble[0:101], count=1)
key_check    = mac64(archive_key, "BSR2/v3/archive/key-check", preamble[0:101])
AD           = preamble[0:133]                    (associated data for every stream and the directory)
entry i      = stream(archive_key, compressed_i, context "bsa:<id>:entry:<i>", AD)
solid block  = stream(archive_key, compress(all files), context "bsa:<id>:solid", AD)
directory    = seal(archive_key, canonical JSON, "bsa:<id>:directory", AD, padding=padme)
```

Footer (64 bytes):

```text
0   8   "BSAFOOT1"
8   8   directory offset
16  8   directory length
24  8   recovery offset
32  8   recovery length (0 = none)
40  16  archive_id
56  4   zero
60  4   CRC-32 of bytes 0..59
```

Recovery aux (36 bytes): `"BSA1" | u64 dir_offset | u64 dir_length | archive_id`. This is enough to rebuild both footers.

Directory JSON (canonical: sorted keys, compact separators, UTF-8):

```json
{
  "format": "BSA-DIRECTORY", "version": 1,
  "comment": "...", "solid": false, "compression": "deflate",
  "entries": [
    {"name": "dir/file.txt", "size": 123, "mtime": 1700000000, "executable": false,
     "crc32": 305419896, "comment": "", "compression": "deflate", "offset": 137, "length": 400}
  ]
}
```

Solid archives replace `offset`, `length`, and per-entry `compression` with `solid_offset`, and add `"solid_block": {"offset", "length", "unpacked"}`.

### Volumes

Each volume file is named `<archive>.NNN`:

```text
0   8   "BSAVOL01"
8   16  set id (random, shared by all volumes)
24  4   index (0-based)
28  4   count
32  8   payload length
40  4   CRC-32 of payload
44  ..  payload
```

---

## 7. Key file: `BSR2-KEYFILE` v1 (`brisart_security_keys.py`)

```json
{
  "format": "BSR2-KEYFILE",
  "version": 1,
  "label": "lab key",
  "key": "<64..256 lowercase hex characters>",
  "fingerprint": "xxxx-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx-xxxx",
  "check": "<16 hex characters>"
}
```

```text
fingerprint = hex(hash64(key, "BSR2/v3/key-fingerprint", 16)) in groups of 4
check       = hex(hash64(JSON[format, version, label, key, fingerprint], "BSR2/v3/keyfile-check", 8))
```

The file is created with mode `0600` and is never silently overwritten.

---

## 8. Legacy envelope v2: `BSR2-ARX-SPONGE-ETM`

This format is unchanged. See `docs/DESIGN.md`, section "Legacy Envelope v2". The JSON field set is exactly `algorithm`, `version`, `salt`, `nonce`, `ciphertext`, and `tag`, with canonical lowercase hex.
