# Prototype validation note — not final paper evidence

Date: 22 July 2026

The current results use 2,000 records produced by the repository's deterministic
demo generator. They validate the implementation and experimental pipeline;
they must not be reported as the final Synthea experiment.

All four unit tests pass. For the 2,000-record validation sample, the adaptive
method satisfied each tested `(k, l)` target without row suppression:

| Target | Achieved | Information loss | F1 retention | Median runtime |
| --- | --- | ---: | ---: | ---: |
| k=2, l=2 | k=8, l=2 | 0.4333 | 0.9945 | 140.0 ms |
| k=5, l=2 | k=8, l=2 | 0.4333 | 0.9945 | 119.8 ms |
| k=10, l=2 | k=10, l=2 | 0.5333 | 0.9995 | 133.2 ms |

At the same sample size, fixed generalization suppressed 58.75%, 80.15%, and
93.95% of records for k=2, k=5, and k=10, respectively. Uniform generalization
retained all records but reached the maximum hierarchy-loss value of one.

These values show that the prototype behaves as intended, not that the research
hypothesis is already confirmed. The final analysis must use official Synthea
exports, repeated runtimes, and the predeclared sample sizes.
