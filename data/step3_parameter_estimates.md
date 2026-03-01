# Step 3 - Parameter Estimates (Auto Generated)

Horizon shown is in *trading days* from today.

## HH_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 3.492257 |
| kappa | 0.006731 |
| theta | 3.177624 |
| sigma | 0.045056 |
| horizon_mean | 3.410037 |
| horizon_std | 0.261755 |
| horizon_p05 | 2.979451 |
| horizon_p95 | 3.840624 |
| gbm_mu_daily | 0.000308 |
| gbm_sigma_daily | 0.014638 |
| gbm_horizon_p05 | 2.998394 |
| gbm_horizon_p95 | 4.141804 |

## TTF_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 10.547970 |
| kappa | 0.030475 |
| theta | 10.396106 |
| sigma | 0.089533 |
| horizon_mean | 10.434643 |
| horizon_std | 0.350788 |
| horizon_p05 | 9.857597 |
| horizon_p95 | 11.011689 |
| gbm_mu_daily | 0.000108 |
| gbm_sigma_daily | 0.008608 |
| gbm_horizon_p05 | 9.622741 |
| gbm_horizon_p95 | 11.635922 |

## JKM_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 13.123328 |
| kappa | 0.086617 |
| theta | 12.191489 |
| sigma | 0.283812 |
| horizon_mean | 12.210394 |
| horizon_std | 0.681752 |
| horizon_p05 | 11.088912 |
| horizon_p95 | 13.331876 |
| gbm_mu_daily | 0.000330 |
| gbm_sigma_daily | 0.022821 |
| gbm_horizon_p05 | 10.233898 |
| gbm_horizon_p95 | 16.934710 |

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
