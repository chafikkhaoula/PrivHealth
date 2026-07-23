"""Task-aware adaptive clinical data de-identification."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import pandas as pd

from .hierarchies import apply_generalization, maximum_level
from .metrics import (
    combined_information_loss,
    hierarchy_loss,
    privacy_profile,
    unsafe_mask,
)


@dataclass(frozen=True)
class PrivacyConfig:
    quasi_identifiers: tuple[str, ...] = (
        "age",
        "gender",
        "race",
        "marital",
        "zip_code",
    )
    removed_columns: tuple[str, ...] = (
        "patient_id",
        "first_name",
        "last_name",
        "birthdate",
        "address",
        "ssn",
        # ZIP is the sole released geography. Keeping exact city/state would
        # bypass the configured ZIP generalization hierarchy.
        "city",
        "state",
    )
    sensitive_attribute: str = "condition"
    k: int = 5
    l: int = 2
    utility_weights: dict[str, float] = field(default_factory=lambda: {
        "age": 3.0,
        "gender": 2.0,
        "race": 1.0,
        "marital": 1.0,
        "zip_code": 0.5,
    })


@dataclass
class AnonymizationResult:
    data: pd.DataFrame
    levels: dict[str, int]
    trace: pd.DataFrame
    metrics: dict[str, float]


def remove_excluded_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    """Remove fields excluded from the released analytical table."""

    return df.drop(columns=[column for column in columns if column in df.columns]).copy()


def finalize_candidate(
    original_without_identifiers: pd.DataFrame,
    transformed: pd.DataFrame,
    levels: dict[str, int],
    config: PrivacyConfig,
    started_at: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Suppress residual unsafe groups and compute final metrics."""

    mask = unsafe_mask(
        transformed,
        config.quasi_identifiers,
        config.sensitive_attribute,
        config.k,
        config.l,
    )
    # Preserve source indices so utility can be compared on the same records.
    final = transformed.loc[~mask].copy()
    suppression_rate = 1.0 - (len(final) / len(original_without_identifiers))
    profile = privacy_profile(
        final,
        config.quasi_identifiers,
        config.sensitive_attribute,
        config.k,
        config.l,
    )
    profile.update({
        "suppression_rate": float(suppression_rate),
        "hierarchy_loss": hierarchy_loss(levels, config.utility_weights),
        "information_loss": combined_information_loss(
            levels, suppression_rate, config.utility_weights
        ),
        "retained_rows": float(len(final)),
        "runtime_ms": (perf_counter() - started_at) * 1000.0,
    })
    return final, profile


class AdaptiveAnonymizer:
    """Greedy search with privacy-valid checkpoint selection."""

    def __init__(self, config: PrivacyConfig):
        self.config = config

    def fit_transform(self, df: pd.DataFrame) -> AnonymizationResult:
        started_at = perf_counter()
        config = self.config
        missing = [
            column
            for column in (*config.quasi_identifiers, config.sensitive_attribute)
            if column not in df.columns
        ]
        if missing:
            raise KeyError(f"Missing required columns: {', '.join(missing)}")

        original = remove_excluded_columns(df, config.removed_columns)
        levels = {column: 0 for column in config.quasi_identifiers}
        current = apply_generalization(original, levels)
        current_profile = privacy_profile(
            current,
            config.quasi_identifiers,
            config.sensitive_attribute,
            config.k,
            config.l,
        )
        checkpoints: list[dict[str, Any]] = []

        def checkpoint(
            transformed: pd.DataFrame,
            candidate_levels: dict[str, int],
            candidate_step: int,
        ) -> dict[str, Any]:
            mask = unsafe_mask(
                transformed,
                config.quasi_identifiers,
                config.sensitive_attribute,
                config.k,
                config.l,
            )
            retained_rows = int((~mask).sum())
            suppression_rate = 1.0 - (
                retained_rows / len(original)
            )
            release_loss = combined_information_loss(
                candidate_levels,
                suppression_rate,
                config.utility_weights,
            )
            candidate_checkpoint = {
                "step": candidate_step,
                "data": transformed,
                "levels": dict(candidate_levels),
                "retained_rows": retained_rows,
                "release_suppression_rate": float(suppression_rate),
                "release_information_loss": float(release_loss),
            }
            checkpoints.append(candidate_checkpoint)
            return candidate_checkpoint

        initial_checkpoint = checkpoint(current, levels, 0)
        history: list[dict[str, Any]] = [{
            "step": 0,
            "attribute": "initial",
            "level": 0,
            "risk": current_profile["risk"],
            "privacy_gain": 0.0,
            "hierarchy_loss": 0.0,
            "score": 0.0,
            "release_suppression_rate": initial_checkpoint[
                "release_suppression_rate"
            ],
            "release_information_loss": initial_checkpoint[
                "release_information_loss"
            ],
            "retained_rows": initial_checkpoint["retained_rows"],
        }]

        step = 0
        while current_profile["risk"] > 0:
            candidates: list[dict[str, Any]] = []
            current_loss = hierarchy_loss(levels, config.utility_weights)
            for column in config.quasi_identifiers:
                if levels[column] >= maximum_level(column):
                    continue
                candidate_levels = dict(levels)
                candidate_levels[column] += 1
                candidate = apply_generalization(original, candidate_levels)
                profile = privacy_profile(
                    candidate,
                    config.quasi_identifiers,
                    config.sensitive_attribute,
                    config.k,
                    config.l,
                )
                candidate_loss = hierarchy_loss(
                    candidate_levels, config.utility_weights
                )
                privacy_gain = current_profile["risk"] - profile["risk"]
                utility_cost = max(candidate_loss - current_loss, 1e-12)
                candidates.append({
                    "column": column,
                    "levels": candidate_levels,
                    "data": candidate,
                    "profile": profile,
                    "privacy_gain": privacy_gain,
                    "loss": candidate_loss,
                    "score": privacy_gain / utility_cost,
                })

            if not candidates:
                break

            best = min(
                candidates,
                key=lambda item: (
                    -item["score"],
                    item["profile"]["risk"],
                    item["loss"],
                    item["column"],
                ),
            )
            levels = best["levels"]
            current = best["data"]
            current_profile = best["profile"]
            step += 1
            current_checkpoint = checkpoint(current, levels, step)
            history.append({
                "step": step,
                "attribute": best["column"],
                "level": levels[best["column"]],
                "risk": current_profile["risk"],
                "privacy_gain": best["privacy_gain"],
                "hierarchy_loss": best["loss"],
                "score": best["score"],
                "release_suppression_rate": current_checkpoint[
                    "release_suppression_rate"
                ],
                "release_information_loss": current_checkpoint[
                    "release_information_loss"
                ],
                "retained_rows": current_checkpoint["retained_rows"],
            })

        valid_checkpoints = [
            candidate
            for candidate in checkpoints
            if candidate["retained_rows"] > 0
        ]
        if not valid_checkpoints:
            selected = checkpoints[-1]
        else:
            selected = min(
                valid_checkpoints,
                key=lambda candidate: (
                    candidate["release_information_loss"],
                    candidate["release_suppression_rate"],
                    candidate["step"],
                ),
            )

        final, metrics = finalize_candidate(
            original,
            selected["data"],
            selected["levels"],
            config,
            started_at,
        )
        metrics["search_steps"] = float(step)
        metrics["selected_step"] = float(selected["step"])
        trace = pd.DataFrame(history)
        trace["selected"] = trace["step"].eq(selected["step"])
        return AnonymizationResult(
            data=final,
            levels=selected["levels"],
            trace=trace,
            metrics=metrics,
        )
