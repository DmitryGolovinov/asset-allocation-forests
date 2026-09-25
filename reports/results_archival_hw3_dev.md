# Results: archival_hw3_dev

Generated from `results/archival_hw3_dev/` (config `2edeb4d0f2a4`, source tree `3f7791215aca`). 234 months, 2003-08-31 to 2023-01-31. Status: previously viewed (original notebook); archival reproduction, no untouched claim. Seeds: [0, 1, 2].

## Table 5 analogue (means over seeds; costs 20 bps per unit turnover)

TO: annualized turnover (%); SD: annualized SD of excess returns (%); CW: cumulative wealth incl. the risk-free rate; SR: annualized Sharpe of excess returns; BE: cost at which net wealth equals EW's net wealth on the same trade schedules (NaN = behind EW at zero cost, inf = no crossing).

| strategy           |   TO_pct |   SD_pct |    CW |    SR |   SR_seed_sd |   MaxDD |   CW_net |   SR_net |   BE_bps |
|:-------------------|---------:|---------:|------:|------:|-------------:|--------:|---------:|---------:|---------:|
| EW                 |   27.051 |    8.536 | 2.789 | 0.524 |        0.000 |  30.629 |    2.755 |    0.516 |  nan     |
| SR                 |   37.782 |    7.516 | 2.852 | 0.599 |        0.000 |  28.388 |    2.805 |    0.588 |  106.833 |
| AAF                |   83.339 |    7.633 | 3.046 | 0.635 |        0.011 |  26.923 |    2.944 |    0.612 |   81.200 |
| AAF_shrunk         |   69.483 |    7.871 | 2.987 | 0.606 |        0.009 |  30.698 |    2.902 |    0.587 |   83.386 |
| AAF_alpha0.5_fixed |   48.893 |    8.002 | 2.919 | 0.582 |        0.005 |  28.794 |    2.859 |    0.569 |  108.506 |
| AAF_band           |   30.470 |    7.655 | 3.036 | 0.631 |        0.010 |  26.620 |    2.994 |    0.622 |  inf     |
| AAF_quarterly      |   44.368 |    7.530 | 3.067 | 0.647 |        0.009 |  26.484 |    3.009 |    0.634 |  289.549 |

## Joint block bootstrap of net Sharpe differences (seed 0, 12-month blocks)

|                             |   diff |   ci_lo |   ci_hi |   p_le_0 |
|:----------------------------|-------:|--------:|--------:|---------:|
| SR_minus_EW                 |  0.071 |  -0.198 |   0.485 |    0.279 |
| AAF_minus_EW                |  0.100 |  -0.081 |   0.347 |    0.132 |
| AAF_shrunk_minus_EW         |  0.071 |  -0.095 |   0.329 |    0.190 |
| AAF_band_minus_EW           |  0.116 |  -0.082 |   0.363 |    0.118 |
| AAF_quarterly_minus_EW      |  0.114 |  -0.055 |   0.351 |    0.096 |
| AAF_alpha0.5_fixed_minus_EW |  0.054 |  -0.032 |   0.170 |    0.105 |
| AAF_shrunk_minus_AAF        | -0.029 |  -0.091 |   0.054 |    0.761 |
| AAF_band_minus_AAF          |  0.016 |  -0.036 |   0.063 |    0.280 |
| AAF_quarterly_minus_AAF     |  0.014 |  -0.011 |   0.038 |    0.129 |
| SR_minus_AAF                | -0.028 |  -0.158 |   0.165 |    0.620 |

## Sequential blocks (net Sharpe, mean over seeds)

| start      |   AAF |   AAF_alpha0.5_fixed |   AAF_band |   AAF_quarterly |   AAF_shrunk |   EW |   SR |
|:-----------|------:|---------------------:|-----------:|----------------:|-------------:|-----:|-----:|
| 2003-08-31 |  0.91 |                 1.00 |       0.92 |            0.91 |         1.04 | 1.08 | 0.91 |
| 2008-08-31 |  0.63 |                 0.55 |       0.62 |            0.63 |         0.49 | 0.47 | 0.54 |
| 2013-08-31 |  0.98 |                 0.72 |       1.01 |            1.00 |         0.98 | 0.46 | 1.13 |
| 2018-08-31 |  0.36 |                 0.39 |       0.38 |            0.41 |         0.36 | 0.40 | 0.32 |

## Leaf-solver and ensemble diagnostics

|                                         |      value |
|:----------------------------------------|-----------:|
| refits                                  |  20        |
| leaf solves (seed 0)                    |   6.28e+05 |
| exact-path fallbacks                    |  11        |
| max |global objective - multistart ref| |   3.49e-16 |
| max global feasibility residual         |   4.65e-16 |
| max (relaxed - equality) objective      |  -4.28e-11 |
| min relaxed var / EW var                |   1        |
| max cond(train covariance)              | 174        |
| mean forest fit seconds                 |   1.38     |

Ex-ante volatility of the averaged forest portfolio relative to the EW target, using each refit's training covariance: mean 0.946, min 0.890, max 1.031. Averaging leaf portfolios that each satisfy the equality lands inside the volatility ball, not on it.

Wealth and weight paths of the archival run are not published: the supplied workbook's redistribution terms are not established.
