# Security Policy

## Experimental status

BrisartSecurityResearch is custom cryptographic research. No independent cryptanalysis, formal verification, certification, or production security review has been done on any part of it.

The first-pass empirical analysis in `docs/CRYPTANALYSIS.md` covers the BSR2 permutation and the legacy rate-32 modes. It does **not** cover the constructions added in `0.4.0-alpha`:

- BSR2-S64
- Sealed message v3
- BSR-STREAM-1
- BSR2-MHF-1
- Brisart Secure Archive

Passing the included tests does not establish cryptographic security.

## Supported use

The project is meant for:

- Controlled research
- Source inspection
- Synthetic or disposable data
- Offline and air-gapped workflow prototypes
- Educational analysis

Do not use it as the only protection for credentials, identity records, recovery secrets, personal information, valuable research, authorization decisions, regulated data, or safety-critical systems.

## What 0.4.0 defends against (behaviourally tested)

- Keystream reuse after a DRBG restart, including the case where OS entropy is replayed too (v3 SIV)
- Tampering, truncation, reordering, and extension of sealed messages, streams, and archives
- Wrong-key confusion (explicit key commitment)
- Header-driven resource exhaustion: KDF memory, chunk size, directory size, entry count, unpacked size, compression bombs
- Path traversal, reserved device names, symlink redirection, and silent overwrites during extraction
- Accidental corruption (recovery records, repaired without the key and re-authenticated afterwards)
- DRBG state duplication through `fork`, `copy`, or `pickle`

## Out of scope

- Timing, cache, power, and other side channels. CPython integer arithmetic is not constant-time, and BSR2-MHF-1 uses data-dependent addressing.
- An attacker who can roll back the complete machine state, including OS randomness
- Public-key authenticity (no digital signatures are implemented)
- Memory disclosure: Python cannot reliably erase keys
- Confidentiality of compressed sizes and file counts beyond the optional padding

## Security claims

The project does not claim any of the following:

- Equivalence to AES, ChaCha20, SHA-2, SHA-3, HMAC, PBKDF2, scrypt, Argon2, or any standardized construction
- Collision or preimage resistance
- Indistinguishability
- Forgery resistance
- Differential, linear, rotational, algebraic, or related-key resistance
- Memory-hardness
- Entropy-source validation
- Side-channel resistance
- Production suitability

## Reporting implementation issues

Please say which kind of issue you are reporting:

- Implementation defect
- Documentation error
- Test-suite defect
- Reproducibility failure
- Suspected cryptographic weakness

A useful report includes:

- The affected file and function
- The exact release (`python brisart_security_cli.py info`) and revision
- Minimal reproduction steps
- Expected and observed behaviour
- Relevant test output
- Whether either known-answer vector file changed

Never include real credentials, personal information, private keys, valuable plaintext, or real key files in a report.

## Disclosure status

This repository does not represent any independent security review or certification. Test reports document only the behaviour measured by their test code and configuration.
