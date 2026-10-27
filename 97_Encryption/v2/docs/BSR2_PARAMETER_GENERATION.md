# BSR2 Parameter Generation

BSR2 fixed parameters are generated deterministically by:

```text
tools/generate_bsr2_parameters.py
```

The generator uses only Python integer and byte operations. It does not call a cryptographic library and does not reuse constants from another cryptographic algorithm.

## Public seed

```text
BrisartSecurityResearch|BSR2|parameter-generation|v1
```

The public seed is not secret and is not entropy. It identifies the project, algorithm generation, purpose, and generator version.

## Generated parameters

The script deterministically produces:

- 24 nonzero, distinct 64-bit round constants
- 3 nonzero, distinct 64-bit structural mixing constants
- 8 distinct rotation distances from 1 through 63
- a permutation of the 16 state-word indexes

## Reproducibility

Run:

```bash
python tools/generate_bsr2_parameters.py
python tools/generate_bsr2_parameters.py --json
```

The same script and seed produce the same parameters on every conforming Python implementation.

## Security status

Transparent generation prevents the parameters from being undocumented or inherited. It does not prove that the generated parameters or BSR2 construction are cryptographically secure.

BSR2 remains experimental research and is incompatible with BSR1 outputs.
