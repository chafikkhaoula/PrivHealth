#!/usr/bin/env python3
"""Convert Synthea CSV exports to the PrivHealth patient-level schema."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def _column(frame: pd.DataFrame, name: str, default: object = "UNKNOWN") -> pd.Series:
    if name in frame.columns:
        return frame[name]
    return pd.Series(default, index=frame.index)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patients", type=Path, required=True)
    parser.add_argument("--conditions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-date", default="2026-01-01")
    args = parser.parse_args()

    patients = pd.read_csv(args.patients, dtype={"ZIP": "string"})
    conditions = pd.read_csv(args.conditions)
    patients.columns = patients.columns.str.upper()
    conditions.columns = conditions.columns.str.upper()
    conditions["PATIENT"] = conditions["PATIENT"].astype(str)

    reference = pd.Timestamp(args.reference_date)
    birthdate = pd.to_datetime(_column(patients, "BIRTHDATE"), errors="coerce")
    age = ((reference - birthdate).dt.days / 365.2425).fillna(0).astype(int)

    hypertension_ids = set(
        conditions.loc[
            _column(conditions, "DESCRIPTION", "").astype(str).str.contains(
                "hypertension", case=False, na=False
            ),
            "PATIENT",
        ].astype(str)
    )

    patient_ids = _column(patients, "ID").astype(str)
    high_risk = patient_ids.isin(hypertension_ids).astype(int)
    standardized = pd.DataFrame({
        "patient_id": patient_ids,
        "first_name": _column(patients, "FIRST"),
        "last_name": _column(patients, "LAST"),
        "birthdate": birthdate.dt.strftime("%Y-%m-%d"),
        "age": age,
        "gender": _column(patients, "GENDER").fillna("UNKNOWN"),
        "race": _column(patients, "RACE").fillna("UNKNOWN"),
        "marital": _column(patients, "MARITAL").fillna("UNKNOWN"),
        "city": _column(patients, "CITY").fillna("UNKNOWN"),
        "state": _column(patients, "STATE").fillna("UNKNOWN"),
        "zip_code": _column(patients, "ZIP").fillna("UNKNOWN"),
        "condition": high_risk.map({1: "hypertension", 0: "non_hypertension"}),
        "high_risk": high_risk,
    })
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    standardized.to_csv(output, index=False)
    print(f"Wrote {len(standardized)} standardized patients to {output}")


if __name__ == "__main__":
    main()
