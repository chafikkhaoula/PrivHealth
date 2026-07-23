from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from privhealth.blockchain import (
    build_release_certificate,
    certificate_hash,
    verify_release_certificate,
)


class ReleaseCertificateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.released_csv = Path(self.temporary_directory.name) / "release.csv"
        self.released_csv.write_text("age,condition\n40-49,hypertension\n")
        self.result = {
            "method": "adaptive",
            "dataset_size": 10,
            "k_target": 5,
            "l_target": 2,
            "achieved_k": 5,
            "achieved_l": 2,
            "retained_rows": 8,
            "suppression_rate": 0.2,
            "information_loss": 0.35,
            "hierarchy_loss": 0.15,
            "privacy_satisfied": True,
            "levels": json.dumps({
                "age": 1,
                "gender": 0,
                "marital": 0,
                "race": 0,
                "zip_code": 3,
            }),
        }

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_builds_verifiable_certificate(self) -> None:
        certificate = build_release_certificate(
            self.released_csv,
            self.result,
            generator_version="test",
            created_at_utc="2026-07-23T12:00:00Z",
        )
        self.assertTrue(
            verify_release_certificate(certificate, self.released_csv)
        )
        self.assertEqual(
            certificate["certificate_hash_sha256"],
            certificate_hash(certificate),
        )

    def test_detects_changed_release_file(self) -> None:
        certificate = build_release_certificate(
            self.released_csv,
            self.result,
            generator_version="test",
        )
        self.released_csv.write_text(
            "age,condition\n40-49,non_hypertension\n"
        )
        self.assertFalse(
            verify_release_certificate(certificate, self.released_csv)
        )

    def test_rejects_privacy_failure(self) -> None:
        self.result["privacy_satisfied"] = False
        with self.assertRaisesRegex(ValueError, "failed its privacy targets"):
            build_release_certificate(
                self.released_csv,
                self.result,
                generator_version="test",
            )


if __name__ == "__main__":
    unittest.main()
