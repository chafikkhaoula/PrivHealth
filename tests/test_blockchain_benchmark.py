"""Unit tests for the Fabric registry benchmark helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    PROJECT_ROOT
    / "blockchain"
    / "fabric-network"
    / "scripts"
    / "benchmark_registry.py"
)
SPEC = importlib.util.spec_from_file_location(
    "benchmark_registry",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class BlockchainBenchmarkTests(unittest.TestCase):
    """Validate pure benchmark preparation and summary behavior."""

    def base_certificate(self) -> dict:
        """Return a minimal valid certificate-shaped mapping."""

        value = {
            "schema_version": "privhealth-release/v1",
            "release_id": "ph-original-release",
            "artifact_name": "adaptive_n10000_k5_l2.csv",
            "dataset_hash_sha256": "a" * 64,
            "method": "adaptive",
            "source_rows": 10000,
            "retained_rows": 7054,
            "target_k": 5,
            "target_l": 2,
            "achieved_k": 5,
            "achieved_l": 2,
            "suppression_rate": "0.294600",
            "information_loss": "0.412167",
            "hierarchy_loss": "0.166667",
            "privacy_satisfied": True,
            "quasi_identifiers": [
                "age",
                "gender",
                "race",
                "marital",
                "zip_code",
            ],
            "sensitive_attribute": "condition",
            "generalization_levels": {
                "age": 1,
                "gender": 0,
                "marital": 0,
                "race": 0,
                "zip_code": 4,
            },
            "generator_version": "privhealth-v0.3",
            "created_at_utc": "2026-07-23T12:00:00Z",
        }
        value["certificate_hash_sha256"] = BENCHMARK.certificate_hash(value)
        return value

    def test_benchmark_certificate_is_unique_and_self_consistent(self) -> None:
        """Each iteration must have a unique ID and a valid metadata hash."""

        first = BENCHMARK.build_benchmark_certificate(
            self.base_certificate(),
            run_id="test-run",
            index=1,
        )
        second = BENCHMARK.build_benchmark_certificate(
            self.base_certificate(),
            run_id="test-run",
            index=2,
        )

        self.assertNotEqual(first["release_id"], second["release_id"])
        self.assertEqual(
            first["certificate_hash_sha256"],
            BENCHMARK.certificate_hash(first),
        )
        self.assertNotIn("ledger_tx_id", first)

    def test_nearest_rank_p95(self) -> None:
        """P95 uses the documented nearest-rank rule."""

        self.assertEqual(
            BENCHMARK.percentile_nearest_rank(list(range(1, 21)), 95),
            19,
        )

    def test_summary_excludes_warmups(self) -> None:
        """Warm-up measurements must not affect reported latency."""

        rows = [
            {
                "operation": "register",
                "warmup": True,
                "success": True,
                "latency_ms": "999.0",
            },
            {
                "operation": "register",
                "warmup": False,
                "success": True,
                "latency_ms": "10.0",
            },
            {
                "operation": "register",
                "warmup": False,
                "success": True,
                "latency_ms": "20.0",
            },
        ]

        summary = BENCHMARK.summarize(
            rows,
            {"register": 1.0},
        )[0]

        self.assertEqual(summary["attempts"], 2)
        self.assertEqual(summary["latency_median_ms"], "15.000000")


if __name__ == "__main__":
    unittest.main()
