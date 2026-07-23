#!/usr/bin/env python3
"""Benchmark the isolated PrivHealth Fabric privacy-release registry."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping, Sequence


SCRIPT_PATH = Path(__file__).resolve()
NETWORK_ROOT = SCRIPT_PATH.parent.parent
PROJECT_ROOT = NETWORK_ROOT.parent.parent
DEFAULT_CERTIFICATE = (
    PROJECT_ROOT
    / "results"
    / "final_synthea_v02_seed42"
    / "release_n10000_k5_l2.json"
)
DEFAULT_RELEASED_CSV = (
    PROJECT_ROOT
    / "results"
    / "final_synthea_v02_seed42"
    / "adaptive_n10000_k5_l2.csv"
)
NETWORK_ENV = SCRIPT_PATH.parent / "network_env.sh"
TX_ID_PATTERN = re.compile(r"txid \[([0-9a-f]+)\]", re.IGNORECASE)
LEDGER_FIELDS = {
    "ledger_tx_id",
    "registered_at_epoch_seconds",
    "registering_msp",
}
RAW_FIELDS = (
    "run_id",
    "operation",
    "iteration",
    "warmup",
    "success",
    "latency_ms",
    "release_id",
    "tx_id",
    "started_at_utc",
    "response_excerpt",
)


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with microsecond precision."""

    return datetime.now(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def canonical_json(value: Mapping[str, Any]) -> str:
    """Serialize an object using the chaincode's canonical JSON rules."""

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def certificate_hash(certificate: Mapping[str, Any]) -> str:
    """Return the SHA-256 digest of a certificate without its hash field."""

    unsigned = {
        key: value
        for key, value in certificate.items()
        if key != "certificate_hash_sha256"
    }
    return hashlib.sha256(
        canonical_json(unsigned).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file without loading it entirely into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile_nearest_rank(values: Sequence[float], percentile: float) -> float:
    """Return a nearest-rank percentile for a non-empty sequence."""

    if not values:
        raise ValueError("A percentile requires at least one value")
    if not 0 < percentile <= 100:
        raise ValueError("percentile must be in (0, 100]")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile / 100 * len(ordered)))
    return ordered[rank - 1]


def load_peer_environment(profile: str) -> dict[str, str]:
    """Load one peer profile from network_env.sh."""

    if profile not in {"use_hospital1", "use_hospital2"}:
        raise ValueError(f"Unsupported peer profile: {profile}")
    command = (
        f"source {shlex.quote(str(NETWORK_ENV))}; "
        f"{profile}; "
        "env -0"
    )
    completed = subprocess.run(
        ["bash", "-c", command],
        check=True,
        capture_output=True,
    )
    environment: dict[str, str] = {}
    for item in completed.stdout.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        environment[key.decode()] = value.decode()
    return environment


def validate_base_certificate(
    certificate: Mapping[str, Any],
    released_csv: Path,
) -> None:
    """Reject an invalid base certificate before mutating the ledger."""

    if certificate_hash(certificate) != certificate.get(
        "certificate_hash_sha256"
    ):
        raise ValueError("Base certificate metadata hash is invalid")
    dataset_hash = sha256_file(released_csv)
    if dataset_hash != certificate.get("dataset_hash_sha256"):
        raise ValueError(
            "Released CSV does not match the base certificate dataset hash"
        )
    if certificate.get("privacy_satisfied") is not True:
        raise ValueError("Base certificate did not satisfy privacy")
    if int(certificate["achieved_k"]) < int(certificate["target_k"]):
        raise ValueError("Base certificate did not achieve target k")
    if int(certificate["achieved_l"]) < int(certificate["target_l"]):
        raise ValueError("Base certificate did not achieve target l")


def build_benchmark_certificate(
    base: Mapping[str, Any],
    *,
    run_id: str,
    index: int,
) -> dict[str, Any]:
    """Create a unique, valid certificate for one registration attempt."""

    certificate = {
        key: value
        for key, value in base.items()
        if key not in LEDGER_FIELDS
    }
    certificate.pop("certificate_hash_sha256", None)
    digest_prefix = str(certificate["dataset_hash_sha256"])[:16]
    certificate["release_id"] = (
        f"ph-{digest_prefix}-bench-{run_id}-i{index:04d}"
    )
    certificate["created_at_utc"] = utc_now()
    certificate["certificate_hash_sha256"] = certificate_hash(certificate)
    return certificate


def ctor(function: str, arguments: Iterable[str]) -> str:
    """Build a compact peer CLI transaction specification."""

    return json.dumps(
        {
            "function": function,
            "Args": list(arguments),
        },
        separators=(",", ":"),
    )


def invoke_command(environment: Mapping[str, str], certificate: Mapping[str, Any]) -> list[str]:
    """Return a two-peer endorsed CreateRelease command."""

    return [
        "peer",
        "chaincode",
        "invoke",
        "-o",
        environment["ORDERER_ADDRESS"],
        "--ordererTLSHostnameOverride",
        environment["ORDERER_HOSTNAME"],
        "--tls",
        "--cafile",
        environment["ORDERER_CA"],
        "--channelID",
        environment["CHANNEL_NAME"],
        "--name",
        environment["CHAINCODE_NAME"],
        "--peerAddresses",
        environment["HOSPITAL1_PEER_ADDRESS"],
        "--tlsRootCertFiles",
        environment["HOSPITAL1_CA"],
        "--peerAddresses",
        environment["HOSPITAL2_PEER_ADDRESS"],
        "--tlsRootCertFiles",
        environment["HOSPITAL2_CA"],
        "--waitForEvent",
        "--waitForEventTimeout",
        "60s",
        "--ctor",
        ctor("CreateRelease", [canonical_json(certificate)]),
    ]


def query_command(
    environment: Mapping[str, str],
    function: str,
    arguments: Iterable[str],
) -> list[str]:
    """Return a peer query command."""

    return [
        "peer",
        "chaincode",
        "query",
        "--channelID",
        environment["CHANNEL_NAME"],
        "--name",
        environment["CHAINCODE_NAME"],
        "--ctor",
        ctor(function, arguments),
    ]


def run_timed(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    timeout_seconds: float,
) -> tuple[bool, float, str, str]:
    """Run one CLI operation and return status, latency, output, and tx ID."""

    started = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command,
            env=dict(environment),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        success = completed.returncode == 0
        combined = "\n".join(
            value.strip()
            for value in (completed.stdout, completed.stderr)
            if value.strip()
        )
    except subprocess.TimeoutExpired as error:
        success = False
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        combined = f"{stdout}\n{stderr}\nTimeout after {timeout_seconds}s"
    latency_ms = (time.perf_counter_ns() - started) / 1_000_000
    match = TX_ID_PATTERN.search(combined)
    transaction_id = match.group(1) if match else ""
    return success, latency_ms, combined.strip(), transaction_id


def response_excerpt(response: str, limit: int = 500) -> str:
    """Normalize a short diagnostic response for the raw CSV."""

    normalized = " ".join(response.split())
    return normalized[:limit]


def measurement_row(
    *,
    run_id: str,
    operation: str,
    iteration: int,
    warmup: bool,
    success: bool,
    latency_ms: float,
    release_id: str,
    tx_id: str,
    started_at_utc: str,
    response: str,
) -> dict[str, Any]:
    """Build one raw measurement row."""

    return {
        "run_id": run_id,
        "operation": operation,
        "iteration": iteration,
        "warmup": warmup,
        "success": success,
        "latency_ms": f"{latency_ms:.6f}",
        "release_id": release_id,
        "tx_id": tx_id,
        "started_at_utc": started_at_utc,
        "response_excerpt": response_excerpt(response),
    }


def summarize(
    rows: Sequence[Mapping[str, Any]],
    operation_wall_seconds: Mapping[str, float],
) -> list[dict[str, Any]]:
    """Summarize non-warmup measurements by operation."""

    summaries: list[dict[str, Any]] = []
    operations = ("register", "read", "verify")
    for operation in operations:
        selected = [
            row
            for row in rows
            if row["operation"] == operation and not row["warmup"]
        ]
        successful_latencies = [
            float(row["latency_ms"])
            for row in selected
            if row["success"]
        ]
        attempts = len(selected)
        successes = len(successful_latencies)
        wall_seconds = operation_wall_seconds.get(operation, 0.0)
        summary: dict[str, Any] = {
            "operation": operation,
            "attempts": attempts,
            "successes": successes,
            "success_rate": f"{successes / attempts:.6f}" if attempts else "",
            "latency_mean_ms": "",
            "latency_median_ms": "",
            "latency_p95_ms": "",
            "latency_min_ms": "",
            "latency_max_ms": "",
            "throughput_ops_s": (
                f"{successes / wall_seconds:.6f}"
                if wall_seconds > 0
                else ""
            ),
        }
        if successful_latencies:
            summary.update({
                "latency_mean_ms": (
                    f"{statistics.fmean(successful_latencies):.6f}"
                ),
                "latency_median_ms": (
                    f"{statistics.median(successful_latencies):.6f}"
                ),
                "latency_p95_ms": (
                    f"{percentile_nearest_rank(successful_latencies, 95):.6f}"
                ),
                "latency_min_ms": f"{min(successful_latencies):.6f}",
                "latency_max_ms": f"{max(successful_latencies):.6f}",
            })
        summaries.append(summary)
    return summaries


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    """Write dictionaries to a UTF-8 CSV file."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def command_output(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> dict[str, Any]:
    """Capture a non-measured diagnostic command."""

    completed = subprocess.run(
        command,
        env=dict(environment),
        text=True,
        capture_output=True,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Sequentially benchmark Fabric release registration, read, "
            "and hash verification."
        )
    )
    parser.add_argument(
        "--certificate",
        type=Path,
        default=DEFAULT_CERTIFICATE,
        help="Base privacy-release certificate JSON.",
    )
    parser.add_argument(
        "--released-csv",
        type=Path,
        default=DEFAULT_RELEASED_CSV,
        help="Released CSV matching the base certificate.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Result directory. A timestamped directory is used by default.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=30,
        help="Measured attempts per operation (default: 30).",
    )
    parser.add_argument(
        "--warmups",
        type=int,
        default=2,
        help="Unmeasured warm-up attempts per operation (default: 2).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=90,
        help="Per-operation timeout (default: 90 seconds).",
    )
    parser.add_argument(
        "--run-id",
        help="Optional unique run identifier.",
    )
    return parser.parse_args()


def validate_arguments(arguments: argparse.Namespace) -> None:
    """Validate arguments before accessing Fabric."""

    if arguments.iterations < 1:
        raise ValueError("--iterations must be at least 1")
    if arguments.warmups < 0:
        raise ValueError("--warmups cannot be negative")
    if arguments.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")
    if not arguments.certificate.is_file():
        raise FileNotFoundError(arguments.certificate)
    if not arguments.released_csv.is_file():
        raise FileNotFoundError(arguments.released_csv)
    if not NETWORK_ENV.is_file():
        raise FileNotFoundError(NETWORK_ENV)


def main() -> int:
    """Run the benchmark and persist raw and summarized evidence."""

    arguments = parse_arguments()
    validate_arguments(arguments)

    run_id = arguments.run_id or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"-p{os.getpid()}"
    )
    if not re.fullmatch(r"[A-Za-z0-9._-]{6,80}", run_id):
        raise ValueError(
            "--run-id must contain 6-80 letters, digits, dots, underscores, "
            "or hyphens"
        )

    output_directory = arguments.output_dir or (
        PROJECT_ROOT / "results" / f"blockchain_benchmark_{run_id}"
    )
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=False)

    base_certificate = json.loads(
        arguments.certificate.read_text(encoding="utf-8")
    )
    validate_base_certificate(base_certificate, arguments.released_csv)

    hospital1_environment = load_peer_environment("use_hospital1")
    hospital2_environment = load_peer_environment("use_hospital2")

    total_attempts = arguments.warmups + arguments.iterations
    certificates = [
        build_benchmark_certificate(
            base_certificate,
            run_id=run_id,
            index=index,
        )
        for index in range(1, total_attempts + 1)
    ]

    raw_rows: list[dict[str, Any]] = []
    successful_release_ids: list[str] = []
    measured_release_ids: list[str] = []
    operation_wall_seconds: dict[str, float] = {}

    print(
        f"Run {run_id}: {arguments.warmups} warm-ups and "
        f"{arguments.iterations} measured attempts per operation."
    )
    operation_wall_seconds["register"] = 0.0
    for position, certificate in enumerate(certificates, start=1):
        warmup = position <= arguments.warmups
        iteration = (
            position
            if warmup
            else position - arguments.warmups
        )
        started_at = utc_now()
        success, latency_ms, response, tx_id = run_timed(
            invoke_command(hospital1_environment, certificate),
            environment=hospital1_environment,
            timeout_seconds=arguments.timeout_seconds,
        )
        release_id = str(certificate["release_id"])
        raw_rows.append(measurement_row(
            run_id=run_id,
            operation="register",
            iteration=iteration,
            warmup=warmup,
            success=success,
            latency_ms=latency_ms,
            release_id=release_id,
            tx_id=tx_id,
            started_at_utc=started_at,
            response=response,
        ))
        if not warmup:
            operation_wall_seconds["register"] += latency_ms / 1000
        if success:
            successful_release_ids.append(release_id)
            if not warmup:
                measured_release_ids.append(release_id)
        label = "warm-up" if warmup else "measured"
        status = "ok" if success else "FAILED"
        print(
            f"register {position}/{total_attempts} "
            f"({label}): {status}, {latency_ms:.3f} ms"
        )
    if not successful_release_ids:
        write_csv(
            output_directory / "raw_measurements.csv",
            raw_rows,
            RAW_FIELDS,
        )
        raise RuntimeError(
            "Every registration failed; raw measurements were saved"
        )

    query_release_ids = measured_release_ids or successful_release_ids
    dataset_hash = str(base_certificate["dataset_hash_sha256"])
    for operation, function in (
        ("read", "ReadRelease"),
        ("verify", "VerifyRelease"),
    ):
        operation_wall_seconds[operation] = 0.0
        total_queries = arguments.warmups + arguments.iterations
        for position in range(1, total_queries + 1):
            warmup = position <= arguments.warmups
            iteration = (
                position
                if warmup
                else position - arguments.warmups
            )
            if warmup:
                release_id = successful_release_ids[0]
            else:
                release_id = query_release_ids[
                    (iteration - 1) % len(query_release_ids)
                ]
            function_arguments = [release_id]
            if operation == "verify":
                function_arguments.append(dataset_hash)
            started_at = utc_now()
            success, latency_ms, response, tx_id = run_timed(
                query_command(
                    hospital1_environment,
                    function,
                    function_arguments,
                ),
                environment=hospital1_environment,
                timeout_seconds=arguments.timeout_seconds,
            )
            if operation == "verify" and success:
                try:
                    success = json.loads(response).get("matches") is True
                except json.JSONDecodeError:
                    success = False
            raw_rows.append(measurement_row(
                run_id=run_id,
                operation=operation,
                iteration=iteration,
                warmup=warmup,
                success=success,
                latency_ms=latency_ms,
                release_id=release_id,
                tx_id=tx_id,
                started_at_utc=started_at,
                response=response,
            ))
            if not warmup:
                operation_wall_seconds[operation] += latency_ms / 1000
            label = "warm-up" if warmup else "measured"
            status = "ok" if success else "FAILED"
            print(
                f"{operation} {position}/{total_queries} "
                f"({label}): {status}, {latency_ms:.3f} ms"
            )
    summaries = summarize(raw_rows, operation_wall_seconds)
    summary_fields = tuple(summaries[0].keys())
    write_csv(
        output_directory / "raw_measurements.csv",
        raw_rows,
        RAW_FIELDS,
    )
    write_csv(
        output_directory / "summary.csv",
        summaries,
        summary_fields,
    )
    (output_directory / "summary.json").write_text(
        json.dumps(summaries, indent=2) + "\n",
        encoding="utf-8",
    )

    channel_info_command = [
        "peer",
        "channel",
        "getinfo",
        "--channelID",
        hospital1_environment["CHANNEL_NAME"],
    ]
    metadata = {
        "run_id": run_id,
        "started_from_certificate": str(arguments.certificate.resolve()),
        "released_csv": str(arguments.released_csv.resolve()),
        "dataset_hash_sha256": dataset_hash,
        "created_at_utc": utc_now(),
        "methodology": {
            "mode": "sequential_single_client",
            "warmups_per_operation": arguments.warmups,
            "measured_attempts_per_operation": arguments.iterations,
            "registration_scope": (
                "client-observed CreateRelease latency including two-peer "
                "endorsement, ordering, validation, and commit-event wait"
            ),
            "read_scope": (
                "client-observed ReadRelease query latency on Hospital1"
            ),
            "verify_scope": (
                "client-observed VerifyRelease query latency on Hospital1; "
                "local file hashing is excluded"
            ),
            "p95_method": "nearest_rank",
            "throughput_method": (
                "successful measured operations divided by the sum of all "
                "measured attempt durations"
            ),
        },
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
            "channel": hospital1_environment["CHANNEL_NAME"],
            "chaincode": hospital1_environment["CHAINCODE_NAME"],
            "registering_msp": hospital1_environment["CORE_PEER_LOCALMSPID"],
            "endorsement_peer_count": 2,
            "peer_version": command_output(
                ["peer", "version"],
                hospital1_environment,
            ),
            "chaincode_definition": command_output(
                [
                    "peer",
                    "lifecycle",
                    "chaincode",
                    "querycommitted",
                    "--channelID",
                    hospital1_environment["CHANNEL_NAME"],
                    "--name",
                    hospital1_environment["CHAINCODE_NAME"],
                ],
                hospital1_environment,
            ),
            "channel_info_hospital1": command_output(
                channel_info_command,
                hospital1_environment,
            ),
            "channel_info_hospital2": command_output(
                channel_info_command,
                hospital2_environment,
            ),
        },
    }
    (output_directory / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nBenchmark summary")
    for summary in summaries:
        print(
            f"{summary['operation']}: "
            f"success={summary['successes']}/{summary['attempts']}, "
            f"median={summary['latency_median_ms']} ms, "
            f"p95={summary['latency_p95_ms']} ms, "
            f"throughput={summary['throughput_ops_s']} ops/s"
        )
    print(f"Results: {output_directory}")

    all_successful = all(
        int(summary["successes"]) == int(summary["attempts"])
        for summary in summaries
    )
    return 0 if all_successful else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
