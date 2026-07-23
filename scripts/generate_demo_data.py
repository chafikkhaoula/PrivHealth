#!/usr/bin/env python3
"""Generate deterministic demo input for local validation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from privhealth.demo_data import generate_demo_data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    generate_demo_data(args.rows, args.seed).to_csv(output, index=False)
    print(f"Wrote {args.rows} rows to {output}")


if __name__ == "__main__":
    main()
