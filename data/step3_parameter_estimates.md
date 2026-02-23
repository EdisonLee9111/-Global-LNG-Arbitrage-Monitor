# Step 3 - Parameter Estimates (Auto Generated)

Horizon shown is in *trading days* from today.

## HH_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 3.483676 |
| kappa | 0.006991 |
| theta | 3.165550 |
| sigma | 0.045170 |
| horizon_mean | 3.397805 |
| horizon_std | 0.261039 |
| horizon_p05 | 2.968396 |
| horizon_p95 | 3.827214 |
| gbm_mu_daily | 0.000306 |
| gbm_sigma_daily | 0.014696 |
| gbm_horizon_p05 | 2.988665 |
| gbm_horizon_p95 | 4.133679 |

## TTF_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 10.526310 |
| kappa | 0.032126 |
| theta | 10.398249 |
| sigma | 0.089556 |
| horizon_mean | 10.428419 |
| horizon_std | 0.343363 |
| horizon_p05 | 9.863587 |
| horizon_p95 | 10.993251 |
| gbm_mu_daily | 0.000105 |
| gbm_sigma_daily | 0.008594 |
| gbm_horizon_p05 | 9.603239 |
| gbm_horizon_p95 | 11.608872 |

## JKM_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 13.101669 |
| kappa | 0.095924 |
| theta | 12.194451 |
| sigma | 0.277207 |
| horizon_mean | 12.206558 |
| horizon_std | 0.632831 |
| horizon_p05 | 11.165551 |
| horizon_p95 | 13.247566 |
| gbm_mu_daily | 0.000315 |
| gbm_sigma_daily | 0.022227 |
| gbm_horizon_p05 | 10.283202 |
| gbm_horizon_p95 | 16.794621 |

## Charter_Rate
- Method: **expert_prior**
- Distribution: `lognormal`
- Horizon: 45 days
- Source: `config_fallback`

| Parameter | Value |
| --- | --- |
| s0 | 60000.000000 |
| mu_ln | 10.940850 |
| sigma_ln | 0.350000 |
| sigma_daily | 0.022048 |
| horizon_median | 59347.325818 |
| horizon_p05 | 46530.512544 |
| horizon_p95 | 75694.525790 |

## USD_JPY
- Method: **historical**
- Distribution: `gbm`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 148.563293 |
| mu_daily | 0.000007 |
| sigma_daily | 0.002022 |
| annualized_vol | 0.032091 |
| horizon_mean | 148.610599 |
| horizon_p05 | 145.318791 |
| horizon_p95 | 151.949027 |

## Fuel_Cost
- Method: **expert_prior**
- Distribution: `lognormal`
- Horizon: 45 days
- Source: `config_fallback`

| Parameter | Value |
| --- | --- |
| s0 | 15000.000000 |
| mu_ln | 9.570805 |
| sigma_ln | 0.300000 |
| sigma_daily | 0.018898 |
| horizon_median | 14879.947286 |
| horizon_p05 | 12079.051539 |
| horizon_p95 | 18330.315963 |

## Voyage_Delay
- Method: **expert_prior**
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
