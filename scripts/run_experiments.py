#!/usr/bin/env python3
"""Run the reproducible PrivHealth privacy-utility benchmark."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from time import perf_counter

os.environ.setdefault("MPLCONFIGDIR", "/tmp/privhealth-matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from privhealth import (
    AdaptiveAnonymizer,
    PrivacyConfig,
    direct_removal,
    fixed_generalization,
    uniform_generalization,
)
from privhealth.metrics import classification_f1


METHODS = {
    "direct_removal": direct_removal,
    "fixed": fixed_generalization,
    "uniform": uniform_generalization,
    "adaptive": None,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--k-values", nargs="+", type=int, default=[2, 5, 10])
    parser.add_argument("--l-value", type=int, default=2)
    parser.add_argument("--target", default="high_risk")
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        help="Optional deterministic sample sizes drawn from the input file",
    )
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    full_source = pd.read_csv(args.input, dtype={"zip_code": "string"})
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_columns = [
        "age",
        "gender",
        "race",
        "marital",
        "zip_code",
        "bmi",
        "smoker",
        "systolic_bp",
        "glucose",
    ]
    rows: list[dict[str, object]] = []
    traces: list[pd.DataFrame] = []

    sizes = args.sizes or [len(full_source)]
    invalid_sizes = [size for size in sizes if size < 20 or size > len(full_source)]
    if invalid_sizes:
        raise ValueError(
            f"Every size must be between 20 and {len(full_source)}; got {invalid_sizes}"
        )
    if args.repetitions < 1:
        raise ValueError("--repetitions must be at least 1")

    for size in sizes:
        source = full_source.sample(n=size, random_state=args.seed).reset_index(drop=True)
        original_f1_full = classification_f1(source, feature_columns, args.target)
        for k in args.k_values:
            config = PrivacyConfig(k=k, l=args.l_value)
            for method_name, method in METHODS.items():
                def execute():
                    if method_name == "adaptive":
                        return AdaptiveAnonymizer(config).fit_transform(source)
                    assert method is not None
                    return method(source, config)

                execute()  # Warm-up run excluded from timing summaries.
                runtimes_ms: list[float] = []
                result = None
                for _ in range(args.repetitions):
                    started = perf_counter()
                    result = execute()
                    runtimes_ms.append((perf_counter() - started) * 1000.0)
                assert result is not None

                output_csv = (
                    output_dir
                    / f"{method_name}_n{size}_k{k}_l{args.l_value}.csv"
                )
                result.data.to_csv(output_csv, index=False)
                retained_original = source.loc[result.data.index]
                original_f1_retained = classification_f1(
                    retained_original, feature_columns, args.target
                )
                anonymized_f1 = classification_f1(result.data, feature_columns, args.target)
                retention = (
                    anonymized_f1 / original_f1_retained
                    if pd.notna(anonymized_f1)
                    and pd.notna(original_f1_retained)
                    and original_f1_retained > 0
                    else float("nan")
                )
                row: dict[str, object] = {
                    "method": method_name,
                    "dataset_size": size,
                    "k_target": k,
                    "l_target": args.l_value,
                    "original_rows": len(source),
                    "original_f1_full": original_f1_full,
                    "original_f1_retained": original_f1_retained,
                    "anonymized_f1": anonymized_f1,
                    "f1_retention": retention,
                    "privacy_satisfied": result.metrics["risk"] == 0.0,
                    "levels": json.dumps(result.levels, sort_keys=True),
                    "runtime_median_ms": float(np.median(runtimes_ms)),
                    "runtime_p95_ms": float(np.percentile(runtimes_ms, 95)),
                }
                row.update(result.metrics)
                rows.append(row)

                if method_name == "adaptive" and not result.trace.empty:
                    trace = result.trace.copy()
                    trace.insert(0, "method", method_name)
                    trace.insert(1, "dataset_size", size)
                    trace.insert(2, "k_target", k)
                    trace.insert(3, "l_target", args.l_value)
                    traces.append(trace)

    summary = pd.DataFrame(rows)
    summary.to_csv(output_dir / "summary.csv", index=False)
    if traces:
        pd.concat(traces, ignore_index=True).to_csv(
            output_dir / "adaptive_trace.csv", index=False
        )

    plot_size = max(sizes)
    plot_data = summary[
        (summary["dataset_size"] == plot_size)
        & (summary["method"] != "direct_removal")
    ]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6))
    for method_name, group in plot_data.groupby("method"):
        ordered = group.sort_values("k_target")
        label = method_name.replace("_", " ")
        axes[0].plot(
            ordered["k_target"],
            ordered["information_loss"],
            marker="o",
            linewidth=1.6,
            label=label,
        )
        axes[1].plot(
            ordered["k_target"],
            ordered["f1_retention"],
            marker="o",
            linewidth=1.6,
            label=label,
        )
    axes[0].set_xlabel("Target k")
    axes[0].set_ylabel("Combined information loss")
    axes[0].set_title("(a) Transformation cost")
    axes[1].set_xlabel("Target k")
    axes[1].set_ylabel("Macro-F1 retention")
    axes[1].axhline(1.0, color="black", linewidth=0.8, linestyle="--")
    axes[1].set_title("(b) Downstream utility")
    for ax in axes:
        ax.grid(alpha=0.25)
    axes[1].legend(frameon=False)
    fig.suptitle(f"Privacy-satisfying methods at n={plot_size}, l={args.l_value}")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.91))
    fig.savefig(output_dir / "privacy_utility.png", dpi=240)
    plt.close(fig)

    printable = summary[[
        "method",
        "dataset_size",
        "k_target",
        "l_target",
        "achieved_k",
        "achieved_l",
        "suppression_rate",
        "information_loss",
        "f1_retention",
        "runtime_median_ms",
        "runtime_p95_ms",
    ]]
    print(printable.to_string(index=False))


if __name__ == "__main__":
    main()
