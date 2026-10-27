"""
File: research/run_research_suite.py

Purpose
-------
Configurable research runner for the Brisart Research Archive 97_Encryption
project. It measures observable behaviour of both generations of BSR2 code:
legacy rate-32 hash/MAC/stream/DRBG/v2 envelope (diffusion, collision and
domain observations, tamper/key/context rejection, simple output statistics)
and, from 0.4.0, the v3 sealed message, nonce-misuse behaviour, BSR2-S64
keystream statistics, BSR-STREAM-1 and the Brisart Secure Archive. It writes
Markdown, JSON and CSV reports with provenance.

Communication / relationships
-----------------------------
Imports every brisart_security_* module it measures plus
brisart_security_version.py for report provenance. Reads
research/research_test_config.json by default and writes to the configured
output directory (``results/`` under the 97_Encryption root).
Moved in 0.4.0 from tests/ to research/, which is where docs/TESTING.md and
README.md always said it lived, and where its default configuration path
already pointed.

Settings / parameters
---------------------
REPOSITORY_ROOT       97_Encryption root (parent of research/)
DEFAULT_CONFIG_PATH   research/research_test_config.json
Config sections: hash, mac, stream, drbg, envelope, v3, performance.
Status values: PASS, FAIL, ERROR, BENCHMARK (benchmarks excluded from counts).

Edge cases
----------
* A missing ``v3`` section skips the v3 checks instead of failing, so older
  configurations still run.
* Git provenance degrades to "unavailable" when git is absent.
* Any exception inside a check is captured as ERROR with its type; the
  process exits 1 if any check is FAIL or ERROR.

Known limitations
-----------------
Every check is observational. Passing results do not establish cryptographic
security, and the statistics are far too small to catch subtle bias.

Examples
--------
    python research/run_research_suite.py
    python research/run_research_suite.py --config research/research_test_config.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from unittest.mock import patch

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = Path(__file__).resolve().with_name("research_test_config.json")

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import brisart_security_aead as aead_module  # noqa: E402
from brisart_security_aead import BrisartSealError, HEADER_BYTES, seal, unseal  # noqa: E402
from brisart_security_archive import ArchiveReader, build_archive  # noqa: E402
from brisart_security_drbg import BrisartDRBG  # noqa: E402
from brisart_security_envelope import BrisartEnvelopeError, decrypt, encrypt  # noqa: E402
from brisart_security_primitives import keyed_mac, sponge_hash, stream_bytes  # noqa: E402
from brisart_security_sponge import keystream64  # noqa: E402
from brisart_security_stream import decrypt_bytes, encrypt_bytes  # noqa: E402
from brisart_security_version import PROJECT_RELEASE, RELEASE_NAME  # noqa: E402


@dataclass
class Result:
    category: str
    name: str
    status: str
    trials: int
    duration_seconds: float
    metrics: dict
    note: str


def _byte_statistics(sample: bytes) -> tuple[float, float]:
    ones_ratio = sum(value.bit_count() for value in sample) / (len(sample) * 8)
    xs = sample[:-1]
    ys = sample[1:]
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = math.sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
    return ones_ratio, (numerator / denominator if denominator else 0.0)


class Suite:
    def __init__(self, config: dict):
        self.config = config
        self.random = random.Random(config["deterministic_seed"])
        self.results: list[Result] = []

    def bytes(self, length: int) -> bytes:
        return bytes(self.random.getrandbits(8) for _ in range(length))

    def run(self, category, name, trials, function: Callable[[], tuple[bool, dict, str]], success_status="PASS") -> None:
        started = time.perf_counter()
        try:
            passed, metrics, note = function()
            status = success_status if passed else "FAIL"
        except Exception as exc:
            status = "ERROR"
            metrics = {"exception_type": type(exc).__name__}
            note = str(exc)
        elapsed = time.perf_counter() - started
        self.results.append(Result(category, name, status, trials, elapsed, metrics, note))
        print(f"[{status:5}] {category}: {name} ({elapsed:.3f}s)")

    # Legacy rate-32 checks ---------------------------------------------------

    def hash_avalanche(self):
        cfg = self.config["hash"]
        distances = []
        for _ in range(cfg["avalanche_trials"]):
            size = self.random.choice(cfg["message_sizes"])
            message = bytearray(self.bytes(size))
            changed = bytearray(message)
            bit = self.random.randrange(size * 8)
            changed[bit // 8] ^= 1 << (bit % 8)
            left = sponge_hash(bytes(message))
            right = sponge_hash(bytes(changed))
            distances.append(sum((a ^ b).bit_count() for a, b in zip(left, right)) / 256)
        mean = statistics.fmean(distances)
        metrics = {
            "mean_changed_bit_ratio": mean,
            "minimum_changed_bit_ratio": min(distances),
            "maximum_changed_bit_ratio": max(distances),
            "population_standard_deviation": statistics.pstdev(distances),
        }
        passed = cfg["avalanche_mean_min"] <= mean <= cfg["avalanche_mean_max"]
        return passed, metrics, "Observational diffusion test; not a proof of resistance to cryptanalysis."

    def hash_collisions(self):
        count = self.config["hash"]["collision_trials"]
        seen = set()
        collisions = 0
        for index in range(count):
            digest = sponge_hash(index.to_bytes(8, "big") + self.bytes(self.random.randint(0, 256)))
            collisions += digest in seen
            seen.add(digest)
        return collisions == 0, {"observed_collisions": collisions, "unique_digests": len(seen)}, (
            "No observed collisions does not establish collision resistance."
        )

    def hash_domain_separation(self):
        count = self.config["hash"]["domain_separation_trials"]
        equal = 0
        for index in range(count):
            message = self.bytes(self.random.randint(0, 256))
            suffix = index.to_bytes(4, "big")
            equal += sponge_hash(message, domain=b"BSR2/test/domain/a/" + suffix) == sponge_hash(
                message, domain=b"BSR2/test/domain/b/" + suffix
            )
        return equal == 0, {"equal_cross_domain_outputs": equal}, "Checks observed separation for explicit test domains."

    def mac_tamper(self):
        count = self.config["mac"]["tamper_trials"]
        unchanged = 0
        for _ in range(count):
            key = self.bytes(32)
            message = bytearray(self.bytes(self.random.randint(1, 512)))
            original = keyed_mac(key, bytes(message))
            bit = self.random.randrange(len(message) * 8)
            message[bit // 8] ^= 1 << (bit % 8)
            unchanged += original == keyed_mac(key, bytes(message))
        return unchanged == 0, {"undetected_message_mutations": unchanged}, "Mutation observation only; not a forgery-resistance proof."

    def mac_domain_separation(self):
        count = self.config["mac"]["domain_trials"]
        equal = 0
        for index in range(count):
            key = self.bytes(32)
            message = self.bytes(self.random.randint(0, 256))
            suffix = index.to_bytes(4, "big")
            equal += keyed_mac(key, b"domain-a" + suffix + message) == keyed_mac(key, b"domain-b" + suffix + message)
        return equal == 0, {"equal_labeled_outputs": equal}, "Tests caller-supplied labels in MAC inputs."

    def stream_unique_blocks(self):
        count = self.config["stream"]["unique_block_trials"]
        key = self.bytes(32)
        blocks = set()
        duplicates = 0
        for index in range(count):
            block = stream_bytes(key, index.to_bytes(32, "big"), 64)
            duplicates += block in blocks
            blocks.add(block)
        return duplicates == 0, {"duplicate_blocks": duplicates, "unique_blocks": len(blocks)}, (
            "No observed duplicates does not establish stream indistinguishability."
        )

    def stream_statistics(self):
        cfg = self.config["stream"]
        sample = stream_bytes(self.bytes(32), self.bytes(32), cfg["sample_bytes"])
        ones_ratio, correlation = _byte_statistics(sample)
        passed = (
            cfg["ones_ratio_min"] <= ones_ratio <= cfg["ones_ratio_max"]
            and abs(correlation) <= cfg["max_absolute_serial_correlation"]
        )
        return passed, {
            "sample_bytes": len(sample),
            "ones_ratio": ones_ratio,
            "adjacent_byte_serial_correlation": correlation,
        }, "Simple output statistics are diagnostic only."

    def drbg_determinism(self):
        cfg = self.config["drbg"]
        mismatches = 0
        for index in range(cfg["determinism_trials"]):
            seed = self.bytes(64)
            label = b"BSR2 intermediate determinism" + index.to_bytes(4, "big")
            additional = b"request/" + index.to_bytes(4, "big")
            first = BrisartDRBG(seed, label).generate(cfg["output_bytes_per_trial"], additional)
            second = BrisartDRBG(seed, label).generate(cfg["output_bytes_per_trial"], additional)
            mismatches += first != second
        return mismatches == 0, {"determinism_mismatches": mismatches}, "Same complete input and call sequence should reproduce output."

    def drbg_seed_sensitivity(self):
        cfg = self.config["drbg"]
        equal = 0
        distances = []
        for index in range(cfg["seed_sensitivity_trials"]):
            seed_a = bytearray(self.bytes(64))
            seed_b = bytearray(seed_a)
            bit = self.random.randrange(len(seed_b) * 8)
            seed_b[bit // 8] ^= 1 << (bit % 8)
            label = b"BSR2 intermediate sensitivity" + index.to_bytes(4, "big")
            additional = b"request/" + index.to_bytes(4, "big")
            first = BrisartDRBG(bytes(seed_a), label).generate(cfg["output_bytes_per_trial"], additional)
            second = BrisartDRBG(bytes(seed_b), label).generate(cfg["output_bytes_per_trial"], additional)
            equal += first == second
            distances.append(sum((a ^ b).bit_count() for a, b in zip(first, second)) / (len(first) * 8))
        return equal == 0, {"equal_outputs": equal, "mean_changed_bit_ratio": statistics.fmean(distances)}, "Sensitivity observation only."

    def envelope_round_trip(self):
        cfg = self.config["envelope"]
        failures = 0
        total_bytes = 0
        master = self.bytes(32)
        for index in range(cfg["round_trip_trials"]):
            size = self.random.randint(0, cfg["maximum_random_plaintext_bytes"])
            plaintext = self.bytes(size)
            total_bytes += size
            seed = hashlib.sha512(b"roundtrip" + index.to_bytes(8, "big")).digest()
            context = f"research-suite:roundtrip:{index}"
            envelope = encrypt(master, plaintext, context, BrisartDRBG(seed, b"BSR2 research suite roundtrip"))
            failures += decrypt(master, envelope, context) != plaintext
        return failures == 0, {"round_trip_failures": failures, "total_plaintext_bytes": total_bytes}, (
            "Behavioral correctness test across deterministic randomized lengths."
        )

    def envelope_tamper(self):
        cfg = self.config["envelope"]
        master = self.bytes(32)
        undetected = 0
        fields = ("salt", "nonce", "ciphertext", "tag")
        for index in range(cfg["tamper_trials"]):
            plaintext = self.bytes(self.random.randint(1, min(1024, cfg["maximum_random_plaintext_bytes"])))
            seed = hashlib.sha512(b"tamper" + index.to_bytes(8, "big")).digest()
            context = f"research-suite:tamper:{index}"
            envelope = encrypt(master, plaintext, context, BrisartDRBG(seed, b"BSR2 research suite tamper"))
            field = fields[index % len(fields)]
            raw = bytearray.fromhex(envelope[field])
            raw[self.random.randrange(len(raw))] ^= 1 << self.random.randrange(8)
            envelope[field] = raw.hex()
            try:
                decrypt(master, envelope, context)
                undetected += 1
            except BrisartEnvelopeError:
                pass
        return undetected == 0, {"undetected_envelope_mutations": undetected}, "Tamper-detection observation; not a forgery-resistance proof."

    def envelope_wrong_context(self):
        count = self.config["envelope"]["wrong_context_trials"]
        master = self.bytes(32)
        accepted = 0
        for index in range(count):
            seed = hashlib.sha512(b"context" + index.to_bytes(8, "big")).digest()
            envelope = encrypt(master, self.bytes(64), f"context:{index}", BrisartDRBG(seed, b"BSR2 context rejection test"))
            try:
                decrypt(master, envelope, f"context:{index}:wrong")
                accepted += 1
            except BrisartEnvelopeError:
                pass
        return accepted == 0, {"wrong_context_acceptances": accepted}, "Checks that context is authenticated."

    def envelope_wrong_key(self):
        count = self.config["envelope"]["wrong_key_trials"]
        accepted = 0
        for index in range(count):
            master = self.bytes(32)
            wrong = self.bytes(32)
            seed = hashlib.sha512(b"wrong-key" + index.to_bytes(8, "big")).digest()
            context = f"wrong-key:{index}"
            envelope = encrypt(master, self.bytes(64), context, BrisartDRBG(seed, b"BSR2 wrong key rejection"))
            try:
                decrypt(wrong, envelope, context)
                accepted += 1
            except BrisartEnvelopeError:
                pass
        return accepted == 0, {"wrong_key_acceptances": accepted}, "Checks observed rejection under unrelated keys."

    # v3 checks (0.4.0) ---------------------------------------------------------

    def v3_sealed_round_trip(self):
        cfg = self.config["v3"]
        key = self.bytes(32)
        failures = 0
        for index in range(cfg["sealed_round_trip_trials"]):
            plaintext = self.bytes(self.random.randint(0, cfg["maximum_random_plaintext_bytes"]))
            padding = ("none", "padme", "block")[index % 3]
            ad = self.bytes(self.random.randint(0, 64))
            blob = seal(key, plaintext, f"research:v3:{index}", associated_data=ad, padding=padding)
            failures += unseal(key, blob, f"research:v3:{index}", associated_data=ad) != plaintext
        return failures == 0, {"round_trip_failures": failures}, "Sealed v3 behavioural round trips across paddings."

    def v3_sealed_tamper(self):
        cfg = self.config["v3"]
        key = self.bytes(32)
        undetected = 0
        for index in range(cfg["sealed_tamper_trials"]):
            blob = bytearray(seal(key, self.bytes(self.random.randint(0, 256)), "research:v3:tamper"))
            position = self.random.randrange(len(blob))
            blob[position] ^= 1 << self.random.randrange(8)
            try:
                unseal(key, bytes(blob), "research:v3:tamper")
                undetected += 1
            except BrisartSealError:
                pass
        return undetected == 0, {"undetected_mutations": undetected}, "Single-bit mutations anywhere in the sealed message."

    def v3_misuse(self):
        cfg = self.config["v3"]
        key = self.bytes(32)
        recoveries = 0
        for _ in range(cfg["misuse_trials"]):
            fixed = self.bytes(32)
            known = self.bytes(48)
            secret = self.bytes(48)
            with patch.object(aead_module, "system_entropy", return_value=fixed):
                first = seal(key, known, "research:v3:misuse")
                second = seal(key, secret, "research:v3:misuse")
            guess = bytes(a ^ b ^ k for a, b, k in zip(first[HEADER_BYTES + 8:], second[HEADER_BYTES + 8:], known))
            recoveries += guess == secret
        return recoveries == 0, {"plaintexts_recovered_under_randomizer_reuse": recoveries}, (
            "Forces randomizer reuse (simulated total entropy failure); SIV must keep keystreams distinct."
        )

    def v3_keystream_statistics(self):
        cfg = self.config["v3"]
        stream_cfg = self.config["stream"]
        sample = keystream64(self.bytes(32), self.bytes(32), cfg["keystream_sample_bytes"])
        ones_ratio, correlation = _byte_statistics(sample)
        passed = (
            stream_cfg["ones_ratio_min"] <= ones_ratio <= stream_cfg["ones_ratio_max"]
            and abs(correlation) <= stream_cfg["max_absolute_serial_correlation"]
        )
        return passed, {"sample_bytes": len(sample), "ones_ratio": ones_ratio, "adjacent_byte_serial_correlation": correlation}, (
            "BSR2-S64 keystream diagnostics only."
        )

    def v3_stream_round_trip(self):
        cfg = self.config["v3"]
        key = self.bytes(32)
        failures = 0
        for index in range(cfg["stream_round_trip_trials"]):
            data = self.bytes(self.random.randint(0, 1024))
            blob = encrypt_bytes(key, data, context=f"research:stream:{index}", chunk_size=64)
            failures += decrypt_bytes(key, blob, context=f"research:stream:{index}") != data
        return failures == 0, {"round_trip_failures": failures}, "BSR-STREAM-1 multi-chunk round trips."

    def v3_archive_round_trip(self):
        cfg = self.config["v3"]
        key = self.bytes(32)
        failures = 0
        for index in range(cfg["archive_round_trip_trials"]):
            members = [(f"m{index}/f{j}.bin", self.bytes(self.random.randint(0, 512)), j, "") for j in range(4)]
            blob = build_archive(members, key=key, solid=bool(index % 2), recovery_percent=10, recovery_chunk_size=128)
            reader = ArchiveReader(blob, key=key)
            failures += any(reader.read(name) != data for name, data, *_ in members)
        return failures == 0, {"round_trip_failures": failures}, "Archive build/read with recovery records."

    # Benchmarks --------------------------------------------------------------

    def performance_hash(self):
        cfg = self.config["performance"]
        rows = []
        for size, repetitions in zip(cfg["hash_message_sizes"], cfg["hash_repetitions"]):
            message = self.bytes(size)
            started = time.perf_counter()
            for _ in range(repetitions):
                sponge_hash(message)
            elapsed = time.perf_counter() - started
            rows.append({"message_bytes": size, "repetitions": repetitions, "bytes_per_second": size * repetitions / elapsed})
        return True, {"measurements": rows}, "Local runtime measurement; machine and interpreter dependent."

    def performance_envelope(self):
        cfg = self.config["performance"]
        master = self.bytes(32)
        rows = []
        for size, repetitions in zip(cfg["envelope_message_sizes"], cfg["envelope_repetitions"]):
            plaintext = self.bytes(size)
            generator = BrisartDRBG(hashlib.sha512(b"perf" + size.to_bytes(8, "big")).digest(), b"BSR2 performance test")
            started = time.perf_counter()
            for index in range(repetitions):
                context = f"performance:{size}:{index}"
                decrypt(master, encrypt(master, plaintext, context, generator), context)
            elapsed = time.perf_counter() - started
            rows.append({"message_bytes": size, "repetitions": repetitions, "round_trip_bytes_per_second": size * repetitions / elapsed})
        return True, {"measurements": rows}, "Legacy v2 envelope encrypt/decrypt local runtime measurement."

    def performance_v3_seal(self):
        cfg = self.config["performance"]
        key = self.bytes(32)
        rows = []
        for size, repetitions in zip(cfg.get("v3_seal_message_sizes", []), cfg.get("v3_seal_repetitions", [])):
            plaintext = self.bytes(size)
            started = time.perf_counter()
            for index in range(repetitions):
                unseal(key, seal(key, plaintext, f"perf:{index}"), f"perf:{index}")
            elapsed = time.perf_counter() - started
            rows.append({"message_bytes": size, "repetitions": repetitions, "round_trip_bytes_per_second": size * repetitions / elapsed})
        return True, {"measurements": rows}, "v3 seal/unseal local runtime measurement."

    def execute(self):
        h, m, s, d, e, p = (self.config[k] for k in ("hash", "mac", "stream", "drbg", "envelope", "performance"))
        self.run("hash", "single-bit avalanche", h["avalanche_trials"], self.hash_avalanche)
        self.run("hash", "collision observation", h["collision_trials"], self.hash_collisions)
        self.run("hash", "domain separation", h["domain_separation_trials"], self.hash_domain_separation)
        self.run("mac", "message tamper sensitivity", m["tamper_trials"], self.mac_tamper)
        self.run("mac", "labeled input separation", m["domain_trials"], self.mac_domain_separation)
        self.run("stream", "unique nonce blocks", s["unique_block_trials"], self.stream_unique_blocks)
        self.run("stream", "bit balance and serial correlation", s["sample_bytes"], self.stream_statistics)
        self.run("drbg", "determinism", d["determinism_trials"], self.drbg_determinism)
        self.run("drbg", "single-bit seed sensitivity", d["seed_sensitivity_trials"], self.drbg_seed_sensitivity)
        self.run("envelope", "randomized round trips", e["round_trip_trials"], self.envelope_round_trip)
        self.run("envelope", "binary field tamper rejection", e["tamper_trials"], self.envelope_tamper)
        self.run("envelope", "wrong context rejection", e["wrong_context_trials"], self.envelope_wrong_context)
        self.run("envelope", "wrong key rejection", e["wrong_key_trials"], self.envelope_wrong_key)
        v3 = self.config.get("v3")
        if v3:
            self.run("v3", "sealed randomized round trips", v3["sealed_round_trip_trials"], self.v3_sealed_round_trip)
            self.run("v3", "sealed single-bit tamper rejection", v3["sealed_tamper_trials"], self.v3_sealed_tamper)
            self.run("v3", "randomizer-reuse misuse resistance", v3["misuse_trials"], self.v3_misuse)
            self.run("v3", "S64 keystream bit balance and correlation", v3["keystream_sample_bytes"], self.v3_keystream_statistics)
            self.run("v3", "stream multi-chunk round trips", v3["stream_round_trip_trials"], self.v3_stream_round_trip)
            self.run("v3", "archive round trips", v3["archive_round_trip_trials"], self.v3_archive_round_trip)
        self.run("performance", "hash throughput", sum(p["hash_repetitions"]), self.performance_hash, success_status="BENCHMARK")
        self.run("performance", "envelope round-trip throughput", sum(p["envelope_repetitions"]), self.performance_envelope, success_status="BENCHMARK")
        if p.get("v3_seal_message_sizes"):
            self.run("performance", "v3 seal round-trip throughput", sum(p["v3_seal_repetitions"]), self.performance_v3_seal, success_status="BENCHMARK")


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_git(repository_root: Path, *arguments: str) -> str | None:
    try:
        completed = subprocess.run(["git", *arguments], cwd=repository_root, check=True, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def build_provenance(config_path: Path) -> dict:
    git_status = run_git(REPOSITORY_ROOT, "status", "--porcelain")
    return {
        "project_release": PROJECT_RELEASE,
        "release_name": RELEASE_NAME,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "operating_system": platform.system(),
        "platform_release": platform.release(),
        "source_revision": run_git(REPOSITORY_ROOT, "rev-parse", "HEAD"),
        "source_tree_dirty": None if git_status is None else bool(git_status),
        "configuration_path": str(config_path),
        "configuration_sha256": sha256_file(config_path),
        "known_answer_vector_path": "tests/known_answer_vectors.json",
        "known_answer_vector_sha256": sha256_file(REPOSITORY_ROOT / "tests" / "known_answer_vectors.json"),
        "v3_known_answer_vector_sha256": sha256_file(REPOSITORY_ROOT / "tests" / "v3_known_answer_vectors.json"),
    }


def resolve_output_directory(config: dict) -> Path:
    output_dir = Path(config["output_directory"])
    return output_dir if output_dir.is_absolute() else REPOSITORY_ROOT / output_dir


def dirty_state_text(value: bool | None) -> str:
    return "unavailable" if value is None else str(value).lower()


def write_outputs(config: dict, results: list[Result], output_dir: Path, provenance: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()
    checks = [r for r in results if r.status != "BENCHMARK"]
    benchmarks = [r for r in results if r.status == "BENCHMARK"]
    summary = {
        "checks_total": len(checks),
        "checks_passed": sum(r.status == "PASS" for r in checks),
        "checks_failed": sum(r.status == "FAIL" for r in checks),
        "checks_errored": sum(r.status == "ERROR" for r in checks),
        "benchmarks_completed": len(benchmarks),
        "results_total": len(results),
        "total_duration_seconds": sum(r.duration_seconds for r in results),
    }
    payload = {
        "generated_utc": generated,
        "warning": "Passing results demonstrate only the measured behavior. They do not establish cryptographic security.",
        "provenance": provenance,
        "configuration": config,
        "summary": summary,
        "results": [asdict(r) for r in results],
    }
    (output_dir / "research_test_results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "research_test_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["category", "name", "status", "trials", "duration_seconds", "metrics", "note"])
        for r in results:
            writer.writerow([r.category, r.name, r.status, r.trials, f"{r.duration_seconds:.6f}", json.dumps(r.metrics, sort_keys=True), r.note])
    lines = [
        "# BrisartSecurityResearch Test Results",
        "",
        f"Generated UTC: `{generated}`",
        f"Release: `{provenance['project_release']}` ({provenance['release_name']})",
        f"Profile: `{config['profile_name']}`",
        "",
        "> Passing checks demonstrate only the measured behavior. They do not establish cryptographic "
        "security, production suitability, or resistance to cryptanalysis.",
        "",
        "## Provenance",
        "",
        f"- Python: `{provenance['python_implementation']} {provenance['python_version']}`",
        f"- Operating system: `{provenance['operating_system']} {provenance['platform_release']}`",
        f"- Source revision: `{provenance['source_revision'] or 'unavailable'}`",
        f"- Uncommitted changes present: `{dirty_state_text(provenance['source_tree_dirty'])}`",
        f"- Configuration SHA-256: `{provenance['configuration_sha256'] or 'unavailable'}`",
        f"- Known-answer vector SHA-256: `{provenance['known_answer_vector_sha256'] or 'unavailable'}`",
        f"- v3 known-answer vector SHA-256: `{provenance['v3_known_answer_vector_sha256'] or 'unavailable'}`",
        "",
        "## Summary",
        "",
        f"- Checks: {summary['checks_total']}",
        f"- Passed: {summary['checks_passed']}",
        f"- Failed: {summary['checks_failed']}",
        f"- Errors: {summary['checks_errored']}",
        f"- Benchmarks completed: {summary['benchmarks_completed']}",
        f"- Total runtime: {summary['total_duration_seconds']:.3f} seconds",
        "",
        "## Detailed Results",
        "",
    ]
    for r in results:
        lines.extend([
            f"### {r.status}: {r.category} / {r.name}",
            "",
            f"- Trials or sample units: {r.trials}",
            f"- Duration: {r.duration_seconds:.3f} seconds",
            f"- Metrics: `{json.dumps(r.metrics, sort_keys=True)}`",
            f"- Note: {r.note}",
            "",
        ])
    (output_dir / "research_test_results.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run configurable Brisart cryptographic research tests.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to JSON configuration.")
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    suite = Suite(config)
    suite.execute()
    write_outputs(config, suite.results, resolve_output_directory(config), build_provenance(config_path))
    return 1 if any(r.status in {"FAIL", "ERROR"} for r in suite.results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
