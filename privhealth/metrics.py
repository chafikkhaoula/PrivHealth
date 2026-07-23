"""Privacy and utility metrics for de-identification experiments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .hierarchies import maximum_level


def _group_stat(
    df: pd.DataFrame,
    quasi_identifiers: Sequence[str],
    sensitive_attribute: str | None,
) -> tuple[pd.Series, pd.Series | None]:
    if df.empty:
        empty = pd.Series(dtype="int64", index=df.index)
        return empty, empty if sensitive_attribute else None
    grouped = df.groupby(list(quasi_identifiers), dropna=False, observed=False)
    sizes = grouped[quasi_identifiers[0]].transform("size")
    diversity = None
    if sensitive_attribute:
        diversity = grouped[sensitive_attribute].transform("nunique")
    return sizes.astype(int), diversity.astype(int) if diversity is not None else None


def privacy_profile(
    df: pd.DataFrame,
    quasi_identifiers: Sequence[str],
    sensitive_attribute: str | None,
    k: int,
    l: int = 1,
) -> dict[str, float]:
    """Compute record-level k/l deficits and achieved minimum group properties."""

    if k < 1 or l < 1:
        raise ValueError("k and l must be positive integers")
    if df.empty:
        return {
            "risk": 1.0,
            "k_deficit": 1.0,
            "l_deficit": 1.0 if l > 1 else 0.0,
            "violating_fraction": 1.0,
            "achieved_k": 0.0,
            "achieved_l": 0.0,
        }

    sizes, diversity = _group_stat(df, quasi_identifiers, sensitive_attribute)
    k_deficit = np.maximum(k - sizes.to_numpy(), 0).mean() / k
    unsafe = sizes < k

    if l > 1:
        if diversity is None:
            raise ValueError("A sensitive attribute is required when l > 1")
        l_deficit = np.maximum(l - diversity.to_numpy(), 0).mean() / l
        unsafe = unsafe | (diversity < l)
        risk = 0.7 * float(k_deficit) + 0.3 * float(l_deficit)
        achieved_l = float(diversity.min())
    else:
        l_deficit = 0.0
        risk = float(k_deficit)
        achieved_l = float("nan")

    return {
        "risk": risk,
        "k_deficit": float(k_deficit),
        "l_deficit": float(l_deficit),
        "violating_fraction": float(unsafe.mean()),
        "achieved_k": float(sizes.min()),
        "achieved_l": achieved_l,
    }


def unsafe_mask(
    df: pd.DataFrame,
    quasi_identifiers: Sequence[str],
    sensitive_attribute: str | None,
    k: int,
    l: int = 1,
) -> pd.Series:
    """Return records belonging to an equivalence class that violates k or l."""

    sizes, diversity = _group_stat(df, quasi_identifiers, sensitive_attribute)
    mask = sizes < k
    if l > 1:
        if diversity is None:
            raise ValueError("A sensitive attribute is required when l > 1")
        mask = mask | (diversity < l)
    return mask


def hierarchy_loss(
    levels: Mapping[str, int],
    weights: Mapping[str, float] | None = None,
) -> float:
    """Weighted normalized hierarchy depth in [0, 1]."""

    weights = weights or {}
    numerator = 0.0
    denominator = 0.0
    for column, level in levels.items():
        weight = float(weights.get(column, 1.0))
        numerator += weight * (level / maximum_level(column))
        denominator += weight
    return numerator / denominator if denominator else 0.0


def combined_information_loss(
    levels: Mapping[str, int],
    suppression_rate: float,
    weights: Mapping[str, float] | None = None,
) -> float:
    """Compute record-weighted loss, treating suppression as maximum loss.

    Retained records incur the configured hierarchy loss. Suppressed records
    contribute a loss of one because none of their values remain available.
    """

    generalization = hierarchy_loss(levels, weights)
    suppression = float(suppression_rate)
    return (1.0 - suppression) * generalization + suppression


def classification_f1(
    df: pd.DataFrame,
    feature_columns: Sequence[str],
    target_column: str,
    random_state: int = 42,
) -> float:
    """Estimate macro-F1 with stratified cross-validation for a utility task."""

    if df.empty or target_column not in df.columns:
        return float("nan")
    y = df[target_column]
    if y.nunique(dropna=True) < 2:
        return float("nan")
    counts = y.value_counts()
    folds = min(5, int(counts.min()))
    if folds < 2:
        return float("nan")

    available = [column for column in feature_columns if column in df.columns]
    if not available:
        return float("nan")
    x = df[available].astype("object")
    transformer = ColumnTransformer(
        [("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]), available)],
        remainder="drop",
    )
    model = Pipeline([
        ("features", transformer),
        ("classifier", LogisticRegression(max_iter=500, random_state=random_state)),
    ])
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=random_state)
    predictions = cross_val_predict(model, x, y, cv=cv, method="predict")
    return float(f1_score(y, predictions, average="macro"))
