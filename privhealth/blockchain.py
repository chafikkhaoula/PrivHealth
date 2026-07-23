"""Build verifiable privacy-release certificates for blockchain registration."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


SCHEMA_VERSION = "privhealth-release/v1"
DEFAULT_QUASI_IDENTIFIERS = (
    "age",
    "gender",
    "race",
    "marital",
    "zip_code",
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Mapping[str, Any]) -> str:
    """Serialize a JSON object deterministically for cross-system hashing."""

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def certificate_hash(certificate: Mapping[str, Any]) -> str:
    """Hash a certificate while excluding its self-referential hash field."""

    unsigned = {
        key: value
        for key, value in certificate.items()
        if key != "certificate_hash_sha256"
    }
    return hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"Cannot interpret {value!r} as a boolean")


def _metric(value: Any) -> str:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"Expected a normalized metric in [0, 1], got {number}")
    return f"{number:.6f}"


def _levels(value: Any) -> dict[str, int]:
    parsed = json.loads(value) if isinstance(value, str) else dict(value)
    return {
        str(key): int(level)
        for key, level in sorted(parsed.items())
    }


def build_release_certificate(
    released_csv: Path,
    result: Mapping[str, Any],
    *,
    generator_version: str,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build and validate a certificate from one benchmark summary row."""

    required = {
        "method",
        "dataset_size",
        "k_target",
        "l_target",
        "achieved_k",
        "achieved_l",
        "retained_rows",
        "suppression_rate",
        "information_loss",
        "hierarchy_loss",
        "privacy_satisfied",
        "levels",
    }
    missing = sorted(required.difference(result))
    if missing:
        raise KeyError(f"Missing benchmark fields: {', '.join(missing)}")
    if not released_csv.is_file():
        raise FileNotFoundError(released_csv)

    target_k = int(float(result["k_target"]))
    target_l = int(float(result["l_target"]))
    achieved_k = int(float(result["achieved_k"]))
    achieved_l = int(float(result["achieved_l"]))
    source_rows = int(float(result["dataset_size"]))
    retained_rows = int(float(result["retained_rows"]))
    privacy_satisfied = _as_bool(result["privacy_satisfied"])

    if target_k < 2 or target_l < 2:
        raise ValueError("Blockchain registration requires k >= 2 and l >= 2")
    if not privacy_satisfied:
        raise ValueError("Cannot certify a release that failed its privacy targets")
    if achieved_k < target_k or achieved_l < target_l:
        raise ValueError("Achieved privacy values do not meet the declared targets")
    if source_rows < 1 or retained_rows < 1 or retained_rows > source_rows:
        raise ValueError("Invalid source/retained row counts")

    digest = sha256_file(released_csv)
    timestamp = created_at_utc or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
    method = str(result["method"]).strip().lower()
    release_id = (
        f"ph-{digest[:16]}-{method}-n{source_rows}-k{target_k}-l{target_l}"
    )
    certificate: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "release_id": release_id,
        "artifact_name": released_csv.name,
        "dataset_hash_sha256": digest,
        "method": method,
        "source_rows": source_rows,
        "retained_rows": retained_rows,
        "target_k": target_k,
        "target_l": target_l,
        "achieved_k": achieved_k,
        "achieved_l": achieved_l,
        "suppression_rate": _metric(result["suppression_rate"]),
        "information_loss": _metric(result["information_loss"]),
        "hierarchy_loss": _metric(result["hierarchy_loss"]),
        "privacy_satisfied": True,
        "quasi_identifiers": list(DEFAULT_QUASI_IDENTIFIERS),
        "sensitive_attribute": "condition",
        "generalization_levels": _levels(result["levels"]),
        "generator_version": generator_version,
        "created_at_utc": timestamp,
    }
    certificate["certificate_hash_sha256"] = certificate_hash(certificate)
    return certificate


def verify_release_certificate(
    certificate: Mapping[str, Any],
    released_csv: Path,
) -> bool:
    """Verify both certificate metadata integrity and released-file integrity."""

    stored_certificate_hash = str(
        certificate.get("certificate_hash_sha256", "")
    ).lower()
    stored_dataset_hash = str(
        certificate.get("dataset_hash_sha256", "")
    ).lower()
    if not SHA256_PATTERN.fullmatch(stored_certificate_hash):
        return False
    if not SHA256_PATTERN.fullmatch(stored_dataset_hash):
        return False
    return (
        certificate_hash(certificate) == stored_certificate_hash
        and sha256_file(released_csv) == stored_dataset_hash
    )
