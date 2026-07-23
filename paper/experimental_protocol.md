# PrivHealth experimental protocol — blockchain extension v0.3

## Scope

The paper evaluates PrivHealth as a self-contained blockchain-assisted clinical
data-release framework. It does not reuse or describe any broader healthcare
workflow architecture. Clinical records and released tables remain off-chain.

## Working title

**PrivHealth: Blockchain-Assisted Adaptive De-identification for Verifiable
Clinical Data Sharing**

## Research question

Can task-aware adaptive generalization satisfy configurable k-anonymity and
l-diversity targets while retaining more downstream analytical utility than
fixed strategies, and can a permissioned blockchain enforce and preserve
verifiable evidence for each privacy-valid release?

## Main claim to test

For the same formal privacy targets, selecting each generalization step by its marginal privacy-gain-to-weighted-utility-cost ratio reduces combined information loss and/or record suppression compared with fixed and uniform generalization.

This is a hypothesis until the benchmark results support it. The paper must report negative or mixed results honestly.

The blockchain claim is separate: a create-only smart contract rejects
certificates that fail their declared privacy targets, preserves the certificate
and dataset hashes, and verifies later copies without placing clinical data
on-chain.

## Method

PrivHealth removes excluded release fields, initializes every quasi-identifier
at its most specific hierarchy level, and iteratively evaluates every valid
one-level generalization. At each iteration it selects the candidate with the
largest marginal reduction in a combined k/l privacy-deficit score per unit of
task-weighted hierarchy loss. Every visited state is also evaluated as a
release checkpoint after suppressing residual unsafe equivalence classes. The
algorithm returns the privacy-valid checkpoint with the lowest combined
generalization and suppression loss.

## Data

Primary planned dataset: Synthea patient and condition CSV exports.

Planned sample sizes: 1,000, 5,000, and 10,000 patient records. The current generated dataset is for software validation only and must not be presented as final experimental evidence.

## Attributes

- Direct identifiers: patient ID, name, birth date, address when available.
- Quasi-identifiers: age, gender, race, marital status, and ZIP code.
- Exact city and state are excluded as redundant raw location fields because
  ZIP code is the sole released geographic quasi-identifier.
- Sensitive attribute: binary hypertension status derived from all recorded
  conditions (`hypertension` or `non_hypertension`).
- Downstream target: presence of a hypertension-related diagnosis. Using the
  same status as the sensitive attribute makes the utility task explicit while
  l-diversity tests protection against homogeneous disclosure of that status.

The final paper must justify each quasi-identifier under the stated linkage threat model and must not imply that all contexts expose the same auxiliary data.

## Compared methods

1. Direct-identifier removal only: diagnostic baseline; it does not promise k/l satisfaction.
2. Fixed generalization followed by suppression.
3. Uniform hierarchy generalization followed by suppression.
4. PrivHealth task-aware adaptive generalization followed by suppression.

## Independent variables

- Dataset size: 1,000; 5,000; 10,000.
- k target: 2; 5; 10.
- l target: 2.
- Method: four methods above.
- Repeated runs: at least 10 timed repetitions after one warm-up; de-identification results are deterministic, while runtimes are summarized by median and P95.

## Outcomes

Privacy:

- achieved minimum equivalence-class size;
- achieved minimum sensitive-value diversity;
- violating-record fraction;
- record-level normalized k/l deficit;
- suppression rate.

Utility:

- weighted normalized hierarchy loss;
- record-weighted information loss, with each suppressed record assigned the
  maximum loss of one;
- macro-F1 of the downstream task;
- F1 retention relative to the original values of the same retained records.

Suppression is also reported independently because a high F1 score on a small,
selected retained subset does not establish preservation of population-level
utility.

Efficiency:

- median execution time;
- P95 execution time;
- number of adaptive search steps.

Blockchain:

- successful rejection of privacy-invalid and metadata-tampered certificates;
- registration success rate for valid certificates;
- median and P95 committed-transaction latency;
- median and P95 ledger-query verification latency;
- integrity verification accuracy for unchanged and modified released files;
- certificate payload size and ledger growth proxy.

## Validity boundaries

- Synthetic records avoid exposing real patient data but do not demonstrate deployment effectiveness in a real clinical institution.
- k-anonymity does not prevent every linkage or inference attack.
- l-diversity addresses one form of attribute homogeneity but does not establish absolute anonymity.
- HIPAA guidance is contextual background, not a compliance certification.
- The downstream classifier is an analytical-utility probe, not a clinical decision-support model.
- Blockchain preserves release evidence but does not itself anonymize clinical
  records or guarantee that a chosen threat model is complete.

## Eight-page allocation

| Section | Target pages |
| --- | ---: |
| Abstract and keywords | 0.3 |
| 1 Introduction | 0.8 |
| 2 Related work and gap | 0.7 |
| 3 PrivHealth method and registry | 1.6 |
| 4 Experimental setup | 1.1 |
| 5 Results and discussion | 1.5 |
| 6 Limitations | 0.3 |
| 7 Conclusion | 0.3 |
| References | 1.0–1.3 |

Planned visual content: one integrated method figure, one privacy–utility plot,
one compact setup table, and one combined privacy/blockchain results table.
