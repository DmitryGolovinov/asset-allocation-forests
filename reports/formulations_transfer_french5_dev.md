# Leaf formulation: equality versus convex inequality (transfer_french5_dev)

858 months, 1947-07-31 to 2018-12-31, seed 0, base cost 0.002 per unit turnover. Generated from `results/transfer_french5_dev_formulations.json`.

|                                       |   SR_gross |   SR_net |   vol_ann_pct |   mean_ann_pct |   TO_ann_pct |
|:--------------------------------------|-----------:|---------:|--------------:|---------------:|-------------:|
| ('AAF', 'equality (paper)')           |      0.574 |    0.551 |        14.511 |          8.330 |      169.093 |
| ('AAF', 'relaxed (convex)')           |      0.568 |    0.544 |        14.493 |          8.229 |      173.613 |
| ('SR', 'equality (paper)')            |      0.546 |    0.541 |        15.530 |          8.472 |       31.107 |
| ('SR', 'relaxed (convex)')            |      0.546 |    0.541 |        15.530 |          8.472 |       31.107 |
| ('AAF_shrunk', 'equality (paper)')    |      0.555 |    0.550 |        14.521 |          8.065 |       39.064 |
| ('AAF_shrunk', 'relaxed (convex)')    |      0.562 |    0.557 |        14.494 |          8.143 |       29.879 |
| ('AAF_quarterly', 'equality (paper)') |      0.575 |    0.565 |        14.523 |          8.344 |       65.909 |
| ('AAF_quarterly', 'relaxed (convex)') |      0.569 |    0.559 |        14.507 |          8.251 |       70.125 |

Net Sharpe difference, relaxed minus equality (paired 12-month block bootstrap, 95%):

- AAF: -0.007 [-0.018, +0.004]
- SR: n/a: identical under both formulations
- AAF_shrunk: +0.008 [-0.001, +0.018]
- AAF_quarterly: -0.006 [-0.018, +0.006]

Share of leaf solves where the relaxed risk constraint is slack: 20.2%. Mean largest weight: equality 0.416, relaxed 0.420; mean HHI 0.295 vs 0.306.
