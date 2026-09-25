# References

Checked against Crossref metadata on 2026-09-23.

| Source | Role | Implemented | Differs |
|---|---|---|---|
| Bettencourt, Petukhina & Tetereva, *Advancing Markowitz: Asset Allocation Forest*, SSRN 4781685 (supplied PDF, created 2024-04-02) | replicated method | leaf problem (eq. 2, lambda = 0), split rule (eq. 3), forest construction, Table 5 metrics | decile thresholds; corrected leaf solver (both roots, degenerate faces, stable solves); covariance of excess returns; seeds and block uncertainty; shrinkage/band/quarterly extension; French-industry transfer |
| Jagannathan & Ma (2003) | context | long-only constraints as shrinkage (cited by the paper) | |
| Ledoit & Wolf (2008) | context | the paper's Sharpe-ratio test | we report a block bootstrap of Sharpe differences instead |
| Kenneth French Data Library | data | 5 industry portfolios, Fama-French RF | |

Author order: the supplied PDF prints Bettencourt, Petukhina, Tetereva (used here); the SSRN/
Crossref record lists Bettencourt, Tetereva, Petukhina, as does the assignment sheet. The earlier
conference manuscript (FoFI 2024) was not used.

- L. O. Bettencourt, A. Petukhina, A. Tetereva. Advancing Markowitz: Asset Allocation Forest.
  SSRN Working Paper 4781685 (version of 2024-04-02). https://doi.org/10.2139/ssrn.4781685
- R. Jagannathan, T. Ma. Risk Reduction in Large Portfolios: Why Imposing the Wrong Constraints
  Helps. *The Journal of Finance* 58(4), 1651-1683, 2003. https://doi.org/10.1111/1540-6261.00580
- O. Ledoit, M. Wolf. Robust performance hypothesis testing with the Sharpe ratio. *Journal of
  Empirical Finance* 15(5), 850-859, 2008. https://doi.org/10.1016/j.jempfin.2008.03.002
- L. Breiman. Random Forests. *Machine Learning* 45(1), 5-32, 2001.
  https://doi.org/10.1023/A:1010933404324
- K. R. French. Data Library, https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
  (files retrieved 2026-09-24 01:03 UTC).
