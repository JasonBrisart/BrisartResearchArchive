"""Configurable research test runner for BrisartSecurityResearch.

The suite measures deterministic behavior, tamper detection, diffusion, simple
output statistics, collision observations, and throughput. Passing it does not
establish cryptographic security.
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = Path(__file__).resolve().with_name(
    "research_test_config.json"
)

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from brisart_security_drbg import BrisartDRBG
from brisart_security_envelope import BrisartEnvelopeError, decrypt, encrypt
from brisart_security_primitives import keyed_mac, sponge_hash, stream_bytes


@dataclass
class Result:
    category: str
    name: str
    status: str
    trials: int
    duration_seconds: float
    metrics: dict
    note: str


class Suite:
    def __init__(self, config: dict):
        self.config = config
        self.random = random.Random(config["deterministic_seed"])
        self.results: list[Result] = []

    def bytes(self, length: int) -> bytes:
        return bytes(self.random.getrandbits(8) for _ in range(length))

    def run(
        self,
        category: str,
        name: str,
        trials: int,
        function: Callable[[], tuple[bool, dict, str]],
        success_status: str = "PASS",
    ) -> None:
        started = time.perf_counter()
        try:
            passed, metrics, note = function()
            status = success_status if passed else "FAIL"
        except Exception as exc:
            status = "ERROR"
            metrics = {"exception_type": type(exc).__name__}
            note = str(exc)
        elapsed = time.perf_counter() - started
        self.results.append(
            Result(
                category,
                name,
                status,
                trials,
                elapsed,
                metrics,
                note,
            )
        )
        print(f"[{status:5}] {category}: {name} ({elapsed:.3f}s)")

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
            distances.append(
                sum(
                    (first ^ second).bit_count()
                    for first, second in zip(left, right)
                )
                / 256
            )
        mean = statistics.fmean(distances)
        metrics = {
            "mean_changed_bit_ratio": mean,
            "minimum_changed_bit_ratio": min(distances),
            "maximum_changed_bit_ratio": max(distances),
            "population_standard_deviation": statistics.pstdev(distances),
        }
        passed = cfg["avalanche_mean_min"] <= mean <= cfg["avalanche_mean_max"]
        return (
            passed,
            metrics,
            "Observational diffusion test; not a proof of resistance to cryptanalysis.",
        )

    def hash_collisions(self):
        count = self.config["hash"]["collision_trials"]
        seen = set()
        collisions = 0
        for index in range(count):
            message = index.to_bytes(8, "big") + self.bytes(
                self.random.randint(0, 256)
            )
            digest = sponge_hash(message)
            if digest in seen:
                collisions += 1
            seen.add(digest)
        return (
            collisions == 0,
            {
                "observed_collisions": collisions,
                "unique_digests": len(seen),
            },
            "No observed collisions does not establish collision resistance.",
        )

    def hash_domain_separation(self):
        count = self.config["hash"]["domain_separation_trials"]
        equal = 0
        for index in range(count):
            message = self.bytes(self.random.randint(0, 256))
            suffix = index.to_bytes(4, "big")
            left = sponge_hash(
                message,
                domain=b"BSR2/test/domain/a/" + suffix,
            )
            right = sponge_hash(
                message,
                domain=b"BSR2/test/domain/b/" + suffix,
            )
            equal += left == right
        return (
            equal == 0,
            {"equal_cross_domain_outputs": equal},
            "Checks observed separation for explicit test domains.",
        )

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
        return (
            unchanged == 0,
            {"undetected_message_mutations": unchanged},
            "Mutation observation only; not a forgery-resistance proof.",
        )

    def mac_domain_separation(self):
        count = self.config["mac"]["domain_trials"]
        equal = 0
        for index in range(count):
            key = self.bytes(32)
            message = self.bytes(self.random.randint(0, 256))
            suffix = index.to_bytes(4, "big")
            left = keyed_mac(key, b"domain-a" + suffix + message)
            right = keyed_mac(key, b"domain-b" + suffix + message)
            equal += left == right
        return (
            equal == 0,
            {"equal_labeled_outputs": equal},
            "Tests caller-supplied labels in MAC inputs.",
        )

    def stream_unique_blocks(self):
        count = self.config["stream"]["unique_block_trials"]
        key = self.bytes(32)
        blocks = set()
        duplicates = 0
        for index in range(count):
            nonce = index.to_bytes(32, "big")
            block = stream_bytes(key, nonce, 64)
            duplicates += block in blocks
            blocks.add(block)
        return (
            duplicates == 0,
            {
                "duplicate_blocks": duplicates,
                "unique_blocks": len(blocks),
            },
            "No observed duplicates does not establish stream indistinguishability.",
        )

    def stream_statistics(self):
        cfg = self.config["stream"]
        sample = stream_bytes(
            self.bytes(32),
            self.bytes(32),
            cfg["sample_bytes"],
        )
        one_bits = sum(value.bit_count() for value in sample)
        ones_ratio = one_bits / (len(sample) * 8)
        xs = sample[:-1]
        ys = sample[1:]
        mean_x = statistics.fmean(xs)
        mean_y = statistics.fmean(ys)
        numerator = sum(
            (x - mean_x) * (y - mean_y)
            for x, y in zip(xs, ys)
        )
        denominator = math.sqrt(
            sum((x - mean_x) ** 2 for x in xs)
            * sum((y - mean_y) ** 2 for y in ys)
        )
        correlation = numerator / denominator if denominator else 0.0
        passed = (
            cfg["ones_ratio_min"] <= ones_ratio <= cfg["ones_ratio_max"]
            and abs(correlation) <= cfg["max_absolute_serial_correlation"]
        )
        return (
            passed,
            {
                "sample_bytes": len(sample),
                "ones_ratio": ones_ratio,
                "adjacent_byte_serial_correlation": correlation,
            },
            "Simple output statistics are diagnostic only.",
        )

    def drbg_determinism(self):
        cfg = self.config["drbg"]
        mismatches = 0
        for index in range(cfg["determinism_trials"]):
            seed = self.bytes(64)
            label = b"BSR2 intermediate determinism" + index.to_bytes(4, "big")
            additional = b"request/" + index.to_bytes(4, "big")
            first = BrisartDRBG(seed, label).generate(
                cfg["output_bytes_per_trial"],
                additional,
            )
            second = BrisartDRBG(seed, label).generate(
                cfg["output_bytes_per_trial"],
                additional,
            )
            mismatches += first != second
        return (
            mismatches == 0,
            {"determinism_mismatches": mismatches},
            "Same complete input and call sequence should reproduce output.",
        )

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
            first = BrisartDRBG(bytes(seed_a), label).generate(
                cfg["output_bytes_per_trial"],
                additional,
            )
            second = BrisartDRBG(bytes(seed_b), label).generate(
                cfg["output_bytes_per_trial"],
                additional,
            )
            equal += first == second
            distances.append(
                sum(
                    (left ^ right).bit_count()
                    for left, right in zip(first, second)
                )
                / (len(first) * 8)
            )
        return (
            equal == 0,
            {
                "equal_outputs": equal,
                "mean_changed_bit_ratio": statistics.fmean(distances),
            },
            "Sensitivity observation only.",
        )

    def envelope_round_trip(self):
        cfg = self.config["envelope"]
        failures = 0
        total_bytes = 0
        master = self.bytes(32)
        for index in range(cfg["round_trip_trials"]):
            size = self.random.randint(
                0,
                cfg["maximum_random_plaintext_bytes"],
            )
            plaintext = self.bytes(size)
            total_bytes += size
            seed = hashlib.sha512(
                b"roundtrip" + index.to_bytes(8, "big")
            ).digest()
            context = f"research-suite:roundtrip:{index}"
            envelope = encrypt(
                master,
                plaintext,
                context,
                BrisartDRBG(seed, b"BSR2 research suite roundtrip"),
            )
            failures += decrypt(master, envelope, context) != plaintext
        return (
            failures == 0,
            {
                "round_trip_failures": failures,
                "total_plaintext_bytes": total_bytes,
            },
            "Behavioral correctness test across deterministic randomized lengths.",
        )

    def envelope_tamper(self):
        cfg = self.config["envelope"]
        master = self.bytes(32)
        undetected = 0
        fields = ("salt", "nonce", "ciphertext", "tag")
        for index in range(cfg["tamper_trials"]):
            plaintext = self.bytes(
                self.random.randint(
                    1,
                    min(1024, cfg["maximum_random_plaintext_bytes"]),
                )
            )
            seed = hashlib.sha512(
                b"tamper" + index.to_bytes(8, "big")
            ).digest()
            context = f"research-suite:tamper:{index}"
            envelope = encrypt(
                master,
                plaintext,
                context,
                BrisartDRBG(seed, b"BSR2 research suite tamper"),
            )
            field = fields[index % len(fields)]
            raw = bytearray.fromhex(envelope[field])
            raw[self.random.randrange(len(raw))] ^= 1 << self.random.randrange(8)
            envelope[field] = raw.hex()
            try:
                decrypt(master, envelope, context)
                undetected += 1
            except BrisartEnvelopeError:
                pass
        return (
            undetected == 0,
            {"undetected_envelope_mutations": undetected},
            "Tamper-detection observation; not a forgery-resistance proof.",
        )

    def envelope_wrong_context(self):
        count = self.config["envelope"]["wrong_context_trials"]
        master = self.bytes(32)
        accepted = 0
        for index in range(count):
            seed = hashlib.sha512(
                b"context" + index.to_bytes(8, "big")
            ).digest()
            envelope = encrypt(
                master,
                self.bytes(64),
                f"context:{index}",
                BrisartDRBG(seed, b"BSR2 context rejection test"),
            )
            try:
                decrypt(master, envelope, f"context:{index}:wrong")
                accepted += 1
            except BrisartEnvelopeError:
                pass
        return (
            accepted == 0,
            {"wrong_context_acceptances": accepted},
            "Checks that context is authenticated.",
        )

    def envelope_wrong_key(self):
        count = self.config["envelope"]["wrong_key_trials"]
        accepted = 0
        for index in range(count):
            master = self.bytes(32)
            wrong = self.bytes(32)
            seed = hashlib.sha512(
                b"wrong-key" + index.to_bytes(8, "big")
            ).digest()
            context = f"wrong-key:{index}"
            envelope = encrypt(
                master,
                self.bytes(64),
                context,
                BrisartDRBG(seed, b"BSR2 wrong key rejection"),
            )
            try:
                decrypt(wrong, envelope, context)
                accepted += 1
            except BrisartEnvelopeError:
                pass
        return (
            accepted == 0,
            {"wrong_key_acceptances": accepted},
            "Checks observed rejection under unrelated keys.",
        )

    def performance_hash(self):
        cfg = self.config["performance"]
        rows = []
        for size, repetitions in zip(
            cfg["hash_message_sizes"],
            cfg["hash_repetitions"],
        ):
            message = self.bytes(size)
            started = time.perf_counter()
            for _ in range(repetitions):
                sponge_hash(message)
            elapsed = time.perf_counter() - started
            rows.append(
                {
                    "message_bytes": size,
                    "repetitions": repetitions,
                    "bytes_per_second": size * repetitions / elapsed,
                }
            )
        return (
            True,
            {"measurements": rows},
            "Local runtime measurement; machine and interpreter dependent.",
        )

    def performance_envelope(self):
        cfg = self.config["performance"]
        master = self.bytes(32)
        rows = []
        for size, repetitions in zip(
            cfg["envelope_message_sizes"],
            cfg["envelope_repetitions"],
        ):
            plaintext = self.bytes(size)
            seed = hashlib.sha512(
                b"perf" + size.to_bytes(8, "big")
            ).digest()
            generator = BrisartDRBG(seed, b"BSR2 performance test")
            started = time.perf_counter()
            for index in range(repetitions):
                context = f"performance:{size}:{index}"
                envelope = encrypt(master, plaintext, context, generator)
                decrypt(master, envelope, context)
            elapsed = time.perf_counter() - started
            rows.append(
                {
                    "message_bytes": size,
                    "repetitions": repetitions,
                    "round_trip_bytes_per_second": (
                        size * repetitions / elapsed
                    ),
                }
            )
        return (
            True,
            {"measurements": rows},
            "Combined encrypt/decrypt local runtime measurement.",
        )

    def execute(self):
        hash_cfg = self.config["hash"]
        mac_cfg = self.config["mac"]
        stream_cfg = self.config["stream"]
        drbg_cfg = self.config["drbg"]
        envelope_cfg = self.config["envelope"]
        performance_cfg = self.config["performance"]

        self.run(
            "hash",
            "single-bit avalanche",
            hash_cfg["avalanche_trials"],
            self.hash_avalanche,
        )
        self.run(
            "hash",
            "collision observation",
            hash_cfg["collision_trials"],
            self.hash_collisions,
        )
        self.run(
            "hash",
            "domain separation",
            hash_cfg["domain_separation_trials"],
            self.hash_domain_separation,
        )
        self.run(
            "mac",
            "message tamper sensitivity",
            mac_cfg["tamper_trials"],
            self.mac_tamper,
        )
        self.run(
            "mac",
            "labeled input separation",
            mac_cfg["domain_trials"],
            self.mac_domain_separation,
        )
        self.run(
            "stream",
            "unique nonce blocks",
            stream_cfg["unique_block_trials"],
            self.stream_unique_blocks,
        )
        self.run(
            "stream",
            "bit balance and serial correlation",
            stream_cfg["sample_bytes"],
            self.stream_statistics,
        )
        self.run(
            "drbg",
            "determinism",
            drbg_cfg["determinism_trials"],
            self.drbg_determinism,
        )
        self.run(
            "drbg",
            "single-bit seed sensitivity",
            drbg_cfg["seed_sensitivity_trials"],
            self.drbg_seed_sensitivity,
        )
        self.run(
            "envelope",
            "randomized round trips",
            envelope_cfg["round_trip_trials"],
            self.envelope_round_trip,
        )
        self.run(
            "envelope",
            "binary field tamper rejection",
            envelope_cfg["tamper_trials"],
            self.envelope_tamper,
        )
        self.run(
            "envelope",
            "wrong context rejection",
            envelope_cfg["wrong_context_trials"],
            self.envelope_wrong_context,
        )
        self.run(
            "envelope",
            "wrong key rejection",
            envelope_cfg["wrong_key_trials"],
            self.envelope_wrong_key,
        )
        self.run(
            "performance",
            "hash throughput",
            sum(performance_cfg["hash_repetitions"]),
            self.performance_hash,
            success_status="BENCHMARK",
        )
        self.run(
            "performance",
            "envelope round-trip throughput",
            sum(performance_cfg["envelope_repetitions"]),
            self.performance_envelope,
            success_status="BENCHMARK",
        )


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
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def build_provenance(config_path: Path) -> dict:
    vector_path = REPOSITORY_ROOT / "tests" / "known_answer_vectors.json"
    git_status = run_git(REPOSITORY_ROOT, "status", "--porcelain")
    source_tree_dirty = None if git_status is None else bool(git_status)
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "operating_system": platform.system(),
        "platform_release": platform.release(),
        "source_revision": run_git(REPOSITORY_ROOT, "rev-parse", "HEAD"),
        "source_tree_dirty": source_tree_dirty,
        "configuration_path": str(config_path),
        "configuration_sha256": sha256_file(config_path),
        "known_answer_vector_path": "tests/known_answer_vectors.json",
        "known_answer_vector_sha256": sha256_file(vector_path),
    }


def resolve_output_directory(config: dict) -> Path:
    output_dir = Path(config["output_directory"])
    if output_dir.is_absolute():
        return output_dir
    return REPOSITORY_ROOT / output_dir


def dirty_state_text(value: bool | None) -> str:
    if value is None:
        return "unavailable"
    return str(value).lower()


def write_outputs(
    config: dict,
    results: list[Result],
    output_dir: Path,
    provenance: dict,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()
    checks = [result for result in results if result.status != "BENCHMARK"]
    benchmarks = [result for result in results if result.status == "BENCHMARK"]
    summary = {
        "checks_total": len(checks),
        "checks_passed": sum(result.status == "PASS" for result in checks),
        "checks_failed": sum(result.status == "FAIL" for result in checks),
        "checks_errored": sum(result.status == "ERROR" for result in checks),
        "benchmarks_completed": len(benchmarks),
        "results_total": len(results),
        "total_duration_seconds": sum(
            result.duration_seconds for result in results
        ),
    }
    payload = {
        "generated_utc": generated,
        "warning": (
            "Passing results demonstrate only the measured behavior. "
            "They do not establish cryptographic security."
        ),
        "provenance": provenance,
        "configuration": config,
        "summary": summary,
        "results": [asdict(result) for result in results],
    }

    (output_dir / "research_test_results.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    with (output_dir / "research_test_results.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "category",
                "name",
                "status",
                "trials",
                "duration_seconds",
                "metrics",
                "note",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result.category,
                    result.name,
                    result.status,
                    result.trials,
                    f"{result.duration_seconds:.6f}",
                    json.dumps(result.metrics, sort_keys=True),
                    result.note,
                ]
            )

    lines = [
        "# BrisartSecurityResearch Test Results",
        "",
        f"Generated UTC: `{generated}`",
        f"Profile: `{config['profile_name']}`",
        "",
        "> Passing checks demonstrate only the measured behavior. They do not "
        "establish cryptographic security, production suitability, or resistance "
        "to cryptanalysis.",
        "",
        "## Provenance",
        "",
        f"- Python: `{provenance['python_implementation']} "
        f"{provenance['python_version']}`",
        f"- Operating system: `{provenance['operating_system']} "
        f"{provenance['platform_release']}`",
        f"- Source revision: `{provenance['source_revision'] or 'unavailable'}`",
        "- Uncommitted changes present: "
        f"`{dirty_state_text(provenance['source_tree_dirty'])}`",
        "- Configuration SHA-256: "
        f"`{provenance['configuration_sha256'] or 'unavailable'}`",
        "- Known-answer vector SHA-256: "
        f"`{provenance['known_answer_vector_sha256'] or 'unavailable'}`",
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
    for result in results:
        lines.extend(
            [
                f"### {result.status}: {result.category} / {result.name}",
                "",
                f"- Trials or sample units: {result.trials}",
                f"- Duration: {result.duration_seconds:.3f} seconds",
                f"- Metrics: `{json.dumps(result.metrics, sort_keys=True)}`",
                f"- Note: {result.note}",
                "",
            ]
        )
    (output_dir / "research_test_results.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run configurable Brisart cryptographic research tests."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to JSON configuration.",
    )
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    suite = Suite(config)
    suite.execute()
    write_outputs(
        config,
        suite.results,
        resolve_output_directory(config),
        build_provenance(config_path),
    )
    return 1 if any(
        result.status in {"FAIL", "ERROR"}
        for result in suite.results
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
