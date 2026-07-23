# PrivHealth

PrivHealth is a reproducible research prototype for blockchain-assisted,
risk-adaptive de-identification of tabular clinical data. It selects global
generalization steps by balancing privacy gain against task-specific
information loss, then suppresses residual unsafe equivalence classes.

Released clinical tables remain off-chain. A create-only Hyperledger Fabric
registry accepts only privacy-valid release certificates and records hashes,
privacy parameters, transformation measurements, and provenance metadata.

## Research question

Can a task-aware adaptive strategy satisfy configurable k-anonymity and
l-diversity targets while retaining more analytical utility than fixed
strategies, while a permissioned ledger enforces and preserves verifiable
release evidence?

## Quick start

```bash
python3 scripts/generate_demo_data.py --rows 2000 --output data/demo_clinical.csv
python3 scripts/run_experiments.py \
  --input data/demo_clinical.csv \
  --output-dir results/demo \
  --sizes 500 1000 2000 \
  --k-values 2 5 10 \
  --l-value 2 \
  --repetitions 10
python3 -m unittest discover -s tests -v
```

The experiment command writes:

- `summary.csv`: privacy, utility, suppression, and runtime metrics;
- `adaptive_trace.csv`: each adaptive transformation selected;
- `privacy_utility.png`: information-loss and downstream-utility comparison;
- de-identified CSV files for reproducibility.

The blockchain module and certificate command are documented in
`blockchain/README.md`.

## Standardized input schema

The default experiment expects these columns:

| Role | Columns |
| --- | --- |
| Direct identifiers | `patient_id`, `first_name`, `last_name`, `birthdate` |
| Quasi-identifiers | `age`, `gender`, `race`, `marital`, `zip_code` |
| Sensitive attribute | `condition` |
| Downstream target | `high_risk` |

Additional columns are preserved unless explicitly configured as direct identifiers. A Synthea preparation script is included for converting `patients.csv` and `conditions.csv` to the standardized schema.

## Important interpretation boundary

This prototype measures formal k-anonymity/l-diversity properties, empirical
data utility, and blockchain registration/verification overhead. Blockchain
does not anonymize the data; it validates and preserves release evidence. The
prototype does not claim legal compliance, absolute anonymity, or protection
against every possible re-identification attack.
