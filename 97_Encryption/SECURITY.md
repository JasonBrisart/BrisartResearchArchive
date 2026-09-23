# Security Policy

## Experimental status

BrisartSecurityResearch is custom cryptographic research. It has not undergone independent cryptanalysis, formal verification, certification, or production security review.

Passing the included behavioral, regression, mutation, statistical, or performance tests does not establish cryptographic security.

## Supported use

This repository is intended for controlled research, source inspection, synthetic data, offline prototypes, and educational analysis.

Do not use it as the sole protection for credentials, identity records, recovery secrets, personal information, valuable research, authorization decisions, regulated data, or safety-critical systems.

## Reporting implementation issues

Reports should clearly distinguish between:

- implementation defects
- documentation errors
- test-suite defects
- reproducibility failures
- suspected cryptographic weaknesses

A useful report includes:

- the affected file and function
- the exact repository revision
- minimal reproduction steps
- expected and observed behavior
- relevant test output
- whether frozen known-answer vectors changed

Do not include real credentials, personal information, private keys, valuable plaintext, or other sensitive data in a report.

## Security claims

The project does not claim:

- equivalence to AES, ChaCha20, SHA-2, SHA-3, HMAC, PBKDF2, Argon2, or any standardized construction
- collision or preimage resistance
- stream indistinguishability
- authentication-forgery resistance
- differential, rotational, algebraic, or related-key resistance
- entropy-source validation
- state-compromise resistance
- side-channel resistance
- production suitability

## Disclosure status

No independent security review or certification is represented by this repository. Test reports document only the behavior measured by their corresponding test code and configuration.
