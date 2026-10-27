# BSR1 Design Notes

## Identifier

```text
BSR1-ARX-SPONGE-ETM
```

## Envelope version

```text
1
```

> [!WARNING]
> This document describes the current implementation. It is not a security proof, standard, certification, or recommendation for production use.

## Construction overview

The implementation combines a custom permutation, sponge-style hashing, custom keyed authentication, subkey derivation, deterministic random generation, counter-based stream generation, and an encrypt-then-authenticate envelope.

Major functions use explicit domain strings to separate purposes.

## Permutation

The custom permutation operates on:

- 16 state words
- 64 bits per word
- 1024 total state bits
- 32 default rounds

Round operations include modular addition, XOR, fixed rotations, round constants, word reordering, and nonlinear neighbor mixing.

The current rotation values are:

```text
7, 13, 19, 29, 31, 37, 43, 53
```

## Sponge-style hash

The sponge-style construction uses:

- a 32-byte rate
- domain-dependent initial-state processing
- a padding marker of `0x80`
- zero padding
- an eight-byte big-endian message bit length
- a default output length of 32 bytes

The implementation accepts output lengths from 1 through 1024 bytes.

## Keyed authentication

The keyed authentication construction uses separate inner and outer hash domains. The implementation frames the key and message, creates a 64-byte inner value, and hashes the framed key, framed inner value, and framed message for the requested output length.

This is a custom construction and has not been established as equivalent to HMAC or another standardized MAC.

## Password-derived key experiment

The password-derived key function combines:

- a UTF-8 password
- a caller-provided salt
- an iteration counter
- an evolving state
- separate start, round, and final domains

The implementation requires a non-empty password, at least 16 salt bytes, and at least 10,000 iterations. The default iteration count is 120,000.

This function is not memory-hard and has not been validated as a production password-hardening construction.

## Subkey derivation

Per-purpose subkeys are produced from:

- the master key
- a framed message salt
- a framed purpose label

The envelope derives separate keys for encryption and authentication.

## Deterministic random-bit generator

The DRBG requires:

- at least 64 seed bytes
- at least 16 personalization bytes
- non-empty additional input for each request

The DRBG maintains mutable state, a counter, request and byte limits, a continuous repeated-block check, reseeding support, and a destroyed state.

The DRBG expands caller-provided seed material. It does not create entropy. In the current implementation, a valid reseed can reactivate a destroyed generator.

## Stream generation

The stream generator repeatedly authenticates a framed nonce and an eight-byte big-endian counter under the encryption key. Each generated block contributes to the output stream until the requested length is reached.

Plaintext is transformed by XOR with the generated stream.

## Authenticated envelope

The envelope contains exactly:

```text
algorithm
version
salt
nonce
ciphertext
tag
```

Binary values are encoded as canonical lowercase hexadecimal strings.

### Encryption

1. The caller provides a master key, plaintext, context string, and generator.
2. The generator produces a 32-byte message salt and a 32-byte nonce using distinct additional-input labels.
3. Separate encryption and authentication keys are derived from the master key and message salt.
4. The plaintext is XORed with the generated stream.
5. The algorithm identifier, version, context, salt, nonce, and ciphertext are framed and authenticated.

### Decryption

1. The implementation validates the exact envelope field set, algorithm, version, encodings, field lengths, and ciphertext size.
2. The same encryption and authentication subkeys are derived.
3. The expected tag is computed and compared before plaintext is returned.
4. Only after successful authentication is the ciphertext transformed back into plaintext.

## Size limits

The current implementation limits:

- envelope plaintext and ciphertext to 16 MiB
- each DRBG request to 1 MiB
- DRBG output before reseeding to 16 MiB
- DRBG requests before reseeding to 100,000

## Unestablished properties

The implementation has not established:

- collision or preimage resistance
- differential or rotational resistance
- algebraic or related-key resistance
- stream indistinguishability
- authentication-forgery resistance
- password-guessing resistance
- entropy-source validity
- state-compromise resistance
- side-channel resistance
- production suitability
