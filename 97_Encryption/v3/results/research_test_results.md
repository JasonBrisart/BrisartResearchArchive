# BrisartSecurityResearch Test Results

Generated UTC: `2026-07-18T22:00:24.782457+00:00`
Profile: `intermediate`

> Passing checks demonstrate only the measured behavior. They do not establish cryptographic security, production suitability, or resistance to cryptanalysis.

## Provenance

- Python: `CPython 3.14.6`
- Operating system: `Windows 11`
- Source revision: `unavailable`
- Uncommitted changes present: `unavailable`
- Configuration SHA-256: `853d680e709b40e1fd66c107bac020ffa7c8a4e625f68dd29e1f4e860ca69c71`
- Known-answer vector SHA-256: `93904aca493410cfed43be9c083d82484c8ecc558e1836861155cfeda6beeb3c`

## Summary

- Checks: 13
- Passed: 13
- Failed: 0
- Errors: 0
- Benchmarks completed: 2
- Total runtime: 173.169 seconds

## Detailed Results

### PASS: hash / single-bit avalanche

- Trials or sample units: 128
- Duration: 1.595 seconds
- Metrics: `{"maximum_changed_bit_ratio": 0.59375, "mean_changed_bit_ratio": 0.498779296875, "minimum_changed_bit_ratio": 0.40234375, "population_standard_deviation": 0.03168471290625661}`
- Note: Observational diffusion test; not a proof of resistance to cryptanalysis.

### PASS: hash / collision observation

- Trials or sample units: 1000
- Duration: 8.224 seconds
- Metrics: `{"observed_collisions": 0, "unique_digests": 1000}`
- Note: No observed collisions does not establish collision resistance.

### PASS: hash / domain separation

- Trials or sample units: 64
- Duration: 1.016 seconds
- Metrics: `{"equal_cross_domain_outputs": 0}`
- Note: Checks observed separation for explicit test domains.

### PASS: mac / message tamper sensitivity

- Trials or sample units: 128
- Duration: 17.767 seconds
- Metrics: `{"undetected_message_mutations": 0}`
- Note: Mutation observation only; not a forgery-resistance proof.

### PASS: mac / labeled input separation

- Trials or sample units: 64
- Duration: 7.990 seconds
- Metrics: `{"equal_labeled_outputs": 0}`
- Note: Tests caller-supplied labels in MAC inputs.

### PASS: stream / unique nonce blocks

- Trials or sample units: 256
- Duration: 11.194 seconds
- Metrics: `{"duplicate_blocks": 0, "unique_blocks": 256}`
- Note: No observed duplicates does not establish stream indistinguishability.

### PASS: stream / bit balance and serial correlation

- Trials or sample units: 8192
- Duration: 5.715 seconds
- Metrics: `{"adjacent_byte_serial_correlation": 0.004756641269248001, "ones_ratio": 0.4994659423828125, "sample_bytes": 8192}`
- Note: Simple output statistics are diagnostic only.

### PASS: drbg / determinism

- Trials or sample units: 64
- Duration: 15.309 seconds
- Metrics: `{"determinism_mismatches": 0}`
- Note: Same complete input and call sequence should reproduce output.

### PASS: drbg / single-bit seed sensitivity

- Trials or sample units: 64
- Duration: 15.224 seconds
- Metrics: `{"equal_outputs": 0, "mean_changed_bit_ratio": 0.5001220703125}`
- Note: Sensitivity observation only.

### PASS: envelope / randomized round trips

- Trials or sample units: 16
- Duration: 8.247 seconds
- Metrics: `{"round_trip_failures": 0, "total_plaintext_bytes": 3931}`
- Note: Behavioral correctness test across deterministic randomized lengths.

### PASS: envelope / binary field tamper rejection

- Trials or sample units: 64
- Duration: 40.008 seconds
- Metrics: `{"undetected_envelope_mutations": 0}`
- Note: Tamper-detection observation; not a forgery-resistance proof.

### PASS: envelope / wrong context rejection

- Trials or sample units: 16
- Duration: 7.165 seconds
- Metrics: `{"wrong_context_acceptances": 0}`
- Note: Checks that context is authenticated.

### PASS: envelope / wrong key rejection

- Trials or sample units: 16
- Duration: 7.374 seconds
- Metrics: `{"wrong_key_acceptances": 0}`
- Note: Checks observed rejection under unrelated keys.

### BENCHMARK: performance / hash throughput

- Trials or sample units: 56
- Duration: 1.972 seconds
- Metrics: `{"measurements": [{"bytes_per_second": 3207.483057823371, "message_bytes": 32, "repetitions": 50}, {"bytes_per_second": 8993.042687697616, "message_bytes": 1024, "repetitions": 5}, {"bytes_per_second": 9086.491486107561, "message_bytes": 8192, "repetitions": 1}]}`
- Note: Local runtime measurement; machine and interpreter dependent.

### BENCHMARK: performance / envelope round-trip throughput

- Trials or sample units: 13
- Duration: 24.367 seconds
- Metrics: `{"measurements": [{"message_bytes": 32, "repetitions": 10, "round_trip_bytes_per_second": 52.72752396193569}, {"message_bytes": 1024, "repetitions": 2, "round_trip_bytes_per_second": 475.4972858768633}, {"message_bytes": 8192, "repetitions": 1, "round_trip_bytes_per_second": 589.213946734305}]}`
- Note: Combined encrypt/decrypt local runtime measurement.
