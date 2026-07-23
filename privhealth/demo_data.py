"""Deterministic synthetic dataset used only for prototype validation."""

from __future__ import annotations

import numpy as np
import pandas as pd


CITY_ZIPS = {
    "MA": [("Boston", 2108), ("Cambridge", 2138), ("Worcester", 1608)],
    "NY": [("Albany", 12207), ("Buffalo", 14201), ("Rochester", 14604)],
    "CA": [("Los Angeles", 90012), ("Oakland", 94607), ("San Diego", 92101)],
    "TX": [("Austin", 78701), ("Dallas", 75201), ("Houston", 77002)],
}


def generate_demo_data(rows: int = 2000, seed: int = 42) -> pd.DataFrame:
    """Create a reproducible clinical-like table with controlled correlations."""

    if rows < 20:
        raise ValueError("At least 20 rows are required")
    rng = np.random.default_rng(seed)
    age = np.clip(rng.normal(49, 18, rows).round(), 18, 90).astype(int)
    gender = rng.choice(["F", "M"], size=rows, p=[0.52, 0.48])
    race = rng.choice(
        ["white", "black", "asian", "other"],
        size=rows,
        p=[0.56, 0.20, 0.14, 0.10],
    )
    marital = rng.choice(
        ["married", "single", "divorced", "widowed"],
        size=rows,
        p=[0.50, 0.30, 0.13, 0.07],
    )
    state = rng.choice(list(CITY_ZIPS), size=rows, p=[0.35, 0.25, 0.25, 0.15])
    city: list[str] = []
    zip_code: list[str] = []
    for selected_state in state:
        selected_city, base_zip = CITY_ZIPS[selected_state][
            int(rng.integers(0, len(CITY_ZIPS[selected_state])))
        ]
        city.append(selected_city)
        zip_code.append(str(base_zip + int(rng.integers(0, 15))).zfill(5))

    bmi = np.clip(rng.normal(27.5, 5.2, rows), 16, 48).round(1)
    smoker = rng.binomial(1, 0.18, rows)
    systolic_bp = np.clip(
        92 + 0.62 * age + 0.45 * (bmi - 22) + 7 * smoker + rng.normal(0, 11, rows),
        85,
        210,
    ).round().astype(int)
    glucose = np.clip(
        70 + 0.27 * age + 0.65 * (bmi - 22) + rng.normal(0, 14, rows),
        60,
        260,
    ).round().astype(int)
    high_risk_probability = 1 / (
        1
        + np.exp(
            -(
                -7.0
                + 0.055 * age
                + 0.075 * bmi
                + 0.95 * smoker
                + 0.011 * systolic_bp
            )
        )
    )
    high_risk = rng.binomial(1, high_risk_probability)

    condition = np.full(rows, "none", dtype=object)
    condition[(glucose >= 126) & (bmi >= 27)] = "diabetes"
    condition[systolic_bp >= 140] = "hypertension"
    asthma = (rng.random(rows) < 0.09) & (condition == "none")
    condition[asthma] = "asthma"

    return pd.DataFrame({
        "patient_id": [f"P{index:07d}" for index in range(rows)],
        "first_name": [f"First{index}" for index in range(rows)],
        "last_name": [f"Last{index}" for index in range(rows)],
        "birthdate": [f"{2026 - value}-01-01" for value in age],
        "age": age,
        "gender": gender,
        "race": race,
        "marital": marital,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "bmi": bmi,
        "smoker": smoker,
        "systolic_bp": systolic_bp,
        "glucose": glucose,
        "condition": condition,
        "high_risk": high_risk,
    })
