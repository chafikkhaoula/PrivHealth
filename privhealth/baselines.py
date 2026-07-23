"""Comparison methods for the PrivHealth experimental protocol."""

from __future__ import annotations

from time import perf_counter

import pandas as pd

from .anonymizer import (
    AnonymizationResult,
    PrivacyConfig,
    finalize_candidate,
    remove_excluded_columns,
)
from .hierarchies import apply_generalization, maximum_level
from .metrics import privacy_profile


def direct_removal(df: pd.DataFrame, config: PrivacyConfig) -> AnonymizationResult:
    """Remove direct identifiers without promising a formal privacy threshold."""

    started_at = perf_counter()
    original = remove_excluded_columns(df, config.removed_columns)
    levels = {column: 0 for column in config.quasi_identifiers}
    profile = privacy_profile(
        original,
        config.quasi_identifiers,
        config.sensitive_attribute,
        config.k,
        config.l,
    )
    profile.update({
        "suppression_rate": 0.0,
        "hierarchy_loss": 0.0,
        "information_loss": 0.0,
        "retained_rows": float(len(original)),
        "runtime_ms": (perf_counter() - started_at) * 1000.0,
    })
    return AnonymizationResult(
        data=original,
        levels=levels,
        trace=pd.DataFrame(),
        metrics=profile,
    )


def fixed_generalization(df: pd.DataFrame, config: PrivacyConfig) -> AnonymizationResult:
    """Apply one fixed hierarchy profile and suppress remaining unsafe groups."""

    started_at = perf_counter()
    original = remove_excluded_columns(df, config.removed_columns)
    preferred = {
        "age": 2,
        "gender": 0,
        "race": 0,
        "marital": 0,
        "zip_code": 2,
    }
    levels = {
        column: min(preferred.get(column, 1), maximum_level(column))
        for column in config.quasi_identifiers
    }
    transformed = apply_generalization(original, levels)
    final, metrics = finalize_candidate(
        original, transformed, levels, config, started_at
    )
    return AnonymizationResult(final, levels, pd.DataFrame(), metrics)


def uniform_generalization(df: pd.DataFrame, config: PrivacyConfig) -> AnonymizationResult:
    """Generalize every QI one level per round until privacy targets are met."""

    started_at = perf_counter()
    original = remove_excluded_columns(df, config.removed_columns)
    levels = {column: 0 for column in config.quasi_identifiers}
    transformed = apply_generalization(original, levels)
    rows: list[dict[str, float | str | int]] = []
    round_number = 0

    while True:
        profile = privacy_profile(
            transformed,
            config.quasi_identifiers,
            config.sensitive_attribute,
            config.k,
            config.l,
        )
        rows.append({
            "step": round_number,
            "attribute": "all",
            "level": round_number,
            "risk": profile["risk"],
        })
        if profile["risk"] <= 0:
            break
        changed = False
        for column in config.quasi_identifiers:
            if levels[column] < maximum_level(column):
                levels[column] += 1
                changed = True
        if not changed:
            break
        transformed = apply_generalization(original, levels)
        round_number += 1

    final, metrics = finalize_candidate(
        original, transformed, levels, config, started_at
    )
    return AnonymizationResult(final, levels, pd.DataFrame(rows), metrics)
