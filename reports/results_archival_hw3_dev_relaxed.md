# Results: archival_hw3_dev_relaxed

Generated from `results/archival_hw3_dev_relaxed/` (config `2edeb4d0f2a4`, source tree `3f7791215aca`). 234 months, 2003-08-31 to 2023-01-31. Status: previously viewed (original notebook); archival reproduction, no untouched claim. Seeds: [0, 1, 2].

## Table 5 analogue (means over seeds; costs 20 bps per unit turnover)

TO: annualized turnover (%); SD: annualized SD of excess returns (%); CW: cumulative wealth incl. the risk-free rate; SR: annualized Sharpe of excess returns; BE: cost at which net wealth equals EW's net wealth on the same trade schedules (NaN = behind EW at zero cost, inf = no crossing).

| strategy           |   TO_pct |   SD_pct |    CW |    SR |   SR_seed_sd |   MaxDD |   CW_net |   SR_net |   BE_bps |
|:-------------------|---------:|---------:|------:|------:|-------------:|--------:|---------:|---------:|---------:|
| EW                 |   27.051 |    8.536 | 2.789 | 0.524 |        0.000 |  30.629 |    2.755 |    0.516 |  nan     |
| SR                 |   37.782 |    7.516 | 2.852 | 0.599 |        0.000 |  28.388 |    2.805 |    0.588 |  106.833 |
| AAF                |   86.369 |    7.609 | 2.976 | 0.621 |        0.007 |  26.698 |    2.873 |    0.598 |   56.468 |
| AAF_shrunk         |   72.050 |    7.847 | 2.916 | 0.592 |        0.001 |  30.690 |    2.830 |    0.572 |   51.387 |
| AAF_alpha0.5_fixed |   50.446 |    7.988 | 2.886 | 0.576 |        0.003 |  28.683 |    2.824 |    0.562 |   75.033 |
| AAF_band           |   34.427 |    7.557 | 3.074 | 0.647 |        0.017 |  24.797 |    3.028 |    0.637 |  777.886 |
| AAF_quarterly      |   46.495 |    7.512 | 2.987 | 0.631 |        0.010 |  26.340 |    2.928 |    0.617 |  180.246 |

## Joint block bootstrap of net Sharpe differences (seed 0, 12-month blocks)

|                             |   diff |   ci_lo |   ci_hi |   p_le_0 |
|:----------------------------|-------:|--------:|--------:|---------:|
| SR_minus_EW                 |  0.071 |  -0.198 |   0.485 |    0.279 |
| AAF_minus_EW                |  0.083 |  -0.098 |   0.328 |    0.184 |
| AAF_shrunk_minus_EW         |  0.058 |  -0.110 |   0.315 |    0.226 |
| AAF_band_minus_EW           |  0.104 |  -0.081 |   0.338 |    0.139 |
| AAF_quarterly_minus_EW      |  0.091 |  -0.082 |   0.322 |    0.150 |
| AAF_alpha0.5_fixed_minus_EW |  0.046 |  -0.041 |   0.162 |    0.141 |
| AAF_shrunk_minus_AAF        | -0.025 |  -0.089 |   0.061 |    0.703 |
| AAF_band_minus_AAF          |  0.022 |  -0.029 |   0.068 |    0.227 |
| AAF_quarterly_minus_AAF     |  0.009 |  -0.015 |   0.030 |    0.234 |
| SR_minus_AAF                | -0.011 |  -0.143 |   0.188 |    0.514 |

## Sequential blocks (net Sharpe, mean over seeds)

| start      |   AAF |   AAF_alpha0.5_fixed |   AAF_band |   AAF_quarterly |   AAF_shrunk |   EW |   SR |
|:-----------|------:|---------------------:|-----------:|----------------:|-------------:|-----:|-----:|
| 2003-08-31 |  0.90 |                 1.00 |       0.89 |            0.90 |         1.04 | 1.08 | 0.91 |
| 2008-08-31 |  0.62 |                 0.54 |       0.70 |            0.63 |         0.49 | 0.47 | 0.54 |
| 2013-08-31 |  0.98 |                 0.71 |       1.03 |            1.00 |         0.98 | 0.46 | 1.13 |
| 2018-08-31 |  0.32 |                 0.37 |       0.34 |            0.36 |         0.32 | 0.40 | 0.32 |

## Leaf-solver and ensemble diagnostics

|                                         |      value |
|:----------------------------------------|-----------:|
| refits                                  |  20        |
| leaf solves (seed 0)                    |   6.3e+05  |
| exact-path fallbacks                    |  10        |
| max |global objective - multistart ref| |   3.49e-16 |
| max global feasibility residual         |   4.65e-16 |
| max (relaxed - equality) objective      |  -4.28e-11 |
| min relaxed var / EW var                |   1        |
| max cond(train covariance)              | 174        |
| mean forest fit seconds                 |   1.37     |

Ex-ante volatility of the averaged forest portfolio relative to the EW target, using each refit's training covariance: mean 0.940, min 0.880, max 1.026. Averaging leaf portfolios that each satisfy the equality lands inside the volatility ball, not on it.

Wealth and weight paths of the archival run are not published: the supplied workbook's redistribution terms are not established.
