"""Generalization hierarchies used by PrivHealth."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


MAX_LEVELS: dict[str, int] = {
    "age": 4,
    "gender": 1,
    "race": 1,
    "marital": 1,
    "zip_code": 4,
    "city": 2,
    "state": 2,
}


US_REGIONS = {
    "CT": "Northeast",
    "MA": "Northeast",
    "ME": "Northeast",
    "NH": "Northeast",
    "NJ": "Northeast",
    "NY": "Northeast",
    "PA": "Northeast",
    "RI": "Northeast",
    "VT": "Northeast",
    "IL": "Midwest",
    "IN": "Midwest",
    "IA": "Midwest",
    "KS": "Midwest",
    "MI": "Midwest",
    "MN": "Midwest",
    "MO": "Midwest",
    "NE": "Midwest",
    "ND": "Midwest",
    "OH": "Midwest",
    "SD": "Midwest",
    "WI": "Midwest",
    "AL": "South",
    "AR": "South",
    "DC": "South",
    "DE": "South",
    "FL": "South",
    "GA": "South",
    "KY": "South",
    "LA": "South",
    "MD": "South",
    "MS": "South",
    "NC": "South",
    "OK": "South",
    "SC": "South",
    "TN": "South",
    "TX": "South",
    "VA": "South",
    "WV": "South",
    "AK": "West",
    "AZ": "West",
    "CA": "West",
    "CO": "West",
    "HI": "West",
    "ID": "West",
    "MT": "West",
    "NM": "West",
    "NV": "West",
    "OR": "West",
    "UT": "West",
    "WA": "West",
    "WY": "West",
}


def maximum_level(column: str) -> int:
    """Return the maximum supported hierarchy level for a column."""

    if column not in MAX_LEVELS:
        raise KeyError(f"No generalization hierarchy registered for {column!r}")
    return MAX_LEVELS[column]


def _age_range(value: object, width: int) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    age = max(0, int(float(value)))
    start = (age // width) * width
    return f"{start}-{start + width - 1}"


def _zip_prefix(value: object, visible: int) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    raw = str(value).split(".")[0].strip().zfill(5)
    return raw[:visible] + "*" * (5 - visible)


def generalize_column(df: pd.DataFrame, column: str, level: int) -> pd.Series:
    """Apply one registered hierarchy level to a source DataFrame column."""

    maximum = maximum_level(column)
    if level < 0 or level > maximum:
        raise ValueError(f"Invalid level {level} for {column}; expected 0..{maximum}")
    source = df[column]
    if level == 0:
        return source.copy()

    if column == "age":
        if level == 4:
            return pd.Series("*", index=df.index, dtype="object")
        width = {1: 5, 2: 10, 3: 20}[level]
        return source.map(lambda value: _age_range(value, width))

    if column == "zip_code":
        if level == 4:
            return pd.Series("*", index=df.index, dtype="object")
        visible = {1: 4, 2: 3, 3: 2}[level]
        return source.map(lambda value: _zip_prefix(value, visible))

    if column == "city":
        if level == 1:
            if "state" not in df.columns:
                raise ValueError("The city hierarchy requires a state column at level 1")
            return df["state"].fillna("UNKNOWN").astype(str)
        return pd.Series("*", index=df.index, dtype="object")

    if column == "state":
        if level == 1:
            return source.fillna("UNKNOWN").astype(str).map(
                lambda value: US_REGIONS.get(value.upper(), "Other")
            )
        return pd.Series("*", index=df.index, dtype="object")

    return pd.Series("*", index=df.index, dtype="object")


def apply_generalization(
    df: pd.DataFrame,
    levels: Mapping[str, int],
) -> pd.DataFrame:
    """Return a copy with every configured hierarchy applied from original values."""

    transformed = df.copy()
    for column, level in levels.items():
        if column not in transformed.columns:
            raise KeyError(f"Missing quasi-identifier column {column!r}")
        transformed[column] = generalize_column(df, column, level)
    return transformed
