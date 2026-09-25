# Leaf formulation: equality versus convex inequality (archival_hw3_dev)

234 months, 2003-08-31 to 2023-01-31, seed 0, base cost 0.002 per unit turnover. Generated from `results/archival_hw3_dev_formulations.json`.

|                                       |   SR_gross |   SR_net |   vol_ann_pct |   mean_ann_pct |   TO_ann_pct |
|:--------------------------------------|-----------:|---------:|--------------:|---------------:|-------------:|
| ('AAF', 'equality (paper)')           |      0.639 |    0.616 |         7.605 |          4.859 |       82.844 |
| ('AAF', 'relaxed (convex)')           |      0.623 |    0.599 |         7.574 |          4.718 |       86.469 |
| ('SR', 'equality (paper)')            |      0.599 |    0.588 |         7.516 |          4.502 |       37.782 |
| ('SR', 'relaxed (convex)')            |      0.599 |    0.588 |         7.516 |          4.502 |       37.782 |
| ('AAF_shrunk', 'equality (paper)')    |      0.606 |    0.588 |         7.858 |          4.759 |       67.011 |
| ('AAF_shrunk', 'relaxed (convex)')    |      0.593 |    0.574 |         7.819 |          4.639 |       69.449 |
| ('AAF_quarterly', 'equality (paper)') |      0.643 |    0.630 |         7.534 |          4.845 |       42.715 |
| ('AAF_quarterly', 'relaxed (convex)') |      0.621 |    0.608 |         7.529 |          4.676 |       44.686 |

Net Sharpe difference, relaxed minus equality (paired 12-month block bootstrap, 95%):

- AAF: -0.017 [-0.036, -0.003]
- SR: n/a: identical under both formulations
- AAF_shrunk: -0.013 [-0.030, -0.001]
- AAF_quarterly: -0.023 [-0.046, -0.006]

Share of leaf solves where the relaxed risk constraint is slack: 3.5%. Mean largest weight: equality 0.352, relaxed 0.361; mean HHI 0.248 vs 0.251.
