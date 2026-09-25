# Leaf formulation: equality versus convex inequality (transfer_french5_final)

91 months, 2019-01-31 to 2026-07-31, seed 0, base cost 0.002 per unit turnover. Generated from `results/transfer_french5_final_formulations.json`.

|                                       |   SR_gross |   SR_net |   vol_ann_pct |   mean_ann_pct |   TO_ann_pct |
|:--------------------------------------|-----------:|---------:|--------------:|---------------:|-------------:|
| ('AAF', 'equality (paper)')           |      0.799 |    0.775 |        14.637 |         11.690 |      178.174 |
| ('AAF', 'relaxed (convex)')           |      0.795 |    0.771 |        14.629 |         11.623 |      175.631 |
| ('SR', 'equality (paper)')            |      0.710 |    0.707 |        14.585 |         10.359 |       27.230 |
| ('SR', 'relaxed (convex)')            |      0.710 |    0.707 |        14.585 |         10.359 |       27.230 |
| ('AAF_shrunk', 'equality (paper)')    |      0.823 |    0.818 |        15.856 |         13.046 |       36.117 |
| ('AAF_shrunk', 'relaxed (convex)')    |      0.831 |    0.828 |        16.016 |         13.306 |       23.957 |
| ('AAF_quarterly', 'equality (paper)') |      0.793 |    0.784 |        14.866 |         11.795 |       68.849 |
| ('AAF_quarterly', 'relaxed (convex)') |      0.787 |    0.777 |        14.867 |         11.696 |       71.494 |

Net Sharpe difference, relaxed minus equality (paired 12-month block bootstrap, 95%):

- AAF: -0.004 [-0.017, +0.014]
- SR: n/a: identical under both formulations
- AAF_shrunk: +0.009 [-0.002, +0.023]
- AAF_quarterly: -0.007 [-0.017, +0.005]

Share of leaf solves where the relaxed risk constraint is slack: 14.4%. Mean largest weight: equality 0.451, relaxed 0.448; mean HHI 0.306 vs 0.305.
