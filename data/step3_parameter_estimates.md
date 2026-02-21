# Step 3 - Parameter Estimates (Auto Generated)

Horizon shown is in *trading days* from today.

## HH_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 3.001790 |
| kappa | 0.030000 |
| theta | 3.000659 |
| sigma | 0.055118 |
| horizon_mean | 3.000952 |
| horizon_std | 0.217325 |
| horizon_p05 | 2.643453 |
| horizon_p95 | 3.358451 |
| gbm_mu_daily | 0.000290 |
| gbm_sigma_daily | 0.026211 |
| gbm_horizon_p05 | 2.242406 |
| gbm_horizon_p95 | 3.998894 |

## TTF_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 9.111154 |
| kappa | 0.030000 |
| theta | 9.021240 |
| sigma | 0.177588 |
| horizon_mean | 9.044549 |
| horizon_std | 0.700214 |
| horizon_p05 | 7.892698 |
| horizon_p95 | 10.196400 |
| gbm_mu_daily | 0.000417 |
| gbm_sigma_daily | 0.028934 |
| gbm_horizon_p05 | 6.620467 |
| gbm_horizon_p95 | 12.537588 |

## JKM_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 10.088620 |
| kappa | 0.030000 |
| theta | 9.968276 |
| sigma | 0.188124 |
| horizon_mean | 9.999474 |
| horizon_std | 0.741756 |
| horizon_p05 | 8.779286 |
| horizon_p95 | 11.219662 |
| gbm_mu_daily | 0.000410 |
| gbm_sigma_daily | 0.027048 |
| gbm_horizon_p05 | 7.500247 |
| gbm_horizon_p95 | 13.624588 |

## Charter_Rate
- Method: **historical**
- Distribution: `lognormal`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 60000.000000 |
| mu_ln | 10.940850 |
| sigma_ln | 0.350000 |
| sigma_daily | 0.022048 |
| horizon_median | 59347.325818 |
| horizon_p05 | 46530.512544 |
| horizon_p95 | 75694.525790 |
| source | 0.000000 |

## USD_JPY
- Method: **historical**
- Distribution: `gbm`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 148.819647 |
| mu_daily | 0.000311 |
| sigma_daily | 0.029788 |
| annualized_vol | 0.472872 |
| horizon_mean | 150.918549 |
| horizon_p05 | 106.491336 |
| horizon_p95 | 205.508420 |

## Fuel_Cost
- Method: **historical**
- Distribution: `lognormal`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 15000.000000 |
| mu_ln | 9.570805 |
| sigma_ln | 0.300000 |
| sigma_daily | 0.018898 |
| horizon_median | 14879.947286 |
| horizon_p05 | 12079.051539 |
| horizon_p95 | 18330.315963 |
| source | 0.000000 |

## Voyage_Delay
- Method: **historical**
- Distribution: `gamma`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| gamma_k | 2.000000 |
| gamma_theta | 1.500000 |
| panama_shift | 3.000000 |
| mean_delay | 6.000000 |

## BOG_Rate
- Method: **manual**
- Distribution: `triangular`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| low | 0.000800 |
| mode | 0.001499 |
| high | 0.001500 |
| mean | 0.001266 |
