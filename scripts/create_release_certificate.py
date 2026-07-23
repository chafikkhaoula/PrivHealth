#!/usr/bin/env python3
"""Create a blockchain-ready certificate for one PrivHealth data release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from privhealth.blockchain import build_release_certificate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--released-csv", type=Path, required=True)
    parser.add_argument("--summary-csv", type=Path, required=True)
    parser.add_argument("--dataset-size", type=int, required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--l", type=int, default=2)
    parser.add_argument("--method", default="adaptive")
    parser.add_argument("--generator-version", default="privhealth-v0.3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary = pd.read_csv(args.summary_csv)
    selected = summary[
        (summary["method"] == args.method)
        & (summary["dataset_size"] == args.dataset_size)
        & (summary["k_target"] == args.k)
        & (summary["l_target"] == args.l)
    ]
    if len(selected) != 1:
        raise ValueError(
            "Expected exactly one matching summary row; "
            f"found {len(selected)}"
        )

    certificate = build_release_certificate(
        args.released_csv,
        selected.iloc[0].to_dict(),
        generator_version=args.generator_version,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(certificate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote release certificate to {args.output.resolve()}")
    print(f"Release ID: {certificate['release_id']}")
    print(f"Dataset SHA-256: {certificate['dataset_hash_sha256']}")
    print(f"Certificate SHA-256: {certificate['certificate_hash_sha256']}")


if __name__ == "__main__":
    main()
